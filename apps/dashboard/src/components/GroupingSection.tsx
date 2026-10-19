import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat } from "../lib/hooks";
import { applyLiveEvent } from "../lib/liveCache";
import { canManageIncidents } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import { SUGGESTION_REASONS, type StaffReportDetail, type Suggestion } from "../lib/types";

type GroupingAction = "accept" | "dismiss" | "detach" | "new";

function SuggestionView({ suggestion }: { suggestion: Suggestion }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <div className="suggestion">
      <p>
        {suggestion.kind === "incident" && suggestion.incident_id ? (
          <Link to={`/incidents/${encodeURIComponent(suggestion.incident_id)}`}>
            {t("ai.grouping.suggestionIncident")}
          </Link>
        ) : (
          <>
            {t("ai.grouping.suggestionReport")}{" "}
            <Link to={`/reports/${encodeURIComponent(suggestion.report_id)}`} className="code" dir="ltr">
              {suggestion.tracking_code}
            </Link>
          </>
        )}
      </p>
      <dl className="fields">
        <dt>{t("ai.grouping.distance")}</dt>
        <dd>{fmt.meters(suggestion.distance_m)}</dd>
        <dt>{t("ai.grouping.minutes")}</dt>
        <dd>{fmt.duration(suggestion.minutes * 60)}</dd>
        <dt>{t("ai.grouping.similarity")}</dt>
        <dd>{suggestion.similarity === null ? t("common.notAvailable") : fmt.percent(suggestion.similarity)}</dd>
        <dt>{t("ai.grouping.score")}</dt>
        <dd>{fmt.percent(suggestion.score)}</dd>
        <dt>{t("ai.grouping.matching")}</dt>
        <dd>{fmt.number(suggestion.matching_reports)}</dd>
        <dt>{t("ai.grouping.reasons")}</dt>
        <dd>
          {suggestion.reasons.map((r) => (
            <span key={r} className="tag">
              {(SUGGESTION_REASONS as readonly string[]).includes(r)
                ? t(`ai.grouping.reason.${r}`)
                : t("ai.componentOther", { key: r })}
            </span>
          ))}
        </dd>
      </dl>
    </div>
  );
}

/**
 * Grouping of a report into an incident (BR-10, BR-11): the waiting suggestion with its reasons,
 * the current incident, or a new one. Write actions only for the status-change roles.
 */
export function GroupingSection({ report }: { report: StaffReportDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const canWrite = canManageIncidents(user?.identity.roles ?? []);
  const [done, setDone] = useState(false);
  const key = queryKeys.report(report.id);
  const suggestion = report.has_suggestion ? (report.analysis?.suggestion ?? null) : null;

  const mutation = useMutation({
    mutationFn: (action: GroupingAction) => {
      switch (action) {
        case "accept":
          return api.linkIncident(report.id, { action: "accept_suggestion" });
        case "new":
          return api.linkIncident(report.id, { action: "new" });
        case "detach":
          return api.detachIncident(report.id);
        case "dismiss":
          return api.dismissSuggestion(report.id);
      }
    },
    onSuccess: (updated) => {
      qc.setQueryData(key, updated);
      // Same cache path as a live update; the status did not change, so the detail is not refetched.
      applyLiveEvent(qc, { type: "report.status_changed", report: updated });
      void qc.invalidateQueries({ queryKey: queryKeys.incidentsAll });
      void qc.invalidateQueries({ queryKey: queryKeys.incidentAll });
      setDone(true);
    },
    onError: (error) => {
      // 409 (suggestion outdated, incident closed…): someone else acted first — fetch the truth.
      if (isApiError(error) && error.status === 409) void qc.invalidateQueries({ queryKey: key });
    },
  });

  const run = (action: GroupingAction) => {
    setDone(false);
    mutation.mutate(action);
  };
  const busy = mutation.isPending;

  return (
    <section className="card grouping" aria-labelledby="sec-grouping">
      <h2 id="sec-grouping">{t("ai.grouping.title")}</h2>

      {report.incident_id && (
        <div className="grouping__block">
          <p>{t("ai.grouping.inIncident")}</p>
          <div className="actions">
            <Link className="btn" to={`/incidents/${encodeURIComponent(report.incident_id)}`}>
              {t("ai.grouping.openIncident")}
            </Link>
            {canWrite && (
              <button type="button" className="btn" disabled={busy} onClick={() => run("detach")}>
                {t("ai.grouping.remove")}
              </button>
            )}
          </div>
        </div>
      )}

      {suggestion && (
        <div className="grouping__block">
          <h3>{t("ai.grouping.suggestionTitle")}</h3>
          <SuggestionView suggestion={suggestion} />
          {canWrite && (
            <div className="actions">
              <button type="button" className="btn btn--primary" disabled={busy} onClick={() => run("accept")}>
                {t("ai.grouping.accept")}
              </button>
              <button type="button" className="btn" disabled={busy} onClick={() => run("dismiss")}>
                {t("ai.grouping.dismiss")}
              </button>
            </div>
          )}
        </div>
      )}

      {!report.incident_id && !suggestion && (
        <div className="grouping__block">
          <p className="muted">{t("ai.grouping.none")}</p>
          {canWrite && (
            <div className="actions">
              <button type="button" className="btn" disabled={busy} onClick={() => run("new")}>
                {t("ai.grouping.newIncident")}
              </button>
            </div>
          )}
        </div>
      )}

      {!canWrite && <p className="muted">{t("ai.grouping.readOnly")}</p>}
      <div aria-live="polite" role="status">
        {busy && <p className="muted">{t("ai.grouping.working")}</p>}
        {done && !busy && <p className="alert alert--ok">{t("ai.grouping.done")}</p>}
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </section>
  );
}
