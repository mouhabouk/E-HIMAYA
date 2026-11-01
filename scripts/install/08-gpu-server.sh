#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 8 (اختيارية): خادم GPU للنماذج الكبيرة، الدليل §10.
#
# متى: فقط إن كان للخادم بطاقة NVIDIA، بعد 02-docker-install.sh. أين: على خادم GPU.
#
# ما يفعله:
#   1. يثبّت مشغّل NVIDIA الموصى به (ubuntu-drivers) إن لم يكن nvidia-smi يعمل، ثم يطلب إعادة التشغيل؛
#   2. بعد إعادة التشغيل: يثبّت NVIDIA Container Toolkit من مستودع NVIDIA الرسمي ويربطه بـ Docker؛
#   3. يتحقق أن الحاويات ترى البطاقة (nvidia-smi داخل حاوية)؛
#   4. يشغّل الملف ai فوق compose.gpu.yml (النماذج على البطاقة بدل المعالج).
# تدريب كاشف النار والدخان (مركز التدريب) يحتاج هذا الخادم أيضًا: services/vision/training.
#
# الاستعمال: scripts/install/08-gpu-server.sh      (مرتين: قبل إعادة التشغيل وبعدها)
source "$(dirname "$0")/00-common.sh"
require_env_file

step "1/4 المشغّل"
if ! nvidia-smi >/dev/null 2>&1; then
  as_root ubuntu-drivers install
  warn "ثُبّت المشغّل: sudo reboot ثم أعد هذا السكريبت"
  exit 0
fi
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

step "2/4 NVIDIA Container Toolkit"
if ! command -v nvidia-ctk >/dev/null 2>&1; then
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey |
    as_root gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |
    as_root tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
  as_root apt-get update
  as_root apt-get install -y nvidia-container-toolkit
fi
as_root nvidia-ctk runtime configure --runtime=docker
as_root systemctl restart docker

step "3/4 البطاقة داخل الحاويات"
docker run --rm --gpus all ubuntu:24.04 nvidia-smi -L || die "الحاويات لا ترى البطاقة"

step "4/4 الذكاء الاصطناعي على البطاقة"
"${COMPOSE[@]}" -f "$ROOT/infra/compose.gpu.yml" --profile ai up -d
ok "الملف ai يعمل على GPU"
