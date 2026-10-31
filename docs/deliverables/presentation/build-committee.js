// Committee presentation in the Prezi style (review point 13, phase 4): one map of seven stations, a Morph zoom into
// each station and back to the map, the map as a clickable summary. Arabic, right to left, speaker notes.
//   cd docs/deliverables/presentation && node prep.js && node build-committee.js e-Himaya_Presentation_Comite.pptx
// PowerPoint 2019/365 plays the Morph transition (objects named "!!…" are matched across slides); older viewers and
// LibreOffice fall back to a fade. Transitions and the timing of every slide (MIN, about 21 minutes) are written as
// PowerPoint writes them, so both can be changed in its Transitions tab; "Use Timings" is on. Each station's content fades in after the Morph. The map's stations link to their first slide, and every slide links back to the map
// (PowerPoint's Summary Zoom cannot be written by a generator; the links give the same navigation).
const pptxgen = require('pptxgenjs');
const { applyTransitions, mmss } = require('../lib/transitions');
const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

const R = process.env.REPO || path.join(__dirname, '..', '..', '..');
const OUT = process.argv[2] || 'e-Himaya_Presentation_Comite.pptx';
const W = 13.333, H = 7.5;
const FONT = 'Arial';
const T = { ink: '182038', muted: '5B6478', page: 'F3F5FA', line: 'E3E7EF', navy: '1F3FA0', red: 'D7141A', orange: 'C25E00',
  green: '188038', purple: '7838A0', teal: '00806A', amber: 'F5B400', sky: '1976D2', slate: '5B6478', deep: '0E1426' };
const TINT = { navy: 'E8EDFA', red: 'FDE8E8', orange: 'FFF3D6', green: 'E6F4EA', purple: 'F2EAF8', teal: 'E0F3EF', slate: 'EEF0F4', sky: 'E3F0FB' };
const AR = { rtlMode: true, lang: 'ar-TN', fontFace: FONT };
const img = n => path.join(__dirname, 'img', n);

// The seven stations of the map, clockwise from the top.
const ST = [
  { key: 'today', title: 'الوضع الحالي', sub: 'ما نعالجه', icon: 'flag', tone: 'slate' },
  { key: 'citizen', title: 'المواطن والمؤسسة', sub: 'التبليغ في ثوان', icon: 'sos', tone: 'red' },
  { key: 'room', title: 'القاعة والميدان', sub: 'من البلاغ إلى المهمة', icon: 'dashboard', tone: 'navy' },
  { key: 'decision', title: 'القرار والكوارث', sub: 'اللجان والحوصلة', icon: 'gavel', tone: 'green' },
  { key: 'snacr', title: 'تحليل المخاطر', sub: 'SNACR والتغطية', icon: 'insights', tone: 'purple' },
  { key: 'security', title: 'الأمن والسيادة', sub: 'مقيس قبل وبعد', icon: 'shield', tone: 'teal' },
  { key: 'road', title: 'الطريق إلى الإنتاج', sub: 'ما ننتظره من الديوان', icon: 'rocket_launch', tone: 'orange' },
];
// Map geometry: frames on an ellipse around the hub. A frame has the slide's ratio, so zooming makes it the slide.
const FW = 2.3, FH = FW * H / W, CX = W / 2, CY = 3.95, RX = 4.55, RY = 2.45;
// Station 1 at the top, then on towards the left (the reading direction of Arabic).
ST.forEach((s, i) => {
  const a = i * 2 * Math.PI / ST.length;
  s.cx = CX - RX * Math.sin(a);
  s.cy = CY - RY * Math.cos(a);
});

async function prepare() {
  fs.mkdirSync(path.join(__dirname, 'img'), { recursive: true });
  const shots = [
    ['shot-phone.png', `${R}/docs/phase-ui/mobile-home-light.jpg`, null],
    ['shot-dash.png', `${R}/docs/phase-ui/dash-ar-light.jpg`, null],
    ['shot-disasters.png', `${R}/docs/phase-n/n-disasters.png`, { left: 0, top: 380, width: 1280, height: 420 }],
    ['shot-dmap.png', `${R}/docs/phase-n/n-disasters.png`, { left: 20, top: 800, width: 870, height: 540 }],
    ['shot-snacr.png', `${R}/docs/phase-s/s-snacr-matrix.png`, { left: 0, top: 0, width: 1280, height: 760 }],
    ['shot-staff.png', `${R}/docs/phase-f/f-on-scene.png`, null],
  ];
  for (const [name, src, crop] of shots) {
    if (fs.existsSync(img(name))) continue;
    let s = sharp(src); if (crop) s = s.extract(crop);
    const buf = await s.png().toBuffer(); const { width, height } = await sharp(buf).metadata();
    const r = Math.round(Math.min(width, height) * 0.04);
    const mask = Buffer.from(`<svg width="${width}" height="${height}"><rect width="${width}" height="${height}" rx="${r}" ry="${r}"/></svg>`);
    await sharp(buf).composite([{ input: mask, blend: 'dest-in' }]).png().toFile(img(name));
  }
  const bpmn = process.env.BPMN_PNG;
  if (bpmn && fs.existsSync(bpmn)) await sharp(bpmn).resize({ width: 2400 }).png().toFile(img('bpmn.png'));
  for (const s of ST) if (!fs.existsSync(img('w-' + s.icon + '.png'))) throw new Error('run prep.js first (icons)');
}
const size = f => { const b = fs.readFileSync(f); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; };

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.rtlMode = true;
pres.title = 'ء-حماية: العرض أمام اللجنة';
pres.author = 'e-Himaya';
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };

// Minutes per slide, in order (seconds): the talk's time plan, shown in the notes and stored as each slide's "After".
const MIN = [30, 60, 90, 15, 120, 90, 15, 120, 75, 15, 120, 60, 15, 120, 15, 90, 75, 15, 120, 30];
let slideCount = 0;
function newSlide() { const s = pres.addSlide(); s.n = slideCount++; return s; }
function notes(s, t) {
  const done = MIN.slice(0, s.n + 1).reduce((a, b) => a + b, 0);
  s.addNotes(`⏱ ${mmss(MIN[s.n])} لهذه الشريحة · ${mmss(done)} من ${mmss(MIN.reduce((a, b) => a + b, 0))} عند نهايتها\n\n${t}`);
}

// Objects added from index `from` on get an entrance fade (named "anim …", timed in the Animations tab).
function animate(s, from) { s._slideObjects.slice(from).forEach((o, k) => { o.options.objectName = `anim ${k + 1} ${o.options.objectName || ''}`.trim(); }); }

function text(s, t, o) { s.addText(t, { isTextBox: true, margin: 0, align: 'right', valign: 'top', color: T.ink, fontSize: 16, ...AR, ...o }); }

// The map drawn at a zoom: k and the point (fx, fy) of the map that lands at the slide centre.
function drawMap(s, { k = 1, fx = CX, fy = CY, focus = -1, visited = [], links = false }) {
  const X = x => (x - fx) * k + W / 2, Y = y => (y - fy) * k + H / 2;
  // The orbit and the hub.
  s.addShape(pres.shapes.OVAL, { x: X(CX - RX), y: Y(CY - RY), w: 2 * RX * k, h: 2 * RY * k, fill: { color: 'FFFFFF', transparency: 100 },
    line: { color: 'C9D2E6', width: 1.5 * Math.min(k, 3), dashType: 'dash' }, objectName: '!!orbit' });
  const hub = 1.55;
  s.addShape(pres.shapes.OVAL, { x: X(CX - hub / 2), y: Y(CY - hub / 2), w: hub * k, h: hub * k, fill: { color: 'FFFFFF' }, line: { color: T.line, width: 1 }, objectName: '!!hub' });
  s.addImage({ path: img('logo.png'), x: X(CX - 0.55), y: Y(CY - 0.62), w: 1.1 * k, h: 1.1 * k, objectName: '!!hub-logo', altText: 'شعار الديوان الوطني للحماية المدنية' });
  if (k === 1) text(s, 'ء-حماية', { x: CX - 1.2, y: CY + 0.5, w: 2.4, h: 0.4, fontSize: 15, bold: true, align: 'center', color: T.navy, objectName: '!!hub-name' });
  ST.forEach((st, i) => {
    const x = st.cx - FW / 2, y = st.cy - FH / 2;
    const isFocus = i === focus;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: X(x), y: Y(y), w: FW * k, h: FH * k, rectRadius: 0.16 * (isFocus ? 1 : k),
      fill: { color: isFocus ? T.page : 'FFFFFF' }, line: { color: isFocus ? T.page : T[st.tone], width: isFocus ? 0 : 2 },
      shadow: isFocus ? undefined : { type: 'outer', color: T.ink, opacity: 0.12, blur: 6, offset: 2, angle: 90 }, objectName: `!!frame-${i}` });
    if (isFocus) return; // the focused station's tile and title are placed by the section slide
    const ts = 0.62 * k;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: X(x + FW - 0.18 - 0.62), y: Y(y + 0.16), w: ts, h: ts, rectRadius: 0.14 * k, fill: { color: T[st.tone] }, line: { color: T[st.tone], width: 0 }, objectName: `!!tile-${i}` });
    s.addImage({ path: img('w-' + st.icon + '.png'), x: X(x + FW - 0.18 - 0.62 + 0.12), y: Y(y + 0.28), w: 0.38 * k, h: 0.38 * k, objectName: `!!icon-${i}`, altText: '' });
    text(s, `${i + 1}`, { x: X(x + 0.15), y: Y(y + 0.14), w: 0.5 * k, h: 0.4 * k, fontSize: 16 * k, bold: true, color: T[st.tone], align: 'left', objectName: `!!num-${i}` });
    text(s, st.title, { x: X(x + 0.12), y: Y(y + 0.82), w: (FW - 0.24) * k, h: 0.34 * k, fontSize: 15 * k, bold: true, objectName: `!!title-${i}`, fit: 'shrink' });
    if (k === 1) text(s, st.sub, { x: X(x + 0.12), y: Y(y + 1.13), w: (FW - 0.24) * k, h: 0.26 * k, fontSize: 11, color: T.muted, objectName: `!!sub-${i}` });
    if (visited.includes(i)) {
      s.addShape(pres.shapes.OVAL, { x: X(x - 0.12), y: Y(y - 0.12), w: 0.36 * k, h: 0.36 * k, fill: { color: T.green }, line: { color: 'FFFFFF', width: 1.5 }, objectName: `!!done-${i}` });
      text(s, '✓', { x: X(x - 0.12), y: Y(y - 0.13), w: 0.36 * k, h: 0.36 * k, fontSize: 13 * k, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle', objectName: `!!done-mark-${i}` });
    }
    if (links && st.slide) text(s, ' ', { x: X(x), y: Y(y), w: FW * k, h: FH * k, hyperlink: { slide: st.slide, tooltip: st.title } });
  });
}

// A section slide: the map zoomed so that station i fills the slide, then the station's own content.
function section(i, heading, speech, body) {
  const st = ST[i];
  const s = newSlide();
  s.background = { color: 'C9D2E6' };
  drawMap(s, { k: W / FW, fx: st.cx, fy: st.cy, focus: i });
  // The station's tile, number and title become the header (same names: Morph moves them).
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: W - 0.6 - 0.8, y: 0.45, w: 0.8, h: 0.8, rectRadius: 0.18, fill: { color: T[st.tone] }, line: { color: T[st.tone], width: 0 }, objectName: `!!tile-${i}` });
  s.addImage({ path: img('w-' + st.icon + '.png'), x: W - 0.6 - 0.8 + 0.16, y: 0.61, w: 0.48, h: 0.48, objectName: `!!icon-${i}`, altText: '' });
  text(s, st.title, { x: 2.2, y: 0.42, w: W - 0.6 - 0.8 - 0.25 - 2.2, h: 0.55, fontSize: 30, bold: true, objectName: `!!title-${i}` });
  text(s, heading, { x: 2.2, y: 0.98, w: W - 0.6 - 0.8 - 0.25 - 2.2, h: 0.4, fontSize: 15, color: T.muted });
  text(s, `${i + 1} / ${ST.length}`, { x: 0.6, y: 0.5, w: 1.2, h: 0.4, fontSize: 16, bold: true, color: T[st.tone], align: 'left', objectName: `!!num-${i}` });
  // Back to the map (bottom left), and the footer.
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: H - 0.62, w: 1.75, h: 0.38, rectRadius: 0.19, fill: { color: 'FFFFFF' }, line: { color: T.line, width: 1 } });
  text(s, '◀ الخريطة', { x: 0.6, y: H - 0.62, w: 1.75, h: 0.38, fontSize: 12, bold: true, color: T.navy, align: 'center', valign: 'middle', hyperlink: { slide: 2, tooltip: 'العودة إلى الخريطة' } });
  text(s, 'ء-حماية · الديوان الوطني للحماية المدنية', { x: W - 6.6, y: H - 0.6, w: 6, h: 0.34, fontSize: 10, color: T.muted, valign: 'middle' });
  // The station's content enters with a fade after the Morph (objects named "anim …", timed in the Animations tab).
  const from = s._slideObjects.length;
  body(s);
  animate(s, from);
  notes(s, speech);
  return s;
}
function card(s, x, y, w, h, o = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.14, fill: { color: o.fill || 'FFFFFF' }, line: { color: o.line || T.line, width: 0.75 },
    shadow: o.flat ? undefined : { type: 'outer', color: T.ink, opacity: 0.08, blur: 6, offset: 2, angle: 90 } });
}
function points(s, list, x, y, w, h, fs = 17) {
  text(s, list.map((p, k) => ({ text: p, options: { bullet: { indent: 18 }, breakLine: k < list.length - 1 } })), { x, y, w, h, fontSize: fs, paraSpaceAfter: 10 });
}
function stat(s, x, y, w, n, label, tone, o = {}) {
  card(s, x, y, w, 1.45, { fill: TINT[tone] || 'FFFFFF', line: TINT[tone] || T.line, flat: true });
  text(s, n, { x: x + 0.2, y: y + 0.15, w: w - 0.4, h: 0.7, fontSize: o.fs || 34, bold: true, color: T[tone] });
  text(s, label, { x: x + 0.2, y: y + 0.85, w: w - 0.4, h: 0.5, fontSize: 13, color: T.ink });
}
function sim(s, x, y) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.75, h: 0.34, rectRadius: 0.17, fill: { color: T.amber }, line: { color: T.amber, width: 0 } });
  text(s, 'بيانات تجريبية [SIM]', { x, y, w: 1.75, h: 0.34, fontSize: 10, bold: true, align: 'center', valign: 'middle' });
}
function shot(s, name, x, y, maxW, maxH, alt) {
  const { w, h } = size(img(name)); const k = Math.min(maxW / w, maxH / h);
  const ww = w * k, hh = h * k, xx = x + (maxW - ww) / 2, yy = y + (maxH - hh) / 2;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: xx - 0.06, y: yy - 0.06, w: ww + 0.12, h: hh + 0.12, rectRadius: 0.12, fill: { color: 'FFFFFF' }, line: { color: T.line, width: 0.75 },
    shadow: { type: 'outer', color: T.ink, opacity: 0.12, blur: 8, offset: 2, angle: 90 } });
  s.addImage({ path: img(name), x: xx, y: yy, w: ww, h: hh, altText: alt });
}

function build() {
  // Slide numbers: 1 cover, 2 map, then each station's slides and a map after each station but the last.
  const plan = [[0, 1], [1, 2], [2, 2], [3, 2], [4, 1], [5, 2], [6, 1]];
  let n = 3; plan.forEach(([i, count]) => { ST[i].slide = n; n += count + 1; });

  // 1. Cover: the map far away, the title.
  {
    const s = newSlide(); s.background = { color: T.deep };
    drawMap(s, { k: 0.35, fx: CX, fy: CY - 4.5 });
    const from = s._slideObjects.length;
    text(s, 'ء-حماية', { x: 0.8, y: 1.0, w: W - 1.6, h: 1.2, fontSize: 64, bold: true, color: 'FFFFFF', align: 'center' });
    text(s, 'منظومة ذكية للتبليغ والمشاركة المجتمعية والمؤسساتية في الوقاية والسلامة وإدارة المخاطر', { x: 1.5, y: 2.25, w: W - 3, h: 0.9, fontSize: 21, color: 'E8ECF5', align: 'center' });
    text(s, 'من التبليغ إلى أخذ القرار', { x: 1.5, y: 3.2, w: W - 3, h: 0.6, fontSize: 26, bold: true, color: 'FFA733', align: 'center' });
    text(s, 'العرض أمام اللجنة · الديوان الوطني للحماية المدنية · 2026', { x: 1.5, y: 6.6, w: W - 3, h: 0.4, fontSize: 14, color: 'A6AFC4', align: 'center' });
    animate(s, from);
    notes(s, 'أصحاب المعالي والسعادة، نقدّم ء-حماية في سبع محطات على خريطة واحدة. كل محطة تُفتح بالتكبير ثم نعود إلى الخريطة. يمكن الضغط على أي محطة للانتقال إليها مباشرة حسب أسئلة اللجنة.');
  }
  const mapSlide = visited => {
    const s = newSlide(); s.background = { color: 'FFFFFF' };
    drawMap(s, { visited, links: true });
    const from = s._slideObjects.length;
    text(s, 'سبع محطات: من التبليغ إلى أخذ القرار', { x: 0.6, y: 0.3, w: W - 1.2, h: 0.5, fontSize: 22, bold: true, color: T.navy });
    text(s, 'اضغط على محطة للانتقال إليها', { x: 0.6, y: H - 0.55, w: W - 1.2, h: 0.35, fontSize: 11, color: T.muted });
    animate(s, from);
    notes(s, visited.length ? `عدنا إلى الخريطة: ${visited.length} من ${ST.length} محطات. المحطة التالية: ${ST[visited.length] ? ST[visited.length].title : ''}.`
      : 'هذه خريطة العرض: المواطن والمؤسسة يبلّغان، القاعة والفريق يتدخلان، القائد واللجان يقررون، التحليل يبني المخطط، والأمن يحمي الكل. نبدأ بالوضع الحالي.');
  };
  mapSlide([]);

  // 1. Today.
  section(0, 'كيف يجري العمل اليوم، وما الذي ينقصه', 'اليوم يصل البلاغ بالهاتف أو اللاسلكي، ويُسجَّل يدويا، ولا يرى القائد واللجان صورة موحّدة. في 2022 وحدها سجل الديوان 143.308 تدخلا في أرشيف SNACR، دون مؤشرات زمن الوصول.', s => {
    stat(s, 8.9, 1.75, 3.83, '143.308', 'تدخلا في 2022 (أرشيف SNACR، حقيقي)', 'navy');
    stat(s, 4.85, 1.75, 3.83, '24 / 279', 'ولاية / معتمدية في المرجع الإداري', 'teal');
    stat(s, 0.8, 1.75, 3.83, '3 قنوات', 'الهاتف واللاسلكي والحضور: دون صورة ولا موقع', 'red');
    points(s, ['البلاغ بالهاتف أو اللاسلكي: لا صورة ولا موقع دقيق ولا رقم تتبع للمبلّغ',
      'التسجيل يدوي في القاعة، والأرشيف يُدخل لاحقا دون عنوان ولا وصف',
      'لا خريطة مشتركة بين القاعة والفريق والقائد واللجان',
      'الكارثة دون محاور ولا تقارير وضع موحدة ولا حوصلة نهائية'], 0.8, 3.55, W - 1.6, 3.0, 19);
  });
  mapSlide([0]);

  // 2. Citizen and institution.
  section(1, 'تطبيق وبوابة: البلاغ يصل بموقعه وصورته', 'المواطن يضغط زر النجدة: ثلاث لمسات على الأكثر، يعمل دون إنترنت ويرسل بالرسائل القصيرة عند الحاجة. المؤسسة تملك بوابة لملف السلامة، وكاميرتها ترسل إنذارا أوليا لصاحبها أولا: إن لم ينفه خلال 90 ثانية يُرفع آليا إلى القاعة.', s => {
    shot(s, 'shot-phone.png', 0.8, 1.6, 2.6, 5.2, 'الشاشة الرئيسية لتطبيق المواطن');
    points(s, ['زر النجدة في ثلاث لمسات، وشريط 198 في كل شاشة', 'بلاغ بصورة وفيديو وموقع، ورقم تتبع فوري',
      'يعمل دون اتصال، ورسالة قصيرة جاهزة إلى 198', 'العربية والفرنسية والإنجليزية، ونفاذ لذوي الهمم (WCAG 2.2 AA)'], 4.0, 1.7, 8.5, 3.0, 18);
    card(s, 4.0, 4.85, 8.5, 1.75, { fill: TINT.red, line: TINT.red, flat: true });
    text(s, 'الإنذار الأولي للمؤسسة', { x: 4.25, y: 4.98, w: 8.0, h: 0.4, fontSize: 17, bold: true, color: T.red });
    text(s, 'كاميرا أو حساس يرصد حريقا (3 من 5 إطارات) ← صاحب المؤسسة يُشعر أولا ← إن لم ينفه خلال 90 ثانية (إعداد قابل للتغيير) يُرفع آليا بلاغا إلى القاعة',
      { x: 4.25, y: 5.42, w: 8.0, h: 1.1, fontSize: 15 });
  });
  section(1, 'بوابة المؤسسات والوقاية', 'البوابة تحفظ ملف السلامة والمعدات وصيانتها والتمارين، وزيارة الوقاية تتم على هاتف المفقّد بالصور والتوقيع، ثم الشهادة موقّعة رقميا برمز QR.', s => {
    const items = [['ملف السلامة', 'الوثائق، فريق السلامة، المواد الخطرة', 'apartment', 'teal'], ['زيارة الوقاية', 'معاينة في عين المكان بالصور والتوقيع، دون اتصال', 'fact_check', 'navy'],
      ['الشهادة', 'موقّعة Ed25519 مع رمز QR يتحقق منه أي شخص', 'verified', 'green'], ['التنبيهات', 'رسائل للمؤسسات مع تأكيد القراءة', 'campaign', 'orange']];
    items.forEach(([t, d, ic, tone], k) => {
      const col = k % 2, row = Math.floor(k / 2), cw = 5.75, x = W - 0.8 - cw - col * (cw + 0.3), y = 1.75 + row * 2.45;
      card(s, x, y, cw, 2.15);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + cw - 1.1, y: y + 0.3, w: 0.8, h: 0.8, rectRadius: 0.18, fill: { color: T[tone] }, line: { color: T[tone], width: 0 } });
      s.addImage({ path: img('w-' + ic + '.png'), x: x + cw - 0.94, y: y + 0.46, w: 0.48, h: 0.48, altText: '' });
      text(s, t, { x: x + 0.3, y: y + 0.35, w: cw - 1.6, h: 0.5, fontSize: 20, bold: true });
      text(s, d, { x: x + 0.3, y: y + 0.95, w: cw - 1.6, h: 1.0, fontSize: 15, color: T.muted });
    });
  });
  mapSlide([0, 1]);

  // 3. Room and field.
  section(2, 'القاعة تؤكد وتستنفر، والفريق يتابع على هاتفه', 'البلاغ يظهر في اللوحة في أقل من نصف ثانية، مع تصنيف وأولوية واقتراح تجميع. البلاغ الهاتفي أو اللاسلكي يدخله العون يدويا مع مصدره فيلتحق بالمسار نفسه. الفريق يتلقى المهمة على تطبيق الأعوان ويرسل تقرير الوضع والحصيلة بالأزرار.', s => {
    shot(s, 'shot-dash.png', 4.3, 1.6, 8.3, 5.2, 'لوحة القيادة بالعربية');
    stat(s, 0.8, 1.7, 3.2, '0,45 ث', 'من الإرسال إلى الظهور في اللوحة', 'navy');
    stat(s, 0.8, 3.35, 3.2, '16 / ث', 'بلاغ SOS في الثانية، p95 = 328 ms', 'green');
    stat(s, 0.8, 5.0, 3.2, '3 قنوات', 'التطبيق، 198 أو اللاسلكي، الحضور', 'orange');
  });
  section(2, 'المسار بترميز BPMN 2.0', 'هذا مسار العمل الكامل كما في البطاقات: من الحادث إلى الغلق بحوصلة، والترقية إلى كارثة عند الحاجة. الملف قابل للتعديل في أي أداة BPMN.', s => {
    if (fs.existsSync(img('bpmn.png'))) shot(s, 'bpmn.png', 0.7, 1.6, W - 1.4, 5.1, 'مسار من البلاغ إلى القرار بترميز BPMN');
  });
  mapSlide([0, 1, 2]);

  // 4. Decision and disasters.
  section(3, 'توصية، قرار موقّع، وكارثة لها حوصلة', 'القائد يرى توصية المساعد مع أسبابها ويقرر؛ القرار موقّع ويصل إلى القاعة المنفذة. الحادث الكبير يُرقّى إلى كارثة لها محاور ومطالب وتقارير وضع، وتراها اللجنة الجهوية برئاسة السيد الوالي واللجنة الوطنية برئاسة السيد وزير الداخلية على خريطة متعددة الولايات.', s => {
    shot(s, 'shot-disasters.png', 0.7, 1.6, W - 1.4, 2.6, 'حوصلة الكوارث');
    points(s, ['التوصية بأسبابها، والقرار موقّع إلكترونيا (Ed25519) مع أجل ومتابعة التنفيذ',
      'قرار اللجنة الوطنية يتقدم على قرار اللجنة الجهوية عند التعارض، ويُشعر الطرفان',
      'الكارثة: محاور، مطالب، إجلاء وإيواء، تقارير وضع دورية، حوصلة نهائية وأرشفة'], 0.8, 4.45, W - 1.6, 2.2, 17);
    sim(s, 0.8, 4.15);
  });
  section(3, 'خريطة الكارثة للقائد واللجان', 'الخريطة تعرض أماكن الكارثة فقط: التدخلات ومراكز الإيواء ومناطق الإجلاء، مع اختيار عدة ولايات وطبقات.', s => {
    shot(s, 'shot-dmap.png', 4.6, 1.6, 8.0, 5.1, 'خريطة الكارثة متعددة الولايات');
    points(s, ['اختيار عدة ولايات وعدة طبقات', 'الجارية والمغلقة في تبويبين', 'نفس العرض للقاعة والقائد واللجنتين، كل في حدود ولايته'], 0.8, 1.9, 3.6, 4.2, 17);
    sim(s, 0.8, 6.3);
  });
  mapSlide([0, 1, 2, 3]);

  // 5. SNACR.
  section(4, 'ثلاث سنوات من التدخلات تصير مخططا', 'أرشيف 2022 الحقيقي نُظّف وربط بكل معتمدية؛ السنوات 2023 إلى 2025 مولّدة [SIM] على توزيعاته حتى يسلّم الديوان ملفاتها. المؤشرات: زمن الوصول بالوسيط والمئين 90، ونسبة التدخلات في الأجل المستهدف، والمصفوفة تحدد المعتمديات ذات الأولوية، واللجنة تعتمد المخطط.', s => {
    shot(s, 'shot-snacr.png', 4.6, 1.6, 8.0, 5.1, 'مصفوفة المخاطر SNACR');
    stat(s, 0.8, 1.7, 3.5, '88,4 %', 'من أسماء 2022 تُعرف كما هي', 'purple');
    stat(s, 0.8, 3.35, 3.5, '90 %', 'هدف الوصول في الأجل (إعداد)', 'green');
    stat(s, 0.8, 5.0, 3.5, '10 / 15 / 25 د', 'حريق: حضري / شبه حضري / ريفي', 'red', { fs: 26 });
    sim(s, 0.8, 6.6);
  });
  mapSlide([0, 1, 2, 3, 4]);

  // 6. Security.
  section(5, 'مقيس قبل وبعد التحصين', 'قسنا الخادم قبل سكريبت التحصين وبعده: مؤشر Lynis من 57 إلى 82 في حاوية دون systemd، وهو حد أدنى. المنفذان الوحيدان 80 و443، وTLS 1.2 و1.3 فقط دون أي ثغرة معروفة. الإنتاج يرفض الإقلاع بأي سر ضعيف.', s => {
    stat(s, 8.9, 1.75, 3.83, '57 ← 82', 'مؤشر Lynis قبل وبعد التحصين', 'green');
    stat(s, 4.85, 1.75, 3.83, '443', 'المنفذ الوحيد للمستعملين (و80 للتحويل)', 'navy');
    stat(s, 0.8, 1.75, 3.83, '0', 'ثغرة TLS معروفة (testssl.sh)', 'teal');
    points(s, ['تشفير الحقول الحساسة AES-256، والملف الطبي مشفّر على الهاتف ولا يفتحه الخادم',
      'عزل كل ولاية في قاعدة البيانات (133 جدولا)، وتحقق بخطوتين لكل عون',
      'سجل تدقيق غير قابل للتعديل، وختم الأدلة بشجرة Merkle', 'سكريبت تحصين قابل لإعادة التشغيل، وقائمة تحقق من 10 بنود قبل التشغيل'], 0.8, 3.55, W - 1.6, 3.0, 18);
  });
  section(5, 'السيادة والقانون', 'كل النماذج مفتوحة الرخصة وتعمل على خوادم الديوان. لا معطى شخصي يخرج إلى خدمة أجنبية. التسجيل الصوتي معطّل حتى ترخيص الهيئة الوطنية لحماية المعطيات الشخصية.', s => {
    const items = [['استضافة وطنية', 'داخل التراب التونسي مع موقع ثان مشفّر', 'public', 'navy'], ['ذكاء اصطناعي محلي', 'Whisper و Qwen و YOLOX برخص مفتوحة، دون إنترنت', 'smart_toy', 'purple'],
      ['القانون 2004-63', 'مدد حفظ آلية، موافقات بإصدارات، حقوق الاطلاع والحذف', 'gavel', 'green'], ['التدقيق الخارجي', 'اختبار اختراق وتدقيق الوكالة الوطنية للأمن السيبراني قبل الإطلاق', 'policy', 'orange']];
    items.forEach(([t, d, ic, tone], k) => {
      const col = k % 2, row = Math.floor(k / 2), cw = 5.75, x = W - 0.8 - cw - col * (cw + 0.3), y = 1.75 + row * 2.45;
      card(s, x, y, cw, 2.15);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + cw - 1.1, y: y + 0.3, w: 0.8, h: 0.8, rectRadius: 0.18, fill: { color: T[tone] }, line: { color: T[tone], width: 0 } });
      s.addImage({ path: img('w-' + ic + '.png'), x: x + cw - 0.94, y: y + 0.46, w: 0.48, h: 0.48, altText: '' });
      text(s, t, { x: x + 0.3, y: y + 0.35, w: cw - 1.6, h: 0.5, fontSize: 20, bold: true });
      text(s, d, { x: x + 0.3, y: y + 0.95, w: cw - 1.6, h: 1.0, fontSize: 15, color: T.muted });
    });
  });
  mapSlide([0, 1, 2, 3, 4, 5]);

  // 7. Road to production.
  section(6, 'من النموذج التجريبي إلى منظومة تشغيل', 'النموذج كامل وجاهز للعرض دون إنترنت. بعد التزكية: ثمانية خوادم بالمناطق، موصل قراءة من Oracle، والحسابات الرسمية. نطلب من الديوان أربعة أشياء: التزكية، الحسابات الرسمية، ملفات SNACR من 2023 إلى 2025، واختيار ولاية للتجربة.', s => {
    const steps = [['منجز', 'النموذج التجريبي', 'green'], ['اليوم', 'التزكية', 'navy'], ['المرحلة 5', 'الإنتاج: 8 خوادم، Oracle، الحسابات', 'orange'], ['3 أشهر [SIM]', 'تجربة في ولاية واحدة', 'purple'], ['بعدها', 'التعميم على 24 ولاية', 'teal']];
    const sw = (W - 1.6) / steps.length;
    steps.forEach(([when, what, tone], k) => {
      const x = W - 0.8 - sw * (k + 1) + 0.1;
      card(s, x, 1.75, sw - 0.2, 1.9, { fill: TINT[tone], line: TINT[tone], flat: true });
      text(s, when, { x: x + 0.15, y: 1.9, w: sw - 0.5, h: 0.4, fontSize: 14, bold: true, color: T[tone] });
      text(s, what, { x: x + 0.15, y: 2.35, w: sw - 0.5, h: 1.2, fontSize: 16, bold: true });
    });
    text(s, 'ما ننتظره من الديوان', { x: 0.8, y: 4.0, w: W - 1.6, h: 0.45, fontSize: 20, bold: true, color: T.navy });
    points(s, ['تزكية المنظومة وتحديد ولاية التجربة', 'الحسابات الرسمية: Firebase، بوابة SMS، خط 198 (SIP)',
      'ملفات SNACR من 2023 إلى 2025 لتعويض المعطيات التجريبية', 'اختيار مركز البيانات داخل التراب التونسي'], 0.8, 4.5, W - 1.6, 2.2, 18);
  });

  // Closing: back to the whole map, every station done.
  {
    const s = newSlide(); s.background = { color: 'FFFFFF' };
    drawMap(s, { visited: [0, 1, 2, 3, 4, 5, 6], links: true });
    const from = s._slideObjects.length;
    text(s, 'شكرا. أسئلتكم؟', { x: 0.6, y: 0.3, w: W - 1.2, h: 0.6, fontSize: 26, bold: true, color: T.navy });
    text(s, 'الوثائق: كراس الشروط، البطاقات و BPMN، الملف التقني والأمني، قاموس البيانات، تقرير التحصين', { x: 0.6, y: H - 0.6, w: W - 1.2, h: 0.4, fontSize: 12, color: T.muted });
    animate(s, from);
    notes(s, 'نعود إلى الخريطة كاملة. أي محطة تحتاج تفصيلا يمكن فتحها بالضغط عليها.');
  }
}

(async () => {
  await prepare();
  build();
  await pres.writeFile({ fileName: OUT });
  if (slideCount !== MIN.length) throw new Error(`MIN has ${MIN.length} entries for ${slideCount} slides`);
  // The cover fades in; every other slide morphs from the previous one.
  const r = await applyTransitions(OUT, MIN.map((sec, k) => ({ effect: k ? 'morph' : 'fade', durMs: k ? 1400 : 800, afterSec: sec })));
  console.log(`transitions on ${r.slides} slides, ${mmss(r.total)} in all`);
  console.log('written', OUT);
})();
