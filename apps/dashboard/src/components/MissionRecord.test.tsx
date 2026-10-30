// covers: phase S2 (docs/phase-s/design-s2.md): the record of a mission in the operations room, its times always in
// order (the return after the departure), typed as digits across midnight, a reason for correcting the team's times.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  dateForClock,
  indicators,
  maskClock,
  parseClock,
  recordBody,
  recordErrors,
  timesOf,
  type RecordTimes,
} from "../lib/missionRecord";
import type { Assignment } from "../lib/opsTypes";
import { makeAssignment } from "../test/opsFixtures";
import { fakeApi, renderApp } from "../test/render";
import { MissionIndicators, MissionRecordEditor } from "./MissionRecord";

const at = (h: number, m: number, s = 0, day = 30) => new Date(2026, 9, day, h, m, s);
const iso = (d: Date) => d.toISOString();

function mission(overrides: Partial<Assignment> = {}): Assignment {
  return makeAssignment({
    status: "on_scene",
    created_at: iso(at(14, 0)),
    en_route_at: iso(at(14, 2, 30)),
    on_scene_at: iso(at(14, 11)),
    crew_count: 4,
    time_sources: { en_route_at: "app", on_scene_at: "app" },
    ...overrides,
  });
}

describe("the rules of the record", () => {
  const times: RecordTimes = timesOf({
    created_at: iso(at(14, 0)),
    en_route_at: iso(at(14, 2)),
    on_scene_at: iso(at(14, 10)),
    left_scene_at: iso(at(14, 40)),
    at_hospital_at: iso(at(14, 55)),
    back_at_unit_at: iso(at(15, 20)),
  });
  const now = at(16, 0);

  it("keeps the times in order and the return after the departure", () => {
    expect(recordErrors(times, now)).toEqual({});
    expect(recordErrors({ ...times, on_scene_at: at(14, 1) }, now)).toEqual({ on_scene_at: "times_out_of_order" });
    expect(recordErrors({ ...times, left_scene_at: null }, now)).toEqual({ at_hospital_at: "time_needs_previous" });
    expect(recordErrors({ ...times, back_at_unit_at: at(17, 0) }, now)).toEqual({ back_at_unit_at: "time_in_future" });
    const flat = { ...times, on_scene_at: null, left_scene_at: null, at_hospital_at: null, back_at_unit_at: at(14, 2) };
    expect(recordErrors(flat, now)).toEqual({ back_at_unit_at: "return_before_departure" });
    expect(recordErrors({ ...times, on_scene_at: null }, now, times).on_scene_at).toBe("time_required");
  });

  it("reads digits as a clock and crosses midnight", () => {
    expect(maskClock("143205")).toBe("14:32:05");
    expect(parseClock("1432")).toBe(14 * 3600 + 32 * 60);
    expect(parseClock("2460")).toBeNull();
    expect(parseClock("14:32:5")).toBeNull();
    // Departure 23:50, return typed 00:20: the next day; a clock a little behind stays (and shows out of order).
    expect(dateForClock(20 * 60, at(23, 50), now)).toEqual(at(0, 20, 0, 31));
    expect(dateForClock(23 * 3600 + 45 * 60, at(23, 50), now)).toEqual(at(23, 45));
  });

  it("measures the mission and sends only what changed", () => {
    const d = indicators(times, at(13, 58));
    expect(d).toMatchObject({ turnout: 120, travel: 480, response: 720, on_scene: 1800, transport: 900, mission: 4800 });
    expect(d.return).toBe(25 * 60);
    const changed = { ...times, on_scene_at: at(14, 9) };
    expect(
      recordBody(times, changed, { before: 4, after: 4 }, { before: {}, after: { water_m3: 2, foam_l: 0 } }, " تأخر "),
    ).toEqual({ times: { on_scene_at: iso(at(14, 9)) }, consumables: { water_m3: 2 }, reason: "تأخر" });
  });
});

describe("the room's editor", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(at(16, 0));
  });
  afterEach(() => vi.useRealTimers());

  it("shows the durations under the assignment", () => {
    renderApp(
      <MissionIndicators assignment={mission({ record_warnings: ["steps_together"] })} calledAt={iso(at(13, 58))} />,
      { lang: "ar" },
    );
    expect(screen.getByText("مهلة الخروج")).toBeInTheDocument();
    expect(screen.getByText("الخروج والوصول في اللحظة نفسها تقريبا")).toBeInTheDocument();
    expect(screen.getByText("من النداء إلى الوصول")).toBeInTheDocument();
  });

  it("marks a time out of order on its own field and asks a reason for the team's times", async () => {
    const saved = mission({ left_scene_at: iso(at(14, 30)) });
    const api = fakeApi({ saveMissionRecord: vi.fn(() => Promise.resolve(saved)) });
    const onSaved = vi.fn();
    renderApp(<MissionRecordEditor assignment={mission()} onSaved={onSaved} onCancel={vi.fn()} />, { api, lang: "ar" });
    const save = screen.getByRole("button", { name: "حفظ السجل" });
    expect(save).toBeDisabled(); // nothing changed yet

    // The arrival typed before the departure: the error is on the arrival.
    const arrival = screen.getByLabelText("الوصول على عين المكان");
    fireEvent.focus(arrival);
    fireEvent.change(arrival, { target: { value: "1401" } });
    fireEvent.blur(arrival);
    expect(await screen.findByText(/التواقيت ليست بالترتيب/)).toBeInTheDocument();
    expect(save).toBeDisabled();

    // Corrected: a time the team gave changed, so a reason is asked.
    fireEvent.focus(arrival);
    fireEvent.change(arrival, { target: { value: "141030" } });
    fireEvent.blur(arrival);
    expect(screen.getByText("سبب التعديل")).toBeInTheDocument();
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByLabelText("حسب سجل اللاسلكي"));

    const left = screen.getByLabelText("مغادرة المكان");
    fireEvent.focus(left);
    fireEvent.change(left, { target: { value: "1430" } });
    fireEvent.blur(left);
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() =>
      expect(api.saveMissionRecord).toHaveBeenCalledWith("a-1", {
        times: { on_scene_at: iso(at(14, 10, 30)), left_scene_at: iso(at(14, 30)) },
        reason: "حسب سجل اللاسلكي",
      }),
    );
    expect(onSaved).toHaveBeenCalledWith(saved);
  });

  it("applies a time read from the radio log only on a click, with the radio log as the reason", async () => {
    const suggestion = {
      step: "left_scene_at" as const,
      at: iso(at(14, 40)),
      source: "pasted" as const,
      words: "غادرنا المكان 14:40",
      written_at: iso(at(16, 0)),
      conflict: null,
    };
    const api = fakeApi({
      suggestMissionTimes: vi.fn(() => Promise.resolve([suggestion])),
      saveMissionRecord: vi.fn(() => Promise.resolve(mission())),
    });
    renderApp(<MissionRecordEditor assignment={mission()} onSaved={vi.fn()} onCancel={vi.fn()} />, { api, lang: "ar" });
    fireEvent.change(screen.getByLabelText("سجل اللاسلكي أو أي نص (اختياري)"), {
      target: { value: "غادرنا المكان 14:40" },
    });
    fireEvent.click(screen.getByRole("button", { name: "اقرأ التواقيت" }));
    await waitFor(() => expect(api.suggestMissionTimes).toHaveBeenCalledWith("a-1", "غادرنا المكان 14:40"));
    const left = screen.getByLabelText<HTMLInputElement>("مغادرة المكان");
    expect(left.value).toBe(""); // nothing applied yet
    fireEvent.click(await screen.findByRole("button", { name: "اعتمد" }));
    expect(left.value).toBe("14:40:00");
    expect(screen.queryByRole("button", { name: "اعتمد" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "حفظ السجل" }));
    await waitFor(() =>
      expect(api.saveMissionRecord).toHaveBeenCalledWith("a-1", { times: { left_scene_at: iso(at(14, 40)) } }),
    );
  });
});
