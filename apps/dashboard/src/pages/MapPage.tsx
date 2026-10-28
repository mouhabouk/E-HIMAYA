import { keepPreviousData, useQueries, useQuery, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { Suspense, useCallback, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { FiltersBar } from "../components/FiltersBar";
import { LazyMapView } from "../components/LazyMap";
import { useBasemap } from "../components/BasemapSwitch";
import { useMapDataLayers, type FolderExtra } from "../components/MapDataLayers";
import { useResourceSearchLayer } from "../components/ResourceSearchLayer";
import type { HeatPoint, MapLine, MapMarker, MapPoi, MapPolygon } from "../components/MapView";
import { MapLegend, orgKindLabel } from "../components/OrgBits";
import { useMapWeather, useWeatherGrid, WeatherControls, WeatherPointCard, type WeatherViews } from "../components/WeatherLayer";
import { useAuth } from "../context/auth";
import { useSoftphone } from "../context/softphone";
import { useLiveEvents } from "../context/live";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import type { BBox } from "../lib/filters";
import { useDebounced, useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { mapKey } from "../lib/liveCache";
import { initialBoundsFor } from "../lib/mapStyle";
import { opsKeys } from "../lib/opsApi";
import type { Message } from "../lib/opsTypes";
import { errorMessageKey } from "../lib/api";
import {
  canOpenDrones,
  canOpenSensors,
  canOpenTowers,
  canReadOrgs,
  canReadResources,
  canUseTelephony,
} from "../lib/roles";
import { droneKeys, isFresh, TRACK_MINUTES, type DroneTrack } from "../lib/drones";
import { sensorKeys, type SensorState } from "../lib/sensors";
import { compassOf, recentEvent, towerKeys } from "../lib/towers";
import { useNow } from "../lib/phase9";
import type { DialBody } from "../lib/telephonyTypes";
import { queryKeys } from "../lib/staffApi";
import type { Page, StaffReport } from "../lib/types";
import { useEffectiveFilters } from "./useEffectiveFilters";
import { localized } from "../lib/localized";
import { PageTitle } from "../components/PageTitle";

const PAGE_SIZE = 200; // server maximum is 500
const MAX_PAGES = 2;
const ORG_LAYER_KEY = "ehimaya.mapOrgLayer";
const RESOURCE_LAYER_KEY = "ehimaya.mapResourceLayer";
const VOLUNTEER_LAYER_KEY = "ehimaya.mapVolunteerLayer";
const ALERT_LAYER_KEY = "ehimaya.mapAlertLayer";
const WEATHER_LAYER_KEY = "ehimaya.mapWeatherLayer";
const SENSOR_LAYER_KEY = "ehimaya.mapSensorLayer";
const TOWER_LAYER_KEY = "ehimaya.mapTowerLayer";
// The wedge of a tower's view: MapLibre paints plain colours, the same in both themes.
const TOWER_VIEW = "#ea580c";
const TOWER_VIEW_ALERT = "#dc2626";
const DRONE_LAYER_KEY = "ehimaya.mapDroneLayer";
// Drones (L5b): the camera's view and the path in purple, work areas in green, no-fly zones in red.
const DRONE_VIEW = "#7c3aed";
const DRONE_WORK = "#16a34a";
const DRONE_NO_FLY = "#dc2626";

const SENSOR_POI: Record<SensorState, MapPoi["kind"]> = {
  normal: "sensor",
  watch: "sensor_watch",
  alarm: "sensor_alarm",
  silent: "sensor_silent",
  disabled: "sensor_silent",
};
const WEATHER_VIEWS_KEY = "ehimaya.mapWeatherViews";

function storedViews(): WeatherViews {
  try {
    const raw = sessionStorage.getItem(WEATHER_VIEWS_KEY);
    if (raw) {
      const v = JSON.parse(raw) as Partial<WeatherViews>;
      return { fire: v.fire !== false, wind: v.wind !== false, rain: v.rain !== false };
    }
  } catch {
    /* ignore */
  }
  return { fire: true, wind: true, rain: true };
}

function storedLayer(key: string): boolean {
  try {
    return sessionStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function storeLayer(key: string, on: boolean): void {
  try {
    sessionStorage.setItem(key, on ? "1" : "0");
  } catch {
    /* ignore */
  }
}

/** A map layer switch remembered for the tab (like the institutions layer). */
function useLayer(key: string): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(() => storedLayer(key));
  return [
    on,
    (value: boolean) => {
      setOn(value);
      storeLayer(key, value);
    },
  ];
}

function LayerToggle({ checked, onChange, label }: { checked: boolean; onChange: (on: boolean) => void; label: string }) {
  const id = useId();
  return (
    <label htmlFor={id} className="checkbox">
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

/** The paths of the flying drones (their last 30 minutes), from the track queries. */
function droneLines(results: readonly { data?: DroneTrack }[]): MapLine[] {
  return results.flatMap(({ data }) =>
    data && data.items.length > 1
      ? [
          {
            id: `drone-track-${data.drone_id}`,
            coordinates: data.items.map((p) => [p.lon, p.lat] as [number, number]),
            colour: DRONE_VIEW,
          },
        ]
      : [],
  );
}

function alertPolygons(alerts: readonly Message[]): MapPolygon[] {
  return alerts.flatMap((a) =>
    a.area.polygon ? [{ id: a.id, coordinates: a.area.polygon.coordinates, tone: a.severity ?? "low" }] : [],
  );
}

/** FR-C-02 (map): reports in the visible area, coloured by status, updated live. */
export function MapPage() {
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const navigate = useNavigate();
  const { filters, national } = useEffectiveFilters();
  const [rawBBox, setRawBBox] = useState<BBox | null>(null);
  const bbox = useDebounced(rawBBox, 400);
  const [fresh, setFresh] = useState<ReadonlySet<string>>(new Set());
  const [initialBounds] = useState(() => initialBoundsFor(user?.identity.gouvernoratCode ?? null));
  const layerToggleId = useId();
  const orgLayerAllowed = canReadOrgs(user?.identity.roles ?? []);
  const [orgLayer, setOrgLayer] = useLayer(ORG_LAYER_KEY);
  const showOrgs = orgLayerAllowed && orgLayer;
  const resourceLayerAllowed = canReadResources(user?.identity.roles ?? []);
  const [resourceLayer, setResourceLayer] = useLayer(RESOURCE_LAYER_KEY);
  const showResources = resourceLayerAllowed && resourceLayer;
  const [showVolunteers, setVolunteerLayer] = useLayer(VOLUNTEER_LAYER_KEY);
  const [showAlerts, setAlertLayer] = useLayer(ALERT_LAYER_KEY);
  const sensorLayerAllowed = canOpenSensors(user?.identity.roles ?? []);
  const [sensorLayer, setSensorLayer] = useLayer(SENSOR_LAYER_KEY);
  const showSensors = sensorLayerAllowed && sensorLayer;
  const towerLayerAllowed = canOpenTowers(user?.identity.roles ?? []);
  const [towerLayer, setTowerLayer] = useLayer(TOWER_LAYER_KEY);
  const showTowers = towerLayerAllowed && towerLayer;
  const droneLayerAllowed = canOpenDrones(user?.identity.roles ?? []);
  const [droneLayer, setDroneLayer] = useLayer(DRONE_LAYER_KEY);
  const showDrones = droneLayerAllowed && droneLayer;
  // A minute is fine enough for "a fire or smoke in the last hour".
  const clock = useNow(60_000);
  const qc = useQueryClient();
  const gouvernorats = useGouvernorats();
  const basemap = useBasemap();

  // Outbound call from a map point (phase 7 §4, FR-C-10): reporter, volunteer or unit, through the softphone.
  const phone = useSoftphone();
  const [callNotice, setCallNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const onCall = useMemo(
    () =>
      phone && canUseTelephony(user?.identity.roles ?? [])
        ? (body: DialBody) => {
            setCallNotice({ ok: true, text: t("phone.dialing") });
            phone.dial(body).then(
              () => setCallNotice({ ok: true, text: t("phone.dialStarted") }),
              (e: unknown) =>
                setCallNotice({
                  ok: false,
                  text:
                    e instanceof Error && e.message === "softphone_not_registered"
                      ? t("errors.softphone_not_registered")
                      : t(errorMessageKey(e)),
                }),
            );
          }
        : undefined,
    [phone, user, t],
  );

  // Weather layer (phase 7 §1, FR-C-08 / FR-C-10): fire danger field, wind arrows, rain level, 48 h slider.
  const [showWeather, setWeatherLayer] = useLayer(WEATHER_LAYER_KEY);
  const [weatherViews, setWeatherViewsState] = useState<WeatherViews>(storedViews);
  const setWeatherViews = (v: WeatherViews) => {
    setWeatherViewsState(v);
    try {
      sessionStorage.setItem(WEATHER_VIEWS_KEY, JSON.stringify(v));
    } catch {
      /* ignore */
    }
  };
  const [weatherHour, setWeatherHour] = useState(0);
  const [weatherPoint, setWeatherPoint] = useState<{ lat: number; lon: number } | null>(null);
  const weatherGrid = useWeatherGrid(showWeather, bbox, weatherHour);
  const mapWeather = useMapWeather(weatherGrid, weatherViews, showWeather);
  const onMapClick = useCallback(
    (lon: number, lat: number) => {
      if (showWeather) setWeatherPoint({ lat, lon });
    },
    [showWeather],
  );
  const onWeatherCentre = () => {
    if (!rawBBox) return;
    setWeatherPoint({ lon: (rawBBox[0] + rawBBox[2]) / 2, lat: (rawBBox[1] + rawBBox[3]) / 2 });
  };
  const weatherPopup = useMemo(
    () =>
      showWeather && weatherPoint
        ? {
            lat: weatherPoint.lat,
            lon: weatherPoint.lon,
            key: `${weatherPoint.lat},${weatherPoint.lon}`,
            node: <WeatherPointCard lat={weatherPoint.lat} lon={weatherPoint.lon} hour={weatherHour} />,
          }
        : null,
    [showWeather, weatherPoint, weatherHour],
  );

  // Operations layers (phase 5, FR-C-06 / FR-C-10): resources and units, ready volunteers, active alerts.
  const resourcesQuery = useQuery({
    queryKey: bbox ? opsKeys.resourcesMap(bbox) : ["resources-map", "pending"],
    enabled: showResources && bbox !== null,
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) => {
      if (!bbox) throw new Error("no bbox");
      return api.resourcesMap(bbox, signal);
    },
  });
  const volunteersQuery = useQuery({
    queryKey: bbox ? opsKeys.volunteersMap(bbox, "") : ["volunteers-map", "pending"],
    enabled: showVolunteers && bbox !== null,
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) => {
      if (!bbox) throw new Error("no bbox");
      return api.volunteersMap(bbox, "", signal);
    },
  });
  const alertsQuery = useQuery({
    queryKey: opsKeys.activeAlerts,
    enabled: showAlerts,
    queryFn: ({ signal }) => api.activeAlerts(signal),
  });

  // Sensors of the local network (L5b, design-l5 §3.1): few points, the room's own; the API keeps the scope.
  const sensorsQuery = useQuery({
    queryKey: sensorKeys.all,
    enabled: showSensors,
    queryFn: ({ signal }) => api.sensors(signal),
  });

  // Watch towers (L5b, design-l5 §3.2): each tower and the wedge of its camera's view.
  const towersQuery = useQuery({
    queryKey: towerKeys.all,
    enabled: showTowers,
    queryFn: ({ signal }) => api.towers(signal),
  });

  // Drones (L5b, design-l5 §3.3, read only): each drone, its camera's view, its path and the zones of the rooms.
  const dronesQuery = useQuery({
    queryKey: droneKeys.list,
    enabled: showDrones,
    queryFn: ({ signal }) => api.drones(signal),
  });
  const zonesQuery = useQuery({
    queryKey: droneKeys.zones,
    enabled: showDrones,
    queryFn: ({ signal }) => api.droneZones(signal),
  });
  const flying = useMemo(
    () => (showDrones ? (dronesQuery.data?.items ?? []).filter((d) => isFresh(d, clock)) : []),
    [showDrones, dronesQuery.data, clock],
  );
  const lines = useQueries({
    queries: flying.map((d) => ({
      queryKey: droneKeys.track(d.id, TRACK_MINUTES),
      queryFn: ({ signal }: { signal: AbortSignal }) => api.droneTrack(d.id, TRACK_MINUTES, signal),
      refetchInterval: 30_000,
    })),
    combine: droneLines,
  });

  // Institutions layer «المؤسسات» (FR-C-10): refetched with the same debounced bbox as the reports.
  const orgsQuery = useQuery({
    queryKey: bbox ? queryKeys.orgsMap(bbox) : ["orgs-map", "pending"],
    enabled: showOrgs && bbox !== null,
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) => {
      if (!bbox) throw new Error("no bbox");
      return api.orgsMap(bbox, signal);
    },
  });

  const query = useQuery({
    queryKey: bbox ? mapKey(filters, bbox) : ["map-reports", "pending"],
    enabled: bbox !== null,
    placeholderData: keepPreviousData,
    queryFn: async ({ signal }): Promise<InfiniteData<Page<StaffReport>, string | null>> => {
      if (!bbox) throw new Error("no bbox");
      const items: StaffReport[] = [];
      let cursor: string | null = null;
      for (let i = 0; i < MAX_PAGES; i += 1) {
        const page: Page<StaffReport> = await api.reports(filters, { cursor, bbox, limit: PAGE_SIZE, signal });
        items.push(...page.items);
        cursor = page.next_cursor;
        if (!cursor) break;
      }
      return { pages: [{ items, next_cursor: cursor }], pageParams: [null] };
    },
  });

  useLiveEvents(
    useCallback((event) => {
      if (event.type === "report.created") setFresh((prev) => new Set(prev).add(event.report.id));
      if (event.type === "sensor.reading") void qc.invalidateQueries({ queryKey: sensorKeys.all });
      if (event.type === "stream.alert") void qc.invalidateQueries({ queryKey: towerKeys.all });
      if (event.type === "drone.telemetry" || event.type === "drone.alert") {
        void qc.invalidateQueries({ queryKey: droneKeys.list });
      }
    }, [qc]),
  );

  const reports = useMemo(() => query.data?.pages.flatMap((p) => p.items) ?? [], [query.data]);
  const truncated = Boolean(query.data?.pages.at(-1)?.next_cursor);

  const markers = useMemo<MapMarker[]>(
    () =>
      reports.map((r) => ({
        id: r.id,
        lon: r.location.lon,
        lat: r.location.lat,
        status: r.status,
        category: r.category,
        title: `${r.tracking_code} · ${t(`category.${r.category}`)}`,
        subtitle: `${t(`status.${r.status}`)} · ${fmt.dateTime(r.received_at)}`,
        highlight: fresh.has(r.id),
      })),
    [reports, fresh, t, fmt],
  );

  const onOpen = useCallback((id: string) => void navigate(`/reports/${encodeURIComponent(id)}`), [navigate]);
  const onOpenPoi = useCallback((href: string) => void navigate(href), [navigate]);

  const orgFeatures = useMemo(() => (showOrgs ? (orgsQuery.data?.features ?? []) : []), [showOrgs, orgsQuery.data]);
  const pois = useMemo<MapPoi[]>(
    () =>
      orgFeatures.map((f) => {
        const p = f.properties;
        const parts = [orgKindLabel(t, p.kind)];
        if (p.capacity !== null) parts.push(t("orgs.layer.capacity", { capacity: fmt.number(p.capacity) }));
        if (p.hazmat_count > 0) parts.push(t("orgs.hazmatBadge", { count: fmt.number(p.hazmat_count) }));
        return {
          id: p.id,
          lon: f.geometry.coordinates[0],
          lat: f.geometry.coordinates[1],
          kind: p.hazmat_count > 0 ? ("org_hazmat" as const) : ("org" as const),
          title: p.name,
          subtitle: parts.join(" · "),
          href: `/orgs/${encodeURIComponent(p.id)}`,
        };
      }),
    [orgFeatures, t, fmt],
  );
  const opsPois = useMemo<MapPoi[]>(() => {
    const out: MapPoi[] = [];
    if (showResources) {
      for (const f of resourcesQuery.data?.features ?? []) {
        const [lon, lat] = f.geometry.coordinates;
        const p = f.properties;
        if (p.layer === "unit") {
          out.push({
            id: `unit-${p.id}`,
            lon,
            lat,
            kind: "unit",
            title: lang === "ar" ? p.name : p.name_fr || p.name,
            subtitle: [t(`resources.units.kind.${p.kind}`), p.phone].filter(Boolean).join(" · "),
            href: "/resources",
            ...(p.phone ? { call: { number: p.phone } } : {}),
          });
        } else {
          out.push({
            id: `resource-${p.id}`,
            lon,
            lat,
            kind: p.status === "assigned" ? "resource_busy" : "resource",
            title: `${p.label} · ${t(`resources.kind.${p.kind}`)}`,
            subtitle: `${t(`resources.status.${p.status}`)} · ${p.unit_name}`,
            href: p.incident_id ? `/incidents/${encodeURIComponent(p.incident_id)}` : "/resources",
          });
        }
      }
    }
    if (showVolunteers) {
      for (const f of volunteersQuery.data?.features ?? []) {
        const p = f.properties;
        out.push({
          id: `volunteer-${p.id}`,
          lon: f.geometry.coordinates[0],
          lat: f.geometry.coordinates[1],
          kind: "volunteer",
          title: p.full_name ?? t("ops.volunteer"),
          subtitle: p.skills.map((sk) => t(`volunteers.skill.${sk}`)).join(t("common.listSeparator")),
          href: `/volunteers/${encodeURIComponent(p.id)}`,
          call: { volunteer_id: p.id },
        });
      }
    }
    if (showSensors) {
      for (const sn of sensorsQuery.data?.items ?? []) {
        const value =
          sn.last_value === null ? t("sensors.map.noReading") : `${fmt.decimal(sn.last_value)} ${t(`sensors.unit.${sn.kind}`)}`;
        out.push({
          id: `sensor-${sn.id}`,
          lon: sn.lon,
          lat: sn.lat,
          kind: SENSOR_POI[sn.state],
          title: `${sn.name}${sn.simulated ? " [SIM]" : ""}`,
          subtitle: [t(`sensors.kind.${sn.kind}`), t(`sensors.state.${sn.state}`), value].join(" · "),
          href: "/sensors",
        });
      }
    }
    if (showTowers) {
      for (const tw of towersQuery.data?.items ?? []) {
        const recent = recentEvent(tw, clock);
        out.push({
          id: `tower-${tw.id}`,
          lon: tw.lon,
          lat: tw.lat,
          kind: recent ? "tower_alert" : "tower",
          title: `${tw.label}${tw.simulated ? " [SIM]" : ""}`,
          subtitle: [
            recent ? t(`towers.label.${recent}`) : null,
            t("towers.view", {
              direction: t(`towers.compass.${compassOf(tw.bearing_deg)}`),
              bearing: fmt.number(tw.bearing_deg),
              fov: fmt.number(tw.fov_deg),
              km: fmt.decimal(tw.range_m / 1000),
            }),
          ]
            .filter(Boolean)
            .join(" · "),
          href: "/towers",
        });
      }
    }
    if (showDrones) {
      for (const d of dronesQuery.data?.items ?? []) {
        if (!d.last) continue;
        out.push({
          id: `drone-${d.id}`,
          lon: d.last.lon,
          lat: d.last.lat,
          kind: d.open_alerts > 0 ? "drone_alert" : "drone",
          title: d.label,
          subtitle: [
            d.open_alerts > 0 ? t("drones.openAlerts", { n: fmt.number(d.open_alerts) }) : null,
            t(isFresh(d, clock) ? "drones.position.fresh" : "drones.position.stale"),
            d.last.alt_m !== null ? t("drones.altitude", { m: fmt.number(Math.round(d.last.alt_m)) }) : null,
            d.last.battery_pct !== null
              ? t("drones.battery", { pct: fmt.number(Math.round(d.last.battery_pct)) })
              : null,
            fmt.dateTime(d.last.at),
          ]
            .filter(Boolean)
            .join(" · "),
          href: "/drones",
        });
      }
    }
    return out;
  }, [
    showResources,
    resourcesQuery.data,
    showVolunteers,
    volunteersQuery.data,
    showSensors,
    sensorsQuery.data,
    showTowers,
    towersQuery.data,
    showDrones,
    dronesQuery.data,
    clock,
    lang,
    t,
    fmt,
  ]);
  // Phase R2: the units and resources of the operations and a resources search sent from the register sit in the
  // «موارد الحماية المدنية» folder of the layer panel, beside the file layers of that folder.
  const resourceSearch = useResourceSearchLayer(bbox);
  const civilProtection = useMemo<FolderExtra[]>(() => {
    const out: FolderExtra[] = [];
    if (resourceSearch.extra) out.push(resourceSearch.extra);
    if (resourceLayerAllowed) {
      out.push({ key: "ops-resources", label: t("ops.map.resourcesToggle"), on: resourceLayer, onChange: setResourceLayer });
    }
    return out;
  }, [resourceSearch.extra, resourceLayerAllowed, resourceLayer, setResourceLayer, t]);
  const folderExtras = useMemo(() => ({ civil_protection: civilProtection }), [civilProtection]);
  // Map data layers loaded from files (phase B1): hospitals, shelters… any number at once.
  const dataLayers = useMapDataLayers(bbox, folderExtras);
  const allPois = useMemo(
    () => [...pois, ...opsPois, ...resourceSearch.pois, ...dataLayers.pois],
    [pois, opsPois, resourceSearch.pois, dataLayers.pois],
  );
  const shapes = useMemo(
    () => ({ ...dataLayers.shapes, features: [...resourceSearch.shapes, ...dataLayers.shapes.features] }),
    [dataLayers.shapes, resourceSearch.shapes],
  );
  const heat = useMemo<HeatPoint[]>(
    () =>
      showVolunteers
        ? (volunteersQuery.data?.features ?? []).map((f) => ({
            lon: f.geometry.coordinates[0],
            lat: f.geometry.coordinates[1],
          }))
        : [],
    [showVolunteers, volunteersQuery.data],
  );
  const alerts = useMemo(() => (showAlerts ? (alertsQuery.data ?? []) : []), [showAlerts, alertsQuery.data]);
  const polygons = useMemo<MapPolygon[]>(() => {
    const wedges: MapPolygon[] = showTowers
      ? (towersQuery.data?.items ?? []).map((tw) => ({
          id: `tower-view-${tw.id}`,
          coordinates: [tw.field_of_view],
          tone: "low",
          colour: recentEvent(tw, clock) ? TOWER_VIEW_ALERT : TOWER_VIEW,
          outline: "solid",
        }))
      : [];
    const zones: MapPolygon[] = showDrones
      ? (zonesQuery.data ?? [])
          .filter((z) => z.active)
          .map((z) => ({
            id: `drone-zone-${z.id}`,
            coordinates: [z.ring],
            tone: "low",
            colour: z.kind === "no_fly" ? DRONE_NO_FLY : DRONE_WORK,
            outline: "dashed",
          }))
      : [];
    const views: MapPolygon[] = flying
      .filter((d) => d.camera_view !== null)
      .map((d) => ({
        id: `drone-view-${d.id}`,
        coordinates: [d.camera_view ?? []],
        tone: "low",
        colour: DRONE_VIEW,
        outline: "solid",
      }));
    return [...alertPolygons(alerts), ...wedges, ...zones, ...views];
  }, [alerts, showTowers, towersQuery.data, clock, showDrones, zonesQuery.data, flying]);

  const legend = useMemo(() => {
    const items: { kind: MapPoi["kind"]; label: string }[] = [];
    if (showOrgs) {
      items.push({ kind: "org", label: t("orgs.layer.org") }, { kind: "org_hazmat", label: t("orgs.layer.hazmat") });
    }
    if (showResources) {
      items.push(
        { kind: "unit", label: t("ops.map.unit") },
        { kind: "resource", label: t("ops.map.resource") },
        { kind: "resource_busy", label: t("ops.map.resourceBusy") },
      );
    }
    if (showVolunteers) items.push({ kind: "volunteer", label: t("ops.map.volunteer") });
    if (showSensors) {
      items.push(
        { kind: "sensor", label: t("sensors.map.normal") },
        { kind: "sensor_watch", label: t("sensors.map.watch") },
        { kind: "sensor_alarm", label: t("sensors.map.alarm") },
        { kind: "sensor_silent", label: t("sensors.map.silent") },
      );
    }
    if (showTowers) {
      items.push({ kind: "tower", label: t("towers.map.tower") }, { kind: "tower_alert", label: t("towers.map.alert") });
    }
    if (showDrones) {
      items.push({ kind: "drone", label: t("drones.map.drone") }, { kind: "drone_alert", label: t("drones.map.alert") });
    }
    return items;
  }, [showOrgs, showResources, showVolunteers, showSensors, showTowers, showDrones, t]);

  return (
    <div className="page page--map">
      <div className="page__head">
        <PageTitle icon="map" tone="teal">{t("map.title")}</PageTitle>
        <p className="muted" role="status" aria-live="polite">
          {query.isFetching ? t("common.loading") : t("map.count", { count: fmt.number(reports.length) })}
          {truncated && ` · ${t("map.truncated")}`}
        </p>
      </div>
      <FiltersBar showGouvernorat={national} />
      <div className="map-layers" role="group" aria-label={t("ops.map.layers")}>
        {orgLayerAllowed && (
          <label htmlFor={layerToggleId} className="checkbox">
            <input
              id={layerToggleId}
              type="checkbox"
              checked={orgLayer}
              onChange={(e) => setOrgLayer(e.target.checked)}
            />
            <span>{t("orgs.layer.toggle")}</span>
          </label>
        )}
        <LayerToggle checked={showVolunteers} onChange={setVolunteerLayer} label={t("ops.map.volunteersToggle")} />
        <LayerToggle checked={showAlerts} onChange={setAlertLayer} label={t("ops.map.alertsToggle")} />
        {sensorLayerAllowed && (
          <LayerToggle checked={sensorLayer} onChange={setSensorLayer} label={t("sensors.map.toggle")} />
        )}
        {towerLayerAllowed && (
          <LayerToggle checked={towerLayer} onChange={setTowerLayer} label={t("towers.map.toggle")} />
        )}
        {droneLayerAllowed && (
          <LayerToggle checked={droneLayer} onChange={setDroneLayer} label={t("drones.map.toggle")} />
        )}
        <LayerToggle
          checked={showWeather}
          onChange={(on) => {
            setWeatherLayer(on);
            if (!on) setWeatherPoint(null);
          }}
          label={t("weather.toggle")}
        />
        {showOrgs && (
          <span className="muted" role="status" aria-live="polite">
            {orgsQuery.isFetching ? t("common.loading") : t("orgs.layer.count", { count: fmt.number(pois.length) })}
          </span>
        )}
        {legend.length > 0 && <MapLegend items={legend} />}
        {basemap.control}
      </div>
      {dataLayers.controls}
      {showWeather && (
        <WeatherControls
          views={weatherViews}
          onViews={setWeatherViews}
          hour={weatherHour}
          onHour={setWeatherHour}
          grid={weatherGrid}
          onCentre={onWeatherCentre}
        />
      )}
      {showAlerts && (
        <section className="card map-alerts" aria-label={t("ops.map.alertsTitle")}>
          {alertsQuery.isError && <ErrorBox error={alertsQuery.error} onRetry={() => void alertsQuery.refetch()} />}
          {alertsQuery.isSuccess && alerts.length === 0 && <p className="muted">{t("ops.map.noAlert")}</p>}
          {alerts.length > 0 && (
            <ul className="alerts-list">
              {alerts.map((a) => (
                <li key={a.id}>
                  <span className={`chip chip--severity-${a.severity ?? "low"}`}>
                    {t(`ops.map.severity.${a.severity ?? "low"}`)}
                  </span>{" "}
                  <strong dir="auto">{localized(a.title, lang)}</strong>
                  <span className="muted">
                    {" · "}
                    {a.area.polygon
                      ? t("ops.map.drawnArea")
                      : a.area.gouvernorat_codes.length === 0
                        ? t("ops.map.national")
                        : a.area.gouvernorat_codes
                            .map((c) => gouvernorats.nameOf(c) ?? String(c))
                            .join(t("common.listSeparator"))}
                    {a.expires_at && ` · ${t("ops.map.until", { time: fmt.dateTime(a.expires_at) })}`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
      {showResources && resourcesQuery.isError && (
        <ErrorBox error={resourcesQuery.error} onRetry={() => void resourcesQuery.refetch()} />
      )}
      {showVolunteers && volunteersQuery.isError && (
        <ErrorBox error={volunteersQuery.error} onRetry={() => void volunteersQuery.refetch()} />
      )}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {showOrgs && orgsQuery.isError && (
        <ErrorBox error={orgsQuery.error} onRetry={() => void orgsQuery.refetch()} />
      )}
      <div role="status" aria-live="polite">
        {callNotice && <p className={`alert ${callNotice.ok ? "alert--info" : "alert--error"}`}>{callNotice.text}</p>}
      </div>
      <Suspense fallback={<Loading />}>
        <LazyMapView
          className="map map--full"
          markers={markers}
          bounds={initialBounds}
          ariaLabel={t("map.label")}
          openLabel={t("map.openDetail")}
          onOpen={onOpen}
          onBoundsChange={setRawBBox}
          styleUrl={mapStyleUrl}
          dir={directionOf(lang)}
          pois={allPois}
          poiOpenLabel={t("orgs.layer.open")}
          onOpenPoi={onOpenPoi}
          polygons={polygons}
          lines={lines}
          heat={heat}
          shapes={shapes}
          weather={mapWeather}
          basemap={basemap.view}
          onMapClick={onMapClick}
          popup={weatherPopup}
          onPopupClose={() => setWeatherPoint(null)}
          onCall={onCall}
          callLabel={t("phone.call")}
        />
      </Suspense>
      <details className="card map-list">
        <summary>{t("map.listToggle")}</summary>
        <ul>
          {reports.map((r) => (
            <li key={r.id}>
              <Link to={`/reports/${encodeURIComponent(r.id)}`}>
                <span dir="ltr">{r.tracking_code}</span> — {t(`category.${r.category}`)} — {t(`status.${r.status}`)}
              </Link>
            </li>
          ))}
          {allPois.map((p) => (
            <li key={`poi-${p.id}`}>
              {p.href ? (
                <Link to={p.href}>
                  <span dir="auto">{p.title}</span> — {p.subtitle}
                </Link>
              ) : (
                <span>
                  <span dir="auto">{p.title}</span>
                  {p.subtitle && ` — ${p.subtitle}`}
                  {p.details && p.details.length > 0 && ` — ${p.details.join(" · ")}`}
                </span>
              )}
            </li>
          ))}
          {showDrones &&
            (zonesQuery.data ?? [])
              .filter((z) => z.active)
              .map((z) => (
                <li key={`zone-${z.id}`}>
                  <Link to="/drones">
                    <span dir="auto">{z.name}</span> — {t(z.kind === "no_fly" ? "drones.map.noFly" : "drones.map.work")}
                  </Link>
                </li>
              ))}
        </ul>
      </details>
    </div>
  );
}
