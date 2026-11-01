#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 9: النشر في الإنتاج (خادم التجربة الميدانية)، الدليل §11 و docs/deploy-production.md.
#
# متى: بعد 03 (والأفضل بعد تجربة 04 و 05). أين: على الخادم الذي تشير إليه أسماء DNS.
#
# قبل التشغيل: خمسة أسماء DNS تشير إلى الخادم، تُكتب في .env:
#   API_HOST (الواجهة البرمجية والرفع)، DASHBOARD_HOST (اللوحة)، PORTAL_HOST (بوابة المؤسسات)، AUTH_HOST (Keycloak)،
#   MEDIA_HOST (البث). و CADDY_TLS = بريد حساب ACME للشهادات العامة، أو internal للعرض دون أسماء حقيقية.
#
# ما يفعله:
#   1. يتحقق من الأسماء الخمسة ومن أنها تُحلّ إلى عنوان؛
#   2. يفرّغ قيم المحاكيات (STREAM_SIM_TOKEN و TELEPHONY_SIM_*): الواجهة البرمجية ترفض الإقلاع في الإنتاج بها؛
#   3. يضبط TUSD_CORS_ORIGIN_REGEX من اسمي اللوحة والبوابة، و ENVIRONMENT_BANNER (pilot لخادم التجربة: شريط كهرماني
#      يسمّي البيئة حتى لا تُخلط بيانات التجربة بالحقيقية؛ auto للإنتاج الفعلي دون شريط)؛
#   4. يفتح منافذ الإنتاج في الجدار الناري: 80 و 443 (TCP و UDP لـ HTTP/3) لـ Caddy، و 8189/UDP لوسائط WebRTC،
#      و RTSP/RTMP من شبكة الكاميرات CAMERA_CIDR فقط، والهاتف (SIP و RTP) من عنوان SBC المشغّل فقط إن حُدد SBC_IP؛
#   5. يبني ويشغّل بـ compose.prod.yml وينتظر الجاهزية (--wait). ترتيب الإقلاع: postgres، db-roles، migrate، api و worker، caddy؛
#   6. يحدّث في Keycloak روابط العودة (Valid redirect URIs و Web origins) لعميلي اللوحة والبوابة إلى أسماء الإنتاج؛
#   7. فحوص ما بعد النشر: /health/ready = 200، /docs = 404 (الوثائق مخفية)، /metrics = 404 من الخارج،
#      رأسا HSTS و CSP على اللوحة، ثم اختبار الدخان على العنوان العام.
#
# الاستعمال: BANNER=pilot CAMERA_CIDR=10.30.0.0/24 SBC_IP=41.x.x.x scripts/install/09-production-deploy.sh
#            LAN=1 ... (على شبكة الديوان دون إنترنت، مع الحساسات والكاميرات والدرون: يضيف compose.lan.yml)
# بعده: scripts/install/10-monitoring.sh
source "$(dirname "$0")/00-common.sh"
require_env_file

cmd=("${COMPOSE_PROD[@]}")
[ "${LAN:-0}" = 1 ] && cmd+=(-f "$ROOT/infra/compose.lan.yml" --profile sensors --profile vision --profile drones)

step "1/7 أسماء DNS"
for v in API_HOST DASHBOARD_HOST PORTAL_HOST AUTH_HOST MEDIA_HOST CADDY_TLS; do
  [ -n "$(env_value "$v")" ] || die "$v فارغ في .env (الدليل §11.1 و §11.2)"
done
for v in API_HOST DASHBOARD_HOST PORTAL_HOST AUTH_HOST MEDIA_HOST; do
  h=$(env_value "$v")
  getent hosts "$h" >/dev/null || warn "$h لا يُحلّ بعد (DNS): شهادة ACME ستفشل حتى يُحلّ"
done
ok "الأسماء مضبوطة"

step "2/7 إفراغ المحاكيات"
for v in STREAM_SIM_TOKEN TELEPHONY_SIM_PASSWORD TELEPHONY_SIM_TOKEN; do set_env "$v" ""; done
ok "لا محاكي في الإنتاج"

step "3/7 الأصول وشريط البيئة"
d=$(env_value DASHBOARD_HOST | sed 's/\./\\./g')
p=$(env_value PORTAL_HOST | sed 's/\./\\./g')
set_env TUSD_CORS_ORIGIN_REGEX "^https://($d|$p)\$"
set_env ENVIRONMENT_BANNER "${BANNER:-auto}"
ok "ENVIRONMENT_BANNER=${BANNER:-auto}"

step "4/7 الجدار الناري للإنتاج"
if command -v ufw >/dev/null 2>&1; then
  as_root ufw allow 80/tcp
  as_root ufw allow 443/tcp
  as_root ufw allow 443/udp
  as_root ufw allow 8189/udp
  if [ -n "${CAMERA_CIDR:-}" ]; then
    as_root ufw allow from "$CAMERA_CIDR" to any port 8554 proto tcp
    as_root ufw allow from "$CAMERA_CIDR" to any port 1935 proto tcp
  fi
  if [ -n "${SBC_IP:-}" ]; then
    as_root ufw allow from "$SBC_IP" to any port 5060,5061 proto tcp
    as_root ufw allow from "$SBC_IP" to any port 5060 proto udp
    as_root ufw allow 10000:10099/udp
  fi
  as_root ufw status numbered | head -30
else
  warn "ufw غير موجود؛ افتح المنافذ يدويًا"
fi

step "5/7 البناء والتشغيل"
"${cmd[@]}" up -d --build --wait

step "6/7 روابط العودة في Keycloak"
kcadm() { "${cmd[@]}" exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"; }
kcadm config credentials --server http://localhost:8080 --realm master \
  --user "$(env_value KEYCLOAK_ADMIN)" --password "$(env_value KEYCLOAK_ADMIN_PASSWORD)" >/dev/null
for pair in "ehimaya-dashboard:DASHBOARD_HOST" "ehimaya-portal:PORTAL_HOST"; do
  client=${pair%%:*}
  host=$(env_value "${pair#*:}")
  realm=ehimaya-staff
  [ "$client" = ehimaya-portal ] && realm=ehimaya-public
  id=$(kcadm get clients -r "$realm" -q "clientId=$client" --fields id --format csv --noquotes || true)
  if [ -n "$id" ]; then
    kcadm update "clients/$id" -r "$realm" -s "redirectUris=[\"https://$host/*\"]" -s "webOrigins=[\"https://$host\"]"
    ok "$client → https://$host"
  else
    warn "العميل $client غير موجود في $realm: حدّث روابطه يدويًا"
  fi
done

step "7/7 فحوص ما بعد النشر"
api=https://$(env_value API_HOST)
code() { curl -s -o /dev/null -w '%{http_code}' "$1"; }
[ "$(code "$api/health/ready")" = 200 ] && ok "/health/ready = 200" || die "/health/ready لا يجيب 200"
[ "$(code "$api/docs")" = 404 ] && ok "/docs مخفية" || warn "/docs ظاهرة في الإنتاج"
[ "$(code "$api/metrics")" = 404 ] && ok "/metrics مغلقة من الخارج" || warn "/metrics مفتوحة من الخارج"
headers=$(curl -sI "https://$(env_value DASHBOARD_HOST)/")
grep -qi strict-transport <<<"$headers" && grep -qi content-security <<<"$headers" && ok "HSTS و CSP حاضران" ||
  warn "رأس HSTS أو CSP غائب"
API_URL=$api TUS_URL=$api/api/v1/uploads/ NOTIFY_SIM_URL='' python3 "$ROOT/infra/smoke/smoke_test.py"
ok "الإنتاج يعمل. التالي: scripts/install/10-monitoring.sh ثم 07-data-load.sh knowledge مع PROD=1"
