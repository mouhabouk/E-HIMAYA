/** Types of the administrator's permissions API (L4, docs/phase-l/design-l4.md §8). */

export type FeatureKind = "page" | "tab" | "button";
export type Effect = "grant" | "hide";
export type TargetKind = "user" | "role";

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
}

export interface PreviewRow {
  key: string;
  default: boolean;
  hidden: boolean;
  granted: boolean;
  refused: string | null;
  open: boolean;
}
