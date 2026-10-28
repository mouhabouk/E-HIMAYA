// [SIM] data of the digital dry run (L5a) for the tests and the screenshots: no real event, person or resource.
import type { Drill, DrillReport, Feed, Inject } from "../lib/drill";

const ID = "4b8e2c1a-7d3f-4e5a-9b6c-1f2e3d4c5b6a";

export const DRILL: Drill = {
  id: ID,
  title: "[SIM] فيضان وادي مجردة: نابل وبنزرت",
  objective: "قياس جاهزية قاعتي نابل وبنزرت وكفاية الزوارق وسيارات الإسعاف أمام فيضان ليلي.",
  hazard_key: "flood",
  plan_document_id: null,
  gouvernorats: [21, 23],
  room: "central",
  planned_start: "2026-11-04T08:00:00Z",
  duration_min: 120,
  evaluator: "eval-sim",
  evaluator_name: "[SIM] مقيّم من قاعة قابس",
  status: "draft",
  started_at: null,
  ended_at: null,
  stop_reason: null,
  stopped_by_name: null,
  conclusion: null,
  created_by_name: "[SIM] القاعة المركزية",
  created_at: "2026-10-28T09:00:00Z",
  participants: [
    { gouvernorat_code: 21, decision: "pending", reason: null, decided_by_name: null, decided_at: null },
    { gouvernorat_code: 23, decision: "pending", reason: null, decided_by_name: null, decided_at: null },
  ],
  injects: 3,
  can_edit: true,
  can_submit: true,
  can_start: false,
  can_stop: false,
  can_evaluate: false,
  can_close: false,
  my_approval: null,
};

export const INJECTS: Inject[] = [
  {
    id: "i-1",
    offset_min: 0,
    gouvernorat_code: null,
    kind: "information",
    title: "[SIM] نشرة إنذار: أمطار غزيرة على الشمال الشرقي",
    body: "",
    needs: {},
    expected: "تفعيل خلية الأزمة وإعلام الوحدات",
    generated: false,
  },
  {
    id: "i-2",
    offset_min: 12,
    gouvernorat_code: 21,
    kind: "report",
    title: "[SIM] عائلة محاصرة بالمياه في منزل قرب الوادي",
    body: "[SIM] خمسة أشخاص بينهم طفلان، المياه في الطابق الأرضي.",
    needs: { boat: 2, ambulance: 1 },
    expected: "إرسال زورقين وسيارة إسعاف",
    generated: false,
  },
  {
    id: "i-3",
    offset_min: 35,
    gouvernorat_code: 21,
    kind: "shortage",
    title: "[SIM] عطب زورق في وحدة قليبية",
    body: "",
    needs: {},
    expected: "طلب تعزيز من الولاية المجاورة",
    generated: true,
  },
];

const [, I2, I3] = INJECTS as [Inject, Inject, Inject];

export const RUNNING: Drill = {
  ...DRILL,
  status: "running",
  started_at: "2026-11-04T08:00:00Z",
  participants: DRILL.participants.map((p) => ({
    ...p,
    decision: "approved" as const,
    decided_by_name: "[SIM] رئيس القاعة",
    decided_at: "2026-11-01T10:00:00Z",
  })),
  can_edit: false,
  can_submit: false,
  can_stop: true,
  my_approval: 21,
};

export const FEED: Feed = {
  exercise_id: ID,
  status: "running",
  elapsed_min: 40,
  remaining_min: 80,
  items: [
    { inject: I3, due_at: "2026-11-04T08:35:00Z", responses: [] },
    {
      inject: I2,
      due_at: "2026-11-04T08:12:00Z",
      responses: [
        {
          id: "r-1",
          gouvernorat_code: 21,
          action: "dispatched",
          text: "[SIM] زورقان من وحدة نابل نحو المنزل",
          responded_by_name: "[SIM] عون القاعة",
          responded_at: "2026-11-04T08:15:00Z",
          bookings: [
            { resource_id: "b-1", label: "[SIM] زورق 1", kind: "boat", released: false },
            { resource_id: "b-2", label: "[SIM] زورق 2", kind: "boat", released: false },
          ],
        },
      ],
    },
  ],
  free: { ambulance: 2, boat: 1 },
  free_resources: [
    { id: "f-1", kind: "ambulance", label: "[SIM] إسعاف 3", unit: "[SIM] وحدة نابل" },
    { id: "f-2", kind: "ambulance", label: "[SIM] إسعاف 4", unit: "[SIM] وحدة قربة" },
    { id: "f-3", kind: "boat", label: "[SIM] زورق 3", unit: "[SIM] وحدة قليبية" },
  ],
};

export const REPORT: DrillReport = {
  exercise: { ...RUNNING, status: "ended", can_stop: false, can_close: true, my_approval: null, ended_at: "2026-11-04T10:00:00Z" },
  injects: [
    { inject: I2, due_at: "2026-11-04T08:12:00Z", answered: true, first_answer_min: 3, booked: { boat: 2 }, shortfall: { ambulance: 1 }, evaluation: { plan_followed: "partly", score: 3, notes: "", evaluated_by_name: "[SIM] مقيّم", evaluated_at: "2026-11-04T10:10:00Z" } },
    { inject: I3, due_at: "2026-11-04T08:35:00Z", answered: false, first_answer_min: null, booked: {}, shortfall: {}, evaluation: null },
  ],
  answered: 1,
  unanswered: 1,
  median_answer_min: 3,
  plan_followed: { partly: 1 },
  mean_score: 3,
  resources: [
    { gouvernorat_code: 21, kind: "boat", available_at_start: 3, peak_booked: 2, short: 0 },
    { gouvernorat_code: 21, kind: "ambulance", available_at_start: 2, peak_booked: 2, short: 1 },
  ],
  stress: [
    {
      environment: "isolated",
      reports_sent: 120000,
      reports_accepted: 118400,
      reports_refused: 1600,
      errors_5xx: 0,
      peak_per_second: 410,
      latency_p95_ms: 380,
      latency_p99_ms: 720,
      duration_s: 600,
      attacks_sent: 2500,
      attacks_blocked: 2500,
      attack_kinds: ["sql_injection", "script", "oversize", "malformed", "flood_same_device"],
    },
  ],
};
