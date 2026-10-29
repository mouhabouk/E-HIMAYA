import { describe, expect, it } from "vitest";
import { maskedParts } from "./MaskedText";

describe("maskedParts", () => {
  it("hides and flags exactly the given ranges", () => {
    expect(
      maskedParts("يا كلب زبي، نذبحك", [
        [0, 6, "hide"],
        [7, 10, "hide"],
        [12, 17, "flag"],
      ]),
    ).toEqual([
      { text: "يا كلب", kind: "hide" },
      { text: " ", kind: "shown" },
      { text: "زبي", kind: "hide" },
      { text: "، ", kind: "shown" },
      { text: "نذبحك", kind: "flag" },
    ]);
  });

  it("counts UTF-16 units, as the API does", () => {
    expect(maskedParts("😀 fuck", [[3, 7, "hide"]])).toEqual([
      { text: "😀 ", kind: "shown" },
      { text: "fuck", kind: "hide" },
    ]);
  });

  it("shows the text as is without masks and ignores ranges that do not fit", () => {
    expect(maskedParts("feu", undefined)).toEqual([{ text: "feu", kind: "shown" }]);
    expect(
      maskedParts("feu", [
        [2, 9, "hide"],
        [1, 1, "flag"],
      ]),
    ).toEqual([{ text: "feu", kind: "shown" }]);
  });
});
