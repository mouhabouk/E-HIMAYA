"""Evaluate the installed detectors on a held-out set with human boxes in YOLO format (``images/`` + ``labels/``).

Used for the test splits of the extra datasets (training/extra_datasets.py: FireNET's validation split, held-out
FURG videos). Reports, per label present in the set:

* frame-level recall at the API thresholds (a frame counts when one box of the label reaches the threshold) and,
  when the set has frames without that label, frame-level precision;
* box-level average precision at IoU 0.5 (AP50, all-point interpolation) and box recall at each threshold.

    VISION_MODELS_DIR=/models python eval/evaluate_yolo.py --dir work/extra/firenet/test --classes fire,smoke

Images whose labels file is missing count as having no box.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("VISION_API_TOKEN", "evaluation-only-token-000000")
os.environ.setdefault("VISION_CALLBACK_TOKEN", "evaluation-only-token-000000")

from app.config import get_settings  # noqa: E402
from app.models import Detectors  # noqa: E402

THRESHOLDS = (0.25, 0.45, 0.6)


def iou(box: np.ndarray, others: np.ndarray) -> np.ndarray:
    x1 = np.maximum(box[0], others[:, 0])
    y1 = np.maximum(box[1], others[:, 1])
    x2 = np.minimum(box[2], others[:, 2])
    y2 = np.minimum(box[3], others[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = (others[:, 2] - others[:, 0]) * (others[:, 3] - others[:, 1])
    return np.asarray(inter / np.maximum(area + areas - inter, 1e-9))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--classes", required=True, help="label names of the YOLO class ids, e.g. fire,smoke")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    names = args.classes.split(",")

    settings = get_settings()
    settings.inference_threads = args.threads
    settings.min_confidence = 0.05
    detectors = Detectors()
    models = detectors.get()

    truth: dict[str, dict[str, np.ndarray]] = {}
    found: dict[str, list[tuple[str, float, tuple[float, ...]]]] = {}
    for image_path in sorted((args.dir / "images").glob("*.jpg")):
        boxes: dict[str, list[list[float]]] = {name: [] for name in names}
        label_path = args.dir / "labels" / f"{image_path.stem}.txt"
        for line in label_path.read_text().splitlines() if label_path.exists() else []:
            if line.strip():
                cls, cx, cy, w, h = (float(v) for v in line.split()[:5])
                boxes[names[int(cls)]].append([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])
        truth[image_path.stem] = {k: np.array(v, dtype=np.float64).reshape(-1, 4) for k, v in boxes.items()}
        image = np.asarray(Image.open(image_path).convert("RGB"))
        found[image_path.stem] = [(d.label, d.confidence, d.box) for d in detectors.detect(image)]

    results: dict = {"models": [f"{m.manifest.name}@{m.manifest.version}" for m in models], "set": str(args.dir)}
    print(f"models: {', '.join(results['models'])} · {len(truth)} images in {args.dir}")
    print("\n| label | images with label | boxes | AP50 | threshold | frame precision | frame recall | box recall |")
    print("|---|---|---|---|---|---|---|---|")
    for name in names:
        positives = [k for k, v in truth.items() if len(v[name])]
        total_boxes = sum(len(v[name]) for v in truth.values())
        if not positives:
            continue
        # Box-level AP50: detections sorted by confidence, greedily matched to unmatched ground-truth boxes.
        detections = sorted(
            ((conf, key, np.array(box)) for key, items in found.items() for label, conf, box in items if label == name),
            key=lambda item: -item[0],
        )
        matched = {key: np.zeros(len(v[name]), dtype=bool) for key, v in truth.items()}
        hits = []
        for _conf, key, box in detections:
            gt = truth[key][name]
            if len(gt):
                overlaps = iou(box, gt)
                overlaps[matched[key]] = 0
                best = int(overlaps.argmax())
                if overlaps[best] >= 0.5:
                    matched[key][best] = True
                    hits.append(True)
                    continue
            hits.append(False)
        hit_array = np.array(hits, dtype=bool)
        recall_curve = np.cumsum(hit_array) / total_boxes
        precision_curve = np.cumsum(hit_array) / np.arange(1, len(hit_array) + 1)
        envelope = np.maximum.accumulate(precision_curve[::-1])[::-1] if len(hits) else np.zeros(0)
        steps = np.diff(np.concatenate([[0.0], recall_curve]))
        ap50 = float((steps * envelope).sum())
        rows = {}
        for threshold in THRESHOLDS:
            flagged = {k for k, items in found.items() if any(lab == name and c >= threshold for lab, c, _ in items)}
            negatives = [k for k in truth if k not in positives]
            tp = len(flagged & set(positives))
            fp = len(flagged & set(negatives))
            box_recall = float(hit_array[[d[0] >= threshold for d in detections]].sum()) / total_boxes
            rows[str(threshold)] = {
                "frame_recall": tp / len(positives),
                "frame_precision": tp / (tp + fp) if negatives and tp + fp else None,
                "box_recall": box_recall,
                "tp": tp,
                "fp": fp,
            }
            precision = rows[str(threshold)]["frame_precision"]
            print(
                f"| {name} | {len(positives)} | {total_boxes} | {ap50:.3f} | {threshold} | "
                f"{'—' if precision is None else f'{precision:.3f}'} | {tp / len(positives):.3f} | {box_recall:.3f} |"
            )
        results[name] = {"images": len(positives), "boxes": total_boxes, "ap50": ap50, "thresholds": rows}
    if args.json:
        args.json.write_text(json.dumps(results, indent=1) + "\n")


if __name__ == "__main__":
    main()
