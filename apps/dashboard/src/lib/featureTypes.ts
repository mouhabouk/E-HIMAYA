/** Types of the administrator's permissions API (L4, docs/phase-l/design-l4.md §8). */

export type FeatureKind = "page" | "tab" | "button" | "system";
/** «suspend» (2026-11-13): a whole system closed for a while, with a message shown in its place. */
export type Effect = "grant" | "hide" | "suspend";
export type TargetKind = "user" | "role" | "everyone";

export interface Feature {
  key: string;
  kind: FeatureKind;
  names: { ar: string; fr: string; en: string };
  parent: string | null;
  group: string | null;
  nav: string | null;
  flags: string[];
  roles: string[];
  act_as: string | null;
  grantable: boolean;
  routes: string[];
}

export interface MyFeatures {
  granted: string[];
  hidden: string[];
  /** Absent from an older API answer. */
  lent?: Record<string, string>;
  /** Phase 5: the system administrator's message for the dashboard. */
  announcement?: Announcement | null;
  /** The systems suspended for the caller, with the administrator's message (absent from an older API answer). */
  suspended?: Record<string, SystemMessage>;
}

export interface SystemMessage {
  ar: string;
  fr: string;
  en: string;
}

/** The system administrator's message (phase 5), shown at once. */
export interface Announcement {
  tone: "info" | "warn";
  ar: string;
  fr: string;
  en: string;
}

export interface FeatureRule {
  id: string;
  feature_key: string;
  effect: Effect;
  target_kind: TargetKind;
  target: string;
  target_name: string | null;
  gouvernorat_code: number | null;
  reason: string;
  starts_at: string | null;
  ends_at: string | null;
  created_by_name: string | null;
  created_at: string;
  revoked_at: string | null;
  revoked_by_name: string | null;
  revoke_reason: string | null;
  message?: SystemMessage | null;
  state: "active" | "scheduled" | "ended" | "revoked";
}

export interface FeatureRuleIn {
  feature_key: string;
  effect: Effect;
  target_kind: TargetKind;
  target: string;
  target_name?: string | null;
  gouvernorat_code?: number | null;
  reason: string;
  starts_at?: string | null;
  ends_at?: string | null;
  /** A «suspend» rule's message to the users of the system. */
  message?: SystemMessage | null;
}

/** One of the 20 systems of the menu, its pages and the rules set on it as a whole (2026-11-13). */
export interface FeatureSystem {
  key: string;
  number: number;
  block: string;
  names: { ar: string; fr: string; en: string };
  pages: { key: string; kind: "page" | "tab"; names: { ar: string; fr: string; en: string }; nav: string | null; flags: string[] }[];
  planned: string[];
  rules: FeatureRule[];
}

export interface SystemGrantIn {
  mode: "read" | "write";
  target_kind: "user" | "role";
  target: string;
  target_name?: string | null;
  gouvernorat_code?: number | null;
  reason: string;
  starts_at?: string | null;
  ends_at?: string | null;
}

export interface SystemGrantOut {
  id: string;
  features: string[];
  skipped?: { feature_key: string; reason: string }[];
}

export interface PreviewRow {
  key: string;
  default: boolean;
  hidden: boolean;
  granted: boolean;
  refused: string | null;
  open: boolean;
}
