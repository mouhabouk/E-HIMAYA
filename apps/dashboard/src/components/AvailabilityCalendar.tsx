// covers: phase N (docs/phase-n/design-n.md §8): the availability calendar a volunteer or a doctor keeps in the app,
// read by the staff on the person's page. "Unavailable" slots win over "available" ones; the call-up does not suggest
// a volunteer whose calendar says unavailable now.
import { useTranslation } from "react-i18next";
import { useFormat } from "../lib/hooks";
import type { AvailabilityCalendarData } from "../lib/opsTypes";

const hhmm = (t: string) => t.slice(0, 5);

export function AvailabilityCalendar({ calendar }: { calendar: AvailabilityCalendarData }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <section className="card" aria-labelledby="sec-calendar">
      <h2 id="sec-calendar">{t("calendar.title")}</h2>
      <p>
        <span className={`chip calendar-now calendar-now--${calendar.planned_now ?? "none"}`}>
          {t(`calendar.now.${calendar.planned_now ?? "none"}`)}
        </span>
      </p>
      {calendar.slots.length === 0 ? (
        <p className="muted">{t("calendar.empty")}</p>
      ) : (
        <ul className="calendar-slots">
          {calendar.slots.map((s) => (
            <li key={s.id} className={`calendar-slots__item calendar-slots__item--${s.kind}`}>
              <strong>{t(`calendar.kind.${s.kind}`)}</strong>{" "}
              {s.ends_on
                ? t("calendar.between", { from: fmt.date(s.starts_on), to: fmt.date(s.ends_on) })
                : t("calendar.from", { from: fmt.date(s.starts_on) })}
              {" · "}
              {s.weekdays.length === 0 ? t("calendar.everyDay") : s.weekdays.map((d) => t(`analytics.weekday.${d}`)).join("، ")}
              {" · "}
              <span dir="ltr" className="calendar-slots__hours">
                {hhmm(s.from_time)}–{hhmm(s.to_time)}
              </span>
              {s.to_time < s.from_time && <span className="muted"> {t("calendar.overnight")}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
