import type { QueryValue } from "./api";
import type { Category, ReportStatus, StaffReport } from "./types";

export const PERIODS = ["24h", "7d", "30d"] as const;
export type Period = (typeof PERIODS)[number];

const PERIOD_MS: Record<Period, number> = {
  "24h": 24 * 3600 * 1000,
  "7d": 7 * 24 * 3600 * 1000,
  "30d": 30 * 24 * 3600 * 1000,
};

/** [minLon, minLat, maxLon, maxLat] as in the contract's `bbox` parameter. */
export type BBox = readonly [number, number, number, number];

export interface ReportFilters {
  statuses: ReportStatus[];
  categories: Category[];
  /** Only for national-scope users; ignored otherwise (the server applies the token's scope). */
  gouvernorat: number | null;
  period: Period;
  q: string;
}

export const DEFAULT_FILTERS: ReportFilters = { statuses: [], categories: [], gouvernorat: null, period: "7d", q: "" };

export function isPeriod(v: unknown): v is Period {
  return typeof v === "string" && (PERIODS as readonly string[]).includes(v);
}

export function periodSince(period: Period, now: number = Date.now()): string {
  return new Date(now - PERIOD_MS[period]).toISOString();
}

export function bboxParam(bbox: BBox): string {
  return bbox.map((n) => n.toFixed(5)).join(",");
}

export function filtersToQuery(
  filters: ReportFilters,
  options: { now?: number; bbox?: BBox | null; cursor?: string | null; limit?: number } = {},
): Record<string, QueryValue> {
  const q = filters.q.trim();
  return {
    status: [...filters.statuses].sort(),
    category: [...filters.categories].sort(),
    gouvernorat_code: filters.gouvernorat,
    since: periodSince(filters.period, options.now),
    q: q || undefined,
    bbox: options.bbox ? bboxParam(options.bbox) : undefined,
    cursor: options.cursor ?? undefined,
    limit: options.limit ?? 50,
  };
}

/** Stable, serialisable representation for react-query keys (excludes the moving `since` instant). */
export function filtersKey(filters: ReportFilters): readonly [string, string, number | null, Period, string] {
  return [
    [...filters.statuses].sort().join(","),
    [...filters.categories].sort().join(","),
    filters.gouvernorat,
    filters.period,
    filters.q.trim().toLowerCase(),
  ];
}

export function inBBox(lon: number, lat: number, bbox: BBox): boolean {
  return lon >= bbox[0] && lon <= bbox[2] && lat >= bbox[1] && lat <= bbox[3];
}

/** Client-side equivalent of the server filters, used to decide where a live event belongs. */
export function matchesFilters(
  report: StaffReport,
  filters: ReportFilters,
  options: { now?: number; bbox?: BBox | null } = {},
): boolean {
  if (filters.statuses.length > 0 && !filters.statuses.includes(report.status)) return false;
  if (filters.categories.length > 0 && !filters.categories.includes(report.category)) return false;
  if (filters.gouvernorat !== null && report.gouvernorat_code !== filters.gouvernorat) return false;
  if (Date.parse(report.received_at) < Date.parse(periodSince(filters.period, options.now))) return false;
  const q = filters.q.trim().toLowerCase();
  if (
    q &&
    !report.tracking_code.toLowerCase().includes(q) &&
    !(report.text ?? "").toLowerCase().includes(q) &&
    !(report.text_ar ?? "").toLowerCase().includes(q)
  ) {
    return false;
  }
  if (options.bbox && !inBBox(report.location.lon, report.location.lat, options.bbox)) return false;
  return true;
}
