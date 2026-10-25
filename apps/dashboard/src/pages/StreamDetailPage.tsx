import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import type { MapPoi } from "../components/MapView";
import { pointsBounds } from "../components/OrgBits";
import { ConfidenceBadges, DetectionBadge, SimTag, SimulationBand, StreamStatusChip, streamTitle } from "../components/StreamBits";
import { StreamPlayer } from "../components/StreamPlayer";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { initialBoundsFor } from "../lib/mapStyle";
import { canStopStreams } from "../lib/roles";
import { streamKeys } from "../lib/streamsApi";
import { STREAM_END_REASONS, type StaffStreamDetail, type StreamRecording } from "../lib/streamTypes";
import { PageTitle } from "../components/PageTitle";

/** Save a file or open a pre-signed link through a temporary <a download>. */
function saveAs(url: string, filename: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function RecordingRow({ streamId, recording }: { streamId: string; recording: StreamRecording }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const download = useMutation({
    mutationFn: () => api.recordingDownload(streamId, recording.media_id),
    onSuccess: (result) => {
      const filename = `ehimaya-recording-${recording.media_id}.mp4`;
      if (result.kind === "link") {
        saveAs(result.url, filename);
        return;
      }
      const objectUrl = URL.createObjectURL(result.blob);
      saveAs(objectUrl, filename);
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    },
  });
  const when = fmt.dateTime(recording.created_at);
  return (
    <tr>
      <td>
        <time dateTime={recording.created_at}>{when}</time>
      </td>
      <td className="num">{recording.duration_s === null ? "—" : fmt.duration(recording.duration_s)}</td>
      <td className="num">{recording.bytes === null ? "—" : fmt.bytes(recording.bytes)}</td>
      <td>
        <span className="hash" dir="ltr">
          {recording.sha256}
        </span>
      </td>
      <td>
        <button
          type="button"
          className="btn btn--small"
          onClick={() => download.mutate()}
          disabled={download.isPending}
          aria-busy={download.isPending}
          aria-label={t("streams.detail.downloadLabel", { date: when })}
        >
          {download.isPending ? t("common.loading") : t("streams.detail.download")}
        </button>
        {download.isError && (
          <p className="alert alert--error" role="alert">
            {t(errorMessageKey(download.error))}
          </p>
        )}
      </td>
    </tr>
  );
}

/** Stop for everyone, after an explicit confirmation (audited by the API). */
function StopStream({ stream }: { stream: StaffStreamDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const mutation = useMutation({
    mutationFn: () => api.stopStream(stream.id),
    onSuccess: () => {
      // `stream.ended` follows on the live feed; show it at once.
      qc.setQueryData<StaffStreamDetail>(streamKeys.detail(stream.id), (d) =>
        d ? { ...d, status: "ended", end_reason: "staff_stopped" } : d,
      );
      void qc.invalidateQueries({ queryKey: streamKeys.detail(stream.id) });
      void qc.invalidateQueries({ queryKey: streamKeys.listsAll });
    },
    onSettled: () => setConfirming(false),
  });
  return (
    <div className="stop-stream">
      {confirming && (
        <p className="alert alert--warn" role="alert">
          {t("streams.detail.stopConfirmText")}
        </p>
      )}
      <div className="actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={mutation.isPending}
          onClick={() => (confirming ? mutation.mutate() : setConfirming(true))}
        >
          {mutation.isPending ? t("streams.detail.stopping") : confirming ? t("streams.detail.stopConfirm") : t("streams.detail.stop")}
        </button>
        {confirming && (
          <button type="button" className="btn" onClick={() => setConfirming(false)}>
            {t("common.cancel")}
          </button>
        )}
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </div>
  );
}

/** One stream: player, track on the map, detections, recordings (SHA-256) and the stop control. */
export function StreamDetailPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const query = useQuery({
    queryKey: streamKeys.detail(id),
    queryFn: ({ signal }) => api.stream(id, signal),
    // Reading the detail is audited (`stream.detail`, the track is personal data): no polling; the live events
    // patch the track and the confidences, and reload it after an alert or a new recording.
    staleTime: 60_000,
    retry: (count, error) => !(isApiError(error) && [403, 404].includes(error.status)) && count < 2,
  });
  const s = query.data;
  const track = useMemo(() => s?.track ?? [], [s?.track]);
  const lines = useMemo(
    () => [{ id: "track", coordinates: track.map((p) => [p.lon, p.lat] as [number, number]) }],
    [track],
  );
  const detections = useMemo(
    () => [...(s?.detections ?? [])].sort((a, b) => Date.parse(b.at) - Date.parse(a.at)),
    [s?.detections],
  );

  if (query.isPending) return <Loading />;
  if (query.isError || !s)
    return (
      <div className="page">
        <Link to="/streams">{t("streams.detail.back")}</Link>
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );

  const name = streamTitle(t, s);
  const position = s.last_location ?? (track.length > 0 ? track[track.length - 1] : null) ?? null;
  const pois: MapPoi[] = position
    ? [{ id: s.id, lon: position.lon, lat: position.lat, kind: "stream", title: t("streams.detail.lastPosition", { name }) }]
    : [];
  const bounds =
    pointsBounds([...track, ...(position ? [position] : [])], 0.004) ?? initialBoundsFor(s.gouvernorat_code);
  const live = s.status === "live";
  const endReason = s.end_reason && (STREAM_END_REASONS as readonly string[]).includes(s.end_reason) ? s.end_reason : null;

  return (
    <article className="page detail" aria-labelledby="stream-title">
      <p>
        <Link to="/streams">{t("streams.detail.back")}</Link>
      </p>
      <div className="page__head">
        <PageTitle icon="videocam" tone="red" id="stream-title">
          {t("streams.detail.title")}{" "}
          <span dir="auto" className="code">
            {name}
          </span>
        </PageTitle>
        <StreamStatusChip status={s.status} />
        {s.simulated && <SimTag />}
        <ConfidenceBadges stream={s} />
      </div>
      {s.simulated && <SimulationBand />}

      <div className="detail__grid">
        <section className="card stream-detail__player" aria-labelledby="sec-player">
          <h2 id="sec-player">{t("streams.detail.player")}</h2>
          <StreamPlayer stream={s} title={t("streams.player.label", { name })} detections={s.detections} />
          {live && user && canStopStreams(user.identity.roles) && <StopStream stream={s} />}
        </section>

        <section className="card" aria-labelledby="sec-stream-info">
          <h2 id="sec-stream-info">{t("streams.detail.info")}</h2>
          <dl className="fields">
            <dt>{t("streams.columns.source")}</dt>
            <dd>{t(`streams.source.${s.source}`)}</dd>
            <dt>{t("streams.detail.report")}</dt>
            <dd>
              {s.report_id ? (
                <Link to={`/reports/${encodeURIComponent(s.report_id)}`} dir="ltr">
                  {s.tracking_code ?? t("streams.detail.openReport")}
                </Link>
              ) : (
                t("streams.detail.noReport")
              )}
            </dd>
            <dt>{t("streams.columns.gouvernorat")}</dt>
            <dd>{gouvernorats.nameOf(s.gouvernorat_code) ?? t("common.notAvailable")}</dd>
            <dt>{t("streams.columns.started")}</dt>
            <dd>{s.started_at ? fmt.dateTime(s.started_at) : t("common.notAvailable")}</dd>
            <dt>{t("streams.detail.ended")}</dt>
            <dd>{s.ended_at ? fmt.dateTime(s.ended_at) : "—"}</dd>
            <dt>{t("streams.columns.duration")}</dt>
            <dd>{s.duration_s === null ? "—" : fmt.duration(s.duration_s)}</dd>
            {endReason && (
              <>
                <dt>{t("streams.detail.endReason")}</dt>
                <dd>{t(`streams.endReason.${endReason}`)}</dd>
              </>
            )}
            <dt>{t("streams.columns.location")}</dt>
            <dd>
              {position ? (
                <span dir="ltr" className="code">
                  {position.lat.toFixed(5)}, {position.lon.toFixed(5)}
                </span>
              ) : (
                t("streams.noLocation")
              )}
            </dd>
          </dl>
        </section>

        <section className="card" aria-labelledby="sec-track">
          <h2 id="sec-track">{t("streams.detail.track")}</h2>
          <Suspense fallback={<Loading />}>
            <LazyMapView
              className="map map--mini"
              markers={[]}
              pois={pois}
              lines={lines}
              bounds={bounds}
              zoom={16}
              ariaLabel={t("streams.detail.mapLabel")}
              styleUrl={mapStyleUrl}
              dir={directionOf(lang)}
            />
          </Suspense>
          <p className="muted">{t("streams.detail.trackSummary", { count: track.length })}</p>
          {track.length > 0 && (
            <details>
              <summary>{t("streams.detail.trackList")}</summary>
              <ol className="track-list">
                {track.map((p, i) => (
                  <li key={`${p.at}-${i}`}>
                    <time dateTime={p.at}>{fmt.time(p.at)}</time>{" "}
                    <span dir="ltr" className="code">
                      {p.lat.toFixed(5)}, {p.lon.toFixed(5)}
                    </span>
                  </li>
                ))}
              </ol>
            </details>
          )}
        </section>

        <section className="card" aria-labelledby="sec-detections">
          <h2 id="sec-detections">
            {t("streams.detail.detections")} ({fmt.number(detections.length)})
          </h2>
          <p className="muted">{t("streams.detail.detectionsNote")}</p>
          {detections.length === 0 ? (
            <p className="muted">{t("streams.detail.noDetections")}</p>
          ) : (
            <ol className="timeline detections">
              {detections.map((d, i) => (
                <li key={`${d.at}-${d.label}-${i}`}>
                  <time dateTime={d.at}>{fmt.time(d.at)}</time>
                  <DetectionBadge label={d.label} confidence={d.confidence} />
                  <span className="muted">{t("streams.detail.boxes", { count: d.boxes.length })}</span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <section className="card" aria-labelledby="sec-recordings">
        <h2 id="sec-recordings">
          {t("streams.detail.recordings")} ({fmt.number(s.recordings.length)})
        </h2>
        {s.recordings.length === 0 ? (
          <p className="muted">{t("streams.detail.noRecordings")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">{t("streams.detail.recordingsCaption")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("streams.detail.recordedAt")}</th>
                  <th scope="col" className="num">
                    {t("streams.columns.duration")}
                  </th>
                  <th scope="col" className="num">
                    {t("detail.size")}
                  </th>
                  <th scope="col">{t("detail.sha256")}</th>
                  <th scope="col">{t("streams.columns.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {s.recordings.map((r) => (
                  <RecordingRow key={r.media_id} streamId={s.id} recording={r} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </article>
  );
}
