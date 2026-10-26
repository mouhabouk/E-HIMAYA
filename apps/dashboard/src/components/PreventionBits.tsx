import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { useServices } from "../context/services";
import type { Formatters } from "../lib/format";
import { useFormat } from "../lib/hooks";
import { isoDate } from "../lib/orgs";
import type { ComparisonReport, Reservation, ReservationState, Visit, VisitDecision, VisitStatus } from "../lib/preventionApi";
import { CertificateChanges } from "./CertificateExtras";
import { ErrorBox, Loading } from "./Feedback";
import { equipmentKindLabel, familyLabel, formatDay, requirementLabel } from "./OrgBits";

const STATUS_TONE: Record<VisitStatus, string> = {
  requested: "warn",
  scheduled: "warn",
  inspected: "warn",
  decided: "ok",
  cancelled: "none",
};
const DECISION_TONE: Record<VisitDecision, string> = {
  approved: "ok",
  approved_with_reservations: "warn",
  refused: "bad",
};
const STATE_TONE: Record<ReservationState, string> = { open: "warn", responded: "warn", overdue: "bad", lifted: "ok" };

export function VisitStatusTag({ status }: { status: VisitStatus }) {
  const { t } = useTranslation();
  return <span className={`tag tag--level-${STATUS_TONE[status]}`}>{t(`prevention.status.${status}`)}</span>;
}

export function DecisionTag({ decision }: { decision: VisitDecision }) {
  const { t } = useTranslation();
  return <span className={`tag tag--level-${DECISION_TONE[decision]}`}>{t(`prevention.decision.${decision}`)}</span>;
}

/** The grid item's name: fixed items have a label; materials are numbered and equipment uses its kind. */
export function itemLabel(t: TFunction, key: string): string {
  const [section, rest = ""] = key.split(".", 2);
  if (section === "hazmat") return t("prevention.item.hazmat", { n: Number(rest) + 1 });
  if (section === "equipment") return equipmentKindLabel(t, rest);
  return t(`prevention.item.${key}`, { defaultValue: key });
}

export function declaredText(t: TFunction, fmt: Formatters, key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (key === "classification.family" && typeof value === "string") return familyLabel(t, value);
  if (typeof value === "number") return fmt.number(value);
  return typeof value === "string" ? value : JSON.stringify(value);
}

/** The automatic comparison report: counts, missing items, changes since the safety certificate, then the grid. */
export function ComparisonView({ report }: { report: ComparisonReport }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <div className="comparison">
      <p className="comparison__counts">
        <span className="tag tag--level-ok">{t("prevention.counts.conform", { n: fmt.number(report.conform) })}</span>
        <span className={`tag tag--level-${report.nonconform > 0 ? "bad" : "none"}`}>
          {t("prevention.counts.nonconform", { n: fmt.number(report.nonconform) })}
        </span>
        <span className="tag tag--level-none">
          {t("prevention.counts.notChecked", { n: fmt.number(report.not_checked) })}
        </span>
        <span className="muted">
          {t("prevention.suggested", { decision: t(`prevention.decision.${report.suggested}`) })}
        </span>
      </p>
      <p>
        {report.missing.length === 0
          ? t("prevention.noMissing")
          : t("prevention.missing", {
              items: report.missing.map((m) => requirementLabel(t, m)).join(t("common.listSeparator")),
            })}
      </p>
      {report.changes.length > 0 && (
        <>
          <h3>{t("prevention.changesTitle")}</h3>
          <CertificateChanges changes={report.changes} />
        </>
      )}
      <table className="table inspection-grid">
        <caption className="visually-hidden">{t("prevention.gridCaption")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("prevention.columns.item")}</th>
            <th scope="col">{t("prevention.columns.declared")}</th>
            <th scope="col">{t("prevention.columns.result")}</th>
            <th scope="col">{t("prevention.columns.observed")}</th>
          </tr>
        </thead>
        <tbody>
          {report.items.map((i) => (
            <tr key={i.key} className={i.result === "nonconform" ? "is-nonconform" : undefined}>
              <th scope="row">{itemLabel(t, i.key)}</th>
              <td dir="auto">{declaredText(t, fmt, i.key, i.declared)}</td>
              <td>
                <span
                  className={`tag tag--level-${i.result === "conform" ? "ok" : i.result === "nonconform" ? "bad" : "none"}`}
                >
                  {t(`prevention.result.${i.result}`)}
                </span>
              </td>
              <td dir="auto">{[i.observed, i.note].filter(Boolean).join(" · ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LiftForm({ item, onDone }: { item: Reservation; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const [note, setNote] = useState("");
  const mutation = useMutation({ mutationFn: () => api.liftReservation(item.id, note.trim() || null), onSuccess: onDone });
  return (
    <form
      className="reservation__lift"
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate();
      }}
    >
      <label htmlFor={id} className="visually-hidden">
        {t("prevention.liftNote")}
      </label>
      <input id={id} value={note} maxLength={500} placeholder={t("prevention.liftNote")} onChange={(e) => setNote(e.target.value)} />
      <button type="submit" className="btn" disabled={mutation.isPending}>
        {t("prevention.lift")}
      </button>
      {mutation.isError && <ErrorBox error={mutation.error} />}
    </form>
  );
}

/** Reservations with their deadline and state; the auditor lifts them. */
export function ReservationList({
  items,
  canLift,
  onChanged,
}: {
  items: readonly Reservation[];
  canLift: boolean;
  onChanged: () => void;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  if (items.length === 0) return <p className="muted">{t("prevention.noReservations")}</p>;
  return (
    <ul className="reservations">
      {items.map((r) => (
        <li key={r.id} className={`reservation reservation--${r.state}`}>
          <p>
            <span className={`tag tag--level-${STATE_TONE[r.state]}`}>{t(`prevention.state.${r.state}`)}</span>{" "}
            <b dir="auto">{r.text}</b>
          </p>
          <p className="muted">
            {t("prevention.dueOn", { date: fmt.date(r.due_on) })}
            {r.item_key && ` · ${itemLabel(t, r.item_key)}`}
          </p>
          {r.response_note && (
            <p>
              {t("prevention.response", { name: r.responded_by_name ?? "—" })} <span dir="auto">{r.response_note}</span>
            </p>
          )}
          {r.lifted_at && (
            <p className="muted">
              {t("prevention.liftedBy", { name: r.lifted_by_name ?? "—", date: fmt.date(r.lifted_at) })}
              {r.lift_note && ` · ${r.lift_note}`}
            </p>
          )}
          {canLift && !r.lifted_at && <LiftForm item={r} onDone={onChanged} />}
        </li>
      ))}
    </ul>
  );
}

function ScheduleNew({ orgId }: { orgId: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const navigate = useNavigate();
  const ids = useId();
  const [day, setDay] = useState(isoDate(new Date()));
  const [inspector, setInspector] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.scheduleNewVisit(orgId, { scheduled_on: day, inspector_name: inspector.trim() || null }),
    onSuccess: (visit) => void navigate(`/orgs/prevention/${encodeURIComponent(visit.id)}`),
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (day) mutation.mutate();
  };
  return (
    <form className="visit-form visit-form--inline" onSubmit={submit} aria-label={t("prevention.scheduleNew")}>
      <div className="field">
        <label htmlFor={`${ids}-day`}>{t("prevention.scheduledOn")}</label>
        <input id={`${ids}-day`} type="date" value={day} min={isoDate(new Date())} onChange={(e) => setDay(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor={`${ids}-who`}>{t("prevention.inspector")}</label>
        <input id={`${ids}-who`} value={inspector} maxLength={120} onChange={(e) => setInspector(e.target.value)} />
      </div>
      <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
        {t("prevention.scheduleNew")}
      </button>
      {mutation.isError && <ErrorBox error={mutation.error} />}
    </form>
  );
}

/** The institution's visits on its page in the dashboard, with "schedule a visit" for the auditor. */
export function OrgVisits({ orgId, canAct }: { orgId: string; canAct: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["org-visits", orgId],
    queryFn: ({ signal }) => api.orgPreventionVisits(orgId, signal),
  });
  const visits: Visit[] = query.data ?? [];
  const open = visits.some((v) => ["requested", "scheduled", "inspected"].includes(v.status));
  return (
    <section className="card" aria-labelledby="sec-org-prevention">
      <h2 id="sec-org-prevention">{t("prevention.orgTitle")}</h2>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void qc.invalidateQueries({ queryKey: ["org-visits", orgId] })} />}
      {query.isSuccess && visits.length === 0 && <p className="muted">{t("prevention.noVisits")}</p>}
      {visits.length > 0 && (
        <ul className="visits">
          {visits.map((v) => (
            <li key={v.id}>
              <Link to={`/orgs/prevention/${encodeURIComponent(v.id)}`}>
                {t(`prevention.origin.${v.origin}`)} · {formatDay(fmt, v.inspected_on ?? v.scheduled_on ?? v.created_at, "—")}
              </Link>{" "}
              <VisitStatusTag status={v.status} /> {v.decision && <DecisionTag decision={v.decision} />}{" "}
              {v.certificate && (
                <span className="code" dir="ltr">
                  {v.certificate.code}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {canAct && query.isSuccess && !open && <ScheduleNew orgId={orgId} />}
    </section>
  );
}
