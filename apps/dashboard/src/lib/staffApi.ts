import type { ApiClient } from "./api";
import { filtersToQuery, type BBox, type ReportFilters } from "./filters";
import type {
  AiSettings,
  AiStatus,
  Gouvernorat,
  IncidentDetail,
  IncidentLinkBody,
  IncidentStatus,
  IncidentSummary,
  Kpis,
  Page,
  ReportStatus,
  StaffReport,
  StaffReportDetail,
} from "./types";

/** `sort` of the staff reports list (phase 3): newest first (default) or highest priority first. */
export type ReportSort = "received" | "priority";

/** `status` of the incidents list: one status or "all". */
export type IncidentStatusFilter = IncidentStatus | "all";

const reportPath = (id: string) => `/api/v1/staff/reports/${encodeURIComponent(id)}`;
const incidentPath = (id: string) => `/api/v1/staff/incidents/${encodeURIComponent(id)}`;

/** Typed calls for contract section 5 (phase 2), sections 2–4 (phase 3) and the geo reference. */
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
};
