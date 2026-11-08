import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { useServices } from "../context/services";
import { useDebounced, useFormat } from "../lib/hooks";
import {
  systemKeys,
  type LogFilters,
  type LogLevel,
  type LogLine,
} from "../lib/systemApi";
import { ApiError } from "../lib/api";

const LEVELS: LogLevel[] = ["debug", "info", "warning", "error", "critical"];
const WINDOWS = [15, 60, 360, 1440, 10080];
// Fields already shown in their own column, or noise.
const SHOWN = new Set(["event", "level", "timestamp", "request_id", "path"]);

function levelClass(level: string | null): string {
  if (level === "error" || level === "critical")
    return "log-level log-level--error";
  if (level === "warning") return "log-level log-level--warning";
  return "log-level";
}

function lineText(line: LogLine): string {
  if (!line.fields) return line.text ?? "";
  return Object.entries(line.fields)
    .filter(([k]) => !SHOWN.has(k))
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(" ");
}

/**
 * The system logs (docs/phase-h/design-h5.md §1): errors of the last 24 hours by service, then the lines of one
 * service, one level or one request (its id ties the lines of the API, the worker and the change journal together).
 */
export function SystemLogsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const base = useId();
  const [params, setParams] = useSearchParams();
  const [filters, setFilters] = useState<LogFilters>({
    service: params.get("service") ?? "",
    level: (params.get("level") as LogLevel | null) ?? "",
    request_id: params.get("request_id") ?? "",
    contains: "",
    minutes: Number(params.get("minutes")) || 60,
  });
  const contains = useDebounced(filters.contains ?? "", 400);
  const effective = {
    ...filters,
    contains: contains.length >= 2 ? contains : "",
  };
  const summary = useQuery({
    queryKey: systemKeys.logSummary(24),
    queryFn: ({ signal }) => api.systemLogSummary(24, signal),
    retry: false,
  });
  const lines = useQuery({
    queryKey: systemKeys.logs(effective),
    queryFn: ({ signal }) => api.systemLogs(effective, signal),
    retry: false,
  });
  const off = [summary.error, lines.error].some(
    (e) => e instanceof ApiError && e.status === 503,
  );
  const set = (k: keyof LogFilters) => (e: { target: { value: string } }) =>
    setFilters((f) => ({
      ...f,
      [k]: k === "minutes" ? Number(e.target.value) : e.target.value,
    }));
  const follow = (patch: Partial<LogFilters>) => {
    const next = { ...filters, ...patch };
    setFilters(next);
    const p = new URLSearchParams();
    if (next.service) p.set("service", next.service);
    if (next.level) p.set("level", next.level);
    if (next.request_id) p.set("request_id", next.request_id);
    setParams(p, { replace: true });
  };

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="monitoring" tone="slate">
          {t("systemLogs.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("systemLogs.intro")}</p>
      {off && <p className="alert alert--warning">{t("systemLogs.off")}</p>}

      {summary.isSuccess && (
        <section aria-labelledby={`${base}-sum`}>
          <h2 id={`${base}-sum`} className="section-title">
            {t("systemLogs.last24h")}
          </h2>
          <ul className="kpis" role="list">
            {summary.data.services.map((s) => (
              <li
                key={s.service}
                className={`card kpi ${s.errors > 0 ? "kpi--high-priority" : ""}`}
              >
                <button
                  type="button"
                  className="link-button"
                  onClick={() => follow({ service: s.service, level: "error" })}
                >
                  <span className="kpi__label" dir="ltr">
                    {s.service}
                  </span>
                </button>
                <p className="kpi__value">{fmt.number(s.errors)}</p>
                <p className="muted">
                  {t("systemLogs.errorsWarnings", {
                    errors: s.errors,
                    warnings: s.warnings,
                  })}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${base}-service`}>{t("systemLogs.service")}</label>
          <select
            id={`${base}-service`}
            value={filters.service ?? ""}
            onChange={(e) => follow({ service: e.target.value })}
          >
            <option value="">{t("systemLogs.allServices")}</option>
            {(summary.data?.services ?? []).map((s) => (
              <option key={s.service} value={s.service}>
                {s.service}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${base}-level`}>{t("systemLogs.level")}</label>
          <select
            id={`${base}-level`}
            value={filters.level ?? ""}
            onChange={(e) => follow({ level: e.target.value as LogLevel | "" })}
          >
            <option value="">{t("systemLogs.allLevels")}</option>
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {t(`systemLogs.levels.${l}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${base}-minutes`}>{t("systemLogs.window")}</label>
          <select
            id={`${base}-minutes`}
            value={filters.minutes ?? 60}
            onChange={set("minutes")}
          >
            {WINDOWS.map((m) => (
              <option key={m} value={m}>
                {t(`systemLogs.windows.${m}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${base}-rid`}>{t("systemLogs.requestId")}</label>
          <input
            id={`${base}-rid`}
            dir="ltr"
            value={filters.request_id ?? ""}
            onChange={(e) => follow({ request_id: e.target.value.trim() })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${base}-contains`}>{t("systemLogs.contains")}</label>
          <input
            id={`${base}-contains`}
            dir="ltr"
            value={filters.contains ?? ""}
            onChange={set("contains")}
          />
        </div>
      </div>

      {lines.isPending && <Loading />}
      {lines.isError && !off && (
        <ErrorBox error={lines.error} onRetry={() => void lines.refetch()} />
      )}
      {lines.isSuccess && lines.data.items.length === 0 && (
        <p className="muted">{t("systemLogs.empty")}</p>
      )}
      {lines.isSuccess && lines.data.items.length > 0 && (
        <div className="table-wrap">
          <table className="table table--compact">
            <caption className="visually-hidden">
              {t("systemLogs.caption")}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t("systemLogs.at")}</th>
                <th scope="col">{t("systemLogs.service")}</th>
                <th scope="col">{t("systemLogs.level")}</th>
                <th scope="col">{t("systemLogs.event")}</th>
                <th scope="col">{t("systemLogs.requestId")}</th>
                <th scope="col">{t("systemLogs.details")}</th>
              </tr>
            </thead>
            <tbody>
              {lines.data.items.map((line, i) => (
                <tr key={`${line.at}-${i}`}>
                  <td>
                    <time dateTime={line.at}>{fmt.dateTime(line.at)}</time>
                  </td>
                  <td dir="ltr" className="code">
                    {line.service}
                  </td>
                  <td>
                    <span className={levelClass(line.level)}>
                      {line.level
                        ? t(`systemLogs.levels.${line.level}`, {
                            defaultValue: line.level,
                          })
                        : "—"}
                    </span>
                  </td>
                  <td dir="ltr" className="code">
                    {line.event ?? "—"}
                  </td>
                  <td dir="ltr">
                    {line.request_id ? (
                      <span className="log-trace">
                        <button
                          type="button"
                          className="link-button code"
                          title={t("systemLogs.followRequest")}
                          onClick={() =>
                            follow({
                              request_id: line.request_id ?? "",
                              service: "",
                              level: "",
                            })
                          }
                        >
                          {line.request_id.slice(0, 12)}
                        </button>
                        <Link
                          to={`/changes?request_id=${encodeURIComponent(line.request_id)}`}
                          title={t("systemLogs.changesOfRequest")}
                        >
                          {t("systemLogs.changes")}
                        </Link>
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td dir="ltr" className="code log-line">
                    {lineText(line)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
