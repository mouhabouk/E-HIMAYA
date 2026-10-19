import type { StyleSpecification } from "maplibre-gl";

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

/** Centre of Tunisia, used when no point is chosen yet. */
export const TUNISIA_CENTER = { lat: 34.8, lon: 9.6 } as const;
