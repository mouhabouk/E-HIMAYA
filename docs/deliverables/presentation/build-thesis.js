// Graduation project defence deck (Arabic, right to left, 30 slides), in the style of a strategy-consulting deck:
// every title is the slide's conclusion, a section tracker on top, the source of each figure at the bottom.
//   cd docs/deliverables/presentation && node prep.js && SCREENS=<dir> node build-thesis.js e-Himaya_Soutenance.pptx
// SCREENS: the unzipped e-Himaya_Interfaces_images.zip (project files, screens/), with mobile/, dash/ and portal/.
// Editable in PowerPoint: layouts with placeholders (New Slide offers them), native charts and tables, a fade
// transition and an "After" time on every slide, content that fades in object by object (Animations tab).
// Figures come from the project files (description V33, phase reports); simulated figures carry [SIM].
const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
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

// The talk's time plan (seconds per slide, about 23 minutes), stored as each slide's "After" time and in its notes.
const MIN = [40, 70, 35, 15, 45, 45, 55, 15, 45, 60, 50, 55, 50, 15, 45, 55, 55, 50, 50, 50, 55, 50, 55, 50, 15, 60, 45, 50, 55, 40];
const SECTIONS = ['الوضع الحالي', 'الرؤية والقيمة المضافة', 'حياة البلاغ', 'الثقة والنتائج', 'الآفاق'];

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
  s.addText(`القسم ${sec + 1} من ${SECTIONS.length}`, { placeholder: 'num', objectName: 'anim 1 num', ...AR });
  s.addText(SECTIONS[sec], { placeholder: 'title', objectName: 'anim 2 title', ...AR });
  s.addText(sub, { placeholder: 'body', objectName: 'anim 3 body', ...AR });
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
// ---------- Screenshots: copied once into img/ (ignored by git), phones with rounded corners. ----------
const R = path.join(__dirname, '..', '..', '..');
const SCREENS = process.env.SCREENS || '/mnt/project-files/screens/images';
const SHOTS = [
  ['t-language.png', `${SCREENS}/mobile/m01-language.png`], ['t-charter.png', `${SCREENS}/mobile/m03-charter.png`],
  ['t-permissions.png', `${SCREENS}/mobile/m05-permissions.png`], ['t-signin.png', `${SCREENS}/mobile/m07-sign-in.png`],
  ['t-volunteer.png', `${SCREENS}/mobile/m37-volunteer-apply.png`], ['t-doctor-apply.png', `${SCREENS}/mobile/m40-doctor-apply.png`],
  ['t-doctor.png', `${SCREENS}/mobile/m39-doctor.png`], ['t-new-report.png', `${SCREENS}/mobile/m13-new-report.png`],
  ['t-report-fire.png', `${SCREENS}/mobile/m14-new-report-fire.png`], ['t-track.png', `${SCREENS}/mobile/m12-track.png`],
  ['t-my-data.png', `${SCREENS}/mobile/m47-my-data.png`], ['t-org-app.png', `${R}/docs/phase-p2a/p2a-home.png`],
  ['t-simple.png', `${R}/docs/phase-p5b/p5b-simple.png`], ['t-flash.png', `${R}/docs/phase-p5a/p5a-flash.png`],
  ['t-mission.png', `${R}/docs/phase-p4a/p4a-mission.png`], ['t-first-report.png', `${R}/docs/phase-p4a/p4a-first-report.png`],
  ['t-report-detail.png', `${SCREENS}/dash/d03-report-detail.png`, { left: 0, top: 225, width: 1440, height: 925 }, 0.012],
  ['t-incident.png', `${SCREENS}/dash/d07-incident-detail.png`, { left: 0, top: 225, width: 1440, height: 925 }, 0.012],
  ['t-portal.png', `${SCREENS}/portal/p06b-org-overview.png`, null, 0.012],
  ['t-model-card.png', `${R}/docs/phase-ai5/ai5-model-card-night.png`, { left: 0, top: 0, width: 1240, height: 1100 }, 0.012],
];
async function prepare() {
  for (const [name, src, crop, radius = 0.07] of SHOTS) {
    if (fs.existsSync(img(name))) continue;
    if (!fs.existsSync(src)) throw new Error('missing screenshot ' + src + ' (set SCREENS)');
    let x = sharp(src); if (crop) x = x.extract(crop);
    const buf = await x.png().toBuffer(); const { width, height } = await sharp(buf).metadata();
    const r = Math.round(width * radius);
    const mask = Buffer.from(`<svg width="${width}" height="${height}"><rect width="${width}" height="${height}" rx="${r}" ry="${r}"/></svg>`);
    await sharp(buf).composite([{ input: mask, blend: 'dest-in' }]).png().toFile(img(name));
  }
}
// A phone screenshot with a caption under it.
function phone(s, name, x, y, h, caption, alt) {
  const { w: pw, h: ph } = size(img(name)); const w = h * pw / ph;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x - 0.04, y: y - 0.04, w: w + 0.08, h: h + 0.08, rectRadius: w * 0.08, fill: { color: HEX.white }, line: { color: HEX.line, width: 0.75 }, shadow: shadow() });
  s.addImage({ path: img(name), x, y, w, h, altText: alt || caption || '' });
  if (caption) text(s, caption, { x: x - 0.2, y: y + h + 0.1, w: w + 0.4, h: 0.3, fontSize: 12, bold: true, color: HEX.muted, align: 'center' });
  return w;
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

function buildSlides() {
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
  const s = content(0, 'الخلاصة التنفيذية: من قنوات متفرقة وتسجيل يدوي إلى سلسلة واحدة تنقل البلاغ إلى القرار في ثوان، بمشاركة المجتمع',
    'المصدر: الملف الوصفي للمشروع V33؛ أرشيف SNACR لسنة 2022؛ قياسات الأداء والتحصين');
  const cols = [
    ['الوضع الحالي', 'red', 'أكثر من 143 ألف تدخل في السنة، تصل بالهاتف واللاسلكي والحضور، وتُسجَّل يدويا، دون موقع دقيق ولا صورة مشتركة للقرار.'],
    ['الرؤية', 'navy', 'منظومة سيادية واحدة: المواطن والمؤسسة يبلّغان، القاعة والفريق يتدخلان، القائد واللجان يقررون، على صورة واحدة.'],
    ['كيف', 'teal', 'حياة البلاغ رقمية من التسجيل إلى الغلق: تحليل آلي للنص والصوت والصورة، استنفار الأقرب، فريق يوثّق بالأزرار.'],
    ['القيمة', 'green', 'البلاغ في اللوحة في 0,45 ث؛ مجتمع شريك في الوقاية؛ نفاذ لكل الفئات؛ معطيات محمية بالقانون والتشفير.'],
  ];
  const cw = (W - 2 * M - 3 * 0.2) / 4;
  cols.forEach(([h, tone, body], i) => {
    const x = W - M - (i + 1) * cw - i * 0.2;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w: cw, h: 0.55, fill: { color: HEX[tone] }, line: { color: HEX[tone], width: 0 } });
    text(s, h, { x: x + 0.15, y: 1.95, w: cw - 0.3, h: 0.55, fontSize: 17, bold: true, color: HEX.white, valign: 'middle' });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.5, w: cw, h: 3.3, fill: { color: TINT[tone] }, line: { color: TINT[tone], width: 0 } });
    text(s, body, { x: x + 0.18, y: 2.7, w: cw - 0.36, h: 3.0, fontSize: 17 });
    if (i < 3) text(s, '◀', { x: x - 0.2, y: 3.95, w: 0.2, h: 0.4, fontSize: 14, color: HEX.muted, align: 'center' });
  });
  takeaway(s, 'المنظومة مبنية ومقيسة (288 من 292 متطلبا منجزة)، وما بقي قرار مؤسساتي: التزكية والحسابات الرسمية وولاية التجربة.');
  notes(s, 'العرض كله في هذه الأعمدة الأربعة: أين نحن اليوم، إلى أين نذهب، كيف يتم ذلك تقنيا عبر حياة البلاغ، وما القيمة المضافة.');
}

// ====================== 3. Agenda ======================
{
  const s = content(0, 'خطة العرض: من الوضع الحالي إلى الرؤية، ثم حياة البلاغ خطوة بخطوة، ثم الضمانات والنتائج');
  const subs = ['الحجم، نقاط التعطل، والمقارنة بين اليوم والغد', 'زمن الاستجابة، النجاعة، الوقاية، التشريك والنفاذ',
    'من تسجيل المستخدم إلى المعالجة في الميدان واللوحة والقرار', 'حماية المعطيات، الأمن المقيس، والنتائج', 'الطريق إلى الإنتاج والتوصيات'];
  SECTIONS.forEach((t, i) => {
    const y = 1.95 + i * 0.86;
    s.addShape(pres.shapes.OVAL, { x: W - M - 0.62, y, w: 0.62, h: 0.62, fill: { color: i === 2 ? HEX.gold : HEX.navy }, line: { color: i === 2 ? HEX.gold : HEX.navy, width: 1.5 } });
    text(s, `${i + 1}`, { x: W - M - 0.62, y, w: 0.62, h: 0.62, fontSize: 18, bold: true, color: HEX.white, align: 'center', valign: 'middle' });
    text(s, t, { x: W - M - 6.0, y, w: 5.2, h: 0.62, fontSize: 20, bold: true, valign: 'middle' });
    text(s, subs[i], { x: M, y, w: W - 2 * M - 6.2, h: 0.62, fontSize: 15, color: HEX.muted, valign: 'middle' });
  });
  text(s, 'القسم 3 هو قلب العرض', { x: M, y: 6.3, w: W - 2 * M, h: 0.3, fontSize: 12, bold: true, color: HEX.gold });
  notes(s, 'خمسة أقسام. القسم الثالث، حياة البلاغ، هو قلب العرض: نتبع بلاغا واحدا من أول تسجيل للمستخدم إلى القرار.');
}

// ====================== Section 1: current state ======================
notes(divider(0, 'كيف يجري العمل اليوم، وأين يضيع الوقت والدليل'), 'نبدأ من الواقع.');
{
  const s = content(0, 'الحجم وطني: أكثر من 143 ألف تدخل في سنة واحدة على 24 ولاية و279 معتمدية',
    'المصدر: أرشيف تدخلات الديوان (SNACR) لسنة 2022، معطيات حقيقية؛ المرجع الإداري للمعهد الوطني للإحصاء');
  stat(s, W - M - 3.9, 1.95, 3.9, 1.75, '143.308', 'تدخلا مسجّلا في 2022 (حقيقي)', 'navy', { fs: 36 });
  stat(s, W - M - 7.95, 1.95, 3.9, 1.75, '24 / 279', 'ولاية / معتمدية في المرجع الإداري', 'teal', { fs: 36 });
  stat(s, M, 1.95, 3.9, 1.75, '497 ألفا', 'تدخل مقدَّر تقريبا للسنوات 2023 إلى 2025 [SIM] على توزيعات 2022', 'orange', { fs: 36 });
  sim(s, M, 3.78);
  bullets(s, ['كل تدخل يمر بالقاعة الجهوية ثم الفريق الميداني، وأحيانا القائد واللجنة',
    'الأرشيف يُدخل لاحقا دون موقع دقيق ولا زمن وصول، فلا يقيس الأداء',
    '11,6 % من أسماء المعتمديات في أرشيف 2022 لا تطابق المرجع الإداري كما هي'], M, 4.2, W - 2 * M, 1.6, 17);
  takeaway(s, 'الحجم يبرر منظومة رقمية؛ وجودة الأرشيف تبرر توحيد المرجع قبل أي تحليل.');
  notes(s, 'أرقام 2022 حقيقية من أرشيف الديوان. السنوات الثلاث التالية مولّدة على توزيعاتها في انتظار الملفات، وهي معلَّمة [SIM].');
}
{
  const s = content(0, 'المسار الحالي يتعطل في أربع نقاط، كلها تؤخر القرار أو تفقده الدليل',
    'المصدر: ملاحظة سير العمل في القاعات؛ الملف الوصفي للمشروع، القسم 1');
  const pains = [['تشتت القنوات', 'الهاتف واللاسلكي والحضور: لا صورة ولا موقع دقيق ولا رقم تتبع للمبلّغ', 'sms', 'red'],
    ['تسجيل يدوي', 'إعادة كتابة البلاغ في القاعة، وإدخال الأرشيف لاحقا دون عنوان ولا وصف', 'fact_check', 'orange'],
    ['لا صورة مشتركة', 'لا خريطة واحدة بين القاعة والفريق والقائد واللجان', 'map', 'purple'],
    ['وقاية منفصلة', 'المؤسسة والمواطن خارج الحلقة: لا تنبيه مبكر ولا ملف سلامة رقمي', 'apartment', 'navy']];
  const cw = (W - 2 * M - 0.3) / 2;
  pains.forEach(([t, d, ic, tone], k) => {
    const col = k % 2, row = Math.floor(k / 2), x = W - M - cw - col * (cw + 0.3), y = 1.95 + row * 2.0;
    card(s, x, y, cw, 1.8);
    tile(s, x + cw - 1.0, y + 0.3, 0.75, tone, ic);
    text(s, t, { x: x + 0.25, y: y + 0.25, w: cw - 1.45, h: 0.45, fontSize: 19, bold: true });
    text(s, d, { x: x + 0.25, y: y + 0.8, w: cw - 1.45, h: 0.9, fontSize: 15, color: HEX.muted });
  });
  notes(s, 'أربع نقاط تعطل. كل خطوة من حياة البلاغ التي سنراها تعالج واحدة منها على الأقل.');
}
{
  const s = content(0, 'من اليوم إلى الغد: كل حلقة من المسار تنتقل من الجهد اليدوي إلى معلومة رقمية موثّقة',
    'المصدر: إعداد الطالب، بالاستناد إلى الملف الوصفي V33');
  table(s, ['البعد', 'اليوم', 'مع ء-حماية'], [
    ['التبليغ', 'مكالمة صوتية، وصف شفهي للمكان', 'SOS في 3 لمسات، موقع آلي، صورة وفيديو، دون إنترنت'],
    ['التسجيل', 'إعادة كتابة يدوية في القاعة', 'رقم تتبع فوري، بصمة للدليل، تصنيف وأولوية آلية'],
    ['الاستنفار', 'بالهاتف واللاسلكي', 'الفريق على تطبيقه، والمتطوع والطبيب الأقرب والأنسب'],
    ['الصورة المشتركة', 'تقارير متفرقة', 'خريطة واحدة للقاعة والفريق والقائد واللجان'],
    ['القرار', 'دون أثر مكتوب منظّم', 'توصية بأسبابها، قرار موقّع، كارثة بحوصلة'],
    ['الوقاية', 'ملفات ورقية للمؤسسات', 'ملف سلامة رقمي، تنبيه الكاميرا، شهادة برمز QR'],
  ], M, 1.95, W - 2 * M, [2.4, 4.2, 5.533], { boldFirst: true, fs: 15, rowH: 0.62 });
  notes(s, 'هذا الجدول هو الجسر بين الوضع الحالي والرؤية: ستة أبعاد، ولكل منها ما يتغير.');
}

// ====================== Section 2: vision and value ======================
notes(divider(1, 'ما تضيفه المنظومة: زمن أقصر، نجاعة أكبر، وقاية أوسع، ومجتمع شريك'), 'ننتقل إلى الرؤية والقيمة المضافة.');
{
  const s = content(1, 'الرؤية: سلسلة قيمة واحدة من ست حلقات، تمر بها المعلومة دون إعادة كتابة ودون أن تفقد دليلها',
    'المصدر: الملف الوصفي V33، القسم 1.1');
  chevrons(s, ['التبليغ', 'المعالجة', 'التحليل', 'مؤشرات الأداء', 'التنبؤ بالذكاء الاصطناعي', 'اتخاذ القرار'], 1.95, 0.95, { fs: 15, tones: ['red', 'orange', 'navy', 'teal', 'purple', 'green'] });
  const items = [['المواطن والمؤسسة', 'SOS، صورة، موقع، إنذار الكاميرا'], ['القاعة والفريق', 'تصنيف، أولوية، تجميع، استنفار'], ['التحليل', 'SNACR، المعتمديات ذات الأولوية'],
    ['المؤشرات', 'زمن الوصول، الأجل المستهدف'], ['الذكاء الاصطناعي', 'توصية بأسبابها، في الظل أولا'], ['القائد واللجان', 'قرار موقّع، كارثة بحوصلة']];
  const n = items.length, gap = 0.06, cw = (W - 2 * M - gap * (n - 1)) / n;
  items.forEach(([t, d], i) => {
    const x = W - M - (i + 1) * cw - i * gap;
    text(s, t, { x: x + 0.1, y: 3.1, w: cw - 0.2, h: 0.45, fontSize: 15, bold: true, align: 'center' });
    text(s, d, { x: x + 0.1, y: 3.55, w: cw - 0.2, h: 1.2, fontSize: 14, color: HEX.muted, align: 'center' });
  });
  takeaway(s, 'الجديد ليس في كل حلقة وحدها، بل في ربط الحلقات الست في منظومة واحدة سيادية.', 5.3);
  notes(s, 'الرؤية النموذجية: ما يدخل في التبليغ يصل إلى القرار بموقعه ودليله وتوقيته.');
}
{
  const s = content(1, 'تقليص زمن الاستجابة: المنظومة تختصر كل مرحلة يضيع فيها الوقت قبل وصول الفريق',
    'المصدر: قياس الأداء NFR-01 (0,45 ث، p95 = 328 ms)؛ أهداف SNACR إعدادات قابلة للتغيير');
  const steps = [['الاستقبال', 'زر SOS، رقم تتبع فوري، يعمل دون إنترنت', 'sos', 'red'], ['التحديد', 'الموقع الآلي ودقته بدل الوصف الشفهي', 'location_on', 'orange'],
    ['التقييم', 'نوع وأولوية من 0 إلى 100 وتجميع للبلاغات المتكررة', 'psychology', 'purple'], ['الاستنفار', 'تنبيه بملء الشاشة للفريق، والمتطوع الأقرب والأنسب', 'campaign', 'navy'],
    ['الطريق', 'أفضل مسار وأقرب مستشفى على الطريق', 'map', 'teal'], ['المتابعة', 'مراحل المهمة بالأزرار بتوقيت آلي', 'timer', 'green']];
  const n = steps.length, cw = (W - 2 * M - 0.15 * (n - 1)) / n;
  steps.forEach(([t, d, ic, tone], i) => {
    const x = W - M - (i + 1) * cw - i * 0.15;
    card(s, x, 1.95, cw, 2.75);
    tile(s, x + (cw - 0.75) / 2, 2.15, 0.75, tone, ic);
    text(s, t, { x: x + 0.1, y: 3.0, w: cw - 0.2, h: 0.45, fontSize: 17, bold: true, align: 'center' });
    text(s, d, { x: x + 0.1, y: 3.45, w: cw - 0.2, h: 1.15, fontSize: 13, color: HEX.muted, align: 'center' });
  });
  stat(s, W - M - 3.9, 4.95, 3.9, 1.35, '0,45 ث', 'من الإرسال إلى الظهور في اللوحة', 'navy', { fs: 28 });
  stat(s, W - M - 7.95, 4.95, 3.9, 1.35, '< 30 ث', 'أول تقرير ميداني للفريق بالأزرار', 'green', { fs: 28 });
  stat(s, M, 4.95, 3.9, 1.35, '10 / 15 / 25 د', 'أجل الحريق المستهدف: حضري / شبه حضري / ريفي', 'red', { fs: 26 });
  notes(s, 'الدقائق تضيع في التحديد والتقييم والاستنفار أكثر مما تضيع في الطريق. المنظومة تعالج كل مرحلة، والأثر الفعلي على زمن الوصول يقاس في التجربة الميدانية.');
}
{
  const s = content(1, 'النجاعة والقيمة الوقائية: من التدخل بعد الحادث إلى منعه، بمعطيات تقود الموارد',
    'المصدر: الملف الوصفي V33، الأقسام 4.3 و4.4؛ المراحل P3 و PL و S');
  const cw = (W - 2 * M - 0.3) / 2;
  [['النجاعة', 'navy', 'speed', ['سجل موارد كل ولاية والبحث عبر الولايات عن آلية أو معدة أو عون', 'خريطة واحدة بطبقات قابلة للإظهار، وتقارير دورية آلية',
    'برمجة الأنشطة اليومية والأسبوعية، ومخططات التدخل حسب الخطر', 'مؤشرات SNACR تحدد المعتمديات ذات الأولوية']],
   ['الوقاية', 'green', 'verified', ['ملف سلامة رقمي لكل مؤسسة، وتصنيف آلي بالنقائص حسب مجلة السلامة', 'زيارة الوقاية على الهاتف، وشهادة موقّعة برمز QR',
    'توعية ونصائح حسب صنف المؤسسة ونوع الخطر', 'البرامج الموسمية وخطر الشواطئ اليومي، والتنبيه المبكر بالكاميرا']]].forEach(([t, tone, ic, list], i) => {
    const x = W - M - (i + 1) * cw - i * 0.3;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w: cw, h: 0.08, fill: { color: HEX[tone] }, line: { color: HEX[tone], width: 0 } });
    tile(s, x + cw - 0.75, 2.2, 0.65, tone, ic);
    text(s, t, { x, y: 2.25, w: cw - 0.9, h: 0.55, fontSize: 21, bold: true, valign: 'middle' });
    bullets(s, list, x, 3.05, cw, 2.7, 16);
  });
  takeaway(s, 'كل تدخل يُتفادى بالوقاية هو أقصر زمن استجابة ممكن.', 5.9);
  notes(s, 'القيمة لا تقف عند السرعة: المنظومة تجعل الموارد مرئية وتحوّل المؤسسة إلى شريك في الوقاية.');
}
{
  const s = content(1, 'التشريك: أربع فئات من المجتمع تصبح جزءا من منظومة الحماية، لكل منها دور ومقابل',
    'المصدر: الملف الوصفي V33، الأقسام 4.1.9 إلى 4.1.13');
  const g = [['المواطنون', 'يبلّغون بالصورة والموقع، ويتلقون التنبيهات والنصائح', 'نقاط وشارات وشهادة تقدير', 'groups', 'red'],
    ['المتطوعون', 'جاهزية باختصاصاتهم، ويستجيبون للاستنفار ولو دون إنترنت', 'قرار معلَّل، ورزنامة توفر', 'handshake', 'orange'],
    ['الأطباء', 'متطوعون أو أطباء الحماية المدنية: ملف طبي مقفل، إحالة، رأي', 'توثيق بعمادة الأطباء ودليل', 'medical_services', 'teal'],
    ['المؤسسات', 'ملف سلامة، فريق سلامة، كاميرا تنبّه مبكرا', 'شهادة سلامة ووقاية رقمية', 'apartment', 'navy']];
  const cw = (W - 2 * M - 0.6) / 4;
  g.forEach(([t, d, get, ic, tone], i) => {
    const x = W - M - (i + 1) * cw - i * 0.2;
    card(s, x, 1.95, cw, 3.75);
    tile(s, x + (cw - 0.8) / 2, 2.2, 0.8, tone, ic);
    text(s, t, { x: x + 0.15, y: 3.15, w: cw - 0.3, h: 0.45, fontSize: 19, bold: true, align: 'center' });
    text(s, d, { x: x + 0.2, y: 3.65, w: cw - 0.4, h: 1.15, fontSize: 14, color: HEX.ink, align: 'center' });
    s.addShape(pres.shapes.LINE, { x: x + 0.3, y: 4.85, w: cw - 0.6, h: 0, line: { color: HEX.line, width: 0.75 } });
    text(s, get, { x: x + 0.2, y: 4.95, w: cw - 0.4, h: 0.6, fontSize: 13, bold: true, color: HEX[tone], align: 'center' });
  });
  takeaway(s, 'الحماية المدنية لم تعد تعمل وحدها: كل فئة تضيف عيونا وأيادي ومعلومة قبل وصول الفريق.', 5.9);
  notes(s, 'التشريك مقنَّن: لكل فئة صلاحيات محددة، وكل مشاركة توثَّق وتُكافأ.');
}
{
  const s = content(1, 'النفاذ لكل الفئات: المنظومة تصل إلى من لا يرى ومن لا يسمع ومن لا يقرأ جيدا ومن لا إنترنت له',
    'المصدر: الملف الوصفي V33، NFR-08 و NFR-10؛ المرحلتان P3c و P5 (مراجعة النفاذ)');
  const a = [['من لا يرى', 'قارئ الشاشة لكل زر وصورة، وقراءة صوتية للأدلة والتنبيهات', 'visibility_off', 'navy'],
    ['من لا يسمع', 'اهتزاز وومض الشاشة والمصباح، وبلاغ نصي دون مكالمة', 'sms', 'purple'],
    ['كبار السن', 'الوضع المبسّط بخمسة أزرار كبيرة، وتكبير الخط حتى 200%', 'accessibility_new', 'teal'],
    ['دون إنترنت', 'البلاغ محفوظ مشفّرا، ورسالة قصيرة جاهزة إلى 198', 'wifi_off', 'orange'],
    ['كل اللغات', 'العربية والفرنسية والإنجليزية، من اليمين أو اليسار', 'translate', 'green'],
    ['دون حساب', 'التبليغ كزائر بمعرّف مستعار، دون تسجيل العنوان IP', 'lock', 'red']];
  const pw = phone(s, 't-simple.png', M + 0.1, 1.95, 3.55, 'الوضع المبسّط', 'الوضع المبسّط بأزرار كبيرة');
  phone(s, 't-flash.png', M + 0.1 + pw + 0.3, 1.95, 3.55, 'الومض عند التنبيه', 'ومض الشاشة عند تنبيه عاجل');
  const left = M + 2 * pw + 0.75, cw = (W - M - left - 0.2) / 2;
  a.forEach(([t, d, ic, tone], k) => {
    const col = k % 2, row = Math.floor(k / 2), x = W - M - (col + 1) * cw - col * 0.2, y = 1.95 + row * 1.3;
    card(s, x, y, cw, 1.15);
    tile(s, x + cw - 0.75, y + 0.22, 0.55, tone, ic);
    text(s, t, { x: x + 0.15, y: y + 0.15, w: cw - 1.0, h: 0.4, fontSize: 16, bold: true });
    text(s, d, { x: x + 0.15, y: y + 0.55, w: cw - 1.0, h: 0.55, fontSize: 12, color: HEX.muted });
  });
  takeaway(s, 'المرجع WCAG 2.2 المستوى AA: لا معنى باللون وحده، وأهداف لمس 48 نقطة، وتباين محقَّق لكل زوج ألوان.', 5.95);
  notes(s, 'منظومة طوارئ لا تصل إلى الجميع ليست منظومة طوارئ. النفاذ صُمّم من البداية لا أُضيف في النهاية.');
}

// ====================== Section 3: the life of a report ======================
notes(divider(2, 'نتبع بلاغا واحدا: من أول تسجيل للمستخدم إلى القرار والغلق'), 'قلب العرض: حياة البلاغ.');
{
  const s = content(2, 'حياة البلاغ في ثماني محطات، تمر بأربع واجهات وخادم واحد',
    'المصدر: مخطط BPMN «من البلاغ إلى القرار»؛ الملف الوصفي V33، القسم 4');
  const st = [['1', 'التسجيل الذكي', 'التطبيق', 'red'], ['2', 'الصفة', 'التطبيق', 'red'], ['3', 'البلاغ', 'التطبيق', 'red'], ['4', 'الاستلام والتحليل', 'الخادم والذكاء', 'purple'],
    ['5', 'المؤسسة', 'التطبيق والبوابة', 'teal'], ['6', 'القاعة', 'اللوحة المركزية', 'navy'], ['7', 'الميدان', 'تطبيق الأعوان', 'orange'], ['8', 'القرار والغلق', 'اللوحة واللجان', 'green']];
  const n = st.length, cw = (W - 2 * M) / n;
  s.addShape(pres.shapes.LINE, { x: M + cw / 2, y: 2.75, w: W - 2 * M - cw, h: 0, line: { color: HEX.line, width: 3 } });
  st.forEach(([k, t, where, tone], i) => {
    const x = W - M - (i + 1) * cw;
    s.addShape(pres.shapes.OVAL, { x: x + cw / 2 - 0.42, y: 2.33, w: 0.84, h: 0.84, fill: { color: HEX[tone] }, line: { color: HEX.white, width: 3 } });
    text(s, k, { x: x + cw / 2 - 0.42, y: 2.33, w: 0.84, h: 0.84, fontSize: 22, bold: true, color: HEX.white, align: 'center', valign: 'middle' });
    text(s, t, { x: x + 0.05, y: 3.35, w: cw - 0.1, h: 0.75, fontSize: 15, bold: true, align: 'center', valign: 'top' });
    text(s, where, { x: x + 0.05, y: 4.1, w: cw - 0.1, h: 0.5, fontSize: 12, color: HEX.muted, align: 'center' });
  });
  card(s, M, 4.85, W - 2 * M, 1.0, { fill: TINT.navy, line: TINT.navy, flat: true });
  text(s, 'خيط واحد يربط المحطات: رقم التتبع وبصمة الدليل وسجل التدقيق. كل تغيير حالة يصل المبلّغ، وكل اطلاع على معطى شخصي يُسجَّل.',
    { x: M + 0.25, y: 4.85, w: W - 2 * M - 0.5, h: 1.0, fontSize: 16, valign: 'middle' });
  notes(s, 'هذه خريطة القسم: ثماني محطات. سنمر عليها واحدة واحدة دون إطالة، مع ما يحدث تقنيا في كل منها.');
}
{
  const s = content(2, 'المحطة 1، التسجيل الذكي: رقم الهاتف يكفي، ولا يُنشأ الحساب قبل التأكد منه، ويمكن التبليغ دون حساب',
    'المصدر: الملف الوصفي V33، F-APP-01 إلى F-APP-15؛ Keycloak بمزوّد ehimaya-phone-otp');
  // Four screens, right to left in the order the user meets them.
  const ph = 3.95, pw = ph * 1080 / 2340, gap = 0.28;
  [['t-language.png', '1. اللغة'], ['t-charter.png', '2. الشروط'], ['t-permissions.png', '3. الأذونات'], ['t-signin.png', '4. الدخول']].forEach(([n, c], i) => {
    phone(s, n, M + 4 * pw + 3 * gap - (i + 1) * pw - i * gap + 0.05, 1.95, ph, c, c);
  });
  const x0 = M + 4 * pw + 3 * gap + 0.45, cw = W - M - x0;
  [['دخول بالهاتف', 'red', 'رقم تونسي ورمز من 6 أرقام صالح 5 دقائق؛ لا حساب قبل الرمز الصحيح'],
    ['خيارات ذكية', 'purple', 'زائر مجهول دون العنوان IP؛ حساب مواطن أو مؤسسة؛ أذونات اختيارية بأسبابها'],
    ['شروط مؤرَّخة', 'navy', 'القبول بعد القراءة حتى النهاية، وكل إصدار جديد يُقبل مرة واحدة'],
    ['معطيات محمية', 'green', 'بطاقة التعريف مشفّرة؛ «معطياتي» للاطلاع والتصدير والحذف']].forEach(([t, tone, d], i) => {
    const y = 1.95 + i * 1.1;
    s.addShape(pres.shapes.RECTANGLE, { x: W - M - 0.07, y, w: 0.07, h: 0.95, fill: { color: HEX[tone] }, line: { color: HEX[tone], width: 0 } });
    text(s, t, { x: x0, y, w: cw - 0.2, h: 0.38, fontSize: 16, bold: true, color: HEX[tone] });
    text(s, d, { x: x0, y: y + 0.38, w: cw - 0.2, h: 0.6, fontSize: 13 });
  });
  text(s, 'لقطات من التطبيق [SIM]', { x: M, y: 6.35, w: 4, h: 0.25, fontSize: 10, color: HEX.muted, align: 'left' });
  notes(s, 'التسجيل مصمم كي لا يعطّل أحدا: الزائر يبلّغ دون حساب، ومن يسجّل يفعل ذلك برقم هاتفه فقط، والحساب لا يوجد قبل التأكد من الرقم.');
}
{
  const s = content(2, 'المحطة 2، الصفة: من «انضم إلينا» يصبح المستخدم متطوعا أو طبيبا متطوعا أو طبيب حماية مدنية، بعد توثيق',
    'المصدر: الملف الوصفي V33، F-APP-83 إلى F-APP-90 و F-APP-100؛ F-DSH-32 و F-DSH-33');
  const cw = (W - 2 * M - 0.4) / 3, shotsOf = ['t-volunteer.png', 't-doctor-apply.png', 't-doctor.png'];
  [['متطوع', 'handshake', 'orange', ['الاختصاصات: إسعاف، غوص، إطفاء، قيادة آليات ثقيلة…', 'الفترة والولاية، ووثائق إثبات مشفّرة', 'جاهزية بموافقة على مشاركة الموقع أثناءها فقط']],
    ['طبيب متطوع', 'medical_services', 'teal', ['الاختصاص (1 إلى 4 من 21)', 'رقم التسجيل بعمادة الأطباء ومكان العمل', 'يظهر في دليل الأطباء الموثَّقين دون هاتفه']],
    ['طبيب الحماية المدنية', 'local_fire_department', 'red', ['الوحدة والمعرّف المهني', 'يفتح الملف الطبي المقفل لمصابي ولايته', 'قد يُعيَّن في اللجنة الطبية (7 على الأكثر)']]].forEach(([t, ic, tone, list], i) => {
    const x = W - M - (i + 1) * cw - i * 0.2;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.95, w: cw, h: 0.7, fill: { color: HEX[tone] }, line: { color: HEX[tone], width: 0 } });
    text(s, t, { x: x + 0.2, y: 1.95, w: cw - 1.0, h: 0.7, fontSize: 18, bold: true, color: HEX.white, valign: 'middle' });
    s.addImage({ path: img('w-' + ic + '.png'), x: x + cw - 0.65, y: 2.08, w: 0.44, h: 0.44, altText: '' });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.65, w: cw, h: 2.4, fill: { color: TINT[tone] }, line: { color: TINT[tone], width: 0 } });
    const pw = phone(s, shotsOf[i], x + 0.15, 2.78, 2.15, null, t);
    bullets(s, list, x + pw + 0.35, 2.8, cw - pw - 0.5, 2.2, 13);
  });
  card(s, M, 5.2, W - 2 * M, 0.8, { fill: HEX.page, line: HEX.line, flat: true });
  text(s, [{ text: 'مشترك بين الثلاث: ', options: { bold: true, color: HEX.navy } }, { text: 'قرار الإدارة معلَّل؛ رزنامة توفر؛ مفتاح شخصي لكل طبيب يحميه رمز من 6 إلى 12 رقما؛ الإجابة على الاستنفار برسالة موقّعة دون إنترنت.' }],
    { x: M + 0.25, y: 5.2, w: W - 2 * M - 0.5, h: 0.8, fontSize: 15, valign: 'middle' });
  notes(s, 'ثلاث صفات من حساب واحد. الطبيب لا يُفتح له شيء قبل التوثيق، والملف الطبي يُفتح على هاتفه هو بمفتاحه الشخصي، لا على الخادم.');
}
{
  const s = content(2, 'المحطة 3، البلاغ: ثلاث لمسات على الأكثر، بالموقع والدليل، ويصل حتى دون إنترنت',
    'المصدر: الملف الوصفي V33، F-APP-30 إلى F-APP-38 و F-APP-40؛ لقطة من التطبيق [SIM]');
  const ph3 = 3.9, pw3 = ph3 * 1080 / 2340;
  [['t-new-report.png', 'النوع'], ['t-report-fire.png', 'الموقع والدليل'], ['t-track.png', 'المتابعة']].forEach(([n, c], i) => phone(s, n, M + 2 * (pw3 + 0.25) - i * (pw3 + 0.25), 1.95, ph3, c, c));
  const rows = [['النوع', 'حريق، فيضان، حادث مرور، غرق، تسرب كيميائي، حالة طبية…'], ['الدليل', 'نص وصور وفيديو وصوت حتى 5 دقائق، رفع بالاستئناف وبصمة SHA-256'],
    ['دون شبكة', 'قاعدة محلية مشفّرة SQLCipher ترسل آليا دون تكرار، أو رسالة قصيرة'], ['البث', 'زر Live ينقل الكاميرا مباشرة إلى الخادم المحلي'],
    ['المتابعة', 'رقم تتبع فوري، حتى للمجهول: مستلم، قيد المعالجة، التدخل جار، مغلق'], ['اختياري', '«أرفق ملفي الطبي»: غير مؤشرة افتراضيا']];
  rows.forEach(([k, v], i) => {
    const y = 1.95 + i * 0.75;
    text(s, k, { x: W - M - 1.5, y, w: 1.5, h: 0.6, fontSize: 15, bold: true, color: HEX.red, valign: 'middle' });
    text(s, v, { x: 6.85, y, w: W - M - 1.6 - 6.85, h: 0.6, fontSize: 14, valign: 'middle' });
    if (i < rows.length - 1) s.addShape(pres.shapes.LINE, { x: 6.85, y: y + 0.68, w: W - M - 6.85, h: 0, line: { color: HEX.line, width: 0.75 } });
  });
  sim(s, M, 6.3);
  notes(s, 'لحظة الضغط هي اللحظة الأصعب على المبلّغ، لذلك كل شيء آلي: الموقع والبصمة والإرسال اللاحق إن غابت الشبكة.');
}
{
  const s = content(2, 'المحطة 4، الاستلام والتحليل: الخادم يقرأ النص والصوت فيقترح النوع والأولوية والمصداقية ويجمع البلاغات المتكررة',
    'المصدر: الملف الوصفي V33، F-SRV-03 و F-SRV-04؛ كل النماذج محلية برخص MIT أو Apache-2.0');
  chevrons(s, ['استلام ورقم تتبع وبصمة', 'تفريغ الصوت Whisper', 'الترجمة إلى العربية Opus-MT', 'القراءة المهيكلة Qwen3 مع قاموس الدارجة', 'الأولوية والمصداقية والتجميع'], 1.95, 0.95, { fs: 13, tones: ['muted', 'purple', 'purple', 'purple', 'navy'] });
  shot(s, 't-report-detail.png', M, 3.1, 6.9, 3.4, 'البلاغ في اللوحة: الصنف والموقع والأولوية والنص');
  stat(s, W - M - 4.9, 3.1, 4.9, 1.05, '0 إلى 100', 'أولوية مفسَّرة: يرى العون لماذا', 'purple', { fs: 24 });
  stat(s, W - M - 4.9, 4.25, 4.9, 1.05, 'تجميع', 'بلاغات الواقعة نفسها بالتشابه والقرب', 'navy', { fs: 24 });
  stat(s, W - M - 4.9, 5.4, 4.9, 1.05, '0,45 ث', 'حتى يظهر البلاغ في اللوحة', 'green', { fs: 24 });
  notes(s, 'البلاغ بالدارجة أو الفرنسية يُفهم. النموذج يقترح ولا يقرر، والعون يرى سبب الأولوية، وكل تصحيح منه يُسجَّل ويصير مادة تعلّم في الظل.');
}
{
  const s = content(2, 'تحليل الصور: نموذج رؤية محلي يكشف النار والدخان والأشخاص، بمكتبات مفتوحة المصدر ومعطيات تدريب موثّقة',
    'المصدر: الملف الوصفي V33، F-SRV-05 و F-SRV-36، القسم 7.2؛ بطاقات النماذج (المرحلة L5)');
  shot(s, 't-model-card.png', M, 1.95, 3.6, 3.65, 'بطاقة نموذج في اللوحة');
  const x0 = M + 3.95, cw = W - M - x0;
  [['النموذج', 'videocam', 'red', ['YOLOX-Tiny لكشف النار والدخان والأشخاص', 'على صور البلاغ والبث وكاميرات المؤسسات والأبراج', 'يعمل على خادم عادي أو جهاز طرفي']],
    ['المكتبات', 'storage', 'navy', ['onnxruntime لتشغيل النموذج دون إنترنت', 'faster-whisper و Qwen3 عبر Ollama للصوت والنص', 'كلها برخص Apache-2.0 أو MIT']],
    ['التدريب والضمانات', 'verified', 'green', ['معطيات Open Images و FireNET و D-Fire', 'تأكيد الحريق في 3 من 5 إطارات قبل التنبيه', 'بطاقة نموذج بالحدود والأخطاء والأرقام بتاريخها']]].forEach(([t, ic, tone, list], i) => {
    const y = 1.95 + i * 1.25;
    card(s, x0, y, cw, 1.12);
    tile(s, W - M - 0.8, y + 0.22, 0.65, tone, ic);
    text(s, t, { x: W - M - 3.0, y: y + 0.1, w: 2.05, h: 0.92, fontSize: 17, bold: true, valign: 'middle' });
    text(s, list.join('؛ '), { x: x0 + 0.2, y: y + 0.08, w: cw - 3.3, h: 0.96, fontSize: 13, valign: 'middle' });
  });
  takeaway(s, 'الصورة لا تخرج من خوادم الديوان، والنموذج لا يرسل تنبيها آليا إلا بعتبة تعتمدها لجنة فنية.', 5.8);
  notes(s, 'تحليل الصور بمكتبات مفتوحة وعلى خوادم محلية. لكل نموذج بطاقة تشرح حدوده، والعتبات تعتمدها لجنة فنية.');
}
{
  const s = content(2, 'المحطة 5، المؤسسة: التطبيق للمتابعة السريعة، والبوابة للمتابعة العميقة، والكاميرا تنبّه صاحبها أولا',
    'المصدر: الملف الوصفي V33، F-APP-130 إلى F-APP-138 و F-POR-01 إلى F-POR-14؛ مخطط BPMN للإنذار الأولي');
  const cw = (W - 2 * M - 0.3) / 2;
  [['تطبيق المؤسسة: نظرة سطحية', 'smartphone', 'teal', ['الحالة ونسبة الجاهزية والفريق والمعدات والشهادة', 'رسائل الديوان مع «اطّلعتُ» يسجّل من أكّد ومتى', 'صيانة معدّة بصورة، تمرين أو تظاهرة، التبليغ باسم المؤسسة']],
    ['بوابة المؤسسات: متابعة عميقة', 'apartment', 'navy', ['التسجيل والأعضاء والأدوار وفريق السلامة ودوراته', 'المواد الخطرة برقم الأمم المتحدة، والوثائق بإصداراتها', 'تصنيف آلي بالنقائص، وشهادة موقّعة برمز QR وصفحة تحقق']]].forEach(([t, ic, tone, list], i) => {
    const x = W - M - (i + 1) * cw - i * 0.3;
    card(s, x, 1.95, cw, 2.85);
    tile(s, x + cw - 0.9, 2.1, 0.6, tone, ic);
    text(s, t, { x: x + 0.2, y: 2.12, w: cw - 1.2, h: 0.5, fontSize: 17, bold: true });
    if (i === 0) { const pw = phone(s, 't-org-app.png', x + 0.2, 2.15, 2.5, null, 'فضاء المؤسسة في التطبيق'); bullets(s, list, x + pw + 0.4, 2.75, cw - pw - 0.55, 2.0, 13); }
    else { shot(s, 't-portal.png', x + 0.15, 2.7, 2.6, 2.0, 'بوابة المؤسسات: النظرة العامة'); bullets(s, list, x + 2.95, 2.75, cw - 3.1, 2.0, 13); }
  });
  chevrons(s, ['الكاميرا ترصد', 'إنذار موقّع لصاحب المؤسسة', 'نفي: يُغلق', 'تأكيد أو لا رد في 90 ث: بلاغ للقاعة'], 5.05, 0.8, { fs: 14, tones: ['muted', 'orange', 'green', 'red'] });
  notes(s, 'المؤسسة تعيش البلاغ من جهتين: صاحبها على الهاتف يرى ويؤكد بسرعة، وفريق السلامة على البوابة يدير الملف كاملا. والإنذار الكاذب لا يصل القاعة.');
}
{
  const s = content(2, 'المحطة 6، القاعة: اللوحة المركزية تجمع البلاغ ووسائطه وتحليله على خريطة واحدة، وتستنفر الأقرب والأنسب',
    'المصدر: الملف الوصفي V33، F-DSH-03 و F-DSH-05 و F-DSH-07 و F-DSH-30 و F-DSH-54 و F-DSH-110؛ لقطة [SIM]');
  shot(s, 't-incident.png', M, 1.9, 6.6, 4.7, 'صفحة الحادث: البلاغان المجمّعان والموقع والأولوية');
  bullets(s, ['عدد المبلّغين عن الواقعة، والوسائط مجمّعة، وتحليل الذكاء الاصطناعي',
    'بلاغ الهاتف أو اللاسلكي يدخله العون بقناته، فيلتحق بالمسار نفسه',
    'استنفار الفريق، والمتطوعين والأطباء الأقرب والأنسب',
    'أقرب المستشفيات على الطريق، وبطاقة الطوارئ الطبية تُفتح عند الطلب ويُسجَّل الفتح',
    'نقطة المهمة على الخريطة تُرسل إلى الفريق'], 7.5, 2.0, W - M - 7.5, 4.6, 15);
  notes(s, 'في القاعة يتحول البلاغ إلى تدخل: العون يؤكد التصنيف ويكلّف الفريق ويستنفر الأقرب، وكل ذلك على خريطة واحدة.');
}
{
  const s = content(2, 'المحطة 7، الميدان: تطبيق الأعوان يوثّق التدخل بالأزرار والصوت، حتى دون شبكة',
    'المصدر: الملف الوصفي V33، F-STF-01 إلى F-STF-14؛ لقطة [SIM]');
  const ph7 = 4.3, pw7 = ph7 * 1080 / 2340;
  phone(s, 't-mission.png', M + pw7 + 0.25, 1.92, ph7, 'المهمة والمراحل', 'شاشة المهمة');
  phone(s, 't-first-report.png', M, 1.92, ph7, 'التقرير الأول', 'التقرير الأول');
  const rows = [['التفعيل', 'الرقم المهني ورمز يعمل مرة واحدة، ثم رقم سري وربط بالجهاز ومسح عن بعد'], ['التنبيه', 'المهمة بملء الشاشة، ونقطة المهمة والطريق إليها'],
    ['المراحل', 'زر دائري بضغط مطوّل: انطلقنا، وصلنا، غادرنا، المستشفى، متاحون، رجعنا'], ['التقرير', 'أول تقرير في أقل من 30 ثانية: النوع، الخطورة، تعزيز، خطر على الأعوان'],
    ['المصابون', 'عدادات ولون الفرز والعمر التقريبي والمستشفى، دون أسماء'], ['الصوت والبث', 'محضر بالصوت يُفرَّغ آليا، وبث المهمة إلى القاعة'], ['دون شبكة', 'مزامنة دون تكرار، أو رسالة قصيرة موقّعة EH2']];
  rows.forEach(([k, v], i) => {
    const y = 1.92 + i * 0.66;
    text(s, k, { x: W - M - 1.6, y, w: 1.6, h: 0.56, fontSize: 15, bold: true, color: HEX.orange, valign: 'middle' });
    text(s, v, { x: 5.1, y, w: W - M - 1.7 - 5.1, h: 0.56, fontSize: 13, valign: 'middle' });
    if (i < rows.length - 1) s.addShape(pres.shapes.LINE, { x: 5.1, y: y + 0.61, w: W - M - 5.1, h: 0, line: { color: HEX.line, width: 0.75 } });
  });
  notes(s, 'قائد الفريق وحده يسجّل، بالأزرار لا بالكتابة. كل مرحلة بتوقيتها الآلي، فيصير زمن الوصول مقيسا لا مقدَّرا.');
}
{
  const s = content(2, 'المحطة 8، القرار والغلق: توصية بأسبابها، قرار موقّع، إعلام المبلّغ، ثم أرشفة تغذي المكتبة والذاكرة الوطنية',
    'المصدر: الملف الوصفي V33، F-DSH-16 و F-DSH-22 و F-DSH-23 و F-DSH-97 و F-APP-38 و F-APP-110؛ لقطة [SIM]');
  shot(s, 'shot-disasters.png', M, 1.9, W - 2 * M, 2.1, 'حوصلة الكوارث');
  const cw = (W - 2 * M - 0.6) / 4;
  [['القرار', 'مساعد القائد يقترح، والقائد يعتمد أو يعدّل أو يرفض بسبب؛ قرار اللجنة موقّع', 'gavel', 'green'],
    ['الكارثة', 'محاور ومطالب وإجلاء وإيواء وتقارير وضع، وحوصلة نهائية', 'thunderstorm', 'navy'],
    ['المبلّغ', 'إشعار «الفريق في الطريق» ثم «وصل»، والحالة حتى الغلق، ونقاط إن تأكد البلاغ', 'campaign', 'orange'],
    ['المكتبة', 'مكتبة الأحداث ببحث دلالي وروزنامة، والذاكرة الوطنية للدروس', 'insights', 'purple']].forEach(([t, d, ic, tone], i) => {
    const x = W - M - (i + 1) * cw - i * 0.2;
    card(s, x, 4.2, cw, 2.15);
    tile(s, x + cw - 0.8, 4.35, 0.55, tone, ic);
    text(s, t, { x: x + 0.15, y: 4.38, w: cw - 1.05, h: 0.45, fontSize: 17, bold: true });
    text(s, d, { x: x + 0.15, y: 5.0, w: cw - 0.3, h: 1.3, fontSize: 13, color: HEX.muted });
  });
  notes(s, 'تنتهي حياة البلاغ حيث تبدأ المعرفة: كل تدخل مغلق يدخل مكتبة الأحداث ويغذي تحليل المخاطر للسنة القادمة.');
}

// ====================== Section 4: trust and results ======================
notes(divider(3, 'ما يضمن الثقة: القانون، الأمن المقيس، والنتائج'), 'القسم الرابع: الضمانات والنتائج.');
{
  const s = content(3, 'حماية المعطيات الشخصية مطبّقة فعلا وفق القانون الأساسي 63 لسنة 2004، لا مكتوبة في الشروط فقط',
    'المصدر: الملف الوصفي V33، القسمان 2 و8؛ القانون الأساسي عدد 63 لسنة 2004؛ اتفاقية مجلس أوروبا 108');
  table(s, ['المبدأ', 'ما طُبّق فعلا في المنظومة'], [
    ['الموافقة', 'شروط بإصدار مؤرَّخ تُقرأ حتى النهاية؛ موافقة منفصلة للمعطيات الطبية ولسجل المواقع'],
    ['حقوق الشخص', '«معطياتي»: الاطلاع والتصدير والتصحيح والحذف النهائي من التطبيق'],
    ['التقليل والغرض', 'التبليغ المجهول؛ الإشعارات دون محتوى حساس؛ مواقع المتطوعين أثناء الجاهزية فقط'],
    ['السرية', 'رقم بطاقة التعريف مشفّر؛ الملف الطبي على الهاتف ولا يفتحه الخادم ولا القاعة'],
    ['المساءلة', 'كل اطلاع مسجَّل في سجل غير قابل للتعديل؛ المواطن يرى من فتح ملفه ومتى'],
    ['الاحتياط', 'تسجيل المكالمات وسجل المواقع معطَّلان حتى ترخيص الهيئة الوطنية لحماية المعطيات الشخصية'],
  ], M + 2.2, 1.95, W - 2 * M - 2.2, [2.4, 7.533], { boldFirst: true, fs: 13, rowH: 0.54 });
  phone(s, 't-my-data.png', M, 1.95, 3.7, '«معطياتي»', 'شاشة معطياتي');
  takeaway(s, 'لا معطى شخصي يخرج إلى خدمة أجنبية، والإطلاق مشروط بترخيص الهيئة.', 6.0);
  notes(s, 'الجانب القانوني ليس فقرة في الشروط: كل مبدأ له تطبيق تقني يمكن التحقق منه. ما يحتاج ترخيصا بقي معطَّلا حتى يصدر.');
}
{
  const s = content(3, 'الأمن مثبت بالقياس: تحصين الخادم رفع مؤشر Lynis من 57 إلى 82 وأبقى منفذين فقط',
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
  notes(s, 'لم أكتف بالتصريح بالأمن: قسته قبل سكريبت التحصين وبعده. القياس في حاوية، فهو حدّ أدنى يُعاد على خادم حقيقي قبل الإطلاق.');
}
{
  const s = content(3, 'النتائج: أداء أفضل بكثير من المطلوب، و288 من 292 متطلبا منجزة',
    'المصدر: الملف الوصفي V33، NFR-01 و NFR-13 و NFR-15 (اختبار الحمل k6 وتمرين الاستعادة)');
  s.addChart(pres.charts.BAR, [
    { name: 'المطلوب', labels: ['الظهور في اللوحة', 'استلام البلاغ'], values: [3, 2] },
    { name: 'المقيس', labels: ['الظهور في اللوحة', 'استلام البلاغ'], values: [0.45, 0.328] },
  ], { x: M, y: 1.95, w: 6.2, h: 4.0, barDir: 'bar', barGrouping: 'clustered', chartColors: [HEX.line, HEX.navy], showValue: true, dataLabelFormatCode: '0.0##',
    showTitle: true, title: 'بالثواني، المئين 95', titleFontSize: 13, titleFontFace: '+mn-lt', titleColor: HEX.ink,
    dataLabelFontSize: 13, dataLabelFontBold: true, catAxisLabelFontSize: 13, valAxisLabelFontSize: 11, showLegend: true, legendPos: 'b', legendFontSize: 12,
    valGridLine: { color: HEX.line, size: 0.5 }, catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt', dataLabelFontFace: '+mn-lt', legendFontFace: '+mn-lt' });
  const kpis = [['288 / 292', 'متطلبا منجزا، والأربعة الباقية جزئية بانتظار قرار خارجي'], ['16 / ث', 'بلاغ SOS في الثانية دون خطأ'], ['2 ث و1 ث', 'زمن الاستعادة وفقدان المعطيات في التمرين'], ['≈ 2000', 'اختبار آلي، و26 فحصا لكل تعديل']];
  kpis.forEach(([n, l], i) => {
    const y = 1.95 + i * 1.0;
    text(s, n, { x: W - M - 2.4, y, w: 2.4, h: 0.85, fontSize: 26, bold: true, color: HEX.navy, valign: 'middle' });
    text(s, l, { x: 7.1, y, w: W - M - 2.5 - 7.1, h: 0.85, fontSize: 15, valign: 'middle' });
    if (i < kpis.length - 1) s.addShape(pres.shapes.LINE, { x: 7.1, y: y + 0.93, w: W - M - 7.1, h: 0, line: { color: HEX.line, width: 0.75 } });
  });
  notes(s, 'القياس على بيئة الاختبار. الهدف الوطني، مليون مستخدم و5000 بلاغ في الساعة، يقاس في التجربة الميدانية.');
}

// ====================== Section 5: outlook ======================
{
  const s = content(4, 'الطريق إلى الإنتاج: التزكية، ثم الإنتاج، ثم تجربة في ولاية واحدة قبل التعميم',
    'المصدر: كراس الشروط (2026)؛ المدد التقديرية [SIM]؛ قائمة المؤجَّل');
  const steps = [['منجز', 'النموذج التجريبي', 'كامل، يُعرض دون إنترنت', 'green'], ['الخطوة 1', 'التزكية', 'قرار الديوان وولاية التجربة', 'navy'],
    ['الخطوة 2', 'الإنتاج', '8 خوادم بالمناطق، ربط Oracle، الحسابات الرسمية', 'orange'], ['الخطوة 3', 'التجربة', '3 أشهر في ولاية واحدة [SIM]', 'purple'], ['بعدها', 'التعميم', '24 ولاية', 'teal']];
  const n = steps.length, cw = (W - 2 * M - 0.2 * (n - 1)) / n;
  s.addShape(pres.shapes.LINE, { x: M + cw / 2, y: 2.2, w: W - 2 * M - cw, h: 0, line: { color: HEX.line, width: 2 } });
  steps.forEach(([w, t, d, tone], i) => {
    const x = W - M - (i + 1) * cw - i * 0.2;
    s.addShape(pres.shapes.OVAL, { x: x + cw / 2 - 0.25, y: 1.95, w: 0.5, h: 0.5, fill: { color: HEX[tone] }, line: { color: HEX.white, width: 2 } });
    text(s, w, { x, y: 2.55, w: cw, h: 0.35, fontSize: 14, bold: true, color: HEX[tone], align: 'center' });
    text(s, t, { x, y: 2.9, w: cw, h: 0.55, fontSize: 18, bold: true, align: 'center', valign: 'middle' });
    text(s, d, { x: x + 0.1, y: 3.45, w: cw - 0.2, h: 0.8, fontSize: 13, color: HEX.muted, align: 'center' });
  });
  const cw2 = (W - 2 * M - 0.3) / 2;
  [['ما ننتظره من الديوان', 'navy', ['التزكية واختيار ولاية التجربة', 'الحسابات الرسمية للإشعارات وبوابة الرسائل والخط 198', 'ملفات SNACR للسنوات 2023 إلى 2025، ومركز بيانات داخل تونس']],
    ['ما يبقى قبل الإطلاق', 'red', ['ترخيص الهيئة الوطنية لحماية المعطيات الشخصية', 'فحص ZAP واختبار اختراق وتدقيق الوكالة الوطنية للأمن السيبراني', 'إعادة قياس الأداء والتحصين على الخوادم الحقيقية']]].forEach(([t, tone, list], i) => {
    const x = W - M - (i + 1) * cw2 - i * 0.3;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 4.45, w: cw2, h: 0.08, fill: { color: HEX[tone] }, line: { color: HEX[tone], width: 0 } });
    text(s, t, { x, y: 4.6, w: cw2, h: 0.45, fontSize: 18, bold: true, color: HEX[tone] });
    bullets(s, list, x, 5.1, cw2, 1.5, 14);
  });
  notes(s, 'المسار واضح والحدود معروفة: ما ينتظر قرارا من الديوان، وما يبقى تقنيا وقانونيا قبل الإطلاق.');
}
{
  const s = newSlide('غلاف', 'الخاتمة');
  s.addImage({ path: img('logo-disc.png'), x: W - M - 2.4, y: 1.95, w: 2.4, h: 2.4, altText: 'شعار الديوان الوطني للحماية المدنية' });
  s.addText('من التبليغ إلى أخذ القرار: سلسلة واحدة، محلية، مقيسة، وجاهزة للتجربة', { placeholder: 'title', ...AR });
  s.addText('شكرا لحسن انتباهكم، أسئلتكم مرحّب بها', { placeholder: 'body', ...AR });
  text(s, 'الوثائق المرفقة: الملف الوصفي V33 · كراس الشروط · مخططات BPMN والبطاقات · قاموس البيانات 2.0 · الملف التقني والأمني · تقرير التحصين',
    { x: M, y: 5.5, w: W - 2 * M, h: 0.7, fontSize: 14, color: HEX.pale });
  notes(s, 'أختم بالجملة التي تلخص المشروع. شكرا، وأنا على ذمة اللجنة للأسئلة.');
}

// ---------- Animation names: content fades in on every slide (not placeholders or trackers). ----------
slides.forEach((s, k) => {
  let a = 0;
  s._slideObjects.forEach(o => {
    const op = o.options || {};
    if (op.placeholder || /^trk /.test(op.objectName || '')) return;
    op.objectName = `anim ${++a} ${op.objectName || ''}`.trim();
  });
});
}

(async () => {
  await prepare();
  buildSlides();
  if (slides.length !== MIN.length) throw new Error(`MIN has ${MIN.length} entries for ${slides.length} slides`);
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  const r = await applyTransitions(OUT, MIN.map((sec, k) => ({ effect: 'fade', durMs: k ? 700 : 1000, afterSec: sec })));
  console.log('ok', OUT, `${r.slides} slides, ${mmss(r.total)}`);
})();
