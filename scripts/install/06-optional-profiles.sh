#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 6: الملفات الاختيارية (الذكاء الاصطناعي، الرؤية، البحث، التوجيه، التضاريس...)، الدليل §9.
#
# متى: بعد 05-first-admin.sh، حسب الحاجة. أين: على الخادم.
#
# كل ملف (profile) يضيف خدمات إلى المنظومة الأساسية نفسها:
#   ai         خدمة الذكاء الاصطناعي و Ollama: تفريغ الرسائل الصوتية، الترجمة، القراءة المهيكلة للبلاغ، مساعد القائد.
#              نحو 6 GB من النماذج تُنزَّل مرة واحدة. كل النماذج تعمل على خوادمنا ولا تخرج أي معطيات.
#   vision     خدمة الرؤية (YOLOX على ONNX Runtime): كشف النار والدخان والأشخاص في الصور والبث، معالج فقط.
#   search     OpenSearch: البحث في مكتبة الأحداث والذاكرة الوطنية (دائم في الإنتاج)، 1 إلى 2 GB ذاكرة.
#   routing    Valhalla مع خريطة تونس (Geofabrik): المسار والوقت إلى موقع الحادث، ورسم المسلك في أمر المهمة.
#   terrain    نموذج التضاريس Copernicus GLO-90 (نحو 115 MB): انتشار الحرائق واتجاه الجريان.
#   sensors    بوابة الحساسات والأبراج (sensor-gateway). يولّد SENSOR_GATEWAY_TOKEN إن كان فارغًا.
#   drones     قارئ مواقع الدرون (لا يوجد أي طريق يرسل أمرًا إلى درون).
#   sim        محاكيات البث والمكالمات [SIM]: للعرض والتجربة فقط، ممنوعة في الإنتاج.
#   monitoring Prometheus و Alertmanager: يُشغَّل بـ 10-monitoring.sh لأنه يحتاج ملفات أسرار.
#
# الاستعمال: scripts/install/06-optional-profiles.sh ai vision search routing terrain
#            PROD=1 scripts/install/06-optional-profiles.sh search routing     # فوق compose.prod.yml
# بعده: scripts/install/07-data-load.sh
source "$(dirname "$0")/00-common.sh"
require_env_file

[ $# -gt 0 ] || die "اذكر ملفًا واحدًا على الأقل: ai vision search routing terrain sensors drones sim"
if [ "${PROD:-0}" = 1 ]; then cmd=("${COMPOSE_PROD[@]}"); else cmd=("${COMPOSE[@]}"); fi

args=()
for p in "$@"; do
  case "$p" in
    ai | vision | search | routing | terrain | sensors | drones) ;;
    sim) [ "${PROD:-0}" = 1 ] && die "المحاكيات [SIM] ممنوعة في الإنتاج" ;;
    monitoring) die "المراقبة: استعمل 10-monitoring.sh" ;;
    *) die "ملف غير معروف: $p" ;;
  esac
  args+=(--profile "$p")
done

if [[ " $* " == *" sensors "* ]] && [ -z "$(env_value SENSOR_GATEWAY_TOKEN)" ]; then
  set_env SENSOR_GATEWAY_TOKEN "$(openssl rand -hex 24)"
  ok "SENSOR_GATEWAY_TOKEN وُلّد"
fi
if [[ " $* " == *" vision "* ]] && [ -f "$ROOT/services/vision/models/fetch_models.py" ]; then
  step "التحقق من بصمة نموذج النار والدخان"
  python3 "$ROOT/services/vision/models/fetch_models.py" || warn "تعذّر التحقق من النموذج؛ خدمة vision-models تنزّله عند الإقلاع"
fi

step "تشغيل: $*"
"${cmd[@]}" "${args[@]}" up -d --build
"${cmd[@]}" "${args[@]}" ps --format 'table {{.Service}}\t{{.State}}\t{{.Health}}'
[[ " $* " == *" ai "* ]] && warn "تنزيل نماذج الذكاء الاصطناعي يأخذ وقتًا في المرة الأولى؛ تابع: docker compose ... logs -f ai-models"
ok "التالي: scripts/install/07-data-load.sh"
