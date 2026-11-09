-- =====================================================================================================================
-- ء-حماية / e-Himaya: طلبات INSERT لإدخال المعطيات الحقيقية
-- =====================================================================================================================
-- الغرض: إدخال المعطيات التشغيلية الحقيقية (الوحدات، الوسائل، المخزون، البلاغات المسجّلة في القاعة، التدخلات،
-- المؤسسات، محاور الأزمة، التمارين، قوائم الأماكن الرسمية، أرشيف التدخلات) مباشرة بـ SQL، بالشكل الذي تكتبه
-- المنظومة نفسها، مع احترام كل القيود (CHECK، المفاتيح الأجنبية) وسجل التغييرات.
--
-- قواعد الاستعمال (مهمة):
--   1. الملف كله داخل معاملة واحدة، وينتهي بـ ROLLBACK افتراضيا: تشغيله العادي «تجربة جافة» تتحقق من صحة كل طلب
--      دون أن يبقى شيء في القاعدة. للحفظ الفعلي:  psql "$MIGRATION_DATABASE_URL" -v commit=1 -f docs/sql/02-inserts.sql
--   2. القيم المكتوبة هنا أمثلة واقعية الشكل (أسماء مبنية على المرجع الجغرافي الرسمي، أرقام لوحات وهواتف بصيغة
--      صحيحة) وليست معطيات رسمية. تُستبدل بقيم الديوان الوطني للحماية المدنية قبل الحفظ، في كتل VALUES المعلَّمة
--      «◀ القيم». لا يُحفظ أي مثال على أنه حقيقي.
--   3. الجغرافيا (24 ولاية، 279 معتمدية، 338 بلدية، 2083 عمادة) حقيقية ومحمّلة سلفا بالترحيلات من مصادر رسمية؛
--      الطلبات تبحث عنها بالاسم أو الرمز ولا تُدخلها.
--   4. الأعمدة المشفّرة (*_enc: نص البلاغ، الهاتف، بطاقة التعريف، مفاتيح المستشعرات والأبراج) يكتبها التطبيق وحده
--      بمفتاح FIELD_ENCRYPTION_KEY؛ لا تُملأ بـ SQL. ما يحتاجها (المستشعرات، الأبراج، الأجهزة) يُسجَّل من لوحة القيادة.
--   5. القاعدة الدائمة: لا يُدرج في المستودع ملف خام من الديوان (SNACR) ولا أرقام مجمّعة لولاية أريانة. القسم I12
--      يقرأ الملف من القرص عند التشغيل (\copy) ولا ينسخه هنا.
--   6. كل سطر يُدرج يُسجَّل في audit.change باسم الفاعل المعرّف في I0 (المُشغّل zz_journal)، ويُضاف سطر في
--      audit.log المقفل يصف عملية الإدخال (I13).
--
-- الأقسام:
--   I0  هوية من يُدخل (سجل التغييرات)
--   I1  الوحدات (إدارات جهوية، وحدات، مراكز متقدمة)           ops.unit
--   I2  الوسائل (شاحنات، إسعاف، زوارق...)                      ops.resource
--   I3  المخزون والمعدات                                        inv.stock
--   I4  حساب مواطن وملفه (مرتبط بـ Keycloak)                   identity.account / identity.profile
--   I5  بلاغ مسجَّل في القاعة (مكالمة 198) ومراحله            reports.report / reports.status_history
--   I6  تدخل، وربطه بالبلاغ، وتكليف وسيلة، والحصيلة           ops.incident / ops.assignment / ...
--   I7  قائمة رسمية لأماكن (المستشفيات) في طبقة الخريطة       geo.layer / geo.layer_feature
--   I8  مؤسسة (منشأة مصنفة)                                    org.organization
--   I9  محور أزمة ومراكز إيواء                                 crisis.axis / crisis.shelter
--   I10 تمرين مبرمج                                            drill.exercise
--   I11 متطوع معتمد                                            identity.volunteer
--   I12 أرشيف التدخلات السنوي للديوان (SNACR)                 snacr.dataset / snacr.intervention
--   I13 أثر العملية في سجل التدقيق المقفل                     audit.log
--   ثم: فحوص بعد الإدخال، وCOMMIT أو ROLLBACK.
-- =====================================================================================================================

\set ON_ERROR_STOP on
\if :{?commit}
\else
  \set commit 0
\endif

BEGIN;

-- ---------------------------------------------------------------------------------------------------------------------
-- I0 · هوية من يُدخل
-- الوصف: المُشغّل audit.journal_row يقرأ هذه الإعدادات ليكتب في audit.change من أدخل كل سطر. is_local = true:
--        تنتهي بنهاية المعاملة. ◀ القيم: معرّف المستخدم في Keycloak واسمه.
-- ---------------------------------------------------------------------------------------------------------------------
SELECT set_config('ehimaya.actor',      'sql-import:data-officer', true),
       set_config('ehimaya.actor_name', 'مكلّف إدخال المعطيات',    true),
       set_config('ehimaya.scope',      'national',                true),
       set_config('ehimaya.request_id', 'sql-import-' || to_char(now(), 'YYYYMMDD-HH24MISS'), true);

-- ---------------------------------------------------------------------------------------------------------------------
-- I1 · الوحدات
-- الوصف: إدارة جهوية (directorate)، ووحدات (unit)، ومراكز متقدمة (advanced_post). الولاية بالرمز الرسمي. الموقع:
--        إحداثيات الثكنة الفعلية إن عُرفت (lon, lat)، وإلا نقطة داخل المعتمدية (ST_PointOnSurface) مؤقتا.
--        ON CONFLICT DO NOTHING لا ينفع هنا (لا قيد فريد على الاسم)، فالطلب يتجاهل وحدة موجودة بالاسم نفسه.
-- ◀ القيم: (اسم عربي، اسم فرنسي، النوع، رمز المعتمدية، lon، lat، الهاتف)
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO ops.unit (id, name_ar, name_fr, kind, gouvernorat_code, location, phone, version, created_at, updated_at)
SELECT gen_random_uuid(), v.name_ar, v.name_fr, v.kind, d.gouvernorat_code,
       coalesce(ST_MakePoint(v.lon, v.lat), ST_PointOnSurface(d.boundary))::geography,
       v.phone, 1, now(), now()
FROM (VALUES
    ('الإدارة الجهوية للحماية المدنية بتونس', 'Direction régionale de la Protection civile de Tunis', 'directorate', 'TN-11-01', NULL::float8, NULL::float8, '+21671000000'),
    ('وحدة الحماية المدنية بقرطاج',          'Unité de la Protection civile de Carthage',            'unit',        'TN-11-03', NULL,         NULL,         '+21671000001'),
    ('وحدة الحماية المدنية بالمرسى',         'Unité de la Protection civile de La Marsa',            'unit',        'TN-11-15', NULL,         NULL,         '+21671000002'),
    ('المركز المتقدم بحلق الوادي',           'Poste avancé de La Goulette',                          'advanced_post','TN-11-14', NULL,        NULL,         NULL)
) AS v(name_ar, name_fr, kind, delegation_code, lon, lat, phone)
JOIN geo.delegation d ON d.code = v.delegation_code
WHERE NOT EXISTS (SELECT 1 FROM ops.unit u WHERE u.name_ar = v.name_ar);

-- ---------------------------------------------------------------------------------------------------------------------
-- I2 · الوسائل
-- الوصف: كل شاحنة أو سيارة إسعاف أو زورق مرتبط بوحدته (بالاسم). kind من القائمة المغلقة، category_key من فهرس
--        inv.category (يحدد الخصائص المعروضة)، code رقم اللوحة أو الرقم الداخلي، year سنة الصنع.
-- ◀ القيم: (اسم الوحدة، النوع، الفئة، التسمية، الرمز/اللوحة، السنة)
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO ops.resource (id, unit_id, kind, label, status, category_key, specs, code, year, version, created_at, updated_at, updated_by)
SELECT gen_random_uuid(), u.id, v.kind, v.label, 'available', v.category_key, '{}'::jsonb, v.code, v.year, 1, now(), now(),
       current_setting('ehimaya.actor')
FROM (VALUES
    ('وحدة الحماية المدنية بقرطاج',  'fire_engine',    'fire_engine',    'شاحنة إطفاء 1',  '1234 تونس 210', 2019::smallint),
    ('وحدة الحماية المدنية بقرطاج',  'ambulance',      'ambulance',      'سيارة إسعاف 1',  '5678 تونس 215', 2021),
    ('وحدة الحماية المدنية بالمرسى', 'fire_engine',    'fire_engine',    'شاحنة إطفاء 1',  '2345 تونس 212', 2018),
    ('وحدة الحماية المدنية بالمرسى', 'water_tanker',   'water_tanker',   'صهريج ماء 1',    '3456 تونس 208', 2016),
    ('وحدة الحماية المدنية بالمرسى', 'rescue_vehicle', 'rescue_vehicle', 'شاحنة إنقاذ 1',  '4567 تونس 219', 2022),
    ('المركز المتقدم بحلق الوادي',  'boat',           'boat',           'زورق إنقاذ 1',   'ZR-11-001',     2020)
) AS v(unit_name, kind, category_key, label, code, year)
JOIN ops.unit u ON u.name_ar = v.unit_name
WHERE NOT EXISTS (SELECT 1 FROM ops.resource r WHERE r.unit_id = u.id AND r.label = v.label);

-- ---------------------------------------------------------------------------------------------------------------------
-- I3 · المخزون والمعدات
-- الوصف: الكميات الجاهزة والمعطّلة من كل فئة معدات في كل وحدة. الفئات من inv.category (kind = 'equipment').
-- ◀ القيم: (اسم الوحدة، مفتاح الفئة، الجاهز، المعطّل)
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO inv.stock (unit_id, gouvernorat_code, category_key, qty_ready, qty_broken, updated_by)
SELECT u.id, u.gouvernorat_code, c.key, v.qty_ready, v.qty_broken, current_setting('ehimaya.actor')
FROM (VALUES
    ('وحدة الحماية المدنية بقرطاج',  1, 12, 1),
    ('وحدة الحماية المدنية بالمرسى', 2,  8, 0)
) AS v(unit_name, category_rank, qty_ready, qty_broken)
JOIN ops.unit u ON u.name_ar = v.unit_name
JOIN LATERAL (
    -- مثال: أول فئتي معدات في الفهرس؛ في الإدخال الحقيقي يُكتب مفتاح الفئة مباشرة (مثلا 'scba').
    SELECT key FROM inv.category WHERE kind = 'equipment' AND active ORDER BY position, key OFFSET v.category_rank - 1 LIMIT 1
) c ON true;

-- ---------------------------------------------------------------------------------------------------------------------
-- I4 · حساب مواطن وملفه
-- الوصف: الحساب يُنشأ عادة عند أول دخول عبر Keycloak؛ هذا الطلب لنقل حسابات موجودة. keycloak_sub إلزامي لغير
--        المجهول، ويجب أن يطابق «sub» في Keycloak. الهاتف وبطاقة التعريف مشفّران: يُتركان فارغين هنا ويكملهما
--        المواطن من التطبيق.
-- ◀ القيم: (keycloak_sub، الاسم، اللقب، البريد، رمز المعتمدية)
-- ---------------------------------------------------------------------------------------------------------------------
WITH acc AS (
    INSERT INTO identity.account (kind, keycloak_sub, status)
    VALUES ('citizen', '3f7c1d2e-0000-4000-8000-000000000001', 'active')
    ON CONFLICT (keycloak_sub) DO NOTHING
    RETURNING user_id
)
INSERT INTO identity.profile (user_id, first_name, last_name, email, gouvernorat_code, delegation_id, locale)
SELECT acc.user_id, 'سامي', 'بن علي', 'citizen@example.tn', d.gouvernorat_code, d.id, 'ar'
FROM acc
JOIN geo.delegation d ON d.code = 'TN-11-15';

-- ---------------------------------------------------------------------------------------------------------------------
-- I5 · بلاغ مسجَّل في القاعة (مكالمة على 198) ومراحله
-- الوصف: بلاغ أدخله عون القاعة من مكالمة هاتفية: source = 'room' يفرض intake_channel وentered_by. رمز التتبع بصيغة
--        المنظومة EH-<السنة>-<الولاية>-<7 أرقام>. الولاية والمعتمدية من موقع البلاغ (ST_Contains)، لا من الإدخال.
--        المستخدم: حساب المبلّغ إن عُرف، وإلا الحساب المجهول المحجوز (00000000-...). النص الأصلي مشفّر ويكتبه التطبيق.
--        يُكتب معه أول سطر في سجل المراحل (received).
-- ◀ القيم: (الصنف، lon، lat، دقة الموقع بالمتر، تاريخ الاستلام، قناة الإدخال، العون)
-- ---------------------------------------------------------------------------------------------------------------------
WITH v AS (
    SELECT 'fire'::text AS category, 10.3247::float8 AS lon, 36.8783::float8 AS lat, 50::real AS accuracy_m,
           timestamptz '2026-07-14 15:42:00+01' AS received_at, 'phone'::text AS channel,
           'operator:tunis-01'::text AS entered_by, 'عون القاعة الجهوية بتونس'::text AS entered_by_name
), place AS (
    SELECT v.*, d.gouvernorat_code, d.id AS delegation_id, ST_MakePoint(v.lon, v.lat)::geography AS geog
    FROM v
    LEFT JOIN geo.delegation d ON ST_Contains(d.boundary, ST_SetSRID(ST_MakePoint(v.lon, v.lat), 4326))
), rep AS (
    INSERT INTO reports.report (id, tracking_code, user_id, category, lang_original, location, location_accuracy_m,
                                gouvernorat_code, delegation_id, status, source, created_at, received_at, updated_at,
                                needs_verification, search_tokens, geo_state, geo_candidates, escalation_state,
                                intake_channel, entered_by, entered_by_name)
    SELECT gen_random_uuid(),
           format('EH-%s-%s-%s', to_char(p.received_at AT TIME ZONE 'Africa/Tunis', 'YY'),
                  lpad(coalesce(p.gouvernorat_code, 0)::text, 2, '0'), lpad((floor(random() * 1e7))::bigint::text, 7, '0')),
           '00000000-0000-0000-0000-000000000000', p.category, 'ar', p.geog, p.accuracy_m,
           p.gouvernorat_code, p.delegation_id, 'received', 'room', p.received_at, p.received_at, now(),
           false, '{}', 'trusted', '{}', 'none',
           p.channel, p.entered_by, p.entered_by_name
    FROM place p
    RETURNING id, received_at, entered_by
)
INSERT INTO reports.status_history (report_id, status, at, actor, note)
SELECT rep.id, 'received', rep.received_at, rep.entered_by, 'بلاغ هاتفي على 198 أدخله عون القاعة'
FROM rep;

-- ---------------------------------------------------------------------------------------------------------------------
-- I6 · تدخل، وربطه بالبلاغ، وتكليف وسيلة، والحصيلة
-- الوصف: سلسلة كاملة في طلب واحد (CTE قابلة للكتابة):
--        1) فتح تدخل في مكان البلاغ وبصنفه، بالمستوى العملياتي «عادي» وقيادة جهوية؛
--        2) ربط البلاغ به وتحويل حالته إلى in_progress مع سطر في سجل المراحل؛
--        3) دور الولاية القائدة في ops.incident_gouvernorat؛
--        4) تكليف أقرب شاحنة إطفاء متاحة (المسافة الجيوديسية) بآجالها الفعلية (الأمر، الانطلاق، الوصول)؛
--        5) جعل الوسيلة «مكلّفة»؛ 6) سطر في الخط الزمني للتدخل؛ 7) الحصيلة الأولية للضحايا.
-- ◀ القيم: الدقائق بين المراحل والحصيلة من تقرير العون الميداني.
-- ---------------------------------------------------------------------------------------------------------------------
WITH rep AS (
    SELECT r.* FROM reports.report r
    WHERE r.source = 'room' AND r.entered_by = 'operator:tunis-01' AND r.incident_id IS NULL
    ORDER BY r.received_at DESC LIMIT 1
), inc AS (
    INSERT INTO ops.incident (id, category, severity, centroid, gouvernorat_code, delegation_id, op_level, status,
                              opened_at, updated_at, title, command_level, command_level_manual)
    SELECT gen_random_uuid(), rep.category, 60, rep.location, rep.gouvernorat_code, rep.delegation_id, 'normal', 'open',
           rep.received_at + interval '2 minutes', now(), 'حريق أعشاب قرب الطريق', 'regional', false
    FROM rep
    RETURNING *
), link AS (
    UPDATE reports.report r
    SET incident_id = inc.id, status = 'in_progress', first_response_at = inc.opened_at,
        claimed_room = format('g:%s', lpad(inc.gouvernorat_code::text, 2, '0')),
        claimed_by = current_setting('ehimaya.actor'), claimed_at = inc.opened_at, updated_at = now()
    FROM inc, rep
    WHERE r.id = rep.id
    RETURNING r.id, inc.opened_at
), hist AS (
    INSERT INTO reports.status_history (report_id, status, at, actor, note)
    SELECT link.id, 'in_progress', link.opened_at, current_setting('ehimaya.actor'), 'فُتح تدخل'
    FROM link
), lead_g AS (
    INSERT INTO ops.incident_gouvernorat (incident_id, gouvernorat_code, role, added_by)
    SELECT inc.id, inc.gouvernorat_code, 'lead', current_setting('ehimaya.actor') FROM inc
), res AS (
    SELECT r.id, inc.id AS incident_id, inc.opened_at
    FROM inc
    CROSS JOIN LATERAL (
        SELECT res.id
        FROM ops.resource res JOIN ops.unit u ON u.id = res.unit_id
        WHERE res.status = 'available' AND res.kind = 'fire_engine'
        ORDER BY coalesce(res.location, u.location) <-> inc.centroid
        LIMIT 1
    ) r
), asg AS (
    INSERT INTO ops.assignment (id, incident_id, kind, resource_id, "order", status, created_by, created_at,
                                acknowledged_at, en_route_at, on_scene_at, crew_count, consumables, time_sources,
                                skipped, field_initiated, damages)
    SELECT gen_random_uuid(), res.incident_id, 'resource', res.id, 'التوجه فورا إلى مكان الحريق', 'on_scene',
           current_setting('ehimaya.actor'), res.opened_at,
           res.opened_at + interval '1 minute', res.opened_at + interval '2 minutes', res.opened_at + interval '11 minutes',
           5, '{}', '{"en_route_at": "room", "on_scene_at": "room"}', '{}', false, '[]'
    FROM res
    RETURNING id, resource_id, incident_id, on_scene_at
), busy AS (
    UPDATE ops.resource r SET status = 'assigned', version = r.version + 1, updated_at = now(),
                              updated_by = current_setting('ehimaya.actor')
    FROM asg WHERE r.id = asg.resource_id
), tl AS (
    INSERT INTO ops.timeline_event (incident_id, at, actor, kind, payload)
    SELECT inc.id, inc.opened_at, current_setting('ehimaya.actor'), 'incident.opened',
           jsonb_build_object('category', inc.category, 'source', 'sql-import')
    FROM inc
)
INSERT INTO ops.casualty_count (incident_id, injured_light, injured_serious, deceased, rescued, trapped, updated_by)
SELECT inc.id, 1, 0, 0, 0, 0, current_setting('ehimaya.actor') FROM inc;

-- ---------------------------------------------------------------------------------------------------------------------
-- I7 · قائمة رسمية لأماكن في طبقة الخريطة (المستشفيات)
-- الوصف: هذا هو الطلب الذي يحل محل الأماكن التقريبية [SIM]. الخطوات:
--        1) جدول مؤقت بأعمدة الملف الرسمي (وزارة الصحة / الديوان)؛
--        2) ملؤه من ملف CSV على القرص (السطر \copy، معطَّل هنا)، أو من VALUES كمثال؛
--        3) إدراج الطبقة إن لم توجد (مفتاح فريد key)، غير تجريبية (simulated = false)؛
--        4) إدراج كل مكان في geo.layer_feature مع ولايته ومعتمديته من موقعه، أو تحديثه إن وُجد (المفتاح layer_id+ref)؛
--        5) رفع data_version للطبقة لتعيد التطبيقات تحميلها.
-- ◀ القيم: ملف CSV بالأعمدة ref,name,kind,phone,lon,lat,source_url
-- ---------------------------------------------------------------------------------------------------------------------
CREATE TEMP TABLE staging_places (
    ref text PRIMARY KEY, name text NOT NULL, kind text, phone text,
    lon double precision NOT NULL, lat double precision NOT NULL, source_url text
) ON COMMIT DROP;

-- \copy staging_places (ref, name, kind, phone, lon, lat, source_url) FROM 'hospitals-official.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO staging_places VALUES
    ('MS-11-0001', 'مثال: مستشفى جامعي بتونس (يُستبدل بالقائمة الرسمية)', 'university_hospital', '+21671000100', 10.1658, 36.8020, NULL);

INSERT INTO geo.layer (key, name, icon, colour, audience, source, licence, to_verify, simulated, status, created_by, updated_by,
                       updated_by_name, group_key, audiences)
VALUES ('hospitals', '{"ar": "المستشفيات", "fr": "Hôpitaux", "en": "Hospitals"}', 'hospital', '#C8102E', 'public',
        'وزارة الصحة / الديوان الوطني للحماية المدنية', 'رخصة الجهة المصدرة', false, false, 'published',
        current_setting('ehimaya.actor'), current_setting('ehimaya.actor'), current_setting('ehimaya.actor_name'),
        'health', ARRAY['citizen', 'room', 'field', 'command'])
ON CONFLICT (key) DO NOTHING;

INSERT INTO geo.layer_feature (layer_id, ref, name, kind, phone, location, gouvernorat_code, delegation_id, name_status,
                               source_url, snapshot_at, updated_by)
SELECT l.id, s.ref, s.name, s.kind, s.phone, ST_MakePoint(s.lon, s.lat)::geography, d.gouvernorat_code, d.id, 'official',
       s.source_url, current_date, current_setting('ehimaya.actor')
FROM staging_places s
JOIN geo.layer l ON l.key = 'hospitals'
LEFT JOIN geo.delegation d ON ST_Contains(d.boundary, ST_SetSRID(ST_MakePoint(s.lon, s.lat), 4326))
ON CONFLICT (layer_id, ref) DO UPDATE
SET name = EXCLUDED.name, kind = EXCLUDED.kind, phone = EXCLUDED.phone, location = EXCLUDED.location,
    gouvernorat_code = EXCLUDED.gouvernorat_code, delegation_id = EXCLUDED.delegation_id,
    version = geo.layer_feature.version + 1, updated_by = EXCLUDED.updated_by, updated_at = now(),
    deleted_at = NULL;

UPDATE geo.layer SET data_version = data_version + 1, updated_at = now(), updated_by = current_setting('ehimaya.actor')
WHERE key = 'hospitals';

-- ---------------------------------------------------------------------------------------------------------------------
-- I8 · مؤسسة (منشأة مصنفة)
-- الوصف: مؤسسة يسجلها الديوان مباشرة (بدل التسجيل الذاتي في البوابة): المعرّف الجبائي (mf) أو رقم السجل الوطني
--        للمؤسسات (rne) فريد. created_by حساب صاحبها (من نوع organization). الحالة active لأن الديوان أدخلها.
-- ◀ القيم: (الاسم، الصبغة، نوع المعرّف، المعرّف، القطاع، الطاقة، الطوابق، العنوان، lon، lat، البريد، الهاتف)
-- ---------------------------------------------------------------------------------------------------------------------
WITH owner AS (
    INSERT INTO identity.account (kind, keycloak_sub, status)
    VALUES ('organization', '3f7c1d2e-0000-4000-8000-000000000002', 'active')
    ON CONFLICT (keycloak_sub) DO UPDATE SET updated_at = now()
    RETURNING user_id
)
INSERT INTO org.organization (name, kind, identifier_type, identifier, activity_sector, capacity, floors, receives_public,
                              address, location, gouvernorat_code, delegation_id, manager, contact_email, contact_phone,
                              status, reviewed_by, reviewed_at, created_by)
SELECT 'مثال: نزل سياحي بقمرت', 'tourism', 'rne', 'B0000002026', 'نزل', 450, 5, true,
       'المنطقة السياحية، قمرت', ST_MakePoint(10.2950, 36.9180)::geography, d.gouvernorat_code, d.id,
       '{"full_name": "مدير المؤسسة", "phone": "+21671000200", "email": "direction@example.tn"}',
       'direction@example.tn', '+21671000200', 'active', current_setting('ehimaya.actor'), now(), owner.user_id
FROM owner
LEFT JOIN geo.delegation d ON ST_Contains(d.boundary, ST_SetSRID(ST_MakePoint(10.2950, 36.9180), 4326))
ON CONFLICT (identifier) DO NOTHING;

-- ---------------------------------------------------------------------------------------------------------------------
-- I9 · محور أزمة ومراكز إيواء
-- الوصف: الرقم بصيغة المنظومة AX-<السنة>-<ترتيب>، من العدّاد crisis.counter (يُزاد في الطلب نفسه حتى لا يتكرر).
--        محور على مستوى ولاية (scope = gouvernorat) بمستوى 1 إلى 4. ثم مراكز الإيواء بطاقتها وعدد شاغليها.
--        محور تمرين يُكتب اسمه بادئا بـ [SIM]؛ المحور الحقيقي بلا هذه البادئة.
-- ◀ القيم: (الاسم، النوع، الولاية، المستوى، الخطة) ومراكز الإيواء (الاسم، lon، lat، الطاقة، الشاغلون)
-- ---------------------------------------------------------------------------------------------------------------------
WITH n AS (
    INSERT INTO crisis.counter (year, last) VALUES (extract(year FROM now())::int, 1)
    ON CONFLICT (year) DO UPDATE SET last = crisis.counter.last + 1
    RETURNING year, last
), ax AS (
    INSERT INTO crisis.axis (number, name, kind, scope, gouvernorat_code, level, plan, opened_by, opened_by_name)
    SELECT format('AX-%s-%s', n.year, lpad(n.last::text, 3, '0')), 'فيضانات وادي مجردة بولاية منوبة', 'flood',
           'gouvernorat', 14, 2, 'المخطط الجهوي للتدخل والإسعاف (ORSEC) للفيضانات',
           current_setting('ehimaya.actor'), current_setting('ehimaya.actor_name')
    FROM n
    RETURNING id
)
INSERT INTO crisis.shelter (axis_id, name, location, capacity, occupants, updated_by)
SELECT ax.id, s.name, ST_MakePoint(s.lon, s.lat)::geography, s.capacity, s.occupants, current_setting('ehimaya.actor')
FROM ax
CROSS JOIN (VALUES
    ('مثال: المدرسة الابتدائية بالبطان', 9.8480, 36.8060, 120, 34),
    ('مثال: دار الشباب بطبربة',          9.8380, 36.8330,  80, 12)
) AS s(name, lon, lat, capacity, occupants);

-- ---------------------------------------------------------------------------------------------------------------------
-- I10 · تمرين مبرمج
-- الوصف: تمرين في حالة مسودة (draft) بولاية أو أكثر، بقاعة القيادة، وموعده ومدته وهدفه. المنظومة تكمل المراحل
--        (submitted ← ready ← running ← ended ← closed) من لوحة القيادة.
-- ◀ القيم: (العنوان، الهدف، الخطر، الولايات، القاعة، الموعد، المدة بالدقائق)
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO drill.exercise (title, objective, hazard_key, gouvernorats, room, planned_start, duration_min,
                            created_by, created_by_name)
VALUES ('تمرين إخلاء مؤسسة تربوية', 'قياس زمن الإخلاء الكامل وتنسيق وحدات الإطفاء والإسعاف', 'fire', ARRAY[11]::smallint[],
        'g:11', timestamptz '2026-12-03 09:00:00+01', 120,
        current_setting('ehimaya.actor'), current_setting('ehimaya.actor_name'));

-- ---------------------------------------------------------------------------------------------------------------------
-- I11 · متطوع معتمد
-- الوصف: متطوع مرتبط بحساب مواطن موجود (I4)، بمهاراته (1 إلى 8)، وتوفّره، وفترته، وولايته. الحالة approved مع من
--        راجعه ومتى. مثال يربط الحساب الذي أُنشئ في I4.
-- ◀ القيم: (keycloak_sub، المهارات، التوفر، من تاريخ، الولاية)
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO identity.volunteer (user_id, status, skills, availability, period_from, gouvernorat_code, reviewed_at, reviewed_by)
SELECT a.user_id, 'approved', ARRAY['first_aid', 'search_rescue'], 'intermittent', current_date, 11, now(), current_setting('ehimaya.actor')
FROM identity.account a
WHERE a.keycloak_sub = '3f7c1d2e-0000-4000-8000-000000000001'
ON CONFLICT (user_id) DO NOTHING;

-- ---------------------------------------------------------------------------------------------------------------------
-- I12 · أرشيف التدخلات السنوي للديوان (SNACR)
-- الوصف: سنة من ملف الديوان تحل محل سنة [SIM] المولّدة بأكملها (لا خلط بين المصدرين):
--        1) حذف السنة إن كانت مولّدة (simulated)؛ الحذف يتسلسل إلى تدخلاتها؛
--        2) جدول مؤقت بأعمدة الملف، يُملأ بـ \copy من القرص (الملف لا يُنسخ إلى المستودع)؛
--        3) سطر snacr.dataset بمصدر office؛ 4) التدخلات مع مطابقة اسم المعتمدية الخام بالمرجع (مباشرة أو عبر
--           snacr.alias)، وحساب زمن الوصول بالدقائق.
--        ملاحظة: الاستيراد من لوحة القيادة (SNACR ← استيراد) يفعل هذا مع تقرير جودة كامل، وهو المفضَّل.
--        إن كانت السنة مستوردة من الديوان سلفا، يتوقف الطلب بخطأ القيد الفريد (year): لا يُستبدل ملف رسمي إلا عمدا.
-- ◀ القيم: السنة واسم الملف، ومسار CSV في \copy.
-- ---------------------------------------------------------------------------------------------------------------------
\set snacr_year 2025
DELETE FROM snacr.dataset WHERE year = :snacr_year AND source = 'simulated';

CREATE TEMP TABLE staging_snacr (
    seq_num bigint, family text, nature text, subtype text, gouvernorat_code smallint, delegation_raw text,
    unit_raw text, called_at timestamptz, departed_at timestamptz, arrived_at timestamptz, ended_at timestamptz,
    crew_count smallint
) ON COMMIT DROP;

-- \copy staging_snacr FROM 'snacr-2025.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO staging_snacr VALUES
    (1, 'fire', 'حريق أعشاب', NULL, 11, 'قرطاج', 'وحدة قرطاج',
     '2025-08-02 14:05+01', '2025-08-02 14:07+01', '2025-08-02 14:16+01', '2025-08-02 15:02+01', 5);

WITH ds AS (
    INSERT INTO snacr.dataset (year, source, simulated, file_name, rows, imported_by, imported_by_name)
    SELECT :snacr_year, 'office', false, 'snacr-' || :snacr_year || '.csv', count(*),
           current_setting('ehimaya.actor'), current_setting('ehimaya.actor_name')
    FROM staging_snacr
    RETURNING id, year
)
INSERT INTO snacr.intervention (dataset_id, year, family, nature, subtype, gouvernorat_code, delegation_id, delegation_raw,
                                called_at, departed_at, arrived_at, ended_at, arrival_min, crew_count, seq_num, unit_raw,
                                intervened)
SELECT ds.id, ds.year, s.family, s.nature, s.subtype, s.gouvernorat_code,
       coalesce(d.id, al.delegation_id), s.delegation_raw,
       s.called_at, s.departed_at, s.arrived_at, s.ended_at,
       round((extract(epoch FROM s.arrived_at - s.called_at) / 60)::numeric, 1),
       s.crew_count, s.seq_num, s.unit_raw, s.arrived_at IS NOT NULL
FROM staging_snacr s
CROSS JOIN ds
LEFT JOIN geo.delegation d ON d.gouvernorat_code = s.gouvernorat_code AND d.name_ar = s.delegation_raw
LEFT JOIN LATERAL (
    SELECT a.delegation_id FROM snacr.alias a
    WHERE a.gouvernorat_code = s.gouvernorat_code AND a.raw = s.delegation_raw
    LIMIT 1
) al ON true;

-- ---------------------------------------------------------------------------------------------------------------------
-- I13 · أثر العملية في سجل التدقيق المقفل
-- الوصف: audit.log سلسلة بصمات (hash): المُشغّل يحسب seq وprev_hash وhash، ولا يقبل تعديلا ولا حذفا. سطر واحد يصف
--        ما أُدخل، والتفصيل سطرا سطرا موجود في audit.change.
-- ---------------------------------------------------------------------------------------------------------------------
INSERT INTO audit.log (actor, action, target, reason, details)
VALUES (current_setting('ehimaya.actor'), 'data.sql_import', 'docs/sql/02-inserts.sql',
        'إدخال معطيات تشغيلية حقيقية بطلبات SQL',
        jsonb_build_object('request_id', current_setting('ehimaya.request_id')));

-- ---------------------------------------------------------------------------------------------------------------------
-- فحوص بعد الإدخال: ما الذي أُدخل في هذه المعاملة؟
-- ---------------------------------------------------------------------------------------------------------------------
SELECT c.schema_name || '.' || c.table_name AS table_name, c.op, count(*) AS rows
FROM audit.change c
WHERE c.request_id = current_setting('ehimaya.request_id')
GROUP BY 1, 2
ORDER BY 1, 2;

\if :commit
  COMMIT;
  \echo 'تم الحفظ (COMMIT).'
\else
  ROLLBACK;
  \echo 'تجربة جافة: أُلغي كل شيء (ROLLBACK). للحفظ: -v commit=1'
\endif
