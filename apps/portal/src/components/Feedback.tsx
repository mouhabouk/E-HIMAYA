import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { errorMessageKey } from "../lib/api";
import { isTusError } from "../lib/tus";

export function Loading({ label }: { label?: string }) {
  const { t } = useTranslation();
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label ?? t("common.loading")}</span>
    </div>
  );
}

/** i18n key for any thrown value, including tus upload errors. */
export function messageKey(error: unknown): string {
  if (isTusError(error)) return `errors.${error.code}`;
  return errorMessageKey(error);
}

export function ErrorBox({ error, onRetry, children }: { error: unknown; onRetry?: () => void; children?: ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="alert alert--error" role="alert">
      <p>{t(messageKey(error))}</p>
      {children}
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "ok" | "error"; children: ReactNode }) {
  return <div className={`alert alert--${tone}`}>{children}</div>;
}

/** Arrow that points "forward" in reading order (mirrored in RTL by CSS). */
export function ForwardIcon() {
  return (
    <svg className="icon icon--directional" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
      <path fill="currentColor" d="M13.2 5.3 19.9 12l-6.7 6.7-1.4-1.4 4.3-4.3H4v-2h12.1l-4.3-4.3z" />
    </svg>
  );
}

export function BackIcon() {
  return (
    <svg className="icon icon--directional" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
      <path fill="currentColor" d="M10.8 5.3 4.1 12l6.7 6.7 1.4-1.4L7.9 13H20v-2H7.9l4.3-4.3z" />
    </svg>
  );
}
