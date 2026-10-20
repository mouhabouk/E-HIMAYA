"""Evaluate the installed detectors on the pinned, held-out sample set (``eval/samples.json``).

Frame-level (image-level) precision and recall per label: a frame counts as "fire detected" when at least one fire
box reaches the threshold. That is the decision the live pipeline makes (one frame → alert candidate). Open Images
has no fire/smoke *boxes*, so box-level mAP cannot be measured on this sample; the ground truth is the
human-verified image-level labels. Images sampled for people (no fire/smoke label proposed) count as negatives for
fire and smoke. Also measures the CPU latency per frame (letterbox + every enabled model + post-processing).

    VISION_MODELS_DIR=/models python eval/evaluate.py [--threads 2] [--json eval/results.json]

The images are downloaded once into eval/cache/ and checked against their SHA-256.
"""

import argparse
import hashlib
import io
import json
import os
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("VISION_API_TOKEN", "evaluation-only-token-000000")
os.environ.setdefault("VISION_CALLBACK_TOKEN", "evaluation-only-token-000000")

from app.config import get_settings  # noqa: E402
from app.imaging import decode  # noqa: E402
from app.models import Detectors  # noqa: E402

LABELS = ("fire", "smoke", "person")
THRESHOLDS = (0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7)
MIN_CONFIDENCE = 0.45  # VISION_MIN_CONFIDENCE of the API: the calibrated operating point


def fetch(sample: dict, cache: Path) -> bytes:
    path = cache / f"{sample['id']}.jpg"
    if not path.exists():
        with urllib.request.urlopen(sample["url"], timeout=60) as response:  # noqa: S310 (pinned https URL)
            path.write_bytes(response.read())
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != sample["sha256"]:
        path.unlink()
        raise SystemExit(f"{sample['id']}: SHA-256 mismatch, refusing to evaluate on a changed image")
    return payload


def truth(sample: dict, label: str) -> int | None:
    value = sample["labels"].get(label)
    if value is None and label in ("fire", "smoke") and sample["group"] in ("person", "no_person"):
        return 0  # ordinary scene: assumed free of fire and smoke
    return value


def scores(found: dict[str, float], samples: list[dict], label: str, threshold: float) -> dict[str, float]:
    tp = fp = fn = tn = 0
    for sample in samples:
        expected = truth(sample, label)
        if expected is None:
            continue
        predicted = found[sample["id"]].get(label, 0.0) >= threshold
        tp += predicted and expected == 1
        fp += predicted and expected == 0
        fn += not predicted and expected == 1
        tn += not predicted and expected == 0
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else float("nan")
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1}


def fit_powers(found: dict[str, dict[str, float]], samples: list[dict], labels: set[str], precision: float) -> None:
    """score' = score ** power, with power such that the lowest raw threshold reaching the target precision becomes
    MIN_CONFIDENCE (0.45). A precision target, not best F1: every false alarm costs an operator's attention."""
    import math

    for label in ("fire", "smoke"):
        if label not in labels:
            continue
        rows = {t / 100: scores(found, samples, label, t / 100) for t in range(5, 96)}
        good = [t for t, r in rows.items() if r["tp"] >= 20 and r["precision"] >= precision]
        if not good:
            print(f"{label}: precision {precision} not reached with 20 true positives on this set: no calibration")
            continue
        best = min(good)
        row = rows[best]
        power = math.log(MIN_CONFIDENCE) / math.log(best)
        print(
            f"{label}: raw threshold {best:.2f} (P {row['precision']:.3f} R {row['recall']:.3f}, "
            f"TP {row['tp']} FP {row['fp']}) → score_power {power:.3f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--samples", type=Path, default=HERE / "samples.json")
    parser.add_argument("--cache", type=Path, default=HERE / "cache")
    parser.add_argument("--threads", type=int, default=2, help="ONNX Runtime threads per inference")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", type=Path)
    parser.add_argument(
        "--fit",
        action="store_true",
        help="ignore the manifest calibration and print the score_power that puts the threshold reaching "
        "--precision at 0.45 (run on eval/calibration.json, never on the evaluation sample)",
    )
    parser.add_argument("--precision", type=float, default=0.8, help="target precision of --fit")
    args = parser.parse_args()

    settings = get_settings()
    settings.inference_threads = args.threads
    settings.min_confidence = min(THRESHOLDS)
    detectors = Detectors()
    models = detectors.get()
    if args.fit:
        settings.min_confidence = 0.05
        for model in models:
            model.manifest.score_power.clear()
    document = json.loads(args.samples.read_text())
    samples = document["samples"][: args.limit or None]
    args.cache.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(8) as pool:
        payloads = list(pool.map(lambda s: fetch(s, args.cache), samples))

    found: dict[str, dict[str, float]] = {}
    latencies: list[float] = []
    for sample, payload in zip(samples, payloads, strict=True):
        image = decode(payload, "image/jpeg", settings.max_image_pixels)
        started = time.perf_counter()
        detections = detectors.detect(image)
        latencies.append(time.perf_counter() - started)
        best: dict[str, float] = {}
        for d in detections:
            best[d.label] = max(best.get(d.label, 0.0), d.confidence)
        found[sample["id"]] = best

    # Latency on a 720p frame, the size the stream watcher hands over (after warm-up).
    frame = np.asarray(Image.open(io.BytesIO(payloads[0])).convert("RGB").resize((1280, 720)))
    for _ in range(3):
        detectors.detect(frame)
    frame_times = []
    for _ in range(20):
        started = time.perf_counter()
        detectors.detect(frame)
        frame_times.append(time.perf_counter() - started)

    results: dict = {
        "models": [f"{m.manifest.name}@{m.manifest.version}" for m in models],
        "samples": len(samples),
        "threads": args.threads,
        "cpu": os.cpu_count(),
        "latency_ms": {
            "per_image_mean": round(statistics.mean(latencies) * 1000, 1),
            "per_image_p95": round(sorted(latencies)[int(len(latencies) * 0.95) - 1] * 1000, 1),
            "frame_720p_median": round(statistics.median(frame_times) * 1000, 1),
            "frame_720p_p95": round(sorted(frame_times)[18] * 1000, 1),
        },
        "labels": {},
    }
    print(f"models: {', '.join(results['models'])} · {len(samples)} images · {args.threads} threads")
    print(f"latency: {results['latency_ms']}")
    print("\n| label | threshold | precision | recall | F1 | TP | FP | FN | TN |")
    print("|---|---|---|---|---|---|---|---|---|")
    available = {label for m in models for label in m.manifest.labels if label}
    for label in LABELS:
        if label not in available:
            continue
        rows = {str(t): scores(found, samples, label, t) for t in THRESHOLDS}
        results["labels"][label] = rows
        for threshold, row in rows.items():
            print(
                f"| {label} | {threshold} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} "
                f"| {row['tp']} | {row['fp']} | {row['fn']} | {row['tn']} |"
            )
    # Share of frames flagged per sample group, at the API floor (0.45) and alert level (0.6).
    groups = sorted({sample["group"] for sample in samples})
    print("\n| group | images | " + " | ".join(f"{label} ≥ {t}" for label in LABELS for t in (0.45, 0.6)) + " |")
    print("|---|---|" + "---|" * 6)
    results["groups"] = {}
    for name in groups:
        members = [sample for sample in samples if sample["group"] == name]
        shares = {
            f"{label}@{t}": sum(found[m["id"]].get(label, 0.0) >= t for m in members) / len(members)
            for label in LABELS
            for t in (0.45, 0.6)
        }
        results["groups"][name] = {"images": len(members), **shares}
        print(f"| {name} | {len(members)} | " + " | ".join(f"{v:.2f}" for v in shares.values()) + " |")
    if args.fit:
        fit_powers(found, samples, available, args.precision)
    if args.json:
        args.json.write_text(json.dumps(results, indent=1) + "\n")


if __name__ == "__main__":
    main()
