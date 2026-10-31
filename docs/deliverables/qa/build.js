// The defence question bank (phase 5): node build.js <out.docx> [out.json]
// Questions live in questions/NN-*.js, one file per domain: [level 1-4, question, model answer, academic depth, source].
// The Word file is for printing and rehearsal; the JSON feeds build_xlsx.py (the filterable spreadsheet).
const fs = require('fs');
const path = require('path');
const L = require('../lib/ar-docx.js');
const { C, WL, h1, h2, p, note, ul, table, cover, document, save } = L;

const LEVELS = { 1: 'أساسي', 2: 'متوسط', 3: 'متقدم', 4: 'تحدٍّ' };
const LEVEL_FILL = { 1: C.greenTint, 2: C.navyTint, 3: C.amberTint, 4: C.redTint };
const LEVEL_HINT = {
  1: 'تعريف أو وصف: يُجاب في جملتين، بدقة ودون تردد.',
  2: 'كيف ولماذا: الآلية والاختيار مع رقم أو مثال من المنظومة.',
  3: 'تحليل ومقارنة: الحدود، البدائل، والمرجع الأكاديمي.',
  4: 'سؤال نقدي أو محرج: الاعتراف بالحد، ثم الحجة، ثم الخطة.',
};

const dir = path.join(__dirname, 'questions');
const domains = fs.readdirSync(dir).filter(f => /^\d\d-.*\.js$/.test(f)).sort().map((f, i) => {
  const d = require(path.join(dir, f));
  const items = d.items.map((r, k) => ({ level: r[0], q: r[1], model: r[2], academic: r[3], source: r[4], order: k }))
    .sort((a, b) => a.level - b.level || a.order - b.order)
    .map((r, k) => ({ ...r, id: `${i + 1}.${String(k + 1).padStart(2, '0')}` }));
  for (const r of items) {
    if (!LEVELS[r.level] || !r.q || !r.model || !r.academic || !r.source) throw new Error(`${f}: incomplete row «${r.q}»`);
  }
  return { n: i + 1, key: d.key, title: d.title, items };
});
const all = domains.flatMap(d => d.items.map(r => ({ ...r, domain: d.title, domainN: d.n })));
const count = lv => all.filter(r => !lv || r.level === lv).length;
const today = new Date().toISOString().slice(0, 10);

const [out = 'e-Himaya_Banque_Questions.docx', jsonOut] = process.argv.slice(2);
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ levels: LEVELS, domains: domains.map(d => ({ n: d.n, title: d.title })), rows: all }, null, 1));

const W6 = [700, 900, 2700, 4300, 3658, 1700]; // id, level, question, model, academic, source (sum WL)
const children = [
  ...cover({
    title: 'بنك أسئلة المناقشة',
    subtitle: 'الأسئلة المحتملة للجنة، مبوّبة حسب الاختصاص ثم الصعوبة، مع الإجابة النموذجية والعمق الأكاديمي',
    lines: ['منظومة ذكية للتبليغ والمشاركة المجتمعية والمؤسساتية في مجال الوقاية والسلامة وإدارة المخاطر: من التبليغ إلى أخذ القرار'],
    meta: [['عدد الأسئلة', `${count()} سؤالا في ${domains.length} اختصاصا`], ['التاريخ', today],
      ['المصدر', 'الملف الوصفي V33، كراس الشروط، الملف التقني والأمني، عرض المناقشة'],
      ['الملف المرافق', 'e-Himaya_Banque_Questions.xlsx: الجدول نفسه بمرشّحات حسب الاختصاص والصعوبة']],
  }),
  h1('كيف يُستعمل هذا البنك'),
  p('كل سؤال في سطر واحد: رقمه (الاختصاص ثم الترتيب)، ومستوى صعوبته، ثم الإجابة النموذجية كما تُقال أمام اللجنة في نصف دقيقة، ثم العمق الأكاديمي (المفهوم والمرجع والمعيار) لمن يطلب التعمق، ثم المرجع في وثائق المشروع للعودة إليه.'),
  table([2000, WL - 2000], ['المستوى', 'ما ينتظره السائل وكيف يُجاب'],
    [1, 2, 3, 4].map(l => [`${LEVELS[l]} (${count(l)})`, LEVEL_HINT[l]]),
    { fills: (ri, ci) => (ci === 0 ? LEVEL_FILL[ri + 1] : undefined), boldCols: [0], size: 19 }),
  p('', { after: 120 }),
  h2('قواعد الإجابة أمام اللجنة'),
  ...ul([
    'ابدأ بالجواب في جملة، ثم الدليل (رقم مقيس أو مثال من المنظومة)، ثم المرجع إن طُلب التعمق.',
    'فرّق دائما بين المقيس والمقدّر: كل معطى محاكى موسوم [SIM]، وقل ذلك صراحة.',
    'في الأسئلة النقدية: اعترف بالحد، واذكر أثره، ثم الخطة لتجاوزه. لا تدافع عن ما لا يُدافع عنه.',
    'إن لم تعرف الجواب: قل ما تعرفه، وما الذي يلزم للإجابة، ولا تخترع رقما.',
    'الأرقام الأساسية في الاختصاص الأخير (أسئلة سريعة) تُحفظ عن ظهر قلب.',
  ]),
  h2('توزيع الأسئلة'),
  table([700, WL - 700 - 4 * 1300 - 1300, 1300, 1300, 1300, 1300, 1300], ['#', 'الاختصاص', ...[1, 2, 3, 4].map(l => LEVELS[l]), 'المجموع'],
    [...domains.map(d => [String(d.n), d.title, ...[1, 2, 3, 4].map(l => String(d.items.filter(r => r.level === l).length)), String(d.items.length)]),
      ['', 'المجموع', ...[1, 2, 3, 4].map(l => String(count(l))), String(count())]],
    { size: 18, fills: (ri) => (ri === domains.length ? C.navyTint : (ri % 2 ? C.zebra : undefined)) }),
];
for (const d of domains) {
  children.push(h1(`${d.n}. ${d.title}`, { pageBreak: true }));
  children.push(note(`${d.items.length} سؤالا: ` + [1, 2, 3, 4].map(l => `${LEVELS[l]} ${d.items.filter(r => r.level === l).length}`).join('، ')));
  children.push(table(W6, ['#', 'الصعوبة', 'السؤال', 'الإجابة النموذجية', 'العمق الأكاديمي', 'المرجع'],
    d.items.map(r => [r.id, LEVELS[r.level], r.q, r.model, r.academic, r.source]),
    { size: 17, boldCols: [2], fills: (ri, ci, row) => (ci === 1 ? LEVEL_FILL[d.items[ri].level] : (ri % 2 ? C.zebra : undefined)) }));
}

save(document({ title: 'بنك أسئلة المناقشة', sections: [{ landscape: true, children }] }), out)
  .then(() => console.log(`${count()} questions in ${domains.length} domains: ` + [1, 2, 3, 4].map(l => `${LEVELS[l]} ${count(l)}`).join(', ')));
