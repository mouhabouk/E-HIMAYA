/**
 * The record of a mission (phase S2, docs/phase-s/design-s2.md): the times from the order to the return to the unit,
 * the crew and what the mission used. The same rules as the server (services/api/app/modules/ops/record.py), checked
 * as the operator types so that a time out of order is shown on its own field before anything is sent.
 */
import type { Assignment } from "./opsTypes";

export const RECORD_STEPS = [
  "created_at",
  "en_route_at",
  "on_scene_at",
  "left_scene_at",
  "at_hospital_at",
  "back_at_unit_at",
] as const;
export type RecordStep = (typeof RECORD_STEPS)[number];
export type EditableStep = Exclude<RecordStep, "created_at">;
export const EDITABLE_STEPS = RECORD_STEPS.slice(1) as readonly EditableStep[];

/** A time needs the one before it: no hospital without leaving the scene, no return without a departure. */
export const NEEDS: Partial<Record<EditableStep, EditableStep>> = {
  on_scene_at: "en_route_at",
  left_scene_at: "on_scene_at",
  at_hospital_at: "left_scene_at",
  back_at_unit_at: "en_route_at",
};
/** Times the status already reached cannot be cleared. */
export const REQUIRED_ONCE_SET: readonly EditableStep[] = ["en_route_at", "on_scene_at"];

export const FUTURE_SKEW_MS = 2 * 60_000;
export const MAX_MISSION_MS = 72 * 3600_000;

export const CONSUMABLES = [
  { key: "water_m3", max: 1000, step: 0.5 },
  { key: "foam_l", max: 20000, step: 10 },
  { key: "powder_kg", max: 5000, step: 1 },
  { key: "co2_kg", max: 2000, step: 1 },
  { key: "extinguishers", max: 200, step: 1 },
  { key: "oxygen_l", max: 50000, step: 10 },
  { key: "fuel_l", max: 5000, step: 1 },
  { key: "sandbags", max: 20000, step: 10 },
  { key: "absorbent_kg", max: 5000, step: 1 },
] as const;
export type Consumable = (typeof CONSUMABLES)[number]["key"];
export type TimeSource = "app" | "sms" | "room";

export type RecordTimes = Record<RecordStep, Date | null>;
export type RecordError =
  | "time_in_future"
  | "times_out_of_order"
  | "time_needs_previous"
  | "return_before_departure"
  | "mission_too_long"
  | "time_required";

export function timesOf(a: Pick<Assignment, RecordStep>): RecordTimes {
  const out = {} as RecordTimes;
  for (const step of RECORD_STEPS) {
    const v = a[step];
    out[step] = v ? new Date(v) : null;
  }
  return out;
}

/** The rule each time breaks, on that time's own field (the server answers with the first one). */
export function recordErrors(
  times: RecordTimes,
  now: Date,
  initial?: RecordTimes,
): Partial<Record<EditableStep, RecordError>> {
  const errors: Partial<Record<EditableStep, RecordError>> = {};
  let previous: Date | null = times.created_at;
  for (const step of EDITABLE_STEPS) {
    const at = times[step];
    if (at === null) {
      if (initial && REQUIRED_ONCE_SET.includes(step) && initial[step] !== null) errors[step] = "time_required";
      continue;
    }
    const before = NEEDS[step];
    if (before && times[before] === null) errors[step] = "time_needs_previous";
    else if (at.getTime() > now.getTime() + FUTURE_SKEW_MS) errors[step] = "time_in_future";
    else if (previous && at.getTime() < previous.getTime()) errors[step] = "times_out_of_order";
    else if (times.created_at && at.getTime() - times.created_at.getTime() > MAX_MISSION_MS)
      errors[step] = "mission_too_long";
    previous = at;
  }
  const back = times.back_at_unit_at;
  const departure = times.en_route_at;
  if (back && departure && back.getTime() <= departure.getTime() && !errors.back_at_unit_at)
    errors.back_at_unit_at = "return_before_departure";
  return errors;
}

/** The time a step follows: the closest earlier time given (the order at least). */
export function anchorOf(times: RecordTimes, step: EditableStep): Date | null {
  const before = RECORD_STEPS.slice(0, RECORD_STEPS.indexOf(step)).reverse();
  return before.map((s) => times[s]).find((at): at is Date => at !== null) ?? null;
}

/** "1430", "14:30", "14:30:15", "143015" → seconds of the day; `null` when it is not a time. */
export function parseClock(text: string): number | null {
  const digits = text.replace(/\D/g, "");
  if (digits.length < 3 || digits.length > 6 || digits.length === 5) return null;
  const padded = digits.length === 3 ? `0${digits}` : digits;
  const h = Number(padded.slice(0, 2));
  const m = Number(padded.slice(2, 4));
  const s = padded.length === 6 ? Number(padded.slice(4, 6)) : 0;
  if (h > 23 || m > 59 || s > 59) return null;
  return h * 3600 + m * 60 + s;
}

/** As the operator types: digits only, the colons put in ("1430" → "14:30", "143015" → "14:30:15"). */
export function maskClock(text: string): string {
  const digits = text.replace(/\D/g, "").slice(0, 6);
  const parts = [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4, 6)].filter(Boolean);
  return parts.join(":");
}

export function clockOf(at: Date, seconds = true): string {
  const two = (n: number) => String(n).padStart(2, "0");
  const base = `${two(at.getHours())}:${two(at.getMinutes())}`;
  return seconds ? `${base}:${two(at.getSeconds())}` : base;
}

/**
 * The full date of a clock time typed for a step: the day of the time it follows, or the next day when the clock
 * is far behind it (a mission across midnight: departure 23:50, return 00:20). A clock a little behind stays on the
 * same day, so that the mistake shows as "out of order" instead of jumping to tomorrow.
 */
export function dateForClock(secondsOfDay: number, anchor: Date | null, now: Date): Date {
  const base = anchor ?? now;
  const at = new Date(base.getFullYear(), base.getMonth(), base.getDate(), 0, 0, secondsOfDay);
  if (anchor && anchor.getTime() - at.getTime() > 12 * 3600_000) at.setDate(at.getDate() + 1);
  return at;
}

export function shiftDays(at: Date, days: number): Date {
  const next = new Date(at);
  next.setDate(next.getDate() + days);
  return next;
}

export function shiftSeconds(at: Date, seconds: number): Date {
  return new Date(at.getTime() + seconds * 1000);
}

/** Days between the calendar dates of two times (0 the same day, 1 the next day). */
export function dayOffset(at: Date, from: Date): number {
  const a = new Date(at.getFullYear(), at.getMonth(), at.getDate()).getTime();
  const b = new Date(from.getFullYear(), from.getMonth(), from.getDate()).getTime();
  return Math.round((a - b) / 86_400_000);
}

export const INDICATORS = [
  { key: "turnout", from: "created_at", to: "en_route_at" },
  { key: "travel", from: "en_route_at", to: "on_scene_at" },
  { key: "response", from: "called_at", to: "on_scene_at" },
  { key: "on_scene", from: "on_scene_at", to: "left_scene_at" },
  { key: "transport", from: "left_scene_at", to: "at_hospital_at" },
  { key: "return", from: "last_out", to: "back_at_unit_at" },
  { key: "mission", from: "created_at", to: "back_at_unit_at" },
] as const;
export type IndicatorKey = (typeof INDICATORS)[number]["key"];

/** The mission's durations in seconds, those whose two ends are known. */
export function indicators(times: RecordTimes, calledAt: Date | null): Partial<Record<IndicatorKey, number>> {
  const point = (name: string): Date | null => {
    if (name === "called_at") return calledAt;
    if (name === "last_out") return times.at_hospital_at ?? times.left_scene_at;
    return times[name as RecordStep];
  };
  const out: Partial<Record<IndicatorKey, number>> = {};
  for (const ind of INDICATORS) {
    const a = point(ind.from);
    const b = point(ind.to);
    if (a && b && b.getTime() >= a.getTime()) out[ind.key] = (b.getTime() - a.getTime()) / 1000;
  }
  return out;
}

export interface RecordBody {
  times?: Partial<Record<EditableStep, string | null>>;
  crew_count?: number | null;
  consumables?: Partial<Record<Consumable, number>>;
  reason?: string | null;
}

/** Only what changed: a time left as it was is not sent (it keeps its seconds and its source). */
export function recordBody(
  initial: RecordTimes,
  times: RecordTimes,
  crew: { before: number | null; after: number | null },
  consumables: {
    before: Record<string, number>;
    after: Record<string, number>;
  },
  reason: string,
): RecordBody {
  const body: RecordBody = {};
  const changed: Partial<Record<EditableStep, string | null>> = {};
  for (const step of EDITABLE_STEPS) {
    if ((initial[step]?.getTime() ?? null) !== (times[step]?.getTime() ?? null))
      changed[step] = times[step]?.toISOString() ?? null;
  }
  if (Object.keys(changed).length) body.times = changed;
  if (crew.after !== crew.before) body.crew_count = crew.after;
  const tidy = (o: Record<string, number>) =>
    JSON.stringify(
      Object.fromEntries(
        Object.entries(o)
          .filter(([, v]) => v > 0)
          .sort(),
      ),
    );
  if (tidy(consumables.before) !== tidy(consumables.after))
    body.consumables = Object.fromEntries(Object.entries(consumables.after).filter(([, v]) => v > 0));
  if (reason.trim()) body.reason = reason.trim();
  return body;
}

/** Times the team gave (app or text message) that the operator changed: a reason is required. */
export function correctedSteps(
  initial: RecordTimes,
  times: RecordTimes,
  sources: Partial<Record<string, TimeSource>>,
): EditableStep[] {
  return EDITABLE_STEPS.filter(
    (s) =>
      initial[s] !== null &&
      initial[s].getTime() !== (times[s]?.getTime() ?? null) &&
      (sources[s] ?? "room") !== "room",
  );
}
