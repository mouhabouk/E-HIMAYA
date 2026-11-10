-- =====================================================================================================================
-- ء-حماية / e-Himaya: استعلامات SQL جاهزة، من الأساسي إلى المتقدم
-- =====================================================================================================================
-- المخطط المرجعي: الترحيل 0097_change_journal (227 جدولا في 38 مخططا، PostgreSQL 17 + PostGIS 3 + pgvector).
-- كل استعلام مسبوق برقمه (Q01...) وعنوانه ووصف عربي: ماذا يجيب، وكيف يُقرأ ناتجه.
-- الاستعلامات للقراءة فقط (SELECT)، ولا تغيّر شيئا في القاعدة. التشغيل:
--     psql "$MIGRATION_DATABASE_URL" -f docs/sql/01-queries.sql          (الكل)
--     أو نسخ استعلام واحد إلى psql / DBeaver / pgAdmin.
-- المتغيرات: الاستعلامات التي تحتاج ولاية أو فترة تستعمل قيما ثابتة واضحة (مثل 11 = تونس، آخر 30 يوما)
-- تُغيَّر عند الحاجة. التوقيت المحلي: 'Africa/Tunis'.
-- تنبيه: النصوص الشخصية مشفّرة في القاعدة (*_enc: نص البلاغ، الهاتف، بطاقة التعريف، الملف الطبي)؛ لا تُقرأ بـ SQL
-- بل عبر واجهة البرمجة التي تملك مفتاح التشفير. الاستعلامات هنا لا تلمسها.
--
-- الأقسام:
--   أ.  استعلامات أساسية (اختيار، تصفية، ترتيب)                         Q01-Q08
--   ب.  الربط والتجميع                                                   Q09-Q18
--   ج.  الاستعلامات المكانية (PostGIS)                                    Q19-Q25
--   د.  السلاسل الزمنية ودوال النوافذ                                     Q26-Q33
--   هـ. استعلامات متقدمة (CTE تكرارية، LATERAL، JSONB، GROUPING SETS...)  Q34-Q44
--   و.  الجودة والتدقيق وإدارة القاعدة                                     Q45-Q52
--   ز.  مراقبة البيانات التجريبية [SIM]                                   Q53-Q56
-- =====================================================================================================================

\set ON_ERROR_STOP on
SET search_path = public;

-- =====================================================================================================================
-- أ. استعلامات أساسية
-- =====================================================================================================================

-- Q01 · الولايات الأربع والعشرون مع سكانها ومساحتها
-- الوصف: المرجع الجغرافي الرسمي (المعهد الوطني للإحصاء، تعداد 2014 و2024) كما هو محمّل في geo.gouvernorat.
--        الكثافة محسوبة: سكان 2024 مقسوما على المساحة. مفيد للتحقق من أن المرجع الجغرافي كامل.
SELECT g.code,
       g.name_ar,
       g.name_fr,
       g.population_2024,
       g.area_km2,
       round((g.population_2024 / NULLIF(g.area_km2, 0))::numeric, 1) AS density_per_km2,
       g.region AS economic_region
FROM geo.gouvernorat g
ORDER BY g.code;

-- Q02 · معتمديات ولاية معيّنة
-- الوصف: قائمة المعتمديات لولاية واحدة (هنا 11 = تونس) مع رمزها ومساحتها، مرتبة بالاسم العربي.
SELECT d.id, d.code, d.name_ar, d.name_fr, d.population_2024, d.area_km2
FROM geo.delegation d
WHERE d.gouvernorat_code = 11
ORDER BY d.name_ar;

-- Q03 · آخر 50 بلاغا مستلَما
-- الوصف: أحدث البلاغات بغض النظر عن حالتها: رمز التتبع، الصنف، الحالة، المصدر (تطبيق، بوابة، مكالمة، قاعة...)،
--        والولاية. النص الأصلي مشفّر ولا يظهر هنا.
SELECT r.tracking_code, r.category, r.status, r.source, r.gouvernorat_code,
       r.priority_score, r.received_at AT TIME ZONE 'Africa/Tunis' AS received_local
FROM reports.report r
ORDER BY r.received_at DESC
LIMIT 50;

-- Q04 · البلاغات المفتوحة ذات الأولوية العالية
-- الوصف: البلاغات التي لم تُغلق ولم تُرفض، ودرجة أولويتها 70 فما فوق (حد فئة «عالية» في إعداد sla.bands)،
--        من الأعلى أولوية إلى الأدنى، ثم الأقدم أولا.
SELECT r.tracking_code, r.category, r.status, r.priority_score, r.sla_band, r.sla_due_at, r.gouvernorat_code
FROM reports.report r
WHERE r.status NOT IN ('closed', 'rejected')
  AND r.priority_score >= 70
ORDER BY r.priority_score DESC, r.received_at;

-- Q05 · البحث عن بلاغ برمز التتبع
-- الوصف: ما يفعله المواطن في صفحة «تتبع بلاغي»: رمز EH-سنة-ولاية-7 أرقام يعيد الحالة ومراحلها.
SELECT r.tracking_code, r.category, r.status, h.status AS step, h.at AT TIME ZONE 'Africa/Tunis' AS step_at, h.actor
FROM reports.report r
LEFT JOIN reports.status_history h ON h.report_id = r.id
WHERE r.tracking_code = 'EH-26-11-0000001'
ORDER BY h.at;

-- Q06 · الوسائل المتاحة الآن في ولاية
-- الوصف: الشاحنات وسيارات الإسعاف وغيرها في حالة «متاحة» لوحدات ولاية واحدة، مع الوحدة التي تتبعها.
SELECT u.name_ar AS unit, res.kind, res.label, res.code, res.status
FROM ops.resource res
JOIN ops.unit u ON u.id = res.unit_id
WHERE u.gouvernorat_code = 11
  AND res.status = 'available'
ORDER BY u.name_ar, res.kind, res.label;

-- Q07 · المستوى العملياتي لكل ولاية
-- الوصف: عادي / أزمة / كارثة لكل ولاية، ومنذ متى، ومن غيّره. الأسطر غير «normal» تظهر أولا.
SELECT g.name_ar, ls.level, ls.since AT TIME ZONE 'Africa/Tunis' AS since_local, ls.set_by_name, ls.reason
FROM ops.level_state ls
JOIN geo.gouvernorat g ON g.code = ls.gouvernorat_code
ORDER BY (ls.level = 'normal'), g.code;

-- Q08 · المؤسسات في انتظار المراجعة
-- الوصف: المؤسسات (مستشفيات، مصانع، نزل...) التي سجّلت في البوابة ولم يراجعها الديوان بعد، الأقدم أولا.
SELECT o.name, o.kind, o.identifier_type, o.identifier, o.gouvernorat_code, o.created_at
FROM org.organization o
WHERE o.status = 'pending_review'
ORDER BY o.created_at;

-- =====================================================================================================================
-- ب. الربط والتجميع
-- =====================================================================================================================

-- Q09 · عدد البلاغات حسب الولاية والصنف (آخر 30 يوما)
-- الوصف: جدول تقاطعي: لكل ولاية عدد البلاغات من كل صنف، بـ COUNT(*) FILTER بدل عدة استعلامات. الولايات بلا بلاغ
--        تظهر بأصفار (LEFT JOIN من جدول الولايات).
SELECT g.code, g.name_ar,
       count(r.id)                                              AS total,
       count(r.id) FILTER (WHERE r.category = 'fire')           AS fire,
       count(r.id) FILTER (WHERE r.category = 'flood')          AS flood,
       count(r.id) FILTER (WHERE r.category = 'traffic_accident') AS traffic,
       count(r.id) FILTER (WHERE r.category = 'drowning')       AS drowning,
       count(r.id) FILTER (WHERE r.category = 'medical')        AS medical,
       count(r.id) FILTER (WHERE r.category = 'sos')            AS sos,
       count(r.id) FILTER (WHERE r.category NOT IN ('fire','flood','traffic_accident','drowning','medical','sos')) AS other
FROM geo.gouvernorat g
LEFT JOIN reports.report r
       ON r.gouvernorat_code = g.code
      AND r.received_at >= now() - interval '30 days'
GROUP BY g.code, g.name_ar
ORDER BY total DESC, g.code;

-- Q10 · زمن الاستجابة الأول لكل ولاية (بالدقائق)
-- الوصف: من استلام البلاغ إلى أول استجابة (first_response_at): المتوسط والوسيط والمئين 90. الوسيط والمئين 90
--        أصدق من المتوسط لأن بلاغا واحدا متأخرا جدا يرفع المتوسط.
SELECT r.gouvernorat_code,
       count(*) AS reports,
       round(avg(extract(epoch FROM r.first_response_at - r.received_at) / 60)::numeric, 1) AS avg_min,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM r.first_response_at - r.received_at) / 60))::numeric, 1) AS median_min,
       round((percentile_cont(0.9) WITHIN GROUP (ORDER BY extract(epoch FROM r.first_response_at - r.received_at) / 60))::numeric, 1) AS p90_min
FROM reports.report r
WHERE r.first_response_at IS NOT NULL
GROUP BY r.gouvernorat_code
ORDER BY median_min DESC;

-- Q11 · التدخلات المفتوحة مع بلاغاتها ووسائلها
-- الوصف: لكل تدخل مفتوح: عدد البلاغات المرتبطة، عدد الوسائل المكلّفة، وكم منها في الطريق أو في المكان.
--        يُظهر الدمج بين ops.incident وreports.report وops.assignment.
SELECT i.id, i.category, i.title, i.op_level, i.gouvernorat_code, i.opened_at,
       (SELECT count(*) FROM reports.report r WHERE r.incident_id = i.id)                 AS reports,
       count(a.id)                                                                        AS assignments,
       count(a.id) FILTER (WHERE a.status = 'en_route')                                   AS en_route,
       count(a.id) FILTER (WHERE a.status = 'on_scene')                                   AS on_scene
FROM ops.incident i
LEFT JOIN ops.assignment a ON a.incident_id = i.id AND a.status <> 'cancelled'
WHERE i.status = 'open'
GROUP BY i.id
ORDER BY i.opened_at;

-- Q12 · حصيلة الضحايا حسب الصنف والشهر
-- الوصف: مجموع الجرحى (خفيف وخطير) والوفيات والمنقذين والمحاصرين من ops.casualty_count، حسب صنف التدخل وشهر فتحه.
SELECT date_trunc('month', i.opened_at AT TIME ZONE 'Africa/Tunis')::date AS month,
       i.category,
       count(*)                AS incidents,
       sum(c.injured_light)    AS injured_light,
       sum(c.injured_serious)  AS injured_serious,
       sum(c.deceased)         AS deceased,
       sum(c.rescued)          AS rescued,
       sum(c.trapped)          AS trapped
FROM ops.incident i
JOIN ops.casualty_count c ON c.incident_id = i.id
GROUP BY 1, 2
ORDER BY 1 DESC, 2;

-- Q13 · جاهزية الأسطول حسب نوع الوسيلة
-- الوصف: لكل نوع وسيلة: كم متاحة، كم مكلّفة، كم خارج الخدمة (صيانة أو عطب)، ونسبة الجاهزية.
SELECT res.kind,
       count(*)                                                      AS total,
       count(*) FILTER (WHERE res.status = 'available')              AS available,
       count(*) FILTER (WHERE res.status = 'assigned')               AS assigned,
       count(*) FILTER (WHERE res.status = 'out_of_service')         AS out_of_service,
       round(100.0 * count(*) FILTER (WHERE res.status <> 'out_of_service') / count(*), 1) AS readiness_pct
FROM ops.resource res
GROUP BY res.kind
ORDER BY total DESC;

-- Q14 · المخزون حسب الولاية والفئة
-- الوصف: الكميات الجاهزة والمعطّلة من المعدات (inv.stock) مع اسم الفئة بالعربية من inv.category.
SELECT s.gouvernorat_code, c.family, c.name ->> 'ar' AS category,
       sum(s.qty_ready) AS ready, sum(s.qty_broken) AS broken
FROM inv.stock s
JOIN inv.category c ON c.key = s.category_key
GROUP BY s.gouvernorat_code, c.family, c.name ->> 'ar'
ORDER BY s.gouvernorat_code, c.family, category;

-- Q15 · المتطوعون المعتمدون حسب المهارة
-- الوصف: identity.volunteer.skills مصفوفة نصوص؛ unnest يفكّها سطرا لكل مهارة ثم نعدّ المتطوعين المعتمدين لكل مهارة
--        ولكل ولاية.
SELECT v.gouvernorat_code, skill, count(*) AS volunteers
FROM identity.volunteer v
CROSS JOIN LATERAL unnest(v.skills) AS skill
WHERE v.status = 'approved'
  AND (v.period_to IS NULL OR v.period_to >= current_date)
GROUP BY v.gouvernorat_code, skill
ORDER BY v.gouvernorat_code, volunteers DESC;

-- Q16 · شهادات السلامة والوقاية التي تنتهي صلاحيتها خلال 90 يوما
-- الوصف: الشهادات المعتمدة التي يقترب تاريخ نهاية صلاحيتها، مع المؤسسة، لتذكيرها بالتجديد.
SELECT o.name, o.gouvernorat_code, c.kind, c.code, c.valid_until,
       c.valid_until - current_date AS days_left
FROM org.certificate c
JOIN org.organization o ON o.id = c.org_id
WHERE c.status = 'approved'
  AND c.valid_until BETWEEN current_date AND current_date + 90
ORDER BY c.valid_until;

-- Q17 · المكالمات حسب الحالة ونسبة المكالمات الضائعة
-- الوصف: مكالمات الطوارئ (telephony.call) الواردة لكل يوم: المجاب عنها، الضائعة، ونسبة الضياع. المكالمات المحاكاة
--        (source = 'sim') مستبعدة.
SELECT (c.started_at AT TIME ZONE 'Africa/Tunis')::date AS day,
       count(*)                                         AS calls,
       count(*) FILTER (WHERE c.answered_at IS NOT NULL) AS answered,
       count(*) FILTER (WHERE c.status = 'missed')      AS missed,
       round(100.0 * count(*) FILTER (WHERE c.status = 'missed') / count(*), 1) AS missed_pct
FROM telephony.call c
WHERE c.direction = 'inbound' AND c.source <> 'sim'
GROUP BY 1
ORDER BY 1 DESC;

-- Q18 · نقاط المواطنين (المكافآت) مع ترتيبهم
-- الوصف: مجموع النقاط في دفتر rewards.points_ledger (دفتر للإضافة فقط: الإلغاء سطر سالب) وترتيب كل مواطن.
SELECT l.citizen_id, sum(l.delta) AS points,
       rank() OVER (ORDER BY sum(l.delta) DESC) AS rank
FROM rewards.points_ledger l
GROUP BY l.citizen_id
ORDER BY points DESC
LIMIT 100;

-- =====================================================================================================================
-- ج. الاستعلامات المكانية (PostGIS)
-- =====================================================================================================================

-- Q19 · في أي ولاية ومعتمدية تقع نقطة؟
-- الوصف: ما تفعله المنظومة عند استلام بلاغ: ST_Contains على حدود المعتمديات. النقطة هنا وسط مدينة تونس
--        (خط الطول 10.1815، خط العرض 36.8065). الإحداثيات بترتيب (lon, lat).
SELECT g.name_ar AS gouvernorat, d.name_ar AS delegation, d.code
FROM geo.delegation d
JOIN geo.gouvernorat g ON g.code = d.gouvernorat_code
WHERE ST_Contains(d.boundary, ST_SetSRID(ST_MakePoint(10.1815, 36.8065), 4326));

-- Q20 · أقرب 5 وسائل متاحة إلى مكان بلاغ
-- الوصف: المسافة الجيوديسية بالمتر (نوع geography) بين موقع البلاغ وموقع الوسيلة، أو موقع وحدتها إن لم يُعرف
--        موقعها الحي. المعامل <-> يستعمل الفهرس المكاني لترتيب الأقرب بسرعة.
WITH target AS (
    SELECT location FROM reports.report WHERE tracking_code = 'EH-26-11-0000001'
)
SELECT res.label, res.kind, u.name_ar AS unit,
       round(ST_Distance(coalesce(res.location, u.location), t.location)) AS distance_m
FROM ops.resource res
JOIN ops.unit u ON u.id = res.unit_id
CROSS JOIN target t
WHERE res.status = 'available'
ORDER BY coalesce(res.location, u.location) <-> t.location
LIMIT 5;

-- Q21 · البلاغات في دائرة نصف قطرها 2 كم حول نقطة (آخر 24 ساعة)
-- الوصف: ST_DWithin على geography بالمتر: يكشف تكرار البلاغات عن الحادث نفسه (عدة مواطنين يبلغون عن حريق واحد).
SELECT r.tracking_code, r.category, r.received_at,
       round(ST_Distance(r.location, ST_MakePoint(10.1815, 36.8065)::geography)) AS distance_m
FROM reports.report r
WHERE ST_DWithin(r.location, ST_MakePoint(10.1815, 36.8065)::geography, 2000)
  AND r.received_at >= now() - interval '24 hours'
ORDER BY distance_m;

-- Q22 · كثافة البلاغات لكل 10 آلاف ساكن حسب المعتمدية
-- الوصف: ربط مكاني بين البلاغات وحدود المعتمديات (بدل الاعتماد على delegation_id المخزّن)، ثم القسمة على سكان 2024.
--        يبرز المعتمديات الأكثر تعرضا للمخاطر نسبة إلى سكانها.
SELECT d.gouvernorat_code, d.name_ar,
       count(r.id) AS reports,
       round(10000.0 * count(r.id) / NULLIF(d.population_2024, 0), 2) AS per_10k
FROM geo.delegation d
LEFT JOIN reports.report r ON ST_Contains(d.boundary, r.location::geometry)
GROUP BY d.id
HAVING count(r.id) > 0
ORDER BY per_10k DESC NULLS LAST
LIMIT 30;

-- Q23 · أقرب مستشفى إلى كل تدخل مفتوح
-- الوصف: LATERAL يبحث لكل تدخل عن أقرب عنصر من طبقة المستشفيات (geo.layer بمفتاح 'hospitals')، ويقول إن كانت
--        الطبقة تجريبية [SIM] (أماكن مخترعة) أو حقيقية.
SELECT i.id, i.category, h.name AS nearest_hospital, h.distance_m, h.simulated
FROM ops.incident i
CROSS JOIN LATERAL (
    SELECT f.name, l.simulated, round(ST_Distance(f.location, i.centroid)) AS distance_m
    FROM geo.layer_feature f
    JOIN geo.layer l ON l.id = f.layer_id
    WHERE l.key = 'hospitals' AND NOT f.hidden AND f.deleted_at IS NULL
    ORDER BY f.location <-> i.centroid
    LIMIT 1
) h
WHERE i.status = 'open' AND i.centroid IS NOT NULL;

-- Q24 · بلاغات تقع خارج الولاية المسجّلة لها (مراقبة جودة الموقع)
-- الوصف: بلاغ سجّلت له المنظومة ولاية لا تحتوي حدودُها موقعه: إما خطأ في تحديد الموقع أو إحالة بين ولايات.
SELECT r.tracking_code, r.gouvernorat_code AS stored, g2.code AS actual, r.geo_state, r.location_accuracy_m
FROM reports.report r
JOIN geo.gouvernorat g ON g.code = r.gouvernorat_code
LEFT JOIN geo.gouvernorat g2 ON ST_Contains(g2.boundary, r.location::geometry)
WHERE NOT ST_Contains(g.boundary, r.location::geometry);

-- Q25 · تصدير البلاغات كـ GeoJSON
-- الوصف: مجموعة معالم GeoJSON جاهزة لأي خريطة (QGIS، Leaflet، MapLibre) دون أي معطى شخصي: الصنف والحالة والتاريخ.
SELECT jsonb_build_object(
         'type', 'FeatureCollection',
         'features', coalesce(jsonb_agg(jsonb_build_object(
             'type', 'Feature',
             'geometry', ST_AsGeoJSON(r.location)::jsonb,
             'properties', jsonb_build_object('category', r.category, 'status', r.status,
                                              'received_at', r.received_at)
         )), '[]'::jsonb)
       ) AS geojson
FROM reports.report r
WHERE r.received_at >= now() - interval '7 days';

-- =====================================================================================================================
-- د. السلاسل الزمنية ودوال النوافذ
-- =====================================================================================================================

-- Q26 · عدد البلاغات لكل يوم مع الأيام الفارغة
-- الوصف: generate_series ينشئ كل أيام الشهر الأخير حتى الأيام بلا بلاغ (صفر)، ثم متوسط متحرك على 7 أيام.
WITH days AS (
    SELECT generate_series(current_date - 29, current_date, interval '1 day')::date AS day
), counts AS (
    SELECT (received_at AT TIME ZONE 'Africa/Tunis')::date AS day, count(*) AS n
    FROM reports.report
    WHERE received_at >= current_date - 30
    GROUP BY 1
)
SELECT d.day, coalesce(c.n, 0) AS reports,
       round(avg(coalesce(c.n, 0)) OVER (ORDER BY d.day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS moving_avg_7d
FROM days d
LEFT JOIN counts c USING (day)
ORDER BY d.day;

-- Q27 · ساعات الذروة: البلاغات حسب ساعة اليوم ويوم الأسبوع
-- الوصف: خريطة حرارية (يوم الأسبوع × الساعة) لتوزيع الأعوان على المناوبات. isodow: 1 = الاثنين ... 7 = الأحد.
SELECT extract(isodow FROM received_at AT TIME ZONE 'Africa/Tunis')::int AS weekday,
       extract(hour   FROM received_at AT TIME ZONE 'Africa/Tunis')::int AS hour,
       count(*) AS reports
FROM reports.report
GROUP BY 1, 2
ORDER BY 1, 2;

-- Q28 · مقارنة كل شهر بالشهر السابق وبالشهر نفسه من السنة الماضية
-- الوصف: LAG على السلسلة الشهرية: التغير الشهري والتغير السنوي بالنسبة المئوية.
WITH m AS (
    SELECT date_trunc('month', received_at AT TIME ZONE 'Africa/Tunis')::date AS month, count(*) AS n
    FROM reports.report
    GROUP BY 1
)
SELECT month, n,
       lag(n)     OVER w AS prev_month,
       round(100.0 * (n - lag(n) OVER w) / NULLIF(lag(n) OVER w, 0), 1) AS mom_pct,
       lag(n, 12) OVER w AS same_month_last_year,
       round(100.0 * (n - lag(n, 12) OVER w) / NULLIF(lag(n, 12) OVER w, 0), 1) AS yoy_pct
FROM m
WINDOW w AS (ORDER BY month)
ORDER BY month DESC;

-- Q29 · مراحل الوسيلة في كل تكليف (الآجال الفعلية)
-- الوصف: من الأمر إلى الانطلاق، ومن الانطلاق إلى الوصول، ومدة البقاء في المكان، بالدقائق. أساس مؤشرات الأداء.
SELECT a.id, a.incident_id, res.label,
       round(extract(epoch FROM a.en_route_at - a.created_at) / 60, 1)  AS to_depart_min,
       round(extract(epoch FROM a.on_scene_at - a.en_route_at) / 60, 1) AS travel_min,
       round(extract(epoch FROM a.left_scene_at - a.on_scene_at) / 60, 1) AS on_scene_min,
       round(extract(epoch FROM a.back_at_unit_at - a.created_at) / 60, 1) AS total_min
FROM ops.assignment a
JOIN ops.resource res ON res.id = a.resource_id
WHERE a.kind = 'resource' AND a.on_scene_at IS NOT NULL
ORDER BY a.created_at DESC
LIMIT 100;

-- Q30 · ترتيب الوحدات حسب زمن الوصول الوسيط
-- الوصف: الوحدات مرتبة بزمن الوصول الوسيط (من الانطلاق إلى المكان)، مع ترتيبها داخل ولايتها (PARTITION BY).
SELECT u.gouvernorat_code, u.name_ar,
       count(*) AS missions,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM a.on_scene_at - a.en_route_at) / 60))::numeric, 1) AS median_travel_min,
       rank() OVER (PARTITION BY u.gouvernorat_code
                    ORDER BY percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM a.on_scene_at - a.en_route_at))) AS rank_in_gouvernorat
FROM ops.assignment a
JOIN ops.resource res ON res.id = a.resource_id
JOIN ops.unit u ON u.id = res.unit_id
WHERE a.on_scene_at IS NOT NULL AND a.en_route_at IS NOT NULL
GROUP BY u.id
ORDER BY u.gouvernorat_code, rank_in_gouvernorat;

-- Q31 · كل مرحلة من مراحل البلاغ ومدتها
-- الوصف: LEAD يجلب المرحلة التالية لكل مرحلة في reports.status_history، فنحسب كم بقي البلاغ في كل حالة.
SELECT r.tracking_code, h.status,
       h.at AT TIME ZONE 'Africa/Tunis' AS entered,
       lead(h.at) OVER (PARTITION BY h.report_id ORDER BY h.at) - h.at AS time_in_status
FROM reports.status_history h
JOIN reports.report r ON r.id = h.report_id
WHERE r.received_at >= now() - interval '7 days'
ORDER BY r.tracking_code, h.at;

-- Q32 · قراءات المستشعرات: آخر قيمة ومتوسط الساعة والقيمة القصوى في 24 ساعة
-- الوصف: لكل مستشعر (مطر، منسوب ماء، حرارة): آخر قراءة (DISTINCT ON) مع إحصاءات اليوم، ومقارنة بعتبتي الإنذار.
SELECT DISTINCT ON (d.id)
       d.code, d.name, d.kind, d.simulated, rd.at AS last_at, rd.value AS last_value,
       d.watch_threshold, d.alarm_threshold,
       avg(rd.value) OVER (PARTITION BY d.id ORDER BY rd.at RANGE BETWEEN interval '1 hour' PRECEDING AND CURRENT ROW) AS avg_1h,
       max(rd.value) OVER (PARTITION BY d.id) AS max_24h
FROM sensor.device d
JOIN sensor.reading rd ON rd.sensor_id = d.id AND rd.at >= now() - interval '24 hours'
ORDER BY d.id, rd.at DESC;

-- Q33 · أيام الشواطئ الخطرة على التوالي (gaps and islands)
-- الوصف: لكل شاطئ، أطول سلسلة أيام متتالية بلون أحمر في coastal.beach_day. تقنية «الجزر»: الفرق بين التاريخ وترتيبه
--        ثابت داخل كل سلسلة متصلة.
WITH red AS (
    SELECT feature_id, day,
           day - (row_number() OVER (PARTITION BY feature_id ORDER BY day))::int AS island
    FROM coastal.beach_day
    WHERE level = 'red'
)
SELECT f.name AS beach, min(day) AS from_day, max(day) AS to_day, count(*) AS red_days
FROM red
JOIN geo.layer_feature f ON f.id = red.feature_id
GROUP BY f.name, red.feature_id, island
ORDER BY red_days DESC
LIMIT 20;

-- =====================================================================================================================
-- هـ. استعلامات متقدمة
-- =====================================================================================================================

-- Q34 · شجرة محاور الأزمة (CTE تكرارية)
-- الوصف: crisis.axis يرتبط بأبيه (parent_id): محور وطني ثم محاور الولايات تحته. الاستعلام يعيد الشجرة كاملة بعمقها
--        ومسارها، مع عدد مراكز الإيواء وشاغليها لكل محور.
WITH RECURSIVE tree AS (
    SELECT a.id, a.parent_id, a.number, a.name, a.level, a.status, 0 AS depth, ARRAY[a.number] AS path
    FROM crisis.axis a
    WHERE a.parent_id IS NULL
    UNION ALL
    SELECT c.id, c.parent_id, c.number, c.name, c.level, c.status, t.depth + 1, t.path || c.number
    FROM crisis.axis c
    JOIN tree t ON c.parent_id = t.id
)
SELECT repeat('    ', t.depth) || t.number AS axis, t.name, t.level, t.status,
       count(s.id) AS shelters, coalesce(sum(s.occupants), 0) AS occupants, coalesce(sum(s.capacity), 0) AS capacity
FROM tree t
LEFT JOIN crisis.shelter s ON s.axis_id = t.id
GROUP BY t.id, t.depth, t.number, t.name, t.level, t.status, t.path
ORDER BY t.path;

-- Q35 · سلسلة الدمج بين التدخلات (CTE تكرارية)
-- الوصف: تدخل مدموج في آخر (merged_into) قد يكون هو نفسه مدموجا: نتبع السلسلة حتى التدخل الجذر الذي بقي.
WITH RECURSIVE chain AS (
    SELECT i.id AS start_id, i.id, i.merged_into, 0 AS hops
    FROM ops.incident i
    WHERE i.status = 'merged'
    UNION ALL
    SELECT c.start_id, i.id, i.merged_into, c.hops + 1
    FROM chain c
    JOIN ops.incident i ON i.id = c.merged_into
    WHERE c.hops < 20
)
SELECT start_id, id AS root_incident, hops
FROM chain
WHERE merged_into IS NULL;

-- Q36 · المجاميع الفرعية والعامة بـ GROUPING SETS
-- الوصف: في استعلام واحد: عدد التدخلات حسب (الولاية، الصنف)، ثم مجموع كل ولاية، ثم مجموع كل صنف، ثم المجموع الكلي.
--        GROUPING() تقول أي سطر هو مجموع.
SELECT CASE WHEN grouping(i.gouvernorat_code) = 1 THEN 'الكل' ELSE i.gouvernorat_code::text END AS gouvernorat,
       CASE WHEN grouping(i.category) = 1 THEN 'الكل' ELSE i.category END AS category,
       count(*) AS incidents
FROM ops.incident i
WHERE i.opened_at >= date_trunc('year', now())
GROUP BY GROUPING SETS ((i.gouvernorat_code, i.category), (i.gouvernorat_code), (i.category), ())
ORDER BY grouping(i.gouvernorat_code), i.gouvernorat_code, grouping(i.category), i.category;

-- Q37 · القراءة داخل JSONB: نتائج نماذج التقرير الميداني
-- الوصف: ops.field_report.answers حقل JSONB يحمل أجوبة نموذج التقرير (القالب). هنا: توزيع جواب «مكان الحريق» (place)
--        في التقارير المفصلة لحرائق السنة. ->> يعيد النص، و? يختبر وجود المفتاح.
SELECT fr.answers ->> 'place' AS fire_place, count(*) AS reports
FROM ops.field_report fr
JOIN ops.incident i ON i.id = fr.incident_id
WHERE fr.kind = 'detailed' AND i.category = 'fire'
  AND fr.answers ? 'place'
  AND fr.created_at >= date_trunc('year', now())
GROUP BY 1
ORDER BY reports DESC;

-- Q38 · فك أسئلة القوالب (jsonb_array_elements)
-- الوصف: ops.report_template.fields مصفوفة JSON من الأسئلة. الاستعلام يعيد سطرا لكل سؤال: مفتاحه ونوعه وعنوانه
--        بالعربية وعدد الخيارات، لكل قالب معتمد.
SELECT t.category, t.version, t.simulated,
       q ->> 'key' AS question_key, q ->> 'type' AS type, q -> 'label' ->> 'ar' AS label_ar,
       jsonb_array_length(coalesce(q -> 'options', '[]'::jsonb)) AS options
FROM ops.report_template t
CROSS JOIN LATERAL jsonb_array_elements(t.fields) AS q
WHERE t.status = 'approved'
ORDER BY t.category, t.version;

-- Q39 · مصفوفة المخاطر (احتمال × خطورة) لكل ولاية
-- الوصف: snacr.special_risk يعطي لكل خطر احتمالا وخطورة من 1 إلى 5؛ الناتج = حاصل الضرب (1 إلى 25) مع درجة
--        (منخفض/متوسط/مرتفع/حرج)، وأعلى ثلاثة أخطار في كل ولاية بـ row_number. السطور [SIM] معلَّمة.
SELECT *
FROM (
    SELECT g.name_ar, sr.hazard, sr.probability, sr.gravity,
           sr.probability * sr.gravity AS score,
           CASE WHEN sr.probability * sr.gravity >= 16 THEN 'حرج'
                WHEN sr.probability * sr.gravity >= 10 THEN 'مرتفع'
                WHEN sr.probability * sr.gravity >= 5  THEN 'متوسط'
                ELSE 'منخفض' END AS band,
           sr.simulated,
           row_number() OVER (PARTITION BY sr.gouvernorat_code ORDER BY sr.probability * sr.gravity DESC, sr.hazard) AS rn
    FROM snacr.special_risk sr
    JOIN geo.gouvernorat g ON g.code = sr.gouvernorat_code
) x
WHERE rn <= 3
ORDER BY name_ar, rn;

-- Q40 · تحليل التغطية الزمنية (SNACR): نسبة التدخلات التي وصلت في أقل من 15 و20 و30 دقيقة
-- الوصف: على أرشيف التدخلات snacr.intervention: لكل ولاية وسنة نسبة التدخلات حسب زمن الوصول (arrival_min)، مع
--        تمييز السنوات المولَّدة [SIM] عن ملف الديوان. هذه هي المؤشرات التي تبني عليها دراسة SNACR.
SELECT i.gouvernorat_code, i.year, ds.source,
       count(*) AS interventions,
       round(100.0 * count(*) FILTER (WHERE i.arrival_min <= 15) / count(*), 1) AS within_15,
       round(100.0 * count(*) FILTER (WHERE i.arrival_min <= 20) / count(*), 1) AS within_20,
       round(100.0 * count(*) FILTER (WHERE i.arrival_min <= 30) / count(*), 1) AS within_30,
       round((percentile_cont(0.9) WITHIN GROUP (ORDER BY i.arrival_min))::numeric, 1) AS p90_min
FROM snacr.intervention i
JOIN snacr.dataset ds ON ds.id = i.dataset_id
WHERE i.arrival_min IS NOT NULL
GROUP BY i.gouvernorat_code, i.year, ds.source
ORDER BY i.gouvernorat_code, i.year;

-- Q41 · بحث تقريبي في أسماء الأماكن (pg_trgm)
-- الوصف: similarity() تجد اسم المعتمدية رغم أخطاء الكتابة ('منزه' ← 'المنزه'، 'اريانة' ← 'أريانة'). مفيد في
--        مطابقة الأسماء الخام لأرشيف الديوان مع المرجع.
SELECT d.name_ar, d.name_fr, g.name_ar AS gouvernorat,
       round(similarity(d.name_ar, 'اريانة المدينة')::numeric, 2) AS score
FROM geo.delegation d
JOIN geo.gouvernorat g ON g.code = d.gouvernorat_code
WHERE d.name_ar % 'اريانة المدينة'
ORDER BY score DESC
LIMIT 10;

-- Q42 · البلاغات المتشابهة دلاليا (pgvector)
-- الوصف: reports.report.embedding متجه من 768 بعدا يحسبه نموذج الذكاء الاصطناعي المحلي. <=> هي مسافة جيب التمام:
--        أقرب 10 بلاغات في المعنى إلى بلاغ معيّن (للكشف عن التكرار حتى بلغات مختلفة).
SELECT r2.tracking_code, r2.category, r2.received_at,
       round((1 - (r2.embedding <=> r1.embedding))::numeric, 3) AS cosine_similarity
FROM reports.report r1
JOIN reports.report r2 ON r2.id <> r1.id AND r2.embedding IS NOT NULL
WHERE r1.tracking_code = 'EH-26-11-0000001' AND r1.embedding IS NOT NULL
ORDER BY r2.embedding <=> r1.embedding
LIMIT 10;

-- Q43 · مدى التزام الآجال (SLA) حسب الفئة: المحتجزة في الوقت والمتأخرة
-- الوصف: لكل فئة أولوية (حرجة، عالية، عادية، منخفضة): كم بلاغا احتُجز قبل sla_due_at، كم بعده، وكم ما زال مفتوحا
--        وتجاوز أجله الآن.
SELECT r.sla_band,
       count(*) AS reports,
       count(*) FILTER (WHERE r.claimed_at <= r.sla_due_at)                    AS on_time,
       count(*) FILTER (WHERE r.claimed_at > r.sla_due_at)                     AS late,
       count(*) FILTER (WHERE r.claimed_at IS NULL AND now() > r.sla_due_at)   AS overdue_now,
       round(100.0 * count(*) FILTER (WHERE r.claimed_at <= r.sla_due_at) / NULLIF(count(*) FILTER (WHERE r.claimed_at IS NOT NULL), 0), 1) AS on_time_pct
FROM reports.report r
WHERE r.sla_band IS NOT NULL
GROUP BY r.sla_band
ORDER BY array_position(ARRAY['critical','high','normal','low'], r.sla_band);

-- Q44 · قرارات القائد: نسبة تبنّي اقتراحات المنظومة
-- الوصف: decision.command_decision يسجل كل اقتراح (قواعد أو أمر صوتي/نصي) وما فعله القائد به. النسبة تقيس فائدة
--        المساعدة على القرار؛ الاقتراحات المحاكاة [SIM] مفصولة.
SELECT d.kind, d.origin, d.simulated,
       count(*) AS proposals,
       count(*) FILTER (WHERE d.status = 'adopted')  AS adopted,
       count(*) FILTER (WHERE d.status = 'modified') AS modified,
       count(*) FILTER (WHERE d.status = 'rejected') AS rejected,
       round(100.0 * count(*) FILTER (WHERE d.status IN ('adopted','modified')) / NULLIF(count(*) FILTER (WHERE d.decided_at IS NOT NULL), 0), 1) AS uptake_pct,
       mode() WITHIN GROUP (ORDER BY d.reason_code) FILTER (WHERE d.status = 'rejected') AS top_reject_reason
FROM decision.command_decision d
GROUP BY d.kind, d.origin, d.simulated
ORDER BY proposals DESC;

-- =====================================================================================================================
-- و. الجودة والتدقيق وإدارة القاعدة
-- =====================================================================================================================

-- Q45 · سجل التغييرات (mouchard) لسطر معيّن
-- الوصف: audit.change يسجل كل إدراج وتعديل وحذف (المُشغّل zz_journal): من، متى، أي أعمدة، القيم القديمة والجديدة.
--        الأعمدة الشخصية مخفية (hidden) ولا تُنسخ قيمها.
SELECT c.at AT TIME ZONE 'Africa/Tunis' AS at_local, c.actor, c.actor_name, c.op, c.columns, c.hidden,
       c.old_values, c.new_values
FROM audit.change c
WHERE c.schema_name = 'ops' AND c.table_name = 'resource'
ORDER BY c.at DESC
LIMIT 50;

-- Q46 · من غيّر ماذا اليوم؟
-- الوصف: ملخص يومي لنشاط كل فاعل: عدد العمليات حسب الجدول ونوع العملية (I إدراج، U تعديل، D حذف).
SELECT c.actor, coalesce(c.actor_name, '') AS name, c.schema_name || '.' || c.table_name AS tbl,
       count(*) FILTER (WHERE c.op = 'I') AS inserts,
       count(*) FILTER (WHERE c.op = 'U') AS updates,
       count(*) FILTER (WHERE c.op = 'D') AS deletes
FROM audit.change c
WHERE c.at >= date_trunc('day', now())
GROUP BY 1, 2, 3
ORDER BY count(*) DESC;

-- Q47 · التحقق من سلامة سلسلة سجل التدقيق
-- الوصف: audit.log سلسلة مقفلة: كل سطر يحمل بصمة السطر السابق (prev_hash). أي سطر لا تطابق prev_hash فيه بصمة
--        سابقه يعني كسرا في السلسلة. ناتج فارغ = سلسلة سليمة.
SELECT seq FROM (
    SELECT l.seq, l.prev_hash, lag(l.hash) OVER (ORDER BY l.seq) AS expected_prev
    FROM audit.log l
) x
WHERE expected_prev IS NOT NULL AND prev_hash IS DISTINCT FROM expected_prev;

-- Q48 · بلاغات ناقصة البيانات
-- الوصف: مراقبة الجودة: بلاغات بلا ولاية، أو موقعها غير مؤكد (pending/contradictory)، أو دقة الموقع أسوأ من 1 كم.
SELECT r.tracking_code, r.gouvernorat_code, r.geo_state, r.location_accuracy_m, r.received_at
FROM reports.report r
WHERE r.gouvernorat_code IS NULL
   OR r.geo_state IN ('pending', 'contradictory')
   OR r.location_accuracy_m > 1000
ORDER BY r.received_at DESC;

-- Q49 · حجم كل مخطط وجداوله الكبرى
-- الوصف: الحجم على القرص (مع الفهارس) لكل جدول، وأكبر 25 جدولا. مفيد لتخطيط النسخ الاحتياطي والأرشفة.
SELECT n.nspname AS schema, c.relname AS table_name,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
       c.reltuples::bigint AS approx_rows
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 25;

-- Q50 · الفهارس غير المستعملة
-- الوصف: فهارس لم يقرأها أي استعلام منذ آخر تصفير للإحصاءات: كلفة في الكتابة بلا فائدة. لا تُحذف قبل مراجعة
--        (فهارس UNIQUE تحمي قيدا حتى إن لم تُقرأ).
SELECT s.schemaname, s.relname AS table_name, s.indexrelname AS index_name,
       pg_size_pretty(pg_relation_size(s.indexrelid)) AS size, s.idx_scan
FROM pg_stat_user_indexes s
JOIN pg_index i ON i.indexrelid = s.indexrelid
WHERE s.idx_scan = 0 AND NOT i.indisunique
ORDER BY pg_relation_size(s.indexrelid) DESC
LIMIT 30;

-- Q51 · الاستعلامات الجارية والأقفال المنتظرة
-- الوصف: ما ينفّذ الآن في القاعدة، ومنذ متى، ومن ينتظر قفلا يملكه من (pg_blocking_pids).
SELECT a.pid, a.usename, a.state, now() - a.query_start AS running_for,
       pg_blocking_pids(a.pid) AS blocked_by, left(a.query, 120) AS query
FROM pg_stat_activity a
WHERE a.datname = current_database() AND a.pid <> pg_backend_pid() AND a.state <> 'idle'
ORDER BY running_for DESC;

-- Q52 · قاموس البيانات: أعمدة جدول مع أنواعها وقيودها
-- الوصف: وصف أي جدول من information_schema (هنا reports.report): الاسم، النوع، إلزامي أم لا، القيمة الافتراضية.
SELECT c.ordinal_position AS pos, c.column_name, c.data_type, c.udt_name,
       c.is_nullable, c.column_default
FROM information_schema.columns c
WHERE c.table_schema = 'reports' AND c.table_name = 'report'
ORDER BY c.ordinal_position;

-- =====================================================================================================================
-- ز. مراقبة البيانات التجريبية [SIM]
-- =====================================================================================================================

-- Q53 · كم سطرا تجريبيا [SIM] بقي في كل جدول؟
-- الوصف: الجرد الحي لكل الجداول التي تحمل علامة المحاكاة (عمود simulated، أو source = 'sim'/'simulated'، أو اسم
--        يبدأ بـ [SIM]، أو محتوى لم يصادق عليه). الهدف: أن تصير كل الأرقام 0 قبل التشغيل الحقيقي. التفصيل وطريقة
--        التحويل في docs/sql/sim-inventory.md وdocs/sql/03-sim-to-real.sql.
SELECT 'geo.layer (طبقات أماكن تقريبية)'          AS what, count(*) FILTER (WHERE simulated) AS sim_rows, count(*) AS all_rows FROM geo.layer WHERE deleted_at IS NULL
UNION ALL SELECT 'geo.layer_feature (أماكن [SIM])', count(*) FILTER (WHERE f.name LIKE '[SIM]%' OR l.simulated), count(*) FROM geo.layer_feature f JOIN geo.layer l ON l.id = f.layer_id WHERE f.deleted_at IS NULL
UNION ALL SELECT 'ops.report_template (قوالب نموذجية)', count(*) FILTER (WHERE simulated AND status = 'approved'), count(*) FROM ops.report_template
UNION ALL SELECT 'snacr.special_risk (سجل المخاطر الأولي)', count(*) FILTER (WHERE simulated), count(*) FROM snacr.special_risk
UNION ALL SELECT 'snacr.dataset (سنوات أرشيف مولَّدة)', count(*) FILTER (WHERE simulated), count(*) FROM snacr.dataset
UNION ALL SELECT 'snacr.study (دراسات على سنوات [SIM])', count(*) FILTER (WHERE simulated AND status = 'current'), count(*) FROM snacr.study
UNION ALL SELECT 'snacr.plan (مخططات على سنوات [SIM])', count(*) FILTER (WHERE simulated AND status <> 'superseded'), count(*) FROM snacr.plan
UNION ALL SELECT 'content.guide_item (دليل غير مصادق طبيا)', count(*) FILTER (WHERE validated_at IS NULL AND NOT hidden), count(*) FROM content.guide_item
UNION ALL SELECT 'weather.grid_point (طقس محاكى)', count(*) FILTER (WHERE simulated), count(*) FROM weather.grid_point
UNION ALL SELECT 'weather.alert_suggestion (اقتراحات على طقس محاكى)', count(*) FILTER (WHERE simulated AND status = 'pending'), count(*) FROM weather.alert_suggestion
UNION ALL SELECT 'coastal.beach (طقس بحري محاكى)', count(*) FILTER (WHERE simulated), count(*) FROM coastal.beach
UNION ALL SELECT 'coastal.beach_day', count(*) FILTER (WHERE simulated AND day >= current_date), count(*) FROM coastal.beach_day
UNION ALL SELECT 'coastal.alert', count(*) FILTER (WHERE simulated AND acked_at IS NULL), count(*) FROM coastal.alert
UNION ALL SELECT 'coastal.risk_model (نموذج الغرق في الظل)', count(*) FILTER (WHERE simulated), count(*) FROM coastal.risk_model
UNION ALL SELECT 'sensor.device (مستشعرات محاكاة)', count(*) FILTER (WHERE simulated AND enabled), count(*) FROM sensor.device
UNION ALL SELECT 'reports.camera_tower (أبراج مراقبة محاكاة)', count(*) FILTER (WHERE simulated), count(*) FROM reports.camera_tower
UNION ALL SELECT 'reports.live_stream (بث محاكى source=sim)', count(*) FILTER (WHERE source = 'sim' AND status IN ('pending','live')), count(*) FROM reports.live_stream
UNION ALL SELECT 'telephony.call (مكالمات محاكاة source=sim)', count(*) FILTER (WHERE source = 'sim'), count(*) FROM telephony.call
UNION ALL SELECT 'org.prealert (إنذارات كاميرا محاكاة)', count(*) FILTER (WHERE simulated AND state = 'pending'), count(*) FROM org.prealert
UNION ALL SELECT 'forecast.run (توقعات على طقس محاكى)', count(*) FILTER (WHERE simulated), count(*) FROM forecast.run
UNION ALL SELECT 'decision.command_decision (اقتراحات محاكاة)', count(*) FILTER (WHERE simulated AND status = 'proposed'), count(*) FROM decision.command_decision
UNION ALL SELECT 'crisis.axis (محاور تمرين [SIM])', count(*) FILTER (WHERE name ~* '^\s*\[SIM\]' AND status = 'open'), count(*) FROM crisis.axis
UNION ALL SELECT 'ops.unit (وحدات العرض [SIM])', count(*) FILTER (WHERE name_ar LIKE '[SIM]%'), count(*) FROM ops.unit
UNION ALL SELECT 'ops.resource (وسائل العرض [SIM])', count(*) FILTER (WHERE label LIKE '[SIM]%'), count(*) FROM ops.resource
UNION ALL SELECT 'org.organization (مؤسسة العرض [SIM])', count(*) FILTER (WHERE name LIKE '[SIM]%'), count(*) FROM org.organization
ORDER BY sim_rows DESC, what;

-- Q54 · بيانات العرض [SIM] في العمليات (python -m app.demo seed)
-- الوصف: سيناريو العرض يكتب وحدات ووسائل وأعوانا ومؤسسة أسماؤها تبدأ بـ [SIM]، وبلاغات تُدخلها «[SIM] قاعة العرض»
--        (entered_by = 'ehimaya-staff:demo-seed') وتدخلات مرتبطة بها. هذا الاستعلام يعدّها لتُستبعد من الإحصاءات
--        الرسمية أو تُحذف بالطلب R16 في docs/sql/03-sim-to-real.sql.
SELECT 'reports.report' AS tbl, count(*) AS sim_rows
FROM reports.report WHERE entered_by = 'ehimaya-staff:demo-seed' OR entered_by_name LIKE '[SIM]%'
UNION ALL
SELECT 'ops.incident', count(DISTINCT incident_id)
FROM reports.report WHERE (entered_by = 'ehimaya-staff:demo-seed' OR entered_by_name LIKE '[SIM]%') AND incident_id IS NOT NULL
UNION ALL
SELECT 'ops.assignment', count(*) FROM ops.assignment WHERE "order" LIKE '[SIM]%'
UNION ALL
SELECT 'ops.field_agent', count(*) FROM ops.field_agent WHERE name LIKE '[SIM]%'
UNION ALL
SELECT 'inv.agent', count(*) FROM inv.agent WHERE full_name LIKE '[SIM]%';

-- Q55 · هل الطبقة المنشورة للمواطن تجريبية؟ (فحص أمان)
-- الوصف: طبقة [SIM] لا يجب أن تُنشر للعموم إلا لتجربة معلنة: هذا الاستعلام يعيد كل طبقة عامة منشورة وما زالت تجريبية.
--        ناتج فارغ = لا خطر أن يرى المواطن أماكن مخترعة.
SELECT l.key, l.name ->> 'ar' AS name, l.audience, l.status, l.simulated, l.to_verify
FROM geo.layer l
WHERE l.simulated AND l.audience = 'public' AND l.status = 'published' AND l.deleted_at IS NULL;

-- Q56 · مصدر كل سنة في أرشيف SNACR
-- الوصف: لكل سنة: ملف الديوان (office)، أو مولَّدة [SIM] (simulated)، أو مبنية من سجلات القاعات (live)، وعدد
--        أسطرها، ومن استوردها ومتى. السنة الحقيقية تحل محل السنة [SIM] بأكملها (لا خلط).
SELECT ds.year, ds.source, ds.simulated, ds.rows, ds.file_name, ds.imported_by_name, ds.imported_at
FROM snacr.dataset ds
ORDER BY ds.year;
