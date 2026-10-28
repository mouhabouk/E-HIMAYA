import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type ReactNode, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { CategoryLabel } from "../components/CategoryIcon";
import { ErrorBox, Loading } from "../components/Feedback";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import {
  RULES,
  toForm,
  validateAiSettings,
  type AiSettingsForm,
  type FieldError,
  type FormErrors,
} from "../lib/aiSettings";
import { errorMessageKey } from "../lib/api";
import { useAiStatus, useFormat } from "../lib/hooks";
import { canEditAiSettings } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import { AI_CAPABILITIES, CATEGORIES, PRIORITY_COMPONENTS, type AiSettings } from "../lib/types";
import { PageTitle } from "../components/PageTitle";
import { Stepper } from "../components/Stepper";

function useFieldError() {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (e: FieldError | undefined): string | null => {
    if (!e) return null;
    if (e.key === "range") return t("aiSettings.validation.range", { min: fmt.number(e.min), max: fmt.number(e.max) });
    return t(`aiSettings.validation.${e.key}`);
  };
}

interface NumberFieldProps {
  id: string;
  label: ReactNode;
  value: string;
  onChange: (v: string) => void;
  rule: { min: number; max: number; integer: boolean };
  error: FieldError | undefined;
  readOnly: boolean;
}

function NumberField({ id, label, value, onChange, rule, error, readOnly }: NumberFieldProps) {
  const message = useFieldError()(error);
  const errorId = `${id}-error`;
  return (
    <div className={`field field--number${message ? " field--invalid" : ""}`}>
      <label htmlFor={id}>{label}</label>
      <Stepper
        id={id}
        dir="ltr"
        min={rule.min}
        max={rule.max}
        step={rule.integer ? 1 : 0.01}
        value={value === "" ? null : Number(value)}
        readOnly={readOnly}
        invalid={Boolean(message)}
        describedBy={message ? errorId : undefined}
        onChange={(n) => onChange(String(n))}
        onClear={() => onChange("")}
      />
      {message && (
        <span id={errorId} className="field__error">
          {message}
        </span>
      )}
    </div>
  );
}

function AiStatusSection() {
  const { t } = useTranslation();
  const status = useAiStatus();
  if (status.isPending) return <Loading />;
  if (status.isError) return <ErrorBox error={status.error} onRetry={() => void status.refetch()} />;
  const s = status.data;
  const extra = Object.keys(s.capabilities).filter((k) => !(AI_CAPABILITIES as readonly string[]).includes(k));
  const keys = [...AI_CAPABILITIES, ...extra];
  return (
    <>
      <p className={`alert ${s.configured ? "alert--ok" : "alert--warn"}`}>
        {s.configured ? t("aiSettings.status.configured") : t("aiSettings.status.notConfigured")}
      </p>
      {s.configured && Object.keys(s.capabilities).length === 0 && (
        <p className="alert alert--warn">{t("aiSettings.status.unreachable")}</p>
      )}
      {s.configured && Object.keys(s.capabilities).length > 0 && (
        <table className="table">
          <caption className="visually-hidden">{t("aiSettings.status.title")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("aiSettings.status.capability")}</th>
              <th scope="col">{t("aiSettings.status.state")}</th>
              <th scope="col">{t("aiSettings.status.model")}</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => {
              const c = s.capabilities[k];
              const ready = c?.ready ?? false;
              return (
                <tr key={k}>
                  <th scope="row">
                    {(AI_CAPABILITIES as readonly string[]).includes(k)
                      ? t(`aiSettings.capabilities.${k}`)
                      : t("ai.componentOther", { key: k })}
                  </th>
                  <td>
                    <span className={`tag ${ready ? "tag--ready" : "tag--down"}`}>
                      {ready ? t("aiSettings.status.ready") : t("aiSettings.status.down")}
                    </span>
                  </td>
                  <td dir="ltr" className="code">
                    {c?.model ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </>
  );
}

/** The settings form; `initial` is the server's current value. */
export function AiSettingsFormView({ initial, editable }: { initial: AiSettings; editable: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const base = useId();
  const fieldError = useFieldError();
  const [form, setForm] = useState<AiSettingsForm>(() => toForm(initial));
  const [errors, setErrors] = useState<FormErrors>({});
  const [saved, setSaved] = useState(false);

  const mutation = useMutation({
    mutationFn: (s: AiSettings) => api.saveAiSettings(s),
    onSuccess: (s) => {
      qc.setQueryData(queryKeys.aiSettings, s);
      setForm(toForm(s));
      setSaved(true);
    },
  });

  const update = (patch: (f: AiSettingsForm) => AiSettingsForm) => {
    setSaved(false);
    setForm((f) => patch(f));
  };

  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const result = validateAiSettings(form);
    setErrors(result.errors);
    if (!result.settings) return;
    mutation.mutate(result.settings);
  };

  const weightTotal = PRIORITY_COMPONENTS.reduce((n, k) => n + (Number(form.weights[k]) || 0), 0);
  const ro = !editable || mutation.isPending;
  const hasErrors = Object.keys(errors).length > 0;

  return (
    <form className="settings-form" onSubmit={submit} noValidate>
      <section className="card" aria-labelledby={`${base}-prio`}>
        <h2 id={`${base}-prio`}>{t("aiSettings.priority.title")}</h2>
        <fieldset>
          <legend>{t("aiSettings.priority.weights")}</legend>
          <p className="muted">{t("aiSettings.priority.weightsHelp")}</p>
          <div className="settings-grid">
            {PRIORITY_COMPONENTS.map((k) => (
              <NumberField
                key={k}
                id={`${base}-w-${k}`}
                label={t(`ai.components.${k}`)}
                value={form.weights[k]}
                rule={RULES.weight}
                error={errors[`weights.${k}`]}
                readOnly={ro}
                onChange={(v) => update((f) => ({ ...f, weights: { ...f.weights, [k]: v } }))}
              />
            ))}
          </div>
          <p className="muted">{t("aiSettings.priority.weightsTotal", { total: fmt.number(weightTotal) })}</p>
          {errors.weights && <p className="field__error">{fieldError(errors.weights)}</p>}
        </fieldset>
        <fieldset>
          <legend>{t("aiSettings.priority.categorySeverity")}</legend>
          <p className="muted">{t("aiSettings.priority.severityHelp")}</p>
          <div className="settings-grid">
            {CATEGORIES.map((c) => (
              <NumberField
                key={c}
                id={`${base}-s-${c}`}
                label={<CategoryLabel category={c} />}
                value={form.category_severity[c]}
                rule={RULES.severity}
                error={errors[`category_severity.${c}`]}
                readOnly={ro}
                onChange={(v) => update((f) => ({ ...f, category_severity: { ...f.category_severity, [c]: v } }))}
              />
            ))}
          </div>
        </fieldset>
        <NumberField
          id={`${base}-conf`}
          label={t("aiSettings.priority.suggestionMinConfidence")}
          value={form.suggestion_min_confidence}
          rule={RULES.suggestion_min_confidence}
          error={errors.suggestion_min_confidence}
          readOnly={ro}
          onChange={(v) => update((f) => ({ ...f, suggestion_min_confidence: v }))}
        />
      </section>

      <section className="card" aria-labelledby={`${base}-group`}>
        <h2 id={`${base}-group`}>{t("aiSettings.grouping.title")}</h2>
        <p className="muted">{t("aiSettings.grouping.help")}</p>
        <NumberField
          id={`${base}-window`}
          label={t("aiSettings.grouping.windowMin")}
          value={form.window_min}
          rule={RULES.window_min}
          error={errors.window_min}
          readOnly={ro}
          onChange={(v) => update((f) => ({ ...f, window_min: v }))}
        />
        <fieldset>
          <legend>{t("aiSettings.grouping.radius")}</legend>
          <div className="settings-grid">
            {CATEGORIES.map((c) => (
              <NumberField
                key={c}
                id={`${base}-r-${c}`}
                label={<CategoryLabel category={c} />}
                value={form.radius_m[c]}
                rule={RULES.radius_m}
                error={errors[`radius_m.${c}`]}
                readOnly={ro}
                onChange={(v) => update((f) => ({ ...f, radius_m: { ...f.radius_m, [c]: v } }))}
              />
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>{t("aiSettings.grouping.semantic")}</legend>
          <div className="settings-grid">
            <NumberField
              id={`${base}-sim`}
              label={t("aiSettings.grouping.semanticMinSimilarity")}
              value={form.semantic_min_similarity}
              rule={RULES.semantic_min_similarity}
              error={errors.semantic_min_similarity}
              readOnly={ro}
              onChange={(v) => update((f) => ({ ...f, semantic_min_similarity: v }))}
            />
            <NumberField
              id={`${base}-srad`}
              label={t("aiSettings.grouping.semanticRadiusM")}
              value={form.semantic_radius_m}
              rule={RULES.semantic_radius_m}
              error={errors.semantic_radius_m}
              readOnly={ro}
              onChange={(v) => update((f) => ({ ...f, semantic_radius_m: v }))}
            />
            <NumberField
              id={`${base}-swin`}
              label={t("aiSettings.grouping.semanticWindowMin")}
              value={form.semantic_window_min}
              rule={RULES.semantic_window_min}
              error={errors.semantic_window_min}
              readOnly={ro}
              onChange={(v) => update((f) => ({ ...f, semantic_window_min: v }))}
            />
          </div>
        </fieldset>
      </section>

      {editable && (
        <div className="actions">
          <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
            {mutation.isPending ? t("aiSettings.saving") : t("aiSettings.save")}
          </button>
          <button
            type="button"
            className="btn"
            disabled={mutation.isPending}
            onClick={() => {
              setErrors({});
              setSaved(false);
              setForm(toForm(initial));
            }}
          >
            {t("aiSettings.reset")}
          </button>
        </div>
      )}
      <div aria-live="polite" role="status">
        {saved && !mutation.isPending && <p className="alert alert--ok">{t("aiSettings.saved")}</p>}
      </div>
      {hasErrors && (
        <p className="alert alert--error" role="alert">
          {t("aiSettings.validation.summary")}
        </p>
      )}
      {mutation.isError && (
        <div className="alert alert--error" role="alert">
          <p>
            <strong>{t("aiSettings.saveFailed")}</strong>
          </p>
          <p>{t(errorMessageKey(mutation.error))}</p>
        </div>
      )}
    </form>
  );
}

/** Phase 3 §4: BR-20 weights and BR-10 thresholds (readable by all staff), and the AI service status. */
export function AiSettingsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const editable = user ? canEditAiSettings(user.identity) : false;
  const query = useQuery({
    queryKey: queryKeys.aiSettings,
    queryFn: ({ signal }) => api.aiSettings(signal),
  });

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="smartToy" tone="slate">{t("aiSettings.title")}</PageTitle>
      </div>
      <p className="muted">{t("aiSettings.intro")}</p>

      <section className="card" aria-labelledby="sec-ai-status">
        <h2 id="sec-ai-status">{t("aiSettings.status.title")}</h2>
        <AiStatusSection />
      </section>

      {!editable && <p className="alert alert--info">{t("aiSettings.readOnly")}</p>}
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && <AiSettingsFormView initial={query.data} editable={editable} />}
    </div>
  );
}
