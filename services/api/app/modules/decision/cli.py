"""One-shot commands of decision support, run in the API image with the API's environment.

python -m app.modules.decision.cli index [--no-embed]   # (re)index docs/procedures, then embed what is missing
python -m app.modules.decision.cli check DIR            # validate the sheets of DIR without touching the database
"""

import argparse
import asyncio
import json
from pathlib import Path

from app.core.db import dispose_engine, get_sessionmaker
from app.modules.decision import procedures


async def _index(embed: bool) -> dict[str, object]:
    try:
        return {
            "directory": str(procedures.default_directory()),
            **await procedures.index_once(get_sessionmaker(), embed=embed),
        }
    finally:
        await dispose_engine()


def _check(directory: Path) -> dict[str, object]:
    passages = procedures.load_directory(directory)
    return {"files": len({p.path for p in passages}), "passages": len(passages)}


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.modules.decision.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index", help="index the procedures library (PROCEDURES_DIR)")
    index.add_argument("--no-embed", action="store_true", help="full-text index only (no AI service call)")
    check = commands.add_parser("check", help="validate procedure sheets")
    check.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = asyncio.run(_index(not args.no_embed)) if args.command == "index" else _check(args.directory)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
