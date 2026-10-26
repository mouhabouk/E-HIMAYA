import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { opsKeys } from "../lib/opsApi";
import {
  ACTIVE_ASSIGNMENT_STATUSES,
  ASSIGNMENT_TRANSITIONS,
  CASUALTY_KINDS,
  OUTCOMES,
  SKILLS,
  classificationsFor,
  type Assignment,
  type AssignmentStatus,
  type Callout,
  type CasualtyKind,
  type OpLevel,
  type Outcome,
  type Skill,
} from "../lib/opsTypes";
import { canCloseIncidents, canDispatch } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import type { IncidentDetail } from "../lib/types";
import { useDraft } from "../lib/drafts";
import { CrewLine, FieldSection, crewTimelineParts } from "./CrewBits";

/** A recommendation's "open assignment" (phase 7 §3): preselects a resource; the operator still submits. */
export interface AssignPreset {
  resourceId: string | null;
  order: string | null;
  nonce: number;
}

const SUMMARY_MIN = 10;
const SUMMARY_MAX = 5000;

function MutationError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  return (
    <p className="alert alert--error" role="alert">
      {t(errorMessageKey(error))}
    </p>
  );
}

export function LevelTag({ level }: { level: OpLevel }) {
  const { t } = useTranslation();
  return <span className={`level-tag level-tag--${level}`}>{t(`levels.name.${level}`)}</span>;
}

export function AssignmentStatusChip({ status }: { status: AssignmentStatus }) {
  const { t } = useTranslation();
  return <span className={`chip chip--assignment-${status}`}>{t(`ops.assignment.status.${status}`)}</span>;
}

/** Refetch the incident (and what derives from it) after an operations action. */
function useRefreshIncident(incidentId: string) {
  const qc = useQueryClient();
  return (updated?: IncidentDetail) => {
    if (updated) qc.setQueryData(queryKeys.incident(incidentId), updated);
    else void qc.invalidateQueries({ queryKey: queryKeys.incident(incidentId) });
    void qc.invalidateQueries({ queryKey: queryKeys.incidentsAll });
  };
}

// ---------------------------------------------------------------- incident card

function CardForm({ incident, canEdit }: { incident: IncidentDetail; canEdit: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const refresh = useRefreshIncident(incident.id);
  const ids = { title: useId(), cls: useId() };
  const [title, setTitle] = useState(incident.title ?? "");
  const [classification, setClassification] = useState(incident.classification ?? "");
  const [saved, setSaved] = useState(false);
  const mutation = useMutation({
    mutationFn: () =>
      api.updateIncidentCard(incident.id, { title: title.trim() || null, classification: classification || null }),
    onSuccess: (updated) => {
      refresh(updated);
      setSaved(true);
    },
  });
  const level = incident.op_level ?? "normal";

  if (!canEdit || incident.status !== "open") {
    return (
      <dl className="fields">
        <dt>{t("ops.card.title")}</dt>
        <dd dir="auto">{incident.title || t("common.notAvailable")}</dd>
        <dt>{t("ops.card.classification")}</dt>
        <dd>
          {incident.classification ? t(`ops.classification.${incident.classification}`) : t("common.notAvailable")}
        </dd>
        <dt>{t("ops.card.level")}</dt>
        <dd>
          <LevelTag level={level} />
        </dd>
      </dl>
    );
  }
  return (
    <form
      className="ops-form"
      onSubmit={(e) => {
        e.preventDefault();
        setSaved(false);
        mutation.mutate();
      }}
    >
      <p>
        {t("ops.card.level")}: <LevelTag level={level} />
      </p>
      <div className="field">
        <label htmlFor={ids.title}>{t("ops.card.title")}</label>
        <input
          id={ids.title}
          value={title}
          maxLength={150}
          dir="auto"
          onChange={(e) => {
            setTitle(e.target.value);
            setSaved(false);
          }}
        />
      </div>
      <div className="field">
        <label htmlFor={ids.cls}>{t("ops.card.classification")}</label>
        <select
          id={ids.cls}
          value={classification}
          onChange={(e) => {
            setClassification(e.target.value);
            setSaved(false);
          }}
        >
          <option value="">{t("ops.card.noClassification")}</option>
          {classificationsFor(incident.category).map((c) => (
            <option key={c} value={c}>
              {t(`ops.classification.${c}`)}
            </option>
          ))}
        </select>
      </div>
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {mutation.isPending ? t("ops.working") : t("ops.card.save")}
        </button>
      </div>
      <div role="status" aria-live="polite">
        {saved && <p className="alert alert--ok">{t("ops.card.saved")}</p>}
      </div>
      <MutationError error={mutation.error} />
    </form>
  );
}

// ---------------------------------------------------------------- assignments

function AssignmentRow({ assignment, canEdit }: { assignment: Assignment; canEdit: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const refresh = useRefreshIncident(assignment.incident_id);
  const qc = useQueryClient();
  const noteId = useId();
  const [note, setNote] = useState("");
  const mutation = useMutation({
    mutationFn: (status: AssignmentStatus) => api.updateAssignment(assignment.id, status, note),
    onSuccess: () => {
      setNote("");
      refresh();
      void qc.invalidateQueries({ queryKey: opsKeys.resourcesAll });
    },
  });
  const next = ASSIGNMENT_TRANSITIONS[assignment.status];
  const who =
    assignment.kind === "resource"
      ? `${assignment.resource?.label ?? ""} · ${assignment.resource ? t(`resources.kind.${assignment.resource.kind}`) : ""}`
      : (assignment.volunteer?.full_name ?? t("ops.volunteer"));
  const last =
    assignment.released_at ??
    assignment.cancelled_at ??
    assignment.on_scene_at ??
    assignment.en_route_at ??
    assignment.created_at;
  return (
    <tr>
      <td>
        <strong dir="auto">{who}</strong>
        <div className="cell-sub">
          {assignment.kind === "resource"
            ? assignment.resource?.unit_name
            : assignment.volunteer?.phone && <span dir="ltr">{assignment.volunteer.phone}</span>}
        </div>
        {assignment.crew && <CrewLine crew={assignment.crew} />}
      </td>
      <td>
        <AssignmentStatusChip status={assignment.status} />
        <div className="cell-sub">
          <time dateTime={last}>{fmt.time(last)}</time>
        </div>
      </td>
      <td dir="auto">{assignment.order ?? "—"}</td>
      <td>
        {canEdit && next.length > 0 ? (
          <div className="ops-row-actions">
            <label className="visually-hidden" htmlFor={noteId}>
              {t("ops.assignment.note")}
            </label>
            <input
              id={noteId}
              value={note}
              maxLength={500}
              placeholder={t("ops.assignment.note")}
              dir="auto"
              onChange={(e) => setNote(e.target.value)}
            />
            {next.map((s) => (
              <button
                key={s}
                type="button"
                className={`btn btn--small${s === "cancelled" ? "" : " btn--primary"}`}
                disabled={mutation.isPending}
                onClick={() => mutation.mutate(s)}
                aria-label={t("ops.assignment.moveLabel", { who, status: t(`ops.assignment.status.${s}`) })}
              >
                {t(`ops.assignment.action.${s}`)}
              </button>
            ))}
            <MutationError error={mutation.error} />
          </div>
        ) : (
          <span className="muted">—</span>
        )}
      </td>
    </tr>
  );
}

function AssignResourceForm({ incident, preset }: { incident: IncidentDetail; preset?: AssignPreset | null }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const refresh = useRefreshIncident(incident.id);
  const ids = { resource: useId(), order: useId() };
  // A preset (recommendation) re-mounts this form with its values (key = nonce, see AssignmentsSection).
  const [resourceId, setResourceId] = useState(preset?.resourceId ?? "");
  const [order, setOrder] = useState(preset?.order ?? "");
  const selectRef = useRef<HTMLSelectElement>(null);
  const hasPreset = Boolean(preset);
  useEffect(() => {
    if (!hasPreset) return;
    selectRef.current?.scrollIntoView({ block: "center" });
    selectRef.current?.focus();
  }, [hasPreset]);
  const available = useQuery({
    queryKey: opsKeys.resources({ status: "available" }),
    queryFn: ({ signal }) => api.resources({ status: "available" }, { limit: 200, signal }),
  });
  const mutation = useMutation({
    mutationFn: () => api.createAssignment(incident.id, resourceId, order),
    onSuccess: () => {
      setResourceId("");
      setOrder("");
      refresh();
      void qc.invalidateQueries({ queryKey: opsKeys.resourcesAll });
      void qc.invalidateQueries({ queryKey: opsKeys.resourceSummary });
    },
  });
  const items = available.data?.items ?? [];
  return (
    <form
      className="ops-form"
      aria-label={t("ops.assignment.formTitle")}
      onSubmit={(e) => {
        e.preventDefault();
        if (resourceId) mutation.mutate();
      }}
    >
      <h3>{t("ops.assignment.formTitle")}</h3>
      {available.isError && <MutationError error={available.error} />}
      <div className="field">
        <label htmlFor={ids.resource}>{t("ops.assignment.resource")}</label>
        <select ref={selectRef} id={ids.resource} value={resourceId} onChange={(e) => setResourceId(e.target.value)}>
          <option value="">
            {available.isPending
              ? t("common.loading")
              : items.length === 0
                ? t("ops.assignment.noResource")
                : t("ops.assignment.chooseResource")}
          </option>
          {items.map((r) => (
            <option key={r.id} value={r.id}>
              {`${r.label} · ${t(`resources.kind.${r.kind}`)} · ${r.unit_name}`}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={ids.order}>{t("ops.assignment.order")}</label>
        <textarea id={ids.order} value={order} maxLength={1000} rows={2} dir="auto" onChange={(e) => setOrder(e.target.value)} />
      </div>
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={!resourceId || mutation.isPending}>
          {mutation.isPending ? t("ops.working") : t("ops.assignment.submit")}
        </button>
      </div>
      <MutationError error={mutation.error} />
    </form>
  );
}

function AssignmentsSection({
  incident,
  canEdit,
  preset,
}: {
  incident: IncidentDetail;
  canEdit: boolean;
  preset?: AssignPreset | null;
}) {
  const { t } = useTranslation();
  const assignments = incident.assignments ?? [];
  const active = assignments.filter((a) => ACTIVE_ASSIGNMENT_STATUSES.includes(a.status));
  const past = assignments.filter((a) => !ACTIVE_ASSIGNMENT_STATUSES.includes(a.status));
  const table = (rows: Assignment[], caption: string) => (
    <div className="table-wrap">
      <table className="table">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">{t("ops.assignment.who")}</th>
            <th scope="col">{t("ops.assignment.statusCol")}</th>
            <th scope="col">{t("ops.assignment.order")}</th>
            <th scope="col">{t("ops.assignment.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => (
            <AssignmentRow key={a.id} assignment={a} canEdit={canEdit} />
          ))}
        </tbody>
      </table>
    </div>
  );
  return (
    <section className="card" aria-labelledby="sec-assignments">
      <h2 id="sec-assignments">
        {t("ops.assignment.title")} ({active.length})
      </h2>
      {active.length === 0 ? <p className="muted">{t("ops.assignment.none")}</p> : table(active, t("ops.assignment.active"))}
      {past.length > 0 && (
        <details>
          <summary>{t("ops.assignment.past", { count: past.length })}</summary>
          {table(past, t("ops.assignment.pastCaption"))}
        </details>
      )}
      {canEdit && incident.status === "open" && <AssignResourceForm key={preset?.nonce ?? 0} incident={incident} preset={preset} />}
    </section>
  );
}

// ---------------------------------------------------------------- call-outs

function CalloutCard({ callout, canEdit }: { callout: Callout; canEdit: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const refresh = useRefreshIncident(callout.incident_id);
  const cancel = useMutation({ mutationFn: () => api.cancelCallout(callout.id), onSuccess: () => refresh() });
  const arrived = useMutation({
    mutationFn: (volunteerId: string) => api.markArrived(callout.id, volunteerId),
    onSuccess: () => refresh(),
  });
  const open = callout.status === "open" || callout.status === "filled";
  return (
    <article className="callout" aria-label={t("ops.callout.label", { skill: t(`volunteers.skill.${callout.skill}`) })}>
      <header className="callout__head">
        <strong>{t(`volunteers.skill.${callout.skill}`)}</strong>
        <span className={`chip chip--callout-${callout.status}`}>{t(`ops.callout.status.${callout.status}`)}</span>
        <span>{t("ops.callout.accepted", { accepted: fmt.number(callout.accepted), requested: fmt.number(callout.requested) })}</span>
        <span className="muted">
          {t("ops.callout.radius", { km: fmt.number(callout.radius_km) })} ·{" "}
          <time dateTime={callout.created_at}>{fmt.dateTime(callout.created_at)}</time>
        </span>
      </header>
      {callout.message && <p dir="auto">{callout.message}</p>}
      <div className="table-wrap">
        <table className="table">
          <caption className="visually-hidden">{t("ops.callout.targets")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("ops.callout.volunteer")}</th>
              <th scope="col">{t("ops.callout.distance")}</th>
              <th scope="col">{t("ops.callout.answer")}</th>
              <th scope="col">{t("ops.callout.eta")}</th>
              <th scope="col">{t("ops.callout.position")}</th>
              {canEdit && <th scope="col">{t("ops.assignment.actions")}</th>}
            </tr>
          </thead>
          <tbody>
            {callout.targets.map((target) => (
              <tr key={target.volunteer_id}>
                <td>
                  <span dir="auto">{target.full_name ?? t("ops.volunteer")}</span>
                  {target.phone && (
                    <div className="cell-sub">
                      <a href={`tel:${target.phone}`} dir="ltr">
                        {target.phone}
                      </a>
                    </div>
                  )}
                </td>
                <td>{target.distance_m === null ? "—" : fmt.meters(target.distance_m)}</td>
                <td>
                  <span className={`chip chip--target-${target.status}`}>{t(`ops.callout.target.${target.status}`)}</span>
                </td>
                <td>
                  {target.eta_minutes === null ? "—" : t("ops.callout.minutes", { count: target.eta_minutes })}
                </td>
                <td>
                  {target.position ? (
                    <span className="code" dir="ltr">
                      {target.position.lat.toFixed(4)}, {target.position.lon.toFixed(4)} ·{" "}
                      <time dateTime={target.position.at}>{fmt.time(target.position.at)}</time>
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                {canEdit && (
                  <td>
                    {target.status === "accepted" && (
                      <button
                        type="button"
                        className="btn btn--small"
                        disabled={arrived.isPending}
                        onClick={() => arrived.mutate(target.volunteer_id)}
                        aria-label={t("ops.callout.markArrivedLabel", { name: target.full_name ?? "" })}
                      >
                        {t("ops.callout.markArrived")}
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {canEdit && open && (
        <div className="actions">
          <button type="button" className="btn" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
            {t("ops.callout.cancel")}
          </button>
        </div>
      )}
      <MutationError error={cancel.error ?? arrived.error} />
    </article>
  );
}

function CalloutForm({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const refresh = useRefreshIncident(incident.id);
  const ids = { skill: useId(), radius: useId(), requested: useId(), message: useId(), mode: useId() };
  const [skill, setSkill] = useState<Skill>("first_aid");
  const [radiusKm, setRadiusKm] = useState(30);
  const [requested, setRequested] = useState(2);
  const [message, setMessage, clearMessage] = useDraft(`incident:${incident.id}:callout`);
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set());
  const [sent, setSent] = useState(false);

  const suggestions = useQuery({
    queryKey: opsKeys.volunteerSuggestions(incident.id, skill, radiusKm),
    queryFn: ({ signal }) => api.volunteerSuggestions(incident.id, { skill, radiusKm, signal }),
    enabled: incident.centroid !== null,
  });
  const mutation = useMutation({
    mutationFn: () =>
      api.createCallout(incident.id, {
        skill,
        requested,
        radius_km: radiusKm,
        message: message.trim() || null,
        volunteer_ids: picked.size > 0 ? [...picked] : null,
      }),
    onSuccess: () => {
      setPicked(new Set());
      clearMessage();
      setSent(true);
      refresh();
    },
  });

  if (!incident.centroid) return <p className="muted">{t("errors.incident_without_location")}</p>;
  const toggle = (id: string) =>
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const list = suggestions.data ?? [];
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setSent(false);
    mutation.mutate();
  };
  return (
    <form className="ops-form" aria-label={t("ops.callout.formTitle")} onSubmit={submit}>
      <h3>{t("ops.callout.formTitle")}</h3>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={ids.skill}>{t("ops.callout.skill")}</label>
          <select
            id={ids.skill}
            value={skill}
            onChange={(e) => {
              setSkill(e.target.value as Skill);
              setPicked(new Set());
            }}
          >
            {SKILLS.map((s) => (
              <option key={s} value={s}>
                {t(`volunteers.skill.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field field--number">
          <label htmlFor={ids.radius}>{t("ops.callout.radiusKm")}</label>
          <input
            id={ids.radius}
            type="number"
            min={1}
            max={100}
            value={radiusKm}
            onChange={(e) => setRadiusKm(Math.min(100, Math.max(1, Number(e.target.value) || 1)))}
          />
        </div>
        <div className="field field--number">
          <label htmlFor={ids.requested}>{t("ops.callout.requested")}</label>
          <input
            id={ids.requested}
            type="number"
            min={1}
            max={50}
            value={requested}
            onChange={(e) => setRequested(Math.min(50, Math.max(1, Number(e.target.value) || 1)))}
          />
        </div>
      </div>
      <fieldset className="ops-suggestions">
        <legend>{t("ops.callout.suggestions")}</legend>
        <p className="muted">{t("ops.callout.pickHelp")}</p>
        {suggestions.isPending && <p className="muted">{t("common.loading")}</p>}
        {suggestions.isError && <MutationError error={suggestions.error} />}
        {suggestions.isSuccess && list.length === 0 && <p className="muted">{t("ops.callout.noSuggestion")}</p>}
        {list.length > 0 && (
          <ul className="checklist">
            {list.map((s) => (
              <li key={s.volunteer_id}>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={picked.has(s.volunteer_id)}
                    onChange={() => toggle(s.volunteer_id)}
                  />
                  <span dir="auto">{s.full_name ?? t("ops.volunteer")}</span>
                  <span className="muted"> · {fmt.meters(s.distance_m)}</span>
                  {s.busy && <span className="tag"> {t("ops.callout.busy")}</span>}
                </label>
              </li>
            ))}
          </ul>
        )}
      </fieldset>
      <div className="field">
        <label htmlFor={ids.message}>{t("ops.callout.message")}</label>
        <textarea
          id={ids.message}
          value={message}
          maxLength={300}
          rows={2}
          dir="auto"
          onChange={(e) => setMessage(e.target.value)}
        />
      </div>
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {mutation.isPending
            ? t("ops.working")
            : picked.size > 0
              ? t("ops.callout.submitPicked", { count: picked.size })
              : t("ops.callout.submitAuto")}
        </button>
      </div>
      <div role="status" aria-live="polite">
        {sent && <p className="alert alert--ok">{t("ops.callout.sent")}</p>}
      </div>
      <MutationError error={mutation.error} />
    </form>
  );
}

function CalloutsSection({ incident, canEdit }: { incident: IncidentDetail; canEdit: boolean }) {
  const { t } = useTranslation();
  const callouts = incident.callouts ?? [];
  return (
    <section className="card" aria-labelledby="sec-callouts">
      <h2 id="sec-callouts">{t("ops.callout.title")}</h2>
      {callouts.length === 0 && <p className="muted">{t("ops.callout.none")}</p>}
      {callouts.map((c) => (
        <CalloutCard key={c.id} callout={c} canEdit={canEdit} />
      ))}
      {canEdit && incident.status === "open" && <CalloutForm incident={incident} />}
    </section>
  );
}

// ---------------------------------------------------------------- notes, close and evaluation

function NoteForm({ incidentId }: { incidentId: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const refresh = useRefreshIncident(incidentId);
  const id = useId();
  const [text, setText, clearText] = useDraft(`incident:${incidentId}:note`);
  const mutation = useMutation({
    mutationFn: () => api.addIncidentNote(incidentId, text.trim()),
    onSuccess: () => {
      clearText();
      refresh();
    },
  });
  return (
    <form
      className="ops-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim()) mutation.mutate();
      }}
    >
      <div className="field">
        <label htmlFor={id}>{t("ops.note.label")}</label>
        <textarea id={id} value={text} maxLength={2000} rows={2} dir="auto" onChange={(e) => setText(e.target.value)} />
      </div>
      <div className="actions">
        <button type="submit" className="btn" disabled={!text.trim() || mutation.isPending}>
          {t("ops.note.submit")}
        </button>
      </div>
      <MutationError error={mutation.error} />
    </form>
  );
}

const ZERO: Record<CasualtyKind, number> = { rescued: 0, injured: 0, deceased: 0, evacuated: 0 };

function CloseForm({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const refresh = useRefreshIncident(incident.id);
  const qc = useQueryClient();
  const ids = { outcome: useId(), summary: useId(), lessons: useId(), base: useId() };
  const [outcome, setOutcome] = useState<Outcome>("resolved");
  // Backlog G4: a live update can hide this form (an assignment becomes active again); the texts come back with it.
  const [summary, setSummary, clearSummary] = useDraft(`incident:${incident.id}:close-summary`);
  const [lessons, setLessons, clearLessons] = useDraft(`incident:${incident.id}:close-lessons`);
  const [casualties, setCasualties] = useState(ZERO);
  const [confirming, setConfirming] = useState(false);
  const [summaryError, setSummaryError] = useState(false);
  const active = incident.assignments
    ? incident.assignments.filter((a) => ACTIVE_ASSIGNMENT_STATUSES.includes(a.status)).length
    : (incident.assignments_active ?? 0);
  const mutation = useMutation({
    mutationFn: () =>
      api.closeIncident(incident.id, { outcome, summary: summary.trim(), casualties, lessons: lessons.trim() || null }),
    onSuccess: (updated) => {
      clearSummary();
      clearLessons();
      refresh(updated);
      void qc.invalidateQueries({ queryKey: queryKeys.reportsAll });
    },
    onSettled: () => setConfirming(false),
  });

  if (active > 0) return <p className="alert alert--info">{t("ops.close.blocked", { count: active })}</p>;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const length = summary.trim().length;
    if (length < SUMMARY_MIN || length > SUMMARY_MAX) {
      setSummaryError(true);
      return;
    }
    setSummaryError(false);
    if (!confirming) {
      setConfirming(true);
      return;
    }
    mutation.mutate();
  };
  return (
    <form className="ops-form" onSubmit={submit} noValidate>
      <div className="field">
        <label htmlFor={ids.outcome}>{t("ops.close.outcome")}</label>
        <select id={ids.outcome} value={outcome} onChange={(e) => setOutcome(e.target.value as Outcome)}>
          {OUTCOMES.map((o) => (
            <option key={o} value={o}>
              {t(`ops.close.outcomes.${o}`)}
            </option>
          ))}
        </select>
      </div>
      <div className={`field${summaryError ? " field--invalid" : ""}`}>
        <label htmlFor={ids.summary}>{t("ops.close.summary")}</label>
        <textarea
          id={ids.summary}
          value={summary}
          rows={4}
          maxLength={SUMMARY_MAX}
          dir="auto"
          aria-invalid={summaryError || undefined}
          aria-describedby={summaryError ? `${ids.summary}-error` : undefined}
          onChange={(e) => setSummary(e.target.value)}
        />
        {summaryError && (
          <span id={`${ids.summary}-error`} className="field__error">
            {t("ops.close.summaryLength", { min: SUMMARY_MIN })}
          </span>
        )}
      </div>
      <fieldset>
        <legend>{t("ops.close.casualties")}</legend>
        <div className="filters__row">
          {CASUALTY_KINDS.map((k) => (
            <div key={k} className="field field--number">
              <label htmlFor={`${ids.base}-${k}`}>{t(`ops.close.casualty.${k}`)}</label>
              <input
                id={`${ids.base}-${k}`}
                type="number"
                min={0}
                value={casualties[k]}
                onChange={(e) => setCasualties((c) => ({ ...c, [k]: Math.max(0, Math.floor(Number(e.target.value) || 0)) }))}
              />
            </div>
          ))}
        </div>
      </fieldset>
      <div className="field">
        <label htmlFor={ids.lessons}>{t("ops.close.lessons")}</label>
        <textarea id={ids.lessons} value={lessons} rows={3} maxLength={5000} dir="auto" onChange={(e) => setLessons(e.target.value)} />
      </div>
      {confirming && (
        <p className="alert alert--warn" role="alert">
          {t("ops.close.confirmText")}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {mutation.isPending ? t("ops.working") : confirming ? t("ops.close.confirm") : t("ops.close.submit")}
        </button>
        {confirming && (
          <button type="button" className="btn" onClick={() => setConfirming(false)}>
            {t("common.cancel")}
          </button>
        )}
      </div>
      <MutationError error={mutation.error} />
    </form>
  );
}

function EvaluationView({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const e = incident.evaluation;
  if (!e) return null;
  return (
    <dl className="fields">
      <dt>{t("ops.close.outcome")}</dt>
      <dd>{t(`ops.close.outcomes.${e.outcome}`)}</dd>
      <dt>{t("ops.close.summary")}</dt>
      <dd dir="auto" className="report-text">
        {e.summary}
      </dd>
      {CASUALTY_KINDS.map((k) => (
        <div key={k} className="ops-dl-row">
          <dt>{t(`ops.close.casualty.${k}`)}</dt>
          <dd>{fmt.number(e.casualties[k])}</dd>
        </div>
      ))}
      {e.lessons && (
        <>
          <dt>{t("ops.close.lessons")}</dt>
          <dd dir="auto" className="report-text">
            {e.lessons}
          </dd>
        </>
      )}
      <dt>{t("ops.close.closedBy")}</dt>
      <dd>
        {e.closed_by ?? "—"} · <time dateTime={e.closed_at}>{fmt.dateTime(e.closed_at)}</time>
      </dd>
    </dl>
  );
}

/** Text of a phase 5 timeline entry's payload (resource, status, skill, ETA, outcome, note text). */
export function OpsTimelineDetails({ kind, payload }: { kind: string; payload: Record<string, unknown> }) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  const parts: string[] = [];
  const str = (k: string) => (typeof payload[k] === "string" ? payload[k] : null);
  const num = (k: string) => (typeof payload[k] === "number" ? payload[k] : null);
  const resource = str("resource");
  if (resource) parts.push(resource);
  const status = str("status");
  if (status && kind === "assignment_status") parts.push(t(`ops.assignment.status.${status}`));
  const skill = str("skill");
  if (skill) parts.push(t(`volunteers.skill.${skill}`));
  const requested = num("requested");
  const sent = num("sent");
  if (requested !== null) parts.push(t("ops.timeline.requested", { count: requested }));
  if (sent !== null) parts.push(t("ops.timeline.sent", { count: sent }));
  const eta = num("eta_minutes");
  if (eta !== null) parts.push(t("ops.callout.minutes", { count: eta }));
  const outcome = str("outcome");
  if (outcome) parts.push(t(`ops.close.outcomes.${outcome}`));
  const level = str("level");
  if (level && kind === "level_changed") parts.push(t(`levels.name.${level}`));
  // Phase 9 (§5.5): gouvernorat, command level and the reason of cross-gouvernorat steps.
  if (kind === "command_level_changed") parts.push(level ? t(`command.level.${level}`) : t("command.auto"));
  const code = num("gouvernorat_code");
  if (code !== null) parts.push(gouvernorats.nameOf(code) ?? String(code));
  const title = str("title");
  if (title && kind === "card_updated") parts.push(title);
  const classification = str("classification");
  if (classification) parts.push(t(`ops.classification.${classification}`));
  parts.push(...crewTimelineParts(kind, payload, t));
  const text = str("text") ?? str("reason");
  return (
    <>
      {parts.length > 0 && <span className="muted"> {parts.join(t("common.listSeparator"))}</span>}
      {text && (
        <span className="ops-note" dir="auto">
          {" "}
          {text}
        </span>
      )}
    </>
  );
}

/** FR-C-09: operations of an incident (card, assignments, volunteer call-outs, notes, close and evaluation). */
export function OperationsPanel({ incident, assignPreset }: { incident: IncidentDetail; assignPreset?: AssignPreset | null }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const roles = user?.identity.roles ?? [];
  const dispatch = canDispatch(roles);
  // Phase 9 §5.4: the central room cannot create assignments or call-outs (403 field_action_regional_only).
  const national = user?.identity.national ?? false;
  const fieldDispatch = dispatch && !national;
  const closer = canCloseIncidents(roles);
  const open = incident.status === "open";
  return (
    <div className="ops-panel">
      <section className="card" aria-labelledby="sec-card">
        <h2 id="sec-card">{t("ops.card.heading")}</h2>
        <CardForm incident={incident} canEdit={dispatch} />
      </section>
      {dispatch && national && open && <p className="alert alert--info">{t("resourceRequests.centralNotice")}</p>}
      <AssignmentsSection incident={incident} canEdit={fieldDispatch && open} preset={assignPreset} />
      <FieldSection incident={incident} />
      <CalloutsSection incident={incident} canEdit={fieldDispatch && open} />
      {dispatch && (
        <section className="card" aria-labelledby="sec-note">
          <h2 id="sec-note">{t("ops.note.title")}</h2>
          <NoteForm incidentId={incident.id} />
        </section>
      )}
      {incident.evaluation ? (
        <section className="card" aria-labelledby="sec-evaluation">
          <h2 id="sec-evaluation">{t("ops.close.evaluation")}</h2>
          <EvaluationView incident={incident} />
        </section>
      ) : (
        closer &&
        open && (
          <section className="card" aria-labelledby="sec-close">
            <h2 id="sec-close">{t("ops.close.title")}</h2>
            <CloseForm incident={incident} />
          </section>
        )
      )}
    </div>
  );
}
