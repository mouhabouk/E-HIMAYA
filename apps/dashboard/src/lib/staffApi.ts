import type { ApiClient } from "./api";
import { bboxParam, filtersToQuery, type BBox, type ReportFilters } from "./filters";
import { normalizeOrgFilters, orgFiltersToQuery, type OrgFilters } from "./orgs";
import type {
  AiSettings,
  AiStatus,
  Certificate,
  CertificateReviewBody,
  CertificateStatus,
  DocumentVersion,
  DownloadLink,
  Gouvernorat,
  IncidentDetail,
  IncidentLinkBody,
  IncidentStatus,
  IncidentSummary,
  Kpis,
  OrgMapCollection,
  OrgReviewBody,
  Page,
  QueueCertificate,
  ReportStatus,
  StaffOrg,
  StaffOrgDetail,
  StaffReport,
  StaffReportDetail,
} from "./types";

/** `sort` of the staff reports list (phase 3): newest first (default) or highest priority first. */
export type ReportSort = "received" | "priority";

/** `status` of the incidents list: one status or "all". */
export type IncidentStatusFilter = IncidentStatus | "all";

const reportPath = (id: string) => `/api/v1/staff/reports/${encodeURIComponent(id)}`;
const incidentPath = (id: string) => `/api/v1/staff/incidents/${encodeURIComponent(id)}`;
const orgPath = (id: string) => `/api/v1/staff/orgs/${encodeURIComponent(id)}`;
const docPath = (orgId: string, docId: string) => `${orgPath(orgId)}/documents/${encodeURIComponent(docId)}`;

/** Typed calls for contract section 5 (phase 2), sections 2–4 (phase 3), section 9 (phase 4) and the geo reference. */
export function staffApi(api: ApiClient) {
  return {
    kpis: (since: string, signal?: AbortSignal) =>
      api.request<Kpis>("/api/v1/staff/kpis", { query: { since }, signal }),

    reports: (
      filters: ReportFilters,
      opts: {
        cursor?: string | null;
        bbox?: BBox | null;
        limit?: number;
        signal?: AbortSignal;
        sort?: ReportSort;
        incidentId?: string | null;
      } = {},
    ) =>
      api.request<Page<StaffReport>>("/api/v1/staff/reports", {
        query: {
          ...filtersToQuery(filters, { cursor: opts.cursor, bbox: opts.bbox, limit: opts.limit }),
          // "received" is the server default: only send the parameter when it changes something.
          sort: opts.sort === "priority" ? "priority" : undefined,
          incident_id: opts.incidentId ?? undefined,
        },
        signal: opts.signal,
      }),

    report: (id: string, signal?: AbortSignal) => api.request<StaffReportDetail>(reportPath(id), { signal }),

    changeStatus: (id: string, status: ReportStatus, note?: string) =>
      api.request<StaffReportDetail>(`${reportPath(id)}/status`, {
        method: "POST",
        body: note?.trim() ? { status, note: note.trim() } : { status },
      }),

    incidents: (
      opts: { status?: IncidentStatusFilter; cursor?: string | null; limit?: number; signal?: AbortSignal } = {},
    ) =>
      api.request<Page<IncidentSummary>>("/api/v1/staff/incidents", {
        query: { status: opts.status ?? "open", limit: opts.limit ?? 50, cursor: opts.cursor ?? undefined },
        signal: opts.signal,
      }),

    incident: (id: string, signal?: AbortSignal) => api.request<IncidentDetail>(incidentPath(id), { signal }),

    /** accept_suggestion / link / new (BR-11: grouping is always confirmed by an operator). */
    linkIncident: (reportId: string, body: IncidentLinkBody) =>
      api.request<StaffReportDetail>(`${reportPath(reportId)}/incident`, { method: "POST", body }),

    detachIncident: (reportId: string) =>
      api.request<StaffReportDetail>(`${reportPath(reportId)}/incident`, { method: "DELETE" }),

    dismissSuggestion: (reportId: string) =>
      api.request<StaffReportDetail>(`${reportPath(reportId)}/suggestion/dismiss`, { method: "POST" }),

    /** Move the reports of `otherId` into `targetId`; answers the target incident. */
    mergeIncident: (targetId: string, otherId: string) =>
      api.request<IncidentDetail>(`${incidentPath(targetId)}/merge`, {
        method: "POST",
        body: { incident_id: otherId },
      }),

    aiSettings: (signal?: AbortSignal) => api.request<AiSettings>("/api/v1/staff/ai/settings", { signal }),

    saveAiSettings: (settings: AiSettings) =>
      api.request<AiSettings>("/api/v1/staff/ai/settings", { method: "PUT", body: settings }),

    aiStatus: (signal?: AbortSignal) => api.request<AiStatus>("/api/v1/staff/ai/status", { signal }),

    // ---------- Institutions (phase 4 §9) ----------

    orgs: (filters: OrgFilters, opts: { cursor?: string | null; limit?: number; signal?: AbortSignal } = {}) =>
      api.request<Page<StaffOrg>>("/api/v1/staff/orgs", {
        query: orgFiltersToQuery(filters, opts),
        signal: opts.signal,
      }),

    /** Opening a staff institution detail is written to the audit log: fetch it only when shown. */
    org: (id: string, signal?: AbortSignal) => api.request<StaffOrgDetail>(orgPath(id), { signal }),

    orgReports: (id: string, opts: { cursor?: string | null; limit?: number; signal?: AbortSignal } = {}) =>
      api.request<Page<StaffReport>>(`${orgPath(id)}/reports`, {
        query: { limit: opts.limit ?? 50, cursor: opts.cursor ?? undefined },
        signal: opts.signal,
      }),

    /**
     * Version history of a document. Not listed in §9 for staff: assumed to mirror the portal endpoint
     * (`GET /api/v1/orgs/{id}/documents/{doc_id}/versions`) under `/api/v1/staff/orgs`.
     */
    orgDocumentVersions: (orgId: string, docId: string, signal?: AbortSignal) =>
      api.request<DocumentVersion[]>(`${docPath(orgId, docId)}/versions`, { signal }),

    /** Pre-signed download link (10 minutes) of one version of a document. */
    orgDocumentDownload: (orgId: string, docId: string, version: number) =>
      api.request<DownloadLink>(`${docPath(orgId, docId)}/versions/${encodeURIComponent(String(version))}/download`),

    /** Pre-signed link (10 minutes) to a certificate's PDF. */
    certificatePdf: (orgId: string, certId: string) =>
      api.request<DownloadLink>(`${orgPath(orgId)}/certificates/${encodeURIComponent(certId)}/pdf`),

    /** Active institutions in scope inside `bbox` (map layer «المؤسسات»). */
    orgsMap: (bbox: BBox, signal?: AbortSignal) =>
      api.request<OrgMapCollection>("/api/v1/staff/orgs/map", { query: { bbox: bboxParam(bbox) }, signal }),

    /** Registration review (`org_auditor`): approve / reject / suspend / reinstate. */
    reviewOrg: (id: string, body: OrgReviewBody) =>
      api.request<StaffOrgDetail>(`${orgPath(id)}/review`, {
        method: "POST",
        body: body.reason?.trim() ? { decision: body.decision, reason: body.reason.trim() } : { decision: body.decision },
      }),

    /** Certificate review queue, oldest submission first. */
    certificates: (
      opts: { status?: CertificateStatus; cursor?: string | null; limit?: number; signal?: AbortSignal } = {},
    ) =>
      api.request<Page<QueueCertificate>>("/api/v1/staff/certificates", {
        query: { status: opts.status ?? "submitted", limit: opts.limit ?? 50, cursor: opts.cursor ?? undefined },
        signal: opts.signal,
      }),

    /** Certificate review (`org_auditor`): approve with `valid_until`, or reject with a reason. */
    reviewCertificate: (certId: string, body: CertificateReviewBody) =>
      api.request<Certificate>(`/api/v1/staff/certificates/${encodeURIComponent(certId)}/review`, {
        method: "POST",
        body,
      }),

    gouvernorats: (signal?: AbortSignal) =>
      api.request<Gouvernorat[]>("/api/v1/geo/gouvernorats", { query: { lang: "ar" }, signal }),
  };
}

export type StaffApi = ReturnType<typeof staffApi>;

export const queryKeys = {
  kpis: (period: string) => ["kpis", period] as const,
  reportsAll: ["reports"] as const,
  reports: (key: readonly unknown[]) => ["reports", ...key] as const,
  mapReportsAll: ["map-reports"] as const,
  mapReports: (key: readonly unknown[], bbox: string) => ["map-reports", ...key, bbox] as const,
  report: (id: string) => ["report", id] as const,
  incidentsAll: ["incidents"] as const,
  incidents: (status: IncidentStatusFilter) => ["incidents", status] as const,
  incidentAll: ["incident"] as const,
  /** Open incidents offered as merge candidates (a plain page, not an infinite list). */
  mergeCandidates: ["incident-candidates"] as const,
  incident: (id: string) => ["incident", id] as const,
  aiSettings: ["ai-settings"] as const,
  aiStatus: ["ai-status"] as const,
  gouvernorats: ["gouvernorats"] as const,
  // Institutions (phase 4). "org" (one detail, audited) and "orgs" (lists) are distinct key roots.
  orgsAll: ["orgs"] as const,
  orgs: (filters: OrgFilters) => ["orgs", normalizeOrgFilters(filters)] as const,
  orgAll: ["org"] as const,
  org: (id: string) => ["org", id] as const,
  orgReportsAll: ["org-reports"] as const,
  orgReports: (id: string) => ["org-reports", id] as const,
  orgDocumentVersions: (orgId: string, docId: string) => ["org-document-versions", orgId, docId] as const,
  orgsMapAll: ["orgs-map"] as const,
  orgsMap: (bbox: BBox) => ["orgs-map", bbox.map((n) => Number(n.toFixed(3)))] as const,
  certificatesAll: ["certificates"] as const,
  certificates: (status: CertificateStatus) => ["certificates", status] as const,
};
