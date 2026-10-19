import type { ApiClient } from "./api";
import { filtersToQuery, type BBox, type ReportFilters } from "./filters";
import type { Gouvernorat, Kpis, Page, ReportStatus, StaffReport, StaffReportDetail } from "./types";

/** Typed calls for contract section 5 and the geo reference. */
export function staffApi(api: ApiClient) {
  return {
    kpis: (since: string, signal?: AbortSignal) =>
      api.request<Kpis>("/api/v1/staff/kpis", { query: { since }, signal }),

    reports: (
      filters: ReportFilters,
      opts: { cursor?: string | null; bbox?: BBox | null; limit?: number; signal?: AbortSignal } = {},
    ) =>
      api.request<Page<StaffReport>>("/api/v1/staff/reports", {
        query: filtersToQuery(filters, { cursor: opts.cursor, bbox: opts.bbox, limit: opts.limit }),
        signal: opts.signal,
      }),

    report: (id: string, signal?: AbortSignal) =>
      api.request<StaffReportDetail>(`/api/v1/staff/reports/${encodeURIComponent(id)}`, { signal }),

    changeStatus: (id: string, status: ReportStatus, note?: string) =>
      api.request<StaffReportDetail>(`/api/v1/staff/reports/${encodeURIComponent(id)}/status`, {
        method: "POST",
        body: note?.trim() ? { status, note: note.trim() } : { status },
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
  gouvernorats: ["gouvernorats"] as const,
};
