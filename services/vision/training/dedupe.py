"""Keep the evaluation honest: list the training images that are near-duplicates of an evaluation image.

A 64-bit DCT perceptual hash (pHash) is computed for every image. A training image is excluded when its hash is
within --eval-distance bits of any protected image: eval/samples.json and eval/calibration.json (the cached
files in eval/cache) and the held-out test splits of the extra datasets (--protect, repeatable); or within
--self-distance bits of a training image already kept (the same photo twice, or two almost identical frames of a
video). Directories are processed in the order given, so the first copy wins.

    python training/dedupe.py --protect eval/cache --protect training/work/extra/firenet/test/images \\
        --protect training/work/extra/furg/test/images --out training/work/exclude.json \\
        training/work/data/images training/work/data-v7/images training/work/extra/*/train/images

The output is a JSON object {file name: reason}; pass it to train.py --exclude.
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

N = 32
# Orthonormal DCT-II matrix: the 2-D DCT of X is D @ X @ D.T.
_k = np.arange(N)
DCT = np.sqrt(2 / N) * np.cos(np.pi * (2 * _k[None, :] + 1) * _k[:, None] / (2 * N))
DCT[0] /= np.sqrt(2)


def phash(path: Path) -> int:
    with Image.open(path) as image:
        gray = np.asarray(image.convert("L").resize((N, N), Image.Resampling.BOX), dtype=np.float64)
    low = (DCT @ gray @ DCT.T)[:8, :8].flatten()
    bits = low > np.median(low[1:])
    return int("".join("1" if b else "0" for b in bits), 2)


def hashes(paths: list[Path]) -> np.ndarray:
    with ThreadPoolExecutor(4) as pool:
        return np.array(list(pool.map(phash, paths)), dtype=np.uint64)


def distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Hamming distances between every hash of ``a`` and every hash of ``b``."""
    xor = (a[:, None] ^ b[None, :]).astype(">u8")
    return np.unpackbits(xor.view(np.uint8).reshape(len(a), len(b), 8), axis=2).sum(axis=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--protect", type=Path, action="append", required=True, help="eval/cache and held-out test image folders"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--eval-distance", type=int, default=8)
    parser.add_argument("--self-distance", type=int, default=4)
    parser.add_argument("directories", type=Path, nargs="+")
    args = parser.parse_args()

    evaluation = hashes(sorted(path for folder in args.protect for path in folder.glob("*.jpg")))
    print(f"{len(evaluation)} protected (evaluation and test) images hashed")
    excluded: dict[str, str] = {}
    kept = np.zeros(0, dtype=np.uint64)
    for directory in args.directories:
        paths = sorted(directory.glob("*.jpg"))
        own = hashes(paths)
        to_eval = distances(own, evaluation).min(axis=1) if len(paths) else np.zeros(0)
        before = len(excluded)
        for i, path in enumerate(paths):
            if to_eval[i] <= args.eval_distance:
                excluded[path.name] = f"near-duplicate of an evaluation or test image ({int(to_eval[i])} bits)"
            elif len(kept) and distances(own[i : i + 1], kept).min() <= args.self_distance:
                excluded[path.name] = "near-duplicate of another training image"
            else:
                kept = np.append(kept, own[i])
        print(f"{directory}: {len(paths)} images, {len(excluded) - before} excluded")
    args.out.write_text(json.dumps(excluded, indent=1, sort_keys=True) + "\n")
    reasons = [r.split(" (")[0] for r in excluded.values()]
    print({r: reasons.count(r) for r in set(reasons)})


if __name__ == "__main__":
    main()
