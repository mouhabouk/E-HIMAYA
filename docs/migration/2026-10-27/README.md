# حزمة ترحيل e-HIMAYA (ء-حماية) — 27 أكتوبر 2026

حصيلة جلسة الترحيل من ChatGPT إلى مشروع Claude «E-HIMAYA». المرجع الملزم هو ما اتُّفق عليه في مشروع Claude؛ ما يتعارض معه مذكور في الوثيقة ومتروك جانباً، وما هو فكرة جديدة أُدرج للدمج. لا يبدأ أي بند إلا بموافقة صاحب المشروع.


> **أماكن الملفات في المستودع:** الوثائق و`README.md` و`HANDOFF.md` هنا في `docs/migration/2026-10-27/`، والتصميم التقريبي في
> `docs/migration/2026-10-27/design/seasonal-programmes/`، والطبقات في `data/osm/`، والبرامج في `data/programmes/2026/`،
> والسكربتات في `scripts/data-prep/`. هذه الحزمة توثيق وبيانات فقط؛ لا تغيّر الشيفرة.

## المحتوى

| المسار | ما فيه |
| --- | --- |
| `HANDOFF.md` | **ابدأ من هنا**: ملخص القرارات، البنود 10–13، ما حُسم وما بقي معلّقاً، وتعليمات الدمج في المستودع |
| `docs/migration-e-himaya.md` / `.docx` | وثيقة الترحيل كاملة (نسخة من Claude Doc بتاريخ 27-10-2026) |
| `docs/summary-chatgpt-e-himaya.pdf` | حوصلة جلسات ChatGPT |
| `data/osm/layers/*_enriched.geojson` | 26 طبقة OSM مع اسم مقترح ودرجة ثقة لكل عنصر غير مسمّى (7,510 عنصراً) |
| `data/osm/osm_unnamed_names_review.xlsx` | ورقة مراجعة المدير (قبول / تعديل / رفض) مع ملخص بالمعادلات |
| `data/osm/beaches/` | طبقة الشواطئ المستكملة (267 شاطئاً) وملف مراجعتها |
| `data/osm/places_tn_overpass_2026-10-27.txt` | 1,800 تجمّع مسمّى من OSM (مرجع التموقع) |
| `data/osm/osm_review_public_layers.csv` | فحص الطبقات العامة (المشتبه فيها) |
| `data/programmes/2026/` | برامج التركيز الموسمية 2026: النموذج xlsx، النقاط csv، json، والمخطط program_schema.json |
| `scripts/` | السكربتات التي أنتجت البيانات (Python 3، تُشغَّل بـ `python3 -I`) |
| `design/seasonal-programmes-canvas/project/` | ملفات التصميم التقريبي «برامج التركيز الموسمية على الخريطة» |

## الروابط الحية

- وثيقة الترحيل: https://claude.ai/artifact/Dpj6GQpzWVvp7ZuTJrrJje
- حوصلة ChatGPT: https://claude.ai/artifact/FNKJWyhvMtd3ghr5afXpcz
- التصميم التقريبي: https://claude.ai/artifact/Xr9eagiv55KQddvWETvP7S

البيانات الجغرافية © OpenStreetMap contributors (ODbL).
