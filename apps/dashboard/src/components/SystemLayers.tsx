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
import { fieldMapKeys } from "../lib/fieldMap";
import { verdictTone } from "../lib/inspectionsApi";
import { useFormat } from "../lib/hooks";
import { LAYER_ICON_PATHS } from "../lib/layers";
import { POI_ICON_PATHS } from "../lib/poiIcons";
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
  "inspections",
  "vehicles",
  "par",
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

// ---------------------------------------------------------------- the field layers (Yamen 2026-11-13)

/** A layer and what it could not place (no position known yet), for the note beside its switch. */
export interface FieldLayer extends SystemLayer {
  unplaced: number;
  count: number;
}

const TONE_COLOURS = { green: "#00806A", amber: "#F08C00", red: "#D7141A", slate: "#5B6B7F" } as const;
// A clipboard with a tick: a place of the periodic inspections.
const INSPECTION_ICON = "M9 2h6v2h3a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3V2zm1 2v2h4V4h-4zm5.3 6.3L11 14.6l-2.3-2.3-1.4 1.4 3.7 3.7 5.7-5.7-1.4-1.4z";
// Three helmets: a team inside a danger zone.
const PAR_ICON = "M12 3a5 5 0 0 0-5 5v1h10V8a5 5 0 0 0-5-5zM5 10h14v2H5v-2zm-3 4a3 3 0 0 1 6 0v1H2v-1zm14 0a3 3 0 0 1 6 0v1h-6v-1zM8 17h8v4H8v-4z";
/** A vehicle whose phone has not given a position for this long is drawn grey: its place may be out of date. */
export const VEHICLE_STALE_MS = 30 * 60_000;
const VEHICLE_COLOURS = { engaged: "#F08C00", free: "#1976D2", stale: "#5B6B7F" } as const;
const PAR_COLOURS: Readonly<Record<string, string>> = {
  ok: "#00806A",
  soon: "#F5B400",
  late: "#F08C00",
  alarm: "#D7141A",
  missing: "#D7141A",
  paused: "#5B6B7F",
};

/** The places of the periodic inspections, coloured by the verdict of their last report (inspector general). */
export function useInspectionSitesLayer(enabled: boolean): FieldLayer {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const q = useQuery({
    queryKey: fieldMapKeys.inspections,
    queryFn: ({ signal }) => api.fieldInspectionSites(signal),
    enabled,
    staleTime: 5 * 60_000,
  });
  const pois = useMemo<MapPoi[]>(() => {
    if (!enabled) return [];
    return (q.data?.items ?? []).map((p) => ({
      id: `inspection-${p.key}`,
      lon: p.location.lon,
      lat: p.location.lat,
      kind: "place" as const,
      title: p.name,
      subtitle: [
        p.target === "room" ? t(`inspections.room.${p.room ?? "central"}`) : t(`inspections.unitKind.${p.unit_kind ?? "other"}`),
        p.last_on
          ? t("mapLayers.inspections.last", {
              date: fmt.date(p.last_on),
              verdict: p.last_verdict ?? "—",
              score: p.last_score === null ? "—" : `${fmt.number(p.last_score)}%`,
            })
          : t("mapLayers.inspections.never"),
        p.next_on ? t("mapLayers.inspections.next", { date: fmt.date(p.next_on) }) : null,
      ]
        .filter(Boolean)
        .join(" · "),
      iconPath: INSPECTION_ICON,
      colour: TONE_COLOURS[verdictTone(p.last_verdict)],
      href: p.last_inspection_id ? `/inspections/records/${encodeURIComponent(p.last_inspection_id)}` : "/inspections",
    }));
  }, [enabled, q.data, t, fmt]);
  return {
    pois,
    polygons: EMPTY,
    hexes: EMPTY,
    error: enabled ? q.error : null,
    refetch: () => void q.refetch(),
    unplaced: enabled ? (q.data?.unplaced ?? 0) : 0,
    count: pois.length,
  };
}

/**
 * The last known position of each vehicle (the leader's phone during a mission): engaged orange, free blue, grey when
 * the position is older than 30 minutes. The popup opens the vehicle's intervention, or the resources screen, for whom
 * may open them.
 */
export function useVehiclesLayer(
  enabled: boolean,
  opens: { incidents: boolean; resources: boolean },
): FieldLayer & { ids: ReadonlySet<string> } {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const q = useQuery({
    queryKey: fieldMapKeys.vehicles,
    queryFn: ({ signal }) => api.fieldVehicles(signal),
    enabled,
    refetchInterval: 30_000,
  });
  const pois = useMemo<MapPoi[]>(() => {
    if (!enabled) return [];
    // The age of a position is read when the answer arrives (every 30 seconds).
    const now = q.dataUpdatedAt;
    return (q.data?.items ?? []).map((v) => {
      const stale = v.at === null || now - new Date(v.at).getTime() > VEHICLE_STALE_MS;
      const href =
        v.incident_id && opens.incidents
          ? `/incidents/${encodeURIComponent(v.incident_id)}`
          : opens.resources
            ? "/resources"
            : undefined;
      return {
        id: `vehicle-${v.id}`,
        lon: v.location.lon,
        lat: v.location.lat,
        kind: "place" as const,
        title: `${v.label} · ${t(`resources.kind.${v.kind}`, { defaultValue: v.kind })}`,
        subtitle: [
          t(`resources.status.${v.status}`, { defaultValue: v.status }),
          v.unit_name,
          v.at ? t("mapLayers.vehicles.at", { time: fmt.dateTime(v.at) }) : t("mapLayers.vehicles.noFix"),
        ].join(" · "),
        iconPath: POI_ICON_PATHS[v.incident_id ? "resource_busy" : "resource"],
        colour: stale ? VEHICLE_COLOURS.stale : v.incident_id ? VEHICLE_COLOURS.engaged : VEHICLE_COLOURS.free,
        ...(href ? { href } : {}),
      };
    });
  }, [enabled, q.data, q.dataUpdatedAt, opens.incidents, opens.resources, t, fmt]);
  // The vehicles drawn here: the units and resources layer leaves them out (one vehicle, one mark on the map).
  const ids = useMemo(() => new Set(enabled ? (q.data?.items ?? []).map((v) => v.id) : []), [enabled, q.data]);
  return {
    ids,
    pois,
    polygons: EMPTY,
    hexes: EMPTY,
    error: enabled ? q.error : null,
    refetch: () => void q.refetch(),
    unplaced: enabled ? (q.data?.unplaced ?? 0) : 0,
    count: pois.length,
  };
}

/** The teams inside a danger zone (PAR), at their vehicle's last position, coloured by the state of their check. */
export function useParLayer(enabled: boolean, canOpenPar: boolean): FieldLayer {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const q = useQuery({
    queryKey: fieldMapKeys.par,
    queryFn: ({ signal }) => api.fieldParTeams(signal),
    enabled,
    refetchInterval: 30_000,
  });
  const items = useMemo(() => (enabled ? (q.data?.items ?? []) : []), [enabled, q.data]);
  const pois = useMemo<MapPoi[]>(
    () =>
      items.flatMap((team) =>
        team.location
          ? [
              {
                id: `par-${team.id}`,
                lon: team.location.lon,
                lat: team.location.lat,
                kind: "place" as const,
                title: `${team.label} · ${t(`par.zone.${team.zone}`, { defaultValue: team.zone })}`,
                subtitle: [
                  t(`par.status.${team.status}`, { defaultValue: team.status }),
                  t("mapLayers.par.members", { n: fmt.number(team.members) }),
                  team.leader_name,
                  t("mapLayers.par.confirmed", { time: fmt.dateTime(team.last_confirmed_at) }),
                  team.location_source === "incident" ? t("mapLayers.par.atIncident") : null,
                ]
                  .filter(Boolean)
                  .join(" · "),
                iconPath: PAR_ICON,
                colour: PAR_COLOURS[team.status] ?? PAR_COLOURS.paused,
                ...(canOpenPar ? { href: "/par" } : {}),
              },
            ]
          : [],
      ),
    [items, canOpenPar, t, fmt],
  );
  return {
    pois,
    polygons: EMPTY,
    hexes: EMPTY,
    error: enabled ? q.error : null,
    refetch: () => void q.refetch(),
    unplaced: items.length - pois.length,
    count: pois.length,
  };
}

/** The colours of each field layer, for its legend under the switch. */
export function fieldLegend(layer: "inspections" | "vehicles" | "par"): [string, string][] {
  if (layer === "inspections") {
    return [
      [TONE_COLOURS.green, "mapLayers.inspections.legendGood"],
      [TONE_COLOURS.amber, "mapLayers.inspections.legendReserved"],
      [TONE_COLOURS.red, "mapLayers.inspections.legendBad"],
      [TONE_COLOURS.slate, "mapLayers.inspections.legendNone"],
    ];
  }
  if (layer === "vehicles") {
    return [
      [VEHICLE_COLOURS.engaged, "mapLayers.vehicles.legendEngaged"],
      [VEHICLE_COLOURS.free, "mapLayers.vehicles.legendFree"],
      [VEHICLE_COLOURS.stale, "mapLayers.vehicles.legendStale"],
    ];
  }
  return [
    [PAR_COLOURS.ok ?? "", "mapLayers.par.legendOk"],
    [PAR_COLOURS.late ?? "", "mapLayers.par.legendLate"],
    [PAR_COLOURS.alarm ?? "", "mapLayers.par.legendAlarm"],
    [PAR_COLOURS.paused ?? "", "mapLayers.par.legendPaused"],
  ];
}

/** Under a field layer's switch: how many are drawn, how many have no position yet, and the legend. */
export function FieldLayerNote({ layer, kind }: { layer: FieldLayer; kind: "inspections" | "vehicles" | "par" }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <div className="field-layer-note">
      <span className="muted" role="status" aria-live="polite">
        {t(`mapLayers.${kind}.count`, { n: fmt.number(layer.count) })}
        {layer.unplaced > 0 ? ` · ${t("mapLayers.unplaced", { n: fmt.number(layer.unplaced) })}` : ""}
      </span>
      <ul className="map-legend">
        {fieldLegend(kind).map(([colour, key]) => (
          <li key={key}>
            <span className="fleet-map-swatch" style={{ background: colour }} aria-hidden="true" />
            <span>{t(key)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
