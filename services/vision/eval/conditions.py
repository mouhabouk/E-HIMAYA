"""False negatives of the fire and smoke detector by condition (docs/phase-l/design-l5.md §4.1, model cards).

For every fire (or smoke) positive of ``eval/samples.json`` tagged in ``eval/conditions.json``: day or night, clear or
smoke and fog, near or far, indoor or outdoor. A positive is missed when no box of its label reaches the threshold
(the frame-level decision of EVALUATION.md). Each rate comes with its 95 % Wilson interval and is flagged ``small``
below 30 images: such a figure says little and the model card says so.

    VISION_MODELS_DIR=/models python eval/conditions.py [--json eval/conditions-results.json]
"""

import argparse
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from evaluate import fetch  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.imaging import decode  # noqa: E402
from app.models import Detectors  # noqa: E402

THRESHOLDS = (0.45, 0.6)
DIMENSIONS = {
    "light": ("day", "night"),
    "visibility": ("clear", "smoke_or_fog"),
    "distance": ("near", "far"),
    "setting": ("indoor", "outdoor"),
}
SMALL = 30


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def rates(scores: list[float]) -> dict:
    n = len(scores)
    out: dict = {"images": n, "small": n < SMALL}
    for t in THRESHOLDS:
        missed = sum(score < t for score in scores)
        low, high = wilson(missed, n)
        out[str(t)] = {
            "missed": missed,
            "rate": round(missed / n, 3) if n else None,
            "interval": [round(low, 3), round(high, 3)] if n else None,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--samples", type=Path, default=HERE / "samples.json")
    parser.add_argument("--tags", type=Path, default=HERE / "conditions.json")
    parser.add_argument("--cache", type=Path, default=HERE / "cache")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    settings = get_settings()
    settings.inference_threads = args.threads
    settings.min_confidence = min(THRESHOLDS)
    detectors = Detectors()
    models = detectors.get()
    tags = json.loads(args.tags.read_text())
    samples = [s for s in json.loads(args.samples.read_text())["samples"] if s["id"] in tags["tags"]]
    args.cache.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(8) as pool:
        payloads = list(pool.map(lambda s: fetch(s, args.cache), samples))
    best: dict[str, dict[str, float]] = {}
    for sample, payload in zip(samples, payloads, strict=True):
        found: dict[str, float] = {}
        for d in detectors.detect(decode(payload, "image/jpeg", settings.max_image_pixels)):
            found[d.label] = max(found.get(d.label, 0.0), d.confidence)
        best[sample["id"]] = found

    results: dict = {
        "models": [f"{m.manifest.name}@{m.manifest.version}" for m in models],
        "measured_on": date.today().isoformat(),
        "tags_reviewed": bool(tags.get("reviewed")),
        "labels": {},
    }
    for label in ("fire", "smoke"):
        positives = [s for s in samples if s["labels"].get(label) == 1]
        tagged = [s for s in positives if tags["tags"][s["id"]] is not None]
        row: dict = {"all": rates([best[s["id"]].get(label, 0.0) for s in positives]), "conditions": {}}
        for dimension, values in DIMENSIONS.items():
            if label == "smoke" and dimension == "visibility":
                continue  # every smoke picture is smoky
            row["conditions"][dimension] = {
                value: rates(
                    [best[s["id"]].get(label, 0.0) for s in tagged if tags["tags"][s["id"]][dimension] == value]
                )
                for value in values
            }
        results["labels"][label] = row

    print(f"models: {', '.join(results['models'])}")
    print("\n| label | condition | images | missed at 0.45 | 95 % interval | missed at 0.6 | |")
    print("|---|---|---|---|---|---|---|")
    for label, row in results["labels"].items():
        groups = [("all", row["all"])] + [
            (f"{dimension}: {value}", r)
            for dimension, values in row["conditions"].items()
            for value, r in values.items()
        ]
        for name, r in groups:
            if not r["images"]:
                continue
            a, b = r["0.45"], r["0.6"]
            note = "small sample" if r["small"] else ""
            print(
                f"| {label} | {name} | {r['images']} | {a['missed']} ({a['rate']:.0%}) "
                f"| {a['interval'][0]:.0%}–{a['interval'][1]:.0%} | {b['missed']} ({b['rate']:.0%}) | {note} |"
            )
    if args.json:
        args.json.write_text(json.dumps(results, indent=1) + "\n")


if __name__ == "__main__":
    main()
