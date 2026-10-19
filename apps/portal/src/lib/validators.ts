/**
 * Client-side validation mirroring the contract (docs/api/phase-4-contract.md). The server stays the
 * authority: these checks only give earlier, translated feedback.
 */
import type { DocumentKind, GeoPoint, IdentifierType } from "./types";

// Matricule fiscal: 7 digits + control letter, optionally /<letter>/<letter>/<3 digits> (§1).
const MF = /^\d{7}[A-Z](\/[A-Z]\/[A-Z]\/\d{3})?$/;
// RNE unique identifier: 7 digits + a letter.
const RNE = /^\d{7}[A-Z]$/;
const PHONE = /^\+216\d{8}$/;
const UN_NUMBER = /^\d{4}$/;
// Deliberately loose (the server and Keycloak do the real checks): something@something.tld
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Upper-case without spaces, as the server stores it. */
export function normalizeIdentifier(raw: string): string {
  return raw.replace(/\s+/g, "").toUpperCase();
}

export function isValidIdentifier(type: IdentifierType, raw: string): boolean {
  const v = normalizeIdentifier(raw);
  return type === "mf" ? MF.test(v) : RNE.test(v);
}

/** "20 123 456", "0021620123456" and "+216 20-123-456" all become "+21620123456". */
export function normalizePhone(raw: string): string {
  let v = raw.replace(/[\s.-]/g, "");
  if (/^\d{8}$/.test(v)) v = `+216${v}`;
  else if (v.startsWith("00216")) v = `+${v.slice(2)}`;
  return v;
}

export function isValidPhone(raw: string): boolean {
  return PHONE.test(normalizePhone(raw));
}

/** UN number: exactly 4 digits; empty means "none" (null). */
export function isValidUnNumber(raw: string): boolean {
  const v = raw.trim();
  return v === "" || UN_NUMBER.test(v);
}

export function isValidEmail(raw: string): boolean {
  return EMAIL.test(raw.trim());
}

/** Same box as reports (phase 2 §3): lat 30.0–37.6, lon 7.4–11.7. */
export const TUNISIA_BOX = { minLat: 30.0, maxLat: 37.6, minLon: 7.4, maxLon: 11.7 } as const;

export function isInTunisia(p: GeoPoint | null | undefined): boolean {
  if (!p || !Number.isFinite(p.lat) || !Number.isFinite(p.lon)) return false;
  return p.lat >= TUNISIA_BOX.minLat && p.lat <= TUNISIA_BOX.maxLat && p.lon >= TUNISIA_BOX.minLon && p.lon <= TUNISIA_BOX.maxLon;
}

/** Great-circle distance in metres (haversine). */
export function distanceMeters(a: GeoPoint, b: GeoPoint): number {
  const R = 6_371_008.8;
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Map features must lie within 2 km of the institution (§5, `422 feature_too_far`). */
export const FEATURE_MAX_DISTANCE_M = 2000;

export function isWithinFeatureRadius(org: GeoPoint, p: GeoPoint): boolean {
  return distanceMeters(org, p) <= FEATURE_MAX_DISTANCE_M;
}

export function isIntInRange(v: number | null | undefined, min: number, max: number): boolean {
  return typeof v === "number" && Number.isInteger(v) && v >= min && v <= max;
}

/** Parse a form number field: "" → null, otherwise a finite number (NaN when invalid). */
export function parseNumber(raw: string): number | null {
  const v = raw.trim().replace(",", ".");
  if (v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : Number.NaN;
}

// ---------------------------------------------------------------- documents (§6)

export const DOCUMENT_MAX_BYTES = 50 * 1024 * 1024;
export const CAD_MAX_BYTES = 100 * 1024 * 1024;
export const NOTE_MAX_LENGTH = 200;

const EXTENSION_TYPES: Readonly<Record<string, string>> = {
  pdf: "application/pdf",
  dwg: "image/vnd.dwg",
  dxf: "image/vnd.dxf",
};

const ALLOWED_TYPES: Readonly<Record<DocumentKind, readonly string[]>> = {
  safety_file: ["application/pdf"],
  safety_plan: ["application/pdf", "image/vnd.dwg", "image/vnd.dxf"],
  sds: ["application/pdf"],
  other: ["application/pdf"],
};

/** `accept` attribute of the file input for a document kind. */
export function acceptFor(kind: DocumentKind): string {
  return kind === "safety_plan" ? "application/pdf,.pdf,.dwg,.dxf" : "application/pdf,.pdf";
}

/**
 * MIME type sent as `filetype`: browsers often give CAD files an empty or vendor type, so the extension
 * decides for .dwg/.dxf; PDFs keep `application/pdf`.
 */
export function detectContentType(file: { name: string; type: string }): string {
  const ext = file.name.toLowerCase().split(".").pop() ?? "";
  const byExt = EXTENSION_TYPES[ext];
  if (byExt && byExt !== "application/pdf") return byExt;
  return file.type || byExt || "application/octet-stream";
}

export type FileProblem = "unsupported_media_type" | "document_too_large" | null;

export function checkDocumentFile(kind: DocumentKind, file: { name: string; type: string; size: number }): FileProblem {
  const type = detectContentType(file);
  if (!ALLOWED_TYPES[kind].includes(type)) return "unsupported_media_type";
  const max = type === "application/pdf" ? DOCUMENT_MAX_BYTES : CAD_MAX_BYTES;
  return file.size > max ? "document_too_large" : null;
}
