import type { ApiClient } from "./api";
import { bboxParam, filtersToQuery, type BBox, type ReportFilters } from "./filters";
import { appFeedbackApi } from "./appFeedback";
import { coastalApi } from "./coastalApi";
import { programmesApi } from "./programmes";
import { crisisApi } from "./crisis";
import { basemapApi } from "./basemap";
import { inventoryApi } from "./inventory";
import { plansApi } from "./plans";
import { registerApi } from "./register";
import { contactApi } from "./contact";
import { opsApi } from "./opsApi";
import { crewApi } from "./crewApi";
import { guideApi } from "./guide";
import { layersApi } from "./layersApi";
import { phase7Api } from "./phase7Api";
import { phase8Api } from "./phase8Api";
import { phase9Api } from "./phase9Api";
import { safetyApi } from "./safetyApi";
import { streamsApi } from "./streamsApi";
import { normalizeOrgFilters, orgFiltersToQuery, type OrgFilters } from "./orgs";
import { doctorsApi } from "./doctorsApi";
import { preventionApi } from "./preventionApi";
import type {
  AiSettings,
  AiStatus,
  Certificate,
  CertificateReviewBody,
  CertificateStamp,
  CertificateStatus,
  CounterView,
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
  StampBody,
  ReportStatus,
  StaffOrg,
  StaffOrgDetail,
  StaffOrgEvent,
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

/**
 * Typed calls for contract section 5 (phase 2), sections 2–4 (phase 3), section 9 (phase 4), the geo reference
 * phase 5 (operations, volunteers, notifications, safety tips: see opsApi.ts) and phase 6 (live streams:
 * see streamsApi.ts), phase 7 (weather, forecast, decision support, telephony: see phase7Api.ts) and phase 8
 * (analytics, reports library, national memory, events library, rewards: see phase8Api.ts) and phase 9 (central
 * and regional rooms, national settings, break-glass, accounts, scoped audit: see phase9Api.ts).
 */
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

    /** Backlog G3: which environment strip to show (public endpoint, null in production). */
    environment: (signal?: AbortSignal) => api.request<EnvironmentInfo>("/api/v1/app/environment", { signal }),

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

    /** Phase P2b: public events declared by institutions in scope, not over yet. */
    orgEvents: (limit = 50, signal?: AbortSignal) =>
      api.request<StaffOrgEvent[]>("/api/v1/staff/org-events", { query: { limit }, signal }),

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

    /** Phase P3a: the certificate shown at the counter, by its code or the verification URL of its QR code. */
    certificateLookup: (code: string, signal?: AbortSignal) =>
      api.request<CounterView>("/api/v1/staff/certificates/lookup", { query: { code }, signal }),
    /** Record the stamp put by hand on the paper certificate (`org_auditor`). */
    addStamp: (certId: string, body: StampBody) =>
      api.request<CertificateStamp>(`/api/v1/staff/certificates/${encodeURIComponent(certId)}/stamps`, {
        method: "POST",
        body,
      }),
    /** The photo of the stamped paper, sent as it is (JPEG or PNG, 5 MB at most). */
    putStampPhoto: (certId: string, stampId: string, file: Blob) =>
      api.request<CertificateStamp>(
        `/api/v1/staff/certificates/${encodeURIComponent(certId)}/stamps/${encodeURIComponent(stampId)}/photo`,
        { method: "PUT", rawBody: file },
      ),
    stampPhoto: (certId: string, stampId: string) =>
      api.request<DownloadLink>(
        `/api/v1/staff/certificates/${encodeURIComponent(certId)}/stamps/${encodeURIComponent(stampId)}/photo`,
      ),
    /** Revoke an approved certificate (`org_auditor`, phase 10 §4.1); the reason stays internal. */
    revokeCertificate: (certId: string, reason: string) =>
      api.request<Certificate>(`/api/v1/staff/certificates/${encodeURIComponent(certId)}/revoke`, {
        method: "POST",
        body: { reason },
      }),

    gouvernorats: (signal?: AbortSignal) =>
      api.request<Gouvernorat[]>("/api/v1/geo/gouvernorats", { query: { lang: "ar" }, signal }),

    ...opsApi(api),
    ...crewApi(api),
    ...streamsApi(api),
    ...phase7Api(api),
    ...phase8Api(api),
    ...phase9Api(api),
    ...layersApi(api),
    ...coastalApi(api),
    ...programmesApi(api),
    ...crisisApi(api),
    ...registerApi(api),
    ...inventoryApi(api),
    ...basemapApi(api),
    ...plansApi(api),
    ...guideApi(api),
    ...preventionApi(api),
    ...contactApi(api),
    ...safetyApi(api),
    ...doctorsApi(api),
    ...appFeedbackApi(api),
  };
}

export type StaffApi = ReturnType<typeof staffApi>;

/** Environment strip (backlog G3): development, field pilot or exercise; null = production, no strip. */
export interface EnvironmentInfo {
  banner: "development" | "pilot" | "training" | null;
}

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
  environment: ["environment"] as const,
  gouvernorats: ["gouvernorats"] as const,
  // Institutions (phase 4). "org" (one detail, audited) and "orgs" (lists) are distinct key roots.
  orgsAll: ["orgs"] as const,
  orgs: (filters: OrgFilters) => ["orgs", normalizeOrgFilters(filters)] as const,
  orgAll: ["org"] as const,
  org: (id: string) => ["org", id] as const,
  orgReportsAll: ["org-reports"] as const,
  orgReports: (id: string) => ["org-reports", id] as const,
  orgDocumentVersions: (orgId: string, docId: string) => ["org-document-versions", orgId, docId] as const,
  orgEvents: ["org-events"] as const,
  orgsMapAll: ["orgs-map"] as const,
  orgsMap: (bbox: BBox) => ["orgs-map", bbox.map((n) => Number(n.toFixed(3)))] as const,
  certificatesAll: ["certificates"] as const,
  certificates: (status: CertificateStatus) => ["certificates", status] as const,
};
