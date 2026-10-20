"""Build ``eval/samples.json``: the held-out evaluation sample (Open Images V7 *test* split, never used in training).

Each entry pins the image by SHA-256 and carries its human-verified image-level labels (1 = present, 0 = absent,
missing = not verified), its licence (CC BY 2.0) and its author, for attribution.
With ``--exclude eval/samples.json`` it builds the disjoint calibration set
(``eval/calibration.json``) used to set the score calibration of the fire/smoke model.
Run once; the result is committed
and ``evaluate.py`` downloads the images at run time and checks the hashes.

    python eval/build_samples.py --out eval/samples.json
"""

import argparse
import csv
import hashlib
import io
import json
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LABELS_URL = "https://storage.googleapis.com/openimages/v5/test-annotations-human-imagelabels.csv"
IMAGES_URL = "https://storage.googleapis.com/openimages/2018_04/test/test-images-with-rotation.csv"
IMAGE_URL = "https://open-images-dataset.s3.amazonaws.com/test/{}.jpg"
FIRE = {"/m/02_41", "/m/01f415", "/m/0fjy1", "/m/012ckm", "/m/019mk7"}  # Fire, Flame, Wildfire, Bonfire, Campfire
SMOKE = {"/m/06q40"}
PERSON = {"/m/01g317"}
QUOTAS = {"fire": 120, "smoke": 60, "hard_negative": 120, "person": 60, "no_person": 40}


def stable(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def stream_csv(url: str) -> csv.reader:
    response = urllib.request.urlopen(url, timeout=60)  # noqa: S310 (fixed https URL)
    return csv.reader(io.TextIOWrapper(response, encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--exclude", type=Path, help="samples file whose images must not be reused (calibration set ≠ evaluation set)"
    )
    args = parser.parse_args()
    excluded = {s["id"] for s in json.loads(args.exclude.read_text())["samples"]} if args.exclude else set()

    labels: dict[str, dict[str, int]] = defaultdict(dict)
    for image_id, _source, label, confidence in stream_csv(LABELS_URL):
        name = "fire" if label in FIRE else "smoke" if label in SMOKE else "person" if label in PERSON else None
        if name:
            labels[image_id][name] = max(labels[image_id].get(name, 0), int(float(confidence)))

    def pick(condition: object, quota: int, taken: set[str]) -> list[str]:
        pool = sorted((i for i, v in labels.items() if condition(v) and i not in taken), key=stable)  # type: ignore[operator]
        return pool[:quota]

    chosen: dict[str, str] = {}
    taken = set(excluded)
    groups = {
        "fire": lambda v: v.get("fire") == 1,
        "smoke": lambda v: v.get("smoke") == 1,
        "hard_negative": lambda v: 0 in (v.get("fire"), v.get("smoke")) and 1 not in (v.get("fire"), v.get("smoke")),
        "person": lambda v: v.get("person") == 1 and "fire" not in v and "smoke" not in v,
        "no_person": lambda v: v.get("person") == 0 and "fire" not in v and "smoke" not in v,
    }
    for group, condition in groups.items():
        for image_id in pick(condition, QUOTAS[group] * 2, taken | set(chosen)):  # extra: some images are gone
            chosen[image_id] = group

    meta = {}
    for row in stream_csv(IMAGES_URL):
        if row[0] in chosen:
            meta[row[0]] = {"license": row[4], "author": row[6], "page": row[3]}

    def fetch(image_id: str) -> tuple[str, str | None]:
        try:
            with urllib.request.urlopen(IMAGE_URL.format(image_id), timeout=60) as response:  # noqa: S310
                return image_id, hashlib.sha256(response.read()).hexdigest()
        except OSError:
            return image_id, None

    with ThreadPoolExecutor(16) as pool:
        hashes = dict(pool.map(fetch, chosen))

    samples, counts = [], dict.fromkeys(QUOTAS, 0)
    for image_id, group in sorted(chosen.items(), key=lambda kv: (kv[1], stable(kv[0]))):
        if hashes.get(image_id) is None or counts[group] >= QUOTAS[group] or image_id not in meta:
            continue
        if "creativecommons.org/licenses/by/2.0" not in meta[image_id]["license"]:
            continue
        counts[group] += 1
        samples.append(
            {
                "id": image_id,
                "group": group,
                "url": IMAGE_URL.format(image_id),
                "sha256": hashes[image_id],
                "labels": labels[image_id],
                "license": "CC-BY-2.0",
                "author": meta[image_id]["author"],
                "page": meta[image_id]["page"],
            }
        )
    document = {
        "source": "Open Images V7, test split (images CC BY 2.0 by their authors; labels CC BY 4.0 Google LLC)",
        "labels_url": LABELS_URL,
        "counts": counts,
        "samples": samples,
    }
    args.out.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(samples)} samples: {counts}")


if __name__ == "__main__":
    main()
