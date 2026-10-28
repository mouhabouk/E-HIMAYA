// covers: phase PL2 (docs/phase-pl/design-plans.md §3): the calendar rules, a week of a gouvernorat with its follow-up,
// adding a repeated activity, sending a programme the way its gouvernorat approves, the approval setting, and the
// governor who sees the progress only.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { bounds, monthWeeks, moveSpan } from "../lib/schedule";
import { canOpenSchedule } from "../lib/roles";
import { fakeScheduleApi, SCHEDULE_DETAIL, SCHEDULE_SLOT } from "../test/scheduleFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { SchedulePage } from "./SchedulePage";

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

describe("schedule helpers", () => {
  it("follows the calendar of the API", () => {
    expect(bounds("week", "2026-10-28")).toEqual(["2026-10-26", "2026-11-01"]);
    expect(bounds("month", "2026-02-14")).toEqual(["2026-02-01", "2026-02-28"]);
    expect(moveSpan("month", "2026-01-31", 1)).toBe("2026-02-01");
    expect(monthWeeks("2026-10-01", "2026-10-31")).toHaveLength(5);
    expect(canOpenSchedule(["governor"])).toBe(true);
    expect(canOpenSchedule(["citizen"])).toBe(false);
  });
});

describe("SchedulePage", () => {
  it("shows the week of a gouvernorat and follows an activity up", async () => {
    const api = fakeScheduleApi();
    renderApp(<SchedulePage />, { api: fakeApi(api), auth: fakeAuth(claims(["operator"], "21")), lang: "ar" });
    expect(await screen.findByText("اعتماد رئيس القاعة")).toBeInTheDocument();
    expect(screen.getAllByText("معتمدة").length).toBeGreaterThan(0);
    expect(screen.getAllByText("[SIM] مناوبة الفريق أ")).toHaveLength(7);
    expect(api.scheduleSlot).toHaveBeenCalledWith("week", expect.any(String), 21, expect.anything());
    // A postponed activity tells why.
    fireEvent.click(screen.getByRole("button", { name: /دورية الشريط الساحلي/ }));
    const panel = within(screen.getByRole("region", { name: "[SIM] دورية الشريط الساحلي الحمامات" }));
    expect(panel.getByText(/رياح قوية/)).toBeInTheDocument();
    fireEvent.change(panel.getByLabelText("السبب (للتأجيل أو الإلغاء)"), { target: { value: "تحسّن الطقس" } });
    fireEvent.click(panel.getByRole("button", { name: "إعادة إلى مبرمج" }));
    await waitFor(() => expect(api.scheduleItemStatus).toHaveBeenCalledWith("patrol-1", "planned", "تحسّن الطقس"));
    // The month view lays the same programme on a grid.
    fireEvent.click(screen.getByRole("button", { name: "شهر" }));
    await waitFor(() => expect(api.scheduleSlot).toHaveBeenLastCalledWith("month", expect.any(String), 21, expect.anything()));
  });

  it("adds a repeated activity and sends the draft", async () => {
    const api = fakeScheduleApi();
    const draft = { ...SCHEDULE_DETAIL, period: { ...SCHEDULE_DETAIL.period, status: "draft" as const }, can_edit: true, can_submit: true, can_follow_up: false };
    vi.mocked(api.scheduleSlot).mockResolvedValue({ ...SCHEDULE_SLOT, period: draft });
    renderApp(<SchedulePage />, { api: fakeApi(api), auth: fakeAuth(claims(["operator"], "21")), lang: "ar" });
    fireEvent.click(await screen.findByRole("button", { name: "إضافة نشاط" }));
    const form = within(screen.getByRole("form", { name: "إضافة نشاط" }));
    fireEvent.change(form.getByLabelText("نوع النشاط"), { target: { value: "patrol" } });
    fireEvent.change(form.getByLabelText("العنوان"), { target: { value: "دورية الغابات" } });
    fireEvent.change(form.getByLabelText("التكرار"), { target: { value: "weekdays" } });
    fireEvent.click(await form.findByRole("button", { name: "إضافة مورد" }));
    fireEvent.change(form.getByLabelText("العدد"), { target: { value: "2" } });
    fireEvent.click(form.getByRole("button", { name: "إضافة نشاط" }));
    await waitFor(() =>
      expect(api.addScheduleItem).toHaveBeenCalledWith(
        "per-nabeul-w44",
        expect.objectContaining({ activity: "patrol", title: "دورية الغابات", repeat: "weekdays", resources: [{ category_key: "pump", qty: 2 }] }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "نسخ الفترة السابقة" }));
    await waitFor(() => expect(api.periodStep).toHaveBeenCalledWith("per-nabeul-w44", "copy-previous", 4, undefined));
    fireEvent.click(screen.getByRole("button", { name: "إرسال للاعتماد" }));
    await waitFor(() => expect(api.periodStep).toHaveBeenLastCalledWith("per-nabeul-w44", "submit", 4, undefined));
  });

  it("lets the head of the room choose how its gouvernorat approves", async () => {
    const api = fakeScheduleApi();
    renderApp(<SchedulePage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "21")), lang: "ar" });
    fireEvent.click(await screen.findByRole("tab", { name: "طريقة الاعتماد" }));
    fireEvent.change(await screen.findByLabelText("طريقة اعتماد نابل"), { target: { value: "head_and_centre" } });
    fireEvent.click(screen.getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(api.saveScheduleSetting).toHaveBeenCalledWith(21, "head_and_centre"));
    expect(screen.queryByLabelText("طريقة اعتماد بنزرت")).not.toBeInTheDocument();
  });

  it("shows the governor the progress only", async () => {
    const api = fakeScheduleApi();
    renderApp(<SchedulePage />, { api: fakeApi(api), auth: fakeAuth(claims(["governor"], "21")), lang: "ar" });
    expect(await screen.findByRole("columnheader", { name: "نسبة الإنجاز" })).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
    expect(api.scheduleSlot).not.toHaveBeenCalled();
  });
});
