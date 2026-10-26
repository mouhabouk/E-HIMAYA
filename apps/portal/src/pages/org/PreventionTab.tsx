import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "../../components/Badges";
import { CertificateChanges } from "../../components/CertificateExtras";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useServices } from "../../context/services";
import { useFormat } from "../../lib/hooks";
import { openPresigned } from "../../lib/openUrl";
import { queryKeys } from "../../lib/portalApi";
import {
  REQUIREMENTS,
  isOneOf,
  type InspectionResult,
  type Reservation,
  type ReservationState,
  type Visit,
  type VisitDecision,
  type VisitStatus,
} from "../../lib/types";
import { BlockedNote, useOrg } from "./OrgWorkspace";

type Tone = "ok" | "warn" | "danger" | "info" | "neutral";
const STATUS_TONE: Record<VisitStatus, Tone> = {
  requested: "info",
  scheduled: "warn",
  inspected: "info",
  decided: "ok",
  cancelled: "neutral",
};
const DECISION_TONE: Record<VisitDecision, Tone> = { approved: "ok", approved_with_reservations: "warn", refused: "danger" };
const STATE_TONE: Record<ReservationState, Tone> = { open: "warn", responded: "info", overdue: "danger", lifted: "ok" };
const RESULT_TONE: Record<InspectionResult, Tone> = { conform: "ok", nonconform: "danger", not_checked: "neutral" };
const OPEN: readonly VisitStatus[] = ["requested", "scheduled", "inspected"];
const FIRST_YEAR = 2020;

/** The grid item's name: fixed items have a label; materials are numbered and equipment uses its kind. */
export function itemLabel(t: TFunction, key: string): string {
  const [section, rest = ""] = key.split(".", 2);
  if (section === "hazmat") return t("prevention.item.hazmat", { n: Number(rest) + 1 });
  if (section === "equipment") return t(`equipmentKinds.${rest}`, { defaultValue: rest });
  return t(`prevention.item.${key}`, { defaultValue: key });
}

function declaredText(t: TFunction, key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (key === "classification.family" && typeof value === "string") return t(`family.${value}`, { defaultValue: value });
  return typeof value === "string" || typeof value === "number" ? String(value) : JSON.stringify(value);
}

function ResponseForm({ item }: { item: Reservation }) {
  const { t } = useTranslation();
  const { org } = useOrg();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [note, setNote] = useState(item.response_note ?? "");
  const [checked, setChecked] = useState(false);
  const send = useMutation({
    mutationFn: () => api.respondReservation(org.id, item.id, note.trim()),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.visits(org.id) }),
  });
  return (
    <form
      className="reservation__answer"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        setChecked(true);
        if (note.trim()) send.mutate();
      }}
    >
      <label htmlFor={id}>{t("prevention.answerLabel")}</label>
      <textarea id={id} rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
      {checked && !note.trim() && <p className="field__error">{t("validation.required")}</p>}
      {send.isError && <ErrorBox error={send.error} />}
      <button type="submit" className="btn btn--small" disabled={send.isPending}>
        {item.response_note ? t("prevention.updateAnswer") : t("prevention.answer")}
      </button>
    </form>
  );
}

function Reservations({ items }: { items: readonly Reservation[] }) {
  const { t } = useTranslation();
  const { can } = useOrg();
  const fmt = useFormat();
  return (
    <ul className="reservations">
      {items.map((r) => (
        <li key={r.id} className={`reservation reservation--${r.state}`}>
          <p>
            <Badge tone={STATE_TONE[r.state]}>{t(`prevention.state.${r.state}`)}</Badge> <b dir="auto">{r.text}</b>
          </p>
          <p className="muted">
            {t("prevention.dueOn", { date: fmt.date(r.due_on) })}
            {r.item_key && ` · ${itemLabel(t, r.item_key)}`}
          </p>
          {r.response_note && (
            <p>
              {t("prevention.yourAnswer", { name: r.responded_by_name ?? "—" })} <span dir="auto">{r.response_note}</span>
            </p>
          )}
          {r.lifted_at && (
            <p className="muted">
              {t("prevention.liftedOn", { date: fmt.date(r.lifted_at) })}
              {r.lift_note && ` · ${r.lift_note}`}
            </p>
          )}
          {!r.lifted_at && can("answerReservations") && <ResponseForm item={r} />}
        </li>
      ))}
    </ul>
  );
}

function Comparison({ visit }: { visit: Visit }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const report = visit.comparison;
  if (!report) return null;
  return (
    <details className="comparison">
      <summary>
        {t("prevention.comparisonSummary", {
          conform: fmt.number(report.conform),
          nonconform: fmt.number(report.nonconform),
          notChecked: fmt.number(report.not_checked),
        })}
      </summary>
      {report.missing.length > 0 && (
        <p>
          {t("prevention.missing", {
            items: report.missing.map((m) => (isOneOf(REQUIREMENTS, m) ? t(`requirements.${m}`) : m)).join("، "),
          })}
        </p>
      )}
      {report.changes.length > 0 && (
        <>
          <h4>{t("prevention.changesTitle")}</h4>
          <CertificateChanges changes={report.changes} />
        </>
      )}
      <div className="table-wrap">
        <table className="table">
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
              <tr key={i.key}>
                <th scope="row">{itemLabel(t, i.key)}</th>
                <td dir="auto">{declaredText(t, i.key, i.declared)}</td>
                <td>
                  <Badge tone={RESULT_TONE[i.result]}>{t(`prevention.result.${i.result}`)}</Badge>
                </td>
                <td dir="auto">{[i.observed, i.note].filter(Boolean).join(" · ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function VisitCard({ visit }: { visit: Visit }) {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const qc = useQueryClient();
  const fmt = useFormat();
  const [link, setLink] = useState<string | null>(null);
  const open = useMutation({
    mutationFn: (get: () => Promise<{ url: string }>) => openPresigned(get),
    onSuccess: setLink,
  });
  const withdraw = useMutation({
    mutationFn: () => api.withdrawVisit(org.id, visit.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.visits(org.id) }),
  });
  const cert = visit.certificate;
  return (
    <article className="card visit" aria-labelledby={`visit-${visit.id}`}>
      <h3 id={`visit-${visit.id}`} className="visit__head">
        {t(`prevention.origin.${visit.origin}`)} · {fmt.date(visit.inspected_on ?? visit.scheduled_on ?? visit.created_at)}{" "}
        <Badge tone={STATUS_TONE[visit.status]}>{t(`prevention.status.${visit.status}`)}</Badge>{" "}
        {visit.decision && <Badge tone={DECISION_TONE[visit.decision]}>{t(`prevention.decision.${visit.decision}`)}</Badge>}
      </h3>
      <dl className="fields">
        {visit.scheduled_on && (
          <>
            <dt>{t("prevention.scheduledOn")}</dt>
            <dd>{fmt.date(visit.scheduled_on)}</dd>
          </>
        )}
        {visit.inspector_name && (
          <>
            <dt>{t("prevention.inspector")}</dt>
            <dd>{visit.inspector_name}</dd>
          </>
        )}
        {visit.inspected_on && (
          <>
            <dt>{t("prevention.inspectedOn")}</dt>
            <dd>{fmt.date(visit.inspected_on)}</dd>
          </>
        )}
        {visit.decision_reason && (
          <>
            <dt>{t("prevention.reason")}</dt>
            <dd dir="auto">{visit.decision_reason}</dd>
          </>
        )}
        {visit.cancel_reason && (
          <>
            <dt>{t("prevention.cancelReason")}</dt>
            <dd dir="auto">{visit.cancel_reason}</dd>
          </>
        )}
        {cert && (
          <>
            <dt>{t("prevention.certificate")}</dt>
            <dd>
              <span className="code">{cert.code}</span> <span className="tag tag--sim">[SIM]</span> ·{" "}
              {t("prevention.validUntil", { date: fmt.date(cert.valid_until) })}
              {cert.superseded && ` · ${t("prevention.superseded")}`}
            </dd>
          </>
        )}
      </dl>
      {visit.status === "requested" && (
        <p className="muted">{t("prevention.waiting")}</p>
      )}
      {visit.status === "scheduled" && <p className="alert alert--warn">{t("prevention.prepare")}</p>}
      <Comparison visit={visit} />
      {visit.reservations.length > 0 && (
        <>
          <h4>{t("prevention.reservationsTitle")}</h4>
          <Reservations items={visit.reservations} />
        </>
      )}
      <div className="actions">
        {visit.has_report && (
          <button type="button" className="btn" disabled={open.isPending} onClick={() => open.mutate(() => api.visitReport(org.id, visit.id))}>
            {t("prevention.report")}
          </button>
        )}
        {cert && (
          <button
            type="button"
            className="btn"
            disabled={open.isPending}
            onClick={() => open.mutate(() => api.certificatePdf(org.id, cert.id))}
          >
            {t("prevention.certificatePdf")}
          </button>
        )}
        {visit.status === "requested" && can("requestVisit") && (
          <button type="button" className="btn" disabled={withdraw.isPending} onClick={() => withdraw.mutate()}>
            {t("prevention.withdraw")}
          </button>
        )}
      </div>
      {link && (
        <p>
          <a href={link} target="_blank" rel="noopener noreferrer">
            {t("prevention.openLink")}
          </a>
        </p>
      )}
      {(open.isError || withdraw.isError) && <ErrorBox error={open.error ?? withdraw.error} />}
    </article>
  );
}

function RequestForm() {
  const { t } = useTranslation();
  const { org } = useOrg();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [note, setNote] = useState("");
  const send = useMutation({
    mutationFn: () => api.requestVisit(org.id, note.trim() || null),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.visits(org.id) }),
  });
  return (
    <form
      className="form"
      onSubmit={(e) => {
        e.preventDefault();
        send.mutate();
      }}
    >
      <div className="field">
        <label htmlFor={id}>{t("prevention.requestNote")}</label>
        <textarea id={id} rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      {send.isError && <ErrorBox error={send.error} />}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={send.isPending}>
          {t("prevention.request")}
        </button>
      </div>
    </form>
  );
}

function AnnualReportSection() {
  const { t } = useTranslation();
  const { org } = useOrg();
  const { api } = useServices();
  const fmt = useFormat();
  const id = useId();
  const current = new Date().getFullYear();
  const [year, setYear] = useState(current);
  const query = useQuery({
    queryKey: queryKeys.annual(org.id, year),
    queryFn: ({ signal }) => api.annualReport(org.id, year, signal),
  });
  const years = Array.from({ length: current - FIRST_YEAR + 1 }, (_, i) => current - i);
  const r = query.data;
  return (
    <section className="card" aria-labelledby="annual-title">
      <div className="section-head">
        <h2 id="annual-title">{t("prevention.annualTitle")}</h2>
        <div className="field field--inline">
          <label htmlFor={id}>{t("prevention.year")}</label>
          <select id={id} value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {r && (
        <dl className="fields annual">
          <dt>{t("prevention.annual.drills")}</dt>
          <dd>{t("prevention.annual.drillsValue", { n: fmt.number(r.drills.length), people: fmt.number(r.participants) })}</dd>
          <dt>{t("prevention.annual.events")}</dt>
          <dd>{fmt.number(r.events.length)}</dd>
          <dt>{t("prevention.annual.maintenance")}</dt>
          <dd>{fmt.number(r.maintenance)}</dd>
          <dt>{t("prevention.annual.training")}</dt>
          <dd>
            {t("prevention.annual.trainingValue", {
              valid: fmt.number(r.training.valid),
              expiring: fmt.number(r.training.expiring),
              expired: fmt.number(r.training.expired),
            })}
          </dd>
          <dt>{t("prevention.annual.visits")}</dt>
          <dd>
            {r.visits.length === 0
              ? "—"
              : r.visits
                  .map((v) => (v.decision ? t(`prevention.decision.${v.decision}`) : t(`prevention.status.${v.status}`)))
                  .join("، ")}
          </dd>
          <dt>{t("prevention.annual.reservations")}</dt>
          <dd>
            {t("prevention.annual.reservationsValue", {
              opened: fmt.number(r.reservations.opened),
              lifted: fmt.number(r.reservations.lifted),
              overdue: fmt.number(r.reservations.overdue),
            })}
          </dd>
          <dt>{t("prevention.annual.certificates")}</dt>
          <dd>{r.certificates.length === 0 ? "—" : r.certificates.map((c) => c.code).join("، ")}</dd>
          <dt>{t("prevention.annual.stamps")}</dt>
          <dd>{fmt.number(r.stamps)}</dd>
          <dt>{t("prevention.annual.reports")}</dt>
          <dd>{fmt.number(r.reports)}</dd>
        </dl>
      )}
    </section>
  );
}

/** F-POR-08: ask for a prevention visit, follow it to the decision, answer the reservations; the annual report. */
export function PreventionTab() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const list = useQuery({ queryKey: queryKeys.visits(org.id), queryFn: ({ signal }) => api.visits(org.id, signal) });

  if (list.isPending) return <Loading />;
  if (list.isError) return <ErrorBox error={list.error} onRetry={() => void list.refetch()} />;
  const hasOpen = list.data.some((v) => OPEN.includes(v.status));

  return (
    <div className="stack">
      <section className="card" aria-labelledby="prevention-title">
        <div className="section-head">
          <h2 id="prevention-title">{t("prevention.title")}</h2>
        </div>
        <p className="muted">{t("prevention.help")}</p>
        <p className="alert alert--info">
          <span className="tag tag--sim">[SIM]</span> {t("prevention.simNote")}
        </p>
        <BlockedNote action="requestVisit" />
        {!hasOpen && can("requestVisit") && <RequestForm />}
        {list.data.length === 0 ? (
          <p className="empty">{t("prevention.empty")}</p>
        ) : (
          <div className="visits">
            {list.data.map((v) => (
              <VisitCard key={v.id} visit={v} />
            ))}
          </div>
        )}
      </section>
      <AnnualReportSection />
    </div>
  );
}
