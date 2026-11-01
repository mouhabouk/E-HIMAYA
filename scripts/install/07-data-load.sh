#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 7: تحميل البيانات الأولى (الطبقات، البرامج الموسمية، الإحصاء، فهرس المكتبة)، الدليل §9 و §11.5.
#
# متى: بعد 04-stack-start.sh (و 06 للبحث). أين: على الخادم. كل أمر يُجرَّب أولًا بالعدّ دون كتابة (--dry-run).
#
# الخطوات (اختر بالأسماء، أو all للكل بالترتيب):
#   layers      طبقات OpenStreetMap المستكملة (data/osm، 31 طبقة) تُحمَّل مسودات لا يراها إلا المدير، ثم ينشر كل طبقة
#               من صفحة «الطبقات» بعد مراجعة أسمائها. الطبقتان الحساستان (الثكنات، النفط والغاز) ليستا في المستودع:
#               يرفعهما المدير من اللوحة ويوسمهما «حساسة».
#   programmes  البرامج الموسمية لسنة PROGRAMMES_YEAR (2026 افتراضيًا) مسودات؛ يعتمدها مدير العمليات من صفحة «البرامج».
#   snacr-sim   سنوات إحصائية تجريبية [SIM] (2023 إلى 2025) لتجربة «تحليل المخاطر» والجداول المتقاطعة قبل وصول ملفات
#               الديوان. الملف الحقيقي يُحمَّل من قسم «الأرشيف» ويعوّض السنة التجريبية. الملفات الخام لا توضع في المستودع.
#   knowledge   فهرسة مكتبة الأحداث أول مرة في OpenSearch (يحتاج الملف search).
#
# الاستعمال: scripts/install/07-data-load.sh layers programmes
#            PROD=1 scripts/install/07-data-load.sh knowledge
# بعده: GPU (08) إن وُجد، ثم النشر في الإنتاج (09).
source "$(dirname "$0")/00-common.sh"
require_env_file

# في الإنتاج تعمل الحلقات في الحاوية worker؛ في التطوير الحاوية api تجمع الاثنين.
if [ "${PROD:-0}" = 1 ]; then cmd=("${COMPOSE_PROD[@]}") svc=worker; else cmd=("${COMPOSE[@]}") svc=api; fi
YEAR=${PROGRAMMES_YEAR:-2026}

run_mounted() { # run_mounted <مجلد محلي> <مسار في الحاوية> <أمر...>
  local src=$1 dst=$2
  shift 2
  "${cmd[@]}" run --rm -v "$src:$dst:ro" "$svc" "$@"
}

load_layers() {
  step "الطبقات: العدّ أولًا"
  run_mounted "$ROOT/data/osm" /data/osm python -m app.modules.layers.cli load-osm /data/osm --dry-run
  confirm "أحمّل هذه الطبقات مسودات؟" || return 0
  run_mounted "$ROOT/data/osm" /data/osm python -m app.modules.layers.cli load-osm /data/osm
  ok "حُمّلت مسودات؛ انشرها من صفحة «الطبقات»"
}

load_programmes() {
  local file=/data/programmes/$YEAR/programmes_$YEAR.json
  [ -f "$ROOT/data/programmes/$YEAR/programmes_$YEAR.json" ] || die "لا ملف برامج لسنة $YEAR"
  step "البرامج $YEAR: العدّ أولًا"
  run_mounted "$ROOT/data/programmes" /data/programmes python -m app.modules.programmes.cli load "$file" --dry-run
  confirm "أحمّل البرامج مسودات؟" || return 0
  run_mounted "$ROOT/data/programmes" /data/programmes python -m app.modules.programmes.cli load "$file"
  ok "حُمّلت؛ يعتمدها مدير العمليات من صفحة «البرامج»"
}

load_snacr_sim() {
  [ "${PROD:-0}" = 1 ] && die "السنوات التجريبية [SIM] لا تُحمَّل في الإنتاج"
  step "السنوات الإحصائية التجريبية [SIM] (نحو دقيقة)"
  "${cmd[@]}" exec -T "$svc" python -m app.modules.snacr.simulate --years 2023 2024 2025
  ok "حُمّلت بشارة [SIM]"
}

load_knowledge() {
  step "فهرسة مكتبة الأحداث"
  "${cmd[@]}" run --rm "$svc" python -m app.modules.knowledge.cli backfill --rebuild
  ok "فُهرست"
}

[ $# -gt 0 ] || die "اذكر خطوة: layers programmes snacr-sim knowledge (أو all)"
[ "$1" = all ] && set -- layers programmes knowledge
for s in "$@"; do
  case "$s" in
    layers) load_layers ;;
    programmes) load_programmes ;;
    snacr-sim) load_snacr_sim ;;
    knowledge) load_knowledge ;;
    *) die "خطوة غير معروفة: $s" ;;
  esac
done
ok "انتهى تحميل البيانات"
