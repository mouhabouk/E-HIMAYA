import maplibregl, { type GeoJSONSource, type Map as MlMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { BBox } from "../lib/filters";
import { mapStyle } from "../lib/mapStyle";
import type { Vertex } from "../lib/polygon";

interface PolygonDrawMapProps {
  vertices: readonly Vertex[];
  /** Called with the clicked position while drawing; omit to show the area read-only. */
  onAddVertex?: (lon: number, lat: number) => void;
  bounds: BBox;
  ariaLabel: string;
  styleUrl: string | null;
  dir: "rtl" | "ltr";
  className?: string;
}

const SOURCE = "alert-area";

type AreaGeometry =
  | { type: "Point"; coordinates: number[] }
  | { type: "LineString"; coordinates: number[][] }
  | { type: "Polygon"; coordinates: number[][][] };
interface AreaFeature {
  type: "Feature";
  geometry: AreaGeometry;
  properties: Record<string, never>;
}

/** GeoJSON FeatureCollection (typed locally: the GeoJSON namespace types are not installed). */
function areaData(vertices: readonly Vertex[]): { type: "FeatureCollection"; features: AreaFeature[] } {
  const features: AreaFeature[] = vertices.map((v) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [v[0], v[1]] },
    properties: {},
  }));
  const first = vertices[0];
  if (vertices.length >= 3 && first) {
    features.push({
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [[...vertices.map((v) => [v[0], v[1]]), [first[0], first[1]]]] },
      properties: {},
    });
  } else if (vertices.length === 2) {
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: vertices.map((v) => [v[0], v[1]]) },
      properties: {},
    });
  }
  return { type: "FeatureCollection", features };
}

/**
 * Map for drawing an alert area (FR-C-18): each click adds a vertex; the parent owns the vertices (undo, clear,
 * validation). The drawn ring is shown filled; the vertex list is also given as text next to the map.
 */
export function PolygonDrawMap({ vertices, onAddVertex, bounds, ariaLabel, styleUrl, dir, className }: PolygonDrawMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const loaded = useRef(false);
  const latest = useRef({ vertices, onAddVertex });
  useEffect(() => {
    latest.current = { vertices, onAddVertex };
  });

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: mapStyle(styleUrl),
      bounds: [bounds[0], bounds[1], bounds[2], bounds[3]],
      fitBoundsOptions: { padding: 24, maxZoom: 13 },
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), dir === "rtl" ? "top-left" : "top-right");
    map.doubleClickZoom.disable();
    map.on("load", () => {
      map.addSource(SOURCE, { type: "geojson", data: areaData(latest.current.vertices) as never });
      map.addLayer({
        id: `${SOURCE}-fill`,
        type: "fill",
        source: SOURCE,
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "fill-color": "#b91c1c", "fill-opacity": 0.2 },
      });
      map.addLayer({
        id: `${SOURCE}-line`,
        type: "line",
        source: SOURCE,
        filter: ["any", ["==", ["geometry-type"], "Polygon"], ["==", ["geometry-type"], "LineString"]],
        paint: { "line-color": "#b91c1c", "line-width": 2 },
      });
      map.addLayer({
        id: `${SOURCE}-points`,
        type: "circle",
        source: SOURCE,
        filter: ["==", ["geometry-type"], "Point"],
        paint: { "circle-radius": 5, "circle-color": "#ffffff", "circle-stroke-color": "#b91c1c", "circle-stroke-width": 2 },
      });
      loaded.current = true;
    });
    map.on("click", (e) => latest.current.onAddVertex?.(e.lngLat.lng, e.lngLat.lat));
    mapRef.current = map;
    return () => {
      loaded.current = false;
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the map is created once per mount
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded.current) return;
    map.getSource<GeoJSONSource>(SOURCE)?.setData(areaData(vertices));
  }, [vertices]);

  useEffect(() => {
    const canvas = mapRef.current?.getCanvas();
    if (canvas) canvas.style.cursor = onAddVertex ? "crosshair" : "";
  }, [onAddVertex]);

  return <div ref={container} className={className ?? "map"} role="region" aria-label={ariaLabel} />;
}
