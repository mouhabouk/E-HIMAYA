import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Suspense, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router";
import { BarChart, type Bar } from "../components/BarChart";
import { TimeChart, type ChartBand, type ChartSeries } from "../components/charts/TimeChart";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import type { MapHex } from "../components/MapView";
import { AreaTabs, CategorySelect, GouvernoratSelect } from "../components/Phase8Bits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import {
  analyticsSearch,
  exportSearch,
  hexBreaks,
  hexColour,
  hexClass,
  hexLegend,
  parseAnalyticsFilters,
  type AnalyticsFilters,
} from "../lib/analytics";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { initialBoundsFor } from "../lib/mapStyle";
import { p8Keys } from "../lib/phase8Api";
import {
  REPORT_SOURCES,
  RESPONSE_STAGES,
  TREND_INTERVALS,
  TREND_METRICS,
  type AnalyticsOverview,
  type Bucket,
  type Hotspots,
  type Trends,
} from "../lib/phase8Types";
import { canCreateReports, canRunScenarios } from "../lib/roles";
import { CATEGORIES, REPORT_STATUSES } from "../lib/types";

export const HEX_SIZES_KM = [2, 5, 10, 20] as const;

/** Tabs of the analytics area (analytics, what-if). */
export function AnalyticsTabs() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const tabs = [{ to: "/analytics", label: t("analytics.tabs.overview"), end: true }];
  if (canRunScenarios(user?.identity.roles ?? [])) tabs.push({ to: "/analytics/scenarios", label: t("analytics.tabs.whatIf"), end: false });
  return <AreaTabs label={t("analytics.tabs.label")} tabs={tabs} />;
}

function Kpis({ overview }: { overview: AnalyticsOverview }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const totals = ["received", "verified", "in_progress", "closed", "rejected"] as const;
  return (
    <>
      <dl className="kpis">
        {totals.map((k) => (
          <div key={k} className="kpi">
            <dt className="kpi__label">{t(`analytics.totals.${k}`)}</dt>
            <dd className="kpi__value">{fmt.number(overview.totals[k])}</dd>
          </div>
        ))}
      </dl>
      <div className="table-wrap">
        <table className="table table--compact">
          <caption>{t("analytics.responseTime.caption")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("analytics.responseTime.stage")}</th>
              <th scope="col">{t("analytics.responseTime.mean")}</th>
              <th scope="col">{t("analytics.responseTime.p90")}</th>
              <th scope="col">{t("analytics.responseTime.n")}</th>
            </tr>
          </thead>
          <tbody>
            {RESPONSE_STAGES.map((stage) => {
              const s = overview.response_time[stage];
              return (
                <tr key={stage}>
                  <th scope="row">{t(`analytics.responseTime.${stage}`)}</th>
                  <td>{s?.mean_s !== null && s?.mean_s !== undefined ? fmt.duration(s.mean_s) : "—"}</td>
                  <td>{s?.p90_s !== null && s?.p90_s !== undefined ? fmt.duration(s.p90_s) : "—"}</td>
                  <td>{s?.n !== undefined ? fmt.number(s.n) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

function TrendsSection({ trends, filters, onChange }: {
  trends: Trends | undefined;
  filters: AnalyticsFilters;
  onChange: (patch: Partial<AnalyticsFilters>) => void;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const base = useId();
  const seconds = trends?.unit === "seconds" || filters.metric === "response_time";
  const formatValue = (n: number) => (seconds ? fmt.duration(n) : fmt.decimal(n));
  const chart = useMemo(() => {
    const points = trends?.points ?? [];
    const series: ChartSeries[] = [
      { key: "value", label: t(`analytics.metric.${filters.metric}`), values: points.map((p) => p.value), tone: "primary" },
      { key: "last_year", label: t("analytics.trends.lastYear"), values: points.map((p) => p.last_year), tone: "secondary", dashed: true },
      { key: "expected", label: t("analytics.trends.expected"), values: points.map((p) => p.expected), tone: "baseline", dashed: true },
      { key: "low", label: t("analytics.trends.low"), values: points.map((p) => p.low), tone: "baseline", edge: true },
      { key: "high", label: t("analytics.trends.high"), values: points.map((p) => p.high), tone: "baseline", edge: true },
    ];
    const hasBand = points.some((p) => p.low !== null && p.high !== null);
    const bands: ChartBand[] = hasBand ? [{ low: 3, high: 4, label: t("analytics.trends.band") }] : [];
    const x = points.map((p) => Math.round(Date.parse(p.period_start) / 1000));
    const labels = points.map((p) => fmt.date(p.period_start));
    const above = points.filter((p) => p.value !== null && p.high !== null && p.value > p.high).length;
    return { series, bands, x, labels, above, hasBand };
  }, [trends, filters.metric, t, fmt]);
  const baseline = trends?.baseline_available ?? chart.hasBand;
  return (
    <section className="card" aria-labelledby={`${base}-h`}>
      <h2 id={`${base}-h`}>{t("analytics.trends.title")}</h2>
      <div className="filters__row">
        <fieldset className="segmented">
          <legend>{t("analytics.trends.metric")}</legend>
          {TREND_METRICS.map((m) => (
            <label key={m} className="segmented__item">
              <input type="radio" name={`${base}-m`} checked={filters.metric === m} onChange={() => onChange({ metric: m })} />
              <span>{t(`analytics.metric.${m}`)}</span>
            </label>
          ))}
        </fieldset>
        <fieldset className="segmented">
          <legend>{t("analytics.trends.interval")}</legend>
          {TREND_INTERVALS.map((i) => (
            <label key={i} className="segmented__item">
              <input type="radio" name={`${base}-i`} checked={filters.interval === i} onChange={() => onChange({ interval: i })} />
              <span>{t(`analytics.interval.${i}`)}</span>
            </label>
          ))}
        </fieldset>
      </div>
      <TimeChart
        caption={t("analytics.trends.caption", { metric: t(`analytics.metric.${filters.metric}`) })}
        summary={
          baseline
            ? t("analytics.trends.aboveBand", { n: fmt.number(chart.above) })
            : t("analytics.trends.noBaseline")
        }
        x={chart.x}
        xLabels={chart.labels}
        xHeader={t("analytics.trends.period")}
        series={chart.series}
        bands={chart.bands}
        formatValue={formatValue}
        emptyText={t("analytics.noData")}
      />
    </section>
  );
}

function bars(buckets: Bucket<string | number>[] | undefined, label: (key: string | number) => string, order?: readonly (string | number)[]): Bar[] {
  const rows = [...(buckets ?? [])];
  if (order) rows.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
  else rows.sort((a, b) => b.count - a.count);
  return rows.map((b) => ({ key: String(b.key), label: label(b.key), value: b.count }));
}

function Breakdowns({ overview }: { overview: AnalyticsOverview }) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  const hours = Array.from({ length: 24 }, (_, h) => h);
  const weekdays = [1, 2, 3, 4, 5, 6, 7];
  const empty = t("analytics.noData");
  const label = (prefix: string) => (k: string | number) => {
    const key = `${prefix}.${String(k)}`;
    return t(key, { defaultValue: String(k) });
  };
  return (
    <div className="charts">
      <BarChart caption={t("analytics.by.category")} bars={bars(overview.by_category, label("category"), CATEGORIES)} emptyText={empty} />
      <BarChart
        caption={t("analytics.by.gouvernorat")}
        bars={bars(overview.by_gouvernorat, (k) => gouvernorats.nameOf(Number(k)) ?? String(k))}
        emptyText={empty}
      />
      <BarChart caption={t("analytics.by.status")} bars={bars(overview.by_status, label("status"), REPORT_STATUSES)} emptyText={empty} />
      <BarChart caption={t("analytics.by.source")} bars={bars(overview.by_source, label("analytics.source"), REPORT_SOURCES)} emptyText={empty} />
      <BarChart
        caption={t("analytics.by.hour")}
        bars={bars(overview.by_hour, (k) => t("analytics.hourLabel", { hour: String(k).padStart(2, "0") }), hours)}
        emptyText={empty}
      />
      <BarChart caption={t("analytics.by.weekday")} bars={bars(overview.by_weekday, label("analytics.weekday"), weekdays)} emptyText={empty} />
    </div>
  );
}

function centre(ring: [number, number][]): [number, number] {
  const pts = ring.slice(0, -1);
  const n = Math.max(1, pts.length);
  return [pts.reduce((s, p) => s + p[0], 0) / n, pts.reduce((s, p) => s + p[1], 0) / n];
}

function HexSection({ hotspots, size, onSize, loading, error, onRetry }: {
  hotspots: Hotspots | undefined;
  size: number;
  onSize: (n: number) => void;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const lang = useLanguage();
  const { mapStyleUrl } = useServices();
  const { user } = useAuth();
  const id = useId();
  const { hexes, legend, top } = useMemo(() => {
    const features = hotspots?.features ?? [];
    const counts = features.map((f) => f.properties.count);
    const breaks = hexBreaks(counts);
    const max = Math.max(0, ...counts);
    const hexes: MapHex[] = features
      .filter((f) => f.properties.count > 0)
      .map((f, i) => ({
        id: f.properties.id ?? String(i),
        coordinates: f.geometry.coordinates as [number, number][][],
        colour: hexColour(hexClass(f.properties.count, breaks)),
        count: f.properties.count,
      }));
    const top = [...hexes]
      .sort((a, b) => b.count - a.count)
      .slice(0, 15)
      .map((h) => ({ ...h, centre: centre(h.coordinates[0] ?? []) }));
    return { hexes, legend: max > 0 ? hexLegend(breaks, max) : [], top };
  }, [hotspots]);
  return (
    <section className="card" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{t("analytics.hotspots.title")}</h2>
      <p className="muted">{t("analytics.hotspots.intro")}</p>
      <div className="field field--inline">
        <label htmlFor={`${id}-size`}>{t("analytics.hotspots.size")}</label>
        <select id={`${id}-size`} value={size} onChange={(e) => onSize(Number(e.target.value))}>
          {HEX_SIZES_KM.map((s) => (
            <option key={s} value={s}>
              {t("analytics.hotspots.km", { n: s })}
            </option>
          ))}
        </select>
      </div>
      {error !== null && error !== undefined && <ErrorBox error={error} onRetry={onRetry} />}
      <Suspense fallback={<Loading />}>
        <LazyMapView
          className="map map--analytics"
          markers={[]}
          bounds={initialBoundsFor(user?.identity.gouvernoratCode ?? null)}
          ariaLabel={t("analytics.hotspots.mapLabel")}
          styleUrl={mapStyleUrl}
          dir={directionOf(lang)}
          hexes={hexes}
        />
      </Suspense>
      {legend.length > 0 && (
        <ul className="map-legend hex-legend" aria-label={t("analytics.hotspots.legend")}>
          {legend.map((row) => (
            <li key={row.from}>
              <span className="swatch" style={{ backgroundColor: row.colour }} aria-hidden="true" />
              {row.to === null || row.to === row.from
                ? fmt.number(row.from)
                : t("analytics.hotspots.range", { from: fmt.number(row.from), to: fmt.number(row.to) })}
            </li>
          ))}
        </ul>
      )}
      {loading && <Loading />}
      <details className="details">
        <summary>{t("analytics.hotspots.tableToggle")}</summary>
        {top.length === 0 ? (
          <p className="muted">{t("analytics.noData")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table table--compact">
              <caption>{t("analytics.hotspots.tableCaption", { n: top.length })}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("analytics.hotspots.cell")}</th>
                  <th scope="col">{t("analytics.hotspots.centre")}</th>
                  <th scope="col">{t("analytics.hotspots.count")}</th>
                </tr>
              </thead>
              <tbody>
                {top.map((h) => (
                  <tr key={h.id}>
                    <th scope="row" className="code" dir="ltr">
                      {h.id}
                    </th>
                    <td className="code" dir="ltr">
                      {h.centre[1].toFixed(2)}, {h.centre[0].toFixed(2)}
                    </td>
                    <td>{fmt.number(h.count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>
    </section>
  );
}

/**
 * Analytics (FR-C-01, §4): KPI cards, trends with the seasonal band, breakdowns and the hexagon layer. Filters live
 * in the URL so a view can be shared; "export" opens the report form prefilled with them.
 */
export function AnalyticsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const national = user?.identity.national ?? false;
  const filters = useMemo(() => parseAnalyticsFilters(params, national), [params, national]);
  const [size, setSize] = useState<number>(5);
  const ids = { from: useId(), to: useId() };
  const update = (patch: Partial<AnalyticsFilters>) => setParams(analyticsSearch({ ...filters, ...patch }), { replace: true });

  const overview = useQuery({
    queryKey: p8Keys.overview(filters),
    queryFn: ({ signal }) => api.analyticsOverview(filters, signal),
    placeholderData: keepPreviousData,
  });
  const trends = useQuery({
    queryKey: p8Keys.trends(filters, filters.metric, filters.interval),
    queryFn: ({ signal }) => api.analyticsTrends(filters, filters.metric, filters.interval, signal),
    placeholderData: keepPreviousData,
  });
  const hotspots = useQuery({
    queryKey: p8Keys.hotspots(filters, size),
    queryFn: ({ signal }) => api.analyticsHotspots(filters, size, signal),
    placeholderData: keepPreviousData,
  });
  const exportable = canCreateReports(user?.identity.roles ?? []);

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("analytics.title")}</h1>
        {exportable && (
          <button type="button" className="btn btn--primary" onClick={() => void navigate(`/reports-library${exportSearch(filters)}`)}>
            {t("analytics.export")}
          </button>
        )}
      </div>
      <AnalyticsTabs />
      <p className="muted">{t("analytics.intro")}</p>
      <form className="filters" aria-label={t("analytics.filters")} onSubmit={(e) => e.preventDefault()}>
        <div className="filters__row">
          <div className="field">
            <label htmlFor={ids.from}>{t("analytics.from")}</label>
            <input id={ids.from} type="date" value={filters.from} max={filters.to} onChange={(e) => e.target.value && update({ from: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor={ids.to}>{t("analytics.to")}</label>
            <input id={ids.to} type="date" value={filters.to} min={filters.from} onChange={(e) => e.target.value && update({ to: e.target.value })} />
          </div>
          {national && (
            <GouvernoratSelect
              value={filters.gouvernorat}
              onChange={(g) => update({ gouvernorat: g })}
              label={t("analytics.gouvernorat")}
              allLabel={t("analytics.national")}
            />
          )}
          <CategorySelect
            value={filters.category}
            onChange={(c) => update({ category: (c as AnalyticsFilters["category"]) ?? null })}
            label={t("analytics.category")}
            allLabel={t("analytics.allCategories")}
          />
          <button type="button" className="btn btn--ghost" onClick={() => setParams(new URLSearchParams(), { replace: true })}>
            {t("filters.reset")}
          </button>
        </div>
      </form>
      {overview.isPending && <Loading />}
      {overview.isError && <ErrorBox error={overview.error} onRetry={() => void overview.refetch()} />}
      {overview.data && <Kpis overview={overview.data} />}
      {trends.isError && <ErrorBox error={trends.error} onRetry={() => void trends.refetch()} />}
      <TrendsSection trends={trends.data} filters={filters} onChange={update} />
      {overview.data && (
        <section aria-label={t("analytics.by.title")}>
          <h2>{t("analytics.by.title")}</h2>
          <Breakdowns overview={overview.data} />
        </section>
      )}
      <HexSection
        hotspots={hotspots.data}
        size={size}
        onSize={setSize}
        loading={hotspots.isFetching}
        error={hotspots.error}
        onRetry={() => void hotspots.refetch()}
      />
      {overview.data?.min_cell !== undefined && (
        <p className="muted">{t("analytics.minCell", { n: overview.data.min_cell })}</p>
      )}
    </div>
  );
}
