import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { SimTag, SimulationBand } from "../components/StreamBits";
import { WeatherAttributionLine } from "../components/WeatherLayer";
import { useAuth } from "../context/auth";
import { useLiveEvents } from "../context/live";
import { useServices } from "../context/services";
import { NEW_ALERT_PATH, prefillFromSuggestion } from "../lib/alertPrefill";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { p7Keys } from "../lib/phase7Api";
import { canDraftMessage } from "../lib/roles";
import type { SuggestionEvidence, WeatherSuggestion } from "../lib/weatherTypes";

const REASON_MIN = 3;
const KNOWN_METRICS = [
  "fire_danger",
  "fwi",
  "wind_gust_kmh",
  "wind_speed_kmh",
  "rain_1h_mm",
  "rain_24h_mm",
  "precipitation_mm_h",
  "temperature_c",
  "humidity_pct",
] as const;

function evidenceRows(evidence: WeatherSuggestion["evidence"]): SuggestionEvidence[] {
  if (Array.isArray(evidence)) return evidence;
  return Object.entries(evidence).flatMap(([metric, value]) =>
    typeof value === "number"
      ? [{ metric, value }]
      : typeof value === "string"
        ? [{ metric, value: Number.NaN, unit: value }]
        : [],
  );
}

function Evidence({ suggestion }: { suggestion: WeatherSuggestion }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const rows = evidenceRows(suggestion.evidence);
  if (rows.length === 0) return <p className="muted">{t("weather.suggestions.noEvidence")}</p>;
  const metric = (m: string) =>
    (KNOWN_METRICS as readonly string[]).includes(m) ? t(`weather.metric.${m}`) : m.replace(/_/g, " ");
  return (
    <div className="table-wrap">
      <table className="table table--compact">
        <caption className="visually-hidden">{t("weather.suggestions.evidence")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("weather.suggestions.metric")}</th>
            <th scope="col">{t("weather.suggestions.value")}</th>
            <th scope="col">{t("weather.suggestions.threshold")}</th>
            <th scope="col">{t("weather.suggestions.where")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.metric}-${i}`}>
              <th scope="row">{metric(r.metric)}</th>
              <td dir="ltr">
                {Number.isFinite(r.value) ? fmt.decimal(r.value) : ""} {r.unit ?? ""}
              </td>
              <td dir="ltr">
                {r.threshold !== null && r.threshold !== undefined ? `≥ ${fmt.decimal(r.threshold)}` : "—"}
              </td>
              <td>
                {r.gouvernorat_code ? gouvernorats.nameOf(r.gouvernorat_code) : null}
                {r.lat !== null && r.lat !== undefined && r.lon !== null && r.lon !== undefined && (
                  <span className="code" dir="ltr">
                    {" "}
                    {r.lat.toFixed(2)}, {r.lon.toFixed(2)}
                  </span>
                )}
                {r.at && (
                  <>
                    {" · "}
                    <time dateTime={r.at}>{fmt.dateTime(r.at)}</time>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DismissForm({ suggestion, onCancel }: { suggestion: WeatherSuggestion; onCancel: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const dismiss = useMutation({
    mutationFn: () => api.dismissWeatherSuggestion(suggestion.id, reason.trim()),
    onSuccess: () => {
      qc.setQueryData<WeatherSuggestion[]>(p7Keys.suggestions, (rows) => rows?.filter((r) => r.id !== suggestion.id));
      void qc.invalidateQueries({ queryKey: p7Keys.suggestions });
    },
  });
  const invalid = reason.trim().length < REASON_MIN;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!invalid) dismiss.mutate();
  };
  return (
    <form className="ops-form" onSubmit={submit} noValidate>
      <div className={`field${touched && invalid ? " field--invalid" : ""}`}>
        <label htmlFor={id}>{t("weather.suggestions.reason")}</label>
        <textarea
          id={id}
          rows={2}
          maxLength={500}
          dir="auto"
          value={reason}
          aria-invalid={touched && invalid ? true : undefined}
          aria-describedby={touched && invalid ? `${id}-error` : undefined}
          onChange={(e) => setReason(e.target.value)}
        />
        {touched && invalid && (
          <p id={`${id}-error`} className="field__error">
            {t("weather.suggestions.reasonRequired")}
          </p>
        )}
      </div>
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={dismiss.isPending}>
          {dismiss.isPending ? t("ops.working") : t("weather.suggestions.confirmDismiss")}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          {t("common.cancel")}
        </button>
      </div>
      {dismiss.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(dismiss.error))}
        </p>
      )}
    </form>
  );
}

function SuggestionCard({ suggestion, fresh }: { suggestion: WeatherSuggestion; fresh: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const headingId = useId();
  const [dismissing, setDismissing] = useState(false);
  const canAlert = canDraftMessage(user?.identity.roles ?? [], "alert");
  const accept = useMutation({
    mutationFn: () => api.acceptWeatherSuggestion(suggestion.id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: p7Keys.suggestions });
      void navigate(NEW_ALERT_PATH, { state: prefillFromSuggestion(suggestion) });
    },
  });
  const title = (lang === "ar" ? suggestion.title.ar : suggestion.title.fr || suggestion.title.ar) ?? "";
  const body = (lang === "ar" ? suggestion.body.ar : suggestion.body.fr || suggestion.body.ar) ?? "";
  const area =
    suggestion.gouvernorat_codes.length === 0
      ? t("ops.map.national")
      : suggestion.gouvernorat_codes.map((c) => gouvernorats.nameOf(c) ?? String(c)).join(t("common.listSeparator"));
  return (
    <article className={`card suggestion${fresh ? " suggestion--new" : ""}`} aria-labelledby={headingId}>
      <header className="suggestion__head">
        <span className={`chip chip--severity-${suggestion.severity}`}>
          {t(`ops.map.severity.${suggestion.severity}`)}
        </span>
        <h2 id={headingId} dir="auto">
          {title || t("weather.suggestions.untitled")}
        </h2>
        {suggestion.simulated && <SimTag />}
        {fresh && <span className="tag tag--new">{t("weather.suggestions.new")}</span>}
      </header>
      <dl className="fields fields--compact">
        <dt>{t("weather.suggestions.area")}</dt>
        <dd>{area}</dd>
        <dt>{t("weather.suggestions.validUntil")}</dt>
        <dd>
          <time dateTime={suggestion.valid_until}>{fmt.dateTime(suggestion.valid_until)}</time>
        </dd>
        {suggestion.created_at && (
          <>
            <dt>{t("weather.suggestions.createdAt")}</dt>
            <dd>
              <time dateTime={suggestion.created_at}>{fmt.dateTime(suggestion.created_at)}</time>
            </dd>
          </>
        )}
        {suggestion.rule && (
          <>
            <dt>{t("weather.suggestions.rule")}</dt>
            <dd className="code" dir="ltr">
              {suggestion.rule}
            </dd>
          </>
        )}
      </dl>
      {body && (
        <p className="suggestion__body" dir="auto">
          {body}
        </p>
      )}
      <h3>{t("weather.suggestions.evidence")}</h3>
      <Evidence suggestion={suggestion} />
      <p className="muted">{t("weather.suggestions.humanDecides")}</p>
      {dismissing ? (
        <DismissForm suggestion={suggestion} onCancel={() => setDismissing(false)} />
      ) : (
        <div className="actions">
          {canAlert && (
            <button
              type="button"
              className="btn btn--primary"
              disabled={accept.isPending}
              onClick={() => accept.mutate()}
            >
              {accept.isPending ? t("ops.working") : t("weather.suggestions.accept")}
            </button>
          )}
          <button type="button" className="btn" onClick={() => setDismissing(true)}>
            {t("weather.suggestions.dismiss")}
          </button>
        </div>
      )}
      {accept.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(accept.error))}
        </p>
      )}
    </article>
  );
}

/** Weather threshold → suggested alert (UC, §1): evidence, accept (opens the alert form prefilled) or dismiss. */
export function WeatherSuggestionsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const [fresh, setFresh] = useState<ReadonlySet<string>>(new Set());
  const [announce, setAnnounce] = useState("");
  const query = useQuery({
    queryKey: p7Keys.suggestions,
    queryFn: ({ signal }) => api.weatherSuggestions(signal),
    // The live feed keeps it current; this only covers a lost connection.
    refetchInterval: 5 * 60_000,
  });
  useLiveEvents(
    useCallback(
      (event) => {
        if (event.type !== "weather.suggestion") return;
        setFresh((prev) => new Set(prev).add(event.suggestion_id));
        setAnnounce(t("weather.suggestions.arrived"));
      },
      [t],
    ),
  );
  const pending = (query.data ?? []).filter((s) => !s.status || s.status === "pending");
  const simulated = pending.some((s) => s.simulated);
  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("weather.suggestions.title")}</h1>
        <p className="muted">{t("weather.suggestions.count", { count: fmt.number(pending.length) })}</p>
      </div>
      <p className="muted">{t("weather.suggestions.intro")}</p>
      <p className="visually-hidden" role="status" aria-live="polite">
        {announce}
      </p>
      {simulated && <SimulationBand note={t("weather.simBand")} />}
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && pending.length === 0 && <p className="muted">{t("weather.suggestions.none")}</p>}
      <div className="suggestions">
        {pending.map((s) => (
          <SuggestionCard key={s.id} suggestion={s} fresh={fresh.has(s.id)} />
        ))}
      </div>
      <WeatherAttributionLine />
    </div>
  );
}
