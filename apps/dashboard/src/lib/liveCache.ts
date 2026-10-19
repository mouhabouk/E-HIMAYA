import type { InfiniteData, QueryClient } from "@tanstack/react-query";
import { matchesFilters, type BBox, type ReportFilters } from "./filters";
import type { LiveEvent } from "./live";
import { comparePriority } from "./priority";
import { queryKeys, type IncidentStatusFilter, type ReportSort } from "./staffApi";
import { TRANSITIONS } from "./status";
import type { IncidentDetail, IncidentSummary, Page, StaffReport, StaffReportDetail } from "./types";

type ReportsData = InfiniteData<Page<StaffReport>, string | null>;
type IncidentsData = InfiniteData<Page<IncidentSummary>, string | null>;

/** Query keys used by list and map so the cache updater can recover their filters (and the list's sort). */
export function listKey(filters: ReportFilters, sort: ReportSort = "received") {
  return [...queryKeys.reportsAll, normalizeFilters(filters), sort] as const;
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

/**
 * Insert/replace/remove `report` in paged data according to whether it still matches the filters.
 * Newest-first lists get new reports on top; priority lists insert them at their rank in the first page.
 */
export function mergeIntoPages(
  data: ReportsData | undefined,
  report: StaffReport,
  matches: boolean,
  insertIfMissing: boolean,
  sort: ReportSort = "received",
): ReportsData | undefined {
  if (!data || data.pages.length === 0) return data;
  const pageIndex = data.pages.findIndex((page) => page.items.some((r) => r.id === report.id));
  if (pageIndex === -1) {
    const first = data.pages[0];
    if (!first || !matches || !insertIfMissing) return data;
    const items =
      sort === "priority" ? [...first.items, report].sort(comparePriority) : [report, ...first.items];
    return { ...data, pages: [{ ...first, items }, ...data.pages.slice(1)] };
  }
  const pages = data.pages.map((page, i) => {
    if (i !== pageIndex) return page;
    if (!matches) return { ...page, items: page.items.filter((r) => r.id !== report.id) };
    const items = page.items.map((r) => (r.id === report.id ? { ...r, ...report } : r));
    // A new score moves the row within its page (moving across loaded pages would break the cursors).
    return { ...page, items: sort === "priority" ? items.sort(comparePriority) : items };
  });
  return { ...data, pages };
}

/** Same for incident lists (newest activity first): an updated incident moves to the top. */
export function mergeIncidentIntoPages(
  data: IncidentsData | undefined,
  incident: IncidentSummary,
  matches: boolean,
): IncidentsData | undefined {
  if (!data || !Array.isArray(data.pages) || data.pages.length === 0) return data;
  const pages = data.pages.map((page) => ({ ...page, items: page.items.filter((i) => i.id !== incident.id) }));
  const first = pages[0];
  if (matches && first) pages[0] = { ...first, items: [incident, ...first.items] };
  return { ...data, pages };
}

function incidentMatches(incident: IncidentSummary, filter: unknown): boolean {
  if (filter === "all") return true;
  if (typeof filter !== "string") return false;
  return filter.split(",").includes(incident.status);
}

function applyIncidentUpdate(qc: QueryClient, incident: IncidentSummary): void {
  for (const [key, data] of qc.getQueriesData<IncidentsData>({ queryKey: queryKeys.incidentsAll })) {
    const filter = key[1] as IncidentStatusFilter | undefined;
    if (filter === undefined) continue;
    qc.setQueryData<IncidentsData>(key, mergeIncidentIntoPages(data, incident, incidentMatches(incident, filter)));
  }
  void qc.invalidateQueries({ queryKey: queryKeys.mergeCandidates });
  const detailKey = queryKeys.incident(incident.id);
  const detail = qc.getQueryData<IncidentDetail>(detailKey);
  if (detail) {
    // Patch the summary at once; members and timeline come with the refetch.
    qc.setQueryData<IncidentDetail>(detailKey, { ...detail, ...incident, reports: detail.reports, timeline: detail.timeline });
    void qc.invalidateQueries({ queryKey: detailKey });
  }
}

/** Keep cached incident details' member lists in line with a report's (new) incident. */
function applyReportToIncidents(qc: QueryClient, report: StaffReport): void {
  for (const [key, detail] of qc.getQueriesData<IncidentDetail>({ queryKey: queryKeys.incidentAll })) {
    if (!detail) continue;
    const listed = detail.reports.some((r) => r.id === report.id);
    if (report.incident_id === detail.id) {
      if (listed) {
        qc.setQueryData<IncidentDetail>(key, {
          ...detail,
          reports: detail.reports.map((r) => (r.id === report.id ? { ...r, ...report } : r)),
        });
      } else {
        void qc.invalidateQueries({ queryKey: key });
      }
    } else if (listed) {
      qc.setQueryData<IncidentDetail>(key, { ...detail, reports: detail.reports.filter((r) => r.id !== report.id) });
      void qc.invalidateQueries({ queryKey: key });
    }
  }
}

/**
 * Apply one live event to react-query caches: report detail, report lists, map queries and incidents.
 * KPI invalidation is debounced by the caller.
 */
export function applyLiveEvent(qc: QueryClient, event: LiveEvent, now: number = Date.now()): void {
  if (event.type === "media.stored") {
    // The detail carries pre-signed URLs, so refetch rather than patch.
    void qc.invalidateQueries({ queryKey: queryKeys.report(event.report_id) });
    return;
  }
  if (event.type === "incident.updated") {
    applyIncidentUpdate(qc, event.incident);
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
      analysis: detail.analysis,
      allowed_transitions:
        detail.status !== report.status ? [...TRANSITIONS[report.status]] : detail.allowed_transitions,
    });
    // A new status needs the server's history; an enrichment brings a new analysis (scores, suggestion).
    if (detail.status !== report.status || event.type === "report.enriched") {
      void qc.invalidateQueries({ queryKey: queryKeys.report(report.id) });
    }
  }

  for (const [key, data] of qc.getQueriesData<ReportsData>({ queryKey: queryKeys.reportsAll })) {
    const filters = key[1] as ReportFilters | undefined;
    if (!filters) continue;
    const sort: ReportSort = key[2] === "priority" ? "priority" : "received";
    const matches = matchesFilters(report, filters, { now });
    qc.setQueryData<ReportsData>(key, mergeIntoPages(data, report, matches, isNew, sort));
  }

  for (const [key, data] of qc.getQueriesData<ReportsData>({ queryKey: queryKeys.mapReportsAll })) {
    const filters = key[1] as ReportFilters | undefined;
    const bbox = key[2] as BBox | undefined;
    if (!filters || !bbox) continue;
    const matches = matchesFilters(report, filters, { now, bbox });
    qc.setQueryData<ReportsData>(key, mergeIntoPages(data, report, matches, true));
  }

  if (!isNew) applyReportToIncidents(qc, report);
}
