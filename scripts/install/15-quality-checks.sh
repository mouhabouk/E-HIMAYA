#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 15: فحوص الجودة والأمن قبل كل إصدار، الدليل §16.
#
# متى: قبل كل إصدار يُنشر على خادم التجربة أو الإنتاج. أين: جهاز المطوّر (ci, zap) أو الخادم (harden).
#
# الأجزاء:
#   ci       scripts/ci-local.sh --keep-going: كل مهام GitHub Actions محليًا بالأوامر نفسها، في حاويات مؤقتة تُمحى بعدها.
#            النتيجة في ci-local-report.md؛ المطلوب: لا مهمة FAILED (المهمة التي تنقصها أداة تظهر SKIPPED مع السبب).
#   zap      infra/security/zap/run.sh: فحص الأمن الديناميكي OWASP ZAP على منظومة تعمل. المطلوب: لا تنبيه عالي الخطورة
#            خارج الاستثناءات الموثقة في rules.tsv.
#   harden   infra/security/harden-host.sh --check --profile prod (على الخادم، يحتاج ADMIN_NET): يعرض ما يجب تغييره في
#            تحصين النظام دون تغيير شيء. للتطبيق: --apply ثم --check من جديد (يجب أن يعطي 0 تغيير).
#   all      ci ثم zap.
# اختبار الحمل (infra/loadtest) لا يُشغَّل من هنا: يرفض الانطلاق إلا على النسخة المعزولة (ISOLATED=yes).
#
# الاستعمال: scripts/install/15-quality-checks.sh ci       أو       ADMIN_NET=10.20.0.0/24 scripts/install/15-quality-checks.sh harden
source "$(dirname "$0")/00-common.sh"

[ $# -gt 0 ] || die "اذكر فحصًا: ci zap harden (أو all)"
[ "$1" = all ] && set -- ci zap
for c in "$@"; do
  case "$c" in
    ci)
      step "مهام CI محليًا (قد تأخذ ساعة)"
      "$ROOT/scripts/ci-local.sh" --keep-going && ok "لا مهمة FAILED (التقرير: ci-local-report.md)" ||
        die "مهمة فشلت؛ السجلات في ci-local-logs/"
      ;;
    zap)
      step "OWASP ZAP"
      "$ROOT/infra/security/zap/run.sh"
      ;;
    harden)
      [ -n "${ADMIN_NET:-}" ] || die "حدّد ADMIN_NET (شبكة الإدارة المسموح لها بـ SSH)"
      step "تحصين الخادم (فحص دون تغيير)"
      as_root env ADMIN_NET="$ADMIN_NET" EHIMAYA_DIR="$ROOT" "$ROOT/infra/security/harden-host.sh" --check --profile prod
      ;;
    *) die "فحص غير معروف: $c" ;;
  esac
done
