/**
 * Types mirroring docs/api/phase-2-contract.md (sections 3 and 5), phase-3-contract.md (AI layer 1) and
 * phase-4-contract.md (institutions, sections 8–10). Phase 5 types live in opsTypes.ts.
 */
import type { Assignment, Callout, Evaluation, OpLevel } from "./opsTypes";
import {
  CREW_TIMELINE_KINDS,
  type Casualties,
  type CrewAlert,
  type FieldAttachment,
  type FieldReport,
  type Transport,
} from "./crewTypes";
import { PHASE9_TIMELINE_KINDS } from "./phase9Types";
import type {
  CommandLevel,
  Escalation,
  EscalationState,
  GeoState,
  ReporterContext,
  ResourceRequest,
  Room,
  SlaBand,
} from "./phase9Types";
import type { MediaAnalysis } from "./streamTypes";
import type { KindFieldValue } from "./kindFields";

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
/** `recording`: a segment of a live stream (phase 6 §1), stored with `stream_id` and `duration_s`. */
export type MediaKind = "image" | "video" | "audio" | "recording";
export type MediaStatus = "uploading" | "verifying" | "stored" | "rejected" | "quarantined";
/** Why the verification worker refused a file (phase 5.5, A7). */
export type MediaRejectionReason = "sha256_mismatch" | "type_mismatch" | "disallowed_type";
export const MEDIA_REJECTION_REASONS: readonly MediaRejectionReason[] = [
  "sha256_mismatch",
  "type_mismatch",
  "disallowed_type",
];
/** Why a report was accepted but flagged for a human check (phase 5.5, A1/A2). */
/** `anonymous_quota`: an SOS accepted beyond the anonymous quota (phase 9 §3). */
export type VerificationReason = "anonymous_budget" | "limiter_degraded" | "anonymous_quota";
export const VERIFICATION_REASONS: readonly VerificationReason[] = ["anonymous_budget", "limiter_degraded", "anonymous_quota"];
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
  /** MIME type: the one verified from the file's bytes once stored (e.g. video/mp4). */
  content_type?: string | null;
  created_at?: string;
  /** Pre-signed URL (10 minutes), only in StaffReportDetail: "stored" media inline, "quarantined" as a download. */
  url?: string | null;
  /** Set on quarantined media (staff only). */
  rejection_reason?: MediaRejectionReason | null;
  /** Phase 6: the live stream a recording (or a frame stored by the vision service) belongs to. */
  stream_id?: string | null;
  duration_s?: number | null;
  /** Phase 6: `analysis.vision` (fire/smoke/person detections) of an image; `source = "vision"` for stream frames. */
  analysis?: MediaAnalysis | null;
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
  /** Words to hide (`hide`) or to shade red (`flag`) on screen, [start, end, kind] in UTF-16 units; absent from older payloads. */
  text_masks?: [number, number, "hide" | "flag"][];
  text_ar_masks?: [number, number, "hide" | "flag"][];
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
  /** Institution the report was made on behalf of (phase 4 §8–9); absent from older payloads. */
  organization?: OrgRef | null;
  /** Accepted beyond the anonymous budget or while the rate limiter was degraded: check before dispatch. */
  needs_verification?: boolean;
  verification_reason?: VerificationReason | null;
  // Phase 9 (§4.6): jurisdiction, claim and SLA; absent from older payloads.
  geo_state?: GeoState;
  /** Candidate gouvernorats of a location that is not trusted yet (§4.2). */
  geo_candidates?: number[];
  geo_reason?: string | null;
  /** `central` or `g:<code>`: the room handling the report. */
  claimed_room?: Room | null;
  claimed_by_name?: string | null;
  claimed_at?: string | null;
  sla_band?: SlaBand | null;
  sla_due_at?: string | null;
  escalation_state?: EscalationState;
  late?: boolean;
  referred_to?: number | null;
}

export interface HistoryEntry {
  status: ReportStatus;
  at: string;
  /** Who made the change (staff subject/username, or the system). */
  actor?: string | null;
  note?: string | null;
}

/**
 * Reporter of a report. From phase 9 (§1.3) the API masks it unless the caller's room handles the report or holds a
 * break-glass grant: `masked: true`, names null and the phone reduced to its last two digits ("+216••••••12").
 */
export type Reporter =
  | { kind: "citizen"; first_name: string | null; last_name: string | null; phone: string | null; masked?: boolean }
  | { kind: "anonymous"; masked?: boolean; first_name?: null; last_name?: null; phone?: string | null };

export interface StaffReportDetail extends StaffReport {
  history: HistoryEntry[];
  media: Media[];
  reporter: Reporter;
  /** Statuses reachable from the current one, computed by the server (authoritative). */
  allowed_transitions?: ReportStatus[];
  /** AI analysis (phase 3); null/absent before the first analysis. */
  analysis?: Analysis | null;
  /** Card of the reporting institution for responders (phase 4 §9); null when not reported by an institution. */
  organization_card?: OrganizationCard | null;
  // Phase 9 (§4.6).
  escalations?: Escalation[];
  /** Restricted (§1.3): null unless the caller may read sensitive data. */
  reporter_context?: ReporterContext | null;
  /** Phase B2: the reporter attached their medical file (opened on request, audited). */
  medical_attached?: boolean;
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
  /** Phase 5: bonus while the gouvernorat is at crisis or disaster level. */
  "op_level",
  /** Phase 6: strongest confirmed fire or smoke of the report (live stream or uploaded image); bonus. */
  "vision_fire",
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
  /** Words to hide on screen, as `StaffReport.text_masks`. */
  text_masks?: [number, number, "hide" | "flag"][];
  translation_ar_masks?: [number, number, "hide" | "flag"][];
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
  // Phase 5 (interventions, §4)
  "card_updated",
  "note",
  "assignment_created",
  "assignment_status",
  "callout_sent",
  "callout_accepted",
  "callout_declined",
  "callout_cancelled",
  "evaluated",
  "level_changed",
  // Phase 9 (§5.5)
  ...PHASE9_TIMELINE_KINDS,
  // Phase P4a (staff app)
  ...CREW_TIMELINE_KINDS,
  // Phase L1b: the hospital the room added (nearest on the road).
  "hospital_chosen",
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
  // Phase 5 (§4); absent from older payloads.
  title?: string | null;
  classification?: string | null;
  op_level?: OpLevel;
  assignments_active?: number;
  callouts_open?: number;
  // Phase 9 (§5.5): `gouvernorat_code` is the lead gouvernorat.
  lead_gouvernorat_code?: number | null;
  participating_gouvernorats?: number[];
  command_level?: CommandLevel;
  /** Not listed in §5.5 (stored by §5.1): read when the API sends them. */
  command_level_manual?: boolean;
  command_level_reason?: string | null;
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
  // Phase 5 (§4).
  assignments?: Assignment[];
  callouts?: Callout[];
  evaluation?: Evaluation | null;
  // Phase 9 (§5.5).
  resource_requests?: ResourceRequest[];
  // Phase P4a: written from the team leaders' phones.
  field_reports?: FieldReport[];
  casualties?: Casualties;
  transports?: Transport[];
  alerts?: CrewAlert[];
  attachments?: FieldAttachment[];
}

export type IncidentLinkBody =
  | { action: "accept_suggestion" }
  | { action: "link"; incident_id: string }
  /** `override_reason` (5–500 characters) creates the incident despite `409 possible_duplicate` (phase 9 §5.2). */
  | { action: "new"; override_reason?: string };

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
  /** AI-01: each suggestion of the local model in the operations can be switched off (design-l5.md §2.3). */
  assist?: {
    plan_reading: boolean;
    programme_suggestions?: boolean;
    anomalies?: boolean;
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
  /** Institutions waiting for a registration review, in scope (phase 4). */
  orgs_pending_review?: number;
  /** Certificates waiting for review, in scope (phase 4). */
  certificates_submitted?: number;
}

export interface Gouvernorat {
  code: number;
  iso_code: string;
  name: string;
  name_ar: string;
  name_fr: string;
  /** English name (phase 9 §8, `geo.gouvernorat.name_en`); absent from older payloads. */
  name_en?: string | null;
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

// ---------- Institutions (phase 4, FR-B-001…FR-B-011, FR-C-05) ----------

export function isOneOf<T extends string>(list: readonly T[], v: unknown): v is T {
  return typeof v === "string" && (list as readonly string[]).includes(v);
}

export const ORG_STATUSES = ["pending_review", "active", "rejected", "suspended"] as const;
export type OrgStatus = (typeof ORG_STATUSES)[number];

export const ORG_KINDS = [
  "health",
  "industrial",
  "energy",
  "tourism",
  "education",
  "social_care",
  "public_admin",
  "culture_sport",
  "commercial",
  "transport",
  "religious",
  "other",
] as const;
export type OrgKind = (typeof ORG_KINDS)[number];

export const ORG_FAMILIES = ["high_rise", "industrial", "erp", "workplace"] as const;
export type OrgFamily = (typeof ORG_FAMILIES)[number];

/** Codes of `classification.required` and `completeness.missing` (§1). */
export const REQUIREMENTS = [
  "safety_file",
  "safety_plan",
  "safety_team",
  "training",
  "hazmat_sds",
  "equipment",
  "evacuation_points",
] as const;
export type Requirement = (typeof REQUIREMENTS)[number];

/** Alert kinds named by the contract example; others are shown with a generic label. */
export const ORG_ALERT_KINDS = [
  "training_expired",
  "training_expiring",
  "maintenance_overdue",
  "maintenance_due_soon",
  // Phase P3a: the current certificate.
  "certificate_expiring",
  "certificate_expired",
  "certificate_needs_update",
  // Phase P3b: a visit to come, reservations' deadlines, the prevention certificate.
  "visit_scheduled",
  "reservation_due_soon",
  "reservation_overdue",
  "prevention_expiring",
  "prevention_expired",
] as const;

export const CERTIFICATE_STATUSES = ["draft", "submitted", "approved", "rejected", "revoked"] as const;
export type CertificateStatus = (typeof CERTIFICATE_STATUSES)[number];
/** `certificate_status` of a StaffOrg and the `certificate=` list filter. */
export const ORG_CERTIFICATE_STATES = ["none", ...CERTIFICATE_STATUSES, "expired"] as const;
export type OrgCertificateState = (typeof ORG_CERTIFICATE_STATES)[number];

export const TEAM_ROLES = ["representative", "member"] as const;
export const TRAINING_STATUSES = ["valid", "expiring", "expired", "unknown"] as const;
export type TrainingStatus = (typeof TRAINING_STATUSES)[number];
export const EQUIPMENT_KINDS = [
  "extinguisher",
  "fire_hose_reel",
  "sprinkler",
  "smoke_detector",
  "alarm_panel",
  "emergency_lighting",
  "fire_door",
  "other",
] as const;
export const MAINTENANCE_STATUSES = ["ok", "due_soon", "overdue", "unknown"] as const;
export type MaintenanceStatus = (typeof MAINTENANCE_STATUSES)[number];
export const HAZMAT_UNITS = ["kg", "t", "l", "m3"] as const;
export const FEATURE_KINDS = ["evacuation_point", "water_point", "alarm"] as const;
export type FeatureKind = (typeof FEATURE_KINDS)[number];
export const DOCUMENT_KINDS = ["safety_file", "safety_plan", "sds", "other"] as const;
export const MEMBER_ROLES = ["admin", "editor", "member"] as const;
/** `reason` of the sensitive_sites priority component (§10). */
export const SENSITIVE_REASONS = ["hazmat", "high_rise", "large_public", "public", "nearby"] as const;

/** Registration review decisions (§9) and the institution statuses they apply to. */
export const ORG_DECISIONS = ["approve", "reject", "suspend", "reinstate"] as const;
export type OrgDecision = (typeof ORG_DECISIONS)[number];

export interface OrgRef {
  id: string;
  name: string;
  kind?: string;
}

export interface Classification {
  family: string;
  /** ERP category 1–5, null for the other families. */
  category: number | null;
  high_rise?: boolean;
  required?: string[];
  /** Thresholds are a working model to be validated against the official text. */
  provisional?: boolean;
}

export interface Completeness {
  ok: boolean;
  missing: string[];
}

export interface OrgAlert {
  kind: string;
  ref: string | null;
  since: string | null;
}

export interface Person {
  full_name: string | null;
  phone: string | null;
  email?: string | null;
}

export interface TeamMember {
  id: string;
  full_name: string;
  team_role: string;
  position: string | null;
  phone: string | null;
  email: string | null;
  last_training_on: string | null;
  training_valid_months: number | null;
  training_status: string;
  training_expires_on: string | null;
}

export interface Hazmat {
  id?: string;
  name: string;
  un_number: string | null;
  hazard_class: string | null;
  quantity: number | null;
  unit: string | null;
  storage_location: string | null;
  sds_document_id?: string | null;
}

export interface Equipment {
  id: string;
  kind: string;
  count: number | null;
  location: string | null;
  last_maintenance_on: string | null;
  maintenance_interval_months: number | null;
  maintenance_status: string;
  next_maintenance_on: string | null;
}

export interface MapFeature {
  id: string;
  kind: string;
  label: string | null;
  location: { lat: number; lon: number };
}

export interface DocumentVersion {
  version: number;
  filename: string | null;
  content_type: string | null;
  bytes: number | null;
  sha256: string | null;
  status: string;
  uploaded_at: string | null;
  uploaded_by: string | null;
  note: string | null;
}

export interface OrgDocument {
  id: string;
  kind: string;
  title: string;
  current_version: DocumentVersion | null;
  versions_count: number;
  /** Not in the contract: used when the server inlines the history in the staff detail. */
  versions?: DocumentVersion[];
}

export interface Certificate {
  id: string;
  code: string;
  /** Phase P3b: the safety self-assessment, or the prevention certificate issued after a visit. */
  kind?: "safety" | "prevention";
  status: CertificateStatus;
  superseded: boolean;
  created_at: string;
  submitted_at: string | null;
  reviewed_at: string | null;
  review_reason: string | null;
  valid_until: string | null;
  fingerprint: string | null;
  pdf_sha256: string | null;
  /** Phase 10 §4.1: signing key, and the revocation by an auditor. */
  key_id?: string | null;
  revoked_at?: string | null;
  revoke_reason?: string | null;
  verify_url: string | null;
  /** Phase P3a, on the current approved certificate only: substantive changes since it was certified. */
  needs_update?: boolean | null;
  changes?: CertificateChange[];
  stamps?: CertificateStamp[];
}

/** docs/phase-p3/design-certificates.md §3.4 */
export const CHANGE_SECTIONS = [
  "identity",
  "building",
  "classification",
  "hazmat",
  "documents",
  "safety_team",
  "evacuation",
] as const;
export type ChangeSection = (typeof CHANGE_SECTIONS)[number];

export interface CertificateChange {
  section: ChangeSection;
  field: string;
  certified: unknown;
  current: unknown;
}

/** A paper certificate stamped by hand at a regional administration (phase P3a). */
export interface CertificateStamp {
  id: string;
  place: string;
  gouvernorat_code: number | null;
  stamped_on: string;
  note: string | null;
  stamped_by_name: string | null;
  recorded_at: string;
  has_photo: boolean;
  changes: CertificateChange[];
}

export interface StampBody {
  place: string;
  stamped_on: string;
  note?: string | null;
}

export const COUNTER_REASONS = ["not_approved", "revoked", "superseded", "expired", "signature", "org_inactive"] as const;
export type CounterReason = (typeof COUNTER_REASONS)[number];

/** GET /staff/certificates/lookup: what the agent at the counter sees. */
export interface CounterView {
  certificate: Certificate;
  valid: boolean;
  reasons: CounterReason[];
  signature_valid: boolean;
  can_stamp: boolean;
  org_id: string;
  org_name: string;
  org_kind: string;
  org_status: string;
  org_address: string | null;
  gouvernorat_code: number | null;
}

export interface StaffOrgMember {
  display_name: string | null;
  email: string | null;
  role: string;
}

/** Row of `GET /api/v1/staff/orgs` (§9) and payload of the `org.updated` live event. */
export interface StaffOrg {
  id: string;
  name: string;
  kind: OrgKind;
  status: OrgStatus;
  identifier_type: string;
  identifier: string;
  gouvernorat_code: number | null;
  capacity: number | null;
  location: { lat: number; lon: number } | null;
  classification: Classification | null;
  hazmat_count: number;
  alerts_count: number;
  certificate_status: OrgCertificateState;
  certificate_valid_until: string | null;
  created_at: string;
  /** Migrated from a kind with no match (P2a): the auditor picks the right kind on approval. */
  kind_review?: boolean;
}

/** `GET /api/v1/staff/orgs/{id}`: the Organization card (without my_role) and its registers. Audited. */
export interface StaffOrgDetail {
  id: string;
  status: OrgStatus;
  version?: number;
  name: string;
  kind: OrgKind;
  identifier_type: string;
  identifier: string;
  activity_sector: string | null;
  activity_type: string | null;
  capacity: number | null;
  floors: number | null;
  height_m: number | null;
  receives_public: boolean | null;
  address: string | null;
  location: { lat: number; lon: number } | null;
  gouvernorat_code: number | null;
  delegation_id: number | null;
  manager: Person | null;
  contact_email: string | null;
  contact_phone: string | null;
  classification: Classification | null;
  completeness: Completeness | null;
  alerts: OrgAlert[];
  review: { reason: string | null; at: string | null } | null;
  created_at: string;
  updated_at: string;
  /** P2a: share of the safety requirements met, in percent. */
  readiness?: number;
  /** P2a: the answers to the kind's fields the auditor may see (public and institution/Office). */
  kind_fields?: Record<string, KindFieldValue>;
  kind_review?: boolean;
  team: TeamMember[];
  hazmat: Hazmat[];
  equipment: Equipment[];
  features: MapFeature[];
  documents: OrgDocument[];
  members: StaffOrgMember[];
  certificates: Certificate[];
  /** Phase P2b: drills held and public events declared, latest first. */
  activities?: OrgActivity[];
  /** Phase P2b: maintenance log of the equipment, with its photos. */
  maintenance?: OrgMaintenance[];
}

/** Phase P2b: a drill held or a public event declared by an institution. */
export interface OrgActivity {
  id: string;
  kind: "drill" | "event";
  title: string;
  starts_on: string;
  ends_on: string | null;
  participants: number | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
}

/** `GET /api/v1/staff/org-events`: public events not over yet, soonest first. */
export interface StaffOrgEvent extends OrgActivity {
  org_id: string;
  org_name: string;
  org_kind: OrgKind;
  gouvernorat_code: number | null;
}

/** Phase P2b: one maintenance of an equipment; `photo_version` once the photo is stored. */
export interface OrgMaintenance {
  id: string;
  equipment_id: string;
  done_on: string;
  note: string | null;
  document_id: string | null;
  photo_version: number | null;
  recorded_by: string | null;
  recorded_at: string;
}

/** `organization_card` of a StaffReportDetail (§9): what responders need on the way. */
export interface OrganizationCard {
  id: string;
  name: string;
  kind: string;
  capacity: number | null;
  address: string | null;
  location: { lat: number; lon: number } | null;
  classification: Classification | null;
  representative: { full_name: string | null; phone: string | null } | null;
  hazmat: Hazmat[];
  features: MapFeature[];
  /** P2a: every answer to the kind's fields, those for a nearby report included (the view is logged). */
  kind_fields?: Record<string, KindFieldValue>;
}

/** Row of the certificate review queue `GET /api/v1/staff/certificates` (oldest submission first). */
export interface QueueCertificate {
  id: string;
  code: string;
  status: CertificateStatus;
  org_id: string;
  org_name: string;
  gouvernorat_code: number | null;
  submitted_at: string | null;
  completeness: Completeness | null;
}

/** Payload of the `certificate.updated` live event. */
export interface CertificateEvent {
  id: string;
  code: string;
  status: CertificateStatus;
  org_id: string;
  org_name: string;
  gouvernorat_code: number | null;
}

/** `kind` (P2a): the auditor sets the right kind, on approval only. */
export type OrgReviewBody = { decision: OrgDecision; reason?: string; kind?: OrgKind };
export type CertificateReviewBody =
  | { decision: "approve"; valid_until: string; reason?: string }
  | { decision: "reject"; reason: string };

/** `GET /api/v1/staff/orgs/map` (map layer «المؤسسات», FR-C-10). */
export interface OrgMapProperties {
  id: string;
  name: string;
  kind: string;
  capacity: number | null;
  hazmat_count: number;
  category: number | null;
  family: string | null;
}

export interface OrgMapFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: OrgMapProperties;
  id?: string | number;
}

export interface OrgMapCollection {
  type: "FeatureCollection";
  features: OrgMapFeature[];
}

export interface DownloadLink {
  url: string;
}
