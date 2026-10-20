"""What the rules know about one incident: the inputs every recommendation shows (FR-C-11).

Everything is read from existing data: the incident and its reports (phase 3–5), the AI extraction of each report,
vision detections (phase 6), registered institutions nearby (phase 4), the operational level (phase 5), and the
weather and spread forecast of phase 7 (``modules/weather``, ``modules/forecast``) through the small
``Environment`` interface below, so this module never depends on how those tables are laid out.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import Analysis
from app.modules.geo.models import Gouvernorat
from app.modules.ops.domain import ACTIVE_ASSIGNMENT
from app.modules.ops.models import Assignment, Incident, Resource
from app.modules.orgs import sites
from app.modules.reports.domain import Status
from app.modules.reports.models import Media, Report
from app.modules.streams.domain import ALERT_LABELS
from app.modules.streams.models import LiveStream, StreamDetection

# Open incidents of the same gouvernorat counted for an escalation suggestion.
BUSY_WINDOW = timedelta(hours=24)
BUSY_SEVERITY = 70


@dataclass(frozen=True, slots=True)
class WeatherAtPoint:
    """Weather at the incident (nearest grid point of the weather layer)."""

    observed_at: datetime | None
    wind_kmh: float | None = None
    gust_kmh: float | None = None
    wind_dir_deg: float | None = None
    temperature_c: float | None = None
    humidity_pct: float | None = None
    rain_1h_mm: float | None = None
    rain_24h_mm: float | None = None
    fire_danger: str | None = None  # low | moderate | high | very_high | extreme
    rain_level: str | None = None  # none | watch | warning
    simulated: bool = False

    def as_inputs(self) -> dict[str, Any]:
        return {
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
            "wind_kmh": self.wind_kmh,
            "gust_kmh": self.gust_kmh,
            "wind_dir_deg": self.wind_dir_deg,
            "temperature_c": self.temperature_c,
            "humidity_pct": self.humidity_pct,
            "rain_1h_mm": self.rain_1h_mm,
            "rain_24h_mm": self.rain_24h_mm,
            "fire_danger": self.fire_danger,
            "rain_level": self.rain_level,
            "simulated": self.simulated,
        }


@dataclass(frozen=True, slots=True)
class SpreadForecast:
    """Latest spread forecast run of the incident (fire: largest horizon; flood: advisory level)."""

    forecast_id: str
    kind: str  # fire | flood
    generated_at: datetime | None
    max_area_ha: float | None = None
    horizon_min: int | None = None
    level: str | None = None
    rate_of_spread_m_min: float | None = None
    # GeoJSON geometry of the largest polygon (alert area).
    geometry: dict[str, Any] | None = None
    simulated: bool = False

    def as_inputs(self) -> dict[str, Any]:
        return {
            "forecast_id": self.forecast_id,
            "kind": self.kind,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "max_area_ha": self.max_area_ha,
            "horizon_min": self.horizon_min,
            "level": self.level,
            "rate_of_spread_m_min": self.rate_of_spread_m_min,
            "simulated": self.simulated,
        }


class Environment(Protocol):
    """Weather and forecast data of phase 7, read through whatever the weather/forecast modules expose."""

    async def weather_at(self, session: AsyncSession, lat: float, lon: float) -> WeatherAtPoint | None: ...

    async def latest_forecast(self, session: AsyncSession, incident_id: uuid.UUID) -> SpreadForecast | None: ...

    async def pending_weather_suggestions(self, session: AsyncSession, gouvernorat_code: int) -> int: ...


class NoEnvironment:
    """No weather layer or forecast available: those inputs are reported as missing."""

    async def weather_at(self, session: AsyncSession, lat: float, lon: float) -> WeatherAtPoint | None:
        return None

    async def latest_forecast(self, session: AsyncSession, incident_id: uuid.UUID) -> SpreadForecast | None:
        return None

    async def pending_weather_suggestions(self, session: AsyncSession, gouvernorat_code: int) -> int:
        return 0


_environment: Environment | None = None


def get_environment() -> Environment:
    if _environment is not None:
        return _environment
    from app.modules.decision.environment import default_environment

    return default_environment()


def set_environment(environment: Environment | None) -> None:
    """Used by tests to inject weather and forecast values."""
    global _environment
    _environment = environment


@dataclass(slots=True)
class Situation:
    incident: Incident
    lat: float | None
    lon: float | None
    gouvernorat: dict[str, str] | None
    report_count: int = 0
    reporter_count: int = 0
    severity: int | None = None
    lives_at_risk: bool = False
    people_trapped: bool = False
    injured: int = 0
    deaths: bool = False
    hazards: list[str] = field(default_factory=list)
    people_detected: int = 0
    vision_fire: dict[str, Any] | None = None
    sensitive_site: dict[str, Any] | None = None
    engaged: dict[str, int] = field(default_factory=dict)
    busy_incidents: int = 0
    weather: WeatherAtPoint | None = None
    forecast: SpreadForecast | None = None
    weather_suggestions: int = 0

    @property
    def category(self) -> str:
        return self.incident.category

    @property
    def classification(self) -> str | None:
        return self.incident.classification

    @property
    def op_level(self) -> str:
        return self.incident.op_level.value

    @property
    def simulated(self) -> bool:
        return bool((self.weather and self.weather.simulated) or (self.forecast and self.forecast.simulated))

    def as_inputs(self) -> dict[str, Any]:
        """The shared inputs, shown with every recommendation."""
        return {
            "category": self.category,
            "classification": self.classification,
            "priority": self.severity,
            "reports": self.report_count,
            "reporters": self.reporter_count,
            "lives_at_risk": self.lives_at_risk,
            "people_trapped": self.people_trapped,
            "injured": self.injured,
            "people_detected": self.people_detected,
            "op_level": self.op_level,
            "hazards": self.hazards,
        }


async def _point(session: AsyncSession, incident: Incident) -> tuple[float | None, float | None]:
    row = (
        await session.execute(
            select(func.ST_Y(cast(Incident.centroid, Geometry)), func.ST_X(cast(Incident.centroid, Geometry))).where(
                Incident.id == incident.id
            )
        )
    ).one()
    return (float(row[0]), float(row[1])) if row[0] is not None else (None, None)


async def _people_detected(session: AsyncSession, report_ids: list[uuid.UUID]) -> tuple[int, dict[str, Any] | None]:
    """Most persons seen in one analysed frame or image of the incident's reports, and the strongest confirmed fire
    or smoke."""
    if not report_ids:
        return 0, None
    owned = StreamDetection.stream_id.in_(
        select(LiveStream.id).where(LiveStream.report_id.in_(report_ids))
    ) | StreamDetection.media_id.in_(select(Media.id).where(Media.report_id.in_(report_ids)))
    persons = await session.scalar(
        select(func.max(func.jsonb_array_length(StreamDetection.boxes))).where(owned, StreamDetection.label == "person")
    )
    fire = (
        await session.execute(
            select(StreamDetection.label, StreamDetection.confidence)
            .where(owned, StreamDetection.confirmed.is_(True), StreamDetection.label.in_(ALERT_LABELS))
            .order_by(StreamDetection.confidence.desc())
            .limit(1)
        )
    ).first()
    vision = {"label": fire[0], "confidence": round(float(fire[1]), 2)} if fire else None
    return int(persons or 0), vision


async def gather(session: AsyncSession, incident: Incident, environment: Environment | None = None) -> Situation:
    environment = environment or get_environment()
    lat, lon = await _point(session, incident)
    gouvernorat = None
    if incident.gouvernorat_code is not None:
        g = await session.get(Gouvernorat, incident.gouvernorat_code)
        if g is not None:
            gouvernorat = {"code": str(g.code), "ar": g.name_ar, "fr": g.name_fr}
    situation = Situation(incident=incident, lat=lat, lon=lon, gouvernorat=gouvernorat)

    members = list(
        (
            await session.execute(
                select(Report, Analysis)
                .outerjoin(Analysis, Analysis.report_id == Report.id)
                .where(Report.incident_id == incident.id, Report.status != Status.REJECTED.value)
            )
        ).all()
    )
    situation.report_count = len(members)
    situation.reporter_count = len({r.user_id for r, _ in members})
    situation.severity = incident.severity
    hazards: set[str] = set()
    for _, analysis in members:
        ex = analysis.extraction if analysis is not None else None
        if not ex:
            continue
        situation.lives_at_risk |= bool(ex.get("lives_at_risk"))
        situation.people_trapped |= bool(ex.get("people_trapped"))
        situation.deaths |= bool(ex.get("deaths_reported"))
        situation.injured = max(situation.injured, int(ex.get("injured_count") or 0))
        hazards.update(str(h) for h in ex.get("hazards") or [])
    situation.lives_at_risk |= situation.people_trapped or situation.deaths
    situation.hazards = sorted(hazards)
    situation.people_detected, situation.vision_fire = await _people_detected(session, [r.id for r, _ in members])
    if incident.centroid is not None:
        site = await sites.nearest(
            session, select(Incident.centroid).where(Incident.id == incident.id).scalar_subquery()
        )
        situation.sensitive_site = {"value": site[0], **site[1]} if site else None

    engaged = (
        await session.execute(
            select(Resource.kind, func.count())
            .join(Assignment, Assignment.resource_id == Resource.id)
            .where(Assignment.incident_id == incident.id, Assignment.status.in_(ACTIVE_ASSIGNMENT))
            .group_by(Resource.kind)
        )
    ).all()
    situation.engaged = {kind: int(n) for kind, n in engaged}
    if incident.gouvernorat_code is not None:
        situation.busy_incidents = int(
            await session.scalar(
                select(func.count()).where(
                    Incident.gouvernorat_code == incident.gouvernorat_code,
                    Incident.status == "open",
                    Incident.id != incident.id,
                    Incident.severity >= BUSY_SEVERITY,
                    Incident.opened_at >= datetime.now(UTC) - BUSY_WINDOW,
                )
            )
            or 0
        )
        situation.weather_suggestions = await environment.pending_weather_suggestions(
            session, incident.gouvernorat_code
        )
    if lat is not None and lon is not None:
        situation.weather = await environment.weather_at(session, lat, lon)
    situation.forecast = await environment.latest_forecast(session, incident.id)
    return situation
