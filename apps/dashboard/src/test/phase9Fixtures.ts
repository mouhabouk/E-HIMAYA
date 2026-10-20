import { vi } from "vitest";
import type { Phase9Api } from "../lib/phase9Api";
import type {
  BreakGlassGrant,
  NearbyIncident,
  PlatformSetting,
  ResourceRequest,
  ScopedAuditEntry,
  StaffAccount,
} from "../lib/phase9Types";

export const NATIONAL_OPERATOR_CLAIMS = {
  sub: "u-c1",
  name: "Hela Central",
  realm_access: { roles: ["operator"] },
  scope_level: "national",
};

export const CENTRAL_COMMITTEE_CLAIMS = {
  sub: "u-cc",
  name: "Mounir Committee",
  realm_access: { roles: ["central_committee"] },
  scope_level: "national",
};

export const OPS_MANAGER_CLAIMS = {
  sub: "u-om",
  name: "Rania Manager",
  realm_access: { roles: ["ops_manager"] },
  gouvernorat_code: "61",
};

export const SECURITY_ADMIN_CLAIMS = {
  sub: "u-sa",
  name: "Karim Security",
  realm_access: { roles: ["security_admin"] },
  scope_level: "national",
};

export const ACCOUNT_ADMIN_CLAIMS = {
  sub: "u-aa",
  name: "Nadia Accounts",
  realm_access: { roles: ["regional_account_admin"] },
  gouvernorat_code: "61",
};

export function makeSettings(editable = true): PlatformSetting[] {
  const base = { version: 1, updated_by_name: "Mounir Committee", updated_at: "2026-10-01T08:00:00Z" };
  return [
    { ...base, key: "sla.bands", value: { critical: 85, high: 70, normal: 40 }, editable },
    { ...base, key: "sla.claim_delay_s", value: { critical: 60, high: 90, normal: 120, low: 180 }, editable },
    { ...base, key: "sla.enforced_since", value: "2026-10-01T00:00:00Z", editable: false },
    { ...base, key: "anonymous.report_quota", value: 5, editable },
    { ...base, key: "geo.max_trusted_accuracy_m", value: 1000, editable },
    { ...base, key: "notify.real_send_enabled", value: false, editable: false },
  ];
}

export function makeResourceRequest(overrides: Partial<ResourceRequest> = {}): ResourceRequest {
  return {
    id: "rr-1",
    incident_id: "i-1",
    from_room: "g:42",
    to_gouvernorat_code: 61,
    resource_id: null,
    resource_kind: "water_tanker",
    quantity: 2,
    reason: "Front de feu étendu vers Sfax",
    status: "pending",
    requested_by_name: "Ali Kasserine",
    requested_at: "2026-10-20T09:00:00Z",
    decided_by_name: null,
    decided_at: null,
    decision_note: null,
    ...overrides,
  };
}

export function makeGrant(overrides: Partial<BreakGlassGrant> = {}): BreakGlassGrant {
  return {
    id: "bg-1",
    subject: "u-1",
    subject_name: "Sami Operator",
    target_kind: "report",
    target_id: "r-1",
    gouvernorat_code: null,
    justification: "Victime injoignable, besoin du numéro pour guider les secours",
    granted_at: "2026-10-20T08:00:00Z",
    expires_at: "2026-10-20T09:00:00Z",
    revoked_at: null,
    revoked_by: null,
    reviewed_by: null,
    reviewed_at: null,
    review_outcome: null,
    review_note: null,
    ...overrides,
  };
}

export function makeAccount(overrides: Partial<StaffAccount> = {}): StaffAccount {
  return {
    id: "acc-1",
    username: "sami.op",
    email: "sami@ehimaya.test",
    first_name: "Sami",
    last_name: "Ben Ali",
    enabled: true,
    roles: ["operator"],
    scope_level: "gouvernorat",
    gouvernorat_code: 61,
    mfa_configured: true,
    ...overrides,
  };
}

export function makeAuditEntry(overrides: Partial<ScopedAuditEntry> = {}): ScopedAuditEntry {
  return {
    seq: 101,
    at: "2026-10-20T09:30:00Z",
    action: "report.claim",
    actor_name: "Sami Operator",
    target: "report:r-1",
    reason: null,
    details: { report_id: "r-1", to: "g:61" },
    gouvernorats: [61],
    ...overrides,
  };
}

export function makeNearby(overrides: Partial<NearbyIncident> = {}): NearbyIncident {
  return {
    id: "i-near",
    category: "fire",
    lead_gouvernorat_code: 11,
    participating_gouvernorats: [],
    centroid: { lat: 34.75, lon: 10.77 },
    severity: 72,
    opened_at: "2026-10-20T08:40:00Z",
    report_count: 3,
    ...overrides,
  };
}

const empty = () => Promise.resolve({ items: [], next_cursor: null });

export function fakePhase9Api(): Phase9Api {
  return {
    platformSettings: vi.fn(() => Promise.resolve(makeSettings(false))),
    savePlatformSetting: vi.fn(),
    claimReport: vi.fn(),
    releaseClaim: vi.fn(),
    lateReports: vi.fn(empty),
    referReport: vi.fn(),
    acceptReferral: vi.fn(),
    refuseReferral: vi.fn(),
    geoQueue: vi.fn(empty),
    geoVerify: vi.fn(),
    nearbyIncidents: vi.fn(() => Promise.resolve([])),
    addParticipant: vi.fn(),
    removeParticipant: vi.fn(),
    transferLead: vi.fn(),
    setCommandLevel: vi.fn(),
    createResourceRequest: vi.fn(),
    resourceRequests: vi.fn(empty),
    approveResourceRequest: vi.fn(),
    refuseResourceRequest: vi.fn(),
    cancelResourceRequest: vi.fn(),
    requestBreakGlass: vi.fn(),
    breakGlassGrants: vi.fn(empty),
    revokeBreakGlass: vi.fn(),
    reviewBreakGlass: vi.fn(),
    accounts: vi.fn(empty),
    createAccount: vi.fn(),
    updateAccount: vi.fn(),
    resetAccountCredentials: vi.fn(),
    scopedAudit: vi.fn(empty),
  };
}
