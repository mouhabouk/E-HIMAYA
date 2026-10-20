/**
 * Decision support on the incident page (phase 7 §2–§4, FR-C-11 / FR-C-13 / FR-C-14): spread forecast,
 * recommendations, suggested responders, the procedures assistant and the crisis conference. Golden rule of the
 * phase: every suggestion shows its justification and inputs, and a human decides — nothing here sends an alert,
 * dispatches a resource or transfers a call by itself.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useSoftphone } from "../context/softphone";
import { NEW_ALERT_PATH, prefillFromAction } from "../lib/alertPrefill";
import { errorMessageKey, isApiError } from "../lib/api";
import {
  DEFAULT_HORIZONS,
  FUEL_MODELS,
  type AssistantAnswer,
  type ForecastKind,
  type ForecastRun,
  type FuelModel,
  type Recommendation,
  type RecommendationAction,
  type RouteProfile,
} from "../lib/decisionTypes";
import { bilingual, inputText, polygonColour, sortedPolygons } from "../lib/forecast";
import { useFormat, useLanguage } from "../lib/hooks";
import { p7Keys } from "../lib/phase7Api";
import { canDispatch, canDraftMessage, canJoinConference, canRunForecast } from "../lib/roles";
import type { DialBody } from "../lib/telephonyTypes";
import type { IncidentDetail } from "../lib/types";
import { ErrorBox, Loading } from "./Feedback";
import { CallButton } from "./Softphone";
import { SimTag, SimulationBand } from "./StreamBits";

const HORIZON_CHOICES = [30, 60, 120, 240] as const;

function MutationError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  return (
    <p className="alert alert--error" role="alert">
      {t(errorMessageKey(error))}
    </p>
  );
}

function Inputs({ inputs, label }: { inputs: Record<string, unknown>; label: string }) {
  const entries = Object.entries(inputs);
  if (entries.length === 0) return null;
  return (
    <details className="inputs">
      <summary>{label}</summary>
      <dl className="fields fields--compact">
        {entries.map(([k, v]) => (
          <div key={k} className="fields__pair">
            <dt className="code" dir="ltr">
              {k}
            </dt>
            <dd dir="ltr">{inputText(v)}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

/** "Advisory: a person decides" note shown with every suggestion block. */
export function AdvisoryNote({ text }: { text?: string }) {
  const { t } = useTranslation();
  return (
    <p className="advisory" role="note">
      <strong>{t("decision.advisory")}</strong> {text ?? t("decision.humanDecides")}
    </p>
  );
}

// ---------------------------------------------------------------- spread forecast

export interface ForecastState {
  kind: ForecastKind;
  run: ForecastRun;
}

export function ForecastPanel({
  incident,
  forecast,
  onForecast,
  shown,
  onShown,
}: {
  incident: IncidentDetail;
  forecast: ForecastState | null;
  onForecast: (f: ForecastState) => void;
  shown: boolean;
  onShown: (on: boolean) => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const base = useId();
  const canRun = canRunForecast(user?.identity.roles ?? []) && incident.status === "open";
  const [kind, setKind] = useState<ForecastKind>(incident.category === "flood" ? "flood" : "fire");
  const [fuel, setFuel] = useState<FuelModel | "">("");
  const [horizons, setHorizons] = useState<number[]>([...DEFAULT_HORIZONS]);
  const [ignition, setIgnition] = useState<"centroid" | "custom">("centroid");
  const [lat, setLat] = useState(incident.centroid ? incident.centroid.lat.toFixed(5) : "");
  const [lon, setLon] = useState(incident.centroid ? incident.centroid.lon.toFixed(5) : "");
  const custom = ignition === "custom";
  const latN = Number(lat);
  const lonN = Number(lon);
  const coordsValid =
    !custom || (lat.trim() !== "" && lon.trim() !== "" && Math.abs(latN) <= 90 && Math.abs(lonN) <= 180);
  const run = useMutation({
    mutationFn: () =>
      kind === "fire"
        ? api.fireForecast(incident.id, {
            ignition: custom ? { lat: latN, lon: lonN } : null,
            ...(fuel ? { fuel_model: fuel } : {}),
            horizons_min: [...horizons].sort((a, b) => a - b),
          })
        : api.floodForecast(incident.id),
    onSuccess: (result) => {
      onForecast({ kind, run: result });
      onShown(true);
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (kind === "fire" && (horizons.length === 0 || !coordsValid)) return;
    run.mutate();
  };
  const result = forecast?.run;
  return (
    <section className="card" aria-labelledby={`${base}-title`}>
      <h2 id={`${base}-title`}>{t("forecast.title")}</h2>
      <AdvisoryNote text={t("forecast.advisory")} />
      {canRun ? (
        <form className="ops-form forecast-form" onSubmit={submit} noValidate>
          <fieldset className="segmented">
            <legend>{t("forecast.kind")}</legend>
            {(["fire", "flood"] as const).map((k) => (
              <label key={k} className="segmented__item">
                <input type="radio" name={`${base}-kind`} checked={kind === k} onChange={() => setKind(k)} />
                <span>{t(`forecast.kinds.${k}`)}</span>
              </label>
            ))}
          </fieldset>
          {kind === "fire" && (
            <>
              <fieldset>
                <legend>{t("forecast.horizons")}</legend>
                {HORIZON_CHOICES.map((h) => (
                  <label key={h} className="checkbox">
                    <input
                      type="checkbox"
                      checked={horizons.includes(h)}
                      onChange={(e) =>
                        setHorizons(e.target.checked ? [...horizons, h] : horizons.filter((x) => x !== h))
                      }
                    />
                    <span>{t("forecast.minutes", { count: h })}</span>
                  </label>
                ))}
                {horizons.length === 0 && <p className="field__error">{t("forecast.horizonRequired")}</p>}
              </fieldset>
              <div className="field">
                <label htmlFor={`${base}-fuel`}>{t("forecast.fuel")}</label>
                <select id={`${base}-fuel`} value={fuel} onChange={(e) => setFuel(e.target.value as FuelModel | "")}>
                  <option value="">{t("forecast.fuelAuto")}</option>
                  {FUEL_MODELS.map((f) => (
                    <option key={f} value={f}>
                      {t(`forecast.fuels.${f}`)}
                    </option>
                  ))}
                </select>
              </div>
              <fieldset>
                <legend>{t("forecast.ignition")}</legend>
                <label className="checkbox">
                  <input type="radio" name={`${base}-ign`} checked={!custom} onChange={() => setIgnition("centroid")} />
                  <span>{t("forecast.ignitionCentroid")}</span>
                </label>
                <label className="checkbox">
                  <input type="radio" name={`${base}-ign`} checked={custom} onChange={() => setIgnition("custom")} />
                  <span>{t("forecast.ignitionCustom")}</span>
                </label>
                {custom && (
                  <div className="forecast-coords">
                    <div className="field">
                      <label htmlFor={`${base}-lat`}>{t("forecast.lat")}</label>
                      <input
                        id={`${base}-lat`}
                        inputMode="decimal"
                        dir="ltr"
                        value={lat}
                        onChange={(e) => setLat(e.target.value)}
                      />
                    </div>
                    <div className="field">
                      <label htmlFor={`${base}-lon`}>{t("forecast.lon")}</label>
                      <input
                        id={`${base}-lon`}
                        inputMode="decimal"
                        dir="ltr"
                        value={lon}
                        onChange={(e) => setLon(e.target.value)}
                      />
                    </div>
                    {!coordsValid && <p className="field__error">{t("forecast.coordsInvalid")}</p>}
                  </div>
                )}
              </fieldset>
            </>
          )}
          {kind === "flood" && <p className="muted">{t("forecast.floodHelp")}</p>}
          <div className="actions">
            <button type="submit" className="btn btn--primary" disabled={run.isPending}>
              {run.isPending ? t("forecast.running") : result ? t("forecast.refresh") : t("forecast.run")}
            </button>
          </div>
          <MutationError error={run.error} />
        </form>
      ) : (
        !result && <p className="muted">{t("forecast.none")}</p>
      )}
      {forecast && (
        <div className="forecast-result" aria-live="polite">
          {forecast.run.simulated && <SimulationBand note={t("forecast.simBand")} />}
          {forecast.run.disclaimer && (
            <p className="alert alert--warn" role="note">
              {bilingual(forecast.run.disclaimer, lang)}
            </p>
          )}
          <p>
            <strong>{t(`forecast.kinds.${forecast.kind}`)}</strong> · <span className="code">{forecast.run.model}</span>{" "}
            · <time dateTime={forecast.run.generated_at}>{fmt.dateTime(forecast.run.generated_at)}</time>
            {forecast.run.simulated && <SimTag />}
          </p>
          {forecast.run.rate_of_spread_m_min !== null && forecast.run.rate_of_spread_m_min !== undefined && (
            <p>{t("forecast.ros", { value: fmt.decimal(forecast.run.rate_of_spread_m_min) })}</p>
          )}
          {forecast.run.level && (
            <p>
              {t("forecast.level", {
                level: t(`forecast.levels.${forecast.run.level}`, { defaultValue: forecast.run.level }),
              })}
            </p>
          )}
          <label className="checkbox">
            <input type="checkbox" checked={shown} onChange={(e) => onShown(e.target.checked)} />
            <span>{t("forecast.showOnMap")}</span>
          </label>
          <ForecastLegend forecast={forecast} />
          <Inputs inputs={forecast.run.inputs} label={t("forecast.inputs")} />
          {forecast.run.assumptions.length > 0 && (
            <>
              <h3>{t("forecast.assumptions")}</h3>
              <ul className="assumptions">
                {forecast.run.assumptions.map((a, i) => (
                  <li key={i} dir="auto">
                    {bilingual(a, lang)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}

/** Legend and table of the forecast polygons (colour + horizon/level + area: never colour alone). */
export function ForecastLegend({ forecast }: { forecast: ForecastState }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const polygons = sortedPolygons(forecast.kind, forecast.run);
  return (
    <div className="table-wrap">
      <table className="table table--compact forecast-legend">
        <caption>{t("forecast.legend")}</caption>
        <thead>
          <tr>
            <th scope="col">{forecast.kind === "fire" ? t("forecast.horizon") : t("forecast.riskLevel")}</th>
            <th scope="col">{t("forecast.area")}</th>
          </tr>
        </thead>
        <tbody>
          {polygons.map((p, i) => (
            <tr key={i}>
              <th scope="row">
                <span
                  className="weather-swatch"
                  style={{ background: polygonColour(forecast.kind, p, i) }}
                  aria-hidden="true"
                />
                {p.minutes !== null && p.minutes !== undefined
                  ? t("forecast.minutes", { count: p.minutes })
                  : t(`forecast.levels.${p.level ?? "unknown"}`, { defaultValue: p.level ?? "—" })}
              </th>
              <td>
                {p.area_ha !== null && p.area_ha !== undefined
                  ? t("forecast.hectares", { value: fmt.decimal(p.area_ha) })
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------- recommendations

function actionLabel(
  t: (k: string, o?: Record<string, unknown>) => string,
  a: RecommendationAction,
  lang: "ar" | "fr",
): string {
  const custom = bilingual(a.label ?? null, lang);
  return custom || t(`decision.action.${a.type}`);
}

function dialBodyOf(a: Extract<RecommendationAction, { type: "call" }>): DialBody | null {
  if (a.number) return { number: a.number };
  if (a.volunteer_id) return { volunteer_id: a.volunteer_id };
  if (a.report_id) return { report_id: a.report_id };
  return null;
}

function RecommendationCard({
  item,
  onAssign,
  onRoute,
}: {
  item: Recommendation;
  onAssign: (resourceId: string | null, order: string | null) => void;
  onRoute: (from: { lat: number; lon: number }, to: { lat: number; lon: number }, profile: RouteProfile) => void;
}) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const lang = useLanguage();
  const navigate = useNavigate();
  const roles = user?.identity.roles ?? [];
  const id = useId();
  return (
    <li className="recommendation" aria-labelledby={id}>
      <div className="recommendation__head">
        <span className="tag">{t(`decision.kind.${item.kind}`)}</span>
        <h3 id={id} dir="auto">
          {bilingual(item.title, lang)}
        </h3>
        <span className={`chip chip--confidence-${item.confidence}`}>
          {t(`decision.confidence.${item.confidence}`)}
        </span>
      </div>
      <p className="recommendation__why" dir="auto">
        <strong>{t("decision.rationale")}</strong> {bilingual(item.rationale, lang)}
      </p>
      <Inputs inputs={item.inputs} label={t("decision.inputs")} />
      {item.actions.length > 0 && (
        <div className="actions">
          {item.actions.map((a, i) => {
            const label = actionLabel(t, a, lang);
            switch (a.type) {
              case "open_assignment":
                return canDispatch(roles) ? (
                  <button
                    key={i}
                    type="button"
                    className="btn btn--small"
                    onClick={() => onAssign(a.resource_id ?? null, a.order ?? null)}
                  >
                    {label}
                  </button>
                ) : null;
              case "open_alert_form":
                return canDraftMessage(roles, "alert") ? (
                  <button
                    key={i}
                    type="button"
                    className="btn btn--small"
                    onClick={() => void navigate(NEW_ALERT_PATH, { state: prefillFromAction(a.prefill) })}
                  >
                    {label}
                  </button>
                ) : null;
              case "call": {
                const body = dialBodyOf(a);
                return body ? <CallButton key={i} body={body} label={label} /> : null;
              }
              case "show_route":
                return (
                  <button
                    key={i}
                    type="button"
                    className="btn btn--small"
                    onClick={() => onRoute(a.from, a.to, a.profile ?? "car")}
                  >
                    {label}
                  </button>
                );
              default:
                return null;
            }
          })}
        </div>
      )}
    </li>
  );
}

export function RecommendationsPanel({
  incident,
  onAssign,
  onRoute,
}: {
  incident: IncidentDetail;
  onAssign: (resourceId: string | null, order: string | null) => void;
  onRoute: (from: { lat: number; lon: number }, to: { lat: number; lon: number }, profile: RouteProfile) => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const base = useId();
  const query = useQuery({
    queryKey: p7Keys.recommendations(incident.id),
    queryFn: ({ signal }) => api.recommendations(incident.id, signal),
    staleTime: 60_000,
  });
  return (
    <section className="card" aria-labelledby={`${base}-title`}>
      <h2 id={`${base}-title`}>{t("decision.title")}</h2>
      <AdvisoryNote />
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && (
        <>
          {query.data.simulated && <SimulationBand note={t("decision.simBand")} />}
          <p className="muted">
            {t("decision.generated", { time: fmt.dateTime(query.data.generated_at) })}{" "}
            <button
              type="button"
              className="btn btn--small btn--ghost"
              disabled={query.isFetching}
              onClick={() => void query.refetch()}
            >
              {query.isFetching ? t("common.loading") : t("decision.refresh")}
            </button>
          </p>
          {query.data.items.length === 0 ? (
            <p className="muted">{t("decision.none")}</p>
          ) : (
            <ul className="recommendations">
              {query.data.items.map((item, i) => (
                <RecommendationCard key={`${item.kind}-${i}`} item={item} onAssign={onAssign} onRoute={onRoute} />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- responders

export function RespondersPanel({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const base = useId();
  const query = useQuery({
    queryKey: p7Keys.responders(incident.id),
    queryFn: ({ signal }) => api.responders(incident.id, signal),
    staleTime: 5 * 60_000,
  });
  return (
    <section className="card" aria-labelledby={`${base}-title`}>
      <h2 id={`${base}-title`}>{t("responders.title")}</h2>
      <p className="muted">{t("responders.intro")}</p>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && query.data.length === 0 && <p className="muted">{t("responders.none")}</p>}
      {query.data && query.data.length > 0 && (
        <ul className="responders">
          {query.data.map((r, i) => (
            <li key={r.id ?? i}>
              <strong dir="auto">{r.name}</strong>
              {(r.role ?? r.organization) && (
                <span className="muted" dir="auto">
                  {" · "}
                  {[r.role, r.organization].filter(Boolean).join(" · ")}
                </span>
              )}
              <p className="responders__why" dir="auto">
                <span className="visually-hidden">{t("decision.rationale")} </span>
                {bilingual(r.reason, lang)}
              </p>
              {r.phone && (
                <span className="responders__phone">
                  <a href={`tel:${r.phone}`} dir="ltr">
                    {r.phone}
                  </a>{" "}
                  <CallButton body={{ number: r.phone }} label={t("phone.callName", { name: r.name })} />
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- assistant

function sourceHref(s: AssistantAnswer["sources"][number]): string | null {
  if (s.kind === "incident") return `/incidents/${encodeURIComponent(s.id)}`;
  if (s.kind === "report") return `/reports/${encodeURIComponent(s.id)}`;
  return null;
}

export function AssistantPanel({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const base = useId();
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<{ question: string; answer: AssistantAnswer }[]>([]);
  const ask = useMutation({
    mutationFn: (q: string) => api.askAssistant(incident.id, q, lang),
    onSuccess: (answer, q) => {
      setHistory((h) => [{ question: q, answer }, ...h]);
      setQuestion("");
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (q.length >= 3) ask.mutate(q);
  };
  const unavailable = isApiError(ask.error) && ask.error.code === "assistant_unavailable";
  return (
    <section className="card assistant" aria-labelledby={`${base}-title`}>
      <h2 id={`${base}-title`}>{t("assistant.title")}</h2>
      <AdvisoryNote text={t("assistant.advisory")} />
      <form onSubmit={submit} className="ops-form">
        <div className="field">
          <label htmlFor={`${base}-q`}>{t("assistant.question")}</label>
          <textarea
            id={`${base}-q`}
            rows={2}
            maxLength={1000}
            dir="auto"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </div>
        <div className="actions">
          <button type="submit" className="btn btn--primary" disabled={ask.isPending || question.trim().length < 3}>
            {ask.isPending ? t("assistant.thinking") : t("assistant.ask")}
          </button>
        </div>
        {unavailable ? (
          <p className="alert alert--warn" role="alert">
            {t("errors.assistant_unavailable")}
          </p>
        ) : (
          <MutationError error={ask.error} />
        )}
      </form>
      <div aria-live="polite">
        {history.map((h, i) => (
          <article key={history.length - i} className="assistant__turn">
            <p className="assistant__q" dir="auto">
              <strong>{t("assistant.you")}</strong> {h.question}
            </p>
            <div className="assistant__a">
              <p className="assistant__label">
                <span className="tag tag--advisory">{t("decision.advisory")}</span>{" "}
                <span className="muted code">{h.answer.model}</span>
              </p>
              <p dir="auto" className="assistant__text">
                {h.answer.answer}
              </p>
              <h3>{t("assistant.sources")}</h3>
              {h.answer.sources.length === 0 ? (
                <p className="muted">{t("assistant.noSources")}</p>
              ) : (
                <ol className="assistant__sources">
                  {h.answer.sources.map((s) => {
                    const href = sourceHref(s);
                    return (
                      <li key={`${s.kind}-${s.id}`}>
                        <span className="tag">{t(`assistant.kind.${s.kind}`)}</span>{" "}
                        {href ? (
                          <Link to={href} dir="auto">
                            {s.title}
                          </Link>
                        ) : s.url ? (
                          <a href={s.url} target="_blank" rel="noopener noreferrer" dir="auto">
                            {s.title}
                          </a>
                        ) : (
                          <strong dir="auto">{s.title}</strong>
                        )}
                        <blockquote dir="auto">{s.excerpt}</blockquote>
                      </li>
                    );
                  })}
                </ol>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- crisis conference

export function ConferencePanel({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const phone = useSoftphone();
  const qc = useQueryClient();
  const base = useId();
  const [ending, setEnding] = useState<string | null>(null);
  const allowed = canJoinConference(user?.identity.roles ?? []);
  const rooms = useQuery({
    queryKey: p7Keys.conferences(incident.id),
    enabled: allowed,
    queryFn: ({ signal }) => api.conferences(incident.id, signal),
  });
  const join = useMutation({
    mutationFn: async (c: { room: string; join_uri: string }) => {
      if (!phone) throw new Error("softphone_not_registered");
      await phone.joinConference(c.room, c.join_uri);
    },
  });
  const start = useMutation({
    mutationFn: () => api.startConference(incident.id),
    onSuccess: (c) => {
      void qc.invalidateQueries({ queryKey: p7Keys.conferences(incident.id) });
      join.mutate(c);
    },
  });
  const end = useMutation({
    mutationFn: (room: string) => api.endConference(incident.id, room),
    onSuccess: () => {
      setEnding(null);
      void qc.invalidateQueries({ queryKey: p7Keys.conferences(incident.id) });
    },
  });
  if (!allowed) return null;
  const list = rooms.data ?? [];
  const joinError =
    join.error instanceof Error && join.error.message === "softphone_not_registered" ? null : join.error;
  return (
    <section className="card" aria-labelledby={`${base}-title`}>
      <h2 id={`${base}-title`}>{t("conference.title")}</h2>
      <p className="muted">{t("conference.intro")}</p>
      {rooms.isPending && <Loading />}
      {rooms.isError && <ErrorBox error={rooms.error} onRetry={() => void rooms.refetch()} />}
      {list.length > 0 && (
        <ul className="conferences">
          {list.map((c) => (
            <li key={c.room}>
              <strong className="code" dir="ltr">
                {c.room}
              </strong>
              {c.started_at && <span className="muted"> · {fmt.dateTime(c.started_at)}</span>}
              {c.participants !== null && c.participants !== undefined && (
                <span className="muted"> · {t("conference.participants", { count: c.participants })}</span>
              )}
              <div className="actions">
                <button
                  type="button"
                  className="btn btn--small btn--primary"
                  disabled={join.isPending}
                  onClick={() => join.mutate(c)}
                >
                  {t("conference.join")}
                </button>
                {ending === c.room ? (
                  <>
                    <button
                      type="button"
                      className="btn btn--small btn--danger"
                      disabled={end.isPending}
                      onClick={() => end.mutate(c.room)}
                    >
                      {t("conference.confirmEnd")}
                    </button>
                    <button type="button" className="btn btn--small" onClick={() => setEnding(null)}>
                      {t("common.cancel")}
                    </button>
                  </>
                ) : (
                  <button type="button" className="btn btn--small" onClick={() => setEnding(c.room)}>
                    {t("conference.end")}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {rooms.isSuccess && list.length === 0 && (
        <div className="actions">
          <button type="button" className="btn btn--primary" disabled={start.isPending} onClick={() => start.mutate()}>
            {start.isPending ? t("ops.working") : t("conference.start")}
          </button>
        </div>
      )}
      <div role="status" aria-live="polite">
        {join.isSuccess && <p className="alert alert--ok">{t("conference.joined")}</p>}
      </div>
      {join.isError && !joinError && (
        <p className="alert alert--error" role="alert">
          {t("errors.softphone_not_registered")}
        </p>
      )}
      <MutationError error={joinError ?? start.error ?? end.error} />
    </section>
  );
}
