// covers: phase L5a (docs/phase-l/design-l5.md §2): the digital dry run in the dashboard: dormant in the menu until
// the administrator grants it, the plan and its scenario (written and generated), the run (answer and book real
// resources inside the dry run), the stop with its reason, and the report with the load and attack results.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { navGroups } from "../components/Navigation";
import { DRILL, RUNNING } from "../test/drillData";
import { fakeDrillApi } from "../test/drillFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { DrillPage } from "./DrillPage";
import { DrillsPage } from "./DrillsPage";

const claims = (gouvernorat?: string) => ({
  sub: "u-room",
  name: "Test",
  realm_access: { roles: ["ops_manager"] },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

const granted = (keys: string[]) =>
  vi.fn(() => Promise.resolve({ granted: keys, hidden: [], lent: Object.fromEntries(keys.map((k) => [k, "ops_manager"])) }));

describe("dry run menu entry", () => {
  it("is hidden from every role until the administrator grants the page", () => {
    const t = ((k: string) => k) as never;
    const identity = { subject: "s", name: "n", roles: ["ops_manager", "sysadmin"], gouvernoratCode: null, national: true, hasScope: true, mfa: true };
    const links = (access?: Parameters<typeof navGroups>[2]) => navGroups(identity, t, access).flatMap((g) => g.items.map((i) => i.to));
    expect(links()).not.toContain("/drills");
    expect(links({ granted: new Set(), hidden: new Set(["drill"]), lent: {} })).not.toContain("/drills");
    expect(links({ granted: new Set(["drill"]), hidden: new Set(), lent: {} })).toContain("/drills");
  });
});

describe("DrillsPage", () => {
  it("plans a dry run only with the planning button", async () => {
    const drill = fakeDrillApi();
    renderApp(<DrillsPage />, { api: fakeApi({ ...drill, myFeatures: granted(["drill", "drill.plan"]) }), auth: fakeAuth(claims()), path: "/drills" });
    expect(await screen.findByText("لا توجد تمارين بعد.")).toBeInTheDocument();
    expect(screen.getByText("المنظومة أمام عدد هائل من البلاغات")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "تمرين جديد" }));
    fireEvent.change(screen.getByLabelText("عنوان التمرين"), { target: { value: "[SIM] فيضان" } });
    fireEvent.change(screen.getByLabelText("الهدف"), { target: { value: "قياس الجاهزية" } });
    fireEvent.click(screen.getByRole("button", { name: "إنشاء المسودة" }));
    expect(await screen.findByText("اختر ولاية واحدة على الأقل.")).toBeInTheDocument();
    expect(drill.createDrill).not.toHaveBeenCalled();
  });

  it("shows no planning button without the grant", async () => {
    renderApp(<DrillsPage />, { api: fakeApi({ ...fakeDrillApi(), myFeatures: granted(["drill"]) }), auth: fakeAuth(claims()), path: "/drills" });
    expect(await screen.findByText("لا توجد تمارين بعد.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "تمرين جديد" })).not.toBeInTheDocument();
  });
});

describe("DrillPage", () => {
  it("writes and generates the scenario of a draft, then submits it", async () => {
    const drill = fakeDrillApi();
    renderApp(<DrillPage />, { api: fakeApi(drill), auth: fakeAuth(claims()), path: `/drills/${DRILL.id}`, route: "/drills/:id" });
    expect(await screen.findByText("عائلة محاصرة بالمياه في منزل قرب الوادي")).toBeInTheDocument();
    expect(screen.getByText(/2 × زورق/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "توليد" }));
    await waitFor(() => expect(drill.generateInjects).toHaveBeenCalledWith(DRILL.id, { count: 30, kinds: ["flood"], seed: 1 }));
    fireEvent.click(screen.getByRole("button", { name: "عرض على الولايات" }));
    await waitFor(() => expect(drill.submitDrill).toHaveBeenCalledWith(DRILL.id));
  });

  it("lets a participating room answer a due message, book its resources, and stop the run with a reason", async () => {
    const drill = { ...fakeDrillApi(), drill: vi.fn(() => Promise.resolve(RUNNING)) };
    renderApp(<DrillPage />, {
      api: fakeApi({ ...drill, myFeatures: granted(["drill", "drill.respond"]) }),
      auth: fakeAuth(claims("21")),
      path: `/drills/${DRILL.id}`,
      route: "/drills/:id",
    });
    expect(await screen.findByText("مضت 40 د")).toBeInTheDocument();
    const item = (await screen.findByText("عطب زورق في وحدة قليبية")).closest("li") as HTMLElement;
    fireEvent.click(within(item).getByLabelText(/زورق · زورق 3/));
    fireEvent.click(within(item).getByRole("button", { name: "إرسال الرد" }));
    await waitFor(() =>
      expect(drill.respondInject).toHaveBeenCalledWith(DRILL.id, "i-3", { action: "dispatched", text: "", resource_ids: ["f-3"] }),
    );

    fireEvent.click(screen.getByRole("button", { name: "إيقاف التمرين فورا" }));
    fireEvent.click(screen.getByRole("button", { name: "تأكيد الإيقاف" }));
    expect(drill.stopDrill).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("سبب الإيقاف"), { target: { value: "[SIM] حريق حقيقي في نابل" } });
    fireEvent.click(screen.getByRole("button", { name: "تأكيد الإيقاف" }));
    await waitFor(() => expect(drill.stopDrill).toHaveBeenCalledWith(DRILL.id, "[SIM] حريق حقيقي في نابل"));
  });

  it("reports the answers, the resources short at the peak and the attacks blocked", async () => {
    const ended = { ...RUNNING, status: "ended" as const, can_stop: false, my_approval: null };
    const drill = { ...fakeDrillApi(), drill: vi.fn(() => Promise.resolve(ended)) };
    renderApp(<DrillPage />, { api: fakeApi(drill), auth: fakeAuth(claims()), path: `/drills/${DRILL.id}`, route: "/drills/:id" });
    fireEvent.click(await screen.findByRole("tab", { name: "التقرير" }));
    expect(await screen.findByText("صُدّت كلها")).toBeInTheDocument();
    expect(screen.getByText("بلا رد")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "الموارد حسب الولاية والنوع" })).toBeInTheDocument();
  });
});
