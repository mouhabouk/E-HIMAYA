// covers: phase S (docs/phase-s/design-s.md): the risk analysis and coverage plan (SNACR) drawn from the Office's
// archive of interventions over three years: the indicators of each délégation and its map, the frequency × coverage
// matrix, the seasons and hours, the register of specific risks, the plan of each committee with its document, the
// archive and its names, and the method with the national and international references it rests on.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useId, useMemo, useState, type CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { BarChart } from "../components/BarChart";
import { SimBadge } from "../components/crisis/CrisisBits";
import { useDelegations } from "../components/DelegationPicker";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import type { MapAdmin } from "../components/MapView";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { ADMIN_LINE, adminKeys, type AdminProps } from "../lib/admin";
import { errorMessageKey, isApiError } from "../lib/api";
import { saveDownload } from "../lib/layersApi";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { localizedName } from "../lib/localized";
import { initialBoundsFor } from "../lib/mapStyle";
import { canPlanSnacr } from "../lib/roles";
import {
  FAMILIES,
  HAZARDS,
  MISSION_PARTS,
  PRIORITY_COLOURS,
  priorityOf,
  snacrKeys,
  ZONES,
  type DelegationAnalysis,
  type Family,
  type Hazard,
  type Priority,
  type SnacrAnalysis,
  type SnacrOverview,
  type SpecialRisk,
} from "../lib/snacr";

const TABS = ["indicators", "matrix", "seasons", "special", "plan", "archive", "method"] as const;
type Tab = (typeof TABS)[number];
const METRICS = ["priority", "rate", "compliance", "completeness"] as const;
type Metric = (typeof METRICS)[number];
const RAMP = ["#FDE8E8", "#F8B4B4", "#F05252", "#C81E1E", "#771D1D"] as const;
const GREENS = ["#C81E1E", "#F05252", "#F59E0B", "#84CC16", "#16A34A"] as const;

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${Math.round(v)} %`;
}

function minutes(v: number | null | undefined, unit: string): string {
  return v === null || v === undefined ? "—" : `${Math.round(v * 10) / 10} ${unit}`;
}

function PriorityTag({ p }: { p: Priority | null }) {
  const { t } = useTranslation();
  if (!p) return <span className="muted">—</span>;
  return <span className={`snacr-priority snacr-priority--${p}`}>{t(`snacr.priority.${p}`)}</span>;
}

/** The colour of a délégation for the chosen measure. */
function colourOf(d: DelegationAnalysis | undefined, metric: Metric, breaks: readonly number[]): string {
  if (!d) return PRIORITY_COLOURS.none;
  if (metric === "priority") return PRIORITY_COLOURS[d.priority ?? "none"];
  if (metric === "rate") {
    if (d.rate_per_1000 === null) return PRIORITY_COLOURS.none;
    const i = breaks.findIndex((b) => (d.rate_per_1000 ?? 0) <= b);
    return RAMP[i === -1 ? RAMP.length - 1 : Math.min(i, RAMP.length - 1)] ?? PRIORITY_COLOURS.none;
  }
  const v = metric === "compliance" ? d.compliance_pct : d.completeness_pct;
  if (v === null) return PRIORITY_COLOURS.none;
  return GREENS[Math.min(4, Math.floor(v / 20))] ?? PRIORITY_COLOURS.none;
}

function DelegationMap({ analysis, gouvernorat }: { analysis: SnacrAnalysis; gouvernorat: number | null }) {
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const lang = useLanguage();
  const fmt = useFormat();
  const [metric, setMetric] = useState<Metric>("priority");
  const [picked, setPicked] = useState<number | null>(null);
  const id = useId();
  const shapes = useQuery({
    queryKey: adminKeys.boundaries("delegations", gouvernorat),
    staleTime: Infinity,
    queryFn: ({ signal }) => api.boundaries("delegations", gouvernorat, signal),
  });
  const byId = useMemo(() => new Map(analysis.delegations.map((d) => [d.id, d])), [analysis.delegations]);
  const admin = useMemo<MapAdmin | null>(
    () =>
      shapes.data
        ? {
            filled: true,
            data: {
              type: "FeatureCollection",
              features: shapes.data.features.map((f) => ({
                ...f,
                properties: {
                  ...f.properties,
                  line: ADMIN_LINE,
                  fill: colourOf(byId.get(Number(f.properties?.id)), metric, analysis.breaks),
                },
              })),
            },
          }
        : null,
    [shapes.data, byId, metric, analysis.breaks],
  );
  const chosen = picked !== null ? byId.get(picked) : undefined;
  return (
    <section className="card snacr-map" aria-labelledby={`${id}-h`}>
      <div className="page__head">
        <h3 id={`${id}-h`}>{t("snacr.map.title")}</h3>
        <div className="field field--inline">
          <label htmlFor={`${id}-m`}>{t("snacr.map.metric")}</label>
          <select id={`${id}-m`} value={metric} onChange={(e) => setMetric(e.target.value as Metric)}>
            {METRICS.map((m) => (
              <option key={m} value={m}>
                {t(`snacr.map.metrics.${m}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {shapes.isPending && <Loading />}
      {admin && (
        <Suspense fallback={<Loading />}>
          <LazyMapView
            className="map map--snacr"
            markers={[]}
            bounds={initialBoundsFor(gouvernorat)}
            ariaLabel={t("snacr.map.aria")}
            styleUrl={mapStyleUrl}
            dir={directionOf(lang)}
            admin={admin}
            onAdminClick={(p) => setPicked(Number(p.id))}
          />
        </Suspense>
      )}
      <p className="muted">{t(`snacr.map.legend.${metric}`)}</p>
      {chosen && (
        <p role="status" className="snacr-map__picked">
          <strong>{lang === "ar" ? chosen.name_ar : chosen.name_fr}</strong> · {t(`snacr.zone.${chosen.zone}`)} ·{" "}
          {t("snacr.ind.annual")}: {fmt.number(chosen.annual)} · {t("snacr.ind.rate")}:{" "}
          {chosen.rate_per_1000 === null ? "—" : fmt.decimal(chosen.rate_per_1000)} · {t("snacr.ind.compliance")}:{" "}
          {pct(chosen.compliance_pct)} · <PriorityTag p={chosen.priority} />
        </p>
      )}
    </section>
  );
}

/** Phase S2: the whole mission, from the records of the rooms (the Office's archive stops at the arrival). */
function MissionTable({ analysis }: { analysis: SnacrAnalysis }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const m = t("snacr.unit.min");
  const rows = FAMILIES.filter((f) => analysis.mission?.[f]);
  if (rows.length === 0) return null;
  return (
    <div className="table-wrap">
      <table className="table table--compact">
        <caption>{t("snacr.mission.title")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("snacr.family.label")}</th>
            <th scope="col">{t("snacr.mission.rows")}</th>
            {MISSION_PARTS.map((p) => (
              <th scope="col" key={p}>
                {t(`snacr.mission.${p}`)}
              </th>
            ))}
            <th scope="col">{t("snacr.mission.crew")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((f) => {
            const x = analysis.mission?.[f];
            if (!x) return null;
            return (
              <tr key={f}>
                <th scope="row">{t(`snacr.family.${f}`)}</th>
                <td>{fmt.number(x.rows)}</td>
                {MISSION_PARTS.map((p) => (
                  <td key={p}>
                    {minutes(x[`${p}_median`], m)}
                    <span className="cell-sub"> · P90 {minutes(x[`${p}_p90`], m)}</span>
                  </td>
                ))}
                <td>{x.crew_mean === null ? "—" : fmt.decimal(x.crew_mean)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="muted">{t("snacr.mission.note")}</p>
    </div>
  );
}

function IndicatorsTab({ analysis, gouvernorat }: { analysis: SnacrAnalysis; gouvernorat: number | null }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const [family, setFamily] = useState<Family>("medical");
  const [sort, setSort] = useState<"priority" | "rate" | "compliance">("priority");
  const id = useId();
  const m = t("snacr.unit.min");
  const totals = analysis.totals;
  const rank: Record<Priority, number> = { high: 0, medium: 1, low: 2 };
  const delegations = [...analysis.delegations].sort((a, b) =>
    sort === "priority"
      ? (a.priority ? rank[a.priority] : 3) - (b.priority ? rank[b.priority] : 3) || b.annual - a.annual
      : sort === "rate"
        ? (b.rate_per_1000 ?? -1) - (a.rate_per_1000 ?? -1)
        : (a.compliance_pct ?? 101) - (b.compliance_pct ?? 101),
  );
  return (
    <>
      <dl className="kpis">
        <div className="kpi">
          <dt className="kpi__label">{t("snacr.ind.annual")}</dt>
          <dd className="kpi__value">{fmt.number(totals.annual)}</dd>
        </div>
        <div className="kpi">
          <dt className="kpi__label">{t("snacr.ind.rate")}</dt>
          <dd className="kpi__value">{totals.rate_per_1000 === null ? "—" : fmt.decimal(totals.rate_per_1000)}</dd>
        </div>
        <div className="kpi">
          <dt className="kpi__label">{t("snacr.ind.compliance", { goal: analysis.method.goal })}</dt>
          <dd className="kpi__value">{pct(totals.compliance_pct)}</dd>
        </div>
        <div className="kpi">
          <dt className="kpi__label">{t("snacr.ind.completeness")}</dt>
          <dd className="kpi__value">{pct(totals.completeness_pct)}</dd>
        </div>
        <div className="kpi">
          <dt className="kpi__label">{t("snacr.ind.unmatched")}</dt>
          <dd className="kpi__value">{fmt.number(totals.unmatched)}</dd>
        </div>
      </dl>
      <DelegationMap analysis={analysis} gouvernorat={gouvernorat} />
      <MissionTable analysis={analysis} />
      <div className="table-wrap">
        <table className="table table--compact">
          <caption>{t("snacr.ind.byGouvernorat")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("snacr.col.gouvernorat")}</th>
              <th scope="col">{t("snacr.ind.annual")}</th>
              <th scope="col">{t("snacr.ind.rate")}</th>
              {FAMILIES.map((f) => (
                <th scope="col" key={f}>
                  {t("snacr.col.p90", { family: t(`snacr.family.${f}`) })}
                </th>
              ))}
              <th scope="col">{t("snacr.ind.complianceShort")}</th>
              <th scope="col">{t("snacr.ind.completeness")}</th>
            </tr>
          </thead>
          <tbody>
            {analysis.gouvernorats.map((g) => (
              <tr key={g.code}>
                <th scope="row">{gouvernorats.nameOf(g.code)}</th>
                <td>{fmt.number(g.annual)}</td>
                <td>{g.rate_per_1000 === null ? "—" : fmt.decimal(g.rate_per_1000)}</td>
                {FAMILIES.map((f) => (
                  <td key={f}>{minutes(g.families[f]?.arrival_p90, m)}</td>
                ))}
                <td>{pct(g.compliance_pct)}</td>
                <td>{pct(g.completeness_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="filters">
        <div className="field field--inline">
          <label htmlFor={`${id}-f`}>{t("snacr.family.label")}</label>
          <select id={`${id}-f`} value={family} onChange={(e) => setFamily(e.target.value as Family)}>
            {FAMILIES.map((f) => (
              <option key={f} value={f}>
                {t(`snacr.family.${f}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field field--inline">
          <label htmlFor={`${id}-s`}>{t("snacr.sort.label")}</label>
          <select id={`${id}-s`} value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
            {(["priority", "rate", "compliance"] as const).map((k) => (
              <option key={k} value={k}>
                {t(`snacr.sort.${k}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="table-wrap">
        <table className="table table--compact">
          <caption>{t("snacr.ind.byDelegation", { family: t(`snacr.family.${family}`) })}</caption>
          <thead>
            <tr>
              <th scope="col">{t("snacr.col.delegation")}</th>
              <th scope="col">{t("snacr.col.zone")}</th>
              <th scope="col">{t("snacr.ind.annual")}</th>
              <th scope="col">{t("snacr.ind.rate")}</th>
              <th scope="col">{t("snacr.col.target")}</th>
              <th scope="col">{t("snacr.col.median")}</th>
              <th scope="col">{t("snacr.col.p90short")}</th>
              <th scope="col">{t("snacr.col.departure")}</th>
              <th scope="col">{t("snacr.ind.complianceShort")}</th>
              <th scope="col">{t("snacr.col.levels")}</th>
              <th scope="col">{t("snacr.col.priority")}</th>
            </tr>
          </thead>
          <tbody>
            {delegations.map((d) => {
              const f = d.families[family];
              return (
                <tr key={d.id}>
                  <th scope="row" dir="auto">
                    {lang === "ar" ? d.name_ar : d.name_fr}
                  </th>
                  <td>{t(`snacr.zone.${d.zone}`)}</td>
                  <td>{fmt.number(d.annual)}</td>
                  <td>{d.rate_per_1000 === null ? "—" : fmt.decimal(d.rate_per_1000)}</td>
                  <td>{minutes(f?.target, m)}</td>
                  <td>{minutes(f?.arrival_median, m)}</td>
                  <td>{minutes(f?.arrival_p90, m)}</td>
                  <td>{minutes(f?.departure_median, m)}</td>
                  <td>{pct(f?.compliance_pct)}</td>
                  <td>
                    {d.frequency_level ?? "—"} × {d.coverage_level ?? "—"}
                  </td>
                  <td>
                    <PriorityTag p={d.priority} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

function MatrixTab({ analysis }: { analysis: SnacrAnalysis }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const levels = [1, 2, 3, 4, 5];
  return (
    <section className="card">
      <h3>{t("snacr.matrix.title")}</h3>
      <p className="muted">{t("snacr.matrix.intro")}</p>
      <div className="table-wrap">
        <table className="snacr-matrix">
          <caption className="visually-hidden">{t("snacr.matrix.title")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("snacr.matrix.corner")}</th>
              {levels.map((c) => (
                <th scope="col" key={c}>
                  {t("snacr.matrix.coverage", { level: c })}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...levels].reverse().map((f) => (
              <tr key={f}>
                <th scope="row">{t("snacr.matrix.frequency", { level: f })}</th>
                {levels.map((c) => {
                  const p = priorityOf(f, c);
                  return (
                    <td key={c} className={`snacr-matrix__cell snacr-matrix__cell--${p}`}>
                      {fmt.number(analysis.matrix[f - 1]?.[c - 1] ?? 0)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="snacr-legend">
        {(["high", "medium", "low"] as const).map((p) => (
          <li key={p}>
            <PriorityTag p={p} /> {t(`snacr.matrix.legend.${p}`)}
          </li>
        ))}
      </ul>
      <p className="muted">{t("snacr.matrix.levels")}</p>
    </section>
  );
}

function SeasonsTab({ analysis }: { analysis: SnacrAnalysis }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const [family, setFamily] = useState<Family>("fire");
  const id = useId();
  const months = analysis.month[family] ?? [];
  const grid = analysis.weekday_hour[family] ?? [];
  const max = Math.max(1, ...grid.flat());
  const subtypes = analysis.subtypes[family] ?? [];
  return (
    <>
      <div className="field field--inline">
        <label htmlFor={`${id}-f`}>{t("snacr.family.label")}</label>
        <select id={`${id}-f`} value={family} onChange={(e) => setFamily(e.target.value as Family)}>
          {FAMILIES.map((f) => (
            <option key={f} value={f}>
              {t(`snacr.family.${f}`)}
            </option>
          ))}
        </select>
      </div>
      <BarChart
        caption={t("snacr.seasons.months", { family: t(`snacr.family.${family}`) })}
        emptyText={t("snacr.empty")}
        bars={months.map((v, i) => ({ key: String(i), label: t(`snacr.month.${i + 1}`), value: v }))}
      />
      <section className="card">
        <h3>{t("snacr.seasons.hours")}</h3>
        <div className="table-wrap">
          <table className="snacr-heat">
            <caption className="visually-hidden">{t("snacr.seasons.hours")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("snacr.seasons.day")}</th>
                {Array.from({ length: 24 }, (_, h) => (
                  <th scope="col" key={h}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {grid.map((row, d) => (
                <tr key={d}>
                  <th scope="row">{t(`snacr.weekday.${d + 1}`)}</th>
                  {row.map((v, h) => (
                    <td
                      key={h}
                      className="snacr-heat__cell"
                      style={{ "--heat": String(v / max) } as CSSProperties}
                      title={fmt.number(v)}
                    >
                      <span className="visually-hidden">{fmt.number(v)}</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <BarChart
        caption={t("snacr.seasons.subtypes", { family: t(`snacr.family.${family}`) })}
        emptyText={t("snacr.empty")}
        bars={subtypes.slice(0, 12).map((s) => ({ key: s.subtype, label: <bdi>{s.subtype}</bdi>, value: s.rows }))}
      />
    </>
  );
}

function SpecialTab({ gouvernorat, canEdit }: { gouvernorat: number | null; canEdit: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const own = user?.identity.national ? null : (user?.identity.gouvernoratCode ?? null);
  const list = useQuery({ queryKey: snacrKeys.special(gouvernorat), queryFn: ({ signal }) => api.specialRisks(gouvernorat, signal) });
  const [form, setForm] = useState({ gouvernorat_code: own ?? gouvernorat ?? 11, hazard: "flood" as Hazard, probability: 3, gravity: 3, note: "" });
  const invalidate = () => void qc.invalidateQueries({ queryKey: snacrKeys.all });
  const save = useMutation({ mutationFn: () => api.saveSpecialRisk({ ...form, note: form.note || null }), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (r: SpecialRisk) => api.deleteSpecialRisk(r.id), onSuccess: invalidate });
  const edit = (r: SpecialRisk) =>
    setForm({ gouvernorat_code: r.gouvernorat_code, hazard: r.hazard, probability: r.probability, gravity: r.gravity, note: r.note ?? "" });
  const rows = [...(list.data ?? [])].sort((a, b) => b.probability * b.gravity - a.probability * a.gravity);
  return (
    <>
      <p className="muted">{t("snacr.special.intro")}</p>
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && (
        <div className="table-wrap">
          <table className="table table--compact">
            <caption>{t("snacr.special.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("snacr.col.gouvernorat")}</th>
                <th scope="col">{t("snacr.special.hazard")}</th>
                <th scope="col">{t("snacr.special.probability")}</th>
                <th scope="col">{t("snacr.special.gravity")}</th>
                <th scope="col">{t("snacr.col.priority")}</th>
                <th scope="col">{t("snacr.special.note")}</th>
                {canEdit && (
                  <th scope="col">
                    <span className="visually-hidden">{t("snacr.special.actions")}</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <th scope="row">{gouvernorats.nameOf(r.gouvernorat_code)}</th>
                  <td>
                    {t(`snacr.hazard.${r.hazard}`)} {r.simulated && <SimBadge />}
                  </td>
                  <td>{r.probability}</td>
                  <td>{r.gravity}</td>
                  <td>
                    <PriorityTag p={r.level} />
                  </td>
                  <td dir="auto">{r.note ?? "—"}</td>
                  {canEdit && (
                    <td className="actions">
                      <button type="button" className="btn btn--small" onClick={() => edit(r)}>
                        {t("snacr.special.edit")}
                      </button>
                      <button type="button" className="btn btn--small btn--danger" onClick={() => remove.mutate(r)}>
                        {t("snacr.special.delete")}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {canEdit && (
        <form
          className="card snacr-form"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <h3>{t("snacr.special.save")}</h3>
          <div className="form-grid">
            {own === null && (
              <div className="field">
                <label htmlFor={`${id}-g`}>{t("snacr.col.gouvernorat")}</label>
                <select id={`${id}-g`} value={form.gouvernorat_code} onChange={(e) => setForm((p) => ({ ...p, gouvernorat_code: Number(e.target.value) }))}>
                  {gouvernorats.list.map((g) => (
                    <option key={g.code} value={g.code}>
                      {gouvernorats.nameOf(g.code)}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="field">
              <label htmlFor={`${id}-h`}>{t("snacr.special.hazard")}</label>
              <select id={`${id}-h`} value={form.hazard} onChange={(e) => setForm((p) => ({ ...p, hazard: e.target.value as Hazard }))}>
                {HAZARDS.map((h) => (
                  <option key={h} value={h}>
                    {t(`snacr.hazard.${h}`)}
                  </option>
                ))}
              </select>
            </div>
            {(["probability", "gravity"] as const).map((k) => (
              <div className="field" key={k}>
                <label htmlFor={`${id}-${k}`}>{t(`snacr.special.${k}`)}</label>
                <input
                  id={`${id}-${k}`}
                  type="number"
                  min={1}
                  max={5}
                  value={form[k]}
                  onChange={(e) => setForm((p) => ({ ...p, [k]: Number(e.target.value) }))}
                />
              </div>
            ))}
            <div className="field">
              <label htmlFor={`${id}-n`}>{t("snacr.special.note")}</label>
              <input id={`${id}-n`} dir="auto" maxLength={500} value={form.note} onChange={(e) => setForm((p) => ({ ...p, note: e.target.value }))} />
            </div>
          </div>
          <p className="muted">
            {t("snacr.special.level")}: <PriorityTag p={priorityOf(form.probability, form.gravity)} />
          </p>
          {save.isError && (
            <p className="alert alert--error" role="alert">
              {t(errorMessageKey(save.error))}
            </p>
          )}
          <button type="submit" className="btn btn--primary" disabled={save.isPending}>
            {t("snacr.special.save")}
          </button>
        </form>
      )}
    </>
  );
}

function PlanTab({ gouvernorat, years }: { gouvernorat: number | null; years: readonly number[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const fmt = useFormat();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const roles = user?.identity.roles ?? [];
  const scope = user?.identity.national ? gouvernorat : (user?.identity.gouvernoratCode ?? null);
  const list = useQuery({ queryKey: snacrKeys.plans(gouvernorat), queryFn: ({ signal }) => api.snacrPlans(gouvernorat, signal) });
  const invalidate = () => void qc.invalidateQueries({ queryKey: snacrKeys.all });
  const create = useMutation({ mutationFn: () => api.createSnacrPlan(scope, years), onSuccess: invalidate });
  const approve = useMutation({ mutationFn: (id: string) => api.approveSnacrPlan(id), onSuccess: invalidate });
  const pdf = useMutation({ mutationFn: api.snacrPlanPdf, onSuccess: saveDownload });
  const error = create.error ?? approve.error ?? pdf.error;
  return (
    <>
      <p className="muted">{t("snacr.plan.intro")}</p>
      {canPlanSnacr(roles) && (
        <p>
          <button type="button" className="btn btn--primary" disabled={create.isPending} onClick={() => create.mutate()}>
            {scope === null ? t("snacr.plan.draftNational") : t("snacr.plan.draftRegional", { name: gouvernorats.nameOf(scope) })}
          </button>
        </p>
      )}
      {error && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(error))}
        </p>
      )}
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && list.data.length === 0 && <p className="card ops-empty">{t("snacr.plan.none")}</p>}
      {list.data && list.data.length > 0 && (
        <div className="table-wrap">
          <table className="table table--compact">
            <caption>{t("snacr.plan.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("snacr.plan.scope")}</th>
                <th scope="col">{t("snacr.plan.version")}</th>
                <th scope="col">{t("snacr.plan.status")}</th>
                <th scope="col">{t("snacr.plan.years")}</th>
                <th scope="col">{t("snacr.plan.objectives")}</th>
                <th scope="col">{t("snacr.plan.review")}</th>
                <th scope="col">{t("snacr.plan.valid")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("snacr.special.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((p) => (
                <tr key={p.id}>
                  <th scope="row">{p.gouvernorat_code === null ? t("snacr.plan.national") : gouvernorats.nameOf(p.gouvernorat_code)}</th>
                  <td>{p.version}</td>
                  <td>
                    {t(`snacr.plan.statuses.${p.status}`)} {p.simulated && <SimBadge />}
                    <span className="muted"> · {p.approved_by_name ?? p.created_by_name ?? ""}</span>
                  </td>
                  <td>{p.years.join("، ")}</td>
                  <td>{fmt.number(p.objectives)}</td>
                  <td>{p.review_due ? fmt.date(p.review_due) : "—"}</td>
                  <td>{p.valid_until ? fmt.date(p.valid_until) : "—"}</td>
                  <td className="actions">
                    <button type="button" className="btn btn--small" disabled={pdf.isPending} onClick={() => pdf.mutate(p)}>
                      {t("snacr.plan.pdf")}
                    </button>
                    {p.can_approve && (
                      <button type="button" className="btn btn--small btn--primary" disabled={approve.isPending} onClick={() => approve.mutate(p.id)}>
                        {t("snacr.plan.approve")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function AliasForm({ code, raw, onDone }: { code: number; raw: string; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const lang = useLanguage();
  const id = useId();
  const shapes = useDelegations(code);
  const units = (shapes.data?.features ?? []).map((f) => f.properties as AdminProps);
  const [target, setTarget] = useState<number | null>(null);
  const save = useMutation({
    mutationFn: () => api.addSnacrAlias({ gouvernorat_code: code, raw, delegation_id: target ?? 0 }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: snacrKeys.all });
      onDone();
    },
  });
  return (
    <form
      className="snacr-alias"
      onSubmit={(e) => {
        e.preventDefault();
        if (target !== null) save.mutate();
      }}
    >
      <label htmlFor={`${id}-d`} className="visually-hidden">
        {t("snacr.archive.aliasTo", { raw })}
      </label>
      <select id={`${id}-d`} value={target ?? ""} onChange={(e) => setTarget(e.target.value ? Number(e.target.value) : null)}>
        <option value="">{t("snacr.archive.pick")}</option>
        {units.map((u) => (
          <option key={String(u.id)} value={Number(u.id)}>
            {localizedName(u, lang)}
          </option>
        ))}
      </select>
      <button type="submit" className="btn btn--small btn--primary" disabled={target === null || save.isPending}>
        {t("snacr.archive.alias")}
      </button>
      {save.isError && (
        <span className="field__error" role="alert">
          {t(errorMessageKey(save.error))}
        </span>
      )}
    </form>
  );
}

function ArchiveTab({ overview }: { overview: SnacrOverview }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const [year, setYear] = useState(new Date().getFullYear() - 1);
  const [file, setFile] = useState<File | null>(null);
  const [aliasing, setAliasing] = useState<string | null>(null);
  const unmatched = useQuery({ queryKey: snacrKeys.unmatched, queryFn: ({ signal }) => api.snacrUnmatched(signal) });
  const invalidate = () => void qc.invalidateQueries({ queryKey: snacrKeys.all });
  const upload = useMutation({ mutationFn: () => api.importSnacr(year, file as File), onSuccess: invalidate });
  const simulate = useMutation({ mutationFn: () => api.simulateSnacr(year), onSuccess: invalidate });
  const live = useMutation({ mutationFn: () => api.liveSnacr(year), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (y: number) => api.deleteSnacrYear(y), onSuccess: invalidate });
  const error = upload.error ?? simulate.error ?? live.error ?? remove.error;
  return (
    <>
      <p className="muted">{t("snacr.archive.intro")}</p>
      <div className="table-wrap">
        <table className="table table--compact">
          <caption>{t("snacr.archive.title")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("snacr.archive.year")}</th>
              <th scope="col">{t("snacr.archive.source")}</th>
              <th scope="col">{t("snacr.archive.rows")}</th>
              <th scope="col">{t("snacr.archive.skipped")}</th>
              <th scope="col">{t("snacr.archive.by")}</th>
              {overview.can_import && (
                <th scope="col">
                  <span className="visually-hidden">{t("snacr.special.actions")}</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {overview.datasets.map((d) => (
              <tr key={d.id}>
                <th scope="row">{d.year}</th>
                <td>
                  {d.simulated ? (
                    <SimBadge />
                  ) : d.source === "live" ? (
                    t("snacr.archive.live")
                  ) : (
                    <bdi dir="ltr">{d.file_name ?? t("snacr.archive.office")}</bdi>
                  )}
                </td>
                <td>{fmt.number(d.rows)}</td>
                <td>{fmt.number(typeof d.quality.read === "number" ? d.quality.read - d.rows : 0)}</td>
                <td className="muted">
                  {d.imported_by_name ?? "—"} · {fmt.dateTime(d.imported_at)}
                </td>
                {overview.can_import && (
                  <td>
                    <button
                      type="button"
                      className="btn btn--small btn--danger"
                      onClick={() => {
                        if (window.confirm(t("snacr.archive.confirmDelete", { year: d.year }))) remove.mutate(d.year);
                      }}
                    >
                      {t("snacr.archive.delete")}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {overview.can_import && (
        <form
          className="card snacr-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (file) upload.mutate();
          }}
        >
          <h3>{t("snacr.archive.import")}</h3>
          <div className="form-grid">
            <div className="field">
              <label htmlFor={`${id}-y`}>{t("snacr.archive.year")}</label>
              <input id={`${id}-y`} type="number" min={2000} max={2100} value={year} onChange={(e) => setYear(Number(e.target.value))} />
            </div>
            <div className="field">
              <label htmlFor={`${id}-f`}>{t("snacr.archive.file")}</label>
              <input id={`${id}-f`} type="file" accept=".xlsx,.csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              <p className="field__hint">{t("snacr.archive.fileHint")}</p>
            </div>
          </div>
          {error && (
            <p className="alert alert--error" role="alert">
              {t(errorMessageKey(error))}
            </p>
          )}
          <div className="actions">
            <button type="submit" className="btn btn--primary" disabled={!file || upload.isPending}>
              {upload.isPending ? t("snacr.archive.reading") : t("snacr.archive.import")}
            </button>
            <button type="button" className="btn" disabled={simulate.isPending} onClick={() => simulate.mutate()}>
              {t("snacr.archive.simulate", { year })}
            </button>
            <button type="button" className="btn" disabled={live.isPending} onClick={() => live.mutate()}>
              {t("snacr.archive.fromRecords", { year })}
            </button>
          </div>
        </form>
      )}
      <section className="card">
        <h3>{t("snacr.archive.unmatched")}</h3>
        <p className="muted">{t("snacr.archive.unmatchedIntro")}</p>
        {unmatched.data && unmatched.data.length === 0 && <p>{t("snacr.archive.allMatched")}</p>}
        <ul className="snacr-unmatched">
          {(unmatched.data ?? []).map((u) => {
            const k = `${u.gouvernorat_code}:${u.raw}`;
            return (
              <li key={k}>
                <span>
                  <bdi>{u.raw}</bdi> · {gouvernorats.nameOf(u.gouvernorat_code)} · {t("snacr.archive.rowsCount", { count: u.rows })}
                </span>
                {overview.can_import &&
                  (aliasing === k ? (
                    <AliasForm code={u.gouvernorat_code} raw={u.raw} onDone={() => setAliasing(null)} />
                  ) : (
                    <button type="button" className="btn btn--small" onClick={() => setAliasing(k)}>
                      {t("snacr.archive.alias")}
                    </button>
                  ))}
              </li>
            );
          })}
        </ul>
      </section>
    </>
  );
}

function MethodTab({ overview }: { overview: SnacrOverview }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const m = overview.method;
  return (
    <>
      <section className="card">
        <h3>{t("snacr.method.title")}</h3>
        <ol className="snacr-steps">
          {(["zones", "rate", "arrival", "levels", "priority", "special", "cycle"] as const).map((k) => (
            <li key={k}>
              {t(`snacr.method.steps.${k}`, {
                urban: fmt.number(m.urban),
                periurban: fmt.number(m.periurban),
                goal: m.goal,
                review: m.review_months,
                validity: m.validity_years,
              })}
            </li>
          ))}
        </ol>
        <div className="table-wrap">
          <table className="table table--compact">
            <caption>{t("snacr.method.targets", { goal: m.goal })}</caption>
            <thead>
              <tr>
                <th scope="col">{t("snacr.family.label")}</th>
                {ZONES.map((z) => (
                  <th scope="col" key={z}>
                    {t(`snacr.zone.${z}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {FAMILIES.map((f) => (
                <tr key={f}>
                  <th scope="row">{t(`snacr.family.${f}`)}</th>
                  {ZONES.map((z) => (
                    <td key={z}>{minutes(m.targets[f][z], t("snacr.unit.min"))}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted">
          {t("snacr.method.settings")} <Link to="/settings">{t("snacr.method.settingsLink")}</Link>
        </p>
      </section>
      <section className="card">
        <h3>{t("snacr.method.references")}</h3>
        <ul className="snacr-references">
          {overview.references.map((r) => (
            <li key={r.code}>
              <strong>
                <bdi dir="ltr">{r.code}</bdi>
              </strong>{" "}
              —{" "}
              {r.url ? (
                <a href={r.url} target="_blank" rel="noopener noreferrer" lang="fr">
                  {r.title}
                </a>
              ) : (
                <span lang="fr">{r.title}</span>
              )}
              <span className="muted"> · {t(`snacr.use.${r.use}`, { defaultValue: r.use })}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

export function SnacrPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const [tab, setTab] = useState<Tab>("indicators");
  const [chosen, setChosen] = useState<number[] | null>(null);
  const [gouvernorat, setGouvernorat] = useState<number | null>(null);
  const national = user?.identity.national ?? false;
  const overview = useQuery({ queryKey: snacrKeys.overview, queryFn: ({ signal }) => api.snacr(signal) });
  const years = chosen ?? overview.data?.default_years ?? [];
  const analysis = useQuery({
    queryKey: snacrKeys.analysis(years, gouvernorat),
    queryFn: ({ signal }) => api.snacrAnalysis(years, gouvernorat, signal),
    enabled: overview.isSuccess && years.length > 0,
  });
  const data = overview.data;
  const available = (data?.datasets ?? []).map((d) => d.year).sort((a, b) => a - b);
  const tabs = TABS.filter((k) => k !== "archive" || data?.can_import || national);
  const canEdit = Boolean(user && ["ops_manager", "local_committee", "central_committee", "governor", "minister"].some((r) => user.identity.roles.includes(r)));
  const needsAnalysis = tab === "indicators" || tab === "matrix" || tab === "seasons";
  const toggleYear = (y: number, on: boolean) => {
    const next = on ? [...years, y] : years.filter((v) => v !== y);
    setChosen(next.sort((a, b) => a - b).slice(-5));
  };
  return (
    <div className="page snacr-page">
      <div className="page__head">
        <PageTitle icon="analytics" tone="purple">
          {t("snacr.title")}
        </PageTitle>
        {analysis.data?.simulated && <SimBadge />}
      </div>
      <p className="muted">{t("snacr.intro")}</p>
      {overview.isPending && <Loading />}
      {overview.isError && <ErrorBox error={overview.error} onRetry={() => void overview.refetch()} />}
      {data && (
        <>
          <div className="filters">
            <fieldset className="chips">
              <legend>{t("snacr.years")}</legend>
              {available.map((y) => (
                <label key={y} className="chip-toggle">
                  <input type="checkbox" checked={years.includes(y)} onChange={(e) => toggleYear(y, e.target.checked)} />
                  <span>
                    {y}
                    {data.datasets.find((d) => d.year === y)?.simulated ? " [SIM]" : ""}
                  </span>
                </label>
              ))}
            </fieldset>
            {national && (
              <div className="field field--inline">
                <label htmlFor={`${id}-g`}>{t("snacr.col.gouvernorat")}</label>
                <select id={`${id}-g`} value={gouvernorat ?? ""} onChange={(e) => setGouvernorat(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">{t("snacr.national")}</option>
                  {gouvernorats.list.map((g) => (
                    <option key={g.code} value={g.code}>
                      {gouvernorats.nameOf(g.code)}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <div role="tablist" aria-label={t("snacr.tabs.label")} className="tabs">
            {tabs.map((k) => (
              <button
                key={k}
                type="button"
                role="tab"
                aria-selected={tab === k}
                className={`tabs__tab${tab === k ? " tabs__tab--active" : ""}`}
                onClick={() => setTab(k)}
              >
                {t(`snacr.tabs.${k}`)}
              </button>
            ))}
          </div>
          {needsAnalysis && years.length === 0 && <p className="card ops-empty">{t("snacr.noData")}</p>}
          {needsAnalysis && analysis.isFetching && !analysis.data && <Loading />}
          {needsAnalysis && analysis.isError && !(isApiError(analysis.error) && analysis.error.status === 404) && (
            <ErrorBox error={analysis.error} onRetry={() => void analysis.refetch()} />
          )}
          {needsAnalysis && analysis.data && tab === "indicators" && <IndicatorsTab analysis={analysis.data} gouvernorat={gouvernorat} />}
          {needsAnalysis && analysis.data && tab === "matrix" && <MatrixTab analysis={analysis.data} />}
          {needsAnalysis && analysis.data && tab === "seasons" && <SeasonsTab analysis={analysis.data} />}
          {tab === "special" && <SpecialTab gouvernorat={gouvernorat} canEdit={canEdit} />}
          {tab === "plan" && <PlanTab gouvernorat={gouvernorat} years={years} />}
          {tab === "archive" && <ArchiveTab overview={data} />}
          {tab === "method" && <MethodTab overview={data} />}
        </>
      )}
    </div>
  );
}
