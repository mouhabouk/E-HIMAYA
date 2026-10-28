// covers: phase L4a (docs/phase-l/design-l4.md §2): moving through the six levels and the heat of a cell.
import { describe, expect, it } from "vitest";
import { heat, isoOf, partOfYear, shiftDay } from "./libraryCalendar";

describe("library calendar", () => {
  it("moves by one period of each level, across months and years", () => {
    expect(shiftDay("day", "2024-02-28", 2)).toBe("2024-03-01");
    expect(shiftDay("week", "2026-12-28", 1)).toBe("2027-01-04");
    expect(shiftDay("month", "2026-01-31", 1)).toBe("2026-02-01");
    expect(shiftDay("quarter", "2026-02-10", -1)).toBe("2025-11-01");
    expect(shiftDay("half", "2026-08-10", 1)).toBe("2027-02-01");
    expect(shiftDay("year", "2026-08-10", -1)).toBe("2025-08-01");
    expect(isoOf(2026, 13, 1)).toBe("2027-01-01");
  });

  it("names quarters and halves and shades cells from 0 to 4", () => {
    expect(partOfYear("quarter", "2026-08-10")).toBe(3);
    expect(partOfYear("half", "2026-06-30")).toBe(1);
    expect([0, 1, 5, 10, 20].map((n) => heat(n, 20))).toEqual([0, 1, 1, 2, 4]);
    expect(heat(3, 0)).toBe(0);
  });
});
