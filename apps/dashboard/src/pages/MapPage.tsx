import { keepPreviousData, useQuery, type InfiniteData } from "@tanstack/react-query";
import { Suspense, useCallback, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { FiltersBar } from "../components/FiltersBar";
import { LazyMapView } from "../components/LazyMap";
import type { HeatPoint, MapMarker, MapPoi, MapPolygon } from "../components/MapView";
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
import { canReadOrgs, canReadResources, canUseTelephony } from "../lib/roles";
import type { DialBody } from "../lib/telephonyTypes";
import { queryKeys } from "../lib/staffApi";
import type { Page, StaffReport } from "../lib/types";
import { useEffectiveFilters } from "./useEffectiveFilters";
import { localized } from "../lib/localized";

const PAGE_SIZE = 200; // server maximum is 500
const MAX_PAGES = 2;
const ORG_LAYER_KEY = "ehimaya.mapOrgLayer";
const RESOURCE_LAYER_KEY = "ehimaya.mapResourceLayer";
const VOLUNTEER_LAYER_KEY = "ehimaya.mapVolunteerLayer";
const ALERT_LAYER_KEY = "ehimaya.mapAlertLayer";
const WEATHER_LAYER_KEY = "ehimaya.mapWeatherLayer";
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
  const gouvernorats = useGouvernorats();

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
    }, []),
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
    return out;
  }, [showResources, resourcesQuery.data, showVolunteers, volunteersQuery.data, lang, t]);
  const allPois = useMemo(() => [...pois, ...opsPois], [pois, opsPois]);
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
  const polygons = useMemo(() => alertPolygons(alerts), [alerts]);

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
    return items;
  }, [showOrgs, showResources, showVolunteers, t]);

  return (
    <div className="page page--map">
      <div className="page__head">
        <h1>{t("map.title")}</h1>
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
        {resourceLayerAllowed && (
          <LayerToggle checked={resourceLayer} onChange={setResourceLayer} label={t("ops.map.resourcesToggle")} />
        )}
        <LayerToggle checked={showVolunteers} onChange={setVolunteerLayer} label={t("ops.map.volunteersToggle")} />
        <LayerToggle checked={showAlerts} onChange={setAlertLayer} label={t("ops.map.alertsToggle")} />
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
      </div>
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
          heat={heat}
          weather={mapWeather}
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
              <Link to={p.href ?? "/orgs"}>
                <span dir="auto">{p.title}</span> — {p.subtitle}
              </Link>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
