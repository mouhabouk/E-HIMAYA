// Graduation project defence deck (Arabic, right to left, 30 slides), in the style of a strategy-consulting deck:
// every title is the slide's conclusion, a section tracker on top, the source of each figure at the bottom.
//   cd docs/deliverables/presentation && node prep.js && node build-thesis.js e-Himaya_Soutenance.pptx
// Editable in PowerPoint: layouts with placeholders (New Slide offers them), native charts and tables, a fade
// transition and an "After" time on every slide, content that fades in object by object (Animations tab).
// Figures come from the project files (description V33, phase reports); simulated figures carry [SIM].
const pptxgen = require('pptxgenjs');
const fs = require('fs');
const { applyTheme } = require(process.env.PPTX_SKILL + '/scripts/apply_theme.js');
const { applyTransitions, mmss } = require('../lib/transitions');

const OUT = process.argv[2] || 'e-Himaya_Soutenance.pptx';
const THEME = {
  name: 'e-Himaya defence',
  headFontFace: 'Arial',
  bodyFontFace: 'Arial',
  colors: {
    dk1: '182038', lt1: 'FFFFFF', dk2: '0E1426', lt2: 'F3F5FA',
    accent1: '1F3FA0', accent2: 'D7141A', accent3: 'C9A227', accent4: '188038', accent5: '7838A0', accent6: '00806A',
    hlink: '1F3FA0', folHlink: '5E2A80',
  },
};
const HEX = { ink: '182038', deep: '0E1426', navy: '1F3FA0', red: 'D7141A', gold: 'C9A227', goldLight: 'F2E3B3', green: '188038',
  purple: '7838A0', teal: '00806A', orange: 'C25E00', muted: '5B6478', line: 'DDE2EC', page: 'F3F5FA', amber: 'F5B400', white: 'FFFFFF', pale: 'A6AFC4' };
const TINT = { navy: 'E8EDFA', red: 'FDE8E8', green: 'E6F4EA', purple: 'F2EAF8', teal: 'E0F3EF', orange: 'FFF3D6', gold: 'FBF5E2', slate: 'EEF0F4' };
const W = 13.333, H = 7.5, M = 0.6;
const AR = { rtlMode: true, lang: 'ar-TN' };
const img = n => 'img/' + n;
const shadow = () => ({ type: 'outer', color: HEX.ink, opacity: 0.08, blur: 6, offset: 2, angle: 90 });

// The talk's time plan (seconds per slide, about 24 minutes), stored as each slide's "After" time and in its notes.
const MIN = [40, 75, 30, 15, 50, 50, 50, 45, 15, 45, 45, 50, 45, 15, 50, 50, 45, 50, 50, 45, 50, 50, 15, 55, 50, 55, 45, 50, 50, 40];
const SECTIONS = ['السياق والإشكالية', 'الإطار والمنهجية', 'الحل المقترح', 'النتائج والتقييم', 'الخلاصة والآفاق'];

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.rtlMode = true;
pres.title = 'ء-حماية: عرض مشروع التخرج';
pres.author = 'e-Himaya';
pres.subject = 'منظومة ذكية للتبليغ والمشاركة المجتمعية والمؤسساتية في مجال السلامة والوقاية وإدارة الأخطار';
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---------- Layouts (PowerPoint: Home > New Slide lists them) ----------
const FOOT = 'ء-حماية · من التبليغ إلى أخذ القرار';
const ph = (name, type, o) => ({ placeholder: { options: { name, type, margin: 0, align: 'right', ...AR, ...o }, text: '' } });
pres.defineSlideMaster({
  title: 'غلاف',
  background: { color: C.text2 },
  objects: [
    { rect: { x: 0, y: H - 0.12, w: W, h: 0.12, fill: { color: HEX.gold } } },
    ph('title', 'title', { x: M, y: 2.0, w: W - 2 * M - 2.9, h: 1.9, fontSize: 34, bold: true, color: C.background1, valign: 'bottom' }),
    ph('body', 'body', { x: M, y: 4.05, w: W - 2 * M - 2.9, h: 0.6, fontSize: 20, bold: true, color: HEX.gold, valign: 'top' }),
  ],
});
pres.defineSlideMaster({
  title: 'فاصل قسم',
  background: { color: C.text2 },
  objects: [
    { rect: { x: W - M - 0.12, y: 2.55, w: 0.12, h: 2.4, fill: { color: HEX.gold } } },
    ph('num', 'body', { x: M, y: 2.5, w: W - 2 * M - 0.45, h: 0.7, fontSize: 22, bold: true, color: HEX.gold }),
    ph('title', 'title', { x: M, y: 3.15, w: W - 2 * M - 0.45, h: 1.0, fontSize: 40, bold: true, color: C.background1, valign: 'middle' }),
    ph('body', 'body', { x: M, y: 4.2, w: W - 2 * M - 0.45, h: 0.8, fontSize: 18, color: HEX.pale }),
  ],
  slideNumber: { x: M, y: H - 0.5, w: 0.6, h: 0.3, fontSize: 10, color: HEX.pale, align: 'left', valign: 'middle' },
});
pres.defineSlideMaster({
  title: 'محتوى',
  background: { color: C.background1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { line: { x: M, y: 1.68, w: W - 2 * M, h: 0, line: { color: HEX.line, width: 1 } } },
    { rect: { x: W - M - 0.9, y: 1.655, w: 0.9, h: 0.05, fill: { color: HEX.gold } } },
    { line: { x: M, y: H - 0.55, w: W - 2 * M, h: 0, line: { color: HEX.line, width: 0.75 } } },
    { image: { x: W - M - 0.3, y: H - 0.46, w: 0.3, h: 0.3, path: img('logo.png') } },
    { text: { text: FOOT, options: { x: W - M - 6.4, y: H - 0.47, w: 6.0, h: 0.32, fontSize: 10, color: HEX.muted, align: 'right', valign: 'middle', margin: 0, ...AR } } },
    ph('title', 'title', { x: M, y: 0.66, w: W - 2 * M, h: 0.95, fontSize: 24, bold: true, color: C.text1, valign: 'middle' }),
    ph('source', 'body', { x: M, y: H - 0.88, w: W - 2 * M, h: 0.3, fontSize: 10, color: HEX.muted, valign: 'bottom' }),
  ],
  slideNumber: { x: M, y: H - 0.47, w: 0.6, h: 0.32, fontSize: 10, color: HEX.muted, align: 'left', valign: 'middle' },
});

// ---------- Helpers ----------
const slides = [], sectionsAdded = new Set();
function newSlide(master, section) {
  if (!sectionsAdded.has(section)) { pres.addSection({ title: section }); sectionsAdded.add(section); }
  const s = pres.addSlide({ masterName: master, sectionTitle: section });
  s.k = slides.length; slides.push(s);
  return s;
}
function notes(s, t) {
  const done = MIN.slice(0, s.k + 1).reduce((a, b) => a + b, 0), all = MIN.reduce((a, b) => a + b, 0);
  s.addNotes(`⏱ ${mmss(MIN[s.k])} لهذه الشريحة · ${mmss(done)} من ${mmss(all)} عند نهايتها\n\n${t}`);
}
function text(s, t, o) {
  s.addText(t, { isTextBox: true, margin: 0, align: 'right', valign: 'top', color: C.text1, fontSize: 15, ...AR, ...o });
}
// The tracker: the five sections, the current one filled. Named "trk" so it does not animate.
function tracker(s, sec) {
  const cw = 2.18, gap = 0.08;
  SECTIONS.forEach((t, i) => {
    const x = W - M - (i + 1) * cw - i * gap, on = i === sec;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.28, w: cw, h: 0.06, fill: { color: on ? HEX.navy : HEX.line }, line: { color: on ? HEX.navy : HEX.line, width: 0 }, objectName: `trk bar ${i}` });
    text(s, `${i + 1}. ${t}`, { x, y: 0.36, w: cw, h: 0.24, fontSize: 10, bold: on, color: on ? HEX.navy : HEX.muted, objectName: `trk ${i}` });
  });
}
function content(sec, title, source) {
  const s = newSlide('محتوى', SECTIONS[sec]);
  tracker(s, sec);
  s.addText(title, { placeholder: 'title', ...AR });
  if (source) s.addText(source, { placeholder: 'source', ...AR });
  return s;
}
function divider(sec, sub) {
  const s = newSlide('فاصل قسم', SECTIONS[sec]);
  s.addText(`القسم ${sec + 1} من ${SECTIONS.length}`, { placeholder: 'num', ...AR });
  s.addText(SECTIONS[sec], { placeholder: 'title', ...AR });
  s.addText(sub, { placeholder: 'body', ...AR });
  return s;
}
function card(s, x, y, w, h, o = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: o.fill || HEX.white },
    line: { color: o.line || HEX.line, width: 0.75 }, shadow: o.flat ? undefined : shadow() });
}
function tile(s, x, y, size, tone, icon) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: size, h: size, rectRadius: size * 0.22, fill: { color: HEX[tone] }, line: { color: HEX[tone], width: 0 } });
  const p = size * 0.2;
  s.addImage({ path: img('w-' + icon + '.png'), x: x + p, y: y + p, w: size - 2 * p, h: size - 2 * p, altText: '' });
}
function stat(s, x, y, w, h, n, label, tone, o = {}) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: TINT[tone] || HEX.page }, line: { color: TINT[tone] || HEX.page, width: 0 } });
  s.addShape(pres.shapes.RECTANGLE, { x: x + w - 0.07, y, w: 0.07, h, fill: { color: HEX[tone] }, line: { color: HEX[tone], width: 0 } });
  text(s, n, { x: x + 0.2, y: y + 0.15, w: w - 0.45, h: 0.75, fontSize: o.fs || 32, bold: true, color: HEX[tone], valign: 'middle' });
  text(s, label, { x: x + 0.2, y: y + 0.92, w: w - 0.45, h: h - 1.0, fontSize: 13, color: HEX.ink });
}
function bullets(s, list, x, y, w, h, fs = 16) {
  text(s, list.map((p, k) => ({ text: p, options: { bullet: { indent: 16 }, breakLine: k < list.length - 1 } })), { x, y, w, h, fontSize: fs, paraSpaceAfter: 8 });
}
function sim(s, x, y) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.7, h: 0.32, rectRadius: 0.16, fill: { color: HEX.amber }, line: { color: HEX.amber, width: 0 } });
  text(s, 'بيانات تجريبية [SIM]', { x, y, w: 1.7, h: 0.32, fontSize: 10, bold: true, align: 'center', valign: 'middle' });
}
const size = f => { const b = fs.readFileSync(f); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; };
function shot(s, name, x, y, maxW, maxH, alt) {
  const { w, h } = size(img(name)); const k = Math.min(maxW / w, maxH / h);
  const ww = w * k, hh = h * k, xx = x + (maxW - ww) / 2, yy = y + (maxH - hh) / 2;
  s.addShape(pres.shapes.RECTANGLE, { x: xx - 0.05, y: yy - 0.05, w: ww + 0.1, h: hh + 0.1, fill: { color: HEX.white }, line: { color: HEX.line, width: 0.75 }, shadow: shadow() });
  s.addImage({ path: img(name), x: xx, y: yy, w: ww, h: hh, altText: alt });
}
// A row of chevrons, right to left.
function chevrons(s, steps, y, h, o = {}) {
  const n = steps.length, gap = 0.06, cw = (W - 2 * M - gap * (n - 1)) / n;
  steps.forEach((t, i) => {
    const x = W - M - (i + 1) * cw - i * gap, on = o.focus === undefined || o.focus === i;
    s.addShape(i === 0 ? pres.shapes.PENTAGON : pres.shapes.CHEVRON, { x, y, w: cw, h, flipH: true, fill: { color: on ? (o.tones ? HEX[o.tones[i]] : HEX.navy) : HEX.line }, line: { color: HEX.white, width: 0 } });
    text(s, t, { x: x + 0.25, y, w: cw - 0.5, h, fontSize: o.fs || 14, bold: true, color: on ? HEX.white : HEX.muted, align: 'center', valign: 'middle' });
  });
}
// A table with the first column on the right: rows are given right to left.
function table(s, head, rows, x, y, w, colW, o = {}) {
  const hd = head.map(t => ({ text: t, options: { bold: true, color: HEX.white, fill: { color: HEX.navy }, align: 'right', ...AR } }));
  const body = rows.map((r, ri) => r.map((t, ci) => ({ text: t, options: { color: HEX.ink, bold: ci === 0 && o.boldFirst, fill: { color: ri % 2 ? HEX.page : HEX.white }, align: 'right', ...AR } })));
  const rev = a => a.slice().reverse();
  s.addTable([rev(hd), ...body.map(rev)], { x, y, w, colW: rev(colW), fontSize: o.fs || 13, margin: [0.05, 0.1, 0.05, 0.1],
    border: { type: 'solid', color: HEX.line, pt: 0.75 }, valign: 'middle', rowH: o.rowH });
}
// A numbered "so what" box.
function takeaway(s, t, y = 6.0) {
  s.addShape(pres.shapes.RECTANGLE, { x: M, y, w: W - 2 * M, h: 0.62, fill: { color: TINT.gold }, line: { color: HEX.gold, width: 0.75 } });
  text(s, [{ text: 'الخلاصة: ', options: { bold: true, color: HEX.orange } }, { text: t }], { x: M + 0.2, y, w: W - 2 * M - 0.4, h: 0.62, fontSize: 15, valign: 'middle' });
}

// ====================== 1. Cover ======================
{
  const s = newSlide('غلاف', 'الافتتاح');
  s.addImage({ path: img('logo-disc.png'), x: W - M - 2.4, y: 1.95, w: 2.4, h: 2.4, altText: 'شعار الديوان الوطني للحماية المدنية' });
  text(s, 'مشروع التخرج', { x: M, y: 0.9, w: W - 2 * M, h: 0.45, fontSize: 16, bold: true, color: HEX.gold });
  s.addText('منظومة ذكية للتبليغ والمشاركة المجتمعية والمؤسساتية في مجال السلامة والوقاية وإدارة الأخطار', { placeholder: 'title', ...AR });
  s.addText('من التبليغ إلى أخذ القرار', { placeholder: 'body', ...AR });
  text(s, 'إعداد: [اسم الطالب]   ·   إشراف: [اسم المشرف]', { x: M, y: 5.35, w: W - 2 * M, h: 0.4, fontSize: 16, color: HEX.white });
  text(s, '[الجامعة · الكلية · البرنامج]   ·   السنة الجامعية 2025-2026', { x: M, y: 5.8, w: W - 2 * M, h: 0.4, fontSize: 14, color: HEX.pale });
  text(s, 'حالة تطبيقية: الديوان الوطني للحماية المدنية، الجمهورية التونسية', { x: M, y: 6.25, w: W - 2 * M, h: 0.4, fontSize: 14, color: HEX.pale });
  notes(s, 'السيد الرئيس، أعضاء اللجنة الموقرة، أتشرف بعرض مشروع تخرجي: منظومة ذكية تربط المواطن والمؤسسة وقاعات العمليات وأصحاب القرار في سلسلة واحدة، من لحظة التبليغ إلى لحظة القرار. (الحقول بين معقفين تُملأ قبل العرض.)');
}

// ====================== 2. Executive summary ======================
{
  const s = content(0, 'الخلاصة التنفيذية: منصة سيادية واحدة تختصر المسار من البلاغ إلى القرار، مبنية ومقيسة لا مقترحة فقط');
  const cols = [
    ['الوضع', 'navy', '143.308 تدخلا في سنة واحدة، تصل عبر قنوات متفرقة (الهاتف، اللاسلكي، الحضور) وتُسجَّل يدويا، دون صورة موحّدة للقرار.'],
    ['الإشكالية', 'red', 'كيف نحوّل البلاغ المتفرق إلى قرار سريع وموثّق ومحمي، مع إشراك المواطن والمؤسسة، وفي احترام السيادة على المعطيات؟'],
    ['الحل', 'green', 'منظومة من خمسة مكونات: تطبيق المواطن، تطبيق الأعوان، بوابة المؤسسات، لوحة القيادة، وطبقة ذكاء اصطناعي محلية.'],
    ['النتيجة', 'purple', '288 من 292 متطلبا منجزة؛ البلاغ يظهر في 0,45 ثانية؛ تحصين الخادم من 57 إلى 82؛ نموذج جاهز للتجربة الميدانية.'],
  ];
  const cw = (W - 2 * M - 3 * 0.2) / 4;
  cols.forEach(([h, tone, body], i) => {
    const x = W - M - (i + 1) * cw - i * 0.2;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w: cw, h: 0.55, fill: { color: HEX[tone] }, line: { color: HEX[tone], width: 0 } });
    text(s, `${i + 1}. ${h}`, { x: x + 0.15, y: 1.95, w: cw - 0.3, h: 0.55, fontSize: 17, bold: true, color: HEX.white, valign: 'middle' });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.5, w: cw, h: 3.3, fill: { color: TINT[tone] }, line: { color: TINT[tone], width: 0 } });
    text(s, body, { x: x + 0.18, y: 2.68, w: cw - 0.36, h: 3.0, fontSize: 16 });
  });
  takeaway(s, 'المشروع يقدّم منظومة تعمل ومقيسة، وما بقي قرار مؤسساتي: التزكية، والحسابات الرسمية، وولاية التجربة.');
  s.addText('المصدر: الملف الوصفي للمشروع V33؛ أرشيف SNACR لسنة 2022؛ تقرير التحصين (2026-10-31)', { placeholder: 'source', ...AR });
  notes(s, 'لو بقيت دقيقة واحدة فهذه هي: الوضع الحالي، السؤال الذي يجيب عنه البحث، الحل المبني، والنتائج المقيسة. كل ما يلي تفصيل لهذه الأعمدة الأربعة.');
}

// ====================== 3. Agenda ======================
{
  const s = content(0, 'خطة العرض: خمسة أقسام تتبع منطق البحث من السؤال إلى الإجابة المقيسة');
  SECTIONS.forEach((t, i) => {
    const y = 1.95 + i * 0.86;
    s.addShape(pres.shapes.OVAL, { x: W - M - 0.62, y, w: 0.62, h: 0.62, fill: { color: i ? HEX.white : HEX.navy }, line: { color: HEX.navy, width: 1.5 } });
    text(s, `${i + 1}`, { x: W - M - 0.62, y, w: 0.62, h: 0.62, fontSize: 18, bold: true, color: i ? HEX.navy : HEX.white, align: 'center', valign: 'middle' });
    text(s, t, { x: W - M - 6.0, y, w: 5.2, h: 0.62, fontSize: 20, bold: true, valign: 'middle' });
    text(s, ['لماذا هذه المنظومة، وما السؤال المطروح', 'المرجعيات والمنهج والمعطيات', 'المكونات والمسار والذكاء الاصطناعي والأمن', 'ما قيس، وما يقابل كل هدف', 'حدود العمل، الطريق إلى الإنتاج، والإسهام'][i],
      { x: M, y, w: W - 2 * M - 6.2, h: 0.62, fontSize: 15, color: HEX.muted, valign: 'middle' });
  });
  notes(s, 'العرض في خمسة أقسام، ويظهر في أعلى كل شريحة أين نحن من هذه الخطة.');
}

// ====================== Section 1 ======================
notes(divider(0, 'لماذا هذه المنظومة، وما السؤال الذي يجيب عنه البحث'), 'نبدأ بالسياق: حجم العمل اليوم، وما ينقصه.');

{
  const s = content(0, 'الحجم كبير والانتشار وطني: أكثر من 143 ألف تدخل في سنة واحدة على 24 ولاية و279 معتمدية',
    'المصدر: أرشيف تدخلات الديوان (SNACR) لسنة 2022، معطيات حقيقية؛ المرجع الإداري للمعهد الوطني للإحصاء');
  stat(s, W - M - 3.9, 1.95, 3.9, 1.75, '143.308', 'تدخلا مسجّلا في 2022 (حقيقي)', 'navy', { fs: 36 });
  stat(s, W - M - 7.95, 1.95, 3.9, 1.75, '24 / 279', 'ولاية / معتمدية يغطيها المرجع الإداري', 'teal', { fs: 36 });
  stat(s, M, 1.95, 3.9, 1.75, '497 ألفا', 'تدخل مقدَّر تقريبا للسنوات 2023 إلى 2025 [SIM] على توزيعات 2022', 'orange', { fs: 36 });
  bullets(s, ['كل تدخل يمر بالقاعة الجهوية ثم الفريق الميداني، وأحيانا القائد واللجنة',
    'الأرشيف يُدخل لاحقا دون موقع دقيق ولا زمن وصول، فلا يقيس الأداء',
    '11,6 % من أسماء المعتمديات في أرشيف 2022 لا تطابق المرجع الإداري كما هي'], M, 4.0, W - 2 * M, 1.8, 17);
  sim(s, M, 3.78);
  takeaway(s, 'الحجم يبرر منظومة رقمية؛ وجودة الأرشيف تبرر توحيد المرجع قبل أي تحليل.');
  notes(s, 'هذه أرقام حقيقية من أرشيف الديوان لسنة 2022. السنوات الثلاث التالية مولّدة على توزيعاتها في انتظار تسليم الملفات، وهي معلَّمة [SIM].');
}
{
  const s = content(0, 'المسار الحالي يتعطل في أربع نقاط، كلها تؤخر القرار أو تفقده الدليل',
    'المصدر: مقابلات وملاحظة سير العمل في القاعات؛ الملف الوصفي للمشروع، القسم 1');
  const pains = [['تشتت القنوات', 'الهاتف واللاسلكي والحضور: لا صورة ولا موقع دقيق ولا رقم تتبع للمبلّغ', 'sms', 'red'],
    ['تسجيل يدوي', 'إعادة كتابة البلاغ في القاعة، وإدخال الأرشيف لاحقا دون عنوان ولا وصف', 'fact_check', 'orange'],
    ['لا صورة مشتركة', 'لا خريطة واحدة بين القاعة والفريق والقائد واللجان', 'map', 'purple'],
    ['كارثة دون إطار', 'لا محاور ولا تقارير وضع موحدة ولا حوصلة نهائية مؤرشفة', 'thunderstorm', 'navy']];
  const cw = (W - 2 * M - 0.3) / 2;
  pains.forEach(([t, d, ic, tone], k) => {
    const col = k % 2, row = Math.floor(k / 2), x = W - M - cw - col * (cw + 0.3), y = 1.95 + row * 1.95;
    card(s, x, y, cw, 1.75);
    tile(s, x + cw - 1.0, y + 0.3, 0.75, tone, ic);
    text(s, t, { x: x + 0.25, y: y + 0.25, w: cw - 1.45, h: 0.45, fontSize: 19, bold: true });
    text(s, d, { x: x + 0.25, y: y + 0.75, w: cw - 1.45, h: 0.9, fontSize: 15, color: HEX.muted });
  });
  notes(s, 'أربع نقاط تعطل: القناة، التسجيل، الصورة المشتركة، وإدارة الكارثة. كل مكوّن من الحل يعالج واحدة منها على الأقل.');
}
{
  const s = content(0, 'إشكالية البحث: كيف ننتقل من بلاغ متفرق إلى قرار سريع وموثّق، دون التفريط في السيادة على المعطيات؟',
    'المصدر: إعداد الطالب');
  card(s, M, 1.95, W - 2 * M, 1.35, { fill: TINT.navy, line: TINT.navy, flat: true });
  text(s, 'السؤال الرئيسي', { x: M + 0.3, y: 2.05, w: W - 2 * M - 0.6, h: 0.4, fontSize: 14, bold: true, color: HEX.navy });
  text(s, 'إلى أي مدى يمكن لمنظومة رقمية موحّدة، مدعومة بذكاء اصطناعي محلي، أن تختصر زمن المسار من التبليغ إلى القرار وتحسّن جودته في الحماية المدنية التونسية؟',
    { x: M + 0.3, y: 2.45, w: W - 2 * M - 0.6, h: 0.8, fontSize: 18, bold: true });
  const qs = [['س1', 'كيف نستقبل البلاغ من المواطن والمؤسسة بموقعه ودليله، حتى دون إنترنت؟'],
    ['س2', 'كيف نوحّد عمل القاعة والفريق والقائد واللجان على صورة واحدة؟'],
    ['س3', 'كيف يساعد الذكاء الاصطناعي القرار دون أن يحلّ محلّ صاحبه؟'],
    ['س4', 'كيف نحمي المعطيات ونثبت ذلك بالقياس لا بالتصريح؟']];
  qs.forEach(([k, q], i) => {
    const y = 3.55 + i * 0.6;
    text(s, k, { x: W - M - 0.7, y, w: 0.7, h: 0.5, fontSize: 16, bold: true, color: HEX.gold, valign: 'middle' });
    text(s, q, { x: M, y, w: W - 2 * M - 0.85, h: 0.5, fontSize: 16, valign: 'middle' });
  });
  notes(s, 'السؤال الرئيسي يتفرع إلى أربعة أسئلة فرعية، ولكل منها جواب في القسم الثالث ودليل في القسم الرابع.');
}
{
  const s = content(0, 'هدف عام واحد وأربعة أهداف خاصة، كل منها قابل للقياس',
    'المصدر: الملف الوصفي V33، المتطلبات غير الوظيفية NFR-01 و NFR-05 و NFR-09 و NFR-10');
  card(s, M, 1.95, W - 2 * M, 0.95, { fill: HEX.deep, line: HEX.deep, flat: true });
  text(s, [{ text: 'الهدف العام: ', options: { bold: true, color: HEX.gold } }, { text: 'تصميم منظومة وطنية ذكية وتطويرها وتقييمها، تربط التبليغ بالقرار في سلسلة قيمة واحدة.', options: { color: HEX.white } }],
    { x: M + 0.3, y: 1.95, w: W - 2 * M - 0.6, h: 0.95, fontSize: 18, valign: 'middle' });
  table(s, ['الهدف الخاص', 'المؤشر', 'القيمة المستهدفة'], [
    ['ه1. تبليغ سريع وسهل للجميع', 'عدد اللمسات لإرسال SOS؛ النفاذ', '3 لمسات على الأكثر؛ WCAG 2.2 AA'],
    ['ه2. معالجة آنية في القاعة', 'زمن الظهور في اللوحة (p95)', 'أقل من 3 ثوان'],
    ['ه3. قرار مدعوم بالتحليل', 'مؤشرات الوصول في الأجل لكل معتمدية', 'مخطط تغطية تعتمده اللجنة'],
    ['ه4. أمن وسيادة مثبتان', 'مؤشر Lynis، المنافذ، TLS، الاستضافة', 'تحصين مقيس؛ معطيات داخل تونس'],
  ], M, 3.15, W - 2 * M, [4.0, 4.4, 3.733], { boldFirst: true, fs: 15, rowH: 0.55 });
  notes(s, 'صغت الأهداف بحيث يقابل كل منها مؤشر يمكن قياسه، وسنعود إلى هذا الجدول في قسم التقييم.');
}

// ====================== Section 2 ======================
notes(divider(1, 'المرجعيات التي يستند إليها التصميم، والمنهج، والمعطيات'), 'ننتقل إلى الإطار النظري والمنهجي.');

{
  const s = content(1, 'التصميم يستند إلى مرجعيات دولية ووطنية معترف بها، لا إلى اختيارات تقنية معزولة',
    'المصادر: UNDRR، إطار سنداي 2015-2030؛ W3C، WCAG 2.2 (2023)؛ OWASP ASVS؛ OMG، BPMN 2.0؛ القانون الأساسي 63 لسنة 2004');
  table(s, ['المرجع', 'ما يأخذه منه المشروع'], [
    ['إطار سنداي للحد من مخاطر الكوارث 2015-2030', 'فهم الخطر (تحليل SNACR)، تعزيز الحوكمة (اللجان)، الاستعداد للاستجابة'],
    ['النظام التونسي للحماية المدنية والتصرف في الكوارث', 'مستويات القرار: القاعة الجهوية، اللجنة الجهوية، اللجنة الوطنية'],
    ['القانون الأساسي 63 لسنة 2004 (حماية المعطيات الشخصية)', 'الموافقة، مدد الحفظ، التشفير، ترخيص الهيئة قبل الإطلاق'],
    ['WCAG 2.2 المستوى AA', 'النفاذ لذوي الهمم في التطبيق والبوابة واللوحة'],
    ['OWASP ASVS المستوى 2 و MASVS', 'متطلبات الأمن للخادم وتطبيق الهاتف'],
    ['BPMN 2.0', 'توصيف مسارات العمل بترميز قياسي قابل للتدقيق'],
  ], M, 1.95, W - 2 * M, [5.2, 6.933], { boldFirst: true, fs: 14, rowH: 0.6 });
  notes(s, 'كل اختيار في المنظومة مرتبط بمرجع: إطار سنداي على المستوى الاستراتيجي، والقانون التونسي على مستوى المعطيات، والمعايير التقنية على مستوى التنفيذ.');
}
{
  const s = content(1, 'الحلول القائمة تغطي حلقة واحدة من السلسلة؛ الفجوة في الربط بين الحلقات',
    'المصدر: مقارنة الطالب لفئات الحلول (تطبيقات الطوارئ، أنظمة الإرسال، منصات التبليغ التشاركي)');
  const head = ['الفئة', 'تبليغ المواطن', 'المؤسسة', 'القاعة والفريق', 'القرار واللجان', 'ذكاء محلي'];
  const rows = [['تطبيقات الطوارئ للمواطن', '●', '○', '○', '○', '○'], ['أنظمة الإرسال في القاعات (CAD)', '○', '○', '●', '◐', '○'],
    ['منصات التبليغ التشاركي', '●', '◐', '○', '○', '○'], ['منصات إدارة الكوارث', '○', '○', '◐', '●', '○'], ['ء-حماية', '●', '●', '●', '●', '●']];
  table(s, head, rows, M, 1.95, W - 2 * M, [3.6, 1.7, 1.7, 1.7, 1.7, 1.733], { boldFirst: true, fs: 15, rowH: 0.62 });
  text(s, '●  تغطية كاملة     ◐  جزئية     ○  غائبة', { x: M, y: 5.8, w: W - 2 * M, h: 0.35, fontSize: 12, color: HEX.muted });
  notes(s, 'لم أقارن منتجات بعينها بل فئات الحلول. كل فئة قوية في حلقة واحدة، والقيمة المضافة للمشروع هي الربط بين الحلقات الخمس في منظومة واحدة.');
}
{
  const s = content(1, 'المنهج: بحث علمي بالتصميم (Design Science)، في 55 مرحلة قصيرة كل منها مراجعة ثم تصميم ثم تطوير ثم قياس',
    'المراجع المنهجية: Hevner وآخرون (2004)؛ Peffers وآخرون (2007)، منهجية DSRM');
  chevrons(s, ['تحديد المشكلة', 'تحديد الأهداف', 'التصميم والتطوير', 'العرض', 'التقييم', 'النشر والتواصل'], 2.0, 0.85, { fs: 14, tones: ['navy', 'navy', 'teal', 'teal', 'green', 'purple'] });
  const cw = (W - 2 * M - 0.4) / 3;
  [['دورة قصيرة', 'كل مرحلة: مراجعة من صاحب المشروع، تصميم مكتوب، تطوير، قياس، تقرير مرحلة', 'schedule', 'navy'],
    ['تحقق مستمر', 'نحو 2000 اختبار آلي و26 فحصا في التكامل المستمر لكل تعديل', 'verified', 'green'],
    ['أثر موثّق', 'تقرير لكل مرحلة، وسجل للإصدارات والقرارات والمؤجَّل', 'policy', 'purple']].forEach(([t, d, ic, tone], i) => {
    const x = W - M - (i + 1) * cw - i * 0.2;
    card(s, x, 3.2, cw, 2.55);
    tile(s, x + cw - 0.95, 3.45, 0.7, tone, ic);
    text(s, t, { x: x + 0.25, y: 3.5, w: cw - 1.35, h: 0.5, fontSize: 18, bold: true });
    text(s, d, { x: x + 0.25, y: 4.3, w: cw - 0.5, h: 1.3, fontSize: 15, color: HEX.muted });
  });
  notes(s, 'اعتمدت منهج البحث بالتصميم: المنتج نفسه هو موضوع البحث، ويُقيَّم بالقياس. طبقت الدورة على 55 مرحلة قصيرة.');
}
{
  const s = content(1, 'المعطيات: أرشيف حقيقي نُظّف ووُحّد مع المرجع الإداري، وما ينقص مولَّد ومعلَّم بوضوح',
    'المصدر: أرشيف SNACR 2022؛ المرجع الإداري (المعهد الوطني للإحصاء)؛ تقرير المرحلة S');
  chevrons(s, ['أرشيف 2022 الخام', 'التنظيف', 'الربط بالمعتمديات', 'التوليد [SIM] 2023-2025', 'المؤشرات'], 2.0, 0.8, { fs: 14, tones: ['slate', 'navy', 'navy', 'orange', 'green'].map(t => t === 'slate' ? 'muted' : t) });
  stat(s, W - M - 3.9, 3.15, 3.9, 1.65, '88,4 %', 'من أسماء 2022 تُعرف كما هي؛ الباقي بقاموس مرادفات', 'purple', { fs: 34 });
  stat(s, W - M - 7.95, 3.15, 3.9, 1.65, '279', 'معتمدية مرجعية بحدودها وعدد سكانها', 'teal', { fs: 34 });
  stat(s, M, 3.15, 3.9, 1.65, '3 سنوات', '2023 إلى 2025 مولّدة حتى يسلّم الديوان ملفاتها', 'orange', { fs: 34 });
  sim(s, M, 4.95);
  takeaway(s, 'كل رقم مولَّد يحمل شارة [SIM] في الواجهات والوثائق، ويُستبدل آليا عند تسليم الملفات الحقيقية.', 5.45);
  notes(s, 'الأمانة العلمية: الحقيقي حقيقي والمولَّد معلَّم. نسبة التعرّف 88,4 بالمئة قيست على أرشيف 2022.');
}

// ====================== Section 3 ======================
notes(divider(2, 'خمسة مكونات على سلسلة قيمة واحدة، من التبليغ إلى القرار'), 'القسم الثالث: الحل المقترح.');

{
  const s = content(2, 'سلسلة قيمة واحدة من ست حلقات: كل وظيفة في المنظومة تخدم حلقة منها',
    'المصدر: الملف الوصفي V33، القسم 1.1');
  chevrons(s, ['التبليغ', 'المعالجة', 'التحليل', 'مؤشرات الأداء', 'التنبؤ بالذكاء الاصطناعي', 'اتخاذ القرار'], 1.95, 0.95, { fs: 15, tones: ['red', 'orange', 'navy', 'teal', 'purple', 'green'] });
  const items = [['المواطن والمؤسسة', 'SOS، صورة، موقع، إنذار الكاميرا'], ['القاعة', 'تصنيف، أولوية، تجميع، استنفار'], ['التحليل', 'SNACR، المعتمديات ذات الأولوية'],
    ['المؤشرات', 'زمن الوصول، الأجل المستهدف'], ['الذكاء الاصطناعي', 'توصية بأسبابها، في الظل أولا'], ['القائد واللجان', 'قرار موقّع، كارثة بحوصلة']];
  const n = items.length, gap = 0.06, cw = (W - 2 * M - gap * (n - 1)) / n;
  items.forEach(([t, d], i) => {
    const x = W - M - (i + 1) * cw - i * gap;
    text(s, t, { x: x + 0.1, y: 3.1, w: cw - 0.2, h: 0.45, fontSize: 15, bold: true, align: 'center' });
    text(s, d, { x: x + 0.1, y: 3.55, w: cw - 0.2, h: 1.2, fontSize: 13, color: HEX.muted, align: 'center' });
  });
  takeaway(s, 'الجديد ليس في كل حلقة وحدها، بل في أن المعلومة تمر بالحلقات الست دون إعادة كتابة ودون أن تفقد دليلها.', 5.3);
  notes(s, 'هذه هي الفكرة المركزية للمشروع: سلسلة واحدة. ما يدخل في التبليغ يصل إلى القرار بموقعه ودليله وتوقيته.');
}
{
  const s = content(2, 'معمارية من أربع طبقات، كل مكوّن فيها مفتوح المصدر ويعمل على خوادم محلية',
    'المصدر: الملف الوصفي V33، القسم 7؛ قاموس البيانات 2.0؛ OpenAPI 1.10.0');
  const layers = [['الواجهات', 'تطبيق المواطن · تطبيق الأعوان · بوابة المؤسسات · لوحة القيادة (عربية، فرنسية، إنجليزية)', 'navy'],
    ['الخدمات', 'واجهة برمجية بـ 745 عملية · عمّال المهام · Keycloak للهوية · البث (MediaMTX) · الهاتف (Asterisk)', 'teal'],
    ['الذكاء الاصطناعي', 'تفريغ الصوت (Whisper) · فهم النص (Qwen) · كشف الحريق والدخان (YOLOX) · محليا دون إنترنت', 'purple'],
    ['المعطيات', 'PostgreSQL مع PostGIS و pgvector · 35 مخططا و219 جدولا · 44 حقلا مشفّرا · نسخ احتياطي مشفّر', 'green']];
  layers.forEach(([t, d, tone], i) => {
    const y = 1.95 + i * 1.0;
    s.addShape(pres.shapes.RECTANGLE, { x: W - M - 2.6, y, w: 2.6, h: 0.85, fill: { color: HEX[tone] }, line: { color: HEX[tone], width: 0 } });
    text(s, t, { x: W - M - 2.5, y, w: 2.4, h: 0.85, fontSize: 17, bold: true, color: HEX.white, valign: 'middle' });
    s.addShape(pres.shapes.RECTANGLE, { x: M, y, w: W - 2 * M - 2.65, h: 0.85, fill: { color: TINT[tone] }, line: { color: TINT[tone], width: 0 } });
    text(s, d, { x: M + 0.2, y, w: W - 2 * M - 3.05, h: 0.85, fontSize: 15, valign: 'middle' });
  });
  takeaway(s, 'لا خدمة أجنبية في مسار المعطيات الشخصية: كل النماذج برخص Apache-2.0 أو MIT وتعمل على خوادم الديوان.', 6.0);
  notes(s, 'أربع طبقات. النقطة الأهم للجنة: لا شيء من المعطيات الشخصية يخرج إلى خدمة أجنبية، والنماذج كلها برخص مفتوحة.');
}
{
  const s = content(2, 'المواطن يبلّغ في ثلاث لمسات على الأكثر، بموقعه ودليله، حتى دون إنترنت',
    'المصدر: الملف الوصفي V33، NFR-04 و NFR-09 و NFR-10؛ لقطة من التطبيق [SIM]');
  shot(s, 'shot-phone.png', M + 0.2, 1.9, 2.7, 4.75, 'الشاشة الرئيسية لتطبيق المواطن');
  bullets(s, ['زر النجدة في ثلاث لمسات، وشريط 198 في كل شاشة', 'بلاغ بصورة وفيديو وموقع، ورقم تتبع فوري وبصمة SHA-256 للدليل',
    'دون اتصال: البلاغ محفوظ مشفّرا، ورسالة قصيرة جاهزة إلى 198', 'ثلاث لغات، وقارئ الشاشة وتكبير الخط 200% واهتزاز وومض للصم',
    'ملف طبي مشفّر على الهاتف لا يفتحه الخادم'], 3.6, 2.0, W - M - 3.6, 3.6, 17);
  sim(s, M + 0.2, 6.6 - 0.3);
  notes(s, 'التطبيق صُمّم للحظة الضغط: ثلاث لمسات، ويعمل دون إنترنت، ويحفظ الدليل ببصمته من لحظة الاستلام.');
}
{
  const s = content(2, 'المؤسسة شريك في الوقاية: كاميرتها تنبّه صاحبها أولا، وغياب ردّه خلال 90 ثانية يرفع البلاغ آليا',
    'المصدر: مخطط BPMN «الإنذار الأولي لصاحب المؤسسة»؛ الإعداد orgs.prealert_seconds');
  chevrons(s, ['كاميرا أو حساس يرصد حدثا', 'إنذار أولي موقّع لصاحب المؤسسة', 'نفي: يُغلق دون إزعاج القاعة', 'تأكيد أو لا رد خلال 90 ث: بلاغ آلي للقاعة'], 2.0, 1.0, { fs: 14, tones: ['muted', 'orange', 'green', 'red'] });
  const cw = (W - 2 * M - 0.4) / 3;
  [['ملف السلامة', 'الوثائق، فريق السلامة، المواد الخطرة، المعدات وصيانتها', 'apartment', 'teal'],
    ['زيارة الوقاية', 'على هاتف المفقّد بالصور والتوقيع، حتى دون اتصال', 'fact_check', 'navy'],
    ['الشهادة', 'موقّعة رقميا مع رمز QR يتحقق منه أي شخص', 'verified', 'green']].forEach(([t, d, ic, tone], i) => {
    const x = W - M - (i + 1) * cw - i * 0.2;
    card(s, x, 3.35, cw, 2.2);
    tile(s, x + cw - 0.95, 3.6, 0.7, tone, ic);
    text(s, t, { x: x + 0.25, y: 3.65, w: cw - 1.35, h: 0.5, fontSize: 18, bold: true });
    text(s, d, { x: x + 0.25, y: 4.45, w: cw - 0.5, h: 1.0, fontSize: 15, color: HEX.muted });
  });
  takeaway(s, 'الإنذار الكاذب لا يصل القاعة، والحقيقي لا ينتظر: التوازن بين الإزعاج والسرعة إعداد قابل للتغيير.', 5.8);
  notes(s, 'الكاميرا ترصد الحريق إذا تكرر في 3 من 5 إطارات، ثم تنبّه صاحب المؤسسة. إن نفى يغلق، وإن أكد أو لم يرد خلال 90 ثانية يصل البلاغ للقاعة.');
}
{
  const s = content(2, 'الذكاء الاصطناعي يوصي ويعلّل، والقائد وحده يقرر: كل نموذج يعمل في الظل قبل أن يُعتمد',
    'المصدر: بطاقات النماذج (المرحلة L5)؛ مساعد القائد (المرحلة AI5)');
  const steps = [['يستمع ويقرأ', 'تفريغ الصوت وفهم النص محليا', 'mic', 'navy'], ['يرى', 'كشف الحريق والدخان في الصور والبث', 'videocam', 'red'],
    ['يوصي', 'اقتراح مرقّم بأسبابه وبما فعله القادة قبل', 'psychology', 'purple'], ['يتعلم في الظل', 'يُقارن بقرارات حقيقية لم يُدرَّب عليها قبل اعتماده', 'trending_up', 'green']];
  const cw = (W - 2 * M - 0.6) / 4;
  steps.forEach(([t, d, ic, tone], i) => {
    const x = W - M - (i + 1) * cw - i * 0.2;
    card(s, x, 1.95, cw, 2.6);
    tile(s, x + (cw - 0.8) / 2, 2.2, 0.8, tone, ic);
    text(s, t, { x: x + 0.15, y: 3.15, w: cw - 0.3, h: 0.45, fontSize: 18, bold: true, align: 'center' });
    text(s, d, { x: x + 0.15, y: 3.6, w: cw - 0.3, h: 0.85, fontSize: 14, color: HEX.muted, align: 'center' });
  });
  card(s, M, 4.8, W - 2 * M, 1.0, { fill: TINT.purple, line: TINT.purple, flat: true });
  text(s, 'ضمانات: لا قرار آلي؛ كل اقتراح يُقبل أو يُعدَّل أو يُرفض بسبب ويُسجَّل؛ عتبات كل نموذج تعتمدها لجنة فنية؛ لكل نموذج بطاقة برخصته وحدوده.',
    { x: M + 0.25, y: 4.8, w: W - 2 * M - 0.5, h: 1.0, fontSize: 16, valign: 'middle' });
  notes(s, 'موقفي من الذكاء الاصطناعي: مساعد لا بديل. يعمل في الظل ويُقارن بقرارات حقيقية، ولا يخرج من الظل إلا بقرار لجنة.');
}
{
  const s = content(2, 'القرار والكارثة: توصية بأسبابها، قرار موقّع، ولكل كارثة محاور وتقارير وضع وحوصلة نهائية',
    'المصدر: المرحلة N (عمل القاعات واللجان)؛ لقطة من حوصلة الكوارث [SIM]');
  shot(s, 'shot-disasters.png', M, 1.9, W - 2 * M, 2.45, 'حوصلة الكوارث');
  bullets(s, ['القرار موقّع إلكترونيا بخوارزمية Ed25519، مع أجل ومتابعة للتنفيذ',
    'اللجنة الجهوية برئاسة السيد الوالي، واللجنة الوطنية برئاسة السيد وزير الداخلية؛ قرار الوطنية يتقدم عند التعارض',
    'الكارثة: محاور ومطالب وإجلاء وإيواء وتقارير وضع دورية، ثم حوصلة وأرشفة في الذاكرة الوطنية'], M, 4.55, W - 2 * M, 1.7, 17);
  sim(s, M, 6.3);
  notes(s, 'الحادث الكبير يُرقّى إلى كارثة لها إطار كامل، وتراها اللجنتان على خريطة متعددة الولايات.');
}
{
  const s = content(2, 'تحليل المخاطر SNACR يحوّل أرشيف التدخلات إلى مخطط تغطية تعتمده اللجنة',
    'المصدر: المرحلة S (الاستراتيجيات و SNACR)؛ الأهداف إعدادات قابلة للتغيير؛ لقطة [SIM]');
  shot(s, 'shot-snacr.png', M, 1.9, 7.9, 4.75, 'مصفوفة المخاطر SNACR');
  stat(s, W - M - 3.9, 1.95, 3.9, 1.45, '90 %', 'هدف الوصول في الأجل (إعداد)', 'green');
  stat(s, W - M - 3.9, 3.55, 3.9, 1.45, '10 / 15 / 25 د', 'أجل الحريق: حضري / شبه حضري / ريفي', 'red', { fs: 26 });
  stat(s, W - M - 3.9, 5.15, 3.9, 1.45, 'p50 و p90', 'زمن الوصول لكل معتمدية', 'purple', { fs: 26 });
  notes(s, 'المصفوفة تحدد المعتمديات ذات الأولوية حسب الخطر والأداء، واللجنة تعتمد المخطط. الأهداف إعدادات يغيّرها الديوان.');
}
{
  const s = content(2, 'الأمن مثبت بالقياس: تحصين الخادم رفع مؤشر Lynis من 57 إلى 82 وأبقى منفذين فقط',
    'المصدر: تقرير التحصين، 2026-10-31 (Lynis 3.0.9، nmap، testssl.sh 3.2)؛ قياس في حاوية، حدّ أدنى');
  s.addChart(pres.charts.BAR, [{ name: 'مؤشر Lynis', labels: ['قبل التحصين', 'بعد التحصين'], values: [57, 82] }], {
    x: M, y: 1.95, w: 5.6, h: 3.9, barDir: 'col', chartColors: [HEX.muted, HEX.green], valAxisMinVal: 0, valAxisMaxVal: 100,
    showValue: true, dataLabelFontSize: 16, dataLabelFontBold: true, catAxisLabelFontSize: 14, valAxisLabelFontSize: 11,
    valGridLine: { color: HEX.line, size: 0.5 }, catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt', dataLabelFontFace: '+mn-lt',
    showLegend: false, showTitle: true, title: 'مؤشر التحصين (من 100)', titleFontSize: 14, titleFontFace: '+mn-lt', titleColor: HEX.ink,
  });
  bullets(s, ['منفذان فقط مفتوحان: 80 و443، حسب فحص nmap', 'بروتوكولا TLS 1.2 و1.3 فقط، ولا ثغرة معروفة حسب testssl.sh',
    'تشفير الحقول الحساسة AES-256، وعزل كل ولاية على 133 جدولا', 'تحقق بخطوتين لكل عون، وسجل تدقيق غير قابل للتعديل',
    'الإنتاج يرفض الإقلاع بأي سرّ ضعيف'], 6.5, 2.0, W - M - 6.5, 3.8, 16);
  notes(s, 'لم أكتف بالتصريح بالأمن: قسته قبل سكريبت التحصين وبعده. القياس في حاوية، فهو حدّ أدنى، ويُعاد على خادم حقيقي قبل الإطلاق.');
}

// ====================== Section 4 ======================
notes(divider(3, 'ما قيس فعلا، وما يقابل كل هدف'), 'القسم الرابع: النتائج والتقييم.');

{
  const s = content(3, 'الأداء المقيس أفضل بكثير من الحد المطلوب: الظهور في 0,45 ث مقابل 3 ث مطلوبة',
    'المصدر: الملف الوصفي V33، NFR-01 و NFR-13 (اختبار الحمل k6 وتمرين الاستعادة)');
  s.addChart(pres.charts.BAR, [
    { name: 'المطلوب', labels: ['الظهور في اللوحة', 'استلام البلاغ'], values: [3, 2] },
    { name: 'المقيس', labels: ['الظهور في اللوحة', 'استلام البلاغ'], values: [0.45, 0.328] },
  ], { x: M, y: 1.95, w: 6.6, h: 4.0, barDir: 'bar', barGrouping: 'clustered', chartColors: [HEX.line, HEX.navy], showValue: true, dataLabelFormatCode: '0.0##',
    showTitle: true, title: 'بالثواني، المئين 95', titleFontSize: 13, titleFontFace: '+mn-lt', titleColor: HEX.ink,
    dataLabelFontSize: 13, dataLabelFontBold: true, catAxisLabelFontSize: 13, valAxisLabelFontSize: 11, showLegend: true, legendPos: 'b', legendFontSize: 12,
    valGridLine: { color: HEX.line, size: 0.5 }, catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt', dataLabelFontFace: '+mn-lt', legendFontFace: '+mn-lt' });
  stat(s, W - M - 5.6, 1.95, 5.6, 1.25, '16 بلاغ / ث', 'حمل SOS مستمر دون خطأ', 'green', { fs: 28 });
  stat(s, W - M - 5.6, 3.35, 5.6, 1.25, '2 ث و1 ث', 'زمن الاستعادة وفقدان المعطيات في تمرين الاستعادة، والمطلوب ساعة و5 دقائق', 'teal', { fs: 28 });
  stat(s, W - M - 5.6, 4.75, 5.6, 1.25, '10 قواعد', 'تنبيه تشغيلي في المراقبة (Prometheus)', 'purple', { fs: 28 });
  notes(s, 'القياس على بيئة الاختبار. الهدف الوطني (مليون مستخدم، 5000 بلاغ في الساعة) يُقاس في التجربة الميدانية.');
}
{
  const s = content(3, 'التغطية الوظيفية شبه كاملة: 288 من 292 متطلبا منجزة، والأربعة الباقية جزئية بانتظار قرار خارجي',
    'المصدر: الملف الوصفي V33 (جدول التتبع)؛ التكامل المستمر على GitHub');
  s.addChart(pres.charts.DOUGHNUT, [{ name: 'المتطلبات', labels: ['منجز', 'منجز جزئيا'], values: [288, 4] }], {
    x: M, y: 1.9, w: 4.6, h: 4.1, holeSize: 62, chartColors: [HEX.green, HEX.amber], showPercent: false, showValue: true, dataLabelFontSize: 13,
    dataLabelColor: HEX.white, showLegend: true, legendPos: 'b', legendFontSize: 12, legendFontFace: '+mn-lt', dataLabelFontFace: '+mn-lt' });
  const kpis = [['292', 'متطلبا وظيفيا بمعرّف وأولوية وحالة'], ['≈ 2000', 'اختبار آلي'], ['26', 'فحصا في كل طلب دمج (كلها ناجحة)'], ['745', 'عملية في الواجهة البرمجية الموثّقة (OpenAPI)'], ['219', 'جدولا في قاموس البيانات المستخرج آليا']];
  kpis.forEach(([n, l], i) => {
    const y = 1.95 + i * 0.82;
    text(s, n, { x: W - M - 1.9, y, w: 1.9, h: 0.7, fontSize: 28, bold: true, color: HEX.navy, valign: 'middle' });
    text(s, l, { x: 5.5, y, w: W - M - 1.9 - 5.6, h: 0.7, fontSize: 16, valign: 'middle' });
    if (i < kpis.length - 1) s.addShape(pres.shapes.LINE, { x: 5.5, y: y + 0.76, w: W - M - 5.5, h: 0, line: { color: HEX.line, width: 0.75 } });
  });
  notes(s, 'كل متطلب له معرّف ثابت حتى يُنقل كما هو إلى كراس الشروط. الأربعة الجزئية تنتظر قرارات من جهات خارجية.');
}
{
  const s = content(3, 'كل هدف خاص تحقق بدليل مقيس، والقياس الوطني الكامل يبقى رهين التجربة الميدانية',
    'المصدر: إعداد الطالب، بالاستناد إلى الملف الوصفي V33 وتقارير المراحل');
  table(s, ['الهدف', 'الدليل', 'الحكم'], [
    ['ه1. تبليغ سريع وسهل', 'SOS في 3 لمسات؛ النفاذ WCAG 2.2 AA؛ عمل دون اتصال', '✔ متحقق'],
    ['ه2. معالجة آنية', 'ظهور في 0,45 ث؛ 16 بلاغ/ث بـ p95 = 328 ms', '✔ متحقق'],
    ['ه3. قرار مدعوم بالتحليل', 'مصفوفة SNACR ومخطط تغطية؛ معطيات 2023-2025 [SIM]', '◐ متحقق تقنيا، ينتظر المعطيات'],
    ['ه4. أمن وسيادة', 'Lynis 57 ← 82؛ منفذان؛ TLS دون ثغرة؛ نماذج محلية', '◐ متحقق، ينتظر مركز البيانات وZAP'],
  ], M, 1.95, W - 2 * M, [3.4, 6.0, 2.733], { boldFirst: true, fs: 15, rowH: 0.75 });
  takeaway(s, 'الإجابة عن السؤال الرئيسي: نعم، في حدود بيئة الاختبار؛ والتجربة الميدانية هي التي تقيس الأثر الفعلي على زمن الوصول.', 5.85);
  notes(s, 'أكون دقيقا: هدفان متحققان بالكامل، واثنان متحققان تقنيا وينتظران معطيات أو قرارات خارجية.');
}
{
  const s = content(3, 'حدود العمل معروفة ومدرجة في خطة واضحة، ولا تمس صحة النتائج المقيسة',
    'المصدر: قائمة المؤجَّل (docs/backlog.md)؛ تقرير المرحلة T');
  table(s, ['الحد', 'أثره', 'المعالجة المقترحة'], [
    ['معطيات 2023-2025 مولّدة [SIM]', 'مؤشرات SNACR تقريبية', 'تسليم الديوان للملفات الحقيقية'],
    ['القياس في بيئة اختبار وحاوية', 'الأداء والتحصين حدّ أدنى', 'إعادة القياس على خادم حقيقي ومن الشبكة'],
    ['فحص ZAP واختبار الاختراق لم يُجريا', 'تقييم الأمن غير مكتمل', 'فحص ZAP ثم تدقيق الوكالة الوطنية للأمن السيبراني'],
    ['لا ربط مباشر بمركز 198 ولا حساسات حقيقية', 'جزء من الاستقبال يدوي', 'اتفاقية رسمية؛ التجربة الميدانية'],
  ], M, 1.95, W - 2 * M, [4.4, 3.6, 4.133], { boldFirst: true, fs: 15, rowH: 0.75 });
  notes(s, 'أفضّل أن أعرض الحدود بنفسي: كلها معروفة، ولكل منها معالجة مقترحة، ولا تمس ما قيس فعلا.');
}

// ====================== Section 5 ======================
{
  const s = content(4, 'الطريق إلى الإنتاج في ثلاث خطوات، تبدأ بقرار التزكية',
    'المصدر: كراس الشروط (2026)؛ المدد التقديرية [SIM]');
  const steps = [['منجز', 'النموذج التجريبي', 'كامل، يُعرض دون إنترنت', 'green'], ['الخطوة 1', 'التزكية', 'قرار الديوان وتحديد ولاية التجربة', 'navy'],
    ['الخطوة 2', 'الإنتاج', '8 خوادم بالمناطق، ربط Oracle، الحسابات الرسمية', 'orange'], ['الخطوة 3', 'التجربة', '3 أشهر في ولاية واحدة [SIM]', 'purple'], ['بعدها', 'التعميم', '24 ولاية', 'teal']];
  const n = steps.length, cw = (W - 2 * M - 0.2 * (n - 1)) / n;
  s.addShape(pres.shapes.LINE, { x: M + cw / 2, y: 2.4, w: W - 2 * M - cw, h: 0, line: { color: HEX.line, width: 2 } });
  steps.forEach(([w, t, d, tone], i) => {
    const x = W - M - (i + 1) * cw - i * 0.2;
    s.addShape(pres.shapes.OVAL, { x: x + cw / 2 - 0.25, y: 2.15, w: 0.5, h: 0.5, fill: { color: HEX[tone] }, line: { color: HEX.white, width: 2 } });
    text(s, w, { x, y: 2.8, w: cw, h: 0.4, fontSize: 14, bold: true, color: HEX[tone], align: 'center' });
    text(s, t, { x, y: 3.2, w: cw, h: 0.8, fontSize: 18, bold: true, align: 'center', valign: 'middle' });
    text(s, d, { x: x + 0.1, y: 4.05, w: cw - 0.2, h: 0.85, fontSize: 14, color: HEX.muted, align: 'center' });
  });
  card(s, M, 5.05, W - 2 * M, 1.1, { fill: TINT.navy, line: TINT.navy, flat: true });
  text(s, [{ text: 'ما ننتظره من الديوان: ', options: { bold: true, color: HEX.navy } }, { text: 'التزكية وولاية التجربة؛ الحسابات الرسمية للإشعارات وبوابة الرسائل القصيرة والخط 198؛ ملفات SNACR للسنوات 2023 إلى 2025؛ مركز بيانات داخل تونس.' }],
    { x: M + 0.25, y: 5.05, w: W - 2 * M - 0.5, h: 1.1, fontSize: 16, valign: 'middle' });
  notes(s, 'المسار واضح: التزكية ثم الإنتاج ثم التجربة في ولاية واحدة ثم التعميم. المدد تقديرية.');
}
{
  const s = content(4, 'الإسهام: نموذج قابل للتعميم يربط المجتمع والمؤسسة والدولة في سلسلة قرار واحدة',
    'المصدر: إعداد الطالب');
  const cw = (W - 2 * M - 0.4) / 3;
  [['إسهام علمي', ['تطبيق منهج البحث بالتصميم على منظومة طوارئ وطنية', 'إطار تقييم يربط كل هدف بمؤشر مقيس', 'نموذج للذكاء الاصطناعي المساعد في الظل'], 'school', 'navy'],
    ['إسهام عملي', ['منظومة تعمل من خمسة مكونات', 'كراس شروط وقاموس بيانات وملف أمني جاهزة', 'معطيات مرجعية موحّدة للمعتمديات'], 'rocket_launch', 'green'],
    ['توصيات', ['اعتماد التجربة الميدانية في ولاية واحدة', 'تسليم ملفات SNACR الحقيقية', 'تدقيق أمني خارجي قبل الإطلاق'], 'flag', 'gold']].forEach(([t, list, ic, tone], i) => {
    const x = W - M - (i + 1) * cw - i * 0.2;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w: cw, h: 0.08, fill: { color: HEX[tone] }, line: { color: HEX[tone], width: 0 } });
    tile(s, x + cw - 0.75, 2.25, 0.65, tone, ic);
    text(s, t, { x, y: 2.3, w: cw - 0.9, h: 0.55, fontSize: 20, bold: true, valign: 'middle' });
    bullets(s, list, x, 3.15, cw, 2.7, 15);
  });
  takeaway(s, 'من التبليغ إلى أخذ القرار: سلسلة واحدة، محلية، مقيسة، وجاهزة للتجربة.');
  notes(s, 'أختم بالإسهام: علمي في المنهج والتقييم، وعملي في منظومة ووثائق جاهزة، وتوصيات محددة لمرحلة ما بعد الدفاع.');
}
{
  const s = newSlide('غلاف', 'الخاتمة');
  s.addImage({ path: img('logo-disc.png'), x: W - M - 2.4, y: 1.95, w: 2.4, h: 2.4, altText: 'شعار الديوان الوطني للحماية المدنية' });
  s.addText('شكرا لحسن انتباهكم', { placeholder: 'title', ...AR });
  s.addText('أسئلتكم وملاحظاتكم مرحّب بها', { placeholder: 'body', ...AR });
  text(s, 'الوثائق المرفقة: الملف الوصفي V33 · كراس الشروط · مخططات BPMN والبطاقات · قاموس البيانات 2.0 · الملف التقني والأمني · تقرير التحصين',
    { x: M, y: 5.5, w: W - 2 * M, h: 0.7, fontSize: 14, color: HEX.pale });
  notes(s, 'شكرا. أنا على ذمة اللجنة للأسئلة، ويمكن العودة إلى أي شريحة أو وثيقة مرفقة.');
}

// ---------- Animation names: content fades in (not placeholders, trackers, or the cover and closing). ----------
slides.forEach((s, k) => {
  if (!k || k === slides.length - 1) return;
  let a = 0;
  s._slideObjects.forEach(o => {
    const op = o.options || {};
    if (op.placeholder || /^trk /.test(op.objectName || '')) return;
    op.objectName = `anim ${++a} ${op.objectName || ''}`.trim();
  });
});

(async () => {
  if (slides.length !== MIN.length) throw new Error(`MIN has ${MIN.length} entries for ${slides.length} slides`);
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  const r = await applyTransitions(OUT, MIN.map((sec, k) => ({ effect: 'fade', durMs: k ? 700 : 1000, afterSec: sec })));
  console.log('ok', OUT, `${r.slides} slides, ${mmss(r.total)}`);
})();
