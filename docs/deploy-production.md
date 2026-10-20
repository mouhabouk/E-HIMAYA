# دليل النشر في الإنتاج (المرحلة 5.5)

يشرح هذا الدليل تشغيل ء-حماية على خادم إنتاج بالملف الإضافي `infra/compose.prod.yml` فوق `infra/compose.yml`.
الملف الإضافي لا يغيّر بيئة التطوير: من دونه يبقى كل شيء كما كان.

## 1. ما يضيفه الملف الإضافي

| المجال | التطوير (`compose.yml`) | الإنتاج (`+ compose.prod.yml`) |
|---|---|---|
| المدخل | منافذ كل خدمة على `127.0.0.1` | **Caddy** وحده على 80 و 443 (TLS، HTTP/3)، ولا منفذ آخر على الخادم |
| TLS | لا يوجد | شهادات ACME (Let's Encrypt/ZeroSSL) لأسماء حقيقية، أو `tls internal` للعرض |
| Keycloak | `start-dev` | `start` مع `KC_HOSTNAME=https://AUTH_HOST`، `KC_PROXY_HEADERS=xforwarded`، فحص `/health/ready` على منفذ الإدارة 9000 |
| الواجهة البرمجية | حاوية واحدة `PROCESS_ROLE=all` | `api` (طلبات HTTP فقط، `WEB_CONCURRENCY=4`) + `worker` واحد (الحلقات الخلفية)، `APP_ENV=production` |
| لوحة التحكم والبوابة | `npm run dev` | صورتان ثابتتان (Caddy غير مميَّز، CSP مولَّدة من الإعداد) |
| قاعدة البيانات | دوران: المالك يرحّل، `ehimaya_app` يشغّل | نفس الشيء، وكلمة مرور دور التشغيل إلزامية |
| أدوات التطوير | mailpit و notify-sim | غير مشغّلة (ملف التعريف `dev-tools`) |

`APP_ENV=production` في الواجهة البرمجية: لا `/docs` ولا `/redoc` ولا `/openapi.json`، ورأس HSTS، ورفض الإقلاع إذا كان
أي سر (كل إعداد من نوع SecretStr، وكلمات المرور داخل `DATABASE_URL` و `VALKEY_URL` و `NATS_URL`) ما زال قيمة مثال
(«change-me»…) أو أقصر من 16 حرفًا أو قليل العشوائية. رسالة الخطأ تسمّي الإعداد ولا تطبع قيمته أبدًا.

## 2. المتطلبات

- خادم Linux بـ Docker Engine 27+ و Docker Compose 2.24+ (لـ `!reset` و `!override`). القياس في
  `infra/loadtest/RESULTS.md` تم على 4 vCPU و 15 GiB لكل المنظومة.
- خمسة أسماء DNS تشير إلى الخادم، مثلًا: `api.ehimaya.tn`، `dashboard.ehimaya.tn`، `portal.ehimaya.tn`،
  `auth.ehimaya.tn`، `media.ehimaya.tn`.
- جدار ناري: 80/tcp و 443/tcp و 443/udp من الإنترنت، و 8189/udp لوسائط WebRTC (البث المباشر)، و 8554/tcp
  (RTSP) و 1935/tcp (RTMP) من شبكات الطائرات المسيّرة والكاميرات فقط (و SSH من شبكة الإدارة). انظر `docs/streaming.md`.

## 3. الإعداد (`.env`)

انسخ `.env.example` إلى `.env` ثم:

```bash
# كل كلمة مرور وكل سر: قيمة عشوائية جديدة (لا تُعاد أبدًا قيمة من .env.example)
for v in POSTGRES_PASSWORD EHIMAYA_DB_PASSWORD EHIMAYA_DB_RUNTIME_PASSWORD KEYCLOAK_DB_PASSWORD KEYCLOAK_ADMIN_PASSWORD \
         VALKEY_PASSWORD NATS_APP_PASSWORD S3_SECRET_KEY TUSD_HOOK_SECRET AI_SERVICE_TOKEN METRICS_TOKEN \
         MEDIAMTX_HOOK_TOKEN MEDIAMTX_API_PASSWORD VISION_API_TOKEN VISION_CALLBACK_TOKEN VISION_READ_PASSWORD; do
  sed -i "s|^$v=.*|$v=$(openssl rand -hex 24)|" .env
done
sed -i "s|^ANON_PSEUDONYM_SECRET=.*|ANON_PSEUDONYM_SECRET=$(openssl rand -hex 32)|" .env
sed -i "s|^FIELD_ENCRYPTION_KEY=.*|FIELD_ENCRYPTION_KEY=$(openssl rand -base64 32)|" .env
sed -i "s|^CERTIFICATE_SIGNING_KEY=.*|CERTIFICATE_SIGNING_KEY=$(openssl rand -base64 32)|" .env
# المحاكاة ممنوعة في الإنتاج (الـ API يرفض الإقلاع بها)
sed -i "s|^STREAM_SIM_TOKEN=.*|STREAM_SIM_TOKEN=|" .env
```

ثم أضف:

```dotenv
API_HOST=api.ehimaya.tn
DASHBOARD_HOST=dashboard.ehimaya.tn
PORTAL_HOST=portal.ehimaya.tn
AUTH_HOST=auth.ehimaya.tn
MEDIA_HOST=media.ehimaya.tn
# بريد حساب ACME (شهادات عامة). للعرض بلا أسماء حقيقية: CADDY_TLS=internal
CADDY_TLS=ops@ehimaya.tn
# الأصول المسموح لها برفع الملفات عبر tusd (النقاط مهرَّبة)
TUSD_CORS_ORIGIN_REGEX=^https://(dashboard|portal)\.ehimaya\.tn$
# من يفتح واجهة إدارة Keycloak (CIDR، مفصولة بمسافة). الافتراضي: الشبكات الخاصة فقط
KEYCLOAK_ADMIN_ALLOW=10.20.0.0/16
# بريد الإنتاج والقنوات الحقيقية (فارغة = القناة «متجاوزة»)
SMTP_HOST=smtp.provider.tn
SMTP_USERNAME=...
SMTP_PASSWORD=...
FCM_SERVICE_ACCOUNT=<base64 -w0 لمفتاح حساب الخدمة من Firebase>
SMS_HTTP_URL=https://sms.provider.tn/send
SMS_HTTP_TOKEN=...
# اختياري: نمط خرائط خاص بدل OpenStreetMap، وأصول بلاطاته وخطوطه للـ CSP
# MAP_STYLE_URL=https://tiles.ehimaya.tn/style.json
# CSP_MAP_SRC=https://tiles.ehimaya.tn
```

`KEYCLOAK_HOSTNAME` و `S3_PUBLIC_ENDPOINT_URL` و `PORTAL_PUBLIC_URL` و `API_CORS_ORIGINS` تُشتق من هذه الأسماء في الملف
الإضافي، فلا تُكتب يدويًا.

**Keycloak:** في الفضاءين `ehimaya-staff` و `ehimaya-public` حدّث عناوين إعادة التوجيه (Valid redirect URIs) و Web
origins للعملاء `ehimaya-dashboard` و `ehimaya-portal` إلى `https://DASHBOARD_HOST/*` و `https://PORTAL_HOST/*`،
وعميل التطبيق إلى مخطط التطبيق. الاستيراد (`--import-realm`) لا يكتب فوق فضاء موجود.

## 4. التشغيل

```bash
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml up -d --build --wait
```

ترتيب الإقلاع: `postgres` ← `db-roles` (ينشئ دور التشغيل أو يحدّثه، متساوي القوة) ← `migrate` (ترحيلات Alembic بحساب
المالك ثم صلاحيات دور التشغيل) ← `api` و `worker` ← `caddy`. الواجهة لا ترحّل عند إقلاعها (`RUN_MIGRATIONS=0` افتراضيًا
في الصورة)، ودورها لا يملك أي جدول.

### فحوص بعد النشر

```bash
curl -fsS https://api.ehimaya.tn/health/ready          # 200، "status": "ok" (أو "degraded" إن تعطل Valkey/NATS)
curl -s -o /dev/null -w '%{http_code}\n' https://api.ehimaya.tn/docs        # 404
curl -s -o /dev/null -w '%{http_code}\n' https://api.ehimaya.tn/metrics     # 404 من الخارج
curl -sI https://dashboard.ehimaya.tn/ | grep -iE 'strict-transport|content-security'
API_URL=https://api.ehimaya.tn TUS_URL=https://api.ehimaya.tn/api/v1/uploads/ NOTIFY_SIM_URL= \
  python3 infra/smoke/smoke_test.py                     # بلاغ مجهول + رفع بالاستئناف + تحقق السلامة
```

بـ `CADDY_TLS=internal` تأتي الشهادات من سلطة Caddy المحلية: استخرج جذرها
(`docker compose ... cp caddy:/data/caddy/pki/authorities/local/root.crt .`) وثبّته على أجهزة العرض.

## 5. الأمن التشغيلي

- **رؤوس الأمان:** Caddy يضيف HSTS لكل الأسماء. لوحة التحكم والبوابة تحملان CSP محسوبة عند بناء الصورة من القيم نفسها
  التي بُني بها الكود (`infra/web/csp.mjs`): `script-src 'self'` مع بصمة السكربت المضمّن فقط، الواجهة البرمجية
  (https و wss)، مُصدر Keycloak، tusd، البلاطات، ومخزن الوسائط؛ `frame-ancestors 'none'`، `Permissions-Policy`،
  `Referrer-Policy`. الواجهة البرمجية ترسل `default-src 'none'; frame-ancestors 'none'`. مخزن الوسائط يُخدم بـ
  `sandbox` و `nosniff` ويرفض كل طريقة غير GET/HEAD.
- **مسارات داخلية:** Caddy يعيد 404 لـ `/internal/*` (خطافات tusd) و `/metrics`. يُجمع `/metrics` من الشبكة الداخلية
  بالرمز `METRICS_TOKEN` (من `api:8000` و `worker:8000`).
- **tusd:** سر الخطاف في عنوان الخطاف (`http://tusd:<secret>@api:8000/...`) على الشبكة الداخلية فقط، لكن tusd 2.8
  يطبع هذا العنوان في سجل الإقلاع: **سجلات حاوية tusd سرية** (لا تُرسل إلى خدمة سجلات خارجية دون حجب)، ويُغيَّر
  `TUSD_HOOK_SECRET` إذا تسرّب سجل.
- **العناوين الحقيقية للعملاء:** `FORWARDED_ALLOW_IPS` يثق بعنوان Caddy الثابت فقط (`EDGE_PROXY_IP`، افتراضيًا
  172.31.250.10 في الشبكة 172.31.250.0/24)، فحدود الطلبات لكل عنوان (A1) ترى عنوان العميل الحقيقي.
- **قاعدة البيانات:** دور التشغيل `ehimaya_app`: SELECT/INSERT/UPDATE/DELETE على جداول التطبيق، و SELECT/INSERT فقط على
  `audit.log`؛ لا TRUNCATE، لا ALTER، لا DISABLE TRIGGER (`services/api/tests/test_db_roles.py`). جداول الترحيلات
  المقبلة تأخذ الصلاحيات نفسها (ALTER DEFAULT PRIVILEGES، وإعادة المنح بعد كل ترحيل).

## 6. الترقية

```bash
git pull
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml build
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml run --rm migrate   # اختياري: الترحيل وحده أولًا
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml up -d --wait
```

الصور الأساسية وصور الخدمات مثبتة بالبصمة (`image:tag@sha256:…`)؛ Dependabot (`.github/dependabot.yml`) يقترح
التحديثات أسبوعيًا، وكل تحديث يمر بفحص Trivy في CI (يفشل عند ثغرة CRITICAL لها إصلاح).

### مجلد بيانات أُنشئ قبل المرحلة 5.5

لا يلزم أي تدخل: الخدمة `db-roles` تنشئ دور التشغيل في قاعدة موجودة، و `migrate` يمنحه الصلاحيات. إن أردت ذلك يدويًا:

```bash
docker compose --env-file .env -f infra/compose.yml up -d postgres
docker compose --env-file .env -f infra/compose.yml run --rm db-roles
docker compose --env-file .env -f infra/compose.yml run --rm migrate
```

وفي التطوير يبقى الحل الأبسط إعادة إنشاء المجلد: `docker compose ... down -v` (يحذف كل البيانات المحلية).

## 7. النسخ الاحتياطي والرجوع

- قاعدة البيانات: `docker compose ... exec -T postgres pg_dump -U postgres -Fc ehimaya > ehimaya-$(date +%F).dump`
  (و `keycloak` بالطريقة نفسها)، ومجلد `s3data` للوسائط. احفظ `FIELD_ENCRYPTION_KEY*` و `CERTIFICATE_SIGNING_KEY`
  و `ANON_PSEUDONYM_SECRET` خارج الخادم: بدونها تصبح البيانات المشفرة والشهادات والأسماء المستعارة غير قابلة للاستعمال.
- الرجوع إلى إصدار سابق: `git checkout <tag>` ثم البناء والتشغيل. ترحيلات Alembic قابلة للتراجع
  (`docker compose ... run --rm migrate alembic downgrade <revision>`) لكن جرّب ذلك على نسخة قبل الإنتاج.

## 8. السعة

اختبار الحمل (`infra/loadtest/`): على 4 vCPU تستوعب المنظومة بتشكيل الإنتاج ~16 بلاغ SOS/ث (≈ 58 000/ساعة) مع
p95 = 328 ms. للتوسع: `API_WORKERS` (عمليات لكل حاوية)، ثم حاويات `api` إضافية، ثم قاعدة البيانات على خادمها. يبقى
`worker` نسخة واحدة.

## 9. الهاتف والرسائل القصيرة (المرحلة 7)

التفاصيل في `docs/telephony.md`. ما يضيفه الملف الإضافي:

| المجال | التطوير | الإنتاج |
|---|---|---|
| Asterisk 22 | منافذ SIP و ARI على `127.0.0.1` | SIP على 5060/udp و 5060/tcp و 5061/tcp، ونطاق RTP (افتراضيًا 10000–10099/udp)؛ ARI داخلي فقط |
| الهاتف في اللوحة | `ws://localhost:8088/ws` | `wss://API_HOST/telephony/ws` عبر Caddy (هذا المسار وحده من Asterisk)، و `CSP_TELEPHONY_SRC` و `CSP_MICROPHONE=self` في صورة اللوحة |
| تسجيل المكالمات | مفعّل | **معطّل افتراضيًا** (`TELEPHONY_RECORDING_ENABLED=false`) إلى أن يُصرَّح بالمعالجة لدى الهيئة الوطنية لحماية المعطيات الشخصية |
| محاكي المكالمات `call-sim` | ملف التعريف `sim` | غير مشغّل (`dev-tools`) |
| بوابة الرسائل القصيرة | — | `POST https://API_HOST/internal/sms/inbound` موقّع بـ `SMS_INBOUND_SECRET` (المسار الوحيد من `/internal` المفتوح في Caddy) |

- جدار ناري: افتح نطاق RTP بـ UDP، وقيّد 5060 و 5061 بعناوين SBC المشغّل فقط.
- أسرار جديدة في `.env`: `TELEPHONY_ARI_PASSWORD` (`openssl rand -hex 24`)، و `SMS_INBOUND_SECRET`
  (`openssl rand -hex 32`، يُسلَّم لمزوّد الرسائل)، وإعدادات `TELEPHONY_TRUNK_*` من عقد المشغّل، و `TELEPHONY_EXTERNAL_HOST`
  إذا لم يكن `API_HOST` هو العنوان العمومي للخادم. اترك `TELEPHONY_SIM_PASSWORD` و `TELEPHONY_SIM_TOKEN` فارغين.
- كل مكالمة إلى 8000 تسمع إشعار التسجيل بالعربية ثم بالفرنسية قبل التسجيل والطابور؛ استبدل الملفات المولّدة بتسجيلات
  احترافية كما في `docs/telephony.md` (الفقرة 3).
- التحويل إلى 198 (السيناريو 2) يبقى معطّلًا (`TELEPHONY_TRANSFER_198_ENABLED=false`) إلى حين توقيع اتفاقية مع المشغّل
  والحماية المدنية ومراجعة تنظيمية. أرقام النجدة في التطبيق تبقى دائمًا مكالمة عادية عبر الشريحة (السيناريو 0).
- فحص بعد النشر:

  ```bash
  docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml exec telephony \
    asterisk -C /run/asterisk/etc/asterisk.conf -rx "core show version"
  docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml logs worker | grep telephony.ari_connected
  ```
