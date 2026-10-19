import type { FeatureCollection } from "geojson";
import type { GeoJSONSource, Map as MlMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { mapStyle } from "../lib/mapStyle";
import { maplibregl } from "../lib/maplibre";
import type { GeoPoint } from "../lib/types";

export type MarkerKind = "org" | "point" | "evacuation_point" | "water_point" | "alarm";

export interface MapMarker {
  id: string;
  lat: number;
  lon: number;
  kind: MarkerKind;
  /** Accessible name of the marker button. */
  label: string;
  draggable?: boolean;
  selected?: boolean;
}

export interface MapViewProps {
  center: GeoPoint;
  zoom?: number;
  markers: MapMarker[];
  ariaLabel: string;
  styleUrl: string | null;
  dir: "rtl" | "ltr";
  className?: string;
  /** Move the view when `center` changes (location pickers). */
  followCenter?: boolean;
  /** Change it to re-apply the markers' positions (e.g. after a refused drag). */
  resetToken?: number;
  /** Circle drawn around a point (the 2 km limit of map features). */
  circle?: { center: GeoPoint; meters: number } | null;
  onMapClick?: (p: GeoPoint) => void;
  onMarkerClick?: (id: string) => void;
  onMarkerDragEnd?: (id: string, p: GeoPoint) => void;
}

const SVG_NS = "http://www.w3.org/2000/svg";
const ICONS: Record<MarkerKind, string> = {
  // Building
  org: "M4 21V5l8-3 8 3v16h-6v-5h-4v5zm4-13v2h2V8zm6 0v2h2V8zm-6 4v2h2v-2zm6 0v2h2v-2z",
  // Pin
  point: "M12 2a7 7 0 0 1 7 7c0 5-7 13-7 13S5 14 5 9a7 7 0 0 1 7-7zm0 4.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z",
  // People gathering (evacuation / assembly point)
  evacuation_point:
    "M8 4a2 2 0 1 1 0 4 2 2 0 0 1 0-4zm8 0a2 2 0 1 1 0 4 2 2 0 0 1 0-4zM5 10h6v6H9v5H7v-5H5zm8 0h6v6h-2v5h-2v-5h-2z",
  // Drop (water point / hydrant)
  water_point: "M12 2s7 7.6 7 12.5A7 7 0 0 1 5 14.5C5 9.6 12 2 12 2z",
  // Bell (alarm)
  alarm: "M12 3a6 6 0 0 1 6 6v5l2 3H4l2-3V9a6 6 0 0 1 6-6zm-2.5 15h5a2.5 2.5 0 0 1-5 0z",
};

function markerElement(m: MapMarker): HTMLElement {
  const el = document.createElement("button");
  el.type = "button";
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("fill", "currentColor");
  svg.appendChild(path);
  el.appendChild(svg);
  updateMarkerElement(el, m);
  return el;
}

function updateMarkerElement(el: HTMLElement, m: MapMarker): void {
  el.className = `map-marker map-marker--${m.kind}${m.selected ? " map-marker--selected" : ""}`;
  el.setAttribute("aria-label", m.label);
  el.title = m.label;
  el.querySelector("path")?.setAttribute("d", ICONS[m.kind]);
}

/** Polygon approximating a circle on the sphere (64 segments). */
export function circlePolygon(center: GeoPoint, meters: number, steps = 64): [number, number][] {
  const R = 6_371_008.8;
  const lat = (center.lat * Math.PI) / 180;
  const lon = (center.lon * Math.PI) / 180;
  const d = meters / R;
  const ring: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const brng = (2 * Math.PI * i) / steps;
    const lat2 = Math.asin(Math.sin(lat) * Math.cos(d) + Math.cos(lat) * Math.sin(d) * Math.cos(brng));
    const lon2 = lon + Math.atan2(Math.sin(brng) * Math.sin(d) * Math.cos(lat), Math.cos(d) - Math.sin(lat) * Math.sin(lat2));
    ring.push([(lon2 * 180) / Math.PI, (lat2 * 180) / Math.PI]);
  }
  return ring;
}

function circleData(circle: { center: GeoPoint; meters: number } | null | undefined): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: circle
      ? [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [circlePolygon(circle.center, circle.meters)] } }]
      : [],
  };
}

/** MapLibre map with keyboard-focusable HTML markers, optional click-to-place, dragging and a radius circle. */
export function MapView({
  center,
  zoom = 15,
  markers,
  ariaLabel,
  styleUrl,
  dir,
  className,
  followCenter = false,
  circle,
  resetToken,
  onMapClick,
  onMarkerClick,
  onMarkerDragEnd,
}: MapViewProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const registry = useRef(new Map<string, { marker: Marker; el: HTMLElement; data: MapMarker }>());
  const callbacks = useRef({ onMapClick, onMarkerClick, onMarkerDragEnd });
  const circleRef = useRef(circle);
  useEffect(() => {
    callbacks.current = { onMapClick, onMarkerClick, onMarkerDragEnd };
    circleRef.current = circle;
  });

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: mapStyle(styleUrl),
      center: [center.lon, center.lat],
      zoom,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), dir === "rtl" ? "top-left" : "top-right");
    map.on("click", (e) => callbacks.current.onMapClick?.({ lat: e.lngLat.lat, lon: e.lngLat.lng }));
    map.on("load", () => {
      map.addSource("radius", { type: "geojson", data: circleData(circleRef.current) });
      map.addLayer({ id: "radius-fill", type: "fill", source: "radius", paint: { "fill-color": "#1a56db", "fill-opacity": 0.06 } });
      map.addLayer({
        id: "radius-line",
        type: "line",
        source: "radius",
        paint: { "line-color": "#1a56db", "line-width": 2, "line-dasharray": [2, 2] },
      });
    });
    mapRef.current = map;
    const markersNow = registry.current;
    return () => {
      for (const { marker } of markersNow.values()) marker.remove();
      markersNow.clear();
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the map is created once per mount
  }, []);

  const lat = center.lat;
  const lon = center.lon;
  useEffect(() => {
    if (followCenter) mapRef.current?.easeTo({ center: [lon, lat] });
  }, [followCenter, lat, lon]);

  useEffect(() => {
    const source = mapRef.current?.getSource<GeoJSONSource>("radius");
    void source?.setData(circleData(circle)); // resolves once applied; failures are fired as map "error" events
  }, [circle]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const seen = new Set<string>();
    for (const m of markers) {
      seen.add(m.id);
      const existing = registry.current.get(m.id);
      if (existing && existing.data.draggable === m.draggable) {
        updateMarkerElement(existing.el, m);
        // Always re-apply the position: a refused drag must snap the marker back to the stored point.
        existing.marker.setLngLat([m.lon, m.lat]);
        existing.data = m;
        continue;
      }
      existing?.marker.remove();
      const el = markerElement(m);
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        callbacks.current.onMarkerClick?.(m.id);
      });
      const marker = new maplibregl.Marker({ element: el, draggable: !!m.draggable }).setLngLat([m.lon, m.lat]).addTo(map);
      marker.on("dragend", () => {
        const p = marker.getLngLat();
        callbacks.current.onMarkerDragEnd?.(m.id, { lat: p.lat, lon: p.lng });
      });
      registry.current.set(m.id, { marker, el, data: m });
    }
    for (const [id, entry] of registry.current) {
      if (!seen.has(id)) {
        entry.marker.remove();
        registry.current.delete(id);
      }
    }
  }, [markers, resetToken]);

  return <div ref={container} className={className ?? "map"} role="region" aria-label={ariaLabel} />;
}
