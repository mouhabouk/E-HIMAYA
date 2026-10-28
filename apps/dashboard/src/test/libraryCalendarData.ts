import { isoOf, shiftDay } from "../lib/libraryCalendar";
import type { CalendarCell, CalendarGrid, CalendarLevel, PeriodFigures } from "../lib/phase8Types";
import { WINDOW_FIGURES } from "./windowData";

/**
 * A simulated library calendar ([SIM], L4a): any level of any day, with a few busy cells, for the unit tests, the
 * accessibility check and the screenshots. No test runner import here, so Playwright loads it too.
 */
const COUNTS = [0, 3, 0, 1, 7, 0, 2, 12, 0, 0, 4, 1];

function bounds(level: CalendarLevel, on: string): [string, string] {
  const [y, m, d] = [Number(on.slice(0, 4)), Number(on.slice(5, 7)), Number(on.slice(8, 10))];
  if (level === "day") return [on, on];
  if (level === "week") {
    const monday = isoOf(y, m, d - ((new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7));
    return [monday, shiftDay("day", monday, 6)];
  }
  const months = { month: 1, quarter: 3, half: 6, year: 12 }[level];
  const first = Math.floor((m - 1) / months) * months + 1;
  return [isoOf(y, first, 1), isoOf(y, first + months, 0)];
}

export function fakeGrid(level: CalendarLevel, on: string): CalendarGrid {
  const [start, end] = bounds(level, on);
  const step = ({ day: "hour", week: "day", month: "day", quarter: "week", half: "month", year: "month" } as const)[level];
  const cells: CalendarCell[] = [];
  if (step === "hour") {
    for (let h = 0; h < 24; h++) cells.push({ start: `${start}T${String(h).padStart(2, "0")}:00:00+01:00`, end: start, count: COUNTS[h % 12] ?? 0 });
  } else {
    let day = start;
    while (day <= end) {
      const next = step === "day" ? shiftDay("day", day, 1) : step === "week" ? shiftDay("week", day, 1) : shiftDay("month", day, 1);
      const last = shiftDay("day", next, -1);
      cells.push({ start: day, end: last < end ? last : end, count: COUNTS[cells.length % 12] ?? 0 });
      day = next;
    }
  }
  return { level, step, start, end, cells };
}

export function fakeFigures(from: string, to: string): PeriodFigures {
  return { from, to, gouvernorats: [], figures: WINDOW_FIGURES, min_cell: 5 };
}
