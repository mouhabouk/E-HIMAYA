import type { Kpis, StaffReport, StaffReportDetail } from "../lib/types";

export function makeReport(overrides: Partial<StaffReport> = {}): StaffReport {
  const now = new Date().toISOString();
  return {
    id: "r-1",
    tracking_code: "EH-26-61-0004821",
    category: "fire",
    status: "received",
    text: "حريق في مستودع",
    lang: "ar",
    location: { lat: 34.74, lon: 10.76, accuracy_m: 12.5 },
    gouvernorat_code: 61,
    delegation_id: null,
    created_at: now,
    received_at: now,
    updated_at: now,
    reporter_kind: "citizen",
    media_count: 1,
    ...overrides,
  };
}

export function makeDetail(overrides: Partial<StaffReportDetail> = {}): StaffReportDetail {
  const base = makeReport(overrides);
  return {
    ...base,
    history: [{ status: "received", at: base.received_at }],
    media: [
      {
        id: "m-1",
        kind: "image",
        bytes: 123456,
        sha256: "a".repeat(64),
        status: "stored",
        url: "https://s3.example/m-1?sig=x",
      },
    ],
    reporter: { kind: "citizen", first_name: "Amira", last_name: "Ben Salah", phone: "+21620000000" },
    ...overrides,
  };
}

export const KPIS: Kpis = {
  since: "2026-10-18T10:00:00Z",
  total: 12,
  by_status: { received: 3, in_progress: 4, intervened: 1, ongoing: 1, closed: 2, rejected: 1 },
  by_category: { fire: 5, flood: 2, medical: 5 },
  by_gouvernorat: [
    { code: 61, count: 7 },
    { code: 11, count: 5 },
  ],
  avg_first_response_s: 312.5,
};

/** Unsigned JWT with the given claims (the dashboard never verifies signatures). */
export function fakeJwt(claims: Record<string, unknown>): string {
  const enc = (o: unknown) =>
    btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(o))))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  return `${enc({ alg: "none", typ: "JWT" })}.${enc(claims)}.sig`;
}
