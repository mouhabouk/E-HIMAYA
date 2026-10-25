import { useEffect, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { ConfidenceBadges, SimTag, streamTitle } from "../components/StreamBits";
import { ALERT_CONFIDENCE } from "../lib/detections";
import { useFormat, useGouvernorats } from "../lib/hooks";
import type { StaffStream } from "../lib/streamTypes";
import { useStreamList } from "../lib/streamHooks";
import { GouvernoratFilter, StreamsNav } from "./StreamsPage";
import { PageTitle } from "../components/PageTitle";

export const DETECTION_FILTERS = ["any", "fire_or_smoke", "fire", "smoke", "none"] as const;
export type DetectionFilter = (typeof DETECTION_FILTERS)[number];

export interface ArchiveFilters {
  /** Local calendar dates "YYYY-MM-DD" (inclusive), or "". */
  from: string;
  to: string;
  detection: DetectionFilter;
}

/** A fire or smoke counts when it reached the alert confidence (§3); weaker ones are shown but not "had fire". */
function had(value: number | null): boolean {
  return value !== null && value >= ALERT_CONFIDENCE;
}

const localDay = (date: string, endOfDay: boolean) => {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(y ?? 0, (m ?? 1) - 1, d ?? 1, endOfDay ? 23 : 0, endOfDay ? 59 : 0, endOfDay ? 59 : 0, endOfDay ? 999 : 0).getTime();
};

/** Date and detection filters, applied to the loaded pages (the §4 list filters by status and gouvernorat only). */
export function matchesArchiveFilters(s: StaffStream, f: ArchiveFilters): boolean {
  const started = Date.parse(s.started_at ?? s.ended_at ?? "");
  if (f.from && !(started >= localDay(f.from, false))) return false;
  if (f.to && !(started <= localDay(f.to, true))) return false;
  const fire = had(s.max_fire_confidence);
  const smoke = had(s.max_smoke_confidence);
  switch (f.detection) {
    case "fire":
      return fire;
    case "smoke":
      return smoke;
    case "fire_or_smoke":
      return fire || smoke;
    case "none":
      return !fire && !smoke;
    default:
      return true;
  }
}

/** Keep loading pages while the client-side filters leave the screen nearly empty. */
const TARGET_ROWS = 20;
const MAX_AUTO_PAGES = 10;

/** Ended streams, newest first, with their recordings and detections. */
export function StreamArchivePage() {
  const { t } = useTranslation();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const ids = { from: useId(), to: useId(), detection: useId() };
  const [gouvernorat, setGouvernorat] = useState<number | null>(null);
  const [filters, setFilters] = useState<ArchiveFilters>({ from: "", to: "", detection: "any" });
  const query = useStreamList({ status: "ended", gouvernorat });
  const all = useMemo(() => query.data?.pages.flatMap((p) => p.items) ?? [], [query.data]);
  const items = useMemo(() => all.filter((s) => matchesArchiveFilters(s, filters)), [all, filters]);
  const pages = query.data?.pages.length ?? 0;

  // Newest first: once the oldest loaded stream started before `from`, further pages cannot match.
  const oldest = all.at(-1)?.started_at ?? null;
  const pastFrom = Boolean(filters.from && oldest && Date.parse(oldest) < localDay(filters.from, false));
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = query;
  useEffect(() => {
    if (items.length < TARGET_ROWS && hasNextPage && !isFetchingNextPage && !pastFrom && pages < MAX_AUTO_PAGES) {
      void fetchNextPage();
    }
  }, [items.length, hasNextPage, isFetchingNextPage, pastFrom, pages, fetchNextPage]);

  const set = (patch: Partial<ArchiveFilters>) => setFilters((f) => ({ ...f, ...patch }));

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="videocam" tone="red">{t("streams.archive.title")}</PageTitle>
        <StreamsNav />
      </div>
      <form className="filters card" onSubmit={(e) => e.preventDefault()} aria-label={t("streams.archive.filters")}>
        <div className="filters__row">
          <div className="field">
            <label htmlFor={ids.from}>{t("streams.archive.from")}</label>
            <input id={ids.from} type="date" value={filters.from} max={filters.to || undefined} onChange={(e) => set({ from: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor={ids.to}>{t("streams.archive.to")}</label>
            <input id={ids.to} type="date" value={filters.to} min={filters.from || undefined} onChange={(e) => set({ to: e.target.value })} />
          </div>
          <GouvernoratFilter value={gouvernorat} onChange={setGouvernorat} />
          <div className="field">
            <label htmlFor={ids.detection}>{t("streams.archive.detection")}</label>
            <select
              id={ids.detection}
              value={filters.detection}
              onChange={(e) => set({ detection: e.target.value as DetectionFilter })}
            >
              {DETECTION_FILTERS.map((d) => (
                <option key={d} value={d}>
                  {t(`streams.archive.detectionOption.${d}`)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <p className="muted">{t("streams.archive.filtersNote")}</p>
      </form>

      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      <p className="visually-hidden" role="status" aria-live="polite">
        {query.isSuccess ? t("streams.archive.count", { count: items.length }) : ""}
      </p>
      {query.isSuccess && items.length === 0 && !query.isFetchingNextPage && (
        <p className="card empty">{t("streams.archive.empty")}</p>
      )}
      {items.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <caption className="visually-hidden">{t("streams.archive.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("streams.columns.started")}</th>
                <th scope="col">{t("streams.columns.stream")}</th>
                <th scope="col">{t("streams.columns.source")}</th>
                <th scope="col">{t("streams.columns.gouvernorat")}</th>
                <th scope="col" className="num">
                  {t("streams.columns.duration")}
                </th>
                <th scope="col">{t("streams.columns.detections")}</th>
                <th scope="col" className="num">
                  {t("streams.columns.recordings")}
                </th>
                <th scope="col">{t("streams.columns.report")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id} className={s.simulated ? "row--sim" : undefined}>
                  <td>{s.started_at ? <time dateTime={s.started_at}>{fmt.dateTime(s.started_at)}</time> : "—"}</td>
                  <td>
                    <Link to={`/streams/${encodeURIComponent(s.id)}`} dir="auto">
                      {streamTitle(t, s)}
                    </Link>
                    {s.simulated && <SimTag />}
                  </td>
                  <td>{t(`streams.source.${s.source}`)}</td>
                  <td>{gouvernorats.nameOf(s.gouvernorat_code) ?? t("common.notAvailable")}</td>
                  <td className="num">{s.duration_s === null ? "—" : fmt.duration(s.duration_s)}</td>
                  <td>
                    <ConfidenceBadges stream={s} />
                  </td>
                  <td className="num">{fmt.number(s.recordings_count)}</td>
                  <td>
                    {s.report_id ? (
                      <Link
                        to={`/reports/${encodeURIComponent(s.report_id)}`}
                        aria-label={t("streams.archive.reportLabel", { code: s.tracking_code ?? "" })}
                      >
                        {t("streams.detail.openReport")}
                      </Link>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && !pastFrom && (
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
