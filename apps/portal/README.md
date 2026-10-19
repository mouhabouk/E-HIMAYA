# ء-حماية · بوابة المؤسسات (المرحلة 4)

بوابة ويب للمؤسسات: تسجيل المؤسسة وبطاقتها، فريق السلامة، سجلّ المواد الخطرة والمعدّات، خريطة نقاط
الإخلاء (ضمن 2 كم)، الوثائق (رفع tus قابل للاستئناف)، الأعضاء والدعوات، البلاغات باسم المؤسسة،
وشهادة السلامة الرقمية مع صفحة تحقّق عامة `/verify/:code` (مقارنة بصمة SHA-256 لملف PDF محليا).
تعتمد العقود `docs/api/phase-4-contract.md` و`phase-2-contract.md` و`phase-3-contract.md`.

- الدخول: Keycloak realm `ehimaya-public`، عميل عام `ehimaya-portal` (Authorization Code + PKCE S256)،
  إنشاء حساب عبر `prompt=create`.
- اللغات: العربية (افتراضية، RTL)، الفرنسية، الإنجليزية — مفاتيح متطابقة في `src/i18n/{ar,fr,en}.json`.
- المنفذ المحلي: 5174.

## متغيرات البيئة

انسخ `.env.example` إلى `.env.local`. لكل قيمة قيمة افتراضية للتطوير.

| المتغير | الافتراضي | الدور |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | عنوان الواجهة البرمجية |
| `VITE_OIDC_ISSUER` | `http://localhost:8080/realms/ehimaya-public` | مُصدِر OIDC |
| `VITE_OIDC_CLIENT_ID` | `ehimaya-portal` | عميل Keycloak العام |
| `VITE_TUS_ENDPOINT` | `http://localhost:1080/api/v1/uploads/` | نقطة رفع tus 1.0 (الشرطة الأخيرة مهمة) |
| `VITE_MAP_STYLE_URL` | فارغ | نمط MapLibre اختياري (وإلا خلفية OSM نقطية) |

## الأوامر

```sh
npm ci               # تثبيت مطابق لملف القفل
npm run dev          # خادم التطوير على http://localhost:5174
npm run lint         # ESLint دون أي تحذير
npm run typecheck    # TypeScript (strict)
npm test             # Vitest + Testing Library (jsdom)
npm run build        # بناء الإنتاج في dist/
```

ملاحظة: `npm install` بالإصدار 10.9 يتعطّل (خطأ arborist `edgesOut`)؛ لتحديث `package-lock.json`
استعمل `npx npm@11 install`. أما `npm ci` فيعمل بالإصدارين.
