// The local AI tools of e-Himaya as a PowerPoint deck (Yamen, 2026-11-14): every AI tool the system runs, where it
// works along the chain «من التبليغ إلى أخذ القرار», what the room does without it and with it, its measured figures,
// its safeguard, and why running it on the Office's own servers makes the difference.
//
//   node scripts/tracking/ai-tools-pptx.mjs <out.pptx>
//
// A separate deck for Yamen's approval; once approved, its slides join the main presentation
// (docs/deliverables/presentation). Same look as the mind maps deck (mindmap-pptx.mjs): the «خوارزمية ء-حماية» night
// blueprint and its day counterpart, a switch on every slide, Reem Kufi for titles, IBM Plex Sans Arabic for text,
// IBM Plex Mono for figures, gold accents, native shapes, links, transitions and entrance animations.
// The facts come from the repository: services/ai, services/vision (README, EVALUATION.md), the model cards
// (services/api/app/modules/modelcards/texts.py), docs/versions.md, docs/phase-ai5/design-ai5.md and docs/learning.md.
import {createRequire} from 'node:module';
import {readFileSync, writeFileSync, mkdtempSync, rmSync, mkdirSync, readdirSync, copyFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const req = createRequire(join(HERE, '../../docs/deliverables/package.json'));
const pptxgen = req('pptxgenjs');
const sharp = req('sharp');
const JSZip = req('jszip');

const [out] = process.argv.slice(2);
const MODES = (process.env.DECK_SETS || 'night,day').split(',').filter(m => ['night', 'day'].includes(m));
if (!out) { console.error('usage: ai-tools-pptx.mjs <out.pptx>'); process.exit(2); }

// ---------------------------------------------------------------- 1. the content
// the stages of the chain, each with its category colour (docs/design-system.md §2.3), dark and light values
const STAGES = [
  {k: 'report', name: 'التبليغ', night: 'FF6B6B', day: 'D7141A'},
  {k: 'watch', name: 'الرصد بالكاميرات', night: 'FFA733', day: 'C25E00'},
  {k: 'sort', name: 'الفرز والتجميع', night: '8FA8FF', day: '1F3FA0'},
  {k: 'command', name: 'القيادة والقرار', night: 'C49BE6', day: '7838A0'},
  {k: 'foresee', name: 'الاستباق', night: '64B5F6', day: '1976D2'},
  {k: 'learn', name: 'التعلم', night: '4CC772', day: '188038'},
];
const TOOLS = [
  {stage: 'report', name: 'تحويل الصوت إلى نص',
    what: 'يحوّل الكلام إلى نص مكتوب: بلاغ المواطن الصوتي، أوامر القائد، رسائل الفرق في كل مرحلة من المهمة، تقارير الحالة، والإملاء في الحقول الحرة. ثم ينقّح النموذج اللغوي النص (الإملاء، كلمات المهنة، الترقيم) دون أن يضيف معلومة أو يحذفها.',
    without: ['المواطن المصاب أو المذعور أو الذي لا يكتب لا يستطيع وصف ما يراه', 'القاعة تستمع إلى كل تسجيل كاملا لتعرف ما فيه', 'الفريق في الميدان يكتب على الهاتف ويداه مشغولتان'],
    with: ['يكفي أن يتكلّم المواطن بالدارجة أو الفصحى أو الفرنسية', 'نص يُقرأ بنظرة ويدخل في الفرز والبحث والتحليل', 'القائد والفريق يمليان، يصحّحان، ثم يرسلان'],
    value: 'الصوت يصبح معطى يُقرأ ويُبحث فيه ويُحلَّل، دون أن يغادر خوادم الديوان.',
    figures: [['≤ 15٪', 'هدف الكلمات الخاطئة بالدارجة'], ['10', 'دقائق، أقصى طول للتسجيل'], ['3', 'لغات: فصحى ودارجة وفرنسية']],
    where: ['بلاغ المواطن الصوتي', 'رسالة القائد الصوتية', 'رسائل الفرق في الميدان', 'تقارير الحالة', 'الإملاء في الحقول الحرة'],
    guard: 'النص يُعرض لصاحبه ليصحّحه قبل الإرسال، والتصحيحات تقيس الدقة وتحسّنها. تسجيلات الأعوان تُحذف بعد التفريغ.',
    tech: 'Whisper large-v3 (faster-whisper) · MIT · موجّه بمعجم الدارجة والطوارئ'},
  {stage: 'report', name: 'القراءة المهيكلة للبلاغ',
    what: 'يقرأ نص البلاغ أو تفريغه الصوتي، ويقترح نوع الحادث، وهل الأرواح في خطر، وعدد المصابين، والمخاطر المرافقة (غاز، كهرباء، انفجار، انهيار)، وملخصا عربيا في سطر.',
    without: ['المشغّل يقرأ كل بلاغ كاملا ليفرزه', 'بلاغ بالدارجة اللاتينية «famma 7ari9» يبقى في صنف «أخرى»', 'خطر على الأرواح يضيع في وسط نص طويل'],
    with: ['ملخص في سطر وصنف مقترح بجانب كل بلاغ', 'يفهم الفصحى والدارجة بالحرفين والفرنسية والإنجليزية', 'إشارة الأرواح في خطر ترفع الأولوية فورا'],
    value: 'فرز أسرع وأدق في الدقائق الأولى، بتعليل يراه المشغّل.',
    figures: [['5', 'لغات وكتابات يقرؤها'], ['0', 'بلاغ تنخفض أولويته بسببه'], ['60', 'بلاغا في مجموعة التقييم [SIM]']],
    where: ['كل بلاغ جديد', 'قائمة الفرز في القاعة', 'بطاقة البلاغ'],
    guard: 'اقتراح موسوم «اقتراح آلي» لا يخفّض أولوية بلاغ أبدا. الجواب مقيَّد بمخطط، وإن فشل يبقى البلاغ بالقواعد وحدها.',
    tech: 'Qwen3 8B عبر Ollama · Apache-2.0 · جواب JSON مقيَّد بمخطط'},
  {stage: 'report', name: 'الترجمة إلى العربية',
    what: 'يترجم البلاغات والنصوص الواردة بالفرنسية أو الإنجليزية إلى العربية، لتقرأها القاعة بلغة واحدة.',
    without: ['بلاغ سائح أو أجنبي ينتظر من يفهم لغته', 'الترجمة عبر خدمة على الإنترنت تكشف كلام المبلّغ'],
    with: ['النص العربي يظهر بجانب الأصل', 'البلاغ يدخل في الفرز والبحث بالعربية'],
    value: 'كل بلاغ يُقرأ بالعربية، ولا يخرج نصه من خوادم الديوان.',
    figures: [['2', 'اتجاها ترجمة إلى العربية'], ['0', 'نص يُرسل إلى خدمة خارجية']],
    where: ['البلاغات بالفرنسية', 'البلاغات بالإنجليزية', 'تحليل البلاغ قبل الفرز'],
    guard: 'الترجمة مساعدة على القراءة، والنص الأصلي محفوظ كما كُتب.',
    tech: 'Opus-MT fr→ar و en→ar · Apache-2.0 / CC-BY-4.0 · CTranslate2'},
  {stage: 'watch', name: 'كشف النار والدخان',
    what: 'يقرأ صور البلاغات وبثّ الكاميرات والدرون، ويقترح «نار» أو «دخان» على المشغّل مع موضعهما في الصورة.',
    without: ['شاشات الكاميرات تحتاج عينا بشرية لا تغفل', 'الحريق يُعرف حين يتصل أحد', 'صورة البلاغ لا تقول شيئا قبل أن يفتحها أحد'],
    with: ['كل كاميرا موصولة تُراقَب إطارا كل ثانية، ليلا ونهارا', 'تنبيه مبكر يُظهر الإطار وموضع النار للمشغّل', 'صورة البلاغ تُقرأ لحظة وصولها'],
    value: 'عين لا تتعب على كل كاميرا، بنموذج دُرّب للمشروع برخصة تسمح باستعماله.',
    figures: [['0.96', 'استرجاع النار (النسخة 3.0.0)'], ['0.1', 'ثانية للإطار على المعالج دون GPU'], ['3 من 5', 'إطارات لتأكيد التنبيه']],
    where: ['صور البلاغات', 'كاميرات المراقبة', 'بثّ الدرون'],
    guard: 'لا يفتح تدخلا وحده: يتأكد التنبيه في 3 إطارات من 5 والمشغّل يقرّر. الدخان تلميح فقط، وحدوده منشورة في بطاقة النموذج.',
    tech: 'YOLOX-Tiny مدرَّب للمشروع 3.0.0 · Apache-2.0 · ONNX Runtime'},
  {stage: 'watch', name: 'كاشف الأشخاص',
    what: 'يعدّ الأشخاص الظاهرين في صور البلاغات وبثّ الكاميرات والدرون، ليعرف المشغّل هل في المكان ناس.',
    without: ['لا يُعرف قبل الوصول هل في المكان ناس', 'تقدير العالقين يعتمد على كلام المتصل وحده'],
    with: ['المشغّل يرى عدد الأشخاص في الصورة', 'معلومة إضافية لتقدير الوسائل قبل الإرسال'],
    value: 'معلومة عن الأرواح في المكان، دون أي تعرّف على الوجوه.',
    figures: [['0', 'وجه يُتعرَّف عليه أو هوية تُحفظ'], ['0.1', 'ثانية للإطار على المعالج']],
    where: ['صور البلاغات', 'كاميرات المراقبة', 'بثّ الدرون'],
    guard: 'لا يتعرّف على الوجوه ولا يحفظ هوية أحد. يُطفأ من الإعدادات على المعالجات الصغيرة.',
    tech: 'YOLOX-Tiny (COCO، صنف الأشخاص وحده) · Apache-2.0 · ONNX Runtime'},
  {stage: 'sort', name: 'بصمة المعنى: تجميع البلاغات والبحث',
    what: 'يحوّل كل نص إلى بصمة معنى، فيُعرف أن بلاغين يصفان الحدث نفسه وإن اختلفت كلماتهما ولغتهما، ويُبحث في مكتبة الأحداث بالمعنى لا بالكلمة وحدها.',
    without: ['عشرون بلاغا عن حريق واحد تظهر عشرين حادثا', 'البحث بالكلمة يفوّت «حريق» حين كُتب «نار» أو «incendie»'],
    with: ['اقتراح تجميع يزن المكان والزمن والمعنى', 'بحث يمزج النص والمعنى ويجد المرادفات عبر اللغات'],
    value: 'صورة واحدة للحدث بدل البلاغات المكرّرة، وذاكرة مؤسسية يُعثر فيها على ما يشبه.',
    figures: [['768', 'بعدا لبصمة المعنى'], ['30٪', 'وزن المعنى في اقتراح التجميع']],
    where: ['اقتراح تجميع البلاغات', 'مكتبة الأحداث', 'بحث الإجراءات والذاكرة'],
    guard: 'التجميع اقتراح يقبله المشغّل أو يرفضه. البحث يحترم صلاحيات كل دور ونطاقه الجغرافي.',
    tech: 'multilingual-e5-base · MIT · pgvector داخل قاعدة البيانات'},
  {stage: 'command', name: 'مساعد القائد',
    what: 'يقترح على القائد قرارات مرقّمة ومعلّلة لكل حادثة، ويقرأ أوامره المكتوبة أو المملاة بالفصحى أو الدارجة أو الفرنسية ليحوّلها إلى بطاقة قرار.',
    without: ['القائد يتذكّر وحده ما ينقص وما فعله غيره في حالات مشابهة', 'الأمر الشفهي يضيع أو يُنقل بغير دقة'],
    with: ['اقتراحات بتعليلها وبما فعله القادة قبله', '«ابعث زوز شاحنات ماء» تصبح بطاقة: الفعل والصنف والعدد', 'كل قرار يُربط بنتيجة الحادث ليتعلّم الترتيب'],
    value: 'ذاكرة القيادة ومساعد لا ينسى، والقرار يبقى للقائد.',
    figures: [['86.7٪', 'مطابقة تامة على 60 أمرا محجوزا'], ['≥ 95٪', 'الهدف المعلن'], ['0', 'أمر يُنفَّذ دون اعتماد']],
    where: ['لوحة القائد', 'نافذة القرار', 'الرسالة الصوتية للقائد'],
    guard: 'القائد يعتمد أو يعدّل أو يرفض بسبب. الاعتماد يفتح المسار المعتاد ولا ينفّذ شيئا. الترتيب المتعلَّم في الظل حتى تقرر اللجنة.',
    tech: 'Qwen3 + معجم الدارجة والفصحى والفرنسية + مرتِّب scikit-learn'},
  {stage: 'command', name: 'قراءة مخطط التدخل',
    what: 'يقرأ مخطط التدخل (PDF) ويستخرج منه قائمة مهام، لكل مهمة رقم صفحتها واقتباس منها.',
    without: ['مخطط من عشرات الصفحات يُقرأ في لحظة الأزمة', 'المهام تُنسخ يدويا إلى قائمة التحقق'],
    with: ['قائمة مهام جاهزة للمراجعة، كل مهمة بمصدرها', 'الاقتباس يُبحث عنه آليا في صفحته'],
    value: 'المخطط المكتوب يصبح قائمة تحقق حيّة في الأزمة.',
    figures: [['1', 'صفحة واقتباس لكل مهمة'], ['100٪', 'من المهام يراجعها رئيس القاعة']],
    where: ['مخططات التدخل', 'قائمة التحقق في الأزمة'],
    guard: 'رئيس القاعة يراجع المهام واحدة واحدة قبل اعتمادها، وما قُبل وما عُدّل وما حُذف يُعدّ في بطاقة النموذج.',
    tech: 'Qwen3 · Apache-2.0'},
  {stage: 'command', name: 'الملخص المكتوب لأصحاب القرار',
    what: 'يكتب في نافذة أصحاب القرار ملخصا استشاريا لنتيجة بحث أو مقارنة، من الأرقام المجمَّعة المعروضة وحدها.',
    without: ['جداول وأرقام تحتاج محلّلا لقراءتها', 'خطر رقم مختلَق في تقرير رسمي'],
    with: ['فقرة تقول ما في الجدول بلغة القرار', 'كل رقم في الملخص يُطابَق مع الجدول، وإلا يُرفض'],
    value: 'قراءة سريعة لصاحب القرار دون أي رقم مختلَق.',
    figures: [['0', 'رقم مختلَق يُعرض'], ['0', 'بلاغ أو اسم يراه النموذج']],
    where: ['نافذة القرار', 'البحث والمقارنة'],
    guard: 'لا يرى أي بلاغ ولا اسم، بل الجدول المجمَّع وحده. كل ملخص ذكر رقما غير موجود يُرفض ويُعدّ.',
    tech: 'Qwen3 · Apache-2.0'},
  {stage: 'foresee', name: 'المؤشرات الخارجة عن عادتها',
    what: 'يقارن كل مؤشر بعادته: عدد البلاغات في الولاية، زمن الوصول في المعتمدية، ونسبة إنجاز البرامج، بالأيام نفسها في السنوات الثلاث الماضية.',
    without: ['ارتفاع غير عادي يُلاحَظ متأخرا أو لا يُلاحَظ', 'تأخّر الوصول في معتمدية يختفي في المعدّل الوطني'],
    with: ['تنبيه هادئ في مركز التنبيهات مع شرحه بالأرقام', 'مقارنة موسمية تحترم الصيف والشتاء'],
    value: 'انتباه مبكر لما تغيّر، بإحصاء شفاف يُفهم ويُراجَع.',
    figures: [['3', 'مؤشرات تُراقَب'], ['3', 'سنوات للمقارنة الموسمية']],
    where: ['الوضع الآن', 'مركز التنبيهات'],
    guard: 'إحصاء بسيط دون نموذج لغوي، كل نتيجة بشرحها. لا يصل شيء منه إلى المواطن.',
    tech: 'إحصاء (الانحراف المعياري) · داخل الخادم'},
  {stage: 'foresee', name: 'نموذج خطر الغرق',
    what: 'يحسب كل يوم احتمال الغرق في كل شاطئ، ويُعرض للأعوان بجانب مستوى القاعدة المعلنة للمقارنة.',
    without: ['مستوى الخطر بالقواعد وحدها', 'لا وسيلة لقياس هل يمكن التنبؤ بأدق'],
    with: ['قراءة ثانية يقارَن بها مستوى القاعدة يوما بيوم', 'دليل بالأرقام قبل أي اعتماد'],
    value: 'طريق مقاس نحو تنبؤ أدق، دون المساس بما يُنشر للمواطن.',
    figures: [['30000', 'يوم-شاطئ للتدريب [SIM]'], ['10000', 'يوم آخر للقياس [SIM]']],
    where: ['خطر الشواطئ', 'بطاقة النموذج'],
    guard: 'في الظل: لا يُنشر للمواطن ولا يفتح تنبيها ولا يغيّر مستوى القاعدة حتى تعتمده اللجنة.',
    tech: 'انحدار لوجستي scikit-learn · BSD-3 · معاملات فقط'},
  {stage: 'learn', name: 'مركز التدريب الذاتي',
    what: 'يعيد تدريب الأدوات من بلاغات المنظومة وقرارات أعوانها: صنف الحادث، الأرواح في خطر، البلاغات المرفوضة، كلمات الدارجة الجديدة، كاشف النار والدخان، وترتيب اقتراحات القائد.',
    without: ['النموذج يبقى كما وصل، لا يعرف الدارجة المحلية', 'التحسين يحتاج مزوّدا خارجيا وإرسال البيانات إليه'],
    with: ['كل تصحيح من مشغّل أو قائد يصبح درسا', 'التدريب على خوادم الديوان، والأرقام تُقارَن قبل الاعتماد'],
    value: 'منظومة تتحسّن بالاستعمال، وبياناتها لا تغادر الديوان.',
    figures: [['6', 'تدريبات'], ['0', 'اسم أو رقم هاتف في العيّنات']],
    where: ['مركز التدريب', 'إعدادات الذكاء الاصطناعي', 'بطاقات النماذج'],
    guard: 'العيّنات مجهَّلة ومشفّرة. كل نسخة مدرّبة تُقاس وتُسجَّل، وكل تشغيل مدقَّق في السجل.',
    tech: 'scikit-learn على العامل · GPU لكاشف النار · داخل خوادم الديوان'},
];
TOOLS.forEach((t, i) => { t.i = i; t.st = STAGES.find(s => s.k === t.stage); });
const WHY = [
  ['السيادة على البيانات', 'بلاغات المواطنين وأصواتهم وصورهم لا تغادر خوادم الديوان، ولا تمرّ بأي خدمة سحابية.'],
  ['تعمل في قلب الأزمة', 'النماذج مثبّتة على الخوادم ولا يُنزَّل شيء أثناء العمل: انقطاع الإنترنت الدولي لا يوقفها.'],
  ['كلفة ثابتة', 'لا اشتراك ولا فاتورة لكل طلب: عشرة بلاغات أو عشرة آلاف، الكلفة هي الخادم.'],
  ['رخص مفتوحة متساهلة', 'كل نموذج برخصة MIT أو Apache أو BSD، الكود والأوزان معا؛ وكل رخصة مقيِّدة تُرفض آليا.'],
  ['شفافة وقابلة للتدقيق', 'لكل أداة بطاقة نموذج بأرقامها وحدودها، وكل اقتراح مسجَّل في السجل.'],
  ['تتعلم من الواقع التونسي', 'الدارجة بالحرفين وكلمات المهنة وبلاغات تونس: الأدوات تتعلم منها محليا.'],
];
const COMPARE = [
  ['أين تبقى البيانات', 'خوادم الديوان', 'خوادم المزوّد في الخارج'],
  ['عند انقطاع الإنترنت', 'تعمل', 'تتوقف'],
  ['الكلفة في أزمة كبرى', 'ثابتة', 'تتضاعف مع عدد الطلبات'],
  ['الدارجة التونسية', 'تُدرَّب عليها محليا', 'حسب ما يقدّمه المزوّد'],
  ['التدقيق', 'بطاقة نموذج وأرقام معلنة', 'صندوق مغلق'],
  ['تغيير النموذج', 'بقرار اللجنة', 'بقرار المزوّد'],
  ['الرخصة', 'مفتوحة متساهلة', 'عقد استعمال'],
];
const GUARDS = [
  ['يقترح ويعلّل، والإنسان يقرّر', 'لا أداة تفتح تدخلا أو ترسل تنبيها وحدها (AI-01).'],
  ['موسوم «اقتراح آلي»', 'كل اقتراح يظهر بوسمه، ومسجَّل في السجل.'],
  ['لا يخفّض الأولوية أبدا', 'الذكاء الاصطناعي يرفع الانتباه ولا ينزله.'],
  ['يُطفأ بمفتاح', 'لكل أداة مفتاح في إعدادات الذكاء الاصطناعي.'],
  ['القواعد تأخذ مكانه', 'إن غاب النموذج يستمر العمل بالقواعد المعلنة.'],
  ['الظل قبل الاعتماد', 'النموذج الجديد يقارَن بالقواعد قبل أن تعتمده اللجنة.'],
];
const PROFILES = [
  ['خادم بمعالج رسومي (الإنتاج)', 'Whisper large-v3', 'Qwen3 8B', 'GPU'],
  ['خادم بمعالج عادي', 'Whisper medium', 'Qwen3 4B', 'CPU'],
  ['الاختبار الآلي', 'Whisper small', 'Qwen3 1.7B', 'CI'],
];

// ---------------------------------------------------------------- 2. palette and helpers
const PALETTES = {
  night: {bg: '08102A', panel: '161E35', line: '26304D', grid: '16224A', edge: '3A4770', root: '0E1426', shade: '050A1C',
    ink: 'E8ECF5', mute: 'A6AFC4', gold: 'C9A24A', white: 'FFFFFF', onGold: '1B1405', no: 'FF6B6B'},
  day: {bg: 'F6F8FC', panel: 'FFFFFF', line: 'D5DCEB', grid: 'E3E9F4', edge: 'B9C4DD', root: '1F3FA0', shade: 'DCE3F1',
    ink: '0E1426', mute: '55607A', gold: '9C7A22', white: 'FFFFFF', onGold: 'FFFFFF', no: 'D7141A'},
};
let C, MODE, GRID, OFF = 0;
const FONT = 'IBM Plex Sans Arabic', DISP = 'Reem Kufi', DISPM = 'Reem Kufi Medium', MONO = 'IBM Plex Mono Medium';
const SYSTEM = 'منظومة ذكية للتبليغ والمشاركة المجتمعية والمؤسساتية في مجال السلامة والوقاية وإدارة الأخطار';
const ind = n => String(n).replace(/\d/g, d => '٠١٢٣٤٥٦٧٨٩'[d]);
const AR = {rtlMode: true, lang: 'ar-SA', fontFace: FONT};
const stc = st => st[MODE];

const ROOT = join(HERE, '../..');
const EMBLEM = 'image/png;base64,' + readFileSync(join(HERE, 'assets/civil-protection-logo.png')).toString('base64');
const WORD = 'image/png;base64,' + (await sharp(join(ROOT, 'infra/keycloak/themes/ehimaya/login/resources/img/logo-horizontal.png'))
  .extract({left: 0, top: 70, width: 590, height: 275}).png().toBuffer()).toString('base64');
const ground = async c => 'image/png;base64,' + (await sharp(Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
  <defs><pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0V40M0 40H40" stroke="#${c.grid}" stroke-width="2" fill="none"/></pattern>
  <radialGradient id="v" cx="50%" cy="40%" r="75%"><stop offset="0" stop-color="#${c.bg}" stop-opacity="0"/><stop offset="1" stop-color="#${c.shade}" stop-opacity=".85"/></radialGradient></defs>
  <rect width="1920" height="1080" fill="#${c.bg}"/><rect width="1920" height="1080" fill="url(#g)"/><rect width="1920" height="1080" fill="url(#v)"/></svg>`))
  .png().toBuffer()).toString('base64');
const GROUNDS = {night: await ground(PALETTES.night), day: await ground(PALETTES.day)};

// slide plan (1-based, for the links)
const plan = [];
const add = (t, o = {}) => { plan.push({t, ...o}); return plan.length; };
const P = {cover: add('cover'), why: add('why'), map: add('map')};
TOOLS.forEach(t => { t.slide = add('tool', {tool: t.i}); });
P.compare = add('compare'); P.guards = add('guards'); P.profiles = add('profiles'); P.end = add('end');
const N = plan.length;

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.title = 'أدوات الذكاء الاصطناعي المحلية في ء-حماية';
pres.author = 'e-Himaya';
pres.rtlMode = true;
pres.theme = {headFontFace: DISP, bodyFontFace: FONT};

const anim = [];
let cur = 0, seq = 0;
const nm = () => `s${cur}_${++seq}`;
const A = (o, fx, delay, dur = 500, dir) => { (anim[cur] ||= []).push({name: o.objectName, fx, delay, dur, dir}); return o; };
const link = n => n ? {hyperlink: {slide: n + OFF, tooltip: ''}} : {};
const linkAbs = n => ({hyperlink: {slide: n, tooltip: ''}});
const shapeLinks = [];
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
function image(s, o) { const opt = {objectName: nm(), ...o}; s.addImage(opt); return opt; }
const panel = (s, x, y, w, h, o = {}) => shape(s, pres.shapes.ROUNDED_RECTANGLE, {x, y, w, h, rectRadius: 0.14, fill: {color: C.panel}, line: {color: C.line, width: 1}, ...o});
function button(s, label, x, y, w, to, primary = false) {
  shape(s, pres.shapes.ROUNDED_RECTANGLE, {x, y, w, h: 0.36, rectRadius: 0.18, fill: {color: primary ? C.gold : C.panel}, line: {color: primary ? C.gold : C.line}, ...link(to)});
  text(s, label, {x, y, w, h: 0.36, align: 'center', fontSize: 11.5, bold: primary, color: primary ? C.onGold : C.ink, ...link(to)});
}
function emblem(s, x = 12.23, y = 0.28, w = 0.6) {
  const o = {data: EMBLEM, x, y, w, h: w, objectName: nm(), altText: 'شعار الديوان الوطني للحماية المدنية', ...link(P.map)};
  s.addImage(o); return o;
}
const crumb = (s, label) => text(s, label, {x: 4.6, y: 0.3, w: 7.45, h: 0.3, fontSize: 11, bold: true, color: C.gold});
function title(s, label, num) {
  const t = num != null ? [{text: ind(num) + '  ', options: {color: C.gold, fontFace: DISP, fontSize: 30}}, {text: label, options: {}}] : label;
  return text(s, t, {x: 3.6, y: 0.58, w: 8.45, h: 0.62, fontSize: 28, fontFace: DISPM, color: C.ink, fit: 'shrink'});
}
const counter = (s, n) => text(s, `${n} / ${N}`, {x: 0.5, y: 7.08, w: 1.4, h: 0.25, fontSize: 9, fontFace: MONO, align: 'left', color: C.mute});
const foot = s => text(s, 'ء-حماية · الذكاء الاصطناعي يعمل داخل خوادم الديوان', {x: 6.0, y: 7.08, w: 6.83, h: 0.25, fontSize: 9, color: C.mute});
function figure(s, x, y, w, v, l, dl, col = C.gold) {
  A(shape(s, pres.shapes.LINE, {x, y, w, h: 0, line: {color: col, width: 1.75}}), 'wipe', dl, 500, 'l');
  A(text(s, String(v), {x, y: y + 0.08, w, h: 0.5, fontSize: 24, fontFace: MONO, color: C.ink, bold: true, ...(/[\u0600-\u06FF]/.test(v) ? {} : {rtlMode: false, lang: 'en-US'})}), 'fade', dl + 150, 500);
  A(text(s, l, {x, y: y + 0.56, w, h: 0.3, fontSize: 10.5, color: C.mute}), 'fade', dl + 200, 500);
}
// a list of short lines, each with its mark (a coloured dot) on the right
function list(s, items, x, y, w, lineH, col, dl, fs = 13) {
  items.forEach((t, k) => {
    const yy = y + k * lineH;
    A(shape(s, pres.shapes.OVAL, {x: x + w - 0.13, y: yy + 0.13, w: 0.11, h: 0.11, fill: {color: col}}), 'fade', dl + k * 120, 400);
    A(text(s, t, {x, y: yy, w: w - 0.25, h: lineH - 0.04, fontSize: fs, valign: 'top', color: C.ink, lineSpacingMultiple: 0.95}), 'fade', dl + k * 120, 400);
  });
}

function newSlide(n) {
  cur = n + OFF; seq = 0;
  const s = pres.addSlide();
  if (pres.slides.length !== cur) throw new Error(`slide ${pres.slides.length} built where the plan expects ${cur}`);
  s.background = {data: GRID};
  if (n !== P.cover) emblem(s);
  if (MODES.length < 2) return s;
  const other = n + (MODES.indexOf(MODE) === 0 ? N : 0), w = 1.05;
  shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 0.5, y: 0.14, w, h: 0.28, rectRadius: 0.14, fill: {color: C.panel}, line: {color: C.line}, ...linkAbs(other)});
  text(s, MODE === 'night' ? '☀ نهاري' : '☾ ليلي', {x: 0.5, y: 0.14, w, h: 0.28, align: 'center', fontSize: 9.5, color: C.ink, ...linkAbs(other)});
  return s;
}

// ---------------------------------------------------------------- 3. the slides, night set then day set
for (const mode of MODES) {
MODE = mode; C = PALETTES[mode]; GRID = GROUNDS[mode]; OFF = MODES.indexOf(mode) * N;

// cover: the hero beside the tools in orbit round the system, each a link to its slide
{
  const s = newSlide(P.cover), cx = 3.2, cy = 3.75, R = 2.35;
  A(shape(s, pres.shapes.OVAL, {x: cx - R - 0.42, y: cy - R - 0.42, w: 2 * (R + 0.42), h: 2 * (R + 0.42), line: {color: C.gold, width: 1.5, dashType: 'sysDot', transparency: 55}}), 'fade', 0, 900);
  A(shape(s, pres.shapes.OVAL, {x: cx - R, y: cy - R, w: 2 * R, h: 2 * R, line: {color: C.edge, width: 0.75, dashType: 'dash'}}), 'fade', 0, 900);
  TOOLS.forEach((t, i) => {
    const a = -Math.PI / 2 + i * 2 * Math.PI / TOOLS.length, x = cx + R * Math.cos(a), y = cy + R * Math.sin(a), r = 0.27, col = stc(t.st), d0 = 300 + i * 90;
    A(shape(s, pres.shapes.LINE, {x: Math.min(cx + 1.05 * Math.cos(a), x - r * Math.cos(a)), y: Math.min(cy + 1.05 * Math.sin(a), y - r * Math.sin(a)),
      w: Math.max(0.01, Math.abs((x - r * Math.cos(a)) - (cx + 1.05 * Math.cos(a)))), h: Math.max(0.01, Math.abs((y - r * Math.sin(a)) - (cy + 1.05 * Math.sin(a)))),
      flipH: (Math.cos(a) < 0) !== (Math.sin(a) < 0), line: {color: col, width: 1.25, transparency: 40}}), 'fade', d0, 400);
    A(shape(s, pres.shapes.OVAL, {x: x - r, y: y - r, w: 2 * r, h: 2 * r, fill: {color: col}, line: {color: C.bg, width: 2}, ...link(t.slide)}), 'zoom', d0 + 100, 400);
    A(text(s, String(i + 1), {x: x - r, y: y - r, w: 2 * r, h: 2 * r, align: 'center', fontSize: 13, fontFace: MONO, bold: true, color: C.white, rtlMode: false, ...link(t.slide)}), 'zoom', d0 + 100, 400);
  });
  A(shape(s, pres.shapes.OVAL, {x: cx - 1.05, y: cy - 1.05, w: 2.1, h: 2.1, fill: {color: C.root}, line: {color: C.gold, width: 3}, ...link(P.map)}), 'zoom', 0, 600);
  A(text(s, [{text: 'ء-حماية', options: {fontSize: 24, fontFace: DISP, bold: true, color: C.white, breakLine: true}}, {text: `${TOOLS.length} أداة محلية`, options: {fontSize: 12, color: C.gold}}],
    {x: cx - 1.05, y: cy - 0.6, w: 2.1, h: 1.2, align: 'center', ...link(P.map)}), 'zoom', 0, 600);
  A(text(s, 'e-HIMAYA · LOCAL AI · 2026', {x: 6.6, y: 0.42, w: 5.2, h: 0.28, fontSize: 10, fontFace: MONO, color: C.gold, rtlMode: false, lang: 'en-US', align: 'right', charSpacing: 2}), 'fade', 0, 600);
  A(emblem(s, 11.93, 0.3, 0.9), 'zoom', 0, 600);
  A(text(s, 'الديوان الوطني للحماية المدنية', {x: 6.6, y: 0.72, w: 5.2, h: 0.4, fontSize: 15, bold: true, color: C.ink}), 'fade', 150, 600);
  if (MODE === 'day') shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: 9.48, y: 1.22, w: 3.5, h: 3.2 * 275 / 590 + 0.2, rectRadius: 0.16, fill: {color: C.root}});
  A(image(s, {data: WORD, x: 9.63, y: 1.32, w: 3.2, h: 3.2 * 275 / 590, altText: 'ء-حماية E-HIMAYA'}), 'fade', 300, 900);
  A(text(s, [{text: 'ذكاء اصطناعي ', options: {color: C.ink}}, {text: 'محلي', options: {color: C.gold}}],
    {x: 6.3, y: 2.95, w: 6.53, h: 0.85, fontSize: 40, fontFace: DISP, bold: true}), 'fade', 450, 800);
  A(text(s, 'أدوات الذكاء الاصطناعي المعتمدة في المنظومة، وما تضيفه في كل مرحلة من التبليغ إلى أخذ القرار',
    {x: 6.3, y: 3.82, w: 6.53, h: 0.85, fontSize: 17, lineSpacingMultiple: 1.05, fontFace: DISPM, color: C.ink, valign: 'top'}), 'fade', 600, 800);
  A(text(s, SYSTEM, {x: 6.3, y: 4.75, w: 6.53, h: 0.55, fontSize: 11.5, color: C.mute, valign: 'top'}), 'fade', 750, 700);
  button(s, 'لماذا محلية؟', 10.73, 5.55, 2.1, P.why, true);
  button(s, 'خريطة الأدوات', 8.48, 5.55, 2.1, P.map);
  A(text(s, 'اضغط على أي رقم للانتقال إلى أداته.', {x: 6.3, y: 6.1, w: 6.53, h: 0.3, fontSize: 10.5, color: C.mute}), 'fade', 900, 600);
}

// why local: six values
{
  const s = newSlide(P.why);
  crumb(s, 'ء-حماية · الذكاء الاصطناعي المحلي'); A(title(s, 'لماذا محلية؟'), 'fade', 0, 500);
  A(text(s, 'كل أداة تعمل على خوادم الديوان، بنماذج مفتوحة المصدر مثبّتة مسبقا. هذا وحده يغيّر ستة أشياء:', {x: 2.9, y: 1.22, w: 9.15, h: 0.36, fontSize: 13.5, color: C.mute}), 'fade', 150, 500);
  WHY.forEach(([h, b], k) => {
    const col = k % 3, row = Math.floor(k / 3), w = 3.95, x = 12.83 - (col + 1) * w - col * 0.2, y = 1.85 + row * 2.45, dl = 300 + k * 140;
    A(panel(s, x, y, w, 2.2), 'fade', dl, 500);
    A(shape(s, pres.shapes.LINE, {x: x + 0.3, y: y + 0.32, w: w - 0.6, h: 0, line: {color: C.gold, width: 1.75}}), 'wipe', dl + 100, 500, 'l');
    A(text(s, [{text: ind(k + 1) + '  ', options: {color: C.gold, fontFace: DISP}}, {text: h, options: {}}], {x: x + 0.3, y: y + 0.45, w: w - 0.6, h: 0.5, fontSize: 18, fontFace: DISPM, color: C.ink}), 'fade', dl + 150, 500);
    A(text(s, b, {x: x + 0.3, y: y + 1.0, w: w - 0.6, h: 1.05, fontSize: 12.5, color: C.ink, valign: 'top'}), 'fade', dl + 200, 500);
  });
  button(s, 'خريطة الأدوات', 0.5, 0.6, 1.5, P.map, true);
  foot(s); counter(s, P.why);
}

// map: the chain from the report to the decision, the tools under their stage, each a link
{
  const s = newSlide(P.map);
  crumb(s, 'ء-حماية · من التبليغ إلى أخذ القرار'); A(title(s, 'خريطة الأدوات'), 'fade', 0, 500);
  A(text(s, 'أين تعمل كل أداة في سلسلة المنظومة. اضغط على أداة لفتح شريحتها.', {x: 2.9, y: 1.22, w: 9.15, h: 0.36, fontSize: 13.5, color: C.mute}), 'fade', 150, 500);
  const n = STAGES.length, gap = 0.14, w = (12.33 - gap * (n - 1)) / n;
  STAGES.forEach((st, k) => {
    const x = 12.83 - (k + 1) * w - k * gap, col = stc(st), dl = 250 + k * 160, tools = TOOLS.filter(t => t.stage === st.k);
    A(shape(s, pres.shapes.CHEVRON, {x, y: 1.8, w: w + 0.05, h: 0.62, fill: {color: col}, flipH: true}), 'wipe', dl, 500, 'l');
    A(text(s, st.name, {x: x + 0.15, y: 1.8, w: w - 0.3, h: 0.62, align: 'center', fontSize: 13, bold: true, color: mode === 'night' ? '0E1426' : 'FFFFFF'}), 'fade', dl + 100, 400);
    tools.forEach((t, j) => {
      const y = 2.65 + j * 1.38, d = dl + 200 + j * 120;
      A(panel(s, x, y, w, 1.22, {line: {color: col, width: 1.25}, ...link(t.slide)}), 'fade', d, 400);
      A(text(s, [{text: String(t.i + 1), options: {fontFace: MONO, color: col, bold: true, breakLine: true}}, {text: t.name, options: {}}],
        {x: x + 0.12, y: y + 0.08, w: w - 0.24, h: 1.06, fontSize: 12.5, bold: true, align: 'center', color: C.ink, ...link(t.slide)}), 'fade', d, 400);
    });
  });
  button(s, 'لماذا محلية؟', 0.5, 0.6, 1.5, P.why);
  foot(s); counter(s, P.map);
}

// one slide per tool: what it does, without it and with it, the difference, its figures, where it works, its safeguard
for (const t of TOOLS) {
  const s = newSlide(t.slide), col = stc(t.st);
  crumb(s, `ء-حماية · ${t.st.name}`); A(title(s, t.name, t.i + 1), 'fade', 0, 500);
  A(shape(s, pres.shapes.RECTANGLE, {x: 12.78, y: 1.3, w: 0.05, h: 0.7, fill: {color: col}}), 'fade', 100, 400);
  A(text(s, t.what, {x: 0.5, y: 1.25, w: 12.15, h: 0.8, fontSize: 13, color: C.mute, valign: 'top', lineSpacingMultiple: 1.0}), 'fade', 150, 500);
  // without (right) and with (middle)
  const pw = 4.05, py = 2.2, ph = 2.45, lh = Math.min(0.62, 1.85 / Math.max(t.without.length, t.with.length));
  const xw = 12.83 - pw, xm = xw - 0.2 - pw;
  A(panel(s, xw, py, pw, ph), 'fade', 300, 500);
  A(text(s, 'دون الأداة', {x: xw + 0.25, y: py + 0.12, w: pw - 0.5, h: 0.36, fontSize: 13, bold: true, color: C.no}), 'fade', 350, 400);
  list(s, t.without, xw + 0.25, py + 0.55, pw - 0.5, lh, C.no, 400, 12);
  A(panel(s, xm, py, pw, ph, {line: {color: col, width: 1.5}}), 'fade', 700, 500);
  A(text(s, 'مع الأداة', {x: xm + 0.25, y: py + 0.12, w: pw - 0.5, h: 0.36, fontSize: 13, bold: true, color: col}), 'fade', 750, 400);
  list(s, t.with, xm + 0.25, py + 0.55, pw - 0.5, lh, col, 800, 12);
  // the difference, in gold, with the figures under it
  const xv = 0.5, wv = xm - 0.2 - xv;
  A(panel(s, xv, py, wv, ph, {fill: {color: C.root}, line: {color: C.gold, width: 1.5}}), 'fade', 1100, 500);
  A(text(s, 'الفارق', {x: xv + 0.25, y: py + 0.12, w: wv - 0.5, h: 0.36, fontSize: 13, bold: true, color: C.gold}), 'fade', 1150, 400);
  A(text(s, t.value, {x: xv + 0.25, y: py + 0.5, w: wv - 0.5, h: 1.85, fontSize: 16.5, bold: true, color: mode === 'night' ? C.ink : C.white, valign: 'top', lineSpacingMultiple: 1.05}), 'fade', 1200, 600);
  // figures
  const fy = 4.95, nf = t.figures.length, fw = (12.33 - 0.3 * (nf - 1)) / Math.max(nf, 3) ;
  t.figures.forEach(([v, l], k) => figure(s, 12.83 - (k + 1) * fw - k * 0.3, fy, fw, v, l, 1400 + k * 150, col));
  // where and the safeguard
  const gy = 5.95;
  A(text(s, [{text: 'أين تعمل: ', options: {bold: true, color: col}}, {text: t.where.join(' · '), options: {color: C.ink}}], {x: 6.75, y: gy, w: 6.08, h: 0.62, fontSize: 11.5, valign: 'top'}), 'fade', 1700, 500);
  A(text(s, [{text: 'الضمانة: ', options: {bold: true, color: C.gold}}, {text: t.guard, options: {color: C.ink}}], {x: 0.5, y: gy, w: 6.05, h: 0.85, fontSize: 11.5, valign: 'top'}), 'fade', 1800, 500);
  A(text(s, t.tech, {x: 6.75, y: 6.62, w: 6.08, h: 0.28, fontSize: 9.5, color: C.mute}), 'fade', 1900, 500);
  // navigation
  button(s, 'الخريطة', 0.5, 0.6, 1.0, P.map, true);
  if (t.i > 0) button(s, 'السابقة', 1.62, 0.6, 0.95, TOOLS[t.i - 1].slide);
  button(s, 'التالية', t.i > 0 ? 2.69 : 1.62, 0.6, 0.95, t.i < TOOLS.length - 1 ? TOOLS[t.i + 1].slide : P.compare);
  counter(s, t.slide);
}

// local against cloud
{
  const s = newSlide(P.compare);
  crumb(s, 'ء-حماية · الذكاء الاصطناعي المحلي'); A(title(s, 'محلي أم سحابي؟'), 'fade', 0, 500);
  A(text(s, 'الأدوات نفسها، في مكانين: الفرق ليس تقنيا فقط، بل في من يملك البيانات والقرار.', {x: 2.9, y: 1.22, w: 9.15, h: 0.36, fontSize: 13.5, color: C.mute}), 'fade', 150, 500);
  const x0 = 0.5, cw = [3.6, 4.4, 4.33], top = 1.85, rh = 0.62;   // right to left: criterion, local, cloud
  const xs = [12.83 - cw[0], 12.83 - cw[0] - cw[1], 12.83 - cw[0] - cw[1] - cw[2]];
  A(shape(s, pres.shapes.ROUNDED_RECTANGLE, {x: xs[1], y: top - 0.08, w: cw[1], h: rh * (COMPARE.length + 1) + 0.16, rectRadius: 0.12, fill: {color: C.panel}, line: {color: C.gold, width: 1.5}}), 'fade', 200, 500);
  [['', C.mute], ['على خوادم الديوان (ء-حماية)', C.gold], ['خدمة سحابية خارجية', C.mute]].forEach(([h, c], k) =>
    A(text(s, h, {x: xs[k] + 0.2, y: top, w: cw[k] - 0.4, h: rh, fontSize: 14, bold: true, color: c, align: k ? 'center' : 'right'}), 'fade', 250, 400));
  COMPARE.forEach((r, j) => {
    const y = top + (j + 1) * rh, dl = 400 + j * 130;
    A(shape(s, pres.shapes.LINE, {x: x0, y, w: 12.33, h: 0, line: {color: C.line, width: 0.75}}), 'fade', dl, 300);
    A(text(s, r[0], {x: xs[0] + 0.2, y, w: cw[0] - 0.4, h: rh, fontSize: 13, bold: true, color: C.ink}), 'fade', dl, 400);
    A(text(s, '✓  ' + r[1], {x: xs[1] + 0.2, y, w: cw[1] - 0.4, h: rh, fontSize: 13, color: C.ink, align: 'center'}), 'fade', dl + 80, 400);
    A(text(s, r[2], {x: xs[2] + 0.2, y, w: cw[2] - 0.4, h: rh, fontSize: 13, color: C.mute, align: 'center'}), 'fade', dl + 120, 400);
  });
  button(s, 'الخريطة', 0.5, 0.6, 1.0, P.map, true);
  foot(s); counter(s, P.compare);
}

// safeguards
{
  const s = newSlide(P.guards);
  crumb(s, 'ء-حماية · الثقة'); A(title(s, 'ست ضمانات على كل أداة'), 'fade', 0, 500);
  A(text(s, 'القاعدة الثابتة AI-01: الذكاء الاصطناعي يقترح ويعلّل، والإنسان يقرّر. وتطبيقها في المنظومة:', {x: 2.9, y: 1.22, w: 9.15, h: 0.36, fontSize: 13.5, color: C.mute}), 'fade', 150, 500);
  GUARDS.forEach(([h, b], k) => {
    const col = k % 2, row = Math.floor(k / 2), w = 6.06, x = 12.83 - (col + 1) * w - col * 0.21, y = 1.85 + row * 1.6, dl = 300 + k * 140;
    A(panel(s, x, y, w, 1.42), 'fade', dl, 500);
    A(shape(s, pres.shapes.OVAL, {x: x + w - 0.95, y: y + 0.36, w: 0.7, h: 0.7, fill: {color: C.root}, line: {color: C.gold, width: 1.5}}), 'zoom', dl + 100, 400);
    A(text(s, ind(k + 1), {x: x + w - 0.95, y: y + 0.36, w: 0.7, h: 0.7, align: 'center', fontSize: 18, fontFace: DISP, color: C.gold}), 'zoom', dl + 100, 400);
    A(text(s, h, {x: x + 0.3, y: y + 0.22, w: w - 1.45, h: 0.45, fontSize: 16, fontFace: DISPM, color: C.ink}), 'fade', dl + 150, 400);
    A(text(s, b, {x: x + 0.3, y: y + 0.72, w: w - 1.45, h: 0.5, fontSize: 12.5, color: C.mute, valign: 'top'}), 'fade', dl + 200, 400);
  });
  button(s, 'الخريطة', 0.5, 0.6, 1.0, P.map, true);
  foot(s); counter(s, P.guards);
}

// hardware profiles
{
  const s = newSlide(P.profiles);
  crumb(s, 'ء-حماية · التجهيز'); A(title(s, 'على أي خادم تعمل؟'), 'fade', 0, 500);
  A(text(s, 'الأدوات نفسها على ثلاثة مقاسات من الخوادم: يتغيّر حجم النموذج، ولا يتغيّر شيء في المنظومة.', {x: 2.9, y: 1.22, w: 9.15, h: 0.36, fontSize: 13.5, color: C.mute}), 'fade', 150, 500);
  PROFILES.forEach(([h, stt, llm, tag], k) => {
    const w = 3.95, x = 12.83 - (k + 1) * w - k * 0.24, y = 1.9, dl = 300 + k * 200;
    A(panel(s, x, y, w, 3.3, k === 0 ? {line: {color: C.gold, width: 1.5}} : {}), 'fade', dl, 500);
    A(text(s, tag, {x: x + 0.3, y: y + 0.25, w: w - 0.6, h: 0.5, fontSize: 22, fontFace: MONO, bold: true, color: C.gold, rtlMode: false, lang: 'en-US', align: 'right'}), 'fade', dl + 100, 400);
    A(text(s, h, {x: x + 0.3, y: y + 0.8, w: w - 0.6, h: 0.45, fontSize: 16, fontFace: DISPM, color: C.ink}), 'fade', dl + 150, 400);
    [['الصوت إلى نص', stt], ['النموذج اللغوي', llm], ['النار والدخان والأشخاص', 'YOLOX-Tiny على المعالج']].forEach(([a, b], j) => {
      A(text(s, a, {x: x + 0.3, y: y + 1.4 + j * 0.6, w: w - 0.6, h: 0.26, fontSize: 10.5, color: C.mute}), 'fade', dl + 200 + j * 80, 400);
      A(text(s, b, {x: x + 0.3, y: y + 1.64 + j * 0.6, w: w - 0.6, h: 0.3, fontSize: 13, bold: true, color: C.ink}), 'fade', dl + 200 + j * 80, 400);
    });
  });
  A(panel(s, 0.5, 5.5, 12.33, 1.3), 'fade', 1000, 500);
  A(text(s, [{text: 'التثبيت مرة واحدة: ', options: {bold: true, color: C.gold}},
    {text: 'سكربت يجلب النماذج ويتحقق من بصمتها ورخصتها، ويرفض أي نموذج رخصته غير متساهلة. بعد ذلك لا يُنزَّل شيء أثناء العمل، ويمكن نقل النماذج إلى خادم دون إنترنت. الترجمة وبصمة المعنى بالنماذج نفسها في المقاسات الثلاثة.', options: {color: C.ink}}],
    {x: 0.8, y: 5.62, w: 11.73, h: 1.06, fontSize: 12.5, valign: 'middle'}), 'fade', 1100, 500);
  button(s, 'الخريطة', 0.5, 0.6, 1.0, P.map, true);
  foot(s); counter(s, P.profiles);
}

// the difference, in one slide
{
  const s = newSlide(P.end);
  crumb(s, 'ء-حماية · الخلاصة'); A(title(s, 'الفارق في ثلاث جمل'), 'fade', 0, 500);
  const lines = [
    ['أسرع', 'الصوت والصورة والنص تُقرأ لحظة وصولها: البلاغ يُفرز، والحريق يُرى، والتكرار يُجمع، قبل أن يفتحها أحد.'],
    ['أدق', 'كل أداة تتعلم من تصحيحات الأعوان وقرارات القادة، بأرقام معلنة في بطاقة نموذجها وأهداف تُقاس.'],
    ['أأمن', 'لا يغادر بلاغ ولا صوت ولا صورة خوادم الديوان، والأدوات تعمل حين ينقطع الإنترنت، والقرار يبقى للإنسان.'],
  ];
  lines.forEach(([h, b], k) => {
    const y = 1.6 + k * 1.55, dl = 300 + k * 300;
    A(shape(s, pres.shapes.LINE, {x: 0.5, y, w: 12.33, h: 0, line: {color: C.gold, width: 1.5}}), 'wipe', dl, 600, 'l');
    A(text(s, h, {x: 10.3, y: y + 0.15, w: 2.53, h: 1.1, fontSize: 40, fontFace: DISP, bold: true, color: C.gold}), 'fade', dl + 150, 500);
    A(text(s, b, {x: 0.5, y: y + 0.2, w: 9.6, h: 1.05, fontSize: 17, bold: true, color: C.ink, valign: 'middle'}), 'fade', dl + 250, 500);
  });
  A(text(s, `${TOOLS.length} أداة · نماذج مفتوحة المصدر برخص MIT و Apache و BSD · تعمل كلها على خوادم الديوان`, {x: 0.5, y: 6.35, w: 12.33, h: 0.32, fontSize: 12, color: C.mute, align: 'center'}), 'fade', 1400, 500);
  button(s, 'الخريطة', 0.5, 0.6, 1.0, P.map, true); button(s, 'الغلاف', 1.62, 0.6, 1.0, P.cover);
  counter(s, P.end);
}
}

// ---------------------------------------------------------------- 4. write, then add the native transitions and animations
const tmp = mkdtempSync(join(tmpdir(), 'ai-pptx-'));
const raw = join(tmp, 'raw.pptx');
await pres.writeFile({fileName: raw});
const zip = await JSZip.loadAsync(readFileSync(raw));

function effect(e, spid, ids) {
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
}
const TRANS = {cover: '<p:fade/>', why: '<p:push dir="l"/>', map: '<p:push dir="l"/>', tool: '<p:fade/>', compare: '<p:push dir="l"/>', guards: '<p:push dir="l"/>', profiles: '<p:push dir="l"/>', end: '<p:fade/>'};
let nAnim = 0;
for (let n = 1; n <= MODES.length * N; n++) {
  const f = `ppt/slides/slide${n}.xml`;
  let xml = await zip.file(f).async('string');
  const ids = {}; for (const m of xml.matchAll(/<p:cNvPr id="(\d+)" name="([^"]+)"/g)) ids[m[2]] = m[1];
  const kind = {}; for (const m of xml.matchAll(/<p:(sp|pic|graphicFrame)>\s*<p:nv\w+Pr>\s*<p:cNvPr id="(\d+)"/g)) kind[m[2]] = m[1];
  const list = (anim[n] || []).filter(e => ids[e.name]).sort((a, b) => a.delay - b.delay);
  const trans = `<p:transition spd="med">${TRANS[plan[(n - 1) % N].t]}</p:transition>`;
  let timing = '';
  if (list.length) {
    const c = {n: 4};
    const effects = list.map(e => effect(e, ids[e.name], c)).join('');
    const spids = [...new Set(list.map(e => ids[e.name]))];
    timing = `<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst><p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst><p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst><p:par><p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>${effects}</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst><p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst><p:bldLst>${spids.map(i => kind[i] === 'graphicFrame' ? `<p:bldGraphic spid="${i}" grpId="0"><p:bldAsOne/></p:bldGraphic>` : kind[i] === 'pic' ? '' : `<p:bldP spid="${i}" grpId="0" animBg="1"/>`).join('')}</p:bldLst></p:timing>`;
    timing = timing.replace('nodeType="withEffect"', 'nodeType="afterEffect"');
    nAnim += list.length;
  }
  xml = xml.replace(/<p:transition[\s\S]*?<\/p:transition>|<p:transition[^>]*\/>/g, '').replace(/<p:timing>[\s\S]*?<\/p:timing>/g, '');
  xml = xml.replace(/(<\/p:clrMapOvr>)/, `$1${trans}${timing}`);
  if (shapeLinks[n]) {
    const rf = `ppt/slides/_rels/slide${n}.xml.rels`;
    let rels = await zip.file(rf).async('string');
    let next = Math.max(0, ...[...rels.matchAll(/Id="rId(\d+)"/g)].map(m => +m[1])) + 1;
    const parts = xml.split(/(?=<p:cNvPr id="\d+" name=")/);
    xml = parts.map(part => {
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
{
  const f = Object.keys(zip.files).find(f => /^ppt\/theme\/theme\d+\.xml$/.test(f));
  let x = await zip.file(f).async('string');
  const T = {dk1: '08102A', lt1: 'FFFFFF', dk2: '0E1426', lt2: 'E8ECF5', accent1: 'C9A24A', accent2: '4DD0B8', accent3: '8FA8FF',
    accent4: 'FFC933', accent5: 'C49BE6', accent6: 'FF6B6B', hlink: 'C9A24A', folHlink: 'A6AFC4'};
  for (const [k, v] of Object.entries(T)) x = x.replace(new RegExp(`<a:${k}>[\\s\\S]*?</a:${k}>`), `<a:${k}><a:srgbClr val="${v}"/></a:${k}>`);
  x = x.replace(/<a:clrScheme name="[^"]*"/, '<a:clrScheme name="E-HIMAYA الليلي"');
  zip.file(f, x);
}
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
{
  const src = join(ROOT, 'apps/mobile/assets/fonts'), dst = join(dirname(out), 'fonts');
  mkdirSync(dst, {recursive: true});
  for (const f of readdirSync(src).filter(f => /^IBMPlexSansArabic-.*\.ttf$|^OFL\.txt$/.test(f))) copyFileSync(join(src, f), join(dst, f));
  for (const f of readdirSync(join(HERE, 'assets/fonts'))) copyFileSync(join(HERE, 'assets/fonts', f), join(dst, f));
}
console.log(`${MODES.length * N} slides (${MODES.join(' and ')}), ${nAnim} animations → ${out}`);
