"""``python -m app.modules.evidence verify|seal``: re-check the whole anchor chain, or seal one anchor now.

Exit status 0 when the chain is intact, 1 otherwise; the report is printed as JSON.
"""

import argparse
import asyncio
import json
import sys

from app.core.db import dispose_engine, get_system_sessionmaker
from app.modules.evidence import service, worker


async def _main(command: str) -> dict[str, object]:
    try:
        if command == "seal":
            return {"sealed_seq": await worker.run_once(get_system_sessionmaker())}
        async with get_system_sessionmaker()() as session:
            return (await service.verify_chain(session)).as_dict()
    finally:
        await dispose_engine()


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.modules.evidence")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="re-check every anchor (chain, hash, signature, roots, audit head)")
    commands.add_parser("seal", help="seal an anchor now (and time-stamp pending ones)")
    result = asyncio.run(_main(parser.parse_args().command))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("intact", True) else 1


if __name__ == "__main__":
    sys.exit(main())
