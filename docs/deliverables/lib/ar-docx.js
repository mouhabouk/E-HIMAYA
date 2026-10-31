// Shared helpers for the Arabic Word deliverables of phase 4 (data dictionary, cards, security file, specification).
// Colours and type follow docs/design-system.md: IBM Plex Sans Arabic, ink #182038, navy #1F3FA0, amber [SIM] badge.
const fs = require('fs');
const d = require('docx');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType,
  HeadingLevel, TableOfContents, Footer, Header, PageNumber, BorderStyle, LevelFormat, VerticalAlign, ImageRun,
  PageBreak, PageOrientation } = d;

const FONT = 'IBM Plex Sans Arabic';
const C = { ink: '182038', muted: '5B6478', navy: '1F3FA0', navyTint: 'E8EDFA', red: 'D7141A', redTint: 'FDE8E8',
  orange: 'F08C00', green: '188038', greenTint: 'E6F4EA', amber: 'F5B400', amberTint: 'FFF3D6', amberText: '7A4B00',
  line: 'E3E7EF', zebra: 'F3F5FA', slateTint: 'EEF0F4', purpleTint: 'F2EAF8', tealTint: 'E0F3EF' };
const W = 9638; // A4 text width with 2 cm margins
const WL = 13958; // A4 landscape text width with 2 cm margins

// Text may carry [SIM]: it is drawn as the amber badge of the design system.
function runs(text, o = {}) {
  const parts = String(text ?? '').split(/(\[SIM\])/);
  return parts.filter(p => p !== '').map(p => p === '[SIM]'
    ? new TextRun({ text: ' SIM ', font: FONT, rightToLeft: true, size: (o.size || 21) - 2, bold: true, color: C.ink,
        shading: { type: ShadingType.CLEAR, color: 'auto', fill: C.amber } })
    : new TextRun({ text: p, font: FONT, rightToLeft: !o.ltr, size: o.size || 21, bold: o.bold, color: o.color || C.ink,
        italics: o.italics }));
}
const para = (text, o = {}) => new Paragraph({
  bidirectional: !o.ltr, alignment: o.align || AlignmentType.START, heading: o.heading, numbering: o.numbering,
  spacing: { after: o.after ?? 110, before: o.before ?? 0, line: o.line || 290 }, keepNext: o.keepNext,
  border: o.border, shading: o.shading, pageBreakBefore: o.pageBreakBefore,
  children: Array.isArray(text) ? text : runs(text, o),
});
const h1 = (t, o = {}) => para(t, { heading: HeadingLevel.HEADING_1, size: 32, bold: true, color: C.navy, before: 240, after: 140, keepNext: true, pageBreakBefore: o.pageBreak });
const h2 = (t, o = {}) => para(t, { heading: HeadingLevel.HEADING_2, size: 26, bold: true, color: C.navy, before: 200, after: 100, keepNext: true, pageBreakBefore: o.pageBreak });
const h3 = t => para(t, { heading: HeadingLevel.HEADING_3, size: 23, bold: true, color: C.ink, before: 160, after: 80, keepNext: true });
const p = (t, o = {}) => para(t, o);
const note = t => para(t, { size: 19, color: C.muted });
const bullet = (t, o = {}) => para(t, { ...o, numbering: { reference: 'bullets', level: o.level || 0 }, after: 60 });
const ul = items => items.map(t => bullet(t));
const code = t => para(t, { ltr: true, size: 17, color: C.ink, align: AlignmentType.LEFT, after: 40, line: 240,
  shading: { type: ShadingType.CLEAR, color: 'auto', fill: C.zebra } });

function cell(text, width, o = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: o.fill ? { type: ShadingType.CLEAR, color: 'auto', fill: o.fill } : undefined,
    verticalAlign: VerticalAlign.CENTER, columnSpan: o.span,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    borders: { top: { style: BorderStyle.SINGLE, size: 4, color: C.line }, bottom: { style: BorderStyle.SINGLE, size: 4, color: C.line },
      left: { style: BorderStyle.SINGLE, size: 4, color: C.line }, right: { style: BorderStyle.SINGLE, size: 4, color: C.line } },
    children: String(text ?? '').split('\n').map(line => para(line, { size: o.size || 18, bold: o.bold, color: o.color, after: 0,
      line: 250, ltr: o.ltr, align: o.ltr ? AlignmentType.LEFT : o.align })),
  });
}
// rows: arrays of strings; o.fills(ri, ci) -> fill, o.ltrCols: indexes of left-to-right columns (code, names).
function table(widths, head, rows, o = {}) {
  const ltr = new Set(o.ltrCols || []);
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: widths, visuallyRightToLeft: true,
    rows: [
      new TableRow({ tableHeader: true, cantSplit: true, children: head.map((h, i) => cell(h, widths[i], { fill: C.navy, bold: true, color: 'FFFFFF', size: o.size || 18 })) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, widths[i], {
        fill: o.fills ? o.fills(ri, i, r) : (ri % 2 ? C.zebra : undefined), ltr: ltr.has(i), size: o.size || 18,
        bold: o.boldCols && o.boldCols.includes(i) })) })),
    ],
  });
}
// A two-column "card" table: label | value.
function kv(rows, widths = [2600, W - 2600]) {
  return new Table({
    width: { size: widths[0] + widths[1], type: WidthType.DXA }, columnWidths: widths, visuallyRightToLeft: true,
    rows: rows.map(([k, v]) => new TableRow({ cantSplit: true, children: [cell(k, widths[0], { fill: C.navyTint, bold: true }), cell(v, widths[1])] })),
  });
}
function image(file, maxW = 600, maxH = 820) {
  const b = fs.readFileSync(file);
  const w = b.readUInt32BE(16), h = b.readUInt32BE(20);
  const s = Math.min(maxW / w, maxH / h, 1);
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
    children: [new ImageRun({ type: 'png', data: b, transformation: { width: Math.round(w * s), height: Math.round(h * s) } })] });
}
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });
const toc = () => [para('المحتويات', { size: 28, bold: true, color: C.navy }),
  new TableOfContents('المحتويات', { hyperlink: true, headingStyleRange: '1-2' }),
  note('(إن لم يظهر الفهرس: انقر عليه بالزر الأيمن ثم «تحديث الحقل»)'), pageBreak()];

function cover({ title, subtitle, lines = [], meta = [], logo }) {
  const out = [];
  if (logo && fs.existsSync(logo)) out.push(image(logo, 150, 150));
  out.push(para('ء-حماية  e-Himaya', { size: 44, bold: true, color: C.navy, align: AlignmentType.CENTER, before: logo ? 200 : 2400, after: 200 }));
  out.push(para(title, { size: 36, bold: true, align: AlignmentType.CENTER, after: 160 }));
  if (subtitle) out.push(para(subtitle, { size: 24, color: C.muted, align: AlignmentType.CENTER, after: 400 }));
  lines.forEach(l => out.push(para(l, { size: 22, align: AlignmentType.CENTER, after: 80 })));
  if (meta.length) { out.push(para('', { after: 300 })); out.push(kv(meta)); }
  out.push(pageBreak());
  return out;
}

// sections: [{ landscape, children }]; children alone makes one portrait (or landscape) section.
function document({ title, children, landscape = false, sections }) {
  const header = () => ({ default: new Header({ children: [para(`ء-حماية e-Himaya · ${title}`, { size: 16, color: C.muted, align: AlignmentType.CENTER, after: 0 })] }) });
  const footer = () => ({ default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
    new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: C.muted }),
    new TextRun({ text: ' / ', font: FONT, size: 16, color: C.muted }),
    new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 16, color: C.muted })] })] }) });
  const secs = (sections || [{ landscape, children }]).map(s => ({
    properties: { page: { size: s.landscape ? { orientation: PageOrientation.LANDSCAPE, width: 11906, height: 16838 } : { width: 11906, height: 16838 },
      margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } }, bidi: true },
    headers: header(), footers: footer(), children: s.children }));
  return new Document({
    creator: 'e-Himaya', title, description: title,
    styles: { default: { document: { run: { font: FONT, size: 21, color: C.ink } } },
      paragraphStyles: [
        { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: FONT, size: 32, bold: true, color: C.navy }, paragraph: { spacing: { before: 240, after: 140 }, outlineLevel: 0 } },
        { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: FONT, size: 26, bold: true, color: C.navy }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
        { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: FONT, size: 23, bold: true, color: C.ink }, paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
      ] },
    numbering: { config: [{ reference: 'bullets', levels: [
      { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.START, style: { paragraph: { indent: { start: 500, hanging: 260 } } } },
      { level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.START, style: { paragraph: { indent: { start: 900, hanging: 260 } } } }] }] },
    features: { updateFields: true },
    sections: secs,
  });
}
async function save(doc, out) { fs.writeFileSync(out, await Packer.toBuffer(doc)); console.log('written', out); }

module.exports = { d, C, W, WL, FONT, runs, para, p, h1, h2, h3, note, bullet, ul, code, cell, table, kv, image, pageBreak, toc, cover, document, save };
