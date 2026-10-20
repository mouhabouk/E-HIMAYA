/**
 * Analytics helpers (phase 8 §1/§4): filters shared in the URL, defaults, and the colour scale of the hex layer.
 * Pure functions, unit tested.
 */
import type { AnalyticsFilterQuery, TrendInterval, TrendMetric } from "./phase8Types";
import { TREND_INTERVALS, TREND_METRICS } from "./phase8Types";
import { CATEGORIES, type Category } from "./types";

export interface AnalyticsFilters extends AnalyticsFilterQuery {
  gouvernorat: number | null;
  category: Category | null;
  metric: TrendMetric;
  interval: TrendInterval;
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
/** The API refuses longer windows (`period_too_long`); 3 years covers the seasonal comparison. */
export const MAX_RANGE_DAYS = 3 * 366;
export const DEFAULT_RANGE_DAYS = 90;

/** Local calendar date "YYYY-MM-DD" (Africa/Tunis in practice: the dashboard runs there). */
export function isoDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split("-").map(Number) as [number, number, number];
  return isoDate(new Date(y, m - 1, d + days));
}

export function daysBetween(from: string, to: string): number {
  const ms = (s: string) => {
    const [y, m, d] = s.split("-").map(Number) as [number, number, number];
    return Date.UTC(y, m - 1, d);
  };
  return Math.round((ms(to) - ms(from)) / 86_400_000);
}

export function isIsoDate(v: string | null): v is string {
  if (!v || !DATE_RE.test(v)) return false;
  const [y, m, d] = v.split("-").map(Number) as [number, number, number];
  const date = new Date(y, m - 1, d);
  return date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d;
}

export function defaultAnalyticsFilters(today: Date = new Date()): AnalyticsFilters {
  const to = isoDate(today);
  return {
    from: addDays(to, -(DEFAULT_RANGE_DAYS - 1)),
    to,
    gouvernorat: null,
    category: null,
    metric: "reports",
    interval: "week",
  };
}

/**
 * Reads the filters from the URL; anything invalid falls back to the default, and a reversed or too long range is
 * repaired (the end date wins). `national` false drops the gouvernorat: the API applies the token's scope.
 */
export function parseAnalyticsFilters(
  params: URLSearchParams,
  national: boolean,
  today: Date = new Date(),
): AnalyticsFilters {
  const d = defaultAnalyticsFilters(today);
  const to = isIsoDate(params.get("to")) ? (params.get("to") as string) : d.to;
  let from = isIsoDate(params.get("from")) ? (params.get("from") as string) : addDays(to, -(DEFAULT_RANGE_DAYS - 1));
  if (daysBetween(from, to) < 0) from = to;
  if (daysBetween(from, to) > MAX_RANGE_DAYS) from = addDays(to, -MAX_RANGE_DAYS);
  const g = Number(params.get("gouvernorat"));
  const category = params.get("category");
  const metric = params.get("metric");
  const interval = params.get("interval");
  return {
    from,
    to,
    gouvernorat: national && Number.isInteger(g) && g > 0 ? g : null,
    category: (CATEGORIES as readonly string[]).includes(category ?? "") ? (category as Category) : null,
    metric: (TREND_METRICS as readonly string[]).includes(metric ?? "") ? (metric as TrendMetric) : d.metric,
    interval: (TREND_INTERVALS as readonly string[]).includes(interval ?? "") ? (interval as TrendInterval) : d.interval,
  };
}

/** Only what differs from the defaults goes into the URL, so a shared link stays short. */
export function analyticsSearch(f: AnalyticsFilters, today: Date = new Date()): URLSearchParams {
  const d = defaultAnalyticsFilters(today);
  const p = new URLSearchParams();
  if (f.from !== d.from || f.to !== d.to) {
    p.set("from", f.from);
    p.set("to", f.to);
  }
  if (f.gouvernorat !== null) p.set("gouvernorat", String(f.gouvernorat));
  if (f.category) p.set("category", f.category);
  if (f.metric !== d.metric) p.set("metric", f.metric);
  if (f.interval !== d.interval) p.set("interval", f.interval);
  return p;
}

/** Query string of the report form opened by "export", prefilled from the analytics filters. */
export function exportSearch(f: AnalyticsFilters): string {
  const p = new URLSearchParams({ new: "1", kind: f.gouvernorat !== null ? "gouvernorat_summary" : "period_summary" });
  p.set("from", f.from);
  p.set("to", f.to);
  if (f.gouvernorat !== null) p.set("gouvernorat", String(f.gouvernorat));
  if (f.category) p.set("category", f.category);
  return `?${p.toString()}`;
}

/**
 * Sequential colour scale of the hex layer (five classes, light → dark, readable on both map themes). Classes are
 * quantiles of the non-zero counts, so one extreme cell does not wash out the rest.
 */
export const HEX_COLOURS = ["#fde68a", "#fbbf24", "#f97316", "#dc2626", "#7f1d1d"] as const;

export function hexBreaks(counts: readonly number[]): number[] {
  const sorted = counts.filter((c) => c > 0).sort((a, b) => a - b);
  if (sorted.length === 0) return [];
  const breaks: number[] = [];
  for (let i = 1; i < HEX_COLOURS.length; i += 1) {
    const value = sorted[Math.min(sorted.length - 1, Math.floor((i / HEX_COLOURS.length) * sorted.length))] ?? 0;
    if (breaks.length === 0 || value > (breaks[breaks.length - 1] ?? 0)) breaks.push(value);
  }
  return breaks;
}

export function hexColour(cls: number): string {
  return HEX_COLOURS[Math.max(0, Math.min(HEX_COLOURS.length - 1, cls))] ?? "#dc2626";
}

/** Class index of a count given the breaks (count < breaks[0] → 0). */
export function hexClass(count: number, breaks: readonly number[]): number {
  let i = 0;
  while (i < breaks.length && count >= (breaks[i] ?? Infinity)) i += 1;
  return Math.min(i, HEX_COLOURS.length - 1);
}

/** Legend rows: [from, to | null] per class actually used. */
export function hexLegend(breaks: readonly number[], max: number): { colour: string; from: number; to: number | null }[] {
  const edges = [1, ...breaks];
  return edges
    .map((from, i) => ({
      colour: hexColour(i),
      from,
      to: i + 1 < edges.length ? (edges[i + 1] ?? from) - 1 : max >= from ? max : null,
    }))
    .filter((row) => row.to === null || row.to >= row.from);
}
