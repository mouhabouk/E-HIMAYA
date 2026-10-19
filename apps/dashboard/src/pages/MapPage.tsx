import { keepPreviousData, useQuery, type InfiniteData } from "@tanstack/react-query";
import { Suspense, useCallback, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { FiltersBar } from "../components/FiltersBar";
import { LazyMapView } from "../components/LazyMap";
import type { MapMarker, MapPoi } from "../components/MapView";
import { MapLegend, orgKindLabel } from "../components/OrgBits";
import { useAuth } from "../context/auth";
import { useLiveEvents } from "../context/live";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import type { BBox } from "../lib/filters";
import { useDebounced, useFormat, useLanguage } from "../lib/hooks";
import { mapKey } from "../lib/liveCache";
import { initialBoundsFor } from "../lib/mapStyle";
import { canReadOrgs } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import type { Page, StaffReport } from "../lib/types";
import { useEffectiveFilters } from "./useEffectiveFilters";

const PAGE_SIZE = 200; // server maximum is 500
const MAX_PAGES = 2;
const ORG_LAYER_KEY = "ehimaya.mapOrgLayer";

function storedOrgLayer(): boolean {
  try {
    return sessionStorage.getItem(ORG_LAYER_KEY) === "1";
  } catch {
    return false;
  }
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
  const [orgLayer, setOrgLayerState] = useState(storedOrgLayer);
  const showOrgs = orgLayerAllowed && orgLayer;
  const setOrgLayer = (on: boolean) => {
    setOrgLayerState(on);
    try {
      sessionStorage.setItem(ORG_LAYER_KEY, on ? "1" : "0");
    } catch {
      /* ignore */
    }
  };

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
  const legend = useMemo(
    () => [
      { kind: "org" as const, label: t("orgs.layer.org") },
      { kind: "org_hazmat" as const, label: t("orgs.layer.hazmat") },
    ],
    [t],
  );

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
      {orgLayerAllowed && (
        <div className="map-layers">
          <label htmlFor={layerToggleId} className="checkbox">
            <input
              id={layerToggleId}
              type="checkbox"
              checked={orgLayer}
              onChange={(e) => setOrgLayer(e.target.checked)}
            />
            <span>{t("orgs.layer.toggle")}</span>
          </label>
          {showOrgs && (
            <>
              <span className="muted" role="status" aria-live="polite">
                {orgsQuery.isFetching ? t("common.loading") : t("orgs.layer.count", { count: fmt.number(pois.length) })}
              </span>
              <MapLegend items={legend} />
            </>
          )}
        </div>
      )}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {showOrgs && orgsQuery.isError && (
        <ErrorBox error={orgsQuery.error} onRetry={() => void orgsQuery.refetch()} />
      )}
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
          pois={pois}
          poiOpenLabel={t("orgs.layer.open")}
          onOpenPoi={onOpenPoi}
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
          {pois.map((p) => (
            <li key={`org-${p.id}`}>
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
