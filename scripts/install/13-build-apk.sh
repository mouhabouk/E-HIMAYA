#!/usr/bin/env bash
# ء-حماية / e-Himaya — الأولوية 13: بناء تطبيقي الهاتف (المواطن والأعوان) للتوزيع، الدليل §14
# و docs/deliverables/apk-integration (الملف التقني لتصدير APK والربط بين الوسائط).
#
# طريقتان:
#   أ) دون أي تثبيت: على GitHub، Actions ← «Android APKs» ← Run workflow (يبني الملفين ويضعهما للتنزيل)، أو بوسم vX.Y.Z
#      فيُنشر إصدار (Release) يحمل الملفين؛ رابط التنزيل ورمز QR في /api/v1/app/download و /api/v1/app/qr.png يشيران إليه.
#   ب) محليًا بهذا السكريبت، على جهاز بناء فيه أدوات 14-dev-tools.sh flutter.
#
# ما يفعله (الطريقة ب):
#   1. يتحقق من Flutter و Java؛
#   2. مفتاح التوقيع: إن لم يوجد apps/mobile/android/key.properties ينشئ مفتاحًا جديدًا (keytool، RSA 4096، 10000 يوم)
#      في KEYSTORE (~/ehimaya-release.jks افتراضيًا) ويكتب key.properties. المفتاح وkey.properties لا يُحفظان في المستودع.
#      ضياع المفتاح يمنع تحديث التطبيق المثبت عند المواطنين: احفظ نسخة منه وكلمة مروره في الخزنة؛
#   3. يقرأ عناوين الخادم من .env (API_HOST و AUTH_HOST) أو من المتغيرين API_BASE_URL و AUTH_BASE_URL؛
#   4. يبني تطبيق المواطن (النكهة citizen) وتطبيق الأعوان (النكهة staff، نقطة الدخول lib/main_staff.dart) بالعناوين نفسها؛
#   5. يضع الملفين في dist/ مع بصمة SHA-256 لكل ملف للتحقق عند التوزيع.
# مفاتيح Firebase (الإشعارات) تُقرأ من FIREBASE_API_KEY و FIREBASE_APP_ID و FIREBASE_STAFF_APP_ID و
# FIREBASE_MESSAGING_SENDER_ID و FIREBASE_PROJECT_ID إن وُجدت؛ دونها يعمل التطبيق دون إشعارات دفع.
# لا يُمرَّر PUSH_SIMULATOR_URL أبدًا في بناء التوزيع (محاكي [SIM]).
#
# الاستعمال: SMS_NUMBER=<رقم البلاغ بالرسائل> scripts/install/13-build-apk.sh
#            API_BASE_URL=https://api.ehimaya.tn AUTH_BASE_URL=https://auth.ehimaya.tn scripts/install/13-build-apk.sh
source "$(dirname "$0")/00-common.sh"

need flutter "14-dev-tools.sh flutter"
need keytool "14-dev-tools.sh flutter"
MOBILE=$ROOT/apps/mobile

step "1/4 العناوين"
API_BASE_URL=${API_BASE_URL:-https://$(env_value API_HOST)}
AUTH_BASE_URL=${AUTH_BASE_URL:-https://$(env_value AUTH_HOST)}
[ "$API_BASE_URL" != https:// ] || die "حدّد API_HOST في .env أو API_BASE_URL"
[ "$AUTH_BASE_URL" != https:// ] || die "حدّد AUTH_HOST في .env أو AUTH_BASE_URL"
echo "  API: $API_BASE_URL   Keycloak: $AUTH_BASE_URL   SMS: ${SMS_NUMBER:-(لا رقم: يختفي زر الرسالة القصيرة)}"

step "2/4 مفتاح التوقيع"
if [ -f "$MOBILE/android/key.properties" ]; then
  ok "key.properties موجود"
else
  KEYSTORE=${KEYSTORE:-$HOME/ehimaya-release.jks}
  read -r -s -p "كلمة مرور جديدة للمفتاح (12 حرفًا أو أكثر): " ks_pass && echo
  [ ${#ks_pass} -ge 12 ] || die "كلمة المرور قصيرة"
  keytool -genkeypair -v -keystore "$KEYSTORE" -keyalg RSA -keysize 4096 -validity 10000 -alias ehimaya \
    -storepass "$ks_pass" -keypass "$ks_pass" -dname "CN=e-Himaya, O=Protection Civile, C=TN"
  (umask 077 && printf 'storeFile=%s\nstorePassword=%s\nkeyAlias=ehimaya\nkeyPassword=%s\n' \
    "$KEYSTORE" "$ks_pass" "$ks_pass" >"$MOBILE/android/key.properties")
  warn "المفتاح في $KEYSTORE: احفظ نسخة منه ومن كلمة مروره في الخزنة الآن"
fi

firebase=(--dart-define=FIREBASE_API_KEY="${FIREBASE_API_KEY:-}"
  --dart-define=FIREBASE_MESSAGING_SENDER_ID="${FIREBASE_MESSAGING_SENDER_ID:-}"
  --dart-define=FIREBASE_PROJECT_ID="${FIREBASE_PROJECT_ID:-}")

step "3/4 البناء"
cd "$MOBILE"
flutter pub get
flutter build apk --release --flavor citizen \
  --dart-define=API_BASE_URL="$API_BASE_URL" \
  --dart-define=TUS_URL="$API_BASE_URL/api/v1/uploads/" \
  --dart-define=OIDC_ISSUER="$AUTH_BASE_URL/realms/ehimaya-public" \
  --dart-define=SMS_REPORT_NUMBER="${SMS_NUMBER:-}" \
  --dart-define=FIREBASE_APP_ID="${FIREBASE_APP_ID:-}" "${firebase[@]}"
flutter build apk --release --flavor staff -t lib/main_staff.dart \
  --dart-define=API_BASE_URL="$API_BASE_URL" \
  --dart-define=STAFF_OIDC_ISSUER="$AUTH_BASE_URL/realms/ehimaya-staff" \
  --dart-define=STAFF_ROOM_PHONE="${STAFF_ROOM_PHONE:-198}" \
  --dart-define=STAFF_SMS_NUMBER="${SMS_NUMBER:-}" \
  --dart-define=FIREBASE_APP_ID="${FIREBASE_STAFF_APP_ID:-}" "${firebase[@]}"

step "4/4 الملفات"
mkdir -p "$ROOT/dist"
version=$(grep -E '^version:' pubspec.yaml | awk '{print $2}')
cp build/app/outputs/flutter-apk/app-citizen-release.apk "$ROOT/dist/e-himaya-citizen-$version.apk"
cp build/app/outputs/flutter-apk/app-staff-release.apk "$ROOT/dist/e-himaya-staff-$version.apk"
(cd "$ROOT/dist" && sha256sum ./*.apk | tee SHA256SUMS)
ok "الملفان في dist/. ثبّت كلًا منهما على هاتف تجربة، ثم أرسل بلاغًا تجريبيًا وتأكد أنه وصل إلى اللوحة"
