"""Builds the administrative reference of migration 0079 from a checkout of Map Tunisia (docs/phase-m/design-m.md).

Map Tunisia (https://github.com/Alaa-Taieb/map-tunisia, data ODbL 1.0, © OpenStreetMap contributors) publishes the
nested boundaries of Tunisia cross-checked against the INS 2024 nomenclature. This script keeps the "high" level of
detail (about 20 m), drops the fields the system does not use (Tifinagh, SVG frame), and writes gzip files into
``services/api/seed/geo/admin/``, with their SHA-256 in ``SOURCE.md``. Run it only to take a newer release:

    git clone --depth 1 https://github.com/Alaa-Taieb/map-tunisia /tmp/map-tunisia
    python3 scripts/admin_reference.py /tmp/map-tunisia          # --check: compare with the committed files

Our délégations keep their internal ids (``TN-61-12``); each is tied to its INS code through Map Tunisia's
``name_fr_ins`` (the INS spelling, the same list ours was taken from). The script stops when one does not match.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "services/api/seed/geo/admin"
OURS = ROOT / "services/api/seed/delegations.csv"
LOD = "high"

KEEP = {
    "governorates": ("iso_3166_2", "ins_code", "name_en", "region", "district", "population_2014",
                     "population_2024", "area_km2", "label_lon", "label_lat"),
    "delegations": ("ins_code", "governorate", "ehimaya_name_fr", "name_fr_ins", "name_en", "name_fr", "name_ar", "population_2014",
                    "population_2024", "hasc", "wikidata", "osm_relation", "area_km2", "label_lon", "label_lat"),
    "sectors": ("id", "ins_code", "delegation", "governorate", "name_en", "name_fr", "name_ar", "osm_relation",
                "area_km2", "label_lon", "label_lat"),
    "municipalities": ("id", "governorate", "name_en", "name_fr", "name_ar", "osm_relation", "area_km2", "label_lon",
                       "label_lat"),
    "water": ("id", "type", "governorate", "governorates", "name_en", "name_fr", "name_ar", "salt", "intermittent",
              "area_km2", "label_lon", "label_lat"),
    "cities": ("id", "type", "capital_of", "governorate", "delegation", "sector", "municipality", "name_en", "name_fr",
               "name_ar", "place"),
}
TABLES = {"regions": ("id", "code", "name_en", "name_fr", "name_ar", "governorates"),
          "districts": ("id", "number", "name_en", "name_fr", "name_ar", "governorates")}


def _rows(src: Path, name: str) -> dict[str, dict[str, str]]:
    with (src / "dist/data" / f"{name}.csv").open(encoding="utf-8", newline="") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


def _gz(data: bytes) -> bytes:
    buf = io.BytesIO()
    # mtime=0: the same input gives the same bytes, so --check can compare.
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as fh:
        fh.write(data)
    return buf.getvalue()


def _match_delegations(rows: dict[str, dict[str, str]]) -> None:
    """Adds ``ehimaya_name_fr``, the name of our délégation, to each row: the key migration 0079 joins on."""
    with OURS.open(encoding="utf-8", newline="") as fh:
        ours = {(int(r["gouvernorat_code"]), r["name_fr"].casefold()): r["name_fr"] for r in csv.DictReader(fh)}
    for row in rows.values():
        gov = int(row["governorate"][3:])
        row["ehimaya_name_fr"] = ours.pop((gov, row["name_fr_ins"].casefold()), "") or ours.pop(
            (gov, row["name_fr"].casefold()), ""
        )
    unmatched = [r["id"] for r in rows.values() if not r["ehimaya_name_fr"]]
    if ours or unmatched:
        sys.exit(f"délégations without a match: ours {sorted(ours.values())}, theirs {unmatched}")


def build(src: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for name, keep in KEEP.items():
        attrs = _rows(src, name)
        if name == "delegations":
            _match_delegations(attrs)
        geo = json.loads((src / "dist/geojson" / f"tunisia-{name}-{LOD}.geojson").read_text(encoding="utf-8"))
        features = []
        for f in sorted(geo["features"], key=lambda f: f["properties"]["id"]):
            row = {**f["properties"], **attrs.get(f["properties"]["id"], {})}
            features.append({"type": "Feature", "properties": {k: row.get(k, "") for k in keep},
                             "geometry": f["geometry"]})
        body = json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False,
                          separators=(",", ":"))
        files[f"{name}.geojson.gz"] = _gz(body.encode())
    for name, keep in TABLES.items():
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(keep)
        for row in _rows(src, name).values():
            writer.writerow([row[k] for k in keep])
        files[f"{name}.csv"] = buf.getvalue().encode()
    commit = subprocess.run(["git", "-C", str(src), "log", "-1", "--format=%H %cs"], capture_output=True, text=True,
                            check=False).stdout.strip() or "unknown"
    lines = [
        "# Administrative reference (Map Tunisia)",
        "",
        "Generated by `scripts/admin_reference.py`; loaded by migration `0079_admin_reference`. Do not edit by hand.",
        "",
        f"* Source: [Map Tunisia](https://github.com/Alaa-Taieb/map-tunisia), commit `{commit}`, level `{LOD}` (~20 m).",
        "* Licence: Open Database License 1.0. Credit wherever the boundaries are shown:",
        "  «Map data © OpenStreetMap contributors · Map Tunisia by Alaa Taieb».",
        "* Census figures: INS (RGPH 2014 and 2024); délégations created after 2014: ISIE lists.",
        "",
        "| File | SHA-256 |",
        "|---|---|",
        *(f"| `{n}` | `{hashlib.sha256(d).hexdigest()}` |" for n, d in sorted(files.items())),
        "",
    ]
    files["SOURCE.md"] = "\n".join(lines).encode()
    return files


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--check"]
    if len(args) != 1:
        print(__doc__)
        return 2
    files = build(Path(args[0]))
    if "--check" in sys.argv:
        stale = [n for n, d in files.items() if not (OUT / n).exists() or (OUT / n).read_bytes() != d]
        print("up to date" if not stale else f"stale: {stale}")
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (OUT / name).write_bytes(data)
    print(f"wrote {len(files)} files to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
