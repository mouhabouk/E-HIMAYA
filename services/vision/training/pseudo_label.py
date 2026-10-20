"""Step 2/4: draw fire and smoke boxes on the training images with an open-vocabulary teacher (Grounding DINO).

Teacher: IDEA-Research Grounding DINO Swin-T OGC (code and weights Apache-2.0), prompted with "fire . smoke .".
It is far too slow for live video on a CPU (seconds per image) but good enough to *draw boxes* on images whose
content a human already verified (Open Images image-level labels). The human labels gate the teacher:
  * class verified present  → teacher boxes kept from score >= --keep-verified,
  * class verified absent   → no box of that class, whatever the teacher says,
  * class not verified      → teacher boxes kept only from score >= --keep-unverified,
  * verified present but the teacher finds nothing → the image is left out (it must not become a negative).

    PYTHONPATH=<GroundingDINO checkout> python training/pseudo_label.py --data training/work/data \
        --checkpoint groundingdino_swint_ogc.pth --vocab bert-base-uncased-vocab.txt
"""

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import torch
import torchvision.transforms.functional as F
from PIL import Image
from torchvision.ops import batched_nms

CLASSES = ("fire", "smoke")
CAPTION = "fire . smoke ."
# Token positions of the class words in "[CLS] fire . smoke . [SEP]".
TOKENS = {"fire": 1, "smoke": 3}
BERT_BASE_UNCASED = {
    "architectures": ["BertForMaskedLM"],
    "attention_probs_dropout_prob": 0.1,
    "hidden_act": "gelu",
    "hidden_dropout_prob": 0.1,
    "hidden_size": 768,
    "initializer_range": 0.02,
    "intermediate_size": 3072,
    "layer_norm_eps": 1e-12,
    "max_position_embeddings": 512,
    "model_type": "bert",
    "num_attention_heads": 12,
    "num_hidden_layers": 12,
    "pad_token_id": 0,
    "type_vocab_size": 2,
    "vocab_size": 30522,
}


def load_teacher(checkpoint: Path, vocab: Path, threads: int) -> torch.nn.Module:
    """Grounding DINO without the Hugging Face hub: BERT config written locally, BERT weights from the checkpoint."""
    import transformers
    from groundingdino.models import build_model
    from groundingdino.util import get_tokenlizer
    from groundingdino.util.misc import clean_state_dict
    from groundingdino.util.slconfig import SLConfig

    torch.set_num_threads(threads)
    bert_dir = Path(tempfile.mkdtemp(prefix="bert-base-uncased-"))
    (bert_dir / "config.json").write_text(json.dumps(BERT_BASE_UNCASED))
    (bert_dir / "vocab.txt").write_bytes(vocab.read_bytes())
    (bert_dir / "tokenizer_config.json").write_text(json.dumps({"do_lower_case": True, "model_max_length": 512}))
    # The text encoder weights are part of the Grounding DINO checkpoint: build an empty BERT, then load.
    get_tokenlizer.get_pretrained_language_model = lambda _name: transformers.BertModel(
        transformers.BertConfig(**BERT_BASE_UNCASED)
    )
    import groundingdino

    config = Path(groundingdino.__file__).parent / "config" / "GroundingDINO_SwinT_OGC.py"
    args = SLConfig.fromfile(str(config))
    args.device = "cpu"
    args.text_encoder_type = str(bert_dir)
    model = build_model(args)
    state = torch.load(checkpoint, map_location="cpu", weights_only=False)["model"]
    missing, unexpected = model.load_state_dict(clean_state_dict(state), strict=False)
    # label_enc (denoising training only) and position_ids buffers are expected leftovers of the checkpoint.
    unexpected = [k for k in unexpected if k != "label_enc.weight" and not k.endswith("position_ids")]
    if [k for k in missing if not k.endswith("position_ids")] or unexpected:
        sys.exit(f"checkpoint mismatch: missing {missing[:5]}, unexpected {unexpected[:5]}")
    return model.eval()


@torch.no_grad()
def label_image(model: torch.nn.Module, image: Image.Image, short_side: int) -> list[tuple[str, float, list[float]]]:
    width, height = image.size
    scale = short_side / min(width, height)
    resized = image.resize((round(width * scale), round(height * scale)), Image.Resampling.BILINEAR)
    tensor = F.normalize(F.to_tensor(resized), [0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    outputs = model(tensor[None], captions=[CAPTION])
    logits = outputs["pred_logits"].sigmoid()[0]  # queries x 256 tokens
    boxes = outputs["pred_boxes"][0]  # cx, cy, w, h normalised
    results = []
    for name in CLASSES:
        scores = logits[:, TOKENS[name]]
        for score, (cx, cy, w, h) in zip(scores.tolist(), boxes.tolist(), strict=True):
            if score >= 0.2:
                results.append((name, score, [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]))
    return results


def gate(
    candidates: list[tuple[str, float, list[float]]], verified: dict[str, int], keep_verified: float, keep_other: float
) -> list[tuple[str, float, list[float]]] | None:
    kept = []
    for name, score, box in candidates:
        status = verified.get(name)
        if status == 0:
            continue
        if score >= (keep_verified if status == 1 else keep_other):
            kept.append((name, score, [min(max(v, 0.0), 1.0) for v in box]))
    if kept:
        tensor = torch.tensor([b for _, _, b in kept])
        scores = torch.tensor([s for _, s, _ in kept])
        classes = torch.tensor([CLASSES.index(n) for n, _, _ in kept])
        kept = [kept[i] for i in batched_nms(tensor, scores, classes, 0.6).tolist()]
    for name in CLASSES:
        if verified.get(name) == 1 and not any(n == name for n, _, _ in kept):
            return None  # a human saw it, the teacher did not: unusable either way
    return kept


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--vocab", type=Path, required=True)
    parser.add_argument("--short-side", type=int, default=640)
    parser.add_argument("--keep-verified", type=float, default=0.30)
    parser.add_argument("--keep-unverified", type=float, default=0.50)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--all", action="store_true", help="also run the teacher on negatives (default: they get no box; slow on CPU)"
    )
    args = parser.parse_args()

    model = load_teacher(args.checkpoint, args.vocab, args.threads)
    raw_path = args.data / "teacher-raw.jsonl"  # resumable: the slow part is cached
    done = {json.loads(line)["id"] for line in raw_path.open()} if raw_path.exists() else set()
    entries = [json.loads(line) for line in (args.data / "images.jsonl").open()]
    if args.limit:
        entries = entries[: args.limit]
    positive = {e["id"] for e in entries if 1 in (e["verified"].get("fire"), e["verified"].get("smoke"))}
    started = time.perf_counter()
    with raw_path.open("a") as raw:
        todo = [e for e in entries if e["id"] not in done and (args.all or e["id"] in positive)]
        for n, entry in enumerate(todo):
            image = Image.open(args.data / "images" / f"{entry['id']}.jpg").convert("RGB")
            candidates = label_image(model, image, args.short_side)
            raw.write(json.dumps({"id": entry["id"], "size": image.size, "candidates": candidates}) + "\n")
            raw.flush()
            if n % 50 == 0:
                rate = (time.perf_counter() - started) / (n + 1)
                print(f"{n}/{len(todo)} ({rate:.2f} s/image)", flush=True)

    verified = {e["id"]: e["verified"] for e in entries}
    kept_images = dropped = boxes = 0
    labelled = set()
    with (args.data / "labels.jsonl").open("w") as out:
        for line in raw_path.open():
            item = json.loads(line)
            if item["id"] not in verified:
                continue
            kept = gate(item["candidates"], verified[item["id"]], args.keep_verified, args.keep_unverified)
            if kept is None:
                dropped += 1
                continue
            kept_images += 1
            boxes += len(kept)
            labelled.add(item["id"])
            out.write(json.dumps({"id": item["id"], "size": item["size"], "boxes": kept}) + "\n")
        # Negatives the teacher did not look at: verified-absent or ordinary scenes, no box.
        for entry in entries:
            if entry["id"] not in labelled and entry["id"] not in positive:
                with Image.open(args.data / "images" / f"{entry['id']}.jpg") as image:
                    size = image.size
                out.write(json.dumps({"id": entry["id"], "size": size, "boxes": []}) + "\n")
                kept_images += 1
    print(f"labels.jsonl: {kept_images} images, {boxes} boxes, {dropped} dropped (teacher missed a verified class)")


if __name__ == "__main__":
    main()
