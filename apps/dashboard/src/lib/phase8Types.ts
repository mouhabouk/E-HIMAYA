/**
 * Types mirroring docs/api/phase-8-contract.md §1–§3 (analytics and reports, national memory and events library,
 * rewards). Where the contract leaves a shape open, the API workers' schemas were followed (see the implementation
 * notes at the end of the contract); readers tolerate the documented variants (see phase8Api.ts).
 */
import type { FeatureCollection, Polygon } from "geojson";
import type { Category } from "./types";

/** Language of a generated document or schedule (phase 9 §8: ar, fr, en; Arabic is right to left). */
export type DocumentLanguage = "ar" | "fr" | "en";

/** `{ar, fr}` text (Markdown in the memory sections). */
export interface LocalizedText {
  ar: string;
  fr: string;
}

// ---------- §1 analytics ----------

export const REPORT_SOURCES = ["app", "sms", "call", "portal"] as const;
export type ReportSource = (typeof REPORT_SOURCES)[number];

export interface AnalyticsFilterQuery {
  from: string;
  to: string;
  gouvernorat?: number | null;
  category?: Category | null;
}

export interface Bucket<K = string> {
  key: K;
  count: number;
}

export interface DurationStat {
  mean_s: number | null;
  p90_s: number | null;
  /** Number of reports measured (mean and p90 are null when 0). */
  n?: number;
}

export const RESPONSE_STAGES = ["to_assignment", "to_on_scene", "to_closed"] as const;
export type ResponseStage = (typeof RESPONSE_STAGES)[number];

export interface AnalyticsOverview {
  from: string;
  to: string;
  /** Scope applied ([] = national). */
  gouvernorats?: number[];
  category?: Category | null;
  totals: { received: number; verified: number; in_progress: number; closed: number; rejected: number };
  response_time: Partial<Record<ResponseStage, DurationStat>>;
  by_category: Bucket[];
  by_gouvernorat: Bucket<number>[];
  by_status: Bucket[];
  by_source: Bucket[];
  /** 0–23, Africa/Tunis. */
  by_hour: Bucket<number>[];
  /** ISO weekday 1 (Monday) – 7 (Sunday). */
  by_weekday: Bucket<number>[];
  /** The k-anonymity floor in force (`ANALYTICS_MIN_CELL`). */
  min_cell?: number;
}

export const TREND_METRICS = ["reports", "response_time", "interventions"] as const;
export type TrendMetric = (typeof TREND_METRICS)[number];
export const TREND_INTERVALS = ["day", "week", "month"] as const;
export type TrendInterval = (typeof TREND_INTERVALS)[number];

export interface TrendPoint {
  /** Start of the period (ISO date or date-time). */
  period_start: string;
  value: number | null;
  last_year: number | null;
  /** Seasonal baseline from the same weeks of previous years; null when history is too short. */
  expected: number | null;
  low: number | null;
  high: number | null;
}

export interface Trends {
  metric: TrendMetric;
  interval: TrendInterval;
  from?: string;
  to?: string;
  points: TrendPoint[];
  baseline_available?: boolean;
  /** `response_time` values are mean seconds (received → first assignment). */
  unit?: "count" | "seconds";
}

export interface HexProperties {
  count: number;
  id?: string;
}

export type Hotspots = FeatureCollection<Polygon, HexProperties> & { cell_size_m?: number; from?: string; to?: string };

export const SCENARIO_WEATHERS = ["as_forecast", "fire_danger_extreme", "heavy_rain"] as const;
export type ScenarioWeather = (typeof SCENARIO_WEATHERS)[number];

export interface ScenarioBody {
  name: string;
  gouvernorats: number[];
  category: Category;
  demand_factor: number;
  /** Resource ids, or counts per resource kind. */
  unavailable_resources: string[] | Record<string, number>;
  horizon_hours: number;
  weather: ScenarioWeather;
  /** Optional fixed seed (the API draws and stores one otherwise). */
  seed?: number;
}

export interface Percentiles {
  p10: number;
  p50: number;
  p90: number;
}

export interface ScenarioHour {
  /** 0-based offset from the start of the horizon. */
  hour: number;
  at?: string;
  demand: Percentiles;
  wait_minutes: Percentiles;
  /** 0..1 */
  utilisation: Percentiles;
  capacity?: number | null;
  overloaded: boolean;
}

export interface ScenarioSummary {
  reports_per_hour: Percentiles;
  wait_minutes: Percentiles;
  utilisation: Percentiles;
  capacity: number;
  total_reports: Percentiles;
}

export interface ScenarioProvenance {
  history_from?: string | null;
  history_to?: string | null;
  events?: number;
  incidents?: number;
  days_covered?: number;
  gap_days?: number;
  service_time_source?: "history" | "default";
  service_time_samples?: number;
  weather_factor?: number | null;
  weather_factor_source?: "history" | "forecast" | "default" | "none";
}

export interface ScenarioResult {
  /** Absent in list items. */
  hours?: ScenarioHour[];
  overload_hours: number[];
  summary?: ScenarioSummary;
  assumptions: LocalizedText[];
  disclaimer: LocalizedText;
  calibration?: "uncalibrated" | "calibrated";
  calibration_note?: LocalizedText | null;
  confidence?: "low" | "normal";
  confidence_reasons?: LocalizedText[];
  provenance?: ScenarioProvenance;
}

export type RunStatus = "queued" | "running" | "done" | "failed";

export interface ScenarioRun {
  id: string;
  name: string;
  status?: RunStatus;
  seed: number;
  runs: number;
  params: ScenarioBody;
  result: ScenarioResult | null;
  created_at: string;
  created_by?: string | null;
  simulated?: boolean;
}

export const LIBRARY_REPORT_KINDS = [
  "incident_summary",
  "period_summary",
  "gouvernorat_summary",
  "scenario",
  "after_action",
] as const;
export type LibraryReportKind = (typeof LIBRARY_REPORT_KINDS)[number];
export const REPORT_FORMATS = ["pdf", "xlsx"] as const;
export type ReportFormat = (typeof REPORT_FORMATS)[number];
export const LIBRARY_REPORT_STATUSES = ["queued", "running", "ready", "failed"] as const;
export type LibraryReportStatus = (typeof LIBRARY_REPORT_STATUSES)[number];

export interface ReportFiltersUsed {
  category?: Category | null;
  incident_id?: string | null;
  scenario_id?: string | null;
  [key: string]: unknown;
}

export interface LibraryReport {
  id: string;
  kind: LibraryReportKind;
  title: string;
  period_from: string;
  period_to: string;
  gouvernorats: number[];
  filters: ReportFiltersUsed;
  format: ReportFormat;
  status: LibraryReportStatus;
  media_id: string | null;
  sha256: string | null;
  created_by: string | null;
  schedule_id: string | null;
  created_at: string;
  /** Language of the file (Arabic RTL or French). */
  lang?: DocumentLanguage;
  error?: string | null;
  bytes?: number | null;
  ready_at?: string | null;
}

export interface LibraryReportBody {
  kind: LibraryReportKind;
  title: string;
  period_from: string;
  period_to: string;
  gouvernorats: number[];
  filters: ReportFiltersUsed;
  format: ReportFormat;
  lang: DocumentLanguage;
}

export interface LibraryReportQuery {
  q?: string;
  kind?: LibraryReportKind | "";
  status?: LibraryReportStatus | "";
  from?: string;
  to?: string;
  gouvernorat?: number | null;
}

/** Only these two kinds can be scheduled. */
export const SCHEDULE_KINDS = ["period_summary", "gouvernorat_summary"] as const;
export type ScheduleKind = (typeof SCHEDULE_KINDS)[number];

export const SCHEDULE_FREQUENCIES = ["daily", "weekly", "monthly"] as const;
export type ScheduleFrequency = (typeof SCHEDULE_FREQUENCIES)[number];

/** `daily|weekly|monthly at a time, Africa/Tunis`. */
export interface ScheduleCron {
  frequency: ScheduleFrequency;
  /** "HH:MM" */
  time: string;
  /** ISO weekday 1–7, weekly only. */
  weekday?: number | null;
  /** Day of month 1–28, monthly only. */
  day?: number | null;
}

export interface ReportSchedule {
  id: string;
  title: string;
  kind: ScheduleKind;
  filters: ReportFiltersUsed;
  gouvernorats: number[];
  format: ReportFormat;
  lang: DocumentLanguage;
  cron: ScheduleCron;
  /** Staff subject ids. */
  recipients: string[];
  enabled: boolean;
  last_run_at?: string | null;
  next_run_at?: string | null;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
}

export type ScheduleBody = Pick<
  ReportSchedule,
  "title" | "kind" | "filters" | "gouvernorats" | "format" | "lang" | "cron" | "recipients" | "enabled"
>;

/** In-app notice that a (scheduled) report is ready. */
export interface ReportNotification {
  id: string;
  kind: "report_ready";
  report_id: string;
  schedule_id: string | null;
  title: string;
  created_at: string;
  read_at: string | null;
}

export interface ReportNotifications {
  items: ReportNotification[];
  next_cursor: string | null;
  unread: number;
}

// ---------- §2 national memory ----------

export const MEMORY_STATUSES = ["draft", "in_review", "published", "archived"] as const;
export type MemoryStatus = (typeof MEMORY_STATUSES)[number];
export const MEMORY_ACCESS = ["national", "gouvernorat", "committee"] as const;
export type MemoryAccess = (typeof MEMORY_ACCESS)[number];
/** The five Markdown sections of an entry, each in ar and fr. */
export const MEMORY_SECTIONS = ["summary", "strengths", "weaknesses", "lessons", "recommendations"] as const;
export type MemorySection = (typeof MEMORY_SECTIONS)[number];

/** A staff member as the API shows them (`id` is an opaque actor string, `name` may be null). */
export interface Person {
  id: string;
  name: string | null;
}

export interface MemoryReviewer extends Person {
  decision: "approved" | "changes_requested";
  note: string | null;
  at: string;
  version: number;
}

export interface MemorySource {
  title: string;
  url?: string | null;
  media_id?: string | null;
}

export interface MemoryEntry extends Record<MemorySection, LocalizedText> {
  id: string;
  title: LocalizedText;
  event_type: string;
  started_at: string | null;
  ended_at: string | null;
  gouvernorats: number[];
  geometry?: unknown;
  incident_ids: string[];
  sources: MemorySource[];
  access: MemoryAccess;
  status: MemoryStatus;
  version: number;
  /** The version readers see while a newer working copy is edited. */
  published_version: number | null;
  author: Person | null;
  updated_by?: Person | null;
  reviewers: MemoryReviewer[];
  created_at?: string;
  updated_at?: string;
  published_at?: string | null;
  can_edit?: boolean;
  can_review?: boolean;
}

export type MemoryListItem = Pick<
  MemoryEntry,
  | "id"
  | "title"
  | "event_type"
  | "started_at"
  | "ended_at"
  | "gouvernorats"
  | "access"
  | "status"
  | "version"
  | "published_version"
  | "author"
  | "updated_at"
>;

export interface MemoryListQuery {
  q?: string;
  status?: MemoryStatus | "";
  access?: MemoryAccess | "";
  event_type?: string;
  gouvernorat?: number | null;
}

export type MemoryBody = Pick<
  MemoryEntry,
  | MemorySection
  | "title"
  | "event_type"
  | "started_at"
  | "ended_at"
  | "gouvernorats"
  | "incident_ids"
  | "sources"
  | "access"
  | "geometry"
>;

export const VERSION_CHANGES = [
  "created",
  "edited",
  "in_review",
  "published",
  "changes_requested",
  "archived",
  "restored",
] as const;
export type VersionChange = (typeof VERSION_CHANGES)[number];

export interface MemoryVersionSummary {
  version: number;
  status: MemoryStatus;
  created_at: string;
  created_by: Person | null;
  change: VersionChange;
  note: string | null;
}

export interface MemoryVersion extends MemoryVersionSummary {
  entry: MemoryBody;
}

/** `POST /memory/{id}/transition` body. */
export interface MemoryTransition {
  to: Exclude<MemoryStatus, never>;
  note: string | null;
  version: number;
}

// ---------- §2 events library ----------

export const LIBRARY_KINDS = ["memory", "report_doc", "incident", "report", "transcript", "procedure"] as const;
export type LibraryKind = (typeof LIBRARY_KINDS)[number];

export interface LibraryHit {
  kind: LibraryKind;
  id: string;
  title: string;
  /** Highlighted with `<mark>` only (rendered by splitting on the marks, never as HTML). */
  excerpt: string;
  date: string | null;
  gouvernorat: number | null;
  gouvernorats?: number[];
  category: string | null;
  incident_id: string | null;
  score: number;
}

export interface LibraryFacets {
  kind: Bucket[];
  year: Bucket[];
  gouvernorat: Bucket[];
  category: Bucket[];
}

export interface LibrarySearch {
  items: LibraryHit[];
  facets: LibraryFacets;
  backend: "opensearch" | "postgres";
  semantic?: boolean;
  next_cursor: string | null;
}

export interface LibraryQuery {
  q: string;
  kinds: LibraryKind[];
  from?: string;
  to?: string;
  gouvernorat?: number | null;
  category?: string | null;
}

export interface CalendarDay {
  date: string;
  count: number;
}

export interface LibraryCalendar {
  year: number;
  month: number;
  days: CalendarDay[];
}

export const TREE_AXES = ["period", "type", "gouvernorat"] as const;
export type TreeAxis = (typeof TREE_AXES)[number];

export interface TreeNode {
  key: string;
  label: LocalizedText | null;
  count: number;
  children?: TreeNode[];
}

export interface LibraryTree {
  by: TreeAxis;
  nodes: TreeNode[];
}

export interface LibraryMedia {
  id: string;
  kind: "image" | "video" | "audio" | "recording" | "document";
  content_type?: string | null;
  duration_s?: number | null;
  /** Pre-signed link (audited by the API when the item is opened). */
  url?: string | null;
}

export interface LibraryItem {
  kind: LibraryKind;
  id: string;
  title: string;
  date: string | null;
  gouvernorat: number | null;
  gouvernorats?: number[];
  category: string | null;
  incident_id: string | null;
  /** Plain text, or Markdown for memory entries, report documents and procedures. */
  body: string;
  /** Kind-specific fields (shown as a plain list). */
  fields?: Record<string, unknown>;
  media: LibraryMedia[];
}

// ---------- §3 rewards ----------

/** Ledger reasons; the first four are rule-driven. */
export const REWARD_REASONS = [
  "report_verified",
  "report_helped_rescue",
  "accurate_category",
  "volunteer_mission",
  "manual",
  "revocation",
] as const;
export type RewardReason = (typeof REWARD_REASONS)[number];
export const RULE_REASONS = ["report_verified", "report_helped_rescue", "accurate_category", "volunteer_mission"] as const;
export type RuleReason = (typeof RULE_REASONS)[number];
/** `accurate_category` is a multiplier (1.0–3.0); the others are points (0–5000). */
export const MULTIPLIER_RANGE = [1, 3] as const;
export const POINTS_RANGE = [0, 5000] as const;

export interface RewardRule {
  id: string;
  reason: RuleReason;
  /** A per-category override, or null for the default rule. */
  category: Category | null;
  points: number | null;
  multiplier: number | null;
  enabled: boolean;
  is_default: boolean;
  updated_at?: string | null;
  updated_by?: string | null;
}

export type RewardRuleBody = Pick<RewardRule, "reason" | "category" | "enabled"> &
  Partial<Pick<RewardRule, "points" | "multiplier">>;
export type RewardRulePatch = Partial<Pick<RewardRule, "points" | "multiplier" | "enabled">>;

export const BADGES = ["bronze", "silver", "gold", "ambassador"] as const;
export type Badge = (typeof BADGES)[number];
export const BADGE_STATUSES = ["pending", "confirmed", "rejected", "revoked"] as const;
export type BadgeStatus = (typeof BADGE_STATUSES)[number];

export interface BadgeAward {
  id: string;
  citizen_id: string | null;
  pseudonym: string;
  level: Badge;
  status: BadgeStatus;
  balance: number | null;
  awarded_at: string;
  decided_at: string | null;
  decided_by: string | null;
  reason: string | null;
}

export const NOMINATION_KINDS = ["vigilant_citizen", "brave_volunteer", "leading_institution"] as const;
export type NominationKind = (typeof NOMINATION_KINDS)[number];
export const SUBJECT_KINDS = ["citizen", "volunteer", "org"] as const;
export type SubjectKind = (typeof SUBJECT_KINDS)[number];
/** The subject kind each nomination kind requires (`422 invalid_subject` otherwise). */
export const NOMINATION_SUBJECT: Record<NominationKind, SubjectKind> = {
  vigilant_citizen: "citizen",
  brave_volunteer: "volunteer",
  leading_institution: "org",
};
export const NOMINATION_STATUSES = ["proposed", "approved", "rejected"] as const;
export type NominationStatus = (typeof NOMINATION_STATUSES)[number];

export interface Nomination {
  id: string;
  kind: NominationKind;
  subject_kind: SubjectKind;
  /** Null once the subject's account was deleted (anonymised). */
  subject_id: string | null;
  /** Pseudonym for people, name for institutions. */
  subject_label: string | null;
  gouvernorat_code: number | null;
  year: number;
  reason: string;
  evidence: { report_ids: string[]; intervention_ids: string[] };
  status: NominationStatus;
  proposed_by: string | null;
  decided_by: string | null;
  decided_at: string | null;
  decision_reason: string | null;
  created_at: string;
}

export type NominationBody = Pick<Nomination, "kind" | "subject_kind" | "year" | "reason" | "evidence"> & {
  subject_id: string;
};

export interface RewardCertificate {
  id: string;
  code: string;
  kind: "badge" | "nomination";
  distinction: string;
  subject_label: string;
  initials: string;
  year: number;
  issued_at: string;
  issued_by: string | null;
  revoked_at: string | null;
  revoked_reason: string | null;
  verify_url: string;
}

export interface LeaderboardRow {
  rank: number;
  pseudonym: string;
  points: number;
  gouvernorat_code: number | null;
}

export interface Leaderboard {
  scope: "gouvernorat" | "national";
  gouvernorat_code: number | null;
  year: number;
  items: LeaderboardRow[];
}

/** Read-only settings: no prize or cash configuration exists (contract §3 Safety). */
export interface RewardSettings {
  /** `REWARDS_DAILY_CAP`: points per citizen and day, rescue awards excluded. */
  daily_cap: number;
  thresholds: Record<Badge, number>;
  /** Gouvernorats at operational level `disaster` (points queued). */
  paused_gouvernorats: number[];
}
