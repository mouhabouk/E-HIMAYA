import type { ApiClient } from "./api";
import type {
  AccountCreateBody,
  AccountFilters,
  AccountPatchBody,
  AuditFilters,
  BreakGlassBody,
  BreakGlassGrant,
  BreakGlassStatus,
  CommandLevel,
  NearbyIncident,
  PlatformSetting,
  ThresholdSpec,
  ReferBody,
  ResourceRequest,
  ResourceRequestBody,
  ResourceRequestDirection,
  ResourceRequestStatus,
  ScopedAuditEntry,
  SettingUpdateBody,
  StaffAccount,
} from "./phase9Types";
import type { IncidentDetail, Page, StaffReport, StaffReportDetail } from "./types";

const enc = encodeURIComponent;
const S = "/api/v1/staff";
const reportPath = (id: string) => `${S}/reports/${enc(id)}`;
const incidentPath = (id: string) => `${S}/incidents/${enc(id)}`;
const requestPath = (id: string) => `${S}/resource-requests/${enc(id)}`;
const grantPath = (id: string) => `${S}/break-glass/${enc(id)}`;
const accountPath = (id: string) => `${S}/accounts/${enc(id)}`;

interface PageOpts {
  cursor?: string | null;
  limit?: number;
  signal?: AbortSignal;
}

/** A list answered as a page, or only `{"items"}` (the accounts list of §6.2 names no cursor). */
function asPage<T>(body: Page<T> | { items: T[]; next_cursor?: string | null }): Page<T> {
  return { items: body.items, next_cursor: body.next_cursor ?? null };
}

/** Typed calls for docs/api/phase-9-contract.md §2 and §4–§7. */
export function phase9Api(api: ApiClient) {
  return {
    // ---------- §2 national settings ----------
    platformSettings: (signal?: AbortSignal) =>
      api.request<{ items: PlatformSetting[] }>(`${S}/settings`, { signal }).then((b) => b.items),

    /** Phase N (§9): what each operational threshold of ``operations.thresholds`` means, and its bounds. */
    thresholdSpecs: (signal?: AbortSignal) =>
      api.request<{ thresholds: ThresholdSpec[] }>(`${S}/settings`, { signal }).then((b) => b.thresholds),

    savePlatformSetting: (key: string, body: SettingUpdateBody) =>
      api.request<PlatformSetting>(`${S}/settings/${enc(key)}`, { method: "PUT", body }),

    // ---------- §4 claim, late list, referral, geo-verification ----------
    claimReport: (id: string) => api.request<StaffReportDetail>(`${reportPath(id)}/claim`, { method: "POST", body: {} }),

    releaseClaim: (id: string, reason: string) =>
      api.request<StaffReportDetail>(`${reportPath(id)}/claim`, { method: "DELETE", body: { reason } }),

    lateReports: (opts: PageOpts & { gouvernorat?: number | null } = {}) =>
      api.request<Page<StaffReport>>(`${S}/reports/late`, {
        query: { cursor: opts.cursor ?? undefined, limit: opts.limit ?? 50, gouvernorat: opts.gouvernorat ?? undefined },
        signal: opts.signal,
      }),

    referReport: (id: string, body: ReferBody) =>
      api.request<StaffReportDetail>(`${reportPath(id)}/refer`, { method: "POST", body }),

    acceptReferral: (id: string, note: string) =>
      api.request<StaffReportDetail>(`${reportPath(id)}/referral/accept`, { method: "POST", body: { note } }),

    refuseReferral: (id: string, reason: string) =>
      api.request<StaffReportDetail>(`${reportPath(id)}/referral/refuse`, { method: "POST", body: { reason } }),

    geoQueue: (opts: PageOpts = {}) =>
      api.request<Page<StaffReport>>(`${S}/reports/geo-queue`, {
        query: { cursor: opts.cursor ?? undefined, limit: opts.limit ?? 50 },
        signal: opts.signal,
      }),

    geoVerify: (id: string, gouvernoratCode: number, reason: string) =>
      api.request<StaffReportDetail>(`${reportPath(id)}/geo-verify`, {
        method: "POST",
        body: { gouvernorat_code: gouvernoratCode, reason },
      }),

    // ---------- §5 incidents across gouvernorats ----------
    nearbyIncidents: (reportId: string, signal?: AbortSignal) =>
      api
        .request<NearbyIncident[] | { items: NearbyIncident[] }>(`${reportPath(reportId)}/nearby-incidents`, { signal })
        .then((b) => (Array.isArray(b) ? b : b.items)),

    addParticipant: (incidentId: string, gouvernoratCode: number, reason: string) =>
      api.request<IncidentDetail>(`${incidentPath(incidentId)}/participants`, {
        method: "POST",
        body: { gouvernorat_code: gouvernoratCode, reason },
      }),

    removeParticipant: (incidentId: string, gouvernoratCode: number, reason: string) =>
      api.request<IncidentDetail>(`${incidentPath(incidentId)}/participants/${enc(String(gouvernoratCode))}`, {
        method: "DELETE",
        body: { reason },
      }),

    transferLead: (incidentId: string, gouvernoratCode: number, reason: string) =>
      api.request<IncidentDetail>(`${incidentPath(incidentId)}/lead`, {
        method: "POST",
        body: { gouvernorat_code: gouvernoratCode, reason },
      }),

    /** `level: null` returns the incident to the automatic rule (§5.3). */
    setCommandLevel: (incidentId: string, level: CommandLevel | null, reason: string) =>
      api.request<IncidentDetail>(`${incidentPath(incidentId)}/command-level`, { method: "POST", body: { level, reason } }),

    createResourceRequest: (incidentId: string, body: ResourceRequestBody) =>
      api.request<ResourceRequest>(`${incidentPath(incidentId)}/resource-requests`, { method: "POST", body }),

    resourceRequests: (
      opts: PageOpts & { direction?: ResourceRequestDirection; status?: ResourceRequestStatus | "" } = {},
    ) =>
      api.request<Page<ResourceRequest>>(`${S}/resource-requests`, {
        query: {
          direction: opts.direction,
          status: opts.status || undefined,
          cursor: opts.cursor ?? undefined,
          limit: opts.limit ?? 50,
        },
        signal: opts.signal,
      }),

    approveResourceRequest: (id: string, resourceIds: string[], note: string) =>
      api.request<ResourceRequest>(`${requestPath(id)}/approve`, {
        method: "POST",
        body: { resource_ids: resourceIds, note },
      }),

    refuseResourceRequest: (id: string, reason: string) =>
      api.request<ResourceRequest>(`${requestPath(id)}/refuse`, { method: "POST", body: { reason } }),

    cancelResourceRequest: (id: string) =>
      api.request<ResourceRequest>(`${requestPath(id)}/cancel`, { method: "POST", body: {} }),

    // ---------- §6.1 break-glass ----------
    requestBreakGlass: (body: BreakGlassBody) =>
      api.request<BreakGlassGrant>(`${S}/break-glass`, { method: "POST", body }),

    breakGlassGrants: (opts: PageOpts & { status?: BreakGlassStatus | "" } = {}) =>
      api.request<Page<BreakGlassGrant>>(`${S}/break-glass`, {
        query: { status: opts.status || undefined, cursor: opts.cursor ?? undefined, limit: opts.limit ?? 50 },
        signal: opts.signal,
      }),

    revokeBreakGlass: (id: string) =>
      api.request<BreakGlassGrant>(`${grantPath(id)}/revoke`, { method: "POST", body: {} }),

    reviewBreakGlass: (id: string, outcome: "justified" | "unjustified", note: string) =>
      api.request<BreakGlassGrant>(`${grantPath(id)}/review`, { method: "POST", body: { outcome, note } }),

    // ---------- §6.2 accounts ----------
    accounts: (filters: AccountFilters, opts: PageOpts = {}) =>
      api
        .request<Page<StaffAccount> | { items: StaffAccount[] }>(`${S}/accounts`, {
          query: {
            gouvernorat: filters.gouvernorat ?? undefined,
            role: filters.role || undefined,
            q: filters.q?.trim() || undefined,
            cursor: opts.cursor ?? undefined,
          },
          signal: opts.signal,
        })
        .then(asPage),

    createAccount: (body: AccountCreateBody) =>
      api.request<StaffAccount>(`${S}/accounts`, { method: "POST", body }),

    updateAccount: (id: string, body: AccountPatchBody) =>
      api.request<StaffAccount>(accountPath(id), { method: "PATCH", body }),

    resetAccountCredentials: (id: string) =>
      api.request<unknown>(`${accountPath(id)}/reset-credentials`, { method: "POST", body: {} }),

    // ---------- §7.3 scoped audit ----------
    scopedAudit: (filters: AuditFilters, opts: PageOpts = {}) =>
      api.request<Page<ScopedAuditEntry>>(`${S}/audit`, {
        query: {
          action: filters.action?.trim() || undefined,
          from: filters.from || undefined,
          to: filters.to || undefined,
          cursor: opts.cursor ?? undefined,
          limit: opts.limit ?? 50,
        },
        signal: opts.signal,
      }),
  };
}

export type Phase9Api = ReturnType<typeof phase9Api>;

export const p9Keys = {
  settings: ["platform-settings"] as const,
  thresholdSpecs: ["platform-settings", "thresholds"] as const,
  lateAll: ["late-reports"] as const,
  late: (gouvernorat: number | null) => ["late-reports", gouvernorat] as const,
  geoQueue: ["geo-queue"] as const,
  nearby: (reportId: string) => ["nearby-incidents", reportId] as const,
  resourceRequestsAll: ["resource-requests"] as const,
  resourceRequests: (direction: ResourceRequestDirection, status: string) =>
    ["resource-requests", direction, status] as const,
  grantsAll: ["break-glass"] as const,
  grants: (status: string) => ["break-glass", status] as const,
  accountsAll: ["accounts"] as const,
  accounts: (filters: AccountFilters) => ["accounts", filters.gouvernorat ?? null, filters.role ?? "", filters.q ?? ""] as const,
  auditAll: ["scoped-audit"] as const,
  audit: (filters: AuditFilters) => ["scoped-audit", filters.action ?? "", filters.from ?? "", filters.to ?? ""] as const,
};
