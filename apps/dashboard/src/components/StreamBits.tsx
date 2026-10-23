import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { confidenceBand } from "../lib/detections";
import { useFormat } from "../lib/hooks";
import { isDetectionLabel, type StaffStream, type StreamStatus } from "../lib/streamTypes";

/** What names a stream on screen: the staff label of a fixed source, else the report's tracking code. */
export function streamTitle(
  t: TFunction,
  stream: Pick<StaffStream, "label" | "tracking_code" | "source"> & { simulated?: boolean },
): string {
  // Simulated labels come prefixed "[SIM] " (contract implementation notes); the [SIM] tag is shown separately.
  const label = stream.simulated ? stream.label?.replace(/^\s*\[SIM\]\s*/i, "") : stream.label;
  return label?.trim() || stream.tracking_code || t(`streams.source.${stream.source}`);
}

/**
 * ┏━━ SIMULATION ━━ The amber band "وضع المحاكاة" of simulated sources (phase 6 §6).
 * ┃ PRODUCTION: nothing to remove: it only shows while a stream with `simulated: true` (the `stream-sim` service of
 * ┃   the compose profile `sim`) is on screen.
 * ┗━━━━━━━━━━━━━━━━
 */
export function SimulationBand({ note }: { note?: string }) {
  const { t } = useTranslation();
  return (
    <div className="sim-band" role="note" aria-label={t("streams.sim.bandLabel")}>
      <strong>
        <span lang="ar">وضع المحاكاة</span> · <span lang="fr">Mode simulation</span>
      </strong>
      <span>{note ?? t("streams.sim.band")}</span>
    </div>
  );
}

/**
 * `[SIM]` marker of simulated data (the text is the contract's prefix; the accessible name says what it is): a
 * simulated stream by default, or what `label` says (e.g. a map layer of approximate trial places, phase B1).
 */
export function SimTag({ label }: { label?: string }) {
  const { t } = useTranslation();
  const title = label ?? t("streams.sim.tagTitle");
  return (
    <span className="tag tag--sim" title={title}>
      <span aria-hidden="true">[SIM]</span>
      <span className="visually-hidden">{title}</span>
    </span>
  );
}

export function StreamStatusChip({ status }: { status: StreamStatus }) {
  const { t } = useTranslation();
  return (
    <span className={`chip chip--stream-${status}`}>
      <span className="chip__dot" aria-hidden="true" />
      {t(`streams.status.${status}`)}
    </span>
  );
}

/** A detection label with its confidence ("Feu 82 %"), banded like the vision thresholds (§3). */
export function DetectionBadge({ label, confidence }: { label: string; confidence: number }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const name = isDetectionLabel(label) ? t(`streams.label.${label}`) : label;
  const band = confidenceBand(confidence);
  return (
    <span
      className={`det det--${isDetectionLabel(label) ? label : "other"} det--${band}`}
      title={t(`streams.band.${band}`)}
    >
      {t("streams.detectionBadge", { label: name, confidence: fmt.percent(confidence) })}
    </span>
  );
}

/** Highest fire and smoke confidences of a stream, when there are any. */
export function ConfidenceBadges({ stream }: { stream: Pick<StaffStream, "max_fire_confidence" | "max_smoke_confidence"> }) {
  const fire = stream.max_fire_confidence;
  const smoke = stream.max_smoke_confidence;
  if (fire === null && smoke === null) return null;
  return (
    <span className="dets">
      {fire !== null && <DetectionBadge label="fire" confidence={fire} />}
      {smoke !== null && <DetectionBadge label="smoke" confidence={smoke} />}
    </span>
  );
}
