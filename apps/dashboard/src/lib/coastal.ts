/**
 * Coastal safety (phase L1b, docs/phase-l/design-l1b-coastal.md): types of `/api/v1/staff/coastal`, the colours of
 * the three risk levels, and the editable rules of the drowning risk (mirroring
 * `services/api/app/modules/coastal/risk.py`). The score supports a decision: it never alerts the public by itself.
 */

export type RiskLevel = "green" | "yellow" | "red";
export const RISK_LEVELS: readonly RiskLevel[] = ["red", "yellow", "green"];
/** The design tokens red, amber, green and slate (design-system.md §2.1), on the map and in the legend. */
export const RISK_COLOURS: Record<RiskLevel | "unknown", string> = {
  red: "#D7141A",
  yellow: "#F5B400",
  green: "#188038",
  unknown: "#5B6478",
};

export const FACTOR_CODES = ["waves", "onshore_wind", "current", "season", "crowd", "unguarded", "past_drownings"] as const;

export interface Factor {
  code: string;
  points: number;
  value: unknown;
}

export interface DayRisk {
  day: string;
  level: RiskLevel;
  score: number;
  factors: Factor[];
  wave_height_m: number | null;
  sea_temp_c: number | null;
  current_kmh: number | null;
  onshore_wind_kmh: number | null;
  max_temperature_c: number | null;
  /** The drowning risk model kept in shadow (L5, design-l5.md §4.2): staff only, [SIM], never published. */
  shadow?: { level: RiskLevel; probability: number; version: number } | null;
}

export interface Beach {
  id: string;
  name: string;
  lat: number;
  lon: number;
  gouvernorat_code: number | null;
  level: RiskLevel | null;
  score: number | null;
  factors: Factor[];
  wave_height_m: number | null;
  sea_temp_c: number | null;
  current_kmh: number | null;
  classification: string | null;
  guarded: boolean | null;
  crowd: string | null;
  /** Phones counted at the beach in the last 30 minutes (anonymous, with consent). */
  present: number | null;
}

export type Attribution = { text: string; url: string; licence: string } | string;

export interface BeachDetail {
  beach: Beach;
  days: DayRisk[];
  card: Record<string, unknown>;
  sources: Record<string, { source?: string; date?: string }>;
  length_m: number | null;
  seaward_deg: number | null;
  simulated: boolean;
  attribution: Attribution[];
}

export interface CoastalKpis {
  beaches: number;
  red: number;
  yellow: number;
  green: number;
  unknown: number;
  average_score: number | null;
  guarded: number;
  drownings_season: number;
  present: number;
}

export interface GouvernoratRisk {
  code: number | null;
  beaches: number;
  red: number;
  yellow: number;
  green: number;
  average_score: number | null;
  crowd_high: number;
  crowd_medium: number;
  crowd_low: number;
}

export interface CoastalOverview {
  day: string;
  computed_at: string | null;
  simulated: boolean;
  attribution: Attribution[];
  kpis: CoastalKpis;
  top_dangerous: Beach[];
  top_touristic: Beach[];
  by_gouvernorat: GouvernoratRisk[];
  beaches: Beach[];
  /** [lat, lon, weight 0..1]. */
  heat_risk: [number, number, number][];
  heat_drownings: [number, number, number][];
}

export interface CoastalAlert {
  id: string;
  feature_id: string;
  name: string;
  day: string;
  level: "yellow" | "red";
  previous_level: RiskLevel | null;
  score: number;
  gouvernorat_code: number | null;
  simulated: boolean;
  created_at: string;
  acked_by_name: string | null;
  acked_at: string | null;
}

export interface CoastalSettings {
  rules: Record<string, unknown>;
  defaults: Record<string, unknown>;
  updated_by: string | null;
  updated_at: string | null;
}

export interface OverviewFilters {
  day?: string;
  gouvernorat?: number;
  classification?: string;
  guarded?: boolean;
  level?: RiskLevel;
}

/** The numeric rules the Office edits in the form (the wave bands and the months have their own fields). */
export const NUMERIC_RULES = [
  "yellow",
  "red",
  "onshore_kmh",
  "onshore_points",
  "strong_onshore_kmh",
  "strong_onshore_points",
  "current_kmh",
  "current_points",
  "hot_c",
  "season_points",
  "crowd_high_points",
  "unguarded_points",
  "incident_radius_m",
  "incident_years",
  "incident_points",
  "incident_max",
] as const;

export type WaveBand = [number | null, number];

/** The wave bands as stored: [upper bound in metres, points], the last one open. */
export function waveBands(rules: Record<string, unknown>): WaveBand[] {
  const raw = rules.waves;
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((b): WaveBand[] =>
    Array.isArray(b) && b.length === 2 && typeof b[1] === "number" && (b[0] === null || typeof b[0] === "number")
      ? [[b[0] as number | null, b[1]]]
      : [],
  );
}

/** Mirrors the API check (422 rule_invalid): red above yellow, increasing wave bands, the last one open. */
export function rulesProblem(rules: Record<string, unknown>): string | null {
  for (const key of NUMERIC_RULES) {
    const v = rules[key];
    if (typeof v !== "number" || !Number.isFinite(v) || v < 0) return key;
  }
  const yellow = rules.yellow as number;
  const red = rules.red as number;
  if (yellow <= 0) return "yellow";
  if (red <= yellow || red > 100) return "red";
  const bands = waveBands(rules);
  if (bands.length === 0 || bands.at(-1)?.[0] !== null) return "waves";
  let previous = 0;
  for (const [upper, points] of bands.slice(0, -1)) {
    if (upper === null || upper <= previous || points < 0) return "waves";
    previous = upper;
  }
  const months = rules.season_months;
  if (!Array.isArray(months) || months.some((m) => typeof m !== "number" || m < 1 || m > 12)) return "season_months";
  return null;
}

/** A beach's level as a key of RISK_COLOURS (no computed risk yet: unknown). */
export const levelKey = (level: RiskLevel | null | undefined): RiskLevel | "unknown" => level ?? "unknown";
