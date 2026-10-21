# الإصدارات المثبتة (المراحل 1 إلى 9)

تُحدَّث هذه القائمة مع كل مرحلة. تُعتمد الإصدارات الدقيقة أدناه في الكود والحاويات.

## الحاويات

| المكون | الصورة | الرخصة |
|---|---|---|
| PostgreSQL + PostGIS | `postgres:17-bookworm` + `postgresql-17-postgis-3` + `postgresql-17-pgvector` (PGDG) | PostgreSQL / GPL-2.0 |
| gosu (داخل صورة قاعدة البيانات) | 1.19، يعاد بناؤه بـ `golang:1.26-bookworm` لسد CVE-2025-68121 | Apache-2.0 |
| Valkey | `valkey/valkey:8.1-alpine` | BSD-3 |
| NATS | `nats:2.10-alpine` | Apache-2.0 |
| SeaweedFS (S3) | `chrislusf/seaweedfs:3.97` | Apache-2.0 |
| Keycloak | `keycloak/keycloak:26.3` (اختُبر 26.3.5) | Apache-2.0 |
| رفع الوسائط بالاستئناف (tus) | `tusproject/tusd:v2.8.0` | MIT |
| الخلفية وخدمة الذكاء الاصطناعي | `python:3.12-slim` | PSF |
| خادم النموذج اللغوي المحلي | `ollama/ollama:0.40.1` | MIT |
| التقاط البريد في التطوير (المرحلة 5) | `axllent/mailpit:v1.31.3` | MIT |
| محاكي Firebase وبوابة SMS في التطوير (`services/notify-sim`، **محاكاة**) | `python:3.12-slim` | — |
| الوكيل العكسي و TLS (الإنتاج) وخادم ملفات لوحة التحكم والبوابة (المرحلة 5.5) | `caddy:2.11-alpine` (2.11.7) | Apache-2.0 |
| خادم البث المباشر (المرحلة 6: WHIP/WHEP و RTSP و RTMP و HLS والتسجيل fMP4)، ويستعمله أيضا `stream-sim` | `bluenviron/mediamtx:1.21.2-ffmpeg` | MIT |
| خدمة الرؤية الحاسوبية (`services/vision`، المرحلة 6) | `python:3.12-slim` | PSF |
| المقسم الهاتفي (`services/telephony`، المرحلة 7) | Asterisk 22.11.0 LTS مبني من المصدر (SHA-256 `3bd5ee04…4d94`) مع pjproject 2.17، على `ubuntu:26.04` | GPL-2.0 (عملية مستقلة، تتصل بها الخلفية عبر HTTP و WebSocket فقط) |
| محرك البحث في مكتبة الأحداث (المرحلة 8، ملف `search`؛ دائم في الإنتاج): عقدة واحدة، إضافة الأمان مفعلة، محللا العربية والفرنسية | `opensearchproject/opensearch:2.19.6` (`sha256:be67c71b…80b5`) | Apache-2.0 |
| محرك التوجيه (المرحلة 7، ملف `routing`) | `ghcr.io/valhalla/valhalla:3.9.1` على خريطة OpenStreetMap لتونس (Geofabrik) | MIT / البيانات ODbL 1.0 |
| بناء لوحة التحكم والبوابة (مرحلة البناء فقط) | `node:22-alpine` | MIT |
| تثبيت حزم Python من `uv.lock` (مرحلة البناء فقط) | `ghcr.io/astral-sh/uv:0.11.32` | MIT / Apache-2.0 |
| اختبار الحمل (خارج المنظومة) | `grafana/k6:2.3.0` | AGPL-3.0 |
| فحص الثغرات في CI | `aquasecurity/trivy-action` 0.35.0 | Apache-2.0 |

منذ المرحلة 5.5 كل صورة مثبتة بالبصمة في الـ Dockerfile وملفات compose (`image:tag@sha256:…`، الوسم للقراءة فقط)،
و Dependabot يقترح التحديثات أسبوعيًا (`.github/dependabot.yml`).

## حزم Python (الخلفية)

مثبتة في `services/api/pyproject.toml`، وشجرة التبعيات كاملة في `services/api/uv.lock`.

| الحزمة | الإصدار |
|---|---|
| fastapi | 0.146.0 |
| uvicorn | 0.54.0 |
| sqlalchemy | 2.1.5 |
| asyncpg | 0.32.0 |
| alembic | 1.20.0 |
| pydantic-settings | 2.16.0 |
| geoalchemy2 | 0.20.0 |
| pgvector | 0.5.1 |
| pyjwt | 2.15.1 |
| redis | 8.1.0 |
| nats-py | 2.16.0 |
| structlog | 26.1.0 |
| prometheus-client (المرحلة 5.5، نقطة `/metrics`) | 0.26.0 |
| boto3 (S3) | 1.43.114 |
| cryptography (AES-256-GCM، توقيع الشهادات Ed25519) | 50.0.2 |
| weasyprint (شهادة السلامة PDF، المرحلة 4؛ تحتاج pango و harfbuzz و fonts-noto-core في الصورة) | 70.0 |
| segno (رمز QR للتحقق من الشهادة) | 1.6.6 |
| openpyxl (تصدير XLSX لمستودع التقارير، المرحلة 8؛ MIT) | 3.1.5 |
| email-validator (عناوين البريد في بطاقة المؤسسة والدعوات) | 2.3.0 |
| pytest / pytest-asyncio | 9.1.1 / 1.4.0 |
| ruff / mypy | 0.17.1 / 2.4.0 |

### قنوات الإشعار (المرحلة 5)

لا حزمة جديدة: الدفع عبر واجهة FCM HTTP v1 باستعمال httpx و pyjwt (توقيع RS256 لحساب الخدمة)، والبريد عبر
`smtplib` من مكتبة Python القياسية، والرسائل القصيرة عبر بوابة HTTP لمزود تونسي (`SMS_HTTP_URL`). كل قناة اختيارية:
دون إعداداتها تُسجَّل عمليات الإرسال «متجاوزة» وتواصل القنوات الأخرى.

**محاكي القنوات (`services/notify-sim`، للتطوير والاختبار فقط):** يحاكي FCM HTTP v1 (مع مصادقة حساب الخدمة) وبوابة
SMS، ويعرض ما يستقبله في صندوق على المنفذ 8090. حزمه بالإصدارات نفسها المعتمدة في الخلفية: fastapi 0.146.0،
uvicorn 0.54.0، pydantic-settings 2.16.0، pyjwt 2.15.1، cryptography 50.0.2، وللاختبار httpx 0.28.1، pytest 9.1.1،
ruff 0.17.1، mypy 2.4.0. التحويل إلى الإرسال الحقيقي موثق في `docs/api/notify-sim.md`.

## طبقة الذكاء الاصطناعي 1 (`services/ai`، المرحلة 3)

كل النماذج تعمل على خوادمنا ولا تُرسل أي معطيات إلى خدمة خارجية (NFR-10، NFR-11). سكربت
`services/ai/models/fetch_models.py` ينزّل النماذج ويحوّلها ويتحقق من صحتها، ويرفض أي نموذج رخصته غير متساهلة.

| القدرة | النموذج (prod، خادم GPU) | النموذج (cpu) | النموذج (ci) | الرخصة | المصدر |
|---|---|---|---|---|---|
| تحويل الصوت إلى نص | Whisper large-v3 (`Systran/faster-whisper-large-v3`) | Whisper medium | Whisper small | MIT | <https://huggingface.co/Systran> |
| الترجمة fr→ar و en→ar | Opus-MT (`Helsinki-NLP/opus-mt-fr-ar`، `opus-mt-en-ar`) | نفسه | نفسه | Apache-2.0 / CC-BY-4.0 | <https://huggingface.co/Helsinki-NLP> |
| التضمين الدلالي (768 بعدا) | `intfloat/multilingual-e5-base` | نفسه | نفسه | MIT | <https://huggingface.co/intfloat/multilingual-e5-base> |
| القراءة المهيكلة للبلاغ | Qwen3 8B (`qwen3:8b`) | Qwen3 4B | Qwen3 1.7B | Apache-2.0 | <https://ollama.com/library/qwen3> |

حزم Python للخدمة، مثبتة في `services/ai/pyproject.toml` و `uv.lock`:

| الحزمة | الإصدار | الدور |
|---|---|---|
| faster-whisper | 1.2.1 | تحويل الصوت (مع كشف الصمت VAD) |
| PyAV (av) | 17.0.0 | فك ترميز الصوت لـ faster-whisper (الإصدار 19 أزال معاملا يستعمله faster-whisper 1.2.1) |
| ctranslate2 | 4.8.3 | تشغيل Whisper و Opus-MT و e5 بسرعة على المعالج أو GPU |
| sentencepiece / tokenizers | 0.2.2 / 0.23.3 | تقطيع النصوص |
| numpy | 2.5.4 | تجميع المتجهات |
| تحويل النماذج فقط: transformers / torch (CPU) / huggingface-hub | 5.20.1 / 2.14.1 / 2.2.0 | لا تُثبت في صورة التشغيل |
| خادم GPU فقط: nvidia-cublas-cu12 / nvidia-cudnn-cu12 | 12.9.2.10 / 9.27.0.42 | مكتبات CUDA لـ CTranslate2 |

## الرؤية الحاسوبية (`services/vision`، المرحلة 6)

كشف الحرائق والدخان والأشخاص في الصور وفي إطارات البث، على المعالج ودون أي خدمة خارجية. لا شيفرة AGPL: المعالجة
(letterbox وفك YOLOX و NMS) مكتوبة في الخدمة، والتشغيل عبر ONNX Runtime. التفاصيل والدقة المقاسة في
`services/vision/README.md` و `services/vision/EVALUATION.md`.

| النموذج | الإصدار | الرخصة | المصدر |
|---|---|---|---|
| `ehimaya-fire-smoke-yolox-tiny` (حريق ودخان، مدرّب للمشروع) | 2.0.0، SHA-256 `3b9f2b5f…39b6` | Apache-2.0 | YOLOX-Tiny (Megvii، Apache-2.0) مضبوط على صور Open Images V7 (CC BY 2.0، التسميات CC BY 4.0) وFireNET (MIT) وFURG fire dataset (CC0-1.0)، وصناديق الدخان الإضافية رسمها Grounding DINO (Apache-2.0) أثناء التدريب فقط |
| `yolox-tiny-coco-person` (أشخاص) | 0.1.1rc0، SHA-256 `427cc366…b0f7` | Apache-2.0 | <https://github.com/Megvii-BaseDetection/YOLOX> |

| الحزمة | الإصدار |
|---|---|
| onnxruntime | 1.30.0 |
| PyAV (av)، قراءة RTSP | 19.0.1 |
| numpy / pillow | 2.5.4 / 12.3.0 |
| fastapi / uvicorn / pydantic-settings / python-multipart | 0.146.0 / 0.54.0 / 2.16.0 / 0.0.32 |
| httpx / structlog / prometheus-client | 0.28.1 / 26.1.0 / 0.26.0 |
| التدريب فقط: torch (CPU) / torchvision / transformers | 2.14.1 / 0.29.1 / 4.57.1 |

مقطع المحاكاة لـ `stream-sim`: `intel-iot-devkit/sample-videos/people-detection.mp4` (CC-BY-4.0، SHA-256
`18ffe867…f693`)، يُنزّل عند التشغيل ولا يُحفظ في المستودع.

## الطقس والتنبؤ والاتصالات (المرحلة 7)

لا حزمة Python جديدة للطقس والتنبؤ: مؤشر خطر الحرائق الكندي FWI ونموذج Rothermel لانتشار الحريق وقارئ نموذج
التضاريس مكتوبة داخل المشروع. الاتصال بـ Asterisk عبر websockets 17.2 (BSD-3-Clause، صارت تبعية مباشرة).

| المصدر | الاستعمال | الرخصة |
|---|---|---|
| Open-Meteo (`api.open-meteo.com`) | الطقس الحالي وتوقعات 48 ساعة على شبكة 285 نقطة | البيانات CC BY 4.0؛ الواجهة المجانية للاستعمال غير التجاري (10 آلاف طلب يوميا، نستعمل نحو 6840)؛ الخادم نفسه AGPL-3.0 ويُستضاف محليا عند الحاجة ويُستدعى عبر HTTP فقط |
| Copernicus DEM GLO-90 | الانحدار واتجاه الجريان (40 مربعا مثبتة بالبصمة، نحو 115 ميغابايت في حجم مستقل) | ترخيص Copernicus DEM المجاني والمفتوح، مع إشعار DLR/Airbus |
| OpenStreetMap (Geofabrik، تونس) | التوجيه عبر Valhalla | ODbL 1.0، مع ذكر المساهمين |

## تطبيق الهاتف (`apps/mobile`)

Flutter 3.47.7 (القناة المستقرة) مع Dart 3.13.5، و Java 17 لبناء أندرويد. التثبيت: <https://docs.flutter.dev/get-started/install>.
الحزم مثبتة بإصدارات دقيقة في `apps/mobile/pubspec.yaml` و `pubspec.lock`.

| الحزمة | الإصدار | الدور |
|---|---|---|
| flutter_riverpod / go_router | 3.4.3 / 18.1.0 | الحالة والتنقل |
| dio | 5.11.1 | الاتصال بالخلفية وعميل tus |
| drift / sqlite3 (SQLCipher) | 2.35.2 / 3.7.1 | قاعدة محلية مشفرة للعمل دون اتصال |
| flutter_appauth / flutter_secure_storage | 12.1.0 / 11.2.0 | الدخول (PKCE) وحفظ الرموز والمفاتيح |
| geolocator / flutter_map | 14.0.1 / 8.3.2 | الموقع والخريطة |
| image_picker / record / just_audio | 1.2.4 / 7.1.2 / 0.10.6 | الصور والفيديو والتسجيل الصوتي |
| url_launcher | 6.3.3 | الاتصال بأرقام النجدة عبر الشريحة (السيناريو 0) |
| connectivity_plus / crypto / uuid | 7.3.2 / 3.0.7 / 4.6.0 | المزامنة، البصمة، معرف البلاغ |
| firebase_core / firebase_messaging (المرحلة 5) | 4.15.0 / 16.7.0 | إشعارات الدفع عبر FCM؛ اختيارية عبر `--dart-define` (FIREBASE_API_KEY، FIREBASE_APP_ID، FIREBASE_MESSAGING_SENDER_ID، FIREBASE_PROJECT_ID) |
| flutter_local_notifications (المرحلة 5) | 22.3.1 | قناتا أندرويد `ehimaya_alerts` و `ehimaya_default` وعرض الإشعار والتطبيق مفتوح |
| desugar_jdk_libs (Gradle، المرحلة 5) | 2.1.4 | تتطلبه مكتبة الإشعارات المحلية |
| flutter_webrtc (المرحلة 6) | 1.6.2+hotfix.3 | البث المباشر عبر WHIP (MIT؛ مكتبة WebRTC الأصلية 150.7871.01) |
| open_filex (المرحلة 8) | 4.7.0 | فتح شهادة المكافآت (PDF) في عارض الهاتف عبر FileProvider (BSD-3-Clause)؛ أذونات قراءة الوسائط التي يعلنها محذوفة من بيان التطبيق |

## لوحة التحكم (`apps/dashboard`)

Node.js 22 LTS و npm 10 أو أحدث. الحزم مثبتة بإصدارات دقيقة في `package.json` و `package-lock.json` (`npm ci`).

| الحزمة | الإصدار |
|---|---|
| react / react-dom | 19.3.0 |
| react-router | 8.4.0 |
| @tanstack/react-query | 5.104.1 |
| oidc-client-ts | 3.5.0 |
| i18next / react-i18next | 26.4.2 / 17.0.15 |
| maplibre-gl | 6.12.0 |
| vite / @vitejs/plugin-react | 8.3.4 / 6.1.2 |
| typescript / typescript-eslint | 5.9.3 / 8.71.0 |
| vitest / eslint | 5.0.5 / 10.12.0 |
| @playwright/test (اختبار المتصفح) | 1.56.1 |
| jssip (المرحلة 7، الهاتف الشبكي للمشغل، يُحمّل عند تفعيله فقط) | 3.13.8 (MIT) |
| hls.js (المرحلة 6، بديل HLS عند تعذر WHEP، يُحمّل عند الحاجة فقط) | 1.7.3 (Apache-2.0) |
| uplot (المرحلة 8، رسوم التحليلات على canvas، تُحمّل عند الحاجة فقط) | 1.6.32 (MIT) |
| markdown-it (المرحلة 8، عرض Markdown للذاكرة الوطنية، `html: false`) | 15.0.3 (MIT، يعالج GHSA-gfr2-rv44-r23c وGHSA-vfgh-jcmw-g37q) |
| dompurify (المرحلة 8، تعقيم HTML الناتج قبل عرضه) | 3.4.16 (MPL-2.0 OR Apache-2.0، مستعملة بترخيص Apache-2.0) |

> المرحلة 9: بقيت typescript على 5.9.3 لأن typescript-eslint 8 لا يدعم TypeScript 7 بعد؛ و Vite 8 (Rolldown) يقبل
> `manualChunks` في صيغة الدالة فقط. اللوحة بثلاث لغات: العربية (من اليمين إلى اليسار) والفرنسية والإنجليزية.

## بوابة المؤسسات (`apps/portal`)

نفس أدوات لوحة التحكم (Node.js 22 و npm 10 أو أحدث، `npm ci`)، بثلاث لغات (ar/fr/en) وعلى المنفذ 5174.
الحزم مثبتة بإصدارات دقيقة في `apps/portal/package.json` و `package-lock.json`؛ الإصدارات نفسها المعتمدة في لوحة التحكم
(react 19.3.0، react-router 8.4.0، react-query 5.104.1، oidc-client-ts 3.5.0، i18next 26.4.2، maplibre-gl 6.12.0،
vite 8.3.4، typescript 5.9.3، vitest 5.0.5، eslint 10.12.0). البصمة SHA-256 تُحسب في المتصفح (WebCrypto) ولا يغادر
الملف جهاز الزائر عند التحقق من شهادة.

> رُقّيت `maplibre-gl` من 5.24.0 إلى 6.12.0 في اللوحة والبوابة لإزالة التنبيه الأمني GHSA-jrc7-96c5-q579
> (يشمل الإصدارات حتى 6.4.0)؛ `npm audit` نظيف في التطبيقين.

## المرحلة 9 (فصل الصلاحيات المركزية والجهوية)

لا حزمة جديدة. أمن مستوى الصفوف (Row-Level Security) من PostgreSQL 17 نفسه (الترحيل `0025_rls_policies`)، ودور
التشغيل `ehimaya_app` بلا `BYPASSRLS`؛ إدارة الحسابات الجهوية عبر واجهة Keycloak 26.3 الإدارية الموجودة.

## أولوية التنصيب

1. Docker Engine 27+ مع Compose v2 (البنية كاملة بأمر واحد).
2. Python 3.12 و uv (تطوير الخلفية).
3. Node.js 22 (لوحة التحكم).
4. Flutter 3.47.7 و Android Studio أو Xcode (تطبيق الهاتف).
5. طبقة الذكاء الاصطناعي: `docker compose ... --profile ai up -d` (ينزّل النماذج مرة واحدة، حوالي 6 غيغابايت في ملف cpu).
   على خادم GPU: مشغّل NVIDIA و NVIDIA Container Toolkit، ثم إضافة `-f infra/compose.gpu.yml`.
