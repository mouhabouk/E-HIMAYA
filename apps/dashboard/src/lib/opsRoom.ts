// Operations room wall view (map/room): a dark, three-dimensional reading of the live situation. Pure helpers here,
// so the figures and the map restyling are tested without a browser.
import type { FeatureCollection, Point } from "geojson";
import type { ResourceKind, ResourceSummary } from "./opsTypes";
import type { Category, Kpis, ReportStatus, StaffReport } from "./types";

/** Category colours on the dark wall (design system dark palette, docs/design-system.md). */
export const OPS_CATEGORY_COLOURS: Readonly<Record<Category, string>> = {
  sos: "#F06292",
  fire: "#FF6B6B",
  flood: "#64B5F6",
  traffic_accident: "#FFA733",
  drowning: "#64B5F6",
  landslide: "#FFC933",
  chemical_leak: "#C49BE6",
  medical: "#4DD0B8",
  other: "#A6AFC4",
};

/** Statuses of a report still being handled. */
export const OPEN_STATUSES: readonly ReportStatus[] = ["received", "in_progress", "intervened", "ongoing"];

export function isOpen(status: ReportStatus): boolean {
  return OPEN_STATUSES.includes(status);
}

/** Start of the local day, as the `since` of the day's figures. */
export function startOfDay(now: Date): string {
  const d = new Date(now);
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

/**
 * Reports per hour over the last 24 hours: index 23 is the current hour, index 0 the hour 23 hours earlier. Reports
 * older than that, or dated in the future, are left out.
 */
export function hourlyCounts(reports: readonly Pick<StaffReport, "created_at">[], now: Date): number[] {
  const counts = new Array<number>(24).fill(0);
  const top = new Date(now);
  top.setMinutes(0, 0, 0);
  const end = top.getTime() + 3_600_000;
  for (const r of reports) {
    const t = Date.parse(r.created_at);
    if (Number.isNaN(t) || t >= end) continue;
    const back = Math.floor((end - 1 - t) / 3_600_000);
    if (back < 24) counts[23 - back] = (counts[23 - back] ?? 0) + 1;
  }
  return counts;
}

/** Number of open reports in the day's figures. */
export function openCount(kpis: Pick<Kpis, "by_status">): number {
  return OPEN_STATUSES.reduce((n, s) => n + (kpis.by_status[s] ?? 0), 0);
}

/** Non-empty categories of the day, most frequent first. */
export function categoryCounts(kpis: Pick<Kpis, "by_category">): { category: Category; count: number }[] {
  return (Object.entries(kpis.by_category) as [Category, number | undefined][])
    .filter((e): e is [Category, number] => (e[1] ?? 0) > 0)
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count || a.category.localeCompare(b.category));
}

export interface Readiness {
  kind: ResourceKind;
  available: number;
  /** In service: available + assigned (out of service left out of the ratio). */
  inService: number;
  total: number;
}

/** Ready share of each kind of means, the largest fleets first. */
export function readiness(summary: ResourceSummary, max = 3): Readiness[] {
  return (Object.entries(summary.by_kind) as [ResourceKind, ResourceSummary["by_kind"][ResourceKind]][])
    .map(([kind, s]) => {
      const available = s?.available ?? 0;
      const assigned = s?.assigned ?? 0;
      const out = s?.out_of_service ?? 0;
      return { kind, available, inService: available + assigned, total: available + assigned + out };
    })
    .filter((r) => r.total > 0)
    .sort((a, b) => b.total - a.total || a.kind.localeCompare(b.kind))
    .slice(0, max);
}

/** The reports as map points, open ones flagged so they glow. */
export function reportPoints(
  reports: readonly Pick<StaffReport, "id" | "category" | "status" | "location">[],
): FeatureCollection<Point, { id: string; colour: string; open: number }> {
  return {
    type: "FeatureCollection",
    features: reports.map((r) => ({
      type: "Feature",
      id: r.id,
      properties: { id: r.id, colour: OPS_CATEGORY_COLOURS[r.category], open: isOpen(r.status) ? 1 : 0 },
      geometry: { type: "Point", coordinates: [r.location.lon, r.location.lat] },
    })),
  };
}

type Paint = Record<string, unknown>;
type Layout = Record<string, unknown>;

/**
 * Night colours for a layer of the e-Himaya street style (infra/maps/styles/ehimaya-streets.json) or of the raster
 * fallback: the same map, read on a dark wall. Unknown layers are left as they are.
 */
export function opsRoomRestyle(layer: { id: string; type: string }): { paint: Paint; layout?: Layout } | null {
  const { id, type } = layer;
  if (type === "background") return { paint: { "background-color": "#0B1122" } };
  if (type === "raster") return { paint: { "raster-brightness-max": 0.32, "raster-saturation": -0.7, "raster-contrast": 0.15 } };
  if (id === "water") return { paint: { "fill-color": "#0C2547" } };
  if (id === "waterway") return { paint: { "line-color": "#3E7CC0" } };
  if (id === "landcover-wood" || id === "park") return { paint: { "fill-color": "#11291F", "fill-opacity": 0.7 } };
  if (id === "landcover-sand") return { paint: { "fill-color": "#1A1C24", "fill-opacity": 0.6 } };
  if (id === "landuse-residential") return { paint: { "fill-color": "#121A30", "fill-opacity": 0.8 } };
  // Buildings rise as extrusions in 3D (opsRoomBuildings); the flat fill stays as their 2D footprint.
  if (id === "building") return { paint: { "fill-color": "#1A2440", "fill-opacity": 0.9 } };
  if (id === "aeroway") return { paint: { "line-color": "#3A4A7A" } };
  if (type === "line" && id.endsWith("-casing")) return { paint: { "line-color": "#0B1122" } };
  if (id === "road-motorway") return { paint: { "line-color": "#FFA733" } };
  if (id === "road-primary") return { paint: { "line-color": "#E0B25A" } };
  if (id === "road-secondary") return { paint: { "line-color": "#5D7BD6" } };
  if (id === "road-minor") return { paint: { "line-color": "#2A3658" } };
  if (id === "railway") return { paint: { "line-color": "#7E89A8" } };
  if (id.startsWith("boundary")) return { paint: { "line-color": "#8FA8FF", "line-opacity": 0.6 } };
  if (type === "symbol") return { paint: { "text-color": "#C7D0E6", "text-halo-color": "#0B1122", "text-halo-width": 1.4 } };
  return null;
}

/** Height of a hotspot column in metres: the busiest cell of the view reaches `top`. */
export function hexHeight(count: number, max: number, top = 2500): number {
  if (max <= 0 || count <= 0) return 0;
  return Math.round((count / max) * top);
}
