/**
 * Types mirroring docs/api/phase-9-contract.md (central and regional rooms, national settings, break-glass,
 * regional account administration, scoped audit). Fields added to existing payloads are optional on those types
 * (types.ts) so older payloads keep rendering; the shapes below are new responses.
 */
import type { Category, IncidentSummary } from "./types";

// ---------- §2 national settings ----------

export const SLA_BANDS = ["critical", "high", "normal", "low"] as const;
export type SlaBand = (typeof SLA_BANDS)[number];

/** Lower bounds of the priority score for the bands above `low` (`sla.bands`). */
export interface SlaBandBounds {
  critical: number;
  high: number;
  normal: number;
}
export type SlaClaimDelays = Record<SlaBand, number>;

export const SETTING_KEYS = [
  "sla.bands",
  "sla.claim_delay_s",
  "sla.enforced_since",
  "anonymous.report_quota",
  "geo.max_trusted_accuracy_m",
  "notify.real_send_enabled",
] as const;
export type SettingKey = (typeof SETTING_KEYS)[number];

export interface PlatformSetting {
  key: string;
  value: unknown;
  version: number;
  updated_by_name: string | null;
  updated_at: string | null;
  /** Computed by the API for the caller (role, national scope, key). The page is read-only otherwise. */
  editable: boolean;
}

export interface SettingUpdateBody {
  value: unknown;
  version: number;
  /** 5–500 characters, audited. */
  reason: string;
}

/** Defaults of §2, used only until the settings are loaded. */
export const DEFAULT_SLA_BANDS: SlaBandBounds = { critical: 85, high: 70, normal: 40 };
export const DEFAULT_CLAIM_DELAYS: SlaClaimDelays = { critical: 60, high: 90, normal: 120, low: 180 };

// ---------- §4 jurisdiction, claim, SLA, escalation ----------

export const GEO_STATES = ["trusted", "pending", "contradictory", "verified"] as const;
export type GeoState = (typeof GEO_STATES)[number];

export const GEO_REASONS = ["accuracy_crosses_border", "outside_boundaries", "low_accuracy", "accuracy_missing"] as const;

export const ESCALATION_STATES = [
  "none",
  "late",
  "central_responding",
  "referred",
  "referral_accepted",
  "referral_refused",
] as const;
export type EscalationState = (typeof ESCALATION_STATES)[number];

export const ESCALATION_KINDS = [
  "late",
  "central_claim",
  "referral",
  "referral_accepted",
  "referral_refused",
  "geo_verified",
  "claim_released",
] as const;
export type EscalationKind = (typeof ESCALATION_KINDS)[number];

/** `central` or `g:<gouvernorat code>`. */
export type Room = string;

export interface Escalation {
  kind: EscalationKind;
  from_room: Room | null;
  to_room: Room | null;
  actor_name: string | null;
  at: string;
  reason: string | null;
}

export interface ReporterContext {
  reporter_gouvernorat_code: number | null;
  source: "profile" | "none";
}

export interface ReferBody {
  to_gouvernorat_code: number;
  reason: string;
  directive: { title: string; body: string; urgency: "normal" | "urgent" } | null;
}

/** Body of `409 already_claimed`. */
export interface AlreadyClaimed {
  detail: "already_claimed";
  claimed_room: Room;
  claimed_by_name: string | null;
}

// ---------- §5 incidents across gouvernorats ----------

export const COMMAND_LEVELS = ["regional", "central"] as const;
export type CommandLevel = (typeof COMMAND_LEVELS)[number];

export const PHASE9_TIMELINE_KINDS = [
  "participant_added",
  "participant_removed",
  "lead_transferred",
  "command_level_changed",
  "duplicate_override",
  "resource_requested",
  "resource_request_approved",
  "resource_request_refused",
  "resource_request_cancelled",
  "report_late",
  "report_central_claim",
  "report_referred",
  "report_referral_accepted",
  "report_referral_refused",
  "report_geo_verified",
] as const;

/**
 * `GET /staff/reports/{id}/nearby-incidents`: a summary only (§5.2). The contract names the fields "lead" and
 * "participants"; the IncidentSummary names (`lead_gouvernorat_code`, `participating_gouvernorats`) are read first.
 */
export interface NearbyIncident {
  id: string;
  category: Category;
  lead_gouvernorat_code?: number | null;
  participating_gouvernorats?: number[];
  lead?: number | null;
  participants?: number[];
  centroid: { lat: number; lon: number } | null;
  severity: number | null;
  opened_at: string;
  report_count: number;
  /** Distance from the report, when the API gives it. */
  distance_m?: number | null;
}

/** Body of `409 possible_duplicate`. */
export interface PossibleDuplicate {
  detail: "possible_duplicate";
  incident_ids: string[];
}

export const RESOURCE_REQUEST_STATUSES = ["pending", "approved", "refused", "cancelled"] as const;
export type ResourceRequestStatus = (typeof RESOURCE_REQUEST_STATUSES)[number];
export type ResourceRequestDirection = "incoming" | "outgoing";

export interface ResourceRequest {
  id: string;
  incident_id: string;
  from_room: Room;
  to_gouvernorat_code: number;
  resource_id: string | null;
  resource_kind: string | null;
  quantity: number;
  reason: string;
  status: ResourceRequestStatus;
  requested_by_name: string | null;
  requested_at: string;
  decided_by_name: string | null;
  decided_at: string | null;
  decision_note: string | null;
  /** Incident category and command level when the API joins them (not fixed by the contract). */
  incident_category?: Category | null;
  incident_command_level?: CommandLevel | null;
}

export interface ResourceRequestBody {
  to_gouvernorat_code: number;
  resource_id: string | null;
  resource_kind: string | null;
  quantity: number;
  reason: string;
}

/** Phase 9 fields of IncidentSummary (§5.5), merged into types.ts. */
export type IncidentScope = Pick<IncidentSummary, "lead_gouvernorat_code" | "participating_gouvernorats" | "command_level">;

// ---------- §6 break-glass and account administration ----------

export const BREAKGLASS_TARGETS = ["report", "incident", "gouvernorat"] as const;
export type BreakGlassTarget = (typeof BREAKGLASS_TARGETS)[number];

export const BREAKGLASS_STATUSES = ["active", "expired", "pending_review", "reviewed"] as const;
export type BreakGlassStatus = (typeof BREAKGLASS_STATUSES)[number];

export const REVIEW_OUTCOMES = ["justified", "unjustified"] as const;
export type ReviewOutcome = (typeof REVIEW_OUTCOMES)[number];

export const BREAKGLASS_MIN_JUSTIFICATION = 20;
export const BREAKGLASS_MAX_JUSTIFICATION = 1000;
export const BREAKGLASS_DURATIONS = [15, 30, 60, 120, 240] as const;

export interface BreakGlassGrant {
  id: string;
  subject: string;
  subject_name: string | null;
  target_kind: BreakGlassTarget;
  target_id: string | null;
  gouvernorat_code: number | null;
  justification: string;
  granted_at: string;
  expires_at: string;
  /** End of the grant: expiry or revocation (null while active). */
  ended_at?: string | null;
  revoked_at: string | null;
  /** Computed by the API; the page falls back to the dates when absent. */
  state?: "active" | "pending_review" | "reviewed";
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_outcome: ReviewOutcome | null;
  review_note: string | null;
}

export interface BreakGlassBody {
  target_kind: BreakGlassTarget;
  target_id: string | null;
  gouvernorat_code: number | null;
  justification: string;
  duration_min: number;
}

export const SCOPE_LEVELS = ["gouvernorat", "national"] as const;
export type ScopeLevel = (typeof SCOPE_LEVELS)[number];

export interface StaffAccount {
  id: string;
  username: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  enabled: boolean;
  roles: string[];
  scope_level: ScopeLevel | null;
  gouvernorat_code: number | null;
  mfa_configured: boolean;
}

export interface AccountCreateBody {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  roles: string[];
  scope_level: ScopeLevel;
  gouvernorat_code: number | null;
}

export interface AccountPatchBody {
  roles?: string[];
  enabled?: boolean;
}

export interface AccountFilters {
  gouvernorat?: number | null;
  role?: string;
  q?: string;
}

// ---------- §7 scoped audit ----------

/** Redacted entry of `GET /staff/audit` (§7.3): no actor id and no hash; details reduced to a whitelist. */
export interface ScopedAuditEntry {
  seq?: number;
  at: string;
  action: string;
  actor_name: string | null;
  target: string | null;
  reason: string | null;
  details: Record<string, unknown>;
  gouvernorats?: number[];
}

export interface AuditFilters {
  action?: string;
  from?: string;
  to?: string;
}
