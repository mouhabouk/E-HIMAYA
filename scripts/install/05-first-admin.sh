#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 5: أول مدير نظام في Keycloak، الدليل التقني §8.
#
# متى: بعد 04-stack-start.sh، مرة واحدة. أين: على الخادم.
#
# ما يفعله (بدل الخطوات اليدوية في واجهة إدارة Keycloak):
#   1. يدخل إلى Keycloak بحساب KEYCLOAK_ADMIN من .env عبر أداة kcadm داخل الحاوية (لا شيء يمر بالشبكة)؛
#   2. ينشئ في الفضاء ehimaya-staff المستخدم ADMIN_USER (افتراضيًا sysadmin) إن لم يكن موجودًا، بنطاق وطني
#      (scope_level=national) أو بولاية إن مرّرت GOUVERNORAT=<الرمز>، مثلا 61 لصفاقس؛
#   3. يسند الدور sysadmin، ثم يُنشئ هذا المدير بقية الحسابات من صفحة «الحسابات» في اللوحة؛
#   4. يعيّن كلمة مرور مؤقتة عشوائية تُطبع مرة واحدة، مع الإجراءين الإجباريين عند أول دخول:
#      تغيير كلمة المرور (UPDATE_PASSWORD) وتفعيل التحقق الثنائي TOTP (CONFIGURE_TOTP).
# حسابات المواطنين لا تُنشأ هنا: يسجّلون من التطبيق برقم الهاتف في الفضاء ehimaya-public.
#
# الاستعمال: ADMIN_USER=yamen ADMIN_EMAIL=yamen@example.tn scripts/install/05-first-admin.sh
# بعده: الملفات الاختيارية 06-optional-profiles.sh، أو النشر في الإنتاج 09-production-deploy.sh.
source "$(dirname "$0")/00-common.sh"
require_env_file

ADMIN_USER=${ADMIN_USER:-sysadmin}
ADMIN_EMAIL=${ADMIN_EMAIL:-$ADMIN_USER@ehimaya.local}
REALM=ehimaya-staff

kcadm() { "${COMPOSE[@]}" exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"; }

step "1/4 الدخول إلى Keycloak"
kcadm config credentials --server http://localhost:8080 --realm master \
  --user "$(env_value KEYCLOAK_ADMIN)" --password "$(env_value KEYCLOAK_ADMIN_PASSWORD)" >/dev/null
ok "متصل"

user_id() { kcadm get users -r "$REALM" -q "username=$ADMIN_USER" -q exact=true --fields id --format csv --noquotes; }

step "2/4 المستخدم $ADMIN_USER"
if [ -n "$(user_id)" ]; then
  ok "موجود من قبل؛ لن أغيّر كلمة مروره"
  exit 0
fi
if [ -n "${GOUVERNORAT:-}" ]; then scope=(-s "attributes.gouvernorat_code=[\"$GOUVERNORAT\"]"); else
  scope=(-s 'attributes.scope_level=["national"]')
fi
kcadm create users -r "$REALM" -s "username=$ADMIN_USER" -s enabled=true -s "email=$ADMIN_EMAIL" -s emailVerified=true \
  "${scope[@]}" -s 'requiredActions=["UPDATE_PASSWORD","CONFIGURE_TOTP"]' >/dev/null
ok "أُنشئ"

step "3/4 الدور sysadmin"
kcadm add-roles -r "$REALM" --uusername "$ADMIN_USER" --rolename sysadmin >/dev/null
ok "أُسند"

step "4/4 كلمة المرور المؤقتة"
password=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)
kcadm set-password -r "$REALM" --username "$ADMIN_USER" --new-password "$password" --temporary >/dev/null
echo
echo "  المستخدم: $ADMIN_USER"
echo "  كلمة المرور المؤقتة (تظهر مرة واحدة): $password"
echo "  عند أول دخول: كلمة مرور جديدة ثم TOTP (Google Authenticator أو FreeOTP أو Microsoft Authenticator)."
echo
ok "التالي: scripts/install/06-optional-profiles.sh (حسب الحاجة)"
