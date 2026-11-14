// The local AI tools of e-Himaya as a PowerPoint deck (Yamen, 2026-11-14): every AI tool the system runs, where it
// works along the chain «من التبليغ إلى أخذ القرار», what the room does without it and with it, its figures, its
// safeguard, and why running it on the Office's own servers makes the difference.
//
//   node scripts/tracking/ai-tools-pptx.mjs <out.pptx>          (DECK_SETS=day for the day set alone)
//
// The same slides are part of the system presentation (pitch-pptx.mjs). The look, the colour sets and the writer are
// the deck kit's (deck-kit.mjs); the content is ai-tools-data.mjs.
import {createKit, DISP, DISPM, MONO, SYSTEM} from './deck-kit.mjs';
import {planAi, drawAi, TOOLS} from './ai-tools-slides.mjs';

const [out] = process.argv.slice(2);
if (!out) { console.error('usage: ai-tools-pptx.mjs <out.pptx>'); process.exit(2); }

const K = await createKit({title: 'أدوات الذكاء الاصطناعي المحلية في ء-حماية', footer: 'ء-حماية · الذكاء الاصطناعي يعمل داخل خوادم الديوان'});
const P = {cover: K.add('cover')};
const AI = planAi(K);
P.end = K.add('end');
K.home = AI.map;

for (const mode of K.MODES) {
  K.begin(mode);
  const {pres, A} = K, C = K.C;
  // cover: the hero beside the tools in orbit round the system, each a link to its slide
  {
    const s = K.newSlide(P.cover), cx = 3.2, cy = 3.75, R = 2.35;
    A(K.shape(s, pres.shapes.OVAL, {x: cx - R - 0.42, y: cy - R - 0.42, w: 2 * (R + 0.42), h: 2 * (R + 0.42), line: {color: C.gold, width: 1.5, dashType: 'sysDot', transparency: 55}}), 'fade', 0, 900);
    A(K.shape(s, pres.shapes.OVAL, {x: cx - R, y: cy - R, w: 2 * R, h: 2 * R, line: {color: C.edge, width: 0.75, dashType: 'dash'}}), 'fade', 0, 900);
    TOOLS.forEach((t, i) => {
      const a = -Math.PI / 2 + i * 2 * Math.PI / TOOLS.length, x = cx + R * Math.cos(a), y = cy + R * Math.sin(a), r = 0.27, col = K.tone(t.st.tone), d0 = 300 + i * 90;
      const x0 = cx + 1.05 * Math.cos(a), y0 = cy + 1.05 * Math.sin(a), x1 = x - r * Math.cos(a), y1 = y - r * Math.sin(a);
      A(K.shape(s, pres.shapes.LINE, {x: Math.min(x0, x1), y: Math.min(y0, y1), w: Math.max(0.01, Math.abs(x1 - x0)), h: Math.max(0.01, Math.abs(y1 - y0)),
        flipH: (Math.cos(a) < 0) !== (Math.sin(a) < 0), line: {color: col, width: 1.25, transparency: 40}}), 'fade', d0, 400);
      A(K.shape(s, pres.shapes.OVAL, {x: x - r, y: y - r, w: 2 * r, h: 2 * r, fill: {color: col}, line: {color: C.bg, width: 2}, ...K.link(AI.tools[i])}), 'zoom', d0 + 100, 400);
      A(K.text(s, String(i + 1), {x: x - r, y: y - r, w: 2 * r, h: 2 * r, align: 'center', fontSize: 13, fontFace: MONO, bold: true, color: C.white, rtlMode: false, ...K.link(AI.tools[i])}), 'zoom', d0 + 100, 400);
    });
    A(K.shape(s, pres.shapes.OVAL, {x: cx - 1.05, y: cy - 1.05, w: 2.1, h: 2.1, fill: {color: C.root}, line: {color: C.gold, width: 3}, ...K.link(AI.map)}), 'zoom', 0, 600);
    A(K.text(s, [{text: 'ء-حماية', options: {fontSize: 24, fontFace: DISP, bold: true, color: C.white, breakLine: true}}, {text: `${TOOLS.length} أداة محلية`, options: {fontSize: 12, color: C.gold}}],
      {x: cx - 1.05, y: cy - 0.6, w: 2.1, h: 1.2, align: 'center', ...K.link(AI.map)}), 'zoom', 0, 600);
    A(K.text(s, 'e-HIMAYA · LOCAL AI · 2026', {x: 6.6, y: 0.42, w: 5.2, h: 0.28, fontSize: 10, fontFace: MONO, color: C.gold, rtlMode: false, lang: 'en-US', align: 'right', charSpacing: 2}), 'fade', 0, 600);
    A(K.emblem(s, 11.93, 0.3, 0.9), 'zoom', 0, 600);
    A(K.text(s, 'الديوان الوطني للحماية المدنية', {x: 6.6, y: 0.72, w: 5.2, h: 0.4, fontSize: 15, bold: true, color: C.ink}), 'fade', 150, 600);
    K.wordmark(s, 9.63, 1.32, 3.2);
    A(K.text(s, [{text: 'ذكاء اصطناعي ', options: {color: C.ink}}, {text: 'محلي', options: {color: C.gold}}], {x: 6.3, y: 2.95, w: 6.53, h: 0.85, fontSize: 40, fontFace: DISP, bold: true}), 'fade', 450, 800);
    A(K.text(s, 'أدوات الذكاء الاصطناعي المعتمدة في المنظومة، وما تضيفه في كل مرحلة من التبليغ إلى أخذ القرار',
      {x: 6.3, y: 3.82, w: 6.53, h: 0.85, fontSize: 17, lineSpacingMultiple: 1.05, fontFace: DISPM, color: C.ink, valign: 'top'}), 'fade', 600, 800);
    A(K.text(s, SYSTEM, {x: 6.3, y: 4.75, w: 6.53, h: 0.55, fontSize: 11.5, color: C.mute, valign: 'top'}), 'fade', 750, 700);
    K.button(s, 'لماذا محلية؟', 10.73, 5.55, 2.1, AI.why, true);
    K.button(s, 'خريطة الأدوات', 8.48, 5.55, 2.1, AI.map);
    A(K.text(s, 'اضغط على أي رقم للانتقال إلى أداته.', {x: 6.3, y: 6.1, w: 6.53, h: 0.3, fontSize: 10.5, color: C.mute}), 'fade', 900, 600);
  }
  drawAi(K, AI, {after: P.end});
  // the difference, in one slide
  {
    const s = K.newSlide(P.end);
    K.crumb(s, 'ء-حماية · الخلاصة'); K.title(s, 'الفارق في ثلاث جمل');
    const lines = [
      ['أسرع', 'الصوت والصورة والنص تُقرأ لحظة وصولها: البلاغ يُفرز، والحريق يُرى، والتكرار يُجمع، قبل أن يفتحها أحد.'],
      ['أدق', 'كل أداة تتعلم من تصحيحات الأعوان وقرارات القادة، بأرقام معلنة في بطاقة نموذجها وأهداف تُقاس.'],
      ['أأمن', 'لا يغادر بلاغ ولا صوت ولا صورة خوادم الديوان، والأدوات تعمل حين ينقطع الإنترنت، والقرار يبقى للإنسان.'],
    ];
    lines.forEach(([h, b], k) => {
      const y = 1.6 + k * 1.55, dl = 300 + k * 300;
      A(K.shape(s, pres.shapes.LINE, {x: 0.5, y, w: 12.33, h: 0, line: {color: C.gold, width: 1.5}}), 'wipe', dl, 600, 'l');
      A(K.text(s, h, {x: 10.3, y: y + 0.15, w: 2.53, h: 1.1, fontSize: 40, fontFace: DISP, bold: true, color: C.gold}), 'fade', dl + 150, 500);
      A(K.text(s, b, {x: 0.5, y: y + 0.2, w: 9.6, h: 1.05, fontSize: 17, bold: true, color: C.ink, valign: 'middle'}), 'fade', dl + 250, 500);
    });
    A(K.text(s, `${TOOLS.length} أداة · نماذج مفتوحة المصدر برخص MIT و Apache و BSD · تعمل كلها على خوادم الديوان`, {x: 0.5, y: 6.35, w: 12.33, h: 0.32, fontSize: 12, color: C.mute, align: 'center'}), 'fade', 1400, 500);
    K.button(s, 'الخريطة', 0.5, 0.6, 1.0, AI.map, true); K.button(s, 'الغلاف', 1.62, 0.6, 1.0, P.cover);
    K.counter(s, P.end);
  }
}

await K.write(out, {cover: '<p:fade/>', why: '<p:push dir="l"/>', aimap: '<p:push dir="l"/>', tool: '<p:fade/>', compare: '<p:push dir="l"/>',
  guards: '<p:push dir="l"/>', profiles: '<p:push dir="l"/>', end: '<p:fade/>'});
