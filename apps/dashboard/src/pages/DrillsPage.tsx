// covers: phase L5a (docs/phase-l/design-l5.md §2): the digital dry run, the list of dry runs and a new plan. Dormant:
// the page shows only when the system administrator granted it, and planning only through its own button.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { SimBadge } from "../components/crisis/CrisisBits";
import { DRILL_HAZARDS, DrillStatusPill } from "../components/DrillBits";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { drillKeys, type DrillIn } from "../lib/drill";
import { useCan } from "../lib/features";
import { useFormat, useGouvernorats } from "../lib/hooks";

/** The next round hour, as a datetime-local value. */
function nextHour(): string {
  const d = new Date(Date.now() + 60 * 60_000);
  d.setMinutes(0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function DrillForm({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const id = useId();
  const geo = useGouvernorats();
  const own = user?.identity.gouvernoratCode ?? null;
  const [form, setForm] = useState({
    title: "",
    objective: "",
    hazard_key: "",
    gouvernorats: own !== null ? [own] : ([] as number[]),
    planned_start: nextHour(),
    duration_min: 120,
    evaluator: "",
    evaluator_name: "",
  });
  const [tried, setTried] = useState(false);
  const create = useMutation({
    mutationFn: () => {
      const body: DrillIn = {
        title: form.title.trim(),
        objective: form.objective.trim(),
        hazard_key: form.hazard_key || null,
        gouvernorats: form.gouvernorats,
        planned_start: new Date(form.planned_start).toISOString(),
        duration_min: form.duration_min,
        evaluator: form.evaluator.trim() || null,
        evaluator_name: form.evaluator_name.trim() || null,
      };
      return api.createDrill(body);
    },
    onSuccess: (d) => {
      void qc.invalidateQueries({ queryKey: drillKeys.all });
      void navigate(`/drills/${d.id}`);
    },
  });
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));
  const titleOk = form.title.trim().length >= 3;
  const objectiveOk = form.objective.trim().length >= 3;
  const placesOk = form.gouvernorats.length > 0;
  const durationOk = form.duration_min >= 10 && form.duration_min <= 720;
  const ok = titleOk && objectiveOk && placesOk && durationOk && Boolean(form.planned_start);
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (ok) create.mutate();
  };
  const toggle = (code: number) =>
    set({
      gouvernorats: form.gouvernorats.includes(code)
        ? form.gouvernorats.filter((c) => c !== code)
        : [...form.gouvernorats, code].sort((a, b) => a - b),
    });
  return (
    <form className="card drill-form" aria-labelledby={`${id}-title`} onSubmit={submit} noValidate>
      <h2 id={`${id}-title`}>{t("drill.new.title")}</h2>
      <p className="muted">{t("drill.new.intro")}</p>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-name`}>
            {t("drill.field.title")}
          </label>
          <input
            id={`${id}-name`}
            value={form.title}
            maxLength={160}
            aria-required="true"
            aria-invalid={(tried && !titleOk) || undefined}
            onChange={(e) => set({ title: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-hazard`}>{t("drill.field.hazard")}</label>
          <select id={`${id}-hazard`} value={form.hazard_key} onChange={(e) => set({ hazard_key: e.target.value })}>
            <option value="">{t("drill.hazard.none")}</option>
            {DRILL_HAZARDS.map((h) => (
              <option key={h} value={h}>
                {t(`drill.hazard.${h}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field drill-form__wide">
          <label htmlFor={`${id}-objective`}>
            {t("drill.field.objective")}
          </label>
          <textarea
            id={`${id}-objective`}
            rows={3}
            value={form.objective}
            maxLength={2000}
            aria-required="true"
            aria-invalid={(tried && !objectiveOk) || undefined}
            onChange={(e) => set({ objective: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-start`}>
            {t("drill.field.planned_start")}
          </label>
          <input
            id={`${id}-start`}
            type="datetime-local"
            value={form.planned_start}
            aria-required="true"
            onChange={(e) => set({ planned_start: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-duration`}>
            {t("drill.field.duration_min")}
          </label>
          <input
            id={`${id}-duration`}
            type="number"
            min={10}
            max={720}
            value={form.duration_min}
            aria-required="true"
            aria-invalid={(tried && !durationOk) || undefined}
            aria-describedby={`${id}-duration-help`}
            onChange={(e) => set({ duration_min: Number(e.target.value) })}
          />
          <p id={`${id}-duration-help`} className={tried && !durationOk ? "field__error" : "muted"}>
            {t("drill.new.durationHelp")}
          </p>
        </div>
        <div className="field">
          <label htmlFor={`${id}-evaluator`}>{t("drill.field.evaluator")}</label>
          <input
            id={`${id}-evaluator`}
            dir="ltr"
            value={form.evaluator}
            maxLength={255}
            aria-describedby={`${id}-evaluator-help`}
            onChange={(e) => set({ evaluator: e.target.value })}
          />
          <p id={`${id}-evaluator-help`} className="muted">
            {t("drill.new.evaluatorHelp")}
          </p>
        </div>
        <div className="field">
          <label htmlFor={`${id}-evaluator-name`}>{t("drill.field.evaluator_name")}</label>
          <input
            id={`${id}-evaluator-name`}
            value={form.evaluator_name}
            maxLength={200}
            onChange={(e) => set({ evaluator_name: e.target.value })}
          />
        </div>
      </div>
      <fieldset className="drill-form__places" aria-invalid={(tried && !placesOk) || undefined}>
        <legend>
          {t("drill.field.gouvernorats")}
        </legend>
        {own !== null ? (
          <p className="muted">{t("drill.new.ownOnly", { name: geo.nameOf(own) })}</p>
        ) : (
          <div className="drill-form__grid">
            {geo.list.map((g) => (
              <label key={g.code} className="checkbox">
                <input type="checkbox" checked={form.gouvernorats.includes(g.code)} onChange={() => toggle(g.code)} />
                <span>{geo.nameOf(g.code)}</span>
              </label>
            ))}
          </div>
        )}
        {tried && !placesOk && <p className="field__error">{t("drill.new.placesHelp")}</p>}
      </fieldset>
      {create.isError && (
        <p role="alert" className="alert alert--error">
          {t(errorMessageKey(create.error))}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={create.isPending}>
          {t("drill.new.create")}
        </button>
        <button type="button" className="btn" onClick={onClose}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

export function DrillsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const geo = useGouvernorats();
  const canPlan = useCan("drill.plan", false);
  const [open, setOpen] = useState(false);
  const list = useQuery({ queryKey: drillKeys.list, queryFn: ({ signal }) => api.drills(signal) });
  const items = list.data ?? [];
  return (
    <div className="page drills-page">
      <PageTitle icon="militaryTech" tone="amber">
        {t("drill.title")}
      </PageTitle>
      <p className="muted">
        <SimBadge /> {t("drill.intro")}
      </p>
      <ul className="drill-measures" aria-label={t("drill.measures.label")}>
        {(["load", "resources", "room"] as const).map((k) => (
          <li key={k} className="card drill-measures__item">
            <strong>{t(`drill.measures.${k}.title`)}</strong>
            <span className="muted">{t(`drill.measures.${k}.text`)}</span>
          </li>
        ))}
      </ul>
      {canPlan && !open && (
        <div className="actions">
          <button type="button" className="btn btn--primary" onClick={() => setOpen(true)}>
            {t("drill.new.open")}
          </button>
        </div>
      )}
      {open && <DrillForm onClose={() => setOpen(false)} />}
      {list.isLoading && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && (
        <div className="table-wrap">
          <table className="table">
            <caption>{t("drill.listCaption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("drill.field.title")}</th>
                <th scope="col">{t("drill.field.gouvernorats")}</th>
                <th scope="col">{t("drill.field.planned_start")}</th>
                <th scope="col">{t("drill.field.duration_min")}</th>
                <th scope="col">{t("drill.field.injects")}</th>
                <th scope="col">{t("drill.field.status")}</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">
                    {t("drill.empty")}
                  </td>
                </tr>
              )}
              {items.map((d) => (
                <tr key={d.id}>
                  <th scope="row">
                    <Link to={`/drills/${d.id}`} dir="auto">
                      {d.title}
                    </Link>
                    {d.my_approval !== null && (
                      <div>
                        <span className="pill tone-amber">{t("drill.approval.awaitsYou")}</span>
                      </div>
                    )}
                  </th>
                  <td>{d.gouvernorats.map((c) => geo.nameOf(c)).join(t("common.listSeparator"))}</td>
                  <td>{fmt.dateTime(d.planned_start)}</td>
                  <td>{t("drill.minutes", { count: d.duration_min })}</td>
                  <td>{fmt.number(d.injects)}</td>
                  <td>
                    <DrillStatusPill status={d.status} />
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
