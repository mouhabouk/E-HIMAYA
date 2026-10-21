"""``python -m app.openapi [path]``: write the OpenAPI document of the API (phase 10 §6.1).

The file (default ``docs/api/openapi.json`` at the repository root) is sorted and stable, so CI can fail when the
committed copy differs from the code ("API · OpenAPI drift"). ``--check`` compares instead of writing.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.main import create_app

DEFAULT = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.json"


def document() -> dict[str, Any]:
    return create_app().openapi()


def render() -> str:
    return json.dumps(document(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.openapi")
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT)
    parser.add_argument("--check", action="store_true", help="exit 1 when the file differs from the code")
    args = parser.parse_args()
    text = render()
    if args.check:
        current = args.path.read_text(encoding="utf-8") if args.path.exists() else ""
        if current != text:
            print(f"{args.path} is out of date: run `python -m app.openapi`", file=sys.stderr)
            return 1
        return 0
    args.path.parent.mkdir(parents=True, exist_ok=True)
    args.path.write_text(text, encoding="utf-8")
    print(f"wrote {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
