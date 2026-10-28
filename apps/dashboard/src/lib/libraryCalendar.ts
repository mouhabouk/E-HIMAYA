import type { CalendarLevel, CalendarStep } from "./phase8Types";

/** Date arithmetic of the six-level calendar (L4a), on "YYYY-MM-DD" strings so no time zone shifts a day. */

const MONTHS: Partial<Record<CalendarLevel, number>> = { month: 1, quarter: 3, half: 6, year: 12 };

/** The level a cell of this step opens; the hours of a day open the day's list instead. */
export const FINER: Record<CalendarStep, CalendarLevel | null> = { hour: null, day: "day", week: "week", month: "month" };

function parts(iso: string): [number, number, number] {
  return [Number(iso.slice(0, 4)), Number(iso.slice(5, 7)), Number(iso.slice(8, 10))];
}

export function isoOf(y: number, m: number, d: number): string {
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.toISOString().slice(0, 10);
}

export function todayIso(now = new Date()): string {
  return isoOf(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

/** The day ``on`` moved by one period of ``level`` (backwards when ``by`` is negative). */
export function shiftDay(level: CalendarLevel, on: string, by: number): string {
  const [y, m, d] = parts(on);
  if (level === "day") return isoOf(y, m, d + by);
  if (level === "week") return isoOf(y, m, d + 7 * by);
  return isoOf(y, m + (MONTHS[level] ?? 1) * by, 1);
}

/** 1-based number of the quarter or half-year of a day. */
export function partOfYear(level: "quarter" | "half", on: string): number {
  const month = parts(on)[1];
  return Math.floor((month - 1) / (level === "quarter" ? 3 : 6)) + 1;
}

/** Heat class 0..4 of a cell, relative to the busiest cell of the grid. */
export function heat(count: number, max: number): number {
  if (count <= 0 || max <= 0) return 0;
  return Math.min(4, Math.ceil((count / max) * 4));
}
