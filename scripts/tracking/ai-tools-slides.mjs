// The slides of the local AI tools, drawn with the deck kit (deck-kit.mjs): why local, the map of the tools, one slide
// per tool (without it, with it, the difference, its figures, where it works, its safeguard), local against cloud,
// the safeguards and the server sizes. Used whole by ai-tools-pptx.mjs and as a part of pitch-pptx.mjs.
import {DISP, DISPM, MONO, ind} from './deck-kit.mjs';
import {STAGES, TOOLS, WHY, COMPARE, GUARDS, PROFILES} from './ai-tools-data.mjs';

export {TOOLS};

// adds the AI slides to the plan; returns their numbers
export function planAi(K) {
  const P = {why: K.add('why'), map: K.add('aimap')};
  P.tools = TOOLS.map(t => K.add('tool', {tool: t.i}));
  P.compare = K.add('compare'); P.guards = K.add('guards'); P.profiles = K.add('profiles');
  return P;
}

// draws them in the current colour set; crumb is the eyebrow's root, after the slide the AI part leads to
export function drawAi(K, P, {crumb = 'ء-حماية · الذكاء الاصطناعي المحلي', after} = {}) {
  const {pres, A} = K, C = K.C, night = K.MODE === 'night';
  const stc = st => K.tone(st.tone);
  const back = (s, extra = []) => { K.button(s, 'خريطة الأدوات', 0.5, 0.6, 1.45, P.map, true); extra.forEach(f => f()); };

  // why local: six values
  {
    const s = K.newSlide(P.why);
    K.crumb(s, crumb); K.title(s, 'لماذا ذكاء اصطناعي محلي؟');
    K.lead(s, 'كل أداة تعمل على خوادم الديوان، بنماذج مفتوحة المصدر مثبّتة مسبقا. هذا وحده يغيّر ستة أشياء:');
    WHY.forEach(([h, b], k) => {
      const col = k % 3, row = Math.floor(k / 3), w = 3.95, x = 12.83 - (col + 1) * w - col * 0.2, y = 1.85 + row * 2.45, dl = 300 + k * 140;
      A(K.panel(s, x, y, w, 2.2), 'fade', dl, 500);
      A(K.shape(s, pres.shapes.LINE, {x: x + 0.3, y: y + 0.32, w: w - 0.6, h: 0, line: {color: C.gold, width: 1.75}}), 'wipe', dl + 100, 500, 'l');
      A(K.text(s, [{text: ind(k + 1) + '  ', options: {color: C.gold, fontFace: DISP}}, {text: h, options: {}}], {x: x + 0.3, y: y + 0.45, w: w - 0.6, h: 0.5, fontSize: 18, fontFace: DISPM, color: C.ink}), 'fade', dl + 150, 500);
      A(K.text(s, b, {x: x + 0.3, y: y + 1.0, w: w - 0.6, h: 1.05, fontSize: 12.5, color: C.ink, valign: 'top'}), 'fade', dl + 200, 500);
    });
    back(s); K.foot(s); K.counter(s, P.why);
  }

  // the tools along the chain, each a link to its slide
  {
    const s = K.newSlide(P.map);
    K.crumb(s, crumb); K.title(s, 'خريطة الأدوات');
    K.lead(s, 'أين تعمل كل أداة في سلسلة المنظومة، من التبليغ إلى أخذ القرار. اضغط على أداة لفتح شريحتها.');
    const n = STAGES.length, gap = 0.14, w = (12.33 - gap * (n - 1)) / n;
    STAGES.forEach((st, k) => {
      const x = 12.83 - (k + 1) * w - k * gap, col = stc(st), dl = 250 + k * 160, tools = TOOLS.filter(t => t.stage === st.k);
      A(K.shape(s, pres.shapes.CHEVRON, {x, y: 1.8, w: w + 0.05, h: 0.62, fill: {color: col}, flipH: true}), 'wipe', dl, 500, 'l');
      A(K.text(s, st.name, {x: x + 0.15, y: 1.8, w: w - 0.3, h: 0.62, align: 'center', fontSize: 13, bold: true, color: C.onTone}), 'fade', dl + 100, 400);
      tools.forEach((t, j) => {
        const y = 2.65 + j * 1.38, d = dl + 200 + j * 120;
        A(K.panel(s, x, y, w, 1.22, {line: {color: col, width: 1.25}, ...K.link(P.tools[t.i])}), 'fade', d, 400);
        A(K.text(s, [{text: String(t.i + 1), options: {fontFace: MONO, color: col, bold: true, breakLine: true}}, {text: t.name, options: {}}],
          {x: x + 0.12, y: y + 0.08, w: w - 0.24, h: 1.06, fontSize: 12.5, bold: true, align: 'center', color: C.ink, ...K.link(P.tools[t.i])}), 'fade', d, 400);
      });
    });
    K.button(s, 'لماذا محلية؟', 0.5, 0.6, 1.45, P.why);
    K.foot(s); K.counter(s, P.map);
  }

  // one slide per tool
  for (const t of TOOLS) {
    const n = P.tools[t.i], s = K.newSlide(n), col = stc(t.st);
    K.crumb(s, `${crumb} · ${t.st.name}`); K.title(s, t.name, t.i + 1);
    A(K.shape(s, pres.shapes.RECTANGLE, {x: 12.78, y: 1.3, w: 0.05, h: 0.7, fill: {color: col}}), 'fade', 100, 400);
    A(K.text(s, t.what, {x: 0.5, y: 1.25, w: 12.15, h: 0.8, fontSize: 13, color: C.mute, valign: 'top'}), 'fade', 150, 500);
    const pw = 4.05, py = 2.2, ph = 2.45, rows = Math.max(t.without.length, t.with.length), lh = Math.min(0.75, 1.85 / rows), fs = rows < 3 ? 13 : 12;
    const xw = 12.83 - pw, xm = xw - 0.2 - pw;
    A(K.panel(s, xw, py, pw, ph), 'fade', 300, 500);
    A(K.text(s, 'دون الأداة', {x: xw + 0.25, y: py + 0.12, w: pw - 0.5, h: 0.36, fontSize: 13, bold: true, color: C.no}), 'fade', 350, 400);
    K.list(s, t.without, xw + 0.25, py + 0.6, pw - 0.5, lh, C.no, 400, fs);
    A(K.panel(s, xm, py, pw, ph, {line: {color: col, width: 1.5}}), 'fade', 700, 500);
    A(K.text(s, 'مع الأداة', {x: xm + 0.25, y: py + 0.12, w: pw - 0.5, h: 0.36, fontSize: 13, bold: true, color: col}), 'fade', 750, 400);
    K.list(s, t.with, xm + 0.25, py + 0.6, pw - 0.5, lh, col, 800, fs);
    const xv = 0.5, wv = xm - 0.2 - xv;
    A(K.panel(s, xv, py, wv, ph, {fill: {color: C.root}, line: {color: C.gold, width: 1.5}}), 'fade', 1100, 500);
    A(K.text(s, 'الفارق', {x: xv + 0.25, y: py + 0.12, w: wv - 0.5, h: 0.36, fontSize: 13, bold: true, color: C.gold}), 'fade', 1150, 400);
    A(K.text(s, t.value, {x: xv + 0.25, y: py + 0.5, w: wv - 0.5, h: 1.85, fontSize: 16.5, bold: true, color: night ? C.ink : C.white, valign: 'top', lineSpacingMultiple: 1.05}), 'fade', 1200, 600);
    const nf = t.figures.length, fw = (12.33 - 0.3 * 2) / 3;
    t.figures.forEach(([v, l], k) => K.figure(s, 12.83 - (k + 1) * fw - k * 0.3, 4.95, fw, v, l, 1400 + k * 150, col));
    void nf;
    A(K.text(s, [{text: 'أين تعمل: ', options: {bold: true, color: col}}, {text: t.where.join(' · '), options: {color: C.ink}}], {x: 6.75, y: 5.95, w: 6.08, h: 0.62, fontSize: 11.5, valign: 'top'}), 'fade', 1700, 500);
    A(K.text(s, [{text: 'الضمانة: ', options: {bold: true, color: C.gold}}, {text: t.guard, options: {color: C.ink}}], {x: 0.5, y: 5.95, w: 6.05, h: 0.85, fontSize: 11.5, valign: 'top'}), 'fade', 1800, 500);
    A(K.text(s, t.tech, {x: 6.75, y: 6.62, w: 6.08, h: 0.28, fontSize: 9.5, color: C.mute}), 'fade', 1900, 500);
    K.button(s, 'الخريطة', 0.5, 0.6, 1.0, P.map, true);
    if (t.i > 0) K.button(s, 'السابقة', 1.62, 0.6, 0.95, P.tools[t.i - 1]);
    K.button(s, 'التالية', t.i > 0 ? 2.69 : 1.62, 0.6, 0.95, t.i < TOOLS.length - 1 ? P.tools[t.i + 1] : P.compare);
    K.counter(s, n);
  }

  // local against cloud
  {
    const s = K.newSlide(P.compare);
    K.crumb(s, crumb); K.title(s, 'محلي أم سحابي؟');
    K.lead(s, 'الأدوات نفسها، في مكانين: الفرق ليس تقنيا فقط، بل في من يملك البيانات والقرار.');
    const cw = [3.6, 4.4, 4.33], top = 1.85, rh = 0.62;
    const xs = [12.83 - cw[0], 12.83 - cw[0] - cw[1], 12.83 - cw[0] - cw[1] - cw[2]];
    A(K.shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: xs[1], y: top - 0.08, w: cw[1], h: rh * (COMPARE.length + 1) + 0.16, rectRadius: 0.12, fill: {color: C.panel}, line: {color: C.gold, width: 1.5}}), 'fade', 200, 500);
    [['', C.mute], ['على خوادم الديوان (ء-حماية)', C.gold], ['خدمة سحابية خارجية', C.mute]].forEach(([h, c], k) =>
      A(K.text(s, h, {x: xs[k] + 0.2, y: top, w: cw[k] - 0.4, h: rh, fontSize: 14, bold: true, color: c, align: k ? 'center' : 'right'}), 'fade', 250, 400));
    COMPARE.forEach((r, j) => {
      const y = top + (j + 1) * rh, dl = 400 + j * 130;
      A(K.shape(s, pres.shapes.LINE, {x: 0.5, y, w: 12.33, h: 0, line: {color: C.line, width: 0.75}}), 'fade', dl, 300);
      A(K.text(s, r[0], {x: xs[0] + 0.2, y, w: cw[0] - 0.4, h: rh, fontSize: 13, bold: true, color: C.ink}), 'fade', dl, 400);
      A(K.text(s, '✓  ' + r[1], {x: xs[1] + 0.2, y, w: cw[1] - 0.4, h: rh, fontSize: 13, color: C.ink, align: 'center'}), 'fade', dl + 80, 400);
      A(K.text(s, r[2], {x: xs[2] + 0.2, y, w: cw[2] - 0.4, h: rh, fontSize: 13, color: C.mute, align: 'center'}), 'fade', dl + 120, 400);
    });
    back(s); K.foot(s); K.counter(s, P.compare);
  }

  // safeguards
  {
    const s = K.newSlide(P.guards);
    K.crumb(s, crumb); K.title(s, 'ست ضمانات على كل أداة');
    K.lead(s, 'القاعدة الثابتة: الذكاء الاصطناعي يقترح ويعلّل، والإنسان يقرّر. وتطبيقها في المنظومة:');
    GUARDS.forEach(([h, b], k) => {
      const col = k % 2, row = Math.floor(k / 2), w = 6.06, x = 12.83 - (col + 1) * w - col * 0.21, y = 1.85 + row * 1.6, dl = 300 + k * 140;
      A(K.panel(s, x, y, w, 1.42), 'fade', dl, 500);
      A(K.shape(s, pres.shapes.OVAL, {x: x + w - 0.95, y: y + 0.36, w: 0.7, h: 0.7, fill: {color: C.root}, line: {color: C.gold, width: 1.5}}), 'zoom', dl + 100, 400);
      A(K.text(s, ind(k + 1), {x: x + w - 0.95, y: y + 0.36, w: 0.7, h: 0.7, align: 'center', fontSize: 18, fontFace: DISP, color: C.gold}), 'zoom', dl + 100, 400);
      A(K.text(s, h, {x: x + 0.3, y: y + 0.22, w: w - 1.45, h: 0.45, fontSize: 16, fontFace: DISPM, color: C.ink}), 'fade', dl + 150, 400);
      A(K.text(s, b, {x: x + 0.3, y: y + 0.72, w: w - 1.45, h: 0.5, fontSize: 12.5, color: C.mute, valign: 'top'}), 'fade', dl + 200, 400);
    });
    back(s); K.foot(s); K.counter(s, P.guards);
  }

  // server sizes
  {
    const s = K.newSlide(P.profiles);
    K.crumb(s, crumb); K.title(s, 'على أي خادم تعمل؟');
    K.lead(s, 'الأدوات نفسها على مقاسين من الخوادم: يتغيّر حجم النموذج، ولا يتغيّر شيء في عمل القاعة.');
    PROFILES.forEach(([h, stt, llm, tag], k) => {
      const w = (12.33 - 0.24 * (PROFILES.length - 1)) / PROFILES.length, x = 12.83 - (k + 1) * w - k * 0.24, y = 1.9, dl = 300 + k * 200;
      A(K.panel(s, x, y, w, 3.3, k === 0 ? {line: {color: C.gold, width: 1.5}} : {}), 'fade', dl, 500);
      A(K.text(s, tag, {x: x + 0.3, y: y + 0.25, w: w - 0.6, h: 0.5, fontSize: 22, fontFace: MONO, bold: true, color: C.gold, rtlMode: false, lang: 'en-US', align: 'right'}), 'fade', dl + 100, 400);
      A(K.text(s, h, {x: x + 0.3, y: y + 0.8, w: w - 0.6, h: 0.45, fontSize: 16, fontFace: DISPM, color: C.ink}), 'fade', dl + 150, 400);
      [['الصوت إلى نص', stt], ['النموذج اللغوي', llm], ['النار والدخان والأشخاص', 'YOLOX-Tiny على المعالج']].forEach(([a, b], j) => {
        A(K.text(s, a, {x: x + 0.3, y: y + 1.4 + j * 0.6, w: w - 0.6, h: 0.26, fontSize: 10.5, color: C.mute}), 'fade', dl + 200 + j * 80, 400);
        A(K.text(s, b, {x: x + 0.3, y: y + 1.64 + j * 0.6, w: w - 0.6, h: 0.3, fontSize: 13, bold: true, color: C.ink}), 'fade', dl + 200 + j * 80, 400);
      });
    });
    A(K.panel(s, 0.5, 5.5, 12.33, 1.3), 'fade', 1000, 500);
    A(K.text(s, [{text: 'التثبيت مرة واحدة: ', options: {bold: true, color: C.gold}},
      {text: 'تُجلب النماذج ويُتحقق من بصمتها ورخصتها، ويُرفض كل نموذج رخصته غير متساهلة. بعد ذلك لا يُنزَّل شيء أثناء العمل، ويمكن نقل النماذج إلى خادم دون إنترنت.', options: {color: C.ink}}],
      {x: 0.8, y: 5.62, w: 11.73, h: 1.06, fontSize: 12.5, valign: 'middle'}), 'fade', 1100, 500);
    back(s, after ? [() => K.button(s, 'متابعة العرض', 2.07, 0.6, 1.6, after)] : []);
    K.foot(s); K.counter(s, P.profiles);
  }
}
