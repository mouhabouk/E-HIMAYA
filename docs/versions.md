# الإصدارات المثبتة (المراحل 1 إلى 3)

تُحدَّث هذه القائمة مع كل مرحلة. تُعتمد الإصدارات الدقيقة أدناه في الكود والحاويات.

## الحاويات

| المكون | الصورة | الرخصة |
|---|---|---|
| PostgreSQL + PostGIS | `postgres:17-bookworm` + `postgresql-17-postgis-3` + `postgresql-17-pgvector` (PGDG) | PostgreSQL / GPL-2.0 |
| Valkey | `valkey/valkey:8.1-alpine` | BSD-3 |
| NATS | `nats:2.10-alpine` | Apache-2.0 |
| SeaweedFS (S3) | `chrislusf/seaweedfs:3.97` | Apache-2.0 |
| Keycloak | `keycloak/keycloak:26.3` (اختُبر 26.3.5) | Apache-2.0 |
| رفع الوسائط بالاستئناف (tus) | `tusproject/tusd:v2.8.0` | MIT |
| الخلفية وخدمة الذكاء الاصطناعي | `python:3.12-slim` | PSF |
| خادم النموذج اللغوي المحلي | `ollama/ollama:0.40.1` | MIT |

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
| boto3 (S3) | 1.43.114 |
| cryptography (AES-256-GCM) | 50.0.2 |
| pytest / pytest-asyncio | 9.1.1 / 1.4.0 |
| ruff / mypy | 0.17.1 / 2.4.0 |

## طبقة الذكاء الاصطناعي 1 (`services/ai`، المرحلة 3)

كل النماذج تعمل على خوادمنا ولا تُرسل أي معطيات إلى خدمة خارجية (NFR-10، NFR-11). سكربت
`services/ai/models/fetch_models.py` ينزّل النماذج ويحوّلها ويتحقق من صحتها، ويرفض أي نموذج رخصته غير متساهلة.

| القدرة | النموذج (prod، خادم GPU) | النموذج (cpu) | النموذج (ci) | الرخصة | المصدر |
|---|---|---|---|---|---|
| تحويل الصوت إلى نص | Whisper large-v3 (`Systran/faster-whisper-large-v3`) | Whisper medium | Whisper base | MIT | <https://huggingface.co/Systran> |
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

## لوحة التحكم (`apps/dashboard`)

Node.js 22 LTS و npm 10 أو أحدث. الحزم مثبتة بإصدارات دقيقة في `package.json` و `package-lock.json` (`npm ci`).

| الحزمة | الإصدار |
|---|---|
| react / react-dom | 19.3.0 |
| react-router | 7.18.4 |
| @tanstack/react-query | 5.104.1 |
| oidc-client-ts | 3.5.0 |
| i18next / react-i18next | 26.4.2 / 17.0.15 |
| maplibre-gl | 5.24.0 |
| vite / typescript | 7.3.6 / 5.9.3 |
| vitest / eslint | 4.1.11 / 10.12.0 |

## أولوية التنصيب

1. Docker Engine 27+ مع Compose v2 (البنية كاملة بأمر واحد).
2. Python 3.12 و uv (تطوير الخلفية).
3. Node.js 22 (لوحة التحكم).
4. Flutter 3.47.7 و Android Studio أو Xcode (تطبيق الهاتف).
5. طبقة الذكاء الاصطناعي: `docker compose ... --profile ai up -d` (ينزّل النماذج مرة واحدة، حوالي 6 غيغابايت في ملف cpu).
   على خادم GPU: مشغّل NVIDIA و NVIDIA Container Toolkit، ثم إضافة `-f infra/compose.gpu.yml`.
