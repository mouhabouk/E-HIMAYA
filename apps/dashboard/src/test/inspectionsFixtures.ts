import { vi } from "vitest";
import type {
  BinRow,
  Dashboard,
  Inspector,
  inspectionsApi,
  Mission,
  PlaceStatus,
  Policy,
  Profile,
  RecordDetail,
  RecordRow,
  RoomLive,
  RoomResult,
  RoomUpcoming,
} from "../lib/inspectionsApi";

/** Phase I2 [SIM]: one profile, one planned mission, one submitted report of a regional room, two inspectors. */
export const INSPECTION_PROFILE: Profile = {
  id: "p-1",
  name: "النموذج الأساسي",
  version: 1,
  config: {
    axes: [
      { key: "readiness", name: "الجاهزية", weight: 60 },
      { key: "room", name: "القاعة", weight: 40 },
    ],
    items: [
      { key: "r1", axis: "readiness", text: "حضور الأعوان", weight: 50 },
      { key: "r2", axis: "readiness", text: "جاهزية الشاحنات", weight: 50 },
      { key: "c1", axis: "room", text: "سجل المكالمات", weight: 100 },
    ],
    values: { ok: 1, note: 0.5, ko: 0 },
    weights: { items: 70, presence: 20, exit: 10 },
    exit: { fast: 60, ok: 120, fast_value: 1, ok_value: 0.6, slow_value: 0.2 },
    levels: [
      { name: "جيد", min: 80, colour: "green" },
      { name: "مقبول", min: 60, colour: "amber" },
      { name: "ضعيف", min: 0, colour: "red" },
    ],
    sections: ["القيادة والإدارة", "العمليات والتدخّل"],
  },
  created_by_name: "المتفقد العام [SIM]",
  created_at: "2026-11-01T08:00:00Z",
};

export const INSPECTION_POLICY: Policy = {
  central: { inspection: true, verdict: true, score: false },
  regional: { inspection: true, verdict: false, score: false },
  recommendations: { high: "both", medium: "regional", low: "none", general: "regional" },
  publish_programme: false,
  notice_days: 15,
  reminder_days: 2,
};

export const INSPECTORS: Inspector[] = [
  {
    id: "i-1",
    kind: "internal",
    matricule: "12345",
    name: "سامي المتفقد [SIM]",
    organisation: null,
    phone: "+21620000000",
    email: null,
    via: "sms",
    status: "active",
    expires_on: null,
    matched_agent: true,
    requested_device: "Pixel 8",
    requested_at: "2026-11-02T09:00:00Z",
    decided_at: "2026-11-02T10:00:00Z",
    decided_by_name: "المتفقد العام [SIM]",
    reject_reason: null,
    code_expires_at: null,
    activated_at: "2026-11-02T11:00:00Z",
    device_model: "Pixel 8",
    last_seen_at: "2026-11-11T08:00:00Z",
    lost_at: null,
  },
  {
    id: "i-2",
    kind: "external",
    matricule: "EXT-7",
    name: "خبير خارجي [SIM]",
    organisation: "وزارة الداخلية",
    phone: null,
    email: "expert@example.org",
    via: "email",
    status: "pending",
    expires_on: null,
    matched_agent: false,
    requested_device: "iPhone 15",
    requested_at: "2026-11-10T09:00:00Z",
    decided_at: null,
    decided_by_name: null,
    reject_reason: null,
    code_expires_at: null,
    activated_at: null,
    device_model: null,
    last_seen_at: null,
    lost_at: null,
  },
];

const [ACTIVE, PENDING] = INSPECTORS as [Inspector, Inspector];

export const MISSION: Mission = {
  id: "m-1",
  ref: "OM-2026-0001",
  on_date: "2026-11-20",
  at_time: "09:00",
  kind: "periodic",
  inspector_id: "i-1",
  inspector_name: "سامي المتفقد [SIM]",
  status: "planned",
  cancel_reason: null,
  published: false,
  sites: [
    {
      id: "s-1",
      position: 1,
      target: "unit",
      unit_kind: "centre",
      unit_name: "مركز باجة المدينة",
      unit_id: null,
      room: null,
      name: "مركز باجة المدينة",
      gouvernorat_code: 31,
      sections: ["القيادة والإدارة"],
      inspection_id: null,
      inspection_status: null,
      arrived_at: "2026-11-12T08:05:00Z",
      arrived_offline: true,
      left_at: null,
    },
  ],
  created_by_name: "المتفقد العام [SIM]",
  created_at: "2026-11-10T08:00:00Z",
};

export const RECORD: RecordRow = {
  id: "x-1",
  mission_ref: "OM-2026-0000",
  kind: "surprise",
  target: "room",
  unit_kind: null,
  room: "regional",
  place: "القاعة الجهوية بباجة",
  gouvernorat_code: 31,
  inspector_name: "سامي المتفقد [SIM]",
  status: "submitted",
  started_at: "2026-11-05T09:00:00Z",
  submitted_at: "2026-11-05T11:00:00Z",
  score: 82.5,
  verdict: "جيد",
  previous_score: 70,
  receipt: "R-1",
};

export const RECORD_DETAIL: RecordDetail = {
  ...RECORD,
  answers: { r1: "ok", r2: "note", c1: "ko" },
  present: 8,
  expected: 10,
  exit_seconds: 75,
  summary: "قاعة منظمة مع ملاحظات على السجل.",
  head_name: "رئيس القاعة [SIM]",
  signed_at: "2026-11-05T11:00:00Z",
  profile_name: "النموذج الأساسي",
  profile_version: 1,
  disclosure: { regional: { inspection: true, verdict: true, score: false } },
  recommendations: [
    { id: "rc-1", kind: "detailed", item_key: "c1", text: "تحيين سجل المكالمات يوميا", priority: "high", audience: "both" },
    { id: "rc-2", kind: "general", item_key: null, text: "تدريب الأعوان الجدد", priority: null, audience: "regional" },
  ],
};

const [REC_HIGH] = RECORD_DETAIL.recommendations as [RecordDetail["recommendations"][number]];

export const INSPECTION_DASHBOARD: Dashboard = {
  month_missions: 4,
  month_done: 1,
  month_planned: 3,
  rooms_without_plan: 2,
  average_score: 82.5,
  by_month: [{ month: "2026-11", count: 4 }],
  levels: { جيد: 1 },
};

export const PLACES: PlaceStatus[] = [
  {
    target: "room",
    unit_kind: null,
    unit_name: null,
    room: "regional",
    name: "القاعة الجهوية بباجة",
    gouvernorat_code: 31,
    last_inspection_id: "x-1",
    last_on: "2026-11-05",
    last_score: 82.5,
    last_verdict: "جيد",
    next_on: null,
  },
];

export const ROOM_RESULTS: RoomResult[] = [
  {
    id: "x-1",
    room: "regional",
    place: "القاعة الجهوية بباجة",
    gouvernorat_code: 31,
    kind: "surprise",
    submitted_at: "2026-11-05T11:00:00Z",
    verdict: "جيد",
    score: null,
    recommendations: [REC_HIGH],
  },
];

export const ROOM_LIVE: RoomLive[] = [
  {
    id: "x-2",
    room: "regional",
    place: "القاعة الجهوية بجندوبة",
    gouvernorat_code: 32,
    inspector_name: "سامي المتفقد [SIM]",
    started_at: "2026-11-12T09:00:00Z",
    answered: 2,
    items: 3,
    score: null,
  },
];

export const ROOM_UPCOMING: RoomUpcoming[] = [
  { ref: "OM-2026-0002", room: "central", place: "القاعة المركزية", gouvernorat_code: null, on_date: "2026-11-25", kind: "periodic" },
];

export const BIN: BinRow[] = [
  {
    id: "x-9",
    place: "مركز قديم",
    submitted_at: "2026-10-01T10:00:00Z",
    deleted_at: "2026-11-11T10:00:00Z",
    deleted_by_name: "مدير النظام [SIM]",
    delete_reason: "تقرير تجريبي مكرر",
  },
];

export function fakeInspectionsApi(): ReturnType<typeof inspectionsApi> {
  return {
    inspectionDashboard: vi.fn(() => Promise.resolve(INSPECTION_DASHBOARD)),
    inspectionPlaces: vi.fn(() => Promise.resolve(PLACES)),
    inspectionMissions: vi.fn(() => Promise.resolve([MISSION])),
    createInspectionMission: vi.fn(() => Promise.resolve(MISSION)),
    cancelInspectionMission: vi.fn(() => Promise.resolve({ ...MISSION, status: "cancelled" as const })),
    downloadMissionOrder: vi.fn(() => Promise.resolve()),
    inspectionRecords: vi.fn(() => Promise.resolve([RECORD])),
    inspectionRecord: vi.fn(() => Promise.resolve(RECORD_DETAIL)),
    setInspectionDisclosure: vi.fn(() => Promise.resolve(RECORD_DETAIL)),
    setRecommendationAudience: vi.fn(() => Promise.resolve(RECORD_DETAIL)),
    inspectors: vi.fn(() => Promise.resolve(INSPECTORS)),
    activateInspector: vi.fn(() => Promise.resolve(ACTIVE)),
    rejectInspector: vi.fn(() => Promise.resolve(PENDING)),
    renewInspectorCode: vi.fn(() => Promise.resolve(ACTIVE)),
    reportInspectorLost: vi.fn(() => Promise.resolve(ACTIVE)),
    closeInspector: vi.fn(() => Promise.resolve(ACTIVE)),
    inspectionProfile: vi.fn(() => Promise.resolve(INSPECTION_PROFILE)),
    saveInspectionProfile: vi.fn(() => Promise.resolve(INSPECTION_PROFILE)),
    orderNotes: vi.fn(() => Promise.resolve({ notes: ["يحمل المتفقد بطاقته المهنية"] })),
    saveOrderNotes: vi.fn((notes: string[]) => Promise.resolve({ notes })),
    inspectionPolicy: vi.fn(() => Promise.resolve(INSPECTION_POLICY)),
    saveInspectionPolicy: vi.fn(() => Promise.resolve(INSPECTION_POLICY)),
    applyInspectionPolicy: vi.fn(() => Promise.resolve({ deleted: 0 })),
    roomResults: vi.fn(() => Promise.resolve(ROOM_RESULTS)),
    roomLive: vi.fn(() => Promise.resolve(ROOM_LIVE)),
    roomUpcoming: vi.fn(() => Promise.resolve(ROOM_UPCOMING)),
    deleteInspections: vi.fn(() => Promise.resolve({ deleted: 1 })),
    inspectionBin: vi.fn(() => Promise.resolve(BIN)),
    restoreInspection: vi.fn(() => Promise.resolve(undefined)),
  };
}
