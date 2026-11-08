"""The demonstration's operations picture (docs/demo.md): every kind of intervention, every team, all [SIM].

Called by ``python -m app.demo seed``. For the scenario's gouvernorat it adds, once:

* three units (the regional directorate, the demonstration unit, an advanced post) and their fleet, one or more
  vehicles of every kind;
* four rotation teams (أ، ب، ج، د), each a leader, a driver and two agents, waiting for activation on a phone;
* one report for every category, entered by the room as a phone call, at a different stage: waiting for the room,
  vehicles ordered, on the way, on the scene, closed (resolved or false alarm).

It goes through the same functions the room uses (intake, grouping, orders, statuses, closing), so tracking codes,
timelines, the audit log and the events are those of a real day. Every text carries [SIM]. Idempotent: a scenario
whose report already exists (same text) is left as it is.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, Realm, Role
from app.modules.audit.service import actor_of
from app.modules.ops import interventions
from app.modules.ops import service as incidents
from app.modules.ops.models import FieldAgent, Incident, Resource, Unit
from app.modules.ops.schemas import AssignmentIn, AssignmentStatusIn, Casualties, CloseIn
from app.modules.reports import intake
from app.modules.reports.domain import Category
from app.modules.reports.models import Report
from app.modules.reports.schemas import LocationIn, RoomReportIn
from app.modules.reports.service import locate_gouvernorat

ACTOR = "system:demo"

# (key, Arabic name, French name, kind, offset from the scenario's place in degrees (lat, lon))
UNITS: tuple[tuple[str, str, str, str, tuple[float, float]], ...] = (
    (
        "directorate",
        "[SIM] الإدارة الجهوية",
        "[SIM] Direction régionale",
        "directorate",
        (0.004, -0.012),
    ),
    ("advanced", "[SIM] المركز المتقدم", "[SIM] Poste avancé", "advanced_post", (-0.045, -0.03)),
)
# (label, kind, unit key: "main" is the demonstration unit of demo.seed)
FLEET: tuple[tuple[str, str, str], ...] = (
    ("[SIM] سيارة القيادة 1", "command_vehicle", "directorate"),
    ("[SIM] طائرة مسيّرة 1", "drone", "directorate"),
    ("[SIM] شاحنة إطفاء 1", "fire_engine", "main"),
    ("[SIM] شاحنة إطفاء 2", "fire_engine", "main"),
    ("[SIM] صهريج ماء 1", "water_tanker", "main"),
    ("[SIM] سيارة إسعاف 1", "ambulance", "main"),
    ("[SIM] سيارة إسعاف 2", "ambulance", "main"),
    ("[SIM] سيارة نجدة 1", "rescue_vehicle", "main"),
    ("[SIM] مطفأة كبيرة 1", "large_extinguisher", "main"),
    ("[SIM] شاحنة إطفاء 3", "fire_engine", "advanced"),
    ("[SIM] سيارة إسعاف 3", "ambulance", "advanced"),
    ("[SIM] سيارة نجدة 2", "rescue_vehicle", "advanced"),
    ("[SIM] زورق إنقاذ 1", "boat", "advanced"),
    ("[SIM] زورق إنقاذ 2", "boat", "advanced"),
    ("[SIM] آلية أشغال ثقيلة 1", "heavy_equipment", "advanced"),
)
TEAMS = ("أ", "ب", "ج", "د")
TEAM_FUNCTIONS = (("leader", "قائد الفريق"), ("driver", "سائق"), ("agent", "عون 1"), ("agent", "عون 2"))


@dataclass(frozen=True)
class Scenario:
    category: Category
    text: str
    offset: tuple[float, float]
    minutes_ago: int
    # The vehicles ordered, by label, and how far the mission went.
    vehicles: tuple[str, ...] = ()
    stage: str = "received"  # received | ordered | en_route | on_scene | resolved | false_alarm
    casualties: dict[str, int] = field(default_factory=dict)


# Inland offsets: the three scenario places are on the coast (Nabeul, Sfax) or near it (Tunis).
SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        Category.FIRE,
        "[SIM] حريق في مستودع، دخان كثيف يرى من الطريق",
        (0.012, -0.018),
        25,
        ("[SIM] شاحنة إطفاء 1", "[SIM] صهريج ماء 1"),
        "on_scene",
    ),
    Scenario(Category.FIRE, "[SIM] حريق أعشاب جافة قرب الطريق الحزامية", (0.03, -0.05), 3),
    Scenario(
        Category.TRAFFIC_ACCIDENT,
        "[SIM] اصطدام سيارتين، شخص عالق داخل سيارة",
        (-0.01, -0.03),
        9,
        ("[SIM] سيارة إسعاف 1", "[SIM] سيارة نجدة 1"),
        "en_route",
    ),
    Scenario(
        Category.MEDICAL,
        "[SIM] رجل مسن فاقد للوعي في منزله",
        (0.02, -0.025),
        140,
        ("[SIM] سيارة إسعاف 2",),
        "resolved",
        {"rescued": 1},
    ),
    Scenario(
        Category.FLOOD,
        "[SIM] تجمع مياه الأمطار في حي سكني، عائلات محاصرة",
        (-0.03, -0.04),
        50,
        ("[SIM] زورق إنقاذ 2", "[SIM] آلية أشغال ثقيلة 1"),
        "on_scene",
    ),
    Scenario(
        Category.DROWNING,
        "[SIM] طفل يصارع الموج على الشاطئ",
        (-0.005, -0.004),
        210,
        ("[SIM] زورق إنقاذ 1",),
        "resolved",
        {"rescued": 1},
    ),
    Scenario(
        Category.LANDSLIDE,
        "[SIM] انزلاق تربة على طريق جبلي، الطريق مقطوعة",
        (0.05, -0.08),
        6,
        ("[SIM] سيارة نجدة 2",),
        "ordered",
    ),
    Scenario(
        Category.CHEMICAL_LEAK,
        "[SIM] تسرب مادة كيميائية من شاحنة نقل",
        (-0.02, -0.06),
        35,
        ("[SIM] شاحنة إطفاء 2", "[SIM] مطفأة كبيرة 1", "[SIM] سيارة القيادة 1"),
        "on_scene",
    ),
    Scenario(Category.SOS, "[SIM] نداء استغاثة دون تفاصيل، الموقع من الهاتف", (0.008, -0.04), 1),
    Scenario(
        Category.OTHER,
        "[SIM] بلاغ عن دخان تبين أنه شواء في حديقة",
        (0.025, -0.01),
        300,
        ("[SIM] شاحنة إطفاء 3",),
        "false_alarm",
    ),
)


def _point(lat: float, lon: float) -> Any:
    return cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)


async def _inside(
    session: AsyncSession, gouvernorat: int, lat: float, lon: float, dlat: float, dlon: float
) -> tuple[float, float]:
    """The scenario's point, pulled towards the centre until it falls in the gouvernorat (small ones: Tunis)."""
    for _ in range(5):
        if await locate_gouvernorat(session, lat + dlat, lon + dlon) == gouvernorat:
            return lat + dlat, lon + dlon
        dlat, dlon = dlat / 2, dlon / 2
    return lat, lon


def room_principal(gouvernorat: int) -> Principal:
    """The regional room of the scenario, as the demo-room account would act."""
    return Principal(
        subject="demo-seed",
        realm=Realm.STAFF,
        roles=frozenset({Role.OPERATOR, Role.OPS_MANAGER}),
        gouvernorat_code=gouvernorat,
        claims={"name": "[SIM] قاعة العرض", "gouvernorat_code": gouvernorat},
    )


async def _units(session: AsyncSession, main: Unit, lat: float, lon: float) -> dict[str, Unit]:
    units = {"main": main}
    for key, name_ar, name_fr, kind, (dlat, dlon) in UNITS:
        unit = await session.scalar(
            select(Unit).where(Unit.name_ar == name_ar, Unit.gouvernorat_code == main.gouvernorat_code)
        )
        if unit is None:
            ulat, ulon = await _inside(session, main.gouvernorat_code, lat, lon, dlat, dlon)
            unit = Unit(
                name_ar=name_ar,
                name_fr=name_fr,
                kind=kind,
                gouvernorat_code=main.gouvernorat_code,
                location=_point(ulat, ulon),
            )
            session.add(unit)
            await session.flush()
        units[key] = unit
    return units


async def _fleet(session: AsyncSession, units: dict[str, Unit], lat: float, lon: float) -> dict[str, Resource]:
    offsets = {"main": (0.0, 0.0), **{key: off for key, _, _, _, off in UNITS}}
    fleet: dict[str, Resource] = {}
    for label, kind, key in FLEET:
        unit = units[key]
        resource = await session.scalar(select(Resource).where(Resource.unit_id == unit.id, Resource.label == label))
        if resource is None:
            rlat, rlon = await _inside(session, unit.gouvernorat_code, lat, lon, *offsets[key])
            resource = Resource(unit_id=unit.id, kind=kind, label=label, location=_point(rlat, rlon), updated_by=ACTOR)
            session.add(resource)
            await session.flush()
        fleet[label] = resource
    return fleet


async def _teams(session: AsyncSession, gouvernorat: int) -> int:
    added = 0
    for t, team in enumerate(TEAMS, start=1):
        for f, (function, title) in enumerate(TEAM_FUNCTIONS, start=1):
            matricule = f"SIMT{t}{f}"
            exists = await session.scalar(
                select(FieldAgent.id).where(
                    FieldAgent.gouvernorat_code == gouvernorat, FieldAgent.matricule == matricule
                )
            )
            if exists is None:
                session.add(
                    FieldAgent(
                        gouvernorat_code=gouvernorat,
                        matricule=matricule,
                        name=f"[SIM] {title}، الفريق {team}",
                        function=function,
                        shift_label=f"الفريق {team}",
                        created_by=ACTOR,
                    )
                )
                added += 1
    await session.flush()
    return added


async def _entered(session: AsyncSession, principal: Principal) -> set[str]:
    """Texts of the reports this seed already entered (the text is encrypted at rest: compared once read)."""
    reports = await session.scalars(
        select(Report).where(
            Report.entered_by == actor_of(principal),
            Report.gouvernorat_code == principal.gouvernorat_code,
        )
    )
    return {r.text_original for r in reports if r.text_original}


async def _scenario(
    session: AsyncSession,
    principal: Principal,
    s: Scenario,
    lat: float,
    lon: float,
    fleet: dict[str, Resource],
) -> str:
    if s.text in await _entered(session, principal):
        return "kept"
    now = datetime.now(UTC)
    assert principal.gouvernorat_code is not None
    plat, plon = await _inside(session, principal.gouvernorat_code, lat, lon, *s.offset)
    report_id = await intake.create(
        session,
        principal,
        RoomReportIn(
            category=s.category,
            location=LocationIn(lat=plat, lon=plon, accuracy_m=30),
            channel="phone",
            text=s.text,
            lang="ar",
            received_at=now - timedelta(minutes=s.minutes_ago),
        ),
    )
    if s.stage == "received":
        return "received"
    report = await session.get(Report, report_id, with_for_update=True)
    assert report is not None
    incident: Incident = await incidents._create(session, report, ACTOR)
    await incidents._attach(session, report, incident, ACTOR, via="new")
    orders = []
    for label in s.vehicles:
        resource = fleet[label]
        if resource.status != "available":
            continue  # taken by another scenario of an earlier run: the order is skipped, not doubled
        orders.append(
            await interventions.create_assignment(
                session, principal, incident, AssignmentIn(resource_id=resource.id, order=f"[SIM] {s.text}")
            )
        )
    path = {
        "ordered": (),
        "en_route": ("en_route",),
        "on_scene": ("en_route", "on_scene"),
        "resolved": ("en_route", "on_scene", "released"),
        "false_alarm": ("en_route", "on_scene", "released"),
    }[s.stage]
    for assignment in orders:
        for step in path:
            await interventions.update_assignment(session, principal, assignment.id, AssignmentStatusIn(status=step))
    if s.stage in ("resolved", "false_alarm"):
        await interventions.close(
            session,
            principal,
            incident,
            CloseIn(
                outcome="resolved" if s.stage == "resolved" else "false_alarm",
                summary=f"[SIM] أُغلق في العرض: {s.text}",
                casualties=Casualties(**s.casualties),
            ),
        )
    return s.stage


async def seed_operations(
    session: AsyncSession, main: Unit, gouvernorat: int, lat: float, lon: float
) -> dict[str, Any]:
    units = await _units(session, main, lat, lon)
    fleet = await _fleet(session, units, lat, lon)
    teams = await _teams(session, gouvernorat)
    principal = room_principal(gouvernorat)
    scenarios = [(s.category.value, await _scenario(session, principal, s, lat, lon, fleet)) for s in SCENARIOS]
    return {"units": len(units), "vehicles": len(fleet), "team_members_added": teams, "scenarios": scenarios}
