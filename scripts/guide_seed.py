"""Writes the app's bundled copy of the emergency guide from the seeds of migrations 0033 and 0036.

The app shows this copy on a first launch without network, then replaces it with the published
guide. Run from ``services/api`` after changing the seed: ``uv run python ../../scripts/guide_seed.py``
(``--check`` only compares).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "services/api/migrations/versions"
ASSET = ROOT / "apps/mobile/assets/emergency_guide.json"


def _module(name: str):
    sys.path.insert(0, str(ROOT / "services/api"))
    spec = importlib.util.spec_from_file_location(f"guide_{name}", MIGRATIONS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed() -> list:
    """The first load (0033), then the topics and items 0036 adds, in the order the migrations write them."""
    seed = [
        (key, icon, colour, title, list(items))
        for key, icon, colour, title, items in _module("0033_emergency_guide").SEED
    ]
    more = _module("0036_emergency_guide_more")
    seed += [(key, icon, colour, title, []) for key, (icon, colour, title) in more.NEW_TOPICS.items()]
    by_key = {topic[0]: topic for topic in seed}
    for key, items in more.MORE:
        by_key[key][4].extend(items)
    return seed


def render() -> str:
    topics = []
    for key, icon, colour, title, items in _seed():
        topics.append(
            {
                "id": f"seed-{key}",
                "key": key,
                "title": title,
                "icon": icon,
                "colour": colour,
                "items": [
                    {
                        "id": f"seed-{key}-{n}",
                        "content": {"ar": ar, "fr": fr, "en": en},
                        "call_198": call,
                        "validated": False,
                    }
                    for n, (call, ar, fr, en) in enumerate(items)
                ],
            }
        )
    return json.dumps({"revision": 0, "topics": topics}, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        if ASSET.read_text(encoding="utf-8") != text:
            print(f"{ASSET.relative_to(ROOT)} is out of date: run scripts/guide_seed.py from services/api")
            return 1
        return 0
    ASSET.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
