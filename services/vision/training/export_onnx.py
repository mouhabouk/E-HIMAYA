"""Step 4/4: export the trained detector to ONNX, check it against PyTorch, print its SHA-256.

The graph has no decoding (raw YOLOX head output ``1 x N x (5 + classes)``, like the official YOLOX ONNX files),
so that the service decodes every model with the same NumPy code (app/processing.py).

    PYTHONPATH=<YOLOX checkout> python training/export_onnx.py --checkpoint training/work/run/final.pth \
        --out fire-smoke-yolox-tiny.onnx

Then publish the file as a release asset and pin its URL and SHA-256 in models/fetch_models.py.
"""

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import CLASSES, SIZE, build_model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    state = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model = build_model(len(CLASSES))
    model.load_state_dict(state["model"])
    model.eval()
    model.head.decode_in_inference = False
    dummy = torch.zeros(1, 3, SIZE, SIZE)
    torch.onnx.export(
        model, dummy, str(args.out), input_names=["images"], output_names=["output"], opset_version=17, dynamo=False
    )

    # The exported graph must give the same raw output as PyTorch on a real-looking input.
    sample = torch.from_numpy(np.random.default_rng(0).uniform(0, 255, (1, 3, SIZE, SIZE)).astype(np.float32))
    with torch.no_grad():
        expected = model(sample).numpy()
    session = ort.InferenceSession(str(args.out), providers=["CPUExecutionProvider"])
    actual = session.run(None, {"images": sample.numpy()})[0]
    error = float((np.abs(expected - actual) / (np.abs(expected) + 1.0)).max())
    if error > 1e-3:
        sys.exit(f"ONNX and PyTorch disagree (max relative error {error})")
    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    print(f"{args.out}: output {actual.shape}, max relative error vs PyTorch {error:.2e}")
    print(f"sha256 {digest}  size {args.out.stat().st_size}")


if __name__ == "__main__":
    main()
