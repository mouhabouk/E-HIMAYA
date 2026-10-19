import { useInfiniteQuery } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { CategoryLabel } from "../components/CategoryIcon";
import { ErrorBox, Loading } from "../components/Feedback";
import { FiltersBar } from "../components/FiltersBar";
import { StatusChip } from "../components/StatusChip";
import { useLiveEvents } from "../context/live";
import { useServices } from "../context/services";
import { matchesFilters } from "../lib/filters";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { listKey } from "../lib/liveCache";
import { useEffectiveFilters } from "./useEffectiveFilters";

/** FR-C-02 (list): incidents in the user's scope, newest first, with live insertion. */
export function ReportsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const { filters, national } = useEffectiveFilters();
  const [fresh, setFresh] = useState<ReadonlySet<string>>(new Set());
  const [unread, setUnread] = useState(0);
  const topRef = useRef<HTMLHeadingElement>(null);

  const query = useInfiniteQuery({
    queryKey: listKey(filters),
    queryFn: ({ pageParam, signal }) => api.reports(filters, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });

  useLiveEvents(
    useCallback(
      (event) => {
        if (event.type !== "report.created" || !matchesFilters(event.report, filters)) return;
        const id = event.report.id;
        setFresh((prev) => new Set(prev).add(id));
        setUnread((n) => n + 1);
      },
      [filters],
    ),
  );

  const acknowledge = () => {
    setUnread(0);
    topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    topRef.current?.focus();
  };

  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="page">
      <div className="page__head">
        <h1 ref={topRef} tabIndex={-1}>
          {t("reports.title")}
        </h1>
        {unread > 0 && (
          <button type="button" className="btn btn--primary new-badge" onClick={acknowledge}>
            {t("reports.newCount", { count: unread })}
          </button>
        )}
      </div>
      <div className="visually-hidden" aria-live="polite">
        {unread > 0 ? t("reports.newCount", { count: unread }) : ""}
      </div>
      <FiltersBar showGouvernorat={national} />

      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="card empty">{t("reports.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <caption className="visually-hidden">{t("reports.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("reports.columns.receivedAt")}</th>
                <th scope="col">{t("reports.columns.trackingCode")}</th>
                <th scope="col">{t("reports.columns.category")}</th>
                <th scope="col">{t("reports.columns.reporter")}</th>
                <th scope="col">{t("reports.columns.gouvernorat")}</th>
                <th scope="col">{t("reports.columns.status")}</th>
                <th scope="col" className="num">
                  {t("reports.columns.media")}
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id} className={fresh.has(r.id) ? "row--new" : undefined}>
                  <td>
                    <time dateTime={r.received_at}>{fmt.dateTime(r.received_at)}</time>
                  </td>
                  <td>
                    <Link to={`/reports/${encodeURIComponent(r.id)}`} className="code" dir="ltr">
                      {r.tracking_code}
                    </Link>
                    {fresh.has(r.id) && <span className="tag tag--new">{t("reports.newBadge")}</span>}
                  </td>
                  <td>
                    <CategoryLabel category={r.category} />
                  </td>
                  <td>{t(`reporterKind.${r.reporter_kind}`)}</td>
                  <td>{gouvernorats.nameOf(r.gouvernorat_code) ?? t("common.notAvailable")}</td>
                  <td>
                    <StatusChip status={r.status} />
                  </td>
                  <td className="num">{fmt.number(r.media_count)}</td>
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
