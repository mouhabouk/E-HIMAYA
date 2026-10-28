import type { Dispatch, DispatchDetail, DispatchPage, DocumentDetail, RegisterDocument, RegisterSearch, Revision } from "../lib/register";

/**
 * Simulated documents of the register and messages between the centre and the gouvernorats ([SIM], phase L3b): the data
 * of the unit tests, the accessibility check and the screenshots. Not real texts. No test runner import here, so
 * Playwright loads it too.
 */
const D = (daysAgo: number) => new Date(Date.UTC(2026, 9, 28, 9, 0) - daysAgo * 86_400_000).toISOString();
const day = (daysAgo: number) => D(daysAgo).slice(0, 10);

function doc(over: Partial<RegisterDocument> & Pick<RegisterDocument, "id" | "number" | "title">): RegisterDocument {
  return {
    reference: "",
    kind: "plan",
    level: "regional",
    gouvernorat_code: 21,
    gouvernorat_name: "نابل",
    issuer: "والي نابل",
    signatory: "",
    summary: "",
    topics: [],
    issued_on: day(200),
    effective_from: null,
    effective_to: null,
    status: "in_force",
    repeal_reason: null,
    repealed_by: null,
    access: "all",
    source: "manual",
    signed: false,
    file_name: null,
    file_type: null,
    file_size: null,
    file_sha256: null,
    recommendations_open: 0,
    recommendations: 0,
    updated_by_name: "[SIM] القاعة الجهوية بنابل",
    updated_at: D(10),
    version: 1,
    excerpt: null,
    can_edit: true,
    ...over,
  };
}

export const PLAN = doc({
  id: "reg-plan",
  number: "REG-2026-0027",
  reference: "قرار والي نابل عدد 27 لسنة 2026",
  title: "[SIM] المخطط الجهوي للنجدة عند الفيضانات بولاية نابل",
  summary:
    "يضبط المخطط مراحل اليقظة والإنذار والتدخل عند الفيضانات، ومهام اللجنة الجهوية لتلافي الكوارث، ونقاط التجمع ومراكز الإيواء الاثني عشر، وتوزيع وسائل الضخ بين المعتمديات.",
  topics: ["floods", "civil_protection"],
  issued_on: day(230),
  effective_from: day(225),
  file_name: "مخطط-النجدة-نابل-2026.pdf",
  file_type: "application/pdf",
  file_size: 2_457_600,
  file_sha256: "9f2c4e1ab3d8c7f6e5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2",
  recommendations_open: 2,
  recommendations: 3,
});

export const CIRCULAR = doc({
  id: "reg-circ",
  number: "REG-2026-0031",
  reference: "منشور وزير الداخلية عدد 12 لسنة 2026",
  kind: "circular",
  level: "central",
  gouvernorat_code: null,
  gouvernorat_name: null,
  issuer: "وزير الداخلية",
  title: "[SIM] منشور حول الاستعداد لموسم الأمطار 2026-2027",
  summary: "تحيين مخططات النجدة الجهوية وجرد وسائل الضخ وتنظيف مجاري الأودية قبل 15 نوفمبر.",
  topics: ["floods", "storms"],
  issued_on: day(40),
  effective_from: day(40),
  effective_to: day(-150),
  recommendations_open: 1,
  recommendations: 2,
  can_edit: false,
});

export const TEMPORARY = doc({
  id: "reg-temp",
  number: "REG-2026-0044",
  reference: "تعليمة المدير الجهوي عدد 9",
  kind: "temporary_instruction",
  issuer: "المدير الجهوي للحماية المدنية بنابل",
  title: "[SIM] منع السباحة بالشواطئ غير المحروسة أثناء الاضطرابات الجوية",
  topics: ["beaches"],
  issued_on: day(120),
  effective_from: day(120),
  effective_to: day(60),
  status: "expired",
});

export const AXIS_DECISION = doc({
  id: "reg-axis",
  number: "REG-2026-0051",
  reference: "AX-2026-007 · 2",
  kind: "decision",
  level: "central",
  gouvernorat_code: null,
  gouvernorat_name: null,
  issuer: "وزير الداخلية",
  signatory: "[SIM] وزير الداخلية",
  title: "[SIM] فيضانات نابل، أكتوبر 2026 (AX-2026-007) · 2",
  summary: "إخلاء الأحياء المنخفضة بمنزل تميم. [SIM]",
  topics: ["floods", "civil_protection"],
  issued_on: day(0),
  effective_from: day(0),
  access: "command",
  source: "axis",
  signed: true,
  can_edit: false,
});

export const OLD_PLAN = doc({
  id: "reg-old",
  number: "REG-2024-0011",
  reference: "قرار والي نابل عدد 14 لسنة 2024",
  title: "[SIM] المخطط الجهوي للنجدة عند الفيضانات (نسخة 2024)",
  issued_on: day(900),
  status: "repealed",
  repeal_reason: "REG-2026-0027 قرار والي نابل عدد 27 لسنة 2026",
  repealed_by: "reg-plan",
  can_edit: false,
});

export const DOCUMENTS = [AXIS_DECISION, CIRCULAR, PLAN, TEMPORARY];

export const SEARCH: RegisterSearch = {
  items: DOCUMENTS,
  total: DOCUMENTS.length,
  facets: {
    kind: [
      { key: "plan", count: 1 },
      { key: "circular", count: 1 },
      { key: "decision", count: 1 },
      { key: "temporary_instruction", count: 1 },
    ],
    level: [
      { key: "central", count: 2 },
      { key: "regional", count: 2 },
    ],
    status: [
      { key: "in_force", count: 3 },
      { key: "expired", count: 1 },
      { key: "repealed", count: 1 },
    ],
  },
  can_create: true,
  can_create_central: false,
};

export const PLAN_DETAIL: DocumentDetail = {
  document: PLAN,
  body: "الفصل 1: تُفعَّل مرحلة الإنذار عند نشرة إنذار برتقالية من المعهد الوطني للرصد الجوي.\nالفصل 2: تُفتح مراكز الإيواء بقرار من الوالي.",
  axes: [{ id: "ax-nabeul", number: "AX-2026-007", name: "[SIM] فيضانات نابل، أكتوبر 2026", status: "open" }],
  links: [
    { id: "reg-old", number: "REG-2024-0011", title: OLD_PLAN.title, kind: "plan", status: "repealed", relation: "repeals", direction: "out" },
    { id: "reg-circ", number: "REG-2026-0031", title: CIRCULAR.title, kind: "circular", status: "in_force", relation: "complements", direction: "in" },
  ],
  recommendations: [
    {
      id: "rec-1",
      number: 1,
      body: "تنظيف مجاري وادي الشيوخ بمنزل تميم قبل موسم الأمطار.",
      responsible: "بلدية منزل تميم",
      due_on: day(5),
      status: "in_progress",
      status_reason: null,
      updated_by_name: "[SIM] القاعة الجهوية بنابل",
      updated_at: D(20),
      overdue: true,
    },
    {
      id: "rec-2",
      number: 2,
      body: "تجهيز مراكز الإيواء الاثني عشر بالأغطية والمولدات.",
      responsible: "المندوبية الجهوية للشؤون الاجتماعية",
      due_on: day(-20),
      status: "proposed",
      status_reason: null,
      updated_by_name: "[SIM] القاعة الجهوية بنابل",
      updated_at: D(20),
      overdue: false,
    },
    {
      id: "rec-3",
      number: 3,
      body: "تمرين محاكاة جهوي للإخلاء.",
      responsible: "اللجنة الجهوية لتلافي الكوارث",
      due_on: day(60),
      status: "done",
      status_reason: null,
      updated_by_name: "[SIM] القاعة الجهوية بنابل",
      updated_at: D(50),
      overdue: false,
    },
  ],
  created_by_name: "[SIM] القاعة الجهوية بنابل",
  created_at: D(230),
};

export const REVISIONS: Revision[] = [
  { version: 3, change: "file", reason: null, created_by_name: "[SIM] القاعة الجهوية بنابل", created_at: D(220), snapshot: {} },
  { version: 2, change: "updated", reason: "إدراج مراكز إيواء جديدة", created_by_name: "[SIM] القاعة الجهوية بنابل", created_at: D(224), snapshot: {} },
  { version: 1, change: "created", reason: null, created_by_name: "[SIM] القاعة الجهوية بنابل", created_at: D(230), snapshot: {} },
];

// --- Directives and notices ---

const H = (hoursAgo: number) => new Date(Date.UTC(2026, 9, 28, 9, 0) - hoursAgo * 3_600_000).toISOString();

function dispatch(over: Partial<Dispatch> & Pick<Dispatch, "id" | "number" | "subject">): Dispatch {
  return {
    kind: "directive",
    audience: "all",
    origin_gouvernorat: null,
    origin_name: null,
    urgency: "normal",
    body: "",
    topics: [],
    incident_id: null,
    axis_id: null,
    reply_required: true,
    reply_due_at: null,
    status: "open",
    closed_at: null,
    created_by_name: "[SIM] القاعة المركزية للعمليات",
    created_at: H(5),
    targets: 24,
    seen: 0,
    replied: 0,
    unread: false,
    overdue: false,
    attachments: 0,
    excerpt: null,
    ...over,
  };
}

export const DIRECTIVE_ALL = dispatch({
  id: "dsp-all",
  number: "DIR-2026-0042",
  subject: "[SIM] جرد وسائل الضخ والمولدات بكل الولايات",
  body: "يُرجى موافاتنا بجدول وسائل الضخ والمولدات الجاهزة حسب المعتمديات، وفق النموذج المرفق، قبل الساعة 18:00.",
  urgency: "urgent",
  reply_due_at: H(-9),
  seen: 19,
  replied: 14,
  attachments: 1,
});

export const DIRECTIVE_NABEUL = dispatch({
  id: "dsp-nab",
  number: "DIR-2026-0043",
  subject: "[SIM] متابعة منسوب سد المصري وسد الشيوخ",
  audience: "targeted",
  urgency: "flash",
  body: "تحيين منسوب السدين كل ساعتين وإعلام القاعة المركزية فورا عند تجاوز 90%.",
  created_at: H(3),
  targets: 1,
  seen: 1,
  replied: 1,
});

export const NOTICE = dispatch({
  id: "dsp-not",
  number: "NOT-2026-0019",
  kind: "notice",
  audience: "centre",
  origin_gouvernorat: 21,
  origin_name: "نابل",
  urgency: "flash",
  subject: "[SIM] انهيار جزئي لجسر وادي الشيوخ على الطريق 27",
  body: "الطريق مقطوعة في الاتجاهين، ولا إصابات. نطلب وحدة هندسة.",
  created_by_name: "[SIM] القاعة الجهوية بنابل",
  created_at: H(1),
  targets: 1,
  unread: true,
});

export const DISPATCH_PAGE: DispatchPage = {
  items: [NOTICE, DIRECTIVE_NABEUL, DIRECTIVE_ALL],
  total: 3,
  unread: 1,
  can_direct: true,
  can_notify: false,
};

const NAMES: Record<number, string> = { 11: "تونس", 21: "نابل", 22: "زغوان", 23: "بنزرت", 32: "جندوبة", 51: "سوسة", 52: "المنستير", 53: "المهدية" };

export const DIRECTIVE_ALL_DETAIL: DispatchDetail = {
  dispatch: DIRECTIVE_ALL,
  attachments: [
    { id: "att-1", file_name: "نموذج-جرد-وسائل-الضخ.xlsx", content_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", size: 48_200, sha256: "ab", created_at: H(5) },
  ],
  targets: Object.entries(NAMES).map(([code, name], n) => ({
    gouvernorat_code: Number(code),
    gouvernorat_name: name,
    seen_at: n < 7 ? H(4.5 - n * 0.3) : null,
    seen_by_name: n < 7 ? "[SIM] رئيس القاعة" : null,
    replied_at: n < 5 ? H(3 - n * 0.4) : null,
    replies: n < 5 ? 1 : 0,
    overdue: false,
  })),
  threads: [
    {
      gouvernorat_code: 21,
      gouvernorat_name: "نابل",
      replies: [
        {
          id: "rp-1",
          gouvernorat_code: 21,
          side: "regional",
          body: "مرفق جدول الجرد: 12 مضخة جاهزة و3 في الصيانة، و8 مولدات. [SIM]",
          created_by_name: "[SIM] رئيس القاعة الجهوية بنابل",
          created_at: H(3),
          attachments: [
            { id: "att-2", file_name: "جرد-نابل.xlsx", content_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", size: 51_300, sha256: "cd", created_at: H(3) },
          ],
          mine: false,
        },
        {
          id: "rp-2",
          gouvernorat_code: 21,
          side: "centre",
          body: "تُوجَّه 4 مضخات إضافية من مستودع بن عروس. [SIM]",
          created_by_name: "[SIM] القاعة المركزية للعمليات",
          created_at: H(2),
          attachments: [],
          mine: true,
        },
      ],
    },
    {
      gouvernorat_code: 51,
      gouvernorat_name: "سوسة",
      replies: [
        {
          id: "rp-3",
          gouvernorat_code: 51,
          side: "regional",
          body: "التقرير المفصل مرفق. [SIM]",
          created_by_name: "[SIM] رئيس القاعة الجهوية بسوسة",
          created_at: H(2.5),
          attachments: [
            { id: "att-3", file_name: "تقرير-سوسة.pdf", content_type: "application/pdf", size: 312_000, sha256: "ef", created_at: H(2.5) },
          ],
          mine: false,
        },
      ],
    },
  ],
  can_reply: true,
  can_close: true,
  can_attach: true,
  viewer_side: "centre",
};

/** The same directive as the room of Nabeul sees it: its own row and its own thread. */
export const DIRECTIVE_ALL_NABEUL: DispatchDetail = {
  ...DIRECTIVE_ALL_DETAIL,
  dispatch: { ...DIRECTIVE_ALL, targets: 1, seen: 1, replied: 1 },
  targets: DIRECTIVE_ALL_DETAIL.targets.filter((t) => t.gouvernorat_code === 21),
  threads: DIRECTIVE_ALL_DETAIL.threads.filter((t) => t.gouvernorat_code === 21),
  can_close: false,
  can_attach: false,
  viewer_side: "regional",
};
