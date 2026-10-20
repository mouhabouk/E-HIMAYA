"""Download and check the detectors of the vision service (standard library only, no ML framework).

Run once per installation (Docker target "models", CI). The runtime service never downloads anything: the models
live in VISION_MODELS_DIR on our own servers (NFR-10, NFR-11). Every file is pinned by SHA-256; a mismatch stops
the installation. Only permissively licensed models are listed (README.md, "Licences"; ADR-08: no AGPL).

    python models/fetch_models.py --out /models
    python models/fetch_models.py --out /models --file fire-smoke=/path/fire-smoke-yolox-tiny.onnx   # local copy
"""

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

COCO_PERSON_ONLY: list[str | None] = ["person", *([None] * 79)]

MODELS: dict[str, dict[str, Any]] = {
    # Fire and smoke: YOLOX-Tiny fine-tuned by e-Himaya (services/vision/training, EVALUATION.md).
    "fire-smoke": {
        "name": "ehimaya-fire-smoke-yolox-tiny",
        "version": "2.0.0",
        "license": "Apache-2.0",
        # Our own weights ship in the repository (20 MB): the repository is private, so no anonymous download URL.
        "bundled": "weights/fire-smoke-yolox-tiny-v2.onnx",
        "sha256": "3b9f2b5f8513ad76a1817a18614bfc73c4d625f5fcf2f3952ed1839ae43339b6",
        "source": "e-Himaya: YOLOX-Tiny (Megvii, Apache-2.0) fine-tuned on Open Images V7 fire/smoke images "
        "(images CC BY 2.0, labels CC BY 4.0, Google LLC; boxes drawn by Grounding DINO, Apache-2.0), "
        "FireNET by Moses Olafenwa (MIT, github.com/OlafenwaMoses/FireNET) and the FURG fire dataset by "
        "Steffens et al. (CC0-1.0, github.com/steffensbola/furg-fire-dataset); see services/vision/training",
        "format": "yolox",
        "input_size": [416, 416],
        "labels": ["fire", "smoke"],
        # Raw score r becomes r ** power, so that the threshold reaching precision 0.80 maps to 0.45 (EVALUATION.md):
        # fire fitted on eval/calibration.json (raw 0.24); smoke on the training-validation split pooled with
        # eval/calibration.json (raw 0.34). Neither set overlaps the evaluation sample.
        "score_power": {"fire": 0.56, "smoke": 0.74},
    },
    # People: the official YOLOX-Tiny COCO model (Megvii, release 0.1.1rc0), only the "person" class is used.
    "person": {
        "name": "yolox-tiny-coco-person",
        "version": "0.1.1rc0",
        "license": "Apache-2.0",
        "url": "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx",
        "sha256": "427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7",
        "source": "https://github.com/Megvii-BaseDetection/YOLOX (COCO 2017, AP 32.8)",
        "format": "yolox",
        "input_size": [416, 416],
        "labels": COCO_PERSON_ONLY,
    },
}
ALLOWED_LICENSES = {"MIT", "Apache-2.0", "BSD-3-Clause", "CC-BY-4.0"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_for(spec: dict[str, Any]) -> dict[str, Any]:
    return {**{k: v for k, v in spec.items() if k != "bundled"}, "file": "model.onnx"}


def installed(target: Path, spec: dict[str, Any]) -> bool:
    """Same manifest (weights, labels, calibration) and intact weights: nothing to do."""
    try:
        manifest = json.loads((target / "manifest.json").read_text())
    except (OSError, ValueError):
        return False
    return bool(manifest == manifest_for(spec)) and sha256(target / "model.onnx") == spec["sha256"]


def fetch(out: Path, key: str, spec: dict[str, Any], local: Path | None) -> None:
    if spec["license"] not in ALLOWED_LICENSES:
        sys.exit(f"{key}: licence {spec['license']} is not in the accepted list {sorted(ALLOWED_LICENSES)}")
    target = out / key
    if installed(target, spec):
        print(f"= {key}: {spec['name']} {spec['version']} already installed")
        return
    if local is None and "bundled" in spec:
        local = Path(__file__).resolve().parent / spec["bundled"]
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        download = Path(tmp) / "model.onnx"
        if local is not None:
            shutil.copyfile(local, download)
        else:
            print(f"↓ {key}: {spec['url']}", flush=True)
            request = urllib.request.Request(spec["url"], headers={"User-Agent": "ehimaya-vision-fetch"})  # noqa: S310
            with urllib.request.urlopen(request, timeout=300) as response, download.open("wb") as handle:  # noqa: S310
                shutil.copyfileobj(response, handle)
        actual = sha256(download)
        if actual != spec["sha256"]:
            sys.exit(f"{key}: SHA-256 mismatch: expected {spec['sha256']}, got {actual}")
        staged = Path(tmp) / key
        staged.mkdir()
        download.rename(staged / "model.onnx")
        (staged / "manifest.json").write_text(json.dumps(manifest_for(spec), ensure_ascii=False, indent=2))
        if target.exists():
            shutil.rmtree(target)
        staged.rename(target)  # atomic on the same file system: the service never sees a half-written model
    print(f"✓ {key}: {spec['name']} {spec['version']} ({spec['license']}) sha256 {spec['sha256'][:12]}…")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", action="append", choices=sorted(MODELS), help="install only these models")
    parser.add_argument("--file", action="append", default=[], help="KEY=PATH: install from a local file")
    args = parser.parse_args()
    local = {k: Path(v) for k, v in (item.split("=", 1) for item in args.file)}
    args.out.mkdir(parents=True, exist_ok=True)
    for key in args.only or MODELS:
        fetch(args.out, key, MODELS[key], local.get(key))


if __name__ == "__main__":
    main()
