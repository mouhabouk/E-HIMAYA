#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 3: جلب المشروع، إنشاء .env وتوليد كل الأسرار، الدليل التقني §6.
#
# متى: بعد 02-docker-install.sh. أين: على الخادم.
#
# ما يفعله:
#   1. إن لم يكن المستودع موجودًا: يستنسخه في /opt/ehimaya (أو INSTALL_DIR) على الفرع أو الوسم REF (main افتراضيًا).
#      إن شغّلته من داخل نسخة موجودة يعمل عليها مباشرة؛
#   2. ينسخ .env.example إلى .env بصلاحية 600 (لا يقرؤه إلا صاحبه)؛
#   3. يولّد قيمة عشوائية جديدة لكل كلمة مرور وكل سر ما زال بقيمة المثال (change-me) أو فارغًا. لا يلمس أي سر موجود:
#      إعادة التشغيل لا تُفسد قاعدة بيانات قائمة؛
#   4. الأسرار الثلاثة الحرجة (FIELD_ENCRYPTION_KEY، CERTIFICATE_SIGNING_KEY، ANON_PSEUDONYM_SECRET) يذكّرك بحفظها
#      خارج الخادم: ضياع الأول يجعل البيانات المشفرة غير قابلة للقراءة، وتغيير الثاني يُبطل الشهادات الصادرة؛
#   5. الطقس: WEATHER=open-meteo يضبط Open-Meteo المجاني (دون مفتاح، بيانات CC BY 4.0) ويتحقق من الوصول إليه؛
#      دون ذلك يبقى المحاكي [SIM] (الشاشات تحمل الشارة الكهرمانية). للاستعمال التجاري: مفتاح Open-Meteo
#      (WEATHER_API_URL=https://customer-api.open-meteo.com و WEATHER_API_KEY) أو خادم Open-Meteo ذاتي؛
#   6. يتحقق أنه لم تبق أي قيمة مثال إلا قيم المحاكيات الثلاث المقصودة لجهاز التطوير.
#
# الاستعمال:
#   scripts/install/03-project-fetch.sh                         # داخل نسخة موجودة
#   REF=v1.0.0 WEATHER=open-meteo bash 03-project-fetch.sh      # استنساخ وسم معتمد مع الطقس الحقيقي
# المستودع الخاص يحتاج حساب GitHub بصلاحية القراءة أو مفتاح نشر (Deploy key) للقراءة فقط على الخادم.
# بعده: scripts/install/04-stack-start.sh
source "$(dirname "$0")/00-common.sh"

REPO_URL=${REPO_URL:-https://github.com/mouhabouk/E-HIMAYA.git}
INSTALL_DIR=${INSTALL_DIR:-/opt/ehimaya}
REF=${REF:-main}

step "1/6 المستودع"
if [ -d "$ROOT/.git" ] && [ -f "$ROOT/infra/compose.yml" ]; then
  ok "أعمل على النسخة الموجودة: $ROOT ($(git -C "$ROOT" describe --tags --always))"
else
  as_root mkdir -p "$INSTALL_DIR"
  as_root chown "$(id -un):" "$INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
  git -C "$INSTALL_DIR" checkout "$REF"
  ROOT=$INSTALL_DIR
  ENV_FILE=${EHIMAYA_ENV_FILE:-$ROOT/.env}
  cd "$ROOT"
  ok "استُنسخ في $ROOT على $REF"
fi

step "2/6 الملف .env"
if [ -f "$ENV_FILE" ]; then
  ok "$ENV_FILE موجود؛ أكمل القيم الناقصة فقط"
else
  cp "$ROOT/.env.example" "$ENV_FILE"
  ok "نُسخ من .env.example"
fi
chmod 600 "$ENV_FILE"

# fresh <اسم>: صحيح إذا كانت القيمة فارغة أو قيمة مثال، أي يجب توليدها.
fresh() {
  local v
  v=$(env_value "$1")
  [ -z "$v" ] || [[ $v == change-me* ]]
}

step "3/6 توليد الأسرار"
# كلمات المرور والرموز: 48 حرفًا ست عشريًا (24 بايت عشوائية). القائمة نفسها في الدليل التقني §6.1.
HEX24=(POSTGRES_PASSWORD EHIMAYA_DB_PASSWORD EHIMAYA_DB_RUNTIME_PASSWORD KEYCLOAK_DB_PASSWORD KEYCLOAK_ADMIN_PASSWORD
  VALKEY_PASSWORD NATS_APP_PASSWORD S3_SECRET_KEY TUSD_HOOK_SECRET AI_SERVICE_TOKEN METRICS_TOKEN
  MEDIAMTX_HOOK_TOKEN MEDIAMTX_API_PASSWORD VISION_API_TOKEN VISION_CALLBACK_TOKEN VISION_READ_PASSWORD
  OPENSEARCH_ADMIN_PASSWORD OPENSEARCH_PASSWORD TELEPHONY_ARI_PASSWORD SENSOR_GATEWAY_TOKEN)
generated=0
for v in "${HEX24[@]}"; do
  grep -qE "^$v=" "$ENV_FILE" || continue # متغير لا يعرفه هذا الإصدار من .env.example
  if fresh "$v"; then
    set_env "$v" "$(openssl rand -hex 24)"
    generated=$((generated + 1))
  fi
done
# الأسرار ذات الصيغة الخاصة: مفتاح التشفير ومفتاح توقيع الشهادات بـ base64 لـ 32 بايت.
fresh ANON_PSEUDONYM_SECRET && set_env ANON_PSEUDONYM_SECRET "$(openssl rand -hex 32)" && generated=$((generated + 1))
fresh FIELD_ENCRYPTION_KEY && set_env FIELD_ENCRYPTION_KEY "$(openssl rand -base64 32)" && generated=$((generated + 1))
fresh CERTIFICATE_SIGNING_KEY && set_env CERTIFICATE_SIGNING_KEY "$(openssl rand -base64 32)" && generated=$((generated + 1))
fresh SMS_INBOUND_SECRET && set_env SMS_INBOUND_SECRET "$(openssl rand -hex 32)" && generated=$((generated + 1))
ok "$generated سرًا جديدًا (الأسرار الموجودة لم تتغير)"
# المفتاحان بصيغة base64 لـ 32 بايت بالضبط، وإلا ترفض الواجهة البرمجية الإقلاع. قيمة غير صالحة لم تشفّر شيئا قط
# (الخادم لا يقلع بها)، فاستبدالها آمن. نهاية سطر Windows (\r) تُحذف من الملف كله أولا.
if grep -q $'\r' "$ENV_FILE"; then
  sed -i 's/\r$//' "$ENV_FILE"
  warn "حُذفت نهايات أسطر Windows (CRLF) من $ENV_FILE"
fi
key_ok() { python3 -c 'import base64,sys; sys.exit(0 if len(base64.b64decode(sys.argv[1].strip().strip(chr(34)+chr(39)), validate=True)) == 32 else 1)' "$1" 2>/dev/null; }
for v in FIELD_ENCRYPTION_KEY CERTIFICATE_SIGNING_KEY; do
  if ! key_ok "$(env_value "$v")"; then
    set_env "$v" "$(openssl rand -base64 32)"
    warn "$v لم يكن base64 لـ 32 بايت (نص المثال، أو قيمة من openssl rand -hex، أو لصق ناقص): وُلّد مفتاح جديد"
  fi
done

step "4/6 الأسرار الحرجة"
warn "انسخ هذه الأسرار الثلاثة إلى خزنة خارج الخادم قبل أي بيانات حقيقية (مظروف مختوم أو مدير أسرار):"
warn "  FIELD_ENCRYPTION_KEY، CERTIFICATE_SIGNING_KEY، ANON_PSEUDONYM_SECRET  (اقرأها بـ: grep -E '^(FIELD|CERT|ANON)' .env)"

step "5/6 الطقس"
case "${WEATHER:-}" in
  open-meteo)
    set_env WEATHER_PROVIDER open-meteo
    set_env WEATHER_API_URL https://api.open-meteo.com
    set_env MARINE_API_URL https://marine-api.open-meteo.com
    # طلب تجريبي على قابس: إن فشل فالخادم لا يصل إلى الإنترنت (جدار ناري أو وكيل)، والمنظومة تعود إلى المحاكي.
    if curl -fsS -m 15 'https://api.open-meteo.com/v1/forecast?latitude=33.88&longitude=10.1&current=temperature_2m,wind_speed_10m' |
      grep -q temperature_2m; then
      ok "Open-Meteo يجيب (الطقس الحقيقي، دون مفتاح)"
    else
      warn "Open-Meteo لا يجيب من هذا الخادم: اسمح بـ api.open-meteo.com و marine-api.open-meteo.com (HTTPS 443)"
    fi
    ;;
  sim | '') ok "الطقس المحاكى [SIM] (شغّل بـ WEATHER=open-meteo للطقس الحقيقي)" ;;
  *) die "WEATHER=${WEATHER} غير معروف (open-meteo أو sim)" ;;
esac

step "6/6 التحقق"
left=$(grep -nE '=change-me' "$ENV_FILE" | grep -vE 'STREAM_SIM|TELEPHONY_SIM' || true)
[ -z "$left" ] || die "بقيت قيم مثال: $(echo "$left" | cut -d= -f1 | tr '\n' ' ')"
ok "لا قيمة مثال متبقية (قيم المحاكيات STREAM_SIM_TOKEN و TELEPHONY_SIM_* تبقى لجهاز التطوير وتُفرَّغ في الإنتاج)"
ok "التالي: scripts/install/04-stack-start.sh"
