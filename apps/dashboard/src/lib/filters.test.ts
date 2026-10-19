import { describe, expect, it } from "vitest";
import { makeReport } from "../test/fixtures";
import { DEFAULT_FILTERS, filtersToQuery, matchesFilters, periodSince } from "./filters";

const NOW = Date.parse("2026-10-19T12:00:00Z");

describe("filters", () => {
  it("converts the period to `since`", () => {
    expect(periodSince("24h", NOW)).toBe("2026-10-18T12:00:00.000Z");
    expect(periodSince("7d", NOW)).toBe("2026-10-12T12:00:00.000Z");
    expect(periodSince("30d", NOW)).toBe("2026-09-19T12:00:00.000Z");
  });

  it("builds the contract query", () => {
    const q = filtersToQuery(
      { statuses: ["in_progress", "received"], categories: ["fire"], gouvernorat: 61, period: "24h", q: "  EH-26 " },
      { now: NOW, bbox: [10, 34, 11, 35], cursor: "abc", limit: 50 },
    );
    expect(q).toEqual({
      status: ["in_progress", "received"],
      category: ["fire"],
      gouvernorat_code: 61,
      since: "2026-10-18T12:00:00.000Z",
      q: "EH-26",
      bbox: "10.00000,34.00000,11.00000,35.00000",
      cursor: "abc",
      limit: 50,
    });
  });

  it("matches live reports like the server would", () => {
    const r = makeReport({ received_at: "2026-10-19T11:00:00Z" });
    expect(matchesFilters(r, DEFAULT_FILTERS, { now: NOW })).toBe(true);
    expect(matchesFilters(r, { ...DEFAULT_FILTERS, statuses: ["closed"] }, { now: NOW })).toBe(false);
    expect(matchesFilters(r, { ...DEFAULT_FILTERS, categories: ["flood"] }, { now: NOW })).toBe(false);
    expect(matchesFilters(r, { ...DEFAULT_FILTERS, gouvernorat: 11 }, { now: NOW })).toBe(false);
    expect(matchesFilters(r, { ...DEFAULT_FILTERS, q: "0004821" }, { now: NOW })).toBe(true);
    expect(matchesFilters(r, { ...DEFAULT_FILTERS, q: "مستودع" }, { now: NOW })).toBe(true);
    expect(matchesFilters(r, { ...DEFAULT_FILTERS, q: "zzz" }, { now: NOW })).toBe(false);
    expect(matchesFilters(r, DEFAULT_FILTERS, { now: NOW, bbox: [10, 34, 11, 35] })).toBe(true);
    expect(matchesFilters(r, DEFAULT_FILTERS, { now: NOW, bbox: [8, 36, 9, 37] })).toBe(false);
    const old = makeReport({ received_at: "2026-09-01T00:00:00Z" });
    expect(matchesFilters(old, DEFAULT_FILTERS, { now: NOW })).toBe(false);
  });
});
