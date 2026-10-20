/**
 * Spread forecast and route drawing helpers (phase 7 §2–§3): forecast polygons as map areas with a colour per
 * horizon (always named in the legend beside the map), and the bounds to fit after a run.
 */
import type { Geometry, Position } from "geojson";
import type { MapPolygon } from "../components/MapView";
import type { BBox } from "./filters";
import type { ForecastKind, ForecastPolygon, ForecastRun } from "./decisionTypes";

/** Yellow → dark red with the horizon (fire); light → dark blue with the level (flood). */
const FIRE_COLOURS = ["#f59e0b", "#ea580c", "#c2410c", "#991b1b", "#7f1d1d"] as const;
const FLOOD_COLOURS: Readonly<Record<string, string>> = {
  low: "#60a5fa",
  moderate: "#2563eb",
  medium: "#2563eb",
  high: "#1e3a8a",
  very_high: "#172554",
};

export function polygonColour(kind: ForecastKind, p: ForecastPolygon, index: number): string {
  if (kind === "flood") return FLOOD_COLOURS[p.level ?? ""] ?? "#2563eb";
  return FIRE_COLOURS[Math.min(index, FIRE_COLOURS.length - 1)] ?? "#b91c1c";
}

function rings(geometry: Geometry): Position[][][] {
  if (geometry.type === "Polygon") return [geometry.coordinates];
  if (geometry.type === "MultiPolygon") return geometry.coordinates;
  if (geometry.type === "GeometryCollection") return geometry.geometries.flatMap(rings);
  return [];
}

/** Fire horizons sorted shortest first; flood polygons in the API's order. */
export function sortedPolygons(kind: ForecastKind, run: ForecastRun): ForecastPolygon[] {
  if (kind === "flood") return [...run.polygons];
  return [...run.polygons].sort((a, b) => (a.minutes ?? 0) - (b.minutes ?? 0));
}

/** Map areas, the largest horizon first so the shorter ones are drawn on top. */
export function forecastMapPolygons(kind: ForecastKind, run: ForecastRun): MapPolygon[] {
  const sorted = sortedPolygons(kind, run);
  return sorted
    .flatMap((p, i) =>
      rings(p.geojson).map((coordinates, j) => ({
        id: `forecast-${run.forecast_id}-${i}-${j}`,
        coordinates: coordinates.map((ring) => ring.map((pos) => [pos[0] ?? 0, pos[1] ?? 0] as [number, number])),
        tone: "high" as const,
        colour: polygonColour(kind, p, i),
        outline: "solid" as const,
      })),
    )
    .reverse();
}

export function boundsOfPositions(positions: readonly (readonly [number, number])[], pad = 0.002): BBox | null {
  if (positions.length === 0) return null;
  const lons = positions.map((p) => p[0]);
  const lats = positions.map((p) => p[1]);
  return [Math.min(...lons) - pad, Math.min(...lats) - pad, Math.max(...lons) + pad, Math.max(...lats) + pad];
}

export function forecastBounds(polygons: MapPolygon[]): BBox | null {
  return boundsOfPositions(polygons.flatMap((p) => p.coordinates.flat()));
}

/** Text of a bilingual value (or plain string) in the UI language, falling back to Arabic. */
export function bilingual(
  v: Partial<Record<"ar" | "fr", string>> | string | null | undefined,
  lang: "ar" | "fr",
): string {
  if (!v) return "";
  if (typeof v === "string") return v;
  return (lang === "fr" ? v.fr || v.ar : v.ar || v.fr) ?? "";
}

/** One input value as text (numbers rounded, objects as key=value pairs). */
export function inputText(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  if (typeof v === "string") return v;
  if (typeof v === "boolean") return v ? "✓" : "✗";
  if (Array.isArray(v)) return v.map(inputText).join(", ");
  if (typeof v === "object") {
    return Object.entries(v as Record<string, unknown>)
      .map(([k, x]) => `${k}: ${inputText(x)}`)
      .join(" · ");
  }
  return "—";
}
