import { describe, expect, it } from "vitest";
import { AI_SETTINGS } from "../test/fixtures";
import { toForm, validateAiSettings } from "./aiSettings";

describe("AI settings validation (mirrors the API's 422 rules)", () => {
  it("round-trips valid settings", () => {
    const { settings, errors } = validateAiSettings(toForm(AI_SETTINGS));
    expect(errors).toEqual({});
    expect(settings).toEqual(AI_SETTINGS);
  });

  it("accepts a decimal comma", () => {
    const form = toForm(AI_SETTINGS);
    form.category_severity.fire = "0,85";
    expect(validateAiSettings(form).settings?.priority.category_severity.fire).toBe(0.85);
  });

  it("rejects empty, non-integer and out-of-range weights, and all-zero weights", () => {
    const form = toForm(AI_SETTINGS);
    form.weights.severity = "";
    form.weights.lives = "12.5";
    form.weights.casualties = "101";
    let result = validateAiSettings(form);
    expect(result.settings).toBeNull();
    expect(result.errors["weights.severity"]).toEqual({ key: "required" });
    expect(result.errors["weights.lives"]).toEqual({ key: "integer" });
    expect(result.errors["weights.casualties"]).toEqual({ key: "range", min: 0, max: 100 });

    const zero = toForm(AI_SETTINGS);
    for (const k of Object.keys(zero.weights) as (keyof typeof zero.weights)[]) zero.weights[k] = "0";
    result = validateAiSettings(zero);
    expect(result.errors.weights).toEqual({ key: "allZero" });
  });

  it("checks severities, confidence and grouping bounds", () => {
    const form = toForm(AI_SETTINGS);
    form.category_severity.flood = "1.2";
    form.suggestion_min_confidence = "-0.1";
    form.window_min = "4";
    form.radius_m.medical = "9";
    form.radius_m.fire = "50001";
    form.semantic_min_similarity = "0.995";
    form.semantic_radius_m = "99";
    form.semantic_window_min = "2881";
    const { settings, errors } = validateAiSettings(form);
    expect(settings).toBeNull();
    expect(errors).toEqual({
      "category_severity.flood": { key: "range", min: 0, max: 1 },
      suggestion_min_confidence: { key: "range", min: 0, max: 1 },
      window_min: { key: "range", min: 5, max: 1440 },
      "radius_m.medical": { key: "range", min: 10, max: 50000 },
      "radius_m.fire": { key: "range", min: 10, max: 50000 },
      semantic_min_similarity: { key: "range", min: 0.5, max: 0.99 },
      semantic_radius_m: { key: "range", min: 100, max: 50000 },
      semantic_window_min: { key: "range", min: 5, max: 2880 },
    });
  });

  it("accepts the bounds themselves", () => {
    const form = toForm(AI_SETTINGS);
    form.window_min = "1440";
    form.radius_m.sos = "10";
    form.semantic_min_similarity = "0.5";
    form.semantic_window_min = "5";
    expect(validateAiSettings(form).errors).toEqual({});
  });
});
