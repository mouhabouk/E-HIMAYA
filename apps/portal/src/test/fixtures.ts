import type { Certificate, MyOrg, Organization, PublicCertificate } from "../lib/types";

/** Unsigned JWT with the given claims (the portal never verifies signatures). */
export function fakeJwt(claims: Record<string, unknown>): string {
  const enc = (o: unknown) =>
    btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(o))))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  return `${enc({ alg: "none", typ: "JWT" })}.${enc(claims)}.sig`;
}

export const USER_CLAIMS = {
  sub: "kc-1",
  name: "Amira Ben Salah",
  email: "amira@x.tn",
  email_verified: true,
};

/** The Organization example of phase-4-contract.md §1. */
export function makeOrg(overrides: Partial<Organization> = {}): Organization {
  return {
    id: "o-1",
    status: "active",
    version: 7,
    name: "Société X",
    kind: "industrial",
    identifier_type: "mf",
    identifier: "1234567A",
    activity_sector: "Chimie",
    activity_type: "Fabrication de peintures",
    capacity: 420,
    floors: 3,
    height_m: 12.5,
    receives_public: false,
    address: "Route de Gabès km 4",
    location: { lat: 34.7, lon: 10.72 },
    gouvernorat_code: 61,
    delegation_id: null,
    manager: { full_name: "Karim Trabelsi", phone: "+21620123456", email: "karim@x.tn" },
    contact_email: "contact@x.tn",
    contact_phone: "+21674000000",
    classification: {
      family: "industrial",
      category: null,
      high_rise: false,
      required: ["safety_file", "safety_plan", "safety_team", "training", "hazmat_sds", "equipment"],
      provisional: true,
    },
    completeness: { ok: false, missing: ["safety_plan", "hazmat_sds"] },
    alerts: [
      { kind: "training_expired", ref: "t-1", since: "2026-09-01" },
      { kind: "maintenance_overdue", ref: "e-1", since: "2026-08-15" },
    ],
    my_role: "admin",
    review: { reason: null, at: null },
    created_at: "2026-10-01T10:00:00Z",
    updated_at: "2026-10-18T10:00:00Z",
    ...overrides,
  };
}

export const MY_ORGS: MyOrg[] = [
  { id: "o-1", name: "Société X", kind: "industrial", status: "active", my_role: "admin", alerts_count: 2 },
  { id: "o-2", name: "Lycée Y", kind: "education", status: "pending_review", my_role: "member", alerts_count: 0 },
];

export function makePublicCertificate(overrides: Partial<PublicCertificate> = {}): PublicCertificate {
  return {
    code: "EHC-26-61-000123",
    status: "approved",
    valid: true,
    superseded: false,
    org_name: "Société X",
    org_kind: "industrial",
    gouvernorat_code: 61,
    classification: { family: "industrial", category: null },
    issued_at: "2026-10-19T09:00:00Z",
    valid_until: "2099-10-19",
    fingerprint: "f".repeat(64),
    pdf_sha256: "0".repeat(64),
    signature_valid: true,
    ...overrides,
  };
}

export function makeCertificate(overrides: Partial<Certificate> = {}): Certificate {
  return {
    id: "c-1",
    code: "EHC-26-61-000123",
    status: "draft",
    superseded: false,
    created_at: "2026-10-19T09:00:00Z",
    submitted_at: null,
    reviewed_at: null,
    review_reason: null,
    valid_until: null,
    fingerprint: "f".repeat(64),
    pdf_sha256: "e".repeat(64),
    verify_url: "http://localhost:5174/verify/EHC-26-61-000123",
    ...overrides,
  };
}

export const GOUVERNORATS = [
  { code: 11, iso_code: "TN-11", name: "تونس", name_ar: "تونس", name_fr: "Tunis", delegation_count: 21 },
  { code: 61, iso_code: "TN-61", name: "صفاقس", name_ar: "صفاقس", name_fr: "Sfax", delegation_count: 16 },
];
