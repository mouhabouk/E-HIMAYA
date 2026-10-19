import { keepPreviousData, useQuery, type InfiniteData } from "@tanstack/react-query";
import { Suspense, useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { FiltersBar } from "../components/FiltersBar";
import { LazyMapView } from "../components/LazyMap";
import type { MapMarker } from "../components/MapView";
import { useAuth } from "../context/auth";
import { useLiveEvents } from "../context/live";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import type { BBox } from "../lib/filters";
import { useDebounced, useFormat, useLanguage } from "../lib/hooks";
import { mapKey } from "../lib/liveCache";
import { initialBoundsFor } from "../lib/mapStyle";
import type { Page, StaffReport } from "../lib/types";
import { useEffectiveFilters } from "./useEffectiveFilters";

const PAGE_SIZE = 200; // server maximum is 500
const MAX_PAGES = 2;

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
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
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
        </ul>
      </details>
    </div>
  );
}
