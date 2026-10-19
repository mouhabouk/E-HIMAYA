import { useTranslation } from "react-i18next";
import { useFormat } from "../lib/hooks";
import { analysisFlag, priorityBand } from "../lib/priority";
import type { IncidentStatus, StaffReport } from "../lib/types";

/** BR-20 priority score coloured by band (always with a text label); a dash when there is no score yet. */
export function PriorityBadge({ score }: { score: number | null | undefined }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const band = priorityBand(score);
  if (band === null || score === null || score === undefined) {
    return (
      <span className="prio prio--none" title={t("priority.none")}>
        <span aria-hidden="true">—</span>
        <span className="visually-hidden">{t("priority.none")}</span>
      </span>
    );
  }
  const label = t("priority.badge", { score: fmt.number(score), band: t(`priority.band.${band}`) });
  return (
    <span className={`prio prio--${band}`} title={label}>
      <span aria-hidden="true">{fmt.number(score)}</span>
      <span className="visually-hidden">{label}</span>
    </span>
  );
}

/** "Awaiting analysis" (pending/running) or "analysis incomplete" (failed); nothing otherwise. */
export function AnalysisChip({ state }: { state: StaffReport["analysis_state"] }) {
  const { t } = useTranslation();
  const flag = analysisFlag(state);
  if (!flag) return null;
  return <span className={`tag tag--analysis-${flag}`}>{t(`ai.${flag}`)}</span>;
}

/** Compact markers of a list row: analysis state, lives at risk, incident membership, waiting suggestion. */
export function ReportMarkers({ report }: { report: StaffReport }) {
  const { t } = useTranslation();
  return (
    <span className="markers">
      <AnalysisChip state={report.analysis_state} />
      {report.lives_at_risk && <span className="tag tag--lives">{t("ai.livesAtRisk")}</span>}
      {report.incident_id && <span className="tag tag--incident">{t("ai.inIncident")}</span>}
      {report.has_suggestion && <span className="tag tag--suggestion">{t("ai.suggestionWaiting")}</span>}
    </span>
  );
}

export function IncidentStatusChip({ status }: { status: IncidentStatus }) {
  const { t } = useTranslation();
  return (
    <span className={`chip chip--incident-${status}`}>
      <span className="chip__dot" aria-hidden="true" />
      {t(`incidents.status.${status}`)}
    </span>
  );
}
