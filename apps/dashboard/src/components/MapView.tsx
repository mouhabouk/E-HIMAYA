import maplibregl, { type Map as MlMap, type Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { CATEGORY_ICON_PATHS } from "../lib/categoryIcons";
import type { BBox } from "../lib/filters";
import { mapStyle } from "../lib/mapStyle";
import type { Category, ReportStatus } from "../lib/types";

export interface MapMarker {
  id: string;
  lon: number;
  lat: number;
  status: ReportStatus;
  category: Category;
  /** Accessible name and popup heading (e.g. tracking code + category). */
  title: string;
  /** Second line of the popup (e.g. status label + time). */
  subtitle: string;
  highlight?: boolean;
}

interface MapViewProps {
  markers: MapMarker[];
  bounds: BBox;
  ariaLabel: string;
  styleUrl: string | null;
  /** Text of the popup link; omit to disable popups (mini-map). */
  openLabel?: string;
  onOpen?: (id: string) => void;
  onBoundsChange?: (bbox: BBox) => void;
  interactive?: boolean;
  zoom?: number;
  className?: string;
  dir: "rtl" | "ltr";
  /** Optional non-interactive point drawn under the markers (e.g. an incident's centroid). */
  centroid?: { lon: number; lat: number; label: string } | null;
}

const SVG_NS = "http://www.w3.org/2000/svg";

function markerElement(m: MapMarker): HTMLElement {
  const el = document.createElement("button");
  el.type = "button";
  el.setAttribute("aria-label", `${m.title} — ${m.subtitle}`);
  updateMarkerElement(el, m);
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("fill", "currentColor");
  path.setAttribute("fill-rule", "evenodd");
  path.setAttribute("d", CATEGORY_ICON_PATHS[m.category]);
  svg.appendChild(path);
  el.appendChild(svg);
  return el;
}

function updateMarkerElement(el: HTMLElement, m: MapMarker): void {
  el.className = `map-marker chip--${m.status}${m.highlight ? " map-marker--new" : ""}`;
  el.setAttribute("aria-label", `${m.title} — ${m.subtitle}`);
}

function popupContent(m: MapMarker, openLabel: string, onOpen?: (id: string) => void): HTMLElement {
  // Built with DOM APIs (textContent), never innerHTML: report data is user-supplied.
  const root = document.createElement("div");
  root.className = "map-popup";
  const title = document.createElement("strong");
  title.textContent = m.title;
  const sub = document.createElement("div");
  sub.textContent = m.subtitle;
  const link = document.createElement("a");
  link.href = `/reports/${encodeURIComponent(m.id)}`;
  link.textContent = openLabel;
  link.addEventListener("click", (e) => {
    if (!onOpen || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    onOpen(m.id);
  });
  root.append(title, sub, link);
  return root;
}

function boundsOf(map: MlMap): BBox {
  const b = map.getBounds();
  return [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
}

/** MapLibre map with HTML markers (keyboard-focusable buttons coloured by status, with the category icon). */
export function MapView({
  markers,
  bounds,
  ariaLabel,
  styleUrl,
  openLabel,
  onOpen,
  onBoundsChange,
  interactive = true,
  zoom,
  className,
  dir,
  centroid,
}: MapViewProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const markersRef = useRef(new Map<string, { marker: Marker; el: HTMLElement; data: MapMarker }>());
  const callbacks = useRef({ onOpen, onBoundsChange });
  useEffect(() => {
    callbacks.current = { onOpen, onBoundsChange };
  });

  // Create the map once (bounds/style changes after mount are not applied: the user controls the view).
  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: mapStyle(styleUrl),
      bounds: [bounds[0], bounds[1], bounds[2], bounds[3]],
      fitBoundsOptions: { padding: 24, maxZoom: zoom ?? 14 },
      interactive,
      attributionControl: { compact: true },
      cooperativeGestures: false,
    });
    if (interactive) {
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), dir === "rtl" ? "top-left" : "top-right");
    }
    const emit = () => callbacks.current.onBoundsChange?.(boundsOf(map));
    map.on("load", emit);
    map.on("moveend", emit);
    mapRef.current = map;
    const registry = markersRef.current;
    return () => {
      for (const { marker } of registry.values()) marker.remove();
      registry.clear();
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the map is created once per mount
  }, []);

  // Sync markers (add / update / remove) without re-creating unchanged ones.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const registry = markersRef.current;
    const seen = new Set<string>();
    for (const m of markers) {
      seen.add(m.id);
      const existing = registry.get(m.id);
      if (existing) {
        updateMarkerElement(existing.el, m);
        if (existing.data.lon !== m.lon || existing.data.lat !== m.lat) existing.marker.setLngLat([m.lon, m.lat]);
        if (openLabel) existing.marker.getPopup().setDOMContent(popupContent(m, openLabel, (id) => callbacks.current.onOpen?.(id)));
        existing.data = m;
        continue;
      }
      const el = markerElement(m);
      const marker = new maplibregl.Marker({ element: el }).setLngLat([m.lon, m.lat]);
      if (openLabel) {
        marker.setPopup(
          new maplibregl.Popup({ offset: 16, closeButton: true, focusAfterOpen: true }).setDOMContent(
            popupContent(m, openLabel, (id) => callbacks.current.onOpen?.(id)),
          ),
        );
      }
      marker.addTo(map);
      registry.set(m.id, { marker, el, data: m });
    }
    for (const [id, entry] of registry) {
      if (!seen.has(id)) {
        entry.marker.remove();
        registry.delete(id);
      }
    }
  }, [markers, openLabel]);

  // Centroid marker (decorative for pointer users, labelled for screen readers).
  const centroidLon = centroid?.lon;
  const centroidLat = centroid?.lat;
  const centroidLabel = centroid?.label;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || centroidLon === undefined || centroidLat === undefined) return;
    const el = document.createElement("div");
    el.className = "map-centroid";
    el.setAttribute("role", "img");
    el.setAttribute("aria-label", centroidLabel ?? "");
    const marker = new maplibregl.Marker({ element: el }).setLngLat([centroidLon, centroidLat]).addTo(map);
    return () => {
      marker.remove();
    };
  }, [centroidLon, centroidLat, centroidLabel]);

  return <div ref={container} className={className ?? "map"} role="region" aria-label={ariaLabel} />;
}
