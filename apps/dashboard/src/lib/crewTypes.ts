/** Staff app of the team leaders (phase P4a, docs/phase-p4/design-staff.md): what the room sees of it. */
import type { ResourceKind } from "./opsTypes";
import type { Category } from "./types";

/** Timeline events written from the leader's phone. */
export const CREW_TIMELINE_KINDS = ["crew_ack", "field_report", "casualties", "transport"] as const;

export const TRIAGES = ["red", "yellow", "green", "black"] as const;
export type Triage = (typeof TRIAGES)[number];
export const AGE_BANDS = ["child", "adult", "elderly", "unknown"] as const;
export const SEXES = ["female", "male", "unknown"] as const;
export const COUNTERS = ["injured", "deceased", "rescued", "trapped"] as const;
export type Counter = (typeof COUNTERS)[number];
export const SEVERITIES = [1, 2, 3, 4] as const;

/** The shift holding the vehicle of an assignment. */
export interface CrewRef {
  shift_id: string;
  leader_name: string | null;
  crew_size: number;
  acknowledged_at: string | null;
}

export interface FieldReport {
  id: string;
  assignment_id: string;
  resource_label: string | null;
  category: Category;
  classification: string | null;
  severity: number;
  backup_needed: boolean;
  backup_note: string | null;
  crew_danger: boolean;
  author_name: string | null;
  device_at: string | null;
  created_at: string;
}

export type Casualties = Record<Counter, number> & { updated_by: string | null; updated_at: string | null };

export interface Transport {
  id: string;
  assignment_id: string;
  triage: Triage;
  age_band: (typeof AGE_BANDS)[number];
  sex: (typeof SEXES)[number];
  hospital: string;
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
