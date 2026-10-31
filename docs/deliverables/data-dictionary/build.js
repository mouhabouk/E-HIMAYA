// Data dictionary (review point 20, phase 4): node build.js dict.json out.docx
// dict.json comes from extract.py (live catalogue of a database migrated to head + glossary.json).
const fs = require('fs');
const path = require('path');
const L = require('../lib/ar-docx.js');
const { C, W, h1, h2, h3, p, note, ul, table, kv, toc, cover, document, save } = L;

const [src, out] = process.argv.slice(2);
const D = JSON.parse(fs.readFileSync(src, 'utf8'));
const today = new Date().toISOString().slice(0, 10);
const N = D.counts;
const yesno = b => (b ? 'نعم' : 'لا');
const shortType = t => t.replace('timestamp with time zone', 'timestamptz').replace('character varying', 'varchar')
  .replace('double precision', 'double').replace('geography(', 'geography(').replace(/^USER-DEFINED$/, 'enum');

const bySchema = {};
for (const t of D.tables) (bySchema[t.schema] ||= []).push(t);

const children = [
  ...cover({ title: 'قاموس البيانات', subtitle: `${N.schemas} مخططا · ${N.tables} جدولا · ${N.columns} عمودا`,
    logo: path.join(__dirname, '..', '..', '..', 'apps', 'dashboard', 'public', 'brand', 'logo.png'),
    meta: [['الإصدار', `2.0 (المرحلة 4، النقطة 20)، يحل محل 0.7.0 (الترحيل 0042، 24 أكتوبر 2026)`],
      ['الترحيل', D.migration], ['التاريخ', today],
      ['المصدر', 'مستخرج آليا من قاعدة مرحَّلة إلى آخر ترحيل (extract.py)، والأوصاف من glossary.json'],
      ['الملف المرافق', 'e-Himaya_schema.sql: البنية الكاملة (الجداول والفهارس والقيود والدوال وسياسات الأمان)']] }),
  ...toc(),
  h1('0. قراءة هذا القاموس'),
  p('هذا القاموس مستخرج آليا من القاعدة الفعلية بعد تطبيق كل الترحيلات، فهو مطابق للشيفرة. يعيد السكريبت extract.py قراءة الفهرس عند كل مرحلة، ويرفض إنتاج القاموس إن ظهر جدول أو عمود بلا وصف في glossary.json.'),
  ...ul([
    `المحرك: PostgreSQL 17 في الإنتاج مع الامتدادات ${D.extensions.join('، ')}. PostGIS للمعطيات الجغرافية (geometry و geography)، و pgvector للبحث الدلالي (vector)، و pg_trgm للبحث التقريبي في الأسماء.`,
    'المعرّفات: UUID في أغلب الجداول. «PK» مفتاح أساسي، و«FK →» مفتاح خارجي نحو الجدول المذكور، و«UQ» قيمة فريدة.',
    `الأعمدة التي ينتهي اسمها بـ _enc مشفّرة على مستوى الحقل (AES-256-GCM) قبل الحفظ (${N.encrypted_columns} عمودا)، والتي تنتهي بـ _hash أو _hmac بصمات تسمح بالبحث دون كشف القيمة.`,
    `الجداول المعلّمة «عزل حسب الولاية» (${N.rls_tables} جدولا) محمية بسياسات Row-Level Security: لا يرى عون جهوي إلا معطيات ولايته، ويعمل التطبيق بدور ehimaya_app الذي لا يملك أي جدول ولا يتجاوز السياسات.`,
    'الملف الطبي المقفل والرأي الطبي مشفّران على هاتف صاحبهما، ولا يملك الخادم مفتاح فكّهما.',
    'العمود version يُستعمل للتزامن المتفائل: يرفض التعديل إن تغيّر السجل منذ قراءته.',
    'ما يحمل الشارة [SIM] معطيات مولّدة للتجربة (مثلا snacr.dataset.generated)، وتعوّضها معطيات الديوان متى وصلت.',
  ]),
  h2('أرقام القاعدة'),
  table([4000, 2000, 3638], ['العنصر', 'العدد', 'ملاحظة'], [
    ['المخططات (schemas)', String(N.schemas), 'كل وحدة وظيفية في مخطط مستقل'],
    ['الجداول', String(N.tables), `منها ${N.rls_tables} بعزل حسب الولاية`],
    ['الأعمدة', String(N.columns), `منها ${N.encrypted_columns} مشفّرة على مستوى الحقل`],
    ['الدوال والإجراءات', String(D.functions), 'خارج دوال الامتدادات'],
    ['آخر ترحيل', D.migration, 'Alembic، صعودا ونزولا'],
  ]),
  h2('المخططات (schemas)'),
  table([1900, 5638, 2100], ['المخطط', 'المجال', 'عدد الجداول'],
    D.schemas.map(s => [s.name, s.description, String(bySchema[s.name].length)]), { ltrCols: [0] }),
];

D.schemas.forEach((s, si) => {
  children.push(h1(`${si + 1}. ${s.name}: ${s.description}`, { pageBreak: true }));
  for (const t of bySchema[s.name]) {
    children.push(h3(`${t.schema}.${t.name}`));
    const flags = [];
    if (t.rls) flags.push(`عزل حسب الولاية (RLS، ${t.policies} سياسة)`);
    if (t.triggers) flags.push(`${t.triggers} زناد`);
    flags.push(`${t.indexes} فهرس`);
    children.push(p(`${t.description}  ·  ${flags.join(' · ')}`, { size: 19, color: C.muted }));
    children.push(table([2300, 1700, 700, 1900, 3038], ['العمود', 'النوع', 'فارغ؟', 'المفتاح', 'الوصف'],
      t.columns.map(c => [c.name, shortType(c.type), yesno(c.nullable),
        [c.pk ? 'PK' : '', c.unique ? 'UQ' : '', c.fk ? `FK → ${c.fk}` : ''].filter(Boolean).join(' '), c.description]),
      { ltrCols: [0, 1, 3], size: 16 }));
    if (t.checks.length) children.push(note(`القيود: ${t.checks.slice(0, 6).join(' ؛ ')}${t.checks.length > 6 ? ` … (+${t.checks.length - 6})` : ''}`));
  }
});

save(document({ title: 'قاموس البيانات', children }), out);
