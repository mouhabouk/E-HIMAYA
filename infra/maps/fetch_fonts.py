"""ء-حماية / e-Himaya — installs the label glyphs of the Office's map server into /data/fonts (docs/offline-maps.md).

Downloads the OpenMapTiles fonts release (Noto Sans and others, SIL Open Font License 1.1, glyph PBFs ready for
MapLibre) once, on a machine with internet, and unpacks it. Set MAPS_FONTS_SHA256 to the checksum recorded in the
guide to refuse any other file. Standard library only (python:3.12-slim).

Environment:
  MAPS_FONTS_URL     release zip (default: openmaptiles/fonts v2.0)
  MAPS_FONTS_SHA256  expected SHA-256 of the zip (recommended)
  MAPS_FONTS_OUT     output folder (default /data/fonts)
"""

import hashlib
import os
import sys
import urllib.request
import zipfile

DEFAULT_URL = "https://github.com/openmaptiles/fonts/releases/download/v2.0/v2.0.zip"
ARABIC_GLYPHS = "1536-1791.pbf"


def main() -> int:
    url = os.environ.get("MAPS_FONTS_URL", DEFAULT_URL)
    expected = os.environ.get("MAPS_FONTS_SHA256", "").strip().lower()
    out = os.environ.get("MAPS_FONTS_OUT", "/data/fonts")
    if os.path.isfile(os.path.join(out, "Noto Sans Regular", ARABIC_GLYPHS)):
        print(f"fonts already installed in {out}")
        return 0
    os.makedirs(out, exist_ok=True)
    part = os.path.join(out, "fonts.zip.part")
    print(f"downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "e-Himaya offline map preparation"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=120) as response, open(part, "wb") as f:  # noqa: S310 (operator URL)
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            f.write(chunk)
    got = digest.hexdigest()
    if expected and got != expected:
        os.remove(part)
        print(f"checksum mismatch: expected {expected}, got {got} (refusing the fonts)")
        return 1
    print(f"sha256 {got}" + ("" if expected else "  (record it as MAPS_FONTS_SHA256)"))
    with zipfile.ZipFile(part) as z:
        for member in z.namelist():
            target = os.path.realpath(os.path.join(out, member))
            if not target.startswith(os.path.realpath(out) + os.sep):
                print(f"refusing {member}: outside {out}")
                return 1
        z.extractall(out)
    os.remove(part)
    if not os.path.isfile(os.path.join(out, "Noto Sans Regular", ARABIC_GLYPHS)):
        print(f"warning: Noto Sans Regular has no {ARABIC_GLYPHS}: Arabic labels need another font stack")
    stacks = sorted(d for d in os.listdir(out) if os.path.isdir(os.path.join(out, d)))
    print(f"installed {len(stacks)} font stacks in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
