# ء-حماية · E-HIMAYA

إنشاء منظومة ذكية للتبليغ والمشاركة المجتمعية والمؤسساتية في مجال الوقاية والسلامة وإدارة المخاطر: من التبليغ إلى أخذ القرار.

| الوثيقة | الرابط |
|---|---|
| وثيقة المتطلبات (معتمدة، الإصدار 1.0) | [`docs/01-requirements.html`](docs/01-requirements.html) |
| وثيقة هيكلة النظام (معتمدة، الإصدار 1.0) | [`docs/02-architecture.html`](docs/02-architecture.html) |
| الإصدارات المثبتة للأدوات | [`docs/versions.md`](docs/versions.md) |
| تقرير المرحلة 1 | [`docs/phase-1-report.html`](docs/phase-1-report.html) |
| تقرير المرحلة 2 | [`docs/phase-2-report.html`](docs/phase-2-report.html) |
| عقد الواجهة البرمجية لمسار البلاغ | [`docs/api/phase-2-contract.md`](docs/api/phase-2-contract.md) |

## محتوى المستودع

```
infra/
  compose.yml            البنية الأساسية للتطوير والتجربة
  postgres/              PostgreSQL 17 + PostGIS 3.5 + pgvector، وسكربت إنشاء القاعدتين
  keycloak/realms/       فضاءا الهوية: ehimaya-public (المواطنون والمؤسسات) و ehimaya-staff (لوحة التحكم، MFA إجباري)
  nats/                  ناقل الأحداث NATS JetStream
  seaweedfs/             تخزين الوسائط المتوافق مع S3
  smoke/                 اختبار دخان للمنظومة كاملة بعد التشغيل
apps/mobile/             تطبيق الهاتف (Flutter، عربية وفرنسية وإنجليزية)
apps/dashboard/          لوحة التحكم المركزية (React، عربية وفرنسية)
services/api/            الخلفية الأساسية (FastAPI)
  app/core/              الإعدادات، قاعدة البيانات، التحقق من الرموز والصلاحيات، السجلات
  app/modules/           الوحدات: geo، identity، audit، reports، ops، health
  migrations/            ترحيلات Alembic (المخطط الكامل + المرجع الإداري)
  seed/                  الولايات الـ24 وحدودها والمعتمديات الـ279
  tests/                 اختبارات على قاعدة بيانات حقيقية
services/notify-sim/     محاكي قنوات الإشعار للتطوير فقط (FCM والرسائل القصيرة) — docs/api/notify-sim.md
docs/                    الوثائق وتقارير المراحل
```

## التشغيل على جهاز التطوير

المتطلبات: Docker Engine 27 أو أحدث مع Compose v2. لتطوير الخلفية خارج الحاويات: Python 3.12 و [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/YaamenMegdiche/E-HIMAYA.git && cd E-HIMAYA
cp .env.example .env
# غيّر كل كلمات المرور في .env، وولّد الأسرار الثلاثة:
sed -i "s|^ANON_PSEUDONYM_SECRET=.*|ANON_PSEUDONYM_SECRET=$(openssl rand -hex 32)|" .env
sed -i "s|^FIELD_ENCRYPTION_KEY=.*|FIELD_ENCRYPTION_KEY=$(openssl rand -base64 32)|" .env
sed -i "s|^TUSD_HOOK_SECRET=.*|TUSD_HOOK_SECRET=$(openssl rand -hex 24)|" .env

docker compose --env-file .env -f infra/compose.yml up -d --build
docker compose --env-file .env -f infra/compose.yml ps
python3 infra/smoke/smoke_test.py   # بلاغ مجهول + رفع ملف بالاستئناف + التحقق من البصمة
```

عند التشغيل تطبّق الخلفية ترحيلات قاعدة البيانات آليا، ويستورد Keycloak الفضاءين.

| الخدمة | العنوان المحلي |
|---|---|
| الواجهة البرمجية ووثائقها | http://localhost:8000/docs |
| فحص الجاهزية | http://localhost:8000/health/ready |
| Keycloak (الإدارة) | http://localhost:8080/admin |
| رفع الوسائط بالاستئناف (tus) | http://localhost:1080/api/v1/uploads/ |
| تخزين S3 | http://localhost:8333 |
| مراقبة NATS | http://localhost:8222 |
| صندوق المحاكاة: الإشعارات والرسائل القصيرة (تطوير فقط) | http://localhost:8090 |

كل المنافذ مربوطة بـ `127.0.0.1` فقط. النشر خارج جهاز التطوير (TLS، البوابة العكسية، النسخ الاحتياطي) يأتي في مرحلة لاحقة.

### إنشاء أول مستخدم إداري

1. ادخل إلى http://localhost:8080/admin بحساب `KEYCLOAK_ADMIN`.
2. اختر الفضاء `ehimaya-staff` ثم Users ثم Add user.
3. حدّد السمة `gouvernorat_code` (مثلا `61` لصفاقس) أو `scope_level = national` للنطاق الوطني، ثم أسند الدور المناسب (`operator`، `sysadmin`...).
4. عند أول دخول يُطلب من المستخدم تغيير كلمة المرور وتفعيل التحقق الثنائي (TOTP).

## تطوير الخلفية واختبارها

```bash
cd services/api
uv sync
export DATABASE_URL=postgresql+asyncpg://ehimaya:<كلمة المرور>@localhost:5432/ehimaya
export ANON_PSEUDONYM_SECRET=$(openssl rand -hex 32)
export FIELD_ENCRYPTION_KEY=$(openssl rand -base64 32)
uv run alembic upgrade head
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run mypy app
uv run uvicorn app.main:app --reload
```

## قواعد العمل في المستودع

- كل تغيير عبر طلب دمج (Pull Request) يمر بالتكامل المستمر: الفحص، الأنواع، الترحيلات صعودا ونزولا، الاختبارات، بناء الصورة، استيراد فضاءات Keycloak.
- لا تُعدّل ترحيلات طُبقت في أي بيئة؛ أضف ترحيلا جديدا.
- لا تُسجَّل معطيات شخصية في السجلات (الأسماء، الهواتف، أرقام بطاقات التعريف)؛ استعمل المعرفات فقط.
- كل اطلاع على معطيات حساسة أو قرار يمر عبر `app.modules.audit.service.record`.
