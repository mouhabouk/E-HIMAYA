const fs = require('fs');
const d = require('docx');
const { S, blocks } = require('./content.js');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType,
  HeadingLevel, PageBreak, TableOfContents, Footer, Header, PageNumber, BorderStyle, LevelFormat, VerticalAlign } = d;

const FONT = 'Arial';
const NAVY = '1F3D99', ORANGE = 'E07B00', GREY = '5B6675';
const STATUS_FILL = { done: 'D9F2E0', partial: 'FFF1CC', approved: 'DCE8FA', proposed: 'EEE6F7', deferred: 'EEEEEE' };
const W = 9638; // A4 text width with 2 cm margins

const run = (text, o = {}) => new TextRun({ text, font: FONT, rightToLeft: true, size: o.size || 22, bold: o.bold, color: o.color, italics: o.italics });
const para = (text, o = {}) => new Paragraph({
  bidirectional: true, alignment: o.align || AlignmentType.START, spacing: { after: o.after ?? 120, before: o.before ?? 0, line: 300 },
  heading: o.heading, numbering: o.numbering, children: Array.isArray(text) ? text : [run(text, o)], border: o.border, shading: o.shading,
});

function cell(text, width, o = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: o.fill ? { type: ShadingType.CLEAR, color: 'auto', fill: o.fill } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [para(text, { size: o.size || 19, bold: o.bold, color: o.color, after: 0, align: o.align })],
  });
}
function table(widths, head, rows, fills) {
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: widths, visuallyRightToLeft: true,
    rows: [
      new TableRow({ tableHeader: true, children: head.map((h, i) => cell(h, widths[i], { fill: NAVY, bold: true, color: 'FFFFFF' })) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, widths[i], { fill: fills ? fills(ri, i) : (ri % 2 ? 'F4F6FA' : undefined) })) })),
    ],
  });
}

const out = [];
const counts = { done: 0, partial: 0, approved: 0, proposed: 0, deferred: 0 };
for (const [kind, v] of blocks) if (kind === 'req') v.forEach(r => counts[r[3]]++);
const total = Object.values(counts).reduce((a, b) => a + b, 0);
for (const [kind, v] of blocks) {
  switch (kind) {
    case 'title': out.push(para(v, { size: 56, bold: true, color: NAVY, align: AlignmentType.CENTER, before: 2400, after: 240 })); break;
    case 'subtitle': out.push(para(v, { size: 36, bold: true, color: ORANGE, align: AlignmentType.CENTER, after: 240 })); break;
    case 'subtitle2': out.push(para(v, { size: 24, color: GREY, align: AlignmentType.CENTER, after: 720 })); break;
    case 'meta': out.push(table([2400, 7238], ['البند', 'القيمة'], v)); break;
    case 'pagebreak': out.push(new Paragraph({ children: [new PageBreak()] })); break;
    case 'toc':
      out.push(para('المحتويات', { size: 32, bold: true, color: NAVY }));
      out.push(new TableOfContents('المحتويات', { hyperlink: true, headingStyleRange: '1-2' }));
      out.push(para('(إن لم يظهر الفهرس: انقر عليه بالزر الأيمن ثم «تحديث الحقل»)', { size: 18, color: GREY }));
      break;
    case 'h1': out.push(para(v, { heading: HeadingLevel.HEADING_1, size: 32, bold: true, color: NAVY, before: 360, after: 160,
      border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ORANGE, space: 4 } } })); break;
    case 'h2': out.push(para(v, { heading: HeadingLevel.HEADING_2, size: 27, bold: true, color: NAVY, before: 240, after: 120 })); break;
    case 'h3': out.push(para(v, { heading: HeadingLevel.HEADING_3, size: 23, bold: true, color: ORANGE, before: 180, after: 80 })); break;
    case 'p': out.push(para(v)); break;
    case 'summary': out.push(para(`حصيلة المتطلبات الوظيفية (${total} متطلباً): ` + Object.entries(counts).filter(([, n]) => n)
      .map(([k, n]) => `${S[k]} ${n}`).join('، ') + '.', { bold: true, color: NAVY })); break;
    case 'note': out.push(para(v, { size: 20, italics: true, color: GREY, shading: { type: ShadingType.CLEAR, color: 'auto', fill: 'FFF7E6' } })); break;
    case 'ul': for (const it of v) out.push(para(it, { numbering: { reference: 'bullets', level: 0 }, after: 60 })); break;
    case 'chain': out.push(para([run(v.join('  ←  '), { bold: true, color: NAVY, size: 24 })], { align: AlignmentType.CENTER, after: 200 })); break;
    case 'table': out.push(table(v.widths, v.head, v.rows)); out.push(para('', { after: 60 })); break;
    case 'req': {
      const rows = v.map(r => [r[0], r[1], r[2], S[r[3]], r[4]]);
      out.push(table([1250, 5288, 700, 1300, 1100], ['المعرف', 'المتطلب', 'الأولوية', 'الحالة', 'المرحلة'], rows,
        (ri, ci) => ci === 3 ? STATUS_FILL[v[ri][3]] : (ri % 2 ? 'F4F6FA' : undefined)));
      out.push(para('', { after: 60 }));
      break;
    }
  }
}
console.log(counts, total);

const doc = new Document({
  creator: 'e-Himaya', title: 'e-Himaya: الملف الوصفي V3', description: 'الملف الوصفي للمشروع، الإصدار الثالث',
  styles: {
    default: { document: { run: { font: FONT, size: 22, rightToLeft: true } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 32, bold: true, color: NAVY, font: FONT }, paragraph: { outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 27, bold: true, color: NAVY, font: FONT }, paragraph: { outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 23, bold: true, color: ORANGE, font: FONT }, paragraph: { outlineLevel: 2 } },
    ],
  },
  numbering: { config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.START,
    style: { paragraph: { indent: { start: 500, hanging: 300 } } } }] }] },
  features: { updateFields: true },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [para('ء-حماية e-Himaya · الملف الوصفي V3', { size: 16, color: GREY, align: AlignmentType.END })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: GREY })] })] }) },
    children: out,
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(process.argv[2] || 'out.docx', b); console.log('ok'); });
