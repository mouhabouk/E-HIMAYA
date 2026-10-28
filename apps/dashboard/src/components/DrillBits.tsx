// The small parts of the digital dry run (L5a, docs/phase-l/design-l5.md §2).
import { useTranslation } from "react-i18next";
import type { ApprovalDecision, DrillStatus } from "../lib/drill";
import { useFormat } from "../lib/hooks";

/** The hazards the scenario generator knows (services/api/app/modules/drill/router.py, GENERATED). */
export const DRILL_HAZARDS = ["fire", "traffic_accident", "flood", "drowning", "medical", "chemical_leak"] as const;

const STATUS_TONE: Record<DrillStatus, string> = {
  draft: "tone-slate",
  submitted: "tone-amber",
  ready: "tone-teal",
  running: "tone-red",
  stopped: "tone-orange",
  ended: "tone-navy",
  closed: "tone-green",
};

const DECISION_TONE: Record<ApprovalDecision, string> = {
  pending: "tone-amber",
  approved: "tone-green",
  refused: "tone-red",
  withdrawn: "tone-slate",
};

export function DrillStatusPill({ status }: { status: DrillStatus }) {
  const { t } = useTranslation();
  return <span className={`pill ${STATUS_TONE[status]}`}>{t(`drill.status.${status}`)}</span>;
}

export function DecisionPill({ decision }: { decision: ApprovalDecision }) {
  const { t } = useTranslation();
  return <span className={`pill ${DECISION_TONE[decision]}`}>{t(`drill.decision.${decision}`)}</span>;
}

/** Resources by kind in words ("2 boats, 1 ambulance"); a dash when none. */
export function Needs({ needs }: { needs: Record<string, number> }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const parts = Object.entries(needs).filter(([, n]) => n > 0);
  if (parts.length === 0) return <>—</>;
  return (
    <>
      {parts
        .map(([kind, n]) => `${fmt.number(n)} × ${t(`resources.kind.${kind}`, { defaultValue: kind })}`)
        .join(t("common.listSeparator"))}
    </>
  );
}
