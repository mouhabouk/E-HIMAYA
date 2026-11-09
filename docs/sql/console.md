# نافذة SQL لمدير النظام

طلب يامن 2026-11-09: نافذة في لوحة القيادة تحاكي برنامج إدارة قواعد البيانات (SGBD)، فيها بيانات الاتصال، ومربع
لكتابة الاستعلام، والنتيجة في جدول تحته، وتصديرها إلى صيغ مختلفة. اختار يامن **القراءة فقط** (الخيار A)، مع **سجل
لكل استعلام** يعدّله صاحبه أو يحذفه.

المسار: `/sql` في لوحة القيادة (قسم «المنظومة»، أيقونة قاعدة البيانات). الواجهة: `/api/v1/admin/sql/...`
(`services/api/app/modules/sqlconsole/`).

## 1. من يفتحها

مدير النظام (`sysadmin`) ذو النطاق الوطني فقط. مسؤول الأمن يقرأ سجل التدقيق وسجل التغييرات، لا المعطيات نفسها.
يمكن إخفاء الصفحة من «إعدادات المنصة» (المفتاح `sql_console`) أو إيقافها كليا من الخادم بـ `SQL_CONSOLE_ENABLED=false`.

## 2. ما تفعله النافذة

| الجزء | الوصف |
|---|---|
| الاتصال | اختيار قاعدة من القواعد المضبوطة في الخادم، وعرض الخادم والمنفذ واسم القاعدة والمستخدم وSSL. كلمة السر لا تصل إلى المتصفح. «اختبار الاتصال» يعرض الإصدار والدور والحجم وزمن الاستجابة، وينبّه إن كان الدور يملك حق الكتابة. |
| الجداول | شجرة المخططات والجداول والعروض وأعمدتها مع أنواعها وعدد الأسطر التقريبي. نقرة على جدول تعرض أول 100 سطر منه في النتيجة (طلب يامن 2026-11-09)، ونقرة على عمود تضيف اسمه في المربع. |
| الفلترة | فوق النتيجة: بحث عن عمود بالاسم (تُخفى الأعمدة الأخرى). تحت اسم كل عمود: مربع فلترة (يحتوي النص، و`NULL` للخانات الفارغة). نقرة على اسم العمود ترتّب تصاعديا ثم تنازليا. الفلترة والترتيب يعملان على الأسطر المعروضة؛ وعند عرض جدول، «طبّق على كامل الجدول» يكتب `WHERE عمود::text ILIKE '%…%'` و`ORDER BY` ويشغّلهما في القاعدة على الجدول كله. |
| المربع | كتابة الاستعلام مع ترقيم الأسطر. `Ctrl+Enter` ينفّذ الأمر الذي فيه المؤشر (أو النص المحدَّد). «خطة التنفيذ» يضيف `EXPLAIN`. «جاهزة (56)» تفتح استعلامات `docs/sql/01-queries.sql` مصنفة بأقسامها. |
| النتيجة | جدول بأسماء الأعمدة وأنواعها، وNULL ظاهر، وصفحات من 50 سطرا، وعدد الأسطر والمدة. الخطأ يُعرض كما أرسلته القاعدة مع رمز SQLSTATE والسطر والعمود. |
| التصدير | Excel (ورقتان: النتيجة والاستعلام، من اليمين إلى اليسار)، CSV (UTF-8 مع BOM ليقرأ Excel العربية)، JSON، أوامر SQL INSERT، HTML، Markdown، ونسخ إلى الحافظة. التصدير يعيد التشغيل حتى حد التصدير. الخلايا التي تبدأ بـ `=` أو `+` أو `-` أو `@` تُحفظ نصا (حماية من حقن الصيغ). |
| السجل | كل استعلام يشغّله المدير، ناجحا أو مرفوضا، يُحفظ في `platform.sql_query`: النص، والاتصال، ونتيجة آخر تشغيل، وعدد مرات التشغيل (النص نفسه على الاتصال نفسه سطر واحد يزيد عدّاده). يرى كل مدير سجله وحده، فيسمّي الاستعلام، أو يثبّته، أو يعيد تشغيله، أو يحفظ فيه نص المربع، أو يحذفه. تبويبات: الكل، المثبّتة، الأخطاء، مع بحث. |

## 3. لماذا هي للقراءة فقط، وكيف

1. **أمر واحد في كل تشغيل.** يُحضَّر النص بـ `prepare` في asyncpg، وPostgreSQL يرفض تحضير أكثر من أمر.
2. **الكلمة الأولى** يجب أن تكون `SELECT` أو `WITH` أو `EXPLAIN` أو `SHOW` أو `VALUES` أو `TABLE`. يُرفض قبل
   الوصول إلى القاعدة كل ما سواها (INSERT، UPDATE، DELETE، DDL، COPY، SET، CALL، DO، BEGIN...)، و`EXPLAIN ANALYZE`
   على أمر كتابة، والدوال التي تؤثر في الخادم ولو في معاملة للقراءة (`pg_terminate_backend`، `set_config`،
   `pg_read_file`، `lo_*`، `dblink`، `pg_advisory_*`...).
3. **معاملة READ ONLY** (`default_transaction_read_only=on` أيضا) تُلغى دائما بـ ROLLBACK، فـ `WITH x AS (DELETE ...)`
   و`nextval()` يرفضهما PostgreSQL نفسه.
4. **حدود:** `statement_timeout` (15 ثانية افتراضيا)، `lock_timeout` ثانيتان، 1000 سطر في النافذة و50000 في
   التصدير. كل استعلام يفتح اتصالا خاصا به (لا يستعمل مجمّع اتصالات الواجهة) باسم التطبيق `ehimaya-sql-console`.
5. **أمان الصفوف (RLS):** تقرأ النافذة بالنطاق الوطني لمديرها (`ehimaya.scope=national`)، كما تقرأ الواجهة.
6. **الأعمدة المشفّرة** (`*_enc`) تظهر بايتات مختصرة: مفتاح فك التشفير عند الواجهة لا في القاعدة.
7. **التدقيق:** كل تشغيل وكل تصدير وكل اختبار اتصال يُكتب في `audit.log` (السلسلة المقفلة) مع نص الاستعلام
   (`sql_console.query`، `sql_console.export`، `sql_console.test`). حذف سطر من السجل الشخصي لا يمسّ سجل التدقيق.

الحارس الحقيقي هو **دور لا يملك إلا SELECT**. بدون إعداد، تستعمل النافذة اتصال الواجهة (`DATABASE_URL`، الدور
`ehimaya_app`)، وهو دور يملك حق الكتابة تحميه البنود 1 إلى 4. في الإنتاج يُنصح بدور خاص:

```sql
-- بصلاحيات المالك أو مدير PostgreSQL، مرة واحدة:
CREATE ROLE ehimaya_console LOGIN PASSWORD '...' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT CONNECT ON DATABASE ehimaya TO ehimaya_console;
DO $$ DECLARE s text; BEGIN
  FOR s IN SELECT nspname FROM pg_namespace
           WHERE nspname NOT LIKE 'pg\_%' AND nspname NOT IN ('information_schema') LOOP
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO ehimaya_console', s);
    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO ehimaya_console', s);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE ehimaya IN SCHEMA %I GRANT SELECT ON TABLES TO ehimaya_console', s);
  END LOOP;
END $$;
-- سياسات أمان الصفوف معرّفة لكل الأدوار (TO public)، فيقرأ الدور الجديد بالشروط نفسها التي يقرأ بها دور التشغيل.
```

ثم يُضبط في `.env` الخادم:

```
SQL_CONSOLE_TARGETS=main=postgresql://ehimaya_console:...@postgres:5432/ehimaya?sslmode=disable
```

وعندها يعرض «اختبار الاتصال» «دور للقراءة فقط».

## 4. الإعدادات (الخادم)

| المتغير | الافتراضي | المعنى |
|---|---|---|
| `SQL_CONSOLE_ENABLED` | `true` | إيقاف النافذة كليا (503). |
| `SQL_CONSOLE_TARGETS` | فارغ: `main` على `DATABASE_URL` | قائمة مفصولة بفواصل: `الاسم=postgresql://مستخدم:كلمة@خادم:منفذ/قاعدة?sslmode=...`. الاسم: حروف لاتينية صغيرة وأرقام و`-` و`_`. القواعد المضبوطة فقط تُفتح (لا يكتب المدير عنوانا من المتصفح). |
| `SQL_CONSOLE_TIMEOUT_S` | `15` | المهلة القصوى لاستعلام (1 إلى 300). |
| `SQL_CONSOLE_MAX_ROWS` | `1000` | الأسطر المعروضة في النافذة (10 إلى 10000). |
| `SQL_CONSOLE_EXPORT_MAX_ROWS` | `50000` | الأسطر في ملف التصدير (100 إلى 500000). |

## 5. الواجهة البرمجية

| الطلب | المعنى |
|---|---|
| `GET /api/v1/admin/sql/connections` | الاتصالات المضبوطة وحدودها (بلا كلمة سر). |
| `POST /api/v1/admin/sql/connections/{name}/test` | اختبار الاتصال. |
| `GET /api/v1/admin/sql/connections/{name}/schema` | شجرة المخططات والجداول والأعمدة. |
| `GET /api/v1/admin/sql/examples` | الاستعلامات الجاهزة Q01 إلى Q56 (نسخة `01-queries.sql` في `app/modules/sqlconsole/examples.sql`، واختبار يتحقق من تطابقهما). |
| `POST /api/v1/admin/sql/query` | `{connection, sql, max_rows?}` ← الأعمدة والأسطر والمدة. الرفض 422 مع `{code, message, position}`. |
| `POST /api/v1/admin/sql/export` | `{connection, sql, format}` و`format` من `xlsx csv json sql html md` ← ملف. |
| `GET /api/v1/admin/sql/history?q=&only=pinned\|errors` | سجل المدير. |
| `PATCH /api/v1/admin/sql/history/{id}` | `{title?, sql?, pinned?}`؛ 409 إن وُجد النص نفسه في سطر آخر. |
| `DELETE /api/v1/admin/sql/history/{id}` | حذف سطر من السجل. |

الترحيل `0098_sql_console` ينشئ `platform.sql_query`، وهو خارج سجل التغييرات (دفتر شخصي، وسجل التدقيق يحفظ كل تشغيل).
الاختبارات: `services/api/tests/test_sql_console.py` (منها تشغيل الاستعلامات الجاهزة الستة والخمسين كلها داخل
النافذة) و`apps/dashboard/src/pages/SqlConsole.test.tsx`.
