import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { CategorySelect, GouvernoratSelect, MutationError } from "../components/Phase8Bits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { p8Keys } from "../lib/phase8Api";
import {
  REPORT_FORMATS,
  SCHEDULE_FREQUENCIES,
  SCHEDULE_KINDS,
  type ReportFormat,
  type ReportSchedule,
  type ScheduleBody,
  type ScheduleFrequency,
  type ScheduleKind,
} from "../lib/phase8Types";
import type { Category } from "../lib/types";
import { ReportsLibraryTabs } from "./ReportsLibraryPage";
import { LANGUAGES, type Language } from "../i18n";
import { PageTitle } from "../components/PageTitle";
import { Stepper } from "../components/Stepper";

const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
/** Staff subject ids are UUIDs (Keycloak `sub`). */
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export interface ScheduleFormState {
  title: string;
  kind: ScheduleKind;
  gouvernorat: number | null;
  category: Category | null;
  format: ReportFormat;
  lang: Language;
  frequency: ScheduleFrequency;
  time: string;
  weekday: number;
  day: number;
  recipients: string[];
  enabled: boolean;
}

export function scheduleBody(f: ScheduleFormState): { body: ScheduleBody | null; errors: Partial<Record<string, true>> } {
  const errors: Partial<Record<string, true>> = {};
  if (!f.title.trim()) errors.title = true;
  if (!TIME_RE.test(f.time)) errors.time = true;
  if (f.recipients.length === 0) errors.recipients = true;
  if (f.kind === "gouvernorat_summary" && f.gouvernorat === null) errors.gouvernorat = true;
  if (Object.keys(errors).length > 0) return { body: null, errors };
  return {
    body: {
      title: f.title.trim(),
      kind: f.kind,
      filters: f.category ? { category: f.category } : {},
      gouvernorats: f.gouvernorat === null ? [] : [f.gouvernorat],
      format: f.format,
      lang: f.lang,
      cron: {
        frequency: f.frequency,
        time: f.time,
        ...(f.frequency === "weekly" ? { weekday: f.weekday } : {}),
        ...(f.frequency === "monthly" ? { day: f.day } : {}),
      },
      recipients: f.recipients,
      enabled: f.enabled,
    },
    errors,
  };
}

function formFrom(s: ReportSchedule | null, own: number | null, me: string, lang: Language): ScheduleFormState {
  if (!s)
    return {
      title: "",
      kind: own !== null ? "gouvernorat_summary" : "period_summary",
      gouvernorat: own,
      category: null,
      format: "pdf",
      lang,
      frequency: "weekly",
      time: "07:00",
      weekday: 1,
      day: 1,
      recipients: me ? [me] : [],
      enabled: true,
    };
  return {
    title: s.title,
    kind: s.kind,
    gouvernorat: s.gouvernorats[0] ?? null,
    category: s.filters.category ?? null,
    format: s.format,
    lang: s.lang,
    frequency: s.cron.frequency,
    time: s.cron.time,
    weekday: s.cron.weekday ?? 1,
    day: s.cron.day ?? 1,
    recipients: s.recipients,
    enabled: s.enabled,
  };
}

function RecipientsField({ value, onChange, invalid }: { value: string[]; onChange: (v: string[]) => void; invalid: boolean }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const id = useId();
  const [text, setText] = useState("");
  const [bad, setBad] = useState(false);
  const me = user?.identity.subject ?? "";
  const add = (raw: string) => {
    const v = raw.trim().toLowerCase();
    if (!UUID_RE.test(v)) {
      setBad(true);
      return;
    }
    setBad(false);
    if (!value.includes(v)) onChange([...value, v]);
    setText("");
  };
  return (
    <fieldset className={`recipients${invalid ? " field--invalid" : ""}`}>
      <legend>{t("schedules.recipients")}</legend>
      <p className="muted">{t("schedules.recipientsHint")}</p>
      <ul className="chips">
        {value.map((r) => (
          <li key={r} className="chip">
            <span className="code" dir="ltr">
              {r === me ? t("schedules.me") : r}
            </span>
            <button
              type="button"
              className="btn btn--ghost btn--small"
              aria-label={t("schedules.removeRecipient", { id: r === me ? t("schedules.me") : r })}
              onClick={() => onChange(value.filter((x) => x !== r))}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      <div className="input-with-button">
        <label htmlFor={id} className="visually-hidden">
          {t("schedules.recipientId")}
        </label>
        <input
          id={id}
          dir="ltr"
          className="code"
          placeholder={t("schedules.recipientId")}
          value={text}
          aria-invalid={bad ? true : undefined}
          onChange={(e) => setText(e.target.value)}
        />
        <button type="button" className="btn" onClick={() => add(text)}>
          {t("schedules.addRecipient")}
        </button>
        {me && !value.includes(me) && UUID_RE.test(me) && (
          <button type="button" className="btn btn--ghost" onClick={() => onChange([...value, me])}>
            {t("schedules.addMe")}
          </button>
        )}
      </div>
      {bad && <p className="field__error">{t("schedules.recipientInvalid")}</p>}
      {invalid && <p className="field__error">{t("schedules.recipientsRequired")}</p>}
    </fieldset>
  );
}

function ScheduleForm({ schedule, onDone }: { schedule: ReportSchedule | null; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const lang = useLanguage();
  const qc = useQueryClient();
  const base = useId();
  const national = user?.identity.national ?? false;
  const own = national ? null : (user?.identity.gouvernoratCode ?? null);
  const [form, setForm] = useState(() => formFrom(schedule, own, user?.identity.subject ?? "", lang));
  const [touched, setTouched] = useState(false);
  const { body, errors } = scheduleBody(form);
  const set = (patch: Partial<ScheduleFormState>) => setForm((f) => ({ ...f, ...patch }));
  const save = useMutation({
    mutationFn: (b: ScheduleBody) => (schedule ? api.updateSchedule(schedule.id, b) : api.createSchedule(b)),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: p8Keys.schedules });
      onDone();
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTouched(true);
    if (body) save.mutate(body);
  };
  const err = (k: string) => touched && errors[k] === true;
  return (
    <form className="card ops-form schedule-form" onSubmit={submit} noValidate aria-labelledby={`${base}-h`}>
      <h2 id={`${base}-h`}>{schedule ? t("schedules.edit") : t("schedules.new")}</h2>
      <div className="fields-row">
        <div className={`field${err("title") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-title`}>{t("library.reports.titleField")}</label>
          <input id={`${base}-title`} dir="auto" maxLength={200} value={form.title} onChange={(e) => set({ title: e.target.value })} />
          {err("title") && <p className="field__error">{t("library.reports.form.titleRequired")}</p>}
        </div>
        <div className="field">
          <label htmlFor={`${base}-kind`}>{t("library.reports.kind")}</label>
          <select id={`${base}-kind`} value={form.kind} onChange={(e) => set({ kind: e.target.value as ScheduleKind })}>
            {SCHEDULE_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`library.reports.kinds.${k}`)}
              </option>
            ))}
          </select>
        </div>
        {national && (
          <GouvernoratSelect
            value={form.gouvernorat}
            onChange={(g) => set({ gouvernorat: g })}
            label={t("analytics.gouvernorat")}
            allLabel={t("analytics.national")}
          />
        )}
        <CategorySelect
          value={form.category}
          onChange={(c) => set({ category: (c as Category | null) ?? null })}
          label={t("analytics.category")}
          allLabel={t("analytics.allCategories")}
        />
      </div>
      {err("gouvernorat") && <p className="field__error">{t("library.reports.form.gouvernoratRequired")}</p>}
      <div className="fields-row">
        <div className="field">
          <label htmlFor={`${base}-freq`}>{t("schedules.frequency")}</label>
          <select id={`${base}-freq`} value={form.frequency} onChange={(e) => set({ frequency: e.target.value as ScheduleFrequency })}>
            {SCHEDULE_FREQUENCIES.map((f) => (
              <option key={f} value={f}>
                {t(`schedules.frequencies.${f}`)}
              </option>
            ))}
          </select>
        </div>
        {form.frequency === "weekly" && (
          <div className="field">
            <label htmlFor={`${base}-wd`}>{t("schedules.weekday")}</label>
            <select id={`${base}-wd`} value={form.weekday} onChange={(e) => set({ weekday: Number(e.target.value) })}>
              {[1, 2, 3, 4, 5, 6, 7].map((d) => (
                <option key={d} value={d}>
                  {t(`analytics.weekday.${d}`)}
                </option>
              ))}
            </select>
          </div>
        )}
        {form.frequency === "monthly" && (
          <div className="field field--number">
            <label htmlFor={`${base}-day`}>{t("schedules.day")}</label>
            <Stepper id={`${base}-day`} min={1} max={28} value={form.day} label={t("schedules.day")} onChange={(n) => set({ day: n })} />
          </div>
        )}
        <div className={`field${err("time") ? " field--invalid" : ""}`}>
          <label htmlFor={`${base}-time`}>{t("schedules.time")}</label>
          <input id={`${base}-time`} type="time" value={form.time} onChange={(e) => set({ time: e.target.value })} />
        </div>
      </div>
      <p className="muted">{t("schedules.timezoneNote")}</p>
      <div className="fields-row">
        <fieldset className="segmented">
          <legend>{t("library.reports.format")}</legend>
          {REPORT_FORMATS.map((f) => (
            <label key={f} className="segmented__item">
              <input type="radio" name={`${base}-format`} checked={form.format === f} onChange={() => set({ format: f })} />
              <span>{t(`library.reports.formats.${f}`)}</span>
            </label>
          ))}
        </fieldset>
        <fieldset className="segmented">
          <legend>{t("library.reports.lang")}</legend>
          {LANGUAGES.map((l) => (
            <label key={l} className="segmented__item">
              <input type="radio" name={`${base}-lang`} checked={form.lang === l} onChange={() => set({ lang: l })} />
              <span lang={l}>{t(`languages.${l}`)}</span>
            </label>
          ))}
        </fieldset>
      </div>
      <RecipientsField value={form.recipients} onChange={(recipients) => set({ recipients })} invalid={err("recipients")} />
      <label className="checkbox">
        <input type="checkbox" checked={form.enabled} onChange={(e) => set({ enabled: e.target.checked })} />
        <span>{t("schedules.enabled")}</span>
      </label>
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={save.isPending}>
          {save.isPending ? t("ops.working") : t("schedules.save")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
      {save.isError && <MutationError error={save.error} />}
    </form>
  );
}

function cronText(s: ReportSchedule, t: (k: string, o?: Record<string, unknown>) => string): string {
  const { frequency, time, weekday, day } = s.cron;
  if (frequency === "weekly") return t("schedules.cron.weekly", { day: t(`analytics.weekday.${weekday ?? 1}`), time });
  if (frequency === "monthly") return t("schedules.cron.monthly", { day: day ?? 1, time });
  return t("schedules.cron.daily", { time });
}

/** Scheduled reports: generated on each run, recipients notified in the app (no e-mail in this phase). */
export function ReportSchedulesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const [editing, setEditing] = useState<ReportSchedule | "new" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const query = useQuery({ queryKey: p8Keys.schedules, queryFn: ({ signal }) => api.schedules(signal) });
  const toggle = useMutation({
    mutationFn: (s: ReportSchedule) => api.updateSchedule(s.id, { enabled: !s.enabled }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: p8Keys.schedules }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteSchedule(id),
    onSuccess: () => {
      setConfirmDelete(null);
      void qc.invalidateQueries({ queryKey: p8Keys.schedules });
    },
  });
  const rows = query.data ?? [];
  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="schedule" tone="slate">{t("schedules.title")}</PageTitle>
        {editing === null && (
          <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
            {t("schedules.new")}
          </button>
        )}
      </div>
      <ReportsLibraryTabs />
      <p className="muted">{t("schedules.intro")}</p>
      {editing !== null && (
        <ScheduleForm
          key={editing === "new" ? "new" : editing.id}
          schedule={editing === "new" ? null : editing}
          onDone={() => setEditing(null)}
        />
      )}
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && rows.length === 0 && <p className="muted">{t("schedules.none")}</p>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("schedules.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("library.reports.titleField")}</th>
                <th scope="col">{t("library.reports.kind")}</th>
                <th scope="col">{t("schedules.when")}</th>
                <th scope="col">{t("analytics.gouvernorat")}</th>
                <th scope="col">{t("schedules.recipients")}</th>
                <th scope="col">{t("schedules.nextRun")}</th>
                <th scope="col">{t("schedules.enabled")}</th>
                <th scope="col">{t("schedules.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id}>
                  <th scope="row" dir="auto">
                    {s.title}
                  </th>
                  <td>{t(`library.reports.kinds.${s.kind}`)}</td>
                  <td>{cronText(s, t)}</td>
                  <td>
                    {s.gouvernorats.length === 0
                      ? t("analytics.national")
                      : s.gouvernorats.map((c) => gouvernorats.nameOf(c)).join(t("common.listSeparator"))}
                  </td>
                  <td>{fmt.number(s.recipients.length)}</td>
                  <td>{s.next_run_at ? fmt.dateTime(s.next_run_at) : "—"}</td>
                  <td>
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={s.enabled}
                        disabled={toggle.isPending}
                        onChange={() => toggle.mutate(s)}
                        aria-label={t("schedules.toggle", { title: s.title })}
                      />
                    </label>
                  </td>
                  <td className="ops-row-actions">
                    <button type="button" className="btn btn--small" onClick={() => setEditing(s)}>
                      {t("schedules.editShort")}
                    </button>
                    {confirmDelete === s.id ? (
                      <>
                        <button
                          type="button"
                          className="btn btn--small btn--danger"
                          disabled={remove.isPending}
                          onClick={() => remove.mutate(s.id)}
                        >
                          {t("schedules.confirmDelete")}
                        </button>
                        <button type="button" className="btn btn--small" onClick={() => setConfirmDelete(null)}>
                          {t("common.cancel")}
                        </button>
                      </>
                    ) : (
                      <button type="button" className="btn btn--small btn--ghost" onClick={() => setConfirmDelete(s.id)}>
                        {t("schedules.delete")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {toggle.isError && <MutationError error={toggle.error} />}
      {remove.isError && <MutationError error={remove.error} />}
    </div>
  );
}
