import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { applyLiveEvent } from "../lib/liveCache";
import { reasonValid } from "../lib/phase9";
import { p9Keys } from "../lib/phase9Api";
import type { NearbyIncident } from "../lib/phase9Types";
import { canManageIncidents } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import { SUGGESTION_REASONS, type StaffReportDetail, type Suggestion } from "../lib/types";
import { PriorityBadge } from "./AiBadges";
import { CategoryLabel } from "./CategoryIcon";
import { ReasonField } from "./Phase9Bits";

type GroupingAction =
  | { kind: "accept" | "dismiss" | "detach" }
  | { kind: "link"; incidentId: string }
  | { kind: "new"; overrideReason?: string };

/** Incident ids of a `409 possible_duplicate` answer (phase 9 §5.2), or null for any other error. */
export function duplicateIds(error: unknown): string[] | null {
  if (!isApiError(error) || error.code !== "possible_duplicate") return null;
  const ids = error.body?.incident_ids;
  return Array.isArray(ids) ? ids.filter((x): x is string => typeof x === "string") : [];
}

/**
 * Open incidents near the report in any gouvernorat (phase 9 §5.2): linking adds the caller's gouvernorat as a
 * participant instead of opening a competing incident.
 */
function NearbyIncidents({
  items,
  canWrite,
  busy,
  onLink,
}: {
  items: NearbyIncident[];
  canWrite: boolean;
  busy: boolean;
  onLink: (id: string) => void;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  if (items.length === 0) return null;
  return (
    <div className="grouping__block alert alert--warn">
      <h3>{t("nearby.title")}</h3>
      <p>{t("nearby.warning")}</p>
      <ul className="nearby-list">
        {items.map((i) => {
          const lead = i.lead_gouvernorat_code ?? i.lead ?? null;
          const participants = i.participating_gouvernorats ?? i.participants ?? [];
          return (
            <li key={i.id}>
              <CategoryLabel category={i.category} /> <PriorityBadge score={i.severity} />{" "}
              <span>
                {t("nearby.lead", { name: gouvernorats.nameOf(lead) ?? t("command.noLead") })}
                {participants.length > 0 &&
                  ` · ${t("nearby.participants", {
                    list: participants.map((c) => gouvernorats.nameOf(c)).join(t("common.listSeparator")),
                  })}`}
                {` · ${t("nearby.reports", { count: i.report_count })} · `}
                <time dateTime={i.opened_at}>{fmt.dateTime(i.opened_at)}</time>
              </span>{" "}
              <Link to={`/incidents/${encodeURIComponent(i.id)}`}>{t("ai.grouping.openIncident")}</Link>{" "}
              {canWrite && (
                <button type="button" className="btn btn--small" disabled={busy} onClick={() => onLink(i.id)}>
                  {t("nearby.link")}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

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
  const [override, setOverride] = useState("");
  const [overrideTried, setOverrideTried] = useState(false);
  const nearby = useQuery({
    queryKey: p9Keys.nearby(report.id),
    queryFn: ({ signal }) => api.nearbyIncidents(report.id, signal),
    enabled: !report.incident_id,
    staleTime: 30_000,
  });

  const mutation = useMutation({
    mutationFn: (action: GroupingAction) => {
      switch (action.kind) {
        case "accept":
          return api.linkIncident(report.id, { action: "accept_suggestion" });
        case "link":
          return api.linkIncident(report.id, { action: "link", incident_id: action.incidentId });
        case "new":
          return api.linkIncident(
            report.id,
            action.overrideReason ? { action: "new", override_reason: action.overrideReason } : { action: "new" },
          );
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
      void qc.invalidateQueries({ queryKey: p9Keys.nearby(report.id) });
      setOverride("");
      setOverrideTried(false);
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
  const duplicates = mutation.isError ? duplicateIds(mutation.error) : null;

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
              <button type="button" className="btn" disabled={busy} onClick={() => run({ kind: "detach" })}>
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
              <button type="button" className="btn btn--primary" disabled={busy} onClick={() => run({ kind: "accept" })}>
                {t("ai.grouping.accept")}
              </button>
              <button type="button" className="btn" disabled={busy} onClick={() => run({ kind: "dismiss" })}>
                {t("ai.grouping.dismiss")}
              </button>
            </div>
          )}
        </div>
      )}

      {!report.incident_id && (
        <NearbyIncidents
          items={nearby.data ?? []}
          canWrite={canWrite}
          busy={busy}
          onLink={(incidentId) => run({ kind: "link", incidentId })}
        />
      )}

      {!report.incident_id && !suggestion && (
        <div className="grouping__block">
          <p className="muted">{t("ai.grouping.none")}</p>
          {canWrite && (
            <div className="actions">
              <button type="button" className="btn" disabled={busy} onClick={() => run({ kind: "new" })}>
                {t("ai.grouping.newIncident")}
              </button>
            </div>
          )}
        </div>
      )}

      {duplicates && (
        <div className="grouping__block alert alert--warn" role="alert">
          <p>{t("nearby.duplicate")}</p>
          <ul>
            {duplicates.map((id) => (
              <li key={id}>
                <Link to={`/incidents/${encodeURIComponent(id)}`}>{t("nearby.openDuplicate", { id: id.slice(0, 8) })}</Link>{" "}
                {canWrite && (
                  <button type="button" className="btn btn--small" disabled={busy} onClick={() => run({ kind: "link", incidentId: id })}>
                    {t("nearby.link")}
                  </button>
                )}
              </li>
            ))}
          </ul>
          {canWrite && (
            <form
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                setOverrideTried(true);
                if (reasonValid(override)) run({ kind: "new", overrideReason: override.trim() });
              }}
            >
              <ReasonField label={t("nearby.overrideReason")} value={override} onChange={setOverride} showError={overrideTried} />
              <button type="submit" className="btn" disabled={busy}>
                {t("nearby.createAnyway")}
              </button>
            </form>
          )}
        </div>
      )}

      {!canWrite && <p className="muted">{t("ai.grouping.readOnly")}</p>}
      <div aria-live="polite" role="status">
        {busy && <p className="muted">{t("ai.grouping.working")}</p>}
        {done && !busy && <p className="alert alert--ok">{t("ai.grouping.done")}</p>}
      </div>
      {mutation.isError && !duplicates && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </section>
  );
}
