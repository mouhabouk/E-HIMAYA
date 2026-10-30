"""ء-حماية / e-Himaya — writes the configuration of the Office's map server (TileServer GL, docs/offline-maps.md).

Run by the compose service "maps-config" before "maps" starts. It lists what is present in the data folder, so the
server starts with the vector tiles alone and serves the satellite imagery once it has been copied:
  /data/tunisia.mbtiles     OpenStreetMap vector tiles of Tunisia (Planetiler, OpenMapTiles schema)   required
  /data/satellite.mbtiles   satellite imagery (fetch_tiles.py or a GDAL import)                       optional
  /data/fonts/<stack>/      glyphs of the labels (fetch_fonts.py)                                     required
Styles come from /styles (infra/maps/styles, committed). Standard library only.
"""

import json
import os
import sys

DATA = os.environ.get("MAPS_DATA", "/data")
STYLES = os.environ.get("MAPS_STYLES", "/styles")
# Tunisia with a margin (apps/dashboard/src/lib/mapStyle.ts TUNISIA_BOUNDS).
BOUNDS = [7.4, 30.2, 11.7, 37.6]
ARABIC_GLYPHS = "1536-1791.pbf"


def main() -> int:
    if not os.path.isfile(os.path.join(DATA, "tunisia.mbtiles")):
        print(f"{DATA}/tunisia.mbtiles is missing: run the maps-prepare profile first (docs/offline-maps.md §3)")
        return 1
    fonts = os.path.join(DATA, "fonts")
    stacks = sorted(d for d in os.listdir(fonts) if os.path.isdir(os.path.join(fonts, d))) if os.path.isdir(fonts) else []
    if "Noto Sans Regular" not in stacks:
        print(f"{fonts}/Noto Sans Regular is missing: run fetch_fonts.py (docs/offline-maps.md §3)")
        return 1
    for stack in stacks:
        if not os.path.isfile(os.path.join(fonts, stack, ARABIC_GLYPHS)):
            print(f"warning: {stack} has no Arabic glyphs ({ARABIC_GLYPHS}); its Arabic labels will not show")

    data = {"tunisia": {"mbtiles": "tunisia.mbtiles"}}
    if os.path.isfile(os.path.join(DATA, "satellite.mbtiles")):
        data["satellite"] = {"mbtiles": "satellite.mbtiles"}
    else:
        print("no satellite.mbtiles yet: the imagery is not served (the labels style still is)")
    styles = {
        name: {"style": f"{name}.json", "tilejson": {"bounds": BOUNDS}}
        for name in ("ehimaya-streets", "ehimaya-labels")
        if os.path.isfile(os.path.join(STYLES, f"{name}.json"))
    }
    config = {
        "options": {
            "paths": {"root": DATA, "fonts": "fonts", "styles": STYLES, "mbtiles": DATA},
            "serveAllFonts": True,
            "maxScaleFactor": 2,
            "maxSize": 2048,
        },
        "styles": styles,
        "data": data,
    }
    with open(os.path.join(DATA, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"config.json: styles {', '.join(styles)}; data {', '.join(data)}; fonts {', '.join(stacks)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
