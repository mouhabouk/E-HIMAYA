"""Write ``dfire.ipynb`` (Google Colab) and ``dfire-kaggle.ipynb`` (Kaggle): train the fire and smoke detector on D-Fire
on a free GPU.

Each notebook carries its own copies of ``training/train.py`` and ``training/export_onnx.py`` (the repository is
private, the notebook cannot clone it), so both are generated from them and checked for drift like the OpenAPI document:

    python training/colab/build_notebook.py          # write
    python training/colab/build_notebook.py --check  # exit 1 if a notebook is out of date
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRAINING = HERE.parent
OUTPUTS = {"colab": HERE / "dfire.ipynb", "kaggle": HERE / "dfire-kaggle.ipynb"}

# YOLOX (Apache-2.0) at the commit pinned in training/requirements.txt, and its COCO weights (release 0.1.1rc0).
YOLOX_COMMIT = "6ddff4824372906469a7fae2dc3206c7aa4bbaee"
COCO_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.pth"
COCO_SHA256 = "9de513de589ac98bb92d3bca53b5af7b9acfa9b0bacb831f7999d0f7afaee8f0"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.strip("\n").splitlines(keepends=True),
    }


# Where each platform keeps the scripts, YOLOX and the COCO weights (not saved with the results).
WORK = {"colab": "/content", "kaggle": "/kaggle/temp"}


def writefile(name: str, platform: str) -> dict:
    return code(f"%%writefile {WORK[platform]}/ehimaya/{name}\n" + (TRAINING / name).read_text(encoding="utf-8"))


INTRO = {
    "colab": """
**قبل التشغيل:**
1. ارفع الملف `D-Fire.zip` إلى Google Drive داخل مجلد `E-HIMAYA` (أي `MyDrive/E-HIMAYA/D-Fire.zip`).
2. من القائمة: *Runtime → Change runtime type → T4 GPU*.
3. *Runtime → Run all*. يُطلب منك السماح بالوصول إلى Drive مرة واحدة.

النتائج تُحفظ في `MyDrive/E-HIMAYA/run-dfire/`. إذا انقطع الاتصال، شغّل الدفتر من جديد: التدريب يستأنف من آخر
دورة محفوظة. في النهاية أرسل الملف `fire-smoke-yolox-tiny-v3.onnx` والملف `history.jsonl`.
""",
    "kaggle": """
**قبل التشغيل** (حساب Kaggle موثّق برقم هاتف، وإلا فلا GPU ولا إنترنت):
1. *Add Input*: أضف مجموعة D-Fire، إما نسخة عامة منها على Kaggle أو الملف `D-Fire.zip` بعد رفعه كمجموعة بيانات
   خاصة (*Upload → New Dataset*). يكفي أن تحتوي على مجلد `train` فيه `images` و`labels`.
2. في اللوحة اليمنى *Session options*: *Accelerator → GPU T4 x2* (أو P100)، و*Internet → On*.
3. *Save Version → Save & Run All (Commit)*: يعمل التدريب في الخلفية حتى 12 ساعة ويمكنك إغلاق المتصفح.

عند الانتهاء، من صفحة النسخة: *Output → run-dfire* نزّل الملف `fire-smoke-yolox-tiny-v3.onnx` والملف
`history.jsonl` وأرسلهما.
""",
}

SETUP = {
    "colab": [
        code("""
# 1. GPU and Google Drive
import shutil
import subprocess

if not shutil.which("nvidia-smi"):
    raise SystemExit("No GPU in this session. Runtime > Change runtime type > T4 GPU, then Runtime > Run all.")
print(subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout)
from google.colab import drive
drive.mount("/content/drive")
"""),
        code("""
# 2. Settings
from pathlib import Path
DRIVE = Path("/content/drive/MyDrive/E-HIMAYA")
ZIP = DRIVE / "D-Fire.zip"
RUN = DRIVE / "run-dfire"          # checkpoints on Drive, so a new session resumes
DATA = Path("/content/dfire")      # images on the local disk (much faster than reading from Drive)
EPOCHS = 25
BATCH = 32
assert ZIP.exists(), f"{ZIP} not found: upload D-Fire.zip to MyDrive/E-HIMAYA/"
RUN.mkdir(parents=True, exist_ok=True)
print(ZIP, f"{ZIP.stat().st_size / 1e9:.2f} GB")
"""),
        code("""
# 3. Unpack D-Fire and find its train/test folders (each with images/ and labels/)
import zipfile
if not (DATA / ".unpacked").exists():
    with zipfile.ZipFile(ZIP) as archive:
        archive.extractall(DATA)
    (DATA / ".unpacked").touch()
splits = {}
for images in DATA.rglob("images"):
    if images.is_dir() and (images.parent / "labels").is_dir():
        splits[images.parent.name.lower()] = images.parent
print(splits)
TRAIN, TEST = splits["train"], splits["test"]
for name, root in (("train", TRAIN), ("test", TEST)):
    jpg = list((root / "images").glob("*.jpg"))
    boxed = [p for p in (root / "labels").glob("*.txt") if p.read_text().strip()]
    print(f"{name}: {len(jpg)} images, {len(boxed)} with boxes")
"""),
    ],
    "kaggle": [
        code("""
# 1. GPU
import shutil
import subprocess

if not shutil.which("nvidia-smi"):
    raise SystemExit("No GPU in this session. Session options > Accelerator > GPU T4 x2 (or P100), then run again.")
print(subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout)
"""),
        code("""
# 2. Settings
from pathlib import Path
INPUT = Path("/kaggle/input")         # the D-Fire dataset added with "Add Input" (read-only)
RUN = Path("/kaggle/working/run-dfire")  # saved with the notebook version: Output > run-dfire
DATA = Path("/kaggle/temp/dfire")     # where a zipped copy of D-Fire is unpacked
EPOCHS = 25
BATCH = 32
RUN.mkdir(parents=True, exist_ok=True)
"""),
        code("""
# 3. Find D-Fire's train/test folders (each with images/ and labels/), unpacking a zip first if that is all there is
import zipfile


def find_splits(root):
    found = {}
    for images in root.rglob("images"):
        if images.is_dir() and (images.parent / "labels").is_dir():
            found[images.parent.name.lower()] = images.parent
    return found


splits = find_splits(INPUT)
if "train" not in splits:
    for archive_path in INPUT.rglob("*.zip"):
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(DATA / archive_path.stem)
    splits = find_splits(DATA)
print(splits)
if "train" not in splits:
    raise SystemExit("D-Fire not found: Add Input > a D-Fire dataset with train/images and train/labels")
TRAIN = splits["train"]
for name, root in splits.items():
    jpg = list((root / "images").glob("*.jpg"))
    boxed = [p for p in (root / "labels").glob("*.txt") if p.read_text().strip()]
    print(f"{name}: {len(jpg)} images, {len(boxed)} with boxes")
"""),
    ],
}

INTERNET = {
    "colab": "",
    "kaggle": """
try:
    urllib.request.urlopen("https://github.com", timeout=10)
except OSError:
    raise SystemExit("No internet: Session options > Internet > On (needs a phone-verified account), then run again.")
""",
}

RESULT = {
    "colab": 'print("Send these two files:", RUN / "fire-smoke-yolox-tiny-v3.onnx", RUN / "history.jsonl")',
    "kaggle": 'print("Download from Output > run-dfire: fire-smoke-yolox-tiny-v3.onnx and history.jsonl")',
}


def notebook(platform: str) -> dict:
    work = WORK[platform]
    title = "Google Colab" if platform == "colab" else "Kaggle"
    cells = [
        md(f"""
# ء-حماية · تدريب كاشف الحرائق والدخان على D-Fire ({title})

يدرّب هذا الدفتر نموذج YOLOX-Tiny (الرخصة Apache-2.0) على مجموعة D-Fire (21,527 صورة، صناديق رسمها بشر، الرخصة
CC0-1.0)، ثم يصدّره بصيغة ONNX لخدمة الرؤية.
{INTRO[platform]}
*Generated by `services/vision/training/colab/build_notebook.py`; do not edit by hand.*
"""),
        *SETUP[platform],
        code(f"""
# 4. YOLOX (pinned commit), its Python dependencies, and the COCO weights
import hashlib, os, urllib.request
{INTERNET[platform]}
if not Path("{work}/YOLOX").exists():
    yolox = "https://github.com/Megvii-BaseDetection/YOLOX"
    subprocess.run(["git", "clone", "-q", yolox, "{work}/YOLOX"], check=True)
    subprocess.run(["git", "-C", "{work}/YOLOX", "checkout", "-q", "{YOLOX_COMMIT}"], check=True)
subprocess.run(["pip", "install", "-q", "loguru==0.7.3", "thop==0.1.1.post2209072238", "tabulate==0.10.0",
                "onnx==1.23.2", "onnxruntime==1.30.0"], check=True)
COCO = Path("{work}/yolox_tiny.pth")
if not COCO.exists():
    urllib.request.urlretrieve("{COCO_URL}", COCO)
assert hashlib.sha256(COCO.read_bytes()).hexdigest() == "{COCO_SHA256}", "unexpected COCO weights"
os.makedirs("{work}/ehimaya", exist_ok=True)
os.environ["PYTHONPATH"] = "{work}/YOLOX"


def run(*args):
    # Run a script in {work}/ehimaya, show its output live, and stop the notebook if it fails.
    process = subprocess.Popen(
        ["python", *map(str, args)], cwd="{work}/ehimaya", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    for line in process.stdout:
        print(line, end="")
    if process.wait():
        raise SystemExit(f"{{args[0]}} failed (exit {{process.returncode}}): see the lines above")


print("ready")
"""),
        md("The two cells below are the repository's `training/train.py` and `training/export_onnx.py`, unchanged."),
        writefile("train.py", platform),
        writefile("export_onnx.py", platform),
        code("""
# 5. Training (about 10 minutes per epoch on a T4; resumes from RUN/last.pth after a disconnect)
run("train.py", "--yolo", f"{TRAIN}:smoke,fire", "--weights", COCO, "--out", RUN, "--epochs", EPOCHS,
    "--batch", BATCH, "--lr", 0.01, "--mixup", 0.15, "--val-fraction", 0.08, "--negatives-per-positive", 0.5,
    "--workers", 2, "--device", "cuda")
"""),
        code("""
# 6. Learning curve (validation: image-level average precision per class)
import json
for line in (RUN / "history.jsonl").read_text().splitlines():
    row = json.loads(line)
    shown = {k: row[k] for k in ("total_loss", "ap_fire", "ap_smoke", "map") if k in row}
    print(row["epoch"], shown, "*" if row.get("best") else "")
"""),
        code(f"""
# 7. Export the best epoch to ONNX (checked against PyTorch) and print its SHA-256
run("export_onnx.py", "--checkpoint", RUN / "best.pth", "--out", RUN / "fire-smoke-yolox-tiny-v3.onnx")
{RESULT[platform]}
"""),
    ]
    metadata = {
        "colab": {
            "accelerator": "GPU",
            "colab": {"gpuType": "T4", "provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "kaggle": {
            "kaggle": {"accelerator": "gpu", "isGpuEnabled": True, "isInternetEnabled": True},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
    }
    return {"cells": cells, "metadata": metadata[platform], "nbformat": 4, "nbformat_minor": 4}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = 0
    for platform, out in OUTPUTS.items():
        text = json.dumps(notebook(platform), ensure_ascii=False, indent=1) + "\n"
        if args.check:
            if not out.exists() or out.read_text(encoding="utf-8") != text:
                print(f"{out.name} is out of date: run python training/colab/build_notebook.py", file=sys.stderr)
                stale = 1
            continue
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    return stale


if __name__ == "__main__":
    sys.exit(main())
