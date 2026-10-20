"""Rules-based recommendations for one incident (FR-C-11, docs/api/phase-7-contract.md §3).

Each rule reads the ``Situation`` (context.py), states its inputs and its reasoning in Arabic and French, rates its
confidence, and offers buttons that open existing flows (assignment order, alert form, call, route). Nothing is ever
applied here: an operator decides.
"""

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.decision import domain, routing
from app.modules.decision import schemas as s
from app.modules.decision.context import Situation
from app.modules.decision.domain import danger_at_least, rain_at_least
from app.modules.decision.responders import suggest as suggest_responders
from app.modules.ops import interventions
from app.modules.ops.models import Resource, Unit
from app.modules.ops.resources import unit_scope
from app.modules.reports.domain import Category

NOTICE = s.Bilingual(
    ar="توصيات مساعدة على القرار مع مبرراتها ومدخلاتها؛ لا يُنفذ أي شيء آليا والقرار للمسؤول.",
    fr="Recommandations d'aide à la décision avec leur justification et leurs données ; rien n'est appliqué "
    "automatiquement, la décision revient au responsable.",
)
# Candidate resources considered per kind (straight line), then ranked by travel time.
RESOURCE_RADIUS_M = 150_000
CANDIDATES_PER_KIND = 8
LARGE_FIRE_HA = 50.0
ALERT_FIRE_HA = 20.0
ESCALATION_FIRE_HA = 100.0


@dataclass(slots=True)
class Need:
    kind: str
    count: int
    reasons: list[s.Bilingual]


def _b(ar: str, fr: str) -> s.Bilingual:
    return s.Bilingual(ar=ar, fr=fr)


def needs(situation: Situation) -> list[Need]:
    """Resource kinds the incident calls for, with why (before what is already engaged)."""
    category = situation.category
    found: dict[str, Need] = {}

    def add(kind: str, count: int, reason: s.Bilingual) -> None:
        need = found.setdefault(kind, Need(kind, 0, []))
        need.count += count
        if reason not in need.reasons:
            need.reasons.append(reason)

    label = domain.CATEGORY_LABELS.get(category, domain.CATEGORY_LABELS[Category.OTHER])
    for kind, count in domain.BASE_NEEDS.get(category, domain.BASE_NEEDS[Category.OTHER]).items():
        add(kind, count, _b(f"استجابة أولى لـ{label['ar']}", f"premier départ pour {label['fr']}"))

    weather, forecast = situation.weather, situation.forecast
    area = forecast.max_area_ha if forecast and forecast.max_area_ha is not None else None
    if category == Category.FIRE:
        forest = situation.classification == "forest_fire"
        danger = weather.fire_danger if weather else None
        if forest or danger_at_least(danger, "high"):
            why = (
                _b("حريق غابات", "feu de forêt")
                if forest
                else _b(f"خطر حرائق مرتفع ({danger})", f"danger d'incendie élevé ({danger})")
            )
            add("fire_engine", 1, why)
            add("water_tanker", 1, why)
            add("heavy_equipment", 1, _b("فتح خطوط النار", "ouverture de pare-feu"))
            add("drone", 1, _b("استطلاع ومراقبة القفزات", "reconnaissance et surveillance des sautes de feu"))
        if area is not None and area >= LARGE_FIRE_HA:
            why = _b(f"مساحة متوقعة {area:.0f} هك", f"surface prévue {area:.0f} ha")
            add("fire_engine", 1, why)
            add("command_vehicle", 1, why)
        if situation.classification == "industrial_fire" or (
            situation.sensitive_site and "hazmat" in str(situation.sensitive_site.get("reason", ""))
        ):
            why = _b("موقع صناعي أو مواد خطرة قريبة", "site industriel ou produits dangereux à proximité")
            add("large_extinguisher", 1, why)
            add("command_vehicle", 1, why)
    if category == Category.FLOOD and (
        rain_at_least(weather.rain_level if weather else None, "warning") or (forecast and forecast.level == "high")
    ):
        add("heavy_equipment", 1, _b("إنذار أمطار: إزالة الحطام تحت الجسور", "alerte pluie : dégager les embâcles"))
        add("boat", 1, _b("إنذار أمطار", "alerte pluie"))
    if category == Category.TRAFFIC_ACCIDENT:
        if situation.injured > 2:
            add(
                "ambulance",
                min(math.ceil(situation.injured / 2) - 1, 3),
                _b(f"{situation.injured} مصابين", f"{situation.injured} blessés"),
            )
        if situation.classification == "chemical_road_accident" or {"fuel", "chemical", "explosion"} & set(
            situation.hazards
        ):
            add("fire_engine", 1, _b("وقود أو مادة خطرة", "carburant ou matière dangereuse"))
    if situation.classification == "building_collapse" or "building_collapse" in situation.hazards:
        why = _b("انهيار بناية", "effondrement de bâtiment")
        add("heavy_equipment", 1, why)
        add("rescue_vehicle", 1, why)
        add("command_vehicle", 1, why)
    if situation.lives_at_risk:
        why = _b("أرواح في خطر", "vies en danger")
        add("ambulance", 1 if "ambulance" not in found else 0, why)
        if category not in (Category.MEDICAL, Category.DROWNING):
            add("rescue_vehicle", 1 if "rescue_vehicle" not in found else 0, why)
    big = (situation.severity or 0) >= 80 or situation.reporter_count >= 10 or situation.people_detected >= 5
    if big:
        main = next(iter(domain.BASE_NEEDS.get(category, domain.BASE_NEEDS[Category.OTHER])))
        add(
            main,
            1,
            _b(
                f"أولوية {situation.severity or 0} و{situation.reporter_count} مبلغين",
                f"priorité {situation.severity or 0}, {situation.reporter_count} déclarants",
            ),
        )
    return [n for n in found.values() if n.count > 0]


async def _candidates(
    session: AsyncSession, principal: Principal, kind: str, lat: float, lon: float
) -> list[tuple[Resource, Unit, float, float]]:
    location = func.coalesce(Resource.location, Unit.location)
    point = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography(srid=4326))
    distance = func.ST_Distance(location, point)
    rows = (
        await session.execute(
            select(Resource, Unit, func.ST_Y(cast(location, Geometry)), func.ST_X(cast(location, Geometry)))
            .join(Unit, Unit.id == Resource.unit_id)
            .where(
                unit_scope(principal),
                Resource.kind == kind,
                Resource.status == "available",
                func.ST_DWithin(location, point, RESOURCE_RADIUS_M),
            )
            .order_by(distance, Resource.label)
            .limit(CANDIDATES_PER_KIND)
        )
    ).all()
    return [(r, u, float(la), float(lo)) for r, u, la, lo in rows]


def _minutes(seconds: float) -> int:
    return max(1, round(seconds / 60))


async def resource_items(
    session: AsyncSession, principal: Principal, situation: Situation
) -> tuple[list[s.Recommendation], tuple[routing.Point, routing.Profile] | None]:
    """One recommendation per resource kind still needed, and the origin of the first proposed vehicle (route)."""
    if situation.lat is None or situation.lon is None:
        return [], None
    target = routing.Point(situation.lat, situation.lon)
    items: list[s.Recommendation] = []
    first_origin: tuple[routing.Point, routing.Profile] | None = None
    for need in needs(situation):
        engaged = situation.engaged.get(need.kind, 0)
        missing = need.count - engaged
        if missing <= 0:
            continue
        label = domain.RESOURCE_LABELS.get(need.kind, domain.RESOURCE_LABELS["other"])
        profile: routing.Profile = "truck" if need.kind in domain.TRUCK_KINDS else "car"
        candidates = await _candidates(session, principal, need.kind, situation.lat, situation.lon)
        legs, engine = await routing.travel([routing.Point(la, lo) for _, _, la, lo in candidates], target, profile)
        ranked = sorted(zip(candidates, legs, strict=True), key=lambda pair: (pair[1].duration_s, pair[0][0].label))
        chosen = ranked[:missing]
        reasons_ar = "، ".join(r.ar for r in need.reasons)
        reasons_fr = ", ".join(r.fr for r in need.reasons)
        inputs: dict[str, Any] = {
            "resource_kind": need.kind,
            "needed": need.count,
            "already_engaged": engaged,
            "travel_engine": engine,
            "candidates": [
                {
                    "resource_id": str(res.id),
                    "label": res.label,
                    "unit": unit.name_ar,
                    "distance_m": round(leg.distance_m),
                    "eta_min": _minutes(leg.duration_s),
                }
                for (res, unit, _, _), leg in ranked
            ],
        }
        if not chosen:
            items.append(
                s.Recommendation(
                    kind="resources",
                    title=_b(f"لا توجد {label['ar']} متاحة", f"Aucun(e) {label['fr']} disponible"),
                    rationale=_b(
                        f"الحاجة: {need.count} ({reasons_ar})، ولا توجد وسيلة متاحة في نطاقكم على مسافة 150 كم: "
                        "اطلبوا تعزيزا من ولاية مجاورة أو من المستوى المركزي.",
                        f"Besoin : {need.count} ({reasons_fr}), aucun moyen disponible dans votre périmètre à moins "
                        "de 150 km : demander un renfort à une gouvernorat voisine ou au niveau central.",
                    ),
                    inputs=inputs,
                    confidence="low",
                )
            )
            continue
        if first_origin is None:
            _, _, la, lo = chosen[0][0]
            first_origin = (routing.Point(la, lo), profile)
        category_ar = domain.CATEGORY_LABELS.get(situation.category, domain.CATEGORY_LABELS[Category.OTHER])["ar"]
        etas = ", ".join(f"{res.label} ({_minutes(leg.duration_s)} min)" for (res, _, _, _), leg in chosen)
        estimate_note = (
            _b(
                " (تقدير بخط مستقيم: محرك المسالك غير متوفر)",
                " (estimation à vol d'oiseau : moteur d'itinéraire indisponible)",
            )
            if engine == "fallback"
            else _b("", "")
        )
        items.append(
            s.Recommendation(
                kind="resources",
                title=_b(f"إرسال {len(chosen)} {label['ar']}", f"Engager {len(chosen)} {label['fr']}"),
                rationale=_b(
                    f"الحاجة: {need.count} ({reasons_ar})، منها {engaged} مكلفة. الأقرب زمنيا: {etas}"
                    f"{estimate_note.ar}.",
                    f"Besoin : {need.count} ({reasons_fr}), dont {engaged} déjà engagé(s). Les plus proches en temps : "
                    f"{etas}{estimate_note.fr}.",
                ),
                inputs=inputs,
                confidence="high" if engine != "fallback" and len(chosen) == missing else "medium",
                actions=[
                    s.Action(
                        type="open_assignment",
                        resource_id=res.id,
                        label=_b(f"تكليف {res.label}", f"Engager {res.label}"),
                        order=f"{label['ar']} {res.label} — {category_ar}",
                    )
                    for (res, _, _, _), _ in chosen
                ],
            )
        )
    return items, first_origin


async def route_item(situation: Situation, origin: routing.Point, profile: routing.Profile) -> s.Recommendation:
    assert situation.lat is not None and situation.lon is not None
    target = routing.Point(situation.lat, situation.lon)
    route = await routing.route(origin, target, profile)
    fallback = route.engine == "fallback"
    minutes = _minutes(route.duration_s)
    km = route.distance_m / 1000
    return s.Recommendation(
        kind="route",
        title=_b(f"أفضل مسلك: {km:.1f} كم، نحو {minutes} دقيقة", f"Meilleur itinéraire : {km:.1f} km, ~{minutes} min"),
        rationale=(
            _b(
                "تقدير بخط مستقيم لأن محرك المسالك غير متوفر؛ تحققوا من الطريق قبل الانطلاق.",
                "Estimation à vol d'oiseau, le moteur d'itinéraire est indisponible ; vérifier la route avant de "
                "partir.",
            )
            if fallback
            else _b(
                f"مسلك {'الشاحنات' if profile == 'truck' else 'السيارات'} على شبكة طرقات OpenStreetMap تونس.",
                f"Itinéraire {'poids lourd' if profile == 'truck' else 'véhicule léger'} sur le réseau OpenStreetMap "
                "Tunisie.",
            )
        ),
        inputs={
            "from": {"lat": origin.lat, "lon": origin.lon},
            "to": {"lat": target.lat, "lon": target.lon},
            "profile": profile,
            "distance_m": round(route.distance_m),
            "duration_s": round(route.duration_s),
            "engine": route.engine,
            "fallback_reason": route.fallback_reason,
        },
        confidence="low" if fallback else "high",
        actions=[
            s.Action(
                type="show_route",
                label=_b("عرض المسلك", "Afficher l'itinéraire"),
                **{"from": s.LatLon(lat=origin.lat, lon=origin.lon)},
                to=s.LatLon(lat=target.lat, lon=target.lon),
                profile=profile,
            )
        ],
    )


async def volunteer_items(session: AsyncSession, principal: Principal, situation: Situation) -> list[s.Recommendation]:
    skills = domain.VOLUNTEER_SKILLS.get(situation.category, ())
    if not skills or situation.lat is None:
        return []
    items: list[s.Recommendation] = []
    wanted = 4 if (situation.severity or 0) >= 70 or situation.lives_at_risk else 2
    for skill in skills:
        found = await interventions.suggestions(session, principal, situation.incident, skill, 20, 20)
        free = [v for v in found if not v.busy]
        label = domain.SKILL_LABELS[skill]
        inputs = {
            "skill": skill,
            "radius_km": 20,
            "ready_nearby": len(found),
            "available": len(free),
            "suggested": [
                {"volunteer_id": str(v.volunteer_id), "distance_m": v.distance_m, "busy": v.busy} for v in found[:10]
            ],
        }
        if not free:
            continue
        chosen = free[:wanted]
        items.append(
            s.Recommendation(
                kind="volunteers",
                title=_b(
                    f"استنفار {len(chosen)} متطوعين ({label['ar']})",
                    f"Mobiliser {len(chosen)} volontaires ({label['fr']})",
                ),
                rationale=_b(
                    f"{len(free)} متطوعين جاهزين بمهارة «{label['ar']}» على أقل من 20 كم، أقربهم على "
                    f"{chosen[0].distance_m} م. يُؤطَّر المتطوعون من قائد العمليات.",
                    f"{len(free)} volontaires prêts avec la compétence « {label['fr']} » à moins de 20 km, le plus "
                    f"proche à {chosen[0].distance_m} m. Les volontaires sont encadrés par le chef des opérations.",
                ),
                inputs=inputs,
                confidence="medium",
                actions=[
                    s.Action(
                        type="call",
                        volunteer_id=v.volunteer_id,
                        label=_b(f"اتصال بمتطوع ({v.distance_m} م)", f"Appeler un volontaire ({v.distance_m} m)"),
                    )
                    for v in chosen
                ],
            )
        )
    return items


def escalation_item(situation: Situation) -> s.Recommendation | None:
    triggers: list[s.Bilingual] = []
    forecast, weather = situation.forecast, situation.weather
    if (situation.severity or 0) >= 85 and (situation.reporter_count >= 10 or situation.people_detected >= 10):
        triggers.append(_b("أولوية قصوى وعدد كبير من المبلغين أو الأشخاص", "priorité maximale et nombreux témoins"))
    if forecast and forecast.kind == "fire" and (forecast.max_area_ha or 0) >= ESCALATION_FIRE_HA:
        triggers.append(
            _b(f"انتشار متوقع {forecast.max_area_ha:.0f} هك", f"propagation prévue {forecast.max_area_ha:.0f} ha")
        )
    if situation.category == Category.FIRE and danger_at_least(weather.fire_danger if weather else None, "extreme"):
        triggers.append(_b("خطر حرائق أقصى", "danger d'incendie extrême"))
    if (
        situation.category == Category.FLOOD
        and situation.lives_at_risk
        and (
            rain_at_least(weather.rain_level if weather else None, "warning") or (forecast and forecast.level == "high")
        )
    ):
        triggers.append(_b("فيضان مع أرواح في خطر وإنذار أمطار", "inondation, vies en danger et alerte pluie"))
    if situation.busy_incidents >= 3:
        triggers.append(
            _b(
                f"{situation.busy_incidents} حوادث أخرى ذات أولوية عالية مفتوحة في الولاية",
                f"{situation.busy_incidents} autres incidents prioritaires ouverts dans la gouvernorat",
            )
        )
    if situation.people_trapped and situation.classification == "building_collapse":
        triggers.append(_b("أشخاص تحت الأنقاض", "personnes sous les décombres"))
    level = situation.op_level
    if not triggers or level == "disaster" or (level == "crisis" and len(triggers) < 3):
        return None
    target = "crisis" if level == "normal" else "disaster"
    who = _b("اللجنة الجهوية", "comité régional") if target == "crisis" else _b("اللجنة المركزية", "comité central")
    target_label = _b("الأزمة", "crise") if target == "crisis" else _b("الكارثة", "catastrophe")
    return s.Recommendation(
        kind="escalation",
        title=_b(f"اقتراح رفع المستوى إلى {target_label.ar}", f"Proposer le passage au niveau {target_label.fr}"),
        rationale=_b(
            f"المستوى الحالي: {level}. المؤشرات: {'، '.join(t.ar for t in triggers)}. القرار لـ{who.ar}.",
            f"Niveau actuel : {level}. Indicateurs : {', '.join(t.fr for t in triggers)}. Décision du {who.fr}.",
        ),
        inputs={
            "op_level": level,
            "proposed_level": target,
            "busy_incidents": situation.busy_incidents,
            "triggers": [t.model_dump() for t in triggers],
            "forecast": forecast.as_inputs() if forecast else None,
        },
        confidence="high" if len(triggers) >= 2 else "medium",
    )


def alert_item(situation: Situation) -> s.Recommendation | None:
    hazard = domain.ALERT_HAZARD.get(situation.category)
    if hazard is None or situation.incident.gouvernorat_code is None:
        return None
    weather, forecast = situation.weather, situation.forecast
    reasons: list[s.Bilingual] = []
    if situation.category == Category.FIRE:
        if situation.classification != "forest_fire" and not danger_at_least(
            weather.fire_danger if weather else None, "very_high"
        ):
            return None
        if forecast and (forecast.max_area_ha or 0) >= ALERT_FIRE_HA:
            reasons.append(
                _b(f"انتشار متوقع {forecast.max_area_ha:.0f} هك", f"propagation prévue {forecast.max_area_ha:.0f} ha")
            )
        if danger_at_least(weather.fire_danger if weather else None, "very_high"):
            reasons.append(_b("خطر حرائق مرتفع جدا", "danger d'incendie très élevé"))
    elif situation.category == Category.FLOOD:
        level = weather.rain_level if weather else None
        if rain_at_least(level, "warning"):
            reasons.append(_b("إنذار أمطار غزيرة", "alerte forte pluie"))
        elif rain_at_least(level, "watch") and situation.lives_at_risk:
            reasons.append(_b("يقظة أمطار وأرواح في خطر", "vigilance pluie et vies en danger"))
        if forecast and forecast.level in ("high", "very_high"):
            reasons.append(_b("تقدير خطر فيضان مرتفع", "avis de risque d'inondation élevé"))
    elif situation.category == Category.CHEMICAL_LEAK:
        if (situation.severity or 0) >= 60 or situation.sensitive_site:
            reasons.append(_b("تسرب مادة خطرة قرب السكان", "fuite de produit dangereux près de la population"))
    elif situation.category == Category.LANDSLIDE and situation.lives_at_risk:
        reasons.append(_b("أرواح في خطر", "vies en danger"))
    if situation.weather_suggestions:
        reasons.append(
            _b(
                f"{situation.weather_suggestions} اقتراح تنبيه جوي في الانتظار للولاية",
                f"{situation.weather_suggestions} suggestion(s) d'alerte météo en attente pour la gouvernorat",
            )
        )
    if not reasons:
        return None
    place = situation.gouvernorat or {"ar": "", "fr": ""}
    texts = domain.ALERT_TEXTS[hazard]
    fmt = {"place_ar": place["ar"], "place_fr": place["fr"]}
    area: dict[str, Any] = {"gouvernorat_codes": [situation.incident.gouvernorat_code]}
    if forecast and forecast.geometry and forecast.geometry.get("type") == "Polygon":
        area["polygon"] = forecast.geometry
    prefill = {
        "kind": "alert",
        "category": "hazard",
        "hazard": hazard,
        "severity": "high" if len(reasons) >= 2 or (situation.severity or 0) >= 80 else "medium",
        "title": {k: v.format(**fmt) for k, v in texts["title"].items()},
        "body": {k: v.format(**fmt) for k, v in texts["body"].items()},
        "channels": ["push", "sms"],
        "area": area,
        "incident_id": str(situation.incident.id),
    }
    return s.Recommendation(
        kind="alert",
        title=_b("اقتراح تنبيه عمومي", "Proposer une alerte publique"),
        rationale=_b(
            f"{'، '.join(r.ar for r in reasons)}. يُراجع النص ويُصادق عليه محرر أو لجنة قبل أي إرسال.",
            f"{', '.join(r.fr for r in reasons)}. Le texte est relu et validé par un éditeur ou un comité avant tout "
            "envoi.",
        ),
        inputs={
            "hazard": hazard,
            "weather": weather.as_inputs() if weather else None,
            "forecast": forecast.as_inputs() if forecast else None,
            "pending_weather_suggestions": situation.weather_suggestions,
        },
        confidence="high" if len(reasons) >= 2 else "medium",
        actions=[
            s.Action(
                type="open_alert_form", label=_b("فتح نموذج التنبيه", "Ouvrir le formulaire d'alerte"), prefill=prefill
            )
        ],
    )


async def responders_item(session: AsyncSession, principal: Principal, situation: Situation) -> s.Recommendation | None:
    responders = await suggest_responders(session, principal, situation)
    callable_ = [r for r in responders if r.phone]
    if not responders:
        return None
    return s.Recommendation(
        kind="responders",
        title=_b(f"إشراك {len(responders)} جهات", f"Associer {len(responders)} intervenants"),
        rationale=_b(
            "، ".join(f"{r.name} ({r.reason.ar})" for r in responders[:6]),
            ", ".join(f"{r.name_fr or r.name} ({r.reason.fr})" for r in responders[:6]),
        ),
        inputs={"responders": [r.model_dump(mode="json") for r in responders]},
        confidence="high" if any(r.kind == "unit" for r in responders) else "medium",
        actions=[
            s.Action(type="call", number=r.phone, label=_b(f"اتصال: {r.name}", f"Appeler : {r.name_fr or r.name}"))
            for r in callable_[:4]
        ],
    )


async def recommend(session: AsyncSession, principal: Principal, situation: Situation) -> s.Recommendations:
    shared = situation.as_inputs()
    items, origin = await resource_items(session, principal, situation)
    if origin is not None:
        items.append(await route_item(situation, *origin))
    items.extend(await volunteer_items(session, principal, situation))
    for item in (escalation_item(situation), alert_item(situation)):
        if item is not None:
            items.append(item)
    responders = await responders_item(session, principal, situation)
    if responders is not None:
        items.append(responders)
    for item in items:
        item.inputs = {"incident": shared, **item.inputs}
    if situation.lat is None:
        items.insert(
            0,
            s.Recommendation(
                kind="resources",
                title=_b("موقع الحادثة غير معروف", "Position de l'incident inconnue"),
                rationale=_b(
                    "لا يمكن اقتراح الوسائل ولا المسالك دون موقع: اربطوا بلاغا محدد الموقع بالحادثة.",
                    "Impossible de proposer moyens et itinéraires sans position : rattacher un signalement localisé.",
                ),
                inputs={"incident": shared},
                confidence="low",
            ),
        )
    return s.Recommendations(
        incident_id=uuid.UUID(str(situation.incident.id)),
        generated_at=datetime.now(UTC),
        items=items,
        simulated=situation.simulated,
        notice=NOTICE,
    )
