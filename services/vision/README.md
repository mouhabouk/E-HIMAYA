# e-Himaya vision service (`services/vision`)

This internal service finds **fire, smoke and people** in two places:

* photos attached to reports (`POST /v1/detect`);
* live streams that MediaMTX relays over internal RTSP (`PUT`/`DELETE /v1/streams/{id}`).

It is called only by the core API, on port 8100, and is never published. The binding interface is
[`docs/api/phase-6-contract.md`](../../docs/api/phase-6-contract.md) §3 (the detection callback) and §5 (this
service). The service decides nothing: the API decides when a detection is confirmed, and a person decides on any
alert (FR-C-11).

## Endpoints

| Method and path | Auth | Purpose |
|---|---|---|
| `GET /healthz` | none | `{"status": "ok"\|"degraded", "model", "detail", "streams", "max_streams"}`. It returns 200 even without a model, in which case `status` is `degraded`. |
| `GET /v1/model` | bearer | `{"name","version","license","labels":["fire","smoke","person"],"models":[…]}`. Returns 503 without a model. |
| `POST /v1/detect` | bearer | Takes a multipart field `image` (JPEG, PNG or WebP; at most 10 MB and 40 Mpx). The magic bytes must match the declared type. Returns `{"model","detections":[{"label","confidence","boxes":[[x1,y1,x2,y2,conf],…]}]}`, with coordinates normalised to 0..1. |
| `PUT /v1/streams/{id}` | bearer | Body `{"rtsp_url","callback_url"}`. Returns `202` and starts watching the stream. Sending the same body again is idempotent. Returns `429` with `Retry-After` when `VISION_MAX_STREAMS` streams are already being watched. |
| `DELETE /v1/streams/{id}` | bearer | Returns `204` and stops watching. It is idempotent. |
| `GET /v1/streams` | bearer | Lists the watched streams (for operations). |
| `GET /metrics` | bearer | Prometheus text: inference time, analysed frames, detections, callbacks, active streams, reconnects. |

Error bodies have the form `{"detail": "<code>"}`. The codes are:

* `401 invalid_token`
* `413 image_too_large`
* `415 unsupported_media_type` or `415 content_type_mismatch`
* `422 image_undecodable`, `422 image_too_small`, `422 image_empty`, `422 rtsp_url_not_allowed`,
  `422 callback_url_not_allowed`
* `503 model_unavailable` (with `Retry-After: 30`)
* `503 busy` (with `Retry-After: 5`)

### Live streams

* **Frame rate.** Each stream gets one thread, which decodes with PyAV (FFmpeg) over TCP. One frame per second is
  analysed (`VISION_FPS_IDLE`). After a fire or smoke detection, the rate rises to two frames per second
  (`VISION_FPS_PENDING`) until `VISION_PENDING_CLEAR_FRAMES` (5) clean frames in a row.
* **Callbacks.** While a stream is pending, **every** analysed frame is posted to `callback_url`, empty ones included,
  so that the API can apply its "3 of the last 5 frames" rule. A frame with detections carries a JPEG reduced to
  640 px (`frame_jpeg_b64`). Frames with only people in them are posted at most every 10 s. The header
  `X-Vision-Token: $VISION_CALLBACK_TOKEN` is sent with each callback.
* **End of a watch.**
  * When the stream breaks, the service reconnects with exponential backoff (1 s up to 15 s).
  * The watch ends when no frame has been read for `VISION_STREAM_GONE_AFTER_S` (60 s): the publisher has left and
    MediaMTX answers 404.
  * The watch also ends when the API answers 404, 409 or 410, after `VISION_MAX_WATCH_S`, or on `DELETE`.
* **Allowed URLs.** URLs are restricted to `VISION_RTSP_URL_PREFIX` and `VISION_CALLBACK_URL_PREFIX`, so the service
  cannot be used for SSRF. The MediaMTX read credentials (`vision` / `VISION_RTSP_PASSWORD`) are added by the service
  and never travel in the request.
* **Bounded CPU and memory.**
  * Every inference, from uploads and streams alike, goes through `VISION_INFERENCE_WORKERS` slots.
  * Each slot uses `VISION_INFERENCE_THREADS` ONNX Runtime threads.
  * Decoding uses one thread per stream.
  * A frame is converted to RGB (at most 1280 px) only when it is due for analysis, and only that frame is kept.
* **Shutdown.** On shutdown every watcher is stopped and joined. A crashing watcher frees its slot and is logged.

## Models

| Key | Model | Input | Labels | Source |
|---|---|---|---|---|
| `fire-smoke` | `ehimaya-fire-smoke-yolox-tiny` 2.0.0 | 416×416 | fire, smoke | YOLOX-Tiny fine-tuned by e-Himaya (`training/`, [EVALUATION.md](EVALUATION.md)) |
| `person` | `yolox-tiny-coco-person` 0.1.1rc0 | 416×416 | person (COCO class 0 only) | [Megvii YOLOX release 0.1.1rc0](https://github.com/Megvii-BaseDetection/YOLOX/releases/tag/0.1.1rc0) |

* **Running the models.** Both models run with ONNX Runtime on the CPU. The letterbox, YOLOX grid decoding, NMS and
  box normalisation are our own NumPy code (`app/processing.py`), so no Ultralytics or other AGPL code is involved.
* **Installing them.** `models/fetch_models.py` installs them. It uses only the standard library, downloads each ONNX
  file (or copies the bundled one), checks the pinned SHA-256 and writes `manifest.json`. Nothing is downloaded at
  run time.
* **Where they come from.** Our fire and smoke weights are committed in `models/weights/fire-smoke-yolox-tiny-v2.onnx`
  (20.2 MB; the repository is private, so a release asset would need a token to download). The person file comes from
  the YOLOX release.
* **Calibration.** A per-label calibration `score ** score_power` in the manifest (fire: 0.56, smoke: 0.74) maps
  the network scores onto the API thresholds (0.45 and 0.6): the raw threshold that reaches precision 0.80 becomes
  0.45. Fire is fitted on `eval/calibration.json` (`python eval/evaluate.py --samples eval/calibration.json --fit`);
  that set has only 3 smoke images, so smoke is fitted on the training-validation split pooled with
  `eval/calibration.json`. Neither overlaps the evaluation sample (EVALUATION.md).
* **Turning one off.** `VISION_ENABLED_MODELS='["fire-smoke"]'` turns the person model off on small CPUs.

```bash
python3 models/fetch_models.py --out /models                       # both models
python3 models/fetch_models.py --out /models --file fire-smoke=x.onnx   # from a local copy (same SHA-256 required)
```

### Why this model

ADR-08 requires that every model, both its code **and** its weights, be under a permissive licence. We checked the
candidates against their primary sources (model card and repository LICENSE) in October 2026:

| Candidate | Result |
|---|---|
| Ultralytics YOLOv8 / YOLO11 fire-smoke fine-tunes (most of Hugging Face and GitHub) | **Rejected:** AGPL-3.0 code, and Ultralytics treats trained weights as AGPL. |
| [pyronear/yolo11s_sensitive-detector](https://huggingface.co/pyronear/yolo11s_sensitive-detector) | **Rejected:** the card says Apache-2.0, but the model is an Ultralytics YOLO11 trained with Ultralytics, so its licence is disputed. |
| [msharma2026/rtdetr-fire-smoke](https://github.com/msharma2026/rtdetr-fire-smoke) | **Rejected:** trained with Ultralytics 8.4, no licence and no published weights. |
| [fireviewer/rfdetr-base-fire-smoke](https://huggingface.co/fireviewer/rfdetr-base-fire-smoke-v1v2-20260927) | **Rejected:** no licence on the model or its data. |
| [pedbrgs/Fire-Detection](https://github.com/pedbrgs/Fire-Detection) (D-Fire models) | **Rejected:** YOLOv5 (GPL-3.0 / AGPL-3.0). |
| AI For Mankind wildfire smoke boxes | **Rejected:** CC BY-NC-SA 4.0 (non-commercial). |
| Zero-shot Grounding DINO / OWLv2 at run time | **Rejected for run time:** licences are fine (Apache-2.0), but they take 5–8 s per frame on CPU against 0.1 s for YOLOX-Tiny. Grounding DINO is used **as a teacher** during training. |

No pretrained fire and smoke detector had both permissive code and permissive weights, so we trained one with only
permissive parts:

1. **Student.** [YOLOX-Tiny](https://github.com/Megvii-BaseDetection/YOLOX) (Apache-2.0, code and COCO weights).
2. **Images.** Open Images V7 *train* and *validation* images that humans verified to contain or not contain Fire,
   Flame, Wildfire, Bonfire, Campfire or Smoke (images CC BY 2.0, labels CC BY 4.0), with ordinary scenes with people
   as background images. Model 2.0.0 adds the human fire boxes of two GitHub datasets whose repositories grant a
   permissive licence: [FireNET](https://github.com/OlafenwaMoses/FireNET) (MIT) and the
   [FURG fire dataset](https://github.com/steffensbola/furg-fire-dataset) (CC0-1.0); see "Fire and smoke datasets
   found on GitHub" below.
3. **Boxes.** Open Images has no fire or smoke boxes. They were drawn by
   [Grounding DINO](https://github.com/IDEA-Research/GroundingDINO) Swin-T OGC (Apache-2.0), prompted "fire . smoke .".
   The human image labels gate them: a class verified absent gets no box, and an image verified positive where the
   teacher finds nothing is dropped. FireNET and FURG box fire only; the teacher adds their smoke boxes (score ≥ 0.5).
4. **Evaluation.** A pinned sample of the Open Images *test* split, never seen in training (see
   [EVALUATION.md](EVALUATION.md)).

The trade-offs are described in EVALUATION.md:

* the training set is still small (1,724 images with boxes, 851 of them with smoke);
* the Open Images boxes and the smoke boxes come from a teacher model, not from people;
* the evaluation is frame-level, because no box ground truth is available.

The pipeline accepts more data in YOLO format: `training/train.py --yolo DIR:smoke,fire`. D-Fire (CC0-1.0, 21,527
images with human fire and smoke boxes) is the best next addition; it is hosted on OneDrive and Kaggle, which the
build machine of 2.0.0 could not reach. The service code does not change, only the ONNX file and its SHA-256 in
`fetch_models.py`.

### Reproducing the fire and smoke model

The `training/` folder is never installed in the service image. It needs a separate environment: PyTorch CPU or GPU,
torchvision, transformers, onnxruntime, a YOLOX checkout and a GroundingDINO checkout.

Model 2.0.0 was fine-tuned from model 1.0.0 (itself from the COCO weights). `build_dataset.py` now reads the V7
label files; model 1.0.0 had used V5 (same images, fewer verified labels). The steps:

```bash
TEACHER="--checkpoint groundingdino_swint_ogc.pth --vocab bert-base-uncased-vocab.txt --short-side 512"
python training/build_dataset.py --out training/work/data --hard-negatives 3000 --background 1200
PYTHONPATH=GroundingDINO python training/pseudo_label.py --data training/work/data $TEACHER
python training/extra_datasets.py prepare --out training/work/extra          # FireNET + FURG, test splits held out
PYTHONPATH=GroundingDINO python training/pseudo_label.py --data training/work/extra/teacher $TEACHER
python training/extra_datasets.py merge --out training/work/extra            # human fire + teacher smoke boxes
python training/dedupe.py --protect eval/cache --protect training/work/extra/firenet/test/images \
    --protect training/work/extra/furg/test/images --out training/work/exclude.json \
    training/work/data/images training/work/extra/firenet/train/images training/work/extra/furg/train/images
PYTHONPATH=YOLOX python training/train.py --data training/work/data \
    --yolo training/work/extra/firenet/train:fire,smoke --yolo training/work/extra/furg/train:fire,smoke \
    --exclude training/work/exclude.json --weights fire-smoke-yolox-tiny-v1.pth --out training/work/run \
    --epochs 14 --smoke-repeat 2 --mixup 0.15 --val-fraction 0.08 --negatives-per-positive 0.6
PYTHONPATH=YOLOX python training/export_onnx.py --checkpoint training/work/run/best.pth --out fire-smoke-yolox-tiny-v2.onnx
VISION_MODELS_DIR=/models python eval/evaluate.py --threads 2
VISION_MODELS_DIR=/models python eval/evaluate_yolo.py --dir training/work/extra/firenet/test --classes fire,smoke
```

For a run from the COCO weights, pass `--weights yolox_tiny.pth` and about 30 epochs.

**D-Fire on a GPU (Google Colab or Kaggle).** `training/colab/dfire.ipynb` trains YOLOX-Tiny from the COCO weights
on the D-Fire train split (human boxes only, no teacher), keeps its checkpoints on Google Drive so that a new session
resumes, and exports the ONNX file. `training/colab/dfire-kaggle.ipynb` does the same on Kaggle (free GPU, sessions of
up to 12 hours, run in the background with *Save & Run All*), reading D-Fire from an attached dataset, unzipped or
not. Both are generated from `train.py` and `export_onnx.py` by `training/colab/build_notebook.py` (checked for drift
in CI). Some copies of the D-Fire archive hold empty or truncated image files (203 of the 17,222 train images in the
copy used here are empty); `train.py` decodes every image once and skips those it cannot read. The D-Fire test
split (4,306 images) is the held-out set:
`VISION_MODELS_DIR=/models python eval/evaluate_yolo.py --dir D-Fire/test --classes smoke,fire`.

### Fire and smoke datasets found on GitHub (October 2026)

Searched for "fire detection dataset", "fire smoke dataset", "wildfire smoke dataset", "D-Fire", "FASDD" and the
GitHub topics `fire-detection` / `smoke-detection`. Licences were read from each dataset's own repository or paper.
Only GitHub-hosted (repository, release asset) and Google Cloud Storage downloads were possible from the build
machine.

| Dataset | Content | Licence (primary source) | Hosting | Verdict |
|---|---|---|---|---|
| [FireNET](https://github.com/OlafenwaMoses/FireNET) | 502 photos, 1 class `fire`, Pascal VOC boxes (412 train / 90 val), small web thumbnails (~275 px) | MIT (repository LICENSE, dataset is the repository's release asset) | GitHub release | **Used** (train split; val split = test) |
| [FURG fire dataset](https://github.com/steffensbola/furg-fire-dataset) | 23 videos, flame rectangle on every frame (OpenCV XML); 17 annotated + 1 non-fire video used | CC0-1.0 (repository LICENSE) | in repository | **Used** (1 frame/s, 3 videos held out as test) |
| [D-Fire](https://github.com/gaia-solutions-on-demand/DFireDataset) | 21,527 images, YOLO boxes, 0 = smoke, 1 = fire (14,692 fire / 11,865 smoke boxes) | CC0-1.0 | OneDrive / Kaggle (blocked here) | Licence OK; **not downloadable here** — the best next addition |
| [FASDD](https://github.com/openrsgis/FASDD) (FASDD_CV) | ~95,000 CV images (fire, smoke, both, neither), YOLO/VOC/COCO | unclear: the Science Data Bank record and the ESSD paper state no data licence (the paper itself is CC BY 4.0); a Roboflow re-export is labelled CC BY 4.0 | Science Data Bank (blocked here) | **Owner decision**: confirm the licence with the authors; not downloadable here |
| [aiformankind/wildfire-smoke-dataset](https://github.com/aiformankind/wildfire-smoke-dataset) | 2,192 HPWREN frames, smoke boxes | CC BY-NC-SA 4.0 | Google Drive | **Rejected: non-commercial** |
| [open-climate-tech/firecam 2019a](https://github.com/open-climate-tech/firecam) | 1,661 HPWREN frames, smoke boxes | data CC BY-NC-SA 4.0 (code Apache-2.0) | in repository | **Rejected: non-commercial** |
| [MattDorling/wildfire-dataset](https://github.com/MattDorling/wildfire-dataset) | 3,852 frames (the two above, YOLO) | CC BY-NC-SA 4.0 (inherited) | in repository | **Rejected: non-commercial** |
| [ScryAbu/DBA-YOLO-Dataset](https://github.com/ScryAbu/DBA-YOLO-Dataset) | 3,905 images, fire and smoke YOLO boxes (web-crawled video frames) | none ("appropriate license terms" to come) | in repository | **Rejected: no licence** |
| [gengyanlei/fire-smoke-detect-yolov4](https://github.com/gengyanlei/fire-smoke-detect-yolov4) | 2,059 labelled + 10,827 unlabelled images | MIT on the code; the data are on Baidu / Google Drive with no data licence | Baidu / Drive | **Rejected: no data licence** |
| [siyuanwu/DFS-FIRE-SMOKE-Dataset](https://github.com/siyuanwu/DFS-FIRE-SMOKE-Dataset) | 9,462 images, fire / smoke / other boxes | none | Baidu / OneDrive | **Rejected: no licence** |
| [CostiCatargiu/NEWFireSmokeDataset_YoloModels](https://github.com/CostiCatargiu/NEWFireSmokeDataset_YoloModels) | fire and smoke YOLO dataset | none | external | **Rejected: no licence** |
| [Biometrix-4/FireSpot-CNX](https://github.com/Biometrix-4/FireSpot-CNX) | 4,000 images (Chiang Mai), labels | CC BY 4.0 (as cited by MultiNatSmoke); no LICENSE in the repository | Google Drive | Probably OK; not downloadable here, licence to confirm |
| [SayBender/Nemo](https://github.com/SayBender/Nemo) | wildfire smoke boxes (COCO JSON) | Apache-2.0 on the repository, but the images are not published | annotations only | Not usable (no images) |
| [DeepQuestAI/Fire-Smoke-Dataset](https://github.com/DeepQuestAI/Fire-Smoke-Dataset) | 3,000 images, classification only | none | GitHub release | **Rejected: no licence, no boxes** |
| [aiformankind/wildfire-dataset](https://github.com/aiformankind/wildfire-dataset) | 343 Google/Bing search images, classification | MIT on the repository, but scraped third-party photos | in repository | **Rejected: rights not held, no boxes** |
| [cair/Fire-Detection-Image-Dataset](https://github.com/cair/Fire-Detection-Image-Dataset) | ~650 images, classification | none | in repository | **Rejected: no licence** |
| [henryzhao0615/MultiNatSmoke](https://github.com/henryzhao0615/MultiNatSmoke), [LujianYao/FoSp](https://github.com/LujianYao/FoSp) (SmokeSeg), [SiyuanYan1/Transmission-BVM](https://github.com/SiyuanYan1/Transmission-BVM) (SMOKE5K) | smoke segmentation masks | mixed / none per source | Hugging Face / Drive | Not usable here (hosting, mixed licences) |
| Open Images V7 (not GitHub; GCS) | human-verified image labels Fire/Flame/Wildfire/Bonfire/Campfire/Smoke | images CC BY 2.0, labels CC BY 4.0 | GCS / S3 mirror | **Used**: the V7 label files list 1,433 verified smoke images in train against 532 in V5 |

## Licences

Every model and dataset that was used, with its primary source:

| Item | Role | Licence | Evidence |
|---|---|---|---|
| `ehimaya-fire-smoke-yolox-tiny` 2.0.0 (our weights) | fire and smoke model, shipped | Apache-2.0 | Derived from the YOLOX-Tiny weights and trained by us on the data below |
| YOLOX code and `yolox_tiny` COCO weights (0.1.1rc0) | person model (shipped); student initialisation | Apache-2.0 | [LICENSE](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE), [release assets](https://github.com/Megvii-BaseDetection/YOLOX/releases/tag/0.1.1rc0) |
| COCO 2017 (training data of YOLOX) | upstream of the person model | annotations CC BY 4.0; images under Flickr terms | [cocodataset.org/#termsofuse](https://cocodataset.org/#termsofuse) |
| Grounding DINO Swin-T OGC (code and `groundingdino_swint_ogc.pth`) | teacher (box drawing); training only, not shipped | Apache-2.0 | [LICENSE](https://github.com/IDEA-Research/GroundingDINO/blob/main/LICENSE), [release v0.1.0-alpha](https://github.com/IDEA-Research/GroundingDINO/releases/tag/v0.1.0-alpha) |
| BERT-base-uncased vocabulary (`vocab.txt`, SHA-256 `07eced37…`) | teacher tokenizer; training only | Apache-2.0 | [google-research/bert](https://github.com/google-research/bert/blob/master/LICENSE) |
| Open Images V7 train and validation images | training images | images CC BY 2.0; labels CC BY 4.0 (Google LLC) | [Open Images licence](https://storage.googleapis.com/openimages/web/factsfigures_v7.html#licenses) |
| Open Images V7 test images (383 in `eval/samples.json`, with author and page) | held-out evaluation; downloaded at run time, not committed | CC BY 2.0 per image; labels CC BY 4.0 | same as above; each sample lists its author and Flickr page |
| FireNET v1.0 (`fire-dataset.zip`, SHA-256 `714a5342…`), by Moses Olafenwa | training images and human fire boxes (412 train); its 90 validation images are a held-out test set | MIT | [LICENSE](https://github.com/OlafenwaMoses/FireNET/blob/master/LICENSE), [release v1.0](https://github.com/OlafenwaMoses/FireNET/releases/tag/v1.0) |
| FURG fire dataset (commit `6aff09d7`), by Steffens, Hüttner et al. | video frames with human fire boxes (17 videos; 3 held out as a test set) | CC0-1.0 | [LICENSE](https://github.com/steffensbola/furg-fire-dataset/blob/master/LICENSE) |
| D-Fire (not used: not reachable from the build machine) | best next training data | CC0-1.0 (the authors note that images keep their providers' terms) | [LICENSE](https://github.com/gaia-solutions-on-demand/DFireDataset/blob/master/LICENSE) |

Runtime libraries:

* ONNX Runtime (MIT)
* NumPy (BSD-3-Clause)
* Pillow (MIT-CMU)
* FastAPI (MIT)
* Uvicorn (BSD-3-Clause)
* httpx (BSD-3-Clause)
* structlog (MIT or Apache-2.0)
* prometheus-client (Apache-2.0)
* python-multipart (Apache-2.0)
* PyAV (BSD-3-Clause)

The FFmpeg that the PyAV wheel bundles includes GPL components (x264 and x265). The service only *decodes*, and no
AGPL component is involved. If the image is redistributed, GPL source offers for FFmpeg, x264 and x265 apply; their
sources are public upstream.

Training libraries (not shipped): PyTorch and torchvision (BSD-3-Clause), transformers (Apache-2.0).

## Configuration (`VISION_*`)

| Variable | Default | Meaning |
|---|---|---|
| `VISION_API_TOKEN` | — (required, ≥ 24 characters) | Bearer token the API presents. |
| `VISION_CALLBACK_TOKEN` | — (required, ≥ 24 characters) | Sent as `X-Vision-Token` on callbacks. |
| `VISION_RTSP_PASSWORD` | empty | MediaMTX read password of user `VISION_RTSP_USER` (`vision`). |
| `VISION_MODELS_DIR` | `/models` | Output of `fetch_models.py`. |
| `VISION_ENABLED_MODELS` | `["fire-smoke","person"]` | Models to load. |
| `VISION_MIN_CONFIDENCE` | 0.45 | Detections under this confidence are dropped (same floor as the API). |
| `VISION_MAX_STREAMS` | 8 | Concurrent watches; beyond this, `429`. |
| `VISION_INFERENCE_WORKERS` / `VISION_INFERENCE_THREADS` | 2 / 2 | CPU budget: workers × threads cores at most. |
| `VISION_FPS_IDLE` / `VISION_FPS_PENDING` | 1 / 2 | Analysed frames per second. |
| `VISION_RTSP_URL_PREFIX` | `rtsp://mediamtx:8554/live/` | Only these streams are watched. |
| `VISION_CALLBACK_URL_PREFIX` | `http://api:8000/internal/vision/` | Only this callback target is accepted. |
| `VISION_STREAM_GONE_AFTER_S` | 60 | Give up after this long without a frame. |
| `VISION_MAX_WATCH_S` | 21600 | Hard cap on a single watch. |
| `VISION_MAX_IMAGE_BYTES` / `VISION_MAX_IMAGE_PIXELS` | 10 MB / 40 Mpx | Upload limits. |

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy app
uv run pytest -q                                   # unit and API tests, no model needed
python3 models/fetch_models.py --out /tmp/vision-models
VISION_MODELS_DIR=/tmp/vision-models uv run pytest -o addopts="" -m models -v -s     # real models
VISION_MODELS_DIR=/tmp/vision-models uv run python eval/evaluate.py
```

CI runs three jobs:

* `Vision · lint, types, tests`;
* `Vision · real models`: fetches the models (cached), runs the real-model tests and the evaluation, then checks that
  the models image fills a volume and the runtime image starts healthy on it;
* the Trivy scan of the runtime image (`Images · build and Trivy scan`).
