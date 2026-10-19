/** Types mirroring docs/api/phase-2-contract.md (sections 3 and 5) and phase-3-contract.md (AI layer 1). */

export const REPORT_STATUSES = ["received", "in_progress", "intervened", "ongoing", "closed", "rejected"] as const;
export type ReportStatus = (typeof REPORT_STATUSES)[number];

export const CATEGORIES = [
  "sos",
  "fire",
  "flood",
  "traffic_accident",
  "drowning",
  "landslide",
  "chemical_leak",
  "medical",
  "other",
] as const;
export type Category = (typeof CATEGORIES)[number];

export type ReporterKind = "citizen" | "anonymous";
export type MediaKind = "image" | "video" | "audio";
export type MediaStatus = "uploading" | "verifying" | "stored" | "rejected";
export type TextLang = "ar" | "fr" | "en";

export const ANALYSIS_STATES = ["pending", "running", "done", "failed"] as const;
export type AnalysisState = (typeof ANALYSIS_STATES)[number];

export interface GeoPoint {
  lat: number;
  lon: number;
  accuracy_m?: number | null;
}

export interface Media {
  id: string;
  kind: MediaKind;
  bytes: number | null;
  sha256: string;
  status: MediaStatus;
  /** MIME type declared at upload (e.g. video/mp4). */
  content_type?: string | null;
  created_at?: string;
  /** Pre-signed URL (10 minutes), only in StaffReportDetail and only when status is "stored". */
  url?: string | null;
}

export interface StaffReport {
  id: string;
  tracking_code: string;
  client_uuid?: string;
  category: Category;
  status: ReportStatus;
  text: string | null;
  lang: TextLang | null;
  location: GeoPoint;
  gouvernorat_code: number | null;
  delegation_id: number | null;
  created_at: string;
  received_at: string;
  updated_at: string;
  reporter_kind: ReporterKind;
  media_count: number;
  media?: Media[];
  // AI layer 1 (phase 3): suggestions for the operator, never applied automatically (BR-06, BR-11).
  /** Arabic translation of a French or English text (FR-A-045); null for Arabic. */
  text_ar: string | null;
  /** BR-20 priority, 0..100. */
  priority_score: number | null;
  /** BR-06 suggested credibility, 0..100. */
  credibility_score: number | null;
  analysis_state: AnalysisState | null;
  lives_at_risk: boolean | null;
  /** Category read by the language model (may differ from the citizen's). */
  suggested_category: Category | null;
  incident_id: string | null;
  /** A grouping suggestion is waiting for the operator. */
  has_suggestion: boolean;
}

export interface HistoryEntry {
  status: ReportStatus;
  at: string;
  /** Who made the change (staff subject/username, or the system). */
  actor?: string | null;
  note?: string | null;
}

export type Reporter =
  | { kind: "citizen"; first_name: string | null; last_name: string | null; phone: string | null }
  | { kind: "anonymous" };

export interface StaffReportDetail extends StaffReport {
  history: HistoryEntry[];
  media: Media[];
  reporter: Reporter;
  /** Statuses reachable from the current one, computed by the server (authoritative). */
  allowed_transitions?: ReportStatus[];
  /** AI analysis (phase 3); null/absent before the first analysis. */
  analysis?: Analysis | null;
}

/** Priority components (BR-20), in the order of the settings. */
export const PRIORITY_COMPONENTS = [
  "severity",
  "lives",
  "casualties",
  "reporters",
  "credibility",
  "sensitive_sites",
  "weather",
] as const;
export type PriorityComponent = (typeof PRIORITY_COMPONENTS)[number];

export const ANALYSIS_STEPS = ["transcribe", "extract", "translate", "embed"] as const;
export type AnalysisStep = (typeof ANALYSIS_STEPS)[number];
export const STEP_STATES = ["done", "skipped", "failed", "unavailable", "disabled"] as const;
export type StepState = (typeof STEP_STATES)[number];

export interface ScoreComponent {
  key: string;
  /** Priority only: 0..1, null = no data source yet (left out, the other weights rescaled). */
  value?: number | null;
  /** Priority only: weight from the settings. */
  weight?: number | null;
  /** Contribution to the score (credibility: signed points). */
  points: number;
  detail: Record<string, unknown>;
}

export interface ExplainedScore {
  score: number;
  components: ScoreComponent[];
}

export interface Extraction {
  language: string;
  category: Category;
  lives_at_risk: boolean;
  people_trapped: boolean;
  injured_count: number;
  deaths_reported: boolean;
  hazards: string[];
  keywords: string[];
  summary_ar: string;
  confidence: number;
}

export const SUGGESTION_REASONS = [
  "same_category",
  "sos_nearby",
  "within_radius",
  "within_window",
  "similar_content",
] as const;

export interface Suggestion {
  /** "incident": join an existing incident; "report": start an incident with another report. */
  kind: "incident" | "report";
  incident_id: string | null;
  report_id: string;
  tracking_code: string;
  score: number;
  distance_m: number;
  minutes: number;
  similarity: number | null;
  reasons: string[];
  matching_reports: number;
}

export interface Transcript {
  media_id: string;
  kind: string;
  text: string | null;
  language: string | null;
  language_probability: number | null;
  duration_s: number | null;
  translation_ar: string | null;
  error: string | null;
  model: string | null;
}

export interface Analysis {
  state: AnalysisState;
  attempts: number;
  language: string | null;
  steps: Partial<Record<string, string>>;
  extraction: Extraction | null;
  priority: ExplainedScore | null;
  credibility: ExplainedScore | null;
  suggestion: Suggestion | null;
  transcripts: Transcript[];
  models: Partial<Record<string, string>>;
  updated_at: string;
}

// ---------- Incidents (phase 3, FR-C-02, BR-10, BR-11) ----------

export const INCIDENT_STATUSES = ["open", "closed", "merged", "dissolved"] as const;
export type IncidentStatus = (typeof INCIDENT_STATUSES)[number];

export const TIMELINE_KINDS = [
  "created",
  "report_linked",
  "report_unlinked",
  "merged_from",
  "merged_into",
  "closed",
  "reopened",
  "dissolved",
] as const;

export interface IncidentSummary {
  id: string;
  category: Category;
  status: IncidentStatus;
  gouvernorat_code: number | null;
  centroid: { lat: number; lon: number } | null;
  /** Highest priority among its reports (0..100). */
  severity: number | null;
  report_count: number;
  reporter_count: number;
  opened_at: string;
  updated_at: string;
  closed_at: string | null;
  merged_into: string | null;
}

export interface TimelineEntry {
  at: string;
  kind: string;
  actor: string | null;
  payload: Record<string, unknown>;
}

export interface IncidentDetail extends IncidentSummary {
  reports: StaffReport[];
  timeline: TimelineEntry[];
}

export type IncidentLinkBody =
  | { action: "accept_suggestion" }
  | { action: "link"; incident_id: string }
  | { action: "new" };

// ---------- AI settings and status (phase 3, section 4) ----------

export interface AiSettings {
  priority: {
    weights: Record<PriorityComponent, number>;
    category_severity: Record<Category, number>;
    suggestion_min_confidence: number;
  };
  grouping: {
    window_min: number;
    radius_m: Record<Category, number>;
    semantic_min_similarity: number;
    semantic_radius_m: number;
    semantic_window_min: number;
  };
}

export const AI_CAPABILITIES = ["transcribe", "translate_fr", "translate_en", "embed", "extract"] as const;
export type AiCapability = (typeof AI_CAPABILITIES)[number];

export interface CapabilityHealth {
  ready: boolean;
  model: string | null;
  detail: string | null;
}

export interface AiStatus {
  configured: boolean;
  capabilities: Partial<Record<string, CapabilityHealth>>;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface Kpis {
  since: string;
  total: number;
  by_status: Partial<Record<ReportStatus, number>>;
  by_category: Partial<Record<Category, number>>;
  by_gouvernorat: { code: number | null; count: number }[];
  avg_first_response_s: number | null;
  /** Reports with priority ≥ 70 (phase 3). */
  high_priority: number;
  /** Reports waiting for (or in) AI analysis (phase 3). */
  analysis_pending: number;
}

export interface Gouvernorat {
  code: number;
  iso_code: string;
  name: string;
  name_ar: string;
  name_fr: string;
  delegation_count: number;
}

export interface Me {
  subject: string;
  realm: string;
  roles: string[];
  gouvernorat_code: number | null;
  is_staff: boolean;
}

export function isReportStatus(v: unknown): v is ReportStatus {
  return typeof v === "string" && (REPORT_STATUSES as readonly string[]).includes(v);
}

export function isCategory(v: unknown): v is Category {
  return typeof v === "string" && (CATEGORIES as readonly string[]).includes(v);
}

export function isIncidentStatus(v: unknown): v is IncidentStatus {
  return typeof v === "string" && (INCIDENT_STATUSES as readonly string[]).includes(v);
}
