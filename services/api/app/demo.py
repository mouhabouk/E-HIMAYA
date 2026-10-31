"""The demonstration before the committee (review point 16, docs/demo.md): one computer, two phones, no Internet.

    python -m app.demo seed --owner-sub <Keycloak id of demo-owner> [--gouvernorat 21]
    python -m app.demo prealert [--label fire|smoke]
    python -m app.demo status

``seed`` is idempotent: it adds, once, the [SIM] institution of the scenario (owned by the public-realm user
``demo-owner``), the team leader of the staff app with a fresh activation code, and links the simulated camera of
``stream-sim`` to the institution. ``prealert`` makes that camera «see» a fire, as the detector would, so the
owner's phone rings and the 90 s countdown starts. Everything it writes carries [SIM].

Refused when ``APP_ENV=production``: the demonstration stack runs ``APP_ENV=development`` with the training strip.
"""

import argparse
import asyncio
import sys
import uuid
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.modules.identity.models import AccountKind
from app.modules.identity.service import _upsert_account
from app.modules.ops import field_agents
from app.modules.ops.models import FieldAgent
from app.modules.orgs import prealert
from app.modules.orgs.models import Member, Organization
from app.modules.streams.domain import Source
from app.modules.streams.models import LiveStream

ORG_NAME = "[SIM] مستودع الشركة التونسية للدهن"
ORG_IDENTIFIER = "9990016Z"
LEADER_MATRICULE = "SIM001"
# Nabeul (21) by default: the scenario's address, Route de Hammamet, near the regional room.
PLACES: dict[int, tuple[float, float, str]] = {
    21: (36.4561, 10.7376, "طريق الحمامات، نابل"),
    11: (36.8065, 10.1815, "شارع الحبيب بورقيبة، تونس"),
    61: (34.7406, 10.7603, "طريق قابس كلم 4، صفاقس"),
}


def _refuse_production() -> None:
    if get_settings().app_env == "production":
        sys.exit("demo: refused with APP_ENV=production (the demonstration stack runs APP_ENV=development)")


async def _org(session: AsyncSession) -> Organization | None:
    return await session.scalar(select(Organization).where(Organization.identifier == ORG_IDENTIFIER))


async def seed(owner_sub: str, gouvernorat: int) -> dict[str, Any]:
    lat, lon, address = PLACES.get(gouvernorat, PLACES[21])
    async with get_system_sessionmaker()() as session, session.begin():
        owner = await _upsert_account(session, AccountKind.CITIZEN, sub=owner_sub, anon=None)
        org = await _org(session)
        if org is None:
            org = Organization(
                status="active",
                name=ORG_NAME,
                kind="commercial",
                identifier_type="mf",
                identifier=ORG_IDENTIFIER,
                activity_sector="صناعة الدهن [SIM]",
                capacity=35,
                floors=1,
                height_m=9.0,
                receives_public=False,
                address=address,
                location=cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography),
                gouvernorat_code=gouvernorat,
                manager={"full_name": "[SIM] صاحب المؤسسة", "phone": "", "email": ""},
                created_by=owner.user_id,
                reviewed_by="system:demo",
            )
            session.add(org)
            await session.flush()
        if await session.get(Member, (org.id, owner.user_id)) is None:
            session.add(Member(org_id=org.id, user_id=owner.user_id, role="admin", display_name="[SIM] صاحب المؤسسة"))

        leader = await session.scalar(
            select(FieldAgent).where(
                FieldAgent.gouvernorat_code == gouvernorat,
                FieldAgent.matricule == LEADER_MATRICULE,
                FieldAgent.status != "deleted",
            )
        )
        code: str | None = None
        if leader is None:
            leader = FieldAgent(
                gouvernorat_code=gouvernorat,
                matricule=LEADER_MATRICULE,
                name="[SIM] قائد الفريق",
                function="leader",
                shift_label="نوبة العرض",
                created_by="system:demo",
            )
            session.add(leader)
            code = await field_agents._give_code(session, leader)
        elif leader.status == "pending":
            code = await field_agents._give_code(session, leader)
        camera = await _link_camera(session, org)
        await session.flush()
        return {
            "org_id": str(org.id),
            "owner_user_id": str(owner.user_id),
            "leader_matricule": LEADER_MATRICULE,
            "leader_code": code,
            "camera": str(camera.id) if camera else None,
        }


async def _link_camera(session: AsyncSession, org: Organization) -> LiveStream | None:
    """The newest live or pending stream of stream-sim becomes the institution's camera (the simulator renames it on
    each start, so this runs again after a restart)."""
    stream = await session.scalar(
        select(LiveStream)
        .where(LiveStream.source == Source.SIM, LiveStream.status.in_(("pending", "live")))
        .order_by(LiveStream.created_at.desc())
        .limit(1)
    )
    if stream is not None:
        stream.org_id = org.id
        stream.report_id = None
    return stream


async def raise_prealert(label: str) -> dict[str, Any]:
    async with get_system_sessionmaker()() as session, session.begin():
        org = await _org(session)
        if org is None:
            sys.exit("demo: run `python -m app.demo seed` first")
        camera = await _link_camera(session, org)
        row = await prealert.open_prealert(
            session,
            org.id,
            source="camera",
            label=label,
            confidence=0.87,
            stream_id=camera.id if camera else None,
            simulated=True,
        )
        return {"prealert_id": str(row.id), "deadline_at": row.deadline_at.isoformat()}


async def status() -> dict[str, Any]:
    async with get_system_sessionmaker()() as session:
        org = await _org(session)
        leader = await session.scalar(select(FieldAgent).where(FieldAgent.matricule == LEADER_MATRICULE))
        return {
            "org": str(org.id) if org else None,
            "leader": leader.status if leader else None,
            "sim_streams": int(
                await session.scalar(
                    select(func.count(LiveStream.id)).where(
                        LiveStream.source == Source.SIM, LiveStream.status == "live"
                    )
                )
                or 0
            ),
        }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.demo", description=__doc__.splitlines()[0] if __doc__ else "")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("seed", help="the scenario's [SIM] institution, team leader and camera (idempotent)")
    s.add_argument("--owner-sub", required=True, help="Keycloak id of the public-realm user demo-owner")
    s.add_argument("--gouvernorat", type=int, default=21)
    p = sub.add_parser("prealert", help="the institution's camera «sees» a fire: the owner's countdown starts")
    p.add_argument("--label", choices=("fire", "smoke"), default="fire")
    sub.add_parser("status", help="what the scenario has")
    args = parser.parse_args(argv)
    _refuse_production()
    if args.command == "seed":
        uuid.UUID(args.owner_sub)  # a Keycloak id; refuses a username typed by mistake
        out = asyncio.run(seed(args.owner_sub, args.gouvernorat))
    elif args.command == "prealert":
        out = asyncio.run(raise_prealert(args.label))
    else:
        out = asyncio.run(status())
    for key, value in out.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
