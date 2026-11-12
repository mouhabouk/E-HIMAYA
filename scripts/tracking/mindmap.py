"""Builds the mind maps of the project, one per phase plus an overview (Yamen, 2026-11-13).

Reads the same rows as the request tracker (requests.py, plus the items of docs/versions.md added since), so a new
phase or a changed status shows on the next run without hand edits.

    python3 scripts/tracking/mindmap.py <out.html>
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import requests as cur  # noqa: E402
from build import collect  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1])
    rows, nitems = collect()
    data = {"groups": cur.G, "rows": rows, "built": date.today().isoformat(), "versions": nitems}
    viewer = (HERE.parent / "atlas" / "viewer.js").read_text(encoding="utf-8")
    html = (HERE / "mindmap.html").read_text(encoding="utf-8").replace("__VIEWER__", viewer)
    out.write_text(html.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    print(f"{len(cur.G)} mind maps, {len(rows)} items → {out}")


if __name__ == "__main__":
    main()
