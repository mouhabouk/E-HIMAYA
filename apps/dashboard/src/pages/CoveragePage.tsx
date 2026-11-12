// covers: OS3 (docs/phase-os3/design-os3.md §3, Yamen 2026-11-11: «تغطية حية وإعادة تمركز عندما تخرج الوحدات»): the
// live coverage of a gouvernorat by family of vehicles against the SNACR targets, the délégations the plan covers and
// the ready vehicles no longer do, and the repositioning the room may accept (the vehicle then waits at the other
// unit as reinforcement; the log keeps the decision and the population it brings back).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { IconTile } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import {
  COVERAGE_FAMILIES,
  fleetKeys,
  type Coverage,
  type CoverageFamily,
  type CoverageSuggestion,
} from "../lib/fleet";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { inventoryKeys } from "../lib/inventory";
import { canSetVehicleState } from "../lib/roles";

export function CoveragePage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const national = user?.identity.national ?? false;
  const roles = user?.identity.roles ?? [];
  const gouvernorats = useGouvernorats();
  const gouvId = useId();
  const [picked, setPicked] = useState<number | null>(null);
  const gouvernorat = national ? (picked ?? gouvernorats.list[0]?.code ?? null) : null;
  const [family, setFamily] = useState<CoverageFamily>("medical");
  const q = useQuery({
    queryKey: fleetKeys.coverage(gouvernorat),
    queryFn: ({ signal }) => api.coverage(gouvernorat, signal),
    enabled: !national || gouvernorat !== null,
    refetchInterval: 60_000,
  });
  return (
    <div className="page coverage-page">
      <div className="page__head">
        <PageTitle print icon="crisisAlert" tone="red">
          {t("coverage.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("coverage.intro")}</p>
      <div className="filters__row">
        {national && (
          <div className="field">
            <label htmlFor={gouvId}>{t("filters.gouvernorat")}</label>
            <select id={gouvId} value={gouvernorat ?? ""} onChange={(e) => setPicked(Number(e.target.value))}>
              {gouvernorats.list.map((g) => (
                <option key={g.code} value={g.code}>
                  {gouvernorats.nameOf(g.code)}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="actions coverage-families" role="group" aria-label={t("coverage.family")}>
          {COVERAGE_FAMILIES.map((f) => (
            <button
              key={f}
              type="button"
              className={`btn btn--small${f === family ? " btn--primary" : " btn--ghost"}`}
              aria-pressed={f === family}
              onClick={() => setFamily(f)}
            >
              {t(`coverage.families.${f}`)}
            </button>
          ))}
        </div>
      </div>
      {q.isPending && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && <Body data={q.data} family={family} canAccept={canSetVehicleState(roles)} />}
    </div>
  );
}

function Body({ data, family, canAccept }: { data: Coverage; family: CoverageFamily; canAccept: boolean }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const lang = useLanguage();
  const row = data.families.find((f) => f.family === family);
  const alerts = data.alerts.filter((a) => a.family === family);
  const suggestions = data.suggestions.filter((s) => s.family === family);
  return (
    <>
      <dl className="kpis">
        {data.families.map((f) => (
          <div key={f.family} className={`kpi kpi--with-icon card${f.family === family ? " kpi--current" : ""}`}>
            <IconTile name={f.covered_pct < f.baseline_pct ? "warning" : "verified"} tone={f.covered_pct < f.baseline_pct ? "red" : "green"} soft />
            <dt className="kpi__label">{t(`coverage.families.${f.family}`)}</dt>
            <dd className="kpi__value">{fmt.percent(f.covered_pct / 100)}</dd>
            <dd className="muted">{t("coverage.planned", { pct: fmt.percent(f.baseline_pct / 100) })}</dd>
            <dd className="muted">{t("coverage.readyOf", { ready: fmt.number(f.ready), fleet: fmt.number(f.fleet) })}</dd>
          </div>
        ))}
      </dl>
      <div className="coverage-grid">
        <section className="card" aria-labelledby="cov-map">
          <h2 id="cov-map">{t("coverage.mapTitle", { family: t(`coverage.families.${family}`) })}</h2>
          <CoverageMap data={data} family={family} />
          <p className="muted">
            {t("coverage.legend")} · {t("coverage.targets", {
              urban: data.targets[family].urban,
              periurban: data.targets[family].periurban,
              rural: data.targets[family].rural,
            })}
          </p>
        </section>
        <div>
          <section className="card" aria-labelledby="cov-alerts">
            <h2 id="cov-alerts">{t("coverage.alerts")}</h2>
            {alerts.length === 0 ? (
              <p className="muted">{t("coverage.noAlert")}</p>
            ) : (
              <ul className="coverage-alerts">
                {alerts.map((a) => (
                  <li key={a.delegation_id} className="alert alert--error">
                    {t("coverage.alert", {
                      place: a.delegation,
                      pop: fmt.number(a.population),
                      now: a.minutes === null ? "—" : fmt.number(a.minutes),
                      target: a.target,
                    })}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="card" aria-labelledby="cov-moves">
            <h2 id="cov-moves">{t("coverage.suggestions")}</h2>
            {suggestions.length === 0 ? (
              <p className="muted">{t("coverage.noSuggestion")}</p>
            ) : (
              suggestions.map((s) => <Suggestion key={`${s.vehicle_id}-${s.to_unit_id}`} s={s} canAccept={canAccept} />)
            )}
          </section>
        </div>
      </div>
      <section className="card" aria-labelledby="cov-table">
        <h2 id="cov-table">{t("coverage.byPlace")}</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("coverage.place")}</th>
                <th scope="col">{t("coverage.population")}</th>
                <th scope="col">{t("coverage.zone")}</th>
                <th scope="col">{t("coverage.time")}</th>
                <th scope="col">{t("coverage.from")}</th>
                <th scope="col">{t("coverage.state")}</th>
              </tr>
            </thead>
            <tbody>
              {[...data.delegations]
                .sort((a, b) => b.population - a.population)
                .map((d) => {
                  const c = d.families[family];
                  return (
                    <tr key={d.id}>
                      <th scope="row">{lang === "ar" ? d.name_ar : d.name_fr}</th>
                      <td className="num">{fmt.number(d.population)}</td>
                      <td>{t(`coverage.zones.${d.zone}`)}</td>
                      <td className="num">
                        {c.minutes === null ? "—" : t("coverage.minutes", { n: fmt.number(c.minutes), target: c.target })}
                      </td>
                      <td dir="auto">{c.unit_name ?? "—"}</td>
                      <td>
                        <span className={`pill tone-${c.covered ? "green" : c.baseline_covered ? "red" : "amber"}`}>
                          {t(c.covered ? "coverage.covered" : c.baseline_covered ? "coverage.lost" : "coverage.notCovered")}
                        </span>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </section>
      <p className="muted">
        {t("coverage.method", { turnout: data.turnout_minutes })} ·{" "}
        {t(data.engine === "fallback" ? "coverage.engineFallback" : "coverage.engineRoad")} ·{" "}
        {t("coverage.computedAt", { at: fmt.dateTime(data.computed_at) })}
        {row ? ` · ${t("coverage.out", { n: fmt.number(row.out) })}` : ""}
      </p>
    </>
  );
}

function Suggestion({ s, canAccept }: { s: CoverageSuggestion; canAccept: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const accept = useMutation({
    mutationFn: () =>
      api.setVehicleState(s.vehicle_id, {
        state: "reinforcement",
        host_unit_id: s.to_unit_id,
        suggested_gain: s.gain_population,
        note: t("coverage.acceptedNote"),
        version: s.version,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["coverage"] });
      void qc.invalidateQueries({ queryKey: inventoryKeys.all });
    },
  });
  return (
    <div className="coverage-move">
      <p>
        <strong dir="auto">{s.label}</strong>:{" "}
        {t("coverage.move", { from: s.from_unit, to: s.to_unit })}
      </p>
      <p className="muted">
        {t("coverage.gain", { n: fmt.number(s.gain_population) })}
        {s.newly_covered.length > 0 && ` — ${s.newly_covered.join("، ")}`}
        {s.lost.length > 0 && ` · ${t("coverage.loses", { places: s.lost.join("، ") })}`}
      </p>
      {canAccept && (
        <button type="button" className="btn btn--small btn--primary" disabled={accept.isPending || accept.isSuccess} onClick={() => accept.mutate()}>
          {accept.isSuccess ? t("coverage.accepted") : t("coverage.accept")}
        </button>
      )}
      {accept.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(accept.error))}
        </p>
      )}
    </div>
  );
}

/** Délégations (circles by population) and units (squares with their ready vehicles of the family), no basemap. */
function CoverageMap({ data, family }: { data: Coverage; family: CoverageFamily }) {
  const { t } = useTranslation();
  const lang = useLanguage();
  const W = 640;
  const H = 420;
  const view = useMemo(() => {
    const pts: [number, number][] = [
      ...data.delegations.map((d): [number, number] => [d.lat, d.lon]),
      ...data.units.map((u): [number, number] => [u.lat, u.lon]),
    ];
    if (pts.length === 0) return null;
    const lats = pts.map((p) => p[0]);
    const lons = pts.map((p) => p[1]);
    const [s, n, w, e] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
    const k = Math.cos(((s + n) / 2) * (Math.PI / 180));
    const spanX = Math.max((e - w) * k, 0.05);
    const spanY = Math.max(n - s, 0.05);
    const scale = Math.min((W - 80) / spanX, (H - 60) / spanY);
    return (lat: number, lon: number) => [40 + (lon - w) * k * scale, 30 + (n - lat) * scale] as const;
  }, [data]);
  if (!view) return <p className="muted">{t("coverage.noPlaces")}</p>;
  const maxPop = Math.max(...data.delegations.map((d) => d.population), 1);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="coverage-map" role="img" aria-label={t("coverage.mapLabel")}>
      {data.delegations.map((d) => {
        const [x, y] = view(d.lat, d.lon);
        const c = d.families[family];
        const tone = c.covered ? "var(--tone-green)" : c.baseline_covered ? "var(--tone-red)" : "var(--tone-amber)";
        return (
          <g key={d.id}>
            <circle cx={x} cy={y} r={6 + 18 * Math.sqrt(d.population / maxPop)} fill={tone} fillOpacity={0.25} stroke={tone} strokeWidth={1.5} />
            <text x={x} y={y + 4} textAnchor="middle" fontSize="11" className="coverage-map__label">
              {lang === "ar" ? d.name_ar : d.name_fr}
            </text>
          </g>
        );
      })}
      {data.units.map((u) => {
        const [x, y] = view(u.lat, u.lon);
        const n = u.ready[family];
        return (
          <g key={u.id}>
            <rect x={x - 8} y={y - 22} width={16} height={16} rx={3} fill={n > 0 ? "var(--tone-navy)" : "var(--muted)"} />
            <text x={x} y={y - 10} textAnchor="middle" fontSize="10" fill="var(--tone-navy-on)">
              {n}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
