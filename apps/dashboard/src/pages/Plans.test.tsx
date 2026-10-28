// covers: phase PL1 (docs/phase-pl/design-plans.md §2): the plans by hazard in their colours, a new plan of a hazard
// opened in the register, the hazards kept by the central room, the plan read on the screen, the plans of an axis.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { textOn } from "../lib/plans";
import { fakeRegisterApi } from "../test/registerFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { PlansPage, PlanViewerPage } from "./PlansPage";
import { RegisterPage } from "./RegisterPage";

const pdf = vi.hoisted(() => {
  const page = {
    getViewport: () => ({ width: 600, height: 800 }),
    render: () => ({ promise: Promise.resolve(), cancel: () => undefined }),
  };
  return {
    openPdf: () => Promise.resolve({ numPages: 3, getPage: () => Promise.resolve(page) }),
    outline: () => Promise.resolve([{ title: "الفصل 1: اليقظة", page: 1 }, { title: "الفصل 2: الإنذار", page: 3 }]),
    findPages: vi.fn(() => Promise.resolve([2, 3])),
  };
});
vi.mock("../lib/pdf", () => pdf);

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
});

describe("plans helpers", () => {
  it("writes black or white on the colour of a hazard", () => {
    expect(textOn("#1976D2")).toBe("#FFFFFF");
    expect(textOn("#F5B400")).toBe("#000000");
  });
});

describe("PlansPage", () => {
  it("shows the plans of every hazard in its colour and keeps the hazards", async () => {
    const api = fakeRegisterApi();
    renderApp(<PlansPage />, { api: fakeApi(api), auth: fakeAuth(claims(["central_committee"])), lang: "ar" });
    const card = (await screen.findByRole("heading", { name: "مخطط الفيضانات" })).closest("li");
    expect(card).toHaveStyle({ "--hazard": "#1976D2" });
    const flood = within(card as HTMLElement);
    expect(flood.getByText("المخطط الأزرق الوطني للتدخل عند الفيضانات")).toBeInTheDocument();
    expect(flood.getByText("نابل")).toBeInTheDocument();
    expect(flood.getAllByRole("link", { name: "عرض على الشاشة" })[0]).toHaveAttribute("href", "/plans/reg-blue");
    expect(flood.getByRole("link", { name: "مخطط جديد لهذا الخطر" })).toHaveAttribute("href", "/register?new=plan&hazard=floods");
    expect(screen.getAllByText("لا مخطط مسجّل لهذا الخطر بعد.")).toHaveLength(3);

    fireEvent.click(screen.getByRole("tab", { name: "المخاطر وألوانها" }));
    fireEvent.click(await screen.findByRole("button", { name: "تعديل الفيضانات" }));
    fireEvent.change(screen.getByLabelText("الترتيب"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(api.saveHazard).toHaveBeenCalledWith("floods", expect.objectContaining({ colour: "#1976D2", position: 5 })));
  });

  it("hides the hazards from a regional room", async () => {
    const api = fakeRegisterApi();
    vi.mocked(api.plans).mockResolvedValue({ ...(await api.plans()), can_manage_hazards: false });
    renderApp(<PlansPage />, { api: fakeApi(api), auth: fakeAuth(claims(["operator"], "21")), lang: "ar" });
    expect(await screen.findByRole("heading", { name: "مخطط الفيضانات" })).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });

  it("opens the register on a new plan of the hazard", async () => {
    const api = fakeRegisterApi();
    renderApp(<RegisterPage />, { api: fakeApi(api), auth: fakeAuth(claims(["ops_manager"], "21")), lang: "ar", path: "/register?new=plan&hazard=floods" });
    const form = within(await screen.findByRole("form", { name: "تدوين وثيقة في السجل" }));
    expect(form.getByLabelText("النوع")).toHaveValue("plan");
    await waitFor(() => expect(form.getByLabelText("الخطر الذي يجيب عنه المخطط")).toHaveValue("floods"));
  });
});

describe("PlanViewerPage", () => {
  it("reads a plan on the screen under the colour of its hazard", async () => {
    const api = fakeRegisterApi();
    renderApp(<PlanViewerPage />, {
      api: fakeApi(api),
      auth: fakeAuth(claims(["operator"], "21")),
      lang: "ar",
      path: "/plans/reg-plan",
      route: "/plans/:id",
    });
    expect(await screen.findByText("مخطط الفيضانات")).toBeInTheDocument();
    const viewer = await screen.findByRole("region", { name: /^عرض / });
    expect(api.documentFileBytes).toHaveBeenCalledWith("reg-plan", expect.anything());
    expect(within(viewer).getByText("من 3")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /التالية/ }));
    expect(screen.getByLabelText("الصفحة")).toHaveValue(2);
    fireEvent.change(screen.getByLabelText("فهرس المخطط"), { target: { value: "3" } });
    expect(screen.getByLabelText("الصفحة")).toHaveValue(3);
    fireEvent.change(screen.getByLabelText("بحث في نص المخطط"), { target: { value: "الإيواء" } });
    fireEvent.click(screen.getByRole("button", { name: "بحث" }));
    expect(await screen.findByText(/وُجد في 2 صفحات/)).toBeInTheDocument();
    expect(pdf.findPages).toHaveBeenCalledWith(expect.anything(), "الإيواء");
    expect(screen.getByLabelText("الصفحة")).toHaveValue(2);
  });
});
