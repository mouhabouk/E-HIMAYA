import { describe, expect, it } from "vitest";
import { makeMessage } from "../test/opsFixtures";
import { emptyForm, formFromMessage, smsPreview, toLocalInput, toMessageBody, validateForm } from "./messageForm";

const NOW = new Date("2026-10-19T08:00:00Z");

describe("message composer form", () => {
  it("requires Arabic text, a channel and the kind's fields", () => {
    const info = { ...emptyForm("info", NOW), channels: [] };
    expect(validateForm(info, NOW)).toEqual({
      titleAr: "titleRequired",
      bodyAr: "bodyRequired",
      channels: "channelsRequired",
      topic: "topicRequired",
    });
    const toUser = { ...emptyForm("info", NOW), audience: "user" as const, userId: "abc" };
    expect(validateForm(toUser, NOW).userId).toBe("userIdInvalid");
    const alert = emptyForm("alert", NOW);
    expect(validateForm(alert, NOW)).toMatchObject({ severity: "severityRequired", category: "categoryRequired" });
    expect(validateForm(alert, NOW).expiresAt).toBeUndefined();
  });

  it("keeps alert expiry in the future and within 7 days", () => {
    const base = { ...emptyForm("alert", NOW), severity: "high" as const, category: "weather" as const };
    const late = toLocalInput(new Date(NOW.getTime() + 8 * 86_400_000));
    const past = toLocalInput(new Date(NOW.getTime() - 3_600_000));
    expect(validateForm({ ...base, expiresAt: late }, NOW).expiresAt).toBe("expiryRange");
    expect(validateForm({ ...base, expiresAt: past }, NOW).expiresAt).toBe("expiryRange");
    expect(validateForm({ ...base, expiresAt: "" }, NOW).expiresAt).toBe("expiryRequired");
  });

  it("validates a drawn area", () => {
    const form = {
      ...emptyForm("alert", NOW),
      severity: "high" as const,
      category: "weather" as const,
      areaMode: "polygon" as const,
      vertices: [[10.7, 34.7]] as [number, number][],
    };
    expect(validateForm(form, NOW).polygon).toBe("polygon.too_few");
  });

  it("builds an alert body with a closed polygon and no gouvernorats", () => {
    const form = {
      ...emptyForm("alert", NOW),
      title: { ar: " تنبيه ", fr: "", en: "" },
      body: { ar: "نص", fr: "", en: "" },
      channels: ["sms", "push"] as ("sms" | "push")[],
      severity: "high" as const,
      category: "weather" as const,
      hazard: "heavy_rain" as const,
      gouvernorats: [61],
      areaMode: "polygon" as const,
      vertices: [
        [10.7, 34.7],
        [10.8, 34.7],
        [10.8, 34.8],
      ] as [number, number][],
    };
    const body = toMessageBody(form, 3);
    expect(body).toMatchObject({ kind: "alert", channels: ["push", "sms"], version: 3, severity: "high", hazard: "heavy_rain" });
    expect(body.title.ar).toBe("تنبيه");
    expect(body.area.gouvernorat_codes).toEqual([]);
    expect(body.area.polygon?.coordinates[0]).toHaveLength(4);
    expect(body.expires_at).toBe(new Date(form.expiresAt).toISOString());
  });

  it("builds an info body; a message to one user has no area", () => {
    const form = { ...emptyForm("info", NOW), topic: "training" as const, gouvernorats: [61] };
    expect(toMessageBody(form)).toMatchObject({ topic: "training", audience: "all", user_id: null, area: { gouvernorat_codes: [61] } });
    const toUser = { ...form, audience: "user" as const, userId: " 1b4e28ba-2fa1-11d2-883f-0016d3cca427 " };
    expect(toMessageBody(toUser)).toMatchObject({ user_id: "1b4e28ba-2fa1-11d2-883f-0016d3cca427", area: { gouvernorat_codes: [] } });
  });

  it("round-trips a stored message and previews the SMS", () => {
    const form = formFromMessage(makeMessage({ area: { gouvernorat_codes: [], polygon: { type: "Polygon", coordinates: [[[10.7, 34.7], [10.8, 34.7], [10.8, 34.8], [10.7, 34.7]]] } } }));
    expect(form.areaMode).toBe("polygon");
    expect(form.vertices).toHaveLength(3);
    expect(smsPreview("Alerte", "x".repeat(400))).toHaveLength(300);
  });
});
