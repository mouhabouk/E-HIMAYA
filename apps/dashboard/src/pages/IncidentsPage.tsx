import { useInfiniteQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { IncidentStatusChip, PriorityBadge } from "../components/AiBadges";
import { CategoryLabel } from "../components/CategoryIcon";
import { ErrorBox, Loading } from "../components/Feedback";
import { LevelTag } from "../components/OperationsPanel";
import { useServices } from "../context/services";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { queryKeys, type IncidentStatusFilter } from "../lib/staffApi";
import { INCIDENT_STATUSES } from "../lib/types";

const STATUS_FILTERS: readonly IncidentStatusFilter[] = [...INCIDENT_STATUSES, "all"];

function StatusFilter({
  value,
  onChange,
}: {
  value: IncidentStatusFilter;
  onChange: (s: IncidentStatusFilter) => void;
}) {
  const { t } = useTranslation();
  const name = useId();
  return (
    <fieldset className="segmented">
      <legend>{t("incidents.statusFilter")}</legend>
      {STATUS_FILTERS.map((s) => (
        <label key={s} className="segmented__item">
          <input type="radio" name={name} value={s} checked={value === s} onChange={() => onChange(s)} />
          <span>{t(`incidents.status.${s}`)}</span>
        </label>
      ))}
    </fieldset>
  );
}

/** FR-C-02 (incidents): groups of reports in the user's scope, newest activity first, updated live. */
export function IncidentsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const [status, setStatus] = useState<IncidentStatusFilter>("open");

  const query = useInfiniteQuery({
    queryKey: queryKeys.incidents(status),
    queryFn: ({ pageParam, signal }) => api.incidents({ status, cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });

  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("incidents.title")}</h1>
        <StatusFilter value={status} onChange={setStatus} />
      </div>
      <p className="muted">{t("incidents.intro")}</p>

      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="card empty">{t("incidents.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <caption className="visually-hidden">{t("incidents.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("incidents.columns.severity")}</th>
                <th scope="col">{t("incidents.columns.category")}</th>
                <th scope="col">{t("incidents.columns.status")}</th>
                <th scope="col">{t("incidents.columns.gouvernorat")}</th>
                <th scope="col" className="num">
                  {t("incidents.columns.reports")}
                </th>
                <th scope="col" className="num">
                  {t("incidents.columns.reporters")}
                </th>
                <th scope="col">{t("ops.list.operations")}</th>
                <th scope="col">{t("incidents.columns.updatedAt")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id}>
                  <td>
                    <PriorityBadge score={i.severity} />
                  </td>
                  <td>
                    <Link
                      to={`/incidents/${encodeURIComponent(i.id)}`}
                      aria-label={t("incidents.openLabel", {
                        category: t(`category.${i.category}`),
                        date: fmt.dateTime(i.opened_at),
                      })}
                    >
                      <CategoryLabel category={i.category} />
                    </Link>
                    {i.title && (
                      <div className="cell-sub" dir="auto">
                        {i.title}
                      </div>
                    )}
                    {i.op_level && i.op_level !== "normal" && <LevelTag level={i.op_level} />}
                  </td>
                  <td>
                    <IncidentStatusChip status={i.status} />
                  </td>
                  <td>{gouvernorats.nameOf(i.gouvernorat_code) ?? t("common.notAvailable")}</td>
                  <td className="num">{fmt.number(i.report_count)}</td>
                  <td className="num">{fmt.number(i.reporter_count)}</td>
                  <td>
                    {(i.assignments_active ?? 0) === 0 && (i.callouts_open ?? 0) === 0 ? (
                      <span className="muted">—</span>
                    ) : (
                      <span>
                        {t("ops.list.assignments", { count: i.assignments_active ?? 0 })}
                        {(i.callouts_open ?? 0) > 0 && ` · ${t("ops.list.callouts", { count: i.callouts_open ?? 0 })}`}
                      </span>
                    )}
                  </td>
                  <td>
                    <time dateTime={i.updated_at}>{fmt.dateTime(i.updated_at)}</time>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && (
        <div className="load-more">
          <button
            type="button"
            className="btn"
            onClick={() => void query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
            aria-busy={query.isFetchingNextPage}
          >
            {query.isFetchingNextPage ? t("common.loading") : t("reports.loadMore")}
          </button>
        </div>
      )}
      {query.isFetchNextPageError && <ErrorBox error={query.error} />}
    </div>
  );
}
