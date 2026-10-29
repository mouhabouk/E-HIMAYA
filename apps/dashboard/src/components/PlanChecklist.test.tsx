// covers: L5 (docs/phase-l/design-l5.md §2.3, AI2): the task list read from the plan. The room manager asks the local
// model to read the plan, reviews each suggestion (with the passage it rests on and whether it was found on its page),
// approves the list; the rooms follow it task by task. Every suggestion carries the AI label.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { APPROVED, EMPTY, fakeChecklistApi, PLAN, REVIEW } from "../test/checklistFixtures";
import { fakeApi, renderApp } from "../test/render";
import { PlanChecklist } from "./PlanChecklist";

const AXIS = { kind: "axis" as const, id: "ax-1" };

describe("PlanChecklist", () => {
  it("asks the local model to read the plan of the axis", async () => {
    const api = fakeChecklistApi(EMPTY);
    renderApp(<PlanChecklist owner={AXIS} />, { api: fakeApi(api), lang: "ar" });
    expect(await screen.findByText("اقتراح الذكاء الاصطناعي")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "المخطط الأزرق للفيضانات [SIM]" })).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "اقرأ المخطط" }));
    await waitFor(() => expect(api.readPlan).toHaveBeenCalledWith(AXIS, PLAN.id, null));
    expect(await screen.findByRole("status")).toHaveTextContent("النموذج المحلي يقرأ المخطط");
  });

  it("shows each suggestion with its page and passage, and approves only once all are reviewed", async () => {
    const api = fakeChecklistApi(REVIEW);
    renderApp(<PlanChecklist owner={AXIS} />, { api: fakeApi(api), lang: "ar" });
    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("فتح خلية الأزمة");
    expect(items[0]).toHaveTextContent("«تفتح القاعة خلية الأزمة»");
    expect(items[0]).toHaveTextContent("المقطع موجود في الصفحة");
    expect(items[1]).toHaveTextContent("لم يُعثر على المقطع في الصفحة: تحقّق من المخطط");
    expect(screen.getByRole("button", { name: "اعتمد القائمة" })).toBeDisabled();
    expect(screen.getByText("اقتراحات بانتظار المراجعة: 3")).toBeInTheDocument();

    fireEvent.click(within(items[0] as HTMLElement).getByRole("button", { name: "اقبل" }));
    await waitFor(() => expect(api.reviewTask).toHaveBeenCalledWith(AXIS, "t-1", "accept", undefined));
    fireEvent.click(within(items[2] as HTMLElement).getByRole("button", { name: "احذف" }));
    await waitFor(() => expect(api.reviewTask).toHaveBeenCalledWith(AXIS, "t-3", "delete", undefined));

    fireEvent.click(within(items[1] as HTMLElement).getByRole("button", { name: "عدّل" }));
    const action = within(items[1] as HTMLElement).getByLabelText("المهمة");
    fireEvent.change(action, { target: { value: "استدعاء فرق الإنقاذ بالزوارق" } });
    fireEvent.click(within(items[1] as HTMLElement).getByRole("button", { name: "احفظ التعديل" }));
    await waitFor(() =>
      expect(api.reviewTask).toHaveBeenCalledWith(AXIS, "t-2", "edit", {
        action: "استدعاء فرق الإنقاذ بالزوارق",
        owner: "",
        resource: "زوارق",
        page: 2,
      }),
    );
  });

  it("adds a task the model missed, with the action required", async () => {
    const api = fakeChecklistApi(REVIEW);
    renderApp(<PlanChecklist owner={AXIS} />, { api: fakeApi(api), lang: "ar" });
    fireEvent.click(await screen.findByRole("button", { name: "أضف مهمة" }));
    fireEvent.click(screen.getByRole("button", { name: "أضف" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("اكتب المهمة");
    fireEvent.change(screen.getByLabelText("المهمة"), { target: { value: "إعلام الوالي كل ساعتين" } });
    fireEvent.click(screen.getByRole("button", { name: "أضف" }));
    await waitFor(() =>
      expect(api.addTask).toHaveBeenCalledWith(AXIS, { action: "إعلام الوالي كل ساعتين", owner: "", resource: "", page: null }),
    );
  });

  it("follows the approved list task by task, without the deleted ones", async () => {
    const api = fakeChecklistApi(APPROVED);
    renderApp(<PlanChecklist owner={{ kind: "drill", id: "ex-1" }} />, { api: fakeApi(api), lang: "ar" });
    expect(await screen.findByText("أُنجز 1 من 2")).toBeInTheDocument();
    expect(screen.queryByText("إخلاء الأحياء المنخفضة")).not.toBeInTheDocument();
    expect(screen.getByText("استدعاء فرق الإنقاذ")).toBeInTheDocument();
    const second = screen.getByRole("group", { name: "حالة المهمة: استدعاء فرق الإنقاذ بالزوارق" });
    fireEvent.click(within(second).getByRole("radio", { name: "أُنجزت" }));
    await waitFor(() => expect(api.followTask).toHaveBeenCalledWith({ kind: "drill", id: "ex-1" }, "t-2", "done", ""));
  });
});
