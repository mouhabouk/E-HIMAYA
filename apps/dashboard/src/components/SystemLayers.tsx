// The data the other screens already draw on their own maps, as optional layers of the interactive map (Yamen,
// 2026-11-13, docs/phase-ml/design-ml.md): integration first, no duplication. Each layer reads the very request its
// source screen reads, with the same permissions and the same scope by gouvernorat (the server's row level security),
// and links back to that screen. Nothing is copied or entered twice: a change made at the source shows here.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { hexBreaks, hexClass, hexColour } from "../lib/analytics";
import { coastalKeys } from "../lib/coastalApi";
import { levelKey, RISK_COLOURS } from "../lib/coastal";
import { crisisKeys, type Area } from "../lib/crisis";
import { useFormat } from "../lib/hooks";
import { LAYER_ICON_PATHS } from "../lib/layers";
import { p8Keys } from "../lib/phase8Api";
import { streamKeys } from "../lib/streamsApi";
import type { MapHex, MapPoi, MapPolygon } from "./MapView";

/** What a system layer adds to the map, and its error to show beside the panel. */
export interface SystemLayer {
  pois: MapPoi[];
  polygons: MapPolygon[];
  hexes: MapHex[];
  error: unknown;
  refetch: () => void;
}

const EMPTY: never[] = [];

/** The layers of the interactive map that carry a link back from a source screen: `/map?layers=<id>`. */
export const MAP_LAYER_IDS = [
  "hotspots",
  "incidents",
  "alerts",
  "aw",
  "coastal",
  "crisis",
  "exposure",
  "resources",
  "volunteers",
  "sensors",
  "towers",
  "drones",
  "streams",
  "weather",
  "orgs",
] as const;
export type MapLayerId = (typeof MAP_LAYER_IDS)[number];

/** The layers asked for in the address (`/map?layers=aw,coastal`), read once when the map opens. */
export function layersFromUrl(search: string): ReadonlySet<string> {
  const raw = new URLSearchParams(search).get("layers") ?? "";
  return new Set(raw.split(",").map((s) => s.trim()).filter(Boolean));
}

// Crisis levels 1 to 4 (design system tones sky, amber, orange, red), as the command map paints them.
const LEVEL_COLOURS: Readonly<Record<number, string>> = { 1: "#1976D2", 2: "#F5B400", 3: "#F08C00", 4: "#D7141A" };
const EVACUATION_COLOUR = "#7838A0";
const SHELTER_COLOUR = "#00806A";
// Open interventions by their highest priority (0..100): high red, medium orange, low blue.
const INCIDENT_COLOURS = { high: "#D7141A", medium: "#F08C00", low: "#1976D2" } as const;
const HOTSPOT_DAYS = 7;
const HOTSPOT_KM = 1;

function ringsOf(area: Area | null): [number, number][][][] {
  if (!area) return [];
  if (area.type === "Polygon") return [area.coordinates as [number, number][][]];
  return area.coordinates as [number, number][][][];
}

function priorityBand(severity: number | null): keyof typeof INCIDENT_COLOURS {
  if (severity !== null && severity >= 70) return "high";
  if (severity !== null && severity >= 40) return "medium";
  return "low";
}

/** Hotspots of the last 7 days in 1 km cells: the request of the operations room (same cache). */
export function useHotspotsLayer(enabled: boolean): SystemLayer {
  const { api } = useServices();
  const [window7] = useState(() => {
    const to = new Date();
    return { from: new Date(to.getTime() - HOTSPOT_DAYS * 86_400_000).toISOString(), to: to.toISOString() };
  });
  const q = useQuery({
    queryKey: p8Keys.hotspots(window7, HOTSPOT_KM),
    queryFn: ({ signal }) => api.analyticsHotspots(window7, HOTSPOT_KM, signal),
    enabled,
    staleTime: 5 * 60_000,
  });
  const hexes = useMemo<MapHex[]>(() => {
    if (!enabled) return [];
    const features = q.data?.features ?? [];
    const breaks = hexBreaks(features.map((f) => f.properties.count));
    return features
      .filter((f) => f.properties.count > 0)
      .map((f, i) => ({
        id: `hot-${f.properties.id ?? i}`,
        coordinates: f.geometry.coordinates as [number, number][][],
        colour: hexColour(hexClass(f.properties.count, breaks)),
        count: f.properties.count,
      }));
  }, [enabled, q.data]);
  return { pois: EMPTY, polygons: EMPTY, hexes, error: enabled ? q.error : null, refetch: () => void q.refetch() };
}

/** Open interventions at their centre, coloured by priority; the popup opens the intervention's file. */
export function useIncidentsLayer(enabled: boolean): SystemLayer {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const q = useQuery({
    queryKey: ["map-layer", "incidents", "open"],
    queryFn: ({ signal }) => api.incidents({ status: "open", limit: 200, signal }),
    enabled,
    refetchInterval: 60_000,
  });
  const pois = useMemo<MapPoi[]>(() => {
    if (!enabled) return [];
    return (q.data?.items ?? []).flatMap((i) =>
      i.centroid
        ? [
            {
              id: `incident-${i.id}`,
              lon: i.centroid.lon,
              lat: i.centroid.lat,
              kind: "place" as const,
              title: i.title || t(`category.${i.category}`),
              subtitle: [
                t(`category.${i.category}`),
                t("mapLayers.incidents.reports", { n: fmt.number(i.report_count) }),
                fmt.dateTime(i.opened_at),
              ].join(" · "),
              iconPath: LAYER_ICON_PATHS.civil_protection,
              colour: INCIDENT_COLOURS[priorityBand(i.severity)],
              href: `/incidents/${encodeURIComponent(i.id)}`,
            },
          ]
        : [],
    );
  }, [enabled, q.data, t, fmt]);
  return { pois, polygons: EMPTY, hexes: EMPTY, error: enabled ? q.error : null, refetch: () => void q.refetch() };
}

/** Beaches with their flag of the day: the request of the coastal safety screen with its default filters. */
export function useCoastalLayer(enabled: boolean): SystemLayer {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const q = useQuery({
    queryKey: coastalKeys.overview({}),
    queryFn: ({ signal }) => api.coastalOverview({}, signal),
    enabled,
  });
  const pois = useMemo<MapPoi[]>(() => {
    if (!enabled) return [];
    const sim = q.data?.simulated ? " [SIM]" : "";
    return (q.data?.beaches ?? []).map((b) => ({
      id: `beach-${b.id}`,
      lon: b.lon,
      lat: b.lat,
      kind: "place" as const,
      title: `${b.name}${sim}`,
      subtitle: [
        t(`coastal.level.${levelKey(b.level)}`),
        b.score === null ? null : t("coastal.score", { score: fmt.number(b.score) }),
      ]
        .filter(Boolean)
        .join(" · "),
      iconPath: LAYER_ICON_PATHS.water,
      colour: RISK_COLOURS[levelKey(b.level)],
      href: "/coastal",
    }));
  }, [enabled, q.data, t, fmt]);
  return { pois, polygons: EMPTY, hexes: EMPTY, error: enabled ? q.error : null, refetch: () => void q.refetch() };
}

/**
 * The open crisis axes: their areas coloured by level, their shelters and their evacuation zones, read from the
 * disasters view (the same two requests). The interventions of the axes are in the interventions layer.
 */
export function useCrisisLayer(enabled: boolean): SystemLayer {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const axes = useQuery({
    queryKey: crisisKeys.axes("open"),
    queryFn: ({ signal }) => api.crisisAxes("open", signal),
    enabled,
    refetchInterval: 60_000,
  });
  const ids = useMemo(() => (axes.data ?? []).map((a) => a.id).sort(), [axes.data]);
  const map = useQuery({
    queryKey: crisisKeys.disasterMap(ids),
    queryFn: ({ signal }) => api.disasterMap(ids, signal),
    enabled: enabled && ids.length > 0,
    refetchInterval: 60_000,
  });
  const data = enabled && ids.length > 0 ? map.data : undefined;
  const polygons = useMemo<MapPolygon[]>(() => {
    if (!data) return [];
    const areas = data.areas.flatMap((a) =>
      ringsOf(a.area).map((coordinates, i) => ({
        id: `axis-${a.id}-${i}`,
        coordinates,
        tone: "low" as const,
        colour: LEVEL_COLOURS[a.level] ?? LEVEL_COLOURS[1],
        outline: "dashed" as const,
      })),
    );
    const evacuations = data.evacuations.flatMap((e) =>
      ringsOf(e.area).map((coordinates, i) => ({
        id: `evacuation-${e.id}-${i}`,
        coordinates,
        tone: "low" as const,
        colour: EVACUATION_COLOUR,
        outline: "solid" as const,
      })),
    );
    return [...areas, ...evacuations];
  }, [data]);
  const pois = useMemo<MapPoi[]>(() => {
    if (!data) return [];
    return data.shelters.flatMap((s) =>
      s.lat !== null && s.lon !== null
        ? [
            {
              id: `shelter-${s.id}`,
              lon: s.lon,
              lat: s.lat,
              kind: "place" as const,
              title: s.name,
              subtitle: t("mapLayers.crisis.shelter", { occupants: fmt.number(s.occupants), capacity: fmt.number(s.capacity) }),
              iconPath: LAYER_ICON_PATHS.shelter,
              colour: SHELTER_COLOUR,
              href: `/axes/${encodeURIComponent(s.axis_id)}`,
            },
          ]
        : [],
    );
  }, [data, t, fmt]);
  const error = enabled ? (axes.error ?? map.error) : null;
  return {
    pois,
    polygons,
    hexes: EMPTY,
    error,
    refetch: () => {
      void axes.refetch();
      void map.refetch();
    },
  };
}

/** Live streams at their last position (citizens, crews, cameras, drones): the request of the streams screen. */
export function useStreamsLayer(enabled: boolean): SystemLayer {
  const { t } = useTranslation();
  const { api } = useServices();
  const filters = useMemo(() => ({ status: "live" as const, gouvernorat: null }), []);
  const q = useQuery({
    queryKey: streamKeys.list(filters),
    queryFn: ({ signal }) => api.streams(filters, { signal }),
    enabled,
    refetchInterval: 30_000,
  });
  const pois = useMemo<MapPoi[]>(() => {
    if (!enabled) return [];
    return (q.data?.items ?? []).flatMap((s) => {
      if (!s.last_location) return [];
      const alert = Math.max(s.max_fire_confidence ?? 0, s.max_smoke_confidence ?? 0) >= 0.5;
      return [
        {
          id: `stream-${s.id}`,
          lon: s.last_location.lon,
          lat: s.last_location.lat,
          kind: alert ? ("stream_alert" as const) : ("stream" as const),
          title: `${s.label ?? s.tracking_code ?? t(`streams.source.${s.source}`)}${s.simulated ? " [SIM]" : ""}`,
          subtitle: t(`streams.source.${s.news ? "news" : s.source}`),
          href: `/streams/${encodeURIComponent(s.id)}`,
        },
      ];
    });
  }, [enabled, q.data, t]);
  return { pois, polygons: EMPTY, hexes: EMPTY, error: enabled ? q.error : null, refetch: () => void q.refetch() };
}
