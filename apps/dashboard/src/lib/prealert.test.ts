import { describe, expect, it } from "vitest";
import ar from "../i18n/ar.json";
import { prealertState } from "./prealert";

const states = ar.cameras.states as Record<string, string>;
const words = (p: Parameters<typeof prealertState>[0]) => {
  const [key, values] = prealertState(p);
  const text = states[key.replace("cameras.states.", "")] ?? key;
  return text.replace("{{seconds}}", String(values.seconds ?? ""));
};

describe("prealertState (safety officer 60 s, owner 60 s, then the room)", () => {
  it("names who is being asked and the seconds left", () => {
    expect(
      words({ stage: "officer", state: "pending", seconds_left: 42 }),
    ).toBe("ينتظر مسؤول السلامة (42 ث)");
    expect(words({ stage: "owner", state: "pending", seconds_left: 7 })).toBe(
      "ينتظر صاحب المؤسسة (7 ث)",
    );
  });

  it("names who confirmed", () => {
    expect(
      words({ stage: "officer", state: "confirmed", seconds_left: 0 }),
    ).toBe("أكّده مسؤول السلامة");
    expect(words({ stage: "owner", state: "confirmed", seconds_left: 0 })).toBe(
      "أكّده صاحب المؤسسة",
    );
  });

  it("says when the Civil Protection follows the device or nobody answered", () => {
    expect(
      words({ stage: "room", state: "escalated", seconds_left: 0 }),
    ).toContain("الحماية المدنية");
    expect(words({ stage: "owner", state: "escalated", seconds_left: 0 })).toBe(
      "رُفع آليا بعد المهلتين",
    );
    expect(
      words({ stage: "officer", state: "cancelled", seconds_left: 0 }),
    ).toBe("إنذار كاذب أو غير مؤكد");
  });
});
