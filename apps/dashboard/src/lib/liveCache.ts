import type { InfiniteData, QueryClient } from "@tanstack/react-query";
import { inBBox, matchesFilters, type BBox, type ReportFilters } from "./filters";
import { isStreamEvent, type LiveEvent } from "./live";
import { p7Keys } from "./phase7Api";
import { opsKeys } from "./opsApi";
import type { LevelRow } from "./opsTypes";
import { compareOrgNames, matchesOrgFilters, type OrgFilters } from "./orgs";
import { comparePriority } from "./priority";
import { queryKeys, type IncidentStatusFilter, type ReportSort } from "./staffApi";
import { applyStreamEvent } from "./streamsCache";
import { TRANSITIONS } from "./status";
import type {
  CertificateEvent,
  IncidentDetail,
  IncidentSummary,
  OrgMapCollection,
  Page,
  QueueCertificate,
  StaffOrg,
  StaffOrgDetail,
  StaffReport,
  StaffReportDetail,
} from "./types";

type ReportsData = InfiniteData<Page<StaffReport>, string | null>;
type IncidentsData = InfiniteData<Page<IncidentSummary>, string | null>;
type OrgsData = InfiniteData<Page<StaffOrg>, string | null>;
type QueueData = InfiniteData<Page<QueueCertificate>, string | null>;

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
    gouvernorats: [...f.gouvernorats].sort((a, b) => a - b),
    period: f.period,
    q: f.q.trim(),
    ...(f.unverified ? { unverified: true } : {}),
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

// ---------- Institutions (phase 4) ----------

/**
 * Place an institution in a name-sorted paged list: remove its old row, then insert it at its rank inside the
 * loaded range. A row ranked after every loaded one is only appended when the list has no further page.
 */
export function mergeOrgIntoPages(data: OrgsData | undefined, org: StaffOrg, matches: boolean): OrgsData | undefined {
  if (!data || !Array.isArray(data.pages) || data.pages.length === 0) return data;
  const pages = data.pages.map((page) =>
    page.items.some((o) => o.id === org.id) ? { ...page, items: page.items.filter((o) => o.id !== org.id) } : page,
  );
  if (matches) {
    let placed = false;
    for (let i = 0; i < pages.length && !placed; i += 1) {
      const page = pages[i];
      if (!page) continue;
      const at = page.items.findIndex((o) => compareOrgNames(org, o) < 0);
      if (at !== -1) {
        pages[i] = { ...page, items: [...page.items.slice(0, at), org, ...page.items.slice(at)] };
        placed = true;
      }
    }
    const last = pages[pages.length - 1];
    if (!placed && last && !last.next_cursor) {
      pages[pages.length - 1] = { ...last, items: [...last.items, org] };
    }
  }
  return { ...data, pages };
}

/** Upsert (active institutions inside the bbox) or remove one point of a cached map layer. */
export function mergeOrgIntoMap(data: OrgMapCollection | undefined, org: StaffOrg, bbox: BBox): OrgMapCollection | undefined {
  if (!data || !Array.isArray(data.features)) return data;
  const features = data.features.filter((f) => f.properties.id !== org.id);
  const loc = org.location;
  if (org.status === "active" && loc && inBBox(loc.lon, loc.lat, bbox)) {
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [loc.lon, loc.lat] },
      properties: {
        id: org.id,
        name: org.name,
        kind: org.kind,
        capacity: org.capacity,
        hazmat_count: org.hazmat_count,
        category: org.classification?.category ?? null,
        family: org.classification?.family ?? null,
      },
    });
  }
  return { ...data, features };
}

function applyOrgUpdate(qc: QueryClient, org: StaffOrg): void {
  for (const [key, data] of qc.getQueriesData<OrgsData>({ queryKey: queryKeys.orgsAll })) {
    const filters = key[1] as OrgFilters | undefined;
    if (!filters || typeof filters !== "object") continue;
    qc.setQueryData<OrgsData>(key, mergeOrgIntoPages(data, org, matchesOrgFilters(org, filters)));
  }

  for (const [key, data] of qc.getQueriesData<OrgMapCollection>({ queryKey: queryKeys.orgsMapAll })) {
    const bbox: unknown = key[1];
    if (!Array.isArray(bbox) || bbox.length !== 4) continue;
    qc.setQueryData<OrgMapCollection>(key, mergeOrgIntoMap(data, org, bbox as unknown as BBox));
  }

  const detailKey = queryKeys.org(org.id);
  const detail = qc.getQueryData<StaffOrgDetail>(detailKey);
  if (detail) {
    qc.setQueryData<StaffOrgDetail>(detailKey, {
      ...detail,
      name: org.name,
      kind: org.kind,
      status: org.status,
      identifier_type: org.identifier_type,
      identifier: org.identifier,
      gouvernorat_code: org.gouvernorat_code,
      capacity: org.capacity,
      location: org.location,
      classification: org.classification,
    });
    // Opening the staff detail writes an audit entry: refetch only a detail that is on screen; a cached
    // one in the background is just marked stale and reloads when it is opened again.
    void qc.invalidateQueries({ queryKey: detailKey, exact: true, refetchType: "active" });
  }
}

function applyCertificateUpdate(qc: QueryClient, cert: CertificateEvent): void {
  for (const [key, data] of qc.getQueriesData<QueueData>({ queryKey: queryKeys.certificatesAll })) {
    const status = key[1];
    if (typeof status !== "string" || !data || !Array.isArray(data.pages)) continue;
    const listed = data.pages.some((p) => p.items.some((c) => c.id === cert.id));
    if (listed) {
      const pages = data.pages.map((p) => ({
        ...p,
        items:
          cert.status === status
            ? p.items.map((c) => (c.id === cert.id ? { ...c, code: cert.code, status: cert.status, org_name: cert.org_name } : c))
            : p.items.filter((c) => c.id !== cert.id),
      }));
      qc.setQueryData<QueueData>(key, { ...data, pages });
    } else if (cert.status === status) {
      // The event lacks submission time and completeness: reload the queue (not an audited endpoint).
      void qc.invalidateQueries({ queryKey: key, exact: true });
    }
  }

  const detailKey = queryKeys.org(cert.org_id);
  const detail = qc.getQueryData<StaffOrgDetail>(detailKey);
  if (detail) {
    qc.setQueryData<StaffOrgDetail>(detailKey, {
      ...detail,
      certificates: detail.certificates.map((c) => (c.id === cert.id ? { ...c, status: cert.status } : c)),
    });
    void qc.invalidateQueries({ queryKey: detailKey, exact: true, refetchType: "active" });
  }

  // The list's certificate column (status, validity) comes from the server: reload lists showing the institution.
  for (const [key, data] of qc.getQueriesData<OrgsData>({ queryKey: queryKeys.orgsAll })) {
    if (data?.pages.some((p) => p.items.some((o) => o.id === cert.org_id))) {
      void qc.invalidateQueries({ queryKey: key, exact: true });
    }
  }
}

/**
 * Apply one live event to react-query caches: report detail, report lists, map queries, incidents and
 * institutions. KPI invalidation is debounced by the caller.
 */
/**
 * Phase 5 events (§10): the level table is patched in place; the other lists are small and scoped, so they are
 * refetched (only the queries on screen, the others when next shown).
 */
function applyOpsEvent(qc: QueryClient, event: LiveEvent): boolean {
  switch (event.type) {
    case "oplevel.changed":
      qc.setQueryData<LevelRow[]>(opsKeys.levels, (rows) =>
        rows?.some((r) => r.gouvernorat_code === event.level.gouvernorat_code)
          ? rows.map((r) => (r.gouvernorat_code === event.level.gouvernorat_code ? event.level : r))
          : rows,
      );
      void qc.invalidateQueries({ queryKey: ["performance"] });
      return true;
    case "directive.issued":
      void qc.invalidateQueries({ queryKey: opsKeys.directivesAll });
      return true;
    case "assignment.updated":
      void qc.invalidateQueries({ queryKey: queryKeys.incident(event.assignment.incident_id) });
      void qc.invalidateQueries({ queryKey: opsKeys.resourcesAll });
      void qc.invalidateQueries({ queryKey: opsKeys.resourceSummary });
      void qc.invalidateQueries({ queryKey: opsKeys.resourcesMapAll });
      return true;
    case "callout.updated":
      void qc.invalidateQueries({ queryKey: queryKeys.incident(event.callout.incident_id) });
      void qc.invalidateQueries({ queryKey: ["volunteer-suggestions", event.callout.incident_id] });
      return true;
    case "resource.updated":
      void qc.invalidateQueries({ queryKey: opsKeys.resourcesAll });
      void qc.invalidateQueries({ queryKey: opsKeys.resourceSummary });
      void qc.invalidateQueries({ queryKey: opsKeys.resourcesMapAll });
      return true;
    case "volunteer.updated":
      void qc.invalidateQueries({ queryKey: opsKeys.volunteersAll });
      void qc.invalidateQueries({ queryKey: opsKeys.volunteer(event.volunteer.id) });
      void qc.invalidateQueries({ queryKey: opsKeys.volunteersMapAll });
      return true;
    case "notification.updated":
    case "alert.issued":
    case "alert.review_needed":
    case "alert.delivery_degraded":
      qc.setQueryData(opsKeys.message(event.message.id), event.message);
      void qc.invalidateQueries({ queryKey: opsKeys.messagesAll });
      if (event.message.kind === "alert") void qc.invalidateQueries({ queryKey: opsKeys.activeAlerts });
      return true;
    default:
      return false;
  }
}

/** Phase 7: the suggestion queue and the calls log are small: refetch what is on screen. */
function applyPhase7Event(qc: QueryClient, event: LiveEvent): boolean {
  switch (event.type) {
    case "weather.suggestion":
      void qc.invalidateQueries({ queryKey: p7Keys.suggestions });
      return true;
    case "call.ringing":
    case "call.answered":
    case "call.ended":
    case "call.recording":
      if (event.call) qc.setQueryData(p7Keys.call(event.call_id), event.call);
      else void qc.invalidateQueries({ queryKey: p7Keys.call(event.call_id) });
      void qc.invalidateQueries({ queryKey: p7Keys.callsAll });
      return true;
    default:
      return false;
  }
}

export function applyLiveEvent(qc: QueryClient, event: LiveEvent, now: number = Date.now()): void {
  if (applyOpsEvent(qc, event)) return;
  if (applyPhase7Event(qc, event)) return;
  if (isStreamEvent(event)) {
    applyStreamEvent(qc, event);
    return;
  }
  if (event.type === "media.stored") {
    // The detail carries pre-signed URLs, so refetch rather than patch.
    void qc.invalidateQueries({ queryKey: queryKeys.report(event.report_id) });
    return;
  }
  if (event.type === "incident.updated") {
    applyIncidentUpdate(qc, event.incident);
    return;
  }
  if (event.type === "org.updated") {
    applyOrgUpdate(qc, event.org);
    return;
  }
  if (event.type === "certificate.updated") {
    applyCertificateUpdate(qc, event.certificate);
    return;
  }
  if (event.type !== "report.created" && event.type !== "report.status_changed" && event.type !== "report.enriched") {
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

  // Reports made on behalf of an institution (phase 4 §8): its "reports" list on the institution page.
  const orgId = report.organization?.id;
  if (orgId) {
    const key = queryKeys.orgReports(orgId);
    qc.setQueryData<ReportsData>(key, (data) => mergeIntoPages(data, report, true, isNew));
  }

  if (!isNew) applyReportToIncidents(qc, report);
}
