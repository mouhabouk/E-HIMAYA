// The relational model (phase 5, point 7): node build.js <dir from extract.py> <out.docx>
// Reads model.json and png/*.png written by extract.py next to the editable files (DBML and draw.io).
const fs = require('fs');
const path = require('path');
const L = require('../lib/ar-docx.js');
const { C, W, h1, h2, h3, p, note, ul, table, kv, image, toc, cover, document, save } = L;

const [dir, out] = process.argv.slice(2);
const M = JSON.parse(fs.readFileSync(path.join(dir, 'model.json'), 'utf8'));
const today = new Date().toISOString().slice(0, 10);
const bySchema = {};
for (const t of M.tables) (bySchema[t.schema] ||= []).push(t);
const desc = Object.fromEntries(M.tables.map(t => [t.key, t.description]));
const KIND = {
  '1:N': 'واحد إلى متعدد (إلزامي)',
  '1:0..N': 'واحد إلى متعدد (اختياري)',
  '1:1': 'واحد إلى واحد (إلزامي)',
  '1:0..1': 'واحد إلى واحد (اختياري)',
};
const ACT = { 'NO ACTION': 'منع', RESTRICT: 'منع', CASCADE: 'حذف متتالٍ', 'SET NULL': 'تفريغ', 'SET DEFAULT': 'القيمة الافتراضية' };
const fks = M.fks;
const cross = fks.filter(f => f.cross);
const count = k => fks.filter(f => f.kind === k).length;
const actCount = a => fks.filter(f => f.on_delete === a).length;
const hubs = Object.entries(fks.reduce((m, f) => ({ ...m, [f.to]: (m[f.to] || 0) + 1 }), {}))
  .sort((a, b) => b[1] - a[1]).slice(0, 12);

const children = [
  ...cover({
    title: 'النموذج العلائقي لقاعدة البيانات',
    subtitle: `${M.schemas.length} مخططا · ${M.tables.length} جدولا · ${fks.length} علاقة`,
    logo: path.join(__dirname, '..', '..', '..', 'apps', 'dashboard', 'public', 'brand', 'logo.png'),
    meta: [['الإصدار', '1.0 (المرحلة 5، النقطة 7)'], ['الترحيل', M.migration], ['التاريخ', today],
      ['المصدر', 'مستخرج آليا من قاعدة مرحَّلة إلى آخر ترحيل (data-model/extract.py)'],
      ['الملفات القابلة للتعديل', 'e-Himaya_Database.dbml و e-Himaya_Database.drawio'],
      ['المرافق', 'قاموس البيانات (وصف كل عمود) و e-Himaya_schema.sql']],
  }),
  ...toc(),
  h1('0. قراءة هذه الوثيقة'),
  p('هذه الوثيقة ترسم العلاقات بين جداول قاعدة البيانات وتصف كل علاقة: من يرتبط بمن، وبأي عمود، وبأي عدد، وماذا يحدث عند الحذف. وصف الأعمدة واحدا واحدا موجود في قاموس البيانات، فلا يتكرر هنا.'),
  h2('الرموز في الرسوم'),
  table([2600, W - 2600], ['الرمز', 'المعنى'], [
    ['رأس أزرق', 'جدول من المخطط المعروض في الصفحة'],
    ['رأس رمادي', 'جدول من مخطط آخر يرتبط به (يُعرض باسمه الكامل schema.table)'],
    ['(RLS)', 'جدول معزول حسب الولاية بسياسات Row-Level Security'],
    ['PK', 'مفتاح أساسي (بالأحمر)'],
    ['FK', 'مفتاح خارجي (بالأزرق)، والسهم يخرج منه نحو الجدول المرجعي'],
    ['خطّان ‖ عند الجدول المرجعي', 'سجل واحد بالضبط'],
    ['قدم الغراب مع خط', 'سجل أو أكثر (التابع إلزامي)'],
    ['قدم الغراب مع دائرة', 'صفر أو أكثر (المرجع اختياري: العمود يقبل الفراغ)'],
    ['+ n columns', 'أعمدة عادية غير معروضة؛ كلها في ملف DBML وفي القاموس'],
  ]),
  h2('أرقام العلاقات'),
  table([4600, 1600, W - 6200], ['العنصر', 'العدد', 'ملاحظة'], [
    ['العلاقات (مفاتيح خارجية)', String(fks.length), `منها ${cross.length} بين مخططين مختلفين`],
    ['واحد إلى متعدد إلزامي', String(count('1:N')), 'التابع لا يوجد دون أصله'],
    ['واحد إلى متعدد اختياري', String(count('1:0..N')), 'المرجع يقبل الفراغ'],
    ['واحد إلى واحد', String(count('1:1') + count('1:0..1')), 'امتداد لجدول (المفتاح الخارجي هو المفتاح الأساسي)'],
    ['حذف متتالٍ (CASCADE)', String(actCount('CASCADE')), 'التوابع جزء من أصلها (خطوات، مرفقات، أسطر)'],
    ['تفريغ عند الحذف (SET NULL)', String(actCount('SET NULL')), 'المرجع اختياري ويبقى السجل'],
    ['منع الحذف (NO ACTION أو RESTRICT)', String(actCount('NO ACTION') + actCount('RESTRICT')), 'الأصل لا يُحذف ما دام له توابع: الأثر محفوظ'],
  ]),
  h2('قواعد التصميم'),
  ...ul([
    'كل وحدة وظيفية في مخطط (schema) مستقل، والعلاقة بين المخططات تمر بمفتاح خارجي صريح أو بمعرّف منطقي موثّق.',
    'المرجع الجغرافي (geo.gouvernorat والمعتمديات) هو محور العزل: أغلب الجداول التشغيلية تحمل gouvernorat_code، وسياسات RLS تقرأه.',
    'الهويات من Keycloak لا تُنسخ: الأعمدة created_by و by_actor و subject تحمل معرّف الحساب (sub) ولا مفتاح خارجي لها، لأن الحساب يعيش خارج القاعدة. الاسم المعروض يُحفظ بجانبه (created_by_name) حتى يبقى الأثر مقروءا بعد حذف الحساب.',
    'السجلات الرقابية (event، log، history) تحفظ الأثر: في أغلبها يُمنع حذف الأصل ما دامت له أحداث، والإلغاء يتم بعمود حالة لا بالحذف.',
    'الأسطر التي لا معنى لها دون أصلها (خطوات القائمة، أسطر المستند، المرفقات) تُحذف معه (CASCADE).',
    'العمود version يحمي من الكتابة المتزامنة، والأعمدة _enc مشفّرة على مستوى الحقل؛ التفاصيل في قاموس البيانات.',
  ]),
  h2('الملفات القابلة للتعديل'),
  table([3000, W - 3000], ['الملف', 'كيف يُفتح ويُعدَّل'], [
    ['e-Himaya_Database.dbml', 'النموذج كاملا بكل الأعمدة والعلاقات والملاحظات العربية، بلغة DBML. يُفتح في dbdiagram.io (Import ثم DBML) أو dbdocs، ويتحول إلى SQL بالأداة @dbml/cli (dbml2sql) دون إنترنت.'],
    ['e-Himaya_Database.drawio', `${M.schemas.length + 1} صفحة: نظرة عامة ثم صفحة لكل مخطط، بالمواضع نفسها التي في هذه الوثيقة. يُفتح ويُعدَّل في diagrams.net أو تطبيق draw.io للحاسوب دون إنترنت، ويُصدَّر إلى PDF أو PNG أو SVG أو Visio.`],
    ['png/', 'الرسوم نفسها صورا، صورة لكل مخطط.'],
  ], { ltrCols: [0] }),
  note('تعديل الملفات يغيّر الرسم لا القاعدة: أي تغيير فعلي في البنية يمر بترحيل Alembic جديد، ثم يُعاد توليد هذه الملفات بالأمر extract.py.'),

  h1('1. النظرة العامة: العلاقات بين المخططات', { pageBreak: true }),
  p('كل صندوق مخطط وعدد جداوله، والرقم على السهم عدد المفاتيح الخارجية من مخطط إلى آخر. المخططات التي لا سهم لها مستقلة أو ترتبط بغيرها بمعرّفات منطقية فقط (حساب Keycloak أو رمز).'),
  image(path.join(dir, 'png', '00-overview.png'), 600, 820),
  h2('الجداول المحورية'),
  p('الجداول التي تشير إليها أكثر المفاتيح الخارجية. تغيير بنيتها يمسّ وحدات كثيرة، فيحتاج مراجعة أوسع.'),
  table([3800, 1400, W - 5200], ['الجدول', 'علاقات واردة', 'الدور'],
    hubs.map(([k, n]) => [k, String(n), desc[k] || '']), { ltrCols: [0] }),
  h2('العلاقات بين المخططات'),
  table([2900, 2000, 2900, W - 7800], ['الجدول التابع', 'العمود', 'الجدول المرجعي', 'النوع والحذف'],
    cross.map(f => [f.from, f.from_cols.join(', '), f.to, `${f.kind} · ${ACT[f.on_delete]}`]), { ltrCols: [0, 1, 2], size: 15 }),
];

M.schemas.forEach((s, i) => {
  const tables = bySchema[s.name];
  const rel = fks.filter(f => f.from.startsWith(s.name + '.'));
  children.push(h1(`${i + 2}. ${s.name}: ${s.description}`, { pageBreak: true }));
  children.push(p(`${tables.length} جدولا، و${rel.length} علاقة تخرج منه${rel.filter(f => f.cross).length ? `، منها ${rel.filter(f => f.cross).length} نحو مخططات أخرى` : ''}.`, { size: 19, color: C.muted }));
  children.push(image(path.join(dir, 'png', `${s.name}.png`), 600, 760));
  children.push(h3('الجداول'));
  children.push(table([2600, 900, W - 3500], ['الجدول', 'أعمدة', 'الوصف'],
    tables.map(t => [t.name + (t.rls ? ' (RLS)' : ''), String(t.columns), t.description]), { ltrCols: [0], size: 16 }));
  if (rel.length) {
    children.push(h3('العلاقات'));
    children.push(table([2000, 1900, 2300, 1500, W - 7700], ['الجدول التابع', 'العمود', 'الجدول المرجعي', 'النوع', 'عند حذف الأصل'],
      rel.map(f => [f.from.split('.')[1], f.from_cols.join(', '), f.cross ? f.to : f.to.split('.')[1], f.kind, ACT[f.on_delete]]),
      { ltrCols: [0, 1, 2, 3], size: 15 }));
    const kinds = [...new Set(rel.map(f => f.kind))];
    children.push(note(kinds.map(k => `${k}: ${KIND[k]}`).join(' · ')));
  } else {
    children.push(note('لا مفتاح خارجي يخرج من هذا المخطط: جداوله مستقلة أو ترتبط بمعرّفات منطقية.'));
  }
});

children.push(h1(`${M.schemas.length + 2}. إعادة التوليد`, { pageBreak: true }));
children.push(...ul([
  'قاعدة مرحَّلة إلى آخر ترحيل: alembic upgrade head في services/api.',
  'python3 docs/deliverables/data-model/extract.py <DSN> <مجلد>: يكتب DBML و draw.io والصور و model.json (يحتاج Graphviz).',
  'node docs/deliverables/data-model/build.js <مجلد> <ملف.docx>، ثم التحويل إلى PDF بـ LibreOffice.',
  'الأوصاف العربية للجداول والمخططات من data-dictionary/glossary.json، فهي مشتركة مع قاموس البيانات.',
]));

save(document({ title: 'النموذج العلائقي لقاعدة البيانات', children }), out);
