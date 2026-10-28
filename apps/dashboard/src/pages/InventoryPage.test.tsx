// covers: phase R1 (docs/phase-r/design-resources.md §2): the resources register page. The counts that the governor
// and the minister see, the tabs of a room, recording a vehicle with its specifications, the staff names kept to the
// operations rooms, and the import preview before saving.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { canListInventory, canOpenInventory } from "../lib/roles";
import { AGENT, fakeInventoryApi, OVERVIEW } from "../test/inventoryFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { InventoryPage } from "./InventoryPage";

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

describe("inventory roles", () => {
  it("opens the counts to the governor and the minister, the lists to the rooms", () => {
    expect(canOpenInventory(["governor"])).toBe(true);
    expect(canListInventory(["governor"])).toBe(false);
    expect(canListInventory(["operator"])).toBe(true);
    expect(canOpenInventory(["citizen"])).toBe(false);
  });
});

describe("InventoryPage", () => {
  it("shows the governor the counts only", async () => {
    const inv = fakeInventoryApi();
    inv.inventoryOverview = () =>
      Promise.resolve({ ...OVERVIEW, can_list: false, can_edit: false, can_see_names: false });
    renderApp(<InventoryPage />, { api: fakeApi(inv), auth: fakeAuth(claims(["governor"], "61")), lang: "ar" });
    expect(await screen.findByText("تظهر هنا الأعداد فقط. القوائم وأسماء الأعوان لقاعات العمليات.")).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.getByRole("table", { name: "حسب الولاية" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "الأعوان حسب الاختصاص" })).toHaveTextContent("غوص");
    expect(inv.inventoryUnits).not.toHaveBeenCalled();
    expect(inv.vehicles).not.toHaveBeenCalled();
  });

  it("records a fire engine with its capacity", async () => {
    const inv = fakeInventoryApi();
    renderApp(<InventoryPage />, { api: fakeApi(inv), auth: fakeAuth(claims(["ops_manager"], "61")), lang: "ar" });
    fireEvent.click(await screen.findByRole("tab", { name: "الآليات" }));
    const table = await screen.findByRole("table", { name: /آلية/ });
    expect(within(table).getByText("إطفاء 12")).toBeInTheDocument();
    expect(within(table).getByText("جاهزة")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "آلية جديدة" }));
    const form = screen.getByRole("form", { name: "آلية جديدة" });
    fireEvent.click(within(form).getByRole("button", { name: "حفظ" }));
    expect(within(form).getByRole("alert")).toHaveTextContent("أكمل الحقول المطلوبة.");
    fireEvent.change(within(form).getByLabelText("الوحدة"), { target: { value: "u-1" } });
    fireEvent.change(within(form).getByLabelText("الصنف"), { target: { value: "fire_engine" } });
    fireEvent.change(within(form).getByLabelText("التسمية"), { target: { value: "إطفاء 14" } });
    fireEvent.change(within(form).getByLabelText(/السعة/), { target: { value: "2000" } });
    fireEvent.click(within(form).getByLabelText("دفع رباعي"));
    fireEvent.click(within(form).getByRole("button", { name: "حفظ" }));
    await waitFor(() =>
      expect(inv.saveVehicle).toHaveBeenCalledWith(
        null,
        expect.objectContaining({ unit_id: "u-1", category_key: "fire_engine", label: "إطفاء 14", specs: { capacity_l: 2000, four_wd: true } }),
      ),
    );
  });

  it("keeps the staff names to the operations rooms", async () => {
    const inv = fakeInventoryApi();
    inv.agents = () =>
      Promise.resolve({
        items: [{ ...AGENT, full_name: null, phone: null, matricule: null }],
        can_edit: false,
        can_see_names: false,
        can_export_names: false,
      });
    renderApp(<InventoryPage />, { api: fakeApi(inv), auth: fakeAuth(claims(["field_commander"], "61")), lang: "ar" });
    fireEvent.click(await screen.findByRole("tab", { name: "الأعوان" }));
    expect(await screen.findByText("الأسماء والهواتف مخفية: تظهر لقاعات العمليات وحدها.")).toBeInTheDocument();
    expect(screen.getByText("اسم مخفي")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "الهاتف" })).not.toBeInTheDocument();
    expect(screen.getByText("دون الأسماء والهواتف، والتصدير مسجَّل.")).toBeInTheDocument();
  });

  it("checks an import before saving it with a reason", async () => {
    const inv = fakeInventoryApi();
    renderApp(<InventoryPage />, { api: fakeApi(inv), auth: fakeAuth(claims(["ops_manager"], "61")), lang: "ar" });
    fireEvent.click(await screen.findByRole("tab", { name: "الاستيراد" }));
    const file = new File(["x"], "sfax.xlsx");
    fireEvent.change(screen.getByLabelText("الملف (xlsx أو CSV)"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "معاينة" }));
    const summary = await screen.findByRole("table", { name: /ما في الملف/ });
    expect(within(summary).getByRole("row", { name: /الآليات/ })).toHaveTextContent(/2\s*1\s*0/);
    expect(screen.getByText(/سنة غير صالحة/)).toBeInTheDocument();
    expect(inv.importInventory).toHaveBeenCalledWith(file, null, null, false);
    fireEvent.change(screen.getByLabelText("سبب التغيير"), { target: { value: "التحميل الأول" } });
    fireEvent.click(screen.getByRole("button", { name: "حفظ في السجل" }));
    await waitFor(() => expect(inv.importInventory).toHaveBeenCalledWith(file, null, null, true, "التحميل الأول"));
  });
});

