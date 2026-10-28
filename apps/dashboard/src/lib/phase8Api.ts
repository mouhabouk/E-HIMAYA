import type { ApiClient } from "./api";
import type {
  AnalyticsFilterQuery,
  AnalyticsOverview,
  BadgeAward,
  BadgeStatus,
  Hotspots,
  LeaderboardRow,
  Leaderboard,
  CalendarGrid,
  CalendarLevel,
  PeriodFigures,
  LibraryItem,
  LibraryKind,
  LibraryQuery,
  LibraryReport,
  LibraryReportBody,
  LibraryReportQuery,
  LibrarySearch,
  LibraryTree,
  MemoryBody,
  MemoryEntry,
  MemoryListItem,
  MemoryListQuery,
  MemoryTransition,
  MemoryVersion,
  MemoryVersionSummary,
  Nomination,
  NominationBody,
  NominationStatus,
  ReportNotifications,
  ReportSchedule,
  RewardCertificate,
  RewardRule,
  RewardRuleBody,
  RewardRulePatch,
  RewardSettings,
  ScenarioBody,
  ScenarioRun,
  ScheduleBody,
  TreeAxis,
  TrendInterval,
  TrendMetric,
  Trends,
} from "./phase8Types";
import type { RecordingDownload } from "./streamsApi";
import type { DownloadLink, Page } from "./types";

const enc = encodeURIComponent;
const A = "/api/v1/staff/analytics";
const LIB = "/api/v1/staff/reports-library";
const SCHED = "/api/v1/staff/report-schedules";
const MEM = "/api/v1/staff/memory";
const EV = "/api/v1/staff/library";
const RW = "/api/v1/staff/rewards";

function filterQuery(f: AnalyticsFilterQuery) {
  return { from: f.from, to: f.to, gouvernorat: f.gouvernorat ?? undefined, category: f.category ?? undefined };
}

/** A list answered as a page or as a bare array. */
function items<T>(body: Page<T> | T[] | { items: T[] }): T[] {
  return Array.isArray(body) ? body : body.items;
}

/**
 * `{"url"}` of a pre-signed link: the API answers 302 by default and `200 {"url"}` when asked for JSON, which a
 * fetch can read (a followed redirect to another origin would need that origin in connect-src).
 */
function linkOf(api: ApiClient, path: string): Promise<DownloadLink> {
  return api.request<DownloadLink>(path);
}

/** Typed calls for docs/api/phase-8-contract.md §1–§3 (analytics and reports, knowledge, rewards). */
export function phase8Api(api: ApiClient) {
  return {
    // ---------- §1 analytics ----------
    analyticsOverview: (f: AnalyticsFilterQuery, signal?: AbortSignal) =>
      api.request<AnalyticsOverview>(`${A}/overview`, { query: filterQuery(f), signal }),

    analyticsTrends: (f: AnalyticsFilterQuery, metric: TrendMetric, interval: TrendInterval, signal?: AbortSignal) =>
      api.request<Trends>(`${A}/trends`, { query: { ...filterQuery(f), metric, interval }, signal }),

    analyticsHotspots: (f: AnalyticsFilterQuery, sizeKm: number, signal?: AbortSignal) =>
      api.request<Hotspots>(`${A}/hotspots`, { query: { ...filterQuery(f), size_km: sizeKm }, signal }),

    runScenario: (body: ScenarioBody) => api.request<ScenarioRun>(`${A}/scenarios`, { method: "POST", body }),

    scenarios: (opts: { cursor?: string | null; signal?: AbortSignal } = {}) =>
      api.request<Page<ScenarioRun>>(`${A}/scenarios`, {
        query: { cursor: opts.cursor ?? undefined },
        signal: opts.signal,
      }),

    scenario: (id: string, signal?: AbortSignal) => api.request<ScenarioRun>(`${A}/scenarios/${enc(id)}`, { signal }),

    reportNotifications: (signal?: AbortSignal) =>
      api.request<ReportNotifications>(`${A}/notifications`, { signal }),

    markReportNotificationRead: (id: string) =>
      api.request<unknown>(`${A}/notifications/${enc(id)}/read`, { method: "POST" }),

    // ---------- §1 reports repository and schedules ----------
    libraryReports: (q: LibraryReportQuery, opts: { cursor?: string | null; signal?: AbortSignal } = {}) =>
      api.request<Page<LibraryReport>>(LIB, {
        query: {
          q: q.q?.trim() || undefined,
          kind: q.kind || undefined,
          status: q.status || undefined,
          from: q.from || undefined,
          to: q.to || undefined,
          gouvernorat: q.gouvernorat ?? undefined,
          cursor: opts.cursor ?? undefined,
        },
        signal: opts.signal,
      }),

    libraryReport: (id: string, signal?: AbortSignal) => api.request<LibraryReport>(`${LIB}/${enc(id)}`, { signal }),

    createLibraryReport: (body: LibraryReportBody) => api.request<LibraryReport>(LIB, { method: "POST", body }),

    /** Pre-signed link of a ready report (audited); `409 report_not_ready` otherwise. */
    libraryReportLink: (id: string) => linkOf(api, `${LIB}/${enc(id)}/download`),

    schedules: async (signal?: AbortSignal) =>
      items(await api.request<Page<ReportSchedule> | ReportSchedule[]>(SCHED, { query: { limit: 100 }, signal })),

    createSchedule: (body: ScheduleBody) => api.request<ReportSchedule>(SCHED, { method: "POST", body }),

    updateSchedule: (id: string, body: Partial<ScheduleBody>) =>
      api.request<ReportSchedule>(`${SCHED}/${enc(id)}`, { method: "PATCH", body }),

    deleteSchedule: (id: string) => api.request<undefined>(`${SCHED}/${enc(id)}`, { method: "DELETE" }),

    // ---------- §2 national memory ----------
    memoryEntries: (q: MemoryListQuery, opts: { cursor?: string | null; signal?: AbortSignal } = {}) =>
      api.request<Page<MemoryListItem>>(MEM, {
        query: {
          q: q.q?.trim() || undefined,
          status: q.status || undefined,
          access: q.access || undefined,
          event_type: q.event_type || undefined,
          gouvernorat: q.gouvernorat ?? undefined,
          cursor: opts.cursor ?? undefined,
        },
        signal: opts.signal,
      }),

    memoryEntry: (id: string, signal?: AbortSignal) => api.request<MemoryEntry>(`${MEM}/${enc(id)}`, { signal }),

    createMemoryEntry: (body: MemoryBody) => api.request<MemoryEntry>(MEM, { method: "POST", body }),

    /** Optimistic: `409 version_conflict` when someone saved in between. */
    updateMemoryEntry: (id: string, body: Partial<MemoryBody> & { version: number }) =>
      api.request<MemoryEntry>(`${MEM}/${enc(id)}`, { method: "PATCH", body }),

    deleteMemoryEntry: (id: string) => api.request<undefined>(`${MEM}/${enc(id)}`, { method: "DELETE" }),

    transitionMemoryEntry: (id: string, body: MemoryTransition) =>
      api.request<MemoryEntry>(`${MEM}/${enc(id)}/transition`, { method: "POST", body }),

    memoryVersions: async (id: string, signal?: AbortSignal) =>
      items(
        await api.request<Page<MemoryVersionSummary> | MemoryVersionSummary[]>(`${MEM}/${enc(id)}/versions`, {
          signal,
        }),
      ),

    memoryVersion: (id: string, version: number, signal?: AbortSignal) =>
      api.request<MemoryVersion>(`${MEM}/${enc(id)}/versions/${version}`, { signal }),

    /** Pre-filled draft for the after-action review; nothing is published automatically. */
    memoryFromIncident: (incidentId: string) =>
      api.request<MemoryEntry>(`${MEM}/from-incident/${enc(incidentId)}`, { method: "POST" }),

    // ---------- §2 events library ----------
    librarySearch: (q: LibraryQuery, opts: { cursor?: string | null; signal?: AbortSignal } = {}) =>
      api.request<LibrarySearch>(`${EV}/search`, {
        query: {
          q: q.q.trim() || undefined,
          kinds: q.kinds,
          from: q.from || undefined,
          to: q.to || undefined,
          gouvernorat: q.gouvernorat ?? undefined,
          category: q.category || undefined,
          cursor: opts.cursor ?? undefined,
        },
        signal: opts.signal,
      }),

    libraryGrid: (level: CalendarLevel, on: string, q: Omit<LibraryQuery, "q">, signal?: AbortSignal) =>
      api.request<CalendarGrid>(`${EV}/calendar/grid`, {
        query: { level, on, kinds: q.kinds, gouvernorat: q.gouvernorat ?? undefined, category: q.category || undefined },
        signal,
      }),

    libraryFigures: (from: string, to: string, q: Omit<LibraryQuery, "q">, signal?: AbortSignal) =>
      api.request<PeriodFigures>(`${EV}/calendar/figures`, {
        query: { from, to, gouvernorat: q.gouvernorat ?? undefined, category: q.category || undefined },
        signal,
      }),


    libraryTree: (by: TreeAxis, q: Omit<LibraryQuery, "q">, signal?: AbortSignal) =>
      api.request<LibraryTree>(`${EV}/tree`, {
        query: { by, kinds: q.kinds, gouvernorat: q.gouvernorat ?? undefined, category: q.category || undefined },
        signal,
      }),

    libraryItem: (kind: LibraryKind, id: string, signal?: AbortSignal) =>
      api.request<LibraryItem>(`${EV}/items/${enc(kind)}/${enc(id)}`, { signal }),

    // ---------- §3 rewards ----------
    rewardSettings: (signal?: AbortSignal) => api.request<RewardSettings>(`${RW}/settings`, { signal }),

    rewardRules: async (signal?: AbortSignal) =>
      items(await api.request<RewardRule[] | Page<RewardRule>>(`${RW}/rules`, { signal })),

    createRewardRule: (body: RewardRuleBody) => api.request<RewardRule>(`${RW}/rules`, { method: "POST", body }),

    updateRewardRule: (id: string, body: RewardRulePatch) =>
      api.request<RewardRule>(`${RW}/rules/${enc(id)}`, { method: "PATCH", body }),

    deleteRewardRule: (id: string) => api.request<undefined>(`${RW}/rules/${enc(id)}`, { method: "DELETE" }),

    badgeAwards: (status: BadgeStatus, opts: { cursor?: string | null; signal?: AbortSignal } = {}) =>
      api.request<Page<BadgeAward>>(`${RW}/badges`, {
        query: { status, cursor: opts.cursor ?? undefined },
        signal: opts.signal,
      }),

    decideBadge: (id: string, action: "confirm" | "reject" | "revoke", reason?: string) =>
      api.request<BadgeAward>(`${RW}/badges/${enc(id)}/${action}`, {
        method: "POST",
        body: action === "confirm" ? {} : { reason: reason?.trim() ?? "" },
      }),

    nominations: (
      q: { status?: NominationStatus | ""; year?: number | null },
      opts: { cursor?: string | null; signal?: AbortSignal } = {},
    ) =>
      api.request<Page<Nomination>>(`${RW}/nominations`, {
        query: { status: q.status || undefined, year: q.year ?? undefined, cursor: opts.cursor ?? undefined },
        signal: opts.signal,
      }),

    createNomination: (body: NominationBody) =>
      api.request<Nomination>(`${RW}/nominations`, { method: "POST", body }),

    decideNomination: (id: string, action: "approve" | "reject", reason: string) =>
      api.request<Nomination>(`${RW}/nominations/${enc(id)}/${action}`, {
        method: "POST",
        body: reason.trim() ? { reason: reason.trim() } : {},
      }),

    rewardCertificates: (opts: { cursor?: string | null; signal?: AbortSignal } = {}) =>
      api.request<Page<RewardCertificate>>(`${RW}/certificates`, {
        query: { cursor: opts.cursor ?? undefined },
        signal: opts.signal,
      }),

    issueRewardCertificate: (source: { nomination_id: string } | { badge_award_id: string }) =>
      api.request<RewardCertificate>(`${RW}/certificates`, { method: "POST", body: source }),

    revokeRewardCertificate: (id: string, reason: string) =>
      api.request<RewardCertificate>(`${RW}/certificates/${enc(id)}/revoke`, {
        method: "POST",
        body: { reason: reason.trim() },
      }),

    /**
     * Certificate PDF (audited): `{"url"}` of a pre-signed link when the API honours `Accept: application/json`,
     * otherwise the PDF itself (same handling as the call recordings of phase 7).
     */
    rewardCertificatePdf: async (id: string): Promise<RecordingDownload> => {
      const response = await api.requestRaw(`${RW}/certificates/${enc(id)}/pdf`, {
        accept: "application/json, application/pdf;q=0.9",
      });
      const type = response.headers.get("Content-Type") ?? "";
      if (type.includes("application/json")) {
        const body = (await response.json()) as { url?: unknown };
        if (typeof body.url === "string") return { kind: "link", url: body.url };
      }
      return { kind: "file", blob: await response.blob(), url: response.url };
    },

    leaderboard: async (
      q: { scope: "gouvernorat" | "national"; gouvernorat?: number | null; year: number },
      signal?: AbortSignal,
    ): Promise<Leaderboard> => {
      const body = await api.request<Leaderboard | LeaderboardRow[]>(`${RW}/leaderboard`, {
        query: { scope: q.scope, gouvernorat: q.gouvernorat ?? undefined, period: "year", year: q.year },
        signal,
      });
      return Array.isArray(body)
        ? { scope: q.scope, gouvernorat_code: q.gouvernorat ?? null, year: q.year, items: body }
        : body;
    },
  };
}

export type Phase8Api = ReturnType<typeof phase8Api>;

export const p8Keys = {
  overview: (f: AnalyticsFilterQuery) => ["analytics-overview", f.from, f.to, f.gouvernorat, f.category] as const,
  trends: (f: AnalyticsFilterQuery, metric: TrendMetric, interval: TrendInterval) =>
    ["analytics-trends", f.from, f.to, f.gouvernorat, f.category, metric, interval] as const,
  hotspots: (f: AnalyticsFilterQuery, size: number) =>
    ["analytics-hotspots", f.from, f.to, f.gouvernorat, f.category, size] as const,
  scenariosAll: ["scenarios"] as const,
  scenario: (id: string) => ["scenario", id] as const,
  reportNotifications: ["report-notifications"] as const,
  libraryReportsAll: ["library-reports"] as const,
  libraryReports: (q: LibraryReportQuery) =>
    ["library-reports", q.q ?? "", q.kind ?? "", q.status ?? "", q.from ?? "", q.to ?? "", q.gouvernorat] as const,
  schedules: ["report-schedules"] as const,
  memoryAll: ["memory"] as const,
  memoryList: (q: MemoryListQuery) =>
    ["memory", "list", q.q ?? "", q.status ?? "", q.access ?? "", q.event_type ?? "", q.gouvernorat] as const,
  memoryEntry: (id: string) => ["memory", "entry", id] as const,
  memoryVersions: (id: string) => ["memory", "versions", id] as const,
  memoryVersion: (id: string, v: number) => ["memory", "version", id, v] as const,
  librarySearch: (q: LibraryQuery) =>
    ["library-search", q.q, q.kinds.join(","), q.from ?? "", q.to ?? "", q.gouvernorat, q.category ?? ""] as const,
  libraryGrid: (level: CalendarLevel, on: string, q: Omit<LibraryQuery, "q">) =>
    ["library-grid", level, on, q.kinds.join(","), q.gouvernorat, q.category ?? ""] as const,
  libraryFigures: (from: string, to: string, q: Omit<LibraryQuery, "q">) =>
    ["library-figures", from, to, q.gouvernorat, q.category ?? ""] as const,
  libraryTree: (by: TreeAxis, q: Omit<LibraryQuery, "q">) =>
    ["library-tree", by, q.kinds.join(","), q.gouvernorat, q.category ?? ""] as const,
  libraryItem: (kind: string, id: string) => ["library-item", kind, id] as const,
  rewardSettings: ["reward-settings"] as const,
  rewardRules: ["reward-rules"] as const,
  badges: (status: BadgeStatus) => ["reward-badges", status] as const,
  badgesAll: ["reward-badges"] as const,
  nominationsAll: ["reward-nominations"] as const,
  nominations: (status: string, year: number | null) => ["reward-nominations", status, year] as const,
  certificates: ["reward-certificates"] as const,
  leaderboard: (scope: string, gouvernorat: number | null, year: number) =>
    ["reward-leaderboard", scope, gouvernorat, year] as const,
};
