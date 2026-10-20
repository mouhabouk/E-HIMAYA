/**
 * Types mirroring docs/api/phase-7-contract.md §1 (weather layer and suggested alerts). The contract names the
 * fields loosely ("all fields"), so the map layer reads them through normalizeWeatherValues (lib/weather.ts).
 */
import type { Localized, Severity } from "./opsTypes";

export const FIRE_DANGER_CLASSES = ["low", "moderate", "high", "very_high", "extreme"] as const;
export type FireDangerClass = (typeof FIRE_DANGER_CLASSES)[number];

export const RAIN_LEVELS = ["none", "watch", "warning"] as const;
export type RainLevel = (typeof RAIN_LEVELS)[number];

/** Data source attribution (Open-Meteo: CC-BY 4.0). */
export interface WeatherAttribution {
  text: string;
  url?: string | null;
  licence?: string | null;
  license?: string | null;
}

/** Values of one point at one hour, as the dashboard uses them (all optional: a feed may lack some). */
export interface WeatherValues {
  time: string | null;
  temperature_c: number | null;
  humidity_pct: number | null;
  wind_speed_kmh: number | null;
  wind_gust_kmh: number | null;
  wind_direction_deg: number | null;
  precipitation_mm_h: number | null;
  rain_24h_mm: number | null;
  fwi: number | null;
  fire_danger: FireDangerClass | null;
  rain_level: RainLevel | null;
}

export interface WeatherPointFeature {
  type: "Feature";
  id?: string | number;
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: Record<string, unknown>;
}

/** `GET /api/v1/staff/weather/grid?bbox=&hour=`. */
export interface WeatherGrid {
  type: "FeatureCollection";
  features: WeatherPointFeature[];
  /** Hour shown (ISO), when the API says it. */
  hour?: string | null;
  generated_at?: string | null;
  simulated?: boolean;
  attribution?: WeatherAttribution | string | null;
}

/** `GET /api/v1/staff/weather/at?lat=&lon=`: the nearest grid point with its 48 h forecast. */
export interface WeatherPointDetail {
  lat: number;
  lon: number;
  current?: Record<string, unknown> | null;
  hourly?: Record<string, unknown>[];
  alerts?: { id: string; title?: Partial<Localized> | null; severity?: Severity | null }[];
  attribution?: WeatherAttribution | string | null;
  simulated?: boolean;
  updated_at?: string | null;
}

export const SUGGESTION_STATUSES = ["pending", "accepted", "dismissed", "expired"] as const;
export type SuggestionStatus = (typeof SUGGESTION_STATUSES)[number];

/** One measured value that crossed a threshold rule. */
export interface SuggestionEvidence {
  metric: string;
  value: number;
  threshold?: number | null;
  unit?: string | null;
  at?: string | null;
  lat?: number | null;
  lon?: number | null;
  gouvernorat_code?: number | null;
}

/** `weather.alert_suggestion` row (`GET /api/v1/staff/weather/suggestions`). */
export interface WeatherSuggestion {
  id: string;
  status?: SuggestionStatus;
  gouvernorat_codes: number[];
  category: "weather";
  severity: Severity;
  hazard?: string | null;
  title: Partial<Localized>;
  body: Partial<Localized>;
  /** A list of values, or an object of named values (both are shown). */
  evidence: SuggestionEvidence[] | Record<string, unknown>;
  rule?: string | null;
  valid_until: string;
  created_at?: string | null;
  simulated?: boolean;
}
