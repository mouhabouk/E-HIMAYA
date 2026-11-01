#!/usr/bin/env bash
# ء-حماية / e-Himaya — المكتبة المشتركة لسكريبتات التنصيب (scripts/install).
#
# هذا الملف لا يُشغَّل وحده: كل سكريبت مرقّم يستدعيه في أوله بالأمر
#     source "$(dirname "$0")/00-common.sh"
# وهو يوفّر:
#   - ROOT: جذر المستودع (المجلد الذي فيه infra/ و services/)، وكل السكريبتات تعمل منه؛
#   - ENV_FILE: ملف الإعدادات (.env افتراضيًا، ويمكن تغييره بالمتغير EHIMAYA_ENV_FILE)؛
#   - COMPOSE / COMPOSE_PROD: أمرا Docker Compose للتطوير وللإنتاج، بالملفات نفسها التي يذكرها الدليل التقني؛
#   - دوال الطباعة (step, ok, warn, die) بالعربية مع رقم السكريبت، حتى يُعرف أين توقف التنصيب؛
#   - env_value: قراءة قيمة من .env دون تحميل الملف كله في الصدفة (لا تُطبع أي قيمة سرية)؛
#   - confirm: سؤال نعم/لا قبل كل خطوة لا رجعة فيها، ويمكن تجاوزه بـ ASSUME_YES=1 في التنصيب الآلي؛
#   - need: التحقق من وجود أداة قبل استعمالها، مع ذكر السكريبت الذي يثبّتها.
#
# كل السكريبتات تتوقف عند أول خطأ (set -euo pipefail) ويمكن إعادة تشغيلها بأمان: كل خطوة تتحقق أولًا هل نُفّذت.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
ENV_FILE=${EHIMAYA_ENV_FILE:-$ROOT/.env}
SCRIPT_NAME=$(basename "$0" .sh)

# shellcheck disable=SC2034 # تُستعمل في السكريبتات التي تستدعي هذا الملف
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$ROOT/infra/compose.yml")
# shellcheck disable=SC2034
COMPOSE_PROD=(docker compose --env-file "$ENV_FILE" -f "$ROOT/infra/compose.yml" -f "$ROOT/infra/compose.prod.yml")

if [ -t 1 ]; then
  C_STEP=$'\e[1;34m' C_OK=$'\e[1;32m' C_WARN=$'\e[1;33m' C_ERR=$'\e[1;31m' C_END=$'\e[0m'
else
  C_STEP='' C_OK='' C_WARN='' C_ERR='' C_END=''
fi

step() { printf '%s[%s] ▶ %s%s\n' "$C_STEP" "$SCRIPT_NAME" "$*" "$C_END"; }
ok() { printf '%s[%s] ✔ %s%s\n' "$C_OK" "$SCRIPT_NAME" "$*" "$C_END"; }
warn() { printf '%s[%s] ⚠ %s%s\n' "$C_WARN" "$SCRIPT_NAME" "$*" "$C_END" >&2; }
die() {
  printf '%s[%s] ✖ %s%s\n' "$C_ERR" "$SCRIPT_NAME" "$*" "$C_END" >&2
  exit 1
}

# need <أداة> <السكريبت الذي يثبّتها>
need() { command -v "$1" >/dev/null 2>&1 || die "الأداة $1 غير موجودة؛ شغّل أولًا $2"; }

# env_value <اسم>: آخر قيمة للمتغير في .env (فارغة إن غاب).
env_value() {
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true
}

# set_env <اسم> <قيمة>: يكتب القيمة في .env (يعوّض السطر إن وُجد، ويضيفه إن غاب).
set_env() {
  local name=$1 value=$2
  if grep -qE "^$name=" "$ENV_FILE"; then
    # الفاصل | لأن القيم قد تحتوي / (روابط، base64)؛ والقيم المولّدة لا تحتوي |.
    sed -i "s|^$name=.*|$name=$value|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$name" "$value" >>"$ENV_FILE"
  fi
}

# confirm <سؤال>: يرجع 0 عند «نعم». ASSUME_YES=1 يجيب نعم دائمًا.
confirm() {
  [ "${ASSUME_YES:-0}" = 1 ] && return 0
  local answer
  read -r -p "$1 [y/N] " answer
  [[ $answer =~ ^(y|Y|yes|YES|ن|نعم)$ ]]
}

# as_root: تشغيل أمر بصلاحية الجذر (sudo إن لم نكن root).
as_root() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi; }

require_env_file() {
  [ -f "$ENV_FILE" ] || die "الملف $ENV_FILE غير موجود؛ شغّل أولًا 03-project-fetch.sh"
}

# wait_http <رابط> <مهلة بالثواني>: ينتظر حتى يجيب الرابط بـ 2xx.
wait_http() {
  local url=$1 timeout=${2:-300} waited=0
  until curl -fsS -o /dev/null "$url" 2>/dev/null; do
    sleep 5
    waited=$((waited + 5))
    [ "$waited" -ge "$timeout" ] && return 1
  done
}

cd "$ROOT"
