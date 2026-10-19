import { CATEGORIES, PRIORITY_COMPONENTS, type AiSettings, type Category, type PriorityComponent } from "./types";

/**
 * Client-side validation of `PUT /api/v1/staff/ai/settings`, mirroring the API rules
 * (services/api/app/modules/ai/settings.py) so mistakes are caught before the 422.
 */

export interface AiSettingsForm {
  weights: Record<PriorityComponent, string>;
  category_severity: Record<Category, string>;
  suggestion_min_confidence: string;
  window_min: string;
  radius_m: Record<Category, string>;
  semantic_min_similarity: string;
  semantic_radius_m: string;
  semantic_window_min: string;
}

export type FieldError =
  | { key: "required" }
  | { key: "integer" }
  | { key: "range"; min: number; max: number }
  | { key: "allZero" };

/** Errors keyed by field path ("weights.lives", "radius_m.fire", "window_min", …). */
export type FormErrors = Partial<Record<string, FieldError>>;

interface Rule {
  min: number;
  max: number;
  integer: boolean;
}

export const RULES = {
  weight: { min: 0, max: 100, integer: true },
  severity: { min: 0, max: 1, integer: false },
  suggestion_min_confidence: { min: 0, max: 1, integer: false },
  window_min: { min: 5, max: 1440, integer: true },
  radius_m: { min: 10, max: 50_000, integer: true },
  semantic_min_similarity: { min: 0.5, max: 0.99, integer: false },
  semantic_radius_m: { min: 100, max: 50_000, integer: true },
  semantic_window_min: { min: 5, max: 2880, integer: true },
} as const satisfies Record<string, Rule>;

function mapRecord<K extends string, A, B>(keys: readonly K[], source: Record<K, A>, f: (a: A) => B): Record<K, B> {
  return Object.fromEntries(keys.map((k) => [k, f(source[k])])) as Record<K, B>;
}

export function toForm(s: AiSettings): AiSettingsForm {
  const str = (n: number | undefined) => (typeof n === "number" ? String(n) : "");
  return {
    weights: mapRecord(PRIORITY_COMPONENTS, s.priority.weights, str),
    category_severity: mapRecord(CATEGORIES, s.priority.category_severity, str),
    suggestion_min_confidence: str(s.priority.suggestion_min_confidence),
    window_min: str(s.grouping.window_min),
    radius_m: mapRecord(CATEGORIES, s.grouping.radius_m, str),
    semantic_min_similarity: str(s.grouping.semantic_min_similarity),
    semantic_radius_m: str(s.grouping.semantic_radius_m),
    semantic_window_min: str(s.grouping.semantic_window_min),
  };
}

/** Parse one field; returns the number or records the error under `path`. */
function check(raw: string, rule: Rule, path: string, errors: FormErrors): number {
  const text = raw.trim().replace(",", ".");
  const n = text === "" ? Number.NaN : Number(text);
  if (text === "" || !Number.isFinite(n)) {
    errors[path] = { key: "required" };
    return Number.NaN;
  }
  if (rule.integer && !Number.isInteger(n)) {
    errors[path] = { key: "integer" };
    return n;
  }
  if (n < rule.min || n > rule.max) errors[path] = { key: "range", min: rule.min, max: rule.max };
  return n;
}

export function validateAiSettings(form: AiSettingsForm): { settings: AiSettings | null; errors: FormErrors } {
  const errors: FormErrors = {};
  const weights = Object.fromEntries(
    PRIORITY_COMPONENTS.map((k) => [k, check(form.weights[k], RULES.weight, `weights.${k}`, errors)]),
  ) as Record<PriorityComponent, number>;
  if (PRIORITY_COMPONENTS.every((k) => weights[k] === 0)) errors.weights = { key: "allZero" };
  const severity = Object.fromEntries(
    CATEGORIES.map((c) => [c, check(form.category_severity[c], RULES.severity, `category_severity.${c}`, errors)]),
  ) as Record<Category, number>;
  const radius = Object.fromEntries(
    CATEGORIES.map((c) => [c, check(form.radius_m[c], RULES.radius_m, `radius_m.${c}`, errors)]),
  ) as Record<Category, number>;
  const settings: AiSettings = {
    priority: {
      weights,
      category_severity: severity,
      suggestion_min_confidence: check(
        form.suggestion_min_confidence,
        RULES.suggestion_min_confidence,
        "suggestion_min_confidence",
        errors,
      ),
    },
    grouping: {
      window_min: check(form.window_min, RULES.window_min, "window_min", errors),
      radius_m: radius,
      semantic_min_similarity: check(
        form.semantic_min_similarity,
        RULES.semantic_min_similarity,
        "semantic_min_similarity",
        errors,
      ),
      semantic_radius_m: check(form.semantic_radius_m, RULES.semantic_radius_m, "semantic_radius_m", errors),
      semantic_window_min: check(form.semantic_window_min, RULES.semantic_window_min, "semantic_window_min", errors),
    },
  };
  return { settings: Object.keys(errors).length === 0 ? settings : null, errors };
}
