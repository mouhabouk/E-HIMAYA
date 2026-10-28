import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { crewKeys } from "../lib/crewApi";
import { FIELD_TYPES, type FieldType, type Lang, type ReportTemplate, type TemplateField } from "../lib/crewTypes";
import { useFormat, useLanguage } from "../lib/hooks";
import { localized } from "../lib/localized";
import { classificationsFor } from "../lib/opsTypes";
import { canEditReportTemplates } from "../lib/roles";
import { CATEGORIES, type Category } from "../lib/types";
import { Stepper } from "../components/Stepper";

const LANGS: Lang[] = ["ar", "fr", "en"];
const KEY = /^[a-z0-9_]{1,40}$/;

function MutationError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  return (
    <p className="alert alert--error" role="alert">
      {t(errorMessageKey(error))}
    </p>
  );
}

/** What the leader sees on the phone: one block per question, chips, yes or no, or − 0 +. */
function PhonePreview({ template }: { template: Pick<ReportTemplate, "fields" | "simulated"> }) {
  const { t } = useTranslation();
  const lang = useLanguage();
  return (
    <div className="phone-preview" aria-label={t("templates.preview")}>
      {template.simulated && <span className="tag tag--sim">[SIM] {t("templates.simulated")}</span>}
      {template.fields.map((f) => (
        <div key={f.key} className="phone-preview__field">
          <strong dir="auto">
            {localized(f.label, lang) || f.key}
            {f.required && <span className="muted"> · {t("templates.required")}</span>}
          </strong>
          <div className="phone-preview__answers">
            {(f.type === "single" || f.type === "multi") &&
              (f.options ?? []).map((o) => (
                <span key={o.key} className="chip" dir="auto">
                  {localized(o.label, lang) || o.key}
                </span>
              ))}
            {f.type === "yesno" && (
              <>
                <span className="chip">{t("common.no")}</span>
                <span className="chip">{t("common.yes")}</span>
              </>
            )}
            {f.type === "count" && (
              <span className="chip">
                − 0 + {f.unit ? <span dir="auto">{localized(f.unit, lang)}</span> : null}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function LabelInputs({
  value,
  onChange,
  legend,
}: {
  value: Partial<Record<Lang, string>>;
  onChange: (v: Partial<Record<Lang, string>>) => void;
  legend: string;
}) {
  const { t } = useTranslation();
  const id = useId();
  return (
    <fieldset className="template-labels">
      <legend>{legend}</legend>
      {LANGS.map((l) => (
        <div key={l} className="field field--inline">
          <label htmlFor={`${id}-${l}`}>{t(`templates.lang.${l}`)}</label>
          <input
            id={`${id}-${l}`}
            lang={l}
            dir={l === "ar" ? "rtl" : "ltr"}
            maxLength={120}
            value={value[l] ?? ""}
            onChange={(e) => onChange({ ...value, [l]: e.target.value })}
          />
        </div>
      ))}
    </fieldset>
  );
}

/** One question of the draft: its key, shape, labels in three languages, and its chips or unit. */
function FieldEditor({
  field,
  index,
  count,
  onChange,
  onRemove,
  onMove,
}: {
  field: TemplateField;
  index: number;
  count: number;
  onChange: (f: TemplateField) => void;
  onRemove: () => void;
  onMove: (delta: number) => void;
}) {
  const { t } = useTranslation();
  const ids = { key: useId(), type: useId(), max: useId() };
  const chips = field.type === "single" || field.type === "multi";
  const options = field.options ?? [];
  return (
    <li className="template-field">
      <div className="template-field__head">
        <strong>{t("templates.fieldN", { n: index + 1 })}</strong>
        <div className="ops-row-actions">
          <button type="button" className="btn btn--small" disabled={index === 0} onClick={() => onMove(-1)}>
            {t("templates.up")}
          </button>
          <button type="button" className="btn btn--small" disabled={index === count - 1} onClick={() => onMove(1)}>
            {t("templates.down")}
          </button>
          <button type="button" className="btn btn--small" onClick={onRemove}>
            {t("templates.removeField")}
          </button>
        </div>
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={ids.key}>{t("templates.key")}</label>
          <input
            id={ids.key}
            dir="ltr"
            value={field.key}
            maxLength={40}
            aria-invalid={!KEY.test(field.key)}
            onChange={(e) => onChange({ ...field, key: e.target.value.toLowerCase() })}
          />
        </div>
        <div className="field">
          <label htmlFor={ids.type}>{t("templates.type")}</label>
          <select
            id={ids.type}
            value={field.type}
            onChange={(e) => {
              const type = e.target.value as FieldType;
              const keep = type === "single" || type === "multi";
              onChange({ ...field, type, options: keep ? options : [], unit: type === "count" ? field.unit : null });
            }}
          >
            {FIELD_TYPES.map((x) => (
              <option key={x} value={x}>
                {t(`templates.types.${x}`)}
              </option>
            ))}
          </select>
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={field.required ?? false}
            onChange={(e) => onChange({ ...field, required: e.target.checked })}
          />
          <span>{t("templates.required")}</span>
        </label>
      </div>
      <LabelInputs legend={t("templates.label")} value={field.label} onChange={(label) => onChange({ ...field, label })} />
      {field.type === "count" && (
        <>
          <LabelInputs
            legend={t("templates.unit")}
            value={field.unit ?? {}}
            onChange={(unit) => onChange({ ...field, unit })}
          />
          <div className="field field--inline">
            <label htmlFor={ids.max}>{t("templates.max")}</label>
            <Stepper
              id={ids.max}
              min={1}
              max={100000}
              value={field.max ?? null}
              label={t("templates.max")}
              onChange={(n) => onChange({ ...field, max: n })}
              onClear={() => onChange({ ...field, max: null })}
            />
          </div>
        </>
      )}
      {chips && (
        <fieldset className="template-options">
          <legend>{t("templates.options")}</legend>
          <ol>
            {options.map((o, i) => (
              <li key={i}>
                <input
                  aria-label={t("templates.optionKey", { n: i + 1 })}
                  dir="ltr"
                  value={o.key}
                  maxLength={40}
                  aria-invalid={!KEY.test(o.key)}
                  onChange={(e) => {
                    const next = [...options];
                    next[i] = { ...o, key: e.target.value.toLowerCase() };
                    onChange({ ...field, options: next });
                  }}
                />
                {LANGS.map((l) => (
                  <input
                    key={l}
                    aria-label={t("templates.optionLabel", { n: i + 1, lang: t(`templates.lang.${l}`) })}
                    lang={l}
                    dir={l === "ar" ? "rtl" : "ltr"}
                    maxLength={120}
                    value={o.label[l] ?? ""}
                    onChange={(e) => {
                      const next = [...options];
                      next[i] = { ...o, label: { ...o.label, [l]: e.target.value } };
                      onChange({ ...field, options: next });
                    }}
                  />
                ))}
                <button
                  type="button"
                  className="btn btn--small"
                  onClick={() => onChange({ ...field, options: options.filter((_, j) => j !== i) })}
                >
                  {t("templates.removeOption")}
                </button>
              </li>
            ))}
          </ol>
          <button
            type="button"
            className="btn btn--small"
            onClick={() => onChange({ ...field, options: [...options, { key: "", label: {} }] })}
          >
            {t("templates.addOption")}
          </button>
        </fieldset>
      )}
    </li>
  );
}

/** Empty labels are dropped (the API wants at least one language per label). */
function clean(fields: TemplateField[]): TemplateField[] {
  const strip = (l: Partial<Record<Lang, string>>) => {
    const out: Partial<Record<Lang, string>> = {};
    for (const lang of LANGS) {
      const v = l[lang]?.trim();
      if (v) out[lang] = v;
    }
    return out;
  };
  return fields.map((f) => ({
    key: f.key.trim(),
    type: f.type,
    label: strip(f.label),
    options: (f.options ?? []).map((o) => ({ key: o.key.trim(), label: strip(o.label) })),
    required: f.required ?? false,
    ...(f.type === "count" && f.unit && Object.keys(strip(f.unit)).length > 0 ? { unit: strip(f.unit) } : {}),
    ...(f.type === "count" && f.max ? { max: f.max } : {}),
  }));
}

function DraftEditor({ draft, canEdit }: { draft: ReportTemplate; canEdit: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const [fields, setFields] = useState<TemplateField[]>(draft.fields);
  const done = () => void qc.invalidateQueries({ queryKey: crewKeys.templatesAll });
  const save = useMutation({ mutationFn: () => api.editTemplate(draft.id, clean(fields)), onSuccess: done });
  const approve = useMutation({
    mutationFn: async () => {
      await api.editTemplate(draft.id, clean(fields));
      return api.approveTemplate(draft.id);
    },
    onSuccess: done,
  });
  const discard = useMutation({ mutationFn: () => api.discardTemplate(draft.id), onSuccess: done });
  const valid =
    fields.length > 0 &&
    fields.every(
      (f) =>
        KEY.test(f.key) &&
        LANGS.some((l) => f.label[l]?.trim()) &&
        ((f.type !== "single" && f.type !== "multi") ||
          ((f.options ?? []).length >= 2 && (f.options ?? []).every((o) => KEY.test(o.key)))),
    );
  const busy = save.isPending || approve.isPending || discard.isPending;
  return (
    <div className="template-editor">
      <PhonePreview template={{ fields, simulated: false }} />
      {canEdit && (
        <>
          <ol className="template-fields">
            {fields.map((f, i) => (
              <FieldEditor
                key={i}
                field={f}
                index={i}
                count={fields.length}
                onChange={(nf) => setFields(fields.map((x, j) => (j === i ? nf : x)))}
                onRemove={() => setFields(fields.filter((_, j) => j !== i))}
                onMove={(d) => {
                  const next = [...fields];
                  const [moved] = next.splice(i, 1);
                  if (moved) next.splice(i + d, 0, moved);
                  setFields(next);
                }}
              />
            ))}
          </ol>
          <div className="actions">
            <button
              type="button"
              className="btn"
              onClick={() => setFields([...fields, { key: "", type: "single", label: {}, options: [], required: false }])}
            >
              {t("templates.addField")}
            </button>
            <button type="button" className="btn" disabled={!valid || busy} onClick={() => save.mutate()}>
              {t("templates.save")}
            </button>
            <button type="button" className="btn btn--primary" disabled={!valid || busy} onClick={() => approve.mutate()}>
              {t("templates.approve")}
            </button>
            <button type="button" className="btn btn--danger" disabled={busy} onClick={() => discard.mutate()}>
              {t("templates.discard")}
            </button>
          </div>
          {!valid && <p className="hint">{t("templates.invalid")}</p>}
          <MutationError error={save.error ?? approve.error ?? discard.error} />
        </>
      )}
    </div>
  );
}

function TemplateCard({ template, all, canEdit }: { template: ReportTemplate; all: ReportTemplate[]; canEdit: boolean }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const qc = useQueryClient();
  const [open, setOpen] = useState(template.status === "draft");
  const done = () => void qc.invalidateQueries({ queryKey: crewKeys.templatesAll });
  const sameSlot = (x: ReportTemplate) => x.category === template.category && x.classification === template.classification;
  const hasDraft = all.some((x) => sameSlot(x) && x.status === "draft");
  const newVersion = useMutation({
    mutationFn: () => api.createTemplate(template.category, template.classification, template.fields),
    onSuccess: done,
  });
  const retire = useMutation({ mutationFn: () => api.retireTemplate(template.id), onSuccess: done });
  const headingId = useId();
  return (
    <article className="card template-card" aria-labelledby={headingId}>
      <header className="template-card__head">
        <h3 id={headingId}>
          {t(`category.${template.category}`)}
          {template.classification && ` · ${t(`ops.classification.${template.classification}`)}`}
          {" · "}
          {t("templates.version", { version: template.version })}
        </h3>
        <span className={`chip chip--template-${template.status}`}>{t(`templates.status.${template.status}`)}</span>
        {template.simulated && <span className="tag tag--sim">[SIM]</span>}
      </header>
      <p className="muted">
        {template.status === "approved" && template.approved_at
          ? t("templates.approvedBy", { name: template.approved_by_name ?? "—", date: fmt.dateTime(template.approved_at) })
          : t("templates.editedAt", { date: fmt.dateTime(template.updated_at) })}
        {" · "}
        {t("templates.fieldCount", { count: template.fields.length })}
      </p>
      {template.status === "draft" ? (
        <DraftEditor draft={template} canEdit={canEdit} />
      ) : (
        <>
          <div className="actions">
            <button type="button" className="btn btn--small" aria-expanded={open} onClick={() => setOpen(!open)}>
              {open ? t("templates.hide") : t("templates.show")}
            </button>
            {canEdit && template.status === "approved" && (
              <>
                <button
                  type="button"
                  className="btn btn--small btn--primary"
                  disabled={hasDraft || newVersion.isPending}
                  title={hasDraft ? t("templates.draftExists") : undefined}
                  onClick={() => newVersion.mutate()}
                >
                  {t("templates.newVersion")}
                </button>
                <button
                  type="button"
                  className="btn btn--small"
                  disabled={retire.isPending}
                  onClick={() => retire.mutate()}
                >
                  {t("templates.retire")}
                </button>
              </>
            )}
          </div>
          <MutationError error={newVersion.error ?? retire.error} />
          {open && <PhonePreview template={template} />}
        </>
      )}
    </article>
  );
}

function NewTemplateForm() {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const ids = { category: useId(), classification: useId() };
  const [category, setCategory] = useState<Category>("fire");
  const [classification, setClassification] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      api.createTemplate(category, classification || null, [
        {
          key: "state",
          type: "single",
          label: { ar: "الوضع", fr: "Situation", en: "Situation" },
          options: [
            { key: "under_control", label: { ar: "تحت السيطرة", fr: "Maîtrisé", en: "Under control" } },
            { key: "ongoing", label: { ar: "مستمر", fr: "En cours", en: "Ongoing" } },
          ],
          required: true,
        },
      ]),
    onSuccess: () => void qc.invalidateQueries({ queryKey: crewKeys.templatesAll }),
  });
  return (
    <form
      className="ops-form"
      aria-label={t("templates.newTitle")}
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate();
      }}
    >
      <h2>{t("templates.newTitle")}</h2>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={ids.category}>{t("templates.category")}</label>
          <select
            id={ids.category}
            value={category}
            onChange={(e) => {
              setCategory(e.target.value as Category);
              setClassification("");
            }}
          >
            {CATEGORIES.filter((c) => c !== "sos").map((c) => (
              <option key={c} value={c}>
                {t(`category.${c}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.classification}>{t("templates.classification")}</label>
          <select id={ids.classification} value={classification} onChange={(e) => setClassification(e.target.value)}>
            <option value="">{t("templates.anyClassification")}</option>
            {classificationsFor(category).map((c) => (
              <option key={c} value={c}>
                {t(`ops.classification.${c}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {t("templates.create")}
        </button>
      </div>
      <MutationError error={mutation.error} />
    </form>
  );
}

/**
 * Phase P4b (F-STF-05, design-staff §5.7): the detailed-report templates of the team leaders' app. Everyone in the room
 * sees them as on the phone; the Office edits drafts and approves them, which retires the version before.
 */
export function ReportTemplatesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const canEdit = user ? canEditReportTemplates(user.identity) : false;
  const [retired, setRetired] = useState(false);
  const query = useQuery({
    queryKey: crewKeys.templates(retired),
    queryFn: ({ signal }) => api.reportTemplates(retired, signal),
  });
  const items = query.data ?? [];
  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="description" tone="purple">
          {t("templates.pageTitle")}
        </PageTitle>
      </div>
      <p className="muted">{t("templates.intro")}</p>
      {!canEdit && <p className="alert alert--info">{t("templates.readOnly")}</p>}
      <label className="checkbox">
        <input type="checkbox" checked={retired} onChange={(e) => setRetired(e.target.checked)} />
        <span>{t("templates.showRetired")}</span>
      </label>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("templates.none")}</p>}
      {items.map((x) => (
        <TemplateCard key={x.id} template={x} all={items} canEdit={canEdit} />
      ))}
      {canEdit && <NewTemplateForm />}
    </div>
  );
}
