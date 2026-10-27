# الإصدارات المثبتة (المراحل 1 إلى 10 والمراحل A و B1 و B2 و C1-a و C1-b و C1-c و UI-2 و P2a و P2b و P3a و P3b و P3c و P5a و P5b و P4a و P4b و P4c)

تُحدَّث هذه القائمة مع كل مرحلة. تُعتمد الإصدارات الدقيقة أدناه في الكود والحاويات.

## الحاويات

| المكون | الصورة | الرخصة |
|---|---|---|
| PostgreSQL + PostGIS | `postgres:17-bookworm` + `postgresql-17-postgis-3` + `postgresql-17-pgvector` (PGDG) | PostgreSQL / GPL-2.0 |
| gosu (داخل صورة قاعدة البيانات) | 1.19، يعاد بناؤه بـ `golang:1.27-bookworm` لسد CVE-2025-68121 | Apache-2.0 |
| Valkey | `valkey/valkey:9.1-alpine` | BSD-3 |
| NATS | `nats:2.15-alpine` | Apache-2.0 |
| SeaweedFS (S3) | `chrislusf/seaweedfs:4.48` | Apache-2.0 |
| Keycloak | `keycloak/keycloak:26.8` (اختُبر 26.8؛ المرحلة 10: انتقل التحقق في CI وci-local من 26.3 إلى 26.8 بعد دمج Dependabot #56) | Apache-2.0 |
| رفع الوسائط بالاستئناف (tus) | `tusproject/tusd:v2.10.1` | MIT |
| الخلفية وخدمة الذكاء الاصطناعي | `python:3.12-slim` | PSF |
| خادم النموذج اللغوي المحلي | `ollama/ollama:0.40.6` | MIT |
| التقاط البريد في التطوير (المرحلة 5) | `axllent/mailpit:v1.31.6` | MIT |
| محاكي Firebase وبوابة SMS في التطوير (`services/notify-sim`، **محاكاة**) | `python:3.12-slim` | — |
| الوكيل العكسي و TLS (الإنتاج) وخادم ملفات لوحة التحكم والبوابة (المرحلة 5.5) | `caddy:2.11-alpine` (2.11.7) | Apache-2.0 |
| خادم البث المباشر (المرحلة 6: WHIP/WHEP و RTSP و RTMP و HLS والتسجيل fMP4)، ويستعمله أيضا `stream-sim` | `bluenviron/mediamtx:1.21.2-ffmpeg` | MIT |
| خدمة الرؤية الحاسوبية (`services/vision`، المرحلة 6) | `python:3.12-slim` | PSF |
| المقسم الهاتفي (`services/telephony`، المرحلة 7) | Asterisk 22.11.0 LTS مبني من المصدر (SHA-256 `3bd5ee04…4d94`) مع pjproject 2.17، على `ubuntu:26.04` | GPL-2.0 (عملية مستقلة، تتصل بها الخلفية عبر HTTP و WebSocket فقط) |
| محرك البحث في مكتبة الأحداث (المرحلة 8، ملف `search`؛ دائم في الإنتاج): عقدة واحدة، إضافة الأمان مفعلة، محللا العربية والفرنسية | `opensearchproject/opensearch:2.19.6` (`sha256:be67c71b…80b5`) | Apache-2.0 |
| محرك التوجيه (المرحلة 7، ملف `routing`) | `ghcr.io/valhalla/valhalla:3.9.1` على خريطة OpenStreetMap لتونس (Geofabrik) | MIT / البيانات ODbL 1.0 |
| بناء لوحة التحكم والبوابة (مرحلة البناء فقط) | `node:22-alpine` | MIT |
| تثبيت حزم Python من `uv.lock` (مرحلة البناء فقط) | `ghcr.io/astral-sh/uv:0.13.4` | MIT / Apache-2.0 |
| اختبار الحمل (خارج المنظومة) | `grafana/k6:2.3.0` | AGPL-3.0 |
| فحص الثغرات في CI | `aquasecurity/trivy-action` 0.36.0 | Apache-2.0 |
| المراقبة (المرحلة 10، ملف `monitoring` في الإنتاج) | `prom/prometheus:v3.5.0` و `prom/alertmanager:v0.28.1` و `prom/node-exporter:v1.9.1` (مقاييس النسخ الاحتياطي)، مثبتة بالبصمة | Apache-2.0 |
| فحص الأمان الديناميكي (المرحلة 10، يدوي قبل الإصدار) | `ghcr.io/zaproxy/zaproxy:2.16.1` (يمكن تغييرها بـ `ZAP_IMAGE`، انظر `infra/security/zap/run.sh`) | Apache-2.0 |

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
| firebase_core / firebase_messaging (المرحلة 5) | 5.0.0 / 17.0.0 | إشعارات الدفع عبر FCM؛ اختيارية عبر `--dart-define` (FIREBASE_API_KEY، FIREBASE_APP_ID، FIREBASE_MESSAGING_SENDER_ID، FIREBASE_PROJECT_ID) |
| flutter_local_notifications (المرحلة 5) | 22.3.1 | قناتا أندرويد `ehimaya_alerts` و `ehimaya_default` وعرض الإشعار والتطبيق مفتوح |
| desugar_jdk_libs (Gradle، المرحلة 5) | 2.1.4 | تتطلبه مكتبة الإشعارات المحلية |
| flutter_webrtc (المرحلة 6) | 1.6.2+hotfix.3 | البث المباشر عبر WHIP (MIT؛ مكتبة WebRTC الأصلية 150.7871.01) |
| open_filex (المرحلة 8) | 5.0.0 | فتح شهادة المكافآت (PDF) في عارض الهاتف عبر FileProvider (BSD-3-Clause)؛ أذونات قراءة الوسائط التي يعلنها محذوفة من بيان التطبيق |
| cryptography (المرحلة C1-b) | 2.9.0 | قفل الملف الطبي على الهاتف: X25519 و HKDF-SHA256 و AES-256-GCM، وحماية مفتاح الطبيب بـ Argon2id (Apache-2.0، تنفيذ Dart خالص) |

## لوحة التحكم (`apps/dashboard`)

Node.js 22 LTS و npm 10 أو أحدث. الحزم مثبتة بإصدارات دقيقة في `package.json` و `package-lock.json` (`npm ci`).

| الحزمة | الإصدار |
|---|---|
| react / react-dom | 19.3.1 |
| react-router | 8.4.0 |
| @tanstack/react-query | 5.104.4 |
| oidc-client-ts | 3.5.0 |
| i18next / react-i18next | 26.5.2 / 17.1.0 |
| maplibre-gl | 6.14.0 |
| vite / @vitejs/plugin-react | 8.3.4 / 6.1.2 |
| typescript / typescript-eslint | 5.9.3 / 8.71.2 |
| vitest / eslint | 5.0.5 / 10.13.0 |
| @playwright/test (اختبار المتصفح) | 1.64.1 |
| @axe-core/playwright (المرحلة 10، فحص إمكانية الوصول WCAG 2.2 A/AA) | 4.13.0 (MPL-2.0) |
| jssip (المرحلة 7، الهاتف الشبكي للمشغل، يُحمّل عند تفعيله فقط) | 3.13.8 (MIT) |
| hls.js (المرحلة 6، بديل HLS عند تعذر WHEP، يُحمّل عند الحاجة فقط) | 1.7.3 (Apache-2.0) |
| uplot (المرحلة 8، رسوم التحليلات على canvas، تُحمّل عند الحاجة فقط) | 1.6.32 (MIT) |
| markdown-it (المرحلة 8، عرض Markdown للذاكرة الوطنية، `html: false`) | 15.0.3 (MIT، يعالج GHSA-gfr2-rv44-r23c وGHSA-vfgh-jcmw-g37q) |
| dompurify (المرحلة 8، تعقيم HTML الناتج قبل عرضه) | 3.4.17 (MPL-2.0 OR Apache-2.0، مستعملة بترخيص Apache-2.0) |

> المرحلة 9: بقيت typescript على 5.9.3 لأن typescript-eslint 8 لا يدعم TypeScript 7 بعد؛ و Vite 8 (Rolldown) يقبل
> `manualChunks` في صيغة الدالة فقط. اللوحة بثلاث لغات: العربية (من اليمين إلى اليسار) والفرنسية والإنجليزية.

## بوابة المؤسسات (`apps/portal`)

نفس أدوات لوحة التحكم (Node.js 22 و npm 10 أو أحدث، `npm ci`)، بثلاث لغات (ar/fr/en) وعلى المنفذ 5174.
الحزم مثبتة بإصدارات دقيقة في `apps/portal/package.json` و `package-lock.json`؛ الإصدارات نفسها المعتمدة في لوحة التحكم
(react 19.3.1، react-router 8.4.0، react-query 5.104.4، oidc-client-ts 3.5.0، i18next 26.5.2، maplibre-gl 6.14.0،
vite 8.3.4، typescript 5.9.3، vitest 5.0.5، eslint 10.13.0). البصمة SHA-256 تُحسب في المتصفح (WebCrypto) ولا يغادر
الملف جهاز الزائر عند التحقق من شهادة.

> رُقّيت `maplibre-gl` من 5.24.0 إلى 6.12.0 في اللوحة والبوابة لإزالة التنبيه الأمني GHSA-jrc7-96c5-q579
> (يشمل الإصدارات حتى 6.4.0)؛ `npm audit` نظيف في التطبيقين.

## المرحلة 9 (فصل الصلاحيات المركزية والجهوية)

لا حزمة جديدة. أمن مستوى الصفوف (Row-Level Security) من PostgreSQL 17 نفسه (الترحيل `0025_rls_policies`)، ودور
التشغيل `ehimaya_app` بلا `BYPASSRLS`؛ إدارة الحسابات الجهوية عبر واجهة Keycloak 26.3 الإدارية الموجودة.

## المرحلة 10 (التحصين)

إصلاح دمج Dependabot الذي لم يمر بأي فحص (`docs/phase-10/review.md` §1): أُعيدت الصور الأساسية إلى
`python:3.12-slim` (لا عجلات cp315 لـ brotli و pyyaml و onnxruntime و ctranslate2 و sentencepiece) و
`postgres:17-bookworm` (حزم PostGIS و pgvector مبنية لـ 17، والترقية الكبرى تحتاج `pg_upgrade`) و `node:22-alpine`
(النسخة طويلة الدعم المختبرة). ملف Dependabot يتجاهل الآن القفزات الكبرى لهذه الصور ولـ Keycloak. `firebase_messaging` 17
يُبقي واجهة رمز FCM (`getToken`) حتى ينتقل الخادم إلى معرّفات التثبيت.

إضافات المرحلة 10:

| الأداة | الإصدار | الاستعمال |
|---|---|---|
| certifi (الخلفية والذكاء الاصطناعي والرؤية) | 2026.10.19 | ترقية بعد تدقيق التبعيات |
| pip-audit (عبر `uvx`) | 2.9.0 | تدقيق ثغرات حزم Python في CI و ci-local |
| cyclonedx-bom (`cyclonedx-py`) | 7.5.0 | قائمة مكونات SBOM لكل خدمة Python (ملفات CI، لا تُحفظ في المستودع) |
| @cyclonedx/cyclonedx-npm | 6.0.1 | SBOM للوحة والبوابة |
| promtool | من صورة Prometheus 3.5.0 | التحقق من قواعد التنبيه واختبارها |
| PostgreSQL 16 + PostGIS + pgvector (حزم Ubuntu 24.04) | 16 | تمرين الاستعادة في CI فقط (عنقودان مؤقتان)؛ الإنتاج يبقى على 17 |
| @playwright/test و @axe-core/playwright في البوابة | 1.64.1 / 4.13.0 | اختبارات المتصفح لإمكانية الوصول (أُضيفت للبوابة في هذه المرحلة) |

## المرحلة A (الاستقبال والدخول بالهاتف والواجهة الرئيسية)

تفاصيل كل أداة (بطاقة وصفية، المصدر، أمر التثبيت، الأولوية) في [تقرير المرحلة A](phase-a-report.html#tools).

| الأداة | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.3.0 (البناء 2) | رقم الإصدار في `pubspec.yaml` و `AppConfig.appVersion` / `appBuild` | — |
| صورة Keycloak الخاصة `ehimaya/keycloak` | مبنية من `keycloak/keycloak:26.8@sha256:79c623a2…d244` | تضيف مزود الدخول بالهاتف (`ehimaya-phone-otp`) وواجهة الدخول `ehimaya` | Apache-2.0 |
| واجهة Keycloak البرمجية للمزودات (`keycloak-server-spi`، `keycloak-server-spi-private`، `keycloak-services`) | 26.8.1 (نطاق `provided`) | بناء المزود فقط، لا تُضمَّن في الملف | Apache-2.0 |
| Maven (مرحلة البناء فقط) | `maven:3.9.11-eclipse-temurin-21@sha256:6fdc855a…d237` | بناء المزود وتشغيل اختباراته داخل `docker build` | Apache-2.0 |
| Java (Eclipse Temurin) | 21 | لغة المزود (`maven.compiler.release` 21) | GPL-2.0 + CE |
| JUnit Jupiter | 5.13.4 | 36 اختبارا لمزود Keycloak | EPL-2.0 |
| maven-surefire-plugin | 3.5.4 | تشغيل اختبارات JUnit | Apache-2.0 |
| Pillow (أداة محلية، خارج المستودع) | — | توليد أيقونات التطبيق من شعار الديوان مرة واحدة | MIT-CMU |

لا حزمة جديدة في Python ولا في Flutter ولا في npm في هذه المرحلة. اختبار جديد يُفشل البناء إذا ظهرت حزمة إعلانات أو
تتبع في `pubspec.lock` أو `uv.lock` أو `package-lock.json` (القاعدة 4).

## المرحلة B1 (طبقات الخريطة، الأقرب إليّ، مركز الطوارئ، اتصل بنا)

تفاصيل كل أداة (بطاقة وصفية، المصدر، أمر التثبيت، الأولوية) في [تقرير المرحلة B1](phase-b1-report.html#tools).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.4.0 (البناء 3) | دليل الطوارئ، الأقرب إليّ، اتصل بنا | — |
| openpyxl (موجودة منذ المرحلة 8) | 3.1.5 | قراءة ملفات XLSX للطبقات (`read_only`، `data_only`: لا تُنفَّذ أي صيغة) | MIT |
| flutter_map / latlong2 (موجودتان) | 8.3.2 / 0.10.1 | لم تتغيرا؛ الأقرب إليّ يحسب المسافات على الهاتف (هافرساين) دون خريطة إضافية | BSD-3 / Apache-2.0 |
| path_provider (موجودة) | 2.1.6 | نسخ الطبقات دون اتصال في مجلد دعم التطبيق (`places/`) | BSD-3 |
| url_launcher (موجودة) | 6.3.3 | الاتصال (`tel:`) وفتح المسار في تطبيق الخرائط (`geo:`) | BSD-3 |
| بيانات OpenStreetMap عبر Overpass API | لقطة يوم التشغيل (`osm_timestamp` في كل ملف) | التحميل الأول للمستشفيات والمصحات والصيدليات والشرطة والحرس، معلَّمة «للتثبت» | ODbL 1.0، مع الإسناد |
| `scripts/osm_layers.py` | جديد (مكتبة Python القياسية فقط) | يحضّر ملف GeoJSON لكل طبقة بصيغة الاستيراد | — |
| `scripts/sim_layers.py` `[SIM]` | جديد (مكتبة Python القياسية فقط) | 144 مكانا تقريبيا وهميا للتجربة بثلاث لغات، دون أرقام هاتف، في `data/sim-layers` | — |
| `scripts/guide_seed.py` | جديد | يولّد النسخة المضمَّنة في التطبيق من دليل الطوارئ (`assets/emergency_guide.json`)، ويتحقق CI من تطابقها | — |

لا حزمة جديدة في Python ولا في Flutter ولا في npm في هذه المرحلة: كل الأدوات المستعملة كانت مثبتة من قبل.

## المرحلة B2 (السلامة الشخصية)

تفاصيل كل أداة (بطاقة وصفية، المصدر، أمر التثبيت، الأولوية) في [تقرير المرحلة B2](phase-b2-report.html#tools).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.5.0 (البناء 4) | جهات الطوارئ، رسالة الاستغاثة، الجهات المرتبطة، الموقع المباشر، فحص السلامة، الملف الطبي | — |
| timezone (جديدة كتبعية مباشرة؛ كانت تبعية غير مباشرة لمكتبة الإشعارات) | 0.11.2 | توقيت تذكيرَي فحص السلامة (10 دقائق ودقيقة قبل الموعد) بتوقيت UTC | BSD-2-Clause |
| flutter_local_notifications (موجودة) | 22.3.1 | `zonedSchedule` للتذكيرات (منبّه غير دقيق، دون إذن خاص)، وقناة التنبيه الحرج لتنبيه الجهة المرتبطة | BSD-3 |
| geolocator (موجودة) | 14.0.1 | الموقع المباشر بخدمة أمامية ظاهرة (إشعار دائم أثناء المشاركة) | MIT |
| url_launcher (موجودة) | 6.3.3 | رسالة SMS لكل الأرقام دفعة واحدة (`sms:`) وواتساب (`https://wa.me/`) والاتصال بـ 198 | BSD-3 |
| drift / SQLCipher (موجودتان) | 2.35.2 / 3.7.1 | قاعدة الهاتف v2: جهات الطوارئ والمجموعات وسجل الرسائل والملف الطبي، مشفرة على الهاتف | MIT |
| واجهات أندرويد الأصلية (دون مكتبة) | Android SDK | منتقي جهات الاتصال (`ACTION_PICK`، دون إذن قراءة جهات الاتصال)، قفل الهاتف (`KeyguardManager`)، اختصارات التطبيق الثابتة | Apache-2.0 |
| PostgreSQL (موجودة) | 17 | مخطط `safety` بأمان على مستوى الصفوف (الهجرات 0037 و 0038 و 0039) | PostgreSQL |

لا حزمة جديدة في Python ولا في npm في هذه المرحلة. لا خدمة خارجية جديدة: الرسالة تُرسل من شريحة الهاتف، والتنبيه داخل
التطبيق يمر بالإشعارات الموجودة.

## المرحلة C1-a (محور الأطباء: الصفات والتوثيق)

تفاصيل الجزء في [تقرير المرحلة C1-a](phase-c1a-report.html) والتصميم في
[design-medical-axis.md](phase-c/design-medical-axis.md).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.6.0 (البناء 5) | فضاء الأطباء: اختيار الصفة، التسجيل، التوفر، دليل الأطباء | — |
| PostgreSQL (موجودة) | 17 | جدولا `identity.doctor` و `identity.doctor_review` (الهجرة 0040)، الأرقام المهنية مشفرة | PostgreSQL |
| Keycloak (موجودة) | 26.8 | دور جديد في مجال الموظفين: `medical_coordinator` (منسّق طبي جهوي) | Apache-2.0 |
| PostgreSQL (موجودة) | 17 | اللجنة الطبية: مدة العضوية في `identity.doctor` (الهجرة 0041)، يعيّنها مدير النظام | PostgreSQL |

لا حزمة جديدة في Python ولا في npm ولا في Flutter، ولا خدمة خارجية جديدة.

## المرحلة C1-b (المفاتيح الشخصية وقفل الملف الطبي)

تفاصيل الجزء في [تقرير المرحلة C1-b](phase-c1b-report.html) والتصميم في
[design-medical-axis.md](phase-c/design-medical-axis.md) (§12).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.7.0 (البناء 6) | مفتاح الطبيب الشخصي، قفل الملف الطبي عند الإرسال، بطاقة الطوارئ، صندوق ملفات الطبيب واللجنة | — |
| cryptography (Dart) | 2.9.0 | التشفير على الهاتف (X25519، HKDF-SHA256، AES-256-GCM، Argon2id) | Apache-2.0 |
| cryptography (Python، موجودة) | 50 | الاختبارات فقط: تقفل الملف وتفتحه كما يفعل الهاتف للتحقق من التوافق | Apache-2.0 / BSD |
| PostgreSQL (موجودة) | 17 | مفتاح الطبيب العام ونسخته المقفلة في `identity.doctor`، ومخطط `medical` (الملف المقفل، نسخ المفتاح، سجل الفتح) بالهجرة 0042 | PostgreSQL |

حزمة Flutter جديدة واحدة (`cryptography` 2.9.0). لا حزمة جديدة في Python ولا في npm، ولا خدمة خارجية جديدة.

## المرحلة C1-c (الإحالة إلى المختصين والرأي الطبي وشفافية المواطن)

تفاصيل الجزء في [تقرير المرحلة C1-c](phase-c1c-report.html) والتصميم في
[design-medical-axis.md](phase-c/design-medical-axis.md) (§13).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.8.0 (البناء 7) | الإحالة إلى مختص، كتابة الرأي وقراءته مقفلاً، القفل لعضو اللجنة الجديد، «من اطّلع على ملفي الطبي» | — |
| cryptography (Dart، موجودة) | 2.9.0 | إعادة قفل مفتاح الملف لمختص أو لعضو جديد، وقفل الرأي بمفتاح جديد | Apache-2.0 |
| PostgreSQL (موجودة) | 17 | جداول `medical.referral` و `medical.opinion` و `medical.opinion_key` بالهجرة 0043، مع أمان الصفوف | PostgreSQL |

لا حزمة جديدة في Flutter ولا في Python ولا في npm، ولا خدمة خارجية جديدة.

## مرحلة نظام التصميم (ألوان زاهية وأيقونات ملونة في التطبيقات الثلاثة)

تفاصيل المرحلة في [تقرير المرحلة](phase-ui-report.html) والقاعدة في [design-system.md](design-system.md).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.9.0 (البناء 8) | الألوان والخط والمكونات المشتركة، الواجهة الرئيسية | — |
| IBM Plex Sans Arabic (ملفات TTF في `apps/mobile/assets/fonts`) | من مستودع google/fonts | خط التطبيق، العربية واللاتينية | SIL OFL 1.1 |
| `@fontsource/ibm-plex-sans-arabic` | 5.3.0 | نفس الخط مستضافا في لوحة التحكم والبوابة | SIL OFL 1.1 |
| Material Symbols Rounded (مسارات SVG مضمَّنة في `Icon.tsx`) | من مستودع google/material-design-icons | أيقونات قائمة اللوحة والبوابة | Apache-2.0 |

لا حزمة جديدة في Flutter ولا في Python، ولا خدمة خارجية. الخط على الويب يُحمَّل من نفس الخادم، فلا تغيير في سياسة CSP.

## مرحلة UI-2 (نظام التصميم في بقية الشاشات، شريط البيئة، حماية المسودات)

تفاصيل المرحلة في [تقرير المرحلة](phase-ui2-report.html). الشكل السابق محفوظ كما هو في الفرع `classic/v0.9.0`.

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.10.0 (البناء 9) | قوائم الإعدادات والسلامة والطوارئ والتسجيل بالبطاقات، شريط البيئة | — |
| الإعداد `ENVIRONMENT_BANNER` | جديد | شريط البيئة **[SIM]**: `auto` أو `development` أو `pilot` أو `training` أو `off` | — |
| `GET /api/v1/app/environment` | جديد | اسم البيئة للوحة والبوابة؛ الحقل `environment` في جواب الإصدار للتطبيق | — |

لا حزمة جديدة في Flutter ولا في Python ولا في npm، ولا خدمة خارجية، ولا ترحيل لقاعدة البيانات. المسودات تُحفظ في
`sessionStorage` داخل علامة التبويب فقط ولا تغادر المتصفح.

## مرحلة P2a (فضاء المؤسسات في التطبيق، الإضافة 12)

تفاصيل المرحلة في [تقرير المرحلة](phase-p2a-report.html) والتصميم في [phase-p2/design-institutions-app.md](phase-p2/design-institutions-app.md).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.11.0 (البناء 10) | تسجيل مؤسسة بأربع خطوات، «مؤسستي» بحلقة الجاهزية والأقسام، البطاقة بتبويبات وشارات الرؤية | — |
| ترحيل قاعدة البيانات | `0044_institution_kinds` | 12 صبغة بدل 6 مع ترحيل القديمة (قابل للتراجع)، العمودان `kind_fields` و `kind_review` | — |
| `GET /api/v1/public/org-kinds` | جديد | الصبغات وخانات كل صبغة ودرجة رؤيتها (قائمة عمل **[SIM]**) | — |

لا حزمة جديدة في Flutter ولا في Python ولا في npm، ولا خدمة خارجية.

## مرحلة P2b (التنبيهات الموجّهة والتوعية والتمارين والصيانة بالصورة)

تفاصيل المرحلة في [تقرير المرحلة](phase-p2b-report.html) والتصميم في القسم 5 من [phase-p2/design-institutions-app.md](phase-p2/design-institutions-app.md).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.12.0 (البناء 11) | رسائل الديوان مع «اطّلعتُ»، التوعية، التمارين والتظاهرات، تسجيل الصيانة بصورة من الكاميرا | — |
| ترحيل قاعدة البيانات | `0045_org_alerts_activities` | `org_kinds` و `ack_required` في الرسالة، `notify.org_ack`، `org_kinds` في النصيحة، `org.activity`، `org.maintenance`، صنف الوثيقة `maintenance_photo` (قابل للتراجع) | — |
| واجهات جديدة | 10 عمليات | `/orgs/{id}/messages` و `/ack`، `/awareness`، `/activities`، `/equipment/{eid}/maintenance`، `/staff/notifications/{id}/acks`، `/staff/org-events` | — |

لا حزمة جديدة: الصورة تُلتقط بـ `image_picker` وتُرفع بعميل tus الموجود، والبصمة بـ `crypto`، وكلاهما مثبّت من قبل.

## مرحلة P3a (تطوير الشهادة: الختم الإلكتروني والشبّاك والتذكير و«تحتاج تحديثاً»)

تفاصيل المرحلة في [تقرير المرحلة](phase-p3a-report.html) والتصميم في [phase-p3/design-certificates.md](phase-p3/design-certificates.md).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.13.0 (البناء 12) | «تحتاج تحديثاً» مع الأقسام المتغيّرة، الأختام، تنبيهات الشهادة الثلاثة | — |
| ترحيل قاعدة البيانات | `0046_certificate_counter` | `reminded_90_on` و `reminded_30_on` في الشهادة، جدول `org.certificate_stamp` (قابل للتراجع) | — |
| واجهات جديدة | 4 عمليات | `/staff/certificates/lookup`، `/staff/certificates/{id}/stamps`، و `PUT`/`GET` صورة الختم | — |
| قراءة رمز QR بالكاميرا في اللوحة | `BarcodeDetector` المدمج في المتصفح | زر «مسح بالكاميرا» حين يدعمه المتصفح، وإلا قارئ QR بـ USB أو كتابة الرمز | — |

لا حزمة جديدة: الختم الإلكتروني يُرسم في HTML الشهادة الموجود (WeasyPrint)، ونوع صورة الختم يُقرأ من أول بايتاتها.

## مرحلة P3b (شهادة الوقاية وقسم التقارير)

تفاصيل المرحلة في [تقرير المرحلة](phase-p3b-report.html) والتصميم في [phase-p3/design-prevention.md](phase-p3/design-prevention.md).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.14.0 (البناء 13) | قسم «التقارير والمحاضر»: التذكيرات، الزيارات ومحاضرها، التحفظات وآجالها، الشهادات بنوعيها، تقارير التمارين، التقرير السنوي | — |
| ترحيل قاعدة البيانات | `0047_prevention_visits` | جدولا `org.prevention_visit` (زيارة مفتوحة واحدة لكل مؤسسة) و `org.prevention_reservation`، وعمودا `kind` و `visit_id` في الشهادة (قابل للتراجع) | — |
| واجهات جديدة | 16 عملية | 6 في البوابة (`/orgs/{id}/prevention/...` و `/annual-report`) و 10 في اللوحة (`/staff/prevention/...`) | — |

لا حزمة جديدة: محضر الزيارة وشهادة الوقاية يُولَّدان بـ WeasyPrint الموجود، والتوقيع بمفتاح Ed25519 نفسه.

## مرحلة P3c (مراجعة النفاذ في التطبيق)

تفاصيل المرحلة في [تقرير المرحلة](phase-p3c-report.html) والتصميم في [phase-p3/design-accessibility.md](phase-p3/design-accessibility.md).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.15.0 (البناء 14) | إصلاح التخطيط عند تكبير الخط 200% في ستة مواضع، ومكوّن `PillBeside` | — |
| فحوص النفاذ في `flutter_test` | مع Flutter 3.47.7 | `androidTapTargetGuideline` و `labeledTapTargetGuideline` و `textContrastGuideline` في `test/widgets/accessibility_test.dart` (88 حالة) | BSD-3-Clause |

لا حزمة جديدة ولا ترحيل.

## مرحلة P5a (القراءة الصوتية والوميض)

تفاصيل المرحلة في [تقرير المرحلة](phase-p5a-report.html) والتصميم في [phase-p5/design-sensory.md](phase-p5/design-sensory.md).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.16.0 (البناء 15) | زر «استمع»، شاشة «النفاذ»، وميض الشاشة والمصباح والقراءة الآلية عند التنبيه العاجل | — |
| `flutter_tts` | 4.2.5 | صوت الهاتف نفسه (Android TextToSpeech و iOS AVSpeechSynthesizer)، دون إرسال أي نص | MIT |
| `torch_light` | 2.0.0 | وميض مصباح الكاميرا، دون إذن الكاميرا | Apache-2.0 |

في `AndroidManifest.xml` أُضيف `android.intent.action.TTS_SERVICE` إلى `<queries>` ليرى التطبيق محرك الكلام في أندرويد 11 وما بعده. لا ترحيل ولا تغيير في الخادم.

## مرحلة P5b (الوضع المبسّط، تقييم التطبيق، حساب المؤسسة من الهاتف)

تفاصيل المرحلة في [تقرير المرحلة](phase-p5b-report.html) والتصميم في [phase-p5/design-simple.md](phase-p5/design-simple.md).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.17.0 (البناء 16) | الوضع المبسّط، «قيّم التطبيق»، «جولة التعريف»، تسجيل المؤسسة من الهاتف بتأكيد البريد برمز | — |
| ترحيل قاعدة البيانات | 0048 | المخطط `feedback` وجدول `app_rating`، وجدول `identity.email_code` (الرمز ببصمة HMAC والبريد مشفّر)، بأمن مستوى الصفوف | — |

لا حزمة جديدة. البريد برمز يمر عبر صندوق الإرسال الموجود (`outbox`).

## مرحلة P4a (تطبيق الأعوان: الدخول، المناوبة، المهام، التقرير الأول، الإصابات)

تفاصيل المرحلة في [تقرير المرحلة](phase-p4a-report.html) والتصميم في [phase-p4/design-staff.md](phase-p4/design-staff.md).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.18.0 (البناء 17) | نقطة دخول ثانية `lib/main_staff.dart` لتطبيق الأعوان (نفس قاعدة الكود ونظام التصميم) | — |
| ترحيل قاعدة البيانات | 0049 | `ops.staff_device` و `ops.shift` و `ops.crew_event` و `ops.field_report` و `ops.casualty_count` و `ops.casualty_transport`، وعمودا `shift_id` و `acknowledged_at` في `ops.assignment`، وقناة `staff_push` في صندوق الإرسال، بأمن مستوى الصفوف | — |
| Keycloak (عالم الأعوان) | 26.x (دون تغيير) | الدور `team_leader`، والعميل العام `ehimaya-staff-app` بمنح الجهاز (RFC 8628) و `offline_access`، وجلسات دون اتصال 24 ساعة خمولا و7 أيام أقصى | Apache-2.0 |

لا حزمة جديدة: الدخول بالرمز يمر عبر `dio` الموجود، وبصمة PIN عبر `crypto`.

## مرحلة P4b (تطبيق الأعوان: الكتابة بأقل قدر، تقارير الوضع، النجدة والخطر، الصور والصوت، التقرير المفصّل)

تفاصيل المرحلة في [تقرير المرحلة](phase-p4b-report.html) والتصميم في [phase-p4/design-staff.md](phase-p4/design-staff.md) (§5).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.19.0 (البناء 18) | شاشات الأعوان بالأزرار والرقائق والعدّادات، الإعداد `STAFF_ROOM_PHONE` | — |
| ترحيل قاعدة البيانات | 0050 | `ops.crew_alert` و `ops.field_attachment` و `ops.report_template`، وأعمدة نوع التقرير والتعزيزات والأجوبة في `ops.field_report`، والمصاب الخطير، ومرجع المستشفى في النقل، ورقم الاتصال في التكليف، بأمن مستوى الصفوف | — |

لا حزمة جديدة: الصورة بـ `image_picker` والتسجيل الصوتي بـ `record`، وكلاهما مثبّت من قبل. المستشفيات القريبة تُقرأ من طبقة
الخريطة الموجودة (بيانات تقريبية [SIM] إلى أن تصل القائمة الرسمية).

## مرحلة P4c (وحدة الوقاية في الموقع على تطبيق الأعوان)

تفاصيل المرحلة في [تقرير المرحلة](phase-p4c-report.html) والتصميم في [phase-p4/design-staff.md](phase-p4/design-staff.md) (§8).

| الأداة أو المصدر | الإصدار | الاستعمال | الرخصة |
|---|---|---|---|
| تطبيق الهاتف | 0.20.0 (البناء 19) | زيارات الوقاية للمفقّد: الشبكة بالأزرار، الصور، التوقيعان، القرار بالتحفظات، الحفظ المشفّر والإرسال المؤجل | — |
| ترحيل قاعدة البيانات | 0051 | أعمدة المفقّد على الهاتف ومعرّف التفقد والتوقيعين واسم الممثل وصفته في `org.prevention_visit`، والجدول `org.prevention_photo` | — |

لا حزمة جديدة: التشفير على الهاتف بـ `cryptography` (AES-256-GCM) والمفتاح في `flutter_secure_storage`، والملفات في
مجلد التطبيق الخاص عبر `path_provider`، والصور بـ `image_picker`، وكلها مثبّتة من قبل. لا تغيير في Keycloak: المفقّد
يدخل بالدور `org_auditor` الموجود وبنفس عميل تطبيق الأعوان.

## أولوية التنصيب

1. Docker Engine 27+ مع Compose v2 (البنية كاملة بأمر واحد).
2. Python 3.12 و uv (تطوير الخلفية).
3. Node.js 22 (لوحة التحكم).
4. Flutter 3.47.7 و Android Studio أو Xcode (تطبيق الهاتف).
5. طبقة الذكاء الاصطناعي: `docker compose ... --profile ai up -d` (ينزّل النماذج مرة واحدة، حوالي 6 غيغابايت في ملف cpu).
   على خادم GPU: مشغّل NVIDIA و NVIDIA Container Toolkit، ثم إضافة `-f infra/compose.gpu.yml`.
6. المرحلة A: لا شيء يُثبَّت يدويا. `docker compose -f infra/compose.yml build keycloak` يبني صورة Keycloak مع المزود
   (يحتاج اتصالا بمستودع Maven المركزي عند أول بناء). لاختبار المزود دون Docker: JDK 21 و Maven 3.9 ثم
   `mvn -f infra/keycloak/providers/phone-otp/pom.xml verify`.
7. المرحلة B1: لا شيء يُثبَّت. `alembic upgrade head` ينشئ الطبقات (0032) ودليل الطوارئ (0033) وطلبات «اتصل بنا»
   (0034). للتحميل الأول من OpenStreetMap: `python3 scripts/osm_layers.py --out build/osm` (يحتاج اتصالا بـ
   `overpass-api.de`) ثم استيراد كل ملف في طبقته من لوحة التحكم.
   للتجربة قبل وصول القوائم: استيراد ملفات `data/sim-layers` في طبقات معلَّمة «بيانات تقريبية [SIM]».
8. المرحلة B2: لا شيء يُثبَّت. `alembic upgrade head` ينشئ مخطط السلامة (0037) والملف الطبي المرفق (0038) وسجل
   المواقع (0039، معطّل افتراضيا عبر الإعداد `safety.location_history`). يُبنى التطبيق 0.5.0 بالأمر المعتاد
   `flutter build apk`.
9. المرحلة C1-a: لا شيء يُثبَّت. `alembic upgrade head` ينشئ جدولَي الأطباء (0040) ومدة عضوية اللجنة الطبية (0041)، ويُستورد مجال الموظفين من جديد
   ليظهر الدور `medical_coordinator` (يمنحه مسؤول الحسابات الجهوي). يُبنى التطبيق 0.6.0 بالأمر المعتاد.
10. المرحلة C1-b: لا شيء يُثبَّت على الخادم. `alembic upgrade head` ينشئ مخطط `medical` (0042)، و `flutter pub get` يجلب
    `cryptography` 2.9.0 ثم يُبنى التطبيق 0.7.0 بالأمر المعتاد. على كل طبيب موثّق أن ينشئ مفتاحه من التطبيق قبل أن تصله الملفات.
11. المرحلة C1-c: لا شيء يُثبَّت. `alembic upgrade head` ينشئ جداول الإحالة والرأي (0043)، ثم يُبنى التطبيق 0.8.0 بالأمر المعتاد.
12. مرحلة نظام التصميم: لا شيء يُثبَّت على الخادم. `npm ci` في `apps/dashboard` و `apps/portal` يجلب الخط، ثم يُبنى التطبيق 0.9.0 بالأمر المعتاد.
13. مرحلة UI-2: لا شيء يُثبَّت. يُضبط `ENVIRONMENT_BANNER` في `.env` حسب الخادم (`pilot` لخادم التجربة)، ثم يُبنى التطبيق 0.10.0 بالأمر المعتاد.
14. مرحلة P2a: لا شيء يُثبَّت. `alembic upgrade head` يرحّل الصبغات (0044): المؤسسات «الخاصة» تصبح «أخرى» وتظهر في
    اللوحة بشارة «تحتاج مراجعة الصبغة» ليختار مراقب المؤسسات صبغتها عند المصادقة. ثم يُبنى التطبيق 0.11.0 بالأمر المعتاد.
15. مرحلة P2b: لا شيء يُثبَّت. `alembic upgrade head` ينشئ جداول الإقرارات والتمارين والصيانة (0045)، ثم يُبنى التطبيق 0.12.0 بالأمر المعتاد.
    يحتاج التطبيق إذن الكاميرا لصورة الصيانة (مصرَّح به منذ المرحلة 2 لصور البلاغ).
16. مرحلة P3a: لا شيء يُثبَّت. `alembic upgrade head` ينشئ جدول الأختام وعمودَي التذكير (0046)، ثم يُبنى التطبيق 0.13.0 بالأمر المعتاد.
    التذكير بالتجديد يعمل في المهام اليومية الموجودة ويرسل عبر خادم البريد المضبوط.
17. مرحلة P3b: لا شيء يُثبَّت. `alembic upgrade head` ينشئ جدولَي الزيارات والتحفظات ونوع الشهادة (0047)، ثم يُبنى التطبيق 0.14.0 بالأمر المعتاد.
    يُمنح المفقّدون الدور `org_auditor` الموجود ليبرمجوا الزيارات ويملؤوا الشبكة ويقرّروا.
18. مرحلة P3c: لا شيء يُثبَّت ولا ترحيل. يُبنى التطبيق 0.15.0 بالأمر المعتاد.
19. مرحلة P5a: لا شيء يُثبَّت على الخادم. `flutter pub get` يجلب `flutter_tts` و `torch_light`، ثم يُبنى التطبيق 0.16.0 بالأمر المعتاد.
    للقراءة بالعربية يحتاج الهاتف صوتا عربيا في «تحويل النص إلى كلام» (محرك Google يوفره ويُنزَّل مرة واحدة).
20. مرحلة P5b: لا شيء يُثبَّت. `alembic upgrade head` ينشئ جدولَي التقييم ورموز البريد (0048)، ثم يُبنى التطبيق 0.17.0 بالأمر المعتاد.
    رموز البريد تُرسل عبر خادم البريد المضبوط أصلا للصندوق؛ في بيئة التجربة تظهر في Mailpit.
21. مرحلة P4a: لا شيء يُثبَّت. يُستورد عالم الأعوان من جديد (`infra/keycloak/realms/ehimaya-staff-realm.json`) ليظهر الدور
    `team_leader` والعميل `ehimaya-staff-app`، ثم `alembic upgrade head` (0049). يمنح مسؤول الحسابات الجهوي الدور لقادة الفرق.
    تطبيق الأعوان يُبنى بـ `flutter build apk -t lib/main_staff.dart` مع `--dart-define=STAFF_OIDC_ISSUER=...` و `API_BASE_URL`.
22. مرحلة P4b: لا شيء يُثبَّت. `alembic upgrade head` (0050)، ثم يُبنى تطبيق الأعوان 0.19.0 بالأمر نفسه مع
    `--dart-define=STAFF_ROOM_PHONE=198` (رقم القاعة). يعتمد المكتب قوالب التقارير المفصّلة من صفحة «قوالب التقارير» في اللوحة.
23. مرحلة P4c: لا شيء يُثبَّت. `alembic upgrade head` (0051)، ثم يُبنى تطبيق الأعوان 0.20.0 بالأمر نفسه. المفقّدون
    (`org_auditor`، بولاية محدّدة) يدخلون التطبيق نفسه ويسجّلون هواتفهم كقادة الفرق؛ من له الدوران يرى زرّ «زيارات الوقاية»
    في شاشة المناوبة.
