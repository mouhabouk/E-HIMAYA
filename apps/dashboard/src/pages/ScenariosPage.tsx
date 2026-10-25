import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { TimeChart, type ChartSeries } from "../components/charts/TimeChart";
import { ErrorBox, Loading } from "../components/Feedback";
import { CategorySelect, LoadMore, MutationError } from "../components/Phase8Bits";
import { SimTag } from "../components/StreamBits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { localized } from "../lib/localized";
import { RESOURCE_KINDS } from "../lib/opsTypes";
import { p8Keys } from "../lib/phase8Api";
import {
  SCENARIO_WEATHERS,
  type Percentiles,
  type ScenarioBody,
  type ScenarioRun,
  type ScenarioWeather,
} from "../lib/phase8Types";
import { canCreateReports } from "../lib/roles";
import type { Category } from "../lib/types";
import { AnalyticsTabs } from "./AnalyticsPage";
import { PageTitle } from "../components/PageTitle";

const FACTOR_MIN = 1;
const FACTOR_MAX = 10;
const HORIZON_MIN = 6;
const HORIZON_MAX = 72;
const MAX_UNAVAILABLE = 200;

interface FormState {
  name: string;
  gouvernorats: number[];
  category: Category;
  factor: string;
  horizon: string;
  weather: ScenarioWeather;
  unavailable: Record<string, string>;
}

export function validateScenario(f: FormState): { body: ScenarioBody | null; errors: Partial<Record<keyof FormState, true>> } {
  const errors: Partial<Record<keyof FormState, true>> = {};
  const factor = Number(f.factor);
  const horizon = Number(f.horizon);
  if (!f.name.trim()) errors.name = true;
  if (f.gouvernorats.length === 0) errors.gouvernorats = true;
  if (!Number.isFinite(factor) || factor < FACTOR_MIN || factor > FACTOR_MAX) errors.factor = true;
  if (!Number.isInteger(horizon) || horizon < HORIZON_MIN || horizon > HORIZON_MAX) errors.horizon = true;
  const unavailable: Record<string, number> = {};
  for (const [kind, raw] of Object.entries(f.unavailable)) {
    if (raw.trim() === "") continue;
    const n = Number(raw);
    if (!Number.isInteger(n) || n < 0 || n > MAX_UNAVAILABLE) errors.unavailable = true;
    else if (n > 0) unavailable[kind] = n;
  }
  if (Object.keys(errors).length > 0) return { body: null, errors };
  return {
    body: {
      name: f.name.trim(),
      gouvernorats: f.gouvernorats,
      category: f.category,
      demand_factor: factor,
      unavailable_resources: unavailable,
      horizon_hours: horizon,
      weather: f.weather,
    },
    errors,
  };
}

function ScenarioForm() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const base = useId();
  const own = user?.identity.gouvernoratCode ?? null;
  const national = user?.identity.national ?? false;
  const [form, setForm] = useState<FormState>({
    name: "",
    gouvernorats: own !== null && !national ? [own] : [],
    category: "fire",
    factor: "1.5",
    horizon: "24",
    weather: "as_forecast",
    unavailable: {},
  });
  const [touched, setTouched] = useState(false);
  const { body, errors } = validateScenario(form);
  const run = useMutation({
    mutationFn: (b: ScenarioBody) => api.runScenario(b),
    onSuccess: (r) => {
      qc.setQueryData(p8Keys.scenario(r.id), r);
      void qc.invalidateQueries({ queryKey: p8Keys.scenariosAll });
      void navigate(`/analytics/scenarios/${encodeURIComponent(r.id)}`);
    },
  });
  const set = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTouched(true);
    if (body) run.mutate(body);
  };
  const err = (k: keyof FormState) => touched && errors[k];
  const options = national ? gouvernorats.list.map((g) => g.code) : own !== null ? [own] : [];
  return (
    <form className="card ops-form scenario-form" onSubmit={submit} noValidate aria-labelledby={`${base}-h`}>
      <h2 id={`${base}-h`}>{t("scenarios.form.title")}</h2>
      <div className={`field${err("name") ? " field--invalid" : ""}`}>
        <label htmlFor={`${base}-name`}>{t("scenarios.form.name")}</label>
        <input
          id={`${base}-name`}
          dir="auto"
          maxLength={120}
          value={form.name}
          aria-invalid={err("name") ? true : undefined}
          onChange={(e) => set({ name: e.target.value })}
        />
        {err("name") && <p className="field__error">{t("scenarios.form.nameRequired")}</p>}
      </div>
      <fieldset className={`chips gouvernorat-picker${err("gouvernorats") ? " field--invalid" : ""}`}>
        <legend>{t("scenarios.form.gouvernorats")}</legend>
        {options.map((code) => (
          <label key={code} className="chip-toggle">
            <input
              type="checkbox"
              checked={form.gouvernorats.includes(code)}
              disabled={!national}
              onChange={(e) =>
                set({
                  gouvernorats: e.target.checked
                    ? [...form.gouvernorats, code].sort((a, b) => a - b)
                    : form.gouvernorats.filter((c) => c !== code),
                })
              }
            />
            <span>{gouvernorats.nameOf(code)}</span>
          </label>
        ))}
        {err("gouvernorats") && <p className="field__error">{t("scenarios.form.gouvernoratsRequired")}</p>}
      </fieldset>
      <div className="fields-row">
        <CategorySelect value={form.category} onChange={(c) => set({ category: (c ?? "fire") as Category })} label={t("scenarios.form.category")} />
        <div className={`field field--number${err("factor") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-factor`}>{t("scenarios.form.factor")}</label>
          <input
            id={`${base}-factor`}
            type="number"
            inputMode="decimal"
            min={FACTOR_MIN}
            max={FACTOR_MAX}
            step={0.1}
            value={form.factor}
            aria-invalid={err("factor") ? true : undefined}
            aria-describedby={`${base}-factor-hint`}
            onChange={(e) => set({ factor: e.target.value })}
          />
          <p id={`${base}-factor-hint`} className="muted">
            {t("scenarios.form.factorHint", { min: FACTOR_MIN, max: FACTOR_MAX })}
          </p>
        </div>
        <div className={`field field--number${err("horizon") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-horizon`}>{t("scenarios.form.horizon")}</label>
          <input
            id={`${base}-horizon`}
            type="number"
            min={HORIZON_MIN}
            max={HORIZON_MAX}
            step={1}
            value={form.horizon}
            aria-invalid={err("horizon") ? true : undefined}
            aria-describedby={`${base}-horizon-hint`}
            onChange={(e) => set({ horizon: e.target.value })}
          />
          <p id={`${base}-horizon-hint`} className="muted">
            {t("scenarios.form.horizonHint", { min: HORIZON_MIN, max: HORIZON_MAX })}
          </p>
        </div>
      </div>
      <fieldset className="segmented">
        <legend>{t("scenarios.form.weather")}</legend>
        {SCENARIO_WEATHERS.map((w) => (
          <label key={w} className="segmented__item">
            <input type="radio" name={`${base}-w`} checked={form.weather === w} onChange={() => set({ weather: w })} />
            <span>{t(`scenarios.weather.${w}`)}</span>
          </label>
        ))}
      </fieldset>
      <fieldset className={`unavailable${err("unavailable") ? " field--invalid" : ""}`}>
        <legend>{t("scenarios.form.unavailable")}</legend>
        <p className="muted">{t("scenarios.form.unavailableHint")}</p>
        <div className="unavailable__grid">
          {RESOURCE_KINDS.map((k) => (
            <div key={k} className="field field--number">
              <label htmlFor={`${base}-u-${k}`}>{t(`resources.kind.${k}`)}</label>
              <input
                id={`${base}-u-${k}`}
                type="number"
                min={0}
                max={MAX_UNAVAILABLE}
                step={1}
                value={form.unavailable[k] ?? ""}
                onChange={(e) => set({ unavailable: { ...form.unavailable, [k]: e.target.value } })}
              />
            </div>
          ))}
        </div>
      </fieldset>
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={run.isPending} aria-busy={run.isPending}>
          {run.isPending ? t("scenarios.form.running") : t("scenarios.form.run")}
        </button>
      </div>
      {run.isError && <MutationError error={run.error} />}
    </form>
  );
}

function ScenarioHistory() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const query = useInfiniteQuery({
    queryKey: p8Keys.scenariosAll,
    queryFn: ({ pageParam, signal }) => api.scenarios({ cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const rows = query.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <section className="card" aria-labelledby="scenario-history">
      <h2 id="scenario-history">{t("scenarios.history")}</h2>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && rows.length === 0 && <p className="muted">{t("scenarios.none")}</p>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("scenarios.form.name")}</th>
                <th scope="col">{t("scenarios.form.category")}</th>
                <th scope="col">{t("scenarios.form.factor")}</th>
                <th scope="col">{t("scenarios.form.horizon")}</th>
                <th scope="col">{t("scenarios.overloadCount")}</th>
                <th scope="col">{t("scenarios.createdAt")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <th scope="row">
                    <Link to={`/analytics/scenarios/${encodeURIComponent(r.id)}`} dir="auto">
                      {r.name}
                    </Link>
                    {r.simulated && <SimTag />}
                  </th>
                  <td>{t(`category.${r.params.category}`)}</td>
                  <td>×{fmt.decimal(r.params.demand_factor)}</td>
                  <td>{t("scenarios.hours", { n: r.params.horizon_hours })}</td>
                  <td>{r.result ? fmt.number(r.result.overload_hours.length) : "—"}</td>
                  <td>{fmt.dateTime(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <LoadMore hasNext={query.hasNextPage} loading={query.isFetchingNextPage} onMore={() => void query.fetchNextPage()} />
    </section>
  );
}

/** What-if form and the history of runs (FR-C-12). */
export function ScenariosPage() {
  const { t } = useTranslation();
  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="analytics" tone="navy">{t("scenarios.title")}</PageTitle>
      </div>
      <AnalyticsTabs />
      <p className="muted">{t("scenarios.intro")}</p>
      <ScenarioForm />
      <ScenarioHistory />
    </div>
  );
}

const range = (p: Percentiles, f: (n: number) => string) => `${f(p.p50)} (${f(p.p10)} – ${f(p.p90)})`;

function ScenarioResultView({ run }: { run: ScenarioRun }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const { user } = useAuth();
  const result = run.result;
  const charts = useMemo(() => {
    const hours = result?.hours ?? [];
    const x = hours.map((h) => h.hour);
    const labels = hours.map((h) => (h.at ? `+${h.hour} h · ${fmt.time(h.at)}` : `+${h.hour} h`));
    const highlight = hours.map((h) => h.overloaded);
    const band = (key: "demand" | "wait_minutes" | "utilisation", label: string, scale = 1): ChartSeries[] => [
      { key: `${key}-p50`, label: `${label} — ${t("scenarios.p50")}`, values: hours.map((h) => h[key].p50 * scale), tone: "primary" },
      { key: `${key}-p10`, label: `${label} — ${t("scenarios.p10")}`, values: hours.map((h) => h[key].p10 * scale), tone: "primary", edge: true },
      { key: `${key}-p90`, label: `${label} — ${t("scenarios.p90")}`, values: hours.map((h) => h[key].p90 * scale), tone: "primary", edge: true },
    ];
    const capacity = result?.summary?.capacity;
    const demand = band("demand", t("scenarios.demand"));
    if (capacity !== undefined) {
      demand.push({ key: "capacity", label: t("scenarios.capacity"), values: hours.map(() => capacity), tone: "capacity", dashed: true });
    }
    return {
      x,
      labels,
      highlight,
      demand,
      wait: band("wait_minutes", t("scenarios.wait")),
      utilisation: band("utilisation", t("scenarios.utilisation"), 100),
    };
  }, [result?.hours, result?.summary?.capacity, t, fmt]);
  const bandDef = [{ low: 1, high: 2, label: t("scenarios.band") }];
  const overloadText =
    result && result.overload_hours.length > 0
      ? t("scenarios.overloadHours", { hours: result.overload_hours.map((h) => `+${h} h`).join(t("common.listSeparator")) })
      : t("scenarios.noOverload");
  const reportable = canCreateReports(user?.identity.roles ?? []);
  const p = run.params;
  return (
    <>
      <div className="alert alert--warn scenario-disclaimer" role="note">
        <p>
          <strong>{t("scenarios.disclaimerTitle")}</strong> {localized(result?.disclaimer, lang) || t("scenarios.disclaimerFallback")}
        </p>
        {result?.calibration_note && <p>{localized(result.calibration_note, lang)}</p>}
        {result?.confidence === "low" && (
          <>
            <p>
              <strong>{t("scenarios.lowConfidence")}</strong>
            </p>
            <ul>
              {(result.confidence_reasons ?? []).map((r, i) => (
                <li key={i}>{localized(r, lang)}</li>
              ))}
            </ul>
          </>
        )}
      </div>
      <dl className="fields fields--compact">
        <dt>{t("scenarios.form.gouvernorats")}</dt>
        <dd>{p.gouvernorats.map((c) => gouvernorats.nameOf(c)).join(t("common.listSeparator"))}</dd>
        <dt>{t("scenarios.form.category")}</dt>
        <dd>{t(`category.${p.category}`)}</dd>
        <dt>{t("scenarios.form.factor")}</dt>
        <dd>×{fmt.decimal(p.demand_factor)}</dd>
        <dt>{t("scenarios.form.horizon")}</dt>
        <dd>{t("scenarios.hours", { n: p.horizon_hours })}</dd>
        <dt>{t("scenarios.form.weather")}</dt>
        <dd>{t(`scenarios.weather.${p.weather}`)}</dd>
        <dt>{t("scenarios.form.unavailable")}</dt>
        <dd>
          {Array.isArray(p.unavailable_resources)
            ? t("scenarios.resourceCount", { n: p.unavailable_resources.length })
            : Object.entries(p.unavailable_resources)
                .map(([k, n]) => `${t(`resources.kind.${k}`, { defaultValue: k })} × ${fmt.number(n)}`)
                .join(t("common.listSeparator")) || t("common.none")}
        </dd>
        <dt>{t("scenarios.seedRuns")}</dt>
        <dd className="code" dir="ltr">
          seed {run.seed} · {fmt.number(run.runs)} runs
        </dd>
      </dl>
      {run.status === "failed" || !result ? (
        <p className="alert alert--error">{t("scenarios.failed")}</p>
      ) : (
        <>
          {result.summary && (
            <dl className="kpis">
              <div className="kpi">
                <dt className="kpi__label">{t("scenarios.totalReports")}</dt>
                <dd className="kpi__value">{range(result.summary.total_reports, (n) => fmt.decimal(n))}</dd>
              </div>
              <div className="kpi">
                <dt className="kpi__label">{t("scenarios.capacity")}</dt>
                <dd className="kpi__value">{fmt.number(result.summary.capacity)}</dd>
              </div>
              <div className="kpi">
                <dt className="kpi__label">{t("scenarios.wait")}</dt>
                <dd className="kpi__value">{range(result.summary.wait_minutes, (n) => t("scenarios.minutes", { n: fmt.decimal(n) }))}</dd>
              </div>
              <div className="kpi">
                <dt className="kpi__label">{t("scenarios.utilisation")}</dt>
                <dd className="kpi__value">{range(result.summary.utilisation, (n) => fmt.percent(n))}</dd>
              </div>
            </dl>
          )}
          <p className={result.overload_hours.length > 0 ? "alert alert--error" : "alert alert--ok"} role="status">
            {overloadText}
          </p>
          <TimeChart
            caption={t("scenarios.chart.demand")}
            x={charts.x}
            xKind="index"
            xLabels={charts.labels}
            xHeader={t("scenarios.hour")}
            series={charts.demand}
            bands={bandDef}
            highlight={charts.highlight}
            highlightLabel={t("scenarios.overloaded")}
            formatValue={(n) => fmt.decimal(n)}
            emptyText={t("analytics.noData")}
          />
          <TimeChart
            caption={t("scenarios.chart.wait")}
            x={charts.x}
            xKind="index"
            xLabels={charts.labels}
            xHeader={t("scenarios.hour")}
            series={charts.wait}
            bands={bandDef}
            highlight={charts.highlight}
            highlightLabel={t("scenarios.overloaded")}
            formatValue={(n) => t("scenarios.minutes", { n: fmt.decimal(n) })}
            emptyText={t("analytics.noData")}
          />
          <TimeChart
            caption={t("scenarios.chart.utilisation")}
            x={charts.x}
            xKind="index"
            xLabels={charts.labels}
            xHeader={t("scenarios.hour")}
            series={charts.utilisation}
            bands={bandDef}
            highlight={charts.highlight}
            highlightLabel={t("scenarios.overloaded")}
            formatValue={(n) => fmt.percent(n / 100)}
            emptyText={t("analytics.noData")}
          />
          <section className="card assumptions" aria-labelledby="scenario-assumptions">
            <h2 id="scenario-assumptions">{t("scenarios.assumptions")}</h2>
            <ul>
              {result.assumptions.map((a, i) => (
                <li key={i}>{localized(a, lang)}</li>
              ))}
            </ul>
            {result.provenance && (
              <p className="muted">
                {t("scenarios.provenance", {
                  from: result.provenance.history_from ? fmt.date(result.provenance.history_from) : "—",
                  to: result.provenance.history_to ? fmt.date(result.provenance.history_to) : "—",
                  events: fmt.number(result.provenance.events ?? 0),
                  days: fmt.number(result.provenance.days_covered ?? 0),
                })}
              </p>
            )}
          </section>
        </>
      )}
      {reportable && result && (
        <p>
          <Link
            className="btn"
            to={`/reports-library?new=1&kind=scenario&scenario=${encodeURIComponent(run.id)}&title=${encodeURIComponent(run.name)}`}
          >
            {t("scenarios.toReport")}
          </Link>
        </p>
      )}
    </>
  );
}

/** One run: percentile bands, overload hours highlighted, assumptions and disclaimer always visible. */
export function ScenarioDetailPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { id = "" } = useParams();
  const query = useQuery({ queryKey: p8Keys.scenario(id), queryFn: ({ signal }) => api.scenario(id, signal) });
  return (
    <article className="page" aria-labelledby="scenario-title">
      <p>
        <Link to="/analytics/scenarios">{t("scenarios.back")}</Link>
      </p>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && (
        <>
          <div className="page__head">
            <PageTitle icon="analytics" tone="navy" id="scenario-title" dir="auto">
              {t("scenarios.resultTitle", { name: query.data.name })}
            </PageTitle>
            {query.data.simulated && <SimTag />}
          </div>
          <ScenarioResultView run={query.data} />
        </>
      )}
    </article>
  );
}
