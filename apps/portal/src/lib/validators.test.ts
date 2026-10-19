import { describe, expect, it } from "vitest";
import {
  checkDocumentFile,
  detectContentType,
  distanceMeters,
  isInTunisia,
  isValidEmail,
  isValidIdentifier,
  isValidPhone,
  isValidUnNumber,
  isWithinFeatureRadius,
  normalizeIdentifier,
  normalizePhone,
  parseNumber,
} from "./validators";

describe("identifier (§1)", () => {
  it("accepts the matricule fiscal with and without the suffix, upper-cased without spaces", () => {
    expect(isValidIdentifier("mf", "1234567A")).toBe(true);
    expect(isValidIdentifier("mf", "1234567A/A/M/000")).toBe(true);
    expect(isValidIdentifier("mf", " 1234567a / a / m / 000 ")).toBe(true);
    expect(normalizeIdentifier(" 1234567a/b/m/000 ")).toBe("1234567A/B/M/000");
  });

  it("refuses malformed matricules", () => {
    for (const bad of ["123456A", "12345678A", "1234567", "1234567A/A/M/00", "1234567A/AA/M/000", "1234567A/1/M/000", "A1234567"]) {
      expect(isValidIdentifier("mf", bad), bad).toBe(false);
    }
  });

  it("accepts only 7 digits + a letter for the RNE", () => {
    expect(isValidIdentifier("rne", "1234567B")).toBe(true);
    expect(isValidIdentifier("rne", "1234567B/A/M/000")).toBe(false);
    expect(isValidIdentifier("rne", "123456B")).toBe(false);
  });
});

describe("phone", () => {
  it("normalises local and international forms to +216XXXXXXXX", () => {
    expect(normalizePhone("20 123 456")).toBe("+21620123456");
    expect(normalizePhone("0021620123456")).toBe("+21620123456");
    expect(normalizePhone("+216 20-123-456")).toBe("+21620123456");
    expect(isValidPhone("20.123.456")).toBe(true);
  });

  it("refuses other lengths and countries", () => {
    for (const bad of ["2012345", "+2162012345", "+21720123456", "+216201234567", "abc"]) {
      expect(isValidPhone(bad), bad).toBe(false);
    }
  });
});

describe("UN number (§4)", () => {
  it("is 4 digits or empty", () => {
    expect(isValidUnNumber("1090")).toBe(true);
    expect(isValidUnNumber("")).toBe(true);
    expect(isValidUnNumber("  ")).toBe(true);
    expect(isValidUnNumber("109")).toBe(false);
    expect(isValidUnNumber("10900")).toBe(false);
    expect(isValidUnNumber("UN1090")).toBe(false);
  });
});

describe("other checks", () => {
  it("validates e-mails loosely", () => {
    expect(isValidEmail("a@x.tn")).toBe(true);
    expect(isValidEmail("a@x")).toBe(false);
  });

  it("checks the Tunisia box and the 2 km feature radius", () => {
    expect(isInTunisia({ lat: 34.7, lon: 10.72 })).toBe(true);
    expect(isInTunisia({ lat: 48.85, lon: 2.35 })).toBe(false);
    expect(isInTunisia({ lat: Number.NaN, lon: 10 })).toBe(false);
    const org = { lat: 34.7, lon: 10.72 };
    expect(distanceMeters(org, { lat: 34.709, lon: 10.72 })).toBeCloseTo(1000, -1);
    expect(isWithinFeatureRadius(org, { lat: 34.71, lon: 10.72 })).toBe(true);
    expect(isWithinFeatureRadius(org, { lat: 34.72, lon: 10.72 })).toBe(false);
  });

  it("parses numbers with comma decimals", () => {
    expect(parseNumber("")).toBeNull();
    expect(parseNumber("12,5")).toBe(12.5);
    expect(parseNumber("x")).toBeNaN();
  });

  it("checks document types and sizes per kind (§6)", () => {
    const mb = 1024 * 1024;
    expect(checkDocumentFile("safety_file", { name: "a.pdf", type: "application/pdf", size: 10 * mb })).toBeNull();
    expect(checkDocumentFile("safety_file", { name: "a.pdf", type: "application/pdf", size: 51 * mb })).toBe("document_too_large");
    expect(checkDocumentFile("safety_file", { name: "plan.dwg", type: "", size: mb })).toBe("unsupported_media_type");
    expect(checkDocumentFile("safety_plan", { name: "plan.dwg", type: "", size: 90 * mb })).toBeNull();
    expect(checkDocumentFile("safety_plan", { name: "plan.dxf", type: "application/octet-stream", size: 101 * mb })).toBe("document_too_large");
    expect(detectContentType({ name: "PLAN.DXF", type: "application/dxf" })).toBe("image/vnd.dxf");
    expect(detectContentType({ name: "x.pdf", type: "" })).toBe("application/pdf");
  });
});
