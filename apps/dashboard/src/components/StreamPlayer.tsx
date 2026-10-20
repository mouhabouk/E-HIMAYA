import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { boxRect, containRect, latestFrame, type Rect } from "../lib/detections";
import { StreamSession, type PlayerSnapshot } from "../lib/streamSession";
import { isDetectionLabel, type StaffStream, type StreamDetection } from "../lib/streamTypes";
import { useFormat } from "../lib/hooks";

/** Boxes of a new frame stay on screen this long (frames come at 1–2 per second while something is detected). */
const OVERLAY_SHOW_MS = 8000;
/** A frame older than this when it reaches the screen (late refetch, skewed clock) is not drawn over live video. */
const OVERLAY_MAX_AGE_MS = 60_000;

/** The detections of the newest frame, while it is fresh. */
function useOverlayFrame(detections: readonly StreamDetection[] | undefined): StreamDetection[] {
  const frame = useMemo(() => latestFrame(detections ?? []), [detections]);
  const key = frame[0]?.at ?? null;
  const [shown, setShown] = useState<string | null>(null);
  useEffect(() => {
    if (!key) return;
    const fresh = Date.now() - Date.parse(key) <= OVERLAY_MAX_AGE_MS;
    const show = setTimeout(() => setShown(fresh ? key : null), 0);
    const hide = setTimeout(() => setShown((k) => (k === key ? null : k)), OVERLAY_SHOW_MS);
    return () => {
      clearTimeout(show);
      clearTimeout(hide);
    };
  }, [key]);
  return key !== null && shown === key ? frame : [];
}

function DetectionOverlay({ frame, area }: { frame: StreamDetection[]; area: Rect }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  if (frame.length === 0 || area.width <= 0) return null;
  return (
    <svg
      className="det-overlay"
      viewBox="0 0 1 1"
      preserveAspectRatio="none"
      style={{ left: area.x, top: area.y, width: area.width, height: area.height }}
      role="img"
      aria-label={frame
        .map((d) =>
          t("streams.detectionBadge", {
            label: isDetectionLabel(d.label) ? t(`streams.label.${d.label}`) : d.label,
            confidence: fmt.percent(d.confidence),
          }),
        )
        .join(t("common.listSeparator"))}
    >
      {frame.flatMap((d, i) =>
        d.boxes.map((box, j) => {
          const r = boxRect(box);
          return (
            <rect
              key={`${i}-${j}`}
              className={`det-box det-box--${isDetectionLabel(d.label) ? d.label : "other"}`}
              x={r.x}
              y={r.y}
              width={r.width}
              height={r.height}
              vectorEffect="non-scaling-stroke"
            />
          );
        }),
      )}
    </svg>
  );
}

interface StreamPlayerProps {
  stream: StaffStream;
  /** Accessible name of the video. */
  title: string;
  detections?: readonly StreamDetection[];
  className?: string;
}

/**
 * Plays a live stream (WHEP, falling back to HLS), muted by default, with the vision boxes over the picture.
 * Off screen (IntersectionObserver) or in a hidden tab the video pauses and the session is released.
 */
export function StreamPlayer({ stream, title, detections, className }: StreamPlayerProps) {
  const { t } = useTranslation();
  const { api, createStreamSession } = useServices();
  const container = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [snapshot, setSnapshot] = useState<PlayerSnapshot>({ state: "idle", transport: null });
  const [muted, setMuted] = useState(true);
  const [area, setArea] = useState<Rect>({ x: 0, y: 0, width: 0, height: 0 });
  const sessionRef = useRef<{ retryNow(): void } | null>(null);
  const live = stream.status === "live";
  const frame = useOverlayFrame(detections);

  useEffect(() => {
    const el = video.current;
    const box = container.current;
    if (!live || !el || !box) return;
    const options = {
      video: el,
      requestGrant: () => api.streamViewer(stream.id),
      onChange: setSnapshot,
    };
    const session = createStreamSession ? createStreamSession(options) : new StreamSession(options);
    sessionRef.current = session;

    // A tile that has never been on screen does not even ask for a viewer token.
    const observable = typeof IntersectionObserver === "function";
    let onScreen = !observable;
    let started = false;
    const sync = () => {
      const visible = onScreen && document.visibilityState !== "hidden";
      if (visible && !started) {
        started = true;
        session.start();
      } else if (visible) session.resume();
      else if (started) session.suspend();
    };
    const observer = observable
      ? new IntersectionObserver((entries) => {
          onScreen = entries.some((e) => e.isIntersecting);
          sync();
        })
      : null;
    observer?.observe(box);
    sync();
    const onOnline = () => session.retryNow();
    document.addEventListener("visibilitychange", sync);
    window.addEventListener("online", onOnline);
    return () => {
      observer?.disconnect();
      document.removeEventListener("visibilitychange", sync);
      window.removeEventListener("online", onOnline);
      session.stop();
      sessionRef.current = null;
    };
  }, [live, stream.id, api, createStreamSession]);

  // Where the picture is drawn inside the tile (object-fit: contain), for the boxes.
  useEffect(() => {
    const el = video.current;
    const box = container.current;
    if (!el || !box) return;
    const measure = () => setArea(containRect(box.clientWidth, box.clientHeight, el.videoWidth, el.videoHeight));
    el.addEventListener("loadedmetadata", measure);
    el.addEventListener("resize", measure);
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(measure) : null;
    observer?.observe(box);
    const first = requestAnimationFrame(measure);
    return () => {
      cancelAnimationFrame(first);
      el.removeEventListener("loadedmetadata", measure);
      el.removeEventListener("resize", measure);
      observer?.disconnect();
    };
  }, []);

  useEffect(() => {
    if (video.current) video.current.muted = muted;
  }, [muted]);

  const state = live ? snapshot.state : "ended";
  const message =
    state === "playing" ? null : state === "idle" ? t("streams.player.connecting") : t(`streams.player.${state}`);

  return (
    <div className={`player${className ? ` ${className}` : ""}`}>
      <div ref={container} className="player__frame">
        <video
          ref={video}
          className="player__video"
          muted
          autoPlay
          playsInline
          aria-label={title}
        />
        <DetectionOverlay frame={frame} area={area} />
        {message && (
          <div className={`player__state player__state--${state}`} role="status" aria-live="polite">
            {state === "connecting" || state === "reconnecting" || state === "idle" ? (
              <span className="spinner" aria-hidden="true" />
            ) : null}
            <span>{message}</span>
          </div>
        )}
      </div>
      <div className="player__bar">
        <button
          type="button"
          className="btn btn--small"
          aria-pressed={!muted}
          onClick={() => setMuted((m) => !m)}
          disabled={!live}
        >
          {muted ? t("streams.player.unmute") : t("streams.player.mute")}
        </button>
        {live && (state === "reconnecting" || state === "unavailable") && (
          <button type="button" className="btn btn--small" onClick={() => sessionRef.current?.retryNow()}>
            {t("common.retry")}
          </button>
        )}
        {snapshot.transport && live && (
          <span className="muted player__transport">{t(`streams.player.transport.${snapshot.transport}`)}</span>
        )}
      </div>
    </div>
  );
}
