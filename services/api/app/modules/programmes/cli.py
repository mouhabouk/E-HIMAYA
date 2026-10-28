"""Load seasonal programmes as drafts (phase L2, docs/phase-l/design-l2.md §2.5), for development and the first
season. Run in the API image with the API's environment:

python -m app.modules.programmes.cli load data/programmes/2026/programmes_2026.json [--dry-run]

Each programme of the file (JSON, xlsx template or CSV of points of programmes already loaded) that is not in the
system yet is created as a draft with its points, recorded as a version and in the audit log as ``system``. A
programme already in the system is left as it is: changes go through the dashboard import, which shows them first.
Nothing is approved here, so nothing shows on a map until a manager approves it.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.db import dispose_engine, get_system_sessionmaker
from app.modules.audit import service as audit
from app.modules.programmes import domain, service
from app.modules.programmes.models import Programme, ProgrammePoint

ACTOR = audit.SYSTEM_ACTOR
REASON = "chargement initial des programmes saisonniers (brouillon)"


async def load(name: str, content: bytes, dry_run: bool) -> dict[str, Any]:
    parsed = domain.parse(name, content)
    report: dict[str, Any] = {
        "errors": [e.out() for e in parsed.errors],
        "warnings": len(parsed.warnings),
        "programmes": {},
    }
    try:
        async with get_system_sessionmaker()() as session:
            index = await service.gouvernorat_index(session)
            for item in parsed.programmes:
                if item.meta is None:
                    report["programmes"][item.code] = "unknown (a CSV adds points to a programme already loaded)"
                    continue
                if await session.scalar(select(Programme.id).where(Programme.code == item.code)):
                    report["programmes"][item.code] = "exists, left as it is"
                    continue
                points = [p for p in item.points if service.gouvernorat_of(index, p.get("governorate", ""))]
                report["programmes"][item.code] = {
                    "points": len(points),
                    "unlocated": sum(1 for p in points if p.get("lat") is None),
                    "dropped": len(item.points) - len(points),
                }
                if dry_run:
                    continue
                programme = Programme(
                    **item.meta, status="draft", declared=item.declared, created_by=ACTOR, updated_by=ACTOR
                )
                session.add(programme)
                await session.flush()
                for p in points:
                    session.add(
                        ProgrammePoint(programme_id=programme.id, updated_by=ACTOR, **service.point_values(p, index))
                    )
                await service.revise(session, programme, None, "import", REASON)
                await audit.record(
                    session,
                    actor=ACTOR,
                    action="programme.import",
                    target=f"programme:{programme.code}",
                    reason=REASON,
                    details={"file": name, "points": len(points)},
                )
            if not dry_run:
                await session.commit()
        return report
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.modules.programmes.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    loading = commands.add_parser("load", help="load seasonal programmes as drafts")
    loading.add_argument("file", type=Path, help="JSON, xlsx template or CSV of points")
    loading.add_argument("--dry-run", action="store_true", help="count what would be created, write nothing")
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(load(args.file.name, args.file.read_bytes(), args.dry_run)),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
