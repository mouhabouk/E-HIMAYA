#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 2: تثبيت Docker Engine 27+ و Docker Compose 2.24+، الدليل التقني §5.
#
# متى: بعد 01-system-prepare.sh (وبعد قرص البيانات إن وُجد).
# أين: على الخادم وعلى جهاز المطوّر (Ubuntu أو WSL2). على Windows يكفي Docker Desktop مع WSL2، ولا حاجة لهذا السكريبت.
#
# ما يفعله:
#   1. يضيف مستودع Docker الرسمي بمفتاحه الموقّع (الطريقة الموصى بها للخوادم، بدل حزمة docker.io القديمة في Ubuntu)؛
#   2. يثبّت docker-ce و docker-compose-plugin و buildx؛
#   3. يحدّ حجم السجلات (50 م.ب × 5 ملفات لكل حاوية) ويضبط DNS الحاويات (DOCKER_DNS)، بالدمج في daemon.json
#      دون حذف أي إعداد موجود؛
#   4. يضيف حسابك إلى المجموعة docker (لتشغيل docker دون sudo؛ يسري بعد الخروج والدخول من جديد)؛
#   5. يتحقق من الإصدارين: Compose 2.24 ضروري لأن compose.prod.yml يستعمل !reset و !override؛
#   6. يشغّل hello-world للتأكد من أن المحرك يعمل.
# إعادة تشغيله آمنة: إن كان Docker مثبتًا بالإصدار المطلوب يتحقق فقط.
#
# الاستعمال: scripts/install/02-docker-install.sh
#            DOCKER_DNS=10.0.0.1 DOCKER_DNS_CHECK=api.ehimaya.lan scripts/install/02-docker-install.sh   (شبكة محلية)
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

step "3/4 حدود السجلات وخادم الأسماء (DNS)"
# يُدمج في /etc/docker/daemon.json دون حذف أي إعداد موجود (نسخة احتياطية قبل كل تغيير).
# DOCKER_DNS: خوادم الأسماء التي تستعملها الحاويات، بالترتيب. في الشبكة المحلية للديوان: الخادم الداخلي أولا
# (مثلا DOCKER_DNS=10.0.0.1)، ثم خادم عام فقط إن كان للخادم مخرج إلى الإنترنت (DOCKER_DNS=10.0.0.1,1.1.1.1).
# دون DOCKER_DNS: لا يُلمس المفتاح dns، ويأخذ Docker خوادم المضيف (systemd-resolved).
daemon=/etc/docker/daemon.json
merged=$(mktemp)
as_root cat "$daemon" 2>/dev/null >"$merged.in" || true
python3 "$(dirname "$0")/docker-daemon-merge.py" "$merged.in" ${DOCKER_DNS:+--dns "$DOCKER_DNS"} >"$merged" ||
  die "تعذّر دمج $daemon (انظر الرسالة أعلاه)"
if as_root cmp -s "$merged" "$daemon"; then
  ok "$daemon على حاله: $(tr -d '\n ' <"$merged")"
else
  if as_root test -f "$daemon"; then
    as_root cp -p "$daemon" "$daemon.bak.$(date +%Y%m%d%H%M%S)"
  fi
  as_root dockerd --validate --config-file "$merged" >/dev/null || die "dockerd يرفض الإعداد المدمج؛ لم يُغيَّر $daemon"
  as_root install -m 0644 "$merged" "$daemon"
  as_root systemctl restart docker
  ok "$daemon: $(tr -d '\n ' <"$merged")"
fi
rm -f "$merged" "$merged.in"
# فحص: هل تحلّ الحاويات الأسماء؟ (اسم داخلي إن أُعطي DOCKER_DNS_CHECK، وإلا registry-1.docker.io عند وجود إنترنت)
check_name=${DOCKER_DNS_CHECK:-}
if [ -n "$check_name" ]; then
  if as_root docker run --rm busybox:1.37 nslookup "$check_name" >/dev/null 2>&1; then
    ok "الحاويات تحلّ $check_name"
  else
    warn "الحاويات لا تحلّ $check_name: راجع DOCKER_DNS (الخادم الداخلي أولا)، أو حمّل الصورة busybox:1.37"
  fi
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
