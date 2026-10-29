# L5d: fire and smoke model 3.0.0 (D-Fire added), measured against 2.0.0

Model file: `services/vision/models/weights/fire-smoke-yolox-tiny-v3.onnx` (not yet wired into `models/fetch_models.py`).
SHA-256 `39de22767c117330708f0a48103003d03d41df5bd3eb72cabb3674ace75384f7`, 20,168,122 bytes, ONNX opset 17, raw
YOLOX head output (1 × 3549 × 7) like 2.0.0. Maximum relative difference from PyTorch: 5.2e-6.
Calibration to use in the manifest: `score_power = {"fire": 0.48, "smoke": 0.42}` (see "Calibration").

## Machine

* NVIDIA RTX 6000 Ada Generation, 48 GB (driver 597.06, CUDA 13.2); Intel Core Ultra 9 285K, 128 GB RAM, Windows 11.
* Python 3.12.13, torch 2.14.1+cu130 / torchvision 0.29.1+cu130, the rest of `training/requirements.txt`, except
  transformers 4.57.1 instead of 5.20.1 (only the Grounding DINO teacher uses it: the pinned GroundingDINO commit calls
  `BertModel.get_extended_attention_mask`, which transformers 5 removed), plus matplotlib and pycocotools (imported by
  GroundingDINO). YOLOX at 6ddff48, GroundingDINO at 856dde2, both via PYTHONPATH.
* Evaluation: a separate venv with the service dependencies (`pyproject.toml`), CPU onnxruntime 1.30.0, 2 threads.
* The GPU was shared with another process holding about 28 GB of VRAM, so batch 64 was the practical maximum
  (batch 128 also ran out of Windows commit memory with 16 loader workers).

Small wrappers outside the repository ran the unchanged scripts on this machine: the teacher on CUDA with the
pure-PyTorch deformable attention (the custom op is not compiled), a picklable `worker_init_fn` for Windows
DataLoader workers (same seeds), and `build_dataset.py` reading the V7 label CSVs from a local copy (downloaded with
parallel range requests; the single-connection stream would have taken about 5 hours).

## Data

| source | images kept | with boxes | with fire | with smoke | fire boxes | smoke boxes | without boxes | validation |
|---|---|---|---|---|---|---|---|---|
| Open Images V7 train (Grounding DINO boxes) | 3,073 | 1,620 | 838 | 898 | 1,035 | 1,119 | 1,453 | 281 |
| FireNET train (human fire, teacher smoke) | 390 | 390 | 390 | 21 | 534 | 21 | 0 | 31 |
| FURG train frames (human fire, teacher smoke) | 175 | 166 | 165 | 17 | 180 | 17 | 9 | 13 |
| D-Fire train (human boxes) | 8,886 | 5,767 | 3,301 | 5,288 | 9,006 | 6,106 | 3,119 | 674 |
| **total** | **12,524** | **7,943** | **4,694** | **6,224** | **10,755** | **7,263** | **4,581** | **999** |

* Open Images: the V7 selection gives 4,701 verified positives, 1,200 hard negatives and 1,200 background images;
  3,446 were on the public mirror (the rest 404). The teacher ran on the GPU on **all** 1,989 positives on the mirror,
  fire-only images included (0.09 s/image, 512 px short side); 351 were dropped because it missed a verified class.
* FireNET 412 train / 90 test, FURG 184 train frames / 69 test frames (3 held-out videos). The teacher added 41 smoke
  boxes to 41 of their train images.
* D-Fire: 17,221 train / 4,306 test images. **204 train images are empty or truncated inside D-Fire.zip itself**
  (AoF01662–AoF01766 and AoF06536–AoF06634: 0-byte entries, AoF01662 truncated); they and their labels were moved
  aside, leaving 17,017. D-Fire test was never trained on.

## De-duplication (`training/dedupe.py`, pHash)

Protected: `eval/cache` (samples.json and calibration.json, 639 images), FireNET test, FURG test and D-Fire test
(5,104 images). 8,186 training images were excluded:

| folder | images | near-duplicate of an evaluation/test image (≤ 8 bits) | near-duplicate of a training image kept earlier (≤ 4 bits) |
|---|---|---|---|
| Open Images V7 | 3,446 | 24 (15 of eval/cache, 9 of D-Fire test) | 0 |
| FireNET train | 412 | 5 (3 FireNET test, 1 eval/cache, 1 D-Fire test) | 17 |
| FURG train | 184 | 0 | 9 |
| D-Fire train | 17,017 | 7,741 (7,716 D-Fire test, 22 eval/cache, 3 FireNET test) | 390 |

**D-Fire's own train/test split leaks heavily**: 7,716 train images are within 8 bits of a test image, 2,972 of them
with an identical hash. They are mostly frames of the same videos (AoF: 5,994 of 6,519 train frames). Excluding them
keeps the D-Fire test figures below honest; a model trained on the full official train split would score
inflated figures on D-Fire test.

## Training (`training/train.py`)

From the COCO `yolox_tiny.pth` (456 tensors loaded, the 6 class-prediction tensors re-initialised).
`--batch 64 --lr 0.02` (0.005 × 64/16), `--epochs 40 --val-fraction 0.08 --smoke-repeat 2 --mixup 0.15
--negatives-per-positive 0.6 --workers 8 --device cuda --seed 0`. Per epoch: 7,332 positives + 5,746 smoke repeats +
4,193 negatives (all available) = 17,271 images, 269 steps. **79 min in total, 119 s per epoch** (about 0.4 s/step,
limited by CPU data loading). Best epoch 36 (EMA weights, image-level AP on the 999 held-out images).

| epoch | AP fire | AP smoke | mAP | | epoch | AP fire | AP smoke | mAP |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.815 | 0.620 | 0.718 | | 20 | 0.967 | 0.933 | 0.950 |
| 1 | 0.899 | 0.813 | 0.856 | | 21 | 0.969 | 0.938 | 0.953 |
| 2 | 0.945 | 0.847 | 0.896 | | 22 | 0.972 | 0.939 | 0.955 |
| 3 | 0.939 | 0.865 | 0.902 | | 23 | 0.958 | 0.951 | 0.954 |
| 4 | 0.930 | 0.875 | 0.903 | | 24 | 0.962 | 0.943 | 0.952 |
| 5 | 0.949 | 0.886 | 0.917 | | 25 | 0.959 | 0.936 | 0.947 |
| 6 | 0.956 | 0.909 | 0.933 | | 26 | 0.968 | 0.939 | 0.953 |
| 7 | 0.953 | 0.902 | 0.927 | | 27 | 0.961 | 0.943 | 0.952 |
| 8 | 0.949 | 0.900 | 0.925 | | 28 | 0.957 | 0.946 | 0.952 |
| 9 | 0.958 | 0.899 | 0.928 | | 29 | 0.965 | 0.942 | 0.954 |
| 10 | 0.962 | 0.921 | 0.941 | | 30 | 0.965 | 0.941 | 0.953 |
| 11 | 0.965 | 0.931 | 0.948 | | 31 | 0.974 | 0.941 | 0.958 |
| 12 | 0.950 | 0.918 | 0.934 | | 32 | 0.963 | 0.942 | 0.953 |
| 13 | 0.952 | 0.899 | 0.926 | | 33 | 0.974 | 0.946 | 0.960 |
| 14 | 0.960 | 0.925 | 0.942 | | 34 | 0.971 | 0.946 | 0.959 |
| 15 | 0.956 | 0.924 | 0.940 | | 35 | 0.973 | 0.949 | 0.961 |
| 16 | 0.954 | 0.902 | 0.928 | | **36** | **0.975** | **0.949** | **0.962** |
| 17 | 0.952 | 0.928 | 0.940 | | 37 | 0.967 | 0.954 | 0.961 |
| 18 | 0.954 | 0.942 | 0.948 | | 38 | 0.971 | 0.950 | 0.961 |
| 19 | 0.962 | 0.932 | 0.947 | | 39 | 0.962 | 0.957 | 0.959 |

Epochs 34–39 ran without mosaic/mixup, with the L1 loss. Full history: `train-history.jsonl`.

## Calibration

As in EVALUATION.md, the lowest raw threshold reaching precision 0.80 (≥ 20 true positives) is mapped to 0.45.
* Fire, on `eval/calibration.json`: raw 0.19 (P 0.803, R 0.950) → power 0.481 (`v3-fit-calibration.json`).
* Smoke: `eval/calibration.json` has 3 smoke images (no fit). Pooled with the 999 held-out training-validation images
  (478 with smoke): raw 0.15 (P 0.805, R 0.952) → power 0.421 (`v3-fit-pooled.json`).
* Rounded to {fire 0.48, smoke 0.42}. On `eval/calibration.json` the calibrated model flags smoke on 12 % of the
  ordinary scenes (person and no_person groups; 2.0.0: 7 % and 5 %) and 42 % of the hard negatives (2.0.0: 11 %).
  Raising the smoke power to 0.60 barely changes this (10–12 %, 33 %): those false smoke detections have high raw
  scores, so it is a model property, not a calibration choice (`v*-calibration-calibrated.json`).

## Results: 2.0.0 vs 3.0.0, same commands, CPU onnxruntime, 2 threads

### Evaluation sample (eval/samples.json, 383 images, frame level)

| label | threshold | 2.0.0 precision | 3.0.0 precision | 2.0.0 recall | 3.0.0 recall |
|---|---|---|---|---|---|
| fire | 0.45 | 0.677 | 0.686 | 0.870 | 0.959 |
| fire | 0.6 | 0.752 | 0.724 | 0.764 | 0.894 |
| smoke | 0.45 | 0.634 | 0.547 | 0.605 | 0.814 |
| smoke | 0.6 | 0.750 | 0.564 | 0.488 | 0.721 |

Share of frames flagged at 0.45 per sample group:

| group | images | fire 2.0.0 | fire 3.0.0 | smoke 2.0.0 | smoke 3.0.0 |
|---|---|---|---|---|---|
| fire | 120 | 0.87 | 0.96 | 0.17 | 0.46 |
| hard_negative | 120 | 0.42 | 0.42 | 0.24 | 0.51 |
| no_person | 40 | 0.03 | 0.05 | 0.12 | 0.12 |
| person | 60 | 0.03 | 0.00 | 0.03 | 0.13 |
| smoke | 43 | 0.16 | 0.16 | 0.60 | 0.81 |

Latency (2 threads, CPU): 720p frame median 85.8 ms (2.0.0) vs 88.0 ms (3.0.0), fire-smoke + people models.

### Held-out test sets with human boxes (eval/evaluate_yolo.py)

| set | label | images | 2.0.0 AP50 | 3.0.0 AP50 | 2.0.0 P@0.45 | 3.0.0 P@0.45 | 2.0.0 frame R@0.45 | 3.0.0 frame R@0.45 | 2.0.0 box R@0.45 | 3.0.0 box R@0.45 |
|---|---|---|---|---|---|---|---|---|---|---|
| FireNET test | fire | 90 | 0.691 | 0.724 | — | — | 0.900 | 0.933 | 0.623 | 0.703 |
| FURG test | fire | 69 | 0.549 | 0.157 | — | — | 0.928 | 0.957 | 0.613 | 0.280 |
| D-Fire test | fire | 1115 | 0.101 | 0.652 | 0.826 | 0.927 | 0.441 | 0.961 | 0.088 | 0.683 |
| D-Fire test | smoke | 2081 | 0.262 | 0.664 | 0.600 | 0.808 | 0.457 | 0.863 | 0.295 | 0.687 |

### Missed positives by condition (eval/conditions.py, eval/samples.json), at 0.45

| label | condition | images | 2.0.0 missed | 3.0.0 missed | 2.0.0 frame recall | 3.0.0 frame recall |
|---|---|---|---|---|---|---|
| fire | all | 123 | 16 | 5 | 0.87 | 0.96 |
| fire | light: day | 35 | 3 | 2 | 0.91 | 0.94 |
| fire | light: night | 87 | 12 | 3 | 0.86 | 0.97 |
| fire | visibility: clear | 94 | 8 | 2 | 0.92 | 0.98 |
| fire | visibility: smoke_or_fog (small) | 28 | 7 | 3 | 0.75 | 0.89 |
| fire | distance: near | 100 | 8 | 3 | 0.92 | 0.97 |
| fire | distance: far (small) | 22 | 7 | 2 | 0.68 | 0.91 |
| fire | setting: indoor (small) | 29 | 1 | 1 | 0.97 | 0.97 |
| fire | setting: outdoor | 72 | 12 | 3 | 0.83 | 0.96 |
| smoke | all | 43 | 17 | 8 | 0.60 | 0.81 |
| smoke | light: day (small) | 26 | 5 | 1 | 0.81 | 0.96 |
| smoke | light: night (small) | 14 | 9 | 5 | 0.36 | 0.64 |
| smoke | distance: near (small) | 16 | 10 | 6 | 0.38 | 0.62 |
| smoke | distance: far (small) | 24 | 4 | 0 | 0.83 | 1.00 |
| smoke | setting: indoor (small) | 12 | 9 | 6 | 0.25 | 0.50 |
| smoke | setting: outdoor (small) | 28 | 5 | 0 | 0.82 | 1.00 |

## Reading the results

* **Fire improves everywhere at the frame level** (the decision the service takes): recall at 0.45 on the evaluation
  sample 0.870 → 0.959 at equal precision (0.677 → 0.686); night 0.86 → 0.97, far 0.68 → 0.91, smoke or fog
  0.75 → 0.89. Fire-like hard negatives are still flagged at the same rate (42 %).
* **Smoke recall rises, smoke precision falls**: recall 0.605 → 0.814 at 0.45, but precision 0.634 → 0.547; smoke is
  flagged on 51 % of the hard negatives (was 24 %) and 13 % of people scenes (was 3 %). D-Fire's smoke labels include
  haze-like plumes, and the smoke threshold is fitted on a pool dominated by D-Fire-like validation images. Smoke stays
  a hint for the operator. A smoke power fitted on ordinary-scene false alarms, or more local fog/steam negatives,
  is the next step if smoke precision matters more than recall.
* **Box geometry follows D-Fire**: D-Fire draws several tight boxes per flame (2.6 per fire image). On FURG test
  (one rectangle per flame) the new model predicts 125 boxes for 75 human boxes, mean area 1.9 % of the frame
  against 6.0 %, so AP50 drops 0.549 → 0.157 while frame recall rises 0.928 → 0.957. FireNET AP50 rises
  0.691 → 0.724.
* **D-Fire test** (in-domain for 3.0.0, de-duplicated): fire AP50 0.101 → 0.652, smoke 0.262 → 0.664; frame recall at
  0.45 fire 0.441 → 0.961, smoke 0.457 → 0.863, with higher precision for both.
* The evaluation sample is small (123 fire, 43 smoke positives): ±4–8 points of sampling error per figure.

## Files

* `v2-*.json`, `v3-*.json`: `eval/evaluate.py --threads 2 --json`, `eval/conditions.py --json`,
  `eval/evaluate_yolo.py` on FireNET test, FURG test, D-Fire test; `*-calibration-*`: runs on `eval/calibration.json`;
  `v3-fit-pooled.json`: `--fit` on the pooled smoke set.
* `train-history.jsonl`: per-epoch losses and validation AP.

## Commands (from `services/vision`)

```bash
python training/build_dataset.py --out training/work/data-v7            # V7 CSVs read from a local copy
python training/extra_datasets.py prepare --out training/work/extra
PYTHONPATH=GroundingDINO python training/pseudo_label.py --data training/work/data-v7 \
    --checkpoint groundingdino_swint_ogc.pth --vocab bert-base-uncased-vocab.txt --short-side 512   # on CUDA
PYTHONPATH=GroundingDINO python training/pseudo_label.py --data training/work/extra/teacher ... --short-side 512
python training/extra_datasets.py merge --out training/work/extra
python training/dedupe.py --protect eval/cache --protect training/work/extra/firenet/test/images \
    --protect training/work/extra/furg/test/images --protect D-Fire/test/images --out training/work/exclude.json \
    training/work/data-v7/images training/work/extra/firenet/train/images training/work/extra/furg/train/images \
    D-Fire/train/images
PYTHONPATH=YOLOX python training/train.py --data training/work/data-v7 \
    --yolo training/work/extra/firenet/train:fire,smoke --yolo training/work/extra/furg/train:fire,smoke \
    --yolo D-Fire/train:smoke,fire --exclude training/work/exclude.json --weights yolox_tiny.pth \
    --out training/work/run-v3 --epochs 40 --batch 64 --lr 0.02 --val-fraction 0.08 --smoke-repeat 2 --mixup 0.15 \
    --negatives-per-positive 0.6 --workers 8 --device cuda --seed 0
PYTHONPATH=YOLOX python training/export_onnx.py --checkpoint training/work/run-v3/best.pth \
    --out fire-smoke-yolox-tiny-v3.onnx
# both models (VISION_MODELS_DIR = fire-smoke + person folders; 3.0.0 manifest score_power {fire 0.48, smoke 0.42})
python eval/evaluate.py --threads 2 --json vX-evaluate.json
python eval/conditions.py --json vX-conditions.json
python eval/evaluate_yolo.py --dir training/work/extra/firenet/test --classes fire,smoke --json vX-firenet-test.json
python eval/evaluate_yolo.py --dir training/work/extra/furg/test --classes fire,smoke --json vX-furg-test.json
python eval/evaluate_yolo.py --dir D-Fire/test --classes smoke,fire --json vX-dfire-test.json
python eval/evaluate.py --samples eval/calibration.json --fit --json v3-fit-calibration.json   # 3.0.0, no score_power
```

D-Fire (CC0-1.0, de Venâncio et al., github.com/gaiasd/DFireDataset) images and labels stay on the training machine
and are not committed.
