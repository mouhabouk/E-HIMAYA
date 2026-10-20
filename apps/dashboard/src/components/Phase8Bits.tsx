/** Small pieces shared by the phase 8 screens (analytics, reports library, memory, events library, rewards). */
import { useId, useMemo, useState, type ReactNode, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";
import { errorMessageKey } from "../lib/api";
import { useGouvernorats } from "../lib/hooks";
import { excerptParts, renderMarkdown } from "../lib/markdown";
import { CATEGORIES } from "../lib/types";
import { directionOf, type Language } from "../i18n";

/** Tabs of one area, as links (the current one marked with aria-current by NavLink). */
export function AreaTabs({ label, tabs }: { label: string; tabs: { to: string; label: string; end?: boolean }[] }) {
  return (
    <nav className="tabs" aria-label={label}>
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) => `tabs__tab${isActive ? " tabs__tab--active" : ""}`}
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}

/**
 * Markdown of the national memory, sanitized (lib/markdown.ts: raw HTML escaped, DOMPurify allowlist). This is the
 * only place the phase 8 screens set HTML.
 */
export function Markdown({ source, lang, className }: { source: string; lang?: Language; className?: string }) {
  const html = useMemo(() => renderMarkdown(source), [source]);
  return (
    <div
      className={`markdown${className ? ` ${className}` : ""}`}
      lang={lang}
      dir={lang ? directionOf(lang) : "auto"}
      // Sanitized above: markdown-it with html disabled, then DOMPurify with a tag allowlist.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/** A search excerpt with its `<mark>` highlights, rendered as text (never as HTML). */
export function Excerpt({ text }: { text: string }) {
  const parts = useMemo(() => excerptParts(text), [text]);
  return (
    <p className="excerpt" dir="auto">
      {parts.map((p, i) => (p.marked ? <mark key={i}>{p.text}</mark> : <span key={i}>{p.text}</span>))}
    </p>
  );
}

export function GouvernoratSelect({
  value,
  onChange,
  label,
  allLabel,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  label: string;
  allLabel: string;
}) {
  const id = useId();
  const gouvernorats = useGouvernorats();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">{allLabel}</option>
        {gouvernorats.list.map((g) => (
          <option key={g.code} value={g.code}>
            {gouvernorats.nameOf(g.code)}
          </option>
        ))}
      </select>
    </div>
  );
}

export function CategorySelect({
  value,
  onChange,
  label,
  allLabel,
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  label: string;
  allLabel?: string;
}) {
  const { t } = useTranslation();
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}>
        {allLabel !== undefined && <option value="">{allLabel}</option>}
        {CATEGORIES.map((c) => (
          <option key={c} value={c}>
            {t(`category.${c}`)}
          </option>
        ))}
      </select>
    </div>
  );
}

export function LoadMore({
  hasNext,
  loading,
  onMore,
}: {
  hasNext: boolean;
  loading: boolean;
  onMore: () => void;
}) {
  const { t } = useTranslation();
  if (!hasNext) return null;
  return (
    <div className="load-more">
      <button type="button" className="btn" onClick={onMore} disabled={loading} aria-busy={loading}>
        {loading ? t("common.loading") : t("reports.loadMore")}
      </button>
    </div>
  );
}

/** An inline "why?" form for decisions that need a reason (reject, revoke, request changes, archive). */
export function ReasonForm({
  label,
  submitLabel,
  required = true,
  pending,
  error,
  onSubmit,
  onCancel,
  minLength = 3,
}: {
  label: string;
  submitLabel: string;
  required?: boolean;
  pending: boolean;
  error: unknown;
  onSubmit: (reason: string) => void;
  onCancel: () => void;
  minLength?: number;
}) {
  const { t } = useTranslation();
  const id = useId();
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const invalid = required && reason.trim().length < minLength;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!invalid) onSubmit(reason.trim());
  };
  return (
    <form className="ops-form reason-form" onSubmit={submit} noValidate>
      <div className={`field${touched && invalid ? " field--invalid" : ""}`}>
        <label htmlFor={id}>{label}</label>
        <textarea
          id={id}
          rows={2}
          maxLength={1000}
          dir="auto"
          value={reason}
          aria-invalid={touched && invalid ? true : undefined}
          aria-describedby={touched && invalid ? `${id}-error` : undefined}
          onChange={(e) => setReason(e.target.value)}
        />
        {touched && invalid && (
          <p id={`${id}-error`} className="field__error">
            {t("p8.reasonRequired")}
          </p>
        )}
      </div>
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={pending}>
          {pending ? t("ops.working") : submitLabel}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          {t("common.cancel")}
        </button>
      </div>
      {error !== null && error !== undefined && <MutationError error={error} />}
    </form>
  );
}

export function MutationError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  return (
    <p className="alert alert--error" role="alert">
      {t(errorMessageKey(error))}
    </p>
  );
}

/** A labelled read-only value (cards of settings). */
export function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="kpi">
      <dt className="kpi__label">{label}</dt>
      <dd className="kpi__value">{children}</dd>
    </div>
  );
}
