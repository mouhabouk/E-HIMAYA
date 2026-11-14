// The deck kit of the «خوارزمية ء-حماية» look (Yamen, 2026-11-14), shared by the PowerPoint decks that are written
// with native shapes: the local AI tools deck (ai-tools-pptx.mjs) and the system presentation (pitch-pptx.mjs).
//
// A deck is built once per colour set: the night blueprint of the algorithm page and its day counterpart on the
// system's white base, each slide linked to its twin by a switch. The kit holds the palette, the fonts (Reem Kufi for
// titles, IBM Plex Sans Arabic for text, IBM Plex Mono for figures), the slide plan and its links, the helpers that
// draw the page's elements, and the writer that adds the native transitions, the entrance animations and the links
// to slides that pptxgenjs leaves out. Two front doors share it: createKit() for the AI tools and pitch decks, and
// deck() with finish() for the decks generated from the mind maps (mindmap-pptx.mjs) and the atlas (atlas-pptx.mjs).
import {createRequire} from 'node:module';
import {readFileSync, writeFileSync, mkdtempSync, rmSync, mkdirSync, readdirSync, copyFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

export const HERE = dirname(fileURLToPath(import.meta.url));
export const ROOT = join(HERE, '../..');
const req = createRequire(join(ROOT, 'docs/deliverables/package.json'));
export const pptxgen = req('pptxgenjs');
export const sharp = req('sharp');
const JSZip = req('jszip');

export const PALETTES = {
  night: {bg: '08102A', deck: '0E1426', panel: '161E35', line: '26304D', grid: '16224A', edge: '3A4770', root: '0E1426', shade: '050A1C',
    ink: 'E8ECF5', mute: 'A6AFC4', gold: 'C9A24A', teal: '4DD0B8', white: 'FFFFFF', onGold: '1B1405', no: 'FF6B6B', ok: '4CC772', onTone: '0E1426'},
  day: {bg: 'F6F8FC', deck: 'EEF2F9', panel: 'FFFFFF', line: 'D5DCEB', grid: 'E3E9F4', edge: 'B9C4DD', root: '1F3FA0', shade: 'DCE3F1',
    ink: '0E1426', mute: '55607A', gold: '9C7A22', teal: '0E7C8F', white: 'FFFFFF', onGold: 'FFFFFF', no: 'D7141A', ok: '188038', onTone: 'FFFFFF'},
};
// the category colours of the design system (docs/design-system.md §2.2 and §2.3): dark and light values
export const TONES = {
  red: {night: 'FF6B6B', day: 'D7141A'}, orange: {night: 'FFA733', day: 'C25E00'}, navy: {night: '8FA8FF', day: '1F3FA0'},
  purple: {night: 'C49BE6', day: '7838A0'}, sky: {night: '64B5F6', day: '1976D2'}, green: {night: '4CC772', day: '188038'},
  teal: {night: '4DD0B8', day: '00806A'}, amber: {night: 'FFC933', day: '9A6B00'}, pink: {night: 'F06292', day: 'C2185B'},
};
export const FONT = 'IBM Plex Sans Arabic', DISP = 'Reem Kufi', DISPM = 'Reem Kufi Medium', MONO = 'IBM Plex Mono Medium';
export const SYSTEM = 'منظومة ذكية للتبليغ والمشاركة المجتمعية والمؤسساتية في مجال السلامة والوقاية وإدارة الأخطار';
// any colour of a page (#abc, #aabbcc, rgb(), rgba()) as the six hex digits PowerPoint wants
export const hex = c => {
  c = String(c || '').trim();
  const m = c.match(/rgba?\(([^)]+)\)/i);
  if (m) return m[1].split(',').slice(0, 3).map(v => Math.round(+v).toString(16).padStart(2, '0')).join('').toUpperCase();
  c = c.replace('#', '');
  if (c.length === 3) c = c.split('').map(x => x + x).join('');
  return c.slice(0, 6).toUpperCase();
};
export const ind = n => String(n).replace(/\d/g, d => '٠١٢٣٤٥٦٧٨٩'[d]);
export const W = 13.333, H = 7.5;
export const AR = {rtlMode: true, lang: 'ar-SA', fontFace: FONT};
const ARABIC = /[\u0600-\u06FF]/;

const ground = async c => 'image/png;base64,' + (await sharp(Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
  <defs><pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0V40M0 40H40" stroke="#${c.grid}" stroke-width="2" fill="none"/></pattern>
  <radialGradient id="v" cx="50%" cy="40%" r="75%"><stop offset="0" stop-color="#${c.bg}" stop-opacity="0"/><stop offset="1" stop-color="#${c.shade}" stop-opacity=".85"/></radialGradient></defs>
  <rect width="1920" height="1080" fill="#${c.bg}"/><rect width="1920" height="1080" fill="url(#g)"/><rect width="1920" height="1080" fill="url(#v)"/></svg>`))
  .png().toBuffer()).toString('base64');

// createKit({title}) → the kit; plan the slides with add(), then for each mode: begin(mode) and draw, then write(out)
// motion: true lays the living grid (assets/grid-{night,day}.gif, from trust-backgrounds.py) under every slide
export async function createKit({title, footer = '', motion = false}) {
  const MODES = (process.env.DECK_SETS || 'night,day').split(',').filter(m => ['night', 'day'].includes(m));
  const EMBLEM = 'image/png;base64,' + readFileSync(join(HERE, 'assets/civil-protection-logo.png')).toString('base64');
  const WORD = 'image/png;base64,' + (await sharp(join(ROOT, 'infra/keycloak/themes/ehimaya/login/resources/img/logo-horizontal.png'))
    .extract({left: 0, top: 70, width: 590, height: 275}).png().toBuffer()).toString('base64');
  const GROUNDS = {night: await ground(PALETTES.night), day: await ground(PALETTES.day)};

  const pres = new pptxgen();
  pres.layout = 'LAYOUT_WIDE';
  pres.title = title;
  pres.author = 'e-Himaya';
  pres.rtlMode = true;
  pres.theme = {headFontFace: DISP, bodyFontFace: FONT};

  const plan = [], anim = [], shapeLinks = [];
  let C, MODE, GRID, OFF = 0, cur = 0, seq = 0;
  const nm = () => `s${cur}_${++seq}`;

  const K = {
    pres, plan, MODES, WORD, P: {},
    get C() { return C; }, get MODE() { return MODE; }, get N() { return plan.length; },
    home: 1,
    tone: t => (TONES[t] || {})[MODE] || t,
    add(t, o = {}) { plan.push({t, ...o}); return plan.length; },
    begin(mode) { MODE = mode; C = PALETTES[mode]; GRID = GROUNDS[mode]; OFF = MODES.indexOf(mode) * plan.length; },
    A(o, fx, delay, dur = 500, dir) { (anim[cur] ||= []).push({name: o.objectName, fx, delay, dur, dir}); return o; },
    link: n => n ? {hyperlink: {slide: n + OFF, tooltip: ''}} : {},
    text(s, t, o) {
      const opt = {...AR, isTextBox: true, margin: 0, color: C.ink, fontSize: 14, align: 'right', valign: 'middle', objectName: nm(), ...o};
      if (opt.hyperlink?.slide) (shapeLinks[cur] ||= {})[opt.objectName] = opt.hyperlink.slide;
      s.addText(t, opt); return opt;
    },
    shape(s, kind, o) {
      const opt = {objectName: nm(), ...o};
      if (opt.hyperlink?.slide) (shapeLinks[cur] ||= {})[opt.objectName] = opt.hyperlink.slide;
      s.addShape(kind, opt); return opt;
    },
    image(s, o) { const opt = {objectName: nm(), ...o}; s.addImage(opt); return opt; },
    emblem(s, x = 12.23, y = 0.28, w = 0.6) {
      const o = {data: EMBLEM, x, y, w, h: w, objectName: nm(), altText: 'شعار الديوان الوطني للحماية المدنية', ...K.link(K.home)};
      s.addImage(o); return o;
    },
    // under: an image laid over the whole slide beneath everything else, such as an animated GIF background
    newSlide(n, under) {
      cur = n + OFF; seq = 0;
      const s = pres.addSlide();
      if (pres.slides.length !== cur) throw new Error(`slide ${pres.slides.length} built where the plan expects ${cur}`);
      s.background = {data: GRID};
      under = under || (motion ? join(HERE, 'assets', `grid-${MODE}.gif`) : null);
      if (under) s.addImage({path: under, x: 0, y: 0, w: 13.333, h: 7.5, objectName: nm(), altText: ''});
      if (plan[n - 1].t !== 'cover') K.emblem(s);
      if (MODES.length < 2) return s;
      // the day / night switch: the same slide in the other colour set
      const other = n + (MODES.indexOf(MODE) === 0 ? plan.length : 0), w = 1.05, to = {hyperlink: {slide: other, tooltip: ''}};
      K.shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 0.5, y: 0.14, w, h: 0.28, rectRadius: 0.14, fill: {color: C.panel}, line: {color: C.line}, ...to});
      K.text(s, MODE === 'night' ? '☀ نهاري' : '☾ ليلي', {x: 0.5, y: 0.14, w, h: 0.28, align: 'center', fontSize: 9.5, color: C.ink, ...to});
      return s;
    },
    panel: (s, x, y, w, h, o = {}) => K.shape(s, pres.shapes.ROUNDED_RECTANGLE, {x, y, w, h, rectRadius: 0.14, fill: {color: C.panel}, line: {color: C.line, width: 1}, ...o}),
    button(s, label, x, y, w, to, primary = false) {
      K.shape(s, pres.shapes.ROUNDED_RECTANGLE, {x, y, w, h: 0.36, rectRadius: 0.18, fill: {color: primary ? C.gold : C.panel}, line: {color: primary ? C.gold : C.line}, ...K.link(to)});
      K.text(s, label, {x, y, w, h: 0.36, align: 'center', fontSize: 11.5, bold: primary, color: primary ? C.onGold : C.ink, ...K.link(to)});
    },
    crumb: (s, label) => K.text(s, label, {x: 4.6, y: 0.3, w: 7.45, h: 0.3, fontSize: 11, bold: true, color: C.gold}),
    title(s, label, num) {
      const t = num != null ? [{text: ind(num) + '  ', options: {color: C.gold, fontFace: DISP, fontSize: 30}}, {text: label, options: {}}] : label;
      return K.A(K.text(s, t, {x: 3.6, y: 0.58, w: 8.45, h: 0.62, fontSize: 28, fontFace: DISPM, color: C.ink, fit: 'shrink'}), 'fade', 0, 500);
    },
    lead: (s, t, o = {}) => K.A(K.text(s, t, {x: 2.9, y: 1.22, w: 9.15, h: 0.36, fontSize: 13.5, color: C.mute, ...o}), 'fade', 150, 500),
    counter: (s, n) => K.text(s, `${n} / ${plan.length}`, {x: 0.5, y: 7.08, w: 1.4, h: 0.25, fontSize: 9, fontFace: MONO, align: 'left', color: C.mute}),
    foot: s => footer && K.text(s, footer, {x: 6.0, y: 7.08, w: 6.83, h: 0.25, fontSize: 9, color: C.mute}),
    // a figure of the page: a rule on top, the number in mono, the label under it
    figure(s, x, y, w, v, l, dl, col = C.gold, size = 24) {
      K.A(K.shape(s, pres.shapes.LINE, {x, y, w, h: 0, line: {color: col, width: 1.75}}), 'wipe', dl, 500, 'l');
      K.A(K.text(s, String(v), {x, y: y + 0.08, w, h: 0.5 * size / 24, fontSize: size, fontFace: MONO, color: C.ink, bold: true,
        ...(ARABIC.test(v) ? {} : {rtlMode: false, lang: 'en-US'})}), 'fade', dl + 150, 500);
      K.A(K.text(s, l, {x, y: y + 0.08 + 0.5 * size / 24, w, h: 0.3, fontSize: 10.5, color: C.mute}), 'fade', dl + 200, 500);
    },
    // short lines, each with a coloured dot on the right
    list(s, items, x, y, w, lineH, col, dl, fs = 13) {
      items.forEach((t, k) => {
        const yy = y + k * lineH;
        K.A(K.shape(s, pres.shapes.OVAL, {x: x + w - 0.13, y: yy + 0.13, w: 0.11, h: 0.11, fill: {color: col}}), 'fade', dl + k * 120, 400);
        K.A(K.text(s, t, {x, y: yy, w: w - 0.25, h: lineH - 0.04, fontSize: fs, valign: 'top', color: C.ink, lineSpacingMultiple: 0.95}), 'fade', dl + k * 120, 400);
      });
    },
    // the wordmark, on royal blue in the day set (it is white)
    wordmark(s, x, y, w, dl = 300) {
      const h = w * 275 / 590;
      if (MODE === 'day') K.shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: x - 0.15, y: y - 0.1, w: w + 0.3, h: h + 0.2, rectRadius: 0.16, fill: {color: C.root}});
      K.A(K.image(s, {data: WORD, x, y, w, h, altText: 'ء-حماية E-HIMAYA'}), 'fade', dl, 900);
    },
  };

  // ------------------------------------------------------------ write, then add transitions, animations and links
  K.write = async (out, TRANS = {}) => {
    const N = plan.length;
    const tmp = mkdtempSync(join(tmpdir(), 'deck-'));
    const raw = join(tmp, 'raw.pptx');
    await pres.writeFile({fileName: raw});
    const zip = await JSZip.loadAsync(readFileSync(raw));
    const effect = (e, spid, ids) => {
      const id = () => ++ids.n;
      const par = id();
      let sub = 0, filter = 'fade', preset = 10, extra = '';
      if (e.fx === 'wipe') { preset = 22; sub = {l: 8, r: 2, u: 1, d: 4}[e.dir || 'l']; filter = `wipe(${{l: 'left', r: 'right', u: 'up', d: 'down'}[e.dir || 'l']})`; }
      else if (e.fx === 'zoom') {
        preset = 53; sub = 16;
        extra = ['ppt_w', 'ppt_h'].map(a => `<p:anim calcmode="lin" valueType="num"><p:cBhvr><p:cTn id="${id()}" dur="${e.dur}" fill="hold"/><p:tgtEl><p:spTgt spid="${spid}"/></p:tgtEl><p:attrNameLst><p:attrName>${a}</p:attrName></p:attrNameLst></p:cBhvr><p:tavLst><p:tav tm="0"><p:val><p:fltVal val="0"/></p:val></p:tav><p:tav tm="100000"><p:val><p:strVal val="#${a}"/></p:val></p:tav></p:tavLst></p:anim>`).join('');
      }
      const set = `<p:set><p:cBhvr><p:cTn id="${id()}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn><p:tgtEl><p:spTgt spid="${spid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>`;
      const fx = `<p:animEffect transition="in" filter="${filter}"><p:cBhvr><p:cTn id="${id()}" dur="${e.dur}"/><p:tgtEl><p:spTgt spid="${spid}"/></p:tgtEl></p:cBhvr></p:animEffect>`;
      return `<p:par><p:cTn id="${par}" presetID="${preset}" presetClass="entr" presetSubtype="${sub}" fill="hold" grpId="0" nodeType="withEffect"><p:stCondLst><p:cond delay="${Math.round(e.delay)}"/></p:stCondLst><p:childTnLst>${set}${extra}${fx}</p:childTnLst></p:cTn></p:par>`;
    };
    let nAnim = 0;
    for (let n = 1; n <= MODES.length * N; n++) {
      const f = `ppt/slides/slide${n}.xml`;
      let xml = await zip.file(f).async('string');
      const ids = {}; for (const m of xml.matchAll(/<p:cNvPr id="(\d+)" name="([^"]+)"/g)) ids[m[2]] = m[1];
      const kind = {}; for (const m of xml.matchAll(/<p:(sp|pic|graphicFrame)>\s*<p:nv\w+Pr>\s*<p:cNvPr id="(\d+)"/g)) kind[m[2]] = m[1];
      const list = (anim[n] || []).filter(e => ids[e.name]).sort((a, b) => a.delay - b.delay);
      const trans = `<p:transition spd="med">${TRANS[plan[(n - 1) % N].t] || '<p:fade/>'}</p:transition>`;
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
      // pptxgenjs writes no relationship for a link on a shape or a text box: write it here, on the object itself
      if (shapeLinks[n]) {
        const rf = `ppt/slides/_rels/slide${n}.xml.rels`;
        let rels = await zip.file(rf).async('string');
        let next = Math.max(0, ...[...rels.matchAll(/Id="rId(\d+)"/g)].map(m => +m[1])) + 1;
        xml = xml.split(/(?=<p:cNvPr id="\d+" name=")/).map(part => {
          const name = part.match(/^<p:cNvPr id="\d+" name="([^"]+)"/)?.[1], to = name && shapeLinks[n][name];
          if (!to) return part;
          const id = `rId${next++}`;
          rels = rels.replace('</Relationships>', `<Relationship Id="${id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slide${to}.xml"/></Relationships>`);
          return part.replace(/ u="sng"/g, '').replace(/<a:hlinkClick\b[^>]*?(?:\/>|>[\s\S]*?<\/a:hlinkClick>)/g, '')
            .replace(/^(<p:cNvPr [^>]*?)(?:\/>|><\/p:cNvPr>)/, `$1><a:hlinkClick r:id="${id}" action="ppaction://hlinksldjump"/></p:cNvPr>`);
        }).join('');
        zip.file(rf, rels);
      }
      zip.file(f, xml);
    }
    // the theme carries the night set, so PowerPoint's colour picker offers it first
    {
      const f = Object.keys(zip.files).find(f => /^ppt\/theme\/theme\d+\.xml$/.test(f));
      let x = await zip.file(f).async('string');
      const T = {dk1: '08102A', lt1: 'FFFFFF', dk2: '0E1426', lt2: 'E8ECF5', accent1: 'C9A24A', accent2: '4DD0B8', accent3: '8FA8FF',
        accent4: 'FFC933', accent5: 'C49BE6', accent6: 'FF6B6B', hlink: 'C9A24A', folHlink: 'A6AFC4'};
      for (const [k, v] of Object.entries(T)) x = x.replace(new RegExp(`<a:${k}>[\\s\\S]*?</a:${k}>`), `<a:${k}><a:srgbClr val="${v}"/></a:${k}>`);
      x = x.replace(/<a:clrScheme name="[^"]*"/, '<a:clrScheme name="E-HIMAYA الليلي"');
      zip.file(f, x);
    }
    // one copy of each image, every slide pointing at it
    {
      const first = new Map(), gone = new Map();
      for (const f of Object.keys(zip.files).filter(f => f.startsWith('ppt/media/') && !zip.files[f].dir).sort()) {
        const key = await zip.file(f).async('base64');
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
    for (const f of Object.keys(zip.files)) if (zip.files[f].dir) delete zip.files[f];
    writeFileSync(out, await zip.generateAsync({type: 'nodebuffer', compression: 'DEFLATE'}));
    rmSync(tmp, {recursive: true, force: true});
    // the font files and their licence, in a fonts folder beside the deck, to install before opening it
    const src = join(ROOT, 'apps/mobile/assets/fonts'), dst = join(dirname(out), 'fonts');
    mkdirSync(dst, {recursive: true});
    for (const f of readdirSync(src).filter(f => /^IBMPlexSansArabic-.*\.ttf$|^OFL\.txt$/.test(f))) copyFileSync(join(src, f), join(dst, f));
    for (const f of readdirSync(join(HERE, 'assets/fonts'))) copyFileSync(join(HERE, 'assets/fonts', f), join(dst, f));
    console.log(`${MODES.length * N} slides (${MODES.join(' and ')}), ${nAnim} animations → ${out}`);
  };
  return K;
}

// ---- deck() and finish(): the module-level brand pictures and the plan-by-number deck ----
// the colour sets to build, in order: both by default (with the switch), or one (DECK_SETS=day writes the day deck alone)
export const MODES = (process.env.DECK_SETS || 'night,day').split(',').filter(m => ['night', 'day'].includes(m));

// brand pictures: the Office's emblem and the system's wordmark (white and gold, from the sign-in theme)
export const EMBLEM = 'image/png;base64,' + readFileSync(join(HERE, 'assets/civil-protection-logo.png')).toString('base64');
export const WORD = 'image/png;base64,' + (await sharp(join(ROOT, 'infra/keycloak/themes/ehimaya/login/resources/img/logo-horizontal.png'))
  .extract({left: 0, top: 70, width: 590, height: 275}).png().toBuffer()).toString('base64');
export const WORD_AR = 275 / 590;
export const GROUNDS = {night: await ground(PALETTES.night), day: await ground(PALETTES.day)};

// A deck: N slides per colour set, built set after set. `k.set(mode)` switches the set; slide numbers given to the
// helpers are those of the plan (1..N) and become absolute in the set being built.
export function deck(title, N, homeSlide) {
  const pres = new pptxgen();
  pres.layout = 'LAYOUT_WIDE';
  pres.title = title;
  pres.rtlMode = true;
  pres.theme = {headFontFace: DISP, bodyFontFace: FONT};
  const anim = [], shapeLinks = [];
  const k = {pres, anim, shapeLinks, N, C: PALETTES.night, MODE: 'night', OFF: 0, cur: 0, seq: 0};
  const nm = () => `s${k.cur}_${++k.seq}`;
  k.set = mode => { k.MODE = mode; k.C = PALETTES[mode]; k.OFF = MODES.indexOf(mode) * N; };
  k.A = (o, fx, delay, dur = 500, dir) => { (anim[k.cur] ||= []).push({name: o.objectName, fx, delay, dur, dir}); return o; };
  k.link = n => n ? {hyperlink: {slide: n + k.OFF, tooltip: ''}} : {};
  const keep = opt => { if (opt.hyperlink?.slide) (shapeLinks[k.cur] ||= {})[opt.objectName] = opt.hyperlink.slide; return opt; };
  k.text = (s, t, o) => { const opt = keep({...AR, isTextBox: true, margin: 0, color: k.C.ink, fontSize: 14, align: 'right', valign: 'middle', objectName: nm(), ...o}); s.addText(t, opt); return opt; };
  k.shape = (s, kind, o) => { const opt = keep({objectName: nm(), ...o}); s.addShape(kind, opt); return opt; };
  k.image = (s, o) => { const opt = {objectName: nm(), ...o}; s.addImage(opt); return opt; };
  k.panel = (s, x, y, w, h, o = {}) => k.shape(s, pres.shapes.ROUNDED_RECTANGLE, {x, y, w, h, rectRadius: 0.18, fill: {color: k.C.panel}, line: {color: k.C.line, width: 1}, ...o});
  k.box = (s, x, y, w, h) => k.shape(s, pres.shapes.ROUNDED_RECTANGLE, {x, y, w, h, rectRadius: 0.2, fill: {color: k.C.deck, transparency: 15}, line: {color: k.C.line}});
  // the pill buttons of the page: gold for the main action, the panel colour with a hairline for the others
  k.button = (s, label, x, y, w, to, primary = false) => {
    const o = k.shape(s, pres.shapes.ROUNDED_RECTANGLE, {x, y, w, h: 0.38, rectRadius: 0.19, fill: {color: primary ? k.C.gold : k.C.panel},
      line: {color: primary ? k.C.gold : k.C.line}, ...k.link(to)});
    const t = k.text(s, label, {x, y, w, h: 0.38, align: 'center', fontSize: 12, bold: primary, color: primary ? k.C.onGold : k.C.ink, ...k.link(to)});
    return [o, t];
  };
  // the eyebrow (gold, the step of the page) and the act title (gold numeral, display face)
  k.crumb = (s, label) => k.text(s, label, {x: 4.6, y: 0.3, w: 7.45, h: 0.3, fontSize: 11, bold: true, color: k.C.gold, fit: 'shrink'});
  k.title = (s, label, num) => {
    const t = num != null ? [{text: ind(num) + '  ', options: {color: k.C.gold, fontFace: DISP, fontSize: 30}}, {text: label, options: {}}] : label;
    return k.text(s, t, {x: 4.1, y: 0.58, w: 7.95, h: 0.62, fontSize: 28, fontFace: DISPM, color: k.C.ink, fit: 'shrink'});
  };
  k.emblem = (s, x = 12.23, y = 0.28, w = 0.6) => {
    const o = {data: EMBLEM, x, y, w, h: w, objectName: nm(), altText: 'شعار الديوان الوطني للحماية المدنية', ...k.link(homeSlide)};
    s.addImage(o); return o;
  };
  k.counter = (s, n) => k.text(s, `${n} / ${N}`, {x: 0.5, y: 7.08, w: 1.4, h: 0.25, fontSize: 9, fontFace: MONO, align: 'left', color: k.C.mute});
  // a figure of the page: a gold rule on top, the number in mono, the label under it
  k.figure = (s, x, y, w, v, l, dl) => {
    k.A(k.shape(s, pres.shapes.LINE, {x, y, w, h: 0, line: {color: k.C.gold, width: 1.75}}), 'wipe', dl, 500, 'l');
    k.A(k.text(s, String(v), {x, y: y + 0.08, w, h: 0.5, fontSize: 26, fontFace: MONO, color: k.C.ink, bold: true}), 'fade', dl + 150, 500);
    k.A(k.text(s, l, {x, y: y + 0.56, w, h: 0.28, fontSize: 11, color: k.C.mute}), 'fade', dl + 200, 500);
  };
  // a new slide of the plan: the ground, the emblem, and the day / night switch to the same slide in the other set
  k.slide = (n, {emblem = true} = {}) => {
    k.cur = n + k.OFF; k.seq = 0;
    const s = pres.addSlide();
    if (pres.slides.length !== k.cur) throw new Error(`slide ${pres.slides.length} built where the plan expects ${k.cur}`);
    s.background = {data: GROUNDS[k.MODE]};
    if (emblem) k.emblem(s);
    if (MODES.length > 1) {
      const other = {hyperlink: {slide: n + (MODES.indexOf(k.MODE) === 0 ? N : 0), tooltip: ''}}, w = 1.05;
      k.shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 0.5, y: 0.14, w, h: 0.28, rectRadius: 0.14, fill: {color: k.C.panel}, line: {color: k.C.line}, ...other});
      k.text(s, k.MODE === 'night' ? '☀ نهاري' : '☾ ليلي', {x: 0.5, y: 0.14, w, h: 0.28, align: 'center', fontSize: 9.5, color: k.C.ink, ...other});
    }
    return s;
  };
  return k;
}

// ---------------------------------------------------------------- writing: native transitions, animations and links
const ENTR = {
  fade: {id: 10, sub: 0, filter: 'fade'},
  wipe: {id: 22, sub: {l: 8, r: 2, u: 1, d: 4}, filter: {l: 'wipe(left)', r: 'wipe(right)', u: 'wipe(up)', d: 'wipe(down)'}},
  zoom: {id: 53, sub: 16, filter: 'fade'},
};
function effect(e, spid, ids) {
  const id = () => ++ids.n;
  const par = id();
  let sub = 0, filter = 'fade', preset = ENTR[e.fx].id, extra = '';
  if (e.fx === 'wipe') {
    if (e.dir === 'cw') { preset = 21; sub = 1; filter = 'wheel(1)'; }   // wheel, one spoke: doughnuts and progress rings
    else { sub = ENTR.wipe.sub[e.dir || 'l']; filter = ENTR.wipe.filter[e.dir || 'l']; }
  } else if (e.fx === 'zoom') {
    extra = ['ppt_w', 'ppt_h'].map(a => `<p:anim calcmode="lin" valueType="num"><p:cBhvr><p:cTn id="${id()}" dur="${e.dur}" fill="hold"/><p:tgtEl><p:spTgt spid="${spid}"/></p:tgtEl><p:attrNameLst><p:attrName>${a}</p:attrName></p:attrNameLst></p:cBhvr><p:tavLst><p:tav tm="0"><p:val><p:fltVal val="0"/></p:val></p:tav><p:tav tm="100000"><p:val><p:strVal val="#${a}"/></p:val></p:tav></p:tavLst></p:anim>`).join('');
    sub = 16;
  }
  const set = `<p:set><p:cBhvr><p:cTn id="${id()}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn><p:tgtEl><p:spTgt spid="${spid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>`;
  const fx = `<p:animEffect transition="in" filter="${filter}"><p:cBhvr><p:cTn id="${id()}" dur="${e.dur}"/><p:tgtEl><p:spTgt spid="${spid}"/></p:tgtEl></p:cBhvr></p:animEffect>`;
  return `<p:par><p:cTn id="${par}" presetID="${preset}" presetClass="entr" presetSubtype="${sub}" fill="hold" grpId="0" nodeType="withEffect"><p:stCondLst><p:cond delay="${Math.round(e.delay)}"/></p:stCondLst><p:childTnLst>${set}${extra}${fx}</p:childTnLst></p:cTn></p:par>`;
}

// Writes the deck, then adds per slide its transition (transOf(n) → '<p:fade/>' …) and its timing, resolves the links
// pptxgenjs leaves on shapes, puts the night set in the theme, keeps one copy of each picture, and copies the font
// files to <out-dir>/fonts. Returns the number of animations.
export async function finish(k, out, transOf) {
  const tmp = mkdtempSync(join(tmpdir(), 'deck-pptx-'));
  const raw = join(tmp, 'raw.pptx');
  await k.pres.writeFile({fileName: raw});
  const zip = await JSZip.loadAsync(readFileSync(raw));
  let nAnim = 0;
  for (let n = 1; n <= k.pres.slides.length; n++) {
    const f = `ppt/slides/slide${n}.xml`;
    let xml = await zip.file(f).async('string');
    const ids = {}; for (const m of xml.matchAll(/<p:cNvPr id="(\d+)" name="([^"]+)"/g)) ids[m[2]] = m[1];
    // what each object is, for its build entry: text shapes get bldP, charts bldGraphic, pictures none (as PowerPoint writes)
    const kind = {}; for (const m of xml.matchAll(/<p:(sp|pic|graphicFrame)>\s*<p:nv\w+Pr>\s*<p:cNvPr id="(\d+)"/g)) kind[m[2]] = m[1];
    const list = (k.anim[n] || []).filter(e => ids[e.name]).sort((a, b) => a.delay - b.delay);
    const trans = `<p:transition spd="med">${transOf(n)}</p:transition>`;
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
    if (k.shapeLinks[n]) {
      const rf = `ppt/slides/_rels/slide${n}.xml.rels`;
      let rels = await zip.file(rf).async('string');
      let next = Math.max(0, ...[...rels.matchAll(/Id="rId(\d+)"/g)].map(m => +m[1])) + 1;
      // pptxgenjs writes no relationship for a link on a shape: the whole object becomes the link, with none on its
      // runs, so a linked label keeps its colour and has no underline
      xml = xml.split(/(?=<p:cNvPr id="\d+" name=")/).map(part => {
        const name = part.match(/^<p:cNvPr id="\d+" name="([^"]+)"/)?.[1], to = name && k.shapeLinks[n][name];
        if (!to) return part;
        const id = `rId${next++}`;
        rels = rels.replace('</Relationships>', `<Relationship Id="${id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slide${to}.xml"/></Relationships>`);
        return part.replace(/ u="sng"/g, '').replace(/<a:hlinkClick\b[^>]*?(?:\/>|>[\s\S]*?<\/a:hlinkClick>)/g, '')
          .replace(/^(<p:cNvPr [^>]*?)(?:\/>|><\/p:cNvPr>)/, `$1><a:hlinkClick r:id="${id}" action="ppaction://hlinksldjump"/></p:cNvPr>`);
      }).join('');
      zip.file(rf, rels);
    }
    zip.file(f, xml);
  }
  // the theme carries the night set, so PowerPoint's colour picker offers it first
  {
    const f = Object.keys(zip.files).find(f => /^ppt\/theme\/theme\d+\.xml$/.test(f));
    let x = await zip.file(f).async('string');
    const T = {dk1: '08102A', lt1: 'FFFFFF', dk2: '0E1426', lt2: 'E8ECF5', accent1: 'C9A24A', accent2: '4DD0B8', accent3: '8FA8FF',
      accent4: 'FFC933', accent5: 'C49BE6', accent6: 'FF6B6B', hlink: 'C9A24A', folHlink: 'A6AFC4'};
    for (const [key, v] of Object.entries(T)) x = x.replace(new RegExp(`<a:${key}>[\\s\\S]*?</a:${key}>`), `<a:${key}><a:srgbClr val="${v}"/></a:${key}>`);
    x = x.replace(/<a:clrScheme name="[^"]*"/, '<a:clrScheme name="E-HIMAYA الليلي"');
    zip.file(f, x);
  }
  // pptxgenjs writes one copy of a picture per slide: keep one copy of each and point every slide at it
  {
    const first = new Map(), gone = new Map();
    for (const f of Object.keys(zip.files).filter(f => f.startsWith('ppt/media/') && !zip.files[f].dir).sort()) {
      const key = await zip.file(f).async('base64');
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
  const src = join(ROOT, 'apps/mobile/assets/fonts'), dst = join(dirname(out), 'fonts');
  mkdirSync(dst, {recursive: true});
  for (const f of readdirSync(src).filter(f => /^IBMPlexSansArabic-.*\.ttf$|^OFL\.txt$/.test(f))) copyFileSync(join(src, f), join(dst, f));
  // the display and mono faces of the algorithm page (Google Fonts, SIL OFL 1.1, like the text face)
  for (const f of readdirSync(join(HERE, 'assets/fonts'))) copyFileSync(join(HERE, 'assets/fonts', f), join(dst, f));
  return nAnim;
}
