// The mind maps as a PowerPoint deck (Yamen, 2026-11-14): the same slides as mindmaps-deck.html, drawn with native
// shapes so every colour, text and curve stays editable, the same palette, and native entrance animations and slide
// transitions whose effect, duration and delay can be changed in PowerPoint's animation pane.
//
//   node scripts/tracking/mindmap-pptx.mjs <mindmaps-deck.html> <out.pptx> [atlas-shots-dir]
//
// Style (Yamen, 2026-11-14): the one of the «خوارزمية ء-حماية» page, a night operations-room blueprint: the night
// ground with its grid, Reem Kufi for titles, IBM Plex Sans Arabic for text, IBM Plex Mono for figures and routes, gold
// for the accents and the dark set of the category colours. A click on an element opens its functional card; when the
// element speaks of dashboard screens, the card shows their screenshots from the atlas, and a click on one opens it
// full size with what the screen is for and what it adds.
//
// The layout of every map is read from the deck page itself (Playwright), so the PowerPoint follows the HTML maps on
// every run of scripts/refresh-all.sh. Branches link to their own slide, and each map has a folded and an unfolded
// version linked to each other, so folding and moving between elements work in slide show.
// The cover carries the Office's emblem and the system's full title; every slide sits in the royal blue frame of the
// system with a gold hairline; the text uses IBM Plex Sans Arabic, whose files are copied to <out-dir>/fonts.
import {createRequire} from 'node:module';
import {readFileSync, existsSync} from 'node:fs';
import {join, resolve} from 'node:path';
import {sharp, hex, ind, SYSTEM, W, DISP, DISPM, MONO, MODES, WORD, WORD_AR, deck, finish} from './deck-kit.mjs';
const {chromium} = createRequire(import.meta.url)('playwright');

const [src, out, shotsDir] = process.argv.slice(2);
if (!src || !out) { console.error('usage: mindmap-pptx.mjs <mindmaps-deck.html> <out.pptx> [atlas-shots-dir]'); process.exit(2); }

// ---------------------------------------------------------------- 1. read the data and every map's layout
const browser = await chromium.launch();
const read = async colorScheme => {   // the maps as drawn in one colour set of the page
const page = await browser.newPage({viewport: {width: 1600, height: 1000}, colorScheme});
await page.goto('file://' + resolve(src));
await page.waitForTimeout(1500);
return page.evaluate(() => {
  const maps = {};
  for (const g of ['all', ...keys]) for (const fold of [true, false]) {
    model = build(g); step = -1; collapsed = new Set(fold ? model.kids.map(k => k.id) : []); render(false);
    const vp = document.getElementById('vp'), bb = vp.getBBox(), items = [];
    vp.querySelectorAll('path, rect, circle, text').forEach(e => {
      if (e.closest('defs')) return;
      const k = e.closest('[data-k]'), b = e.getBBox(), cs = getComputedStyle(e);
      items.push({tag: e.tagName, k: k ? +k.dataset.k : null, leaf: !!e.closest('g.leaf'), root: !!e.closest('g.node') && !k,
        d: e.getAttribute('d'), fill: e.getAttribute('fill') || cs.fill, stroke: e.getAttribute('stroke'), sw: +(e.getAttribute('stroke-width') || 0),
        op: +(e.getAttribute('opacity') || 1), glow: !!e.getAttribute('filter'), dash: !!e.getAttribute('stroke-dasharray'),
        text: e.tagName === 'text' ? e.textContent : '', fs: +(e.getAttribute('font-size') || parseFloat(cs.fontSize) || 13),
        bold: +(e.getAttribute('font-weight') || cs.fontWeight) >= 600, x: b.x, y: b.y, w: b.width, h: b.height,
        cx: +(e.getAttribute('cx') || 0), cy: +(e.getAttribute('cy') || 0), r: +(e.getAttribute('r') || 0)});
    });
    maps[g + (fold ? ':fold' : ':full')] = {bb: {x: bb.x, y: bb.y, w: bb.width, h: bb.height}, items,
      kids: model.kids.map(k => ({label: k.label, color: k.color, leaves: k.leaves.map(l => l.t), row: k.row || null, go: k.go || null}))};
  }
  const st = {}; for (const k in ST) st[k] = [ST[k][0], css(ST[k][1])];
  return {D, keys, ST: st, PAL, maps, groups: keys.map(k => ({k, name: D.groups[k], rows: byG(k)}))};
});
};
// the night deck reads the dark set, the day deck the light set (Yamen 2026-11-14: a day and night switch)
const X = await read('dark'), XL = await read('light');
await browser.close();
const {D, keys, PAL, groups} = X;
const SETS = {night: {maps: X.maps, ST: X.ST}, day: {maps: XL.maps, ST: XL.ST}};
let maps, ST;

// ---------------------------------------------------------------- 2. plan and helpers
const SZ = {S: 'صغير', M: 'متوسط', L: 'كبير', XL: 'كبير جدا'}, IMP = {4: 'حرجة', 3: 'عالية', 2: 'متوسطة', 1: 'منخفضة'};
const doneOf = rs => rs.filter(r => r.status === 'done').length;
const pct = (a, b) => b ? Math.round(100 * a / b) : 0;

// the atlas screenshots of the screens an element speaks of, made lighter for the deck
const SHOT = {};
if (shotsDir && existsSync(shotsDir)) {
  const file = p => join(shotsDir, (p.replace(/^\/|\/$/g, '').replace(/[/:]+/g, '-').replace(/-+/g, '-') || 'home') + '.jpg');
  // a screen the atlas account could not open (its page says so) is left out rather than shown as a refusal
  const denied = p => { const f = file(p).replace(/[/\\]shots[/\\]([^/\\]+)\.jpg$/, '/screens/$1.html');
    return existsSync(f) && readFileSync(f, 'utf8').includes('لا تملك صلاحية الوصول'); };
  for (const r of D.rows) for (const sc of r.screens || []) if (!(sc.p in SHOT) && existsSync(file(sc.p)) && !denied(sc.p)) {
    const buf = await sharp(file(sc.p)).resize({width: 1280}).jpeg({quality: 72}).toBuffer();
    const meta = await sharp(buf).metadata();
    SHOT[sc.p] = {data: 'image/jpeg;base64,' + buf.toString('base64'), ar: meta.height / meta.width};
  }
}
const shotsOf = r => (r.screens || []).filter(sc => SHOT[sc.p]).slice(0, 3);

// slide plan (1-based numbers, for the links)
const plan = [];
const add = (t, o = {}) => { plan.push({t, ...o}); return plan.length; };
const P = {cover: add('cover'), toc: add('toc')};
P.allFold = add('map', {g: 'all', fold: true}); P.allFull = add('map', {g: 'all', fold: false});
const PH = groups.map((gr, i) => {
  const o = {i, ...gr};
  o.chap = add('chapter', {gi: i}); o.fold = add('map', {g: gr.k, gi: i, fold: true}); o.full = add('map', {g: gr.k, gi: i, fold: false});
  o.branch = []; o.shots = [];
  gr.rows.forEach((r, j) => { o.branch.push(add('branch', {gi: i, j})); o.shots.push(shotsOf(r).map((sc, q) => add('shot', {gi: i, j, q}))); });
  return o;
});
P.end = add('end');
const N = plan.length;   // slides per colour set; the day deck follows the night one

// the deck and its helpers (scripts/tracking/deck-kit.mjs); C and MODE follow the colour set being built
const k = deck('خرائط ء-حماية الذهنية', N, P.toc), {pres, A, link, text, shape, image, panel, button, crumb, title, counter, figure} = k;
const emblem = k.emblem, newSlide = n => k.slide(n, {emblem: n !== P.cover}), nm = () => `s${k.cur}_${++k.seq}`;
let C, MODE;

// ---------------------------------------------------------------- 3. the slides
// built twice: the night set, then the day set, each slide linked to its twin by the switch at its foot
for (const mode of MODES) {
k.set(mode); MODE = mode; C = k.C; ({maps, ST} = SETS[mode]);
// cover: the hero of the page beside the phases in orbit, each with its progress ring, each a link to its chapter
{
  const s = newSlide(P.cover), all = D.rows, cx = 3.2, cy = 3.6, R = 2.3;
  A(shape(s, pres.shapes.OVAL, {x: cx - R - 0.45, y: cy - R - 0.45, w: 2 * (R + 0.45), h: 2 * (R + 0.45), line: {color: C.gold, width: 1.5, dashType: 'sysDot', transparency: 55}}), 'fade', 0, 900);
  A(shape(s, pres.shapes.OVAL, {x: cx - R, y: cy - R, w: 2 * R, h: 2 * R, line: {color: C.edge, width: 0.75, dashType: 'dash'}}), 'fade', 0, 900);
  PH.forEach((p, i) => {
    const a = -Math.PI / 2 + i * 2 * Math.PI / PH.length, x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
    const col = hex(PAL[i % PAL.length]), r = 0.25 + Math.min(0.14, p.rows.length / 80), pr = pct(doneOf(p.rows), p.rows.length);
    const d0 = 300 + i * 120;
    const x0 = cx + 1.0 * Math.cos(a), y0 = cy + 1.0 * Math.sin(a), x1 = x - r * Math.cos(a), y1 = y - r * Math.sin(a);
    A(shape(s, pres.shapes.CUSTOM_GEOMETRY, {x: Math.min(x0, x1), y: Math.min(y0, y1), w: Math.max(0.01, Math.abs(x1 - x0)), h: Math.max(0.01, Math.abs(y1 - y0)),
      points: [{x: x0 - Math.min(x0, x1), y: y0 - Math.min(y0, y1)}, {x: x1 - Math.min(x0, x1), y: y1 - Math.min(y0, y1)}], line: {color: col, width: 1.5, transparency: 35}}), 'fade', d0, 400);
    A(shape(s, pres.shapes.OVAL, {x: x - r - 0.09, y: y - r - 0.09, w: 2 * (r + 0.09), h: 2 * (r + 0.09), line: {color: C.edge, width: 2.5}}), 'zoom', d0 + 100, 400);
    if (pr > 0) A(shape(s, pres.shapes.BLOCK_ARC, {x: x - r - 0.12, y: y - r - 0.12, w: 2 * (r + 0.12), h: 2 * (r + 0.12), fill: {color: C.gold},
      angleRange: [270, (270 + Math.max(1, Math.min(359.9, pr * 3.6))) % 360], arcThicknessRatio: 0.16}), 'wipe', d0 + 250, 500, 'cw');
    A(shape(s, pres.shapes.OVAL, {x: x - r, y: y - r, w: 2 * r, h: 2 * r, fill: {color: col}, ...link(p.chap)}), 'zoom', d0 + 100, 400);
    A(text(s, String(i + 1), {x: x - r, y: y - r, w: 2 * r, h: 2 * r, align: 'center', fontSize: 14, fontFace: MONO, bold: true, color: C.white, ...link(p.chap)}), 'zoom', d0 + 100, 400);
  });
  A(shape(s, pres.shapes.OVAL, {x: cx - 1, y: cy - 1, w: 2, h: 2, fill: {color: C.root}, line: {color: C.gold, width: 3}, ...link(P.toc)}), 'zoom', 0, 600);
  A(text(s, [{text: 'ء-حماية', options: {fontSize: 24, fontFace: DISP, bold: true, color: C.white, breakLine: true}}, {text: `${all.length} عنصرا`, options: {fontSize: 12, color: C.gold}}],
    {x: cx - 1, y: cy - 0.6, w: 2, h: 1.2, align: 'center', ...link(P.toc)}), 'zoom', 0, 600);
  // the hero: the eyebrow, the Office, the wordmark, the system's full title in the display face, the deck's lead
  A(text(s, `e-HIMAYA · MIND MAPS · ${D.built}`, {x: 6.6, y: 0.42, w: 5.2, h: 0.28, fontSize: 10, fontFace: MONO, color: C.gold, rtlMode: false, lang: 'en-US', align: 'right', charSpacing: 2}), 'fade', 0, 600);
  A(emblem(s, 11.93, 0.3, 0.9), 'zoom', 0, 600);
  A(text(s, 'الديوان الوطني للحماية المدنية', {x: 6.6, y: 0.72, w: 5.2, h: 0.4, fontSize: 15, bold: true, color: C.ink}), 'fade', 150, 600);
  if (MODE === 'day') shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 9.48, y: 1.22, w: 3.5, h: 3.2 * 275 / 590 + 0.2, rectRadius: 0.16, fill: {color: C.root}});   // the white wordmark needs the royal blue under it
  A(image(s, {data: WORD, x: 9.63, y: 1.32, w: 3.2, h: 3.2 * WORD_AR, altText: 'ء-حماية E-HIMAYA'}), 'fade', 300, 900);
  A(text(s, [{text: 'من التبليغ إلى ', options: {color: C.ink}}, {text: 'أخذ القرار', options: {color: C.gold}}],
    {x: 6.3, y: 2.85, w: 6.53, h: 0.85, fontSize: 40, fontFace: DISP, bold: true}), 'fade', 450, 800);
  A(text(s, SYSTEM, {x: 6.3, y: 3.68, w: 6.53, h: 0.9, fontSize: 17, lineSpacingMultiple: 1.05, fontFace: DISPM, color: C.ink, valign: 'top'}), 'fade', 600, 800);
  A(text(s, `الخرائط الذهنية لمراحل المنظومة: ${PH.length} مرحلة، لكل مرحلة خريطة تتفرع إلى عناصرها، ولكل عنصر بطاقته الوظيفية ولقطات شاشاته. اضغط على أي مرحلة أو فرع للانتقال إليه.`,
    {x: 6.3, y: 4.62, w: 6.53, h: 0.55, fontSize: 11.5, color: C.mute, valign: 'top'}), 'fade', 750, 700);
  const figs = [[PH.length, 'مرحلة'], [all.length, 'عنصرا'], [pct(doneOf(all), all.length) + '%', 'منجز ومعتمد'], [Object.keys(SHOT).length, 'شاشة مصوّرة']];
  figs.forEach(([v, l], i) => figure(s, 12.83 - (i + 1) * 1.7 + 0.15, 5.35, 1.55, v, l, 850 + i * 150));
  A(button(s, 'ابدأ العرض ‹', 11.13, 6.55, 1.7, P.toc, true)[0], 'zoom', 1500, 400);
  A(s._slideObjects.at(-1).options, 'zoom', 1500, 400);
  counter(s, P.cover);
}

// table of contents: one card per phase
{
  const s = newSlide(P.toc);
  crumb(s, 'ء-حماية · الفهرس'); A(title(s, 'فهرس المراحل'), 'fade', 0, 500);
  button(s, 'الخلاصة', 0.5, 0.6, 1.2, P.end); button(s, 'نظرة شاملة', 1.85, 0.6, 1.5, P.allFold, true);
  const cw = 3.95, ch = 0.95, gx = 0.24, gy = 0.2;
  PH.forEach((p, i) => {
    const col = i % 3, row = Math.floor(i / 3), x = 12.83 - (col + 1) * cw - col * gx, y = 1.5 + row * (ch + gy);
    const c = hex(PAL[i % PAL.length]), d = doneOf(p.rows), pr = pct(d, p.rows.length), dl = 200 + i * 90;
    A(panel(s, x, y, cw, ch, {rectRadius: 0.14, ...link(p.chap)}), 'fade', dl, 400);
    A(shape(s, pres.shapes.OVAL, {x: x + cw - 0.68, y: y + 0.2, w: 0.52, h: 0.52, fill: {color: c}, ...link(p.chap)}), 'zoom', dl, 400);
    A(text(s, String(i + 1), {x: x + cw - 0.68, y: y + 0.2, w: 0.52, h: 0.52, align: 'center', fontSize: 14, fontFace: MONO, bold: true, color: C.white, ...link(p.chap)}), 'zoom', dl, 400);
    A(text(s, p.name, {x: x + 0.2, y: y + 0.12, w: cw - 1.0, h: 0.4, fontSize: 14, bold: true, fit: 'shrink', ...link(p.chap)}), 'fade', dl, 400);
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: x + 0.75, y: y + 0.62, w: cw - 1.55, h: 0.1, rectRadius: 0.05, fill: {color: C.line}}), 'fade', dl, 400);
    if (pr) A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: x + 0.75 + (cw - 1.55) * (1 - pr / 100), y: y + 0.62, w: (cw - 1.55) * pr / 100, h: 0.1, rectRadius: 0.05, fill: {color: c}}), 'wipe', dl + 200, 600, 'r');
    A(text(s, `${d}/${p.rows.length}`, {x: x + 0.15, y: y + 0.52, w: 0.55, h: 0.3, fontSize: 10, fontFace: MONO, color: C.mute, align: 'left'}), 'fade', dl, 400);
  });
  counter(s, P.toc);
}

// a mind map read from the page (dark set): paths become custom curves, pills rounded rectangles, texts text boxes
function drawMap(s, m, area, linkOf, rootLink, timed) {
  const {bb} = m, k = Math.min(area.w * 96 / bb.w, area.h * 96 / bb.h, 1.3);
  const ox = area.x + (area.w - bb.w * k / 96) / 2, oy = area.y + (area.h - bb.h * k / 96) / 2;
  const X = v => ox + (v - bb.x) * k / 96, Y = v => oy + (v - bb.y) * k / 96, L = v => v * k / 96, PT = v => v * k * 0.75;
  const delay = (it, part) => {
    if (it.root || it.k == null) return 0;
    const base = 250 + it.k * 160;
    return {branch: base, pill: base + 250, leaf: base + 450}[part] ?? base;
  };
  const leafSeq = {};
  for (const it of m.items) {
    const lk = it.root ? rootLink : (it.k != null && !it.leaf ? linkOf(it.k) : 0);
    if (it.tag === 'path') {
      const n = (it.d.match(/-?\d+(\.\d+)?(e-?\d+)?/g) || []).map(Number);
      const pts = []; for (let i = 0; i < n.length; i += 2) pts.push([X(n[i]), Y(n[i + 1])]);
      const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]), x0 = Math.min(...xs), y0 = Math.min(...ys);
      const rel = ([a, b]) => ({x: a - x0, y: b - y0});
      const points = [rel(pts[0]), {...rel(pts[3]), curve: {type: 'cubic', x1: rel(pts[1]).x, y1: rel(pts[1]).y, x2: rel(pts[2]).x, y2: rel(pts[2]).y}}];
      if (pts[4]) points.push(rel(pts[4]));
      const o = shape(s, pres.shapes.CUSTOM_GEOMETRY, {x: x0, y: y0, w: Math.max(0.01, Math.max(...xs) - x0), h: Math.max(0.01, Math.max(...ys) - y0), points,
        line: {color: hex(it.stroke), width: Math.max(0.5, PT(it.sw)), transparency: Math.round((1 - it.op) * 100)}});
      if (timed) A(o, 'wipe', it.leaf || pts[4] ? delay(it, 'leaf') : delay(it, 'branch'), it.leaf || pts[4] ? 450 : 600, pts[0][0] < pts.at(-1)[0] ? 'l' : 'r');
    } else if (it.tag === 'rect') {
      const o = shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: X(it.x), y: Y(it.y), w: L(it.w), h: L(it.h), rectRadius: L(it.h) / 2,
        fill: {color: hex(it.fill)}, ...(lk ? link(lk) : {})});
      if (timed) A(o, 'zoom', delay(it, 'pill'), 400);
    } else if (it.tag === 'circle') {
      const fill = /url/.test(it.fill) ? C.root : (it.fill === 'none' ? null : hex(it.fill));
      const o = shape(s, pres.shapes.OVAL, {x: X(it.cx - it.r), y: Y(it.cy - it.r), w: L(2 * it.r), h: L(2 * it.r),
        ...(fill ? {fill: {color: fill, transparency: it.glow ? 55 : 0}} : {}),
        ...(it.stroke ? {line: {color: hex(it.stroke), width: Math.max(0.5, PT(it.sw)), ...(it.dash ? {dashType: 'sysDot'} : {})}} : {}),
        ...(it.glow ? {} : (lk ? link(lk) : {}))});
      if (timed) A(o, 'zoom', it.root ? 0 : it.leaf ? delay(it, 'leaf') : delay(it, 'pill'), it.root ? 600 : 400);
    } else if (it.tag === 'text' && it.text.trim()) {
      const pad = L(Math.max(6, it.w * 0.08));
      const o = text(s, it.text, {x: X(it.x) - pad, y: Y(it.y) - L(2), w: L(it.w) + 2 * pad, h: L(it.h) + L(4), align: 'center', wrap: false,
        fontSize: Math.max(6, +PT(it.fs * 0.95).toFixed(1)), bold: it.bold, color: it.root ? C.white : hex(it.fill), ...(it.root ? {fontFace: DISP} : {}), ...(lk ? link(lk) : {})});
      if (timed) {
        if (it.leaf) { leafSeq[it.k] = (leafSeq[it.k] || 0) + 1; A(o, 'fade', delay(it, 'leaf') + 120 + leafSeq[it.k] * 70, 350); }
        else A(o, 'zoom', it.root ? 0 : delay(it, 'pill'), it.root ? 600 : 400);
      }
    }
  }
}

function legend(s, y = 7.05) {
  let x = 12.83;
  Object.entries(ST).forEach(([k, [lab, col]]) => {
    const w = 0.25 + lab.length * 0.085;
    x -= w;
    shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: x + w - 0.15, y: y + 0.08, w: 0.12, h: 0.12, rectRadius: 0.03, fill: {color: hex(col)}});
    text(s, lab, {x, y, w: w - 0.2, h: 0.28, fontSize: 9, color: C.mute});
    x -= 0.15;
  });
}
const mapBox = s => shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 0.4, y: 1.32, w: 12.53, h: 5.62, rectRadius: 0.2, fill: {color: C.deck, transparency: 15}, line: {color: C.line}});

// overview maps: a branch per phase, each a link to the phase's chapter
for (const fold of [true, false]) {
  const n = fold ? P.allFold : P.allFull, s = newSlide(n), m = maps[`all:${fold ? 'fold' : 'full'}`];
  crumb(s, 'نظرة شاملة على كل المراحل'); A(title(s, fold ? 'المنظومة في خريطة واحدة' : 'المنظومة بكل فروعها'), 'fade', 0, 500);
  button(s, fold ? 'بسط الفروع' : 'طيّ الفروع', 0.5, 0.6, 1.3, fold ? P.allFull : P.allFold, true);
  button(s, 'الفهرس', 1.95, 0.6, 1.0, P.toc);
  mapBox(s);
  drawMap(s, m, {x: 0.5, y: 1.4, w: 12.33, h: 5.45}, i => PH[i].chap, P.toc, true);
  legend(s); counter(s, n);
}

// chapter of a phase: the act number, a doughnut of the statuses, the five most important items
function makeChapter(p) {
  const s = newSlide(p.chap), c = hex(PAL[p.i % PAL.length]), rs = p.rows;
  crumb(s, `المرحلة ${p.i + 1} من ${PH.length}`);
  button(s, 'افتح الخريطة ‹', 0.5, 0.6, 1.6, p.fold, true); button(s, 'الفهرس', 2.25, 0.6, 1.0, P.toc);
  A(text(s, ind(p.i + 1), {x: 9.33, y: 0.8, w: 3.5, h: 1.55, fontSize: 96, fontFace: DISP, bold: true, color: C.gold}), 'fade', 0, 600);
  A(text(s, p.name, {x: 6.93, y: 2.35, w: 5.9, h: 0.8, fontSize: 32, fontFace: DISPM, color: C.ink, fit: 'shrink'}), 'fade', 200, 600);
  A(text(s, `${rs.length} عنصرا، منها ${doneOf(rs)} منجزة ومعتمدة.`, {x: 6.93, y: 3.12, w: 5.9, h: 0.4, fontSize: 15, color: C.mute}), 'fade', 350, 600);
  const used = Object.keys(ST).filter(k => rs.some(r => r.status === k));
  s.addChart(pres.charts.DOUGHNUT, [{name: 'الحالات', labels: used.map(k => ST[k][0]), values: used.map(k => rs.filter(r => r.status === k).length)}],
    {x: 9.93, y: 3.6, w: 2.9, h: 2.9, holeSize: 64, chartColors: used.map(k => hex(ST[k][1])), showLegend: false, showValue: false, showPercent: false,
      showLabel: false, showTitle: false, dataBorder: {pt: 1.5, color: C.bg}, objectName: nm()});
  A(s._slideObjects.at(-1).options, 'wipe', 500, 900, 'cw');
  A(text(s, [{text: pct(doneOf(rs), rs.length) + '%', options: {fontSize: 26, fontFace: MONO, bold: true, color: C.ink, breakLine: true}}, {text: 'منجز ومعتمد', options: {fontSize: 11, color: C.mute}}],
    {x: 10.53, y: 4.6, w: 1.7, h: 0.9, align: 'center'}), 'fade', 1100, 500);
  used.forEach((k, j) => {
    const n = rs.filter(r => r.status === k).length, y = 3.7 + j * 0.42;
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 6.93, y, w: 2.75, h: 0.32, rectRadius: 0.16, fill: {color: C.panel}, line: {color: C.line}}), 'fade', 900 + j * 120, 400);
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 9.45, y: y + 0.1, w: 0.12, h: 0.12, rectRadius: 0.03, fill: {color: hex(ST[k][1])}}), 'fade', 900 + j * 120, 400);
    A(text(s, `${ST[k][0]}: ${n}`, {x: 7.03, y, w: 2.35, h: 0.32, fontSize: 11}), 'fade', 900 + j * 120, 400);
  });
  // the five most important items, each a link to its card
  A(panel(s, 0.5, 1.4, 6.0, 5.45, {rectRadius: 0.2}), 'fade', 300, 500);
  A(text(s, 'أهم العناصر', {x: 0.8, y: 1.6, w: 5.4, h: 0.4, fontSize: 17, fontFace: DISPM, color: C.gold}), 'fade', 400, 500);
  rs.slice(0, 5).forEach((r, j) => {
    const y = 2.15 + j * 0.9, to = p.branch[j], dl = 600 + j * 200;
    A(shape(s, pres.shapes.OVAL, {x: 5.75, y: y + 0.1, w: 0.42, h: 0.42, fill: {color: c}, ...link(to)}), 'zoom', dl, 400);
    A(text(s, String(j + 1), {x: 5.75, y: y + 0.1, w: 0.42, h: 0.42, align: 'center', fontSize: 12, fontFace: MONO, bold: true, color: C.white, ...link(to)}), 'zoom', dl, 400);
    A(text(s, [{text: r.title, options: {fontSize: 15, color: C.ink, breakLine: true}}, {text: `${ST[r.status][0]} · الأهمية ${IMP[r.imp]}`, options: {fontSize: 11, color: C.mute}}],
      {x: 0.8, y, w: 4.8, h: 0.66, fit: 'shrink', ...link(to)}), 'fade', dl + 100, 450);
  });
  counter(s, p.chap);
}

// the map of a phase, folded and unfolded; a branch opens its card
function makeMaps(p) {
  for (const fold of [true, false]) {
    const n = fold ? p.fold : p.full, s = newSlide(n), m = maps[`${p.k}:${fold ? 'fold' : 'full'}`];
    crumb(s, `المرحلة ${p.i + 1} من ${PH.length} · الخريطة · اضغط على فرع لترى بطاقته`); A(title(s, p.name, p.i + 1), 'fade', 0, 500);
    button(s, fold ? 'بسط الفروع' : 'طيّ الفروع', 0.5, 0.6, 1.3, fold ? p.full : p.fold, true);
    button(s, 'الفصل', 1.95, 0.6, 0.9, p.chap); button(s, 'الفهرس', 3.0, 0.6, 0.9, P.toc);
    mapBox(s);
    drawMap(s, m, {x: 0.5, y: 1.4, w: 12.33, h: 5.45}, i => p.branch[i], p.chap, true);
    legend(s); counter(s, n);
  }
}

// the functional card of an element (the step panel of the algorithm page): beside it, the element as a branch of its
// phase with its details as leaves; under its text, the screenshots of the screens it speaks of, each a link to its view
function makeBranch(p, r, j) {
  const n = p.branch[j], s = newSlide(n), col = hex(PAL[j % PAL.length]);
  const kid = maps[`${p.k}:full`].kids[j], leaves = kid.leaves, st = ST[r.status], shots = shotsOf(r);
  crumb(s, `المرحلة ${p.i + 1} · ${p.name}`);
  A(title(s, 'البطاقة الوظيفية'), 'fade', 0, 400);
  button(s, 'الخريطة', 0.5, 0.6, 1.0, p.fold);
  button(s, '› السابق', 1.65, 0.6, 1.0, j ? p.branch[j - 1] : p.chap);
  button(s, 'التالي ‹', 2.8, 0.6, 1.0, j < p.rows.length - 1 ? p.branch[j + 1] : (PH[p.i + 1]?.chap || P.end), true);
  // the diagram box: root (the phase), the branch, the leaves
  shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 0.4, y: 1.35, w: 7.95, h: 5.5, rectRadius: 0.2, fill: {color: C.deck, transparency: 15}, line: {color: C.line}});
  const rx = 7.35, ry = 4.1, R = 0.72;
  A(shape(s, pres.shapes.OVAL, {x: rx - R - 0.1, y: ry - R - 0.1, w: 2 * R + 0.2, h: 2 * R + 0.2, fill: {color: C.gold, transparency: 70}}), 'zoom', 0, 500);
  A(shape(s, pres.shapes.OVAL, {x: rx - R, y: ry - R, w: 2 * R, h: 2 * R, fill: {color: C.root}, line: {color: C.gold, width: 2.5}, ...link(p.fold)}), 'zoom', 0, 500);
  A(text(s, p.name, {x: rx - R + 0.1, y: ry - 0.45, w: 2 * R - 0.2, h: 0.9, align: 'center', fontSize: 11, fontFace: DISPM, color: C.white, fit: 'shrink', ...link(p.fold)}), 'zoom', 0, 500);
  const label = kid.label, pw = Math.min(2.9, 0.9 + label.length * 0.09), px = rx - R - 0.35 - pw, py = ry - 0.25;
  A(shape(s, pres.shapes.LINE, {x: px + pw, y: ry, w: rx - R - px - pw, h: 0, line: {color: col, width: 4}}), 'wipe', 300, 400, 'r');
  A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: px, y: py, w: pw, h: 0.5, rectRadius: 0.25, fill: {color: col}, line: {color: C.gold, width: 1.5}}), 'zoom', 600, 450);
  A(shape(s, pres.shapes.OVAL, {x: px + 0.14, y: ry - 0.07, w: 0.14, h: 0.14, fill: {color: hex(st[1])}, line: {color: C.white, width: 1.25}}), 'zoom', 600, 450);
  A(text(s, label, {x: px + 0.33, y: py, w: pw - 0.42, h: 0.5, align: 'center', fontSize: 13, bold: true, color: C.white, fit: 'shrink'}), 'zoom', 600, 450);
  const nl = Math.min(leaves.length, 9), gap = Math.min(0.58, 4.9 / Math.max(1, nl)), top = ry - (nl - 1) * gap / 2;
  const x2 = Math.min(3.85, px - 0.55), lw = x2 - 0.75;
  leaves.slice(0, nl).forEach((t, q) => {
    const ly = top + q * gap, hgt = Math.max(0.01, Math.abs(ly - ry)), down = ly > ry;
    A(shape(s, pres.shapes.CUSTOM_GEOMETRY, {x: x2, y: Math.min(ry, ly), w: px - x2, h: hgt,
      points: [{x: px - x2, y: down ? 0 : hgt}, {x: 0, y: down ? hgt : 0, curve: {type: 'cubic', x1: (px - x2) * 0.45, y1: down ? 0 : hgt, x2: (px - x2) * 0.55, y2: down ? hgt : 0}}],
      line: {color: col, width: 1.5, transparency: 25}}), 'wipe', 1000 + q * 160, 500, 'r');
    A(shape(s, pres.shapes.OVAL, {x: x2 - 0.07, y: ly - 0.07, w: 0.14, h: 0.14, fill: {color: C.deck}, line: {color: col, width: 1.5}}), 'zoom', 1100 + q * 160, 300);
    A(text(s, t, {x: 0.7, y: ly - 0.16, w: lw - 0.15, h: 0.32, fontSize: 12, color: C.ink, fit: 'shrink'}), 'fade', 1150 + q * 160, 400);
  });
  if (!leaves.length) A(text(s, 'لا تفاصيل إضافية لهذا العنصر.', {x: 0.7, y: ry - 0.16, w: lw, h: 0.32, fontSize: 12, color: C.mute}), 'fade', 1000, 400);
  // the card
  const cx0 = 8.55, cw = 4.28, d0 = 300;
  A(panel(s, cx0, 1.35, cw, 5.5), 'fade', d0, 500);
  const L = (t, o) => text(s, t, {x: cx0 + 0.25, w: cw - 0.5, ...o});
  A(L(`العنصر ${j + 1} من ${p.rows.length} · ${r.kind || 'عنصر'} ${r.code || ''}`.trim(), {y: 1.52, h: 0.28, fontSize: 11, bold: true, color: C.gold}), 'fade', d0 + 100, 400);
  A(L(r.title, {y: 1.8, h: 0.72, fontSize: 19, fontFace: DISPM, color: C.ink, valign: 'top', fit: 'shrink'}), 'fade', d0 + 150, 450);
  // chips: status and importance
  let chx = cx0 + cw - 0.25;
  [[`● ${st[0]}`, hex(st[1])], [`الأهمية: ${IMP[r.imp]}`, C.ink]].forEach(([t, c2]) => {
    const w = 0.35 + t.length * 0.08; chx -= w;
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: chx, y: 2.58, w, h: 0.3, rectRadius: 0.15, fill: {color: C.deck}, line: {color: C.line}}), 'fade', d0 + 250, 400);
    A(text(s, t, {x: chx, y: 2.58, w, h: 0.3, align: 'center', fontSize: 10, color: c2}), 'fade', d0 + 250, 400);
    chx -= 0.1;
  });
  const descH = shots.length ? 1.75 : 3.3;
  A(L(r.desc || '', {y: 3.02, h: descH, fontSize: 12, color: C.ink, valign: 'top', fit: 'shrink', lineSpacingMultiple: 1.1}), 'fade', d0 + 350, 500);
  if (shots.length) {
    A(L('شاشات من المنظومة · اضغط لتكبيرها', {y: 4.86, h: 0.26, fontSize: 10, bold: true, color: C.gold}), 'fade', d0 + 450, 400);
    const tw = (cw - 0.5 - 0.12 * (shots.length - 1)) / shots.length, th = Math.min(0.95, tw * 0.625);
    shots.forEach((sc, q) => {
      const x = cx0 + cw - 0.25 - (q + 1) * tw - q * 0.12, to = p.shots[j][q];
      A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: x - 0.03, y: 5.15, w: tw + 0.06, h: th + 0.06, rectRadius: 0.06, fill: {color: C.deck}, line: {color: C.teal, width: 1}, ...link(to)}), 'zoom', d0 + 550 + q * 120, 400);
      A(image(s, {data: SHOT[sc.p].data, x, y: 5.18, w: tw, h: th, sizing: {type: 'cover', w: tw, h: th}, altText: sc.l, ...link(to)}), 'zoom', d0 + 550 + q * 120, 400);
      A(text(s, sc.p, {x, y: 5.2 + th + 0.04, w: tw, h: 0.22, fontSize: 8.5, fontFace: MONO, color: C.teal, align: 'center', rtlMode: false, lang: 'en-US', fit: 'shrink', ...link(to)}), 'fade', d0 + 600 + q * 120, 400);
    });
  }
  A(L([r.size ? `الحجم ${SZ[r.size] || r.size}` : '', r.date || '', r.ref ? `المرجع ${r.ref}` : ''].filter(Boolean).join(' · '),
    {y: 6.45, h: 0.26, fontSize: 9.5, color: C.mute, fit: 'shrink'}), 'fade', d0 + 700, 400);
  // the dots: every element of the phase, the current one ringed in gold
  const dn = p.rows.length, dw = 0.18, x0 = W / 2 + (dn * (dw + 0.08)) / 2;
  p.rows.forEach((_, q) => {
    const x = x0 - (q + 1) * (dw + 0.08);
    if (q === j) shape(s, pres.shapes.OVAL, {x: x - 0.05, y: 7.02 - 0.05, w: dw + 0.1, h: dw + 0.1, line: {color: C.gold, width: 2}});
    shape(s, pres.shapes.OVAL, {x, y: 7.02, w: dw, h: dw, fill: {color: hex(PAL[q % PAL.length]), transparency: q === j ? 0 : 45}, ...link(p.branch[q])});
  });
  counter(s, n);
}

// a screen of an element, full size: the atlas screenshot, what the screen is for and what it adds
function makeShot(p, r, j, q) {
  const n = p.shots[j][q], s = newSlide(n), sc = shotsOf(r)[q], all = shotsOf(r);
  crumb(s, `${r.title} · الشاشة ${q + 1} من ${all.length}`);
  A(title(s, sc.l), 'fade', 0, 400);
  button(s, 'البطاقة', 0.5, 0.6, 1.0, p.branch[j], true);
  if (all.length > 1) button(s, q < all.length - 1 ? 'الشاشة التالية ‹' : '› الشاشة الأولى', 1.65, 0.6, 1.6, p.shots[j][(q + 1) % all.length]);
  const bw = 8.6, bh = Math.min(5.45, bw * SHOT[sc.p].ar), iw = bh / SHOT[sc.p].ar;
  A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 0.45, y: 1.32, w: iw + 0.1, h: bh + 0.1, rectRadius: 0.08, fill: {color: C.deck}, line: {color: C.teal, width: 1.25}}), 'fade', 100, 500);
  A(image(s, {data: SHOT[sc.p].data, x: 0.5, y: 1.37, w: iw, h: bh, altText: sc.l, ...link(p.branch[j])}), 'zoom', 200, 600);
  const cx0 = 0.5 + iw + 0.35, cw = 12.83 - cx0;
  A(panel(s, cx0, 1.32, cw, 5.5), 'fade', 300, 500);
  const L = (t, o) => text(s, t, {x: cx0 + 0.25, w: cw - 0.5, ...o});
  A(L(sc.p, {y: 1.5, h: 0.32, fontSize: 12, fontFace: MONO, color: C.teal, rtlMode: false, lang: 'en-US'}), 'fade', 400, 400);
  A(L('وظيفة الشاشة', {y: 1.95, h: 0.3, fontSize: 12, bold: true, color: C.gold}), 'fade', 500, 400);
  A(L(sc.u || 'شاشة من لوحة القيادة.', {y: 2.25, h: 1.6, fontSize: 13, color: C.ink, valign: 'top', fit: 'shrink'}), 'fade', 550, 500);
  if (sc.v) {
    A(L('ما تضيفه', {y: 3.95, h: 0.3, fontSize: 12, bold: true, color: C.gold}), 'fade', 700, 400);
    A(L(sc.v, {y: 4.25, h: 1.5, fontSize: 13, color: C.ink, valign: 'top', fit: 'shrink'}), 'fade', 750, 500);
  }
  A(L('لقطة من أطلس الشاشات، تُحدَّث مع كل تحيين.', {y: 6.4, h: 0.26, fontSize: 9.5, color: C.mute}), 'fade', 800, 400);
  counter(s, n);
}
// in the order of the plan, so the slide numbers of the links hold
PH.forEach(p => { makeChapter(p); makeMaps(p); p.rows.forEach((r, j) => { makeBranch(p, r, j); shotsOf(r).forEach((_, q) => makeShot(p, r, j, q)); }); });

// summary: a bar per phase, split by status, each a link to its map
{
  const s = newSlide(P.end);
  crumb(s, 'ء-حماية · الخلاصة'); A(title(s, 'الخلاصة'), 'fade', 0, 500);
  A(text(s, 'تقدّم كل مرحلة حسب الحالة. اضغط على مرحلة للعودة إلى خريطتها.', {x: 3.4, y: 1.15, w: 8.65, h: 0.32, fontSize: 13, color: C.mute}), 'fade', 200, 500);
  button(s, 'الفهرس', 0.5, 0.6, 1.0, P.toc, true); button(s, 'الغلاف', 1.65, 0.6, 1.0, P.cover);
  const rowH = Math.min(0.36, 5.3 / PH.length);
  PH.forEach((p, i) => {
    const y = 1.65 + i * rowH, dl = 300 + i * 110, bx = 0.95, bw = 8.2;
    A(text(s, `${i + 1}. ${p.name}`, {x: 9.35, y, w: 3.48, h: rowH - 0.06, fontSize: 12, bold: true, color: C.ink, fit: 'shrink', ...link(p.fold)}), 'fade', dl, 400);
    A(shape(s, pres.shapes.RECTANGLE, {x: bx, y: y + rowH * 0.28, w: bw, h: rowH * 0.36, fill: {color: C.panel}, ...link(p.fold)}), 'fade', dl, 400);
    let x = bx + bw;
    Object.keys(ST).forEach(k => {
      const c = p.rows.filter(r => r.status === k).length; if (!c) return;
      const w = bw * c / p.rows.length; x -= w;
      A(shape(s, pres.shapes.RECTANGLE, {x, y: y + rowH * 0.28, w, h: rowH * 0.36, fill: {color: hex(ST[k][1])}, ...link(p.fold)}), 'wipe', dl + 150, 600, 'r');
    });
    A(text(s, `${doneOf(p.rows)}/${p.rows.length}`, {x: 0.3, y, w: 0.6, h: rowH - 0.06, fontSize: 10, fontFace: MONO, color: C.mute, align: 'left'}), 'fade', dl, 400);
  });
  legend(s); counter(s, P.end);
}
}

// ---------------------------------------------------------------- 4. write, with native transitions and animations
const TRANS = {shot: '<p:fade/>', cover: '<p:fade/>', toc: '<p:push dir="l"/>', map: '<p:fade/>', chapter: '<p:push dir="l"/>', branch: '<p:fade/>', end: '<p:fade/>'};
const nAnim = await finish(k, out, n => TRANS[plan[(n - 1) % N].t]);
console.log(`${MODES.length * N} slides (${MODES.join(' and ')}), ${nAnim} animations → ${out}`);
