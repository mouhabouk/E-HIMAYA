// e-Himaya presentation for senior officials (Arabic, right to left). Run from this folder after prep.js:
//   node build.js e-Himaya_Presentation.pptx
// Updated at the end of every phase with the other deliverables (docs/phase-end.md).
const pptxgen = require('pptxgenjs');
const { applyTheme } = require(process.env.PPTX_SKILL + '/scripts/apply_theme.js');
const fs = require('fs');

const THEME = {
  name: 'e-Himaya',
  headFontFace: 'Arial',
  bodyFontFace: 'Arial',
  colors: {
    dk1: '182038', lt1: 'FFFFFF', dk2: '0E1426', lt2: 'F3F5FA',
    accent1: '1F3FA0', accent2: 'D7141A', accent3: 'F08C00', accent4: '188038', accent5: '7838A0', accent6: '00806A',
    hlink: '1F3FA0', folHlink: '5E2A80',
  },
};
// Hex values for options that take hex only (shadows, chart grid lines).
const HEX = { navy: '1F3FA0', ink: '182038', muted: '5B6478', line: 'E3E7EF', page: 'F3F5FA', amber: 'F5B400', teal: '00806A', pink: 'C2185B', sky: '1976D2', slate: '5B6478' };
// Tones of the design system: fill for icon tiles.
const TONE = { navy: '1F3FA0', red: 'D7141A', orange: 'C25E00', green: '188038', purple: '7838A0', teal: '00806A', amber: 'F5B400', pink: 'C2185B', sky: '1976D2', slate: '5B6478' };

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13.333 x 7.5 in
pres.rtlMode = true;
pres.title = 'ء-حماية: عرض تقديمي';
pres.author = 'e-Himaya';
pres.subject = 'المنظومة الوطنية الذكية للتبليغ والوقاية وإدارة المخاطر';
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, M = 0.6;
const AR = { rtlMode: true, lang: 'ar-TN' };
const img = n => 'img/' + n;
const shadow = () => ({ type: 'outer', color: HEX.ink, opacity: 0.1, blur: 8, offset: 2, angle: 90 });

// ---------- Layouts ----------
const FOOT = 'ء-حماية · الديوان الوطني للحماية المدنية';
pres.defineSlideMaster({
  title: 'COVER',
  background: { color: C.text2 },
  objects: [],
});
pres.defineSlideMaster({
  title: 'CONTENT',
  background: { color: C.background2 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { image: { x: W - M - 0.42, y: 7.5 - 0.52, w: 0.34, h: 0.34, path: img('logo.png') } },
    { text: { text: FOOT, options: { x: W - M - 6.5, y: 7.5 - 0.53, w: 6.0, h: 0.36, fontSize: 10, color: HEX.muted, align: 'right', valign: 'middle', margin: 0, ...AR } } },
    { placeholder: { options: { name: 'title', type: 'title', x: M, y: 0.4, w: W - 2 * M, h: 0.85, fontSize: 32, bold: true, color: C.text1, align: 'right', valign: 'middle', margin: 0, ...AR }, text: '' } },
    { placeholder: { options: { name: 'kicker', type: 'body', x: M, y: 1.22, w: W - 2 * M, h: 0.45, fontSize: 15, color: HEX.muted, align: 'right', valign: 'top', margin: 0, ...AR }, text: '' } },
  ],
  slideNumber: { x: M, y: 7.5 - 0.53, w: 0.6, h: 0.36, fontSize: 10, color: HEX.muted, align: 'left', valign: 'middle' },
});
pres.defineSlideMaster({
  title: 'DARK',
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: M, y: 0.55, w: W - 2 * M, h: 0.9, fontSize: 34, bold: true, color: C.background1, align: 'right', valign: 'middle', margin: 0, ...AR }, text: '' } },
  ],
  slideNumber: { x: M, y: 7.5 - 0.53, w: 0.6, h: 0.36, fontSize: 10, color: 'A6AFC4', align: 'left', valign: 'middle' },
});

// ---------- Helpers ----------
function text(s, t, o) {
  s.addText(t, { isTextBox: true, margin: 0, align: 'right', valign: 'top', color: C.text1, fontSize: 15, ...AR, ...o });
}
function card(s, x, y, w, h, o = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.14, fill: { color: o.fill || C.background1 },
    line: { color: o.line || HEX.line, width: 0.75 }, shadow: o.flat ? undefined : shadow(), objectName: o.name });
}
function tile(s, x, y, size, tone, icon, name) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: size, h: size, rectRadius: size * 0.22, fill: { color: TONE[tone] }, line: { color: TONE[tone], width: 0 }, objectName: name });
  const p = size * 0.2;
  s.addImage({ path: img('w-' + icon + '.png'), x: x + p, y: y + p, w: size - 2 * p, h: size - 2 * p, altText: '' });
}
function simBadge(s, x, y) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.55, h: 0.36, rectRadius: 0.18, fill: { color: HEX.amber }, line: { color: HEX.amber, width: 0 } });
  text(s, 'بيانات تجريبية [SIM]', { x, y, w: 1.55, h: 0.36, fontSize: 10, bold: true, align: 'center', valign: 'middle', color: C.text1 });
}
function content(section, title, kicker) {
  const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: section });
  s.addText(title, { placeholder: 'title', ...AR });
  if (kicker) s.addText(kicker, { placeholder: 'kicker', ...AR });
  return s;
}

// ---------- 1. Cover ----------
pres.addSection({ title: 'الافتتاح' });
{
  const s = pres.addSlide({ masterName: 'COVER', sectionTitle: 'الافتتاح' });
  s.addImage({ path: img('logo-disc.png'), x: W - M - 2.3, y: 1.35, w: 2.3, h: 2.3, altText: 'شعار الديوان الوطني للحماية المدنية' });
  text(s, 'ء-حماية', { x: M, y: 1.35, w: W - 2 * M - 2.75, h: 1.2, fontSize: 60, bold: true, color: C.background1, valign: 'middle' });
  text(s, 'المنظومة الوطنية الذكية للتبليغ والمشاركة المجتمعية والمؤسساتية في الوقاية والسلامة وإدارة المخاطر',
    { x: M, y: 2.6, w: W - 2 * M - 2.75, h: 1.0, fontSize: 20, color: 'E8ECF5' });
  text(s, 'من التبليغ إلى أخذ القرار', { x: M, y: 4.25, w: W - 2 * M, h: 0.6, fontSize: 26, bold: true, color: 'FFA733' });
  text(s, 'الديوان الوطني للحماية المدنية · الجمهورية التونسية', { x: M, y: 6.1, w: W - 2 * M, h: 0.4, fontSize: 14, color: 'A6AFC4' });
  text(s, 'عرض تقديمي · أكتوبر 2026', { x: M, y: 6.5, w: W - 2 * M, h: 0.4, fontSize: 14, color: 'A6AFC4' });
  s.addNotes('أصحاب المعالي والسعادة، نقدّم لكم منظومة ء-حماية: منصة وطنية واحدة تربط المواطن والمؤسسة وقاعات العمليات، هدفها أن يتحول كل بلاغ إلى قرار سريع ومدروس.');
}

// ---------- 2. In one minute ----------
pres.addSection({ title: 'الرؤية' });
{
  const s = content('الرؤية', 'ء-حماية في دقيقة', 'منصة وطنية واحدة تربط المواطن والمؤسسة وقاعات العمليات، وتحوّل كل بلاغ إلى قرار سريع ومدروس');
  const stats = [
    ['24', 'ولاية', 'مغطاة بالمرجع الإداري، مع 279 معتمدية وقاعات عمليات جهوية', 'map', 'navy'],
    ['3', 'واجهات', 'تطبيق المواطن، بوابة المؤسسات، لوحات القيادة المركزية والجهوية', 'dashboard', 'red'],
    ['3', 'لغات', 'العربية والفرنسية والإنجليزية، مع دعم كامل للكتابة من اليمين', 'translate', 'green'],
    ['100%', 'سيادة', 'نماذج مفتوحة المصدر على خوادم وطنية، دون إرسال معطيات شخصية إلى الخارج', 'shield', 'purple'],
  ];
  const cw = 2.83, gap = 0.3, y = 2.1, h = 4.15;
  stats.forEach(([n, u, d, ic, tone], i) => {
    const x = W - M - cw - i * (cw + gap);
    card(s, x, y, cw, h, { name: 'stat-' + i });
    tile(s, x + cw - 0.3 - 0.75, y + 0.35, 0.75, tone, ic);
    text(s, [{ text: n, options: { fontSize: 54, bold: true, color: TONE[tone] } }], { x: x + 0.3, y: y + 1.3, w: cw - 0.6, h: 1.0, valign: 'middle' });
    text(s, u, { x: x + 0.3, y: y + 2.3, w: cw - 0.6, h: 0.45, fontSize: 20, bold: true });
    text(s, d, { x: x + 0.3, y: y + 2.85, w: cw - 0.6, h: 1.1, fontSize: 14, color: HEX.muted });
  });
  s.addNotes('أربعة أرقام تلخص المنظومة: تغطية وطنية لكل الولايات، ثلاث واجهات لكل المتداخلين، ثلاث لغات، وسيادة كاملة على المعطيات والذكاء الاصطناعي.');
}

// ---------- 3. The challenge ----------
{
  const s = content('الرؤية', 'ما تعالجه المنظومة', 'كل دقيقة في حالة الطوارئ تُحتسب، والمعلومة الموحّدة هي أساس القرار');
  const items = [
    ['بلاغات من قنوات متفرقة', 'مكالمات ورسائل وصور تصل منفصلة، ويصعب جمعها في صورة واحدة للحادثة', 'campaign', 'red'],
    ['الموقع والأولوية', 'تحديد مكان الحادث ودرجة خطورته يستهلك وقتاً ثميناً في الدقائق الأولى', 'location_on', 'orange'],
    ['صورة وطنية موحّدة', 'المؤشرات الجهوية والمركزية تحتاج مصدراً واحداً محيّناً في الزمن الحقيقي', 'insights', 'navy'],
    ['مشاركة المواطن والمؤسسة', 'الوقاية تبدأ قبل الحادث: ملفات السلامة، المتطوعون، التنبيهات والنصائح', 'groups', 'green'],
  ];
  const cw = (W - 2 * M - 0.3) / 2, ch = 2.05;
  items.forEach(([t, d, ic, tone], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = W - M - cw - col * (cw + 0.3), y = 2.0 + row * (ch + 0.3);
    card(s, x, y, cw, ch, { name: 'challenge-' + i });
    tile(s, x + cw - 0.35 - 0.85, y + 0.35, 0.85, tone, ic);
    text(s, t, { x: x + 0.35, y: y + 0.38, w: cw - 1.65, h: 0.5, fontSize: 20, bold: true });
    text(s, d, { x: x + 0.35, y: y + 0.95, w: cw - 1.65, h: 0.9, fontSize: 15, color: HEX.muted });
  });
  s.addNotes('المنظومة تعالج أربعة تحديات: تشتت قنوات التبليغ، والوقت الذي يضيع في تحديد الموقع والأولوية، وغياب صورة موحدة للمؤشرات، والحاجة إلى إشراك المواطن والمؤسسة في الوقاية.');
}

// ---------- 4. The value chain ----------
{
  const s = content('الرؤية', 'سلسلة واحدة: من التبليغ إلى أخذ القرار', 'كل وظيفة في المنظومة تخدم حلقة من هذه الحلقات الست');
  const steps = [
    ['التبليغ', 'تطبيق، رسالة قصيرة، مكالمة، بث مباشر', 'sos', 'red'],
    ['المعالجة', 'تكفّل القاعة الجهوية وتجميع البلاغات في حادثة', 'account_tree', 'orange'],
    ['التحليل', 'تصنيف وأولوية مفسّرة من 0 إلى 100', 'psychology', 'purple'],
    ['المؤشرات', 'لوحة حية حسب الولاية والصنف والحالة', 'analytics', 'navy'],
    ['التنبؤ', 'الطقس ونماذج انتشار الحرائق', 'thunderstorm', 'teal'],
    ['القرار', 'اللجنة الجهوية برئاسة الوالي، والمركزية برئاسة وزير الداخلية', 'gavel', 'green'],
  ];
  const n = steps.length, span = W - 2 * M, sw = span / n, d = 1.15, cy = 2.35;
  steps.forEach(([t, desc, ic, tone], i) => {
    const cx = W - M - sw * i - sw / 2;
    if (i < n - 1) s.addShape(pres.shapes.LINE, { x: cx - sw + d / 2 + 0.12, y: cy + d / 2, w: sw - d - 0.24, h: 0, line: { color: HEX.line, width: 2.5, beginArrowType: 'triangle' } });
    s.addShape(pres.shapes.OVAL, { x: cx - d / 2, y: cy, w: d, h: d, fill: { color: TONE[tone] }, line: { color: TONE[tone], width: 0 }, objectName: 'step-' + i });
    s.addImage({ path: img('w-' + ic + '.png'), x: cx - 0.3, y: cy + d / 2 - 0.3, w: 0.6, h: 0.6, altText: '' });
    text(s, String(i + 1), { x: cx - sw / 2, y: cy - 0.55, w: sw, h: 0.4, fontSize: 14, bold: true, color: TONE[tone], align: 'center' });
    text(s, t, { x: cx - sw / 2 + 0.08, y: cy + d + 0.25, w: sw - 0.16, h: 0.5, fontSize: 20, bold: true, align: 'center' });
    text(s, desc, { x: cx - sw / 2 + 0.1, y: cy + d + 0.8, w: sw - 0.2, h: 1.3, fontSize: 14, color: HEX.muted, align: 'center' });
  });
  card(s, M, 5.85, W - 2 * M, 0.85, { fill: 'E8EDFA', line: 'E8EDFA', flat: true, name: 'chain-note' });
  text(s, 'البلاغ يظهر في قاعة العمليات خلال أقل من نصف ثانية من إرساله (0.45 ثانية في الاختبار)',
    { x: M + 0.35, y: 5.85, w: W - 2 * M - 0.7, h: 0.85, fontSize: 16, bold: true, color: C.accent1, valign: 'middle' });
  s.addNotes('هذه هي الفكرة الجوهرية: سلسلة قيمة واحدة. المواطن يبلّغ، القاعة الجهوية تتكفل، الذكاء الاصطناعي يصنّف ويقترح الأولوية، المؤشرات تُحدَّث آلياً، نماذج الطقس والانتشار تتنبأ، واللجان الجهوية والمركزية تقرر.');
}

// ---------- 5. Three interfaces ----------
pres.addSection({ title: 'المنظومة' });
{
  const s = content('المنظومة', 'ثلاث واجهات لكل المتداخلين', 'لغة بصرية واحدة في كل الواجهات، وكلها تعمل بالعربية والفرنسية والإنجليزية');
  const cols = [
    ['تطبيق المواطن', 'أندرويد و iOS', ['المواطن، المجهول والمسجّل', 'المتطوعون والأطباء', 'فرق السلامة في المؤسسات'], 'smartphone', 'red'],
    ['بوابة المؤسسات', 'موقع واب', ['ملف السلامة والوثائق', 'فريق السلامة والمواد الخطرة', 'شهادة رقمية موقّعة برمز QR'], 'apartment', 'teal'],
    ['لوحات القيادة', 'مركزية وجهوية', ['قاعات العمليات والقادة', 'اللجان الجهوية والمركزية', 'تحقق بخطوتين إجباري لكل عون'], 'dashboard', 'navy'],
  ];
  const cw = (W - 2 * M - 0.6) / 3, y = 2.0, h = 4.55;
  cols.forEach(([t, sub, pts, ic, tone], i) => {
    const x = W - M - cw - i * (cw + 0.3);
    card(s, x, y, cw, h, { name: 'iface-' + i });
    tile(s, x + cw - 0.35 - 0.9, y + 0.35, 0.9, tone, ic);
    text(s, t, { x: x + 0.35, y: y + 1.45, w: cw - 0.7, h: 0.5, fontSize: 22, bold: true });
    text(s, sub, { x: x + 0.35, y: y + 1.95, w: cw - 0.7, h: 0.4, fontSize: 14, color: TONE[tone], bold: true });
    text(s, pts.map((p, k) => ({ text: p, options: { bullet: { indent: 18 }, breakLine: k < pts.length - 1 } })),
      { x: x + 0.35, y: y + 2.55, w: cw - 0.7, h: 1.7, fontSize: 15, paraSpaceAfter: 8 });
  });
  s.addNotes('ثلاث واجهات: تطبيق المواطن، وبوابة المؤسسات، ولوحات القيادة المركزية والجهوية. وتطبيق خاص بقادة الفرق الميدانية يُستعمل بالأزرار دون كتابة تقريباً، أجزاؤه الأربعة جاهزة (P4a إلى P4d): الثالث يحمل وحدة الوقاية للمفقِّد في الموقع، والرابع يجعله يعمل دون شبكة، وهو اليوم تطبيق مستقل «ء-حماية الأعوان».');
}

// ---------- 6. Citizen app ----------
{
  const s = content('المنظومة', 'تطبيق المواطن: النجدة في ثلاث لمسات', 'صُمّم للحظة الخطر: زر واحد كبير، ويعمل حتى دون إنترنت');
  const ph = { x: M + 0.5, y: 1.85, h: 5.1 }; ph.w = ph.h * 540 / 1170;
  card(s, ph.x - 0.12, ph.y - 0.12, ph.w + 0.24, ph.h + 0.24, { fill: HEX.ink, line: HEX.ink, name: 'phone-frame' });
  s.addImage({ path: img('phone.png'), x: ph.x, y: ph.y, w: ph.w, h: ph.h, altText: 'الشاشة الرئيسية لتطبيق ء-حماية: زر النجدة وأرقام الطوارئ' });
  const rows = [
    ['نجدة فورية', 'زر النجدة يرسل الموقع مباشرة، والمكالمة إلى 198 بلمسة واحدة', 'sos', 'red'],
    ['يعمل دون إنترنت', 'البلاغ يُحفظ مشفّراً ويُرسل آلياً عند عودة الشبكة؛ الأرقام والنصائح متاحة دائماً', 'wifi_off', 'slate'],
    ['تبليغ بالصورة والصوت والبث', 'صورة أو تسجيل صوتي أو بث مباشر من مكان الحادث', 'videocam', 'navy'],
    ['السلامة الشخصية', 'فحص السلامة، وتنبيه الأقارب، ومشاركة الموقع لمدة محددة', 'shield', 'green'],
    ['المتطوعون والأطباء', 'استنفار المتطوع الأقرب حسب اختصاصه وبموافقته', 'medical_services', 'purple'],
  ];
  const x0 = ph.x + ph.w + 0.7, w = W - M - x0, rh = 0.98;
  rows.forEach(([t, d, ic, tone], i) => {
    const y = 1.95 + i * rh;
    tile(s, W - M - 0.7, y, 0.7, tone, ic);
    text(s, t, { x: x0, y: y - 0.02, w: w - 0.95, h: 0.4, fontSize: 18, bold: true });
    text(s, d, { x: x0, y: y + 0.38, w: w - 0.95, h: 0.5, fontSize: 14, color: HEX.muted });
  });
  s.addNotes('التطبيق صُمّم للحظة الخطر. البلاغ المجهول ممكن بحصة محدودة لمنع الإساءة، أما الاستغاثة فلا تُمنع أبداً. التطبيق يعمل دون إنترنت ويزامن آلياً.');
}

// ---------- 7. Dashboards ----------
{
  const s = content('المنظومة', 'لوحات القيادة: صورة حية لكل ولاية وللوطن', 'كل عون يرى ما يخصه: الصلاحية تجمع الدور والنطاق، والاختصاص بموقع الحادث');
  const iw = 7.4, ih = iw * 370 / 1280, ix = M, iy = 2.1;
  card(s, ix - 0.1, iy - 0.1, iw + 0.2, ih + 0.2, { name: 'dash-frame' });
  s.addImage({ path: img('dash-kpi.png'), x: ix, y: iy, w: iw, h: ih, altText: 'لوحة المؤشرات الرئيسية في لوحة القيادة المركزية' });
  simBadge(s, ix + 0.15, iy + ih - 0.5);
  const nh = iw * 230 / 1280, ny = iy + ih + 0.35;
  card(s, ix - 0.1, ny - 0.1, iw + 0.2, nh + 0.2, { name: 'nav-frame' });
  s.addImage({ path: img('dash-nav.png'), x: ix, y: ny, w: iw, h: nh, altText: 'قائمة لوحة القيادة بمربعات أيقونات ملوّنة' });
  const rows = [
    ['خريطة حية وبث مباشر', 'البلاغات والحوادث والوحدات على خريطة واحدة', 'map', 'teal'],
    ['مركزي وجهوي', 'كل ولاية تعالج حوادثها، والمركز يرى الوطن كله', 'hub', 'navy'],
    ['مهلة التكفل والتصعيد', 'البلاغ غير المعالج في الأجل يُصعَّد آلياً إلى المركز', 'timer', 'orange'],
    ['المستويات التشغيلية', 'عادي، أزمة، كارثة، مع اللجان المحلية والمركزية', 'flag', 'red'],
  ];
  const x0 = ix + iw + 0.6, w = W - M - x0, rh = 1.12;
  rows.forEach(([t, d, ic, tone], i) => {
    const y = 2.1 + i * rh;
    tile(s, W - M - 0.7, y, 0.7, tone, ic);
    text(s, t, { x: x0, y: y - 0.02, w: w - 0.95, h: 0.4, fontSize: 18, bold: true });
    text(s, d, { x: x0, y: y + 0.38, w: w - 0.95, h: 0.6, fontSize: 14, color: HEX.muted });
  });
  s.addNotes('لوحة القيادة تعطي صورة حية. الأرقام في الصورة بيانات تجريبية. الاختصاص يُحدَّد بموقع الحادث، والبلاغ الذي لا يُعالج في الأجل يُصعَّد آلياً إلى القاعة المركزية.');
}

// ---------- 8. Sovereign AI ----------
pres.addSection({ title: 'الذكاء والثقة' });
{
  const s = content('الذكاء والثقة', 'ذكاء اصطناعي سيادي في خدمة القرار', 'كل النماذج مفتوحة المصدر وتعمل على خوادم وطنية، ولا يغادر أي معطى شخصي البلاد');
  const items = [
    ['تحويل الصوت إلى نص', 'البلاغ الصوتي يُقرأ فوراً في القاعة', 'mic', 'navy'],
    ['الترجمة والدارجة', 'من الفرنسية والإنجليزية إلى العربية، مع قاموس للدارجة', 'translate', 'teal'],
    ['التصنيف والأولوية', 'أولوية من 0 إلى 100 مع تفسير، ودرجة مصداقية', 'psychology', 'purple'],
    ['تجميع البلاغات', 'البلاغات المتشابهة تُقترح في حادثة واحدة', 'account_tree', 'orange'],
    ['كشف الحريق والدخان', 'في الصور والبث المباشر (إصدار أولي يُستكمل تدريبه)', 'local_fire_department', 'red'],
    ['الطقس وانتشار الحرائق', 'تنبيهات جوية مقترحة ونماذج انتشار على التضاريس', 'thunderstorm', 'sky'],
  ];
  const cw = (W - 2 * M - 0.6) / 3, ch = 2.1;
  items.forEach(([t, d, ic, tone], i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = W - M - cw - col * (cw + 0.3), y = 2.0 + row * (ch + 0.3);
    card(s, x, y, cw, ch, { name: 'ai-' + i });
    tile(s, x + cw - 0.3 - 0.75, y + 0.3, 0.75, tone, ic);
    text(s, t, { x: x + 0.3, y: y + 1.12, w: cw - 0.6, h: 0.42, fontSize: 18, bold: true });
    text(s, d, { x: x + 0.3, y: y + 1.52, w: cw - 0.6, h: 0.5, fontSize: 14, color: HEX.muted });
  });
  s.addNotes('الذكاء الاصطناعي يساعد العون ولا يعوّضه: يقترح ويفسّر، والقرار للإنسان. كل النماذج برخص مفتوحة وتعمل محلياً. كاشف الحرائق في إصداره الأول ويحتاج تدريباً إضافياً قبل التجربة الميدانية.');
}

// ---------- 9. Security and trust ----------
{
  const s = content('الذكاء والثقة', 'الأمن وحماية المعطيات الشخصية', 'مصمّمة منذ البداية وفق القانون الأساسي عدد 63 لسنة 2004 المتعلق بحماية المعطيات الشخصية');
  const bw = 4.6, bx = M, by = 2.0, bh = 4.6;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: by, w: bw, h: bh, rectRadius: 0.16, fill: { color: C.accent1 }, line: { color: HEX.navy, width: 0 }, objectName: 'medical-callout' });
  s.addShape(pres.shapes.OVAL, { x: bx + bw - 0.4 - 1.0, y: by + 0.4, w: 1.0, h: 1.0, fill: { color: '3A57B5' }, line: { color: '3A57B5', width: 0 } });
  s.addImage({ path: img('w-lock.png'), x: bx + bw - 0.4 - 0.8, y: by + 0.6, w: 0.6, h: 0.6, altText: '' });
  text(s, 'الملف الطبي للمواطن', { x: bx + 0.4, y: by + 1.65, w: bw - 0.8, h: 0.5, fontSize: 20, bold: true, color: C.background1 });
  text(s, 'لا يستطيع الخادم قراءته', { x: bx + 0.3, y: by + 2.1, w: bw - 0.6, h: 0.6, fontSize: 24, bold: true, color: 'FFC933' });
  text(s, 'يُقفل على هاتف المواطن نفسه، ولا يفتحه إلا أطباء الحماية المدنية في ولاية البلاغ واللجنة الطبية. كل فتح مسجَّل، والمواطن يرى من اطّلع على ملفه ومتى.',
    { x: bx + 0.4, y: by + 2.95, w: bw - 0.8, h: 1.45, fontSize: 14, color: 'E8ECF5' });
  const rows = [
    ['تحقق بخطوتين إجباري', 'لكل حساب من حسابات الأعوان، مع إلغاء فوري للجلسات', 'verified', 'navy'],
    ['تشفير المعطيات الحساسة', 'رقم بطاقة التعريف والمعطيات الطبية مشفّرة (AES-256)', 'lock', 'purple'],
    ['سجل تدقيق لا يُعدَّل', 'كل اطلاع وكل قرار مسجَّل: من، متى، ماذا، ولماذا', 'policy', 'slate'],
    ['أدلة موثوقة', 'بصمة رقمية لكل صورة وفيديو، وختم دوري لا يمكن تزويره', 'fact_check', 'green'],
    ['عزل معطيات كل ولاية', 'قاعدة البيانات نفسها تمنع الاطلاع خارج النطاق', 'database', 'teal'],
  ];
  const x0 = bx + bw + 0.5, w = W - M - x0, rh = 0.93;
  rows.forEach(([t, d, ic, tone], i) => {
    const y = 2.0 + i * rh;
    tile(s, W - M - 0.66, y, 0.66, tone, ic);
    text(s, t, { x: x0, y: y - 0.02, w: w - 0.9, h: 0.4, fontSize: 18, bold: true });
    text(s, d, { x: x0, y: y + 0.38, w: w - 0.9, h: 0.45, fontSize: 14, color: HEX.muted });
  });
  s.addNotes('الثقة شرط النجاح. الملف الطبي مثال واضح: يُشفَّر على الهاتف، والخادم لا يملك مفتاحه. قبل الإطلاق نحتاج ترخيص الهيئة الوطنية لحماية المعطيات الشخصية وتدقيق الوكالة الوطنية للأمن السيبراني.');
}

// ---------- 10. Progress ----------
pres.addSection({ title: 'الإنجاز' });
{
  const s = content('الإنجاز', 'ما أُنجز: 37 مرحلة مكتملة', 'كل مرحلة مرّت بالمراجعة ثم إعادة التصميم ثم التطوير، وانتهت بتقرير واختبارات آلية');
  const groups = [
    ['الأساس ومسار البلاغ', 'البنية، الهوية والصلاحيات، البلاغ من الهاتف إلى القاعة، الطبقة الأولى من الذكاء الاصطناعي', 'المراحل 1 إلى 3', 'navy'],
    ['المؤسسات والعمليات', 'بوابة المؤسسات والشهادة الرقمية، التدخلات والتنبيهات، شهادة الوقاية، تطبيق الأعوان، الخريطة والسلامة الساحلية والبرامج الموسمية، محور الكارثة والسجل والتوجيهات', 'المراحل 4 إلى 5.5 و P2 إلى P4 و L', 'teal'],
    ['البث والطقس والمعرفة', 'البث المباشر وكشف الحرائق، الطقس ودعم القرار والاتصالات، التحليلات والذاكرة الوطنية', 'المراحل 6 إلى 8', 'orange'],
    ['الصلاحيات والتحصين', 'فصل القاعة المركزية عن الجهوية، التحقق بخطوتين، النسخ والاستعادة، المراقبة', 'المرحلتان 9 و10', 'purple'],
    ['تجربة المواطن والأطباء', 'الاستقبال والدخول بالهاتف، مركز الطوارئ، السلامة الشخصية، محور الأطباء، نظام التصميم وشريط البيئة وحماية المسودات، والنفاذ لذوي الإعاقة في التطبيق بالقراءة الصوتية والوميض والوضع المبسّط', 'A و B و C1 و UI و UI-2 و UI-3 و P3c و P5a و P5b', 'red'],
  ];
  const rh = 0.86, gap = 0.12, y0 = 1.95, w = W - 2 * M;
  groups.forEach(([t, d, ph, tone], i) => {
    const y = y0 + i * (rh + gap);
    card(s, M, y, w, rh, { name: 'phase-' + i });
    tile(s, W - M - 0.2 - 0.56, y + 0.15, 0.56, tone, 'check_circle');
    text(s, t, { x: W - M - 4.0, y: y + 0.08, w: 3.1, h: 0.4, fontSize: 17, bold: true });
    text(s, ph, { x: W - M - 4.0, y: y + 0.46, w: 3.1, h: 0.32, fontSize: 12, bold: true, color: TONE[tone] });
    text(s, d, { x: M + 1.75, y: y + 0.1, w: w - 5.85, h: rh - 0.2, fontSize: 14, color: HEX.muted, valign: 'middle' });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M + 0.25, y: y + 0.24, w: 1.3, h: 0.38, rectRadius: 0.19, fill: { color: 'E6F4EA' }, line: { color: 'E6F4EA', width: 0 } });
    text(s, 'مكتملة 100%', { x: M + 0.25, y: y + 0.24, w: 1.3, h: 0.38, fontSize: 12, bold: true, color: '166B2E', align: 'center', valign: 'middle' });
  });
  s.addNotes('أُنجزت سبع وثلاثون مرحلة، مجمّعة هنا في خمسة محاور. آخرها UI-3 و UI-3b: صارت القائمة الرئيسية للوحة في سبع مجموعات حسب العمل، كالعمليات اليومية والأزمات والقيادة، تُفتح بمجرد المرور عليها، أو تظهر كل روابطها إن فضّل المستخدم ذلك، أعلى الشاشة أو على يمينها أو يسارها، يختار كل مستخدم ما يناسبه من قائمة حسابه. وصارت طبقات الخريطة في مجلدات: موارد الحماية المدنية، المؤسسات الصحية بمستشفياتها ومصحاتها وصيدلياتها، الأمن، النقل وغيرها، يفتح المستخدم المجلد الذي يحتاجه ويُظهر طبقاته كلها بضغطة؛ ولا يرى أحد مجلدا ليس فيه طبقة مسموح له بها، فالطبقات الحساسة تبقى للوزير وحده. وقبلها L3b: صار للديوان سجل واحد لكل المخططات والقرارات والمناشير والتعليمات والتوصيات، مركزيا وجهويا، يُبحث فيه بالموضوع والفترة والولاية، وتُتابع فيه أهم التوصيات بآجالها؛ ومخطط كل محور يُختار منه. وصارت التوجيهات تخرج من القاعة المركزية إلى ولاية بعينها أو إلى الكل، بنص أو بملفات Word و Excel و PDF، وترد كل ولاية في خيط لا تراه غيرها، وترى القاعة المركزية كل الخيوط ومن اطّلع ومن ردّ؛ وترفع القاعة الجهوية إشعارا فوريا عن حدث. وقبلها L3: صار للكارثة أو الأزمة الكبرى «محور» يجمع تدخلاتها في مكان واحد، برقم ومستوى من واحد إلى أربعة وحيّز على الخريطة؛ يطلب رئيس القاعة الجهوية إعلانه ويفتحه رئيس القاعة المركزية، ويرفعه إلى وطني إن اتسع؛ ويرى الوالي محاور ولايته والوزير كل المحاور، بالأرقام والخريطة دون أسماء المبلّغين أو الضحايا، ولا يرى الوالي الطبقات الحساسة؛ ويصدر كل منهما توصية أو قرارا موقّعا رقميا لا يُعدَّل، تنفّذه القاعة وتحدّث حالته، وقرار الوزير يُعتمد إن تعارض مع قرار الوالي؛ وتُعدّ المنظومة تقرير الوضع آليا كل ست ساعات أو أقل حسب المستوى؛ وعند الإغلاق تُحسب الحصيلة وتُنشأ مسودة في الذاكرة الوطنية. وللواجهات وضع ليلي ووضع نهاري. وقبلها L2: صارت برامج الصيف، كبرنامج المراقبة على الطرقات والتركيز التدريجي بالشواطئ، تُحمَّل من ملف الديوان كما هو، فيرى المسؤول قبل الحفظ الأخطاء والفروق بين المجاميع المصرّح بها والمحسوبة وما تغيّر عن النسخة السابقة؛ ويعتمدها مدير العمليات فتظهر طبقة على الخريطة بين تاريخي بدايتها ونهايتها فقط؛ ولكل نقطة حالتها وعدد المنقذين المبرمجين والمنتشرين، وتتابعها القاعة يوميا، ويُحفظ لكل تعديل سببه ونسخته ويمكن استرجاع أي نسخة؛ ويُعدّ الشاطئ محروسا متى كانت قربه نقطة مفتوحة. اسم المشرف وهاتفه تراهما قاعات العمليات وحدها ولا يراهما المواطن. وفي الدخول، بعد ثلاث محاولات فاشلة يطلب المتصفح حلّ مسألة حسابية قصيرة دون أن يُسأل الشخص شيئا، وتُقفل الحساب مؤقتا بعد عشر محاولات، وكلمة السر ثمانية أحرف على الأقل. وقبلها L1b: صار لكل شاطئ لون يومي، أخضر أو أصفر أو أحمر، لليوم وثلاثة أيام قادمة، يُحسب كل ساعة من الأمواج وحرارة البحر والتيار والريح والحراسة والحوادث السابقة بقواعد معلنة يعدّلها الديوان، مع سبب كل نقطة؛ تتلقى القاعات الساحلية تنبيها حيا حين يصير شاطئ خطرا، ولها لوحة بأخطر الشواطئ والتوزيع حسب الولاية ونشرة يومية؛ ويرى المواطن ألوان الشواطئ في تطبيقه، وينبّهه هاتفه قرب شاطئ خطر إن وافق، دون أن يُرسل موقعه. وقبلها L1a: صار مدير المنظومة يتحكم في كل طبقة من طبقات الخريطة؛ يحدد من يراها من المواطنين والقاعات والميدان والقيادة، ويجعل الطبقة الحساسة للوزير وحده مع تسجيل كل اطلاع، ويخفي حقلا عن فئة بعينها، ويعدّل الطبقة أو يحذفها أو يسترجعها خلال ثلاثين يوما، ويراجع الأسماء المقترحة لطبقات OpenStreetMap قبل أن يراها المواطن. وقبلها P4d: صار تطبيق الأعوان يعمل في الميدان ولو انقطعت الشبكة؛ كل ضغطة يقوم بها القائد تُحفظ مشفّرة على هاتفه وتظهر فوراً، ثم تُرسل وحدها بالترتيب عند عودة الشبكة دون تكرار وبوقتها الحقيقي؛ وإن طال الانقطاع يرسل الخطوة أو طلب النجدة برسالة قصيرة موقّعة بمفتاح هاتفه فلا يمكن تزويرها؛ وترى القاعة موقع المركبة وبُعدها عن الحادث؛ وترنّ المهمة بملء الشاشة ولو كان الهاتف مقفلاً؛ وصار للأعوان تطبيق مستقل بجانب تطبيق المواطن؛ ويُعلَم المواطن المبلّغ بأن الفريق في الطريق إليه ثم بوصوله. وقبلها P4c: صار مفقِّد الوقاية يحمل الزيارة على هاتفه، يعاين كل بند صرّحت به المؤسسة بزر «مطابق» أو «غير مطابق» مع سبب جاهز وصورة، ويأخذ توقيع ممثل المؤسسة وتوقيعه بالإصبع، ويقرّر الموافقة أو التحفظات بآجالها أو الرفض، كل ذلك ولو في قبو دون شبكة؛ يُحفظ العمل مشفّراً على الهاتف ويُرسل وحده عند عودة الشبكة، وتصدر الشهادة من الخادم. وقبلها P4b: صار تطبيق قادة الفرق يُستعمل بالأزرار والرقائق والعدّادات دون كتابة تقريباً؛ يرسل القائد تقرير الوضع وعدد المصابين ونقلهم إلى أقرب مستشفى في ثوانٍ، ويطلب النجدة أو ينبّه إلى خطر على الطاقم بزر أحمر فيظهر في رأس بطاقة الحادث حتى تضغط القاعة «اطّلعت»، ويرفق صورة أو صوتاً، ويملأ التقرير المفصّل حسب قالب يعتمده الديوان من اللوحة. وقبلها P4a: تطبيق قادة فرق التدخل، يدخل فيه القائد بالتحقق بخطوتين ورمز PIN، يبدأ مناوبته بالآلية، يرنّ هاتفه عند التكليف، ويرسل الخطوات والتقرير الأول وعدد الضحايا في ثوانٍ، وتراها القاعة فوراً، ويُمسح الهاتف عن بعد عند ضياعه. المراحل الثلاث الأخيرة خصّت ذوي الإعاقة وسهولة الاستعمال في تطبيق الهاتف. في P3c صار كل زر مسمّى لقارئ الشاشة، والتباين مطابقاً لمعيار WCAG، والخط المكبَّر إلى الضعف لا يُقصّ في أي شاشة. وفي P5a يقرأ زر «استمع» الأدلة والنصائح والتنبيهات بصوت الهاتف نفسه دون إنترنت، ويستطيع ضعيف السمع أن يختار وميض الشاشة ومصباح الكاميرا عند وصول تنبيه عاجل، إضافة إلى الاهتزاز الخاص بالتنبيهات الرسمية. وفي P5b صار للمسنّين ومن يصعب عليه الاستعمال «وضع مبسّط»: خمسة أزرار كبيرة بجمل قصيرة في متناول الإبهام، وصار المواطن يقيّم التطبيق بالنجوم ويعيد جولة التعريف، وصارت المؤسسة تسجّل من الهاتف ببريدها المهني المؤكَّد برمز. P4d تنتظر الدمج النهائي.');
}

// ---------- 11. Quality in numbers ----------
{
  const s = content('الإنجاز', 'الجودة بالأرقام', 'كل تعديل يمر بفحوص آلية قبل قبوله، ولا يُدمج إلا إذا نجحت كلها');
  const cx = M, cw = 7.0, cy = 1.95, chh = 4.75;
  card(s, cx, cy, cw, chh, { name: 'chart-card' });
  s.addChart(pres.charts.BAR, [{ name: 'الاختبارات الآلية', labels: ['الخلفية', 'لوحة القيادة', 'تطبيق الهاتف', 'الخدمات المساعدة', 'البوابة', 'مزود الهوية'], values: [953, 521, 575, 190, 104, 44] }], {
    x: cx + 0.25, y: cy + 0.2, w: cw - 0.5, h: chh - 0.4, barDir: 'bar', chartColors: [HEX.navy],
    showTitle: true, title: 'الاختبارات الآلية حسب المكوّن (أكثر من 2000)', titleFontSize: 14, titleColor: HEX.ink, titleFontFace: '+mn-lt',
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 12, dataLabelColor: HEX.ink, dataLabelFontFace: '+mn-lt',
    catAxisLabelColor: HEX.muted, catAxisLabelFontSize: 12, catAxisLabelFontFace: '+mn-lt', catAxisOrientation: 'maxMin',
    valAxisHidden: true, valGridLine: { style: 'none' }, catGridLine: { style: 'none' }, showLegend: false, barGapWidthPct: 60,
  });
  const stats = [
    ['27', 'فحصاً آلياً قبل دمج أي تعديل', 'navy'],
    ['16', 'بلاغ نجدة في الثانية في اختبار الحمل، بزمن استجابة 0.33 ثانية', 'red'],
    ['0', 'مخالفة في فحص النفاذ لذوي الإعاقة (WCAG 2.2) في الويب والتطبيق', 'green'],
  ];
  const x0 = cx + cw + 0.4, w = W - M - x0, sh = 1.45;
  stats.forEach(([n, d, tone], i) => {
    const y = cy + i * (sh + 0.2);
    card(s, x0, y, w, sh, { name: 'q-' + i });
    text(s, n, { x: W - M - 0.3 - 1.5, y: y + 0.15, w: 1.5, h: sh - 0.3, fontSize: 44, bold: true, color: TONE[tone], valign: 'middle', align: 'center' });
    text(s, d, { x: x0 + 0.3, y: y + 0.15, w: w - 2.2, h: sh - 0.3, fontSize: 15, valign: 'middle' });
  });
  s.addNotes('أكثر من ألفي اختبار آلي، وسبعة وعشرون فحصاً لكل تعديل. في اختبار الحمل استقبلت المنظومة ست عشرة استغاثة في الثانية مع زمن استجابة في حدود ثلث ثانية.');
}

// ---------- 12. What is needed ----------
pres.addSection({ title: 'الخطوات القادمة' });
{
  const s = content('الخطوات القادمة', 'ما يحتاجه المشروع من الديوان', 'مدخلات لا تُنجز تقنياً، وهي شرط للانتقال إلى التجربة الميدانية');
  const items = [
    ['بوابة رسائل قصيرة رسمية', 'لرموز الدخول والتنبيهات والتبليغ بالرسائل', 'sms', 'navy'],
    ['مركز بيانات داخل تونس', 'للاستضافة والنسخ الاحتياطي في موقع ثانٍ', 'dns', 'teal'],
    ['ترخيص حماية المعطيات', 'من الهيئة الوطنية، خاصة للمعطيات الصحية وسجل المواقع', 'gavel', 'purple'],
    ['تدقيق الأمن السيبراني', 'من الوكالة الوطنية قبل الإطلاق', 'policy', 'slate'],
    ['مصادقة طبية', 'على محتوى الإسعافات الأولية الموجّه للمواطن', 'medical_services', 'red'],
    ['قوائم ونماذج مرجعية', 'المراكز وأصناف المؤسسات، والختم الرسمي، ونص شهادة الوقاية وشبكة التفقد الرسمية', 'location_on', 'orange'],
  ];
  const cw = (W - 2 * M - 0.6) / 3, ch = 2.1;
  items.forEach(([t, d, ic, tone], i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = W - M - cw - col * (cw + 0.3), y = 2.0 + row * (ch + 0.3);
    card(s, x, y, cw, ch, { name: 'need-' + i });
    tile(s, x + cw - 0.3 - 0.75, y + 0.3, 0.75, tone, ic);
    text(s, t, { x: x + 0.3, y: y + 1.12, w: cw - 0.6, h: 0.42, fontSize: 18, bold: true });
    text(s, d, { x: x + 0.3, y: y + 1.52, w: cw - 0.6, h: 0.5, fontSize: 14, color: HEX.muted });
  });
  s.addNotes('هذه المدخلات خارج نطاق الفريق التقني، وهي ما يفصلنا عن التجربة الميدانية: بوابة الرسائل، ومركز البيانات، والتراخيص، والمصادقة الطبية، والقوائم المرجعية.');
}

// ---------- 13. Roadmap ----------
{
  const s = content('الخطوات القادمة', 'خارطة الطريق نحو الإطلاق', 'خمس خطوات متتالية، ولا يُنتقل إلى خطوة إلا بعد موافقة الديوان');
  const steps = [
    ['تجربة النفاذ', 'قارئ الشاشة والأصوات العربية والوضع المبسّط مع جمعيات ذوي الإعاقة، ببروتوكول جاهز', 'smartphone', 'navy'],
    ['تطبيق الأعوان', 'مكتمل؛ تبقى التجربة مع فرق حقيقية وتفعيل الإشعارات', 'engineering', 'orange'],
    ['الخريطة والقرار', 'الخريطة ومحور الكارثة والسجل أُنجزت؛ يبقى سجل الموارد ونافذة القرار والتمارين [SIM]', 'map', 'purple'],
    ['التحصين', 'اختبار الاختراق وتدقيق الأمن واستكمال كاشف الحرائق', 'shield', 'purple'],
    ['التجربة الميدانية', 'في ولاية واحدة، بتقرير نتائج قبل التعميم الوطني', 'rocket_launch', 'green'],
  ];
  const span = W - 2 * M, n = steps.length, sw = span / n, ly = 2.55;
  s.addShape(pres.shapes.LINE, { x: M + sw / 2, y: ly, w: span - sw, h: 0, line: { color: HEX.line, width: 3 } });
  steps.forEach(([t, d, ic, tone], i) => {
    const cx = W - M - sw * i - sw / 2;
    s.addShape(pres.shapes.OVAL, { x: cx - 0.5, y: ly - 0.5, w: 1.0, h: 1.0, fill: { color: TONE[tone] }, line: { color: 'FFFFFF', width: 3 }, objectName: 'road-' + i });
    s.addImage({ path: img('w-' + ic + '.png'), x: cx - 0.27, y: ly - 0.27, w: 0.54, h: 0.54, altText: '' });
    const x = cx - sw / 2 + 0.12, w = sw - 0.24, y = ly + 0.85;
    card(s, x, y, w, 2.85, { name: 'road-card-' + i });
    text(s, 'الخطوة ' + (i + 1), { x: x + 0.25, y: y + 0.25, w: w - 0.5, h: 0.35, fontSize: 12, bold: true, color: TONE[tone] });
    text(s, t, { x: x + 0.2, y: y + 0.6, w: w - 0.4, h: 0.45, fontSize: 16, bold: true, fit: 'shrink' });
    text(s, d, { x: x + 0.2, y: y + 1.15, w: w - 0.4, h: 1.6, fontSize: 13, color: HEX.muted });
  });
  s.addNotes('خمس خطوات نحو الإطلاق. كل خطوة تبدأ بموافقة الديوان، والتجربة الميدانية في ولاية واحدة تسبق أي تعميم.');
}

// ---------- 14. Closing ----------
{
  const s = pres.addSlide({ masterName: 'DARK', sectionTitle: 'الخطوات القادمة' });
  s.addText('الخطوات المقترحة', { placeholder: 'title', ...AR });
  const asks = [
    ['1', 'اختيار ولاية التجربة الميدانية'],
    ['2', 'توفير المدخلات: الرسائل القصيرة، مركز البيانات، التراخيص'],
    ['3', 'تعيين فريق متابعة من الديوان لمرافقة التجربة'],
  ];
  asks.forEach(([n, t], i) => {
    const y = 1.85 + i * 1.05;
    s.addShape(pres.shapes.OVAL, { x: W - M - 0.75, y, w: 0.75, h: 0.75, fill: { color: 'FFA733' }, line: { color: 'FFA733', width: 0 } });
    text(s, n, { x: W - M - 0.75, y, w: 0.75, h: 0.75, fontSize: 24, bold: true, color: C.text2, align: 'center', valign: 'middle' });
    text(s, t, { x: M + 2.7, y, w: W - 2 * M - 3.7, h: 0.75, fontSize: 22, color: C.background1, valign: 'middle' });
  });
  s.addImage({ path: img('logo-disc.png'), x: M, y: 1.85, w: 2.1, h: 2.1, altText: 'شعار الديوان الوطني للحماية المدنية' });
  text(s, 'ء-حماية · من التبليغ إلى أخذ القرار', { x: M, y: 5.35, w: W - 2 * M, h: 0.7, fontSize: 28, bold: true, color: 'FFA733', align: 'center', valign: 'middle' });
  text(s, 'شكراً لحسن انتباهكم', { x: M, y: 6.1, w: W - 2 * M, h: 0.5, fontSize: 18, color: 'E8ECF5', align: 'center' });
  s.addNotes('نقترح ثلاث خطوات عملية للمرور إلى التجربة الميدانية. شكراً لحسن انتباهكم، ونحن على ذمتكم للأسئلة.');
}

(async () => {
  const out = process.argv[2] || 'deck.pptx';
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log('ok', out);
})();
