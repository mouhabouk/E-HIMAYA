import type { UseMutationResult } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ConfirmDialog } from "../../components/Dialog";
import { ErrorBox } from "../../components/Feedback";

/** Table row actions: edit and delete with confirmation (hidden when the role cannot write). */
export function RowActions({
  name,
  editable,
  onEdit,
  remove,
  id,
}: {
  name: string;
  editable: boolean;
  onEdit: () => void;
  remove: UseMutationResult<undefined, Error, string>;
  id: string;
}) {
  const { t } = useTranslation();
  const [confirm, setConfirm] = useState(false);
  if (!editable) return null;
  return (
    <span className="row-actions">
      <button type="button" className="btn btn--small" onClick={onEdit} aria-label={t("common.editNamed", { name })}>
        {t("common.edit")}
      </button>
      <button type="button" className="btn btn--small btn--danger-ghost" onClick={() => setConfirm(true)} aria-label={t("common.deleteNamed", { name })}>
        {t("common.delete")}
      </button>
      {confirm && (
        <ConfirmDialog
          title={t("common.confirmDeleteTitle")}
          body={t("common.confirmDelete", { name })}
          confirmLabel={t("common.delete")}
          danger
          busy={remove.isPending}
          onClose={() => {
            remove.reset();
            setConfirm(false);
          }}
          onConfirm={() => remove.mutate(id, { onSuccess: () => setConfirm(false) })}
        >
          {remove.isError && <ErrorBox error={remove.error} />}
        </ConfirmDialog>
      )}
    </span>
  );
}

/** "Fields marked * are required." at the top of a form with required fields (phase A, rule 2). */
export function RequiredNote() {
  const { t } = useTranslation();
  return <p className="field__hint required-note">{t("validation.requiredNote")}</p>;
}

/** Labelled input/select wrapper with optional hint and error (ids derived from `id`). */
export function Field({
  id,
  label,
  error,
  hint,
  required = false,
  children,
}: {
  id: string;
  label: string;
  error?: string | null;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={`field${error ? " field--invalid" : ""}`}>
      <label htmlFor={id}>
        {label}
        {required && <span className="required-mark" aria-hidden="true"> *</span>}
      </label>
      {children}
      {hint && (
        <span id={`${id}-hint`} className="field__hint">
          {hint}
        </span>
      )}
      {error && (
        <span id={`${id}-error`} className="field__error">
          {error}
        </span>
      )}
    </div>
  );
}

export function describedBy(id: string, hint?: unknown, error?: unknown): string | undefined {
  return [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;
}
