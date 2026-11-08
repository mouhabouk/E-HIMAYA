import { useInfiniteQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useServices } from "../../context/services";
import { useFormat } from "../../lib/hooks";
import { queryKeys, type OrgChange, type OrgChangeFilters } from "../../lib/portalApi";
import { useOrg } from "./OrgWorkspace";

const OPS = ["I", "U", "D"] as const;
const TABLES = [
  "organization",
  "member",
  "invitation",
  "team_member",
  "document",
  "document_version",
  "equipment",
  "maintenance",
  "hazmat",
  "map_feature",
  "activity",
  "certificate",
  "prevention_visit",
  "prevention_reservation",
  "prealert",
] as const;

function show(v: unknown): string {
  if (v === null || v === undefined) return "∅";
  return typeof v === "string" ? v : JSON.stringify(v);
}

function Row({ change }: { change: OrgChange }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const hidden = new Set(change.hidden);
  return (
    <tr>
      <td>
        <time dateTime={change.at}>{fmt.dateTime(change.at)}</time>
      </td>
      <td>
        <span className={`change-op change-op--${change.op}`}>{t(`changes.ops.${change.op}`)}</span>
      </td>
      <td>{t(`changes.tables.${change.table_name}`, { defaultValue: change.table_name })}</td>
      <td>
        {change.by === "member" ? (change.by_name ?? t("changes.aMember")) : t(`changes.byKinds.${change.by}`)}
      </td>
      <td>
        <ul className="change-columns" role="list">
          {change.columns.map((c) => (
            <li key={c}>
              <span className="change-columns__name">
                {t(`changes.columns.${c}`, { defaultValue: c })}
              </span>
              {hidden.has(c) ? (
                <span className="muted">{t("changes.notKept")}</span>
              ) : (
                <span dir="ltr">
                  {change.op !== "I" && <del>{show(change.old_values?.[c])}</del>}
                  {change.op === "U" && " → "}
                  {change.op !== "D" && <ins>{show(change.new_values?.[c])}</ins>}
                </span>
              )}
            </li>
          ))}
        </ul>
      </td>
    </tr>
  );
}

/**
 * The institution's change journal (Yamen, 2026-11-08): every addition, update and deletion to its records, who made
 * it (a member by name, the civil protection or the platform), and what changed. Administrators only; values that
 * may be personal (names, phones, addresses, notes) are never kept, only the fact that they changed.
 */
export function ChangesTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { org } = useOrg();
  const base = useId();
  const [filters, setFilters] = useState<OrgChangeFilters>({ table: "", op: "", from: "", to: "" });
  const query = useInfiniteQuery({
    queryKey: queryKeys.changes(org.id, filters),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.orgChanges(org.id, filters, pageParam, signal),
    getNextPageParam: (last) => last.next_cursor,
    enabled: org.my_role === "admin",
  });
  if (org.my_role !== "admin") return <p className="muted">{t("changes.adminsOnly")}</p>;
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  const set = (k: keyof OrgChangeFilters) => (e: { target: { value: string } }) =>
    setFilters((f) => ({ ...f, [k]: e.target.value }));

  return (
    <section className="card" aria-labelledby={`${base}-title`}>
      <h2 id={`${base}-title`}>{t("changes.title")}</h2>
      <p className="muted">{t("changes.intro")}</p>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${base}-table`}>{t("changes.section")}</label>
          <select id={`${base}-table`} value={filters.table} onChange={set("table")}>
            <option value="">{t("changes.all")}</option>
            {TABLES.map((n) => (
              <option key={n} value={n}>
                {t(`changes.tables.${n}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${base}-op`}>{t("changes.op")}</label>
          <select id={`${base}-op`} value={filters.op} onChange={set("op")}>
            <option value="">{t("changes.all")}</option>
            {OPS.map((op) => (
              <option key={op} value={op}>
                {t(`changes.ops.${op}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${base}-from`}>{t("changes.from")}</label>
          <input id={`${base}-from`} type="date" value={filters.from} onChange={set("from")} />
        </div>
        <div className="field">
          <label htmlFor={`${base}-to`}>{t("changes.to")}</label>
          <input id={`${base}-to`} type="date" value={filters.to} onChange={set("to")} />
        </div>
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("changes.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("changes.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("changes.at")}</th>
                <th scope="col">{t("changes.op")}</th>
                <th scope="col">{t("changes.section")}</th>
                <th scope="col">{t("changes.by")}</th>
                <th scope="col">{t("changes.what")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <Row key={c.id} change={c} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && (
        <button type="button" className="btn" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
          {t("changes.more")}
        </button>
      )}
    </section>
  );
}
