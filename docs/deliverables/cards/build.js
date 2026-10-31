// The three detailed cards (functional, non-functional, technical) and the BPMN processes (review point 11, phase 4).
//   node build.js <bpmn-dir> <dict.json> <out.docx>
// The requirements, NFR and technologies are read from the project description (../description/content.js), so the
// cards never drift from the specification; the database figures from the data dictionary extract.
const fs = require('fs');
const path = require('path');
const L = require('../lib/ar-docx.js');
const { C, W, WL, h1, h2, h3, p, note, ul, table, kv, image, toc, cover, document, save } = L;
const { S, blocks } = require('../description/content.js');
const processes = require('../bpmn/processes.js');

const [bpmnDir, dictFile, out] = process.argv.slice(2);
const dict = JSON.parse(fs.readFileSync(dictFile, 'utf8'));
const api = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'api', 'openapi.json'), 'utf8'));
const ops = Object.values(api.paths).reduce((n, v) => n + Object.keys(v).filter(m => ['get', 'post', 'put', 'patch', 'delete'].includes(m)).length, 0);
const today = new Date().toISOString().slice(0, 10);
const PRIO = { M: 'إلزامي', S: 'مهم', C: 'اختياري' };

// Requirements grouped by component (h2) and sub-section (h3).
const comps = [];
let h2cur = null, h3cur = null, nfr = null, tech = null, sims = null, arch = null, sec = null;
for (let i = 0; i < blocks.length; i++) {
  const [k, v] = blocks[i];
  if (k === 'h1') { h2cur = null; }
  if (k === 'h2') { h2cur = { title: v, groups: [] }; if (/^4\.\d/.test(v)) comps.push(h2cur); h3cur = null; }
  if (k === 'h3' && h2cur) { h3cur = { title: v, reqs: [] }; h2cur.groups.push(h3cur); }
  if (k === 'req' && h2cur) { if (!h3cur) { h3cur = { title: h2cur.title, reqs: [] }; h2cur.groups.push(h3cur); } h3cur.reqs.push(...v); }
  if (k === 'table' && v.head && v.head[0] === 'المعرف' && v.head[2] === 'المتطلب القابل للقياس') nfr = v;
  if (k === 'table' && v.head && v.head[0] === 'الطبقة') tech = v;
  if (k === 'table' && v.head && v.head[0] === 'المحاكي') sims = v;
  if (k === 'h2' && v.startsWith('7.1')) arch = blocks[i + 1][1];
  if (k === 'h2' && v.startsWith('7.4')) sec = blocks[i + 1][1];
}
const all = comps.flatMap(c => c.groups.flatMap(g => g.reqs));
const count = (rs, f) => rs.filter(f).length;

const children = [
  ...cover({ title: 'البطاقات الوظيفية وغير الوظيفية والتقنية', subtitle: 'ومخططات سير العمل BPMN 2.0',
    logo: path.join(__dirname, '..', '..', '..', 'apps', 'dashboard', 'public', 'brand', 'logo.png'),
    meta: [['الإصدار', '1.0 (المرحلة 4، النقطة 11)'], ['التاريخ', today],
      ['المصدر', 'الملف الوصفي V33 (المتطلبات والقيود)، والقاعدة الفعلية (الترحيل ' + dict.migration + ')، و OpenAPI ' + api.info.version],
      ['الملفات المرافقة', processes.map(x => x.file + '.bpmn').join('، ') + ': تُفتح في Camunda Modeler أو bpmn.io أو Bizagi']] }),
  ...toc(),
  h1('0. الغرض'),
  p('تلخّص هذه الوثيقة المنظومة في ثلاث بطاقات يمكن إلحاقها بكراس الشروط كما هي: البطاقة الوظيفية (ماذا تفعل المنظومة ولمن)، والبطاقة غير الوظيفية (بأي جودة، وكيف تُقاس)، والبطاقة التقنية (بأي مكونات وأي بنية). وتسبقها مخططات سير العمل الرئيسية بترميز BPMN 2.0 المعياري.'),
  table([3000, 2200, 4438], ['البطاقة', 'العدد', 'المرجع'], [
    ['البطاقة الوظيفية', `${all.length} متطلبا في ${comps.length} مكونات`, 'الملف الوصفي، القسم 4'],
    ['البطاقة غير الوظيفية', `${nfr.rows.length} متطلبا قابلا للقياس`, 'الملف الوصفي، القسم 6'],
    ['البطاقة التقنية', `${tech.rows.length} طبقة تقنية، ${ops} عملية API، ${dict.counts.tables} جدولا`, 'الملف الوصفي، القسم 7، وقاموس البيانات'],
    ['مخططات BPMN', `${processes.length} مسارات`, 'هذه الوثيقة، القسم 1'],
  ]),

];
const bpmn = [
  h1('1. مخططات سير العمل (BPMN 2.0)'),
  p('المسارات مرسومة بالترميز المعياري: الدائرة الخضراء بداية، والحمراء نهاية، والمستطيل الأزرق مهمة يؤديها شخص، والأخضر المائل مهمة آلية للمنظومة، والمعيّن قرار، والساعة مهلة. كل مسار في ملف .bpmn قابل للتعديل.'),
  ...ul(['الرموز: start = بداية، userTask = مهمة بشرية، serviceTask = مهمة آلية، exclusiveGateway = قرار حصري، timer = مهلة، message = إشعار.']),
];
processes.forEach((pr, i) => {
  bpmn.push(h2(`1.${i + 1} ${pr.title}`, { pageBreak: i > 0 }));
  bpmn.push(note(`المتداخلون (المسارات الأفقية): ${pr.lanes.join('، ')}. الملف: ${pr.file}.bpmn`));
  bpmn.push(image(path.join(bpmnDir, `${pr.file}.png`), 930, 520));
});
const rest = [];

// Card 1: functional.
rest.push(h1('2. البطاقة الوظيفية'));
rest.push(kv([
  ['الغرض', 'منظومة ذكية للتبليغ والمشاركة المجتمعية والمؤسساتية في الوقاية والسلامة وإدارة المخاطر، من التبليغ إلى أخذ القرار.'],
  ['المستعملون', 'المواطن والزائر، المتطوع والطبيب المتطوع، المؤسسة، أعوان القاعات الجهوية والمركزية، الفرق الميدانية، القادة، اللجان الجهوية والوطنية، مدير النظام.'],
  ['المكونات', comps.map(c => c.title.replace(/^4\.\d+ /, '')).join('؛ ')],
  ['الحالة', `${count(all, r => r[3] === 'done')} منجزا و ${count(all, r => r[3] === 'partial')} منجزا جزئيا من ${all.length}`],
]));
rest.push(h2('2.1 ملخص حسب المكون'));
rest.push(table([3900, 1100, 1100, 1100, 1200, 1238], ['المكون', 'المتطلبات', 'إلزامي', 'مهم', 'اختياري', 'منجز'],
  comps.map(c => { const rs = c.groups.flatMap(g => g.reqs); return [c.title, String(rs.length), String(count(rs, r => r[2] === 'M')),
    String(count(rs, r => r[2] === 'S')), String(count(rs, r => r[2] === 'C')), String(count(rs, r => r[3] === 'done'))]; })));
for (const c of comps) {
  rest.push(h2(c.title));
  for (const g of c.groups) {
    if (g.title !== c.title) rest.push(h3(g.title));
    rest.push(table([1300, 5838, 1100, 1400], ['المعرف', 'المتطلب', 'الأولوية', 'الحالة'],
      g.reqs.map(r => [r[0], r[1], PRIO[r[2]] || r[2], S[r[3]]]), { ltrCols: [0], size: 16,
        fills: (ri, ci, r) => ci === 3 ? (r[3] === S.done ? C.greenTint : C.amberTint) : (ri % 2 ? C.zebra : undefined) }));
  }
}

// Card 2: non-functional.
rest.push(h1('3. البطاقة غير الوظيفية', { pageBreak: true }));
rest.push(p('كل متطلب قابل للقياس، ومعه ما قيس فعلا عند تاريخ الوثيقة. ما لم يُقس بعد يُقاس في التجربة الميدانية أو في التدقيق الخارجي، وهو مذكور كذلك.'));
rest.push(table([1000, 1500, 4338, 2800], nfr.head, nfr.rows, { ltrCols: [0], size: 16 }));
rest.push(h2('3.1 طريقة القياس'));
rest.push(table([2400, 7238], ['الفئة', 'الأداة والطريقة'], [
  ['الأداء والتوسع', 'k6 (infra/loadtest) على نسخة معزولة؛ المئين 95 لزمن الاستجابة؛ تقرير في كل مرحلة'],
  ['التوفر والاستعادة', 'تمرين الاستعادة في CI (pg_basebackup + WAL)، وقياس RPO و RTO'],
  ['الأمن', 'Trivy على كل صورة، و ZAP baseline، و Lynis و nmap و testssl.sh (تقرير التحصين، المرحلة 4)، واختبار اختراق خارجي قبل الإطلاق'],
  ['النفاذ', 'axe في اختبارات المتصفح، و 91 حالة نفاذ في تطبيق الهاتف، وبروتوكول TalkBack و VoiceOver'],
  ['اللغات', 'فحص آلي لاكتمال ملفات الترجمة الثلاثة'],
  ['جودة الشيفرة', 'ruff و mypy و eslint و flutter analyze؛ تغطية الاختبارات؛ فحص انحراف OpenAPI و ERD'],
]));

// Card 3: technical.
rest.push(h1('4. البطاقة التقنية', { pageBreak: true }));
rest.push(kv([
  ['البنية', 'خدمات مستقلة في حاويات (Docker Compose)، قابلة للنقل إلى Kubernetes؛ خادم عكسي واحد (Caddy) على المنفذ 443.'],
  ['الواجهة البرمجية', `REST/JSON موثقة بـ OpenAPI ${api.info.version}: ${ops} عملية، مع أحداث فورية (WebSocket عبر NATS).`],
  ['قاعدة البيانات', `PostgreSQL 17 مع PostGIS و pgvector: ${dict.counts.schemas} مخططا، ${dict.counts.tables} جدولا، ${dict.counts.columns} عمودا، ${dict.counts.rls_tables} جدولا بعزل حسب الولاية، ${dict.counts.encrypted_columns} عمودا مشفّرا؛ الترحيل ${dict.migration}.`],
  ['الهوية', 'Keycloak بفضاءين (عام بالهاتف ورمز SMS، وإداري بالتحقق بخطوتين)؛ رموز OIDC؛ أدوار وولاية في الرمز.'],
  ['الواجهات', 'تطبيق Flutter (المواطن والأعوان)، بوابة المؤسسات ولوحة القيادة (React)، بالعربية والفرنسية والإنجليزية.'],
  ['الاستضافة', 'داخل التراب التونسي؛ يعمل دون إنترنت للعرض (حاسوب واحد)، وعلى 8 خوادم بالمناطق في الإنتاج (المرحلة 5).'],
]));
rest.push(h2('4.1 المعمارية'));
rest.push(...ul(arch));
rest.push(h2('4.2 التقنيات والإصدارات'));
rest.push(table([2200, 3800, 3638], tech.head, tech.rows, { size: 16 }));
rest.push(h2('4.3 الأمن'));
rest.push(...ul(sec));
rest.push(note('التفاصيل: الملف التقني والأمني الموحد (مصفوفة المنافذ، الأسرار، البروتوكولات، التحصين).'));
rest.push(h2('4.4 المحاكاة [SIM]'));
rest.push(table([3200, 6438], sims.head, sims.rows));

save(document({ title: 'البطاقات وسير العمل', sections: [{ children }, { landscape: true, children: bpmn }, { children: rest }] }), out);
