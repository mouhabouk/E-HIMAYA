// Operations room wall view (map/room): the day's figures, the last 24 hours, the readiness of the means and the
// active alerts around a dark 3D map of the live reports. Read only; every figure comes from the existing staff API.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { FeatureCollection, Point, Polygon } from "geojson";
import { lazy, Suspense, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import type { OpsRoomLayers } from "../components/OpsRoomMap";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { DEFAULT_FILTERS } from "../lib/filters";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { localized } from "../lib/localized";
import { initialBoundsFor } from "../lib/mapStyle";
import { opsKeys } from "../lib/opsApi";
import {
  categoryCounts,
  hexHeight,
  hourlyCounts,
  isOpen,
  openCount,
  OPS_CATEGORY_COLOURS,
  readiness,
  reportPoints,
  startOfDay,
} from "../lib/opsRoom";
import { p8Keys } from "../lib/phase8Api";
import { useNow } from "../lib/phase9";
import { queryKeys } from "../lib/staffApi";
import type { StaffReport } from "../lib/types";

const OpsRoomMap = lazy(() => import("../components/OpsRoomMap").then((m) => ({ default: m.OpsRoomMap })));

const REFRESH_MS = 30_000;
const HOTSPOT_DAYS = 7;
const HOTSPOT_KM = 1;
const RING_COLOURS = ["#4DD0B8", "#FFA733", "#8FA8FF"];
const SEVERITY_COLOURS: Record<string, string> = { high: "#FF6B6B", medium: "#FFA733", low: "#64B5F6" };

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  const id = useId();
  return (
    <section className="ops-room__panel" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {children}
    </section>
  );
}

/** Reports of the last 24 hours, as an area with the current hour marked. */
function Last24({ counts, label }: { counts: number[]; label: string }) {
  const { t } = useTranslation();
  const W = 268;
  const H = 104;
  const pad = 16;
  const max = Math.max(1, ...counts) * 1.15;
  const x = (i: number) => (i / 23) * W;
  const y = (v: number) => H - pad - (v / max) * (H - pad - 8);
  const line = counts.map((v, i) => `${x(i)},${y(v)}`).join("L");
  const peakValue = Math.max(0, ...counts);
  const peak = counts.indexOf(peakValue);
  return (
    <figure className="ops-room__chart">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={label}>
        <defs>
          <linearGradient id="ops-room-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#8FA8FF" stopOpacity="0.45" />
            <stop offset="1" stopColor="#8FA8FF" stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1="0" x2={W} y1={H - pad} y2={H - pad} stroke="#26304D" />
        <path d={`M${line}L${W},${H - pad}L0,${H - pad}Z`} fill="url(#ops-room-area)" />
        <path d={`M${line}`} fill="none" stroke="#8FA8FF" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
        {peakValue > 0 && <circle cx={x(peak)} cy={y(peakValue)} r="3" fill="#FFA733" />}
      </svg>
      <figcaption>
        <span>{t("opsRoom.chart.ago24")}</span>
        <span>{t("opsRoom.chart.peak", { count: peakValue })}</span>
        <span>{t("opsRoom.chart.now")}</span>
      </figcaption>
    </figure>
  );
}

function Ring({ fraction, colour, label, detail }: { fraction: number; colour: string; label: string; detail: string }) {
  const fmt = useFormat();
  const r = 28;
  const c = 2 * Math.PI * r;
  return (
    <div className="ops-room__ring-tile">
      <svg viewBox="0 0 70 70" aria-hidden="true">
        <circle cx="35" cy="35" r={r} fill="none" stroke="#26304D" strokeWidth="6" />
        <circle
          cx="35"
          cy="35"
          r={r}
          fill="none"
          stroke={colour}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={`${c * fraction} ${c}`}
          transform="rotate(-90 35 35)"
        />
      </svg>
      <span className="ops-room__ring-value">{fmt.percent(fraction)}</span>
      <span>{label}</span>
      <b>{detail}</b>
    </div>
  );
}

export function OpsRoomPage() {
  const { t } = useTranslation();
  const fmt = useFormat();
  const lang = useLanguage();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const { nameOf } = useGouvernorats();
  const now = useNow(60_000);
  const [bounds] = useState(() => initialBoundsFor(user?.identity.gouvernoratCode ?? null));
  const [threeD, setThreeD] = useState(true);
  const [homeKey, setHomeKey] = useState(0);
  const [layers, setLayers] = useState<OpsRoomLayers>({ reports: true, hotspots: true, units: true, buildings: true });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [since] = useState(() => startOfDay(new Date()));
  const [window7] = useState(() => {
    const to = new Date();
    return { from: new Date(to.getTime() - HOTSPOT_DAYS * 86_400_000).toISOString(), to: to.toISOString() };
  });

  const kpis = useQuery({
    queryKey: [...queryKeys.kpis(since), "ops-room"],
    queryFn: ({ signal }) => api.kpis(since, signal),
    refetchInterval: REFRESH_MS,
  });
  const reports = useQuery({
    queryKey: ["ops-room", "reports-24h"],
    queryFn: ({ signal }) => api.reports({ ...DEFAULT_FILTERS, period: "24h" }, { limit: 500, signal }),
    refetchInterval: REFRESH_MS,
    placeholderData: keepPreviousData,
  });
  const hotspots = useQuery({
    queryKey: p8Keys.hotspots(window7, HOTSPOT_KM),
    queryFn: ({ signal }) => api.analyticsHotspots(window7, HOTSPOT_KM, signal),
    staleTime: 5 * 60_000,
  });
  const summary = useQuery({
    queryKey: ["ops-room", "resource-summary"],
    queryFn: ({ signal }) => api.resourceSummary(signal),
    refetchInterval: 60_000,
  });
  const units = useQuery({
    queryKey: opsKeys.resourcesMap(bounds),
    queryFn: ({ signal }) => api.resourcesMap(bounds, signal),
    staleTime: 5 * 60_000,
  });
  const alerts = useQuery({
    queryKey: opsKeys.activeAlerts,
    queryFn: ({ signal }) => api.activeAlerts(signal),
    refetchInterval: 60_000,
  });

  const items: StaffReport[] = useMemo(() => reports.data?.items ?? [], [reports.data]);
  const hours = useMemo(() => hourlyCounts(items, new Date(now)), [items, now]);
  const points = useMemo(() => reportPoints(items), [items]);
  const hexes = useMemo((): FeatureCollection<Polygon, { count: number; height: number }> => {
    const f = hotspots.data?.features ?? [];
    const max = Math.max(0, ...f.map((h) => h.properties.count));
    return {
      type: "FeatureCollection",
      features: f.map((h) => ({ ...h, properties: { count: h.properties.count, height: hexHeight(h.properties.count, max) } })),
    };
  }, [hotspots.data]);
  const unitPoints = useMemo(
    (): FeatureCollection<Point, { name: string }> => ({
      type: "FeatureCollection",
      features: (units.data?.features ?? []).flatMap((f) =>
        f.properties.layer === "unit"
          ? [{ type: "Feature" as const, geometry: f.geometry, properties: { name: f.properties.name } }]
          : [],
      ),
    }),
    [units.data],
  );
  const openReports = useMemo(
    () =>
      items
        .filter((r) => isOpen(r.status))
        .sort((a, b) => (b.priority_score ?? -1) - (a.priority_score ?? -1) || b.created_at.localeCompare(a.created_at)),
    [items],
  );
  const selected = items.find((r) => r.id === selectedId) ?? null;
  const k = kpis.data;
  const cats = k ? categoryCounts(k).slice(0, 6) : [];
  const catMax = cats[0]?.count ?? 1;
  const ready = summary.data ? readiness(summary.data) : [];
  const toggles: [keyof OpsRoomLayers, string, string][] = [
    ["reports", t("opsRoom.layers.reports"), "#FFA733"],
    ["hotspots", t("opsRoom.layers.hotspots", { days: HOTSPOT_DAYS }), "#FF6B6B"],
    ["units", t("opsRoom.layers.units"), "#FF6B6B"],
    ["buildings", t("opsRoom.layers.buildings"), "#8FA8FF"],
  ];

  return (
    <div className="ops-room">
      <header className="ops-room__head">
        <PageTitle icon="monitoring" tone="red">
          {t("opsRoom.title")}
        </PageTitle>
        <span className="ops-room__live">
          <i aria-hidden="true" />
          {t("opsRoom.live")}
        </span>
        <span className="ops-room__clock">{fmt.dateTime(new Date(now).toISOString())}</span>
        <Link className="ops-room__back" to="/map">
          {t("opsRoom.back")}
        </Link>
      </header>

      <div className="ops-room__grid">
        <div className="ops-room__col">
          <Panel title={t("opsRoom.today")}>
            {kpis.isError ? (
              <ErrorBox error={kpis.error} onRetry={() => void kpis.refetch()} />
            ) : !k ? (
              <Loading />
            ) : (
              <dl className="ops-room__kpis">
                <div>
                  <dt>{t("opsRoom.kpi.total")}</dt>
                  <dd>{fmt.number(k.total)}</dd>
                </div>
                <div>
                  <dt>{t("opsRoom.kpi.open")}</dt>
                  <dd style={{ color: "#FFA733" }}>{fmt.number(openCount(k))}</dd>
                </div>
                <div>
                  <dt>{t("opsRoom.kpi.highPriority")}</dt>
                  <dd style={{ color: "#FF6B6B" }}>{fmt.number(k.high_priority)}</dd>
                </div>
                <div>
                  <dt>{t("opsRoom.kpi.firstResponse")}</dt>
                  <dd style={{ color: "#4DD0B8" }}>
                    {k.avg_first_response_s === null ? "—" : fmt.duration(k.avg_first_response_s)}
                  </dd>
                </div>
              </dl>
            )}
          </Panel>
          <Panel title={t("opsRoom.last24")}>
            {reports.isError ? (
              <ErrorBox error={reports.error} onRetry={() => void reports.refetch()} />
            ) : (
              <Last24 counts={hours} label={t("opsRoom.chart.label", { total: hours.reduce((a, b) => a + b, 0) })} />
            )}
          </Panel>
          <Panel title={t("opsRoom.byCategory")}>
            {cats.length === 0 ? (
              <p className="ops-room__empty">{t("opsRoom.none")}</p>
            ) : (
              <ul className="ops-room__bars">
                {cats.map((c) => (
                  <li key={c.category}>
                    <span>{t(`category.${c.category}`)}</span>
                    <span className="ops-room__track" aria-hidden="true">
                      <i style={{ inlineSize: `${(c.count / catMax) * 100}%`, background: OPS_CATEGORY_COLOURS[c.category] }} />
                    </span>
                    <span className="ops-room__n">{fmt.number(c.count)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <div className="ops-room__stage">
          <Suspense fallback={<Loading />}>
            <OpsRoomMap
              styleUrl={mapStyleUrl}
              bounds={bounds}
              ariaLabel={t("opsRoom.mapLabel")}
              dir={directionOf(lang)}
              threeD={threeD}
              layers={layers}
              reports={points}
              hotspots={hexes}
              units={unitPoints}
              selected={selected ? { lon: selected.location.lon, lat: selected.location.lat } : null}
              onSelect={setSelectedId}
              homeKey={homeKey}
            />
          </Suspense>
          <div className="ops-room__tags">
            <span>
              {t("opsRoom.tag.open")} <b>{fmt.number(openReports.length)}</b>
            </span>
            <span>
              {t("opsRoom.tag.units")} <b>{fmt.number(unitPoints.features.length)}</b>
            </span>
          </div>
          <div className="ops-room__tools">
            <button type="button" aria-pressed={threeD} onClick={() => setThreeD((v) => !v)}>
              {threeD ? "3D" : "2D"}
            </button>
            <button type="button" onClick={() => setHomeKey((n) => n + 1)}>
              {t("opsRoom.home")}
            </button>
          </div>
          {selected && (
            <aside className="ops-room__card" aria-label={t("opsRoom.card.label")}>
              <div className="ops-room__card-head">
                <span className="ops-room__pill" style={{ color: OPS_CATEGORY_COLOURS[selected.category] }}>
                  {t(`category.${selected.category}`)}
                </span>
                <b>{nameOf(selected.gouvernorat_code) ?? "—"}</b>
                <button type="button" onClick={() => setSelectedId(null)} aria-label={t("opsRoom.card.close")}>
                  ×
                </button>
              </div>
              <dl>
                <dt>{t("opsRoom.card.code")}</dt>
                <dd className="ops-room__mono">{selected.tracking_code}</dd>
                <dt>{t("opsRoom.card.status")}</dt>
                <dd>{t(`status.${selected.status}`)}</dd>
                <dt>{t("opsRoom.card.time")}</dt>
                <dd>{fmt.time(selected.created_at)}</dd>
                <dt>{t("opsRoom.card.priority")}</dt>
                <dd>{selected.priority_score === null ? t("priority.none") : fmt.number(selected.priority_score)}</dd>
              </dl>
              <Link to={`/reports/${selected.id}`}>{t("opsRoom.card.open")}</Link>
            </aside>
          )}
        </div>

        <div className="ops-room__col">
          <Panel title={t("opsRoom.layers.title")}>
            <div className="ops-room__layers">
              {toggles.map(([key, label, colour]) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    className="ops-room__toggle"
                    checked={layers[key]}
                    onChange={(e) => setLayers((l) => ({ ...l, [key]: e.target.checked }))}
                  />
                  <span className="ops-room__swatch" style={{ background: colour }} aria-hidden="true" />
                  {label}
                </label>
              ))}
            </div>
          </Panel>
          <Panel title={t("opsRoom.readiness")}>
            {ready.length === 0 ? (
              <p className="ops-room__empty">{summary.isLoading ? t("opsRoom.loading") : t("opsRoom.none")}</p>
            ) : (
              <div className="ops-room__rings">
                {ready.map((r, i) => (
                  <Ring
                    key={r.kind}
                    fraction={r.total ? r.available / r.total : 0}
                    colour={RING_COLOURS[i % RING_COLOURS.length] ?? "#8FA8FF"}
                    label={t(`resources.kind.${r.kind}`)}
                    detail={`${fmt.number(r.available)}/${fmt.number(r.total)}`}
                  />
                ))}
              </div>
            )}
          </Panel>
          <Panel title={t("opsRoom.openReports")}>
            {openReports.length === 0 ? (
              <p className="ops-room__empty">{t("opsRoom.none")}</p>
            ) : (
              <ul className="ops-room__list">
                {openReports.slice(0, 5).map((r) => (
                  <li key={r.id}>
                    <button type="button" onClick={() => setSelectedId(r.id)} aria-pressed={r.id === selectedId}>
                      <i style={{ background: OPS_CATEGORY_COLOURS[r.category] }} aria-hidden="true" />
                      <span>
                        <b>{t(`category.${r.category}`)}</b>
                        <small>
                          {nameOf(r.gouvernorat_code) ?? "—"} · {t(`status.${r.status}`)}
                        </small>
                      </span>
                      <time dateTime={r.created_at}>{fmt.time(r.created_at)}</time>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title={t("opsRoom.alerts")}>
            {(alerts.data ?? []).length === 0 ? (
              <p className="ops-room__empty">{t("opsRoom.noAlerts")}</p>
            ) : (
              <ul className="ops-room__list">
                {(alerts.data ?? []).slice(0, 4).map((m) => (
                  <li key={m.id}>
                    <div className="ops-room__alert">
                      <i style={{ background: SEVERITY_COLOURS[m.severity ?? ""] ?? "#8FA8FF" }} aria-hidden="true" />
                      <span>
                        <b>{localized(m.title, lang)}</b>
                      </span>
                      {m.published_at && <time dateTime={m.published_at}>{fmt.time(m.published_at)}</time>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

