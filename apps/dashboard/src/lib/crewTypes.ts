/** Staff app of the team leaders (phase P4a, docs/phase-p4/design-staff.md): what the room sees of it. */
import type { ResourceKind } from "./opsTypes";
import type { Category } from "./types";

/** Timeline events written from the leader's phone (P4a, then P4b: alerts, attachments, detailed reports). */
export const CREW_TIMELINE_KINDS = [
  "crew_ack",
  "field_report",
  "casualties",
  "transport",
  "crew_alert",
  "crew_alert_seen",
  "field_attachment",
  "detailed_report",
] as const;

export const TRIAGES = ["red", "yellow", "green", "black"] as const;
export type Triage = (typeof TRIAGES)[number];
/** Age bands of phase P4b; the first three of P4a ("child", "adult", "elderly") are still read. */
export const AGE_BANDS = [
  "under_12",
  "12_17",
  "18_29",
  "30_44",
  "45_59",
  "60_plus",
  "unknown",
  "child",
  "adult",
  "elderly",
] as const;
export const SEXES = ["female", "male", "unknown"] as const;
export const COUNTERS = ["injured_light", "injured_serious", "deceased", "rescued", "trapped"] as const;
export type Counter = (typeof COUNTERS)[number];
export const SEVERITIES = [1, 2, 3, 4] as const;
export const BACKUP_KINDS = [
  "fire_engine",
  "ambulance",
  "extrication",
  "ladder",
  "water_tanker",
  "hazmat",
  "police",
  "heavy_equipment",
] as const;
export const DANGER_KINDS = ["fire_spread", "collapse", "gas", "electricity", "violence", "traffic"] as const;

/** The shift holding the vehicle of an assignment. */
export interface CrewRef {
  shift_id: string;
  leader_name: string | null;
  crew_size: number;
  acknowledged_at: string | null;
  /** Backup and danger alerts of this assignment the room has not marked as seen. */
  unseen_alerts?: number;
}

/** A situation report (first, then updates) or a detailed report answering a template. */
export interface FieldReport {
  id: string;
  assignment_id: string;
  resource_label: string | null;
  kind?: "first" | "update" | "detailed";
  category: Category;
  classification: string | null;
  severity: number | null;
  backup_needed: boolean;
  backup_note: string | null;
  backup_kinds?: string[];
  crew_danger: boolean;
  template_id?: string | null;
  template_version?: number | null;
  answers?: Record<string, unknown> | null;
  note?: string | null;
  author_name: string | null;
  device_at: string | null;
  created_at: string;
}

export type Casualties = Record<Counter, number> & {
  transported?: number;
  updated_by: string | null;
  updated_at: string | null;
};

/** "Backup" or "danger to the crew" from a leader's phone, and when the room saw it. */
export interface CrewAlert {
  id: string;
  assignment_id: string;
  resource_label: string | null;
  kind: "backup" | "danger";
  items: string[];
  created_by_name: string | null;
  device_at: string | null;
  created_at: string;
  seen_by_name: string | null;
  seen_at: string | null;
}

/** A photo, a voice note or a short text from the scene; `url` is a short-lived link to the file. */
export interface FieldAttachment {
  id: string;
  assignment_id: string;
  kind: "photo" | "voice" | "text";
  body: string | null;
  content_type: string | null;
  bytes: number | null;
  duration_s: number | null;
  created_by_name: string | null;
  device_at: string | null;
  created_at: string;
  url?: string | null;
}

export type Lang = "ar" | "fr" | "en";
export type Localized = Partial<Record<Lang, string>>;
export const FIELD_TYPES = ["single", "multi", "yesno", "count"] as const;
export type FieldType = (typeof FIELD_TYPES)[number];

export interface TemplateOption {
  key: string;
  label: Localized;
}

/** One question of a detailed report, answered with a tap on the phone. */
export interface TemplateField {
  key: string;
  type: FieldType;
  label: Localized;
  options?: TemplateOption[];
  required?: boolean;
  unit?: Localized | null;
  max?: number | null;
}

export interface ReportTemplate {
  id: string;
  category: Category;
  classification: string | null;
  version: number;
  status: "draft" | "approved" | "retired";
  fields: TemplateField[];
  simulated: boolean;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
  approved_by_name: string | null;
  approved_at: string | null;
}

export interface Transport {
  id: string;
  assignment_id: string;
  triage: Triage;
  age_band: (typeof AGE_BANDS)[number];
  sex: (typeof SEXES)[number];
  hospital: string;
  hospital_ref?: string | null;
  created_by_name: string | null;
  device_at: string | null;
  created_at: string;
}

export interface ShiftRow {
  id: string;
  resource: { id: string; label: string; kind: ResourceKind; unit_name: string };
  crew_size: number;
  crew_names: string | null;
  started_at: string;
  ended_at: string | null;
  leader_name: string | null;
  gouvernorat_code: number;
  unseen_alerts?: number;
}

export interface CrewDevice {
  id: string;
  holder_name: string | null;
  label: string | null;
  platform: string;
  app_build: number | null;
  created_at: string;
  last_seen_at: string;
  revoked_at: string | null;
  on_shift: boolean;
  gouvernorat_code: number;
}
