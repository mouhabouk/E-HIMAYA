import type {
  CompareResult,
  Delegate,
  Delegation,
  Figures,
  SavedSearch,
  SearchResult,
  Synonym,
  WindowAccess,
  WindowNow,
  WindowSummary,
} from "../lib/windowTypes";

/**
 * A simulated decision window ([SIM], phase L4 §3 and §5): the data of the unit tests, the accessibility check and
 * the screenshots. No test runner import here, so Playwright loads it too.
 */
export const WINDOW_FIGURES: Figures = {
  incidents: 42,
  by_category: [
    { key: "fire", count: 27 },
    { key: "traffic_accident", count: 11 },
    { key: "flood", count: null },
  ],
  by_severity: [
    { key: "3", count: 18 },
    { key: "2", count: 16 },
    { key: "4", count: 8 },
  ],
  by_status: [
    { key: "closed", count: 36 },
    { key: "open", count: 6 },
  ],
  by_gouvernorat: [{ key: "21", count: 42 }],
  series_step: "day",
  series: [
    { key: "2026-07-01", count: 6 },
    { key: "2026-07-02", count: null },
    { key: "2026-07-03", count: 9 },
  ],
  injured: 14,
  deceased: null,
  rescued: 23,
  burned_ha: 312.5,
  to_assignment_min: 6.4,
  to_on_scene_min: 17.9,
  reports: 118,
  confirmed: 96,
  confirmed_rate: 0.814,
};

export const WINDOW_SEARCH: SearchResult = {
  from: "2026-07-01",
  to: "2026-07-31",
  gouvernorats: [21],
  understood: [
    { text: "حرايق", kind: "category", key: "fire" },
    { text: "نابل", kind: "gouvernorat", key: "21" },
  ],
  figures: WINDOW_FIGURES,
  items: [
    {
      id: "7d1f5a2e-0c4b-4c55-9f0e-2a6c1b9e8d01",
      ref: "7d1f5a2e",
      category: "fire",
      classification: "forest_fire",
      severity: 4,
      status: "closed",
      gouvernorat_code: 21,
      delegation_id: null,
      opened_at: "2026-07-12T13:20:00Z",
      closed_at: "2026-07-12T19:05:00Z",
      axis_number: "AX-2026-004",
    },
  ],
  truncated: false,
  delegated: false,
  min_cell: 5,
};

const side = (label: string, from: string, to: string, incidents: number | null) => ({
  label,
  from,
  to,
  gouvernorats: [21],
  figures: { ...WINDOW_FIGURES, incidents },
  programmes: {
    programmes: 2,
    posts: 38,
    lifeguards_planned: 120,
    lifeguards_deployed: 104,
    activities_due: 240,
    activities_done: 201,
    rate: 0.838,
  },
});

export const WINDOW_COMPARE: CompareResult = {
  mode: "periods",
  a: side("a", "2025-07-01", "2025-08-31", 51),
  b: side("b", "2026-07-01", "2026-08-31", 42),
  rows: [
    { metric: "incidents", key: null, a: 51, b: 42, delta: -9, pct: -0.176 },
    { metric: "deceased", key: null, a: 6, b: null, delta: null, pct: null },
    { metric: "burned_ha", key: null, a: 410.2, b: 312.5, delta: -97.7, pct: -0.238 },
    { metric: "confirmed_rate", key: null, a: 0.77, b: 0.814, delta: 0.044, pct: 0.057 },
    { metric: "category", key: "fire", a: 33, b: 27, delta: -6, pct: -0.182 },
    { metric: "programmes.rate", key: null, a: 0.79, b: 0.838, delta: 0.048, pct: 0.061 },
  ],
  delegated: false,
  min_cell: 5,
};

export const WINDOW_NOW: WindowNow = {
  at: "2026-10-28T09:00:00Z",
  delegated: false,
  axes: [
    {
      id: "0b6f3c1d-4e2a-4b8f-9a7d-5c3e2f1a0b9c",
      number: "AX-2026-004",
      name: "[SIM] حرائق غابات نابل",
      kind: "forest_fire",
      level: 3,
      scope: "gouvernorat",
      gouvernorat_code: 21,
      opened_at: "2026-10-27T15:00:00Z",
      plan: "",
      plan_document_id: "1c2d3e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f",
      plan_title: "[SIM] مخطط مجابهة حرائق الغابات",
      incidents: 7,
    },
  ],
  open_incidents: [
    { key: "4", count: 2 },
    { key: "3", count: 5 },
    { key: "2", count: 9 },
  ],
  open_total: 16,
  resources: [
    { kind: "fire_engine", available: 14, assigned: 6, out_of_service: 2 },
    { kind: "ambulance", available: 21, assigned: 4, out_of_service: 1 },
  ],
  progress: [
    {
      gouvernorat_code: 21,
      gouvernorat_name: "نابل",
      day_due: 12,
      day_done: 9,
      day_rate: 0.75,
      week_due: 60,
      week_done: 48,
      week_rate: 0.8,
    },
  ],
  decisions: [
    {
      id: "5e4d3c2b-1a09-4f8e-8d7c-6b5a49382716",
      axis_id: "0b6f3c1d-4e2a-4b8f-9a7d-5c3e2f1a0b9c",
      axis_number: "AX-2026-004",
      number: 3,
      kind: "decision",
      category: "evacuation",
      body: "[SIM] إخلاء المنازل المحاذية لغابة دار شيشو",
      issuer_role: "governor",
      issued_at: "2026-10-28T07:30:00Z",
      status: "in_progress",
    },
  ],
  anomalies: [
    {
      id: "an-1",
      indicator: "arrival",
      gouvernorat_code: 21,
      gouvernorat_name: "نابل",
      delegation_id: 2101,
      delegation_name: "الحمامات",
      day: "2026-10-29",
      value: 24,
      mean: 14,
      std: 3,
      z: 3.3,
      baseline: "recent",
      points: 8,
      n: 9,
      higher: true,
      text: "[SIM] زمن الوصول في معتمدية الحمامات خلال الأيام السبعة الأخيرة 24 دقيقة، والمعتاد 14 ± 3 (في الأسابيع الثمانية السابقة).",
      raised_at: "2026-10-29T07:00:00Z",
    },
  ],
};

export const WINDOW_DELEGATION: Delegation = {
  id: "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d",
  grantee: "gov-nabeul",
  grantee_name: "[SIM] والي نابل",
  grantee_roles: ["governor"],
  grantee_gouvernorat: 21,
  reason: "[SIM] متابعة حرائق الغابات",
  starts_at: "2026-10-27T16:00:00Z",
  ends_at: "2026-11-03T16:00:00Z",
  granted_by_name: "[SIM] مدير عمليات نابل",
  granted_room: "g:21",
  created_at: "2026-10-27T16:00:00Z",
  revoked_at: null,
  revoked_by_name: null,
  revoke_reason: null,
  state: "active",
  events: [
    {
      kind: "axis",
      id: "0b6f3c1d-4e2a-4b8f-9a7d-5c3e2f1a0b9c",
      label: "AX-2026-004 · [SIM] حرائق غابات نابل",
      gouvernorat_code: 21,
      added_by_name: "[SIM] مدير عمليات نابل",
      added_at: "2026-10-27T16:00:00Z",
    },
  ],
};

export const WINDOW_ACCESS_FULL: WindowAccess = {
  full: true,
  delegated: false,
  may_delegate: true,
  keeps_dictionary: false,
  delegations: [],
};

export const WINDOW_ACCESS_DELEGATED: WindowAccess = {
  full: false,
  delegated: true,
  may_delegate: false,
  keeps_dictionary: false,
  delegations: [WINDOW_DELEGATION],
};

export const WINDOW_DELEGATES: Delegate[] = [
  { id: "gov-nabeul", name: "[SIM] والي نابل", roles: ["governor"], gouvernorat_code: 21 },
];

export const WINDOW_SAVED: SavedSearch[] = [
  { id: "s-1", name: "[SIM] حرائق الصيف", kind: "search", query: { q: "حريق", from: "2026-07-01", to: "2026-08-31" }, created_at: "2026-10-20T10:00:00Z" },
];

export const WINDOW_SYNONYMS: Synonym[] = [
  { id: "y-1", meaning: "traffic_accident", words: ["كسيدة", "اكسيدان", "accident"], updated_by_name: "e-Himaya", updated_at: "2026-10-28T00:00:00Z" },
];

export const WINDOW_SUMMARY: WindowSummary = {
  text: "[SIM] سُجّل 42 تدخلا في جويلية، منها 27 حريقا و11 حادث مرور.",
  supported: true,
  model: "qwen3",
  notice: "ملخص آلي استشاري، أعدّه نموذج لغوي محلي من الأعداد المجمّعة المعروضة فقط. راجع الأرقام قبل اعتماده.",
  generated_at: "2026-10-28T09:00:00Z",
};
