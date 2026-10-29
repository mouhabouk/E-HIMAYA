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
    fireEvent.change(panel.getByLabelText("السبب (إذا لم يتم أو أُجّل أو رُفض أو أُلغي)"), { target: { value: "تحسّن الطقس" } });
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

  it("offers the suggested activities with their reasons, to accept or set aside (AI3)", async () => {
    const api = fakeScheduleApi();
    const draft = { ...SCHEDULE_DETAIL, period: { ...SCHEDULE_DETAIL.period, status: "draft" as const }, can_edit: true, can_submit: true, can_follow_up: false };
    vi.mocked(api.scheduleSlot).mockResolvedValue({ ...SCHEDULE_SLOT, period: draft });
    vi.mocked(api.scheduleSuggestions).mockResolvedValue({
      enabled: true,
      can_accept: true,
      items: [
        {
          key: "fire_patrol:2026-10-27",
          source: "weather",
          activity: "patrol",
          on_date: "2026-10-27",
          title: "دورية مراقبة الغابات: خطر حرائق مرتفع جدا",
          reasons: ["توقع خطر الحرائق مرتفع جدا يوم 2026-10-27 في 3 من 5 نقاط الطقس بالولاية."],
          simulated: true,
        },
        {
          key: "season:fire",
          source: "season",
          activity: "prevention_visit",
          on_date: "2026-10-26",
          title: "زيارات وقائية: موسم الحرائق",
          reasons: ["6 تدخلا (الحرائق) في نفس الأيام خلال السنوات الثلاث الماضية، أي 2.4 مرة المعدل السنوي."],
          simulated: false,
        },
      ],
    });
    renderApp(<SchedulePage />, { api: fakeApi(api), auth: fakeAuth(claims(["operator"], "21")), lang: "ar" });
    const bar = within(await screen.findByRole("region", { name: /أنشطة مقترحة/ }));
    expect(bar.getByText(/نقاط الطقس بالولاية/)).toBeInTheDocument();
    expect(bar.getAllByText("اقتراح الذكاء الاصطناعي").length).toBeGreaterThan(0);
    fireEvent.click(bar.getAllByRole("button", { name: "قبول وإضافته" })[0] as HTMLElement);
    await waitFor(() => expect(api.acceptScheduleSuggestion).toHaveBeenCalledWith("per-nabeul-w44", "fire_patrol:2026-10-27", 4, "ar"));
    fireEvent.click(bar.getAllByRole("button", { name: "تنحية" })[1] as HTMLElement);
    fireEvent.change(bar.getByLabelText("السبب (اختياري)"), { target: { value: "زيارات مبرمجة سابقا" } });
    fireEvent.click(bar.getByRole("button", { name: "تأكيد التنحية" }));
    await waitFor(() => expect(api.dismissScheduleSuggestion).toHaveBeenCalledWith("per-nabeul-w44", "season:fire", "زيارات مبرمجة سابقا"));
  });

  it("keeps a programme as a template and starts a new one from it", async () => {
    const api = fakeScheduleApi();
    vi.mocked(api.scheduleSlot).mockResolvedValue({ ...SCHEDULE_SLOT, period: null, can_create: true });
    renderApp(<SchedulePage />, { api: fakeApi(api), auth: fakeAuth(claims(["operator"], "21")), lang: "ar" });
    fireEvent.change(await screen.findByLabelText("أو من نموذج"), { target: { value: "tpl-week" } });
    fireEvent.click(screen.getByRole("button", { name: "إنشاء من النموذج" }));
    await waitFor(() => expect(api.applyScheduleTemplate).toHaveBeenCalledWith("per-nabeul-w44", 4, "tpl-week"));
    expect(api.createPeriod).toHaveBeenCalledWith("week", expect.any(String), 21);
  });

  it("saves the programme under a name and lists the templates", async () => {
    const api = fakeScheduleApi();
    renderApp(<SchedulePage />, { api: fakeApi(api), auth: fakeAuth(claims(["operator"], "21")), lang: "ar" });
    fireEvent.click(await screen.findByRole("button", { name: "حفظ هذه البرمجة نموذجا" }));
    fireEvent.change(screen.getByLabelText("اسم النموذج"), { target: { value: "أسبوع الشتاء" } });
    fireEvent.click(screen.getByRole("button", { name: "حفظ النموذج" }));
    await waitFor(() => expect(api.saveScheduleTemplate).toHaveBeenCalledWith("per-nabeul-w44", "أسبوع الشتاء"));
    expect(await screen.findByText("حُفظ النموذج «أسبوع الشتاء».")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "النماذج" }));
    expect(await screen.findByDisplayValue("[SIM] أسبوع موسم الاصطياف")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "حذف النموذج [SIM] الأسبوع العادي" }));
    await waitFor(() => expect(api.deleteScheduleTemplate).toHaveBeenCalledWith("tpl-week"));
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
