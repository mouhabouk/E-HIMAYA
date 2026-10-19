import { useInfiniteQuery } from "@tanstack/react-query";
import { useCallback, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { PriorityBadge, ReportMarkers } from "../components/AiBadges";
import { AiStatusBanner } from "../components/AiStatusBanner";
import { CategoryLabel } from "../components/CategoryIcon";
import { ErrorBox, Loading } from "../components/Feedback";
import { FiltersBar } from "../components/FiltersBar";
import { StatusChip } from "../components/StatusChip";
import { useLiveEvents } from "../context/live";
import { useServices } from "../context/services";
import { matchesFilters } from "../lib/filters";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { listKey } from "../lib/liveCache";
import type { ReportSort } from "../lib/staffApi";
import type { StaffReport } from "../lib/types";
import { useEffectiveFilters } from "./useEffectiveFilters";

const SORTS: readonly ReportSort[] = ["received", "priority"];
const SORT_STORAGE_KEY = "ehimaya.reportsSort";

function storedSort(): ReportSort {
  try {
    return sessionStorage.getItem(SORT_STORAGE_KEY) === "priority" ? "priority" : "received";
  } catch {
    return "received";
  }
}

function SortToggle({ value, onChange }: { value: ReportSort; onChange: (s: ReportSort) => void }) {
  const { t } = useTranslation();
  const name = useId();
  return (
    <fieldset className="segmented">
      <legend>{t("reports.sort.label")}</legend>
      {SORTS.map((s) => (
        <label key={s} className="segmented__item">
          <input type="radio" name={name} value={s} checked={value === s} onChange={() => onChange(s)} />
          <span>{t(`reports.sort.${s}`)}</span>
        </label>
      ))}
    </fieldset>
  );
}

/** Original text, and its Arabic translation (FR-A-045) labelled as such. */
function TextCell({ report }: { report: StaffReport }) {
  const { t } = useTranslation();
  if (!report.text) return <span className="muted">{t("common.notAvailable")}</span>;
  return (
    <div className="text-cell">
      <p className="clamp" lang={report.lang ?? undefined} dir="auto">
        {report.text}
      </p>
      {report.text_ar && (
        <p className="clamp text-cell__translation" lang="ar" dir="rtl">
          <span className="tag tag--translation">{t("ai.translationShort")}</span> {report.text_ar}
        </p>
      )}
    </div>
  );
}

/** FR-C-02 (list): reports in the user's scope, newest or highest priority first, with live insertion. */
export function ReportsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const { filters, national } = useEffectiveFilters();
  const [fresh, setFresh] = useState<ReadonlySet<string>>(new Set());
  const [unread, setUnread] = useState(0);
  const [sort, setSortState] = useState<ReportSort>(storedSort);
  const topRef = useRef<HTMLHeadingElement>(null);

  const setSort = (next: ReportSort) => {
    setSortState(next);
    try {
      sessionStorage.setItem(SORT_STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  };

  const query = useInfiniteQuery({
    queryKey: listKey(filters, sort),
    queryFn: ({ pageParam, signal }) => api.reports(filters, { cursor: pageParam, signal, sort }),
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
      <AiStatusBanner />
      <FiltersBar showGouvernorat={national} />
      <div className="list-tools">
        <SortToggle value={sort} onChange={setSort} />
      </div>

      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="card empty">{t("reports.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <caption className="visually-hidden">
              {sort === "priority" ? t("reports.captionPriority") : t("reports.caption")}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t("reports.columns.priority")}</th>
                <th scope="col">{t("reports.columns.receivedAt")}</th>
                <th scope="col">{t("reports.columns.trackingCode")}</th>
                <th scope="col">{t("reports.columns.category")}</th>
                <th scope="col">{t("reports.columns.text")}</th>
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
                    <PriorityBadge score={r.priority_score} />
                  </td>
                  <td>
                    <time dateTime={r.received_at}>{fmt.dateTime(r.received_at)}</time>
                  </td>
                  <td>
                    <Link to={`/reports/${encodeURIComponent(r.id)}`} className="code" dir="ltr">
                      {r.tracking_code}
                    </Link>
                    {fresh.has(r.id) && <span className="tag tag--new">{t("reports.newBadge")}</span>}
                    <ReportMarkers report={r} />
                  </td>
                  <td>
                    <CategoryLabel category={r.category} />
                  </td>
                  <td>
                    <TextCell report={r} />
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
