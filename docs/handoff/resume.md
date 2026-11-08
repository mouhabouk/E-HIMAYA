# حوصلة الاستئناف: ء-حماية (e-Himaya)

آخر تحديث: 2026-11-08، بعد المرحلة H1 والسجلات وسجل التغييرات وCI/CD وشاشة الدخول. هذه الوثيقة تكفي جلسة جديدة لتواصل العمل
دون سؤالك عمّا سبق. انسخ «نص البداية» في آخرها والصقه في أول رسالة لأي جلسة جديدة.

## 1. المشروع في سطور

- **الاسم:** ء-حماية / e-Himaya. منظومة ذكية للتبليغ والمشاركة المجتمعية والمؤسساتية في الوقاية والسلامة وإدارة
  المخاطر، من التبليغ إلى أخذ القرار، للديوان الوطني للحماية المدنية بتونس. وهو أيضا مشروع تخرج (ماجستير) ليامن.
- **المستودع:** `github.com/mouhabouk/E-HIMAYA` (كان سابقا عند `YaamenMegdiche/E-HIMAYA`). الفرع الرئيسي `main`.
- **فرع العمل:** `claude/project-thread-xq2ez8`. بعد كل دمج يُعاد الفرع من `main` ويُفتح طلب دمج جديد.
- **المكونات:**
  - `services/api`: الخلفية FastAPI، PostgreSQL 17 + PostGIS + pgvector، Alembic (آخر ترحيل `0097_change_journal`).
  - `apps/dashboard`: اللوحة المركزية React + Vite (العربية والفرنسية والإنجليزية).
  - `apps/portal`: بوابة المؤسسات React.
  - `apps/mobile`: تطبيق Flutter واحد فيه تطبيق المواطن وتطبيق الأعوان (الحزمة `ehimaya`).
  - `services/ai`, `services/vision`, `services/notify-sim`: الذكاء الاصطناعي المحلي، كشف الحرائق والدخان، محاكي الإشعارات.
  - `infra/`: Docker Compose، Keycloak (فضاءا `ehimaya-public` و `ehimaya-staff`)، Caddy، NATS، SeaweedFS، Asterisk، MediaMTX، Prometheus، Loki وAlloy (ملف التعريف `logs`).
  - `.github/workflows/`: CI لكل دفعة، و`release.yml` للإصدار والتوقيع والنشر (`docs/cicd.md`)، و`scripts/deploy.sh` على الخادم.
  - `docs/`: تقارير المراحل HTML، `versions.md`، `backlog.md`، `design-system.md`، مولّدات الوثائق في `docs/deliverables`.

## 2. القواعد الدائمة (من يامن)

1. الردود على يامن **بالعربية**، جمل كاملة، مختصرة، تبدأ بالنتيجة.
2. كل واجهة تتبع `docs/design-system.md`.
3. في نهاية كل مرحلة (لا بعد كل عنصر) تُحدَّث معا، كما في `docs/phase-end.md`: مرجع التصميم، مخططات UML، الملف الوصفي
   (كراس الشروط)، العرض الرسمي، ثم تقرير HTML واحد للمرحلة و `docs/versions.md`.
4. كل محاكاة تحمل الشارة الكهرمانية **[SIM]**.
5. **لا دمج أبدا**: يامن يدمج بنفسه.
6. **ظهور المستودع:** لا يغيّره Claude أبدا. يقول ليامن حرفيا «**اجعل الجيت هيب عام**» قبل الدفع أو حين يحتاج CI،
   و«**اجعل الجيت هيب خاص**» بعد الدمج حين لا يحتاج شيء إلى CI.
7. ملفات الديوان الخام (SNACR والأرقام المجمّعة لأريانة) لا تُودَع في المستودع ولا تُنشر أبدا.
8. لا ذكر لمعرّف النموذج في الإيداعات وطلبات الدمج.
9. الحدود الثابتة للصلاحيات (قرار يامن، أكّده في المرحلة G):
   - الحسابات التقنية بلا صلاحيات تشغيلية؛
   - الوالي والوزير لا يريان المعطيات الشخصية؛
   - الخصائص الوطنية لا تُمنح لحساب جهوي.

## 3. أين وصل العمل

| المرحلة | المحتوى | الحالة |
|---|---|---|
| 1 إلى 10، ثم P2..P5، UI، L1..L5، R، PL، M، N، S، S2، F، D، AI5 | المنظومة كاملة (التفاصيل في `docs/versions.md` البنود 1 إلى 40 وتقارير المراحل) | مدمجة |
| خطة المراحل الخمس (1 إلى 3، T، G) | الدراسات، الوثائق والأمن، صلاحيات المدير على كل الأسطح | مدمجة |
| ما بعد G (البنود 43 إلى 50) | كشف النار على مرحلتين، جسر الكاميرات الحرارية، الصوت في كل مرحلة، فصل الوقاية عن القاعة، إصلاحات التنصيب | مدمجة (#158 إلى #174) |
| H1 | فضاء التصرف في الأفراد: الملف الإداري، الغيابات، الموجود العام، دور `personnel_officer` (الترحيل 0096) | مدمجة (#175) |
| H5 وCI/CD | السجلات (Loki وAlloy، نافذة «سجلات المنظومة»)، سجل التغييرات mouchard (`audit.change`، الترحيل 0097، نافذة مدير النظام وقسم مدير المؤسسة في البوابة)، الإصدار الموقّع والنشر بالرجوع الآلي، شاشة الدخول (كحلي وذهبي، الشعار فقاعات) | **طلب الدمج #176 مفتوح، بانتظار CI ودمج يامن** |
| H2 إلى H4 | برامج التوزيع، نافذة الوضعيات واقتراح التدخل، برنامج العون في التطبيق والتقارير (`docs/phase-h/design-h.md` §8) | معتمدة، لم تبدأ |

### طلب الدمج #176 بالتفصيل (للمتابعة)

- **الخلفية:** `app/modules/syslogs/router.py` (وكيل Loki، الاستعلام يبنيه الخادم)، `app/modules/audit/journal.py`
  (`EXCLUDED`، المسارات `/admin/changes` و`/orgs/{id}/changes`)، `app/core/db.py` (`ehimaya.actor` و`request_id` لكل
  معاملة)، `app/main.py` (سطر `http.request`)، الترحيل `0097_change_journal`، الاختبارات `test_change_journal.py` و`test_syslogs.py`.
- **اللوحة والبوابة:** `pages/SystemLogsPage.tsx` و`pages/ChangesPage.tsx` و`lib/systemApi.ts`؛ وفي البوابة `pages/org/ChangesTab.tsx`.
- **البنية:** `infra/logging/`، `infra/compose.prod.yml` (loki وalloy)، `infra/compose.release.yml`، `.github/workflows/release.yml`،
  `scripts/deploy.sh`، سمة الدخول `infra/keycloak/themes/ehimaya/login/` (الخلفية يولّدها `scripts/login_bubbles.py`).
- **الوثائق:** `docs/phase-h/design-h5.md`، `docs/cicd.md`، `versions.md` 52، الملف الوصفي V35، النموذج العلائقي (227 جدولا).
- **ما بقي:** متابعة CI حتى يخضرّ، ثم قول «اجعل الجيت هيب خاص» بعد الدمج؛ ثم H2.

## 4. الخيوط في المشروع

| الخيط | الموضوع | الحالة |
|---|---|---|
| قراءة وصف مشروع ء-حماية | المراحل الأولى من 1 إلى 8 | منتهٍ |
| الصلاحيات والتصليب الأمني | المراحل 9 و10 وما بعدها حتى L5 | منتهٍ |
| Make Arabic promo video | فيديو ترويجي بالعربية | بانتظار المراجعة |
| Compare e-Himaya to similar platforms | مقارنة دولية | ينتظر يامن |
| تدريب ذاتي على نصوص البلاغات | AI5 | منتهٍ |
| بناء مساعد القرار الذكي المحلي | AI5 | منتهٍ |
| مراجعة الملاحظات قبل التنفيذ | خطة المراحل الخمس، المرحلتان 1 و2 | منتهٍ |
| تصميم شعار ء-حماية الرسمي | الشعار | ينتظر يامن |
| إكمال المرحلة 3 | المرحلة 3 | منتهٍ |
| إنجاز المرحلة 4: الوثائق والأمن | T و G، ثم H1 والسجلات وسجل التغييرات وCI/CD وشاشة الدخول | جارٍ (#176) |

## 5. تشغيل البيئة من الصفر (جلسة سحابية جديدة)

```bash
# قاعدة البيانات
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/pgd -l /tmp/pgd.log start"   # أو initdb إن لم توجد
# المستخدم ehimaya/ehimaya على localhost:5432، الامتداد postgis
cd services/api && uv sync   # أو python -m venv .venv && pip install -e .[dev]
export DATABASE_URL=postgresql+asyncpg://ehimaya:ehimaya@localhost:5432/ehimaya \
  ANON_PSEUDONYM_SECRET=ci-only-secret-ci-only-secret-ci-only-01 \
  FIELD_ENCRYPTION_KEY=Y2ktb25seS1rZXktY2ktb25seS1rZXktY2ktb25seTE= DB_RUNTIME_ROLE=ehimaya_app PYTHONPATH=.
.venv/bin/alembic upgrade head
.venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
.venv/bin/python -m app.openapi && .venv/bin/python -m app.erd        # يُعاد توليدهما عند تغيير المسارات أو الجداول
python3 ../../scripts/guide_seed.py --check && python3 ../../scripts/traceability.py --check

# اللوحة والبوابة
cd apps/dashboard && npm ci && npx tsc -b --noEmit && npx eslint . --max-warnings=0 && npx vitest run
cd apps/portal    && npm ci && npx tsc -b --noEmit && npx eslint . --max-warnings=0 && npx vitest run

# الهاتف (Flutter 3.47.7)
export PATH=/opt/flutterdl/flutter/bin:$PATH FLUTTER_SUPPRESS_ANALYTICS=true
cd apps/mobile && flutter pub get && dart format lib test && flutter analyze && flutter test
```

- محليا تفشل نحو 34 اختبارا في الخلفية حتى على `main` دون تعديل (بيئة محلية)؛ CI على GitHub هو المرجع.
- المولّدات: `docs/deliverables/*/build.js` تحتاج `npm install` في `docs/deliverables`؛ العرض يحتاج
  `NODE_PATH=docs/deliverables/node_modules PPTX_SKILL=/mnt/skills/public/pptx`؛ PDF بـ LibreOffice؛ UML بـ PlantUML؛
  النموذج العلائقي بـ Graphviz.
- النسخة دون إنترنت تُعاد بـ `python3 scripts/offline_archive.py` (انظر رأس الملف).

## 6. طريقة العمل المعتمدة

1. قائمة تقدم ظاهرة ليامن، تُحدَّث عند كل خطوة.
2. كل طلب تغيير: فرع العمل، اختبارات، إيداع بالتذييل المعتاد، دفع، طلب دمج جديد جاهز (لا مسودة)، متابعة CI وإصلاحه.
3. رأس كل طلب دمج:
   ```
   <!-- claude-projects-attribution: {"github_login":"YaamenMegdiche"} -->
   _Requested by **Yamen** · [project thread](https://claude.ai/code/project/chan_01K8PVgA29b9BXXWAr9DkJPY?thread=cmsg_01K8PVgA29b9BXXWAr9DkJPYRofE2udKkNXrwecxJM2JCt)_
   ```
4. القرارات التي تغيّر الهدف تُعرض على يامن بخيارات وتوصية؛ ما يمكن التراجع عنه يُنفَّذ ويُذكر.
5. التسليمات في ملفات المشروع (`/mnt/project-files/`) بمجلد لكل مرحلة، وتُرفق في الرد.

## 7. نص البداية لجلسة جديدة

> أنت تواصل مشروع ء-حماية (e-Himaya) في المستودع mouhabouk/E-HIMAYA على الفرع claude/project-thread-xq2ez8.
> اقرأ أولا `docs/handoff/resume.md` ثم `CLAUDE.md` و `docs/phase-end.md` و `docs/phase-h/design-h.md` و
> `docs/phase-h/design-h5.md` و `docs/cicd.md`. التزم بالقواعد الدائمة في القسم 2 من الحوصلة، ورد عليّ بالعربية. آخر ما
> أُنجز: السجلات وسجل التغييرات وCI/CD وشاشة الدخول (طلب الدمج #176). المطلوب الآن: [اكتب طلبك هنا].
