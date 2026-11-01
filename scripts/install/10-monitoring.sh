#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 10: المراقبة والتنبيه في الإنتاج، الدليل §11.6.
#
# متى: بعد 09-production-deploy.sh. أين: على خادم الإنتاج.
#
# ما يفعله:
#   1. يكتب ملفي الأسرار اللذين يقرؤهما Prometheus من .env (METRICS_TOKEN و MEDIAMTX_API_PASSWORD) في
#      infra/monitoring/secrets بصلاحية 0400، دون طباعتهما؛
#   2. يشغّل الملف monitoring: Prometheus و Alertmanager و node-exporter؛
#   3. يذكّر بوجهة التنبيهات (infra/monitoring/alertmanager.yml) وبقواعدها (alerts.yml، منها WalArchiveLag و BaseBackupMissing).
#
# الاستعمال: scripts/install/10-monitoring.sh
# بعده: scripts/install/11-backup-check.sh (صباح اليوم التالي، بعد أول نسخة ليلية)
source "$(dirname "$0")/00-common.sh"
require_env_file

step "1/2 ملفات الأسرار"
dir=$ROOT/infra/monitoring/secrets
mkdir -p "$dir"
for pair in metrics_token:METRICS_TOKEN mediamtx_api_password:MEDIAMTX_API_PASSWORD; do
  f=$dir/${pair%%:*}
  [ -n "$(env_value "${pair#*:}")" ] || die "${pair#*:} فارغ في .env"
  [ -f "$f" ] && chmod 0600 "$f"
  (umask 077 && env_value "${pair#*:}" >"$f")
  chmod 0400 "$f"
done
ok "كُتبت بصلاحية 0400"

step "2/2 تشغيل المراقبة"
"${COMPOSE_PROD[@]}" --profile monitoring up -d
"${COMPOSE_PROD[@]}" --profile monitoring ps --format 'table {{.Service}}\t{{.State}}' | grep -Ei 'prometheus|alertmanager|node' || true
warn "تأكد من وجهة التنبيهات (البريد أو الهاتف) في infra/monitoring/alertmanager.yml"
ok "التالي: scripts/install/11-backup-check.sh بعد أول نسخة ليلية"
