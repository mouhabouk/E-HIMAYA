"""The four screens the menu of 20 systems lacked (Yamen 2026-11-13, «الحصر العميق للخصائص الوظيفية»).

* ``GET /staff/vision/overview`` (system 7): the fire, smoke and person detections of the live streams, the towers,
  the drones and the reports' images, with a first estimate of the danger. It helps the decision and never alerts by
  itself: the alert stays with a human (FR-C-11).
* ``GET /staff/forecast/overview`` (system 5): the fire danger (FWI) and the heavy rain of the next hours per
  gouvernorat, and the last spread and flood runs of the incidents.
* ``GET /staff/citizens/overview`` (system 17): figures about the citizens per gouvernorat, never an identity.
* ``GET /staff/admin-board/overview`` (system 19): the mother board of the national system administrator: the health
  of the services, the accounts, the rules on the features and the last changes.

Each answer stays in the caller's scope: a regional account sees its gouvernorat only.
"""

import asyncio
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import as_system, get_session
from app.core.security import Principal, Role, require_roles
from app.modules.appinfo.models import AppRating
from app.modules.audit.models import AuditLog
from app.modules.features import registry
from app.modules.features.models import FeatureRule
from app.modules.forecast.models import ForecastRun
from app.modules.identity.models import Account, AccountKind
from app.modules.ops.models import Incident
from app.modules.reports.models import Media, Report
from app.modules.reports.staff_router import READ_ROLES
from app.modules.streams.models import LiveStream, StreamDetection
from app.modules.volunteers.models import Volunteer
from app.modules.weather.fwi import DANGER_RANK, FireDanger
from app.modules.weather.models import GridPoint, Observation
from app.modules.weather.signals import RAIN_VALUES

router = APIRouter(prefix="/api/v1/staff", tags=["staff", "boards"])
Session = Annotated[AsyncSession, Depends(get_session)]
StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]


def _scope(principal: Principal) -> int | None:
    """The gouvernorat a regional caller is held to; None for a national one."""
    return None if principal.is_national else principal.gouvernorat_code


# ---------------------------------------------------------------- 7. image and video analysis


def danger(label: str, confidence: float, confirmed: bool, alert_at: float) -> str:
    """A first estimate of the danger of one detection (the commander's aid, never an alert by itself)."""
    if label == "fire" and confirmed:
        return "high"
    if label in ("fire", "smoke") and (confirmed or confidence >= alert_at):
        return "medium"
    return "low"


@router.get("/vision/overview")
async def vision_overview(
    principal: StaffReader,
    session: Session,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
    limit: Annotated[int, Query(ge=1, le=200)] = 60,
) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(hours=hours)
    scope = _scope(principal)
    alert_at = get_settings().vision_alert_confidence
    gov = func.coalesce(LiveStream.gouvernorat_code, Report.gouvernorat_code)
    query = (
        select(StreamDetection, LiveStream.source, LiveStream.label, LiveStream.report_id, Media.report_id, gov)
        .outerjoin(LiveStream, LiveStream.id == StreamDetection.stream_id)
        .outerjoin(Media, Media.id == StreamDetection.media_id)
        .outerjoin(Report, Report.id == func.coalesce(Media.report_id, LiveStream.report_id))
        .where(StreamDetection.at >= since)
        .order_by(StreamDetection.at.desc())
    )
    if scope is not None:
        query = query.where(gov == scope)
    rows = (await session.execute(query.limit(2000))).all()
    counts: Counter[str] = Counter()
    confirmed = 0
    levels: Counter[str] = Counter()
    items: list[dict[str, Any]] = []
    for det, source, label, stream_report, media_report, gouvernorat in rows:
        counts[det.label] += 1
        confirmed += int(det.confirmed)
        level = danger(det.label, det.confidence, det.confirmed, alert_at)
        levels[level] += 1
        if len(items) < limit:
            items.append(
                {
                    "at": det.at.isoformat(),
                    "label": det.label,
                    "confidence": round(det.confidence, 3),
                    "confirmed": det.confirmed,
                    "danger": level,
                    "origin": "report_image" if det.media_id else (source or "stream"),
                    "stream_id": str(det.stream_id) if det.stream_id else None,
                    "stream_label": label,
                    "report_id": str(media_report or stream_report) if (media_report or stream_report) else None,
                    "gouvernorat_code": gouvernorat,
                    "model": det.model,
                }
            )
    watching_q = select(func.count()).select_from(LiveStream).where(LiveStream.vision_state == "watching")
    if scope is not None:
        watching_q = watching_q.where(LiveStream.gouvernorat_code == scope)
    return {
        "hours": hours,
        "counts": {k: counts.get(k, 0) for k in ("fire", "smoke", "person")},
        "confirmed": confirmed,
        "danger": {k: levels.get(k, 0) for k in ("high", "medium", "low")},
        "watching": int(await session.scalar(watching_q) or 0),
        "alert_confidence": alert_at,
        "items": items,
    }


# ---------------------------------------------------------------- 5. forecasting


@router.get("/forecast/overview")
async def forecast_overview(
    principal: StaffReader,
    session: Session,
    hours: Annotated[int, Query(ge=1, le=48)] = 48,
) -> dict[str, Any]:
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    scope = _scope(principal)
    query = (
        select(
            GridPoint.gouvernorat_code,
            Observation.at,
            Observation.fwi,
            Observation.fire_danger,
            Observation.heavy_rain,
            Observation.precipitation_24h_mm,
            Observation.wind_gust_kmh,
            GridPoint.simulated,
        )
        .join(Observation, Observation.point_id == GridPoint.id)
        .where(and_(Observation.at >= now, Observation.at <= now + timedelta(hours=hours)))
        .where(GridPoint.gouvernorat_code.is_not(None))
    )
    if scope is not None:
        query = query.where(GridPoint.gouvernorat_code == scope)
    by_gov: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "fwi": None,
            "fire_danger": None,
            "fire_at": None,
            "rain": "none",
            "rain_24h_mm": None,
            "gust_kmh": None,
        }
    )
    simulated = False
    for gouvernorat, at, fwi, fire_danger, rain, rain24, gust, sim in (await session.execute(query)).all():
        simulated = simulated or sim
        if gouvernorat is None:
            continue
        g = by_gov[gouvernorat]
        if fwi is not None and (g["fwi"] is None or fwi > g["fwi"]):
            g["fwi"], g["fire_at"] = round(fwi, 1), at.isoformat()
        if fire_danger and (
            g["fire_danger"] is None or DANGER_RANK[FireDanger(fire_danger)] > DANGER_RANK[FireDanger(g["fire_danger"])]
        ):
            g["fire_danger"] = fire_danger
        if RAIN_VALUES.get(rain, 0) > RAIN_VALUES.get(g["rain"], 0):
            g["rain"] = rain
        if rain24 is not None and (g["rain_24h_mm"] is None or rain24 > g["rain_24h_mm"]):
            g["rain_24h_mm"] = round(rain24, 1)
        if gust is not None and (g["gust_kmh"] is None or gust > g["gust_kmh"]):
            g["gust_kmh"] = round(gust, 1)
    runs_q = (
        select(ForecastRun, Incident.gouvernorat_code, Incident.title)
        .join(Incident, Incident.id == ForecastRun.incident_id)
        .order_by(ForecastRun.created_at.desc())
        .limit(20)
    )
    if scope is not None:
        runs_q = runs_q.where(Incident.gouvernorat_code == scope)
    runs = [
        {
            "id": str(run.id),
            "incident_id": str(run.incident_id),
            "incident_title": title,
            "gouvernorat_code": gouvernorat,
            "kind": run.kind,
            "model": run.model,
            "at": run.created_at.isoformat(),
            "simulated": run.simulated,
            "summary": {k: v for k, v in run.result.items() if isinstance(v, int | float | str)},
        }
        for run, gouvernorat, title in (await session.execute(runs_q)).all()
    ]
    rows = [{"gouvernorat_code": code, **values} for code, values in sorted(by_gov.items())]
    rows.sort(key=lambda r: -(r["fwi"] or 0))
    return {"hours": hours, "from": now.isoformat(), "simulated": simulated, "gouvernorats": rows, "runs": runs}


# ---------------------------------------------------------------- 17. citizens


@router.get("/citizens/overview")
async def citizens_overview(
    principal: StaffReader,
    session: Session,
    days: Annotated[int, Query(ge=7, le=365)] = 90,
) -> dict[str, Any]:
    """Figures about the citizens, never an identity: reporters, reports kept and rejected, volunteers, the app's
    rating. A gouvernorat is the place of the report (a citizen's account has no gouvernorat)."""
    since = datetime.now(UTC) - timedelta(days=days)
    scope = _scope(principal)
    report_q = (
        select(
            Report.gouvernorat_code,
            func.count(func.distinct(Report.user_id)),
            func.count(),
            func.count().filter(Report.status == "rejected"),
            func.count().filter(Report.status.in_(("intervened", "ongoing", "closed"))),
        )
        .where(Report.created_at >= since, Report.source != "room", Report.gouvernorat_code.is_not(None))
        .group_by(Report.gouvernorat_code)
    )
    vol_q = select(Volunteer.gouvernorat_code, func.count()).where(Volunteer.status == "approved")
    if scope is not None:
        report_q = report_q.where(Report.gouvernorat_code == scope)
        vol_q = vol_q.where(Volunteer.gouvernorat_code == scope)
    volunteers: dict[int, int] = {
        int(code): int(n) for code, n in (await session.execute(vol_q.group_by(Volunteer.gouvernorat_code))).all()
    }
    rows: list[dict[str, int]] = []
    for code, reporters, reports, rejected, kept in (await session.execute(report_q)).all():
        if code is None:
            continue
        rows.append(
            {
                "gouvernorat_code": code,
                "reporters": reporters,
                "reports": reports,
                "rejected": rejected,
                "kept": kept,
                "volunteers": int(volunteers.get(code, 0)),
            }
        )
    for code, n in volunteers.items():
        if not any(r["gouvernorat_code"] == code for r in rows):
            rows.append(
                {"gouvernorat_code": code, "reporters": 0, "reports": 0, "rejected": 0, "kept": 0, "volunteers": int(n)}
            )
    rows.sort(key=lambda r: -r["reports"])
    national: dict[str, Any] = {}
    if scope is None:
        accounts = dict((await session.execute(select(Account.kind, func.count()).group_by(Account.kind))).all())
        rating = (
            await session.execute(select(func.avg(AppRating.stars), func.count()).where(AppRating.created_at >= since))
        ).one()
        national = {
            "citizens": int(accounts.get(AccountKind.CITIZEN, 0)),
            "anonymous": int(accounts.get(AccountKind.ANONYMOUS, 0)),
            "organizations": int(accounts.get(AccountKind.ORGANIZATION, 0)),
            "rating": round(float(rating[0]), 2) if rating[0] is not None else None,
            "ratings": int(rating[1]),
        }
    return {"days": days, "national": national, "gouvernorats": rows}


# ---------------------------------------------------------------- 19. the administrator's mother board


async def _administrator(principal: Annotated[Principal, Depends(require_roles(Role.SYSADMIN))]) -> Principal:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")
    return principal


async def _probe(url: str | None) -> str:
    """A service the API calls, reached or not (its own health page, 3 s at most); not configured = in simulation."""
    if not url:
        return "not_configured"
    import httpx

    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(url.rstrip("/") + "/health")
        return "ok" if r.status_code < 500 else "error"
    except Exception:
        return "unreachable"


@router.get("/admin-board/overview")
async def admin_board(principal: Annotated[Principal, Depends(_administrator)], session: Session) -> dict[str, Any]:
    settings = get_settings()
    now = datetime.now(UTC)
    week = now - timedelta(days=7)
    probes = await asyncio.gather(
        _probe(settings.ai_service_url), _probe(settings.vision_service_url), _probe(settings.telephony_ari_url)
    )
    async with as_system(session):
        await session.execute(text("SELECT 1"))
        accounts = dict(
            (
                await session.execute(
                    select(Account.kind, func.count()).where(Account.created_at >= week).group_by(Account.kind)
                )
            ).all()
        )
        rules = list(
            await session.scalars(
                select(FeatureRule).where(
                    FeatureRule.revoked_at.is_(None), (FeatureRule.ends_at.is_(None)) | (FeatureRule.ends_at > now)
                )
            )
        )
        recent = list(
            await session.scalars(
                select(AuditLog)
                .where(AuditLog.action.like("features.%") | AuditLog.action.like("settings.%"))
                .order_by(AuditLog.at.desc())
                .limit(15)
            )
        )
    systems = {s.key: s for s in registry.get().systems}
    on_systems = [r for r in rules if r.feature_key.startswith(registry.SYSTEM_PREFIX)]
    return {
        "services": {
            "database": "ok",
            "ai": probes[0],
            "vision": probes[1],
            "telephony": probes[2],
            "notifications": "real" if settings.notify_real_send else "simulated",
        },
        "accounts_week": {k.value: int(v) for k, v in accounts.items()},
        "rules": {
            "grants": sum(1 for r in rules if r.effect == "grant"),
            "hidden": sum(1 for r in rules if r.effect == "hide" and r not in on_systems),
            "assignments": len({r.profile_assignment_id for r in rules if r.profile_assignment_id}),
        },
        "systems": [
            {
                "key": r.feature_key.removeprefix(registry.SYSTEM_PREFIX),
                "number": systems[k].number
                if (k := r.feature_key.removeprefix(registry.SYSTEM_PREFIX)) in systems
                else None,
                "effect": r.effect,
                "target_kind": r.target_kind,
                "target": r.target,
                "message": r.message,
                "ends_at": r.ends_at.isoformat() if r.ends_at else None,
            }
            for r in on_systems
        ],
        "recent": [
            {"at": e.at.isoformat(), "action": e.action, "target": e.target, "reason": e.reason} for e in recent
        ],
    }
