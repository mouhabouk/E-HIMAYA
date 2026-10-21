import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useLiveEvents } from "../context/live";
import { useFormat, useLanguage } from "../lib/hooks";
import type { LiveEvent } from "../lib/live";
import { localized } from "../lib/localized";

type FollowUp = Extract<LiveEvent, { type: "alert.review_needed" | "alert.delivery_degraded" }>;

/** At most this many follow-ups on screen; the alert pages keep the full picture. */
const MAX_TOASTS = 4;

function keyOf(event: FollowUp): string {
  return event.type === "alert.delivery_degraded"
    ? `${event.type}:${event.message.id}:${event.channel}`
    : `${event.type}:${event.message.id}`;
}

/**
 * Phase 10 §5: what an alert still needs from a person. A channel that did not deliver (10 % of failures or more, or no
 * provider configured) and an alert published alone under the emergency override stay on screen until dismissed, with
 * a link to the alert.
 */
export function AlertFollowUpToasts() {
  const { t } = useTranslation();
  const fmt = useFormat();
  const lang = useLanguage();
  const [toasts, setToasts] = useState<FollowUp[]>([]);

  useLiveEvents((event) => {
    if (event.type !== "alert.review_needed" && event.type !== "alert.delivery_degraded") return;
    const key = keyOf(event);
    setToasts((list) => [event, ...list.filter((x) => keyOf(x) !== key)].slice(0, MAX_TOASTS));
  });

  const dismiss = useCallback((key: string) => setToasts((list) => list.filter((x) => keyOf(x) !== key)), []);

  if (toasts.length === 0) return null;
  return (
    <section className="toasts toasts--follow-up" aria-label={t("notify.followUp.region")}>
      {toasts.map((toast) => {
        const key = keyOf(toast);
        const title = localized(toast.message.title, lang);
        return (
          <div key={key} className="toast toast--follow-up" role="alert">
            <p className="toast__title">
              <strong>
                {toast.type === "alert.delivery_degraded"
                  ? t("notify.followUp.degradedTitle")
                  : t("notify.followUp.reviewTitle")}
              </strong>
            </p>
            <p dir="auto">{title}</p>
            {toast.type === "alert.delivery_degraded" ? (
              <p>
                {toast.reason === "not_configured"
                  ? t("notify.followUp.notConfigured", { channel: t(`notify.channel.${toast.channel}`) })
                  : t("notify.followUp.failures", {
                      channel: t(`notify.channel.${toast.channel}`),
                      sent: fmt.number(toast.sent),
                      failed: fmt.number(toast.failed),
                    })}
              </p>
            ) : (
              <p dir="auto">
                {t("notify.followUp.reviewBody", { reason: toast.message.emergency_reason ?? "—" })}
              </p>
            )}
            <div className="actions">
              <Link className="btn btn--small btn--primary" to={`/notifications/${encodeURIComponent(toast.message.id)}`}>
                {t("notify.followUp.open")}
              </Link>
              <button type="button" className="btn btn--small btn--ghost" onClick={() => dismiss(key)}>
                {t("notify.followUp.dismiss")}
              </button>
            </div>
          </div>
        );
      })}
    </section>
  );
}
