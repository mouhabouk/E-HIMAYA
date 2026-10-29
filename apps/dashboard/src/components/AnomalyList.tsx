// covers: L5 (docs/phase-l/design-l5.md §4.4, AI4): the indicators out of their habit, shown calmly with their
// explanation and the AI label, in the situation now and the alert centre.
import { useTranslation } from "react-i18next";
import type { Anomaly } from "../lib/anomalies";

export function AnomalyList({ items, headingId }: { items: Anomaly[]; headingId: string }) {
  const { t } = useTranslation();
  return (
    <section className="card anomalies" aria-labelledby={headingId}>
      <h2 id={headingId}>
        {t("anomalies.title")} <span className="tag tag--ai">{t("anomalies.ai")}</span>
      </h2>
      <p className="muted">{t("anomalies.help")}</p>
      <ul className="anomalies__list">
        {items.map((a) => (
          <li key={a.id} className="anomalies__item">
            <span className="tag">{t(`anomalies.indicator.${a.indicator}`)}</span>{" "}
            <span dir="auto">{a.text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
