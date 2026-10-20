"""Step 1/4 of the fire-and-smoke detector: select and download the training images (Open Images V7, train split).

Open Images has no fire or smoke *boxes*, but it has human-verified *image-level* labels ("Fire", "Smoke",
"Flame", …: verified present = 1, verified absent = 0). We keep:
  * every train image verified to show fire or smoke (positives, boxed by the teacher in step 2),
  * images verified NOT to show them although a classifier proposed it (hard negatives: sunsets, lamps, fog…),
  * a sample of ordinary scenes with people (background, so that people and lights are not taken for fire).

Licences: the images are listed by Open Images as CC BY 2.0, the annotations are CC BY 4.0 (Google LLC). The
validation and test splits are never used here: they are the held-out evaluation set (eval/evaluate.py).

    python training/build_dataset.py --out training/work/data
"""

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

# Train and validation splits; the test split is kept for the evaluation (eval/evaluate.py).
# V7 labels: about 2.7 times more verified fire and smoke images than the V5 files used for model 1.0.0.
SPLITS = {
    "train": "https://storage.googleapis.com/openimages/v7/oidv7-train-annotations-human-imagelabels.csv",
    "validation": "https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv",
}
# The public mirror only holds part of the train split (the "boxable" subset); missing images are skipped.
IMAGE_URL = "https://open-images-dataset.s3.amazonaws.com/{}/{}.jpg"
FIRE = {"/m/02_41", "/m/01f415", "/m/0fjy1", "/m/012ckm", "/m/019mk7"}  # Fire, Flame, Wildfire, Bonfire, Campfire
SMOKE = {"/m/06q40"}
PERSON = "/m/01g317"
MAX_SIDE = 640
SAMPLE = {f"{i:02x}" for i in range(4)}


def stable(image_id: str) -> str:
    """Deterministic pseudo-random order (the selection does not depend on the CSV order)."""
    return hashlib.sha256(image_id.encode()).hexdigest()


def read_labels(directory: Path) -> dict[str, dict[str, int]]:
    """ImageID → {"split", "fire": 0/1, "smoke": 0/1, "person": 1} from the official CSVs (streamed and filtered)."""
    labels: dict[str, dict[str, int]] = defaultdict(dict)
    splits: dict[str, str] = {}
    for split, url in SPLITS.items():
        for image_id, name, value in read_split(directory / f"labels-{split}.csv", url):
            splits[image_id] = split
            # Any verified-present member of the family wins over a verified-absent one.
            labels[image_id][name] = max(labels[image_id].get(name, 0), value)
    return {i: {**v, "split": splits[i]} for i, v in labels.items()}  # type: ignore[dict-item]


def read_split(cache: Path, url: str) -> list[tuple[str, str, int]]:
    if not cache.exists():
        print(f"streaming {url} …", flush=True)
        keep = FIRE | SMOKE | {PERSON}
        with urllib.request.urlopen(url, timeout=60) as response, cache.open("w") as out:  # noqa: S310
            for raw in io.TextIOWrapper(response, encoding="utf-8"):
                parts = raw.rstrip("\r\n").split(",")
                if len(parts) != 4 or parts[2] not in keep:
                    continue
                # People are everywhere: keep a fixed 1/64 sample of them (background images).
                if parts[2] == PERSON and (float(parts[3]) != 1 or stable(parts[0])[:2] not in SAMPLE):
                    continue
                out.write(raw)
    rows = []
    with cache.open() as handle:
        for image_id, _source, label, confidence in csv.reader(handle):
            if image_id == "ImageID":
                continue
            name = "fire" if label in FIRE else "smoke" if label in SMOKE else "person"
            rows.append((image_id, name, int(float(confidence))))
    return rows


def select(labels: dict[str, dict[str, int]], hard_negatives: int, background: int) -> dict[str, dict[str, int]]:
    positives = {i: v for i, v in labels.items() if v.get("fire") == 1 or v.get("smoke") == 1}
    negatives = {i: v for i, v in labels.items() if i not in positives and 0 in (v.get("fire"), v.get("smoke"))}
    people = {i: v for i, v in labels.items() if i not in positives and i not in negatives and v.get("person") == 1}
    chosen = dict(positives)
    for pool, limit in ((negatives, hard_negatives), (people, background)):
        for image_id in sorted(pool, key=stable)[:limit]:
            chosen[image_id] = pool[image_id]
    print(
        f"positives {len(positives)}, hard negatives {min(len(negatives), hard_negatives)}, "
        f"background {min(len(people), background)}"
    )
    return chosen


def download(image_id: str, split: str, target: Path) -> bool:
    if target.exists():
        return True
    try:
        with urllib.request.urlopen(IMAGE_URL.format(split, image_id), timeout=60) as response:  # noqa: S310
            image = Image.open(io.BytesIO(response.read())).convert("RGB")
    except Exception as exc:  # removed or unreadable image: skipped
        print(f"  skip {image_id}: {type(exc).__name__}", file=sys.stderr)
        return False
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    image.save(target, quality=92)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--hard-negatives", type=int, default=1200)
    parser.add_argument("--background", type=int, default=1200)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    images = args.out / "images"
    images.mkdir(parents=True, exist_ok=True)
    chosen = select(read_labels(args.out), args.hard_negatives, args.background)
    ids = sorted(chosen, key=stable)
    with ThreadPoolExecutor(args.workers) as pool:
        ok = list(pool.map(lambda i: download(i, str(chosen[i]["split"]), images / f"{i}.jpg"), ids))
    with (args.out / "images.jsonl").open("w") as out:
        for image_id, fine in zip(ids, ok, strict=True):
            if fine:
                out.write(json.dumps({"id": image_id, "verified": chosen[image_id]}) + "\n")
    print(f"{sum(ok)} images in {images}")


if __name__ == "__main__":
    main()
