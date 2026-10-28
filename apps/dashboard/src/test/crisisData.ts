import type {
  Axis,
  AxisDetail,
  CommandOverview,
  DeclarationRequest,
  Directive,
  Figures,
  Sitrep,
} from "../lib/crisis";

/**
 * A simulated flood axis in Nabeul ([SIM], phase L3), a forest fire in Jendouba and a storm watch in Sousse: the data
 * of the unit tests, the accessibility check and the screenshots of the command screens. Not real events. No test
 * runner import here, so Playwright loads it too.
 */
const H = (hoursAgo: number) => new Date(Date.UTC(2026, 9, 28, 9, 0) - hoursAgo * 3_600_000).toISOString();

export const NABEUL_AREA = {
  type: "Polygon" as const,
  coordinates: [
    [
      [10.62, 36.38],
      [10.78, 36.36],
      [10.86, 36.45],
      [10.84, 36.56],
      [10.7, 36.6],
      [10.6, 36.52],
      [10.62, 36.38],
    ],
  ],
};

/** First and second items of a fixture list (they always exist). */
export function first<T>(items: readonly T[]): T {
  return items[0] as T;
}

function second<T>(items: readonly T[]): T {
  return items[1] as T;
}

function figures(over: Partial<Figures>): Figures {
  return {
    incidents: 0,
    incidents_open: 0,
    deceased: 0,
    injured: 0,
    injured_serious: 0,
    rescued: 0,
    trapped: 0,
    evacuated: 0,
    shelters: 0,
    shelter_capacity: 0,
    sheltered: 0,
    resources: 0,
    resources_by_kind: {},
    volunteers: 0,
    needs_open: 0,
    decisions: 0,
    decisions_done: 0,
    decisions_failed: 0,
    done_share: null,
    mean_hours_to_done: null,
    ...over,
  };
}

const base = {
  scope: "gouvernorat" as const,
  parent_id: null,
  plan: "",
  status: "open" as const,
  opened_by_name: "العقيد ك. ب.",
  closed_by_name: null,
  closed_at: null,
  closing: null,
  memory_id: null,
  version: 3,
  children: [],
  can_manage: true,
  can_command: true,
  can_issue: false,
};

export const NABEUL_FIGURES = figures({
  incidents: 14,
  incidents_open: 9,
  deceased: 2,
  injured: 17,
  injured_serious: 4,
  rescued: 63,
  trapped: 3,
  evacuated: 412,
  shelters: 3,
  shelter_capacity: 650,
  sheltered: 318,
  resources: 27,
  resources_by_kind: { rescue_vehicle: 7, ambulance: 6, boat: 4, heavy_equipment: 3, water_tanker: 2, drone: 2, fire_engine: 3 },
  volunteers: 21,
  needs_open: 2,
  decisions: 3,
  decisions_done: 1,
  decisions_failed: 0,
  done_share: 0.333,
  mean_hours_to_done: 2.4,
});

export const NABEUL_AXIS: Axis = {
  ...base,
  id: "ax-nabeul",
  number: "AX-2026-014",
  name: "[SIM] فيضانات نابل، أكتوبر 2026",
  kind: "flood",
  gouvernorat_code: 21,
  gouvernorat_name: "نابل",
  gouvernorats: [21],
  area: NABEUL_AREA,
  level: 3,
  plan: "[SIM] المخطط الجهوي للنجدة مفعّل بقرار والي نابل عدد 27 لسنة 2026.",
  opened_at: H(19),
  next_sitrep_at: new Date(Date.UTC(2026, 9, 28, 11, 0)).toISOString(),
  figures: NABEUL_FIGURES,
};

export const JENDOUBA_AXIS: Axis = {
  ...base,
  id: "ax-jendouba",
  number: "AX-2026-013",
  name: "[SIM] حرائق غابات عين دراهم",
  kind: "forest_fire",
  gouvernorat_code: 32,
  gouvernorat_name: "جندوبة",
  gouvernorats: [32],
  area: {
    type: "Polygon",
    coordinates: [
      [
        [8.62, 36.72],
        [8.8, 36.72],
        [8.8, 36.84],
        [8.62, 36.84],
        [8.62, 36.72],
      ],
    ],
  },
  level: 2,
  opened_at: H(31),
  next_sitrep_at: new Date(Date.UTC(2026, 9, 28, 14, 0)).toISOString(),
  figures: figures({
    incidents: 5,
    incidents_open: 3,
    injured: 2,
    rescued: 6,
    evacuated: 45,
    shelters: 1,
    shelter_capacity: 120,
    sheltered: 38,
    resources: 11,
    resources_by_kind: { fire_engine: 6, water_tanker: 3, drone: 1, heavy_equipment: 1 },
    volunteers: 9,
    needs_open: 1,
    decisions: 1,
    decisions_done: 1,
    done_share: 1,
    mean_hours_to_done: 3.1,
  }),
};

export const SOUSSE_AXIS: Axis = {
  ...base,
  id: "ax-sousse",
  number: "AX-2026-015",
  name: "[SIM] اضطرابات جوية بالساحل",
  kind: "storm",
  gouvernorat_code: 51,
  gouvernorat_name: "سوسة",
  gouvernorats: [51],
  area: null,
  level: 1,
  opened_at: H(4),
  next_sitrep_at: new Date(Date.UTC(2026, 9, 29, 5, 0)).toISOString(),
  figures: figures({ incidents: 2, incidents_open: 2, resources: 3, resources_by_kind: { rescue_vehicle: 2, boat: 1 } }),
};

const point = (lat: number, lon: number) => ({ lat, lon });
const INCIDENTS: [string, number, number, number, string, number, number, number][] = [
  ["flood", 5, 36.456, 10.735, "حي الوفاء، مياه داخل المنازل", 1, 4, 5],
  ["drowning", 5, 36.402, 10.66, "وادي سوحيل، سيارة جرفتها المياه", 1, 2, 3],
  ["flood", 4, 36.47, 10.71, "طريق الحمامات، محاصرون فوق الأسطح", 0, 3, 4],
  ["flood", 4, 36.52, 10.79, "قربة، فيضان واد", 0, 1, 2],
  ["landslide", 3, 36.55, 10.7, "بني خيار، انهيار جدار", 0, 2, 2],
  ["flood", 3, 36.43, 10.69, "المعمورة، تسرب مياه", 0, 0, 2],
  ["sos", 4, 36.49, 10.76, "استغاثة: عائلة محاصرة", 0, 1, 3],
  ["medical", 3, 36.44, 10.75, "نقل مريض غسيل كلى", 0, 1, 1],
  ["flood", 2, 36.41, 10.63, "بوعرقوب، طريق مقطوعة", 0, 0, 1],
];

export const NABEUL_DETAIL: AxisDetail = {
  axis: NABEUL_AXIS,
  incidents: INCIDENTS.map(([category, severity, lat, lon, title, d, i, r], n) => ({
    id: `inc-${n}`,
    axis_id: NABEUL_AXIS.id,
    category,
    severity,
    status: n < 7 ? "open" : "closed",
    gouvernorat_code: 21,
    ...point(lat, lon),
    opened_at: H(18 - n),
    title: `[SIM] ${title}`,
    deceased: d,
    injured: i,
    rescued: 0,
    resources: r,
    attached_by_name: "رئيس القاعة الجهوية",
    attached_at: H(17 - n),
  })),
  shelters: [
    { id: "sh-1", axis_id: NABEUL_AXIS.id, name: "[SIM] المعهد النموذجي بنابل", ...point(36.452, 10.72), capacity: 300, occupants: 214, updated_at: H(1) },
    { id: "sh-2", axis_id: NABEUL_AXIS.id, name: "[SIM] دار الشباب قربة", ...point(36.57, 10.86), capacity: 150, occupants: 62, updated_at: H(2) },
    { id: "sh-3", axis_id: NABEUL_AXIS.id, name: "[SIM] القاعة الرياضية دار شعبان", ...point(36.47, 10.75), capacity: 200, occupants: 42, updated_at: H(3) },
  ],
  evacuations: [
    {
      id: "ev-1",
      axis_id: NABEUL_AXIS.id,
      name: "[SIM] حي الوفاء",
      area: {
        type: "Polygon",
        coordinates: [
          [
            [10.725, 36.448],
            [10.745, 36.448],
            [10.745, 36.464],
            [10.725, 36.464],
            [10.725, 36.448],
          ],
        ],
      },
      evacuated: 286,
      updated_at: H(2),
    },
    { id: "ev-2", axis_id: NABEUL_AXIS.id, name: "[SIM] ضفاف وادي سوحيل", area: null, evacuated: 126, updated_at: H(5) },
  ],
  needs: [
    { id: "nd-1", axis_id: NABEUL_AXIS.id, label: "مضخات شفط كبيرة", quantity: 3, status: "raised", created_by_name: "رئيس القاعة الجهوية", created_at: H(6), met_at: null },
    { id: "nd-2", axis_id: NABEUL_AXIS.id, label: "زوارق مطاطية", quantity: 2, status: "raised", created_by_name: "رئيس القاعة الجهوية", created_at: H(4), met_at: null },
    { id: "nd-3", axis_id: NABEUL_AXIS.id, label: "أغطية وأفرشة", quantity: 400, status: "met", created_by_name: "رئيس القاعة الجهوية", created_at: H(10), met_at: H(7) },
  ],
  directives: [],
  sitreps: [],
  timeline: [],
};

function directive(over: Partial<Directive> & Pick<Directive, "id" | "number" | "kind" | "category" | "body">): Directive {
  return {
    axis_id: NABEUL_AXIS.id,
    axis_number: NABEUL_AXIS.number,
    area: null,
    executor: "regional",
    executor_name: null,
    due_at: null,
    status: "issued",
    status_reason: null,
    issuer_role: "governor",
    issued_by_name: "والي نابل",
    issued_at: H(10),
    signature: "c2lnbmF0dXJl",
    key_id: "7f3a9c21b04d8e55",
    overridden_by: null,
    overdue: false,
    done_at: null,
    events: [],
    can_update: false,
    ...over,
  };
}

export const DIRECTIVES: Directive[] = [
  directive({
    id: "dr-4",
    number: 4,
    kind: "decision",
    category: "evacuation",
    body: "[SIM] إخلاء كل الأحياء المنخفضة على ضفتي وادي سوحيل قبل منتصف النهار، وتوجيه السكان إلى مراكز الإيواء الثلاثة.",
    issuer_role: "minister",
    issued_by_name: "وزير الداخلية",
    issued_at: H(3),
    due_at: new Date(Date.UTC(2026, 9, 28, 12, 0)).toISOString(),
    status: "in_progress",
    area: NABEUL_DETAIL.evacuations[0]?.area ?? null,
    events: [
      { status: "issued", reason: null, by_name: "وزير الداخلية", at: H(3) },
      { status: "received", reason: null, by_name: "القاعة الجهوية بنابل", at: H(2.8) },
      { status: "in_progress", reason: null, by_name: "القاعة الجهوية بنابل", at: H(2.5) },
    ],
  }),
  directive({
    id: "dr-3",
    number: 3,
    kind: "decision",
    category: "evacuation",
    body: "[SIM] إخلاء حي الوفاء وحده.",
    issued_at: H(6),
    overridden_by: "dr-4",
  }),
  directive({
    id: "dr-2",
    number: 2,
    kind: "decision",
    category: "closure",
    body: "[SIM] غلق الطريق الجهوية 27 بين نابل والحمامات إلى إشعار آخر.",
    issued_at: H(12),
    status: "done",
    done_at: H(10.6),
    executor: "partner",
    executor_name: "الحرس الوطني",
  }),
  directive({
    id: "dr-1",
    number: 1,
    kind: "recommendation",
    category: "public_information",
    body: "[SIM] بث تنبيه للمواطنين بعدم الاقتراب من مجاري الأودية وتعليق الدروس غدا.",
    issued_at: H(16),
    status: "received",
    executor: "central",
  }),
];

export const SITREPS: Sitrep[] = [
  {
    id: "sr-3",
    axis_id: NABEUL_AXIS.id,
    number: 3,
    figures: { incidents: 14, deceased: 2, evacuated: 412, sheltered: 318, level: 3 },
    assessment: "[SIM] منسوب الأودية في انخفاض بطيء؛ نقص في المضخات بقربة؛ الإخلاء جارٍ على ضفاف سوحيل.",
    status: "sent",
    created_at: H(1.5),
    sent_by_name: "رئيس القاعة الجهوية",
    sent_at: H(1),
  },
  {
    id: "sr-2",
    axis_id: NABEUL_AXIS.id,
    number: 2,
    figures: { incidents: 11, deceased: 2, evacuated: 250, sheltered: 190, level: 3 },
    assessment: "[SIM] أمطار متواصلة؛ تسجيل وفاتين؛ فتح مركز إيواء ثالث.",
    status: "sent",
    created_at: H(7.5),
    sent_by_name: "رئيس القاعة الجهوية",
    sent_at: H(7),
  },
];

NABEUL_DETAIL.directives = DIRECTIVES;
// Phase L3b: the plan of the axis is a document of the register, and the decisions recorded there are listed.
NABEUL_AXIS.plan_document = {
  id: "reg-plan",
  number: "REG-2026-0027",
  reference: "قرار والي نابل عدد 27 لسنة 2026",
  title: "[SIM] المخطط الجهوي للنجدة عند الفيضانات بولاية نابل",
  kind: "plan",
  status: "in_force",
};
NABEUL_DETAIL.documents = [
  NABEUL_AXIS.plan_document,
  { id: "reg-axis", number: "REG-2026-0051", reference: "AX-2026-007 · 2", title: "[SIM] فيضانات نابل، أكتوبر 2026 (AX-2026-007) · 2", kind: "decision", status: "in_force" },
];
NABEUL_DETAIL.sitreps = SITREPS;
NABEUL_DETAIL.timeline = [
  { at: H(0.5), actor_name: "القاعة الجهوية بنابل", kind: "shelter_updated", payload: {} },
  { at: H(1), actor_name: "رئيس القاعة الجهوية", kind: "sitrep_sent", payload: {} },
  { at: H(2.5), actor_name: "القاعة الجهوية بنابل", kind: "directive_in_progress", payload: {} },
  { at: H(3), actor_name: "وزير الداخلية", kind: "directive_issued", payload: {} },
  { at: H(4), actor_name: "رئيس القاعة الجهوية", kind: "need_raised", payload: {} },
  { at: H(6), actor_name: "والي نابل", kind: "directive_issued", payload: {} },
  { at: H(12), actor_name: "رئيس القاعة الجهوية", kind: "evacuation_ordered", payload: {} },
  { at: H(17), actor_name: "رئيس القاعة الجهوية", kind: "incident_attached", payload: {} },
  { at: H(19), actor_name: "رئيس القاعة المركزية", kind: "opened", payload: {} },
];

export const SUGGESTIONS = [
  { ...first(NABEUL_DETAIL.incidents), id: "sg-1", axis_id: null, title: "[SIM] نزل بالحمامات، مياه في الطابق الأرضي", severity: 3, attached_by_name: null, attached_at: null },
  { ...second(NABEUL_DETAIL.incidents), id: "sg-2", axis_id: null, title: "[SIM] منزل آيل للسقوط، بني خيار", category: "landslide", severity: 4, attached_by_name: null, attached_at: null },
];

export const REQUEST: DeclarationRequest = {
  id: "rq-1",
  gouvernorat_code: 51,
  gouvernorat_name: "سوسة",
  name: "[SIM] فيضانات سوسة المدينة",
  kind: "flood",
  level: 2,
  facts: "[SIM] أمطار طوفانية منذ الفجر، 6 تدخلات مفتوحة، ارتفاع منسوب وادي الحمدون.",
  incident_ids: ["a", "b", "c"],
  area: null,
  status: "pending",
  created_by_name: "رئيس القاعة الجهوية بسوسة",
  created_at: H(0.7),
  decided_by_name: null,
  decided_at: null,
  decision_reason: null,
  axis_id: null,
};

export function overview(role: "governor" | "minister"): CommandOverview {
  const axes = role === "minister" ? [NABEUL_AXIS, JENDOUBA_AXIS, SOUSSE_AXIS] : [NABEUL_AXIS];
  const issuer = role === "minister" ? { can_issue: true } : { can_issue: true };
  const totals = role === "minister"
    ? figures({
        incidents: 21, incidents_open: 14, deceased: 2, injured: 19, rescued: 69, evacuated: 457, shelters: 4,
        shelter_capacity: 770, sheltered: 356, resources: 41,
        resources_by_kind: { rescue_vehicle: 9, fire_engine: 9, ambulance: 6, boat: 5, water_tanker: 5, heavy_equipment: 4, drone: 3 },
        volunteers: 30, needs_open: 3, decisions: 4, decisions_done: 2, done_share: 0.5, mean_hours_to_done: 2.8,
      })
    : NABEUL_FIGURES;
  return {
    role,
    gouvernorat_code: role === "minister" ? null : 21,
    totals,
    axes: axes.map((a) => ({ ...a, ...issuer, can_manage: false, can_command: false })),
    gouvernorats:
      role === "minister"
        ? [
            { code: 21, name: "نابل", level: 3, axes: 1, incidents_open: 9, resources: 27, weight: 0.33, deceased: 2, evacuated: 412, needs_open: 2 },
            { code: 32, name: "جندوبة", level: 2, axes: 1, incidents_open: 3, resources: 11, weight: 0.27, deceased: 0, evacuated: 45, needs_open: 1 },
            { code: 51, name: "سوسة", level: 1, axes: 1, incidents_open: 2, resources: 3, weight: 0.67, deceased: 0, evacuated: 0, needs_open: 0 },
          ]
        : [{ code: 21, name: "نابل", level: 3, axes: 1, incidents_open: 9, resources: 27, weight: 0.33, deceased: 2, evacuated: 412, needs_open: 2 }],
    needs: [
      ...NABEUL_DETAIL.needs.filter((n) => n.status === "raised"),
      ...(role === "minister"
        ? [{ id: "nd-j", axis_id: JENDOUBA_AXIS.id, label: "طائرة إطفاء (دعم من الجيش)", quantity: 1, status: "raised" as const, created_by_name: null, created_at: H(5), met_at: null }]
        : []),
    ],
    directives: role === "minister" ? DIRECTIVES.filter((d) => d.issuer_role === "minister") : DIRECTIVES.filter((d) => d.issuer_role === "governor"),
    sitreps: SITREPS,
    closed: [
      {
        ...base,
        id: "ax-old",
        number: "AX-2026-009",
        name: "[SIM] حرائق غابات برقو",
        kind: "forest_fire",
        gouvernorat_code: 34,
        gouvernorat_name: "سليانة",
        gouvernorats: [34],
        area: null,
        level: 2,
        status: "closed",
        opened_at: "2026-08-11T10:00:00Z",
        closed_at: "2026-08-14T18:00:00Z",
        closing: { ...figures({ incidents: 7, evacuated: 30, sheltered: 22 }), hours: 80 },
        next_sitrep_at: null,
        figures: figures({ incidents: 7 }),
      },
    ],
  };
}
