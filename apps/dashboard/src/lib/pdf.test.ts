// covers: phase PL1 (docs/phase-pl/design-plans.md §2.4): the search in the text of a plan, in reading and in visual order.
import { describe, expect, it } from "vitest";
import { contains, fold } from "./pdf";

describe("plan search", () => {
  it("finds a word whatever order and forms the PDF keeps", () => {
    expect(contains(["فتح مراكز ", "الإيواء"], fold("الإيواء"))).toBe(true);
    // A PDF printed by a browser: presentation forms, a piece per glyph from right to left.
    const printed = ["ﻧ", "اء وإ", "ﻮ", "ﻳ", "ﻹ", "ا", " ", "ﺰ", "ﻛ", "ا", "ﺮ", "ﻣ"];
    expect(contains(printed, fold("مراكز الإيواء"))).toBe(false);
    expect(contains(printed, fold("الإيواء"))).toBe(true);
    expect(contains(printed, fold("مراكز"))).toBe(true);
    expect(contains(printed, fold("الحرائق"))).toBe(false);
    expect(fold("مَرْكَزُ الإيـواء")).toBe("مركز الايواء");
  });
});
