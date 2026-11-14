// The system presentation for the high-level committee (Yamen, 2026-11-14): how the operations room works today
// (the 198 call, the hand work of the agent, sending resources without a sound estimate, no location, no picture, no
// decision indicators, about 7,300 outings without intervention between 2022 and 2025, volunteers, citizens and
// institutions not connected), then how e-Himaya works and every value it adds, the local AI tools, and the vision
// once the system is in use. No development phases: functions, added value, before and after.
//
//   node scripts/tracking/pitch-pptx.mjs <out.pptx>            (DECK_SETS=day for the day set alone)
//
// Look, colour sets and writer: deck-kit.mjs. The AI part is ai-tools-slides.mjs, the same slides as the AI deck.
import {createKit, DISP, DISPM, MONO, SYSTEM, ind} from './deck-kit.mjs';
import {planAi, drawAi} from './ai-tools-slides.mjs';

const [out] = process.argv.slice(2);
if (!out) { console.error('usage: pitch-pptx.mjs <out.pptx>'); process.exit(2); }

// ---------------------------------------------------------------- 1. the content
const ACTS = [
  {name: 'اليوم', title: 'كيف تعمل القاعة اليوم', lead: 'بلاغ بالهاتف، وعون يعمل بذاكرته وخبرته، وموارد تُسخَّر دون صورة ولا موقع.'},
  {name: 'التحوّل', title: 'كيف تعمل ء-حماية', lead: 'السلسلة نفسها، من التبليغ إلى أخذ القرار، لكن بمعطى دقيق في كل حلقة.'},
  {name: 'القيم المضافة', title: 'ما تضيفه لكل متدخّل', lead: 'المواطن والقاعة والفريق والمؤسسة والمتطوع والقيادة: لكل واحد منهم ما يتغيّر في عمله.'},
  {name: 'الذكاء المحلي', title: 'الذكاء الاصطناعي المحلي', lead: 'اثنتا عشرة أداة تعمل داخل خوادم الديوان: تقترح وتعلّل، والإنسان يقرّر.'},
  {name: 'الرؤية', title: 'الرؤية: عند الاستعمال وبعده', lead: 'من ردّ الفعل إلى الاستباق، ومن المكالمة إلى القرار المبني على الأرقام.'},
];
const TODAY = [
  ['المواطن يتصل بـ198', 'وقد يجد الخط مشغولا في الذروة'],
  ['العون يسأل عن المكان', 'وصف شفوي، وعنوان يُبحث عنه'],
  ['يدوّن البلاغ بيده', 'لا صورة ولا صوت محفوظ'],
  ['يقدّر الوسائل', 'من كلام المبلّغ وانفعاله'],
  ['يُعلم الوحدة', 'بالهاتف أو اللاسلكي'],
  ['الفريق يكتشف الوضع', 'عند الوصول: المؤسسة ومخاطرها مجهولة'],
  ['التقرير بعد العودة', 'والأرقام تُجمع لاحقا باليد'],
];
const TOMORROW = [
  ['بلاغ بموقعه', 'تطبيق أو رسالة أو مكالمة، بصورة وصوت وبث'],
  ['في القاعة فورا', 'على الخريطة في أقل من نصف ثانية'],
  ['يُقرأ ويُرتَّب', 'صنف وأولوية مفسَّرة، والمكرر يُجمع'],
  ['العون يرى المحيط', 'المؤسسات والمواد الخطرة والسكان المعرضون'],
  ['يسخّر بقدر الحاجة', 'الوسائل المتاحة الأقرب والمتطوع الأقرب'],
  ['الفريق على هاتفه', 'المهمة والمراحل والأزمنة والصوت والصورة'],
  ['القيادة تقرّر', 'بمؤشرات تُحدَّث آليا في كل لحظة'],
];
const GAPS = [
  ['قناة واحدة: الهاتف 198', 'البلاغ صوت فقط، والخط ينشغل في الذروة، ولا أثر مكتوب لما قيل.'],
  ['غياب التموقع الجغرافي', 'المكان يُوصف شفويا، والعنوان يُبحث عنه، والدقائق الأولى تضيع.'],
  ['تسخير دون تقدير دقيق', 'الوسائل تُقدَّر من كلام الجهة المبلّغة، فتزيد عن الحاجة أو تنقص.'],
  ['لا صورة ولا نقل ميداني', 'حجم الحادث الحقيقي يُكتشف عند الوصول لا قبله.'],
  ['غياب مؤشرات القرار', 'لا لوحة حية؛ الأرقام تُجمع بعد الحدث، والقرار يُبنى على التقدير.'],
  ['بلاغات مكررة لحدث واحد', 'عشرات المكالمات عن الحريق نفسه تشغل الخط والعون.'],
  ['شبكة متطوعين غير محددة', 'لا يُعرف من المتطوع، ولا أين هو، ولا ما اختصاصه.'],
  ['مواطن متصل لا مشارك', 'لا متابعة لبلاغه ولا تحفيز، فتضعف الثقة بين المواطن والإدارة.'],
  ['نسيج مؤسساتي غير مربوط', 'موقع المؤسسة وبطاقتها وموادها الخطرة غائبة عن العون قبل الوصول.'],
  ['فريق ميداني معزول', 'المراحل والأزمنة تُدوَّن لاحقا، ولا محاسبة آنية للأفراد في المنطقة الخطرة.'],
  ['توثيق ورقي بلا ذاكرة', 'سجلات يدوية يصعب البحث فيها، والدروس والقرارات لا تُجمع.'],
  ['لا إنذار موجّه للسكان', 'التحذير لا يصل حسب المنطقة المهددة إلى هواتف من فيها.'],
];
const BRIDGE = [
  ['الهاتف 198 وحده', 'تطبيق ورسالة قصيرة ومكالمة مدمجة وبث مباشر، في شاشة واحدة'],
  ['وصف شفوي للمكان', 'موقع دقيق على الخريطة يصل مع البلاغ'],
  ['تقدير من كلام المبلّغ', 'أولوية مفسَّرة ووسائل مقترحة حسب الصنف وما هو مكلَّف'],
  ['لا صورة', 'صورة وصوت وبث، وكاميرات وأبراج ودرون، وكشف آلي للنار والدخان'],
  ['أرقام بعد الحدث', 'لوحة حية لكل ولاية وللوطن، بالمؤشرات حسب الصنف والحالة'],
  ['مكالمات مكررة', 'تجميع آلي للبلاغات في حادثة واحدة'],
  ['متطوعون مجهولون', 'سجل باختصاصاتهم ومواقعهم الحية، واستنفار الأقرب بموافقته'],
  ['مواطن متصل', 'رقم تتبع وتنبيهات ونقاط وشارات «المواطن اليقظ»'],
  ['مؤسسة مجهولة', 'بطاقة المؤسسة وملف السلامة والمواد الخطرة على الخريطة'],
  ['فريق معزول', 'تطبيق الأعوان: المهمة والمراحل والصوت ومحاسبة الأفراد'],
  ['توثيق ورقي', 'سجل رقمي كامل، ومكتبة أحداث يُبحث فيها، وسجل تدقيق لا يُعدَّل'],
  ['لا إنذار موجّه', 'تنبيهات حسب الولاية والمنطقة إلى هواتف السكان'],
];
const VALUES = [
  {k: 'citizen', name: 'المواطن', tone: 'red', tag: 'شريك لا متصل: يرى أثر بلاغه، فتُبنى الثقة.', figs: [['3', 'لمسات للنجدة'], ['دون إنترنت', 'البلاغ يُحفظ ويُرسل لاحقا']],
    items: [['النجدة في ثلاث لمسات', 'زر واحد يرسل الموقع، والمكالمة إلى 198 بلمسة.'], ['يعمل دون إنترنت', 'البلاغ يُحفظ مشفّرا ويُرسل عند عودة الشبكة، والرسالة القصيرة بديل.'],
      ['صورة وصوت وبث', 'من مكان الحادث، ليرى العون ما يراه المواطن.'], ['متابعة البلاغ', 'رقم تتبع يقول: تم التدخل، التدخل متواصل، أُغلق.'],
      ['تنبيهات ونصائح', 'تحذيرات حسب منطقته، ودليل السلوك الآمن لكل خطر.'], ['«المواطن اليقظ»', 'نقاط وشارات وشهادات تكريم موقّعة لمن يساهم.']]},
  {k: 'room', name: 'قاعة العمليات', tone: 'navy', tag: 'العون يقرّر بمعطى دقيق، لا بالتقدير وحده.', figs: [['0.45 ث', 'من الإرسال إلى الشاشة'], ['0–100', 'أولوية مفسَّرة لكل بلاغ']],
    items: [['البلاغ على الخريطة', 'يصل بموقعه وصوره، ويظهر بجانب الوحدات والوسائل.'], ['أولوية مفسَّرة', 'من 0 إلى 100، مع سببها ومصداقية المبلّغ.'],
      ['تجميع المكرر', 'البلاغات عن حدث واحد تُقترح في حادثة واحدة.'], ['المكالمات في اللوحة', 'المقسم الهاتفي مدمج، وبطاقة استقبال موحّدة لكل مكالمة.'],
      ['مهلة التكفل', 'البلاغ غير المعالج في الأجل يُصعَّد آليا إلى المركز.'], ['تحذيرات وإعلام الشركاء', 'العناوين الخطرة مسجّلة، والجهات الشريكة تُعلَم ويُحفظ ذلك.']]},
  {k: 'crew', name: 'الفريق الميداني', tone: 'orange', tag: 'الفريق يصل وهو يعرف، والقاعة تعرف أين هو وماذا يرى.', figs: [['دون شبكة', 'يعمل ويزامن عند عودتها'], ['كل مرحلة', 'بزمنها وصوتها']],
    items: [['المهمة على الهاتف', 'تصل بكل معطياتها، وتُدار بالأزرار دون كتابة تقريبا.'], ['مراحل بأزمنتها', 'الانطلاق، الوصول، الرجوع، و«بدون تدخل» بسببه.'],
      ['رسالة صوتية', 'في كل مرحلة، تصل القاعة نصا مقروءا.'], ['دون شبكة', 'يعمل في المناطق المعزولة ويزامن عند عودة الشبكة.'],
      ['محاسبة الأفراد', 'من في المنطقة الخطرة، بمواعيد تفقّد وتنبيه عند الغياب.'], ['تقرير الحالة', 'يُنقل إلى القاعة كما قيل، ويظهر على لوحة الحادث.']]},
  {k: 'orgs', name: 'المؤسسات والوقاية', tone: 'teal', tag: 'العون يعرف المكان قبل أن يصله.', figs: [['QR', 'شهادة سلامة رقمية'], ['قبل الحادث', 'تُعرف المواد الخطرة']],
    items: [['بوابة المؤسسات', 'بطاقة المؤسسة ونشاطها وطاقة استيعابها وموقعها على الخريطة.'], ['ملف السلامة', 'المخطط وفريق السلامة بهواتفهم وتاريخ آخر تكوين.'],
      ['المواد الخطرة', 'مسجّلة قبل الحادث، وتظهر في محيطه للعون.'], ['شهادة رقمية', 'موقّعة، يُتحقق منها برمز QR.'],
      ['التفقدات الدورية', 'بتطبيق المتفقد في الموقع، حتى دون شبكة.'], ['رسائل موجهة', 'للمؤسسات حسب صنفها وولايتها.']]},
  {k: 'volunteers', name: 'المتطوعون والأطباء', tone: 'green', tag: 'شبكة معروفة وجاهزة، تُستنفر في دقائق.', figs: [['الأقرب', 'حسب الاختصاص'], ['SMS', 'حين ينقطع الإنترنت']],
    items: [['سجل وطني للمتطوعين', 'باختصاصاتهم وفترات تطوعهم، بعد تأكيد الحماية المدنية.'], ['مواقع حية', 'المتطوعون الجاهزون على الخريطة، بموافقتهم.'],
      ['استنفار الأقرب', 'حسب الاختصاص، والمتطوع يقبل أو يعتذر.'], ['دون إنترنت', 'الاستنفار والرد بالرسالة القصيرة.'],
      ['أطباء معتمدون', 'أطباء الحماية المدنية واللجنة الطبية بمدة اعتماد.'], ['الملف الطبي', 'مقفل على هاتف المواطن، لا يفتحه إلا الأطباء المعتمدون.']]},
  {k: 'fleet', name: 'الموارد والأسطول', tone: 'amber', tag: 'تسخير بقدر الحاجة، لا بقدر الخوف.', figs: [['الآن', 'الوسائل المتاحة'], ['كل ولاية', 'سجل مواردها']],
    items: [['سجل الموارد', 'المركبات والمعدات والأفراد لكل ولاية ووحدة.'], ['حالة المركبة', 'جاهزة، في مهمة، في الصيانة، أو خارج الخدمة.'],
      ['التغطية الحية', 'أين الوسائل المتاحة الآن، وأين الفراغ.'], ['الأفراد والنوبات', 'من في الخدمة، ومن الاحتياط.'],
      ['الوسائل الناقصة', 'تُقترح حسب صنف الحادث وما هو مكلَّف.'], ['التفقدات الدورية للوحدات', 'بمعايير موحّدة ونتيجة تُقرأ في القاعة.']]},
  {k: 'command', name: 'القيادة وأصحاب القرار', tone: 'purple', tag: 'القرار في الأزمة مبني على صورة واحدة محيّنة.', figs: [['3', 'مستويات: عادي، أزمة، كارثة'], ['24', 'ولاية في صورة واحدة']],
    items: [['لوحة حية', 'لكل ولاية وللوطن، حسب الصنف والحالة.'], ['مستويات التشغيل', 'عادي وأزمة وكارثة، مع اللجان الجهوية والمركزية وتوجيهاتها.'],
      ['محور الأزمة', 'السكان والأماكن المعرضة للخطر على مساحته.'], ['نافذة القرار', 'بحث ومقارنة ومؤشرات، بملخص يقول ما في الأرقام.'],
      ['الطقس والانتشار', 'تنبيهات جوية، وانتشار الحريق ومخاطر الفيضان على التضاريس.'], ['العملية البيضاء', 'تمرين رقمي للولايات على سيناريو معتمد.']]},
  {k: 'trust', name: 'الثقة وحماية المعطيات', tone: 'sky', tag: 'الثقة شرط النجاح: المعطى محمي، وكل اطلاع مسجَّل.', figs: [['AES-256', 'للمعطيات الحساسة'], ['2', 'خطوتان للتحقق لكل عون']],
    items: [['القانون الأساسي 63 لسنة 2004', 'المنظومة مصمَّمة وفقه منذ البداية.'], ['الملف الطبي', 'لا يستطيع الخادم قراءته، والمواطن يرى من اطّلع عليه.'],
      ['تحقق بخطوتين', 'لكل حساب عون، مع إلغاء فوري للجلسات.'], ['سجل لا يُعدَّل', 'من اطّلع، متى، ماذا، ولماذا.'],
      ['أدلة موثوقة', 'بصمة رقمية لكل صورة وفيديو، وختم دوري لا يُزوَّر.'], ['عزل كل ولاية', 'قاعدة البيانات نفسها تمنع الاطلاع خارج النطاق.']]},
];
const OUTINGS = [
  ['التثبت قبل التسخير', 'صورة وبث من المبلّغ، وكاميرات وأبراج ودرون، وكشف آلي للنار والدخان.'],
  ['موقع دقيق', 'لا بحث عن عنوان، ولا خروج إلى مكان خاطئ.'],
  ['مصداقية المبلّغ', 'تاريخ بلاغاته يدخل في الأولوية، والبلاغ الكاذب يُراجَع والمتكرر يُحجَّر.'],
  ['حدث واحد، مهمة واحدة', 'البلاغات المكررة تُجمع قبل أن تُسخَّر لها وسائل.'],
  ['قراءة البلاغ', 'الأرواح في خطر والمخاطر المرافقة تُعرف قبل الإرسال.'],
  ['«بدون تدخل» يُقاس', 'يُسجَّل بسببه في تطبيق الأعوان، فيُحلَّل حسب الولاية والسبب ويُتابَع.'],
];
const HORIZONS = [
  ['عند الاستعمال', 'الأشهر الأولى', ['كل بلاغ يصل بموقعه وصورته', 'القاعة ترى البلاغات والوسائل على خريطة واحدة', 'الفرق مربوطة بالقاعة في كل مرحلة', 'المؤسسات تسجّل ملفاتها وموادها الخطرة']],
  ['بعد سنة', 'الذاكرة والمقارنة', ['ذاكرة وطنية للحوادث والقرارات يُبحث فيها', 'مؤشرات تُقارَن بين الولايات والفصول والسنوات', 'شبكة متطوعين حية ومعروفة', 'أدوات الذكاء تعلّمت الدارجة وقرارات القادة']],
  ['على المدى البعيد', 'من ردّ الفعل إلى الاستباق', ['خرائط الخطر والتنبؤ توجّه الوقاية', 'توزيع الوحدات والوسائل حسب الأرقام', 'ثقة متجددة بين المواطن والإدارة', 'نموذج تونسي سيادي في إدارة المخاطر']],
];
const KPIS = [
  ['زمن التكفل', 'من وصول البلاغ إلى تكليف الفريق'], ['زمن الوصول', 'من الانطلاق إلى المكان، حسب المعتمدية'],
  ['الخروج دون تدخل', 'عدده وأسبابه حسب الولاية'], ['البلاغات بموقع دقيق', 'نسبتها من كل البلاغات'],
  ['البلاغات المكررة المجمَّعة', 'ما وُفّر من مهام'], ['المتطوعون الجاهزون', 'حسب الاختصاص والولاية'],
  ['المؤسسات بملف سلامة محيَّن', 'حسب الصنف والولاية'], ['متابعة المواطن لبلاغه', 'ورضاه عن الاستجابة'],
];

// ---------------------------------------------------------------- 2. the plan
const K = await createKit({title: 'ء-حماية: من التبليغ إلى أخذ القرار', footer: 'ء-حماية · من التبليغ إلى أخذ القرار'});
const P = {cover: K.add('cover'), agenda: K.add('agenda')};
P.act = [K.add('act', {a: 0})];
P.today = K.add('journey'); P.outings = K.add('big'); P.gaps = K.add('grid'); P.cost = K.add('cost');
P.act.push(K.add('act', {a: 1}));
P.glance = K.add('glance'); P.tomorrow = K.add('journey'); P.bridge = [K.add('bridge'), K.add('bridge')];
P.act.push(K.add('act', {a: 2}));
P.values = VALUES.map(() => K.add('value'));
P.act.push(K.add('act', {a: 3}));
const AI = planAi(K);
P.act.push(K.add('act', {a: 4}));
P.answer = K.add('answer'); P.vision = K.add('vision'); P.kpis = K.add('kpis'); P.end = K.add('end');
K.home = P.agenda;
const ACT_START = [P.act[0], P.act[1], P.act[2], P.act[3], P.act[4]];
const actOf = n => ACT_START.filter(a => a <= n).length - 1;

// ---------------------------------------------------------------- 3. the slides
for (const mode of K.MODES) {
  K.begin(mode);
  const {pres, A} = K, C = K.C, night = mode === 'night';
  const crumbOf = n => `ء-حماية · ${ind(actOf(n) + 1)} ${ACTS[actOf(n)].name}`;
  const nav = (s, n) => { K.button(s, 'الفهرس', 0.5, 0.6, 1.0, P.agenda, true); K.counter(s, n); K.foot(s); };

  // cover: the hero beside the eight spaces of the system in orbit, each a link to its value slide
  {
    const s = K.newSlide(P.cover), cx = 3.2, cy = 3.75, R = 2.35;
    A(K.shape(s, pres.shapes.OVAL, {x: cx - R - 0.42, y: cy - R - 0.42, w: 2 * (R + 0.42), h: 2 * (R + 0.42), line: {color: C.gold, width: 1.5, dashType: 'sysDot', transparency: 55}}), 'fade', 0, 900);
    A(K.shape(s, pres.shapes.OVAL, {x: cx - R, y: cy - R, w: 2 * R, h: 2 * R, line: {color: C.edge, width: 0.75, dashType: 'dash'}}), 'fade', 0, 900);
    VALUES.forEach((v, i) => {
      const a = -Math.PI / 2 + i * 2 * Math.PI / VALUES.length, x = cx + R * Math.cos(a), y = cy + R * Math.sin(a), r = 0.5, col = K.tone(v.tone), d0 = 300 + i * 110;
      const x0 = cx + 1.1 * Math.cos(a), y0 = cy + 1.1 * Math.sin(a), x1 = x - r * Math.cos(a), y1 = y - r * Math.sin(a);
      A(K.shape(s, pres.shapes.LINE, {x: Math.min(x0, x1), y: Math.min(y0, y1), w: Math.max(0.01, Math.abs(x1 - x0)), h: Math.max(0.01, Math.abs(y1 - y0)),
        flipH: (Math.cos(a) < 0) !== (Math.sin(a) < 0), line: {color: col, width: 1.25, transparency: 40}}), 'fade', d0, 400);
      A(K.shape(s, pres.shapes.OVAL, {x: x - r, y: y - r, w: 2 * r, h: 2 * r, fill: {color: col}, line: {color: C.bg, width: 2}, ...K.link(P.values[i])}), 'zoom', d0 + 100, 400);
      A(K.text(s, v.name, {x: x - r, y: y - r, w: 2 * r, h: 2 * r, align: 'center', fontSize: 9.5, bold: true, color: C.onTone, fit: 'shrink', ...K.link(P.values[i])}), 'zoom', d0 + 100, 400);
    });
    A(K.shape(s, pres.shapes.OVAL, {x: cx - 1.1, y: cy - 1.1, w: 2.2, h: 2.2, fill: {color: C.root}, line: {color: C.gold, width: 3}, ...K.link(P.agenda)}), 'zoom', 0, 600);
    A(K.text(s, [{text: 'ء-حماية', options: {fontSize: 26, fontFace: DISP, bold: true, color: C.white, breakLine: true}}, {text: 'منظومة واحدة', options: {fontSize: 12, color: C.gold}}],
      {x: cx - 1.1, y: cy - 0.62, w: 2.2, h: 1.24, align: 'center', ...K.link(P.agenda)}), 'zoom', 0, 600);
    A(K.text(s, 'e-HIMAYA · 2026', {x: 6.6, y: 0.42, w: 5.2, h: 0.28, fontSize: 10, fontFace: MONO, color: C.gold, rtlMode: false, lang: 'en-US', align: 'right', charSpacing: 2}), 'fade', 0, 600);
    A(K.emblem(s, 11.93, 0.3, 0.9), 'zoom', 0, 600);
    A(K.text(s, 'الديوان الوطني للحماية المدنية', {x: 6.6, y: 0.72, w: 5.2, h: 0.4, fontSize: 15, bold: true, color: C.ink}), 'fade', 150, 600);
    K.wordmark(s, 9.63, 1.32, 3.2);
    A(K.text(s, [{text: 'من التبليغ إلى ', options: {color: C.ink}}, {text: 'أخذ القرار', options: {color: C.gold}}], {x: 6.3, y: 2.95, w: 6.53, h: 0.85, fontSize: 40, fontFace: DISP, bold: true}), 'fade', 450, 800);
    A(K.text(s, SYSTEM, {x: 6.3, y: 3.85, w: 6.53, h: 0.8, fontSize: 14, lineSpacingMultiple: 1.05, bold: true, color: C.ink, valign: 'top'}), 'fade', 600, 800);
    A(K.text(s, 'كيف تعمل القاعة اليوم، وكيف ستعمل مع ء-حماية، وما الذي يتغيّر لكل متدخّل.', {x: 6.3, y: 4.85, w: 6.53, h: 0.5, fontSize: 12.5, color: C.mute, valign: 'top'}), 'fade', 750, 700);
    K.button(s, 'ابدأ العرض', 10.73, 5.55, 2.1, P.agenda, true);
    K.button(s, 'الوضع اليوم', 8.48, 5.55, 2.1, P.act[0]);
  }

  // agenda: the five acts, each a link
  {
    const s = K.newSlide(P.agenda);
    K.crumb(s, 'ء-حماية · العرض'); K.title(s, 'خمسة فصول');
    K.lead(s, 'من الوضع الحالي إلى الرؤية. اضغط على فصل للانتقال إليه.');
    ACTS.forEach((a, k) => {
      const y = 1.85 + k * 1.0, dl = 250 + k * 150;
      A(K.panel(s, 0.5, y, 12.33, 0.84, {...K.link(P.act[k])}), 'fade', dl, 400);
      A(K.text(s, ind(k + 1), {x: 11.95, y, w: 0.7, h: 0.84, align: 'center', fontSize: 30, fontFace: DISP, color: C.gold, ...K.link(P.act[k])}), 'fade', dl, 400);
      A(K.text(s, a.title, {x: 7.2, y, w: 4.6, h: 0.84, fontSize: 18, fontFace: DISPM, color: C.ink, ...K.link(P.act[k])}), 'fade', dl + 80, 400);
      A(K.text(s, a.lead, {x: 0.8, y, w: 6.2, h: 0.84, fontSize: 12, color: C.mute, ...K.link(P.act[k])}), 'fade', dl + 120, 400);
    });
    K.counter(s, P.agenda); K.foot(s);
  }

  // an act divider: the big numeral, the title, the lead, and the five acts at the foot
  const divider = k => {
    const n = P.act[k], s = K.newSlide(n);
    A(K.text(s, ind(k + 1), {x: 9.0, y: 1.3, w: 3.83, h: 3.0, fontSize: 200, fontFace: DISP, color: C.gold, align: 'right'}), 'zoom', 0, 700);
    A(K.text(s, `الفصل ${ind(k + 1)} · ${ACTS[k].name}`, {x: 0.5, y: 2.0, w: 8.3, h: 0.4, fontSize: 14, bold: true, color: C.gold}), 'fade', 200, 500);
    A(K.text(s, ACTS[k].title, {x: 0.5, y: 2.45, w: 8.3, h: 1.0, fontSize: 40, fontFace: DISP, bold: true, color: C.ink}), 'fade', 300, 600);
    A(K.text(s, ACTS[k].lead, {x: 0.5, y: 3.55, w: 8.3, h: 0.9, fontSize: 16, color: C.mute, valign: 'top'}), 'fade', 450, 600);
    const w = 12.33 / 5;
    ACTS.forEach((a, j) => {
      const x = 12.83 - (j + 1) * w, on = j === k;
      A(K.shape(s, pres.shapes.LINE, {x: x + 0.05, y: 5.9, w: w - 0.1, h: 0, line: {color: on ? C.gold : C.edge, width: on ? 3 : 1.25}}), 'wipe', 600 + j * 80, 400, 'l');
      A(K.text(s, `${ind(j + 1)}  ${a.name}`, {x: x + 0.05, y: 6.0, w: w - 0.1, h: 0.36, fontSize: 12, bold: on, color: on ? C.gold : C.mute, ...K.link(P.act[j])}), 'fade', 600 + j * 80, 400);
    });
    K.button(s, 'الفهرس', 0.5, 0.6, 1.0, P.agenda, true); K.counter(s, n);
  };

  // a journey: seven steps right to left, each with its node, its words and its mark
  const journey = (n, title, lead, steps, tone, mark) => {
    const s = K.newSlide(n), col = K.tone(tone);
    K.crumb(s, crumbOf(n)); K.title(s, title); K.lead(s, lead);
    const w = 12.33 / steps.length, y = 2.75;
    A(K.shape(s, pres.shapes.LINE, {x: 0.5 + w / 2, y: y + 0.35, w: 12.33 - w, h: 0, line: {color: col, width: 2, dashType: mark === '!' ? 'dash' : 'solid'}}), 'wipe', 200, 1200, 'l');
    steps.forEach(([h, b], k) => {
      const x = 12.83 - (k + 1) * w, cx = x + w / 2, dl = 300 + k * 220;
      A(K.shape(s, pres.shapes.OVAL, {x: cx - 0.35, y, w: 0.7, h: 0.7, fill: {color: C.panel}, line: {color: col, width: 2.5}}), 'zoom', dl, 400);
      A(K.text(s, ind(k + 1), {x: cx - 0.35, y, w: 0.7, h: 0.7, align: 'center', fontSize: 18, fontFace: DISP, color: col}), 'zoom', dl, 400);
      A(K.text(s, h, {x: x + 0.06, y: y + 0.9, w: w - 0.12, h: 0.75, align: 'center', fontSize: 14, bold: true, color: C.ink, valign: 'top'}), 'fade', dl + 100, 400);
      A(K.text(s, b, {x: x + 0.06, y: y + 1.65, w: w - 0.12, h: 0.9, align: 'center', fontSize: 11.5, color: C.mute, valign: 'top'}), 'fade', dl + 150, 400);
      A(K.shape(s, pres.shapes.OVAL, {x: cx - 0.17, y: y + 2.65, w: 0.34, h: 0.34, fill: {color: col}}), 'zoom', dl + 200, 300);
      A(K.text(s, mark, {x: cx - 0.17, y: y + 2.65, w: 0.34, h: 0.34, align: 'center', fontSize: 11, bold: true, color: C.onTone}), 'zoom', dl + 200, 300);
    });
    return s;
  };

  divider(0);
  { const s = journey(P.today, 'بلاغ اليوم: رحلة بالهاتف', 'سبع خطوات يقوم بها العون بيده وذاكرته، والمعطى الدقيق غائب في كل واحدة منها.', TODAY, 'red', '!');
    A(K.text(s, 'كل خطوة تأخذ من الدقائق الأولى، وهي الدقائق التي تصنع الفرق في إنقاذ الأرواح.', {x: 0.5, y: 6.25, w: 12.33, h: 0.4, fontSize: 14, bold: true, color: C.gold, align: 'center'}), 'fade', 2000, 600);
    nav(s, P.today); }

  // the outings without intervention
  {
    const s = K.newSlide(P.outings), red = K.tone('red');
    K.crumb(s, crumbOf(P.outings)); K.title(s, 'الكلفة التي لا تُرى');
    A(K.text(s, '≈ 7300', {x: 6.4, y: 1.55, w: 6.43, h: 1.9, fontSize: 110, fontFace: MONO, bold: true, color: red, rtlMode: false, lang: 'en-US', align: 'right'}), 'zoom', 200, 800);
    A(K.text(s, 'عملية خروج دون تدخل بين 2022 و2025', {x: 6.4, y: 3.45, w: 6.43, h: 0.55, fontSize: 22, fontFace: DISPM, color: C.ink}), 'fade', 600, 600);
    K.figure(s, 9.73, 4.4, 3.1, '≈ 1825', 'في السنة', 900, red, 26);
    K.figure(s, 6.4, 4.4, 3.1, '≈ 5', 'كل يوم', 1050, red, 26);
    A(K.panel(s, 0.5, 1.6, 5.6, 4.6, {line: {color: red, width: 1.5}}), 'fade', 400, 500);
    A(K.text(s, 'كل خروج دون تدخل هو:', {x: 0.8, y: 1.8, w: 5.0, h: 0.4, fontSize: 15, bold: true, color: red}), 'fade', 500, 400);
    K.list(s, ['فريق يغيب عن حادث حقيقي في اللحظة نفسها', 'مركبة ووقود وتآكل للمعدات', 'خطر على الأعوان في الطريق دون سبب', 'إرهاق يتراكم على الفرق', 'ثقة تهتز في البلاغ القادم'], 0.8, 2.35, 5.0, 0.58, red, 700, 13.5);
    A(K.text(s, 'وفي غياب صورة أو نقل ميداني مباشر، لا وسيلة للتثبت قبل التسخير.', {x: 0.8, y: 5.3, w: 5.0, h: 0.75, fontSize: 13, bold: true, color: C.gold, valign: 'top'}), 'fade', 1500, 500);
    A(K.text(s, 'المصدر: أرقام الديوان الوطني للحماية المدنية، 2022 إلى 2025. المعدلات تقريبية.', {x: 6.4, y: 5.6, w: 6.43, h: 0.3, fontSize: 10, color: C.mute}), 'fade', 1300, 400);
    K.button(s, 'الجواب', 1.62, 0.6, 1.0, P.answer);
    nav(s, P.outings);
  }

  // the shortcomings
  {
    const s = K.newSlide(P.gaps), red = K.tone('red');
    K.crumb(s, crumbOf(P.gaps)); K.title(s, 'اثنتا عشرة نقيصة');
    K.lead(s, 'ليست تقصيرا من العون، بل حدود طريقة عمل بُنيت على الهاتف والورق.');
    const cols = 4, w = (12.33 - 0.18 * (cols - 1)) / cols, h = 1.5;
    GAPS.forEach(([t, b], k) => {
      const c = k % cols, r = Math.floor(k / cols), x = 12.83 - (c + 1) * w - c * 0.18, y = 1.8 + r * (h + 0.15), dl = 250 + k * 90;
      A(K.panel(s, x, y, w, h), 'fade', dl, 400);
      A(K.shape(s, pres.shapes.RECTANGLE, {x: x + w - 0.07, y: y + 0.2, w: 0.07, h: h - 0.4, fill: {color: red}}), 'fade', dl, 400);
      A(K.text(s, [{text: String(k + 1) + '  ', options: {fontFace: MONO, color: red}}, {text: t, options: {}}], {x: x + 0.2, y: y + 0.12, w: w - 0.4, h: 0.42, fontSize: 13.5, bold: true, color: C.ink}), 'fade', dl + 60, 400);
      A(K.text(s, b, {x: x + 0.2, y: y + 0.56, w: w - 0.4, h: h - 0.66, fontSize: 11, color: C.mute, valign: 'top'}), 'fade', dl + 100, 400);
    });
    K.button(s, 'من … إلى', 1.62, 0.6, 1.1, P.bridge[0]);
    nav(s, P.gaps);
  }

  // the hidden cost: four losses
  {
    const s = K.newSlide(P.cost), red = K.tone('red');
    K.crumb(s, crumbOf(P.cost)); K.title(s, 'ما يكلّفه ذلك');
    K.lead(s, 'أربع خسائر تتكرر في كل بلاغ، ولا يظهر أي منها في التقارير.');
    [['الوقت', 'دقائق تضيع في السؤال عن المكان والتثبت والإعلام، وهي الدقائق التي تنقذ.'],
     ['الموارد', 'وسائل تُسخَّر أكثر من الحاجة أو أقل منها، وأخرى تخرج دون تدخل.'],
     ['سلامة الأعوان', 'فرق تدخل مكانا لا تعرف مواده الخطرة، ولا يُعرف من بقي في الداخل.'],
     ['الثقة', 'مواطن لا يعرف مصير بلاغه، وإدارة لا ترى أثر عملها في أرقام.']].forEach(([h, b], k) => {
      const w = (12.33 - 0.2 * 3) / 4, x = 12.83 - (k + 1) * w - k * 0.2, dl = 300 + k * 200;
      A(K.panel(s, x, 1.9, w, 4.3), 'fade', dl, 500);
      A(K.text(s, ind(k + 1), {x: x + 0.3, y: 2.05, w: w - 0.6, h: 1.2, fontSize: 64, fontFace: DISP, color: red}), 'zoom', dl + 100, 500);
      A(K.shape(s, pres.shapes.LINE, {x: x + 0.3, y: 3.35, w: w - 0.6, h: 0, line: {color: C.gold, width: 1.75}}), 'wipe', dl + 150, 500, 'l');
      A(K.text(s, h, {x: x + 0.3, y: 3.5, w: w - 0.6, h: 0.6, fontSize: 24, fontFace: DISPM, color: C.ink}), 'fade', dl + 200, 500);
      A(K.text(s, b, {x: x + 0.3, y: 4.2, w: w - 0.6, h: 1.8, fontSize: 13.5, color: C.mute, valign: 'top'}), 'fade', dl + 250, 500);
    });
    nav(s, P.cost);
  }

  divider(1);
  // the system at a glance: five spaces round one platform
  {
    const s = K.newSlide(P.glance);
    K.crumb(s, crumbOf(P.glance)); K.title(s, 'منظومة واحدة تربط الجميع');
    K.lead(s, 'منصة وطنية واحدة، وخمسة فضاءات يرى كل منها ما يخصه، في الزمن الحقيقي.');
    const cx = 6.67, cy = 4.2;
    const spaces = [['تطبيق المواطن', 'المواطن والمتطوع والطبيب', 'red', -90], ['بوابة المؤسسات', 'المؤسسة وفريق السلامة', 'teal', -18], ['تطبيق الأعوان', 'قادة الفرق والمتفقدون', 'orange', 54],
      ['لوحة القيادة', 'القاعات الجهوية والمركزية', 'navy', 126], ['نافذة القرار', 'اللجان وأصحاب القرار', 'purple', 198]];
    spaces.forEach(([h, b, tone, deg], k) => {
      const a = deg * Math.PI / 180, x = cx + 3.6 * Math.cos(a), y = cy + 2.0 * Math.sin(a), col = K.tone(tone), dl = 400 + k * 180;
      A(K.shape(s, pres.shapes.LINE, {x: Math.min(cx, x), y: Math.min(cy, y), w: Math.max(0.01, Math.abs(x - cx)), h: Math.max(0.01, Math.abs(y - cy)), flipH: (Math.cos(a) < 0) !== (Math.sin(a) < 0), line: {color: col, width: 1.5, transparency: 30}}), 'fade', dl, 400);
      A(K.panel(s, x - 1.45, y - 0.48, 2.9, 0.96, {line: {color: col, width: 1.75}}), 'zoom', dl + 80, 400);
      A(K.text(s, h, {x: x - 1.35, y: y - 0.42, w: 2.7, h: 0.42, align: 'center', fontSize: 15, bold: true, color: col}), 'fade', dl + 120, 400);
      A(K.text(s, b, {x: x - 1.35, y: y + 0.0, w: 2.7, h: 0.38, align: 'center', fontSize: 11, color: C.mute}), 'fade', dl + 140, 400);
    });
    A(K.shape(s, pres.shapes.OVAL, {x: cx - 1.2, y: cy - 1.2, w: 2.4, h: 2.4, fill: {color: C.root}, line: {color: C.gold, width: 3}}), 'zoom', 200, 600);
    A(K.text(s, 'ء-حماية', {x: cx - 1.2, y: cy - 0.55, w: 2.4, h: 0.6, align: 'center', fontSize: 22, fontFace: DISP, bold: true, color: C.white}), 'zoom', 200, 600);
    A(K.text(s, 'معطى واحد · خوادم وطنية', {x: cx - 1.1, y: cy + 0.1, w: 2.2, h: 0.4, align: 'center', fontSize: 10.5, bold: true, color: C.gold}), 'zoom', 200, 600);
    nav(s, P.glance);
  }
  { const s = journey(P.tomorrow, 'البلاغ مع ء-حماية', 'الخطوات نفسها، لكن المعطى الدقيق حاضر في كل واحدة منها، والعون يتفرغ للقرار.', TOMORROW, 'green', '✓');
    A(K.text(s, 'من الإرسال إلى شاشة القاعة: أقل من نصف ثانية. ومن الشاشة إلى القرار: بمعطى، لا بتقدير.', {x: 0.5, y: 6.25, w: 12.33, h: 0.4, fontSize: 14, bold: true, color: C.gold, align: 'center'}), 'fade', 2000, 600);
    nav(s, P.tomorrow); }

  // from → to, two slides of six
  P.bridge.forEach((n, half) => {
    const s = K.newSlide(n), red = K.tone('red'), green = K.tone('green');
    K.crumb(s, crumbOf(n)); K.title(s, `من … إلى  (${ind(half + 1)}/${ind(2)})`);
    K.lead(s, 'كل نقيصة من النقائص الاثنتي عشرة، وجوابها في المنظومة.');
    const rows = BRIDGE.slice(half * 6, half * 6 + 6), top = 1.85, rh = 0.8, wl = 3.6, wr = 7.93;
    A(K.text(s, 'اليوم', {x: 12.83 - wl, y: top, w: wl, h: 0.4, fontSize: 14, bold: true, color: red}), 'fade', 200, 400);
    A(K.text(s, 'مع ء-حماية', {x: 0.5, y: top, w: wr, h: 0.4, fontSize: 14, bold: true, color: green}), 'fade', 200, 400);
    rows.forEach(([a, b], j) => {
      const y = top + 0.5 + j * rh, dl = 300 + j * 200, k = half * 6 + j;
      A(K.panel(s, 12.83 - wl, y, wl, rh - 0.12, {line: {color: red, width: 1}}), 'fade', dl, 400);
      A(K.text(s, [{text: String(k + 1) + '  ', options: {fontFace: MONO, color: red}}, {text: a, options: {}}], {x: 12.83 - wl + 0.2, y, w: wl - 0.4, h: rh - 0.12, fontSize: 13.5, bold: true, color: C.ink}), 'fade', dl, 400);
      A(K.shape(s, pres.shapes.LEFT_ARROW, {x: 0.5 + wr + 0.08, y: y + (rh - 0.12) / 2 - 0.14, w: 0.55, h: 0.28, fill: {color: C.gold}}), 'wipe', dl + 120, 300, 'l');
      A(K.panel(s, 0.5, y, wr, rh - 0.12, {line: {color: green, width: 1.25}}), 'fade', dl + 180, 400);
      A(K.text(s, b, {x: 0.75, y, w: wr - 0.5, h: rh - 0.12, fontSize: 14, color: C.ink}), 'fade', dl + 200, 400);
    });
    if (half === 0) K.button(s, 'التالية', 1.62, 0.6, 1.0, P.bridge[1]);
    nav(s, n);
  });

  divider(2);
  // one value slide per space
  VALUES.forEach((v, i) => {
    const n = P.values[i], s = K.newSlide(n), col = K.tone(v.tone);
    K.crumb(s, crumbOf(n)); K.title(s, v.name, i + 1);
    const cw = 4.0, ch = 1.45, gx = 0.18, gy = 0.18, x0 = 12.83;
    v.items.forEach(([h, b], k) => {
      const c = k % 2, r = Math.floor(k / 2), x = x0 - (c + 1) * cw - c * gx, y = 1.45 + r * (ch + gy), dl = 300 + k * 140;
      A(K.panel(s, x, y, cw, ch), 'fade', dl, 400);
      A(K.shape(s, pres.shapes.RECTANGLE, {x: x + cw - 0.07, y: y + 0.2, w: 0.07, h: ch - 0.4, fill: {color: col}}), 'fade', dl, 400);
      A(K.text(s, h, {x: x + 0.22, y: y + 0.14, w: cw - 0.45, h: 0.42, fontSize: 14.5, bold: true, color: col}), 'fade', dl + 60, 400);
      A(K.text(s, b, {x: x + 0.22, y: y + 0.6, w: cw - 0.45, h: ch - 0.7, fontSize: 12.5, color: C.ink, valign: 'top'}), 'fade', dl + 100, 400);
    });
    const xv = 0.5, wv = x0 - 2 * cw - gx - 0.25 - xv;
    A(K.panel(s, xv, 1.45, wv, 3 * ch + 2 * gy, {fill: {color: C.root}, line: {color: C.gold, width: 1.5}}), 'fade', 1100, 500);
    A(K.text(s, 'الفارق', {x: xv + 0.3, y: 1.6, w: wv - 0.6, h: 0.36, fontSize: 13, bold: true, color: C.gold}), 'fade', 1150, 400);
    A(K.text(s, v.tag, {x: xv + 0.3, y: 2.0, w: wv - 0.6, h: 1.6, fontSize: 19, bold: true, color: night ? C.ink : C.white, valign: 'top', lineSpacingMultiple: 1.05}), 'fade', 1200, 500);
    v.figs.forEach(([a, b], k) => {
      const y = 3.75 + k * 0.95;
      A(K.shape(s, pres.shapes.LINE, {x: xv + 0.3, y, w: wv - 0.6, h: 0, line: {color: C.gold, width: 1.5}}), 'wipe', 1400 + k * 150, 400, 'l');
      A(K.text(s, a, {x: xv + 0.3, y: y + 0.06, w: wv - 0.6, h: 0.5, fontSize: 24, fontFace: MONO, bold: true, color: night ? C.ink : C.white, ...(/[؀-ۿ]/.test(a) ? {} : {rtlMode: false, lang: 'en-US'})}), 'fade', 1450 + k * 150, 400);
      A(K.text(s, b, {x: xv + 0.3, y: y + 0.52, w: wv - 0.6, h: 0.3, fontSize: 11, color: night ? C.mute : 'DCE3F1'}), 'fade', 1500 + k * 150, 400);
    });
    // the eight spaces as a strip of links
    const sw = 12.33 / VALUES.length;
    VALUES.forEach((u, j) => {
      const x = 12.83 - (j + 1) * sw, on = j === i, c2 = K.tone(u.tone);
      A(K.shape(s, pres.shapes.LINE, {x: x + 0.04, y: 6.5, w: sw - 0.08, h: 0, line: {color: on ? c2 : C.edge, width: on ? 3 : 1}}), 'fade', 1600, 300);
      K.text(s, u.name, {x: x + 0.04, y: 6.56, w: sw - 0.08, h: 0.32, fontSize: 9.5, align: 'center', bold: on, color: on ? c2 : C.mute, fit: 'shrink', ...K.link(P.values[j])});
    });
    if (i < VALUES.length - 1) K.button(s, 'التالية', 1.62, 0.6, 1.0, P.values[i + 1]);
    else K.button(s, 'الذكاء المحلي', 1.62, 0.6, 1.4, P.act[3]);
    K.button(s, 'الفهرس', 0.5, 0.6, 1.0, P.agenda, true); K.counter(s, n);
  });

  divider(3);
  drawAi(K, AI, {crumb: `ء-حماية · ${ind(4)} الذكاء المحلي`, after: P.act[4]});

  divider(4);
  // the answer to the outings without intervention
  {
    const s = K.newSlide(P.answer), green = K.tone('green');
    K.crumb(s, crumbOf(P.answer)); K.title(s, 'جواب المنظومة على الخروج دون تدخل');
    K.lead(s, 'ستّ آليات تعمل قبل أن تتحرك المركبة، وآلية سابعة تقيس ما بقي.');
    OUTINGS.forEach(([h, b], k) => {
      const c = k % 3, r = Math.floor(k / 3), w = 3.95, x = 12.83 - (c + 1) * w - c * 0.24, y = 1.85 + r * 2.15, dl = 300 + k * 150;
      A(K.panel(s, x, y, w, 1.95, {line: {color: green, width: 1.25}}), 'fade', dl, 500);
      A(K.text(s, [{text: ind(k + 1) + '  ', options: {color: C.gold, fontFace: DISP}}, {text: h, options: {}}], {x: x + 0.3, y: y + 0.2, w: w - 0.6, h: 0.5, fontSize: 17, fontFace: DISPM, color: C.ink}), 'fade', dl + 80, 400);
      A(K.text(s, b, {x: x + 0.3, y: y + 0.8, w: w - 0.6, h: 1.0, fontSize: 12.5, color: C.mute, valign: 'top'}), 'fade', dl + 120, 400);
    });
    A(K.text(s, [{text: '≈ 7300  ', options: {fontFace: MONO, color: K.tone('red'), bold: true}}, {text: 'خروج دون تدخل في أربع سنوات: رقم تستطيع المنظومة أن تقيسه كل يوم، حسب الولاية والسبب، وأن تتابع انخفاضه.', options: {color: C.ink, bold: true}}],
      {x: 0.5, y: 6.25, w: 12.33, h: 0.45, fontSize: 13.5, align: 'center'}), 'fade', 1400, 600);
    K.button(s, 'الرقم', 1.62, 0.6, 1.0, P.outings);
    nav(s, P.answer);
  }

  // the vision: three horizons
  {
    const s = K.newSlide(P.vision);
    K.crumb(s, crumbOf(P.vision)); K.title(s, 'الرؤية: ثلاثة آفاق');
    K.lead(s, 'ما يتغيّر عند الاستعمال، ثم بعد سنة، ثم حين تصبح المنظومة ذاكرة القرار.');
    A(K.shape(s, pres.shapes.LINE, {x: 0.9, y: 2.15, w: 11.53, h: 0, line: {color: C.gold, width: 2}}), 'wipe', 200, 1200, 'l');
    HORIZONS.forEach(([h, sub, items], k) => {
      const w = 3.95, x = 12.83 - (k + 1) * w - k * 0.24, dl = 400 + k * 350, col = K.tone(['navy', 'purple', 'green'][k]);
      A(K.shape(s, pres.shapes.OVAL, {x: x + w / 2 - 0.2, y: 1.95, w: 0.4, h: 0.4, fill: {color: C.gold}, line: {color: C.bg, width: 3}}), 'zoom', dl, 400);
      A(K.panel(s, x, 2.6, w, 3.9, {line: {color: col, width: 1.5}}), 'fade', dl + 100, 500);
      A(K.text(s, h, {x: x + 0.3, y: 2.75, w: w - 0.6, h: 0.55, fontSize: 22, fontFace: DISPM, color: col}), 'fade', dl + 150, 400);
      A(K.text(s, sub, {x: x + 0.3, y: 3.3, w: w - 0.6, h: 0.32, fontSize: 12, bold: true, color: C.gold}), 'fade', dl + 180, 400);
      K.list(s, items, x + 0.3, 3.8, w - 0.6, 0.65, col, dl + 250, 12.5);
    });
    nav(s, P.vision);
  }

  // the indicators to follow
  {
    const s = K.newSlide(P.kpis);
    K.crumb(s, crumbOf(P.kpis)); K.title(s, 'ثمانية مؤشرات تقيس النجاح');
    K.lead(s, 'كلها تُحسب آليا من عمل المنظومة نفسه، دون استبيان ولا جمع يدوي.');
    KPIS.forEach(([h, b], k) => {
      const c = k % 4, r = Math.floor(k / 4), w = (12.33 - 0.18 * 3) / 4, x = 12.83 - (c + 1) * w - c * 0.18, y = 1.9 + r * 2.2, dl = 300 + k * 120;
      A(K.panel(s, x, y, w, 1.95), 'fade', dl, 400);
      A(K.shape(s, pres.shapes.LINE, {x: x + 0.25, y: y + 0.3, w: w - 0.5, h: 0, line: {color: C.gold, width: 1.75}}), 'wipe', dl + 80, 400, 'l');
      A(K.text(s, h, {x: x + 0.25, y: y + 0.45, w: w - 0.5, h: 0.6, fontSize: 15.5, bold: true, color: C.ink, valign: 'top'}), 'fade', dl + 100, 400);
      A(K.text(s, b, {x: x + 0.25, y: y + 1.1, w: w - 0.5, h: 0.7, fontSize: 12, color: C.mute, valign: 'top'}), 'fade', dl + 140, 400);
    });
    nav(s, P.kpis);
  }

  // the end: from the report to the decision
  {
    const s = K.newSlide(P.end);
    K.crumb(s, 'ء-حماية · الخلاصة'); K.title(s, 'من التبليغ إلى أخذ القرار');
    [['اليوم', 'بلاغ بالهاتف، ووصف شفوي، وتقدير، وخروج قد يكون دون تدخل.', 'red'],
     ['غدا', 'بلاغ بموقعه وصورته، يُقرأ ويُرتَّب، ووسائل بقدر الحاجة، وفريق مربوط بالقاعة.', 'green'],
     ['الرؤية', 'قرار مبني على الأرقام، ومواطن شريك، ومؤسسات معروفة، وذكاء سيادي يتعلم.', 'purple']].forEach(([h, b, t], k) => {
      const y = 1.5 + k * 1.5, dl = 300 + k * 300, col = K.tone(t);
      A(K.shape(s, pres.shapes.LINE, {x: 0.5, y, w: 12.33, h: 0, line: {color: C.gold, width: 1.5}}), 'wipe', dl, 600, 'l');
      A(K.text(s, h, {x: 10.1, y: y + 0.15, w: 2.73, h: 1.1, fontSize: 40, fontFace: DISP, bold: true, color: col}), 'fade', dl + 150, 500);
      A(K.text(s, b, {x: 0.5, y: y + 0.2, w: 9.4, h: 1.05, fontSize: 17, bold: true, color: C.ink, valign: 'middle'}), 'fade', dl + 250, 500);
    });
    A(K.panel(s, 0.5, 6.1, 12.33, 0.75, {fill: {color: C.root}, line: {color: C.gold, width: 1.5}}), 'fade', 1300, 500);
    A(K.text(s, 'ء-حماية: منظومة وطنية واحدة، على خوادم وطنية، في خدمة المواطن وعون الحماية المدنية.', {x: 0.8, y: 6.1, w: 11.73, h: 0.75, fontSize: 15, bold: true, align: 'center', color: night ? C.ink : C.white}), 'fade', 1400, 500);
    K.button(s, 'الفهرس', 0.5, 0.6, 1.0, P.agenda, true); K.button(s, 'الغلاف', 1.62, 0.6, 1.0, P.cover);
    K.counter(s, P.end);
  }
}

await K.write(out, {cover: '<p:fade/>', agenda: '<p:fade/>', act: '<p:push dir="l"/>', journey: '<p:fade/>', big: '<p:fade/>', grid: '<p:fade/>',
  cost: '<p:fade/>', glance: '<p:fade/>', bridge: '<p:push dir="l"/>', value: '<p:fade/>', why: '<p:fade/>', aimap: '<p:fade/>', tool: '<p:fade/>',
  compare: '<p:fade/>', guards: '<p:fade/>', profiles: '<p:fade/>', answer: '<p:fade/>', vision: '<p:fade/>', kpis: '<p:fade/>', end: '<p:fade/>'});
