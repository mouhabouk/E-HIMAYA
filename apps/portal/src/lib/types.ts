/** Types mirroring docs/api/phase-4-contract.md (institutions) and phase-2-contract.md (reports, consents). */

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

export const TEXT_LANGS = ["ar", "fr", "en"] as const;
export type TextLang = (typeof TEXT_LANGS)[number];

export interface GeoPoint {
  lat: number;
  lon: number;
}

// ---------------------------------------------------------------- institutions (§1)

export const ORG_STATUSES = ["pending_review", "active", "rejected", "suspended"] as const;
export type OrgStatus = (typeof ORG_STATUSES)[number];

export const ORG_KINDS = ["industrial", "educational", "hotel", "government", "private", "other"] as const;
export type OrgKind = (typeof ORG_KINDS)[number];

export const ORG_ROLES = ["admin", "editor", "member"] as const;
export type OrgRole = (typeof ORG_ROLES)[number];

export const IDENTIFIER_TYPES = ["mf", "rne"] as const;
export type IdentifierType = (typeof IDENTIFIER_TYPES)[number];

export const FAMILIES = ["high_rise", "industrial", "erp", "workplace"] as const;
export type Family = (typeof FAMILIES)[number];

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

/** Alert kinds: the two of the contract's example plus the "soon" variants of the same rules (§3, §4). */
export const ALERT_KINDS = ["training_expired", "training_expiring", "maintenance_overdue", "maintenance_due_soon"] as const;
export type AlertKind = (typeof ALERT_KINDS)[number];

export interface Classification {
  family: Family;
  category: number | null;
  high_rise: boolean;
  required: string[];
  provisional: boolean;
}

export interface Alert {
  kind: string;
  ref: string | null;
  since: string | null;
}

export interface Person {
  full_name: string;
  phone: string;
  email: string | null;
}

/** Editable card fields (body of POST /orgs and, with `version`, PUT /orgs/{id}). */
export interface OrgCard {
  name: string;
  kind: OrgKind;
  identifier_type: IdentifierType;
  identifier: string;
  activity_sector: string | null;
  activity_type: string | null;
  capacity: number | null;
  floors: number | null;
  height_m: number | null;
  receives_public: boolean;
  address: string;
  location: GeoPoint;
  manager: Person;
  contact_email: string | null;
  contact_phone: string | null;
}

export interface Organization extends OrgCard {
  id: string;
  status: OrgStatus;
  version: number;
  gouvernorat_code: number | null;
  delegation_id: number | null;
  classification: Classification;
  completeness: { ok: boolean; missing: string[] };
  alerts: Alert[];
  my_role: OrgRole;
  review: { reason: string | null; at: string | null };
  created_at: string;
  updated_at: string;
}

export interface MyOrg {
  id: string;
  name: string;
  kind: OrgKind;
  status: OrgStatus;
  my_role: OrgRole;
  alerts_count: number;
}

// ---------------------------------------------------------------- members (§2)

export interface Member {
  user_id: string;
  display_name: string | null;
  email: string | null;
  role: OrgRole;
  joined_at: string;
}

export interface Invitation {
  id: string;
  email: string;
  role: OrgRole;
  expires_at: string;
}

export interface CreatedInvitation extends Invitation {
  token: string;
  accept_url: string;
}

export interface InvitationPreview {
  org_name: string;
  role: OrgRole;
  email: string;
  expires_at: string;
}

// ---------------------------------------------------------------- registers (§3, §4, §5)

export const TEAM_ROLES = ["representative", "member"] as const;
export type TeamRole = (typeof TEAM_ROLES)[number];
export const TRAINING_STATUSES = ["valid", "expiring", "expired", "unknown"] as const;
export type TrainingStatus = (typeof TRAINING_STATUSES)[number];

export interface TeamMemberInput {
  full_name: string;
  team_role: TeamRole;
  position: string | null;
  phone: string | null;
  email: string | null;
  last_training_on: string | null;
  training_valid_months: number;
}

export interface TeamMember extends TeamMemberInput {
  id: string;
  training_status: TrainingStatus;
  training_expires_on: string | null;
}

export const HAZMAT_UNITS = ["kg", "t", "l", "m3"] as const;
export type HazmatUnit = (typeof HAZMAT_UNITS)[number];

export interface HazmatInput {
  name: string;
  un_number: string | null;
  hazard_class: string | null;
  quantity: number;
  unit: HazmatUnit;
  storage_location: string | null;
  sds_document_id: string | null;
}

export interface Hazmat extends HazmatInput {
  id: string;
}

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
export type EquipmentKind = (typeof EQUIPMENT_KINDS)[number];
export const MAINTENANCE_STATUSES = ["ok", "due_soon", "overdue", "unknown"] as const;
export type MaintenanceStatus = (typeof MAINTENANCE_STATUSES)[number];

export interface EquipmentInput {
  kind: EquipmentKind;
  count: number;
  location: string | null;
  last_maintenance_on: string | null;
  maintenance_interval_months: number;
}

export interface Equipment extends EquipmentInput {
  id: string;
  maintenance_status: MaintenanceStatus;
  next_maintenance_on: string | null;
}

export const FEATURE_KINDS = ["evacuation_point", "water_point", "alarm"] as const;
export type FeatureKind = (typeof FEATURE_KINDS)[number];

export interface MapFeatureInput {
  kind: FeatureKind;
  label: string;
  location: GeoPoint;
}

export interface MapFeature extends MapFeatureInput {
  id: string;
}

// ---------------------------------------------------------------- documents (§6)

export const DOCUMENT_KINDS = ["safety_file", "safety_plan", "sds", "other"] as const;
export type DocumentKind = (typeof DOCUMENT_KINDS)[number];
export const VERSION_STATUSES = ["uploading", "verifying", "stored", "rejected"] as const;
export type VersionStatus = (typeof VERSION_STATUSES)[number];

export interface DocumentVersion {
  version: number;
  filename: string;
  content_type: string;
  bytes: number | null;
  sha256: string;
  status: VersionStatus;
  uploaded_at: string;
  uploaded_by: string | null;
  note: string | null;
}

export interface OrgDocument {
  id: string;
  kind: DocumentKind;
  title: string;
  current_version: DocumentVersion | null;
  versions_count: number;
}

// ---------------------------------------------------------------- certificates (§7)

export const CERTIFICATE_STATUSES = ["draft", "submitted", "approved", "rejected"] as const;
export type CertificateStatus = (typeof CERTIFICATE_STATUSES)[number];

export interface Certificate {
  id: string;
  code: string;
  status: CertificateStatus;
  superseded: boolean;
  created_at: string;
  submitted_at: string | null;
  reviewed_at: string | null;
  review_reason: string | null;
  valid_until: string | null;
  fingerprint: string;
  pdf_sha256: string | null;
  verify_url: string;
}

export interface PublicCertificate {
  code: string;
  status: CertificateStatus;
  valid: boolean;
  superseded: boolean;
  org_name: string;
  org_kind: OrgKind;
  gouvernorat_code: number | null;
  classification: { family: Family; category: number | null };
  issued_at: string | null;
  valid_until: string | null;
  fingerprint: string;
  pdf_sha256: string | null;
  signature_valid: boolean | null;
}

// ---------------------------------------------------------------- reports (§8, phase 2 §3)

export interface OrgReport {
  id: string;
  tracking_code: string;
  category: Category;
  status: ReportStatus;
  text: string | null;
  received_at: string;
  updated_at: string;
  reporter_display_name: string | null;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface NewReport {
  client_uuid: string;
  category: Category;
  text: string | null;
  lang: TextLang;
  location: GeoPoint & { accuracy_m?: number | null };
  created_at: string;
  organization_id: string;
}

export interface Report {
  id: string;
  tracking_code: string;
  client_uuid: string;
  category: Category;
  status: ReportStatus;
  received_at: string;
  organization: { id: string; name: string } | null;
}

export interface Gouvernorat {
  code: number;
  name_ar: string;
  name_fr: string;
}

export function isOneOf<T extends string>(list: readonly T[], v: unknown): v is T {
  return typeof v === "string" && (list as readonly string[]).includes(v);
}
