/** The decision window (L4, design-l4.md §3 and §5): the shapes the API answers. */
import type { Anomaly } from "./anomalies";

export interface WindowFilters {
  q?: string;
  from?: string;
  to?: string;
  gouvernorats?: number[];
  delegation?: number | null;
  category?: string[];
  classification?: string[];
  severity?: number[];
  status?: string[];
  source?: string[];
  unit?: string | null;
  org?: string | null;
}

export interface Understood {
  text: string;
  kind: "category" | "classification" | "gouvernorat" | "delegation" | "reference" | "word" | "unmatched";
  key: string | null;
}

/** `count` null: fewer than the floor, shown "<5". */
export interface Cell {
  key: string;
  count: number | null;
}

export interface Figures {
  incidents: number | null;
  by_category: Cell[];
  by_severity: Cell[];
  by_status: Cell[];
  by_gouvernorat: Cell[];
  series_step: "day" | "month";
  series: Cell[];
  injured: number | null;
  deceased: number | null;
  rescued: number | null;
  burned_ha: number | null;
  to_assignment_min: number | null;
  to_on_scene_min: number | null;
  reports: number | null;
  confirmed: number | null;
  confirmed_rate: number | null;
}

export interface IncidentRow {
  id: string;
  ref: string;
  category: string;
  classification: string | null;
  severity: number | null;
  status: string;
  gouvernorat_code: number | null;
  delegation_id: number | null;
  opened_at: string;
  closed_at: string | null;
  axis_number: string | null;
}

export interface SearchResult {
  from: string;
  to: string;
  gouvernorats: number[];
  understood: Understood[];
  figures: Figures;
  items: IncidentRow[];
  truncated: boolean;
  delegated: boolean;
  min_cell: number;
}

export interface Programmes {
  programmes: number;
  posts: number;
  lifeguards_planned: number;
  lifeguards_deployed: number;
  activities_due: number;
  activities_done: number;
  rate: number | null;
}

export interface Side {
  label: string;
  from: string;
  to: string;
  gouvernorats: number[];
  figures: Figures;
  programmes: Programmes | null;
}

export interface CompareRow {
  metric: string;
  key: string | null;
  a: number | null;
  b: number | null;
  delta: number | null;
  pct: number | null;
}

export type CompareMode = "periods" | "gouvernorats";

export interface CompareQuery {
  mode: CompareMode;
  a_from?: string;
  a_to?: string;
  b_from?: string;
  b_to?: string;
  a_gouvernorat?: number | null;
  b_gouvernorat?: number | null;
}

export interface CompareResult {
  mode: CompareMode;
  a: Side;
  b: Side;
  rows: CompareRow[];
  delegated: boolean;
  min_cell: number;
}

export interface AxisNow {
  id: string;
  number: string;
  name: string;
  kind: string;
  level: number;
  scope: string;
  gouvernorat_code: number | null;
  opened_at: string;
  plan: string;
  plan_document_id: string | null;
  plan_title: string | null;
  incidents: number;
}

export interface ResourceNow {
  kind: string;
  available: number;
  assigned: number;
  out_of_service: number;
}

export interface ProgressNow {
  gouvernorat_code: number;
  gouvernorat_name: string;
  day_due: number;
  day_done: number;
  day_rate: number | null;
  week_due: number;
  week_done: number;
  week_rate: number | null;
}

export interface DecisionNow {
  id: string;
  axis_id: string;
  axis_number: string;
  number: number;
  kind: string;
  category: string;
  body: string;
  issuer_role: string;
  issued_at: string;
  status: string;
}

export interface WindowNow {
  at: string;
  delegated: boolean;
  axes: AxisNow[];
  open_incidents: Cell[];
  open_total: number;
  resources: ResourceNow[] | null;
  progress: ProgressNow[] | null;
  decisions: DecisionNow[];
  /** The indicators out of their habit today (AI4); full view only, null when switched off. */
  anomalies?: Anomaly[] | null;
}

export interface EventRef {
  kind: "axis" | "incident";
  id: string;
}

export interface DelegationEvent extends EventRef {
  label: string;
  gouvernorat_code: number | null;
  added_by_name: string | null;
  added_at: string;
}

export interface Delegation {
  id: string;
  grantee: string;
  grantee_name: string | null;
  grantee_roles: string[];
  grantee_gouvernorat: number | null;
  reason: string;
  starts_at: string;
  ends_at: string;
  granted_by_name: string | null;
  granted_room: string;
  created_at: string;
  revoked_at: string | null;
  revoked_by_name: string | null;
  revoke_reason: string | null;
  state: "active" | "scheduled" | "ended" | "revoked";
  events: DelegationEvent[];
}

export interface DelegationIn {
  grantee: string;
  reason: string;
  starts_at?: string | null;
  ends_at: string;
  events: EventRef[];
}

export interface Delegate {
  id: string;
  name: string;
  roles: string[];
  gouvernorat_code: number | null;
}

export interface WindowAccess {
  full: boolean;
  delegated: boolean;
  may_delegate: boolean;
  keeps_dictionary: boolean;
  delegations: Delegation[];
}

export interface SavedSearch {
  id: string;
  name: string;
  kind: "search" | "compare";
  query: Record<string, unknown>;
  created_at: string;
}

export interface Synonym {
  id: string;
  meaning: string;
  words: string[];
  updated_by_name: string | null;
  updated_at: string;
}

export interface ExportIn {
  kind: "search" | "compare";
  format: "pdf" | "xlsx";
  lang: "ar" | "fr" | "en";
  filters: WindowFilters;
  compare?: (CompareQuery & { filters: WindowFilters }) | null;
}

export interface SummaryIn {
  kind: "search" | "compare";
  lang: "ar" | "fr" | "en";
  filters: WindowFilters;
  compare?: (CompareQuery & { filters: WindowFilters }) | null;
}

/** The advisory written summary (§9, item 1); `supported` false: the model's answer was refused. */
export interface WindowSummary {
  text: string;
  supported: boolean;
  model: string;
  notice: string;
  generated_at: string;
}
