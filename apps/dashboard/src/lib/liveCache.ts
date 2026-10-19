import type { InfiniteData, QueryClient } from "@tanstack/react-query";
import { matchesFilters, type BBox, type ReportFilters } from "./filters";
import type { LiveEvent } from "./live";
import { queryKeys } from "./staffApi";
import { TRANSITIONS } from "./status";
import type { Page, StaffReport, StaffReportDetail } from "./types";

type ReportsData = InfiniteData<Page<StaffReport>, string | null>;

/** Query keys used by list and map so the cache updater can recover their filters. */
export function listKey(filters: ReportFilters) {
  return [...queryKeys.reportsAll, normalizeFilters(filters)] as const;
}

export function mapKey(filters: ReportFilters, bbox: BBox) {
  return [...queryKeys.mapReportsAll, normalizeFilters(filters), bbox.map((n) => Number(n.toFixed(3)))] as const;
}

export function normalizeFilters(f: ReportFilters): ReportFilters {
  return {
    statuses: [...f.statuses].sort(),
    categories: [...f.categories].sort(),
    gouvernorat: f.gouvernorat,
    period: f.period,
    q: f.q.trim(),
  };
}

/** Insert/replace/remove `report` in paged data according to whether it still matches the filters. */
export function mergeIntoPages(
  data: ReportsData | undefined,
  report: StaffReport,
  matches: boolean,
  insertIfMissing: boolean,
): ReportsData | undefined {
  if (!data || data.pages.length === 0) return data;
  const pageIndex = data.pages.findIndex((page) => page.items.some((r) => r.id === report.id));
  if (pageIndex === -1) {
    const first = data.pages[0];
    if (!first || !matches || !insertIfMissing) return data;
    return { ...data, pages: [{ ...first, items: [report, ...first.items] }, ...data.pages.slice(1)] };
  }
  const pages = data.pages.map((page, i) => {
    if (i !== pageIndex) return page;
    const items = matches
      ? page.items.map((r) => (r.id === report.id ? { ...r, ...report } : r))
      : page.items.filter((r) => r.id !== report.id);
    return { ...page, items };
  });
  return { ...data, pages };
}

/**
 * Apply one live event to react-query caches: report detail, incident lists and map queries.
 * KPI invalidation is debounced by the caller.
 */
export function applyLiveEvent(qc: QueryClient, event: LiveEvent, now: number = Date.now()): void {
  if (event.type === "media.stored") {
    // The detail carries pre-signed URLs, so refetch rather than patch.
    void qc.invalidateQueries({ queryKey: queryKeys.report(event.report_id) });
    return;
  }
  const report = event.report;
  const isNew = event.type === "report.created";

  const detail = qc.getQueryData<StaffReportDetail>(queryKeys.report(report.id));
  if (detail) {
    qc.setQueryData<StaffReportDetail>(queryKeys.report(report.id), {
      ...detail,
      ...report,
      media: detail.media,
      history: detail.history,
      reporter: detail.reporter,
      allowed_transitions:
        detail.status !== report.status ? [...TRANSITIONS[report.status]] : detail.allowed_transitions,
    });
    if (detail.status !== report.status) {
      void qc.invalidateQueries({ queryKey: queryKeys.report(report.id) });
    }
  }

  for (const [key, data] of qc.getQueriesData<ReportsData>({ queryKey: queryKeys.reportsAll })) {
    const filters = key[1] as ReportFilters | undefined;
    if (!filters) continue;
    const matches = matchesFilters(report, filters, { now });
    qc.setQueryData<ReportsData>(key, mergeIntoPages(data, report, matches, isNew));
  }

  for (const [key, data] of qc.getQueriesData<ReportsData>({ queryKey: queryKeys.mapReportsAll })) {
    const filters = key[1] as ReportFilters | undefined;
    const bbox = key[2] as BBox | undefined;
    if (!filters || !bbox) continue;
    const matches = matchesFilters(report, filters, { now, bbox });
    qc.setQueryData<ReportsData>(key, mergeIntoPages(data, report, matches, true));
  }
}
