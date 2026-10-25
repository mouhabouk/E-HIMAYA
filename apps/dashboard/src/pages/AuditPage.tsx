import { useInfiniteQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useDebounced, useFormat, useGouvernorats } from "../lib/hooks";
import { p9Keys } from "../lib/phase9Api";
import type { AuditFilters, ScopedAuditEntry } from "../lib/phase9Types";
import { PageTitle } from "../components/PageTitle";

/** Whitelisted details of a redacted entry, as "key: value" pairs (ids, from, to, status, outcome, kind). */
function detailsText(details: Record<string, unknown>): string {
  return Object.entries(details)
    .filter(([, v]) => v !== null && v !== undefined && (typeof v === "string" || typeof v === "number" || typeof v === "boolean"))
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join(" · ");
}

function EntryRow({ entry }: { entry: ScopedAuditEntry }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <tr>
      <td>
        <time dateTime={entry.at}>{fmt.dateTime(entry.at)}</time>
      </td>
      <td dir="ltr" className="code">
        {entry.action}
      </td>
      <td dir="auto">
        {entry.actor_name === "system" ? t("audit.system") : (entry.actor_name ?? t("common.notAvailable"))}
      </td>
      <td dir="ltr" className="code">
        {entry.target ?? "—"}
      </td>
      <td dir="ltr" className="code">
        {detailsText(entry.details) || "—"}
      </td>
      <td dir="auto">{entry.reason ?? "—"}</td>
    </tr>
  );
}

/**
 * Scoped, redacted audit of the user's gouvernorat (phase 9 §7.3): entries tagged with the gouvernorat only, the
 * actor as a display name, details reduced by the API to a whitelist, no hash. Reading it is itself audited.
 */
export function AuditPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const base = useId();
  const [filters, setFilters] = useState<AuditFilters>({ action: "", from: "", to: "" });
  const action = useDebounced(filters.action ?? "", 300);
  const effective = { ...filters, action };
  const query = useInfiniteQuery({
    queryKey: p9Keys.audit(effective),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.scopedAudit(effective, { cursor: pageParam, signal }),
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  const set = (k: keyof AuditFilters) => (e: { target: { value: string } }) => setFilters((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="policy" tone="slate">{t("audit.title")}</PageTitle>
      </div>
      <p className="muted">{t("audit.intro", { name: gouvernorats.nameOf(user?.identity.gouvernoratCode) ?? "" })}</p>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${base}-action`}>{t("audit.action")}</label>
          <input id={`${base}-action`} dir="ltr" value={filters.action ?? ""} placeholder="report.claim" onChange={set("action")} />
        </div>
        <div className="field">
          <label htmlFor={`${base}-from`}>{t("analytics.from")}</label>
          <input id={`${base}-from`} type="date" value={filters.from ?? ""} onChange={set("from")} />
        </div>
        <div className="field">
          <label htmlFor={`${base}-to`}>{t("analytics.to")}</label>
          <input id={`${base}-to`} type="date" value={filters.to ?? ""} onChange={set("to")} />
        </div>
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("audit.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("audit.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("audit.at")}</th>
                <th scope="col">{t("audit.action")}</th>
                <th scope="col">{t("audit.actor")}</th>
                <th scope="col">{t("audit.target")}</th>
                <th scope="col">{t("audit.details")}</th>
                <th scope="col">{t("audit.reason")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e, i) => (
                <EntryRow key={e.seq ?? `${e.at}-${i}`} entry={e} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && (
        <button type="button" className="btn" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
          {t("reports.loadMore")}
        </button>
      )}
    </div>
  );
}
