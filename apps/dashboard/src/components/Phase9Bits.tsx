/** Small shared pieces of the phase 9 screens: rooms, claim badge, SLA countdown, geo and escalation tags. */
import { useId, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useGouvernorats } from "../lib/hooks";
import { clock, REASON_RANGE, reasonValid, secondsUntil, useNow } from "../lib/phase9";
import type { EscalationState, GeoState, SlaBand } from "../lib/phase9Types";
import { roomGouvernorat } from "../lib/roles";
import type { StaffReport } from "../lib/types";

/** Name of a room: the central room, or the gouvernorat of a `g:<code>` room. */
export function useRoomName(): (room: string | null | undefined) => string {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  return (room) => {
    if (!room) return t("rooms.none");
    if (room === "central") return t("rooms.central");
    const code = roomGouvernorat(room);
    return code === null ? room : t("rooms.regional", { name: gouvernorats.nameOf(code) ?? String(code) });
  };
}

/** "Claimed by <name> (<room>)" or "Not claimed". */
export function ClaimBadge({ report }: { report: Pick<StaffReport, "claimed_room" | "claimed_by_name"> }) {
  const { t } = useTranslation();
  const roomName = useRoomName();
  if (!report.claimed_room) return <span className="tag tag--unclaimed">{t("claim.unclaimed")}</span>;
  return (
    <span className="tag tag--claimed">
      {t("claim.claimedBy", {
        name: report.claimed_by_name || t("claim.someone"),
        room: roomName(report.claimed_room),
      })}
    </span>
  );
}

/** Time left before the claim deadline, or time overdue; refreshed every second. */
export function SlaCountdown({ dueAt, now: fixedNow }: { dueAt: string | null | undefined; now?: number }) {
  const { t } = useTranslation();
  const ticking = useNow(1000);
  const now = fixedNow ?? ticking;
  const left = secondsUntil(dueAt, now);
  if (left === null) return <span className="muted">{t("common.notAvailable")}</span>;
  const overdue = left < 0;
  return (
    <span className={`countdown${overdue ? " countdown--overdue" : ""}`}>
      <span dir="ltr" className="code">
        {clock(left)}
      </span>{" "}
      <span>{overdue ? t("sla.overdue") : t("sla.remaining")}</span>
    </span>
  );
}

export function SlaBandTag({ band }: { band: SlaBand | null | undefined }) {
  const { t } = useTranslation();
  if (!band) return null;
  return <span className={`tag tag--sla-${band}`}>{t(`sla.band.${band}`)}</span>;
}

export function GeoStateTag({ state }: { state: GeoState | undefined }) {
  const { t } = useTranslation();
  if (!state || state === "trusted") return null;
  return <span className={`tag tag--geo-${state}`}>{t(`geo.state.${state}`)}</span>;
}

export function EscalationTag({ state }: { state: EscalationState | undefined }) {
  const { t } = useTranslation();
  if (!state || state === "none") return null;
  return <span className={`tag tag--escalation-${state}`}>{t(`escalation.state.${state}`)}</span>;
}

/** Labelled reason field (5–500 characters unless told otherwise) with its length hint. */
export function ReasonField({
  label,
  value,
  onChange,
  disabled,
  range = REASON_RANGE,
  showError,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  range?: { min: number; max: number };
  showError?: boolean;
}) {
  const { t } = useTranslation();
  const id = useId();
  const invalid = Boolean(showError) && !reasonValid(value, range);
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <textarea
        id={id}
        rows={2}
        value={value}
        maxLength={range.max}
        dir="auto"
        disabled={disabled}
        aria-invalid={invalid || undefined}
        aria-describedby={`${id}-hint`}
        onChange={(e) => onChange(e.target.value)}
      />
      <p id={`${id}-hint`} className={invalid ? "field__error" : "muted"}>
        {t("common.reasonLength", { min: range.min, max: range.max })}
      </p>
    </div>
  );
}

/** Inline, non-modal panel opened by a button (the dashboard has no modal dialogs). */
export function InlineDialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const { t } = useTranslation();
  const id = useId();
  return (
    <div className="inline-dialog card" role="dialog" aria-labelledby={id}>
      <div className="inline-dialog__head">
        <h3 id={id}>{title}</h3>
        <button type="button" className="btn btn--ghost btn--small" onClick={onClose}>
          {t("common.close")}
        </button>
      </div>
      {children}
    </div>
  );
}
