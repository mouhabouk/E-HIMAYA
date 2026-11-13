// The four screens the menu of 20 systems lacked (Yamen 2026-11-13, «الحصر العميق للخصائص الوظيفية»): the image and
// video analysis centre (system 7), the forecasting (5), the citizens (17) and the administrator's mother board (19).
// Each one reads one overview of the API, in the caller's scope; none of them alerts or decides by itself.
import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { SimTag, SimulationBand } from "../components/StreamBits";
import { useServices } from "../context/services";
import { boardsKeys, type DangerLevel, type ServiceState } from "../lib/boardsApi";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { localized } from "../lib/localized";

const DANGER_TONE: Record<DangerLevel, string> = { high: "tone-red", medium: "tone-amber", low: "tone-slate" };
const FIRE_TONE: Record<string, string> = {
  extreme: "tone-red",
  very_high: "tone-red",
  high: "tone-amber",
  moderate: "tone-amber",
  low: "tone-green",
};
const RAIN_TONE: Record<string, string> = { warning: "tone-red", watch: "tone-amber", none: "tone-slate" };
const SERVICE_TONE: Record<ServiceState, string> = {
  ok: "tone-green",
  real: "tone-green",
  simulated: "tone-amber",
  not_configured: "tone-amber",
  error: "tone-red",
  unreachable: "tone-red",
};

function Kpi({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className={`kpi${tone ? ` ${tone}` : ""}`}>
      <dt className="kpi__label">{label}</dt>
      <dd className="kpi__value">{value}</dd>
    </div>
  );
}

function Period({
  value,
  options,
  onChange,
  label,
}: {
  value: number;
  options: readonly number[];
  onChange: (n: number) => void;
  label: (n: number) => string;
}) {
  const { t } = useTranslation();
  const id = useId();
  return (
    <label className="field" htmlFor={id}>
      <span>{t("boards.period")}</span>
      <select id={id} value={value} onChange={(e) => onChange(Number(e.target.value))}>
        {options.map((n) => (
          <option key={n} value={n}>
            {label(n)}
          </option>
        ))}
      </select>
    </label>
  );
}

// ---------------------------------------------------------------- 7. image and video analysis

const VISION_HOURS = [6, 24, 72, 168] as const;

export function VisionPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const { nameOf } = useGouvernorats();
  const [hours, setHours] = useState<number>(24);
  const query = useQuery({
    queryKey: boardsKeys.vision(hours),
    queryFn: ({ signal }) => api.visionOverview(hours, signal),
    refetchInterval: 60_000,
  });
  const data = query.data;
  return (
    <div className="page boards-page">
      <PageTitle icon="visibility" tone="purple">
        {t("boards.vision.title")}
      </PageTitle>
      <p className="muted">{t("boards.vision.intro")}</p>
      <Period value={hours} options={VISION_HOURS} onChange={setHours} label={(n) => t("boards.hours", { n })} />
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {data && (
        <>
          <dl className="kpis" aria-label={t("boards.vision.kpis")}>
            <Kpi label={t("streams.label.fire")} value={fmt.number(data.counts.fire)} />
            <Kpi label={t("streams.label.smoke")} value={fmt.number(data.counts.smoke)} />
            <Kpi label={t("streams.label.person")} value={fmt.number(data.counts.person)} />
            <Kpi label={t("boards.vision.confirmed")} value={fmt.number(data.confirmed)} />
            <Kpi label={t("boards.danger.high")} value={fmt.number(data.danger.high)} tone="tone-red" />
            <Kpi label={t("boards.danger.medium")} value={fmt.number(data.danger.medium)} tone="tone-amber" />
            <Kpi label={t("boards.vision.watching")} value={fmt.number(data.watching)} />
          </dl>
          <p className="muted">
            {t("boards.vision.threshold", { value: fmt.percent(data.alert_confidence) })}{" "}
            <Link to="/streams">{t("boards.vision.toStreams")}</Link>
          </p>
          {data.items.length === 0 ? (
            <p className="empty">{t("boards.vision.empty")}</p>
          ) : (
            <div className="table-wrap card">
              <table className="table table--compact">
                <caption className="visually-hidden">{t("boards.vision.table")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("boards.at")}</th>
                    <th scope="col">{t("boards.vision.label")}</th>
                    <th scope="col">{t("boards.vision.confidence")}</th>
                    <th scope="col">{t("boards.vision.danger")}</th>
                    <th scope="col">{t("boards.vision.origin")}</th>
                    <th scope="col">{t("boards.gouvernorat")}</th>
                    <th scope="col">{t("boards.vision.report")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((i, n) => (
                    <tr key={`${i.at}-${n}`}>
                      <td>{fmt.dateTime(i.at)}</td>
                      <td>
                        {t(`streams.label.${i.label}`, { defaultValue: i.label })}
                        {i.confirmed && <> · {t("boards.vision.confirmedOne")}</>}
                      </td>
                      <td>{fmt.percent(i.confidence)}</td>
                      <td>
                        <span className={`pill ${DANGER_TONE[i.danger]}`}>{t(`boards.danger.${i.danger}`)}</span>
                      </td>
                      <td>
                        {i.origin === "report_image"
                          ? t("boards.vision.reportImage")
                          : t(`streams.source.${i.origin}`, { defaultValue: i.origin })}
                        {i.origin === "sim" && <SimTag />}
                        {i.stream_label ? ` · ${i.stream_label}` : ""}
                      </td>
                      <td>{nameOf(i.gouvernorat_code) ?? "—"}</td>
                      <td>{i.report_id ? <Link to={`/reports/${i.report_id}`}>{t("boards.open")}</Link> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- 5. forecasting

export function ForecastPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const { nameOf } = useGouvernorats();
  const query = useQuery({
    queryKey: boardsKeys.forecast,
    queryFn: ({ signal }) => api.forecastOverview(signal),
    refetchInterval: 15 * 60_000,
  });
  const data = query.data;
  const num = (n: number | null) => (n === null ? "—" : fmt.decimal(n));
  return (
    <div className="page boards-page">
      <PageTitle icon="thunderstorm" tone="sky">
        {t("boards.forecast.title")}
      </PageTitle>
      <p className="muted">{t("boards.forecast.intro")}</p>
      {data?.simulated && <SimulationBand note={t("boards.forecast.sim")} />}
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {data && (
        <>
          <h2>{t("boards.forecast.next", { n: data.hours })}</h2>
          {data.gouvernorats.length === 0 ? (
            <p className="empty">{t("boards.forecast.empty")}</p>
          ) : (
            <div className="table-wrap card">
              <table className="table table--compact">
                <caption className="visually-hidden">{t("boards.forecast.table")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("boards.gouvernorat")}</th>
                    <th scope="col">{t("weather.field.fireDanger")}</th>
                    <th scope="col">FWI</th>
                    <th scope="col">{t("boards.forecast.fireAt")}</th>
                    <th scope="col">{t("weather.field.rain")}</th>
                    <th scope="col">{t("boards.forecast.rain24")}</th>
                    <th scope="col">{t("boards.forecast.gust")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.gouvernorats.map((g) => (
                    <tr key={g.gouvernorat_code}>
                      <th scope="row">{nameOf(g.gouvernorat_code)}</th>
                      <td>
                        {g.fire_danger ? (
                          <span className={`pill ${FIRE_TONE[g.fire_danger] ?? "tone-slate"}`}>
                            {t(`weather.fireDanger.${g.fire_danger}`)}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>{num(g.fwi)}</td>
                      <td>{g.fire_at ? fmt.dateTime(g.fire_at) : "—"}</td>
                      <td>
                        <span className={`pill ${RAIN_TONE[g.rain] ?? "tone-slate"}`}>
                          {t(`weather.rainLevel.${g.rain}`)}
                        </span>
                      </td>
                      <td>{num(g.rain_24h_mm)}</td>
                      <td>{num(g.gust_kmh)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <h2>{t("boards.forecast.runs")}</h2>
          <p className="muted">{t("forecast.advisory")}</p>
          {data.runs.length === 0 ? (
            <p className="empty">{t("boards.forecast.noRuns")}</p>
          ) : (
            <div className="table-wrap card">
              <table className="table table--compact">
                <caption className="visually-hidden">{t("boards.forecast.runs")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("boards.at")}</th>
                    <th scope="col">{t("forecast.kind")}</th>
                    <th scope="col">{t("boards.forecast.incident")}</th>
                    <th scope="col">{t("boards.gouvernorat")}</th>
                    <th scope="col">{t("boards.forecast.model")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.runs.map((r) => (
                    <tr key={r.id}>
                      <td>{fmt.dateTime(r.at)}</td>
                      <td>
                        {t(`forecast.kinds.${r.kind}`, { defaultValue: r.kind })}
                        {r.simulated && <SimTag />}
                      </td>
                      <td>
                        <Link to={`/incidents/${r.incident_id}`}>{r.incident_title ?? t("boards.open")}</Link>
                      </td>
                      <td>{nameOf(r.gouvernorat_code) ?? "—"}</td>
                      <td>{r.model}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- 17. citizens

const CITIZEN_DAYS = [30, 90, 365] as const;

export function CitizensPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const { nameOf } = useGouvernorats();
  const [days, setDays] = useState<number>(90);
  const query = useQuery({
    queryKey: boardsKeys.citizens(days),
    queryFn: ({ signal }) => api.citizensOverview(days, signal),
  });
  const data = query.data;
  const total = (k: "reporters" | "reports" | "rejected" | "kept" | "volunteers") =>
    (data?.gouvernorats ?? []).reduce((s, g) => s + g[k], 0);
  const n = data?.national;
  return (
    <div className="page boards-page">
      <PageTitle icon="accountCircle" tone="green">
        {t("boards.citizens.title")}
      </PageTitle>
      <p className="muted">{t("boards.citizens.intro")}</p>
      <Period value={days} options={CITIZEN_DAYS} onChange={setDays} label={(d) => t("boards.days", { n: d })} />
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {data && (
        <>
          <dl className="kpis" aria-label={t("boards.citizens.kpis")}>
            <Kpi label={t("boards.citizens.reporters")} value={fmt.number(total("reporters"))} />
            <Kpi label={t("boards.citizens.reports")} value={fmt.number(total("reports"))} />
            <Kpi label={t("boards.citizens.kept")} value={fmt.number(total("kept"))} />
            <Kpi label={t("boards.citizens.rejected")} value={fmt.number(total("rejected"))} />
            <Kpi label={t("boards.citizens.volunteers")} value={fmt.number(total("volunteers"))} />
            {n?.citizens !== undefined && (
              <Kpi label={t("boards.citizens.accounts")} value={fmt.number(n.citizens)} />
            )}
            {n?.anonymous !== undefined && (
              <Kpi label={t("boards.citizens.anonymous")} value={fmt.number(n.anonymous)} />
            )}
            {n?.ratings !== undefined && (
              <Kpi
                label={t("boards.citizens.rating")}
                value={n.rating === null || n.rating === undefined ? "—" : `${fmt.decimal(n.rating)} / 5`}
              />
            )}
          </dl>
          <p className="muted">
            {t("boards.citizens.privacy")} <Link to="/rewards">{t("nav.rewards")}</Link>
          </p>
          {data.gouvernorats.length === 0 ? (
            <p className="empty">{t("boards.citizens.empty")}</p>
          ) : (
            <div className="table-wrap card">
              <table className="table table--compact">
                <caption className="visually-hidden">{t("boards.citizens.table")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("boards.gouvernorat")}</th>
                    <th scope="col">{t("boards.citizens.reporters")}</th>
                    <th scope="col">{t("boards.citizens.reports")}</th>
                    <th scope="col">{t("boards.citizens.kept")}</th>
                    <th scope="col">{t("boards.citizens.rejected")}</th>
                    <th scope="col">{t("boards.citizens.volunteers")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.gouvernorats.map((g) => (
                    <tr key={g.gouvernorat_code}>
                      <th scope="row">{nameOf(g.gouvernorat_code)}</th>
                      <td>{fmt.number(g.reporters)}</td>
                      <td>{fmt.number(g.reports)}</td>
                      <td>{fmt.number(g.kept)}</td>
                      <td>{fmt.number(g.rejected)}</td>
                      <td>{fmt.number(g.volunteers)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- 19. the administrator's mother board

const SERVICES = ["database", "ai", "vision", "telephony", "notifications"] as const;

export function AdminBoardPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const query = useQuery({
    queryKey: boardsKeys.admin,
    queryFn: ({ signal }) => api.adminBoardOverview(signal),
    refetchInterval: 60_000,
  });
  const data = query.data;
  const weekTotal = data ? Object.values(data.accounts_week).reduce((s, v) => s + v, 0) : 0;
  return (
    <div className="page boards-page">
      <PageTitle icon="dashboard" tone="slate">
        {t("boards.admin.title")}
      </PageTitle>
      <p className="muted">{t("boards.admin.intro")}</p>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {data && (
        <>
          <h2>{t("boards.admin.services")}</h2>
          <dl className="kpis" aria-label={t("boards.admin.services")}>
            {SERVICES.map((s) => (
              <Kpi
                key={s}
                label={t(`boards.admin.service.${s}`)}
                value={t(`boards.admin.state.${data.services[s]}`)}
                tone={SERVICE_TONE[data.services[s]]}
              />
            ))}
          </dl>
          <h2>{t("boards.admin.activity")}</h2>
          <dl className="kpis">
            <Kpi label={t("boards.admin.accountsWeek")} value={fmt.number(weekTotal)} />
            <Kpi label={t("boards.admin.grants")} value={fmt.number(data.rules.grants)} />
            <Kpi label={t("boards.admin.hidden")} value={fmt.number(data.rules.hidden)} />
            <Kpi label={t("boards.admin.assignments")} value={fmt.number(data.rules.assignments)} />
          </dl>
          <p className="boards-links">
            <Link to="/settings/systems">{t("nav.systems")}</Link> · <Link to="/settings/menu">{t("nav.menuOrder")}</Link>{" "}
            · <Link to="/permissions">{t("nav.permissions")}</Link> · <Link to="/accounts">{t("nav.accounts")}</Link> ·{" "}
            <Link to="/settings">{t("nav.settings")}</Link>
          </p>
          <h2>{t("boards.admin.systems")}</h2>
          {data.systems.length === 0 ? (
            <p className="empty">{t("boards.admin.noSystemRules")}</p>
          ) : (
            <ul className="boards-list">
              {data.systems.map((r, i) => (
                <li key={`${r.key}-${i}`}>
                  <span className={`pill ${r.effect === "suspend" ? "tone-amber" : "tone-slate"}`}>
                    {t(`boards.admin.effect.${r.effect}`, { defaultValue: r.effect })}
                  </span>{" "}
                  {r.number !== null ? `${r.number}. ` : ""}
                  {r.key} · {t(`boards.admin.target.${r.target_kind}`, { defaultValue: r.target_kind })}
                  {r.target ? ` ${r.target}` : ""}
                  {r.message ? ` · «${localized(r.message, lang)}»` : ""}
                  {r.ends_at ? ` · ${t("boards.admin.until", { at: fmt.dateTime(r.ends_at) })}` : ""}
                </li>
              ))}
            </ul>
          )}
          <h2>{t("boards.admin.recent")}</h2>
          {data.recent.length === 0 ? (
            <p className="empty">{t("boards.admin.noRecent")}</p>
          ) : (
            <div className="table-wrap card">
              <table className="table table--compact">
                <caption className="visually-hidden">{t("boards.admin.recent")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("boards.at")}</th>
                    <th scope="col">{t("boards.admin.action")}</th>
                    <th scope="col">{t("boards.admin.targetCol")}</th>
                    <th scope="col">{t("boards.admin.reason")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent.map((e, i) => (
                    <tr key={`${e.at}-${i}`}>
                      <td>{fmt.dateTime(e.at)}</td>
                      <td>
                        <code>{e.action}</code>
                      </td>
                      <td>{e.target ?? "—"}</td>
                      <td>{e.reason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
