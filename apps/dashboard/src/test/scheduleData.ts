import type { PeriodDetail, PeriodSlot, Progress, ScheduleItem, ScheduleOptions, ScheduleSetting, ScheduleTemplate } from "../lib/schedule";

/**
 * A simulated weekly programme of Nabeul ([SIM], phase PL2): the data of the unit tests, the accessibility check and
 * the screenshots. Not a real programme. No test runner import here, so Playwright loads it too.
 */
export const WEEK_START = "2026-10-26";

const item = (over: Partial<ScheduleItem> & Pick<ScheduleItem, "id" | "activity" | "title" | "on_date">): ScheduleItem => ({
  series_id: null,
  starts_at: "08:00:00",
  ends_at: "16:00:00",
  unit_id: "u-nabeul",
  unit_name: "الوحدة الجهوية بنابل",
  place: "",
  responsible: "رئيس الوحدة",
  staff_count: 6,
  resources: [],
  plan_document_id: null,
  plan_title: null,
  notes: "",
  status: "planned",
  status_reason: null,
  status_by_name: null,
  status_at: null,
  ...over,
});

const day = (n: number) => new Date(Date.UTC(2026, 9, 26 + n)).toISOString().slice(0, 10);

export const SCHEDULE_ITEMS: ScheduleItem[] = [
  ...[0, 1, 2, 3, 4, 5, 6].map((n) =>
    item({
      id: `duty-${n}`,
      series_id: "series-duty",
      activity: "duty",
      title: "[SIM] مناوبة الفريق أ",
      on_date: day(n),
      starts_at: "07:00:00",
      ends_at: "19:00:00",
      staff_count: 12,
      status: n === 0 ? "done" : n === 1 ? "done" : "planned",
      status_by_name: n < 2 ? "[SIM] عون القاعة" : null,
      status_at: n < 2 ? `${day(n)}T19:05:00Z` : null,
    }),
  ),
  item({
    id: "patrol-1",
    activity: "patrol",
    title: "[SIM] دورية الشريط الساحلي الحمامات",
    on_date: day(1),
    starts_at: "09:00:00",
    ends_at: "12:00:00",
    place: "الحمامات",
    resources: [{ category_key: "fire_truck_light", name: { ar: "شاحنة إطفاء خفيفة", fr: "Camion léger", en: "Light fire truck" }, qty: 1 }],
    status: "postponed",
    status_reason: "رياح قوية",
    status_by_name: "[SIM] عون القاعة",
    status_at: `${day(1)}T08:30:00Z`,
  }),
  item({
    id: "exercise-1",
    activity: "exercise",
    title: "[SIM] تمرين إخلاء عند الفيضانات",
    on_date: day(3),
    starts_at: "10:00:00",
    ends_at: "13:00:00",
    place: "معتمدية بني خلاد",
    plan_document_id: "reg-plan",
    plan_title: "[SIM] المخطط الجهوي للنجدة عند الفيضانات بولاية نابل",
    staff_count: 25,
  }),
  item({ id: "visit-1", activity: "prevention_visit", title: "[SIM] زيارة وقاية لنزل", on_date: day(2), starts_at: "14:00:00", ends_at: "16:00:00" }),
  item({
    id: "maintenance-1",
    activity: "maintenance",
    title: "[SIM] صيانة المضخات",
    on_date: day(4),
    starts_at: null,
    ends_at: null,
    resources: [{ category_key: "pump", name: { ar: "مضخة", fr: "Motopompe", en: "Pump" }, qty: 4 }],
  }),
];

export const SCHEDULE_DETAIL: PeriodDetail = {
  period: {
    id: "per-nabeul-w44",
    gouvernorat_code: 21,
    gouvernorat_name: "نابل",
    span: "week",
    starts_on: WEEK_START,
    ends_on: "2026-11-01",
    status: "approved",
    approval: "head",
    notes: "",
    return_reason: null,
    submitted_by_name: "[SIM] عون القاعة",
    submitted_at: "2026-10-24T10:00:00Z",
    approved_by_name: "[SIM] رئيس القاعة الجهوية",
    approved_at: "2026-10-24T15:00:00Z",
    centre_approved_by_name: null,
    centre_approved_at: null,
    version: 4,
    created_by_name: "[SIM] عون القاعة",
    updated_by_name: "[SIM] عون القاعة",
    updated_at: "2026-10-27T19:05:00Z",
    counts: { items: 11, due: 5, done: 2, postponed: 1, cancelled: 0, rate: 0.4 },
  },
  items: SCHEDULE_ITEMS,
  can_edit: false,
  can_submit: false,
  can_approve: false,
  can_return: false,
  can_follow_up: true,
  can_delete: false,
  previous_id: "per-nabeul-w43",
};

export const SCHEDULE_SLOT: PeriodSlot = {
  gouvernorat_code: 21,
  span: "week",
  starts_on: WEEK_START,
  ends_on: "2026-11-01",
  period: SCHEDULE_DETAIL,
  can_create: false,
};

const NAMES: [number, string][] = [
  [11, "تونس"],
  [21, "نابل"],
  [23, "بنزرت"],
  [51, "سوسة"],
  [61, "صفاقس"],
];

export const SCHEDULE_PROGRESS: Progress = {
  span: "week",
  starts_on: WEEK_START,
  ends_on: "2026-11-01",
  lists: true,
  rows: NAMES.map(([code, name], n) => ({
    gouvernorat_code: code,
    gouvernorat_name: name,
    approval: n === 2 ? "head_and_centre" : n === 3 ? "direct" : "head",
    period_id: n === 4 ? null : `per-${code}`,
    status: n === 4 ? null : (["approved", "approved", "awaiting_centre", "approved"] as const)[n] ?? "draft",
    counts:
      n === 4
        ? { items: 0, due: 0, done: 0, postponed: 0, cancelled: 0, rate: null }
        : { items: 30 + n, due: 12, done: 12 - n * 2, postponed: n, cancelled: 0, rate: (12 - n * 2) / 12 },
  })),
};

export const SCHEDULE_SETTINGS: ScheduleSetting[] = NAMES.map(([code, name], n) => ({
  gouvernorat_code: code,
  gouvernorat_name: name,
  approval: n === 2 ? "head_and_centre" : n === 3 ? "direct" : "head",
  updated_by_name: n === 2 ? "[SIM] رئيس القاعة الجهوية ببنزرت" : null,
  updated_at: n === 2 ? "2026-10-20T09:00:00Z" : null,
  can_edit: code === 21,
}));

export const SCHEDULE_OPTIONS: ScheduleOptions = {
  units: [{ id: "u-nabeul", name: "الوحدة الجهوية بنابل" }],
  categories: [
    { key: "pump", kind: "equipment", name: { ar: "مضخة", fr: "Motopompe", en: "Pump" } },
    { key: "fire_truck_light", kind: "vehicle", name: { ar: "شاحنة إطفاء خفيفة", fr: "Camion léger", en: "Light fire truck" } },
  ],
  plans: [{ id: "reg-plan", title: "[SIM] المخطط الجهوي للنجدة عند الفيضانات بولاية نابل", hazard_key: "floods" }],
};

export const SCHEDULE_TEMPLATES: ScheduleTemplate[] = [
  {
    id: "tpl-week",
    gouvernorat_code: 21,
    span: "week",
    name: "[SIM] الأسبوع العادي",
    items: 11,
    activities: { duty: 7, patrol: 1, exercise: 1, prevention_visit: 1, maintenance: 1 },
    created_by_name: "[SIM] رئيس القاعة الجهوية",
    created_at: "2026-10-10T09:00:00Z",
    updated_by_name: "[SIM] رئيس القاعة الجهوية",
    updated_at: "2026-10-24T15:10:00Z",
  },
  {
    id: "tpl-summer",
    gouvernorat_code: 21,
    span: "week",
    name: "[SIM] أسبوع موسم الاصطياف",
    items: 18,
    activities: { duty: 7, patrol: 7, awareness: 2, readiness_check: 2 },
    created_by_name: "[SIM] رئيس القاعة الجهوية",
    created_at: "2026-06-01T09:00:00Z",
    updated_by_name: "[SIM] رئيس القاعة الجهوية",
    updated_at: "2026-06-01T09:00:00Z",
  },
];
