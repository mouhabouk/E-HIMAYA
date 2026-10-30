import type { StyleSpecification } from "maplibre-gl";
import type { BBox } from "./filters";

/** Fallback style: OpenStreetMap raster tiles (respect https://operations.osmfoundation.org/policies/tiles/). */
export const OSM_RASTER_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

export function mapStyle(styleUrl: string | null): string | StyleSpecification {
  return styleUrl ?? OSM_RASTER_STYLE;
}

/** Whole country (with a margin), and the contract's accepted report area. */
export const TUNISIA_BOUNDS: BBox = [7.4, 30.2, 11.7, 37.6];

/** Bounding boxes of the 24 gouvernorats (from services/api/seed/geo/tn_gouvernorats.geojson, geoBoundaries). */
export const GOUVERNORAT_BOUNDS: Readonly<Record<number, BBox>> = {
  11: [10.0, 36.69, 10.35, 36.94],
  12: [9.96, 36.82, 10.29, 37.12],
  13: [10.04, 36.45, 10.42, 36.81],
  14: [9.57, 36.55, 10.12, 36.97],
  21: [10.33, 36.35, 11.14, 37.14],
  22: [9.59, 36.0, 10.39, 36.66],
  23: [8.9, 36.72, 10.28, 37.54],
  31: [8.88, 36.34, 9.86, 37.16],
  32: [8.15, 36.35, 9.08, 37.01],
  33: [8.25, 35.62, 9.17, 36.45],
  34: [8.92, 35.48, 9.77, 36.47],
  41: [9.27, 35.02, 10.31, 36.14],
  42: [8.25, 34.63, 9.34, 35.79],
  43: [8.92, 34.26, 10.06, 35.5],
  51: [10.16, 35.4, 10.69, 36.39],
  52: [10.49, 35.42, 11.05, 35.81],
  53: [10.16, 35.09, 11.17, 35.59],
  61: [9.71, 34.17, 11.34, 35.28],
  71: [8.04, 34.05, 9.56, 34.81],
  72: [7.52, 33.42, 8.65, 34.53],
  73: [7.73, 32.5, 10.01, 34.19],
  81: [9.25, 33.27, 10.48, 34.28],
  82: [9.71, 32.25, 11.6, 33.92],
  83: [8.36, 30.23, 11.34, 33.23],
};

export function initialBoundsFor(gouvernoratCode: number | null): BBox {
  return (gouvernoratCode !== null ? GOUVERNORAT_BOUNDS[gouvernoratCode] : undefined) ?? TUNISIA_BOUNDS;
}

/** The box around the given gouvernorats (Tunisia when none). */
export function gouvernoratsBounds(codes: readonly number[]): BBox {
  if (codes.length === 0) return TUNISIA_BOUNDS;
  const boxes = codes.map((c) => initialBoundsFor(c));
  return [
    Math.min(...boxes.map((b) => b[0])),
    Math.min(...boxes.map((b) => b[1])),
    Math.max(...boxes.map((b) => b[2])),
    Math.max(...boxes.map((b) => b[3])),
  ];
}
