// covers: the operator's confirmation of a final report's reading for the self-learning (docs/learning.md §2): the
// category, lives at risk and whether it was rightly rejected. A confirmed label weighs more than the system's own.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import {
  learningKeys,
  type LearningLabel,
  type LearningLabelIn,
} from "../lib/learning";
import { canLabelForLearning } from "../lib/roles";
import {
  CATEGORIES,
  type Category,
  type StaffReportDetail,
} from "../lib/types";

function YesNo({
  name,
  legend,
  value,
  onChange,
}: {
  name: string;
  legend: string;
  value: boolean | null;
  onChange: (v: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <fieldset className="segmented segmented--small">
      <legend>{legend}</legend>
      {([true, false] as const).map((v) => (
        <label key={String(v)} className="segmented__item">
          <input
            type="radio"
            name={name}
            checked={value === v}
            onChange={() => onChange(v)}
          />
          <span>{v ? t("common.yes") : t("common.no")}</span>
        </label>
      ))}
    </fieldset>
  );
}

function Form({
  report,
  label,
}: {
  report: StaffReportDetail;
  label: LearningLabel;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [form, setForm] = useState<LearningLabelIn>({
    category: label.category ?? report.category,
    lives_at_risk: label.lives_at_risk,
    rejected: label.rejected,
  });
  const save = useMutation({
    mutationFn: (body: LearningLabelIn) =>
      api.saveLearningLabel(report.id, body),
    onSuccess: (saved) => qc.setQueryData(learningKeys.label(report.id), saved),
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const body: LearningLabelIn = {};
    if (form.category) body.category = form.category;
    if (form.lives_at_risk !== null && form.lives_at_risk !== undefined)
      body.lives_at_risk = form.lives_at_risk;
    if (form.rejected !== null && form.rejected !== undefined)
      body.rejected = form.rejected;
    save.mutate(body);
  };
  const confirmed = label.confirmed.length > 0;
  return (
    <form className="learning-label" onSubmit={submit}>
      <p className="muted">{t("learning.label.help")}</p>
      <div className="field">
        <label htmlFor={`${id}-cat`}>{t("learning.label.category")}</label>
        <select
          id={`${id}-cat`}
          value={form.category ?? ""}
          onChange={(e) =>
            setForm((f) => ({ ...f, category: e.target.value as Category }))
          }
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {t(`category.${c}`)}
            </option>
          ))}
        </select>
      </div>
      <YesNo
        name={`${id}-lives`}
        legend={t("learning.label.lives")}
        value={form.lives_at_risk ?? null}
        onChange={(v) => setForm((f) => ({ ...f, lives_at_risk: v }))}
      />
      <YesNo
        name={`${id}-rej`}
        legend={t("learning.label.rejected")}
        value={form.rejected ?? null}
        onChange={(v) => setForm((f) => ({ ...f, rejected: v }))}
      />
      <div className="actions">
        <button
          type="submit"
          className="btn btn--primary btn--small"
          disabled={save.isPending}
        >
          {t("learning.label.save")}
        </button>
        {confirmed && (
          <span className="pill tone-green">
            {t("learning.label.confirmed")}
          </span>
        )}
      </div>
      {save.error ? (
        <p role="alert" className="field__error">
          {t(errorMessageKey(save.error))}
        </p>
      ) : null}
    </form>
  );
}

/** Shown on a closed or rejected report to whoever may change its status. */
export function LearningLabelSection({
  report,
}: {
  report: StaffReportDetail;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const final = report.status === "closed" || report.status === "rejected";
  const allowed =
    final && user !== null && canLabelForLearning(user.identity.roles);
  const query = useQuery({
    queryKey: learningKeys.label(report.id),
    queryFn: ({ signal }) => api.learningLabel(report.id, signal),
    enabled: allowed,
    retry: false,
  });
  if (!allowed) return null;
  return (
    <section className="card" aria-labelledby="sec-learning">
      <h2 id="sec-learning">{t("learning.label.title")}</h2>
      {query.data ? (
        <Form report={report} label={query.data} />
      ) : query.isError ? (
        <p className="muted">{t(errorMessageKey(query.error))}</p>
      ) : null}
    </section>
  );
}
