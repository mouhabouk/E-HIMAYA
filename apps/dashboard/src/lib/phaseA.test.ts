import { describe, expect, it } from "vitest";
import { parseTerms, releaseFrom, termsFrom, validateRelease } from "./phaseA";

const release = releaseFrom({
  latest_version: "0.3.0",
  latest_build: 2,
  min_build: 1,
  notes: { ar: "جديد", fr: "Nouveau", en: "New" },
  channel: "server",
  download_url: "https://apk.ehimaya.tn/ehimaya-0.3.0.apk",
});

describe("app.release (mirrors the API)", () => {
  it("defaults when the value is missing", () => {
    expect(releaseFrom(null)).toEqual({
      latest_version: "0.2.0",
      latest_build: 1,
      min_build: 1,
      notes: { ar: "", fr: "", en: "" },
      channel: "server",
      download_url: null,
    });
    expect(validateRelease(releaseFrom(undefined))).toBeNull();
  });

  it("accepts a consistent release", () => {
    expect(validateRelease(release)).toBeNull();
    expect(validateRelease({ ...release, channel: "play", download_url: null })).toBeNull();
  });

  it.each([
    [{ latest_version: "0.3" }, "version"],
    [{ latest_version: "v0.3.0" }, "version"],
    [{ latest_build: 0 }, "build"],
    [{ min_build: 1.5 }, "build"],
    [{ latest_build: Number.NaN }, "build"],
    [{ latest_build: 2_000_000 }, "build"],
    [{ min_build: 3 }, "order"],
    [{ download_url: "http://apk.test/a.apk" }, "url"],
    [{ download_url: null }, "urlMissing"],
    [{ notes: { ar: "x".repeat(2001), fr: "", en: "" } }, "notes"],
  ] as const)("refuses %o (%s)", (change, error) => {
    expect(validateRelease({ ...release, ...change })).toBe(error);
  });
});

describe("moderation.extra_terms", () => {
  it("one per line, trimmed, blank lines ignored, duplicates removed", () => {
    expect(parseTerms(" abc \n\nabc\nكلمة\n")).toEqual({ terms: ["abc", "كلمة"], error: null });
  });

  it("refuses too short, too long and too many", () => {
    expect(parseTerms("a").error).toBe("length");
    expect(parseTerms("x".repeat(65)).error).toBe("length");
    const many = Array.from({ length: 501 }, (_, i) => `w${i}`).join("\n");
    expect(parseTerms(many).error).toBe("count");
  });

  it("reads the stored list", () => {
    expect(termsFrom(["a1", 3, "b2"])).toEqual(["a1", "b2"]);
    expect(termsFrom("x")).toEqual([]);
  });
});
