import type { GeoJSONSource, Map as MlMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection } from "geojson";
import { useEffect, useRef } from "react";
import { CATEGORY_ICON_PATHS } from "../lib/categoryIcons";
import type { BBox } from "../lib/filters";
import { maplibregl } from "../lib/maplibre";
import { mapStyle } from "../lib/mapStyle";
import { POI_ICON_PATHS, type PoiKind } from "../lib/poiIcons";
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

/** A point of the institutions layer: an institution, or one of its features (evacuation, water, alarm). */
export interface MapPoi {
  id: string;
  lon: number;
  lat: number;
  kind: PoiKind;
  /** Accessible name and popup heading. */
  title: string;
  subtitle?: string;
  /** In-app link opened from the popup (e.g. /orgs/:id); without it the point is not interactive. */
  href?: string;
}

/** A filled area drawn under the markers (phase 5: alert polygons), always also named in a list beside the map. */
export interface MapPolygon {
  id: string;
  /** GeoJSON Polygon rings of [lon, lat]. */
  coordinates: [number, number][][];
  /** Colour band of the area (alerts: their severity). */
  tone: "high" | "medium" | "low";
}

/** A path drawn as a line (phase 6: the location track of a live stream), also described in text beside the map. */
export interface MapLine {
  id: string;
  /** [lon, lat] positions, oldest first. */
  coordinates: [number, number][];
}

/** A point of a density (heat) layer, e.g. ready volunteers. */
export interface HeatPoint {
  lon: number;
  lat: number;
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
  /** Institutions layer (phase 4): drawn with distinct shapes, above or beside the report markers. */
  pois?: MapPoi[];
  /** Text of the popup link of a point that has an `href`. */
  poiOpenLabel?: string;
  onOpenPoi?: (href: string) => void;
  /** Areas drawn as translucent fills with an outline (alerts layer). */
  polygons?: MapPolygon[];
  /** Density layer (ready volunteers): a MapLibre heatmap under the markers. */
  heat?: HeatPoint[];
  /** Paths (stream location tracks). */
  lines?: MapLine[];
}

type GeoJsonData = FeatureCollection;

const POLYGON_SOURCE = "ehimaya-polygons";
const HEAT_SOURCE = "ehimaya-heat";
const LINE_SOURCE = "ehimaya-lines";
const TONE_COLOURS: Record<MapPolygon["tone"], string> = { high: "#b91c1c", medium: "#b45309", low: "#4b5563" };

/** Run `fn` now if the style is ready, otherwise once it has loaded. */
function whenStyleReady(map: MlMap, fn: () => void): void {
  if (map.isStyleLoaded()) fn();
  // The style loads once: a plain listener is enough (`once` without a listener returns a promise).
  else map.on("load", fn);
}

function polygonData(polygons: MapPolygon[]): GeoJsonData {
  return {
    type: "FeatureCollection",
    features: polygons.map((p) => ({
      type: "Feature",
      id: p.id,
      properties: { colour: TONE_COLOURS[p.tone] },
      geometry: { type: "Polygon", coordinates: p.coordinates },
    })),
  };
}

function heatData(points: HeatPoint[]): GeoJsonData {
  return {
    type: "FeatureCollection",
    features: points.map((p) => ({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [p.lon, p.lat] } })),
  };
}

function lineData(lines: MapLine[]): GeoJsonData {
  return {
    type: "FeatureCollection",
    features: lines
      .filter((l) => l.coordinates.length >= 2)
      .map((l) => ({ type: "Feature", id: l.id, properties: {}, geometry: { type: "LineString", coordinates: l.coordinates } })),
  };
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

function iconSvg(path: string): SVGSVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const p = document.createElementNS(SVG_NS, "path");
  p.setAttribute("fill", "currentColor");
  p.setAttribute("fill-rule", "evenodd");
  p.setAttribute("d", path);
  svg.appendChild(p);
  return svg;
}

function poiLabel(p: MapPoi): string {
  return p.subtitle ? `${p.title} — ${p.subtitle}` : p.title;
}

function poiElement(p: MapPoi): HTMLElement {
  // Interactive points are buttons (keyboard-focusable, open a popup); the others are labelled images.
  const el = p.href ? document.createElement("button") : document.createElement("div");
  if (el instanceof HTMLButtonElement) el.type = "button";
  else el.setAttribute("role", "img");
  el.className = `map-poi map-poi--${p.kind}`;
  el.setAttribute("aria-label", poiLabel(p));
  el.appendChild(iconSvg(POI_ICON_PATHS[p.kind]));
  return el;
}

function poiPopupContent(p: MapPoi, openLabel: string, onOpen?: (href: string) => void): HTMLElement {
  const root = document.createElement("div");
  root.className = "map-popup";
  const title = document.createElement("strong");
  title.textContent = p.title;
  root.append(title);
  if (p.subtitle) {
    const sub = document.createElement("div");
    sub.textContent = p.subtitle;
    root.append(sub);
  }
  if (p.href) {
    const href = p.href;
    const link = document.createElement("a");
    link.href = href;
    link.textContent = openLabel;
    link.addEventListener("click", (e) => {
      if (!onOpen || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
      e.preventDefault();
      onOpen(href);
    });
    root.append(link);
  }
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
  pois,
  poiOpenLabel,
  onOpenPoi,
  polygons,
  heat,
  lines,
}: MapViewProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const markersRef = useRef(new Map<string, { marker: Marker; el: HTMLElement; data: MapMarker }>());
  const poisRef = useRef(new Map<string, { marker: Marker; key: string }>());
  const callbacks = useRef({ onOpen, onBoundsChange, onOpenPoi });
  useEffect(() => {
    callbacks.current = { onOpen, onBoundsChange, onOpenPoi };
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
    const poiRegistry = poisRef.current;
    return () => {
      for (const { marker } of registry.values()) marker.remove();
      registry.clear();
      for (const { marker } of poiRegistry.values()) marker.remove();
      poiRegistry.clear();
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

  // Institutions layer: re-create a point only when what it shows changed.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const registry = poisRef.current;
    const seen = new Set<string>();
    for (const p of pois ?? []) {
      const id = `${p.kind}:${p.id}`;
      seen.add(id);
      const key = JSON.stringify([p.lon, p.lat, p.title, p.subtitle, p.href, poiOpenLabel]);
      const existing = registry.get(id);
      if (existing?.key === key) continue;
      existing?.marker.remove();
      const marker = new maplibregl.Marker({ element: poiElement(p) }).setLngLat([p.lon, p.lat]);
      if (p.href) {
        marker.setPopup(
          new maplibregl.Popup({ offset: 14, closeButton: true, focusAfterOpen: true }).setDOMContent(
            poiPopupContent(p, poiOpenLabel ?? "", (href) => callbacks.current.onOpenPoi?.(href)),
          ),
        );
      }
      marker.addTo(map);
      registry.set(id, { marker, key });
    }
    for (const [id, entry] of registry) {
      if (!seen.has(id)) {
        entry.marker.remove();
        registry.delete(id);
      }
    }
  }, [pois, poiOpenLabel]);

  // Alert areas: one GeoJSON source, created on first use and then only updated.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || polygons === undefined) return;
    const data = polygonData(polygons);
    whenStyleReady(map, () => {
      const source = map.getSource<GeoJSONSource>(POLYGON_SOURCE);
      if (source) {
        void source.setData(data); // resolves once applied; failures are fired as map "error" events
        return;
      }
      map.addSource(POLYGON_SOURCE, { type: "geojson", data });
      map.addLayer({
        id: `${POLYGON_SOURCE}-fill`,
        type: "fill",
        source: POLYGON_SOURCE,
        paint: { "fill-color": ["get", "colour"], "fill-opacity": 0.18 },
      });
      map.addLayer({
        id: `${POLYGON_SOURCE}-line`,
        type: "line",
        source: POLYGON_SOURCE,
        paint: { "line-color": ["get", "colour"], "line-width": 2, "line-dasharray": [3, 2] },
      });
    });
  }, [polygons]);

  // Readiness density (ready volunteers).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || heat === undefined) return;
    const data = heatData(heat);
    whenStyleReady(map, () => {
      const source = map.getSource<GeoJSONSource>(HEAT_SOURCE);
      if (source) {
        void source.setData(data); // resolves once applied; failures are fired as map "error" events
        return;
      }
      map.addSource(HEAT_SOURCE, { type: "geojson", data });
      map.addLayer({
        id: `${HEAT_SOURCE}-layer`,
        type: "heatmap",
        source: HEAT_SOURCE,
        maxzoom: 15,
        paint: {
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 6, 12, 14, 30],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 6, 0.6, 14, 1.5],
          "heatmap-opacity": 0.65,
          "heatmap-color": [
            "interpolate",
            ["linear"],
            ["heatmap-density"],
            0,
            "rgba(21,128,61,0)",
            0.3,
            "rgb(134,239,172)",
            0.6,
            "rgb(34,197,94)",
            1,
            "rgb(20,83,45)",
          ],
        },
      });
    });
  }, [heat]);

  // Location tracks: one line source, created on first use and then only updated.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || lines === undefined) return;
    const data = lineData(lines);
    whenStyleReady(map, () => {
      const source = map.getSource<GeoJSONSource>(LINE_SOURCE);
      if (source) {
        void source.setData(data); // resolves once applied; failures are fired as map "error" events
        return;
      }
      map.addSource(LINE_SOURCE, { type: "geojson", data });
      map.addLayer({
        id: `${LINE_SOURCE}-layer`,
        type: "line",
        source: LINE_SOURCE,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#1d4ed8", "line-width": 3, "line-opacity": 0.85 },
      });
    });
  }, [lines]);

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
