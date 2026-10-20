import { useQueries } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useServices } from "../context/services";
import { useFormat } from "../lib/hooks";
import { streamKeys } from "../lib/streamsApi";
import type { StaffStream } from "../lib/streamTypes";
import type { StaffReportDetail } from "../lib/types";
import { useStreamList } from "../lib/streamHooks";
import { ConfidenceBadges, SimTag, SimulationBand, StreamStatusChip, streamTitle } from "./StreamBits";
import { StreamPlayer } from "./StreamPlayer";

/**
 * Live streams of a report (phase 6). The §4 list has no report filter, so they are found from the report's
 * recordings (`media.stream_id`) and from the live list (`report_id`); the others are read one by one.
 */
export function LinkedStreams({ report }: { report: StaffReportDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const [watching, setWatching] = useState<string | null>(null);
  const live = useStreamList({ status: "live", gouvernorat: null });
  const liveRows = useMemo(
    () => (live.data?.pages.flatMap((p) => p.items) ?? []).filter((s) => s.report_id === report.id),
    [live.data, report.id],
  );
  const otherIds = useMemo(() => {
    const known = new Set(liveRows.map((s) => s.id));
    return [...new Set(report.media.map((m) => m.stream_id).filter((id): id is string => Boolean(id)))].filter(
      (id) => !known.has(id),
    );
  }, [report.media, liveRows]);
  const details = useQueries({
    queries: otherIds.map((id) => ({
      queryKey: streamKeys.detail(id),
      queryFn: ({ signal }: { signal: AbortSignal }) => api.stream(id, signal),
      staleTime: 60_000,
    })),
  });
  const streams: StaffStream[] = [...liveRows, ...details.flatMap((q) => (q.data ? [q.data] : []))];
  if (streams.length === 0) return null;

  return (
    <section className="card" aria-labelledby="sec-streams">
      <h2 id="sec-streams">
        {t("streams.report.title")} ({fmt.number(streams.length)})
      </h2>
      {streams.some((s) => s.simulated) && <SimulationBand />}
      <ul className="linked-streams">
        {streams.map((s) => {
          const name = streamTitle(t, s);
          return (
            <li key={s.id} className="linked-stream">
              <div className="linked-stream__head">
                <Link to={`/streams/${encodeURIComponent(s.id)}`}>{t("streams.report.open", { source: t(`streams.source.${s.source}`) })}</Link>
                <StreamStatusChip status={s.status} />
                {s.simulated && <SimTag />}
                <ConfidenceBadges stream={s} />
              </div>
              <p className="muted">
                {s.started_at ? t("streams.report.started", { date: fmt.dateTime(s.started_at) }) : null}
                {s.duration_s !== null && ` · ${fmt.duration(s.duration_s)}`}
                {` · ${t("streams.report.recordings", { count: s.recordings_count })}`}
              </p>
              {s.status === "live" &&
                (watching === s.id ? (
                  <>
                    <StreamPlayer stream={s} title={t("streams.player.label", { name })} />
                    <button type="button" className="btn btn--small" onClick={() => setWatching(null)}>
                      {t("streams.report.hide")}
                    </button>
                  </>
                ) : (
                  <button type="button" className="btn btn--small btn--primary" onClick={() => setWatching(s.id)}>
                    {t("streams.report.watch")}
                  </button>
                ))}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
