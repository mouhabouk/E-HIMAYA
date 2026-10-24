const fs = require('fs');
const d = require('docx');
const { Document, Packer, Paragraph, TextRun, AlignmentType, HeadingLevel, PageBreak, Footer, Header, PageNumber, PageOrientation, ImageRun, BorderStyle, TableOfContents } = d;
const FONT = 'Arial', NAVY = '1F3D99', ORANGE = 'E07B00', GREY = '5B6675';
const run = (t, o = {}) => new TextRun({ text: t, font: FONT, rightToLeft: true, size: o.size || 21, bold: o.bold, color: o.color, italics: o.italics });
const para = (t, o = {}) => new Paragraph({ bidirectional: true, alignment: o.align || AlignmentType.START, heading: o.heading,
  spacing: { after: o.after ?? 100, before: o.before ?? 0, line: 280 }, children: [run(t, o)], border: o.border });
const png = f => { const b = fs.readFileSync(f); return { b, w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; };
const D = [
 ['1. المتداخلون والمنظومة', [
  ['01-context', 'مخطط السياق', 'كل المتداخلين مجمّعين حسب القناة: الهاتف لعموم المواطنين، البوابة للمؤسسات، اللوحة المركزية لأعوان الحماية المدنية بالتحقق بخطوتين، والأنظمة الخارجية (Keycloak، بوابة SMS، Firebase، الطقس، المقسم الهاتفي).'],
  ['03-interactions', 'خريطة التفاعل بين المتداخلين', 'من يرسل ماذا إلى من عبر المنظومة: البلاغ من المواطن إلى القاعة، الاستنفار من القاعة إلى المتطوع، الملف الطبي المقفل إلى طبيب الحماية المدنية، التوجيهات من اللجنة المركزية، الشهادة بين المؤسسة والمدقق، والتنبيهات من محرر المحتوى إلى المواطنين.'],
  ['02-architecture', 'البنية التقنية', 'المكونات وتدفقاتها: التطبيق والمتصفح، الخادم العكسي، الواجهة البرمجية والعمّال، Keycloak، MediaMTX، Asterisk، خدمات الذكاء الاصطناعي، PostgreSQL مع عزل حسب الولاية، والتخزين. يصلح أساساً لقسم «البنية» في كراس الشروط.'],
 ]],
 ['2. مخططات حالات الاستعمال (Use Case)', [
  ['10-uc-overview', 'نظرة عامة حسب الفاعل', 'الفاعلون الرئيسيون وعلاقة التعميم: المواطن المسجل يرث الزائر، والمتطوع والطبيب والمسؤول عن المؤسسة يرثون المواطن.'],
  ['11-uc-citizen', 'المواطن (التطبيق)', 'حالات استعمال التطبيق مع علاقات include وextend حول التبليغ، والفاعلان الثانويان: القاعة والأشخاص المرتبطون.'],
  ['12-uc-volunteer-doctor', 'المتطوعون والأطباء', 'من الترشح والجاهزية والاستنفار إلى توثيق الأطباء والمفتاح الشخصي وفتح الملف الطبي المسجَّل، ثم الإحالة إلى مختص والرأي المقفل وإعادة القفل لعضو اللجنة الجديد، و«من اطّلع على ملفي» للمواطن (C1-c).'],
  ['13-uc-org', 'المؤسسات (البوابة)', 'تسجيل المؤسسة والتصنيف الآلي وفريق السلامة والمواد الخطرة والوثائق، ثم الشهادة الموقّعة والتحقق العمومي منها.'],
  ['14-uc-staff', 'قاعة العمليات والقيادة', 'عمل المشغل ومدير العمليات وقائد الميدان واللجان والمحرر والمسؤولين، وكلها تمر بالتحقق بخطوتين.'],
 ]],
 ['3. مخططات الأصناف (Class)', [
  ['20-class-identity', 'الهوية والأدوار', 'الحساب والملف الشخصي والموافقات والمتطوع والطبيب وقرارات المراجعة، مع الولاية والمعتمدية وحسابات الأعوان في Keycloak.'],
  ['21-class-operations', 'البلاغات والحوادث والعمليات', 'البلاغ ووسائطه وتاريخ حالاته وتحليله الآلي والبث، والحادثة التي تجمع البلاغات، والتكليفات والاستنفار وطلبات الدعم والمستويات والتوجيهات.'],
  ['22-class-org', 'المؤسسات والشهادة', 'المؤسسة وأعضاؤها وفريق السلامة والمواد الخطرة والمعدات ونقاط الخريطة والوثائق بالإصدارات والشهادة الموقّعة.'],
  ['23-class-safety-medical', 'السلامة الشخصية والملف الطبي', 'الربط بين المستعملين، رسائل الاستغاثة، مشاركة الموقع، فحص السلامة، سجل المواقع، والملف الطبي المقفل بنسخة مفتاح لكل طبيب، والإحالة والرأي الطبي المقفل بنسخة مفتاح لكل قارئ (C1-c).'],
  ['24-class-content', 'التنبيهات والمحتوى والمكافآت والتتبع', 'الرسائل وقنوات إرسالها، اقتراحات الطقس، النصائح والدليل، طبقات الخريطة، النقاط والشارات، سجل التدقيق المتسلسل والختم، والذاكرة الوطنية.'],
 ]],
 ['4. مخططات التسلسل (Sequence)', [
  ['30-seq-report', 'التبليغ عن حادث', 'من الهاتف (حتى دون اتصال) إلى الخادم ثم التحليل الآلي ثم القاعة، وصولاً إلى متابعة المواطن لحالة بلاغه.'],
  ['31-seq-login', 'أول تشغيل والدخول بالهاتف', 'اللغة والشروط والأذونات، ثم المتابعة كزائر أو الدخول برمز SMS.'],
  ['32-seq-callout', 'استنفار المتطوعين', 'الجاهزية، ثم اختيار المتطوعين القريبين حسب الاختصاص، والإشعار، والرد بوقت الوصول، والوصول.'],
  ['33-seq-medical', 'الملف الطبي المقفل', 'إنشاء مفتاح الطبيب، تشفير الملف على هاتف المواطن لكل طبيب، ثم الفتح المسجَّل وفك التشفير على هاتف الطبيب فقط.'],
  ['38-seq-referral', 'الإحالة إلى مختص والرأي المقفل والشفافية', 'هاتف الطبيب يعيد قفل مفتاح الملف لكل مختص، والمختص يكتب رأيه ويقفله لقرّائه فقط، والمواطن يرى صفة من اطّلع على ملفه ووقته دون أسماء (C1-c).'],
  ['34-seq-safety', 'فحص السلامة ورسالة الاستغاثة', 'العدّ التنازلي و«أنا بخير»، أو التنبيه الحرج للأشخاص المرتبطين عند انتهاء المهلة.'],
  ['35-seq-live', 'البث المباشر', 'WHIP من الهاتف، والمشاهدة WHEP في اللوحة، والكشف الآلي عن الحريق والدخان، والتسجيل كأدلة.'],
  ['36-seq-certificate', 'شهادة سلامة المؤسسة', 'اكتمال الملف، المسودة، التقديم، مصادقة المدقق، PDF موقّع برمز QR، والتحقق العمومي.'],
  ['37-seq-alert', 'التنبيه الجغرافي', 'اقتراح آلي من الطقس أو تنبيه يدوي، مراجعة المحرر، ثم الإرسال إلى الأجهزة في المنطقة.'],
 ]],
 ['5. مخططات الحالات (State)', [
  ['40-state-report', 'حالات البلاغ', 'الانتقالات المسموح بها كما يفرضها الخادم.'],
  ['41-state-volunteer-doctor', 'حالات المتطوع والطبيب والشهادة', 'دورة حياة الطلبات والشهادة.'],
 ]],
];
const children = [
  para('ء-حماية e-Himaya', { size: 52, bold: true, color: NAVY, align: AlignmentType.CENTER, before: 1600 }),
  para('المخططات التحليلية والتصميمية (UML)', { size: 38, bold: true, color: ORANGE, align: AlignmentType.CENTER }),
  para('السياق، التفاعل بين المتداخلين، البنية، حالات الاستعمال، الأصناف، التسلسل، الحالات', { size: 24, color: GREY, align: AlignmentType.CENTER, after: 400 }),
  para('المخططات مستخرجة من المنظومة كما هي في الإصدار 0.9.0 (تحيين نهاية مرحلة نظام التصميم، 2026-10-24): الأصناف مبنية على مخطط قاعدة البيانات الفعلي (20 مخططاً و97 جدولاً تقريباً)، مع الاكتفاء بالسمات المهمة لكل صنف. والتسلسلات مبنية على المسارات الفعلية في الواجهة البرمجية.'),
  para('التسميات داخل المخططات بالفرنسية، وهي لغة كراسات الشروط المعتادة، والشرح بالعربية. المصادر بصيغة PlantUML مرفقة، ويمكن تعديلها وإعادة توليدها، ومعها الصور بصيغة SVG للطباعة بجودة عالية.'),
  para('سجل التحيين: الإصدار 1 (0.7.0) عند نهاية C1-b. الإصدار 2 (0.9.0): إضافة الإحالة والرأي المقفل والشفافية (C1-c) في مخطط حالات الاستعمال للأطباء ومخطط أصناف الملف الطبي ومخطط تسلسل جديد. مرحلة نظام التصميم لا تغيّر المخططات لأنها تخص المظهر فقط. يُحدَّث هذا الملف في نهاية كل مرحلة.', { size: 20, color: GREY }),
  new Paragraph({ children: [new PageBreak()] }),
  para('المحتويات', { size: 32, bold: true, color: NAVY }),
  new TableOfContents('المحتويات', { hyperlink: true, headingStyleRange: '1-2' }),
  new Paragraph({ children: [new PageBreak()] }),
];
for (const [sec, items] of D) {
  children.push(para(sec, { heading: HeadingLevel.HEADING_1, size: 32, bold: true, color: NAVY, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ORANGE, space: 4 } } }));
  items.forEach(([f, t, desc], i) => {
    if (i) children.push(new Paragraph({ children: [new PageBreak()] }));
    const { b, w, h } = png(`out/${f}.png`);
    const maxW = 940, maxH = 560, s = Math.min(maxW / w, maxH / h);
    children.push(para(t, { heading: HeadingLevel.HEADING_2, size: 26, bold: true, color: NAVY, before: 120 }));
    children.push(para(desc, { size: 20, color: GREY }));
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ type: 'png', data: b, transformation: { width: Math.round(w * s), height: Math.round(h * s) } })] }));
  });
  children.push(new Paragraph({ children: [new PageBreak()] }));
}
const doc = new Document({ creator: 'e-Himaya', title: 'e-Himaya: المخططات UML', features: { updateFields: true },
  styles: { default: { document: { run: { font: FONT, size: 21, rightToLeft: true } } }, paragraphStyles: [
    { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 32, bold: true, color: NAVY, font: FONT }, paragraph: { outlineLevel: 0 } },
    { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 26, bold: true, color: NAVY, font: FONT }, paragraph: { outlineLevel: 1 } }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838, orientation: PageOrientation.LANDSCAPE }, margin: { top: 800, bottom: 800, left: 900, right: 900 } } },
    headers: { default: new Header({ children: [para('ء-حماية e-Himaya · المخططات UML', { size: 16, color: GREY, align: AlignmentType.END })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: GREY })] })] }) },
    children }] });
Packer.toBuffer(doc).then(x => { fs.writeFileSync(process.argv[2], x); console.log('ok'); });
