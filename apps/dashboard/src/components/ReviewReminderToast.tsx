import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useLiveEvents } from "../context/live";
import { awKeys } from "../lib/addressWarnings";
import { useFormat } from "../lib/hooks";
import type { LiveEvent } from "../lib/live";

type Reminder = Extract<LiveEvent, { type: "address_warnings.review_reminder" }>;

/**
 * OS8-3 (docs/phase-os8/design-os8.md §10): the morning review reminder of the address warnings. Once a day from 08:00
 * the room of each gouvernorat with marks past or near their review date gets it (the national room: every one); it
 * stays on screen until dismissed and opens the reminders of the register.
 */
export function ReviewReminderToast() {
  const { t } = useTranslation();
  const fmt = useFormat();
  const qc = useQueryClient();
  const [items, setItems] = useState<Reminder[]>([]);
  useLiveEvents((event) => {
    if (event.type !== "address_warnings.review_reminder") return;
    void qc.invalidateQueries({ queryKey: awKeys.reminders });
    setItems((list) =>
      [event, ...list.filter((x) => x.gouvernorat_code !== event.gouvernorat_code || x.day !== event.day)].slice(0, 3),
    );
  });
  if (items.length === 0) return null;
  const dismiss = (r: Reminder) => setItems((list) => list.filter((x) => x !== r));
  return (
    <section className="toasts toasts--follow-up toasts--aw" aria-label={t("addressWarnings.reminders.toastRegion")}>
      {items.map((r) => (
        <div key={`${r.gouvernorat_code}-${r.day}`} className="toast toast--follow-up" role="status">
          <p className="toast__title">
            <strong>{t("addressWarnings.reminders.toastTitle")}</strong>
          </p>
          <p>
            {t("addressWarnings.reminders.toastBody", { late: fmt.number(r.late), soon: fmt.number(r.soon) })}
            {r.central > 0
              ? ` ${t("addressWarnings.reminders.toastCentral", { n: fmt.number(r.central) })}`
              : r.manager > 0
                ? ` ${t("addressWarnings.reminders.toastManager", { n: fmt.number(r.manager) })}`
                : ""}
          </p>
          <div className="actions">
            <Link className="btn btn--small btn--primary" to="/address-warnings?tab=reminders" onClick={() => dismiss(r)}>
              {t("addressWarnings.reminders.open")}
            </Link>
            <button type="button" className="btn btn--small btn--ghost" onClick={() => dismiss(r)}>
              {t("notify.followUp.dismiss")}
            </button>
          </div>
        </div>
      ))}
    </section>
  );
}
