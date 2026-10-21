"""One-shot commands of the events library, run in the API image with the API's environment.

python -m app.modules.knowledge.cli backfill [--kinds memory,report,...] [--rebuild]
    rebuild knowledge.search_doc from every source and push it to OpenSearch (when configured); --rebuild fills new
    OpenSearch indices and moves the aliases to them at the end (after a mapping change, INDEX_VERSION).
python -m app.modules.knowledge.cli status
    rows per kind, rows waiting for OpenSearch or for a vector, and the OpenSearch cluster status.
"""

import argparse
import asyncio
import json
from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import dispose_engine, get_system_sessionmaker
from app.modules.knowledge import indexer
from app.modules.knowledge.domain import Kind
from app.modules.knowledge.opensearch import get_engine


async def _backfill(kinds: list[Kind] | None, rebuild: bool) -> dict[str, Any]:
    try:
        counts = await indexer.backfill(get_system_sessionmaker(), kinds, rebuild=rebuild)
        return {"backend": get_settings().search_engine, **counts}
    finally:
        await dispose_engine()


async def _status() -> dict[str, Any]:
    try:
        async with get_system_sessionmaker()() as session:
            rows = await session.execute(
                text(
                    "SELECT kind, count(*) FILTER (WHERE NOT deleted) AS items, count(*) FILTER (WHERE os_dirty) AS "
                    "dirty, count(*) FILTER (WHERE embedding IS NULL AND NOT deleted) AS unembedded "
                    "FROM knowledge.search_doc GROUP BY kind ORDER BY kind"
                )
            )
            kinds = {r.kind: {"items": r.items, "dirty": r.dirty, "unembedded": r.unembedded} for r in rows}
        engine = get_engine()
        return {
            "backend": get_settings().search_engine,
            "opensearch": await engine.health() if engine is not None else None,
            "kinds": kinds,
        }
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.modules.knowledge.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    backfill = commands.add_parser("backfill", help="re-index every library item")
    backfill.add_argument("--kinds", help="comma-separated kinds (default: all)")
    backfill.add_argument("--rebuild", action="store_true", help="new OpenSearch indices, aliases moved at the end")
    commands.add_parser("status", help="index status")
    args = parser.parse_args()
    if args.command == "backfill":
        kinds = [Kind(k.strip()) for k in args.kinds.split(",") if k.strip()] if args.kinds else None
        result = asyncio.run(_backfill(kinds, args.rebuild))
    else:
        result = asyncio.run(_status())
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
