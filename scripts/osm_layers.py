"""Prepares the first load of the map layers from OpenStreetMap (phase B1, docs/phase-b/design.md §2.8).

While the Office's official lists are missing, hospitals, clinics, pharmacies, police stations and National Guard posts
of Tunisia are taken from OpenStreetMap (real public data, ODbL licence). This script writes one GeoJSON file per
layer, in the import format of the dashboard (``id``, ``name``, ``type``, ``phone``, ``address``, ``hours``,
``website``, ``email`` and a few extra columns). Import each file in its layer with "to be verified" ticked and the
source "OpenStreetMap contributors", licence "ODbL 1.0". The Office's lists later replace them (*replace* mode).

Nothing is invented: places without a name are left out and counted. Standard library only.

Usage (from the repository root)::

    python3 scripts/osm_layers.py --out build/osm                 # asks the Overpass API
    python3 scripts/osm_layers.py --input overpass.json --out build/osm   # an Overpass answer saved before

The Overpass query used is printed by ``--print-query`` (run it on overpass-turbo.eu to save the answer by hand).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

OVERPASS = "https://overpass-api.de/api/interpreter"
ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)"
USER_AGENT = "e-Himaya layer preparation (ONPC Tunisia)"

# Layer key → OpenStreetMap tags (key, value) that select its places. Order matters: a place goes to the first layer
# whose tags it has (a hospital tagged healthcare=clinic too stays a hospital).
LAYERS: dict[str, tuple[tuple[str, str], ...]] = {
    "hospitals": (("amenity", "hospital"), ("healthcare", "hospital")),
    "clinics": (("amenity", "clinic"), ("healthcare", "clinic"), ("healthcare", "centre")),
    "pharmacies": (("amenity", "pharmacy"), ("healthcare", "pharmacy")),
    "national_guard": (),  # police places operated by the National Guard, see _is_guard
    "police": (("amenity", "police"),),
}
_GUARD_WORDS = ("garde nationale", "الحرس الوطني", "national guard", "حرس")


def query() -> str:
    """Overpass QL: every node, way and relation of the tags above inside Tunisia (centres for areas)."""
    selectors = "".join(f'  nwr["{k}"="{v}"](area.tn);\n' for tags in LAYERS.values() for k, v in tags)
    head = '[out:json][timeout:300];\narea["ISO3166-1"="TN"][admin_level=2]->.tn;\n'
    return f"{head}(\n{selectors});\nout center tags;\n"


def fetch(endpoint: str) -> dict[str, Any]:
    data = urllib.parse.urlencode({"data": query()}).encode()
    request = urllib.request.Request(endpoint, data=data, headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(request, timeout=330) as response:  # noqa: S310 (fixed https endpoint by default)
        return json.load(response)


def _is_guard(tags: dict[str, str]) -> bool:
    text = " ".join(tags.get(k, "") for k in ("operator", "name", "name:fr", "name:ar", "police:FR")).lower()
    return tags.get("amenity") == "police" and any(w in text for w in _GUARD_WORDS)


def layer_of(tags: dict[str, str]) -> str | None:
    if _is_guard(tags):
        return "national_guard"
    for layer, selectors in LAYERS.items():
        if any(tags.get(k) == v for k, v in selectors):
            return layer
    return None


def _name(tags: dict[str, str]) -> str | None:
    for key in ("name", "name:ar", "name:fr", "official_name", "name:en"):
        value = (tags.get(key) or "").strip()
        if value:
            return value[:200]
    return None


def _address(tags: dict[str, str]) -> str | None:
    if tags.get("addr:full"):
        return tags["addr:full"].strip()
    street = " ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p)
    parts = [street, tags.get("addr:postcode", ""), tags.get("addr:city", "")]
    joined = ", ".join(p.strip() for p in parts if p and p.strip())
    return joined or None


def _type(layer: str, tags: dict[str, str]) -> str | None:
    if layer == "hospitals" and tags.get("emergency") == "yes":
        return "emergency"
    if layer in ("clinics", "hospitals"):
        return tags.get("healthcare:speciality") or tags.get("operator:type") or None
    return None


def feature(element: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None, str | None]:
    """(layer, GeoJSON feature, reason left out). Ways and relations use the centre Overpass gives."""
    tags: dict[str, str] = element.get("tags") or {}
    layer = layer_of(tags)
    if layer is None:
        return None, None, "other"
    lat = element.get("lat", (element.get("center") or {}).get("lat"))
    lon = element.get("lon", (element.get("center") or {}).get("lon"))
    if lat is None or lon is None:
        return layer, None, "no_position"
    name = _name(tags)
    if name is None:
        return layer, None, "no_name"
    props: dict[str, Any] = {
        # A stable identifier: a later run updates the same place instead of adding a duplicate.
        "id": f"osm-{element['type']}-{element['id']}",
        "name": name,
        "type": _type(layer, tags),
        "phone": tags.get("phone") or tags.get("contact:phone"),
        "address": _address(tags),
        "hours": tags.get("opening_hours"),
        "website": tags.get("website") or tags.get("contact:website"),
        "email": tags.get("email") or tags.get("contact:email"),
        "name_ar": tags.get("name:ar"),
        "name_fr": tags.get("name:fr"),
        "operator": tags.get("operator"),
        "beds": tags.get("beds"),
        "emergency": tags.get("emergency"),
    }
    props = {k: v for k, v in props.items() if v not in (None, "")}
    geometry = {"type": "Point", "coordinates": [round(float(lon), 7), round(float(lat), 7)]}
    return layer, {"type": "Feature", "id": props["id"], "geometry": geometry, "properties": props}, None


def convert(answer: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], Counter[str]]:
    by_layer: dict[str, list[dict[str, Any]]] = {layer: [] for layer in LAYERS}
    left_out: Counter[str] = Counter()
    seen: set[str] = set()
    for element in answer.get("elements", []):
        layer, feat, reason = feature(element)
        if reason == "other" or layer is None:
            continue
        if feat is None:
            left_out[f"{layer}:{reason}"] += 1
            continue
        if feat["id"] in seen:
            continue
        seen.add(feat["id"])
        by_layer[layer].append(feat)
    for features in by_layer.values():
        features.sort(key=lambda f: (f["properties"]["name"], f["id"]))
    return by_layer, left_out


def write(by_layer: dict[str, list[dict[str, Any]]], out: Path, timestamp: str | None) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for layer, features in by_layer.items():
        doc = {
            "type": "FeatureCollection",
            "attribution": ATTRIBUTION,
            "osm_timestamp": timestamp,
            "features": features,
        }
        path = out / f"osm-{layer}.geojson"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("build/osm"), help="folder of the GeoJSON files")
    parser.add_argument("--input", type=Path, help="an Overpass JSON answer saved before (no network)")
    parser.add_argument("--endpoint", default=OVERPASS, help="Overpass API endpoint")
    parser.add_argument("--print-query", action="store_true", help="print the Overpass query and stop")
    args = parser.parse_args(argv)
    if args.print_query:
        print(query())
        return 0
    answer = json.loads(args.input.read_text(encoding="utf-8")) if args.input else fetch(args.endpoint)
    by_layer, left_out = convert(answer)
    timestamp = (answer.get("osm3s") or {}).get("timestamp_osm_base")
    for path in write(by_layer, args.out, timestamp):
        print(f"{path}: {len(json.loads(path.read_text(encoding='utf-8'))['features'])} places")
    for reason, count in sorted(left_out.items()):
        print(f"left out {reason}: {count}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
