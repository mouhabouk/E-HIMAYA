# Vision service: evaluation (v3.0.0, October 2026)

These are honest numbers for the detectors shipped in `models/fetch_models.py`, measured with `eval/evaluate.py` on
a held-out sample. The sample was never used for training, for picking the best epoch or for calibration. Read the
limits at the end before quoting any figure. Model 3.0.0 (L5d, D-Fire added, trained on a GPU) is shipped; 2.0.0
was measured again with the same commands for the comparison. The 2.0.0 against 1.0.0 section is kept as history.

## What was measured

* **Evaluation set.** `eval/samples.json` holds 383 images from the Open Images V7 **test** split. Each image is
  pinned by SHA-256 and is CC BY 2.0, with its author and page listed. The ground truth is the **human-verified
  image-level labels** (1 = present, 0 = absent). The images fall into these groups:

  | Group | Images | Content |
  |---|---|---|
  | `fire` | 120 | verified Fire, Flame, Wildfire, Bonfire or Campfire |
  | `smoke` | 43 | verified Smoke, which is every smoke-positive test image left |
  | `hard_negative` | 120 | fire or smoke was proposed by Google's classifier and **rejected by a human**: sunsets, lamps, candles, fog, steam… |
  | `person` | 60 | ordinary scenes with people |
  | `no_person` | 40 | ordinary scenes with no people |

* **Metric.** The metric is **frame-level** precision and recall per label. A frame counts as "fire" when at least
  one fire box reaches the threshold, which is the decision the live pipeline takes on each frame. Open Images has
  no fire or smoke *boxes*, so box-level mAP **cannot** be measured on this sample, and none is claimed.
* **Thresholds.** 0.45 is `VISION_MIN_CONFIDENCE`, the API's floor. 0.6 is `VISION_ALERT_CONFIDENCE`, the
  confirmation level that must be reached in 3 of 5 frames.
* **Extra test sets with human boxes** (`eval/evaluate_yolo.py`): the 90 validation images of FireNET and 69 frames
  of three FURG videos (`case2_car`, `hand_held_winnebago`, `house1`), all held out of training. They box fire only,
  so they give fire recall and box AP50, not precision or smoke figures.
* **Machine.** 4 vCPU Intel Xeon @ 2.80 GHz (cloud VM, shared with other jobs), ONNX Runtime 1.30.0, CPU only.

## Results: 3.0.0 against 2.0.0 (L5d, 2026-10-29)

3.0.0 is YOLOX-Tiny trained from the COCO weights on the 2.0.0 data rebuilt on a GPU (the teacher this time also on
the fire-only Open Images images) plus **D-Fire** (CC0-1.0, human fire and smoke boxes): 12,524 images after
de-duplication, 7,943 with boxes. Data, de-duplication, training curve and the commands are in
[`eval/l5d/README.md`](eval/l5d/README.md); every result file is in `eval/l5d/`. The figures below were measured on
the training machine and again in the cloud workspace, with the same results.

**Calibration (shipped):** `score_power` = {fire: 0.48, smoke: 1.7}.

* Fire as before: the raw threshold reaching precision 0.80 on `eval/calibration.json` maps to 0.45 (raw 0.19,
  recall 0.95 there).
* Smoke: the precision-0.80 rule on the pooled validation images gives 0.42, but then 3.0.0 flags smoke on 12 % of
  ordinary scenes and 42 % of the fire-like hard negatives of `eval/calibration.json` (2.0.0: 5–7 % and 11 %). Those
  false smoke detections score high, so we kept the **false-alarm rate** of 2.0.0 instead: 1.7 is the lowest power
  at which 3.0.0 flags no more of the 109 smoke-free images of `eval/calibration.json` than 2.0.0 does (4.6 % against
  5.5 %). The fit uses `eval/calibration.json` only, never the evaluation sample.

| Label | Threshold | 2.0.0 precision | 2.0.0 recall | **3.0.0 precision** | **3.0.0 recall** |
|---|---|---|---|---|---|
| fire | 0.45 | 0.677 (107 TP, 51 FP) | 0.870 | 0.686 (118 TP, 54 FP) | **0.959** |
| fire | 0.60 | 0.752 | 0.764 | 0.724 | **0.894** |
| smoke | 0.45 | 0.634 (26 TP, 15 FP) | 0.605 | 0.625 (25 TP, 15 FP) | 0.581 |
| smoke | 0.60 | 0.750 | 0.488 | 0.767 | 0.535 |

| Group | Images | Fire ≥ 0.45 (2.0.0 → 3.0.0) | Fire ≥ 0.6 | Smoke ≥ 0.45 | Smoke ≥ 0.6 |
|---|---|---|---|---|---|
| fire | 120 | 0.87 → 0.96 | 0.77 → 0.89 | 0.17 → 0.21 | 0.08 → 0.13 |
| smoke | 43 | 0.16 → 0.16 | 0.12 → 0.14 | 0.60 → 0.58 | 0.49 → 0.53 |
| hard_negative (fire-like scenes) | 120 | 0.42 → 0.42 | 0.28 → 0.33 | 0.24 → 0.28 | 0.15 → 0.20 |
| person (ordinary scenes) | 60 | 0.03 → 0.00 | 0.00 → 0.00 | 0.03 → 0.05 | 0.02 → 0.00 |
| no_person (ordinary scenes) | 40 | 0.03 → 0.05 | 0.00 → 0.03 | 0.12 → 0.10 | 0.07 → 0.05 |

Held-out test sets with human boxes (`eval/evaluate_yolo.py`; frame recall at 0.45, measured with the precision-0.80
smoke power 0.42, which does not change fire):

| Set | Label | 2.0.0 AP50 | 3.0.0 AP50 | 2.0.0 frame recall | 3.0.0 frame recall |
|---|---|---|---|---|---|
| FireNET validation (90) | fire | 0.691 | 0.724 | 0.900 | 0.933 |
| FURG, 3 held-out videos (69) | fire | 0.549 | 0.157 | 0.928 | 0.957 |
| D-Fire test (1,115 with fire) | fire | 0.101 | 0.652 | 0.441 | 0.961 |
| D-Fire test (2,081 with smoke) | smoke | 0.262 | 0.664 | 0.457 | 0.863 |

Missed fire by condition at 0.45 (`eval/conditions.py`, eye-tagged, not yet reviewed): night 12 → 3 of 87, far
7 → 2 of 22, smoke or fog 7 → 3 of 28, outdoor 12 → 3 of 72. Smoke: 17 → 18 of 43 missed.

**Reading.**

* **Fire is clearly better** at the same precision: 5 missed frames of 123 instead of 16, and the gain holds at
  night, at a distance and through smoke or fog, and on every held-out set at frame level. This is the decision the
  service takes.
* **FURG AP50 fell** (0.549 → 0.157) while its frame recall rose: D-Fire draws several small boxes per flame, so
  3.0.0 predicts 125 boxes against 75 human boxes, of 1.9 % of the frame against 6.0 %. Box geometry changed, not
  detection; the service only uses the frame decision and the box for display.
* **Smoke is unchanged** on this sample at the chosen calibration (within one image), with its false alarms held at
  the 2.0.0 level. On D-Fire's fire-scene footage 3.0.0 is far better (frame recall 0.46 → 0.86 at precision 0.60 →
  0.81, at power 0.42). A looser smoke calibration would trade more smoke found for about twice the false smoke;
  we did not take it. Smoke stays a hint for the operator.
* **D-Fire's own split leaks**: 7,716 of its training images are near-duplicates of its test images (mostly frames
  of the same videos); they were excluded, so the D-Fire test figures above are not inflated.
* Latency is unchanged (same architecture and input size): 720p frame, both models, 2 threads, median 85.8 ms
  (2.0.0) and 88.0 ms (3.0.0) on the training machine; 118 ms for 3.0.0 on the shared cloud VM.

### Full tables (3.0.0, `python eval/evaluate.py --threads 2`)

| Label | Threshold | Precision | Recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|
| fire | 0.30 | 0.636 | 0.967 | 0.768 | 119 | 68 | 4 | 155 |
| fire | 0.45 | 0.686 | 0.959 | 0.800 | 118 | 54 | 5 | 169 |
| fire | 0.50 | 0.712 | 0.943 | 0.811 | 116 | 47 | 7 | 176 |
| fire | 0.60 | 0.724 | 0.894 | 0.800 | 110 | 42 | 13 | 181 |
| fire | 0.70 | 0.777 | 0.821 | 0.798 | 101 | 29 | 22 | 194 |
| smoke | 0.30 | 0.583 | 0.651 | 0.615 | 28 | 20 | 15 | 106 |
| smoke | 0.45 | 0.625 | 0.581 | 0.602 | 25 | 15 | 18 | 111 |
| smoke | 0.50 | 0.658 | 0.581 | 0.617 | 25 | 13 | 18 | 113 |
| smoke | 0.60 | 0.767 | 0.535 | 0.630 | 23 | 7 | 20 | 119 |
| smoke | 0.70 | 0.850 | 0.395 | 0.540 | 17 | 3 | 26 | 123 |

## History: 2.0.0 against 1.0.0

Both with their own calibration (2.0.0: fire 0.56, smoke 0.74; 1.0.0: fire 0.72, smoke uncalibrated).

| Label | Threshold | 1.0.0 precision | 1.0.0 recall | **2.0.0 precision** | **2.0.0 recall** |
|---|---|---|---|---|---|
| fire | 0.45 | 0.704 (107 TP, 45 FP) | 0.870 | 0.677 (107 TP, 51 FP) | 0.870 |
| fire | 0.60 | 0.776 | 0.732 | 0.752 | 0.764 |
| smoke | 0.45 | 0.750 (3 TP, 1 FP) | **0.070** | 0.634 (26 TP, 15 FP) | **0.605** |
| smoke | 0.60 | — (0 detections) | 0.000 | 0.750 (21 TP, 7 FP) | 0.488 |

| Held-out set with human fire boxes | 1.0.0 AP50 | 1.0.0 frame recall at 0.45 | **2.0.0 AP50** | **2.0.0 frame recall at 0.45** |
|---|---|---|---|---|
| FireNET validation (90 images, 138 boxes) | 0.331 | 0.656 | 0.691 | 0.900 |
| FURG, 3 held-out videos (69 frames, 75 boxes) | 0.406 | 0.783 | 0.549 | 0.928 |

### Share of frames flagged, by group (false-alarm rate on the negative groups)

| Group | Images | Fire ≥ 0.45 (1.0.0 → 2.0.0) | Fire ≥ 0.6 | Smoke ≥ 0.45 | Smoke ≥ 0.6 |
|---|---|---|---|---|---|
| fire | 120 | 0.88 → 0.87 | 0.74 → 0.77 | 0.01 → 0.17 | 0.00 → 0.08 |
| smoke | 43 | 0.14 → 0.16 | 0.02 → 0.12 | 0.07 → **0.60** | 0.00 → **0.49** |
| hard_negative (fire-like scenes) | 120 | 0.34 → 0.42 | 0.23 → 0.28 | 0.07 → 0.24 | 0.00 → 0.15 |
| person (ordinary scenes) | 60 | 0.00 → 0.03 | 0.00 → 0.00 | 0.00 → 0.03 | 0.00 → 0.02 |
| no_person (ordinary scenes) | 40 | 0.05 → 0.03 | 0.00 → 0.00 | 0.03 → 0.12 | 0.00 → 0.07 |

**Reading.**

* **Smoke** goes from unusable (7 % recall at 0.45) to usable as a hint (60 % recall at precision 0.63; 49 % at
  precision 0.75 at the alert level). The price is false smoke on fire-like scenes (fog, steam, haze, dust: 24 % at
  0.45) and on some ordinary scenes (3–12 %).
* **Fire** is unchanged on this sample within its sampling error (same recall at 0.45, precision −2.7 points;
  at 0.6 recall +3.2, precision −2.4). It is much better on the two held-out sets with human boxes (AP50 ×2 on
  FireNET, frame recall +12 to +24 points): the new data covers small flames, video frames and night scenes. The
  FireNET gain is partly in-distribution (same kind of web thumbnails as its training split).
* Fire false alarms on fire-like scenes rose from 34 % to 42 % of frames at 0.45 (10 of 120 images). The API's
  3-of-5 confirmation at 0.6 and the operator remain the safeguards (FR-C-11).

### Full tables (2.0.0, history)

| Label | Threshold | Precision | Recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|
| fire | 0.30 | 0.632 | 0.951 | 0.760 | 117 | 68 | 6 | 155 |
| fire | 0.45 | 0.677 | 0.870 | 0.762 | 107 | 51 | 16 | 172 |
| fire | 0.50 | 0.701 | 0.821 | 0.757 | 101 | 43 | 22 | 180 |
| fire | 0.60 | 0.752 | 0.764 | 0.758 | 94 | 31 | 29 | 192 |
| fire | 0.70 | 0.804 | 0.634 | 0.709 | 78 | 19 | 45 | 204 |
| smoke | 0.30 | 0.458 | 0.628 | 0.529 | 27 | 32 | 16 | 94 |
| smoke | 0.45 | 0.634 | 0.605 | 0.619 | 26 | 15 | 17 | 111 |
| smoke | 0.50 | 0.641 | 0.581 | 0.610 | 25 | 14 | 18 | 112 |
| smoke | 0.60 | 0.750 | 0.488 | 0.592 | 21 | 7 | 22 | 119 |
| smoke | 0.70 | 0.818 | 0.419 | 0.554 | 18 | 4 | 25 | 122 |

## People (`yolox-tiny-coco-person`, official COCO weights, not trained by us; unchanged)

| Threshold | Precision | Recall | F1 |
|---|---|---|---|
| 0.45 | 0.873 | 0.802 | 0.836 |
| 0.60 | 0.913 | 0.757 | 0.828 |

## CPU latency (measured for 2.0.0; 3.0.0 has the same architecture)

The pipeline is letterbox → both ONNX models → decode and NMS, with no GPU. 2.0.0 has the same architecture and
input size as 1.0.0, so the cost is the same (measured in the same session):

| Configuration | 1.0.0 | 2.0.0 |
|---|---|---|
| 720p frame, both models, 2 threads, median | 97 ms | 98 ms |
| 720p frame, both models, 2 threads, p95 | 110 ms | 124 ms (shared VM) |
| Uploaded photos (mixed sizes, decode excluded), 2 threads, mean | 104 ms | 103 ms |
| Fire and smoke model alone, 720p, 2 threads, median | — | 47 ms |

One 2-thread worker therefore analyses about 8–10 frames per second. That covers `VISION_MAX_STREAMS=8` streams at
1 frame per second, or 4 pending streams at 2 frames per second. Decoding one stream takes one more thread.

For comparison, the Grounding DINO teacher took **4–11 s per image** at 512 px on the same (shared) machine, which
is why it is only used offline to draw training boxes.

### End-to-end checks (local, real binaries; model 1.0.0, the pipeline is unchanged)

* **RTSP through MediaMTX.** MediaMTX 1.21.2 ran with read authentication (user `vision`), and a PyAV publisher sent
  an MPEG-4 stream of a fire photo at 10 fps. The service posted 16 callbacks with `fire` 0.83, the
  `X-Vision-Token` header and a JPEG frame, at 2 frames per second while pending.
* **Publisher stop.** After the publisher stopped, MediaMTX answered 404 and the service reconnected with backoff.
  It ended the watch as `gone` and freed the slot.

## How the fire and smoke model was built

**3.0.0 (L5d)** follows the same steps on a GPU (NVIDIA RTX 6000 Ada), from the COCO weights, with D-Fire added and
the teacher run on every Open Images positive. 40 epochs in 79 minutes, batch 64, lr 0.02; best epoch 36 (fire AP
0.975, smoke AP 0.949 on 999 held-out training images). ONNX SHA-256 `39de2276…84f7`. Every detail is in
[`eval/l5d/README.md`](eval/l5d/README.md). The table below describes **2.0.0**, kept for history.

| Step | Detail |
|---|---|
| Data search | GitHub search for fire and smoke datasets (README.md, "Fire and smoke datasets found on GitHub"). Only datasets whose own repository grants a permissive licence **and** that are hosted on GitHub were usable from the build machine: FireNET (MIT) and FURG (CC0-1.0). D-Fire (CC0-1.0) is on OneDrive/Kaggle, unreachable there. |
| Open Images | The V7 label files list 1,433 human-verified smoke images in train, against 532 in the V5 files used for 1.0.0. 1,354 new verified-positive images (743 with smoke) and 269 new verified-absent hard negatives were on the public mirror. On the shared CPU the teacher was run on every new **smoke** image first; 536 fire-only images were left out for time. |
| Boxes | Grounding DINO Swin-T OGC, prompt `fire . smoke .`, 512 px short side, gated by the human labels as for 1.0.0 (≥ 0.30 when the class is verified present, ≥ 0.50 when not verified, none when verified absent; an image whose verified class the teacher misses is dropped: 110 of 812). FireNET and FURG keep their human fire boxes; the teacher added smoke boxes (≥ 0.50) to 38 of their images. |
| FURG frames | About one frame per second of the 17 annotated videos, only frames with flame boxes, minus near-identical consecutive frames (dHash ≤ 6 bits); 10 frames of the non-fire robot video as negatives. Whole videos are held out as the test split. |
| De-duplication | `training/dedupe.py`: 64-bit DCT pHash of every image. **22** training images within 8 bits of an evaluation, calibration or test image and **26** training images within 4 bits of another training image were excluded. The close pairs inspected by eye were mostly dark scenes (candles, night fires) with similar hashes, not copies; they were excluded anyway. |
| Training set | 3,919 images: 1,724 with boxes (986 with fire, 851 with smoke; 1,245 fire and 1,056 smoke boxes, against 456 and 167 for 1.0.0) and 2,195 without. 8 % of them (325 images, grouped so that frames of one video stay together) were held out to pick the best epoch. |
| Student | YOLOX-Tiny (5.0 M parameters, 416×416), initialised from model 1.0.0 (itself from the COCO weights). |
| Training | 14 epochs on the shared 4-vCPU machine, 2 h 36 min (9–22 min per epoch). Each epoch: every positive, every smoke image a second time (`--smoke-repeat 2`), and 0.6 negatives per positive drawn at random: 3,305 images, batch 16. SGD with Nesterov momentum, lr 0.005, one warm-up epoch then cosine decay, weight decay 5e-4, EMA. Mosaic, mixup (p 0.15), scale, flip, HSV (small hue shift) and blur (p 0.1) for epochs 0–10; epochs 11–13 without mosaic or mixup, with the L1 loss. |
| Model selection | Image-level AP per class of the EMA weights on the 325 held-out images after every epoch. Best: epoch 10, fire AP 0.943 and smoke AP 0.801 (model 1.0.0 on the same images: 0.836 and 0.547). |
| Export | ONNX opset 17, raw head output without decoding. The maximum relative difference from PyTorch is 1.1e-6. SHA-256 `3b9f2b5f8513ad76a1817a18614bfc73c4d625f5fcf2f3952ed1839ae43339b6`, 20.2 MB. |
| Calibration | `score_power` = {fire: 0.56, smoke: 0.74}: the lowest raw threshold reaching precision 0.80 (with at least 20 true positives) is mapped to 0.45. Fire: fitted on `eval/calibration.json` as for 1.0.0 (raw 0.24, recall 0.83 there). Smoke: `eval/calibration.json` has only 3 smoke images, so the fit pools the 325 held-out training-validation images (74 smoke) with `eval/calibration.json`, whose ordinary scenes and fire-like hard negatives keep the threshold honest (raw 0.34, recall 0.69 there). A fit on the validation split alone gave 0.45 (raw 0.17), which flagged smoke on 20–25 % of ordinary scenes; it was not used. None of these images is in the evaluation sample. |

## Limits and known weaknesses

1. **Smoke: about 58 % recall, precision 0.63 at 0.45** on the Open Images sample (much better on fire-scene
   footage such as D-Fire). Fog, steam, haze, clouds, dust and snow spray are the main false smoke detections; the
   3.0.0 calibration keeps them at the 2.0.0 level on purpose. Use smoke as a hint, never alone for a decision.
2. **Fire-like scenes** fool the fire model on about 40 % of the frames at 0.45 (sunsets, candles, stage lights,
   orange-lit interiors). The API's 3-of-5 confirmation and the human operator are the safeguards. Detections are
   suggestions only (FR-C-11).
3. **Box geometry.** The Open Images boxes come from Grounding DINO, and D-Fire draws several small boxes per
   flame, so 3.0.0's boxes are smaller than FURG's human boxes (hence its low FURG AP50). The frame-level decision
   is what was evaluated and what the service uses.
4. **Footage gaps.** D-Fire adds surveillance-style and night footage; drone, infrared and Tunisian footage remain
   under-represented.
5. **The sample is small**, so expect ±4–8 points of sampling error on each figure: 123 fire-positive and 43
   smoke-positive images. The fire gain of 3.0.0 (11 more fires found of 123) is larger than that error; the smoke difference is not.
6. The machine was a shared cloud VM; latency on a dedicated server core is likely lower.

## Improving the model

The service does not change: only the ONNX file and its SHA-256 in `models/fetch_models.py` change.

* Done in 3.0.0: D-Fire added (de-duplicated against every evaluation and test image), the fire-only Open Images
  images labelled by the teacher.
* Smoke precision: fog, steam and haze frames as hard negatives, then a calibration that finds more smoke at the
  same false-alarm rate.
* Train YOLOX-S at 640 px on a GPU server for better small-fire recall, at about 3 times the CPU cost.
* Collect labelled frames from Tunisian Civil Protection footage, with their consent and under the platform's data
  rules; a few hundred frames of local fog and steam would help smoke precision most.

Reproduce these numbers:

```bash
VISION_MODELS_DIR=/models python eval/evaluate.py --threads 2 --json results.json
VISION_MODELS_DIR=/models python eval/evaluate_yolo.py --dir training/work/extra/firenet/test --classes fire,smoke
VISION_MODELS_DIR=/models python eval/evaluate_yolo.py --dir training/work/extra/furg/test --classes fire,smoke
VISION_MODELS_DIR=/models python eval/evaluate_yolo.py --dir /data/D-Fire/test --classes smoke,fire
```
