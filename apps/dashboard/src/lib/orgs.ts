/** Institutions (phase 4 §9): list filters, review transitions and certificate validity rules. */
import type { QueryValue } from "./api";
import {
  isOneOf,
  ORG_CERTIFICATE_STATES,
  ORG_KINDS,
  ORG_STATUSES,
  type OrgCertificateState,
  type OrgDecision,
  type OrgKind,
  type OrgStatus,
  type StaffOrg,
} from "./types";

export interface OrgFilters {
  status: OrgStatus | null;
  kind: OrgKind | null;
  /** Only for national-scope users; the server applies the token's scope otherwise. */
  gouvernorat: number | null;
  certificate: OrgCertificateState | null;
  /** `has_hazmat=true|false`; null = no filter. */
  hasHazmat: boolean | null;
  q: string;
}

export const DEFAULT_ORG_FILTERS: OrgFilters = {
  status: null,
  kind: null,
  gouvernorat: null,
  certificate: null,
  hasHazmat: null,
  q: "",
};

export function normalizeOrgFilters(f: OrgFilters): OrgFilters {
  return { ...f, q: f.q.trim() };
}

export function orgFiltersToQuery(
  f: OrgFilters,
  opts: { cursor?: string | null; limit?: number } = {},
): Record<string, QueryValue> {
  const q = f.q.trim();
  return {
    status: f.status ?? undefined,
    kind: f.kind ?? undefined,
    gouvernorat_code: f.gouvernorat ?? undefined,
    certificate: f.certificate ?? undefined,
    has_hazmat: f.hasHazmat === null ? undefined : String(f.hasHazmat),
    q: q || undefined,
    limit: opts.limit ?? 50,
    cursor: opts.cursor ?? undefined,
  };
}

/** Filters ⇄ URL search params of `/orgs` (so KPI tiles and links can open a filtered list). */
export function orgFiltersFromSearch(params: URLSearchParams): OrgFilters {
  const status = params.get("status");
  const kind = params.get("kind");
  const cert = params.get("certificate");
  const hazmat = params.get("has_hazmat");
  const gouv = Number.parseInt(params.get("gouvernorat_code") ?? "", 10);
  return {
    status: isOneOf(ORG_STATUSES, status) ? status : null,
    kind: isOneOf(ORG_KINDS, kind) ? kind : null,
    gouvernorat: Number.isInteger(gouv) ? gouv : null,
    certificate: isOneOf(ORG_CERTIFICATE_STATES, cert) ? cert : null,
    hasHazmat: hazmat === "true" ? true : hazmat === "false" ? false : null,
    q: (params.get("q") ?? "").slice(0, 100),
  };
}

export function orgFiltersToSearch(f: OrgFilters): URLSearchParams {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(orgFiltersToQuery(f))) {
    if (k === "limit" || k === "cursor" || v === undefined || v === null || v === "") continue;
    p.set(k, String(v));
  }
  return p;
}

/** Client-side equivalent of the list filters, to place an `org.updated` event in cached lists. */
export function matchesOrgFilters(org: StaffOrg, f: OrgFilters): boolean {
  if (f.status && org.status !== f.status) return false;
  if (f.kind && org.kind !== f.kind) return false;
  if (f.gouvernorat !== null && org.gouvernorat_code !== f.gouvernorat) return false;
  if (f.certificate && org.certificate_status !== f.certificate) return false;
  if (f.hasHazmat !== null && org.hazmat_count > 0 !== f.hasHazmat) return false;
  const q = f.q.trim().toLowerCase();
  if (q && !org.name.toLowerCase().includes(q) && !org.identifier.toLowerCase().includes(q)) return false;
  return true;
}

/** Name order of the staff list ("sorted by name"). */
export function compareOrgNames(a: { name: string; id: string }, b: { name: string; id: string }): number {
  const byName = a.name.localeCompare(b.name, ["ar", "fr"], { sensitivity: "base" });
  return byName !== 0 ? byName : a.id.localeCompare(b.id);
}

/** Allowed registration decisions by current status (§9; anything else answers 409 invalid_transition). */
export const ORG_REVIEW_TRANSITIONS: Readonly<Record<OrgStatus, readonly OrgDecision[]>> = {
  pending_review: ["approve", "reject"],
  active: ["suspend"],
  suspended: ["reinstate"],
  rejected: [],
};

export function reviewDecisions(status: OrgStatus): readonly OrgDecision[] {
  return ORG_REVIEW_TRANSITIONS[status];
}

/** `reason` is required for reject and suspend (422 reason_required). */
export function decisionNeedsReason(decision: OrgDecision): boolean {
  return decision === "reject" || decision === "suspend";
}

// ---------- Certificate validity (`valid_until`: between tomorrow and 5 years) ----------

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** Local calendar date as YYYY-MM-DD. */
export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function addDays(d: Date, days: number): Date {
  const out = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  out.setDate(out.getDate() + days);
  return out;
}

function addYears(d: Date, years: number): Date {
  const out = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  out.setFullYear(out.getFullYear() + years);
  return out;
}

export function validUntilBounds(today: Date = new Date()): { min: string; max: string; default: string } {
  return { min: isoDate(addDays(today, 1)), max: isoDate(addYears(today, 5)), default: isoDate(addYears(today, 1)) };
}

export type ValidUntilError = "required" | "format" | "range";

/** Same rule as the server (`422 invalid_valid_until`), checked before sending. */
export function validateValidUntil(value: string, today: Date = new Date()): ValidUntilError | null {
  if (!value) return "required";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return "format";
  const [y, m, d] = value.split("-").map(Number) as [number, number, number];
  const date = new Date(y, m - 1, d);
  if (date.getFullYear() !== y || date.getMonth() !== m - 1 || date.getDate() !== d) return "format";
  const { min, max } = validUntilBounds(today);
  // ISO dates compare lexicographically.
  if (value < min || value > max) return "range";
  return null;
}
