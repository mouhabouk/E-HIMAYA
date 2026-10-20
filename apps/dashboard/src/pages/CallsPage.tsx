import { useInfiniteQuery, useMutation } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { SimTag } from "../components/StreamBits";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat } from "../lib/hooks";
import { p7Keys } from "../lib/phase7Api";
import type { RecordingDownload } from "../lib/streamsApi";
import {
  CALL_DIRECTIONS,
  CALL_STATUSES,
  type CallFilters,
  type CallStatus,
  type StaffCall,
} from "../lib/telephonyTypes";

type LinkFilter = "" | "linked" | "unlinked";

function knownOr(t: (k: string, o?: Record<string, unknown>) => string, prefix: string, value: string): string {
  return t(`${prefix}.${value}`, { defaultValue: value });
}

function callDuration(c: StaffCall): number | null {
  if (!c.answered_at || !c.ended_at) return null;
  return Math.max(0, (Date.parse(c.ended_at) - Date.parse(c.answered_at)) / 1000);
}

/** Playback (an <audio> on the recording) and download; both go through the audited API endpoint. */
function Recording({ call }: { call: StaffCall }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const [download, setDownload] = useState<RecordingDownload | null>(null);
  const objectUrl = useMemo(() => (download?.kind === "file" ? URL.createObjectURL(download.blob) : null), [download]);
  useEffect(
    () => () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    },
    [objectUrl],
  );
  const fetchIt = useMutation({ mutationFn: () => api.callRecording(call.id), onSuccess: setDownload });
  if (!call.recording_media_id) return <span className="muted">—</span>;
  const src = download ? (download.kind === "link" ? download.url : objectUrl) : null;
  return (
    <div className="call-recording">
      {src ? (
        <>
          <audio controls src={src} aria-label={t("calls.recordingOf", { time: fmt.dateTime(call.started_at) })} />
          <a className="btn btn--small" href={src} download={`call-${call.id}.wav`}>
            {t("calls.download")}
          </a>
        </>
      ) : (
        <button type="button" className="btn btn--small" disabled={fetchIt.isPending} onClick={() => fetchIt.mutate()}>
          {fetchIt.isPending ? t("common.loading") : t("calls.listen")}
        </button>
      )}
      {fetchIt.isError && (
        <span className="field__error" role="alert">
          {t(errorMessageKey(fetchIt.error))}
        </span>
      )}
    </div>
  );
}

/** Calls log (phase 7 §4): every queued, outbound and conference call, its links, outcome and recording. */
export function CallsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const ids = { status: useId(), direction: useId(), link: useId(), search: useId() };
  const [filters, setFilters] = useState<CallFilters>({ status: "" });
  const [direction, setDirection] = useState("");
  const [link, setLink] = useState<LinkFilter>("");
  const [search, setSearch] = useState("");
  const query = useInfiniteQuery({
    queryKey: p7Keys.calls(filters),
    queryFn: ({ pageParam, signal }) => api.calls(filters, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const rows = useMemo(() => {
    const all = query.data?.pages.flatMap((p) => p.items) ?? [];
    const needle = search.trim().toLowerCase();
    return all.filter(
      (c) =>
        (!direction || c.direction === direction) &&
        (!link || (link === "linked") === Boolean(c.report_id ?? c.incident_id)) &&
        (!needle ||
          [c.tracking_code, c.caller_number, c.queue, c.operator_name].some((v) => v?.toLowerCase().includes(needle))),
    );
  }, [query.data, direction, link, search]);

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("calls.title")}</h1>
        <p className="muted" role="status" aria-live="polite">
          {query.isFetching ? t("common.loading") : t("calls.count", { count: fmt.number(rows.length) })}
        </p>
      </div>
      <p className="muted">{t("calls.intro")}</p>
      <div className="filters" role="group" aria-label={t("calls.filters")}>
        <div className="field">
          <label htmlFor={ids.status}>{t("calls.columns.status")}</label>
          <select
            id={ids.status}
            value={filters.status}
            onChange={(e) => setFilters({ status: e.target.value as CallStatus | "" })}
          >
            <option value="">{t("calls.all")}</option>
            {CALL_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`calls.status.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.direction}>{t("calls.columns.direction")}</label>
          <select id={ids.direction} value={direction} onChange={(e) => setDirection(e.target.value)}>
            <option value="">{t("calls.all")}</option>
            {CALL_DIRECTIONS.map((d) => (
              <option key={d} value={d}>
                {t(`calls.direction.${d}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.link}>{t("calls.columns.link")}</label>
          <select id={ids.link} value={link} onChange={(e) => setLink(e.target.value as LinkFilter)}>
            <option value="">{t("calls.all")}</option>
            <option value="linked">{t("calls.linked")}</option>
            <option value="unlinked">{t("calls.unlinked")}</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.search}>{t("calls.search")}</label>
          <input id={ids.search} type="search" dir="auto" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && rows.length === 0 && <p className="muted">{t("calls.none")}</p>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("calls.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("calls.columns.startedAt")}</th>
                <th scope="col">{t("calls.columns.direction")}</th>
                <th scope="col">{t("calls.columns.number")}</th>
                <th scope="col">{t("calls.columns.queue")}</th>
                <th scope="col">{t("calls.columns.status")}</th>
                <th scope="col">{t("calls.columns.duration")}</th>
                <th scope="col">{t("calls.columns.operator")}</th>
                <th scope="col">{t("calls.columns.link")}</th>
                <th scope="col">{t("calls.columns.recording")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => {
                const d = callDuration(c);
                return (
                  <tr key={c.id}>
                    <td>
                      <time dateTime={c.started_at}>{fmt.dateTime(c.started_at)}</time>
                      {c.simulated && <SimTag />}
                    </td>
                    <td>{knownOr(t, "calls.direction", c.direction)}</td>
                    <td dir="ltr" className="code">
                      {c.caller_number ?? "—"}
                    </td>
                    <td>{c.queue ?? "—"}</td>
                    <td>
                      <span className={`chip chip--call-${c.status}`}>{knownOr(t, "calls.status", c.status)}</span>
                      {c.transferred_to && <span className="muted"> → {c.transferred_to}</span>}
                      {c.end_reason && <div className="muted">{knownOr(t, "calls.endReason", c.end_reason)}</div>}
                    </td>
                    <td>{d === null ? "—" : fmt.duration(d)}</td>
                    <td>{c.operator_name ?? (c.operator_user_id ? t("calls.operatorSet") : "—")}</td>
                    <td>
                      {c.report_id && (
                        <Link to={`/reports/${encodeURIComponent(c.report_id)}`} className="code" dir="ltr">
                          {c.tracking_code ?? t("phone.link.report")}
                        </Link>
                      )}
                      {!c.report_id && c.tracking_code && (
                        <span className="code" dir="ltr">
                          {c.tracking_code}
                        </span>
                      )}
                      {c.incident_id && (
                        <>
                          {" "}
                          <Link to={`/incidents/${encodeURIComponent(c.incident_id)}`}>{t("phone.link.incident")}</Link>
                        </>
                      )}
                      {!c.report_id && !c.incident_id && !c.tracking_code && <span className="muted">—</span>}
                    </td>
                    <td>
                      <Recording call={c} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && (
        <div className="actions">
          <button
            type="button"
            className="btn"
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >
            {query.isFetchingNextPage ? t("common.loading") : t("calls.more")}
          </button>
        </div>
      )}
    </div>
  );
}
