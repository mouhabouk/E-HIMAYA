import type { FeatureCollection } from "geojson";
import type { ApiClient } from "./api";

/**
 * Administrative boundaries of phase M (docs/phase-m/design-m.md §4): the Map Tunisia levels served by the API, and
 * the reports per délégation coloured by their rate per 10,000 inhabitants (census 2024).
 */

export const ADMIN_LEVELS = ["gouvernorats", "delegations", "sectors", "municipalities"] as const;
export type AdminLevel = (typeof ADMIN_LEVELS)[number];

/** Properties of one unit as the API returns them (some only on some levels). */
export interface AdminProps {
  id: number | string;
  name_ar: string;
  name_fr: string;
  name_en: string;
  ins_code?: string | number | null;
  gouvernorat_code?: number;
  delegation_id?: number;
  population_2024?: number | null;
  area_km2?: number | null;
}

export interface DelegationCount {
  delegation_id: number;
  count: number;
}

/** Sequential reds of the rate classes, light to dark (the same in both themes: drawn on the map). */
export const RATE_COLOURS = ["#FDE8E8", "#F8B4B4", "#F05252", "#C81E1E", "#771D1D"] as const;
export const NO_REPORT_COLOUR = "#E3E7EF";
export const ADMIN_LINE = "#1F3FA0";

export const adminKeys = {
  boundaries: (level: AdminLevel, gouvernorat: number | null) => ["admin-boundaries", level, gouvernorat] as const,
  counts: (days: number) => ["admin-counts", days] as const,
};

export function adminApi(api: ApiClient) {
  return {
    boundaries: (level: AdminLevel, gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<FeatureCollection>(`/api/v1/geo/boundaries/${level}`, {
        query: { gouvernorat, detail: "medium" },
        signal,
        anonymous: true,
      }),
    delegationCounts: (since: string, signal?: AbortSignal) =>
      api.request<DelegationCount[]>("/api/v1/staff/kpis/delegations", { query: { since }, signal }),
  };
}

/** Reports per 10,000 inhabitants, or null without a census figure. */
export function ratePer10k(count: number, population: number | null | undefined): number | null {
  return population && population > 0 ? (count * 10_000) / population : null;
}

/**
 * Upper bounds of the five classes: quantiles of the non-zero rates, so that each colour holds about as many
 * délégations. Fewer distinct rates give fewer classes.
 */
export function rateBreaks(rates: readonly number[]): number[] {
  const sorted = rates.filter((r) => r > 0).sort((a, b) => a - b);
  if (sorted.length === 0) return [];
  const breaks: number[] = [];
  for (let i = 1; i <= RATE_COLOURS.length; i++) {
    const value = sorted[Math.min(sorted.length - 1, Math.ceil((i * sorted.length) / RATE_COLOURS.length) - 1)] ?? 0;
    if (value > (breaks.at(-1) ?? 0)) breaks.push(value);
  }
  return breaks;
}

/** The colour of a rate given the class bounds. */
export function rateColour(rate: number | null, breaks: readonly number[]): string {
  if (rate === null || rate <= 0 || breaks.length === 0) return NO_REPORT_COLOUR;
  const index = breaks.findIndex((b) => rate <= b);
  const cls = index === -1 ? breaks.length - 1 : index;
  // Fewer classes than colours: spread them over the ramp, darkest last.
  const step = breaks.length > 1 ? (RATE_COLOURS.length - 1) / (breaks.length - 1) : 0;
  return RATE_COLOURS[Math.round(cls * step)] ?? NO_REPORT_COLOUR;
}
