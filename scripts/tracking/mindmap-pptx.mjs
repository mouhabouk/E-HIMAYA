// The mind maps as a PowerPoint deck (Yamen, 2026-11-14): the same slides as mindmaps-deck.html, drawn with native
// shapes so every colour, text and curve stays editable, the same palette, and native entrance animations and slide
// transitions whose effect, duration and delay can be changed in PowerPoint's animation pane.
//
//   node scripts/tracking/mindmap-pptx.mjs <mindmaps-deck.html> <out.pptx>
//
// The layout of every map is read from the deck page itself (Playwright), so the PowerPoint follows the HTML maps on
// every run of scripts/refresh-all.sh. Branches link to their own slide, and each map has a folded and an unfolded
// version linked to each other, so folding and moving between elements work in slide show.
// The cover carries the Office's emblem and the system's full title; every slide sits in the royal blue frame of the
// system with a gold hairline; the text uses IBM Plex Sans Arabic, whose files are copied to <out-dir>/fonts.
import {createRequire} from 'node:module';
import {readFileSync, writeFileSync, mkdtempSync, rmSync, mkdirSync, readdirSync, copyFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const req = createRequire(join(HERE, '../../docs/deliverables/package.json'));
const pptxgen = req('pptxgenjs');
const sharp = req('sharp');
const JSZip = req('jszip');
const {chromium} = createRequire(import.meta.url)('playwright');

const [src, out] = process.argv.slice(2);
if (!src || !out) { console.error('usage: mindmap-pptx.mjs <mindmaps-deck.html> <out.pptx>'); process.exit(2); }

// ---------------------------------------------------------------- 1. read the data and every map's layout
const browser = await chromium.launch();
const page = await browser.newPage({viewport: {width: 1600, height: 1000}});
await page.goto('file://' + resolve(src));
await page.waitForTimeout(1500);
const X = await page.evaluate(() => {
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
await browser.close();
const {D, keys, ST, PAL, maps, groups} = X;

// ---------------------------------------------------------------- 2. palette and helpers
// any colour of the page (#abc, #aabbcc, rgb(), rgba()) as the six hex digits PowerPoint wants
const hex = c => {
  c = String(c || '').trim();
  const m = c.match(/rgba?\(([^)]+)\)/i);
  if (m) return m[1].split(',').slice(0, 3).map(v => Math.round(+v).toString(16).padStart(2, '0')).join('').toUpperCase();
  c = c.replace('#', '');
  if (c.length === 3) c = c.split('').map(x => x + x).join('');
  return c.slice(0, 6).toUpperCase();
};
const C = {navy: '1F3FA0', deep: '0B1A3F', gold: 'C9A24A', page: 'F2F5FB', ink: '0E1426', mute: '55607A', line: 'D5DCEB', card: 'FFFFFF', leaf: '2A3350', white: 'FFFFFF'};
// the system's font (docs/design-system.md §2.4); its files ship beside the deck in a fonts folder (Yamen, 2026-11-14)
const FONT = 'IBM Plex Sans Arabic';
// the system's full title (Yamen, 2026-11-14)
const SYSTEM = 'منظومة ذكية للتبليغ والمشاركة المجتمعية والمؤسساتية في مجال السلامة والوقاية وإدارة الأخطار';
const SZ = {S: 'صغير', M: 'متوسط', L: 'كبير', XL: 'كبير جدا'}, IMP = {4: 'حرجة', 3: 'عالية', 2: 'متوسطة', 1: 'منخفضة'};
const W = 13.333, H = 7.5;
const doneOf = rs => rs.filter(r => r.status === 'done').length;
const pct = (a, b) => b ? Math.round(100 * a / b) : 0;
const AR = {rtlMode: true, lang: 'ar-SA', fontFace: FONT};

// the emblem of the Office (top of every slide) and the system's wordmark (cover), from the repository's brand files
const ROOT = join(HERE, '../..');
const EMBLEM = 'image/png;base64,' + readFileSync(join(HERE, 'assets/civil-protection-logo.png')).toString('base64');
const WORD = 'image/png;base64,' + (await sharp(join(ROOT, 'infra/keycloak/themes/ehimaya/login/resources/img/logo-horizontal.png'))
  .extract({left: 0, top: 70, width: 590, height: 275}).png().toBuffer()).toString('base64');

// slide plan (1-based numbers, for the links)
const plan = [];
const add = (t, o = {}) => { plan.push({t, ...o}); return plan.length; };
const P = {cover: add('cover'), toc: add('toc')};
P.allFold = add('map', {g: 'all', fold: true}); P.allFull = add('map', {g: 'all', fold: false});
const PH = groups.map((gr, i) => {
  const o = {i, ...gr};
  o.chap = add('chapter', {gi: i}); o.fold = add('map', {g: gr.k, gi: i, fold: true}); o.full = add('map', {g: gr.k, gi: i, fold: false});
  o.branch = gr.rows.map((r, j) => add('branch', {gi: i, j}));
  return o;
});
P.end = add('end');

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.title = 'خرائط ء-حماية الذهنية';
pres.rtlMode = true;
pres.theme = {headFontFace: FONT, bodyFontFace: FONT};

// animations wanted on each slide, by shape name, read again after writing (section 4)
const anim = [];             // anim[slideNo] = [{name, fx, delay, dur, dir}]
let cur = 0, seq = 0;
const nm = () => `s${cur}_${++seq}`;
const A = (o, fx, delay, dur = 500, dir) => { (anim[cur] ||= []).push({name: o.objectName, fx, delay, dur, dir}); return o; };
const link = n => n ? {hyperlink: {slide: n, tooltip: plan[n - 1] ? '' : ''}} : {};

function newSlide(n, bg) {
  cur = n; seq = 0;
  const s = pres.addSlide();
  if (pres.slides.length !== n) throw new Error(`slide ${pres.slides.length} built where the plan expects ${n}`);
  // the royal frame of the system (docs/design-system.md §2.0, Yamen 2026-11-14): a royal blue background with a gold
  // hairline; light slides put their content on a pale panel inside it, as the screens of the system do
  s.background = {color: C.navy};
  const inset = 0.13;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {x: inset, y: inset, w: W - 2 * inset, h: H - 2 * inset, rectRadius: 0.2,
    fill: bg === C.page ? {color: C.page} : {type: 'none'}, line: {color: C.gold, width: 1.25}, objectName: nm()});
  if (n !== P.cover) emblem(s);
  return s;
}
// pptxgenjs writes no relationship for a link on a shape or a text box: keep the target and write it after (section 4)
const shapeLinks = [];       // shapeLinks[slideNo] = {objectName: targetSlide}
function text(s, t, o) {
  const opt = {...AR, isTextBox: true, margin: 0, color: C.ink, fontSize: 14, align: 'right', valign: 'middle', objectName: nm(), ...o};
  if (opt.hyperlink?.slide) (shapeLinks[cur] ||= {})[opt.objectName] = opt.hyperlink.slide;
  s.addText(t, opt); return opt;
}
function shape(s, kind, o) {
  const opt = {objectName: nm(), ...o};
  if (opt.hyperlink?.slide) (shapeLinks[cur] ||= {})[opt.objectName] = opt.hyperlink.slide;
  s.addShape(kind, opt); return opt;
}
// a pill button with a link
function button(s, label, x, y, w, to, dark = false) {
  const o = shape(s, pres.shapes.ROUNDED_RECTANGLE, {x, y, w, h: 0.38, rectRadius: 0.19, fill: {color: dark ? C.gold : C.navy},
    line: {color: dark ? C.gold : C.navy}, ...link(to)});
  const t = text(s, label, {x, y, w, h: 0.38, align: 'center', fontSize: 12, bold: true, color: dark ? '1B1405' : C.white, ...link(to)});
  return [o, t];
}
function crumb(s, label, dark) { return text(s, label, {x: 5.2, y: 0.3, w: 6.85, h: 0.3, fontSize: 11, color: dark ? 'B9C3E0' : C.mute}); }
function title(s, label, dark) { return text(s, label, {x: 4.1, y: 0.55, w: 7.95, h: 0.6, fontSize: 28, bold: true, color: dark ? C.white : C.navy}); }
function emblem(s, x = 12.23, y = 0.28, w = 0.6) {
  const o = {data: EMBLEM, x, y, w, h: w, objectName: nm(), altText: 'شعار الديوان الوطني للحماية المدنية', ...link(P.toc)};
  s.addImage(o); return o;
}
function counter(s, n, dark) { text(s, `${n} / ${plan.length}`, {x: 0.5, y: 7.05, w: 1.4, h: 0.25, fontSize: 10, align: 'left', color: dark ? '8FA0CC' : C.mute}); }

// ---------------------------------------------------------------- 3. the slides
// cover: the phases in orbit around the system, each with its progress ring, each a link to its chapter
{
  const s = newSlide(P.cover, C.deep), all = D.rows, cx = 3.7, cy = 3.85, R = 2.35;
  A(shape(s, pres.shapes.OVAL, {x: cx - R - 0.45, y: cy - R - 0.45, w: 2 * (R + 0.45), h: 2 * (R + 0.45), line: {color: C.gold, width: 1.5, dashType: 'sysDot', transparency: 55}}), 'fade', 0, 900);
  A(shape(s, pres.shapes.OVAL, {x: cx - R, y: cy - R, w: 2 * R, h: 2 * R, line: {color: 'FFFFFF', width: 0.75, dashType: 'dash', transparency: 75}}), 'fade', 0, 900);
  PH.forEach((p, i) => {
    const a = -Math.PI / 2 + i * 2 * Math.PI / PH.length, x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
    const col = hex(PAL[i % PAL.length]), r = 0.25 + Math.min(0.14, p.rows.length / 80), pr = pct(doneOf(p.rows), p.rows.length);
    const d0 = 300 + i * 120;
    // spoke: a straight custom path from the centre circle to the phase
    const x0 = cx + 1.0 * Math.cos(a), y0 = cy + 1.0 * Math.sin(a), x1 = x - r * Math.cos(a), y1 = y - r * Math.sin(a);
    A(shape(s, pres.shapes.CUSTOM_GEOMETRY, {x: Math.min(x0, x1), y: Math.min(y0, y1), w: Math.max(0.01, Math.abs(x1 - x0)), h: Math.max(0.01, Math.abs(y1 - y0)),
      points: [{x: x0 - Math.min(x0, x1), y: y0 - Math.min(y0, y1)}, {x: x1 - Math.min(x0, x1), y: y1 - Math.min(y0, y1)}], line: {color: col, width: 1.5, transparency: 35}}), 'fade', d0, 400);
    A(shape(s, pres.shapes.OVAL, {x: x - r - 0.09, y: y - r - 0.09, w: 2 * (r + 0.09), h: 2 * (r + 0.09), line: {color: 'FFFFFF', width: 2.5, transparency: 80}}), 'zoom', d0 + 100, 400);
    if (pr > 0) A(shape(s, pres.shapes.BLOCK_ARC, {x: x - r - 0.12, y: y - r - 0.12, w: 2 * (r + 0.12), h: 2 * (r + 0.12), fill: {color: C.gold},
      angleRange: [270, (270 + Math.max(1, Math.min(359.9, pr * 3.6))) % 360], arcThicknessRatio: 0.16}), 'wipe', d0 + 250, 500, 'cw');
    A(shape(s, pres.shapes.OVAL, {x: x - r, y: y - r, w: 2 * r, h: 2 * r, fill: {color: col}, ...link(p.chap)}), 'zoom', d0 + 100, 400);
    A(text(s, String(i + 1), {x: x - r, y: y - r, w: 2 * r, h: 2 * r, align: 'center', fontSize: 14, bold: true, color: C.white, ...link(p.chap)}), 'zoom', d0 + 100, 400);
  });
  A(shape(s, pres.shapes.OVAL, {x: cx - 1, y: cy - 1, w: 2, h: 2, fill: {color: '0B1A3F'}, line: {color: C.gold, width: 3}, ...link(P.toc)}), 'zoom', 0, 600);
  A(text(s, [{text: 'ء-حماية', options: {fontSize: 22, bold: true, color: C.white, breakLine: true}}, {text: `${all.length} عنصرا`, options: {fontSize: 12, color: C.gold}}],
    {x: cx - 1, y: cy - 0.6, w: 2, h: 1.2, align: 'center', ...link(P.toc)}), 'zoom', 0, 600);
  // the Office's emblem and name, the system's wordmark, its full title, then the title of the deck
  A(emblem(s, 11.93, 0.4, 0.9), 'zoom', 0, 600);
  A(text(s, 'الديوان الوطني للحماية المدنية', {x: 7.3, y: 0.55, w: 4.45, h: 0.45, fontSize: 16, bold: true, color: C.white}), 'fade', 150, 600);
  s.addImage({data: WORD, x: 9.33, y: 1.38, w: 3.5, h: 3.5 * 275 / 590, objectName: nm(), altText: 'ء-حماية E-HIMAYA'});
  A(s._slideObjects.at(-1).options, 'fade', 300, 900);
  A(shape(s, pres.shapes.LINE, {x: 9.5, y: 3.08, w: 3.33, h: 0, line: {color: C.gold, width: 1.5}}), 'wipe', 450, 500, 'l');
  A(text(s, [{text: SYSTEM, options: {fontSize: 17, bold: true, color: C.white, breakLine: true}},
    {text: 'من التبليغ إلى أخذ القرار', options: {fontSize: 15, bold: true, color: C.gold}}],
    {x: 6.6, y: 3.15, w: 6.23, h: 1.05, valign: 'top', lineSpacingMultiple: 1.05}), 'fade', 550, 800);
  A(text(s, `الخرائط الذهنية لمراحل المنظومة: ${PH.length} مرحلة، لكل مرحلة خريطة تتفرع إلى عناصرها ثم إلى تفاصيلها. اضغط على أي مرحلة أو فرع للانتقال إليه.`,
    {x: 6.6, y: 4.25, w: 6.23, h: 0.6, fontSize: 12, color: 'D7DEF5', valign: 'top'}), 'fade', 800, 700);
  [[PH.length, 'مرحلة'], [all.length, 'عنصرا'], [pct(doneOf(all), all.length) + '%', 'منجز ومعتمد'], [D.built, 'آخر تحيين']].forEach(([v, l], i) => {
    const w = i === 3 ? 1.75 : 1.25, x = 12.83 - [0, 1.4, 2.8, 4.2][i] - w;
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x, y: 5.0, w, h: 0.95, rectRadius: 0.14, fill: {color: 'FFFFFF', transparency: 90}, line: {color: 'FFFFFF', transparency: 70}}), 'zoom', 800 + i * 150, 400);
    A(text(s, [{text: String(v), options: {fontSize: i === 3 ? 18 : 24, bold: true, color: C.gold, breakLine: true}}, {text: l, options: {fontSize: 11, color: 'D7DEF5'}}],
      {x: x + 0.12, y: 5.03, w: w - 0.24, h: 0.89}), 'zoom', 800 + i * 150, 400);
  });
  A(button(s, 'ابدأ العرض ‹', 11.13, 6.25, 1.7, P.toc, true)[0], 'zoom', 1500, 400);
  A(s._slideObjects.at(-1).options, 'zoom', 1500, 400);
  counter(s, P.cover, true);
}

// table of contents: one card per phase
{
  const s = newSlide(P.toc, C.page);
  crumb(s, 'ء-حماية'); A(title(s, 'فهرس المراحل'), 'fade', 0, 500);
  button(s, 'الخلاصة', 0.5, 0.6, 1.2, P.end); button(s, 'نظرة شاملة', 1.85, 0.6, 1.5, P.allFold);
  const cw = 3.95, ch = 0.95, gx = 0.24, gy = 0.2;
  PH.forEach((p, i) => {
    const col = i % 3, row = Math.floor(i / 3), x = 12.83 - (col + 1) * cw - col * gx, y = 1.5 + row * (ch + gy);
    const c = hex(PAL[i % PAL.length]), d = doneOf(p.rows), pr = pct(d, p.rows.length), dl = 200 + i * 90;
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x, y, w: cw, h: ch, rectRadius: 0.14, fill: {color: C.card}, line: {color: C.line},
      shadow: {type: 'outer', color: '0E1426', opacity: 0.08, blur: 6, offset: 2, angle: 90}, ...link(p.chap)}), 'fade', dl, 400);
    A(shape(s, pres.shapes.OVAL, {x: x + cw - 0.68, y: y + 0.2, w: 0.52, h: 0.52, fill: {color: c}, ...link(p.chap)}), 'zoom', dl, 400);
    A(text(s, String(i + 1), {x: x + cw - 0.68, y: y + 0.2, w: 0.52, h: 0.52, align: 'center', fontSize: 15, bold: true, color: C.white, ...link(p.chap)}), 'zoom', dl, 400);
    A(text(s, p.name, {x: x + 0.2, y: y + 0.12, w: cw - 1.0, h: 0.4, fontSize: 14, bold: true, ...link(p.chap)}), 'fade', dl, 400);
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: x + 0.75, y: y + 0.62, w: cw - 1.55, h: 0.12, rectRadius: 0.06, fill: {color: C.line}}), 'fade', dl, 400);
    if (pr) A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: x + 0.75 + (cw - 1.55) * (1 - pr / 100), y: y + 0.62, w: (cw - 1.55) * pr / 100, h: 0.12, rectRadius: 0.06, fill: {color: c}}), 'wipe', dl + 200, 600, 'r');
    A(text(s, `${d}/${p.rows.length}`, {x: x + 0.15, y: y + 0.52, w: 0.55, h: 0.3, fontSize: 11, color: C.mute, align: 'left'}), 'fade', dl, 400);
  });
  counter(s, P.toc);
}

// a mind map read from the page: paths become custom curves, pills rounded rectangles, every text a text box
function drawMap(s, m, area, linkOf, rootLink, timed) {
  const {bb} = m, k = Math.min(area.w * 96 / bb.w, area.h * 96 / bb.h, 1.3);
  const ox = area.x + (area.w - bb.w * k / 96) / 2, oy = area.y + (area.h - bb.h * k / 96) / 2;
  const X = v => ox + (v - bb.x) * k / 96, Y = v => oy + (v - bb.y) * k / 96, L = v => v * k / 96, PT = v => v * k * 0.75;
  const order = new Map();      // the drawing order of the branches, for the timings
  const delay = (it, part) => {
    if (it.root || it.k == null) return part === 'glow' ? 0 : 0;
    const i = it.k, base = 250 + i * 160;
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
      if (timed) {
        const side = pts[0][0] < pts.at(-1)[0] ? 'l' : 'r';
        A(o, 'wipe', it.leaf || pts[4] ? delay(it, 'leaf') : delay(it, 'branch'), it.leaf || pts[4] ? 450 : 600, side);
      }
    } else if (it.tag === 'rect') {
      const o = shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: X(it.x), y: Y(it.y), w: L(it.w), h: L(it.h), rectRadius: L(it.h) / 2,
        fill: {color: hex(it.fill)}, ...(lk ? link(lk) : {})});
      if (timed) A(o, 'zoom', delay(it, 'pill'), 400);
    } else if (it.tag === 'circle') {
      const fill = /url/.test(it.fill) ? C.navy : (it.fill === 'none' ? null : hex(it.fill));
      const o = shape(s, pres.shapes.OVAL, {x: X(it.cx - it.r), y: Y(it.cy - it.r), w: L(2 * it.r), h: L(2 * it.r),
        ...(fill ? {fill: {color: fill, transparency: it.glow ? 55 : 0}} : {}),
        ...(it.stroke ? {line: {color: hex(it.stroke), width: Math.max(0.5, PT(it.sw)), ...(it.dash ? {dashType: 'sysDot'} : {})}} : {}),
        ...(it.glow ? {} : (lk ? link(lk) : {}))});
      if (timed) A(o, 'zoom', it.root ? 0 : it.leaf ? delay(it, 'leaf') : delay(it, 'pill'), it.root ? 600 : 400);
    } else if (it.tag === 'text' && it.text.trim()) {
      const pad = L(Math.max(6, it.w * 0.08));
      const color = it.root ? C.white : hex(it.fill);
      const o = text(s, it.text, {x: X(it.x) - pad, y: Y(it.y) - L(2), w: L(it.w) + 2 * pad, h: L(it.h) + L(4), align: 'center', wrap: false,
        fontSize: Math.max(6, +PT(it.fs * 0.95).toFixed(1)), bold: it.bold, color, ...(lk ? link(lk) : {})});
      if (timed) {
        if (it.leaf) { leafSeq[it.k] = (leafSeq[it.k] || 0) + 1; A(o, 'fade', delay(it, 'leaf') + 120 + leafSeq[it.k] * 70, 350); }
        else A(o, it.root ? 'zoom' : 'zoom', it.root ? 0 : delay(it, 'pill'), it.root ? 600 : 400);
      }
    }
  }
}

function legend(s, y = 7.02) {
  let x = 12.83;
  Object.entries(ST).forEach(([k, [lab, col]]) => {
    const w = 0.25 + lab.length * 0.085;
    x -= w;
    shape(s, pres.shapes.OVAL, {x: x + w - 0.14, y: y + 0.08, w: 0.12, h: 0.12, fill: {color: hex(col)}});
    text(s, lab, {x, y, w: w - 0.2, h: 0.28, fontSize: 9, color: C.mute});
    x -= 0.15;
  });
}

// overview maps: a branch per phase, each a link to the phase's chapter
for (const fold of [true, false]) {
  const n = fold ? P.allFold : P.allFull, s = newSlide(n, C.page), m = maps[`all:${fold ? 'fold' : 'full'}`];
  crumb(s, 'نظرة شاملة على كل المراحل'); A(title(s, fold ? 'المنظومة في خريطة واحدة' : 'المنظومة بكل فروعها'), 'fade', 0, 500);
  button(s, fold ? 'بسط الفروع' : 'طيّ الفروع', 0.5, 0.6, 1.3, fold ? P.allFull : P.allFold);
  button(s, 'الفهرس', 1.95, 0.6, 1.0, P.toc);
  drawMap(s, m, {x: 0.4, y: 1.35, w: 12.53, h: 5.55}, i => PH[i].chap, P.toc, true);
  legend(s); counter(s, n);
}

// chapter of a phase: the number, a doughnut of the statuses, the five most important items
function makeChapter(p) {
  const s = newSlide(p.chap, C.page), c = hex(PAL[p.i % PAL.length]), rs = p.rows;
  crumb(s, `المرحلة ${p.i + 1} من ${PH.length}`);
  button(s, 'افتح الخريطة ‹', 0.5, 0.6, 1.6, p.fold, true); button(s, 'الفهرس', 2.25, 0.6, 1.0, P.toc);
  A(text(s, String(p.i + 1).padStart(2, '0'), {x: 9.33, y: 0.85, w: 3.5, h: 1.5, fontSize: 96, bold: true, color: C.gold}), 'fade', 0, 600);
  A(text(s, p.name, {x: 6.93, y: 2.35, w: 5.9, h: 0.75, fontSize: 32, bold: true, color: C.ink}), 'fade', 200, 600);
  A(text(s, `${rs.length} عنصرا، منها ${doneOf(rs)} منجزة ومعتمدة.`, {x: 6.93, y: 3.08, w: 5.9, h: 0.4, fontSize: 15, color: C.mute}), 'fade', 350, 600);
  const used = Object.keys(ST).filter(k => rs.some(r => r.status === k));
  s.addChart(pres.charts.DOUGHNUT, [{name: 'الحالات', labels: used.map(k => ST[k][0]), values: used.map(k => rs.filter(r => r.status === k).length)}],
    {x: 9.93, y: 3.55, w: 2.9, h: 2.9, holeSize: 62, chartColors: used.map(k => hex(ST[k][1])), showLegend: false, showValue: false, showPercent: false,
      showLabel: false, showTitle: false, dataBorder: {pt: 1, color: 'F2F5FB'}, objectName: nm()});
  A(s._slideObjects.at(-1).options, 'wipe', 500, 900, 'cw');
  A(text(s, [{text: pct(doneOf(rs), rs.length) + '%', options: {fontSize: 28, bold: true, color: C.ink, breakLine: true}}, {text: 'منجز ومعتمد', options: {fontSize: 11, color: C.mute}}],
    {x: 10.63, y: 4.55, w: 1.5, h: 0.9, align: 'center'}), 'fade', 1100, 500);
  used.forEach((k, j) => {
    const n = rs.filter(r => r.status === k).length, y = 3.65 + j * 0.42;
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 6.93, y, w: 2.75, h: 0.32, rectRadius: 0.16, fill: {color: C.card}, line: {color: C.line}}), 'fade', 900 + j * 120, 400);
    A(shape(s, pres.shapes.OVAL, {x: 9.45, y: y + 0.1, w: 0.12, h: 0.12, fill: {color: hex(ST[k][1])}}), 'fade', 900 + j * 120, 400);
    A(text(s, `${ST[k][0]}: ${n}`, {x: 7.03, y, w: 2.35, h: 0.32, fontSize: 11}), 'fade', 900 + j * 120, 400);
  });
  // the five most important items, each a link to its slide
  A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 0.5, y: 1.4, w: 6.0, h: 5.4, rectRadius: 0.2, fill: {color: C.card}, line: {color: C.line},
    shadow: {type: 'outer', color: '0E1426', opacity: 0.1, blur: 10, offset: 3, angle: 90}}), 'fade', 300, 500);
  A(text(s, 'أهم العناصر', {x: 0.8, y: 1.6, w: 5.4, h: 0.4, fontSize: 15, bold: true, color: C.mute}), 'fade', 400, 500);
  rs.slice(0, 5).forEach((r, j) => {
    const y = 2.15 + j * 0.88, to = p.branch[j], dl = 600 + j * 200;
    A(shape(s, pres.shapes.OVAL, {x: 5.75, y: y + 0.1, w: 0.42, h: 0.42, fill: {color: c}, ...link(to)}), 'zoom', dl, 400);
    A(text(s, String(j + 1), {x: 5.75, y: y + 0.1, w: 0.42, h: 0.42, align: 'center', fontSize: 13, bold: true, color: C.white, ...link(to)}), 'zoom', dl, 400);
    A(text(s, [{text: r.title, options: {fontSize: 15, color: C.ink, breakLine: true}}, {text: `${ST[r.status][0]} · الأهمية ${IMP[r.imp]}`, options: {fontSize: 11, color: C.mute}}],
      {x: 0.8, y, w: 4.8, h: 0.66, ...link(to)}), 'fade', dl + 100, 450);
  });
  counter(s, p.chap);
}

// the map of a phase, folded and unfolded; a branch opens its own slide
function makeMaps(p) {
  for (const fold of [true, false]) {
    const n = fold ? p.fold : p.full, s = newSlide(n, C.page), m = maps[`${p.k}:${fold ? 'fold' : 'full'}`];
    crumb(s, `المرحلة ${p.i + 1} من ${PH.length} · الخريطة`); A(title(s, p.name), 'fade', 0, 500);
    button(s, fold ? 'بسط الفروع' : 'طيّ الفروع', 0.5, 0.6, 1.3, fold ? p.full : p.fold);
    button(s, 'الفصل', 1.95, 0.6, 0.9, p.chap); button(s, 'الفهرس', 3.0, 0.6, 0.9, P.toc);
    drawMap(s, m, {x: 0.4, y: 1.35, w: 12.53, h: 5.55}, i => p.branch[i], p.chap, true);
    legend(s); counter(s, n);
  }
}

// one slide per element: the phase, the branch, its details as leaves, and the full card
function makeBranch(p, r, j) {
  const n = p.branch[j], s = newSlide(n, C.page), col = hex(PAL[j % PAL.length]);
  const kid = maps[`${p.k}:full`].kids[j], leaves = kid.leaves, st = ST[r.status];
  crumb(s, `المرحلة ${p.i + 1} · ${p.name} · العنصر ${j + 1} من ${p.rows.length}`);
  button(s, 'الخريطة', 0.5, 0.6, 1.0, p.fold);
  button(s, '› السابق', 1.65, 0.6, 1.0, j ? p.branch[j - 1] : p.chap);
  button(s, 'التالي ‹', 2.8, 0.6, 1.0, j < p.rows.length - 1 ? p.branch[j + 1] : (PH[p.i + 1]?.chap || P.end), true);
  // root: the phase
  const rx = 11.35, ry = 3.05, R = 0.95;
  A(shape(s, pres.shapes.OVAL, {x: rx - R - 0.1, y: ry - R - 0.1, w: 2 * R + 0.2, h: 2 * R + 0.2, fill: {color: C.gold, transparency: 65}}), 'zoom', 0, 500);
  A(shape(s, pres.shapes.OVAL, {x: rx - R, y: ry - R, w: 2 * R, h: 2 * R, fill: {color: C.navy}, line: {color: C.gold, width: 2.5}, ...link(p.fold)}), 'zoom', 0, 500);
  A(text(s, p.name, {x: rx - R + 0.15, y: ry - 0.55, w: 2 * R - 0.3, h: 1.1, align: 'center', fontSize: 13, bold: true, color: C.white, ...link(p.fold)}), 'zoom', 0, 500);
  // branch pill
  const label = kid.label, pw = Math.min(5.0, 1.0 + label.length * 0.105), px = 9.95 - pw, py = ry - 0.27;
  A(shape(s, pres.shapes.CUSTOM_GEOMETRY, {x: 9.95, y: ry - 0.01, w: rx - R - 9.95 + 0.05, h: 0.02, points: [{x: rx - R - 9.95 + 0.05, y: 0.01}, {x: 0, y: 0.01}],
    line: {color: col, width: 5}}), 'wipe', 300, 400, 'r');
  A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: px, y: py, w: pw, h: 0.54, rectRadius: 0.27, fill: {color: col}, line: {color: C.gold, width: 2}}), 'zoom', 600, 450);
  A(shape(s, pres.shapes.OVAL, {x: px + 0.17, y: ry - 0.08, w: 0.16, h: 0.16, fill: {color: hex(st[1])}, line: {color: C.white, width: 1.5}}), 'zoom', 600, 450);
  A(text(s, label, {x: px + 0.4, y: py, w: pw - 0.55, h: 0.54, align: 'center', fontSize: 15, bold: true, color: C.white}), 'zoom', 600, 450);
  // leaves fanning to the left
  const nl = leaves.length, top = ry - (nl - 1) * 0.36;
  leaves.forEach((t, q) => {
    const ly = top + q * 0.72, x1 = px, x2 = 5.2;
    A(shape(s, pres.shapes.CUSTOM_GEOMETRY, {x: x2 - 4.4, y: Math.min(ry, ly + 0.2), w: x1 - x2 + 4.4, h: Math.max(0.01, Math.abs(ly + 0.2 - ry)),
      points: [{x: x1 - x2 + 4.4, y: ry < ly + 0.2 ? 0 : Math.abs(ly + 0.2 - ry)},
        {x: 4.4, y: ry < ly + 0.2 ? Math.abs(ly + 0.2 - ry) : 0, curve: {type: 'cubic', x1: x1 - x2 + 3.6, y1: ry < ly + 0.2 ? 0 : Math.abs(ly + 0.2 - ry), x2: 5.2, y2: ry < ly + 0.2 ? Math.abs(ly + 0.2 - ry) : 0}},
        {x: 0, y: ry < ly + 0.2 ? Math.abs(ly + 0.2 - ry) : 0}],
      line: {color: col, width: 1.75, transparency: 20}}), 'wipe', 1000 + q * 180, 500, 'r');
    A(text(s, t, {x: 0.8, y: ly - 0.12, w: 4.4, h: 0.32, fontSize: 14, color: C.leaf}), 'fade', 1150 + q * 180, 400);
  });
  if (!nl) A(text(s, 'لا تفاصيل إضافية لهذا العنصر.', {x: 0.8, y: ry - 0.16, w: 4.4, h: 0.32, fontSize: 13, color: C.mute}), 'fade', 1000, 400);
  // the card: status, size, importance, date, description, reference
  const cy0 = 5.05, chips = [[`● ${st[0]}`, hex(st[1])], [`الحجم: ${SZ[r.size] || r.size}`, C.ink], [`الأهمية: ${IMP[r.imp]}`, C.ink]].concat(r.date ? [[r.date, C.ink]] : []);
  A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 0.5, y: cy0, w: 12.33, h: 1.85, rectRadius: 0.18, fill: {color: C.card}, line: {color: C.line},
    shadow: {type: 'outer', color: '0E1426', opacity: 0.1, blur: 10, offset: 3, angle: 90}}), 'fade', 1300 + nl * 180, 500);
  let cx = 12.6;
  chips.forEach(([t, c2]) => {
    const w = 0.35 + t.length * 0.085; cx -= w;
    A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: cx, y: cy0 + 0.18, w, h: 0.32, rectRadius: 0.16, fill: {color: C.page}, line: {color: C.line}}), 'fade', 1400 + nl * 180, 400);
    A(text(s, t, {x: cx, y: cy0 + 0.18, w, h: 0.32, align: 'center', fontSize: 11, color: c2}), 'fade', 1400 + nl * 180, 400);
    cx -= 0.12;
  });
  A(text(s, r.desc || '', {x: 0.75, y: cy0 + 0.6, w: 11.85, h: 0.85, fontSize: 13, color: C.mute, valign: 'top', fit: 'shrink'}), 'fade', 1500 + nl * 180, 500);
  if (r.ref) A(text(s, `المرجع: ${r.ref}`, {x: 0.75, y: cy0 + 1.47, w: 11.85, h: 0.28, fontSize: 10, color: C.mute}), 'fade', 1500 + nl * 180, 500);
  // the dots: every element of the phase, the current one ringed in gold
  const dn = p.rows.length, dw = 0.2, x0 = W / 2 + (dn * (dw + 0.08)) / 2;
  p.rows.forEach((_, q) => {
    const x = x0 - (q + 1) * (dw + 0.08);
    if (q === j) shape(s, pres.shapes.OVAL, {x: x - 0.05, y: 7.0 - 0.05, w: dw + 0.1, h: dw + 0.1, line: {color: C.gold, width: 2}});
    shape(s, pres.shapes.OVAL, {x, y: 7.0, w: dw, h: dw, fill: {color: hex(PAL[q % PAL.length]), transparency: q === j ? 0 : 45}, ...link(p.branch[q])});
  });
  counter(s, n);
}
// in the order of the plan, so the slide numbers of the links hold
PH.forEach(p => { makeChapter(p); makeMaps(p); p.rows.forEach((r, j) => makeBranch(p, r, j)); });

// summary: a bar per phase, split by status, each a link to its map
{
  const s = newSlide(P.end, C.deep);
  A(text(s, 'الخلاصة', {x: 3.4, y: 0.45, w: 8.65, h: 0.7, fontSize: 32, bold: true, color: C.white}), 'fade', 0, 500);
  A(text(s, 'تقدّم كل مرحلة حسب الحالة. اضغط على مرحلة للعودة إلى خريطتها.', {x: 3.4, y: 1.1, w: 8.65, h: 0.35, fontSize: 14, color: 'B9C3E0'}), 'fade', 200, 500);
  button(s, 'الفهرس', 0.5, 0.6, 1.0, P.toc, true); button(s, 'الغلاف', 1.65, 0.6, 1.0, P.cover, true);
  const rowH = Math.min(0.36, 5.3 / PH.length);
  PH.forEach((p, i) => {
    const y = 1.65 + i * rowH, dl = 300 + i * 110, bx = 0.95, bw = 8.2;
    A(text(s, `${i + 1}. ${p.name}`, {x: 9.35, y, w: 3.48, h: rowH - 0.06, fontSize: 12, bold: true, color: C.white, ...link(p.fold)}), 'fade', dl, 400);
    A(shape(s, pres.shapes.RECTANGLE, {x: bx, y: y + rowH * 0.25, w: bw, h: rowH * 0.42, fill: {color: '26304F'}, ...link(p.fold)}), 'fade', dl, 400);
    let x = bx + bw;
    Object.keys(ST).forEach(k => {
      const c = p.rows.filter(r => r.status === k).length; if (!c) return;
      const w = bw * c / p.rows.length; x -= w;
      A(shape(s, pres.shapes.RECTANGLE, {x, y: y + rowH * 0.25, w, h: rowH * 0.42, fill: {color: hex(ST[k][1])}, ...link(p.fold)}), 'wipe', dl + 150, 600, 'r');
    });
    A(text(s, `${doneOf(p.rows)}/${p.rows.length}`, {x: 0.3, y, w: 0.6, h: rowH - 0.06, fontSize: 11, color: 'B9C3E0', align: 'left'}), 'fade', dl, 400);
  });
  counter(s, P.end, true);
}

// ---------------------------------------------------------------- 4. write, then add the native transitions and animations
const tmp = mkdtempSync(join(tmpdir(), 'mm-pptx-'));
const raw = join(tmp, 'raw.pptx');
await pres.writeFile({fileName: raw});
const zip = await JSZip.loadAsync(readFileSync(raw));

const ENTR = {
  fade: {id: 10, sub: 0, filter: 'fade'},
  wipe: {id: 22, sub: {l: 8, r: 2, u: 1, d: 4, cw: 8}, filter: {l: 'wipe(left)', r: 'wipe(right)', u: 'wipe(up)', d: 'wipe(down)', cw: 'wheel(1)'}},
  zoom: {id: 53, sub: 16, filter: 'fade'},
};
function effect(e, spid, ids) {
  const id = () => ++ids.n;
  const par = id();
  let sub = 0, filter = 'fade', preset = ENTR[e.fx].id, extra = '';
  if (e.fx === 'wipe') {
    if (e.dir === 'cw') { preset = 21; sub = 1; filter = 'wheel(1)'; }   // wheel, one spoke: the doughnut and the progress rings
    else { sub = ENTR.wipe.sub[e.dir || 'l']; filter = ENTR.wipe.filter[e.dir || 'l']; }
  } else if (e.fx === 'zoom') {
    sub = 16;
    extra = ['ppt_w', 'ppt_h'].map(a => `<p:anim calcmode="lin" valueType="num"><p:cBhvr><p:cTn id="${id()}" dur="${e.dur}" fill="hold"/><p:tgtEl><p:spTgt spid="${spid}"/></p:tgtEl><p:attrNameLst><p:attrName>${a}</p:attrName></p:attrNameLst></p:cBhvr><p:tavLst><p:tav tm="0"><p:val><p:fltVal val="0"/></p:val></p:tav><p:tav tm="100000"><p:val><p:strVal val="#${a}"/></p:val></p:tav></p:tavLst></p:anim>`).join('');
  }
  const set = `<p:set><p:cBhvr><p:cTn id="${id()}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn><p:tgtEl><p:spTgt spid="${spid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>`;
  const fx = `<p:animEffect transition="in" filter="${filter}"><p:cBhvr><p:cTn id="${id()}" dur="${e.dur}"/><p:tgtEl><p:spTgt spid="${spid}"/></p:tgtEl></p:cBhvr></p:animEffect>`;
  return `<p:par><p:cTn id="${par}" presetID="${preset}" presetClass="entr" presetSubtype="${sub}" fill="hold" grpId="0" nodeType="withEffect"><p:stCondLst><p:cond delay="${Math.round(e.delay)}"/></p:stCondLst><p:childTnLst>${set}${extra}${fx}</p:childTnLst></p:cTn></p:par>`;
}
const TRANS = {cover: '<p:fade/>', toc: '<p:push dir="l"/>', map: '<p:fade/>', chapter: '<p:push dir="l"/>', branch: '<p:fade/>', end: '<p:fade/>'};
let nAnim = 0;
for (let n = 1; n <= plan.length; n++) {
  const f = `ppt/slides/slide${n}.xml`;
  let xml = await zip.file(f).async('string');
  const ids = {}; for (const m of xml.matchAll(/<p:cNvPr id="(\d+)" name="([^"]+)"/g)) ids[m[2]] = m[1];
  // what each object is, for its build entry: text shapes get bldP, charts bldGraphic, pictures none (as PowerPoint writes)
  const kind = {}; for (const m of xml.matchAll(/<p:(sp|pic|graphicFrame)>\s*<p:nv\w+Pr>\s*<p:cNvPr id="(\d+)"/g)) kind[m[2]] = m[1];
  const list = (anim[n] || []).filter(e => ids[e.name]).sort((a, b) => a.delay - b.delay);
  const trans = `<p:transition spd="med">${TRANS[plan[n - 1].t]}</p:transition>`;
  let timing = '';
  if (list.length) {
    const c = {n: 4};
    const effects = list.map(e => effect(e, ids[e.name], c)).join('');
    const spids = [...new Set(list.map(e => ids[e.name]))];
    timing = `<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst><p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst><p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst><p:par><p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>${effects}</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst><p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst><p:bldLst>${spids.map(i => kind[i] === 'graphicFrame' ? `<p:bldGraphic spid="${i}" grpId="0"><p:bldAsOne/></p:bldGraphic>` : kind[i] === 'pic' ? '' : `<p:bldP spid="${i}" grpId="0" animBg="1"/>`).join('')}</p:bldLst></p:timing>`;
    // the first effect starts the chain "after previous" so the slide plays by itself; the rest run "with previous"
    timing = timing.replace('nodeType="withEffect"', 'nodeType="afterEffect"');
    nAnim += list.length;
  }
  xml = xml.replace(/<p:transition[\s\S]*?<\/p:transition>|<p:transition[^>]*\/>/g, '').replace(/<p:timing>[\s\S]*?<\/p:timing>/g, '');
  xml = xml.replace(/(<\/p:clrMapOvr>)/, `$1${trans}${timing}`);
  if (shapeLinks[n]) {
    const rf = `ppt/slides/_rels/slide${n}.xml.rels`;
    let rels = await zip.file(rf).async('string');
    let next = Math.max(0, ...[...rels.matchAll(/Id="rId(\d+)"/g)].map(m => +m[1])) + 1;
    // every link still unresolved inside a named object (on the object itself or on its runs) goes to that object's target
    const parts = xml.split(/(?=<p:cNvPr id="\d+" name=")/);
    xml = parts.map(part => {
      const name = part.match(/^<p:cNvPr id="\d+" name="([^"]+)"/)?.[1], to = name && shapeLinks[n][name];
      if (!to) return part;
      const id = `rId${next++}`;
      rels = rels.replace('</Relationships>', `<Relationship Id="${id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slide${to}.xml"/></Relationships>`);
      // the whole object is the link, with no link on its runs, so a linked label keeps its colour and has no underline
      return part.replace(/ u="sng"/g, "").replace(/<a:hlinkClick\b[^>]*?(?:\/>|>[\s\S]*?<\/a:hlinkClick>)/g, '')
        .replace(/^(<p:cNvPr [^>]*?)(?:\/>|><\/p:cNvPr>)/, `$1><a:hlinkClick r:id="${id}" action="ppaction://hlinksldjump"/></p:cNvPr>`);
    }).join('');
    zip.file(rf, rels);
  }
  zip.file(f, xml);
}
// the theme carries the royal colours, so PowerPoint's colour picker offers them first
{
  const f = Object.keys(zip.files).find(f => /^ppt\/theme\/theme\d+\.xml$/.test(f));
  let x = await zip.file(f).async('string');
  const T = {dk1: '0E1426', lt1: 'FFFFFF', dk2: '1F3FA0', lt2: 'F2F5FB', accent1: '1F3FA0', accent2: 'C9A24A', accent3: '9B1B2C',
    accent4: '152D78', accent5: '0B1A3F', accent6: '761420', hlink: '1F3FA0', folHlink: '152D78'};
  for (const [k, v] of Object.entries(T)) x = x.replace(new RegExp(`<a:${k}>[\\s\\S]*?</a:${k}>`), `<a:${k}><a:srgbClr val="${v}"/></a:${k}>`);
  x = x.replace(/<a:clrScheme name="[^"]*"/, '<a:clrScheme name="E-HIMAYA الألوان الملكية"');
  zip.file(f, x);
}
// pptxgenjs writes one copy of an image per slide: keep one copy of each and point every slide at it
{
  const first = new Map(), gone = new Map();
  for (const f of Object.keys(zip.files).filter(f => f.startsWith('ppt/media/') && !zip.files[f].dir).sort()) {
    const key = (await zip.file(f).async('base64'));
    if (first.has(key)) { gone.set(f.slice(4), first.get(key).slice(4)); zip.remove(f); } else first.set(key, f);
  }
  for (const f of Object.keys(zip.files).filter(f => /^ppt\/slides\/_rels\/.*\.rels$/.test(f))) {
    let x = await zip.file(f).async('string');
    x = x.replace(/Target="\.\.\/(media\/[^"]+)"/g, (a, t) => gone.has(t) ? `Target="../${gone.get(t)}"` : a);
    zip.file(f, x);
  }
  let ct = await zip.file('[Content_Types].xml').async('string');
  for (const t of gone.keys()) ct = ct.replace(new RegExp(`<Override[^>]*PartName="/ppt/${t.replace(/[.]/g, '\\.')}"[^>]*/>`), '');
  zip.file('[Content_Types].xml', ct);
}
for (const f of Object.keys(zip.files)) if (zip.files[f].dir) delete zip.files[f];   // no folder entries in the package
writeFileSync(out, await zip.generateAsync({type: 'nodebuffer', compression: 'DEFLATE'}));
rmSync(tmp, {recursive: true, force: true});
// the font files, with their licence, in a fonts folder beside the deck, to install before opening it
{
  const src = join(ROOT, 'apps/mobile/assets/fonts'), dst = join(dirname(out), 'fonts');
  mkdirSync(dst, {recursive: true});
  for (const f of readdirSync(src).filter(f => /^IBMPlexSansArabic-.*\.ttf$|^OFL\.txt$/.test(f))) copyFileSync(join(src, f), join(dst, f));
}
console.log(`${plan.length} slides, ${nAnim} animations → ${out}`);
