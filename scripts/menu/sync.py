"""Copies the menu's one source to the API (its image is built from services/api alone).

    python3 scripts/menu/sync.py            write the copy
    python3 scripts/menu/sync.py --check    fail when the copy differs (CI)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from menu import API_COPY, SOURCE  # noqa: E402


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    if "--check" in sys.argv:
        if not API_COPY.exists() or API_COPY.read_text(encoding="utf-8") != source:
            print(f"{API_COPY} differs from {SOURCE}: run python3 scripts/menu/sync.py", file=sys.stderr)
            return 1
        print("menu copy up to date")
        return 0
    API_COPY.write_text(source, encoding="utf-8")
    print(f"wrote {API_COPY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
