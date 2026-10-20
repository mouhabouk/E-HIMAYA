"""Extra human-labelled fire data from GitHub, converted to YOLO format (model 2.0.0).

Only datasets whose own repository grants a permissive licence are used (README.md, "Licences"):

* FireNET, github.com/OlafenwaMoses/FireNET, release v1.0 ``fire-dataset.zip`` (MIT, Moses Olafenwa): 502 photos
  with Pascal VOC ``fire`` boxes, split 412 train / 90 validation by the authors. Their validation split is our
  held-out test split.
* FURG fire dataset, github.com/steffensbola/furg-fire-dataset (CC0-1.0, Steffens et al.): videos with a flame
  rectangle on every frame (OpenCV XML). About one frame per second is kept, only frames with flame boxes, minus
  near-identical consecutive frames (dHash). The non-fire robot video gives negatives; the robot videos without any
  annotation are skipped. Whole videos are held out as the test split (TEST_VIDEOS).

Both datasets box fire only. Smoke in their images would otherwise be learnt as background, so the train images
also go through the Grounding DINO teacher (pseudo_label.py, class "fire" marked as verified) and ``merge`` adds
the teacher's smoke boxes (score >= 0.5, the threshold for unverified classes) to the human fire boxes.

    python training/extra_datasets.py prepare --out training/work/extra
    PYTHONPATH=GroundingDINO python training/pseudo_label.py --data training/work/extra/teacher \\
        --checkpoint groundingdino_swint_ogc.pth --vocab bert-base-uncased-vocab.txt --short-side 512
    python training/extra_datasets.py merge --out training/work/extra
    # then: train.py ... --yolo training/work/extra/firenet/train:fire,smoke \\
    #                     --yolo training/work/extra/furg/train:fire,smoke

Needs opencv-python (video decoding) besides the training requirements.
"""

import argparse
import hashlib
import http.client
import io
import json
import shutil
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np

FIRENET_URL = "https://github.com/OlafenwaMoses/FireNET/releases/download/v1.0/fire-dataset.zip"
FIRENET_SHA256 = "714a5342cccb55a7fa08b7fdaedf06ec94a74567b64be657a1c3d183084b27d5"
FURG_COMMIT = "6aff09d7baa27425f31d1df685284c26cbffe7af"
FURG_RAW = f"https://raw.githubusercontent.com/steffensbola/furg-fire-dataset/{FURG_COMMIT}/"
# Annotated videos (the robot videos cleaner, coolerbot, icra and rover have empty annotations).
FURG_VIDEOS = {
    "Car1.mp4": "Car1.xml",
    "barbecue.mp4": "barbecue.xml",
    "car2.mp4": "Car2.xml",
    "car3.mp4": "Car3.xml",
    "case2_car.mp4": "case2_car.xml",
    "case2_house.mp4": "case2_house.xml",
    "hand_held_batteries_night.mp4": "hand_held_batteries_night.xml",
    "hand_held_camera_wildfire.mp4": "hand_held_camera_wildfire.xml",
    "hand_held_nasa_training.mp4": "hand_held_nasa_training.xml",
    "hand_held_nasa_training2.mp4": "hand_held_nasa_training2.xml",
    "hand_held_winnebago.mp4": "hand_held_winnebago.xml",
    "house1.mp4": "house1.xml",
    "house2.mp4": "house2.xml",
    "house3.mp4": "house3.xml",
    "house4.mp4": "house4.xml",
    "house5.mp4": "house5.xml",
    "house6.mp4": "house6.xml",
    "non_fire_patrolbot_onboard.mp4": None,  # negatives
}
TEST_VIDEOS = {"case2_car", "hand_held_winnebago", "house1"}
SMOKE_THRESHOLD = 0.5


def fetch(url: str, attempts: int = 4) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ehimaya-training"})  # noqa: S310
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
                return response.read()
        except (OSError, http.client.HTTPException):
            if attempt == attempts - 1:
                raise
    raise AssertionError("unreachable")


def yolo_line(cls: int, x0: float, y0: float, x1: float, y1: float, width: float, height: float) -> str:
    cx, cy = (x0 + x1) / 2 / width, (y0 + y1) / 2 / height
    return f"{cls} {cx:.6f} {cy:.6f} {(x1 - x0) / width:.6f} {(y1 - y0) / height:.6f}"


def prepare_firenet(out: Path) -> None:
    payload = fetch(FIRENET_URL)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != FIRENET_SHA256:
        raise SystemExit(f"FireNET archive changed: sha256 {digest}")
    archive = zipfile.ZipFile(io.BytesIO(payload))
    for source, split in (("train", "train"), ("validation", "test")):
        target = out / "firenet" / split
        (target / "images").mkdir(parents=True, exist_ok=True)
        (target / "labels").mkdir(parents=True, exist_ok=True)
        for name in sorted(archive.namelist()):
            if not name.startswith(f"fire-dataset/{source}/annotations/") or not name.endswith(".xml"):
                continue
            root = ET.fromstring(archive.read(name))  # noqa: S314 (pinned archive)
            filename = root.findtext("filename", "")
            stem = "firenet_" + source + "_" + Path(filename).stem.translate(str.maketrans("", "", " ()"))
            width, height = int(root.findtext("size/width", "0")), int(root.findtext("size/height", "0"))
            rows = []
            for obj in root.iter("object"):
                if obj.findtext("name", "").strip().lower() != "fire":
                    continue
                x0, y0, x1, y1 = (float(obj.findtext(f"bndbox/{k}", "0")) for k in ("xmin", "ymin", "xmax", "ymax"))
                rows.append(yolo_line(0, x0, y0, x1, y1, width, height))
            (target / "images" / f"{stem}.jpg").write_bytes(archive.read(f"fire-dataset/{source}/images/{filename}"))
            (target / "labels" / f"{stem}.txt").write_text("".join(f"{r}\n" for r in rows))
        print(f"FireNET {split}: {len(list((target / 'images').glob('*.jpg')))} images")


def dhash(gray: np.ndarray) -> np.ndarray:
    import cv2

    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    return np.packbits((small[:, 1:] > small[:, :-1]).flatten())


def prepare_furg(out: Path, scratch: Path) -> None:
    import cv2

    scratch.mkdir(parents=True, exist_ok=True)
    for video, annotation in FURG_VIDEOS.items():
        stem = Path(video).stem
        split = "test" if stem in TEST_VIDEOS else "train"
        target = out / "furg" / split
        (target / "images").mkdir(parents=True, exist_ok=True)
        (target / "labels").mkdir(parents=True, exist_ok=True)
        if any(target.glob(f"images/furg_{stem}_*.jpg")):
            continue
        boxes: dict[int, list[list[int]]] = {}
        if annotation is not None:
            root = ET.fromstring(fetch(FURG_RAW + annotation))  # noqa: S314 (pinned commit)
            frames = root.find("frames")
            for frame in frames if frames is not None else []:
                rects = [[int(v) for v in (a.text or "").split()] for a in frame.iterfind("annotations/_")]
                boxes[int(frame.findtext("frameNumber", "-1"))] = [r for r in rects if len(r) == 4 and min(r[2:]) > 2]
        path = scratch / video
        path.write_bytes(fetch(FURG_RAW + video))
        capture = cv2.VideoCapture(str(path))
        step = max(1, round(capture.get(cv2.CAP_PROP_FPS) or 25))
        kept: list[np.ndarray] = []
        index, saved = -1, 0
        while True:
            ok, frame = capture.read()
            index += 1
            if not ok:
                break
            if index % step or (annotation is not None and not boxes.get(index)):
                continue
            signature = dhash(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            if any(int(np.unpackbits(signature ^ k).sum()) <= 6 for k in kept[-30:]):
                continue  # static camera: almost the same frame as a recent one
            kept.append(signature)
            height, width = frame.shape[:2]
            scale = min(1.0, 640 / max(height, width))
            if scale < 1:
                frame = cv2.resize(frame, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
            name = f"furg_{stem}_{index:06d}"
            cv2.imwrite(str(target / "images" / f"{name}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            rows = []
            for x, y, w, h in boxes.get(index, []):
                x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, width), min(y + h, height)
                rows.append(yolo_line(0, x0, y0, x1, y1, width, height))
            (target / "labels" / f"{name}.txt").write_text("".join(f"{r}\n" for r in rows))
            saved += 1
        capture.release()
        path.unlink()
        print(f"FURG {video} ({split}): {saved} frames kept of {index}")


def prepare(out: Path) -> None:
    prepare_firenet(out)
    prepare_furg(out, out / "videos")
    # Train images for the teacher (smoke boxes): fire is human-verified present in every annotated image.
    teacher = out / "teacher"
    (teacher / "images").mkdir(parents=True, exist_ok=True)
    with (teacher / "images.jsonl").open("w") as listing:
        for dataset in ("firenet", "furg"):
            for image in sorted((out / dataset / "train" / "images").glob("*.jpg")):
                link = teacher / "images" / image.name
                if not link.exists():
                    shutil.copyfile(image, link)
                listing.write(json.dumps({"id": image.stem, "verified": {"fire": 1}}) + "\n")


def merge(out: Path) -> None:
    """Human fire boxes (class 0) + teacher smoke boxes (class 1) for the train images."""
    import torch
    from torchvision.ops import nms

    raw = {}
    for line in (out / "teacher" / "teacher-raw.jsonl").open():
        item = json.loads(line)
        raw[item["id"]] = item["candidates"]
    added = images = 0
    for dataset in ("firenet", "furg"):
        for label in sorted((out / dataset / "train" / "labels").glob("*.txt")):
            fire = [r for r in label.read_text().splitlines() if r.startswith("0 ")]
            smoke = [(s, b) for n, s, b in raw.get(label.stem, []) if n == "smoke" and s >= SMOKE_THRESHOLD]
            rows = list(fire)
            if smoke:
                boxes = torch.tensor([[min(max(v, 0.0), 1.0) for v in b] for _, b in smoke])
                for i in nms(boxes, torch.tensor([s for s, _ in smoke]), 0.6).tolist():
                    x0, y0, x1, y1 = boxes[i].tolist()
                    rows.append(yolo_line(1, x0, y0, x1, y1, 1, 1))
                    added += 1
                images += 1
            label.write_text("".join(f"{r}\n" for r in rows))
    print(f"teacher smoke boxes added: {added} on {images} images (classes now 0 = fire, 1 = smoke)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=("prepare", "merge"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.out) if args.step == "prepare" else merge(args.out)


if __name__ == "__main__":
    main()
