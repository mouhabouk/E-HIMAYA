"""Coastal safety endpoints (phase L1b, docs/phase-l/design-l1b-coastal.md §3).

Public: the beaches of the day with their colour and its reasons (the phone keeps them to warn near a dangerous beach,
computed on the phone), one beach with four days and its card, and the anonymous "I am at this beach".
Staff: the coastal dashboard (indicators, top 10, by gouvernorat, heat maps), the alerts of the day with their
acknowledgement, the daily bulletin (PDF), and the declared rules. A regional account sees its own gouvernorat only.
The beaches layer keeps its own visibility (L1a): a reader who may not see it gets 404.
"""

import html
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system, get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.coastal import marine, risk, schemas, service
from app.modules.coastal.models import Beach, BeachDay, CoastalAlert, CoastalSettings
from app.modules.geo.models import Gouvernorat, Layer, LayerFeature
from app.modules.layers import access
from app.modules.layers.service import LAT, LON, public_place
from app.modules.reports.domain import Category, Status
from app.modules.reports.models import Report
from app.modules.reports.staff_router import READ_ROLES
from app.modules.weather import service as weather

public_router = APIRouter(prefix="/api/v1/coastal", tags=["coastal"])
router = APIRouter(prefix="/api/v1/staff/coastal", tags=["staff", "coastal"])
Session = Annotated[AsyncSession, Depends(get_session)]
EDITOR_ROLES = (Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)
StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.CONTENT_EDITOR, Role.SYSADMIN))]
RuleEditor = Annotated[Principal, Depends(require_roles(*EDITOR_ROLES))]
Lang = Literal["ar", "fr", "en"]
WARN_RADIUS_M = 1000
# The beach card (PLAGES_MASTER, design §1.3), in display order; each column may carry its source and date in the
# columns "<name>_source" and "<name>_date" of the file (or set by hand on the layer page).
CARD_FIELDS = (
    "classification",
    "blue_flag",
    "guarded",
    "guard_hours",
    "sand",
    "slope",
    "depth",
    "currents",
    "crowd",
    "usage",
    "peak_season",
    "water_quality",
)
TOURISTIC = ("touristic", "international")
CROWD_ORDER = {"high": 0, "medium": 1, "low": 2}
LENGTH = func.coalesce(
    func.ST_Length(LayerFeature.shape),
    func.ST_Perimeter(LayerFeature.shape) / 2,
)


def _day(day: date | None) -> date:
    return day or service.today_in_tunis(datetime.now(UTC))


async def _layer_for(session: AsyncSession, principal: Principal | None) -> Layer:
    async with as_system(session):
        layer = await service.beach_layer(session)
    if layer is None or not access.sees(principal, layer):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "layer_not_found")
    return layer


def _attribution(simulated: bool) -> list[dict[str, str] | str]:
    if simulated:
        return [marine.SIM_ATTRIBUTION, weather.attribution(True)]
    return [marine.get_provider().attribution(), weather.attribution(False)]


def _beach_out(
    feature: LayerFeature, lat: float, lon: float, row: BeachDay | None, present: int | None
) -> schemas.BeachOut:
    props = feature.props or {}
    inputs = row.inputs if row else {}
    guarded = props.get("guarded")
    return schemas.BeachOut(
        id=str(feature.id),
        name=feature.name,
        lat=lat,
        lon=lon,
        gouvernorat_code=feature.gouvernorat_code,
        level=row.level if row else None,
        score=row.score if row else None,
        factors=[schemas.Factor.model_validate(f) for f in (row.factors if row else [])],
        wave_height_m=inputs.get("wave_height_m"),
        sea_temp_c=inputs.get("sea_temp_c"),
        current_kmh=inputs.get("current_kmh"),
        classification=props.get("classification"),
        guarded=True if inputs.get("guarded_by") else service.flag(guarded),
        crowd=props.get("crowd"),
        present=present,
    )


async def _rows(
    session: AsyncSession, layer: Layer, day: date, public: bool, gouvernorat: int | None = None
) -> list[tuple[LayerFeature, float, float, BeachDay | None]]:
    query = (
        select(LayerFeature, LAT, LON, BeachDay)
        .join(Beach, Beach.feature_id == LayerFeature.id)
        .outerjoin(BeachDay, (BeachDay.feature_id == LayerFeature.id) & (BeachDay.day == day))
        .where(LayerFeature.layer_id == layer.id, LayerFeature.deleted_at.is_(None))
        .order_by(LayerFeature.name, LayerFeature.id)
    )
    if public:
        query = query.where(public_place())
    if gouvernorat is not None:
        query = query.where(LayerFeature.gouvernorat_code == gouvernorat)
    return [(r[0], float(r[1]), float(r[2]), r[3]) for r in (await session.execute(query)).all()]


def _computed(rows: list[tuple[LayerFeature, float, float, BeachDay | None]]) -> tuple[datetime | None, bool]:
    days = [r[3] for r in rows if r[3] is not None]
    if not days:
        return None, False
    return max(d.computed_at for d in days), any(d.simulated for d in days)


# ---------------------------------------------------------------- public


@public_router.get("/beaches", response_model=schemas.BeachesOut)
async def public_beaches(
    session: Session, response: Response, day: Annotated[date | None, Query()] = None
) -> schemas.BeachesOut:
    layer = await _layer_for(session, None)
    rows = await _rows(session, layer, _day(day), public=True)
    computed_at, simulated = _computed(rows)
    response.headers["Cache-Control"] = "public, max-age=900"
    return schemas.BeachesOut(
        day=_day(day),
        computed_at=computed_at,
        simulated=simulated,
        attribution=_attribution(simulated),
        warn_radius_m=WARN_RADIUS_M,
        items=[_beach_out(f, lat, lon, r, None) for f, lat, lon, r in rows],
    )


async def _detail(session: AsyncSession, principal: Principal | None, feature_id: uuid.UUID) -> schemas.BeachDetail:
    layer = await _layer_for(session, principal)
    query = (
        select(LayerFeature, LAT, LON, LENGTH, Beach.seaward_deg)
        .join(Beach, Beach.feature_id == LayerFeature.id)
        .where(LayerFeature.id == feature_id, LayerFeature.layer_id == layer.id, LayerFeature.deleted_at.is_(None))
    )
    if principal is None or not principal.is_staff:
        query = query.where(public_place())
    found = (await session.execute(query)).first()
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "beach_not_found")
    feature, lat, lon, length, seaward = found
    if principal is not None and principal.is_staff and not principal.is_national:
        if feature.gouvernorat_code != principal.gouvernorat_code:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "beach_not_found")
    today = service.today_in_tunis(datetime.now(UTC))
    days = (
        await session.scalars(
            select(BeachDay)
            .where(BeachDay.feature_id == feature.id, BeachDay.day >= today)
            .order_by(BeachDay.day)
            .limit(service.FORECAST_DAYS)
        )
    ).all()
    hidden = access.visible_fields(principal if principal and principal.is_staff else None, layer)
    props = access.strip(feature.props or {}, hidden)
    card = {k: props[k] for k in CARD_FIELDS if props.get(k) not in (None, "")}
    sources = {
        k: {"source": props.get(f"{k}_source"), "date": props.get(f"{k}_date")}
        for k in card
        if props.get(f"{k}_source") or props.get(f"{k}_date")
    }
    # An open point of a beach programme in force guards the beach today (phase L2, design-l2.md §2.6).
    guarded_by = days[0].inputs.get("guarded_by") if days and days[0].day == today else None
    if guarded_by:
        card["guarded"] = "yes"
        sources["guarded"] = {"source": guarded_by, "date": today.isoformat()}
    simulated = any(d.simulated for d in days)
    present = None
    if principal is not None and principal.is_staff:
        present = (await service.presence_counts(session, datetime.now(UTC))).get(feature.id, 0)
    return schemas.BeachDetail(
        beach=_beach_out(feature, float(lat), float(lon), days[0] if days and days[0].day == today else None, present),
        days=[
            schemas.DayRisk(
                day=d.day,
                level=d.level,
                score=d.score,
                factors=[schemas.Factor.model_validate(f) for f in d.factors],
                wave_height_m=d.inputs.get("wave_height_m"),
                sea_temp_c=d.inputs.get("sea_temp_c"),
                current_kmh=d.inputs.get("current_kmh"),
                onshore_wind_kmh=d.inputs.get("onshore_wind_kmh"),
                max_temperature_c=d.inputs.get("max_temperature_c"),
            )
            for d in days
        ],
        card=card,
        sources=sources,
        length_m=round(float(length)) if length else None,
        seaward_deg=float(seaward) if seaward is not None else None,
        simulated=simulated,
        attribution=_attribution(simulated),
    )


@public_router.get("/beaches/{feature_id}", response_model=schemas.BeachDetail)
async def public_beach(session: Session, feature_id: uuid.UUID) -> schemas.BeachDetail:
    return await _detail(session, None, feature_id)


@public_router.post("/beaches/{feature_id}/presence", status_code=status.HTTP_204_NO_CONTENT)
async def presence(session: Session, feature_id: uuid.UUID, body: schemas.PresenceIn) -> Response:
    """ "I am at this beach", sent by a phone whose owner agreed: no account, no position, a daily random token."""
    layer = await _layer_for(session, None)
    found = await session.scalar(
        select(LayerFeature.id)
        .join(Beach, Beach.feature_id == LayerFeature.id)
        .where(LayerFeature.id == feature_id, LayerFeature.layer_id == layer.id, public_place())
    )
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "beach_not_found")
    async with as_system(session):
        await service.record_presence(session, feature_id, body.token, datetime.now(UTC))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- staff


@router.get("/beaches/{feature_id}", response_model=schemas.BeachDetail)
async def staff_beach(session: Session, principal: StaffReader, feature_id: uuid.UUID) -> schemas.BeachDetail:
    return await _detail(session, principal, feature_id)


async def _drownings(session: AsyncSession, principal: Principal, since: datetime) -> list[tuple[float, float]]:
    geometry = cast(Report.location, Geometry)
    query = select(func.ST_Y(geometry), func.ST_X(geometry)).where(
        Report.category == Category.DROWNING.value,
        Report.status != Status.REJECTED.value,
        Report.created_at >= since,
    )
    if not principal.is_national:
        query = query.where(Report.gouvernorat_code == principal.gouvernorat_code)
    return [(float(r[0]), float(r[1])) for r in (await session.execute(query)).all()]


def _grid(points: list[tuple[float, float]], cell: float = 0.01) -> list[list[float]]:
    cells: dict[tuple[int, int], int] = {}
    for lat, lon in points:
        key = (round(lat / cell), round(lon / cell))
        cells[key] = cells.get(key, 0) + 1
    top = max(cells.values(), default=1)
    return [[round(k[0] * cell, 4), round(k[1] * cell, 4), round(n / top, 3)] for k, n in sorted(cells.items())]


@router.get("/overview", response_model=schemas.Overview)
async def overview(
    session: Session,
    principal: StaffReader,
    day: Annotated[date | None, Query()] = None,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    classification: Annotated[str | None, Query(max_length=40)] = None,
    guarded: Annotated[bool | None, Query()] = None,
    level: Annotated[Literal["green", "yellow", "red"] | None, Query()] = None,
) -> schemas.Overview:
    layer = await _layer_for(session, principal)
    the_day = _day(day)
    scope = gouvernorat if principal.is_national else principal.gouvernorat_code
    rows = await _rows(session, layer, the_day, public=False, gouvernorat=scope)
    now = datetime.now(UTC)
    counts = await service.presence_counts(session, now)
    beaches = [_beach_out(f, lat, lon, r, counts.get(f.id, 0)) for f, lat, lon, r in rows]
    if classification:
        beaches = [b for b in beaches if b.classification == classification]
    if guarded is not None:
        beaches = [b for b in beaches if b.guarded is guarded]
    if level:
        beaches = [b for b in beaches if b.level == level]
    computed_at, simulated = _computed(rows)
    scored = [b for b in beaches if b.score is not None]
    season_start = datetime(now.year, 6, 1, tzinfo=UTC) if now.month >= 6 else datetime(now.year - 1, 6, 1, tzinfo=UTC)
    drownings = await _drownings(session, principal, now - timedelta(days=365 * 5))
    season = await _drownings(session, principal, season_start)
    by_code: dict[int | None, list[schemas.BeachOut]] = {}
    for b in beaches:
        by_code.setdefault(b.gouvernorat_code, []).append(b)
    kpis = schemas.Kpis(
        beaches=len(beaches),
        red=sum(b.level == "red" for b in beaches),
        yellow=sum(b.level == "yellow" for b in beaches),
        green=sum(b.level == "green" for b in beaches),
        unknown=sum(b.level is None for b in beaches),
        average_score=round(sum(b.score or 0 for b in scored) / len(scored), 1) if scored else None,
        guarded=sum(b.guarded is True for b in beaches),
        drownings_season=len(season),
        present=sum(b.present or 0 for b in beaches),
    )
    touristic = [b for b in beaches if b.classification in TOURISTIC]
    return schemas.Overview(
        day=the_day,
        computed_at=computed_at,
        simulated=simulated,
        attribution=_attribution(simulated),
        kpis=kpis,
        top_dangerous=sorted(scored, key=lambda b: (-(b.score or 0), b.name))[:10],
        top_touristic=sorted(touristic, key=lambda b: (CROWD_ORDER.get(b.crowd or "", 3), -(b.present or 0), b.name))[
            :10
        ],
        by_gouvernorat=[
            schemas.GouvernoratRisk(
                code=code,
                beaches=len(items),
                red=sum(b.level == "red" for b in items),
                yellow=sum(b.level == "yellow" for b in items),
                green=sum(b.level == "green" for b in items),
                average_score=(
                    round(sum(b.score or 0 for b in s) / len(s), 1)
                    if (s := [b for b in items if b.score is not None])
                    else None
                ),
                crowd_high=sum(b.crowd == "high" for b in items),
                crowd_medium=sum(b.crowd == "medium" for b in items),
                crowd_low=sum(b.crowd == "low" for b in items),
            )
            for code, items in sorted(by_code.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
        ],
        beaches=beaches,
        heat_risk=[[b.lat, b.lon, round((b.score or 0) / 100, 2)] for b in scored if (b.score or 0) > 0],
        heat_drownings=_grid(drownings),
    )


def _alert_out(alert: CoastalAlert, name: str) -> schemas.AlertOut:
    return schemas.AlertOut(
        id=str(alert.id),
        feature_id=str(alert.feature_id),
        name=name,
        day=alert.day,
        level=alert.level,
        previous_level=alert.previous_level,
        score=alert.score,
        gouvernorat_code=alert.gouvernorat_code,
        simulated=alert.simulated,
        created_at=alert.created_at,
        acked_by_name=alert.acked_by_name,
        acked_at=alert.acked_at,
    )


@router.get("/alerts", response_model=schemas.AlertsOut)
async def alerts(
    session: Session, principal: StaffReader, day: Annotated[date | None, Query()] = None
) -> schemas.AlertsOut:
    await _layer_for(session, principal)
    rows = (
        await session.execute(
            select(CoastalAlert, LayerFeature.name)
            .join(LayerFeature, LayerFeature.id == CoastalAlert.feature_id)
            .where(CoastalAlert.day == _day(day))
            .order_by(
                CoastalAlert.acked_at.is_not(None),
                (CoastalAlert.level == "red").desc(),
                CoastalAlert.score.desc(),
                CoastalAlert.created_at.desc(),
            )
        )
    ).all()
    return schemas.AlertsOut(items=[_alert_out(a, n) for a, n in rows])


@router.post("/alerts/{alert_id}/ack", response_model=schemas.AlertOut)
async def ack(session: Session, principal: StaffReader, alert_id: uuid.UUID) -> schemas.AlertOut:
    await _layer_for(session, principal)
    found = (
        await session.execute(
            select(CoastalAlert, LayerFeature.name)
            .join(LayerFeature, LayerFeature.id == CoastalAlert.feature_id)
            .where(CoastalAlert.id == alert_id)
        )
    ).first()
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert_not_found")
    alert, name = found
    if alert.acked_at is None:
        alert.acked_at = datetime.now(UTC)
        alert.acked_by = principal.subject
        alert.acked_by_name = audit.name_of(principal)
        await audit.record(
            session,
            actor=principal.subject,
            action="coastal.alert_ack",
            target=f"coastal_alert:{alert.id}",
            gouvernorats=[alert.gouvernorat_code] if alert.gouvernorat_code else None,
        )
        await session.commit()
    return _alert_out(alert, name)


@router.get("/settings", response_model=schemas.SettingsOut)
async def get_rules(session: Session, principal: StaffReader) -> schemas.SettingsOut:
    row = await session.get(CoastalSettings, 1)
    return schemas.SettingsOut(
        rules=risk.rules_of(row.rules if row else None),
        defaults=risk.DEFAULT_RULES,
        updated_by=row.updated_by if row else None,
        updated_at=row.updated_at if row and row.updated_by else None,
    )


def _check_rules(rules: dict[str, Any]) -> dict[str, Any]:
    unknown = set(rules) - set(risk.DEFAULT_RULES)
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "rule_unknown")
    merged = risk.rules_of(rules)
    try:
        bands = [(None if u is None else float(u), int(p)) for u, p in merged["waves"]]
        numbers = {k: float(v) for k, v in merged.items() if k not in ("waves", "season_months")}
        months = [int(m) for m in merged["season_months"]]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "rule_invalid") from exc
    ordered = [u for u, _ in bands[:-1]]
    if (
        not bands
        or bands[-1][0] is not None
        or any(u is None for u in ordered)
        or ordered != sorted(ordered)  # type: ignore[type-var]
        or not 0 < numbers["yellow"] < numbers["red"] <= 100
        or not 0 <= numbers["first_hour"] < numbers["last_hour"] <= 23
        or any(not 1 <= m <= 12 for m in months)
        or any(v < 0 for v in numbers.values())
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "rule_invalid")
    return rules


@router.put("/settings", response_model=schemas.SettingsOut)
async def put_rules(session: Session, principal: RuleEditor, body: schemas.SettingsIn) -> schemas.SettingsOut:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_only")
    rules = _check_rules(body.rules)
    row = await session.get(CoastalSettings, 1)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "settings_missing")
    before = dict(row.rules)
    row.rules = rules
    row.updated_by = audit.name_of(principal)
    row.updated_at = datetime.now(UTC)
    await audit.record(
        session,
        actor=principal.subject,
        action="coastal.rules_update",
        target="coastal:settings",
        reason=body.reason,
        details={"before": before, "after": rules},
    )
    await session.commit()
    return await get_rules(session, principal)


# ---------------------------------------------------------------- bulletin

_TITLES = {
    "ar": "النشرة الساحلية اليومية",
    "fr": "Bulletin côtier quotidien",
    "en": "Daily coastal bulletin",
}
_LEVEL_NAMES = {
    "ar": {"red": "أحمر", "yellow": "أصفر", "green": "أخضر"},
    "fr": {"red": "rouge", "yellow": "jaune", "green": "vert"},
    "en": {"red": "red", "yellow": "yellow", "green": "green"},
}
_FACTOR_NAMES = {
    "ar": {
        "waves": "الأمواج",
        "onshore_wind": "ريح نحو الشاطئ",
        "current": "التيار",
        "season": "الموسم والحرارة",
        "crowd": "إقبال مرتفع",
        "unguarded": "غير محروس",
        "past_drownings": "حوادث غرق سابقة",
    },
    "fr": {
        "waves": "vagues",
        "onshore_wind": "vent de mer",
        "current": "courant",
        "season": "saison et chaleur",
        "crowd": "forte affluence",
        "unguarded": "non surveillée",
        "past_drownings": "noyades passées",
    },
    "en": {
        "waves": "waves",
        "onshore_wind": "onshore wind",
        "current": "current",
        "season": "season and heat",
        "crowd": "high crowd",
        "unguarded": "unguarded",
        "past_drownings": "past drownings",
    },
}
_HEAD = {
    "ar": ("الشاطئ", "الولاية", "اللون", "النقاط", "الأسباب"),
    "fr": ("Plage", "Gouvernorat", "Niveau", "Score", "Raisons"),
    "en": ("Beach", "Gouvernorat", "Level", "Score", "Reasons"),
}
_SUMMARY = {
    "ar": "{red} أحمر، {yellow} أصفر، {green} أخضر، من {beaches} شاطئا. المؤشر لدعم القرار، بقواعد معلنة.",
    "fr": (
        "{red} rouge, {yellow} jaune, {green} vert, sur {beaches} plages. Indice d'aide à la décision, règles publiées."
    ),
    "en": "{red} red, {yellow} yellow, {green} green, of {beaches} beaches. A decision aid, by declared rules.",
}


@router.get("/bulletin.pdf")
async def bulletin(
    session: Session,
    principal: StaffReader,
    day: Annotated[date | None, Query()] = None,
    lang: Annotated[Lang, Query()] = "ar",
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
) -> Response:
    data = await overview(session, principal, day=day, gouvernorat=gouvernorat)
    names = {
        g.code: {"ar": g.name_ar, "fr": g.name_fr, "en": g.name_en}[lang]
        for g in (await session.scalars(select(Gouvernorat))).all()
    }
    e = html.escape
    risky = sorted((b for b in data.beaches if b.level in ("red", "yellow")), key=lambda b: (-(b.score or 0), b.name))
    separator = "، " if lang == "ar" else ", "

    def reasons(b: schemas.BeachOut) -> str:
        return separator.join(_FACTOR_NAMES[lang].get(f.code, f.code) for f in b.factors)

    rows = "".join(
        f'<tr class="{b.level}"><td>{e(b.name)}</td><td>{e(names.get(b.gouvernorat_code or 0, "—"))}</td>'
        f"<td>{e(_LEVEL_NAMES[lang][b.level or 'green'])}</td><td>{b.score}</td><td>{e(reasons(b))}</td></tr>"
        for b in risky
    )
    head = "".join(f"<th>{e(h)}</th>" for h in _HEAD[lang])
    sim = '<p class="sim">[SIM]</p>' if data.simulated else ""
    attribution = " · ".join(a if isinstance(a, str) else a["text"] for a in data.attribution)
    page = f"""<!doctype html><html lang="{lang}" dir="{"rtl" if lang == "ar" else "ltr"}"><head><meta charset="utf-8">
<style>body{{font-family:"Noto Naskh Arabic","DejaVu Sans",sans-serif;font-size:11pt;color:#182038}}
h1{{font-size:18pt;margin:0 0 4pt}}table{{border-collapse:collapse;width:100%;margin-top:10pt}}
th,td{{border:1px solid #E3E7EF;padding:4pt 6pt;text-align:start}}th{{background:#F3F5FA}}
tr.red td:nth-child(3){{color:#D7141A;font-weight:bold}}tr.yellow td:nth-child(3){{color:#8A6100;font-weight:bold}}
.sim{{display:inline-block;background:#F5B400;color:#182038;font-weight:bold;padding:1pt 6pt;border-radius:8pt}}
.small{{color:#5B6478;font-size:9pt}}</style></head><body>
<h1>{e(_TITLES[lang])}</h1><p>{e(data.day.isoformat())}</p>{sim}
<p>{e(_SUMMARY[lang].format(**data.kpis.model_dump()))}</p>
<table><tr>{head}</tr>{rows or '<tr><td colspan="5">—</td></tr>'}</table>
<p class="small">{e(attribution)}</p></body></html>"""
    from weasyprint import HTML

    pdf: bytes = HTML(string=page).write_pdf()
    await audit.record(
        session,
        actor=principal.subject,
        action="coastal.bulletin",
        target=f"coastal:bulletin:{data.day.isoformat()}",
        gouvernorats=[gouvernorat] if gouvernorat else None,
    )
    await session.commit()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="coastal-bulletin-{data.day.isoformat()}.pdf"'},
    )
