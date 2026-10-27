// covers: phase L1b (docs/phase-l/design-l1b-coastal.md §4): the coastal safety dashboard of the room.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useCallback, useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { BarChart } from "../components/BarChart";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import type { HeatPoint, MapPoi } from "../components/MapView";
import { PageTitle } from "../components/PageTitle";
import { SimTag, SimulationBand } from "../components/StreamBits";
import { useAuth } from "../context/auth";
import { useLiveEvents } from "../context/live";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import {
  FACTOR_CODES,
  levelKey,
  NUMERIC_RULES,
  RISK_COLOURS,
  RISK_LEVELS,
  rulesProblem,
  waveBands,
  type Attribution,
  type Beach,
  type CoastalAlert,
  type Factor,
  type OverviewFilters,
  type RiskLevel,
  type WaveBand,
} from "../lib/coastal";
import { coastalKeys } from "../lib/coastalApi";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { LAYER_ICON_PATHS } from "../lib/layers";
import { saveDownload } from "../lib/layersApi";
import { initialBoundsFor } from "../lib/mapStyle";
import { canEditCoastalRules } from "../lib/roles";
import { directionOf } from "../i18n";

const FORECAST_DAYS = 4;
const REASON_MIN = 3;
const LEVEL_TONE: Record<RiskLevel | "unknown", string> = {
  red: "tone-red",
  yellow: "tone-amber",
  green: "tone-green",
  unknown: "tone-slate",
};
type HeatMode = "none" | "risk" | "drownings";

/** Today and the next three days, in Tunis time (UTC+1, no daylight saving). */
function forecastDays(now = new Date()): string[] {
  const tunis = new Date(now.getTime() + 3_600_000);
  return Array.from({ length: FORECAST_DAYS }, (_, i) => {
    const d = new Date(Date.UTC(tunis.getUTCFullYear(), tunis.getUTCMonth(), tunis.getUTCDate() + i));
    return d.toISOString().slice(0, 10);
  });
}

export function LevelPill({ level }: { level: RiskLevel | null | undefined }) {
  const { t } = useTranslation();
  const key = levelKey(level);
  return <span className={`pill ${LEVEL_TONE[key]}`}>{t(`coastal.level.${key}`)}</span>;
}

/** One reason of a score, in words ("Waves 2.8 m: +55"). */
function useFactorText() {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (f: Factor) => {
    const known = (FACTOR_CODES as readonly string[]).includes(f.code);
    const value = typeof f.value === "number" ? fmt.decimal(f.value) : "";
    const label = known ? t(`coastal.factor.${f.code}`, { value }) : f.code;
    return `${label}: +${fmt.number(f.points)}`;
  };
}

function AttributionLines({ items }: { items: Attribution[] }) {
  const { t } = useTranslation();
  return (
    <div className="weather-attribution">
      {items.map((a, i) =>
        typeof a === "string" ? (
          <p key={i}>
            <SimTag label={t("coastal.simulated")} /> {a}
          </p>
        ) : (
          <p key={i}>
            {t("weather.attribution")}{" "}
            <a href={a.url} target="_blank" rel="noopener noreferrer" dir="ltr">
              {a.text}
            </a>{" "}
            ({a.licence})
          </p>
        ),
      )}
    </div>
  );
}

function Filters({
  value,
  onChange,
  national,
  classifications,
}: {
  value: OverviewFilters;
  onChange: (f: OverviewFilters) => void;
  national: boolean;
  classifications: string[];
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const days = useMemo(() => forecastDays(), []);
  return (
    <form className="filters card" aria-label={t("coastal.filters")} onSubmit={(e) => e.preventDefault()}>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${id}-day`}>{t("coastal.day")}</label>
          <select
            id={`${id}-day`}
            value={value.day ?? days[0]}
            onChange={(e) => onChange({ ...value, day: e.target.value === days[0] ? undefined : e.target.value })}
          >
            {days.map((d, i) => (
              <option key={d} value={d}>
                {i === 0 ? t("coastal.today") : fmt.date(`${d}T12:00:00Z`)}
              </option>
            ))}
          </select>
        </div>
        {national && (
          <div className="field">
            <label htmlFor={`${id}-gov`}>{t("coastal.gouvernorat")}</label>
            <select
              id={`${id}-gov`}
              value={value.gouvernorat ?? ""}
              onChange={(e) => onChange({ ...value, gouvernorat: e.target.value ? Number(e.target.value) : undefined })}
            >
              <option value="">{t("coastal.allGouvernorats")}</option>
              {gouvernorats.list.map((g) => (
                <option key={g.code} value={g.code}>
                  {gouvernorats.nameOf(g.code)}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="field">
          <label htmlFor={`${id}-class`}>{t("coastal.card.classification")}</label>
          <select
            id={`${id}-class`}
            value={value.classification ?? ""}
            onChange={(e) => onChange({ ...value, classification: e.target.value || undefined })}
          >
            <option value="">{t("coastal.all")}</option>
            {classifications.map((c) => (
              <option key={c} value={c}>
                {t(`coastal.classification.${c}`, { defaultValue: c })}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-guarded`}>{t("coastal.card.guarded")}</label>
          <select
            id={`${id}-guarded`}
            value={value.guarded === undefined ? "" : String(value.guarded)}
            onChange={(e) => onChange({ ...value, guarded: e.target.value === "" ? undefined : e.target.value === "true" })}
          >
            <option value="">{t("coastal.all")}</option>
            <option value="true">{t("coastal.guarded")}</option>
            <option value="false">{t("coastal.unguarded")}</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-level`}>{t("coastal.levelLabel")}</label>
          <select
            id={`${id}-level`}
            value={value.level ?? ""}
            onChange={(e) => onChange({ ...value, level: (e.target.value || undefined) as RiskLevel | undefined })}
          >
            <option value="">{t("coastal.all")}</option>
            {RISK_LEVELS.map((l) => (
              <option key={l} value={l}>
                {t(`coastal.level.${l}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
    </form>
  );
}

function AlertsCentre({ day, onOpen }: { day: string | undefined; onOpen: (id: string) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const alerts = useQuery({ queryKey: coastalKeys.alerts(day), queryFn: ({ signal }) => api.coastalAlerts(day, signal) });
  const ack = useMutation({
    mutationFn: (id: string) => api.ackCoastalAlert(id),
    onSuccess: (row) => {
      qc.setQueryData<CoastalAlert[]>(coastalKeys.alerts(day), (rows) => rows?.map((r) => (r.id === row.id ? row : r)));
    },
  });
  const open = (alerts.data ?? []).filter((a) => !a.acked_at).length;
  return (
    <section className="card" aria-labelledby="coastal-alerts">
      <h2 id="coastal-alerts">
        {t("coastal.alerts.title")} <span className="chip">{fmt.number(open)}</span>
      </h2>
      <p className="muted">{t("coastal.alerts.note")}</p>
      {alerts.isLoading && <Loading />}
      {alerts.isError && <ErrorBox error={alerts.error} onRetry={() => void alerts.refetch()} />}
      {ack.isError && (
        <p role="alert" className="alert alert--error">
          {t(errorMessageKey(ack.error))}
        </p>
      )}
      {alerts.data && alerts.data.length === 0 && <p className="muted">{t("coastal.alerts.none")}</p>}
      <ul className="coastal-alerts">
        {(alerts.data ?? []).map((a) => (
          <li key={a.id} className={a.acked_at ? "coastal-alert coastal-alert--acked" : "coastal-alert"}>
            <LevelPill level={a.level} />
            <button type="button" className="link" onClick={() => onOpen(a.feature_id)} dir="auto">
              {a.name}
            </button>
            <span className="muted">
              {t("coastal.score", { score: fmt.number(a.score) })}
              {a.gouvernorat_code ? ` · ${gouvernorats.nameOf(a.gouvernorat_code)}` : ""}
              {a.previous_level ? ` · ${t("coastal.alerts.was", { level: t(`coastal.level.${a.previous_level}`) })}` : ""}
            </span>
            {a.simulated && <SimTag label={t("coastal.simulated")} />}
            {a.acked_at ? (
              <span className="muted">
                {t("coastal.alerts.acked", { name: a.acked_by_name ?? "—", at: fmt.time(a.acked_at) })}
              </span>
            ) : (
              <button
                type="button"
                className="btn btn--small"
                disabled={ack.isPending}
                onClick={() => ack.mutate(a.id)}
              >
                {t("coastal.alerts.ack")}
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function BeachTable({ caption, beaches, onOpen }: { caption: string; beaches: Beach[]; onOpen: (id: string) => void }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const reason = useFactorText();
  return (
    <div className="table-wrap card">
      <table className="table table--compact">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">{t("coastal.beach")}</th>
            <th scope="col">{t("coastal.levelLabel")}</th>
            <th scope="col">{t("coastal.gouvernorat")}</th>
            <th scope="col">{t("coastal.why")}</th>
            <th scope="col">{t("coastal.present")}</th>
          </tr>
        </thead>
        <tbody>
          {beaches.length === 0 && (
            <tr>
              <td colSpan={5} className="muted">
                {t("coastal.noBeaches")}
              </td>
            </tr>
          )}
          {beaches.map((b) => (
            <tr key={b.id}>
              <th scope="row">
                <button type="button" className="link" onClick={() => onOpen(b.id)} dir="auto">
                  {b.name}
                </button>
              </th>
              <td>
                <LevelPill level={b.level} /> {b.score !== null && <span dir="ltr">{fmt.number(b.score)}</span>}
              </td>
              <td>{gouvernorats.nameOf(b.gouvernorat_code) ?? "—"}</td>
              <td>{b.factors.length ? b.factors.map(reason).join(t("common.listSeparator")) : "—"}</td>
              <td>{b.present === null ? "—" : fmt.number(b.present)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function cardValue(t: (k: string, o?: Record<string, unknown>) => string, field: string, value: unknown): string {
  if (typeof value !== "string" && typeof value !== "number" && typeof value !== "boolean") return "—";
  const text = String(value).trim();
  if (!text) return "—";
  const lower = text.toLowerCase();
  if (["true", "yes", "oui", "1"].includes(lower)) return t("coastal.yes");
  if (["false", "no", "non", "0"].includes(lower)) return t("coastal.no");
  if (field === "classification") return t(`coastal.classification.${lower}`, { defaultValue: text });
  return t(`coastal.value.${lower}`, { defaultValue: text });
}

function BeachPanel({ id, onClose }: { id: string; onClose: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const reason = useFactorText();
  const detail = useQuery({ queryKey: coastalKeys.beach(id), queryFn: ({ signal }) => api.coastalBeach(id, signal) });
  const d = detail.data;
  return (
    <section className="card coastal-beach" aria-labelledby="coastal-beach-title">
      <div className="coastal-beach__head">
        <h2 id="coastal-beach-title" dir="auto">
          {d ? d.beach.name : t("coastal.beach")}
        </h2>
        <button type="button" className="btn btn--small" onClick={onClose}>
          {t("common.close")}
        </button>
      </div>
      {detail.isLoading && <Loading />}
      {detail.isError && <ErrorBox error={detail.error} onRetry={() => void detail.refetch()} />}
      {d && (
        <>
          <p>
            <LevelPill level={d.beach.level} />{" "}
            {d.beach.score !== null && t("coastal.score", { score: fmt.number(d.beach.score) })}
            {d.beach.gouvernorat_code ? ` · ${gouvernorats.nameOf(d.beach.gouvernorat_code)}` : ""}
            {d.beach.present !== null && ` · ${t("coastal.presentNow", { count: d.beach.present })}`}
            {d.simulated && (
              <>
                {" "}
                <SimTag label={t("coastal.simulated")} />
              </>
            )}
          </p>
          <div className="table-wrap">
            <table className="table table--compact">
              <caption>{t("coastal.days")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("coastal.day")}</th>
                  <th scope="col">{t("coastal.levelLabel")}</th>
                  <th scope="col">{t("coastal.waves")}</th>
                  <th scope="col">{t("coastal.seaTemp")}</th>
                  <th scope="col">{t("coastal.why")}</th>
                </tr>
              </thead>
              <tbody>
                {d.days.map((day) => (
                  <tr key={day.day}>
                    <th scope="row">{fmt.date(`${day.day}T12:00:00Z`)}</th>
                    <td>
                      <LevelPill level={day.level} /> <span dir="ltr">{fmt.number(day.score)}</span>
                    </td>
                    <td dir="ltr">{day.wave_height_m === null ? "—" : `${fmt.decimal(day.wave_height_m)} m`}</td>
                    <td dir="ltr">{day.sea_temp_c === null ? "—" : `${fmt.decimal(day.sea_temp_c)} °C`}</td>
                    <td>{day.factors.length ? day.factors.map(reason).join(t("common.listSeparator")) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3>{t("coastal.card.title")}</h3>
          <dl className="coastal-card">
            {Object.entries(d.card).map(([field, value]) => {
              const src = d.sources[field];
              return (
                <div key={field}>
                  <dt>{t(`coastal.card.${field}`, { defaultValue: field })}</dt>
                  <dd>
                    {cardValue(t, field, value)}
                    {src?.source && (
                      <span className="muted">
                        {" "}
                        ({t("coastal.source", { source: src.source, date: src.date ?? "—" })})
                      </span>
                    )}
                  </dd>
                </div>
              );
            })}
            {d.length_m !== null && (
              <div>
                <dt>{t("coastal.length")}</dt>
                <dd dir="ltr">{fmt.number(Math.round(d.length_m))} m</dd>
              </div>
            )}
          </dl>
          {Object.keys(d.card).length === 0 && <p className="muted">{t("coastal.card.empty")}</p>}
          <AttributionLines items={d.attribution} />
        </>
      )}
    </section>
  );
}

function RulesEditor() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const qc = useQueryClient();
  const id = useId();
  const editable = user ? canEditCoastalRules(user.identity) : false;
  const settings = useQuery({ queryKey: coastalKeys.settings, queryFn: ({ signal }) => api.coastalSettings(signal) });
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const save = useMutation({
    mutationFn: (rules: Record<string, unknown>) => api.saveCoastalSettings(rules, reason.trim()),
    onSuccess: (row) => {
      qc.setQueryData(coastalKeys.settings, row);
      void qc.invalidateQueries({ queryKey: coastalKeys.all });
      setDraft(null);
      setReason("");
      setTouched(false);
    },
  });
  if (settings.isLoading) return <Loading />;
  if (settings.isError) return <ErrorBox error={settings.error} onRetry={() => void settings.refetch()} />;
  if (!settings.data) return null;
  const rules = draft ?? settings.data.rules;
  const bands = waveBands(rules);
  const problem = rulesProblem(rules);
  const reasonMissing = reason.trim().length < REASON_MIN;
  const set = (key: string, value: unknown) => setDraft({ ...rules, [key]: value });
  const setBand = (i: number, part: 0 | 1, value: string) => {
    const next = bands.map((b): WaveBand => [...b]);
    const n = value === "" ? Number.NaN : Number(value);
    if (next[i]) next[i][part] = n;
    set("waves", next);
  };
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!problem && !reasonMissing) save.mutate(rules);
  };
  return (
    <form className="ops-form" onSubmit={submit} noValidate aria-describedby={`${id}-note`}>
      <p id={`${id}-note`} className="muted">
        {t("coastal.rules.note")}
        {settings.data.updated_by &&
          settings.data.updated_at &&
          ` ${t("coastal.rules.updated", { name: settings.data.updated_by, at: fmt.dateTime(settings.data.updated_at) })}`}
      </p>
      <fieldset disabled={!editable}>
        <legend>{t("coastal.rules.waves")}</legend>
        <div className="coastal-rules">
          {bands.map(([upper, points], i) => (
            <div key={i} className="coastal-rules__band">
              <div className="field">
                <label htmlFor={`${id}-w${i}`}>
                  {upper === null ? t("coastal.rules.waveAbove") : t("coastal.rules.waveBelow")}
                </label>
                <input
                  id={`${id}-w${i}`}
                  type="number"
                  step="0.1"
                  min="0"
                  dir="ltr"
                  value={upper === null ? (bands[i - 1]?.[0] ?? "") : Number.isNaN(upper) ? "" : upper}
                  disabled={upper === null}
                  onChange={(e) => setBand(i, 0, e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor={`${id}-p${i}`}>{t("coastal.rules.points")}</label>
                <input
                  id={`${id}-p${i}`}
                  type="number"
                  min="0"
                  dir="ltr"
                  value={Number.isNaN(points) ? "" : points}
                  onChange={(e) => setBand(i, 1, e.target.value)}
                />
              </div>
            </div>
          ))}
        </div>
      </fieldset>
      <fieldset disabled={!editable}>
        <legend>{t("coastal.rules.others")}</legend>
        <div className="coastal-rules">
          {NUMERIC_RULES.map((key) => (
            <div key={key} className={`field${touched && problem === key ? " field--invalid" : ""}`}>
              <label htmlFor={`${id}-${key}`}>{t(`coastal.rules.${key}`)}</label>
              <input
                id={`${id}-${key}`}
                type="number"
                min="0"
                step="any"
                dir="ltr"
                value={typeof rules[key] === "number" && !Number.isNaN(rules[key]) ? rules[key] : ""}
                onChange={(e) => set(key, e.target.value === "" ? Number.NaN : Number(e.target.value))}
              />
            </div>
          ))}
        </div>
      </fieldset>
      {touched && problem && (
        <p role="alert" className="alert alert--error">
          {t("coastal.rules.invalid", { rule: t(`coastal.rules.${problem}`) })}
        </p>
      )}
      {editable ? (
        <>
          <div className={`field${touched && reasonMissing ? " field--invalid" : ""}`}>
            <label htmlFor={`${id}-reason`}>
              {t("coastal.rules.reason")}
            </label>
            <input
              id={`${id}-reason`}
              value={reason}
              required
              aria-invalid={touched && reasonMissing}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          {save.isError && (
            <p role="alert" className="alert alert--error">
              {t(errorMessageKey(save.error))}
            </p>
          )}
          <div className="actions">
            <button type="submit" className="btn btn--primary" disabled={save.isPending}>
              {t("coastal.rules.save")}
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => setDraft({ ...settings.data.defaults })}
            >
              {t("coastal.rules.defaults")}
            </button>
          </div>
        </>
      ) : (
        <p className="muted">{t("coastal.rules.readOnly")}</p>
      )}
    </form>
  );
}

export function CoastalPage() {
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const national = user?.identity.national ?? false;
  const [filters, setFilters] = useState<OverviewFilters>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [heatMode, setHeatMode] = useState<HeatMode>("risk");
  const [announce, setAnnounce] = useState("");
  const [initialBounds] = useState(() => initialBoundsFor(user?.identity.gouvernoratCode ?? null));
  const overview = useQuery({
    queryKey: coastalKeys.overview(filters),
    queryFn: ({ signal }) => api.coastalOverview(filters, signal),
  });
  const bulletin = useMutation({
    mutationFn: () => api.coastalBulletin(filters.day, lang, filters.gouvernorat),
    onSuccess: saveDownload,
  });

  useLiveEvents(
    useCallback(
      (event) => {
        if (event.type !== "coastal.alert") return;
        void qc.invalidateQueries({ queryKey: coastalKeys.all });
        setAnnounce(t("coastal.alerts.arrived", { name: event.name, level: t(`coastal.level.${event.level}`) }));
      },
      [qc, t],
    ),
  );

  const data = overview.data;
  const classifications = useMemo(
    () => [...new Set((data?.beaches ?? []).map((b) => b.classification).filter((c): c is string => Boolean(c)))].sort(),
    [data],
  );
  const pois = useMemo<MapPoi[]>(
    () =>
      (data?.beaches ?? []).map((b) => ({
        id: `beach:${b.id}`,
        lon: b.lon,
        lat: b.lat,
        kind: "place",
        title: b.name,
        subtitle: [
          t(`coastal.level.${levelKey(b.level)}`),
          b.score === null ? null : t("coastal.score", { score: fmt.number(b.score) }),
        ]
          .filter(Boolean)
          .join(" · "),
        iconPath: LAYER_ICON_PATHS.water,
        colour: RISK_COLOURS[levelKey(b.level)],
        href: `beach:${b.id}`,
        details: b.factors.slice(0, 6).map((f) => `${t(`coastal.factor.${f.code}`, { value: f.value ?? "" })} +${f.points}`),
      })),
    [data, t, fmt],
  );
  const heat = useMemo<HeatPoint[] | undefined>(() => {
    if (!data || heatMode === "none") return [];
    const rows = heatMode === "risk" ? data.heat_risk : data.heat_drownings;
    return rows.map(([lat, lon, w]) => ({ lat, lon, weight: w }));
  }, [data, heatMode]);
  const k = data?.kpis;

  return (
    <div className="page coastal-page">
      <PageTitle icon="healthAndSafety" tone="sky">
        {t("coastal.title")}
      </PageTitle>
      <p className="muted">{t("coastal.intro")}</p>
      {data?.simulated && <SimulationBand note={t("coastal.simBand")} />}
      <p className="visually-hidden" role="status" aria-live="polite">
        {announce}
      </p>
      <Filters value={filters} onChange={setFilters} national={national} classifications={classifications} />
      {overview.isLoading && <Loading />}
      {overview.isError && <ErrorBox error={overview.error} onRetry={() => void overview.refetch()} />}
      {k && (
        <dl className="kpis" aria-label={t("coastal.kpis")}>
          <div className="kpi">
            <dt className="kpi__label">{t("coastal.kpi.beaches")}</dt>
            <dd className="kpi__value">{fmt.number(k.beaches)}</dd>
          </div>
          <div className="kpi kpi--risk-red">
            <dt className="kpi__label">{t("coastal.level.red")}</dt>
            <dd className="kpi__value">{fmt.number(k.red)}</dd>
          </div>
          <div className="kpi kpi--risk-yellow">
            <dt className="kpi__label">{t("coastal.level.yellow")}</dt>
            <dd className="kpi__value">{fmt.number(k.yellow)}</dd>
          </div>
          <div className="kpi kpi--risk-green">
            <dt className="kpi__label">{t("coastal.level.green")}</dt>
            <dd className="kpi__value">{fmt.number(k.green)}</dd>
          </div>
          <div className="kpi">
            <dt className="kpi__label">{t("coastal.kpi.average")}</dt>
            <dd className="kpi__value">{k.average_score === null ? "—" : fmt.decimal(k.average_score)}</dd>
          </div>
          <div className="kpi">
            <dt className="kpi__label">{t("coastal.kpi.guarded")}</dt>
            <dd className="kpi__value">{fmt.number(k.guarded)}</dd>
          </div>
          <div className="kpi">
            <dt className="kpi__label">{t("coastal.kpi.drownings")}</dt>
            <dd className="kpi__value">{fmt.number(k.drownings_season)}</dd>
          </div>
          <div className="kpi">
            <dt className="kpi__label">{t("coastal.kpi.present")}</dt>
            <dd className="kpi__value">{fmt.number(k.present)}</dd>
          </div>
        </dl>
      )}
      {data && (
        <div className="coastal-actions">
          <fieldset className="segmented">
            <legend>{t("coastal.heat.label")}</legend>
            {(["risk", "drownings", "none"] as const).map((m) => (
              <label key={m} className="segmented__item">
                <input type="radio" name="coastal-heat" checked={heatMode === m} onChange={() => setHeatMode(m)} />
                <span>{t(`coastal.heat.${m}`)}</span>
              </label>
            ))}
          </fieldset>
          <button type="button" className="btn btn--primary" disabled={bulletin.isPending} onClick={() => bulletin.mutate()}>
            {t("coastal.bulletin")}
          </button>
          {bulletin.isError && (
            <p role="alert" className="alert alert--error">
              {t(errorMessageKey(bulletin.error))}
            </p>
          )}
        </div>
      )}
      <div className="coastal-grid">
        <div className="coastal-map">
          <Suspense fallback={<Loading />}>
            <LazyMapView
              className="map coastal-map__map"
              markers={[]}
              bounds={initialBounds}
              ariaLabel={t("coastal.mapLabel")}
              styleUrl={mapStyleUrl}
              dir={directionOf(lang)}
              pois={pois}
              poiOpenLabel={t("coastal.openCard")}
              onOpenPoi={(href) => setSelected(href.replace(/^beach:/, ""))}
              heat={heat}
              heatTone="risk"
            />
          </Suspense>
          <ul className="coastal-legend" aria-label={t("coastal.legend")}>
            {(["red", "yellow", "green", "unknown"] as const).map((l) => (
              <li key={l}>
                <span className="coastal-legend__dot" style={{ background: RISK_COLOURS[l] }} aria-hidden="true" />
                {t(`coastal.level.${l}`)}
              </li>
            ))}
          </ul>
        </div>
        <AlertsCentre day={filters.day} onOpen={setSelected} />
      </div>
      {selected && <BeachPanel id={selected} onClose={() => setSelected(null)} />}
      {data && (
        <>
          <div className="charts">
            <BeachTable caption={t("coastal.topDangerous")} beaches={data.top_dangerous} onOpen={setSelected} />
            <BeachTable caption={t("coastal.topTouristic")} beaches={data.top_touristic} onOpen={setSelected} />
          </div>
          <div className="charts">
            <BarChart
              caption={t("coastal.byGouvernorat")}
              emptyText={t("coastal.noBeaches")}
              bars={data.by_gouvernorat.map((g) => ({
                key: String(g.code ?? "none"),
                label: gouvernorats.nameOf(g.code) ?? t("coastal.noGouvernorat"),
                value: g.average_score ?? 0,
              }))}
            />
            <BarChart
              caption={t("coastal.redByGouvernorat")}
              emptyText={t("coastal.noBeaches")}
              bars={data.by_gouvernorat.map((g) => ({
                key: String(g.code ?? "none"),
                label: gouvernorats.nameOf(g.code) ?? t("coastal.noGouvernorat"),
                value: g.red + g.yellow,
                tone: "bars__bar--risk",
              }))}
            />
          </div>
          <AttributionLines items={data.attribution} />
        </>
      )}
      <details className="card">
        <summary>{t("coastal.rules.title")}</summary>
        <RulesEditor />
      </details>
    </div>
  );
}
