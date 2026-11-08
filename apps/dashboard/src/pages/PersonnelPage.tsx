// covers: phase H1 (docs/phase-h/design-h.md): the personnel department keeps the staff, their administrative file
// (rank, appointment, transfer, sanction, reward) and their absences; the operations rooms read the staff with the
// kind of their absence and the general strength, and record nothing.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState, type ReactNode, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useDebounced, useFormat, useGouvernorats } from "../lib/hooks";
import {
  ABSENCE_KINDS,
  CATEGORIES,
  EVENT_KINDS,
  isoDay,
  monthRange,
  personnelKeys,
  type Absence,
  type AbsenceBrief,
  type AbsenceKind,
  type AgentFilters,
  type Category,
  type EventKind,
  type PersonnelAgent,
  type PersonnelEvent,
  type PersonnelUnit,
  type StrengthCount,
} from "../lib/personnelApi";
import { canManagePersonnel } from "../lib/roles";

export type PersonnelTab = "agents" | "absences" | "strength";
const TABS: readonly [PersonnelTab, string][] = [
  ["agents", "/personnel"],
  ["absences", "/personnel/absences"],
  ["strength", "/personnel/strength"],
];
const MIN_REASON = 5;

/** Colour family of an absence kind in the calendar and the tags (leave, sickness, duty away, other). */
export function absenceTone(kind: AbsenceKind): "leave" | "sick" | "duty" | "other" {
  if (kind === "sick") return "sick";
  if (kind === "mission" || kind === "training") return "duty";
  if (kind === "other") return "other";
  return "leave";
}

function useIdentity() {
  const { user } = useAuth();
  const roles = user?.identity.roles ?? [];
  return { officer: canManagePersonnel(roles), national: user?.identity.national ?? false };
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => void qc.invalidateQueries({ queryKey: personnelKeys.all });
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
    </div>
  );
}

function FormCard({
  title,
  error,
  problem,
  pending,
  onSubmit,
  onCancel,
  children,
}: {
  title: string;
  error: unknown;
  problem?: string | null;
  pending: boolean;
  onSubmit: () => void;
  onCancel: () => void;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const id = useId();
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    onSubmit();
  };
  return (
    <form noValidate className="card personnel-form" aria-labelledby={`${id}-title`} onSubmit={submit}>
      <h3 id={`${id}-title`}>{title}</h3>
      <div className="form-grid">{children}</div>
      {problem && (
        <p className="alert alert--error" role="alert">
          {problem}
        </p>
      )}
      {error !== null && error !== undefined && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(error))}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={pending}>
          {pending ? t("aiSettings.saving") : t("aiSettings.save")}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

function UnitSelect({
  id,
  units,
  value,
  onChange,
  any,
}: {
  id: string;
  units: PersonnelUnit[];
  value: string;
  onChange: (v: string) => void;
  any: string;
}) {
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{any}</option>
      {units.map((u) => (
        <option key={u.id} value={u.id}>
          {u.name}
        </option>
      ))}
    </select>
  );
}

/** "Present", or the kind of the absence with its end ("annual leave until 12/11"). */
export function StatusTag({ absence }: { absence: AbsenceBrief | null }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  if (!absence) return <span className="tag tag--ready">{t("personnel.present")}</span>;
  return (
    <span className={`tag absence-tag absence-tag--${absenceTone(absence.kind)}`}>
      {t(`personnel.absenceKind.${absence.kind}`)}
      <span className="cell-sub">{t("personnel.until", { date: fmt.date(absence.ends_on) })}</span>
    </span>
  );
}

/** A cancel button that asks for a reason in place. */
function CancelWithReason({ label, onConfirm, pending }: { label: string; onConfirm: (r: string) => void; pending: boolean }) {
  const { t } = useTranslation();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  if (!open)
    return (
      <button type="button" className="btn btn--small btn--ghost" onClick={() => setOpen(true)}>
        {label}
      </button>
    );
  return (
    <span className="inline-reason">
      <label htmlFor={id} className="visually-hidden">
        {t("personnel.reason")}
      </label>
      <input
        id={id}
        value={reason}
        maxLength={500}
        placeholder={t("personnel.reason")}
        onChange={(e) => setReason(e.target.value)}
      />
      <button
        type="button"
        className="btn btn--small"
        disabled={pending || reason.trim().length < MIN_REASON}
        onClick={() => onConfirm(reason)}
      >
        {t("personnel.confirm")}
      </button>
      <button type="button" className="btn btn--small btn--ghost" onClick={() => setOpen(false)}>
        {t("common.cancel")}
      </button>
    </span>
  );
}

// ---------------------------------------------------------------- the page

export function PersonnelPage({ tab }: { tab: PersonnelTab }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { officer, national } = useIdentity();
  const gouvernorats = useGouvernorats();
  const gouvId = useId();
  const [gouvernorat, setGouvernorat] = useState<number | null>(null);
  const units = useQuery({
    queryKey: personnelKeys.units(gouvernorat),
    queryFn: ({ signal }) => api.personnelUnits(gouvernorat, signal),
  });
  return (
    <div className="page personnel-page">
      <div className="page__head">
        <PageTitle icon="manageAccounts" tone="navy">
          {t("personnel.title")}
        </PageTitle>
      </div>
      <p className="muted">{t(officer ? "personnel.introOfficer" : "personnel.introRoom")}</p>
      <nav className="tabs" aria-label={t("personnel.tabs.label")}>
        {TABS.map(([key, to]) => (
          <NavLink
            key={key}
            to={to}
            end
            className={({ isActive }) => `tabs__tab${isActive ? " tabs__tab--active" : ""}`}
          >
            {t(`personnel.tabs.${key}`)}
          </NavLink>
        ))}
      </nav>
      {national && (
        <div className="filters__row">
          <div className="field">
            <label htmlFor={gouvId}>{t("filters.gouvernorat")}</label>
            <select
              id={gouvId}
              value={gouvernorat ?? ""}
              onChange={(e) => setGouvernorat(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">{t("filters.allGouvernorats")}</option>
              {gouvernorats.list.map((g) => (
                <option key={g.code} value={g.code}>
                  {gouvernorats.nameOf(g.code)}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
      {tab === "agents" && <AgentsTab gouvernorat={gouvernorat} units={units.data ?? []} officer={officer} />}
      {tab === "absences" && <AbsencesTab gouvernorat={gouvernorat} units={units.data ?? []} officer={officer} />}
      {tab === "strength" && <StrengthTab gouvernorat={gouvernorat} />}
    </div>
  );
}

// ---------------------------------------------------------------- staff

function AgentsTab({ gouvernorat, units, officer }: { gouvernorat: number | null; units: PersonnelUnit[]; officer: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const ids = { unit: useId(), category: useId(), q: useId() };
  const [unit, setUnit] = useState("");
  const [category, setCategory] = useState<Category | "">("");
  const [text, setText] = useState("");
  const [adding, setAdding] = useState(false);
  const q = useDebounced(text, 350);
  const filters: AgentFilters = useMemo(
    () => ({ gouvernorat, unit_id: unit || null, category, q }),
    [gouvernorat, unit, category, q],
  );
  const agents = useQuery({
    queryKey: personnelKeys.agents(filters),
    queryFn: ({ signal }) => api.personnelAgents(filters, signal),
  });
  const items = agents.data?.items ?? [];
  return (
    <>
      <section className="filters card" aria-label={t("personnel.filters")}>
        <div className="filters__row">
          <Field id={ids.q} label={t("personnel.search")}>
            <input id={ids.q} type="search" value={text} maxLength={60} onChange={(e) => setText(e.target.value)} />
          </Field>
          <Field id={ids.unit} label={t("personnel.columns.unit")}>
            <UnitSelect id={ids.unit} units={units} value={unit} onChange={setUnit} any={t("personnel.allUnits")} />
          </Field>
          <Field id={ids.category} label={t("personnel.columns.category")}>
            <select id={ids.category} value={category} onChange={(e) => setCategory(e.target.value as Category | "")}>
              <option value="">{t("personnel.anyCategory")}</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {t(`personnel.category.${c}`)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {officer && !adding && (
          <div className="actions">
            <button type="button" className="btn btn--primary" onClick={() => setAdding(true)}>
              {t("personnel.addAgent")}
            </button>
          </div>
        )}
      </section>
      {adding && <AgentForm units={units} onDone={() => setAdding(false)} />}
      {agents.isPending && <Loading />}
      {agents.isError && <ErrorBox error={agents.error} onRetry={() => void agents.refetch()} />}
      {agents.isSuccess && items.length === 0 && <p className="card empty">{t("personnel.noAgents")}</p>}
      {items.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <caption className="visually-hidden">{t("personnel.tabs.agents")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("personnel.columns.name")}</th>
                <th scope="col">{t("personnel.columns.matricule")}</th>
                <th scope="col">{t("personnel.columns.rank")}</th>
                <th scope="col">{t("personnel.columns.post")}</th>
                <th scope="col">{t("personnel.columns.category")}</th>
                <th scope="col">{t("personnel.columns.unit")}</th>
                <th scope="col">{t("personnel.columns.status")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id}>
                  <td dir="auto">
                    {officer ? <Link to={`/personnel/agents/${encodeURIComponent(a.id)}`}>{a.full_name}</Link> : a.full_name}
                  </td>
                  <td dir="ltr">{a.matricule}</td>
                  <td>{a.rank ?? "—"}</td>
                  <td>{a.post ?? "—"}</td>
                  <td>{t(`personnel.category.${a.category}`)}</td>
                  <td>{a.unit_name}</td>
                  <td>
                    <StatusTag absence={a.absence} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function AgentForm({ units, onDone }: { units: PersonnelUnit[]; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const ids = { unit: useId(), matricule: useId(), name: useId(), rank: useId(), post: useId(), category: useId(), phone: useId() };
  const [v, setV] = useState({ unit_id: "", matricule: "", full_name: "", rank: "", post: "", category: "intervention" as Category, phone: "" });
  const [problem, setProblem] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api.createPersonnelAgent(v),
    onSuccess: () => {
      done();
      onDone();
    },
  });
  const submit = () => {
    if (!v.unit_id || v.matricule.trim().length < 2 || v.full_name.trim().length < 2) {
      setProblem(t("personnel.form.required"));
      return;
    }
    setProblem(null);
    save.mutate();
  };
  const set = (p: Partial<typeof v>) => setV((x) => ({ ...x, ...p }));
  return (
    <FormCard title={t("personnel.addAgent")} error={save.error} problem={problem} pending={save.isPending} onSubmit={submit} onCancel={onDone}>
      <Field id={ids.unit} label={t("personnel.columns.unit")}>
        <UnitSelect id={ids.unit} units={units} value={v.unit_id} onChange={(unit_id) => set({ unit_id })} any={t("personnel.form.pickUnit")} />
      </Field>
      <Field id={ids.matricule} label={t("personnel.columns.matricule")}>
        <input id={ids.matricule} dir="ltr" maxLength={30} value={v.matricule} onChange={(e) => set({ matricule: e.target.value })} />
      </Field>
      <Field id={ids.name} label={t("personnel.columns.name")}>
        <input id={ids.name} dir="auto" maxLength={120} value={v.full_name} onChange={(e) => set({ full_name: e.target.value })} />
      </Field>
      <Field id={ids.rank} label={t("personnel.columns.rank")}>
        <input id={ids.rank} maxLength={60} value={v.rank} onChange={(e) => set({ rank: e.target.value })} />
      </Field>
      <Field id={ids.post} label={t("personnel.columns.post")}>
        <input id={ids.post} maxLength={80} value={v.post} onChange={(e) => set({ post: e.target.value })} />
      </Field>
      <Field id={ids.category} label={t("personnel.columns.category")}>
        <select id={ids.category} value={v.category} onChange={(e) => set({ category: e.target.value as Category })}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {t(`personnel.category.${c}`)}
            </option>
          ))}
        </select>
      </Field>
      <Field id={ids.phone} label={t("personnel.columns.phone")}>
        <input id={ids.phone} dir="ltr" type="tel" maxLength={30} value={v.phone} onChange={(e) => set({ phone: e.target.value })} />
      </Field>
    </FormCard>
  );
}

// ---------------------------------------------------------------- absences

function daysOf(start: string, end: string): string[] {
  const out: string[] = [];
  const [y = 1970, m = 1, d = 1] = start.split("-").map(Number);
  for (let day = new Date(y, m - 1, d); isoDay(day) <= end; day.setDate(day.getDate() + 1)) out.push(isoDay(day));
  return out;
}

function AbsencesTab({ gouvernorat, units, officer }: { gouvernorat: number | null; units: PersonnelUnit[]; officer: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const done = useInvalidate();
  const ids = { month: useId(), unit: useId(), kind: useId() };
  const [month, setMonth] = useState(isoDay(new Date()).slice(0, 7));
  const [unit, setUnit] = useState("");
  const [kind, setKind] = useState<AbsenceKind | "">("");
  const [editing, setEditing] = useState<Absence | "new" | null>(null);
  const range = monthRange(`${month}-01`);
  const filters = { ...range, gouvernorat, unit_id: unit || null, kind };
  const absences = useQuery({
    queryKey: personnelKeys.absences(filters),
    queryFn: ({ signal }) => api.absences(filters, signal),
  });
  const cancel = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => api.cancelAbsence(id, reason),
    onSuccess: done,
  });
  const items = absences.data?.items ?? [];
  const days = daysOf(range.start, range.end);
  const byAgent = new Map<string, Absence[]>();
  for (const a of items) byAgent.set(a.agent_id, [...(byAgent.get(a.agent_id) ?? []), a]);
  return (
    <>
      <section className="filters card" aria-label={t("personnel.filters")}>
        <div className="filters__row">
          <Field id={ids.month} label={t("personnel.month")}>
            <input id={ids.month} type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} />
          </Field>
          <Field id={ids.unit} label={t("personnel.columns.unit")}>
            <UnitSelect id={ids.unit} units={units} value={unit} onChange={setUnit} any={t("personnel.allUnits")} />
          </Field>
          <Field id={ids.kind} label={t("personnel.columns.kind")}>
            <select id={ids.kind} value={kind} onChange={(e) => setKind(e.target.value as AbsenceKind | "")}>
              <option value="">{t("personnel.anyKind")}</option>
              {ABSENCE_KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`personnel.absenceKind.${k}`)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {officer && editing === null && (
          <div className="actions">
            <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
              {t("personnel.addAbsence")}
            </button>
          </div>
        )}
      </section>
      {editing !== null && (
        <AbsenceForm absence={editing === "new" ? null : editing} gouvernorat={gouvernorat} onDone={() => setEditing(null)} />
      )}
      {absences.isPending && <Loading />}
      {absences.isError && <ErrorBox error={absences.error} onRetry={() => void absences.refetch()} />}
      {absences.isSuccess && items.length === 0 && <p className="card empty">{t("personnel.noAbsences")}</p>}
      {items.length > 0 && (
        <>
          <div className="table-wrap card personnel-calendar">
            <table className="table">
              <caption>{t("personnel.calendar")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("personnel.columns.name")}</th>
                  {days.map((d) => (
                    <th key={d} scope="col" className="personnel-calendar__day">
                      {Number(d.slice(8))}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...byAgent.entries()].map(([agentId, list]) => (
                  <tr key={agentId}>
                    <th scope="row" dir="auto">
                      {list[0]?.full_name}
                    </th>
                    {days.map((d) => {
                      const hit = list.find((a) => a.starts_on <= d && d <= a.ends_on);
                      return (
                        <td
                          key={d}
                          className={hit ? `personnel-calendar__cell absence-tag--${absenceTone(hit.kind)}` : "personnel-calendar__cell"}
                          title={hit ? t(`personnel.absenceKind.${hit.kind}`) : undefined}
                        >
                          {hit ? <span className="visually-hidden">{t(`personnel.absenceKind.${hit.kind}`)}</span> : null}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <ul className="personnel-legend">
              {(["leave", "sick", "duty", "other"] as const).map((tone) => (
                <li key={tone}>
                  <span className={`personnel-legend__swatch absence-tag--${tone}`} aria-hidden="true" />
                  {t(`personnel.tone.${tone}`)}
                </li>
              ))}
            </ul>
          </div>
          <div className="table-wrap card">
            <table className="table">
              <caption className="visually-hidden">{t("personnel.tabs.absences")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("personnel.columns.name")}</th>
                  <th scope="col">{t("personnel.columns.unit")}</th>
                  <th scope="col">{t("personnel.columns.kind")}</th>
                  <th scope="col">{t("personnel.columns.from")}</th>
                  <th scope="col">{t("personnel.columns.to")}</th>
                  <th scope="col">{t("personnel.columns.days")}</th>
                  {officer && <th scope="col">{t("personnel.columns.reference")}</th>}
                  {officer && <th scope="col">{t("personnel.columns.actions")}</th>}
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id}>
                    <td dir="auto">{a.full_name}</td>
                    <td>{a.unit_name}</td>
                    <td>
                      <span className={`tag absence-tag absence-tag--${absenceTone(a.kind)}`}>{t(`personnel.absenceKind.${a.kind}`)}</span>
                    </td>
                    <td>{fmt.date(a.starts_on)}</td>
                    <td>{fmt.date(a.ends_on)}</td>
                    <td>{fmt.number(a.days)}</td>
                    {officer && <td dir="auto">{a.reference ?? "—"}</td>}
                    {officer && (
                      <td className="actions">
                        <button type="button" className="btn btn--small" onClick={() => setEditing(a)}>
                          {t("personnel.edit")}
                        </button>
                        <CancelWithReason
                          label={t("personnel.cancelAbsence")}
                          pending={cancel.isPending}
                          onConfirm={(reason) => cancel.mutate({ id: a.id, reason })}
                        />
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}

function AbsenceForm({
  absence,
  gouvernorat,
  agentId,
  onDone,
}: {
  absence: Absence | null;
  gouvernorat: number | null;
  agentId?: string;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const ids = { agent: useId(), kind: useId(), from: useId(), to: useId(), ref: useId(), note: useId() };
  const today = isoDay(new Date());
  const [v, setV] = useState({
    agent_id: absence?.agent_id ?? agentId ?? "",
    kind: absence?.kind ?? ("annual"),
    starts_on: absence?.starts_on ?? today,
    ends_on: absence?.ends_on ?? today,
    reference: absence?.reference ?? "",
    note: absence?.note ?? "",
  });
  const [problem, setProblem] = useState<string | null>(null);
  const agents = useQuery({
    queryKey: personnelKeys.agents({ gouvernorat }),
    queryFn: ({ signal }) => api.personnelAgents({ gouvernorat }, signal),
    enabled: !absence && !agentId,
  });
  const save = useMutation({
    mutationFn: () => (absence ? api.updateAbsence(absence.id, { ...v, version: absence.version }) : api.createAbsence(v)),
    onSuccess: () => {
      done();
      onDone();
    },
  });
  const submit = () => {
    if (!v.agent_id) return setProblem(t("personnel.form.pickAgent"));
    if (v.ends_on < v.starts_on) return setProblem(t("errors.range_invalid"));
    setProblem(null);
    save.mutate();
  };
  const set = (p: Partial<typeof v>) => setV((x) => ({ ...x, ...p }));
  return (
    <FormCard
      title={t(absence ? "personnel.editAbsence" : "personnel.addAbsence")}
      error={save.error}
      problem={problem}
      pending={save.isPending}
      onSubmit={submit}
      onCancel={onDone}
    >
      {absence || agentId ? null : (
        <Field id={ids.agent} label={t("personnel.columns.name")}>
          <select id={ids.agent} value={v.agent_id} onChange={(e) => set({ agent_id: e.target.value })}>
            <option value="">{t("personnel.form.pickAgent")}</option>
            {(agents.data?.items ?? []).map((a: PersonnelAgent) => (
              <option key={a.id} value={a.id}>
                {a.full_name} · {a.matricule}
              </option>
            ))}
          </select>
        </Field>
      )}
      <Field id={ids.kind} label={t("personnel.columns.kind")}>
        <select id={ids.kind} value={v.kind} onChange={(e) => set({ kind: e.target.value as AbsenceKind })}>
          {ABSENCE_KINDS.map((k) => (
            <option key={k} value={k}>
              {t(`personnel.absenceKind.${k}`)}
            </option>
          ))}
        </select>
      </Field>
      <Field id={ids.from} label={t("personnel.columns.from")}>
        <input id={ids.from} type="date" value={v.starts_on} onChange={(e) => set({ starts_on: e.target.value })} />
      </Field>
      <Field id={ids.to} label={t("personnel.columns.to")}>
        <input id={ids.to} type="date" value={v.ends_on} onChange={(e) => set({ ends_on: e.target.value })} />
      </Field>
      <Field id={ids.ref} label={t("personnel.columns.reference")}>
        <input id={ids.ref} dir="auto" maxLength={120} value={v.reference} onChange={(e) => set({ reference: e.target.value })} />
      </Field>
      <Field id={ids.note} label={t("personnel.columns.note")}>
        <textarea id={ids.note} dir="auto" maxLength={1000} rows={2} value={v.note} onChange={(e) => set({ note: e.target.value })} />
      </Field>
      {v.kind === "sick" && <p className="muted personnel-form__hint">{t("personnel.form.noDiagnosis")}</p>}
    </FormCard>
  );
}

// ---------------------------------------------------------------- general strength

function CountCell({ c }: { c: StrengthCount }) {
  const fmt = useFormat();
  return (
    <>
      <td>{fmt.number(c.total)}</td>
      <td>{fmt.number(c.absent)}</td>
      <td className="personnel-strength__present">{fmt.number(c.present)}</td>
    </>
  );
}

function StrengthTab({ gouvernorat }: { gouvernorat: number | null }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const id = useId();
  const [on, setOn] = useState(isoDay(new Date()));
  const strength = useQuery({
    queryKey: personnelKeys.strength(on, gouvernorat),
    queryFn: ({ signal }) => api.strength(on, gouvernorat, signal),
  });
  const total = strength.data?.total;
  return (
    <>
      <section className="filters card" aria-label={t("personnel.filters")}>
        <div className="filters__row">
          <Field id={id} label={t("personnel.day")}>
            <input id={id} type="date" value={on} onChange={(e) => e.target.value && setOn(e.target.value)} />
          </Field>
        </div>
        <p className="muted">{t("personnel.strengthIntro")}</p>
      </section>
      {strength.isPending && <Loading />}
      {strength.isError && <ErrorBox error={strength.error} onRetry={() => void strength.refetch()} />}
      {total && (
        <div className="kpi-row personnel-kpis">
          <div className="card kpi">
            <span className="kpi__label">{t("personnel.readyToIntervene")}</span>
            <strong className="kpi__value">{fmt.number(total.intervention.present)}</strong>
            <span className="muted">{t("personnel.ofTotal", { total: fmt.number(total.intervention.total) })}</span>
          </div>
          <div className="card kpi">
            <span className="kpi__label">{t("personnel.logistics")}</span>
            <strong className="kpi__value">{fmt.number(total.room.present)}</strong>
            <span className="muted">{t("personnel.ofTotal", { total: fmt.number(total.room.total) })}</span>
          </div>
          <div className="card kpi">
            <span className="kpi__label">{t("personnel.category.admin")}</span>
            <strong className="kpi__value">{fmt.number(total.admin.present)}</strong>
            <span className="muted">{t("personnel.ofTotal", { total: fmt.number(total.admin.total) })}</span>
          </div>
        </div>
      )}
      {total && Object.keys(total.intervention.by_kind).length > 0 && (
        <ul className="tags personnel-absent-kinds" aria-label={t("personnel.absentByKind")}>
          {(Object.entries(total.intervention.by_kind) as [AbsenceKind, number][]).map(([k, n]) => (
            <li key={k} className={`tag absence-tag absence-tag--${absenceTone(k)}`}>
              {t(`personnel.absenceKind.${k}`)}: {fmt.number(n)}
            </li>
          ))}
        </ul>
      )}
      {strength.data && strength.data.units.length === 0 && <p className="card empty">{t("personnel.noAgents")}</p>}
      {strength.data && strength.data.units.length > 0 && (
        <div className="table-wrap card">
          <table className="table personnel-strength">
            <caption className="visually-hidden">{t("personnel.tabs.strength")}</caption>
            <thead>
              <tr>
                <th scope="col" rowSpan={2}>
                  {t("personnel.columns.unit")}
                </th>
                <th scope="colgroup" colSpan={3}>
                  {t("personnel.category.intervention")}
                </th>
                <th scope="colgroup" colSpan={3}>
                  {t("personnel.logistics")}
                </th>
                <th scope="colgroup" colSpan={3}>
                  {t("personnel.category.admin")}
                </th>
              </tr>
              <tr>
                {[0, 1, 2].flatMap((i) => [
                  <th key={`t${i}`} scope="col">
                    {t("personnel.total")}
                  </th>,
                  <th key={`a${i}`} scope="col">
                    {t("personnel.absent")}
                  </th>,
                  <th key={`p${i}`} scope="col">
                    {t("personnel.presentCount")}
                  </th>,
                ])}
              </tr>
            </thead>
            <tbody>
              {strength.data.units.map((u) => (
                <tr key={u.unit_id ?? "total"}>
                  <th scope="row">{u.unit_name}</th>
                  <CountCell c={u.intervention} />
                  <CountCell c={u.room} />
                  <CountCell c={u.admin} />
                </tr>
              ))}
            </tbody>
            {total && (
              <tfoot>
                <tr>
                  <th scope="row">{t("personnel.total")}</th>
                  <CountCell c={total.intervention} />
                  <CountCell c={total.room} />
                  <CountCell c={total.admin} />
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------- the administrative file

export function PersonnelFilePage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const done = useInvalidate();
  const { officer } = useIdentity();
  const { id = "" } = useParams();
  const [adding, setAdding] = useState<"event" | "absence" | "identity" | null>(null);
  const file = useQuery({
    queryKey: personnelKeys.file(id),
    queryFn: ({ signal }) => api.agentFile(id, signal),
    enabled: officer && Boolean(id),
  });
  const cancelEvent = useMutation({
    mutationFn: ({ eventId, reason }: { eventId: string; reason: string }) => api.cancelPersonnelEvent(eventId, reason),
    onSuccess: done,
  });
  if (!officer) return <p className="card empty">{t("personnel.officerOnly")}</p>;
  const agent = file.data?.agent;
  return (
    <div className="page personnel-page">
      <p>
        <Link to="/personnel">{t("personnel.back")}</Link>
      </p>
      {file.isPending && <Loading />}
      {file.isError && <ErrorBox error={file.error} onRetry={() => void file.refetch()} />}
      {agent && file.data && (
        <>
          <div className="page__head">
            <PageTitle icon="manageAccounts" tone="navy">
              {agent.full_name}
            </PageTitle>
          </div>
          <section className="card personnel-identity" aria-label={t("personnel.identity")}>
            <dl className="facts">
              <dt>{t("personnel.columns.matricule")}</dt>
              <dd dir="ltr">{agent.matricule}</dd>
              <dt>{t("personnel.columns.rank")}</dt>
              <dd>{agent.rank ?? "—"}</dd>
              <dt>{t("personnel.columns.post")}</dt>
              <dd>{agent.post ?? "—"}</dd>
              <dt>{t("personnel.columns.category")}</dt>
              <dd>{t(`personnel.category.${agent.category}`)}</dd>
              <dt>{t("personnel.columns.unit")}</dt>
              <dd>{agent.unit_name}</dd>
              <dt>{t("personnel.columns.phone")}</dt>
              <dd dir="ltr">{agent.phone ?? "—"}</dd>
              <dt>{t("personnel.columns.status")}</dt>
              <dd>
                <StatusTag absence={agent.absence} />
              </dd>
            </dl>
            {adding === null && (
              <div className="actions">
                <button type="button" className="btn btn--primary" onClick={() => setAdding("event")}>
                  {t("personnel.addEvent")}
                </button>
                <button type="button" className="btn" onClick={() => setAdding("absence")}>
                  {t("personnel.addAbsence")}
                </button>
                <button type="button" className="btn btn--ghost" onClick={() => setAdding("identity")}>
                  {t("personnel.editIdentity")}
                </button>
              </div>
            )}
          </section>
          {adding === "event" && <EventForm agent={agent} onDone={() => setAdding(null)} />}
          {adding === "absence" && <AbsenceForm absence={null} gouvernorat={null} agentId={agent.id} onDone={() => setAdding(null)} />}
          {adding === "identity" && <IdentityForm agent={agent} onDone={() => setAdding(null)} />}

          <h2>{t("personnel.file")}</h2>
          {file.data.events.length === 0 ? (
            <p className="card empty">{t("personnel.noEvents")}</p>
          ) : (
            <ol className="card personnel-timeline">
              {file.data.events.map((e: PersonnelEvent) => (
                <li key={e.id} className={e.cancelled_at ? "personnel-timeline__item--cancelled" : undefined}>
                  <time dateTime={e.effective_on}>{fmt.date(e.effective_on)}</time>
                  <span className={`tag personnel-event personnel-event--${e.kind}`}>{t(`personnel.eventKind.${e.kind}`)}</span>
                  <span dir="auto">
                    {e.kind === "transfer"
                      ? t("personnel.transferLine", { from: e.from_unit_name ?? "—", to: e.unit_name ?? "—" })
                      : e.title}
                    {e.kind === "appointment" && e.unit_name ? ` · ${e.unit_name}` : null}
                  </span>
                  {e.reference && <span className="cell-sub">{t("personnel.referenceLine", { ref: e.reference })}</span>}
                  {e.note && (
                    <span className="cell-sub" dir="auto">
                      {e.note}
                    </span>
                  )}
                  {e.cancelled_at ? (
                    <span className="tag tag--level-bad">
                      {t("personnel.cancelled")}: {e.cancel_reason}
                    </span>
                  ) : (
                    <CancelWithReason
                      label={t("personnel.cancelEvent")}
                      pending={cancelEvent.isPending}
                      onConfirm={(reason) => cancelEvent.mutate({ eventId: e.id, reason })}
                    />
                  )}
                </li>
              ))}
            </ol>
          )}
          {cancelEvent.isError && (
            <p className="alert alert--error" role="alert">
              {t(errorMessageKey(cancelEvent.error))}
            </p>
          )}

          <h2>{t("personnel.tabs.absences")}</h2>
          {file.data.absences.length === 0 ? (
            <p className="card empty">{t("personnel.noAbsences")}</p>
          ) : (
            <div className="table-wrap card">
              <table className="table">
                <caption className="visually-hidden">{t("personnel.tabs.absences")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("personnel.columns.kind")}</th>
                    <th scope="col">{t("personnel.columns.from")}</th>
                    <th scope="col">{t("personnel.columns.to")}</th>
                    <th scope="col">{t("personnel.columns.days")}</th>
                    <th scope="col">{t("personnel.columns.reference")}</th>
                  </tr>
                </thead>
                <tbody>
                  {file.data.absences.map((a) => (
                    <tr key={a.id} className={a.cancelled_at ? "row--muted" : undefined}>
                      <td>
                        <span className={`tag absence-tag absence-tag--${absenceTone(a.kind)}`}>{t(`personnel.absenceKind.${a.kind}`)}</span>
                        {a.cancelled_at && <span className="tag tag--level-bad">{t("personnel.cancelled")}</span>}
                      </td>
                      <td>{fmt.date(a.starts_on)}</td>
                      <td>{fmt.date(a.ends_on)}</td>
                      <td>{fmt.number(a.days)}</td>
                      <td dir="auto">{a.reference ?? "—"}</td>
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

function EventForm({ agent, onDone }: { agent: PersonnelAgent; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { national } = useIdentity();
  const done = useInvalidate();
  const ids = { kind: useId(), on: useId(), title: useId(), unit: useId(), ref: useId(), note: useId() };
  const [v, setV] = useState({
    kind: "rank" as EventKind,
    effective_on: isoDay(new Date()),
    title: "",
    unit_id: "",
    reference: "",
    note: "",
  });
  const [problem, setProblem] = useState<string | null>(null);
  // A transfer to another gouvernorat is the central department's: it chooses among every unit.
  const units = useQuery({
    queryKey: personnelKeys.units(national ? null : agent.gouvernorat_code),
    queryFn: ({ signal }) => api.personnelUnits(national ? null : agent.gouvernorat_code, signal),
    enabled: v.kind === "transfer" || v.kind === "appointment",
  });
  const save = useMutation({
    mutationFn: () =>
      api.addPersonnelEvent(agent.id, {
        kind: v.kind,
        effective_on: v.effective_on,
        title: v.kind === "transfer" ? null : v.title,
        unit_id: v.unit_id || null,
        reference: v.reference,
        note: v.note,
      }),
    onSuccess: () => {
      done();
      onDone();
    },
  });
  const submit = () => {
    if (v.kind === "transfer" && !v.unit_id) return setProblem(t("personnel.form.pickUnit"));
    if (v.kind !== "transfer" && !v.title.trim()) return setProblem(t("personnel.form.titleRequired"));
    setProblem(null);
    save.mutate();
  };
  const set = (p: Partial<typeof v>) => setV((x) => ({ ...x, ...p }));
  const unitChoices = (units.data ?? []).filter((u) => u.id !== agent.unit_id && (v.kind === "transfer" || u.gouvernorat_code === agent.gouvernorat_code));
  return (
    <FormCard title={t("personnel.addEvent")} error={save.error} problem={problem} pending={save.isPending} onSubmit={submit} onCancel={onDone}>
      <Field id={ids.kind} label={t("personnel.eventType")}>
        <select id={ids.kind} value={v.kind} onChange={(e) => set({ kind: e.target.value as EventKind, unit_id: "" })}>
          {EVENT_KINDS.map((k) => (
            <option key={k} value={k}>
              {t(`personnel.eventKind.${k}`)}
            </option>
          ))}
        </select>
      </Field>
      <Field id={ids.on} label={t("personnel.effectiveOn")}>
        <input id={ids.on} type="date" max={isoDay(new Date())} value={v.effective_on} onChange={(e) => set({ effective_on: e.target.value })} />
      </Field>
      {v.kind !== "transfer" && (
        <Field id={ids.title} label={t(`personnel.eventTitle.${v.kind}`)}>
          <input id={ids.title} dir="auto" maxLength={120} value={v.title} onChange={(e) => set({ title: e.target.value })} />
        </Field>
      )}
      {(v.kind === "transfer" || v.kind === "appointment") && (
        <Field id={ids.unit} label={t(v.kind === "transfer" ? "personnel.toUnit" : "personnel.toUnitOptional")}>
          <UnitSelect id={ids.unit} units={unitChoices} value={v.unit_id} onChange={(unit_id) => set({ unit_id })} any={t("personnel.form.pickUnit")} />
        </Field>
      )}
      <Field id={ids.ref} label={t("personnel.columns.reference")}>
        <input id={ids.ref} dir="auto" maxLength={120} value={v.reference} onChange={(e) => set({ reference: e.target.value })} />
      </Field>
      <Field id={ids.note} label={t("personnel.columns.note")}>
        <textarea id={ids.note} dir="auto" maxLength={1000} rows={2} value={v.note} onChange={(e) => set({ note: e.target.value })} />
      </Field>
    </FormCard>
  );
}

function IdentityForm({ agent, onDone }: { agent: PersonnelAgent; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const done = useInvalidate();
  const ids = { matricule: useId(), name: useId(), category: useId(), phone: useId() };
  const [v, setV] = useState({ matricule: agent.matricule, full_name: agent.full_name, category: agent.category, phone: agent.phone ?? "" });
  const save = useMutation({
    mutationFn: () => api.updatePersonnelAgent(agent.id, { ...v, phone: v.phone.trim() || null, version: agent.version }),
    onSuccess: () => {
      done();
      onDone();
    },
  });
  const set = (p: Partial<typeof v>) => setV((x) => ({ ...x, ...p }));
  return (
    <FormCard title={t("personnel.editIdentity")} error={save.error} pending={save.isPending} onSubmit={() => save.mutate()} onCancel={onDone}>
      <Field id={ids.matricule} label={t("personnel.columns.matricule")}>
        <input id={ids.matricule} dir="ltr" maxLength={30} value={v.matricule} onChange={(e) => set({ matricule: e.target.value })} />
      </Field>
      <Field id={ids.name} label={t("personnel.columns.name")}>
        <input id={ids.name} dir="auto" maxLength={120} value={v.full_name} onChange={(e) => set({ full_name: e.target.value })} />
      </Field>
      <Field id={ids.category} label={t("personnel.columns.category")}>
        <select id={ids.category} value={v.category} onChange={(e) => set({ category: e.target.value as Category })}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {t(`personnel.category.${c}`)}
            </option>
          ))}
        </select>
      </Field>
      <Field id={ids.phone} label={t("personnel.columns.phone")}>
        <input id={ids.phone} dir="ltr" type="tel" maxLength={30} value={v.phone} onChange={(e) => set({ phone: e.target.value })} />
      </Field>
      <p className="muted personnel-form__hint">{t("personnel.form.rankThroughFile")}</p>
    </FormCard>
  );
}
