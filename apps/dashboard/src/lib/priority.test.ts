import { describe, expect, it } from "vitest";
import { AI_STATUS_READY, makeReport } from "../test/fixtures";
import { aiDegraded, analysisFlag, comparePriority, priorityBand } from "./priority";

describe("priorityBand (BR-20 display bands)", () => {
  it("maps ≥ 85 to critical, 70–84 to high, 40–69 to medium (labelled normal) and < 40 to low", () => {
    expect(priorityBand(100)).toBe("critical");
    expect(priorityBand(85)).toBe("critical");
    expect(priorityBand(84)).toBe("high");
    expect(priorityBand(70)).toBe("high");
    expect(priorityBand(69)).toBe("medium");
    expect(priorityBand(69.9)).toBe("medium");
    expect(priorityBand(40)).toBe("medium");
    expect(priorityBand(39)).toBe("low");
    expect(priorityBand(0)).toBe("low");
  });

  it("follows the national band settings", () => {
    const bounds = { critical: 90, high: 60, normal: 30 };
    expect(priorityBand(89, bounds)).toBe("high");
    expect(priorityBand(59, bounds)).toBe("medium");
    expect(priorityBand(29, bounds)).toBe("low");
  });

  it("has no band without a score", () => {
    expect(priorityBand(null)).toBeNull();
    expect(priorityBand(undefined)).toBeNull();
    expect(priorityBand(Number.NaN)).toBeNull();
  });
});

describe("analysisFlag", () => {
  it("flags pending and running as awaiting, failed as incomplete", () => {
    expect(analysisFlag("pending")).toBe("awaiting");
    expect(analysisFlag("running")).toBe("awaiting");
    expect(analysisFlag("failed")).toBe("incomplete");
    expect(analysisFlag("done")).toBeNull();
    expect(analysisFlag(null)).toBeNull();
  });
});

describe("comparePriority", () => {
  it("orders by priority, then newest, unscored last", () => {
    const a = makeReport({ id: "a", priority_score: 50, received_at: "2026-10-19T10:00:00Z" });
    const b = makeReport({ id: "b", priority_score: 80, received_at: "2026-10-19T09:00:00Z" });
    const c = makeReport({ id: "c", priority_score: 50, received_at: "2026-10-19T11:00:00Z" });
    const d = makeReport({ id: "d", priority_score: null, received_at: "2026-10-19T12:00:00Z" });
    expect([a, b, c, d].sort(comparePriority).map((r) => r.id)).toEqual(["b", "c", "a", "d"]);
  });
});

describe("aiDegraded", () => {
  it("detects a missing service or a capability down", () => {
    expect(aiDegraded(undefined)).toBeNull();
    expect(aiDegraded(AI_STATUS_READY)).toBeNull();
    expect(aiDegraded({ configured: false, capabilities: {} })).toBe("notConfigured");
    expect(aiDegraded({ configured: true, capabilities: {} })).toBe("capabilityDown");
    expect(
      aiDegraded({
        configured: true,
        capabilities: { ...AI_STATUS_READY.capabilities, extract: { ready: false, model: "qwen3:8b", detail: "down" } },
      }),
    ).toBe("capabilityDown");
  });
});
