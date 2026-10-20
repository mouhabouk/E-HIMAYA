"""Step 3/4: fine-tune YOLOX-Tiny (Megvii, Apache-2.0) from its COCO weights into a fire and smoke detector.

Pure PyTorch training loop around the YOLOX model and loss (no YOLOX trainer: it assumes CUDA). Runs on a CPU
(hours) or a GPU (minutes): --device cuda. Augmentations: mosaic (first 85 % of the epochs), random scale and
placement, horizontal flip, HSV jitter; EMA of the weights; L1 box loss for the last epochs, as in YOLOX.

Each epoch sees every positive image and as many negatives (verified absent, ordinary scenes) drawn at random.
Extra datasets in YOLO format (one ``.txt`` per image: ``class cx cy w h`` normalised) can be added with
--yolo DIR:MAP, e.g. D-Fire (CC0, classes 0 = smoke, 1 = fire): ``--yolo /data/D-Fire/train:smoke,fire``.

    PYTHONPATH=<YOLOX checkout> python training/train.py --data training/work/data --weights yolox_tiny.pth \
        --out training/work/run --epochs 30
"""

import argparse
import json
import math
import random
import time
from copy import deepcopy
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

CLASSES = ("fire", "smoke")
SIZE = 416
MAX_LABELS = 60


def build_model(num_classes: int) -> torch.nn.Module:
    from yolox.models import YOLOPAFPN, YOLOX, YOLOXHead

    depth, width = 0.33, 0.375  # YOLOX-Tiny
    in_channels = [256, 512, 1024]
    backbone = YOLOPAFPN(depth, width, in_channels=in_channels, act="silu")
    head = YOLOXHead(num_classes, width, in_channels=in_channels, act="silu")
    model = YOLOX(backbone, head)
    for module in model.modules():
        if isinstance(module, torch.nn.BatchNorm2d):
            module.eps, module.momentum = 1e-3, 0.03
    head.initialize_biases(1e-2)
    return model


def load_coco(model: torch.nn.Module, weights: Path) -> None:
    """COCO weights, except the class prediction layers (80 classes → 2)."""
    state = torch.load(weights, map_location="cpu", weights_only=False)["model"]
    own = model.state_dict()
    usable = {k: v for k, v in state.items() if k in own and own[k].shape == v.shape}
    model.load_state_dict(usable, strict=False)
    skipped = sorted(set(own) - set(usable))
    print(f"COCO weights: {len(usable)} tensors loaded, {len(skipped)} re-initialised ({skipped[:3]}…)")


class Samples:
    """(image path, boxes N x 5 [class, x1, y1, x2, y2] normalised)."""

    def __init__(self) -> None:
        self.items: list[tuple[Path, np.ndarray]] = []

    def add_pseudo_labels(self, data: Path) -> None:
        for line in (data / "labels.jsonl").open():
            item = json.loads(line)
            boxes = [[CLASSES.index(name), *box] for name, _score, box in item["boxes"]]
            array = np.array(boxes, dtype=np.float32).reshape(-1, 5)
            self.items.append((data / "images" / f"{item['id']}.jpg", array))

    def add_yolo(self, spec: str) -> None:
        directory, names = spec.rsplit(":", 1)
        mapping = [CLASSES.index(n) if n in CLASSES else -1 for n in names.split(",")]
        root = Path(directory)
        for image in sorted((root / "images").glob("*.jpg")):
            label = root / "labels" / f"{image.stem}.txt"
            rows = []
            if label.exists():
                for line in label.read_text().split("\n"):
                    if line.strip():
                        cls, cx, cy, w, h = (float(v) for v in line.split()[:5])
                        if mapping[int(cls)] >= 0:
                            rows.append([mapping[int(cls)], cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])
            self.items.append((image, np.array(rows, dtype=np.float32).reshape(-1, 5)))


def load(path: Path, boxes: np.ndarray, size: int) -> tuple[np.ndarray, np.ndarray]:
    """Image resized so that its longest side is ``size``; boxes in pixels."""
    image = Image.open(path).convert("RGB")
    ratio = size / max(image.size)
    image = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))))
    pixels = boxes.copy()
    pixels[:, [1, 3]] *= image.width
    pixels[:, [2, 4]] *= image.height
    return np.asarray(image), pixels


class Train(Dataset):
    def __init__(self, samples: list[tuple[Path, np.ndarray]], mosaic: bool) -> None:
        self.samples = samples
        self.mosaic = mosaic

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        if self.mosaic and random.random() < 0.5:
            image, boxes = self._mosaic(index)
        else:
            image, boxes = load(*self.samples[index], SIZE)
        image, boxes = place(image, boxes)
        if random.random() < 0.5:
            image = image[:, ::-1]
            boxes[:, [1, 3]] = SIZE - boxes[:, [3, 1]]
        image = hsv_jitter(image)
        boxes = boxes[((boxes[:, 3] - boxes[:, 1]) > 3) & ((boxes[:, 4] - boxes[:, 2]) > 3)][:MAX_LABELS]
        targets = np.zeros((MAX_LABELS, 5), dtype=np.float32)
        if len(boxes):
            targets[: len(boxes), 0] = boxes[:, 0]
            targets[: len(boxes), 1] = (boxes[:, 1] + boxes[:, 3]) / 2
            targets[: len(boxes), 2] = (boxes[:, 2] + boxes[:, 4]) / 2
            targets[: len(boxes), 3] = boxes[:, 3] - boxes[:, 1]
            targets[: len(boxes), 4] = boxes[:, 4] - boxes[:, 2]
        tensor = torch.from_numpy(np.ascontiguousarray(image[:, :, ::-1].transpose(2, 0, 1))).float()  # BGR 0..255
        return tensor, torch.from_numpy(targets)

    def _mosaic(self, index: int) -> tuple[np.ndarray, np.ndarray]:
        """Four images around a random centre of a 2S x 2S canvas."""
        canvas = np.full((2 * SIZE, 2 * SIZE, 3), 114, dtype=np.uint8)
        xc, yc = (int(random.uniform(0.5 * SIZE, 1.5 * SIZE)) for _ in range(2))
        indices = [index] + [random.randrange(len(self.samples)) for _ in range(3)]
        all_boxes = []
        for quadrant, i in enumerate(indices):
            image, boxes = load(*self.samples[i], SIZE)
            h, w = image.shape[:2]
            if quadrant == 0:
                x1, y1, x2, y2 = max(xc - w, 0), max(yc - h, 0), xc, yc
                crop = image[h - (y2 - y1) :, w - (x2 - x1) :]
            elif quadrant == 1:
                x1, y1, x2, y2 = xc, max(yc - h, 0), min(xc + w, 2 * SIZE), yc
                crop = image[h - (y2 - y1) :, : x2 - x1]
            elif quadrant == 2:
                x1, y1, x2, y2 = max(xc - w, 0), yc, xc, min(yc + h, 2 * SIZE)
                crop = image[: y2 - y1, w - (x2 - x1) :]
            else:
                x1, y1, x2, y2 = xc, yc, min(xc + w, 2 * SIZE), min(yc + h, 2 * SIZE)
                crop = image[: y2 - y1, : x2 - x1]
            canvas[y1:y2, x1:x2] = crop
            dx = x1 - (w - crop.shape[1] if quadrant in (0, 2) else 0)
            dy = y1 - (h - crop.shape[0] if quadrant in (0, 1) else 0)
            shifted = boxes.copy()
            shifted[:, [1, 3]] = np.clip(shifted[:, [1, 3]] + dx, x1, x2)
            shifted[:, [2, 4]] = np.clip(shifted[:, [2, 4]] + dy, y1, y2)
            all_boxes.append(shifted)
        return canvas, np.concatenate(all_boxes)


def place(image: np.ndarray, boxes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Random scale (0.5-1.5 of fit) and position in the S x S input; padding 114 like inference."""
    h, w = image.shape[:2]
    scale = SIZE / max(h, w) * random.uniform(0.5, 1.5)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    resized = np.asarray(Image.fromarray(image).resize((nw, nh), Image.Resampling.BILINEAR))
    ox = random.randint(min(0, SIZE - nw), max(0, SIZE - nw))
    oy = random.randint(min(0, SIZE - nh), max(0, SIZE - nh))
    canvas = np.full((SIZE, SIZE, 3), 114, dtype=np.uint8)
    sx1, sy1 = max(0, -ox), max(0, -oy)
    dx1, dy1 = max(0, ox), max(0, oy)
    cw, ch = min(nw - sx1, SIZE - dx1), min(nh - sy1, SIZE - dy1)
    canvas[dy1 : dy1 + ch, dx1 : dx1 + cw] = resized[sy1 : sy1 + ch, sx1 : sx1 + cw]
    out = boxes.copy()
    out[:, 1:] *= scale
    out[:, [1, 3]] = np.clip(out[:, [1, 3]] + ox, 0, SIZE)
    out[:, [2, 4]] = np.clip(out[:, [2, 4]] + oy, 0, SIZE)
    # Keep boxes that are still mostly visible.
    area = (boxes[:, 3] - boxes[:, 1]) * (boxes[:, 4] - boxes[:, 2]) * scale * scale
    visible = (out[:, 3] - out[:, 1]) * (out[:, 4] - out[:, 2])
    return canvas, out[visible > 0.3 * np.maximum(area, 1e-6)]


def hsv_jitter(image: np.ndarray) -> np.ndarray:
    hsv = np.asarray(Image.fromarray(np.ascontiguousarray(image)).convert("HSV")).astype(np.float32)
    gains = np.random.uniform(-1, 1, 3) * np.array([0.015, 0.7, 0.4]) + 1  # small hue shift: fire is orange
    hsv[..., 0] = (hsv[..., 0] * gains[0]) % 256
    hsv[..., 1:] = np.clip(hsv[..., 1:] * gains[1:], 0, 255)
    return np.asarray(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB"))


class EMA:
    def __init__(self, model: torch.nn.Module, decay: float = 0.9998) -> None:
        self.model = deepcopy(model).eval()
        self.decay, self.updates = decay, 0
        for p in self.model.parameters():
            p.requires_grad_(False)

    @torch.no_grad()
    def update(self, model: torch.nn.Module) -> None:
        self.updates += 1
        d = self.decay * (1 - math.exp(-self.updates / 2000))
        source = model.state_dict()
        for key, value in self.model.state_dict().items():
            if value.dtype.is_floating_point:
                value.mul_(d).add_(source[key].detach(), alpha=1 - d)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, required=True, help="output of build_dataset.py + pseudo_label.py")
    parser.add_argument("--yolo", action="append", default=[], help="extra YOLO-format dataset DIR:class,names")
    parser.add_argument("--weights", type=Path, required=True, help="yolox_tiny.pth (COCO)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--lr", type=float, default=0.005)
    parser.add_argument("--negatives-per-positive", type=float, default=1.0)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    args.out.mkdir(parents=True, exist_ok=True)

    samples = Samples()
    samples.add_pseudo_labels(args.data)
    for spec in args.yolo:
        samples.add_yolo(spec)
    positives = [s for s in samples.items if len(s[1])]
    negatives = [s for s in samples.items if not len(s[1])]
    print(f"{len(positives)} images with boxes, {len(negatives)} without")

    model = build_model(len(CLASSES))
    load_coco(model, args.weights)
    model.to(args.device).train()
    ema = EMA(model)

    decay, no_decay = [], []
    for name, param in model.named_parameters():
        (no_decay if param.ndim <= 1 or name.endswith(".bias") else decay).append(param)
    optimiser = torch.optim.SGD(no_decay, lr=args.lr, momentum=0.9, nesterov=True)
    optimiser.add_param_group({"params": decay, "weight_decay": 5e-4})

    start_epoch = 0
    checkpoint = args.out / "last.pth"
    if checkpoint.exists():  # resume
        state = torch.load(checkpoint, map_location="cpu", weights_only=False)
        model.load_state_dict(state["model"])
        ema.model.load_state_dict(state["ema"])
        ema.updates = state["ema_updates"]
        optimiser.load_state_dict(state["optimiser"])
        start_epoch = state["epoch"] + 1
        print(f"resumed after epoch {state['epoch']}")

    per_epoch = len(positives) + min(len(negatives), int(len(positives) * args.negatives_per_positive))
    steps_per_epoch = per_epoch // args.batch
    total_steps = steps_per_epoch * args.epochs
    warmup = steps_per_epoch  # one epoch
    no_aug_from = int(args.epochs * 0.85)

    for epoch in range(start_epoch, args.epochs):
        rng = random.Random(args.seed + epoch)
        chosen = positives + rng.sample(negatives, per_epoch - len(positives))
        mosaic = epoch < no_aug_from
        model.head.use_l1 = not mosaic
        loader = DataLoader(
            Train(chosen, mosaic),
            batch_size=args.batch,
            shuffle=True,
            num_workers=args.workers,
            drop_last=True,
            persistent_workers=False,
            worker_init_fn=lambda w, e=epoch: (
                random.seed(args.seed * 1000 + e * 10 + w),
                np.random.seed(args.seed * 1000 + e * 10 + w),
            ),
        )
        started, totals = time.perf_counter(), {}
        for step, (images, targets) in enumerate(loader):
            global_step = epoch * steps_per_epoch + step
            if global_step < warmup:
                lr = args.lr * (global_step / warmup) ** 2
            else:
                lr = 0.05 * args.lr + 0.95 * args.lr * 0.5 * (1 + math.cos(math.pi * global_step / total_steps))
            for group in optimiser.param_groups:
                group["lr"] = lr
            outputs = model(images.to(args.device), targets.to(args.device))
            optimiser.zero_grad()
            outputs["total_loss"].backward()
            optimiser.step()
            ema.update(model)
            for key in ("total_loss", "iou_loss", "conf_loss", "cls_loss"):
                totals[key] = totals.get(key, 0.0) + float(outputs[key])
            if step % 20 == 0:
                print(
                    f"epoch {epoch} step {step}/{steps_per_epoch} lr {lr:.5f} loss {float(outputs['total_loss']):.3f}"
                    f" ({(time.perf_counter() - started) / (step + 1):.1f} s/step)",
                    flush=True,
                )
        means = {k: round(v / max(1, step + 1), 4) for k, v in totals.items()}
        print(f"epoch {epoch} done in {time.perf_counter() - started:.0f} s: {means}", flush=True)
        torch.save(
            {
                "model": model.state_dict(),
                "ema": ema.model.state_dict(),
                "ema_updates": ema.updates,
                "optimiser": optimiser.state_dict(),
                "epoch": epoch,
            },
            checkpoint,
        )
        with (args.out / "history.jsonl").open("a") as history:
            history.write(json.dumps({"epoch": epoch, **means}) + "\n")
    torch.save({"model": ema.model.state_dict(), "classes": CLASSES, "size": SIZE}, args.out / "final.pth")
    print(f"saved {args.out / 'final.pth'}")


if __name__ == "__main__":
    main()
