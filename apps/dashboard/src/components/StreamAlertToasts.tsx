import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useLiveEvents } from "../context/live";
import { playAlertTone, useAlertSound } from "../lib/alertSound";
import { useFormat } from "../lib/hooks";
import { findCachedStream } from "../lib/streamsCache";
import type { AlertLabel, StaffStream } from "../lib/streamTypes";
import { SimTag, streamTitle } from "./StreamBits";

interface Toast {
  key: string;
  streamId: string;
  reportId: string | null;
  label: AlertLabel;
  confidence: number;
  stream: StaffStream | null;
  simulated: boolean;
}

/** At most this many alerts on screen; older ones stay on the streams pages. */
const MAX_TOASTS = 4;
/** A dismissed alert for the same stream and label comes back only after this pause. */
const REALERT_AFTER_MS = 60_000;

/** Sound on/off for the fire and smoke alerts (kept in this browser). */
export function AlertSoundToggle() {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useAlertSound();
  return (
    <button type="button" className="btn btn--small" aria-pressed={enabled} onClick={() => setEnabled(!enabled)}>
      {enabled ? t("streams.alerts.soundOn") : t("streams.alerts.soundOff")}
    </button>
  );
}

/**
 * FR-C-07: a confirmed fire or smoke on a live stream (`stream.alert`) is announced on every screen, with a short
 * sound, until the operator dismisses it. It only informs: what to do stays an operator's decision (FR-C-11), so
 * nothing is triggered from here.
 */
export function StreamAlertToasts() {
  const { t } = useTranslation();
  const fmt = useFormat();
  const qc = useQueryClient();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const shown = useRef(new Set<string>());
  const dismissedAt = useRef(new Map<string, number>());

  useEffect(() => {
    shown.current = new Set(toasts.map((x) => x.key));
  }, [toasts]);

  useLiveEvents((event) => {
    if (event.type !== "stream.alert") return;
    const key = `${event.stream_id}:${event.label}`;
    const isNew = !shown.current.has(key);
    if (isNew && Date.now() - (dismissedAt.current.get(key) ?? 0) < REALERT_AFTER_MS) return;
    const stream = findCachedStream(qc, event.stream_id);
    setToasts((list) => {
      const existing = list.find((x) => x.key === key);
      if (existing) {
        return list.map((x) => (x.key === key ? { ...x, confidence: Math.max(x.confidence, event.confidence), stream: stream ?? x.stream } : x));
      }
      const toast: Toast = {
        key,
        streamId: event.stream_id,
        reportId: event.report_id,
        label: event.label,
        confidence: event.confidence,
        stream,
        simulated: event.simulated ?? stream?.simulated ?? false,
      };
      return [toast, ...list].slice(0, MAX_TOASTS);
    });
    if (isNew) {
      shown.current.add(key);
      playAlertTone();
    }
  });

  const dismiss = useCallback((key: string) => {
    dismissedAt.current.set(key, Date.now());
    setToasts((list) => list.filter((x) => x.key !== key));
  }, []);

  if (toasts.length === 0) return null;
  return (
    <section className="toasts" aria-label={t("streams.alerts.region")}>
      <div className="toasts__tools">
        <AlertSoundToggle />
      </div>
      {toasts.map((toast) => {
        const name = toast.stream ? streamTitle(t, toast.stream) : t("streams.alerts.unknownStream");
        return (
          <div
            key={toast.key}
            className={`toast toast--${toast.label}`}
            role="alert"
            onKeyDown={(e) => {
              if (e.key === "Escape") dismiss(toast.key);
            }}
          >
            <p className="toast__title">
              <strong>{t(`streams.alerts.title.${toast.label}`)}</strong>
              {toast.simulated && <SimTag />}
            </p>
            <p>
              {t("streams.alerts.body", { confidence: fmt.percent(toast.confidence), name })}
            </p>
            <p className="toast__note">{t("streams.alerts.humanDecision")}</p>
            <div className="actions">
              <Link className="btn btn--small btn--primary" to={`/streams/${encodeURIComponent(toast.streamId)}`}>
                {t("streams.alerts.watch")}
              </Link>
              {toast.reportId && (
                <Link className="btn btn--small" to={`/reports/${encodeURIComponent(toast.reportId)}`}>
                  {t("streams.alerts.openReport")}
                </Link>
              )}
              <button
                type="button"
                className="btn btn--small btn--ghost"
                aria-label={t("streams.alerts.dismissLabel", { kind: t(`streams.label.${toast.label}`), name })}
                onClick={() => dismiss(toast.key)}
              >
                {t("streams.alerts.dismiss")}
              </button>
            </div>
          </div>
        );
      })}
    </section>
  );
}
