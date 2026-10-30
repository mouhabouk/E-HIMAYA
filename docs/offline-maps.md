# خادم الخرائط المحلي للمكتب: دليل التنصيب خطوة بخطوة

هذا الدليل يجهّز خادم خرائط داخل شبكة الديوان الوطني للحماية المدنية يخدم كل ما تحتاجه المنظومة من خرائط دون أي
طلب يخرج من الشبكة:

- خريطة الشوارع التونسية (بلاطات متجهة من OpenStreetMap) بأسماء عربية أولا.
- صور القمر الصناعي.
- أسماء الأماكن والطرق فوق صور القمر الصناعي (الوضع الهجين).
- الخطوط التي تُرسم بها الأسماء.
- ملف الطرقات نفسه لمحرك الملاحة (Valhalla).

التصميم والقرارات في `docs/phase-m/design-m.md` §8.

> المبدأ: **تحضير مرة واحدة على جهاز متصل بالإنترنت، ثم نقل مجلد واحد إلى الخادم**. بعد ذلك يعمل كل شيء دون إنترنت.

## 1. المكوّنات

| المكوّن | الدور | الرخصة |
|---|---|---|
| [TileServer GL](https://github.com/maptiler/tileserver-gl) 5.7.0 | يخدم البلاطات المتجهة والصور ويرسم البلاطات النقطية للتطبيق | BSD-2 |
| [Planetiler](https://github.com/onthegomap/planetiler) 0.10.2 | يبني بلاطات تونس المتجهة بمخطط OpenMapTiles من ملف OpenStreetMap | Apache 2.0 |
| بيانات OpenStreetMap (مستخرج Geofabrik لتونس) | الشوارع والمباني والمياه والأسماء | ODbL 1.0: ذكر «© OpenStreetMap contributors» إلزامي |
| [خطوط OpenMapTiles](https://github.com/openmaptiles/fonts) 2.0 | خطوط Noto Sans الجاهزة للخريطة، ومنها العربية | SIL OFL 1.1 |
| صور Sentinel‑2 cloudless 2020 (EOX) | صور القمر الصناعي المفتوحة، بدقة 10 م | CC BY-NC-SA 4.0: الاستعمال غير التجاري وذكر المصدر |
| GDAL 3.13 (اختياري) | تحويل صور المكتب (صور جوية، فسيفساء Copernicus) إلى ملف MBTiles | MIT |

كل الصور (images) مثبّتة ببصمتها (digest) في `infra/compose.yml`.

### الأنماط

الأنماط محفوظة في المستودع (`infra/maps/styles`):

- `ehimaya-streets`: خريطة شوارع هادئة الألوان، الأسماء بالعربية ثم بالاسم المحلي.
- `ehimaya-labels`: الطرق الكبرى والأسماء بخط أبيض بهالة داكنة، بخلفية شفافة توضع فوق صور القمر الصناعي.

## 2. ما يلزم

### جهاز التحضير

جهاز متصل بالإنترنت، عليه Docker و Docker Compose، ونسخة من المستودع.

### الخادم

- **العتاد:** معالجان (2 vCPU) وذاكرة 2 غيغابايت تكفي الخدمة.
- **القرص:**

| الملف | الحجم التقريبي |
|---|---|
| `tunisia.mbtiles` (البلاطات المتجهة حتى التقريب 14) | 200 إلى 300 ميغابايت |
| `sources/` (مستخرج تونس ومصادر البحر والبحيرات) | نحو 1.5 غيغابايت، يمكن حذفه من الخادم بعد البناء، ما عدا `tunisia.osm.pbf` إن كانت الملاحة مفعّلة |
| `satellite.mbtiles` حتى التقريب 14 | نحو 1.7 غيغابايت |
| `satellite.mbtiles` حتى التقريب 15 أو 16 | تضيف نحو 5 غيغابايت أو نحو 20 غيغابايت |
| `fonts/` | نحو 100 ميغابايت |

### التقدير قبل التنزيل

`SAT_COUNT_ONLY=1` يحسب عدد صور القمر الصناعي وحجمها لكل مستوى تقريب دون تنزيل شيء (الخطوة 3.3).

## 3. التحضير (على جهاز متصل بالإنترنت)

نفّذ كل الأوامر من جذر المستودع. النتائج كلها تُكتب في `infra/maps/data/`، وهذا المجلد لا يُرفع إلى Git أبدا.

### 3.1 البلاطات المتجهة لتونس

```bash
docker compose -f infra/compose.yml --profile maps-prepare run --rm maps-tiles
```

ما يفعله الأمر:

- ينزّل Planetiler مستخرج تونس من Geofabrik ومصادر البحر والبحيرات إلى `infra/maps/data/sources/`.
- ثم يبني `infra/maps/data/tunisia.mbtiles` بالأسماء العربية والفرنسية والإنجليزية (`--languages=ar,fr,en`).
- المدة بين 5 و15 دقيقة.

بعد انتهائه، سجّل بصمة المستخرج، فهي تلزم الملاحة (الخطوة 6.4) وتوثّق النسخة المستعملة:

```bash
sha256sum infra/maps/data/sources/tunisia.osm.pbf
```

### 3.2 الخطوط

```bash
docker compose -f infra/compose.yml --profile maps-prepare run --rm maps-fonts
```

- يطبع الأمر بصمة الملف المنزّل. سجّلها في `.env` تحت اسم `MAPS_FONTS_SHA256`، فيرفض أي ملف آخر في المرات القادمة.
- تحقّق من وجود الحروف العربية:

  ```bash
  ls -l "infra/maps/data/fonts/Noto Sans Regular/1536-1791.pbf"
  ```

  إذا كان الملف غائبا، ظهر تنبيه، ولن تظهر الأسماء العربية بهذا الخط.

### 3.3 صور القمر الصناعي

**الطريقة الأولى: نسخة من صور Sentinel‑2 المفتوحة.**

قدّر الحجم أولا:

```bash
SAT_COUNT_ONLY=1 docker compose -f infra/compose.yml --profile maps-prepare run --rm maps-satellite
```

ثم انسخ الصور، حتى التقريب 14 افتراضيا. يمكن إيقاف النسخ واستئنافه، فالصور المنسوخة لا تُطلب مرة ثانية.

```bash
docker compose -f infra/compose.yml --profile maps-prepare run --rm maps-satellite
```

ما ينسخه:

- الصور التي تغطي الولايات فقط، مع هامش.
- بعدد قليل من الطلبات في آن واحد، وكل صورة يُتحقّق أنها صورة فعلا.

لتغيير المصدر أو آخر مستوى تقريب، استعمل `SAT_URL` و`SAT_MAX_ZOOM` و`SAT_ATTRIBUTION` في `.env`. لا تستعمل مصدرا إلا
بإذن صاحبه وحسب رخصته: رخصة EOX تسمح بالاستعمال غير التجاري مع ذكر المصدر، وهو حال الحماية المدنية.

**الطريقة الثانية: صور المكتب.** صور جوية من المركز الوطني لرسم الخرائط والاستشعار عن بعد (CNCT)، أو فسيفساء
Copernicus، أو صور مزوّد متعاقد معه.

1. ضع الصورة بصيغة GeoTIFF في `infra/maps/data/sources/satellite.tif`.
2. نفّذ:

   ```bash
   docker compose -f infra/compose.yml --profile maps-prepare run --rm maps-satellite-import
   ```

   يعيد GDAL إسقاط الصورة إلى EPSG:3857، ثم يكتب `satellite.mbtiles` بصيغة JPEG، ثم يضيف المستويات الأقل تقريبا.

### 3.4 النقل إلى الخادم

انقل المجلد كله إلى الخادم (قرص خارجي، أو `rsync` داخل الشبكة) في المكان نفسه: `infra/maps/data/` داخل نسخة المستودع
على الخادم.

```bash
rsync -a --info=progress2 infra/maps/data/ server:/opt/e-himaya/infra/maps/data/
```

## 4. التشغيل على الخادم

```bash
docker compose --env-file .env -f infra/compose.yml --profile maps up -d
```

### ما يحدث

1. `maps-config` يكتب `data/config.json` حسب الملفات الموجودة:
   - البلاطات المتجهة لازمة.
   - الصور اختيارية: الخادم يعمل دونها، ويخدمها حين تُنسخ ويُعاد التشغيل.
   - يرفض البدء إذا غابت البلاطات أو الخطوط، ويقول ما الذي ينقص.
2. ثم يبدأ `maps` (TileServer GL).

### العناوين

- **التطوير:** على `http://localhost:8091` (من الخادم نفسه فقط).
- **الإنتاج:** مع `infra/compose.prod.yml`، لا منفذ مفتوحا للخادم. يمرّ كل شيء عبر Caddy على
  `https://API_HOST/maps/`، للقراءة فقط.

```bash
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml --profile maps up -d
```

### صفحة الخادم

صفحة `https://API_HOST/maps/` تعرض الأنماط والبيانات وتسمح بمعاينتها.

## 5. التحقق

نفّذ هذه الأوامر من الخادم، أو من أي جهاز في الشبكة، بعد استبدال `API_HOST`:

```bash
# الخادم حي
curl -fsS https://API_HOST/maps/health
# النمطان والبيانات
curl -fsS https://API_HOST/maps/styles.json | head
curl -fsS https://API_HOST/maps/data/tunisia.json | head
# بلاطة من صفاقس (التقريب 12) بالنمط، وصورة القمر الصناعي نفسها
curl -fsS -o /tmp/sfax.png https://API_HOST/maps/styles/ehimaya-streets/12/2170/1624.png && file /tmp/sfax.png
curl -fsS -o /tmp/sfax.jpg https://API_HOST/maps/data/satellite/12/2170/1624.jpg && file /tmp/sfax.jpg
# الخط العربي
curl -fsS -o /dev/null -w '%{http_code}\n' "https://API_HOST/maps/fonts/Noto%20Sans%20Regular/1536-1791.pbf"
```

**الاختبار الحاسم:** اقطع الإنترنت عن الخادم (أو امنع الخروج في جدار الحماية)، ثم افتح لوحة القيادة والبوابة والتطبيق.
يجب أن تظهر الخريطة وصور القمر الصناعي والأسماء العربية كاملة. في أدوات المطوّر في المتصفح (تبويب الشبكة)، لا يجب أن
يظهر أي طلب إلى نطاق غير نطاقات المكتب.

## 6. توجيه المنظومة إلى الخادم المحلي

اكتب في `.env`، مع استبدال `API_HOST` باسم الخادم:

### 6.1 لوحة القيادة والبوابة

```bash
MAP_STYLE_URL=https://API_HOST/maps/styles/ehimaya-streets/style.json
```

- يُقرأ عند بناء الصورتين، فأعد البناء بعد تغييره:
  `docker compose ... -f infra/compose.prod.yml up -d --build dashboard portal`
- النمط والبلاطات والخطوط كلها من `API_HOST`، وهو مسموح أصلا في سياسة أمن المحتوى (CSP)، فلا حاجة إلى `CSP_MAP_SRC`.
- MapLibre 6 يرسم العربية ويرتّب النص من اليمين إلى اليسار بنفسه، دون أي إضافة خارجية.

### 6.2 خلفية القمر الصناعي (الواجهة البرمجية)

```bash
BASEMAP_OPEN_TILES=https://API_HOST/maps/data/satellite/{z}/{x}/{y}.jpg
BASEMAP_OPEN_ATTRIBUTION=Sentinel-2 cloudless – s2maps.eu by EOX IT Services GmbH (Copernicus 2020) – نسخة المكتب
BASEMAP_OPEN_MAX_ZOOM=14
BASEMAP_LABEL_TILES=https://API_HOST/maps/styles/ehimaya-labels/{z}/{x}/{y}.png
BASEMAP_LABEL_ATTRIBUTION=© OpenStreetMap contributors
```

- أعد تشغيل `api`.
- مفتاح «خريطة / قمر صناعي / هجين» في الخرائط يستعمل هذه المصادر بدل المصادر العامة.
- المزوّد المدفوع، إن فعّلته الإدارة، يبقى أولى منها.

### 6.3 تطبيق الهاتف

يُحدَّد العنوان عند بناء التطبيق:

```bash
flutter build apk --release \
  --dart-define=MAP_TILE_URL=https://API_HOST/maps/styles/ehimaya-streets/{z}/{x}/{y}.png \
  --dart-define=MAP_ATTRIBUTION="© OpenStreetMap contributors"
```

### 6.4 محرك الملاحة (Valhalla)

يبني الطرقات من الملف نفسه دون تنزيل:

```bash
ROUTING_OSM_URL=file:///sources/tunisia.osm.pbf
ROUTING_OSM_SHA256=<البصمة المسجّلة في الخطوة 3.1>
ROUTING_URL=http://routing:8002
```

ثم:

```bash
docker compose --env-file .env -f infra/compose.yml --profile routing up -d
```

## 7. التحديث

- **خريطة OpenStreetMap:** تتغيّر كل يوم. يكفي تحديثها كل ثلاثة إلى ستة أشهر:
  1. أعد الخطوة 3.1 على جهاز التحضير.
  2. انقل `tunisia.mbtiles` و`sources/tunisia.osm.pbf`.
  3. أعد تشغيل `maps`.
  4. للملاحة، حدّث `ROUTING_OSM_SHA256` وأعد تشغيل `routing-prepare`، فيبني الطرقات الجديدة بجانب القديمة ثم يبدّل
     إليها.
- **صور القمر الصناعي:** تُحدَّث عند توفّر صور أحدث يملك المكتب حق استعمالها.
- **الحدود الإدارية (Map Tunisia):** مستقلة عن هذا الخادم، وهي في قاعدة البيانات (الترحيل 0079، `scripts/admin_reference.py`).

## 8. استكشاف الأعطال

| العَرَض | السبب والحل |
|---|---|
| `maps` لا يبدأ و`maps-config` يقول `tunisia.mbtiles is missing` | الخطوة 3.1 لم تتم، أو المجلد نُقل إلى مكان آخر |
| الخريطة تظهر دون أسماء عربية | `1536-1791.pbf` غائب من الخط (الخطوة 3.2) |
| `502` على `https://API_HOST/maps/` | الملف الشخصي `maps` غير مشغّل: `docker compose ... --profile maps ps` |
| الصور رمادية في الوضع الهجين | `satellite.mbtiles` غائب، أو `BASEMAP_OPEN_TILES` لا يشير إلى `.../data/satellite/...` |
| `checksum mismatch` في الخطوط أو الملاحة | الملف تغيّر عند المصدر: تحقّق منه، ثم حدّث البصمة المسجّلة |
| نسخ الصور بطيء أو يتوقف | المصدر يحدّ الطلبات. أعد الأمر نفسه فيكمل من حيث توقّف، أو قلّل `SAT_WORKERS` |
