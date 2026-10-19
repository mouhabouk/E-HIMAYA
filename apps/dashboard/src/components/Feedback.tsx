import { useTranslation } from "react-i18next";
import { errorMessageKey } from "../lib/api";

export function Loading({ label }: { label?: string }) {
  const { t } = useTranslation();
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label ?? t("common.loading")}</span>
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="alert alert--error" role="alert">
      <p>{t(errorMessageKey(error))}</p>
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}
