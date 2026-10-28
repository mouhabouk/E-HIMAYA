import type { ExpressionSpecification, GeoJSONSource, Map as MlMap, MapMouseEvent, Marker, Popup } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection } from "geojson";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { CATEGORY_ICON_PATHS } from "../lib/categoryIcons";
import type { BBox } from "../lib/filters";
import { maplibregl } from "../lib/maplibre";
import { mapStyle } from "../lib/mapStyle";
import { POI_ICON_PATHS, type PoiKind } from "../lib/poiIcons";
import type { DialBody } from "../lib/telephonyTypes";
import type { Category, ReportStatus } from "../lib/types";
import { windArrowImage } from "../lib/weather";

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
  /** Outbound call from the popup through the softphone (phase 7, FR-C-10). */
  call?: DialBody;
  /** Map data layers (phase B1): the layer's own icon path and colour; a cluster shows its count. */
  iconPath?: string;
  colour?: string;
  count?: number;
  /** Extra lines of the popup (phone, address, hours…). */
  details?: string[];
}

/** A filled area drawn under the markers (phase 5: alert polygons), always also named in a list beside the map. */
export interface MapPolygon {
  id: string;
  /** GeoJSON Polygon rings of [lon, lat]. */
  coordinates: [number, number][][];
  /** Colour band of the area (alerts: their severity). */
  tone: "high" | "medium" | "low";
  /** Explicit colour (phase 7 forecast horizons), overriding the tone. */
  colour?: string;
  /** Outline style: dashed (alerts, default) or solid (forecasts). */
  outline?: "dashed" | "solid";
}

/** A path drawn as a line (phase 6: the location track of a live stream), also described in text beside the map. */
export interface MapLine {
  id: string;
  /** [lon, lat] positions, oldest first. */
  coordinates: [number, number][];
  /** Line colour (phase 7 vehicle route), default blue. */
  colour?: string;
}

/**
 * Weather layer (phase 7 §1): grid points with the values the paint expressions read (see lib/weather.ts
 * weatherMapData), and which of the three views are on.
 */
export interface MapWeather {
  data: FeatureCollection;
  fire: boolean;
  wind: boolean;
  rain: boolean;
}

/** A popup anchored on the map whose content is rendered by React (e.g. the weather of a point). */
export interface MapPopupContent {
  lon: number;
  lat: number;
  /** Changes when the content is for another point (re-opens the popup there). */
  key: string;
  node: ReactNode;
}

/** A cell of an aggregate grid (phase 8 hotspots): a hexagon filled by its count class, never a single point. */
export interface MapHex {
  id: string;
  /** GeoJSON Polygon rings of [lon, lat]. */
  coordinates: [number, number][][];
  colour: string;
  count: number;
}

/** A point of a density (heat) layer, e.g. ready volunteers. */
export interface HeatPoint {
  lon: number;
  lat: number;
  /** Weight of the point (phase L1b: a beach's risk score / 100); 1 when omitted. */
  weight?: number;
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
  /** Aggregate hexagon grid (analytics hotspots), drawn under every other layer. */
  hexes?: MapHex[];
  /** Density layer (ready volunteers): a MapLibre heatmap under the markers. */
  heat?: HeatPoint[];
  /** Colours of the density layer, fixed when the map is created: greens (readiness) or green-amber-red (risk). */
  heatTone?: "ready" | "risk";
  /** Lines and areas of the map data layers (phase L1b): GeoJSON features whose `colour` property paints them. */
  shapes?: FeatureCollection;
  /** Paths (stream location tracks). */
  lines?: MapLine[];
  /** Weather layer (fire danger field, wind arrows, rain level). */
  weather?: MapWeather | null;
  /** A click on the map background (not on a marker): e.g. the weather of that point. */
  onMapClick?: (lon: number, lat: number) => void;
  /** React-rendered popup; `onPopupClose` is called when the user closes it. */
  popup?: MapPopupContent | null;
  onPopupClose?: () => void;
  /** Fit the view to these bounds whenever they change (e.g. a forecast or a route was drawn). */
  focusBounds?: BBox | null;
  /** "Call" button in the popups of reports (reporter) and points with `call`; omitted without telephony. */
  onCall?: (body: DialBody) => void;
  callLabel?: string;
}

type GeoJsonData = FeatureCollection;

const POLYGON_SOURCE = "ehimaya-polygons";
const HEAT_SOURCE = "ehimaya-heat";
const HEX_SOURCE = "ehimaya-hexes";
const LINE_SOURCE = "ehimaya-lines";
const SHAPE_SOURCE = "ehimaya-shapes";
const WEATHER_SOURCE = "ehimaya-weather";
const WIND_ICON = "ehimaya-wind-arrow";
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
      properties: { colour: p.colour ?? TONE_COLOURS[p.tone], dashed: p.outline !== "solid" },
      geometry: { type: "Polygon", coordinates: p.coordinates },
    })),
  };
}

function hexData(hexes: MapHex[]): GeoJsonData {
  return {
    type: "FeatureCollection",
    features: hexes.map((h) => ({
      type: "Feature",
      id: h.id,
      properties: { colour: h.colour, count: h.count },
      geometry: { type: "Polygon", coordinates: h.coordinates },
    })),
  };
}

function heatData(points: HeatPoint[]): GeoJsonData {
  return {
    type: "FeatureCollection",
    features: points.map((p) => ({
      type: "Feature",
      properties: { w: p.weight ?? 1 },
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
    })),
  };
}

function lineData(lines: MapLine[]): GeoJsonData {
  return {
    type: "FeatureCollection",
    features: lines
      .filter((l) => l.coordinates.length >= 2)
      .map((l) => ({
        type: "Feature",
        id: l.id,
        properties: { colour: l.colour ?? "#1d4ed8" },
        geometry: { type: "LineString", coordinates: l.coordinates },
      })),
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

function callButton(label: string, body: DialBody, onCall: (body: DialBody) => void): HTMLElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn--small btn--call";
  button.textContent = label;
  button.addEventListener("click", () => onCall(body));
  return button;
}

function popupContent(
  m: MapMarker,
  openLabel: string,
  onOpen?: (id: string) => void,
  call?: { label: string; onCall: (body: DialBody) => void },
): HTMLElement {
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
  if (call) root.append(callButton(call.label, { report_id: m.id }, call.onCall));
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

/** A point opens a popup when it links somewhere or has details to show (places of a map data layer). */
function poiInteractive(p: MapPoi): boolean {
  return Boolean(p.href) || (p.details?.length ?? 0) > 0;
}

function poiElement(p: MapPoi): HTMLElement {
  // Interactive points are buttons (keyboard-focusable, open a popup); the others are labelled images.
  const el = poiInteractive(p) ? document.createElement("button") : document.createElement("div");
  if (el instanceof HTMLButtonElement) el.type = "button";
  else el.setAttribute("role", "img");
  el.className = `map-poi map-poi--${p.kind}`;
  el.setAttribute("aria-label", poiLabel(p));
  if (p.colour) el.style.background = p.colour;
  if (p.count !== undefined) {
    const count = document.createElement("span");
    count.textContent = String(p.count);
    count.setAttribute("aria-hidden", "true");
    el.appendChild(count);
  } else {
    el.appendChild(iconSvg(p.iconPath ?? POI_ICON_PATHS[p.kind]));
  }
  return el;
}

function poiPopupContent(
  p: MapPoi,
  openLabel: string,
  onOpen?: (href: string) => void,
  call?: { label: string; onCall: (body: DialBody) => void },
): HTMLElement {
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
  for (const line of p.details ?? []) {
    const detail = document.createElement("div");
    detail.dir = "auto";
    detail.textContent = line;
    root.append(detail);
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
  if (call && p.call) root.append(callButton(call.label, p.call, call.onCall));
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
  hexes,
  heat,
  heatTone = "ready",
  shapes,
  lines,
  weather,
  onMapClick,
  popup,
  onPopupClose,
  focusBounds,
  onCall,
  callLabel,
}: MapViewProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const markersRef = useRef(new Map<string, { marker: Marker; el: HTMLElement; data: MapMarker }>());
  const poisRef = useRef(new Map<string, { marker: Marker; key: string }>());
  const callbacks = useRef({ onOpen, onBoundsChange, onOpenPoi, onMapClick, onPopupClose, onCall });
  useEffect(() => {
    callbacks.current = { onOpen, onBoundsChange, onOpenPoi, onMapClick, onPopupClose, onCall };
  });
  // The call button is offered only when a handler is given (telephony roles); its label is part of the popup.
  const callKey = onCall && callLabel ? callLabel : "";
  const [popupEl] = useState(() => {
    const el = document.createElement("div");
    el.className = "map-popup map-popup--react";
    return el;
  });
  const popupRef = useRef<Popup | null>(null);

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
    // Background clicks only: markers are buttons of their own, whose clicks bubble through the container.
    map.on("click", (e: MapMouseEvent) => {
      if (e.originalEvent.target !== map.getCanvas()) return;
      callbacks.current.onMapClick?.(e.lngLat.lng, e.lngLat.lat);
    });
    mapRef.current = map;
    const registry = markersRef.current;
    const poiRegistry = poisRef.current;
    return () => {
      for (const { marker } of registry.values()) marker.remove();
      registry.clear();
      for (const { marker } of poiRegistry.values()) marker.remove();
      poiRegistry.clear();
      popupRef.current?.remove();
      popupRef.current = null;
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
    const call = callKey ? { label: callKey, onCall: (b: DialBody) => callbacks.current.onCall?.(b) } : undefined;
    for (const m of markers) {
      seen.add(m.id);
      const existing = registry.get(m.id);
      if (existing) {
        updateMarkerElement(existing.el, m);
        if (existing.data.lon !== m.lon || existing.data.lat !== m.lat) existing.marker.setLngLat([m.lon, m.lat]);
        if (openLabel) existing.marker.getPopup().setDOMContent(popupContent(m, openLabel, (id) => callbacks.current.onOpen?.(id), call));
        existing.data = m;
        continue;
      }
      const el = markerElement(m);
      const marker = new maplibregl.Marker({ element: el }).setLngLat([m.lon, m.lat]);
      if (openLabel) {
        marker.setPopup(
          new maplibregl.Popup({ offset: 16, closeButton: true, focusAfterOpen: true }).setDOMContent(
            popupContent(m, openLabel, (id) => callbacks.current.onOpen?.(id), call),
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
  }, [markers, openLabel, callKey]);

  // Institutions layer: re-create a point only when what it shows changed.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const registry = poisRef.current;
    const seen = new Set<string>();
    const call = callKey ? { label: callKey, onCall: (b: DialBody) => callbacks.current.onCall?.(b) } : undefined;
    for (const p of pois ?? []) {
      const id = `${p.kind}:${p.id}`;
      seen.add(id);
      const key = JSON.stringify([
        p.lon,
        p.lat,
        p.title,
        p.subtitle,
        p.href,
        poiOpenLabel,
        p.call,
        callKey,
        p.iconPath,
        p.colour,
        p.count,
        p.details,
      ]);
      const existing = registry.get(id);
      if (existing?.key === key) continue;
      existing?.marker.remove();
      const marker = new maplibregl.Marker({ element: poiElement(p) }).setLngLat([p.lon, p.lat]);
      if (poiInteractive(p)) {
        marker.setPopup(
          new maplibregl.Popup({ offset: 14, closeButton: true, focusAfterOpen: true }).setDOMContent(
            poiPopupContent(p, poiOpenLabel ?? "", (href) => callbacks.current.onOpenPoi?.(href), call),
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
  }, [pois, poiOpenLabel, callKey]);

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
        filter: ["==", ["get", "dashed"], true],
        paint: { "line-color": ["get", "colour"], "line-width": 2, "line-dasharray": [3, 2] },
      });
      map.addLayer({
        id: `${POLYGON_SOURCE}-solid`,
        type: "line",
        source: POLYGON_SOURCE,
        filter: ["==", ["get", "dashed"], false],
        paint: { "line-color": ["get", "colour"], "line-width": 2.5 },
      });
    });
  }, [polygons]);

  // Hotspot hexagons (phase 8): one source, created on first use and then only updated.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || hexes === undefined) return;
    const data = hexData(hexes);
    whenStyleReady(map, () => {
      const source = map.getSource<GeoJSONSource>(HEX_SOURCE);
      if (source) {
        void source.setData(data); // resolves once applied; failures are fired as map "error" events
        return;
      }
      map.addSource(HEX_SOURCE, { type: "geojson", data });
      map.addLayer({
        id: `${HEX_SOURCE}-fill`,
        type: "fill",
        source: HEX_SOURCE,
        paint: { "fill-color": ["get", "colour"], "fill-opacity": 0.62 },
      });
      map.addLayer({
        id: `${HEX_SOURCE}-line`,
        type: "line",
        source: HEX_SOURCE,
        paint: { "line-color": "#ffffff", "line-width": 0.6, "line-opacity": 0.8 },
      });
    });
  }, [hexes]);

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
          "heatmap-weight": ["coalesce", ["get", "w"], 1],
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 6, 12, 14, 30],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 6, 0.6, 14, 1.5],
          "heatmap-opacity": 0.65,
          "heatmap-color":
            heatTone === "risk"
              ? ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(21,128,61,0)", 0.25, "rgb(22,163,74)", 0.5, "rgb(217,119,6)", 0.8, "rgb(220,38,38)", 1, "rgb(127,29,29)"]
              : ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(21,128,61,0)", 0.3, "rgb(134,239,172)", 0.6, "rgb(34,197,94)", 1, "rgb(20,83,45)"],
        },
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the tone is fixed when the layer is created
  }, [heat]);

  // Lines and areas of the map data layers (rivers, forests, beaches): under the markers, in each layer's colour.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || shapes === undefined) return;
    whenStyleReady(map, () => {
      const source = map.getSource<GeoJSONSource>(SHAPE_SOURCE);
      if (source) {
        void source.setData(shapes); // resolves once applied; failures are fired as map "error" events
        return;
      }
      map.addSource(SHAPE_SOURCE, { type: "geojson", data: shapes });
      const areas: ExpressionSpecification = ["match", ["geometry-type"], ["Polygon", "MultiPolygon"], true, false];
      map.addLayer({
        id: `${SHAPE_SOURCE}-fill`,
        type: "fill",
        source: SHAPE_SOURCE,
        filter: areas,
        paint: { "fill-color": ["get", "colour"], "fill-opacity": 0.22 },
      });
      map.addLayer({
        id: `${SHAPE_SOURCE}-line`,
        type: "line",
        source: SHAPE_SOURCE,
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": ["get", "colour"], "line-width": ["case", areas, 1.2, 3], "line-opacity": 0.9 },
      });
    });
  }, [shapes]);

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
        paint: { "line-color": ["get", "colour"], "line-width": 4, "line-opacity": 0.85 },
      });
    });
  }, [lines]);

  // Weather layer: fire danger field (blurred discs), heavy-rain rings and wind arrows, under every marker.
  const showFire = weather?.fire ?? false;
  const showWind = weather?.wind ?? false;
  const showRain = weather?.rain ?? false;
  const weatherData = weather?.data;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || weather === undefined) return;
    const data: GeoJsonData = weatherData ?? { type: "FeatureCollection", features: [] };
    whenStyleReady(map, () => {
      const visibility = (on: boolean) => (on ? "visible" : "none");
      const source = map.getSource<GeoJSONSource>(WEATHER_SOURCE);
      if (source) {
        void source.setData(data);
      } else {
        map.addSource(WEATHER_SOURCE, { type: "geojson", data });
        // A 0.25° grid is ~28 km between points: the discs grow with the zoom so neighbours blend into a field.
        const radius = ["interpolate", ["exponential", 2], ["zoom"], 4, 3, 6, 12, 8, 48, 10, 190] as const;
        map.addLayer({
          id: `${WEATHER_SOURCE}-fire`,
          type: "circle",
          source: WEATHER_SOURCE,
          filter: ["!=", ["get", "fire_class"], ""],
          paint: {
            "circle-color": ["get", "fire"],
            "circle-radius": radius as unknown as number,
            "circle-blur": 0.7,
            "circle-opacity": 0.45,
          },
        });
        map.addLayer({
          id: `${WEATHER_SOURCE}-rain`,
          type: "circle",
          source: WEATHER_SOURCE,
          filter: ["!=", ["get", "rain_level"], "none"],
          paint: {
            "circle-color": "rgba(0,0,0,0)",
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 5, 10, 22],
            "circle-stroke-color": ["get", "rain"],
            "circle-stroke-width": ["match", ["get", "rain_level"], "warning", 4, 2],
          },
        });
        if (!map.hasImage(WIND_ICON)) {
          const image = windArrowImage();
          if (image) map.addImage(WIND_ICON, image, { pixelRatio: 2 });
        }
        map.addLayer({
          id: `${WEATHER_SOURCE}-wind`,
          type: "symbol",
          source: WEATHER_SOURCE,
          filter: ["==", ["get", "has_wind"], true],
          layout: {
            "icon-image": WIND_ICON,
            "icon-rotate": ["get", "wind_to"],
            "icon-rotation-alignment": "map",
            "icon-allow-overlap": true,
            "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["get", "wind"], 0, 0.6, 30, 1, 80, 1.6],
          },
        });
      }
      map.setLayoutProperty(`${WEATHER_SOURCE}-fire`, "visibility", visibility(showFire));
      map.setLayoutProperty(`${WEATHER_SOURCE}-rain`, "visibility", visibility(showRain));
      map.setLayoutProperty(`${WEATHER_SOURCE}-wind`, "visibility", visibility(showWind));
    });
    // `weather` itself is only checked for presence; the data and switches are the dependencies.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weatherData, showFire, showWind, showRain, weather === undefined]);

  // React-rendered popup (portal into a MapLibre popup).
  const popupKey = popup?.key ?? null;
  const popupLon = popup?.lon;
  const popupLat = popup?.lat;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || popupKey === null || popupLon === undefined || popupLat === undefined) return;
    const p = new maplibregl.Popup({ closeButton: true, focusAfterOpen: true, maxWidth: "320px" })
      .setLngLat([popupLon, popupLat])
      .setDOMContent(popupEl)
      .addTo(map);
    const onClose = () => callbacks.current.onPopupClose?.();
    p.on("close", onClose);
    popupRef.current = p;
    return () => {
      p.off("close", onClose);
      p.remove();
      if (popupRef.current === p) popupRef.current = null;
    };
  }, [popupKey, popupLon, popupLat, popupEl]);

  // Fit the view to new focus bounds (a forecast or route drawn on demand).
  const focusKey = focusBounds ? focusBounds.map((n) => n.toFixed(5)).join(",") : null;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focusKey) return;
    const [w, s, e, n] = focusKey.split(",").map(Number) as [number, number, number, number];
    map.fitBounds([w, s, e, n], { padding: 32, maxZoom: 15, duration: 0 });
  }, [focusKey]);

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

  return (
    <>
      <div ref={container} className={className ?? "map"} role="region" aria-label={ariaLabel} />
      {popup && createPortal(popup.node, popupEl)}
    </>
  );
}
