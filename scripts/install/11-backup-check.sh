#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 11: النسخ الاحتياطي والتحقق منه وتمرين الاستعادة، الدليل §13.1 و §13.2.
#
# النسخ الاحتياطي نفسه آلي في الإنتاج (الحاوية backup في compose.prod.yml): أرشفة WAL كل دقيقة على الأكثر، ونسخة قاعدية
# كل ليلة في BACKUP_HOUR (بتوقيت UTC)، مع الاحتفاظ بـ BACKUP_KEEP نسخ، ونسخة ثانية مشفرة في BACKUP_REMOTE (rclone) إن ضُبط.
# الهدف: خسارة 5 دقائق على الأكثر (RPO) والعودة في ساعة (RTO).
#
# هذا السكريبت:
#   check (يوميًا، دقيقتان): يعرض إعدادات النسخ، ويقرأ سجل الحاوية backup ليتأكد من نسخة الليلة، ويذكّر بالتنبيهين
#          WalArchiveLag و BaseBackupMissing في Prometheus؛
#   drill (كل ثلاثة أشهر، 30 دقيقة): يشغّل infra/backup/drill.sh الذي يستعيد نسخة في قاعدة مؤقتة ويجب أن ينتهي بـ DRILL PASSED.
#          يحتاج PostgreSQL و PostGIS و pgvector على الجهاز الذي يُشغَّل عليه.
# احفظ دائمًا خارج الخادم: .env، والأسرار الثلاثة الحرجة، ونسخة من قاعدة Keycloak.
#
# الاستعمال: scripts/install/11-backup-check.sh check | drill
source "$(dirname "$0")/00-common.sh"
require_env_file

case "${1:-check}" in
  check)
    step "الإعدادات"
    echo "  BACKUP_HOUR=$(b=$(env_value BACKUP_HOUR); echo "${b:-01}") (UTC)   BACKUP_KEEP=$(k=$(env_value BACKUP_KEEP); echo "${k:-7}")"
    [ -n "$(env_value BACKUP_REMOTE)" ] && ok "نسخة ثانية خارج الخادم: مضبوطة" || warn "BACKUP_REMOTE فارغ: لا نسخة خارج الخادم"
    step "سجل النسخ (آخر 24 ساعة)"
    "${COMPOSE_PROD[@]}" logs --since 24h --tail 40 backup || die "الحاوية backup غير موجودة (هل الإنتاج يعمل بـ compose.prod.yml؟)"
    warn "تحقق أيضًا ألا تنبيه WalArchiveLag أو BaseBackupMissing في Prometheus"
    ;;
  drill)
    step "تمرين الاستعادة"
    sh "$ROOT/infra/backup/drill.sh" | tee /tmp/ehimaya-drill.log
    grep -q 'DRILL PASSED' /tmp/ehimaya-drill.log && ok "DRILL PASSED" || die "فشل التمرين؛ راجع docs/runbooks/backup-restore.md"
    ;;
  *) die "check أو drill" ;;
esac
