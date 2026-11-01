#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 12: ترقية إصدار مثبت (وكيفية الرجوع)، الدليل §13.3.
#
# متى: عند كل إصدار جديد يُعتمد. أين: على خادم الإنتاج.
#
# ما يفعله بالترتيب:
#   1. يتحقق أن نسخة الليلة موجودة (يذكّر بـ 11-backup-check.sh) ويسأل قبل المتابعة؛
#   2. يحفظ رقم الإصدار الحالي في .ehimaya-previous-ref للرجوع إليه؛
#   3. يجلب الإصدار المطلوب: الوسم REF إن مُرّر، وإلا آخر main (git pull --ff-only، فلا يدمج تعديلات محلية)؛
#   4. يبني الصور الجديدة والخدمات تعمل (لا انقطاع أثناء البناء)؛
#   5. يطبّق ترحيلات القاعدة (migrate) قبل تشغيل الإصدار الجديد؛
#   6. يعيد تشغيل الخدمات وينتظر الجاهزية، ثم يتحقق من /health/ready.
#
# الرجوع: scripts/install/12-upgrade.sh rollback
#   يعود إلى الإصدار المحفوظ ويبنيه ويشغّله. الترحيلات لا تُلغى آليًا: إن احتاج الرجوع إلغاء ترحيل فنفّذ يدويًا
#   docker compose ... run --rm migrate alembic downgrade <revision>، بعد تجربته على نسخة. عند حادث: docs/runbooks/incident-response.md
#
# الاستعمال: REF=v1.1.0 scripts/install/12-upgrade.sh     أو    scripts/install/12-upgrade.sh rollback
source "$(dirname "$0")/00-common.sh"
require_env_file

state=$ROOT/.ehimaya-previous-ref
current=$(git -C "$ROOT" rev-parse HEAD)

restart() {
  step "البناء"
  "${COMPOSE_PROD[@]}" build
  step "ترحيلات القاعدة"
  "${COMPOSE_PROD[@]}" run --rm migrate
  step "التشغيل"
  "${COMPOSE_PROD[@]}" up -d --wait
  curl -fsS "https://$(env_value API_HOST)/health/ready" >/dev/null && ok "/health/ready = 200" || die "الخدمة لا تجيب؛ فكّر في: 12-upgrade.sh rollback"
}

if [ "${1:-}" = rollback ]; then
  [ -f "$state" ] || die "لا إصدار سابق محفوظ"
  prev=$(cat "$state")
  confirm "أرجع إلى $prev؟" || exit 0
  git -C "$ROOT" checkout "$prev"
  restart
  ok "رجعت إلى $prev"
  exit 0
fi

[ -z "$(git -C "$ROOT" status --porcelain --untracked-files=no)" ] || die "في المستودع تعديلات محلية؛ احفظها أو ألغها قبل الترقية"
warn "قبل الترقية: تأكد من نسخة الليلة (scripts/install/11-backup-check.sh check)"
confirm "أتابع الترقية من $(git -C "$ROOT" describe --tags --always)؟" || exit 0
echo "$current" >"$state"

step "جلب الإصدار"
git -C "$ROOT" fetch --tags origin
if [ -n "${REF:-}" ]; then git -C "$ROOT" checkout "$REF"; else git -C "$ROOT" pull --ff-only; fi
ok "الإصدار: $(git -C "$ROOT" describe --tags --always)"
restart
ok "انتهت الترقية (الإصدار السابق محفوظ في $state)"
