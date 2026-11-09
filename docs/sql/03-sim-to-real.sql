-- =====================================================================================================================
-- ء-حماية / e-Himaya: طلبات تحويل المعطيات التجريبية [SIM] إلى معطيات حقيقية
-- =====================================================================================================================
-- كل طلب هنا (R01...R20) مرتبط بسطر في الجدول التفصيلي docs/sql/sim-inventory.md، الذي يقول أين يظهر الوسم [SIM] في
-- الواجهات، ولماذا هو تجريبي، وما المعطى الحقيقي المطلوب ومن يقدّمه. الوسوم التي لا تزول بـ SQL بل بإعداد
-- (متغير بيئة، مفتاح، خدمة) مذكورة في الجدول نفسه بعمود «الإعداد».
--
-- قواعد الاستعمال:
--   1. الملف داخل معاملة واحدة وينتهي بـ ROLLBACK افتراضيا (تجربة جافة تتحقق من كل طلب). للحفظ:
--          psql "$MIGRATION_DATABASE_URL" -v commit=1 -f docs/sql/03-sim-to-real.sql
--      ويمكن تشغيل طلب واحد بنسخه مع كتلة I0 (هوية الفاعل) بين BEGIN وCOMMIT.
--   2. لا يُحوَّل وسم [SIM] إلى حقيقي إلا بمعطى حقيقي وصل فعلا (قائمة رسمية، مصادقة، ملف الديوان). الطلبات التي تنزع
--      العلامة مشروطة بوجود هذا المعطى (WHERE EXISTS ...)، فلا تنزعها عن معطى ما زال مخترعا.
--   3. كتل VALUES المعلَّمة «◀ القيم» تُملأ بالمعطى الرسمي؛ الأسطر الموجودة فيها أمثلة على الصيغة فقط.
--   4. كل تغيير يُسجَّل في audit.change باسم الفاعل (I0)، وسطر في audit.log المقفل في النهاية.
-- =====================================================================================================================

\set ON_ERROR_STOP on
\if :{?commit}
\else
  \set commit 0
\endif

BEGIN;

-- I0 · هوية من يحوّل (تُقرأ في سجل التغييرات). ◀ القيم: المعرّف والاسم.
SELECT set_config('ehimaya.actor',      'sql-import:data-officer', true),
       set_config('ehimaya.actor_name', 'مكلّف إدخال المعطيات',    true),
       set_config('ehimaya.scope',      'national',                true),
       set_config('ehimaya.request_id', 'sim-to-real-' || to_char(now(), 'YYYYMMDD-HH24MISS'), true);

-- الوضع قبل التحويل (للمقارنة مع الفحص في آخر الملف)
\echo '== قبل التحويل =='
SELECT 'geo.layer' AS t, count(*) FILTER (WHERE simulated) AS sim FROM geo.layer WHERE deleted_at IS NULL
UNION ALL SELECT 'ops.report_template', count(*) FILTER (WHERE simulated AND status = 'approved') FROM ops.report_template
UNION ALL SELECT 'snacr.special_risk', count(*) FILTER (WHERE simulated) FROM snacr.special_risk
UNION ALL SELECT 'snacr.dataset', count(*) FILTER (WHERE simulated) FROM snacr.dataset
UNION ALL SELECT 'content.guide_item', count(*) FILTER (WHERE validated_at IS NULL AND NOT hidden) FROM content.guide_item;

-- =====================================================================================================================
-- R01 · طبقات الأماكن التقريبية [SIM] ← القوائم الرسمية
-- يزيل: الوسم [SIM] «بيانات تقريبية للتجربة» على طبقات المستشفيات، ومراكز الصحة الأساسية، والصيدليات، ومراكز الأمن،
--        والحرس الوطني (data/sim-layers)، في لوحة القيادة (الطبقات، الخريطة، «أقرب المستشفيات») وفي التطبيق
--        («الأقرب إليّ»، شريحة «[SIM] تجربة»، و«[SIM]» بجانب المستشفى في تطبيق الأعوان).
-- الشرط: أن تكون القائمة الرسمية قد أُدرجت في الطبقة نفسها (الطلب I7 في 02-inserts.sql، أو «استيراد» في لوحة القيادة
--        بوضع الاستبدال). الطلب: (أ) يحذف حذفا ليّنا كل مكان [SIM] متبقٍّ في كل طبقة تحمل الآن مكانا رسميا واحدا على
--        الأقل؛ (ب) ينزع علامة simulated وto_verify عن هذه الطبقات فقط، ويرفع رقم نسختها.
-- =====================================================================================================================
WITH real_layers AS (
    SELECT l.id
    FROM geo.layer l
    WHERE l.simulated AND l.deleted_at IS NULL
      AND EXISTS (SELECT 1 FROM geo.layer_feature f
                  WHERE f.layer_id = l.id AND f.deleted_at IS NULL AND f.name NOT LIKE '[SIM]%')
), gone AS (
    UPDATE geo.layer_feature f
    SET deleted_at = now(), deleted_by = current_setting('ehimaya.actor'),
        delete_reason = 'حل محله المكان الرسمي (تحويل [SIM])', version = f.version + 1, updated_at = now()
    FROM real_layers rl
    WHERE f.layer_id = rl.id AND f.deleted_at IS NULL AND f.name LIKE '[SIM]%'
    RETURNING f.layer_id
)
UPDATE geo.layer l
SET simulated = false, to_verify = false, version = l.version + 1, data_version = l.data_version + 1,
    updated_by = current_setting('ehimaya.actor'), updated_by_name = current_setting('ehimaya.actor_name'), updated_at = now()
FROM real_layers rl
WHERE l.id = rl.id;

-- =====================================================================================================================
-- R02 · قوالب التقرير الميداني النموذجية [SIM] ← قوالب يصادق عليها الديوان
-- يزيل: «[SIM] قالب نموذجي إلى أن يصادق عليه الديوان» في تطبيق الأعوان، و[SIM] في «قوالب التقارير» بلوحة القيادة.
-- الطلب: لكل صنف، نسخة جديدة معتمدة (version + 1، simulated = false) بالأسئلة التي صادق عليها الديوان، ثم سحب
--        النسخة النموذجية (retired). التقارير القديمة تحتفظ بالنسخة التي أجابت عنها.
-- ◀ القيم: (الصنف، أسئلة القالب JSON كما صادق عليها الديوان، أو NULL = صادق على النموذج كما هو دون تغيير، اسم المصادِق)
-- =====================================================================================================================
CREATE TEMP TABLE approved_templates (category text PRIMARY KEY, fields jsonb, approved_by_name text NOT NULL) ON COMMIT DROP;
INSERT INTO approved_templates VALUES
    ('fire', NULL, 'مثال: مدير الوقاية بالديوان الوطني للحماية المدنية');

-- (1) سحب النسخة النموذجية أولا: القيد ux_report_template_approved يسمح بنسخة معتمدة واحدة لكل صنف.
CREATE TEMP TABLE retired_templates ON COMMIT DROP AS
WITH r AS (
    UPDATE ops.report_template t
    SET status = 'retired', retired_at = now(), updated_at = now()
    FROM approved_templates a
    WHERE a.category = t.category AND t.status = 'approved' AND t.simulated AND t.classification IS NULL
    RETURNING t.category, t.classification, t.version, t.fields, a.fields AS new_fields, a.approved_by_name
)
SELECT * FROM r;

-- (2) النسخة المعتمدة الجديدة، غير تجريبية.
INSERT INTO ops.report_template (category, classification, version, status, fields, simulated, created_by,
                                 created_by_name, approved_by, approved_by_name, approved_at)
SELECT r.category, r.classification,
       (SELECT max(version) + 1 FROM ops.report_template x
        WHERE x.category = r.category AND x.classification IS NOT DISTINCT FROM r.classification),
       'approved', coalesce(r.new_fields, r.fields), false,
       current_setting('ehimaya.actor'), current_setting('ehimaya.actor_name'),
       current_setting('ehimaya.actor'), r.approved_by_name, now()
FROM retired_templates r;

-- =====================================================================================================================
-- R03 · سجل المخاطر الخاصة الأولي [SIM] ← تقدير اللجان الجهوية
-- يزيل: [SIM] بجانب كل خطر في «SNACR ← المخاطر الخاصة» وفي الدراسة المصدّرة.
-- الطلب: تحديث الاحتمال والخطورة (1 إلى 5) والملاحظة لكل (ولاية، خطر) كما قدّرتها اللجنة، وsimulated = false.
--        خطر لم يكن في السجل يُضاف (ON CONFLICT على المفتاح الفريد gouvernorat_code + hazard).
-- ◀ القيم: (رمز الولاية، الخطر، الاحتمال، الخطورة، الملاحظة/مرجع محضر اللجنة)
-- =====================================================================================================================
INSERT INTO snacr.special_risk (gouvernorat_code, hazard, probability, gravity, note, simulated, updated_by, updated_by_name)
SELECT v.g, v.hazard, v.p, v.gr, v.note, false, current_setting('ehimaya.actor'), current_setting('ehimaya.actor_name')
FROM (VALUES
    (21::smallint, 'forest_fire', 4::smallint, 4::smallint, 'مثال: محضر اللجنة الجهوية لمجابهة الكوارث، الجلسة رقم ...')
) AS v(g, hazard, p, gr, note)
ON CONFLICT (gouvernorat_code, hazard) DO UPDATE
SET probability = EXCLUDED.probability, gravity = EXCLUDED.gravity, note = EXCLUDED.note, simulated = false,
    updated_by = EXCLUDED.updated_by, updated_by_name = EXCLUDED.updated_by_name, updated_at = now();

-- =====================================================================================================================
-- R04 · سنوات أرشيف التدخلات المولَّدة [SIM] ← ملفات الديوان
-- يزيل: «[SIM] جزء من المعطيات تجريبي» في دراسة SNACR وتصديرها، و[SIM] بجانب السنة في «جودة المعطيات».
-- الطلب: (أ) إدخال سنة الديوان يتم بالطلب I12 في 02-inserts.sql (أو استيراد لوحة القيادة) الذي يحذف السنة [SIM] نفسها
--        أولا؛ (ب) هنا: أرشفة الدراسات الجارية المبنية على سنوات [SIM] (تبقى للتاريخ، وتُعاد الدراسة من لوحة القيادة على
--        السنوات الحقيقية)، وحذف مسودات المخططات [SIM]، وجعل المخططات المعتمدة [SIM] «مستبدلة».
--        الشرط: ألا تبقى في الأرشيف أي سنة [SIM].
-- =====================================================================================================================
UPDATE snacr.study s
SET status = 'archived', archived_at = now()
WHERE s.simulated AND s.status = 'current'
  AND NOT EXISTS (SELECT 1 FROM snacr.dataset d WHERE d.simulated);

DELETE FROM snacr.plan p
WHERE p.simulated AND p.status = 'draft'
  AND NOT EXISTS (SELECT 1 FROM snacr.dataset d WHERE d.simulated);

UPDATE snacr.plan p
SET status = 'superseded'
WHERE p.simulated AND p.status = 'approved'
  AND NOT EXISTS (SELECT 1 FROM snacr.dataset d WHERE d.simulated);

-- =====================================================================================================================
-- R05 · دليل الطوارئ (الإسعافات الأولية) في انتظار المصادقة الطبية [SIM] ← مصادقة الإطار الطبي
-- يزيل: الشريط «[SIM] محتوى في انتظار المصادقة من الإطار الطبي للحماية المدنية» ووسم «[SIM] في انتظار المصادقة
--        الطبية» في التطبيق، و«في انتظار المصادقة» في «دليل الطوارئ» بلوحة القيادة.
-- الطلب: لكل بند صادق عليه الطبيب (بمعرّفه)، تسجيل اسم المصادِق وتاريخ المصادقة ورفع رقم النسخة. البند الذي يتغير نصه
--        لاحقا يعود غير مصادق تلقائيا (يفعلها التطبيق).
-- ◀ القيم: (مفتاح الموضوع أو NULL لكل المواضيع، المصادِق: «د. الاسم، الإدارة الطبية»)
-- =====================================================================================================================
CREATE TEMP TABLE medical_validation (topic_key text, validated_by text NOT NULL) ON COMMIT DROP;
INSERT INTO medical_validation VALUES ('bleeding', 'مثال: د. ...، الإدارة الطبية للحماية المدنية');

UPDATE content.guide_item i
SET validated_by = mv.validated_by, validated_at = now(), version = i.version + 1,
    updated_by = current_setting('ehimaya.actor'), updated_at = now()
FROM content.guide_topic t, medical_validation mv
WHERE i.topic_id = t.id
  AND (mv.topic_key IS NULL OR t.key = mv.topic_key)
  AND i.validated_at IS NULL;

-- =====================================================================================================================
-- R06 · الطقس المحاكى [SIM] ← Open-Meteo / المعهد الوطني للرصد الجوي
-- يزيل: الشريط «وضع المحاكاة» في بطاقة الطقس (التطبيق ولوحة القيادة)، و[SIM] على اقتراحات التنبيه، وفي التوقع
--        (انتشار الحريق/الفيضان) وفي اقتراحات الجدولة.
-- الإعداد أولا: WEATHER_PROVIDER=open-meteo (APP_ENV=production يرفض sim). ثم الطلب: حذف القراءات المحاكاة، وإعادة كل
--        نقطة شبكة إلى «جلب فوري» (next_fetch_at = now()) لتملأها الخدمة بمعطى حقيقي وتنزع العلامة بنفسها، وإنهاء
--        اقتراحات التنبيه المعلّقة المبنية على طقس محاكى.
-- =====================================================================================================================
DELETE FROM weather.observation o
USING weather.grid_point p
WHERE o.point_id = p.id AND p.simulated;

UPDATE weather.grid_point
SET next_fetch_at = now(), attempts = 0
WHERE simulated;

UPDATE weather.alert_suggestion
SET status = 'expired', updated_at = now()
WHERE simulated AND status = 'pending';

-- =====================================================================================================================
-- R07 · الطقس البحري المحاكى للشواطئ [SIM] ← Open-Meteo Marine
-- يزيل: «[SIM] طقس بحري تجريبي» في صفحة الشواطئ بالتطبيق، و[SIM] في «السلامة الساحلية» بلوحة القيادة.
-- الإعداد: WEATHER_PROVIDER=open-meteo (الخدمة نفسها). الطلب: حذف الساعات البحرية وأيام الشواطئ المستقبلية المحسوبة على
--        بحر محاكى، وإغلاق تنبيهات الشواطئ المحاكاة غير المعالجة، وإعادة الشواطئ إلى «جلب فوري».
-- =====================================================================================================================
DELETE FROM coastal.marine_hour m
USING coastal.beach b
WHERE m.feature_id = b.feature_id AND b.simulated;

DELETE FROM coastal.beach_day
WHERE simulated AND day >= current_date;

UPDATE coastal.alert
SET acked_by = current_setting('ehimaya.actor'), acked_by_name = 'إغلاق آلي: تنبيه على طقس بحري محاكى', acked_at = now()
WHERE simulated AND acked_at IS NULL;

UPDATE coastal.beach
SET next_fetch_at = now(), attempts = 0
WHERE simulated;

-- =====================================================================================================================
-- R08 · نموذج خطر الغرق «في الظل» المدرَّب على أيام [SIM] ← سجل غرق حقيقي (لا يزول بـ SQL الآن)
-- يبقى: [SIM] في «بطاقات النماذج» و«السلامة الساحلية». لا يُحوَّل إلا بتدريب جديد على حوادث غرق حقيقية لكل شاطئ ويوم.
-- الطلب: فحص جاهزية المعطى فقط: كم تدخل غرق مغلق له موقع وتاريخ، وكم شاطئا ويوما يغطي. التدريب من «بطاقات النماذج».
-- =====================================================================================================================
SELECT count(*) AS closed_drownings,
       count(DISTINCT (opened_at AT TIME ZONE 'Africa/Tunis')::date) AS distinct_days,
       min(opened_at) AS since
FROM ops.incident
WHERE category = 'drowning' AND status = 'closed' AND centroid IS NOT NULL;

-- =====================================================================================================================
-- R09 · المستشعرات المحاكاة [SIM] ← أجهزة مركّبة في الميدان
-- يزيل: [SIM] بجانب اسم المستشعر في «المستشعرات» والخريطة، وعلى الإنذارات الناتجة عنه.
-- الطلب: المستشعر الحقيقي يُسجَّل من لوحة القيادة (مفتاح التوقيع يُشفَّر هناك). هنا: (أ) نزع العلامة عن مستشعر رُكّب فعلا
--        بالرمز نفسه وأرسل قراءة موقّعة خلال 24 ساعة؛ (ب) تعطيل كل مستشعر [SIM] آخر في الولاية نفسها.
-- ◀ القيم: رموز المستشعرات المركّبة ومزوّدها.
-- =====================================================================================================================
CREATE TEMP TABLE installed_sensors (code text PRIMARY KEY, provider text NOT NULL) ON COMMIT DROP;
INSERT INTO installed_sensors VALUES ('MEJ-RAIN-01', 'مثال: المعهد الوطني للرصد الجوي');

UPDATE sensor.device d
SET simulated = false, provider = s.provider, updated_at = now()
FROM installed_sensors s
WHERE d.code = s.code AND d.simulated AND d.last_at >= now() - interval '24 hours';

UPDATE sensor.device d
SET enabled = false, updated_at = now()
WHERE d.simulated AND d.enabled
  AND d.gouvernorat_code IN (SELECT gouvernorat_code FROM sensor.device x JOIN installed_sensors s ON s.code = x.code);

-- =====================================================================================================================
-- R10 · أبراج المراقبة (كاميرات الحرائق) المحاكاة [SIM] ← أبراج مركّبة
-- يزيل: [SIM] في «الأبراج» والخريطة، وعلى أحداث الدخان والنار الصادرة عنها.
-- الطلب: نزع العلامة عن برج مركّب فعلا (سجّل حدثا موقّعا خلال 7 أيام) بالرمز نفسه.
-- ◀ القيم: رموز الأبراج المركّبة.
-- =====================================================================================================================
UPDATE reports.camera_tower t
SET simulated = false, updated_at = now()
WHERE t.simulated AND t.code IN ('MEJ-TOWER-01')
  AND t.last_event_at >= now() - interval '7 days';

-- =====================================================================================================================
-- R11 · البث المرئي المحاكى (stream-sim) [SIM] ← كاميرات ودرونات حقيقية
-- يزيل: الشريط «وضع المحاكاة» و[SIM] في «البث المباشر»، وجدار البث، والأرشيف، ومعرض صور التدخل، وتنبيهات البث.
-- الإعداد: STREAM_SIM_TOKEN فارغ وإيقاف ملف compose «sim». الطلب: إنهاء كل بث محاكى ما زال قائما.
-- =====================================================================================================================
UPDATE reports.live_stream
SET status = 'ended', end_reason = 'staff_stopped', ended_at = now()
WHERE source = 'sim' AND status IN ('pending', 'live');

-- =====================================================================================================================
-- R12 · إنذارات الكاميرا المسبقة المحاكاة [SIM] ← كاميرات المؤسسات الحقيقية
-- يزيل: «[SIM] تنبيه تجريبي من كاميرا محاكاة» في تطبيق المؤسسة، و[SIM] في إنذارات القاعة.
-- الطلب: إلغاء كل إنذار محاكى ما زال معلّقا (بسبب مكتوب، كما يفرض القيد).
-- =====================================================================================================================
UPDATE org.prealert
SET state = 'cancelled', decided_at = now(), reason = 'إنذار من كاميرا محاكاة [SIM]: أُغلق عند التحويل إلى المعطيات الحقيقية'
WHERE simulated AND state = 'pending';

-- =====================================================================================================================
-- R13 · المكالمات المحاكاة (call-sim) [SIM] ← مكالمات حقيقية عبر خط المشغّل (SIP trunk)
-- يزيل: [SIM] في «المكالمات» وفي الهاتف البرمجي.
-- الإعداد: TELEPHONY_SIM_PASSWORD وTELEPHONY_SIM_TOKEN فارغان. الطلب: فصل المكالمات المحاكاة عن البلاغات والتدخلات
--        حتى لا تُحسب في الإحصاءات (الأسطر تبقى للتاريخ).
-- =====================================================================================================================
UPDATE telephony.call
SET report_id = NULL, incident_id = NULL, updated_at = now()
WHERE source = 'sim' AND (report_id IS NOT NULL OR incident_id IS NOT NULL);

-- =====================================================================================================================
-- R14 · اقتراحات القائد المحاكاة [SIM] ← اقتراحات على تدخلات حقيقية
-- يزيل: الشريط [SIM] في «مساعدة القرار» على تدخل.
-- الطلب: إنهاء (expired) كل اقتراح محاكى لم يُقرَّر فيه. الاقتراحات الجديدة على طقس وتدخلات حقيقية تكون حقيقية تلقائيا.
-- =====================================================================================================================
UPDATE decision.command_decision
SET status = 'expired', updated_at = now()
WHERE simulated AND status = 'proposed';

-- =====================================================================================================================
-- R15 · محاور الأزمة والتمارين [SIM] ← (تبقى [SIM] بطبيعتها)
-- التمارين ومحاور العرض تحمل [SIM] عمدا ولا تُحوَّل إلى حقيقية. الطلب: إغلاق محاور [SIM] المفتوحة بعد انتهاء التمرين
--        حتى لا تظهر في «لوحة القيادة العليا» بجانب المحاور الحقيقية.
-- =====================================================================================================================
UPDATE crisis.axis
SET status = 'closed', closed_by = current_setting('ehimaya.actor'), closed_by_name = current_setting('ehimaya.actor_name'),
    closed_at = now(), version = version + 1, updated_at = now()
WHERE name ~* '^\s*\[SIM\]' AND status = 'open';

-- =====================================================================================================================
-- R16 · بيانات العرض [SIM] (python -m app.demo seed) ← حذفها قبل التشغيل الحقيقي
-- يزيل: وحدات «[SIM] الإدارة الجهوية/المركز المتقدم»، ووسائل «[SIM] شاحنة إطفاء 1...»، وأعوان «[SIM] عون التدخل...»،
--        ومؤسسة «[SIM] مستودع الشركة التونسية للدهن»، وبلاغات «[SIM] قاعة العرض» وتدخلاتها.
-- الطلب: حذف بترتيب المفاتيح الأجنبية (الأبناء قبل الآباء). جداول بـ ON DELETE CASCADE (الخط الزمني، الحصيلة،
--        التقارير الميدانية...) تُحذف تلقائيا. ملاحظة: الحذف نهائي بعد COMMIT؛ جرّبه أولا بلا -v commit=1.
-- =====================================================================================================================
CREATE TEMP TABLE sim_reports ON COMMIT DROP AS
SELECT id, incident_id FROM reports.report
WHERE entered_by = 'ehimaya-staff:demo-seed' OR entered_by_name LIKE '[SIM]%';

CREATE TEMP TABLE sim_units ON COMMIT DROP AS
SELECT id FROM ops.unit WHERE name_ar LIKE '[SIM]%';

CREATE TEMP TABLE sim_resources ON COMMIT DROP AS
SELECT id FROM ops.resource WHERE label LIKE '[SIM]%' OR unit_id IN (SELECT id FROM sim_units);

CREATE TEMP TABLE sim_incidents ON COMMIT DROP AS
SELECT DISTINCT incident_id AS id FROM sim_reports WHERE incident_id IS NOT NULL
UNION
SELECT DISTINCT a.incident_id FROM ops.assignment a WHERE a.resource_id IN (SELECT id FROM sim_resources);

DELETE FROM ops.callout_target ct USING ops.assignment a
WHERE ct.assignment_id = a.id AND a.incident_id IN (SELECT id FROM sim_incidents);
DELETE FROM ops.callout WHERE incident_id IN (SELECT id FROM sim_incidents);
UPDATE reports.report SET incident_id = NULL WHERE incident_id IN (SELECT id FROM sim_incidents);
DELETE FROM ops.assignment WHERE incident_id IN (SELECT id FROM sim_incidents);
UPDATE ops.incident SET merged_into = NULL WHERE merged_into IN (SELECT id FROM sim_incidents);
DELETE FROM ops.incident WHERE id IN (SELECT id FROM sim_incidents);
DELETE FROM reports.report WHERE id IN (SELECT id FROM sim_reports);
DELETE FROM ops.shift WHERE resource_id IN (SELECT id FROM sim_resources);
DELETE FROM ops.assignment WHERE resource_id IN (SELECT id FROM sim_resources);
DELETE FROM ops.resource WHERE id IN (SELECT id FROM sim_resources);
DELETE FROM inv.stock WHERE unit_id IN (SELECT id FROM sim_units);
DELETE FROM inv.agent WHERE unit_id IN (SELECT id FROM sim_units) OR full_name LIKE '[SIM]%';
DELETE FROM inv.unit_check WHERE unit_id IN (SELECT id FROM sim_units);
DELETE FROM sched.item WHERE unit_id IN (SELECT id FROM sim_units);
DELETE FROM personnel.event WHERE unit_id IN (SELECT id FROM sim_units) OR from_unit_id IN (SELECT id FROM sim_units);
DELETE FROM inv.transfer WHERE to_unit_id IN (SELECT id FROM sim_units) OR from_unit_id IN (SELECT id FROM sim_units);
DELETE FROM ops.unit WHERE id IN (SELECT id FROM sim_units);
DELETE FROM ops.staff_device WHERE agent_id IN (SELECT id FROM ops.field_agent WHERE name LIKE '[SIM]%');
DELETE FROM ops.field_agent WHERE name LIKE '[SIM]%';
UPDATE reports.report SET organization_id = NULL WHERE organization_id IN (SELECT id FROM org.organization WHERE name LIKE '[SIM]%');
DELETE FROM org.organization WHERE name LIKE '[SIM]%';

-- =====================================================================================================================
-- R17 · الإرسال الحقيقي للرسائل القصيرة والإشعارات (notify-sim) [SIM]
-- يزيل: «[SIM] محاكاة: تذهب الرسالة إلى بوابة الاختبار» في شاشة الرمز، وشريط «وضع المحاكاة» للإشعارات.
-- الإعداد أولا: SMS_HTTP_URL/SMS_HTTP_TOKEN لمزوّد الرسائل، وFCM_SERVICE_ACCOUNT لمفتاح Firebase، وحذف خدمة notify-sim.
-- الطلب: تفعيل الإرسال الحقيقي في إعدادات المنصة (المفتاح notify.real_send_enabled، معطَّل افتراضيا).
--        لا يُفعَّل إلا بعد الإعداد: وإلا تذهب الرسائل إلى لا أحد.
-- =====================================================================================================================
UPDATE platform.setting
SET value = 'true'::jsonb, version = version + 1, updated_by = current_setting('ehimaya.actor'),
    updated_by_name = current_setting('ehimaya.actor_name'), updated_at = now()
WHERE key = 'notify.real_send_enabled' AND value <> 'true'::jsonb;

-- =====================================================================================================================
-- أثر العملية في سجل التدقيق المقفل، ثم الفحص بعد التحويل
-- =====================================================================================================================
INSERT INTO audit.log (actor, action, target, reason, details)
VALUES (current_setting('ehimaya.actor'), 'data.sim_to_real', 'docs/sql/03-sim-to-real.sql',
        'تحويل معطيات [SIM] إلى معطيات حقيقية',
        jsonb_build_object('request_id', current_setting('ehimaya.request_id')));

\echo '== ما تغيّر في هذه المعاملة =='
SELECT c.schema_name || '.' || c.table_name AS table_name, c.op, count(*) AS rows
FROM audit.change c
WHERE c.request_id = current_setting('ehimaya.request_id')
GROUP BY 1, 2
ORDER BY 1, 2;

\echo '== بعد التحويل =='
SELECT 'geo.layer' AS t, count(*) FILTER (WHERE simulated) AS sim FROM geo.layer WHERE deleted_at IS NULL
UNION ALL SELECT 'ops.report_template', count(*) FILTER (WHERE simulated AND status = 'approved') FROM ops.report_template
UNION ALL SELECT 'snacr.special_risk', count(*) FILTER (WHERE simulated) FROM snacr.special_risk
UNION ALL SELECT 'snacr.dataset', count(*) FILTER (WHERE simulated) FROM snacr.dataset
UNION ALL SELECT 'content.guide_item', count(*) FILTER (WHERE validated_at IS NULL AND NOT hidden) FROM content.guide_item;

\if :commit
  COMMIT;
  \echo 'تم الحفظ (COMMIT).'
\else
  ROLLBACK;
  \echo 'تجربة جافة: أُلغي كل شيء (ROLLBACK). للحفظ: -v commit=1'
\endif
