// Map of the operations room wall view (map/room): the e-Himaya street map restyled for a dark wall, buildings and
// report hotspots raised in 3D, the reports as glowing points and the units as shields. Loaded lazily with MapLibre.
import type { FeatureCollection, Point, Polygon } from "geojson";
import type { GeoJSONSource, Map as MlMap, MapMouseEvent, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { BBox } from "../lib/filters";
import { maplibregl } from "../lib/maplibre";
import { mapStyle } from "../lib/mapStyle";
import { opsRoomRestyle } from "../lib/opsRoom";

export interface OpsRoomLayers {
  reports: boolean;
  hotspots: boolean;
  units: boolean;
  buildings: boolean;
}

interface Props {
  styleUrl: string | null;
  bounds: BBox;
  ariaLabel: string;
  dir: "rtl" | "ltr";
  threeD: boolean;
  layers: OpsRoomLayers;
  reports: FeatureCollection<Point, { id: string; colour: string; open: number }>;
  hotspots: FeatureCollection<Polygon, { count: number; height: number }>;
  units: FeatureCollection<Point, { name: string }>;
  selected: { lon: number; lat: number } | null;
  onSelect: (id: string) => void;
  /** Bumped by the "back to my area" button. */
  homeKey: number;
}

const PITCH = 55;
const BEARING = -15;

function whenReady(map: MlMap, fn: () => void) {
  if (map.isStyleLoaded()) fn();
  else map.once("idle", fn);
}

function setVisible(map: MlMap, ids: string[], on: boolean) {
  for (const id of ids) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
}

export function OpsRoomMap(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MlMap | null>(null);
  const latest = useRef(props);
  useEffect(() => {
    latest.current = props;
  });
  const ring = useRef<HTMLDivElement | null>(null);
  const ringMarker = useRef<Marker | null>(null);

  useEffect(() => {
    if (!container.current) return;
    const { styleUrl, bounds, dir } = latest.current;
    const map = new maplibregl.Map({
      container: container.current,
      style: mapStyle(styleUrl),
      bounds: [bounds[0], bounds[1], bounds[2], bounds[3]],
      fitBoundsOptions: { padding: 32 },
      pitch: latest.current.threeD ? PITCH : 0,
      bearing: latest.current.threeD ? BEARING : 0,
      maxPitch: 75,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), dir === "rtl" ? "top-left" : "top-right");

    map.on("load", () => {
      // Night colours over the street style (or the raster fallback).
      for (const layer of map.getStyle().layers) {
        const r = opsRoomRestyle(layer);
        if (!r) continue;
        for (const [k, v] of Object.entries(r.paint)) {
          try {
            map.setPaintProperty(layer.id, k as Parameters<MlMap["setPaintProperty"]>[1], v as Parameters<MlMap["setPaintProperty"]>[2]);
          } catch {
            /* a property this layer type does not take */
          }
        }
      }
      const firstSymbol = map.getStyle().layers.find((l) => l.type === "symbol")?.id;
      // Buildings in 3D when the vector tiles carry them (OpenMapTiles `building`, with render heights).
      if (map.getSource("openmaptiles")) {
        map.addLayer(
          {
            id: "ops-buildings",
            type: "fill-extrusion",
            source: "openmaptiles",
            "source-layer": "building",
            minzoom: 13,
            paint: {
              "fill-extrusion-color": "#22305A",
              "fill-extrusion-height": ["coalesce", ["get", "render_height"], 8],
              "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
              "fill-extrusion-opacity": 0.85,
            },
          },
          firstSymbol,
        );
      }
      map.addSource("ops-hex", { type: "geojson", data: latest.current.hotspots });
      map.addLayer({
        id: "ops-hex",
        type: "fill-extrusion",
        source: "ops-hex",
        paint: {
          "fill-extrusion-color": [
            "interpolate",
            ["linear"],
            ["get", "height"],
            0,
            "#2F6FD0",
            600,
            "#4DD0B8",
            1200,
            "#FFC933",
            1800,
            "#FFA733",
            2500,
            "#FF6B6B",
          ],
          "fill-extrusion-height": ["get", "height"],
          "fill-extrusion-opacity": 0.78,
        },
      });
      map.addSource("ops-units", { type: "geojson", data: latest.current.units });
      map.addLayer({
        id: "ops-units-glow",
        type: "circle",
        source: "ops-units",
        paint: { "circle-radius": 12, "circle-color": "#FF6B6B", "circle-blur": 1, "circle-opacity": 0.45 },
      });
      map.addLayer({
        id: "ops-units",
        type: "circle",
        source: "ops-units",
        paint: { "circle-radius": 5, "circle-color": "#2A0F18", "circle-stroke-color": "#FF6B6B", "circle-stroke-width": 2 },
      });
      map.addSource("ops-reports", { type: "geojson", data: latest.current.reports });
      map.addLayer({
        id: "ops-reports-glow",
        type: "circle",
        source: "ops-reports",
        paint: {
          "circle-radius": ["case", ["==", ["get", "open"], 1], 15, 7],
          "circle-color": ["get", "colour"],
          "circle-blur": 1,
          "circle-opacity": ["case", ["==", ["get", "open"], 1], 0.55, 0.15],
          "circle-pitch-alignment": "map",
        },
      });
      map.addLayer({
        id: "ops-reports",
        type: "circle",
        source: "ops-reports",
        paint: {
          "circle-radius": ["case", ["==", ["get", "open"], 1], 4, 2.4],
          "circle-color": ["get", "colour"],
          "circle-stroke-color": "#0B1122",
          "circle-stroke-width": 0.8,
          "circle-opacity": ["case", ["==", ["get", "open"], 1], 1, 0.55],
        },
      });
      applyLayers(map, latest.current.layers, latest.current.threeD);
    });
    map.on("click", "ops-reports", (e: MapMouseEvent & { features?: { properties: Record<string, unknown> }[] }) => {
      const id = e.features?.[0]?.properties.id;
      if (typeof id === "string") latest.current.onSelect(id);
    });
    map.on("mouseenter", "ops-reports", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "ops-reports", () => (map.getCanvas().style.cursor = ""));
    return () => {
      ringMarker.current?.remove();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Data updates (the live reports refresh every 30 s).
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    whenReady(map, () => {
      void map.getSource<GeoJSONSource>("ops-reports")?.setData(props.reports);
      void map.getSource<GeoJSONSource>("ops-hex")?.setData(props.hotspots);
      void map.getSource<GeoJSONSource>("ops-units")?.setData(props.units);
    });
  }, [props.reports, props.hotspots, props.units]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    whenReady(map, () => applyLayers(map, props.layers, props.threeD));
  }, [props.layers, props.threeD]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.easeTo({ pitch: props.threeD ? PITCH : 0, bearing: props.threeD ? BEARING : 0, duration: 700 });
  }, [props.threeD]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || props.homeKey === 0) return;
    const b = latest.current.bounds;
    map.fitBounds([b[0], b[1], b[2], b[3]], { padding: 32, pitch: latest.current.threeD ? PITCH : 0, bearing: latest.current.threeD ? BEARING : 0 });
  }, [props.homeKey]);

  // Pulsing ring around the selected report.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    ringMarker.current?.remove();
    ringMarker.current = null;
    if (!props.selected) return;
    if (!ring.current) {
      ring.current = document.createElement("div");
      ring.current.className = "ops-room__ring";
      ring.current.setAttribute("aria-hidden", "true");
    }
    ringMarker.current = new maplibregl.Marker({ element: ring.current }).setLngLat([props.selected.lon, props.selected.lat]).addTo(map);
  }, [props.selected]);

  return <div ref={container} className="ops-room__map" role="region" aria-label={props.ariaLabel} />;
}

function applyLayers(map: MlMap, layers: OpsRoomLayers, threeD: boolean) {
  setVisible(map, ["ops-reports", "ops-reports-glow"], layers.reports);
  setVisible(map, ["ops-hex"], layers.hotspots && threeD);
  setVisible(map, ["ops-units", "ops-units-glow"], layers.units);
  setVisible(map, ["ops-buildings"], layers.buildings && threeD);
}
