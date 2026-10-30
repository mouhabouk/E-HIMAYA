"""Who to involve in an incident (FR-C-13: «اقتراح آلي للجهات المتدخلة حسب نوع الحادثة وموقعها»).

The suggestion is drawn from what the platform already knows, each entry with its reason:

* civil protection units of the directory of phase 5 (``ops.unit``): the gouvernorat's regional directorate and the
  units or advanced posts quickest to reach on the road (L4 §10), with their phone, road distance and time;
* the regional committee of the gouvernorat when the situation may call for a level change (phase 5 committees);
* national services involved by incident type and classification (``domain.AGENCIES``), with the public emergency
  number when one exists nationally (190 SAMU, 193 Garde nationale, 197 Police);
* the registered institution nearest to the incident (phase 4), its contact and its manager.
"""

from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.decision import domain, routing
from app.modules.decision import schemas as s
from app.modules.decision.context import Situation
from app.modules.ops.models import Unit
from app.modules.ops.resources import unit_scope
from app.modules.orgs.models import Organization
from app.modules.reports.domain import Category
from app.modules.settings import service as settings

NEAREST_UNITS = 2
# Units timed on the road among the closest as the crow flies.
UNIT_CANDIDATES = 6
_LIVES_CATEGORIES = frozenset({Category.MEDICAL, Category.DROWNING, Category.TRAFFIC_ACCIDENT, Category.SOS})


async def _units(session: AsyncSession, principal: Principal, situation: Situation) -> list[s.Responder]:
    found: list[s.Responder] = []
    code = situation.incident.gouvernorat_code
    if code is not None:
        directorate = await session.scalar(
            select(Unit)
            .where(unit_scope(principal), Unit.gouvernorat_code == code, Unit.kind == "directorate")
            .order_by(Unit.name_ar)
            .limit(1)
        )
        if directorate is not None:
            found.append(
                s.Responder(
                    id=f"unit:{directorate.id}",
                    kind="unit",
                    name=directorate.name_ar,
                    name_fr=directorate.name_fr,
                    role="directorate",
                    organization="الحماية المدنية",
                    phone=directorate.phone,
                    gouvernorat_code=directorate.gouvernorat_code,
                    reason=s.Bilingual(
                        ar="الإدارة الجهوية للحماية المدنية بالولاية", fr="direction régionale de la protection civile"
                    ),
                )
            )
    if situation.lat is None or situation.lon is None:
        return found
    point = cast(func.ST_SetSRID(func.ST_MakePoint(situation.lon, situation.lat), 4326), Geography(srid=4326))
    distance = func.ST_Distance(Unit.location, point)
    geometry = cast(Unit.location, Geometry)
    rows = (
        await session.execute(
            select(Unit, distance, func.ST_Y(geometry), func.ST_X(geometry))
            .where(
                unit_scope(principal),
                Unit.kind != "directorate",
                func.ST_DWithin(Unit.location, point, await settings.threshold(session, "decision.unit_radius_m")),
            )
            .order_by(distance)
            .limit(UNIT_CANDIDATES)
        )
    ).all()
    if not rows:
        return found
    # The closest as the crow flies, then timed on the road; the quickest first (L4 §10).
    target = routing.Point(situation.lat, situation.lon)
    legs, engine = await routing.travel([routing.Point(float(r[2]), float(r[3])) for r in rows], target, "car")
    timed = sorted(zip(rows, legs, strict=True), key=lambda pair: (pair[1].duration_s, float(pair[0][1])))
    for (unit, meters, lat, lon), leg in timed[:NEAREST_UNITS]:
        km = leg.distance_m / 1000
        minutes = max(1, round(leg.duration_s / 60))
        estimate = engine == "fallback"
        found.append(
            s.Responder(
                id=f"unit:{unit.id}",
                kind="unit",
                name=unit.name_ar,
                name_fr=unit.name_fr,
                role=unit.kind,
                organization="الحماية المدنية",
                phone=unit.phone,
                gouvernorat_code=unit.gouvernorat_code,
                distance_m=round(float(meters)),
                lat=float(lat),
                lon=float(lon),
                road_m=round(leg.distance_m),
                road_s=round(leg.duration_s),
                engine=engine,
                reason=s.Bilingual(
                    ar=f"الأسرع وصولا: {minutes} دقيقة، {km:.1f} كم على الطريق" + (" (تقدير)" if estimate else ""),
                    fr=f"la plus rapide : {minutes} min, {km:.1f} km par la route"
                    + (" (estimation)" if estimate else ""),
                ),
            )
        )
    return found


def _agencies(situation: Situation) -> list[s.Responder]:
    rules: list[tuple[str, dict[str, str]]] = []
    if situation.lives_at_risk or situation.injured or situation.deaths or situation.category in _LIVES_CATEGORIES:
        rules.append(("samu", domain.SAMU_REASON))
    rules.extend(domain.AGENCY_RULES.get(situation.category, []))
    if situation.classification:
        rules.extend(domain.CLASSIFICATION_AGENCIES.get(situation.classification, []))
    if "gas" in situation.hazards:
        rules.append(("steg", {"ar": "خطر غاز", "fr": "risque gaz"}))
    seen: set[str] = set()
    found: list[s.Responder] = []
    for key, reason in rules:
        if key in seen:
            continue
        seen.add(key)
        agency: dict[str, Any] = domain.AGENCIES[key]
        name = agency["name"]
        found.append(
            s.Responder(
                id=f"agency:{key}",
                kind="agency",
                name=name["ar"],
                name_fr=name["fr"],
                role=key,
                organization=name["ar"],
                phone=agency["phone"],
                gouvernorat_code=situation.incident.gouvernorat_code,
                reason=s.Bilingual(**reason),
            )
        )
    return found


def _committee(situation: Situation) -> s.Responder | None:
    code = situation.incident.gouvernorat_code
    if code is None or (situation.op_level == "normal" and (situation.severity or 0) < 80):
        return None
    place = situation.gouvernorat or {"ar": str(code), "fr": str(code)}
    return s.Responder(
        id=f"committee:{code}",
        kind="committee",
        name=f"اللجنة الجهوية لمجابهة الكوارث — {place['ar']}",
        name_fr=f"Comité régional de lutte contre les catastrophes — {place['fr']}",
        role="local_committee",
        gouvernorat_code=code,
        reason=s.Bilingual(
            ar=f"المستوى {situation.op_level} وأولوية {situation.severity or 0}: تنسيق جهوي",
            fr=f"niveau {situation.op_level}, priorité {situation.severity or 0} : coordination régionale",
        ),
    )


async def _institution(session: AsyncSession, situation: Situation) -> s.Responder | None:
    site = situation.sensitive_site
    if not site or not site.get("org_id"):
        return None
    org = await session.get(Organization, site["org_id"])
    if org is None:
        return None
    manager = org.manager or {}
    distance = site.get("distance_m")
    return s.Responder(
        id=f"institution:{org.id}",
        kind="institution",
        name=org.name,
        role="site_manager",
        organization=org.name,
        phone=org.contact_phone or manager.get("phone"),
        email=org.contact_email or manager.get("email"),
        gouvernorat_code=org.gouvernorat_code,
        distance_m=round(float(distance)) if distance is not None else None,
        reason=s.Bilingual(
            ar=f"مؤسسة مسجلة على بعد {distance} م ({site.get('reason')}): مخطط النجدة والمواد الخطرة",
            fr=f"établissement enregistré à {distance} m ({site.get('reason')}) : plan de secours et produits "
            "dangereux",
        ),
    )


async def suggest(session: AsyncSession, principal: Principal, situation: Situation) -> list[s.Responder]:
    found = await _units(session, principal, situation)
    committee = _committee(situation)
    if committee is not None:
        found.append(committee)
    institution = await _institution(session, situation)
    if institution is not None:
        found.append(institution)
    found.extend(_agencies(situation))
    return found
