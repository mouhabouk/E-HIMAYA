/** The digital dry run (L5a, docs/phase-l/design-l5.md §2), as services/api/app/modules/drill/schemas.py answers it. */

export const INJECT_KINDS = ["report", "development", "shortage", "evacuation", "decision", "information"] as const;
export type InjectKind = (typeof INJECT_KINDS)[number];
export const RESPONSE_ACTIONS = ["acknowledged", "dispatched", "escalated", "evacuation", "decision", "note"] as const;
export type ResponseAction = (typeof RESPONSE_ACTIONS)[number];
export type DrillStatus = "draft" | "submitted" | "ready" | "running" | "stopped" | "ended" | "closed";
export type ApprovalDecision = "pending" | "approved" | "refused" | "withdrawn";
export const PLAN_FOLLOWED = ["yes", "partly", "no", "not_applicable"] as const;
export type PlanFollowed = (typeof PLAN_FOLLOWED)[number];
export const RESOURCE_KINDS = [
  "fire_engine",
  "water_tanker",
  "ambulance",
  "rescue_vehicle",
  "heavy_equipment",
  "drone",
  "large_extinguisher",
  "boat",
  "command_vehicle",
  "other",
] as const;
export type ResourceKind = (typeof RESOURCE_KINDS)[number];

export interface DrillParticipant {
  gouvernorat_code: number;
  decision: ApprovalDecision;
  reason: string | null;
  decided_by_name: string | null;
  decided_at: string | null;
}

export interface Drill {
  id: string;
  title: string;
  objective: string;
  hazard_key: string | null;
  plan_document_id: string | null;
  gouvernorats: number[];
  room: string;
  planned_start: string;
  duration_min: number;
  evaluator: string | null;
  evaluator_name: string | null;
  status: DrillStatus;
  started_at: string | null;
  ended_at: string | null;
  stop_reason: string | null;
  stopped_by_name: string | null;
  conclusion: string | null;
  created_by_name: string | null;
  created_at: string;
  participants: DrillParticipant[];
  injects: number;
  can_edit: boolean;
  can_submit: boolean;
  can_start: boolean;
  can_stop: boolean;
  can_evaluate: boolean;
  can_close: boolean;
  my_approval: number | null;
}

export interface DrillIn {
  title: string;
  objective: string;
  hazard_key?: string | null;
  gouvernorats: number[];
  planned_start: string;
  duration_min: number;
  evaluator?: string | null;
  evaluator_name?: string | null;
}

export interface Inject {
  id: string;
  offset_min: number;
  gouvernorat_code: number | null;
  kind: InjectKind;
  title: string;
  body: string;
  needs: Record<string, number>;
  expected: string;
  generated: boolean;
}

export interface InjectIn {
  offset_min: number;
  gouvernorat_code: number | null;
  kind: InjectKind;
  title: string;
  body?: string;
  needs?: Partial<Record<ResourceKind, number>>;
  expected?: string;
}

export interface GenerateIn {
  count: number;
  kinds?: string[];
  seed?: number;
}

export interface Booking {
  resource_id: string;
  label: string;
  kind: string;
  released: boolean;
}

export interface DrillResponse {
  id: string;
  gouvernorat_code: number;
  action: ResponseAction;
  text: string;
  responded_by_name: string | null;
  responded_at: string;
  bookings: Booking[];
}

export interface ResponseIn {
  action: ResponseAction;
  text: string;
  resource_ids: string[];
}

export interface FreeResource {
  id: string;
  kind: string;
  label: string;
  unit: string;
}

export interface FeedItem {
  inject: Inject;
  due_at: string;
  responses: DrillResponse[];
}

export interface Feed {
  exercise_id: string;
  status: DrillStatus;
  elapsed_min: number;
  remaining_min: number;
  items: FeedItem[];
  free: Record<string, number>;
  free_resources: FreeResource[];
}

export interface Evaluation {
  plan_followed: PlanFollowed;
  score: number;
  notes: string;
  evaluated_by_name: string | null;
  evaluated_at: string;
}

export interface EvaluationIn {
  plan_followed: PlanFollowed;
  score: number;
  notes: string;
}

export interface Stress {
  environment: "isolated";
  reports_sent: number;
  reports_accepted: number;
  reports_refused: number;
  errors_5xx: number;
  peak_per_second: number;
  latency_p95_ms: number;
  latency_p99_ms: number;
  duration_s: number;
  attacks_sent: number;
  attacks_blocked: number;
  attack_kinds: string[];
}

export interface InjectReport {
  inject: Inject;
  due_at: string | null;
  answered: boolean;
  first_answer_min: number | null;
  booked: Record<string, number>;
  shortfall: Record<string, number>;
  evaluation: Evaluation | null;
}

export interface ResourceLine {
  gouvernorat_code: number;
  kind: string;
  available_at_start: number;
  peak_booked: number;
  short: number;
}

export interface DrillReport {
  exercise: Drill;
  injects: InjectReport[];
  answered: number;
  unanswered: number;
  median_answer_min: number | null;
  plan_followed: Record<string, number>;
  mean_score: number | null;
  resources: ResourceLine[];
  stress: Stress[];
}
