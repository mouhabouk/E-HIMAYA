import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { DownloadButton, formatDay, orgKindLabel } from "../components/OrgBits";
import { PageTitle } from "../components/PageTitle";
import {
  ComparisonView,
  DecisionTag,
  declaredText,
  FieldEvidence,
  itemLabel,
  ReservationList,
  VisitStatusTag,
} from "../components/PreventionBits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { isoDate } from "../lib/orgs";
import {
  INSPECTION_RESULTS,
  PREVENTION_DEFAULT_MONTHS,
  RESERVATION_MAX_MONTHS,
  VISIT_DECISIONS,
  VISIT_STATUSES,
  type InspectionResult,
  type StaffVisit,
  type VisitDecision,
  type VisitStatus,
} from "../lib/preventionApi";
import { canReviewOrgs } from "../lib/roles";

const OPEN: readonly VisitStatus[] = ["requested", "scheduled", "inspected"];
const FILTERS = ["open", ...VISIT_STATUSES, "all"] as const;
type Filter = (typeof FILTERS)[number];

export function addMonths(day: string, months: number): string {
  const d = new Date(`${day}T12:00:00Z`);
  const target = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + months, 1, 12));
  const last = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0, 12)).getUTCDate();
  target.setUTCDate(Math.min(d.getUTCDate(), last));
  return target.toISOString().slice(0, 10);
}

export function addDays(day: string, days: number): string {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** F-POR-08 / F-DSH-34: the prevention visits in scope, open ones first by default. */
export function PreventionPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const [params, setParams] = useSearchParams();
  const raw = params.get("status");
  const filter: Filter = (FILTERS as readonly string[]).includes(raw ?? "") ? (raw as Filter) : "open";
  const statuses: readonly VisitStatus[] = filter === "open" ? OPEN : filter === "all" ? [] : [filter];
  const filterId = useId();

  const query = useInfiniteQuery({
    queryKey: ["prevention-visits", filter],
    queryFn: ({ pageParam, signal }) => api.preventionVisits({ status: statuses, cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="policy" tone="purple">
          {t("prevention.title")}
        </PageTitle>
        <Link to="/orgs">{t("orgs.detail.back")}</Link>
      </div>
      <p className="muted">{t("prevention.intro")}</p>
      <div className="filters card filters__row">
        <div className="field">
          <label htmlFor={filterId}>{t("prevention.filter")}</label>
          <select
            id={filterId}
            value={filter}
            onChange={(e) => setParams(e.target.value === "open" ? {} : { status: e.target.value }, { replace: true })}
          >
            {FILTERS.map((f) => (
              <option key={f} value={f}>
                {f === "open" || f === "all" ? t(`prevention.filters.${f}`) : t(`prevention.status.${f}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="card empty">{t("prevention.empty")}</p>}
      {items.length > 0 && (
        <ol className="queue" aria-label={t("prevention.title")}>
          {items.map((v) => {
            const overdue = v.reservations.filter((r) => r.state === "overdue").length;
            return (
              <li key={v.id} className="card queue__item">
                <p className="cert__head">
                  <Link to={`/orgs/prevention/${encodeURIComponent(v.id)}`} dir="auto">
                    {v.org_name}
                  </Link>
                  <VisitStatusTag status={v.status} />
                  {v.decision && <DecisionTag decision={v.decision} />}
                  {overdue > 0 && (
                    <span className="tag tag--level-bad">{t("prevention.overdueCount", { n: fmt.number(overdue) })}</span>
                  )}
                </p>
                <dl className="fields">
                  <dt>{t("orgs.certs.columns.gouvernorat")}</dt>
                  <dd>{gouvernorats.nameOf(v.gouvernorat_code) ?? t("common.notAvailable")}</dd>
                  <dt>{t("prevention.originLabel")}</dt>
                  <dd>
                    {t(`prevention.origin.${v.origin}`)} · {orgKindLabel(t, v.org_kind)}
                  </dd>
                  <dt>{t("prevention.scheduledOn")}</dt>
                  <dd>{formatDay(fmt, v.scheduled_on, "—")}</dd>
                  <dt>{t("prevention.inspectedOn")}</dt>
                  <dd>{formatDay(fmt, v.inspected_on, "—")}</dd>
                </dl>
              </li>
            );
          })}
        </ol>
      )}
      {query.hasNextPage && (
        <div className="load-more">
          <button type="button" className="btn" onClick={() => void query.fetchNextPage()} disabled={query.isFetchingNextPage}>
            {query.isFetchingNextPage ? t("common.loading") : t("reports.loadMore")}
          </button>
        </div>
      )}
    </div>
  );
}

function ScheduleForm({ visit, onDone }: { visit: StaffVisit; onDone: (v: StaffVisit) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const ids = useId();
  const today = isoDate(new Date());
  const [day, setDay] = useState(visit.scheduled_on ?? today);
  const [inspector, setInspector] = useState(visit.inspector_name ?? "");
  const mutation = useMutation({
    mutationFn: () => api.scheduleVisit(visit.id, { scheduled_on: day, inspector_name: inspector.trim() || null }),
    onSuccess: onDone,
  });
  return (
    <form
      className="card visit-form"
      aria-labelledby={`${ids}-t`}
      onSubmit={(e) => {
        e.preventDefault();
        if (day && day >= today) mutation.mutate();
      }}
    >
      <h2 id={`${ids}-t`}>{visit.status === "requested" ? t("prevention.schedule") : t("prevention.reschedule")}</h2>
      <div className="visit-form__row">
        <div className="field">
          <label htmlFor={`${ids}-day`}>{t("prevention.scheduledOn")}</label>
          <input id={`${ids}-day`} type="date" value={day} min={today} onChange={(e) => setDay(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={`${ids}-who`}>{t("prevention.inspector")}</label>
          <input id={`${ids}-who`} value={inspector} maxLength={120} onChange={(e) => setInspector(e.target.value)} />
        </div>
      </div>
      {mutation.isError && <ErrorBox error={mutation.error} />}
      <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
        {t("prevention.saveSchedule")}
      </button>
    </form>
  );
}

interface Row {
  result: InspectionResult;
  observed: string;
  note: string;
}
const EMPTY_ROW: Row = { result: "not_checked", observed: "", note: "" };

function InspectionForm({ visit, onDone }: { visit: StaffVisit; onDone: (v: StaffVisit) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const ids = useId();
  const today = isoDate(new Date());
  const previous = new Map((visit.comparison?.items ?? []).map((i) => [i.key, i]));
  const [rows, setRows] = useState<Record<string, Row>>(() =>
    Object.fromEntries(
      visit.checklist.map((c) => {
        const p = previous.get(c.key);
        return [c.key, { result: p?.result ?? "not_checked", observed: p?.observed ?? "", note: p?.note ?? "" }];
      }),
    ),
  );
  const [day, setDay] = useState(visit.inspected_on ?? (visit.scheduled_on && visit.scheduled_on <= today ? visit.scheduled_on : today));
  const [attendees, setAttendees] = useState(visit.attendees ?? "");
  const [checked, setChecked] = useState(false);
  const set = (key: string, patch: Partial<Row>) =>
    setRows((r) => ({ ...r, [key]: { ...(r[key] ?? EMPTY_ROW), ...patch } }));
  const lacking = Object.entries(rows).filter(([, r]) => r.result === "nonconform" && !r.observed.trim() && !r.note.trim());

  const mutation = useMutation({
    mutationFn: () =>
      api.recordInspection(visit.id, {
        inspected_on: day,
        attendees: attendees.trim() || null,
        items: Object.entries(rows)
          .filter(([, r]) => r.result !== "not_checked")
          .map(([key, r]) => ({ key, result: r.result, observed: r.observed.trim() || null, note: r.note.trim() || null })),
      }),
    onSuccess: onDone,
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setChecked(true);
    if (!day || day > today || lacking.length > 0) return;
    mutation.mutate();
  };

  return (
    <form className="card visit-form" onSubmit={submit} noValidate aria-labelledby={`${ids}-t`}>
      <h2 id={`${ids}-t`}>{t("prevention.inspection")}</h2>
      <p className="muted">{t("prevention.inspectionHelp")}</p>
      <div className="visit-form__row">
        <div className="field">
          <label htmlFor={`${ids}-day`}>{t("prevention.inspectedOn")}</label>
          <input id={`${ids}-day`} type="date" value={day} max={today} onChange={(e) => setDay(e.target.value)} />
        </div>
        <div className="field field--grow">
          <label htmlFor={`${ids}-att`}>{t("prevention.attendees")}</label>
          <input id={`${ids}-att`} value={attendees} maxLength={500} onChange={(e) => setAttendees(e.target.value)} />
        </div>
      </div>
      <p>
        <button
          type="button"
          className="btn"
          onClick={() =>
            setRows((r) =>
              Object.fromEntries(
                Object.entries(r).map(([k, v]) => [k, v.result === "not_checked" ? { ...v, result: "conform" as const } : v]),
              ),
            )
          }
        >
          {t("prevention.allConform")}
        </button>
      </p>
      <table className="table inspection-grid inspection-grid--edit">
        <caption className="visually-hidden">{t("prevention.gridCaption")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("prevention.columns.item")}</th>
            <th scope="col">{t("prevention.columns.declared")}</th>
            <th scope="col">{t("prevention.columns.result")}</th>
            <th scope="col">{t("prevention.columns.observed")}</th>
            <th scope="col">{t("prevention.columns.note")}</th>
          </tr>
        </thead>
        <tbody>
          {visit.checklist.map((c) => {
            const r = rows[c.key] ?? EMPTY_ROW;
            const label = itemLabel(t, c.key);
            const bad = checked && r.result === "nonconform" && !r.observed.trim() && !r.note.trim();
            return (
              <tr key={c.key} className={r.result === "nonconform" ? "is-nonconform" : undefined}>
                <th scope="row">
                  {label}
                  {c.section === "site" && <span className="tag tag--sim">[SIM]</span>}
                </th>
                <td dir="auto">{declaredText(t, fmt, c.key, c.declared)}</td>
                <td>
                  <select
                    aria-label={t("prevention.resultFor", { item: label })}
                    value={r.result}
                    onChange={(e) => set(c.key, { result: e.target.value as InspectionResult })}
                  >
                    {INSPECTION_RESULTS.map((x) => (
                      <option key={x} value={x}>
                        {t(`prevention.result.${x}`)}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    aria-label={t("prevention.observedFor", { item: label })}
                    aria-invalid={bad}
                    value={r.observed}
                    maxLength={200}
                    onChange={(e) => set(c.key, { observed: e.target.value })}
                  />
                </td>
                <td>
                  <input
                    aria-label={t("prevention.noteFor", { item: label })}
                    aria-invalid={bad}
                    value={r.note}
                    maxLength={500}
                    onChange={(e) => set(c.key, { note: e.target.value })}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {checked && lacking.length > 0 && (
        <p className="field__error">{t("errors.finding_detail_required")}</p>
      )}
      {mutation.isError && <ErrorBox error={mutation.error} />}
      <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
        {mutation.isPending ? t("common.loading") : t("prevention.saveInspection")}
      </button>
    </form>
  );
}

interface Draft {
  text: string;
  due_on: string;
  item_key: string | null;
}

function DecisionForm({ visit, onDone }: { visit: StaffVisit; onDone: (v: StaffVisit) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const ids = useId();
  const today = isoDate(new Date());
  const latest = addMonths(today, RESERVATION_MAX_MONTHS);
  const report = visit.comparison;
  const [decision, setDecision] = useState<VisitDecision>(report?.suggested ?? "approved");
  const [validUntil, setValidUntil] = useState(addMonths(today, PREVENTION_DEFAULT_MONTHS));
  const [reason, setReason] = useState("");
  const [drafts, setDrafts] = useState<Draft[]>(() =>
    (report?.items ?? [])
      .filter((i) => i.result === "nonconform")
      .map((i) => ({
        text: [itemLabel(t, i.key), i.observed, i.note].filter(Boolean).join(" — "),
        due_on: addDays(today, 30),
        item_key: i.key,
      })),
  );
  const [checked, setChecked] = useState(false);
  const withReservations = decision === "approved_with_reservations";
  const badDraft = (d: Draft) => !d.text.trim() || !d.due_on || d.due_on <= today || d.due_on > latest;
  const problems = {
    reason: decision === "refused" && !reason.trim(),
    validUntil: decision !== "refused" && (!validUntil || validUntil <= today),
    reservations: withReservations && (drafts.length === 0 || drafts.some(badDraft)),
  };

  const mutation = useMutation({
    mutationFn: () =>
      api.decideVisit(visit.id, {
        decision,
        reason: reason.trim() || null,
        valid_until: decision === "refused" ? null : validUntil,
        reservations: withReservations
          ? drafts.map((d) => ({ text: d.text.trim(), due_on: d.due_on, item_key: d.item_key }))
          : [],
      }),
    onSuccess: onDone,
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setChecked(true);
    if (Object.values(problems).some(Boolean)) return;
    mutation.mutate();
  };
  const edit = (n: number, patch: Partial<Draft>) =>
    setDrafts((list) => list.map((d, i) => (i === n ? { ...d, ...patch } : d)));

  return (
    <form className="card visit-form" onSubmit={submit} noValidate aria-labelledby={`${ids}-t`}>
      <h2 id={`${ids}-t`}>{t("prevention.decisionTitle")}</h2>
      <fieldset className="visit-form__choices">
        <legend>{t("prevention.decisionLabel")}</legend>
        {VISIT_DECISIONS.map((d) => (
          <label key={d}>
            <input type="radio" name={`${ids}-d`} value={d} checked={decision === d} onChange={() => setDecision(d)} />{" "}
            {t(`prevention.decision.${d}`)}
          </label>
        ))}
      </fieldset>
      {decision !== "refused" && (
        <div className="field">
          <label htmlFor={`${ids}-vu`}>
            {t("prevention.validUntil")} <span className="tag tag--sim">[SIM]</span>
          </label>
          <input id={`${ids}-vu`} type="date" value={validUntil} min={addDays(today, 1)} onChange={(e) => setValidUntil(e.target.value)} />
          {checked && problems.validUntil && <p className="field__error">{t("errors.invalid_valid_until")}</p>}
        </div>
      )}
      <div className="field">
        <label htmlFor={`${ids}-r`}>{decision === "refused" ? t("prevention.reasonRequired") : t("prevention.reasonOptional")}</label>
        <textarea id={`${ids}-r`} rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
        {checked && problems.reason && <p className="field__error">{t("errors.reason_required")}</p>}
      </div>
      {withReservations && (
        <fieldset className="reservation-drafts">
          <legend>{t("prevention.reservationsTitle")}</legend>
          {drafts.map((d, n) => (
            <div key={n} className="reservation-draft">
              <div className="field field--grow">
                <label htmlFor={`${ids}-t${n}`}>{t("prevention.reservationText", { n: n + 1 })}</label>
                <input id={`${ids}-t${n}`} value={d.text} maxLength={500} aria-invalid={checked && !d.text.trim()} onChange={(e) => edit(n, { text: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor={`${ids}-d${n}`}>{t("prevention.reservationDue")}</label>
                <input
                  id={`${ids}-d${n}`}
                  type="date"
                  value={d.due_on}
                  min={addDays(today, 1)}
                  max={latest}
                  aria-invalid={checked && badDraft(d)}
                  onChange={(e) => edit(n, { due_on: e.target.value })}
                />
              </div>
              <button type="button" className="btn" onClick={() => setDrafts((list) => list.filter((_, i) => i !== n))}>
                {t("prevention.removeReservation")}
              </button>
            </div>
          ))}
          <button
            type="button"
            className="btn"
            onClick={() => setDrafts((list) => [...list, { text: "", due_on: addDays(today, 30), item_key: null }])}
          >
            {t("prevention.addReservation")}
          </button>
          {checked && problems.reservations && <p className="field__error">{t("prevention.reservationsInvalid")}</p>}
        </fieldset>
      )}
      {mutation.isError && <ErrorBox error={mutation.error} />}
      <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
        {mutation.isPending ? t("common.loading") : t("prevention.decide")}
      </button>
    </form>
  );
}

function CancelForm({ visit, onDone }: { visit: StaffVisit; onDone: (v: StaffVisit) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const [reason, setReason] = useState("");
  const [checked, setChecked] = useState(false);
  const mutation = useMutation({ mutationFn: () => api.cancelVisit(visit.id, reason.trim()), onSuccess: onDone });
  return (
    <form
      className="visit-form visit-form--inline"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        setChecked(true);
        if (reason.trim()) mutation.mutate();
      }}
    >
      <div className="field field--grow">
        <label htmlFor={id}>{t("prevention.cancelReason")}</label>
        <input id={id} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
        {checked && !reason.trim() && <p className="field__error">{t("errors.reason_required")}</p>}
      </div>
      <button type="submit" className="btn btn--danger" disabled={mutation.isPending}>
        {t("prevention.cancel")}
      </button>
      {mutation.isError && <ErrorBox error={mutation.error} />}
    </form>
  );
}

/** One visit: its stages for the auditor (schedule, inspect, decide), its report, certificate and reservations. */
export function VisitPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const qc = useQueryClient();
  const canAct = canReviewOrgs(user?.identity.roles ?? []);
  const [message, setMessage] = useState<string | null>(null);
  const key = ["prevention-visit", id];
  const query = useQuery({ queryKey: key, queryFn: ({ signal }) => api.preventionVisit(id, signal) });

  const done = (text: string) => (visit: StaffVisit) => {
    qc.setQueryData(key, visit);
    void qc.invalidateQueries({ queryKey: ["prevention-visits"] });
    void qc.invalidateQueries({ queryKey: ["org-visits", visit.org_id] });
    setMessage(text);
  };

  if (query.isPending) return <Loading />;
  if (query.isError)
    return (
      <div className="page">
        <Link to="/orgs/prevention">{t("prevention.back")}</Link>
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );
  const visit = query.data;
  const cert = visit.certificate;

  return (
    <article className="page detail" aria-labelledby="visit-title">
      <p>
        <Link to="/orgs/prevention">{t("prevention.back")}</Link>
      </p>
      <div className="page__head">
        <PageTitle icon="policy" tone="purple" id="visit-title">
          {t("prevention.visitTitle", { org: visit.org_name })}
        </PageTitle>
        <VisitStatusTag status={visit.status} />
        {visit.decision && <DecisionTag decision={visit.decision} />}
      </div>
      <div aria-live="polite" role="status">
        {message && <p className="alert alert--ok">{message}</p>}
      </div>
      {!canAct && OPEN.includes(visit.status) && <p className="alert alert--info">{t("prevention.readOnly")}</p>}

      <section className="card" aria-labelledby="visit-facts">
        <h2 id="visit-facts">{t("prevention.facts")}</h2>
        <dl className="fields">
          <dt>{t("orgs.counter.org")}</dt>
          <dd>
            <Link to={`/orgs/${encodeURIComponent(visit.org_id)}`} dir="auto">
              {visit.org_name}
            </Link>{" "}
            · {orgKindLabel(t, visit.org_kind)}
          </dd>
          <dt>{t("prevention.originLabel")}</dt>
          <dd>{t(`prevention.origin.${visit.origin}`)}</dd>
          {visit.request_note && (
            <>
              <dt>{t("prevention.requestNote")}</dt>
              <dd dir="auto">{visit.request_note}</dd>
            </>
          )}
          {visit.requested_by_name && (
            <>
              <dt>{t("prevention.requestedBy")}</dt>
              <dd>
                {visit.requested_by_name} · {visit.requested_at ? fmt.dateTime(visit.requested_at) : "—"}
              </dd>
            </>
          )}
          <dt>{t("prevention.scheduledOn")}</dt>
          <dd>{formatDay(fmt, visit.scheduled_on, "—")}</dd>
          <dt>{t("prevention.inspector")}</dt>
          <dd>
            {visit.inspector_name ?? "—"}
            {visit.inspector_on_phone && (
              <>
                {" "}
                <span className="tag tag--level-ok">{t("prevention.onPhone")}</span>
              </>
            )}
          </dd>
          <dt>{t("prevention.inspectedOn")}</dt>
          <dd>{formatDay(fmt, visit.inspected_on, "—")}</dd>
          {visit.attendees && (
            <>
              <dt>{t("prevention.attendees")}</dt>
              <dd dir="auto">{visit.attendees}</dd>
            </>
          )}
          {visit.cancel_reason && (
            <>
              <dt>{t("prevention.cancelReason")}</dt>
              <dd dir="auto">{visit.cancel_reason}</dd>
            </>
          )}
        </dl>
        {visit.has_report && (
          <DownloadButton label={t("prevention.report")} fetchLink={() => api.visitReport(visit.id)} />
        )}
        {canAct && (visit.status === "requested" || visit.status === "scheduled") && (
          <CancelForm visit={visit} onDone={done(t("prevention.cancelled"))} />
        )}
      </section>

      {canAct && (visit.status === "requested" || visit.status === "scheduled") && (
        <ScheduleForm visit={visit} onDone={done(t("prevention.scheduled"))} />
      )}

      {visit.comparison && (
        <section className="card" aria-labelledby="visit-compare">
          <h2 id="visit-compare">{t("prevention.comparisonTitle")}</h2>
          <ComparisonView report={visit.comparison} />
        </section>
      )}

      {((visit.photos?.length ?? 0) > 0 || visit.signatures) && (
        <section className="card" aria-labelledby="visit-field">
          <h2 id="visit-field">{t("prevention.fieldTitle")}</h2>
          <FieldEvidence photos={visit.photos ?? []} signatures={visit.signatures ?? null} />
        </section>
      )}

      {canAct && (visit.status === "scheduled" || visit.status === "inspected") && (
        <InspectionForm key={`${visit.id}-${visit.inspected_on ?? ""}`} visit={visit} onDone={done(t("prevention.inspected"))} />
      )}

      {canAct && visit.status === "inspected" && <DecisionForm visit={visit} onDone={done(t("prevention.decided"))} />}

      {visit.status === "decided" && (
        <section className="card" aria-labelledby="visit-decision">
          <h2 id="visit-decision">{t("prevention.decisionTitle")}</h2>
          <dl className="fields">
            <dt>{t("prevention.decisionLabel")}</dt>
            <dd>{visit.decision && <DecisionTag decision={visit.decision} />}</dd>
            {visit.decision_reason && (
              <>
                <dt>{t("prevention.reason")}</dt>
                <dd dir="auto">{visit.decision_reason}</dd>
              </>
            )}
            <dt>{t("prevention.decidedBy")}</dt>
            <dd>
              {visit.decided_by_name ?? "—"} · {visit.decided_at ? fmt.dateTime(visit.decided_at) : "—"}
            </dd>
            {cert && (
              <>
                <dt>{t("prevention.certificate")}</dt>
                <dd>
                  <span className="code" dir="ltr">
                    {cert.code}
                  </span>{" "}
                  <span className="tag tag--sim">[SIM]</span> · {t("orgs.detail.validUntilLabel")}{" "}
                  {formatDay(fmt, cert.valid_until, "—")}
                  {cert.superseded && <span className="tag"> {t("orgs.detail.superseded")}</span>}
                </dd>
              </>
            )}
          </dl>
          {cert && (
            <DownloadButton label={`${t("orgs.detail.pdf")} ${cert.code}`} fetchLink={() => api.certificatePdf(visit.org_id, cert.id)} />
          )}
          <h3>{t("prevention.reservationsTitle")}</h3>
          <ReservationList
            items={visit.reservations}
            canLift={canAct}
            onChanged={() => {
              void qc.invalidateQueries({ queryKey: key });
              setMessage(t("prevention.lifted"));
            }}
          />
        </section>
      )}
    </article>
  );
}
