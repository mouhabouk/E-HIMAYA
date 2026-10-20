# Vision service: evaluation (v1.0.0, October 2026)

These are honest numbers for the detectors shipped in `models/fetch_models.py`, measured with `eval/evaluate.py` on
a held-out sample. The sample was never used for training or for calibration. Read the limits at the end before
quoting any figure.

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
  no fire or smoke *boxes*, so box-level mAP **cannot** be measured here, and none is claimed.
* **Thresholds.** 0.45 is `VISION_MIN_CONFIDENCE`, the API's floor. 0.6 is `VISION_ALERT_CONFIDENCE`, the
  confirmation level that must be reached in 3 of 5 frames.
* **Machine.** 4 vCPU Intel Xeon @ 2.80 GHz (cloud VM, shared with other jobs), ONNX Runtime 1.30.0, CPU only.

## Results (`python eval/evaluate.py --threads 2`)

### Fire (`ehimaya-fire-smoke-yolox-tiny` 1.0.0, with the calibration below)

| Threshold | Precision | Recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|
| 0.30 | 0.630 | 0.943 | 0.756 | 116 | 68 | 7 | 155 |
| 0.45 (API floor) | **0.704** | **0.870** | 0.778 | 107 | 45 | 16 | 178 |
| 0.50 | 0.746 | 0.837 | 0.789 | 103 | 35 | 20 | 188 |
| 0.60 (alert level) | **0.776** | **0.732** | 0.753 | 90 | 26 | 33 | 197 |
| 0.70 | 0.829 | 0.512 | 0.633 | 63 | 13 | 60 | 210 |

### Share of frames flagged, by group

| Group | Images | Fire ≥ 0.45 | Fire ≥ 0.6 | Smoke ≥ 0.45 | Person ≥ 0.45 |
|---|---|---|---|---|---|
| fire | 120 | **0.88** | 0.74 | 0.01 | 0.28 |
| hard_negative | 120 | **0.34** | 0.23 | 0.07 | 0.23 |
| person (ordinary scenes) | 60 | **0.00** | 0.00 | 0.00 | 0.88 |
| no_person (ordinary scenes) | 40 | 0.05 | 0.00 | 0.03 | 0.07 |
| smoke | 43 | 0.14 | 0.02 | 0.07 | 0.12 |

The false fire alarms come almost entirely from the *hard negatives*, which are fire-like scenes a human had to
reject. On ordinary scenes the fire false-positive rate is 0–5 % per frame. The API also requires 3 of 5 frames
≥ 0.6 before it confirms an alert, which lowers the false-alarm rate on a live stream further. That reduction is not
measured here, because the sample is made of still images.

### Smoke: not reliable in v1.0.0

| Threshold | Precision | Recall | TP | FP | FN |
|---|---|---|---|---|---|
| 0.25 | 0.625 | 0.349 | 15 | 9 | 28 |
| 0.45 | 0.750 | **0.070** | 3 | 1 | 40 |
| 0.60 | — | 0.000 | 0 | 0 | 43 |

Smoke recall is very low because the training set had only 167 smoke boxes. **Smoke detections must not be relied
on yet.** Fire detections are usable as a hint to operators. The fix is more smoke data (see "Improving the model").

### People (`yolox-tiny-coco-person`, official COCO weights, not trained by us)

| Threshold | Precision | Recall | F1 |
|---|---|---|---|
| 0.45 | 0.873 | 0.802 | 0.836 |
| 0.60 | 0.913 | 0.757 | 0.828 |

### CPU latency

The pipeline is letterbox → both ONNX models → decode and NMS, with no GPU.

| Configuration | Median | p95 |
|---|---|---|
| 720p frame, both models, 2 threads | **121–129 ms** | 136–161 ms |
| 720p frame, both models, 1 thread | 175 ms | 228 ms |
| Uploaded photos (mixed sizes, decode excluded), 2 threads | 119 ms (mean) | 151 ms |
| 720p frame, both models, 2 threads, inside the real-model test | 115 ms | — |

One 2-thread worker therefore analyses about 8 frames per second. That covers `VISION_MAX_STREAMS=8` streams at 1
frame per second, or 4 pending streams at 2 frames per second. The default of 2 workers leaves headroom; for more
streams, add workers and cores.

Decoding one stream takes one more thread (H.264 at 720p and 30 fps). Frames are converted to RGB only at 1 or 2 per
second.

For comparison, the Grounding DINO teacher took **3.8–8 s per image** at 512 px on the same machine. That is about
50 times slower, which is why it is only used offline to draw training boxes.

### End-to-end checks (local, real binaries)

* **RTSP through MediaMTX.** MediaMTX 1.21.2 ran with read authentication (user `vision`), and a PyAV publisher sent
  an MPEG-4 stream of a fire photo at 10 fps. The service watched it through `PUT /v1/streams`. It posted 16
  callbacks with `fire` 0.83, the `X-Vision-Token` header and a JPEG frame. The mean interval was **0.55 s**, which
  is 2 frames per second while pending.
* **Publisher stop.** After the publisher stopped, MediaMTX answered 404 and the service reconnected with backoff.
  It ended the watch as `gone` and freed the slot.
* **People only.** With only people in the picture, about 1 frame per second was analysed and a callback was sent
  every 10 s.

## How the fire and smoke model was built

| Step | Detail |
|---|---|
| Images | Open Images V7 train and validation splits. **471** images with fire or smoke boxes, plus **1,922** without (verified-absent hard negatives and ordinary scenes with people). The public mirror only holds part of the train split, so 2,393 images were usable out of 5,159 selected. |
| Boxes | Grounding DINO Swin-T OGC, prompt `fire . smoke .`, 512 px short side. Boxes were kept at score ≥ 0.30 when the class was human-verified present, and ≥ 0.50 when it was not verified. A class verified absent got no box. **92** verified-positive images were dropped because the teacher found nothing. The result was 623 boxes: 456 fire and 167 smoke. |
| Student | YOLOX-Tiny (5.0 M parameters, 416×416), initialised from the official COCO weights, with only the class layers re-initialised. |
| Training | 24 epochs on CPU (4 vCPU, about 155 s per epoch, 63 min in total). Batch 16, SGD with Nesterov momentum, lr 0.005, one warm-up epoch then cosine decay, weight decay 5e-4, EMA. Each epoch used all positives and an equal number of random negatives. Mosaic, scale, flip and HSV augmentation (small hue shift) ran for epochs 0–19; epochs 20–23 had no mosaic and added the L1 loss. The final loss was 4.75 (IoU 1.61, objectness 1.93, class 0.56). |
| Export | ONNX opset 17, raw head output without decoding. The maximum relative difference from PyTorch is 1.8e-6. SHA-256 `173073b780ef5f74d389ee9bdd7e90260a1ce22ee8a867aea79b20c71bcdaa00`, 20.2 MB. |
| Calibration | `score_power` = {fire: 0.72}. It was fitted on `eval/calibration.json`, 256 other test-split images **disjoint** from the evaluation set. The criterion was the lowest raw threshold reaching precision 0.80, which was 0.33 (recall 0.79), mapped to 0.45. The calibration set has too few smoke images, so smoke is left uncalibrated. |

The evaluation set holds more fire-like hard negatives (120) than the calibration set (36). This is why precision at
0.45 is 0.70 on evaluation against 0.80 on calibration. The calibration was **not** re-tuned on the evaluation set.

## Limits and known weaknesses

1. **Smoke recall is very low (7 % at 0.45).** Do not use smoke alone for any decision.
2. **Fire-like scenes** fool the fire model on about a third of the frames at 0.45: sunsets, candles, stage lights,
   orange-lit interiors. The API's 3-of-5 confirmation and the human operator are the safeguards. Detections are
   suggestions only (FR-C-11).
3. **Teacher boxes, not human boxes.** Box placement inherits Grounding DINO's errors, so the box geometry is
   approximate. The frame-level decision is what was evaluated.
4. **Small dataset, photos not CCTV.** The model was trained on 471 positive images, mostly consumer photos. Drone,
   CCTV, night and infrared footage are under-represented and were not evaluated.
5. **The sample is small**, so expect ±4–8 points of sampling error on each figure: 123 fire-positive and 43
   smoke-positive images.
6. The evaluation machine was a shared cloud VM. Latency on a dedicated server core is likely lower.

## Improving the model

The service does not change: only the ONNX file and its SHA-256 in `models/fetch_models.py` change.

* Add D-Fire (CC0-1.0, 21,527 images with human fire and smoke boxes) on a GPU, then retrain and re-evaluate:

  ```bash
  python training/train.py --data training/work/data --yolo /data/D-Fire/train:smoke,fire --device cuda --epochs 80
  ```

* Train YOLOX-S at 640 px on a GPU server for better small-fire recall, at about 3 times the CPU cost.
* Collect labelled frames from Tunisian Civil Protection footage, with their consent and under the platform's data
  rules.

Reproduce these numbers:

```bash
VISION_MODELS_DIR=/models python eval/evaluate.py --threads 2 --json results.json
```
