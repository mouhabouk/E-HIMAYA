#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 2: تثبيت Docker Engine 27+ و Docker Compose 2.24+، الدليل التقني §5.
#
# متى: بعد 01-system-prepare.sh (وبعد قرص البيانات إن وُجد).
# أين: على الخادم وعلى جهاز المطوّر (Ubuntu أو WSL2). على Windows يكفي Docker Desktop مع WSL2، ولا حاجة لهذا السكريبت.
#
# ما يفعله:
#   1. يضيف مستودع Docker الرسمي بمفتاحه الموقّع (الطريقة الموصى بها للخوادم، بدل حزمة docker.io القديمة في Ubuntu)؛
#   2. يثبّت docker-ce و docker-compose-plugin و buildx؛
#   3. يحدّ حجم السجلات (50 م.ب × 5 ملفات لكل حاوية) حتى لا يمتلئ القرص؛
#   4. يضيف حسابك إلى المجموعة docker (لتشغيل docker دون sudo؛ يسري بعد الخروج والدخول من جديد)؛
#   5. يتحقق من الإصدارين: Compose 2.24 ضروري لأن compose.prod.yml يستعمل !reset و !override؛
#   6. يشغّل hello-world للتأكد من أن المحرك يعمل.
# إعادة تشغيله آمنة: إن كان Docker مثبتًا بالإصدار المطلوب يتحقق فقط.
#
# الاستعمال: scripts/install/02-docker-install.sh
# بعده: اخرج وادخل من جديد (المجموعة docker)، ثم 03-project-fetch.sh.
source "$(dirname "$0")/00-common.sh"

version_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  ok "Docker مثبت من قبل"
else
  step "1/4 مستودع Docker الرسمي"
  as_root install -m 0755 -d /etc/apt/keyrings
  as_root curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  as_root chmod a+r /etc/apt/keyrings/docker.asc
  codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $codename stable" |
    as_root tee /etc/apt/sources.list.d/docker.list >/dev/null
  as_root apt-get update

  step "2/4 تثبيت المحرك و Compose"
  as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

step "3/4 حدود السجلات"
if [ ! -f /etc/docker/daemon.json ]; then
  echo '{ "log-driver": "json-file", "log-opts": { "max-size": "50m", "max-file": "5" } }' |
    as_root tee /etc/docker/daemon.json >/dev/null
  as_root systemctl restart docker
  ok "50m × 5 لكل حاوية"
else
  ok "/etc/docker/daemon.json موجود؛ لم ألمسه"
fi
if [ "$(id -u)" -ne 0 ] && ! id -nG "$USER" | grep -qw docker; then
  as_root usermod -aG docker "$USER"
  warn "أُضيف $USER إلى المجموعة docker: اخرج وادخل من جديد قبل السكريبت التالي"
fi

step "4/4 التحقق من الإصدارات"
engine=$(as_root docker version --format '{{.Server.Version}}')
compose=$(as_root docker compose version --short | sed 's/^v//')
version_ge "$engine" 27.0.0 || die "Docker Engine $engine أقدم من 27"
version_ge "$compose" 2.24.0 || die "Docker Compose $compose أقدم من 2.24 (compose.prod.yml يحتاج !reset)"
as_root docker run --rm hello-world >/dev/null
ok "Docker $engine و Compose $compose يعملان. التالي: scripts/install/03-project-fetch.sh"
