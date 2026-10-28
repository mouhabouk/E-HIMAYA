import { vi } from "vitest";
import type { Phase8Api } from "../lib/phase8Api";
import type { CalendarLevel } from "../lib/phase8Types";
import { fakeFigures, fakeGrid } from "./libraryCalendarData";
import type {
  AnalyticsOverview,
  BadgeAward,
  Hotspots,
  LibraryItem,
  LibraryReport,
  LibrarySearch,
  MemoryEntry,
  Nomination,
  ReportSchedule,
  RewardCertificate,
  RewardRule,
  RewardSettings,
  ScenarioRun,
  Trends,
} from "../lib/phase8Types";

export function makeOverview(overrides: Partial<AnalyticsOverview> = {}): AnalyticsOverview {
  return {
    from: "2026-07-23",
    to: "2026-10-20",
    gouvernorats: [],
    category: null,
    totals: { received: 1240, verified: 980, in_progress: 42, closed: 900, rejected: 61 },
    response_time: {
      to_assignment: { mean_s: 312, p90_s: 840, n: 950 },
      to_on_scene: { mean_s: 1260, p90_s: 2400, n: 870 },
      to_closed: { mean_s: null, p90_s: null, n: 0 },
    },
    by_category: [
      { key: "fire", count: 610 },
      { key: "flood", count: 120 },
    ],
    by_gouvernorat: [
      { key: 61, count: 700 },
      { key: 11, count: 540 },
    ],
    by_status: [{ key: "closed", count: 900 }],
    by_source: [
      { key: "app", count: 800 },
      { key: "call", count: 440 },
    ],
    by_hour: [{ key: 14, count: 120 }],
    by_weekday: [{ key: 1, count: 200 }],
    min_cell: 5,
    ...overrides,
  };
}

export function makeTrends(overrides: Partial<Trends> = {}): Trends {
  return {
    metric: "reports",
    interval: "week",
    points: [
      { period_start: "2026-09-28", value: 80, last_year: 70, expected: 75, low: 60, high: 90 },
      { period_start: "2026-10-05", value: 130, last_year: 72, expected: 78, low: 62, high: 94 },
      { period_start: "2026-10-12", value: 85, last_year: null, expected: 76, low: 61, high: 92 },
    ],
    baseline_available: true,
    unit: "count",
    ...overrides,
  };
}

const hexRing = (lon: number, lat: number, r = 0.05): [number, number][] => {
  const ring: [number, number][] = [];
  for (let i = 0; i < 6; i += 1) {
    const a = (Math.PI / 3) * i;
    ring.push([lon + r * Math.cos(a), lat + r * Math.sin(a)]);
  }
  ring.push(ring[0] as [number, number]);
  return ring;
};

export function makeHotspots(): Hotspots {
  return {
    type: "FeatureCollection",
    cell_size_m: 5000,
    features: [
      { type: "Feature", properties: { id: "12:40", count: 42 }, geometry: { type: "Polygon", coordinates: [hexRing(10.76, 34.74)] } },
      { type: "Feature", properties: { id: "13:40", count: 7 }, geometry: { type: "Polygon", coordinates: [hexRing(10.18, 36.8)] } },
    ],
  };
}

export function makeScenario(overrides: Partial<ScenarioRun> = {}): ScenarioRun {
  const hours = Array.from({ length: 6 }, (_, h) => ({
    hour: h,
    at: new Date(Date.UTC(2026, 9, 20, 8 + h)).toISOString(),
    demand: { p10: 2 + h, p50: 3 + h, p90: 5 + h },
    wait_minutes: { p10: 2, p50: 5 + h * 3, p90: 12 + h * 4 },
    utilisation: { p10: 0.4, p50: Math.min(1, 0.5 + h * 0.1), p90: Math.min(1, 0.7 + h * 0.08) },
    overloaded: h >= 4,
  }));
  return {
    id: "sc-1",
    name: "Canicule Sfax",
    status: "done",
    seed: 4242,
    runs: 500,
    params: {
      name: "Canicule Sfax",
      gouvernorats: [61],
      category: "fire",
      demand_factor: 2.5,
      unavailable_resources: { fire_engine: 2 },
      horizon_hours: 6,
      weather: "fire_danger_extreme",
    },
    result: {
      hours,
      overload_hours: [4, 5],
      summary: {
        reports_per_hour: { p10: 3, p50: 5, p90: 8 },
        wait_minutes: { p10: 3, p50: 9, p90: 25 },
        utilisation: { p10: 0.5, p50: 0.8, p90: 0.98 },
        capacity: 7,
        total_reports: { p10: 20, p50: 33, p90: 51 },
      },
      assumptions: [{ ar: "يعاد تشغيل نسق الوصول التاريخي.", fr: "Le rythme d’arrivée historique est rejoué." }],
      disclaimer: { ar: "أداة تخطيط مبنية على السجل.", fr: "Outil de planification fondé sur l’historique." },
      calibration: "uncalibrated",
      calibration_note: { ar: "غير معاير.", fr: "Modèle non calibré sur des crises réelles." },
      confidence: "low",
      confidence_reasons: [{ ar: "سجل قصير.", fr: "Historique court (40 jours)." }],
    },
    created_at: "2026-10-20T08:00:00Z",
    created_by: "u-1",
    ...overrides,
  };
}

export function makeLibraryReport(overrides: Partial<LibraryReport> = {}): LibraryReport {
  return {
    id: "rep-1",
    kind: "period_summary",
    title: "Synthèse septembre",
    period_from: "2026-09-01",
    period_to: "2026-09-30",
    gouvernorats: [61],
    filters: {},
    format: "pdf",
    status: "ready",
    media_id: "m-1",
    sha256: "a".repeat(64),
    created_by: "u-1",
    schedule_id: null,
    created_at: "2026-10-01T07:00:00Z",
    lang: "fr",
    ...overrides,
  };
}

export function makeSchedule(overrides: Partial<ReportSchedule> = {}): ReportSchedule {
  return {
    id: "sch-1",
    title: "Hebdo Sfax",
    kind: "gouvernorat_summary",
    filters: {},
    gouvernorats: [61],
    format: "pdf",
    lang: "fr",
    cron: { frequency: "weekly", time: "07:00", weekday: 1 },
    recipients: ["5f0c8e4a-1b2c-4d3e-8f90-a1b2c3d4e5f6"],
    enabled: true,
    next_run_at: "2026-10-26T06:00:00Z",
    ...overrides,
  };
}

const text = (ar: string, fr: string) => ({ ar, fr });

export function makeMemoryEntry(overrides: Partial<MemoryEntry> = {}): MemoryEntry {
  return {
    id: "mem-1",
    title: text("حرائق غابات الكاف 2026", "Feux de forêt du Kef 2026"),
    event_type: "fire",
    started_at: "2026-08-02T10:00:00Z",
    ended_at: "2026-08-05T18:00:00Z",
    gouvernorats: [61],
    geometry: null,
    incident_ids: ["0b6c2a3e-6a52-4b8a-9d1e-1f2e3d4c5b6a"],
    summary: text("ملخص **الحدث**", "Résumé de l’**événement**\n\n<script>alert(1)</script>\n\n[lien](javascript:alert(1))"),
    strengths: text("", "- Mobilisation rapide"),
    weaknesses: text("", ""),
    lessons: text("", ""),
    recommendations: text("", ""),
    sources: [{ title: "Rapport ONPC", url: "https://example.tn/rapport", media_id: null }],
    access: "national",
    status: "draft",
    version: 3,
    published_version: null,
    author: { id: "ehimaya-staff:u-2", name: "Amel" },
    reviewers: [],
    created_at: "2026-08-10T10:00:00Z",
    updated_at: "2026-08-12T10:00:00Z",
    can_edit: true,
    can_review: false,
    ...overrides,
  };
}

export function makeSearch(overrides: Partial<LibrarySearch> = {}): LibrarySearch {
  return {
    items: [
      {
        kind: "memory",
        id: "mem-1",
        title: "Feux de forêt du Kef 2026",
        excerpt: "Les <mark>feux</mark> &lt;b&gt; du Kef",
        date: "2026-08-02",
        gouvernorat: 61,
        category: "fire",
        incident_id: null,
        score: 1.2,
      },
    ],
    facets: {
      kind: [
        { key: "memory", count: 1 },
        { key: "report", count: 4 },
      ],
      year: [{ key: "2026", count: 5 }],
      gouvernorat: [{ key: "61", count: 5 }],
      category: [{ key: "fire", count: 5 }],
    },
    backend: "postgres",
    next_cursor: null,
    ...overrides,
  };
}

export function makeLibraryItem(overrides: Partial<LibraryItem> = {}): LibraryItem {
  return {
    kind: "transcript",
    id: "tr-1",
    title: "Appel 198",
    date: "2026-08-02T10:05:00Z",
    gouvernorat: 61,
    category: "fire",
    incident_id: "0b6c2a3e-6a52-4b8a-9d1e-1f2e3d4c5b6a",
    body: "Bonjour, il y a un feu près de la route.",
    fields: { duration_s: 74 },
    media: [{ id: "m-9", kind: "audio", content_type: "audio/ogg", url: "https://s3.example/m-9?sig=x", duration_s: 74 }],
    ...overrides,
  };
}

export function makeRule(overrides: Partial<RewardRule> = {}): RewardRule {
  return {
    id: "rule-1",
    reason: "report_verified",
    category: null,
    points: 50,
    multiplier: null,
    enabled: true,
    is_default: true,
    ...overrides,
  };
}

export const REWARD_SETTINGS: RewardSettings = {
  daily_cap: 200,
  thresholds: { bronze: 100, silver: 500, gold: 2000, ambassador: 10000 },
  paused_gouvernorats: [],
};

export function makeBadge(overrides: Partial<BadgeAward> = {}): BadgeAward {
  return {
    id: "b-1",
    citizen_id: "c-1",
    pseudonym: "Faucon-482",
    level: "gold",
    status: "pending",
    balance: 2150,
    awarded_at: "2026-10-01T10:00:00Z",
    decided_at: null,
    decided_by: null,
    reason: null,
    ...overrides,
  };
}

export function makeNomination(overrides: Partial<Nomination> = {}): Nomination {
  return {
    id: "n-1",
    kind: "vigilant_citizen",
    subject_kind: "citizen",
    subject_id: "c-1",
    subject_label: "Faucon-482",
    gouvernorat_code: 61,
    year: 2026,
    reason: "Trois signalements vérifiés ayant permis une intervention rapide.",
    evidence: { report_ids: ["r-1"], intervention_ids: [] },
    status: "proposed",
    proposed_by: "u-9",
    decided_by: null,
    decided_at: null,
    decision_reason: null,
    created_at: "2026-10-02T10:00:00Z",
    ...overrides,
  };
}

export function makeRewardCertificate(overrides: Partial<RewardCertificate> = {}): RewardCertificate {
  return {
    id: "rc-1",
    code: "RW-2026-0001",
    kind: "nomination",
    distinction: "Citoyen vigilant",
    subject_label: "Faucon-482",
    initials: "F. B.",
    year: 2026,
    issued_at: "2026-10-03T10:00:00Z",
    issued_by: "u-9",
    revoked_at: null,
    revoked_reason: null,
    verify_url: "https://api.ehimaya.test/api/v1/rewards/certificates/RW-2026-0001",
    ...overrides,
  };
}

export function fakePhase8Api(): Phase8Api {
  return {
    analyticsOverview: vi.fn(() => Promise.resolve(makeOverview())),
    analyticsTrends: vi.fn(() => Promise.resolve(makeTrends())),
    analyticsHotspots: vi.fn(() => Promise.resolve(makeHotspots())),
    runScenario: vi.fn(() => Promise.resolve(makeScenario())),
    scenarios: vi.fn(() => Promise.resolve({ items: [makeScenario()], next_cursor: null })),
    scenario: vi.fn(() => Promise.resolve(makeScenario())),
    reportNotifications: vi.fn(() => Promise.resolve({ items: [], next_cursor: null, unread: 0 })),
    markReportNotificationRead: vi.fn(() => Promise.resolve({})),
    libraryReports: vi.fn(() => Promise.resolve({ items: [makeLibraryReport()], next_cursor: null })),
    libraryReport: vi.fn(() => Promise.resolve(makeLibraryReport())),
    createLibraryReport: vi.fn(() => Promise.resolve(makeLibraryReport({ status: "queued" }))),
    libraryReportLink: vi.fn(() => Promise.resolve({ url: "https://s3.example/rep-1.pdf?sig=x" })),
    schedules: vi.fn(() => Promise.resolve([makeSchedule()])),
    createSchedule: vi.fn(() => Promise.resolve(makeSchedule())),
    updateSchedule: vi.fn(() => Promise.resolve(makeSchedule())),
    deleteSchedule: vi.fn(() => Promise.resolve(undefined)),
    memoryEntries: vi.fn(() => Promise.resolve({ items: [makeMemoryEntry()], next_cursor: null })),
    memoryEntry: vi.fn(() => Promise.resolve(makeMemoryEntry())),
    createMemoryEntry: vi.fn(() => Promise.resolve(makeMemoryEntry())),
    updateMemoryEntry: vi.fn(() => Promise.resolve(makeMemoryEntry({ version: 4 }))),
    deleteMemoryEntry: vi.fn(() => Promise.resolve(undefined)),
    transitionMemoryEntry: vi.fn(() => Promise.resolve(makeMemoryEntry({ status: "in_review", version: 4 }))),
    memoryVersions: vi.fn(() => Promise.resolve([])),
    memoryVersion: vi.fn(),
    memoryFromIncident: vi.fn(() => Promise.resolve(makeMemoryEntry({ id: "mem-new" }))),
    librarySearch: vi.fn(() => Promise.resolve(makeSearch())),
    libraryGrid: vi.fn((level: CalendarLevel, on: string) => Promise.resolve(fakeGrid(level, on))),
    libraryFigures: vi.fn((from: string, to: string) => Promise.resolve(fakeFigures(from, to))),
    libraryTree: vi.fn(() => Promise.resolve({ by: "period" as const, nodes: [] })),
    libraryItem: vi.fn(() => Promise.resolve(makeLibraryItem())),
    rewardSettings: vi.fn(() => Promise.resolve(REWARD_SETTINGS)),
    rewardRules: vi.fn(() =>
      Promise.resolve([
        makeRule(),
        makeRule({ id: "rule-2", reason: "accurate_category", points: null, multiplier: 1.5 }),
      ]),
    ),
    createRewardRule: vi.fn(() => Promise.resolve(makeRule({ id: "rule-9", is_default: false, category: "fire" }))),
    updateRewardRule: vi.fn(() => Promise.resolve(makeRule())),
    deleteRewardRule: vi.fn(() => Promise.resolve(undefined)),
    badgeAwards: vi.fn(() => Promise.resolve({ items: [makeBadge()], next_cursor: null })),
    decideBadge: vi.fn(() => Promise.resolve(makeBadge({ status: "confirmed" }))),
    nominations: vi.fn(() => Promise.resolve({ items: [makeNomination()], next_cursor: null })),
    createNomination: vi.fn(() => Promise.resolve(makeNomination())),
    decideNomination: vi.fn(() => Promise.resolve(makeNomination({ status: "approved" }))),
    rewardCertificates: vi.fn(() => Promise.resolve({ items: [makeRewardCertificate()], next_cursor: null })),
    issueRewardCertificate: vi.fn(() => Promise.resolve(makeRewardCertificate())),
    revokeRewardCertificate: vi.fn(() => Promise.resolve(makeRewardCertificate())),
    rewardCertificatePdf: vi.fn(() => Promise.resolve({ kind: "link" as const, url: "https://s3.example/rc-1.pdf?sig=x" })),
    leaderboard: vi.fn(() =>
      Promise.resolve({
        scope: "national" as const,
        gouvernorat_code: null,
        year: 2026,
        items: [{ rank: 1, pseudonym: "Faucon-482", points: 2150, gouvernorat_code: 61 }],
      }),
    ),
  };
}
