/**
 * Types mirroring docs/api/phase-7-contract.md §2 (spread forecast) and §3 (decision support). Every
 * recommendation is advisory: it comes with its rationale and inputs and a human decides.
 */
import type { Geometry } from "geojson";

export interface Bilingual {
  ar: string;
  fr: string;
}

export const FUEL_MODELS = ["grass", "shrub", "timber_litter", "mixed"] as const;
export type FuelModel = (typeof FUEL_MODELS)[number];

export const DEFAULT_HORIZONS = [30, 60, 120] as const;

export interface FireForecastBody {
  ignition: { lat: number; lon: number } | null;
  fuel_model?: FuelModel;
  horizons_min: number[];
}

export interface ForecastPolygon {
  minutes?: number | null;
  /** Flood risk polygons carry a level instead of a horizon. */
  level?: string | null;
  geojson: Geometry;
  area_ha?: number | null;
}

/** Answer of `POST …/forecast/fire` and `POST …/forecast/flood`. */
export interface ForecastRun {
  forecast_id: string;
  model: string;
  inputs: Record<string, unknown>;
  polygons: ForecastPolygon[];
  rate_of_spread_m_min?: number | null;
  /** Flood: overall risk level. */
  level?: string | null;
  assumptions: (string | Partial<Bilingual>)[];
  disclaimer?: Partial<Bilingual> | string | null;
  generated_at: string;
  simulated?: boolean;
}

export type ForecastKind = "fire" | "flood";

export const RECOMMENDATION_KINDS = ["resources", "volunteers", "route", "escalation", "alert", "responders"] as const;
export type RecommendationKind = (typeof RECOMMENDATION_KINDS)[number];

export const CONFIDENCES = ["low", "medium", "high"] as const;
export type Confidence = (typeof CONFIDENCES)[number];

export interface LatLonPoint {
  lat: number;
  lon: number;
}

/** A button of a recommendation, wired to an existing flow; nothing is applied without the operator. */
export type RecommendationAction =
  | { type: "open_assignment"; resource_id?: string | null; label?: Partial<Bilingual> | null; order?: string | null }
  | {
      type: "open_alert_form";
      label?: Partial<Bilingual> | null;
      prefill?: Record<string, unknown> | null;
    }
  | {
      type: "call";
      label?: Partial<Bilingual> | null;
      number?: string | null;
      volunteer_id?: string | null;
      report_id?: string | null;
    }
  | {
      type: "show_route";
      label?: Partial<Bilingual> | null;
      from: LatLonPoint;
      to: LatLonPoint;
      profile?: RouteProfile | null;
    };

export interface Recommendation {
  kind: RecommendationKind;
  title: Partial<Bilingual>;
  rationale: Partial<Bilingual>;
  inputs: Record<string, unknown>;
  confidence: Confidence;
  actions: RecommendationAction[];
}

export interface Recommendations {
  generated_at: string;
  items: Recommendation[];
  simulated?: boolean;
}

export type RouteProfile = "car" | "truck";

/** `GET /api/v1/staff/route`. */
export interface RouteResult {
  distance_m: number;
  duration_s: number;
  geometry: { type: "LineString"; coordinates: [number, number][] };
  engine: "osrm" | "valhalla" | "fallback";
  simulated: boolean;
  attribution?: string | null;
}

/** `GET /api/v1/staff/incidents/{id}/responders` (FR-C-13): officials to involve, with the reason. */
export interface Responder {
  id?: string | null;
  name: string;
  role?: string | null;
  organization?: string | null;
  phone?: string | null;
  email?: string | null;
  reason: Partial<Bilingual> | string;
}

export interface RespondersResult {
  items: Responder[];
}

export const SOURCE_KINDS = ["procedure", "incident", "report", "memory"] as const;
export type SourceKind = (typeof SOURCE_KINDS)[number];

export interface AssistantSource {
  kind: SourceKind;
  id: string;
  title: string;
  excerpt: string;
  /** A readable copy of a procedure, when the API serves one. */
  url?: string | null;
}

/** `POST /api/v1/staff/incidents/{id}/assistant`. */
export interface AssistantAnswer {
  answer: string;
  sources: AssistantSource[];
  model: string;
}
