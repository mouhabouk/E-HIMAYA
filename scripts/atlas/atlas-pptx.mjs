// The flowchart atlas as a PowerPoint deck (Yamen, 2026-11-14), in the template of the mind maps deck
// (scripts/tracking/deck-kit.mjs): the style of the «خوارزمية ء-حماية» page, a night set and a day set with a switch.
//
//   node scripts/atlas/atlas-pptx.mjs <atlas-dir> <out.pptx>          (DECK_SETS=day for the day set alone)
//
// Read from the atlas the same run built (<atlas-dir>/index.html and its shots/): a cover, a table of the six chapters,
// then per chapter its act slide and, for every screen, tab and window, its flowchart in the standard shapes (start or
// end, input, process, decision) that plays step by step, beside its functional card: what it is for, what it adds,
// who opens it, the tables it touches, its calls to the server. A click on a step or on the thumbnail opens the
// screenshot full size with what the user sees and does there. The link cards of each chapter close it.
import {readFileSync, existsSync} from 'node:fs';
import {join, resolve} from 'node:path';
import {sharp, hex, ind, SYSTEM, DISP, DISPM, MONO, MODES, WORD, WORD_AR, deck, finish} from '../tracking/deck-kit.mjs';

const [dir, out] = process.argv.slice(2);
if (!dir || !out) { console.error('usage: atlas-pptx.mjs <atlas-dir> <out.pptx>'); process.exit(2); }
const html = readFileSync(join(resolve(dir), 'index.html'), 'utf8');
const blob = html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/);
if (!blob) throw new Error('no atlas data in ' + dir);
const {meta, screens: S} = JSON.parse(blob[1].replace(/<\\\//g, '</'));

// ---------------------------------------------------------------- 1. the screenshots, made lighter for the deck
// a desktop page is cut to its first screen (16:10), a phone screen kept whole up to 9:19.5
const SHOT = {};
for (const sc of S) {
  if (!sc.shot) continue;
  const f = join(resolve(dir), sc.shot);
  if (!existsSync(f)) continue;
  const im = sharp(f), m = await im.metadata();
  const ar = sc.phone ? Math.min(m.height / m.width, 2.17) : Math.min(m.height / m.width, 0.625);
  const buf = await im.extract({left: 0, top: 0, width: m.width, height: Math.round(m.width * ar)})
    .resize({width: sc.phone ? 520 : 1280}).jpeg({quality: 70}).toBuffer();
  SHOT[sc.id] = {data: 'image/jpeg;base64,' + buf.toString('base64'), ar};
}

// ---------------------------------------------------------------- 2. plan
const SAMPLE = +process.env.ATLAS_SAMPLE || 0;   // a few cards per chapter, to look at the deck quickly
const CH = Object.entries(meta.chapters).map(([key, name], i) => ({key, name: name.replace(/^\d+\.\s*/, ''), i,
  cards: S.filter(s => s.chap === key).filter((s, j, a) => !SAMPLE || j < SAMPLE || j === a.length - 1)}));
const PAL = ['#E8590C', '#1F9D55', '#7B3FD1', '#0E8FA8', '#D6336C', '#C9A24A', '#2F6FE0', '#B5651D'];
const plan = [];
const add = (t, o = {}) => { plan.push({t, ...o}); return plan.length; };
const P = {cover: add('cover'), toc: add('toc')};
for (const ch of CH) {
  ch.slide = add('chapter');
  for (const c of ch.cards) { c.slide = add('screen'); if (SHOT[c.id]) c.shotSlide = add('shot'); }
}
P.end = add('end');
const N = plan.length;
const byId = Object.fromEntries(S.map(s => [s.id, s]));
const tables = new Set(S.flatMap(s => s.tables || [])), calls = new Set(S.flatMap(s => (s.api || []).map(a => a.verb + ' ' + a.path)));

const k = deck('أطلس ء-حماية: المخططات الانسيابية', N, P.toc), {pres, A, link, text, shape, image, panel, button, crumb, title, counter, figure} = k;
let C, MODE;
// the standard shapes of a flowchart, and the colour of each kind in both sets
const KIND = {
  term: {shape: () => pres.shapes.ROUNDED_RECTANGLE, r: 0.26, name: 'بداية أو نهاية', col: () => C.gold},
  io: {shape: () => pres.shapes.PARALLELOGRAM, name: 'إدخال', col: () => C.teal},
  proc: {shape: () => pres.shapes.ROUNDED_RECTANGLE, r: 0.05, name: 'معالجة', col: () => (MODE === 'night' ? '8FA8FF' : '2F55C8')},
  dec: {shape: () => pres.shapes.DIAMOND, name: 'قرار', col: () => (MODE === 'night' ? 'FFC933' : 'B7791F')},
};
const who = c => c.who?.length ? c.who.join('، ')
  : Object.entries(c.access || {}).filter(([, v]) => v).map(([p]) => meta.personas[p] || p).join('، ') || 'مدير النظام';

// ---------------------------------------------------------------- 3. the slides, once per colour set
for (const mode of MODES) {
k.set(mode); MODE = mode; C = k.C;

// cover: the four standard shapes as a small flowchart beside the hero of the page
{
  const s = k.slide(P.cover, {emblem: false});
  const steps = [['term', 'بلاغ أو طلب يصل'], ['io', 'إدخال المعطيات'], ['proc', 'معالجة في الشاشة'], ['dec', 'قرار؟'], ['term', 'يُحفظ ويُسجَّل']];
  const x = 1.35, w = 3.4, h = 0.62, gap = 1.12, y0 = 0.95;
  k.box(s, 0.55, 0.55, 5.0, 6.4);
  steps.forEach(([t, l], i) => {
    const y = y0 + i * gap, kd = KIND[t], d = 300 + i * 380, hh = t === 'dec' ? 0.9 : h, yy = t === 'dec' ? y - 0.14 : y;
    A(shape(s, kd.shape(), {x, y: yy, w, h: hh, ...(kd.r ? {rectRadius: kd.r} : {}), fill: {color: C.panel}, line: {color: kd.col(), width: 2}}), 'zoom', d, 400);
    A(text(s, l, {x, y: yy, w, h: hh, align: 'center', fontSize: 14, bold: true}), 'zoom', d, 400);
    if (i < steps.length - 1) A(shape(s, pres.shapes.LINE, {x: x + w / 2, y: yy + hh, w: 0, h: y0 + (i + 1) * gap - (yy + hh) - (steps[i + 1][0] === 'dec' ? 0.14 : 0),
      line: {color: C.gold, width: 2, endArrowType: 'triangle'}}), 'wipe', d + 250, 300, 'd');
  });
  A(text(s, 'نعم', {x: x + w / 2 + 0.08, y: y0 + 4 * gap - 0.4, w: 0.5, h: 0.25, fontSize: 11, bold: true, color: C.gold}), 'fade', 2000, 300);
  A(text(s, `e-HIMAYA · FLOWCHART ATLAS · ${meta.built}`, {x: 6.3, y: 0.42, w: 5.5, h: 0.28, fontSize: 10, fontFace: MONO, color: C.gold, rtlMode: false, lang: 'en-US', align: 'right', charSpacing: 2}), 'fade', 0, 600);
  A(k.emblem(s, 11.93, 0.3, 0.9), 'zoom', 0, 600);
  A(text(s, 'الديوان الوطني للحماية المدنية', {x: 6.3, y: 0.72, w: 5.5, h: 0.4, fontSize: 15, bold: true}), 'fade', 150, 600);
  if (MODE === 'day') shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 9.48, y: 1.22, w: 3.5, h: 3.2 * WORD_AR + 0.2, rectRadius: 0.16, fill: {color: C.root}});
  A(image(s, {data: WORD, x: 9.63, y: 1.32, w: 3.2, h: 3.2 * WORD_AR, altText: 'ء-حماية E-HIMAYA'}), 'fade', 300, 900);
  A(text(s, [{text: 'أطلس ', options: {color: C.ink}}, {text: 'المخططات الانسيابية', options: {color: C.gold}}],
    {x: 6.0, y: 2.85, w: 6.83, h: 0.85, fontSize: 38, fontFace: DISP, bold: true}), 'fade', 450, 800);
  A(text(s, SYSTEM, {x: 6.0, y: 3.68, w: 6.83, h: 0.9, fontSize: 17, fontFace: DISPM, valign: 'top', lineSpacingMultiple: 1.05}), 'fade', 600, 800);
  A(text(s, `كل شاشة من شاشات المنظومة، وكل تبويب ونافذة فيها، في مخطط انسيابي بالأشكال المعيارية يتحرك خطوة بخطوة، مع بطاقتها الوظيفية ولقطتها. اضغط على أي خطوة لترى الشاشة.`,
    {x: 6.0, y: 4.62, w: 6.83, h: 0.55, fontSize: 11.5, color: C.mute, valign: 'top'}), 'fade', 750, 700);
  [[CH.length, 'فصول'], [S.length, 'بطاقة'], [tables.size, 'جدولا'], [calls.size, 'عملية في الواجهة']]
    .forEach(([v, l], i) => figure(s, 12.83 - (i + 1) * 1.7 + 0.15, 5.35, 1.55, v, l, 850 + i * 150));
  A(button(s, 'ابدأ العرض ‹', 11.13, 6.55, 1.7, P.toc, true)[0], 'zoom', 1500, 400);
  A(s._slideObjects.at(-1).options, 'zoom', 1500, 400);
  counter(s, P.cover);
}

// table of contents: the six chapters
{
  const s = k.slide(P.toc);
  crumb(s, 'ء-حماية · أطلس المخططات الانسيابية'); A(title(s, 'فصول الأطلس'), 'fade', 0, 500);
  button(s, 'الخاتمة', 0.5, 0.6, 1.1, P.end); button(s, 'الغلاف', 1.75, 0.6, 1.0, P.cover);
  const cw = 3.95, ch = 2.45, gx = 0.24, gy = 0.25;
  CH.forEach((c, i) => {
    const col = i % 3, row = Math.floor(i / 3), x = 12.83 - (col + 1) * cw - col * gx, y = 1.5 + row * (ch + gy), dl = 200 + i * 140;
    const color = hex(PAL[i % PAL.length]), surf = {};
    c.cards.forEach(x2 => { surf[x2.surface] = (surf[x2.surface] || 0) + 1; });
    A(panel(s, x, y, cw, ch, {...link(c.slide)}), 'fade', dl, 400);
    A(text(s, ind(i + 1), {x: x + cw - 1.0, y: y + 0.15, w: 0.8, h: 0.8, fontSize: 40, fontFace: DISP, bold: true, color: C.gold, ...link(c.slide)}), 'zoom', dl, 400);
    A(shape(s, pres.shapes.LINE, {x: x + 0.25, y: y + 1.0, w: cw - 0.5, h: 0, line: {color, width: 2}}), 'wipe', dl + 150, 400, 'l');
    A(text(s, c.name, {x: x + 0.25, y: y + 1.1, w: cw - 0.5, h: 0.62, fontSize: 15, fontFace: DISPM, valign: 'top', fit: 'shrink', ...link(c.slide)}), 'fade', dl, 400);
    A(text(s, Object.entries(surf).map(([sf, n]) => `${meta.surfaces[sf] || sf}: ${n}`).join(' · '),
      {x: x + 0.25, y: y + 1.78, w: cw - 0.5, h: 0.5, fontSize: 10, color: C.mute, valign: 'top', fit: 'shrink', ...link(c.slide)}), 'fade', dl + 100, 400);
    A(text(s, `${c.cards.length}`, {x: x + 0.25, y: y + 0.25, w: 1.2, h: 0.5, fontSize: 24, fontFace: MONO, bold: true, align: 'left', ...link(c.slide)}), 'fade', dl + 100, 400);
  });
  counter(s, P.toc);
}

// the act of a chapter: its numeral, its name, its groups each a link to their first card
function chapterSlide(c) {
  const s = k.slide(c.slide), color = hex(PAL[c.i % PAL.length]);
  crumb(s, `الفصل ${c.i + 1} من ${CH.length}`);
  button(s, 'ابدأ الفصل ‹', 0.5, 0.6, 1.5, c.cards[0]?.slide, true); button(s, 'الفهرس', 2.15, 0.6, 1.0, P.toc);
  A(text(s, ind(c.i + 1), {x: 9.33, y: 0.8, w: 3.5, h: 1.55, fontSize: 96, fontFace: DISP, bold: true, color: C.gold}), 'fade', 0, 600);
  A(text(s, c.name, {x: 6.93, y: 2.35, w: 5.9, h: 1.0, fontSize: 30, fontFace: DISPM, valign: 'top', fit: 'shrink'}), 'fade', 200, 600);
  const surf = {}; c.cards.forEach(x => { surf[x.surface] = (surf[x.surface] || 0) + 1; });
  A(text(s, `${c.cards.length} بطاقة: ` + Object.entries(surf).map(([sf, n]) => `${meta.surfaces[sf] || sf} ${n}`).join('، ') + '.',
    {x: 6.93, y: 3.4, w: 5.9, h: 0.6, fontSize: 14, color: C.mute, valign: 'top', fit: 'shrink'}), 'fade', 350, 600);
  const used = [...new Set(c.cards.flatMap(x => x.tables || []))].length;
  figure(s, 11.13, 4.4, 1.7, c.cards.filter(x => SHOT[x.id]).length, 'لقطة شاشة', 500);
  figure(s, 9.28, 4.4, 1.7, used, 'جدولا', 650);
  figure(s, 7.43, 4.4, 1.7, new Set(c.cards.flatMap(x => (x.api || []).map(a => a.verb + a.path))).size, 'عملية', 800);
  // the groups of the chapter, each a link to its first card
  const groups = []; for (const x of c.cards) if (!groups.some(g => g.name === x.group)) groups.push({name: x.group, first: x.slide, n: c.cards.filter(y => y.group === x.group).length});
  A(panel(s, 0.5, 1.4, 6.0, 5.45, {rectRadius: 0.2}), 'fade', 300, 500);
  A(text(s, 'أجزاء الفصل', {x: 0.8, y: 1.58, w: 5.4, h: 0.4, fontSize: 17, fontFace: DISPM, color: C.gold}), 'fade', 400, 500);
  const shown = groups.slice(0, 12), rowH = Math.min(0.42, 4.6 / Math.max(1, shown.length));
  shown.forEach((g, j) => {
    const y = 2.1 + j * rowH, dl = 500 + j * 90;
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 5.95, y: y + rowH / 2 - 0.07, w: 0.14, h: 0.14, rectRadius: 0.03, fill: {color}}), 'zoom', dl, 300);
    A(text(s, g.name.replace(/^[^·]*·\s*/, ''), {x: 1.4, y, w: 4.45, h: rowH, fontSize: 12.5, fit: 'shrink', ...link(g.first)}), 'fade', dl, 400);
    A(text(s, String(g.n), {x: 0.8, y, w: 0.5, h: rowH, fontSize: 11, fontFace: MONO, color: C.mute, align: 'left'}), 'fade', dl, 400);
  });
  if (groups.length > shown.length) text(s, `و${groups.length - shown.length} أجزاء أخرى في الفصل.`, {x: 0.8, y: 6.45, w: 5.4, h: 0.28, fontSize: 10, color: C.mute});
  counter(s, c.slide);
}

// a card: its flowchart, playing step by step, beside its functional card
function screenSlide(c, ch, j) {
  const s = k.slide(c.slide), nx = ch.cards[j + 1], pv = ch.cards[j - 1];
  const to = c.shotSlide;
  crumb(s, `الفصل ${ch.i + 1} · ${c.group} · ${j + 1} من ${ch.cards.length}`);
  A(title(s, c.surface === 'link' ? 'الترابط' : 'المخطط الانسيابي والبطاقة'), 'fade', 0, 400);
  button(s, 'الفصل', 0.5, 0.6, 0.9, ch.slide);
  button(s, '› السابق', 1.55, 0.6, 1.0, pv ? pv.slide : ch.slide);
  button(s, 'التالي ‹', 2.7, 0.6, 1.0, nx ? nx.slide : (CH[ch.i + 1]?.slide || P.end), true);
  // the flowchart: one column up to seven steps, two (right then left) beyond
  k.box(s, 0.4, 1.35, 7.25, 5.5);
  const F = c.flow || [], cols = F.length > 7 ? 2 : 1, per = Math.ceil(F.length / cols);
  const gap = Math.min(0.78, 5.1 / per), nh = Math.min(0.56, gap - 0.2), nw = cols === 2 ? 3.0 : 4.2;
  const colX = q => cols === 2 ? (q === 0 ? 4.35 : 0.75) : 0.4 + (7.25 - nw) / 2;
  const pos = F.map((_, i) => { const q = Math.floor(i / per), r = i % per; return {x: colX(q), y: 1.6 + r * gap + (gap - nh) / 2 - 0.1, q, r}; });
  F.forEach((n, i) => {
    const kd = KIND[n.t] || KIND.proc, {x, y} = pos[i], d = 300 + i * 360, h = n.t === 'dec' ? nh + 0.14 : nh, yy = n.t === 'dec' ? y - 0.07 : y;
    const lk = to && n.r != null ? link(to) : {};
    A(shape(s, kd.shape(), {x, y: yy, w: nw, h, ...(kd.r ? {rectRadius: Math.min(kd.r, h / 2)} : {}), fill: {color: C.panel}, line: {color: kd.col(), width: 2}, ...lk}), 'zoom', d, 400);
    A(text(s, [{text: n.l || '', options: {bold: true, fontSize: 11.5, color: C.ink, breakLine: !!n.s}}, ...(n.s ? [{text: n.s, options: {fontSize: 8.5, color: C.mute}}] : [])],
      {x: x + (n.t === 'io' ? 0.25 : 0.12), y: yy, w: nw - (n.t === 'io' ? 0.5 : 0.24), h, align: 'center', fit: 'shrink', ...lk}), 'zoom', d, 400);
    if (i < F.length - 1) {
      const p2 = pos[i + 1];
      if (p2.q === pos[i].q) A(shape(s, pres.shapes.LINE, {x: x + nw / 2, y: yy + h, w: 0, h: Math.max(0.05, p2.y - (yy + h) - (F[i + 1].t === 'dec' ? 0.07 : 0)),
        line: {color: C.gold, width: 1.75, endArrowType: 'triangle'}}), 'wipe', d + 230, 250, 'd');
      else {   // from the foot of the right column to the head of the left one
        const x1 = x + nw / 2, y1 = yy + h, x2 = p2.x + nw / 2, y2 = p2.y, ym = Math.max(y1, 6.55) + 0.12;
        A(shape(s, pres.shapes.CUSTOM_GEOMETRY, {x: x2, y: 1.35 + 0.08, w: x1 - x2, h: ym - 1.43,
          points: [{x: x1 - x2, y: y1 - 1.43}, {x: x1 - x2, y: ym - 1.43}, {x: (x1 - x2) / 2, y: ym - 1.43}, {x: (x1 - x2) / 2, y: 0.02}, {x: 0, y: 0.02}, {x: 0, y: y2 - 1.43}],
          line: {color: C.gold, width: 1.5, dashType: 'dash', endArrowType: 'triangle'}}), 'fade', d + 230, 400);
      }
    }
  });
  // the legend of the shapes, under the box
  let lx = 7.6;
  for (const t of ['term', 'io', 'proc', 'dec']) {
    const kd = KIND[t], w = 0.4 + kd.name.length * 0.085; lx -= w;
    shape(s, kd.shape(), {x: lx + w - 0.32, y: 7.06, w: 0.28, h: 0.17, ...(kd.r ? {rectRadius: Math.min(kd.r, 0.085)} : {}), fill: {color: C.panel}, line: {color: kd.col(), width: 1.25}});
    text(s, kd.name, {x: lx, y: 7.02, w: w - 0.38, h: 0.25, fontSize: 9, color: C.mute});
    lx -= 0.12;
  }
  // the card
  const cx0 = 7.85, cw = 4.98, d0 = 250, L = (t, o) => text(s, t, {x: cx0 + 0.25, w: cw - 0.5, ...o});
  A(panel(s, cx0, 1.35, cw, 5.5), 'fade', d0, 500);
  A(L(`${c.surfaceName || meta.surfaces[c.surface] || ''}${c.locked ? ' · تُفتح على المستوى الجهوي' : ''}`, {y: 1.5, h: 0.26, fontSize: 10.5, bold: true, color: C.gold, fit: 'shrink'}), 'fade', d0 + 100, 400);
  A(L(c.title, {y: 1.76, h: 0.62, fontSize: 18, fontFace: DISPM, valign: 'top', fit: 'shrink'}), 'fade', d0 + 150, 450);
  if (c.surface === 'link') {
    const items = (c.functional || []).slice(0, 5).map((t, i, a) => ({text: t, options: {bullet: true, breakLine: i < a.length - 1, paraSpaceAfter: 4}}));
    A(L(items.length ? items : c.purpose, {y: 2.45, h: 2.6, fontSize: 11, valign: 'top', fit: 'shrink'}), 'fade', d0 + 300, 500);
    const sideLinks = (lst, lab, y) => {
      const xs = (lst || []).map(x => byId[x.id]).filter(Boolean).slice(0, 5);
      if (!xs.length) return;
      L(lab, {y, h: 0.24, fontSize: 10, bold: true, color: C.gold});
      L(xs.map((x, i) => ({text: x.item || x.title, options: {...link(x.slide), breakLine: false}})).flatMap((r, i) => i ? [{text: ' · ', options: {}}, r] : [r]),
        {y: y + 0.25, h: 0.5, fontSize: 10.5, color: C.teal, valign: 'top', fit: 'shrink'});
    };
    sideLinks(c.appScreens, 'شاشات التطبيق', 5.15); sideLinks(c.boardScreens, 'شاشات اللوحة', 5.9);
    counter(s, c.slide);
    return;
  }
  A(L(c.purpose || '', {y: 2.42, h: 1.0, fontSize: 12, valign: 'top', fit: 'shrink'}), 'fade', d0 + 300, 500);
  if (c.value) {
    A(L('ما تضيفه', {y: 3.45, h: 0.24, fontSize: 10.5, bold: true, color: C.gold}), 'fade', d0 + 400, 400);
    A(L(c.value, {y: 3.69, h: 0.62, fontSize: 11.5, valign: 'top', fit: 'shrink'}), 'fade', d0 + 450, 400);
  }
  A(L(`من يفتحها: ${who(c)}`, {y: 4.34, h: 0.42, fontSize: 10, color: C.mute, valign: 'top', fit: 'shrink'}), 'fade', d0 + 500, 400);
  if ((c.tables || []).length) A(L(c.tables.slice(0, 6).join('   ') + (c.tables.length > 6 ? `   +${c.tables.length - 6}` : ''),
    {y: 4.78, h: 0.36, fontSize: 9, fontFace: MONO, color: C.teal, rtlMode: false, lang: 'en-US', valign: 'top', fit: 'shrink'}), 'fade', d0 + 550, 400);
  // the thumbnail, a link to the screenshot; beside it, the calls to the server
  if (SHOT[c.id]) {
    const th = 1.5, tw = c.phone ? th / SHOT[c.id].ar : Math.min(2.6, th / SHOT[c.id].ar), tx = cx0 + 0.25;
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: tx - 0.03, y: 5.17, w: tw + 0.06, h: th + 0.06, rectRadius: 0.05, fill: {color: C.deck}, line: {color: C.teal, width: 1}, ...link(to)}), 'zoom', d0 + 650, 400);
    A(image(s, {data: SHOT[c.id].data, x: tx, y: 5.2, w: tw, h: th, altText: c.title, ...link(to)}), 'zoom', d0 + 650, 400);
    const ops = (c.api || []).length, writes = (c.api || []).some(a => a.verb !== 'GET');
    A(text(s, [{text: 'اضغط على اللقطة أو على خطوة لتكبيرها', options: {bold: true, color: C.gold, breakLine: true}},
      {text: ops ? `${ops} نداء للخادم · ${writes ? 'تكتب في القاعدة وتُسجَّل' : 'قراءة فقط'}` : 'تُعرض دون نداء للخادم', options: {color: C.mute}}],
      {x: tx + tw + 0.2, y: 5.2, w: cx0 + cw - 0.25 - (tx + tw + 0.2), h: th, fontSize: 10, valign: 'bottom', fit: 'shrink'}), 'fade', d0 + 700, 400);
  }
  counter(s, c.slide);
}

// the screenshot full size, with what the user sees and does there
function shotSlide(c, ch) {
  const s = k.slide(c.shotSlide), sh = SHOT[c.id];
  crumb(s, `الفصل ${ch.i + 1} · ${c.group}`);
  A(title(s, c.title), 'fade', 0, 400);
  button(s, 'المخطط', 0.5, 0.6, 1.0, c.slide, true);
  const bh = 5.45, iw = c.phone ? bh / sh.ar : Math.min(8.6, bh / sh.ar), ih = c.phone ? bh : iw * sh.ar;
  A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 0.45, y: 1.32, w: iw + 0.1, h: ih + 0.1, rectRadius: 0.08, fill: {color: C.deck}, line: {color: C.teal, width: 1.25}}), 'fade', 100, 500);
  A(image(s, {data: sh.data, x: 0.5, y: 1.37, w: iw, h: ih, altText: c.title, ...link(c.slide)}), 'zoom', 200, 600);
  const cx0 = 0.5 + iw + 0.35, cw = 12.83 - cx0, L = (t, o) => text(s, t, {x: cx0 + 0.25, w: cw - 0.5, ...o});
  A(panel(s, cx0, 1.32, cw, 5.5), 'fade', 300, 500);
  const where = c.route || c.path || c.page || '';
  if (where) A(L(where, {y: 1.5, h: 0.32, fontSize: 11, fontFace: MONO, color: C.teal, rtlMode: false, lang: 'en-US', fit: 'shrink'}), 'fade', 400, 400);
  A(L('وظيفة الشاشة', {y: 1.95, h: 0.3, fontSize: 12, bold: true, color: C.gold}), 'fade', 500, 400);
  A(L(c.purpose || '', {y: 2.25, h: 1.25, fontSize: 12.5, valign: 'top', fit: 'shrink'}), 'fade', 550, 500);
  const steps = (c.steps?.length ? c.steps : (c.flow || []).filter(n => n.t !== 'term').map(n => n.l)).slice(0, 8);
  if (steps.length) {
    A(L('ما يراه المستخدم وما يفعله', {y: 3.6, h: 0.3, fontSize: 12, bold: true, color: C.gold}), 'fade', 650, 400);
    A(L(steps.map((t, i) => ({text: t, options: {bullet: true, breakLine: i < steps.length - 1}})), {y: 3.92, h: 2.4, fontSize: 11.5, valign: 'top', fit: 'shrink'}), 'fade', 700, 500);
  }
  A(L('لقطة من أطلس الشاشات، تُحدَّث مع كل تحيين.', {y: 6.4, h: 0.26, fontSize: 9.5, color: C.mute}), 'fade', 800, 400);
  counter(s, c.shotSlide);
}

for (const ch of CH) {
  chapterSlide(ch);
  ch.cards.forEach((c, j) => { screenSlide(c, ch, j); if (c.shotSlide) shotSlide(c, ch); });
}

// the close: the figures again, each chapter a link
{
  const s = k.slide(P.end);
  crumb(s, 'ء-حماية · الخاتمة'); A(title(s, 'من الشاشة إلى القرار'), 'fade', 0, 500);
  button(s, 'الفهرس', 0.5, 0.6, 1.0, P.toc, true); button(s, 'الغلاف', 1.65, 0.6, 1.0, P.cover);
  A(text(s, 'كل بطاقة في هذا الأطلس مأخوذة من المنظومة نفسها عند آخر تحيين: لقطة الشاشة، والجداول التي تقرأ منها أو تكتب فيها، ومن يفتحها.',
    {x: 3.4, y: 1.25, w: 8.65, h: 0.55, fontSize: 13, color: C.mute, valign: 'top'}), 'fade', 200, 500);
  const max = Math.max(...CH.map(c => c.cards.length));
  CH.forEach((c, i) => {
    const y = 2.1 + i * 0.62, dl = 300 + i * 150, bw = 7.6 * c.cards.length / max;
    A(text(s, `${ind(i + 1)}  ${c.name}`, {x: 8.8, y, w: 4.03, h: 0.45, fontSize: 13, fontFace: DISPM, fit: 'shrink', ...link(c.slide)}), 'fade', dl, 400);
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 8.6 - bw, y: y + 0.12, w: bw, h: 0.22, rectRadius: 0.11, fill: {color: hex(PAL[i % PAL.length])}, ...link(c.slide)}), 'wipe', dl + 120, 600, 'l');
    A(text(s, String(c.cards.length), {x: 8.6 - bw - 0.65, y, w: 0.55, h: 0.45, fontSize: 12, fontFace: MONO, color: C.mute, align: 'left'}), 'fade', dl + 300, 400);
  });
  counter(s, P.end);
}
}

// ---------------------------------------------------------------- 4. write, with native transitions and animations
const TRANS = {cover: '<p:fade/>', toc: '<p:push dir="l"/>', chapter: '<p:push dir="l"/>', screen: '<p:fade/>', shot: '<p:fade/>', end: '<p:fade/>'};
const nAnim = await finish(k, out, n => TRANS[plan[(n - 1) % N].t]);
console.log(`${MODES.length * N} slides (${MODES.join(' and ')}), ${nAnim} animations → ${out}`);
