"""Maintenance commands for data protection, run in the API image with the API's environment.

python -m app.modules.privacy.cli reencrypt [--batch 500] [--dry-run]   # key rotation
python -m app.modules.privacy.cli retention                             # run every retention job once
python -m app.modules.privacy.cli erasures [--done ID ...]              # identity-provider accounts to disable
"""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.core.crypto import get_cipher
from app.core.db import dispose_engine, get_system_sessionmaker
from app.modules.identity.models import ErasureRequest
from app.modules.privacy import retention, rotation


async def _reencrypt(batch: int, dry_run: bool) -> dict[str, object]:
    counts = await rotation.reencrypt(get_system_sessionmaker(), batch=batch, dry_run=dry_run)
    return {"active_version": get_cipher().active, "dry_run": dry_run, "rows": counts}


async def _erasures(done: list[int]) -> dict[str, object]:
    async with get_system_sessionmaker()() as session, session.begin():
        if done:
            await session.execute(
                update(ErasureRequest)
                .where(ErasureRequest.id.in_(done), ErasureRequest.disabled_at.is_(None))
                .values(disabled_at=datetime.now(UTC))
            )
        pending = await session.scalars(select(ErasureRequest).where(ErasureRequest.disabled_at.is_(None)))
        return {
            "pending": [
                {"id": r.id, "keycloak_sub": r.keycloak_sub, "requested_at": r.requested_at.isoformat()}
                for r in pending
            ]
        }


async def _main(args: argparse.Namespace) -> dict[str, object]:
    try:
        if args.command == "reencrypt":
            return await _reencrypt(args.batch, args.dry_run)
        if args.command == "retention":
            return {"rows": await retention.run_all(get_system_sessionmaker())}
        return await _erasures(args.done or [])
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.modules.privacy.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    reencrypt = commands.add_parser("reencrypt", help="re-encrypt every value under the active key version")
    reencrypt.add_argument("--batch", type=int, default=500)
    reencrypt.add_argument("--dry-run", action="store_true", help="only count what remains under old versions")
    commands.add_parser("retention", help="run every retention and anonymisation job once")
    erasures = commands.add_parser("erasures", help="list (and acknowledge) Keycloak accounts to disable")
    erasures.add_argument("--done", type=int, nargs="*", help="ids whose Keycloak account is now disabled")
    print(json.dumps(asyncio.run(_main(parser.parse_args())), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
