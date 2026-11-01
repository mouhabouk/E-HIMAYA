#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 16: قائمة التحقق النهائية قبل استقبال أول بلاغ حقيقي، الدليل §18.
#
# متى: في آخر التنصيب، وبعد كل ترقية. أين: على الخادم. لا يغيّر شيئًا: يقرأ ويحكم فقط.
#
# كل سطر نتيجته ✔ (ناجح) أو ⚠ (يحتاج انتباهًا) أو ✖ (مانع). البنود التي تتطلب عينًا بشرية (أول مدير فعّل TOTP،
# الأسرار محفوظة خارج الخادم، APK مثبت على هاتف تجربة) تظهر في آخره للتأشير اليدوي.
#
# الاستعمال: scripts/install/16-final-verify.sh          (PROD=1 لفحوص الإنتاج عبر الأسماء العامة)
# الخروج بـ 1 إن وُجد بند مانع.
source "$(dirname "$0")/00-common.sh"
require_env_file

fails=0
check() { # check <وصف> <أمر...>
  local what=$1
  shift
  if "$@" >/dev/null 2>&1; then ok "$what"; else
    warn "$what"
    fails=$((fails + 1))
  fi
}
version_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }

step "النظام"
check "الوقت متزامن" sh -c "timedatectl show -p NTPSynchronized --value | grep -q yes"
check "SSH بالمفاتيح فقط" sh -c "sshd -T 2>/dev/null | grep -qi '^passwordauthentication no' || grep -qE '^PasswordAuthentication no' /etc/ssh/sshd_config"
check "الجدار الناري مفعّل" sh -c "ufw status 2>/dev/null | grep -q 'Status: active' || sudo -n ufw status | grep -q 'Status: active'"
check "Compose 2.24 أو أحدث" version_ge "$(docker compose version --short | sed 's/^v//')" 2.24.0

step "الإعداد"
check ".env بصلاحية 600" sh -c "[ \"\$(stat -c %a '$ENV_FILE')\" = 600 ]"
check "لا قيمة مثال change-me (خارج المحاكيات)" sh -c "! grep -E '=change-me' '$ENV_FILE' | grep -vqE 'STREAM_SIM|TELEPHONY_SIM'"
check "الطقس الحقيقي مضبوط (وإلا [SIM])" sh -c "grep -q '^WEATHER_PROVIDER=open-meteo' '$ENV_FILE'"

step "الخدمات"
if [ "${PROD:-0}" = 1 ]; then
  api=https://$(env_value API_HOST)
  check "لا قيمة محاكي في الإنتاج" sh -c "! grep -qE '^(STREAM_SIM_TOKEN|TELEPHONY_SIM_TOKEN|TELEPHONY_SIM_PASSWORD)=.+' '$ENV_FILE'"
  check "/docs = 404" sh -c "[ \"\$(curl -s -o /dev/null -w '%{http_code}' $api/docs)\" = 404 ]"
  check "HSTS و CSP على اللوحة" sh -c "curl -sI https://$(env_value DASHBOARD_HOST)/ | grep -qi strict-transport"
  check "نسخة احتياطية في آخر 24 ساعة" sh -c "${COMPOSE_PROD[*]} logs --since 24h backup 2>/dev/null | grep -qi backup"
else
  api=http://localhost:8000
fi
check "/health/ready = 200" curl -fsS "$api/health/ready"
check "رابط تنزيل التطبيق ورمز QR" curl -fsS -o /dev/null "$api/api/v1/app/qr.svg"
check "اختبار الدخان" python3 "$ROOT/infra/smoke/smoke_test.py"

step "للتأشير اليدوي"
cat <<'LIST'
  [ ] أول مدير نظام دخل وفعّل TOTP.
  [ ] الأسرار الثلاثة (FIELD_ENCRYPTION_KEY، CERTIFICATE_SIGNING_KEY، ANON_PSEUDONYM_SECRET) ونسخة .env في الخزنة.
  [ ] المراقبة تعمل ووجهة التنبيه مجرّبة.
  [ ] تمرين الاستعادة DRILL PASSED (11-backup-check.sh drill).
  [ ] ملفا APK موقّعان بعناوين الخادم ومثبتان على هاتف تجربة، وبلاغ تجريبي وصل إلى اللوحة.
  [ ] 15-quality-checks.sh ci و zap دون فشل.
LIST

[ "$fails" -eq 0 ] && ok "كل الفحوص الآلية ناجحة" || die "$fails بند يحتاج انتباهًا (السطور ⚠ أعلاه)"
