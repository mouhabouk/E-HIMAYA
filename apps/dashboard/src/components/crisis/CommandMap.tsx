import type { FeatureCollection, Feature, Geometry } from "geojson";
import type { GeoJSONSource, Map as MlMap, Marker, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Area, AxisIncident, Evacuation, Shelter } from "../../lib/crisis";
import type { BBox } from "../../lib/filters";
import { maplibregl } from "../../lib/maplibre";
import { OSM_RASTER_STYLE } from "../../lib/mapStyle";
import { useDarkMode } from "./theme";

/**
 * The command map of the crisis screens (phase L3, design §6): a dark or light operations-room map with the
 * gouvernorats (coloured by the highest level of their open axes on the minister's map), the axis areas, the
 * interventions by severity, the shelters, the evacuation zones and the areas of the decisions. A layers panel, zoom,
 * a home button and a 2D/3D switch (the gouvernorats rise with their level in 3D). Every item is also listed beside
 * the map: the map is never the only way to read a value.
 */
export interface CommandMapProps {
  ariaLabel: string;
  bounds: BBox;
  styleUrl: string | null;
  boundaries?: FeatureCollection | null;
  /** Highest open level per gouvernorat code (choropleth, extruded in 3D). */
  levels?: Readonly<Record<number, number>>;
  /** Gouvernorats outside these are dimmed (a governor's map). */
  focus?: readonly number[];
  axisAreas?: { id: string; area: Area | null; level: number }[];
  incidents?: AxisIncident[];
  shelters?: Shelter[];
  evacuations?: Evacuation[];
  decisionAreas?: { id: string; area: Area | null }[];
  /** Gouvernorat names drawn on the map (code → name). */
  labels?: Readonly<Record<number, string>>;
  onSelectGouvernorat?: (code: number) => void;
  /** Starts tilted (3D). */
  tilted?: boolean;
  /** The map sits under the operations-room panels: fit what it shows between them. */
  framed?: boolean;
  className?: string;
}

/** Padding that keeps the fitted area clear of the ops-room panels (mirrors `.ops-room` in global.css). */
function framePadding(el: HTMLElement | null, framed: boolean | undefined) {
  if (!framed || !el || el.clientWidth <= 1100) return 40;
  const side = Math.min(380, Math.max(300, window.innerWidth * 0.23)) + 24;
  return { top: 96, bottom: Math.round(el.clientHeight * 0.34) + 24, left: side, right: side };
}

type LayerKey = "gouvernorats" | "axes" | "incidents" | "shelters" | "evacuations" | "decisions";
const LAYER_KEYS: LayerKey[] = ["gouvernorats", "axes", "incidents", "shelters", "evacuations", "decisions"];
const LAYER_IDS: Record<LayerKey, string[]> = {
  gouvernorats: ["g-fill", "g-extrude", "g-line"],
  axes: ["axis-fill", "axis-glow", "axis-line"],
  incidents: ["inc-halo", "inc-core"],
  shelters: ["shelter-core"],
  evacuations: ["evac-fill", "evac-line"],
  decisions: ["dec-line"],
};

/** Colours of the design system (light / dark values, docs/design-system.md §2). */
function palette(dark: boolean) {
  return dark
    ? {
        sea: "#081022",
        land: "#121a30",
        border: "#3b4a78",
        dim: "#0c1326",
        level: { 1: "#64b5f6", 2: "#ffc933", 3: "#ffa733", 4: "#ff6b6b" } as Record<number, string>,
        severe: "#ff6b6b",
        high: "#ffa733",
        normal: "#ffc933",
        shelter: "#4dd0b8",
        evac: "#4cc772",
        decision: "#c49be6",
        ink: "#e8ecf5",
      }
    : {
        sea: "#dfe8f3",
        land: "#f7f9fc",
        border: "#7c8db8",
        dim: "#e9edf4",
        level: { 1: "#1976d2", 2: "#f5b400", 3: "#f08c00", 4: "#d7141a" } as Record<number, string>,
        severe: "#d7141a",
        high: "#f08c00",
        normal: "#f5b400",
        shelter: "#00806a",
        evac: "#188038",
        decision: "#7838a0",
        ink: "#182038",
      };
}

function baseStyle(styleUrl: string | null, dark: boolean): StyleSpecification | string {
  const colours = palette(dark);
  if (styleUrl) return styleUrl;
  // Without a vector style: the OpenStreetMap raster, darkened at night, over the sea colour.
  return {
    ...OSM_RASTER_STYLE,
    layers: [
      { id: "sea", type: "background", paint: { "background-color": colours.sea } },
      {
        id: "osm",
        type: "raster",
        source: "osm",
        paint: dark
          ? {
              "raster-brightness-min": 0.92,
              "raster-brightness-max": 0.08,
              "raster-saturation": -0.75,
              "raster-contrast": 0.15,
              "raster-opacity": 0.85,
            }
          : { "raster-saturation": -0.35, "raster-opacity": 0.9 },
      },
    ],
  };
}

const feature = (geometry: Geometry, properties: Record<string, unknown>): Feature => ({
  type: "Feature",
  geometry,
  properties,
});
const box = (b: BBox): [number, number, number, number] => [b[0], b[1], b[2], b[3]];
const collection = (features: Feature[]): FeatureCollection => ({ type: "FeatureCollection", features });

export function CommandMap(props: CommandMapProps) {
  const { t, i18n } = useTranslation();
  const dark = useDarkMode();
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const markers = useRef<Marker[]>([]);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [tilted, setTilted] = useState(props.tilted ?? true);
  const [visible, setVisible] = useState<Record<LayerKey, boolean>>({
    gouvernorats: true,
    axes: true,
    incidents: true,
    shelters: true,
    evacuations: true,
    decisions: true,
  });
  const [panelOpen, setPanelOpen] = useState(true);
  const panelId = useId();
  const select = useRef(props.onSelectGouvernorat);
  const bounds = useRef(props.bounds);
  useEffect(() => {
    select.current = props.onSelectGouvernorat;
    bounds.current = props.bounds;
  });

  const data = useMemo(() => {
    const levels = props.levels ?? {};
    const focus = props.focus ? new Set(props.focus) : null;
    const gouvernorats = collection(
      (props.boundaries?.features ?? []).map((f) => {
        const code = Number(f.properties?.code);
        return feature(f.geometry, {
          code,
          level: levels[code] ?? 0,
          dim: focus ? !focus.has(code) : false,
        });
      }),
    );
    const areas = (items: { id: string; area: Area | null }[], extra: (id: string) => Record<string, unknown>) =>
      collection(items.filter((i) => i.area).map((i) => feature(i.area as Geometry, { id: i.id, ...extra(i.id) })));
    const axisLevel = new Map((props.axisAreas ?? []).map((a) => [a.id, a.level]));
    return {
      gouvernorats,
      axes: areas(props.axisAreas ?? [], (id) => ({ level: axisLevel.get(id) ?? 1 })),
      incidents: collection(
        (props.incidents ?? [])
          .filter((i) => i.lat !== null && i.lon !== null)
          .map((i) =>
            feature(
              { type: "Point", coordinates: [i.lon as number, i.lat as number] },
              { id: i.id, band: (i.severity ?? 0) >= 4 ? 2 : (i.severity ?? 0) >= 3 ? 1 : 0, open: i.status === "open" },
            ),
          ),
      ),
      shelters: collection(
        (props.shelters ?? [])
          .filter((s) => s.lat !== null && s.lon !== null)
          .map((s) => feature({ type: "Point", coordinates: [s.lon as number, s.lat as number] }, { id: s.id })),
      ),
      evacuations: areas(props.evacuations ?? [], () => ({})),
      decisions: areas(props.decisionAreas ?? [], () => ({})),
    };
  }, [props.boundaries, props.levels, props.focus, props.axisAreas, props.incidents, props.shelters, props.evacuations, props.decisionAreas]);

  // Create the map once per theme (the base style and the colours follow the theme).
  useEffect(() => {
    if (!container.current) return;
    let instance: MlMap;
    try {
      instance = new maplibregl.Map({
        container: container.current,
        style: baseStyle(props.styleUrl, dark),
        bounds: box(bounds.current),
        fitBoundsOptions: { padding: framePadding(container.current, props.framed) },
        pitch: tilted ? 45 : 0,
        maxPitch: 70,
        attributionControl: { compact: true },
      });
    } catch {
      // No WebGL (old browser, tests): the lists beside the map carry every value.
      queueMicrotask(() => setFailed(true));
      return;
    }
    map.current = instance;
    const c = palette(dark);
    const levelColour: unknown[] = ["match", ["get", "level"], 1, c.level[1], 2, c.level[2], 3, c.level[3], 4, c.level[4], c.land];
    instance.on("load", () => {
      const empty = collection([]);
      for (const key of LAYER_KEYS) instance.addSource(key, { type: "geojson", data: empty });
      instance.addLayer({
        id: "g-fill",
        type: "fill",
        source: "gouvernorats",
        paint: {
          "fill-color": ["case", ["get", "dim"], c.dim, ["==", ["get", "level"], 0], c.land, levelColour] as never,
          "fill-opacity": ["case", ["==", ["get", "level"], 0], 0.55, 0.42] as never,
        },
      });
      instance.addLayer({
        id: "g-extrude",
        type: "fill-extrusion",
        source: "gouvernorats",
        filter: [">", ["get", "level"], 0],
        paint: {
          "fill-extrusion-color": levelColour as never,
          "fill-extrusion-height": ["*", ["get", "level"], 9000] as never,
          "fill-extrusion-opacity": 0.55,
        },
      });
      instance.addLayer({
        id: "g-line",
        type: "line",
        source: "gouvernorats",
        paint: { "line-color": c.border, "line-width": 1, "line-opacity": 0.8 },
      });
      instance.addLayer({
        id: "evac-fill",
        type: "fill",
        source: "evacuations",
        paint: { "fill-color": c.evac, "fill-opacity": 0.22 },
      });
      instance.addLayer({
        id: "evac-line",
        type: "line",
        source: "evacuations",
        paint: { "line-color": c.evac, "line-width": 2, "line-dasharray": [2, 1] },
      });
      instance.addLayer({
        id: "axis-fill",
        type: "fill",
        source: "axes",
        paint: { "fill-color": levelColour as never, "fill-opacity": 0.14 },
      });
      instance.addLayer({
        id: "axis-glow",
        type: "line",
        source: "axes",
        paint: { "line-color": levelColour as never, "line-width": 10, "line-blur": 8, "line-opacity": dark ? 0.7 : 0.35 },
      });
      instance.addLayer({
        id: "axis-line",
        type: "line",
        source: "axes",
        paint: { "line-color": levelColour as never, "line-width": 2 },
      });
      instance.addLayer({
        id: "dec-line",
        type: "line",
        source: "decisions",
        paint: { "line-color": c.decision, "line-width": 2.5, "line-dasharray": [3, 2] },
      });
      const band: unknown[] = ["match", ["get", "band"], 2, c.severe, 1, c.high, c.normal];
      instance.addLayer({
        id: "inc-halo",
        type: "circle",
        source: "incidents",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 9, 12, 22] as never,
          "circle-color": band as never,
          "circle-opacity": dark ? 0.35 : 0.25,
          "circle-blur": 0.9,
        },
      });
      instance.addLayer({
        id: "inc-core",
        type: "circle",
        source: "incidents",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 3.5, 12, 7] as never,
          "circle-color": band as never,
          "circle-stroke-color": dark ? "#0e1426" : "#ffffff",
          "circle-stroke-width": 1.5,
        },
      });
      instance.addLayer({
        id: "shelter-core",
        type: "circle",
        source: "shelters",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 4, 12, 8] as never,
          "circle-color": c.shelter,
          "circle-stroke-color": dark ? "#e8ecf5" : "#ffffff",
          "circle-stroke-width": 2,
        },
      });
      instance.on("click", "g-fill", (e) => {
        const code = Number(e.features?.[0]?.properties.code);
        if (code && select.current) select.current(code);
      });
      instance.on("mouseenter", "g-fill", () => {
        if (select.current) instance.getCanvas().style.cursor = "pointer";
      });
      instance.on("mouseleave", "g-fill", () => {
        instance.getCanvas().style.cursor = "";
      });
      setReady(true);
    });
    instance.on("error", () => undefined);
    return () => {
      setReady(false);
      for (const m of markers.current) m.remove();
      markers.current = [];
      instance.remove();
      map.current = null;
    };
    // The map is rebuilt only when the theme or the base style changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dark, props.styleUrl]);

  // Data.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    for (const key of LAYER_KEYS) void m.getSource<GeoJSONSource>(key)?.setData(data[key]);
  }, [data, ready]);

  // Layer visibility.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    for (const key of LAYER_KEYS)
      for (const id of LAYER_IDS[key])
        if (m.getLayer(id)) m.setLayoutProperty(id, "visibility", visible[key] ? "visible" : "none");
    if (m.getLayer("g-extrude")) m.setLayoutProperty("g-extrude", "visibility", visible.gouvernorats && tilted ? "visible" : "none");
  }, [visible, ready, tilted]);

  // Gouvernorat names (HTML labels: the map needs no font server, and the names follow the page direction).
  useEffect(() => {
    const m = map.current;
    for (const marker of markers.current) marker.remove();
    markers.current = [];
    if (!m || !ready || !props.labels || !props.boundaries) return;
    for (const f of props.boundaries.features) {
      const code = Number(f.properties?.code);
      const name = props.labels[code];
      if (!name) continue;
      const centre = labelPoint(f.geometry);
      if (!centre) continue;
      const el = document.createElement("span");
      el.className = "command-map__label";
      el.textContent = name;
      el.setAttribute("aria-hidden", "true");
      markers.current.push(new maplibregl.Marker({ element: el }).setLngLat(centre).addTo(m));
    }
  }, [ready, props.labels, props.boundaries, i18n.language]);

  // Fit the bounds when they change.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    m.fitBounds(box(props.bounds), { padding: framePadding(container.current, props.framed), duration: 600, pitch: tilted ? 45 : 0 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.bounds.join(","), ready]);

  const toggleTilt = () => {
    const next = !tilted;
    setTilted(next);
    map.current?.easeTo({ pitch: next ? 45 : 0, bearing: next ? -12 : 0, duration: 700 });
  };
  const zoom = (delta: number) => {
    const m = map.current;
    m?.easeTo({ zoom: m.getZoom() + delta, duration: 300 });
  };
  const home = () => map.current?.fitBounds(box(props.bounds), { padding: framePadding(container.current, props.framed), duration: 600, pitch: tilted ? 45 : 0, bearing: 0 });

  return (
    <div className={`command-map ${props.className ?? ""}`}>
      <div ref={container} className="command-map__canvas" role="img" aria-label={props.ariaLabel} />
      {failed && <p className="command-map__fallback">{t("crisis.map.unavailable")}</p>}
      <div className="command-map__controls" role="group" aria-label={t("crisis.map.controls")}>
        <button type="button" className="map-fab" onClick={() => zoom(1)} aria-label={t("crisis.map.zoomIn")}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        </button>
        <button type="button" className="map-fab" onClick={() => zoom(-1)} aria-label={t("crisis.map.zoomOut")}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14" /></svg>
        </button>
        <button type="button" className="map-fab" onClick={home} aria-label={t("crisis.map.home")}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 11 12 4l8 7M6 10v9h12v-9" /></svg>
        </button>
        <button type="button" className="map-fab map-fab--text" onClick={toggleTilt} aria-pressed={tilted}>
          {tilted ? "3D" : "2D"}
          <span className="visually-hidden">{t("crisis.map.tilt")}</span>
        </button>
      </div>
      <div className="command-map__layers">
        <button
          type="button"
          className="layer-toggle layer-toggle--head"
          aria-expanded={panelOpen}
          aria-controls={panelId}
          onClick={() => setPanelOpen((o) => !o)}
        >
          <span>{panelOpen ? t("crisis.map.hideLayers") : t("crisis.map.showLayers")}</span>
          <svg viewBox="0 0 24 24" aria-hidden="true" className="layer-toggle__icon">
            <path d="m12 4 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5" />
          </svg>
        </button>
        <ul id={panelId} hidden={!panelOpen}>
          {LAYER_KEYS.map((key) => (
            <li key={key}>
              <button
                type="button"
                className={`layer-toggle layer-toggle--${key}`}
                aria-pressed={visible[key]}
                onClick={() => setVisible((v) => ({ ...v, [key]: !v[key] }))}
              >
                <span>{t(`crisis.map.layer.${key}`)}</span>
                <span className="layer-toggle__swatch" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      </div>
      <ul className="command-map__legend" aria-label={t("crisis.map.legend")}>
        {[1, 2, 3, 4].map((level) => (
          <li key={level}>
            <span className={`legend-dot legend-dot--l${level}`} aria-hidden="true" />
            {t(`crisis.level.${level}`)}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A point inside the largest ring's bounding box centre (good enough for labels of the 24 gouvernorats). */
function labelPoint(geometry: Geometry): [number, number] | null {
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.type === "MultiPolygon" ? geometry.coordinates : [];
  let best: number[][] | null = null;
  let bestSize = -1;
  for (const polygon of polygons) {
    const ring = polygon[0];
    if (!ring) continue;
    if (ring.length > bestSize) {
      bestSize = ring.length;
      best = ring;
    }
  }
  if (!best) return null;
  let sx = 0;
  let sy = 0;
  for (const [x = 0, y = 0] of best) {
    sx += x;
    sy += y;
  }
  return [sx / best.length, sy / best.length];
}
