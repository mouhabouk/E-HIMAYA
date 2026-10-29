// Daily, weekly and monthly programmes of every gouvernorat (phase PL2, docs/phase-pl/design-plans.md §3).
import type { ApiClient } from "./api";

const S = "/api/v1/staff/schedule";
const enc = encodeURIComponent;

export const SPANS = ["day", "week", "month"] as const;
export type Span = (typeof SPANS)[number];
export const APPROVALS = ["direct", "head", "head_and_centre"] as const;
export type Approval = (typeof APPROVALS)[number];
export const REPEATS = ["none", "daily", "weekdays", "weekly"] as const;
export type Repeat = (typeof REPEATS)[number];
export const ITEM_STATUSES = ["planned", "in_progress", "done", "not_done", "postponed", "refused", "cancelled"] as const;
export type ItemStatus = (typeof ITEM_STATUSES)[number];
/** Set by hand with a reason (docs/phase-l/design-l4.md §6). */
export const WITH_REASON: readonly ItemStatus[] = ["not_done", "postponed", "refused", "cancelled"];
export const PERIOD_STATUSES = ["draft", "submitted", "awaiting_centre", "approved", "returned"] as const;
export type PeriodStatus = (typeof PERIOD_STATUSES)[number];

/** Every kind of activity a programme holds (Yamen, 2026-10-28: «كلها»), each with the tone of its chip. */
export const ACTIVITIES = {
  duty: "navy",
  patrol: "sky",
  exercise: "red",
  prevention_visit: "green",
  maintenance: "amber",
  training: "purple",
  awareness: "teal",
  readiness_check: "orange",
  meeting: "slate",
  other: "pink",
} as const;
export type Activity = keyof typeof ACTIVITIES;
export const ACTIVITY_KEYS = Object.keys(ACTIVITIES) as Activity[];

// Tones of the design system (components/Icon.tsx), named here so Playwright can load this file.
type Tone = "slate" | "amber" | "orange" | "green" | "red" | "sky" | "pink";

export const PERIOD_TONE: Record<PeriodStatus, Tone> = {
  draft: "slate",
  submitted: "amber",
  awaiting_centre: "orange",
  approved: "green",
  returned: "red",
};

export const ITEM_TONE: Record<ItemStatus, Tone> = {
  planned: "slate",
  in_progress: "sky",
  done: "green",
  not_done: "orange",
  postponed: "amber",
  refused: "pink",
  cancelled: "red",
};

export interface Counts {
  items: number;
  due: number;
  done: number;
  in_progress: number;
  not_done: number;
  postponed: number;
  refused: number;
  cancelled: number;
  rate: number | null;
}

export interface ScheduleItem {
  id: string;
  series_id: string | null;
  activity: Activity;
  title: string;
  on_date: string;
  starts_at: string | null;
  ends_at: string | null;
  unit_id: string | null;
  unit_name: string | null;
  place: string;
  responsible: string;
  staff_count: number | null;
  resources: { category_key: string; name: Record<string, string>; qty: number }[];
  plan_document_id: string | null;
  plan_title: string | null;
  notes: string;
  status: ItemStatus;
  /** The clock set the status from the hours of the activity. */
  status_auto: boolean;
  status_reason: string | null;
  status_by_name: string | null;
  status_at: string | null;
  /** Accepted from a suggestion (AI3): it keeps the AI label. */
  suggested?: boolean;
}

/** An activity the engine suggests for the days still ahead (AI3, design-l5.md §4.3); nothing is added until the
 * room accepts it. */
export interface ScheduleSuggestion {
  key: string;
  source: "weather" | "beaches" | "season" | "rise";
  activity: Activity;
  on_date: string;
  title: string;
  reasons: string[];
  simulated: boolean;
}

export interface ScheduleSuggestions {
  enabled: boolean;
  can_accept: boolean;
  items: ScheduleSuggestion[];
}

export const MAX_DISMISS_REASON = 300;

export interface Period {
  id: string;
  gouvernorat_code: number;
  gouvernorat_name: string | null;
  span: Span;
  starts_on: string;
  ends_on: string;
  status: PeriodStatus;
  approval: Approval;
  notes: string;
  return_reason: string | null;
  submitted_by_name: string | null;
  submitted_at: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  centre_approved_by_name: string | null;
  centre_approved_at: string | null;
  version: number;
  created_by_name: string | null;
  updated_by_name: string | null;
  updated_at: string;
  counts: Counts;
}

export interface PeriodDetail {
  period: Period;
  items: ScheduleItem[];
  can_edit: boolean;
  can_submit: boolean;
  can_approve: boolean;
  can_return: boolean;
  can_follow_up: boolean;
  can_delete: boolean;
  previous_id: string | null;
}

export interface PeriodSlot {
  gouvernorat_code: number;
  span: Span;
  starts_on: string;
  ends_on: string;
  period: PeriodDetail | null;
  can_create: boolean;
}

export interface ItemBody {
  activity: Activity;
  title: string;
  on_date: string;
  starts_at: string | null;
  ends_at: string | null;
  unit_id: string | null;
  place: string;
  responsible: string;
  staff_count: number | null;
  resources: { category_key: string; qty: number }[];
  plan_document_id: string | null;
  notes: string;
  repeat?: Repeat;
}

export interface ScheduleSetting {
  gouvernorat_code: number;
  gouvernorat_name: string | null;
  approval: Approval;
  updated_by_name: string | null;
  updated_at: string | null;
  can_edit: boolean;
}

export interface ProgressRow {
  gouvernorat_code: number;
  gouvernorat_name: string | null;
  approval: Approval;
  period_id: string | null;
  status: PeriodStatus | null;
  counts: Counts;
}

export interface Progress {
  span: Span;
  starts_on: string;
  ends_on: string;
  rows: ProgressRow[];
  lists: boolean;
}

export interface ScheduleOptions {
  units: { id: string; name: string }[];
  categories: { key: string; kind: string; name: Record<string, string> }[];
  plans: { id: string; title: string; hazard_key: string | null }[];
}

/** A programme kept under a name to start the next ones from (Yamen, 2026-10-28). */
export interface ScheduleTemplate {
  id: string;
  gouvernorat_code: number;
  span: Span;
  name: string;
  items: number;
  activities: Partial<Record<Activity, number>>;
  created_by_name: string | null;
  created_at: string;
  updated_by_name: string | null;
  updated_at: string;
}

export const scheduleKeys = {
  all: ["schedule"] as const,
  slot: (g: number | null, span: Span, on: string) => ["schedule", "slot", g, span, on] as const,
  progress: (span: Span, on: string) => ["schedule", "progress", span, on] as const,
  settings: ["schedule", "settings"] as const,
  options: (g: number | null) => ["schedule", "options", g] as const,
  templates: (g: number | null, span: Span | null) => ["schedule", "templates", g, span] as const,
  suggestions: (periodId: string, version: number, lang: string) => ["schedule", "suggestions", periodId, version, lang] as const,
};

// ---------------------------------------------------------------- calendar (dates as YYYY-MM-DD, no time zone)

export function parseDay(iso: string): Date {
  const [y = 1970, m = 1, d = 1] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

export function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function addDays(iso: string, n: number): string {
  const d = parseDay(iso);
  d.setUTCDate(d.getUTCDate() + n);
  return isoDay(d);
}

/** The same rules as the API: a week runs from Monday, a month from the 1st. */
export function bounds(span: Span, on: string): [string, string] {
  const d = parseDay(on);
  if (span === "day") return [on, on];
  if (span === "week") {
    const start = addDays(on, -((d.getUTCDay() + 6) % 7));
    return [start, addDays(start, 6)];
  }
  const start = isoDay(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1)));
  const end = isoDay(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)));
  return [start, end];
}

/** The day in the next (``step`` 1) or previous (-1) period. */
export function moveSpan(span: Span, on: string, step: 1 | -1): string {
  if (span === "day") return addDays(on, step);
  if (span === "week") return addDays(on, 7 * step);
  const d = parseDay(on);
  return isoDay(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + step, 1)));
}

export function daysOf(start: string, end: string): string[] {
  const out: string[] = [];
  for (let d = start; d <= end; d = addDays(d, 1)) out.push(d);
  return out;
}

/** The weeks (Monday to Sunday) that cover a month, for its grid. */
export function monthWeeks(start: string, end: string): string[][] {
  const [first] = bounds("week", start);
  const [, last] = bounds("week", end);
  const days = daysOf(first, last);
  const weeks: string[][] = [];
  for (let i = 0; i < days.length; i += 7) weeks.push(days.slice(i, i + 7));
  return weeks;
}

export function hhmm(t: string | null): string {
  return t ? t.slice(0, 5) : "";
}

export function scheduleApi(api: ApiClient) {
  return {
    scheduleSlot: (span: Span, on: string, gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<PeriodSlot>(`${S}/slot`, { signal, query: { span, on, gouvernorat } }),
    schedulePeriod: (id: string, signal?: AbortSignal) => api.request<PeriodDetail>(`${S}/periods/${enc(id)}`, { signal }),
    createPeriod: (span: Span, on: string, gouvernorat: number | null) =>
      api.request<PeriodDetail>(`${S}/periods`, { method: "POST", body: { span, on, gouvernorat_code: gouvernorat } }),
    periodNotes: (id: string, version: number, notes: string) =>
      api.request<PeriodDetail>(`${S}/periods/${enc(id)}`, { method: "PATCH", body: { version, notes } }),
    deletePeriod: (id: string) => api.request<undefined>(`${S}/periods/${enc(id)}`, { method: "DELETE" }),
    periodStep: (id: string, action: "submit" | "approve" | "return" | "copy-previous", version: number, reason?: string) =>
      api.request<PeriodDetail>(`${S}/periods/${enc(id)}/${action}`, {
        method: "POST",
        body: reason === undefined ? { version } : { version, reason },
      }),
    addScheduleItem: (periodId: string, body: ItemBody) =>
      api.request<PeriodDetail>(`${S}/periods/${enc(periodId)}/items`, { method: "POST", body }),
    updateScheduleItem: (id: string, body: ItemBody) => api.request<PeriodDetail>(`${S}/items/${enc(id)}`, { method: "PUT", body }),
    deleteScheduleItem: (id: string, series: boolean) =>
      api.request<PeriodDetail>(`${S}/items/${enc(id)}`, { method: "DELETE", query: { series } }),
    scheduleItemStatus: (id: string, status: ItemStatus, reason: string) =>
      api.request<PeriodDetail>(`${S}/items/${enc(id)}/status`, { method: "POST", body: { status, reason } }),
    scheduleProgress: (span: Span, on: string, signal?: AbortSignal) =>
      api.request<Progress>(`${S}/progress`, { signal, query: { span, on } }),
    scheduleSettings: (signal?: AbortSignal) => api.request<ScheduleSetting[]>(`${S}/settings`, { signal }),
    saveScheduleSetting: (code: number, approval: Approval) =>
      api.request<ScheduleSetting>(`${S}/settings/${code}`, { method: "PUT", body: { approval } }),
    scheduleTemplates: (gouvernorat: number | null, span: Span | null, signal?: AbortSignal) =>
      api.request<ScheduleTemplate[]>(`${S}/templates`, { signal, query: { gouvernorat, span } }),
    saveScheduleTemplate: (periodId: string, name: string) =>
      api.request<ScheduleTemplate>(`${S}/periods/${enc(periodId)}/template`, { method: "POST", body: { name } }),
    renameScheduleTemplate: (id: string, name: string) =>
      api.request<ScheduleTemplate>(`${S}/templates/${enc(id)}`, { method: "PATCH", body: { name } }),
    deleteScheduleTemplate: (id: string) => api.request<undefined>(`${S}/templates/${enc(id)}`, { method: "DELETE" }),
    applyScheduleTemplate: (periodId: string, version: number, templateId: string) =>
      api.request<PeriodDetail>(`${S}/periods/${enc(periodId)}/apply-template`, {
        method: "POST",
        body: { version, template_id: templateId },
      }),
    scheduleSuggestions: (periodId: string, lang: string, signal?: AbortSignal) =>
      api.request<ScheduleSuggestions>(`${S}/periods/${enc(periodId)}/suggestions`, { signal, query: { lang } }),
    acceptScheduleSuggestion: (periodId: string, key: string, version: number, lang: string) =>
      api.request<PeriodDetail>(`${S}/periods/${enc(periodId)}/suggestions/${enc(key)}/accept`, {
        method: "POST",
        body: { version, lang },
      }),
    dismissScheduleSuggestion: (periodId: string, key: string, reason: string) =>
      api.request<undefined>(`${S}/periods/${enc(periodId)}/suggestions/${enc(key)}/dismiss`, {
        method: "POST",
        body: { reason },
      }),
    scheduleOptions: (gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<ScheduleOptions>(`${S}/options`, { signal, query: { gouvernorat } }),
  };
}
