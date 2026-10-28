// covers: phase R1 (docs/phase-r/design-resources.md §2): the resources register page. The counts that the governor
// and the minister see, the tabs of a room, recording a vehicle with its specifications, the staff names kept to the
// operations rooms, and the import preview before saving. Phase R2 (§2.3): the search across the gouvernorats.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { canListInventory, canOpenInventory } from "../lib/roles";
import { describeSearch } from "../components/ResourceSearchLayer";
import { EMPTY_SEARCH, parseSearch, searchParam } from "../lib/inventory";
import { AGENT, CATALOGUE, FOREIGN_PREVIEW, fakeInventoryApi, MAPPED_PREVIEW, OVERVIEW } from "../test/inventoryFixtures";
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
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["نظرة عامة", "البحث عبر الولايات"]);
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
    fireEvent.change(within(form).getByRole("spinbutton", { name: /السعة/ }), { target: { value: "2000" } });
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
    fireEvent.change(screen.getByLabelText("الملف (xlsx أو CSV أو JSON)"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "معاينة" }));
    const summary = await screen.findByRole("table", { name: /ما في الملف/ });
    expect(within(summary).getByRole("row", { name: /الآليات/ })).toHaveTextContent(/2\s*1\s*0/);
    expect(screen.getByText(/سنة غير صالحة/)).toBeInTheDocument();
    expect(inv.importInventory).toHaveBeenCalledWith(file, null, null, false, "", { profile: null, mapping: {} });
    fireEvent.change(screen.getByLabelText("سبب التغيير"), { target: { value: "التحميل الأول" } });
    fireEvent.click(screen.getByRole("button", { name: "حفظ في السجل" }));
    await waitFor(() =>
      expect(inv.importInventory).toHaveBeenCalledWith(file, null, null, true, "التحميل الأول", { profile: null, mapping: {} }),
    );
  });

  it("searches every gouvernorat for fire engines of 2000 L or more", async () => {
    const inv = fakeInventoryApi();
    renderApp(<InventoryPage />, { api: fakeApi(inv), auth: fakeAuth(claims(["minister"])), lang: "ar" });
    fireEvent.click(await screen.findByRole("tab", { name: "البحث عبر الولايات" }));
    fireEvent.change(await screen.findByLabelText("الصنف"), { target: { value: "fire_engine" } });
    fireEvent.change(screen.getByLabelText("السعة (L): من"), { target: { value: "2000" } });
    fireEvent.click(screen.getByLabelText("الآليات الجاهزة فقط"));
    fireEvent.click(screen.getByRole("button", { name: "بحث" }));
    const table = await screen.findByRole("table", { name: "نتيجة البحث حسب الولاية" });
    expect(inv.searchInventory).toHaveBeenCalledWith(
      { ...EMPTY_SEARCH, category: "fire_engine", specs: { capacity_l: [2000, null] }, ready_only: true },
      expect.anything(),
    );
    // Bizerte has none: left out of the table; the units of a gouvernorat sit under its name.
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getByRole("row", { name: /تونس/ })).toHaveTextContent("وحدة باب سعدون");
    expect(screen.getByText(/في 2 ولاية/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "تصدير النتيجة (CSV)" }));
    await waitFor(() => expect(inv.exportSearch).toHaveBeenCalled());
    // The minister reads the counts here; the live map is the rooms' screen.
    expect(screen.queryByRole("button", { name: "عرض على الخريطة" })).not.toBeInTheDocument();
    expect(screen.getByText(/الخريطة الحية خاصة بقاعات العمليات/)).toBeInTheDocument();
  });
});

describe("resources search on the map", () => {
  it("travels in the address and reads back in words", () => {
    const q = { ...EMPTY_SEARCH, category: "fire_engine", specs: { capacity_l: [2000, null] as [number, null], four_wd: true } };
    expect(parseSearch(searchParam(q))).toEqual(q);
    expect(parseSearch("{\"what\":\"drones\"}")).toBeNull();
    expect(parseSearch("not json")).toBeNull();
    const t = (key: string, o?: Record<string, unknown>) => `${key}${o ? JSON.stringify(o) : ""}`;
    expect(describeSearch(q, CATALOGUE.items[0], "ar", t, String)).toBe(
      'شاحنة إطفاء · map.resourceSearch.atLeast{"spec":"السعة","value":"\u20682000 L\u2069"} · دفع رباعي',
    );
  });
});

// Phase R3: a transfer between gouvernorats sent by one room and decided by the other; equipment on a vehicle.
describe("inventory R3", () => {
  it("sends a transfer and accepts the incoming one with its new unit", async () => {
    const inv = fakeInventoryApi();
    renderApp(<InventoryPage />, { api: fakeApi(inv), auth: fakeAuth(claims(["ops_manager"], "61")), lang: "ar" });
    fireEvent.click(await screen.findByRole("tab", { name: "الأعوان" }));
    const incoming = (await screen.findByText("[SIM] منير الإطفائي")).closest("li") as HTMLElement;
    expect(within(incoming).getByText("بانتظار القرار")).toBeInTheDocument();
    const accept = within(incoming).getByRole("button", { name: "قبول النقلة" });
    expect(accept).toBeDisabled();
    fireEvent.change(within(incoming).getByLabelText("الوحدة الجديدة"), { target: { value: "u-1" } });
    fireEvent.click(accept);
    await waitFor(() => expect(inv.acceptTransfer).toHaveBeenCalledWith("t-1", "u-1", ""));

    fireEvent.click(screen.getByRole("button", { name: "نقلة سامي الغواص" }));
    const form = screen.getByRole("form", { name: "نقلة سامي الغواص إلى ولاية أخرى" });
    fireEvent.change(within(form).getByLabelText("الولاية المستقبلة"), { target: { value: "11" } });
    fireEvent.change(within(form).getByLabelText("سبب التغيير"), { target: { value: "[SIM] تعزيز وحدة الغوص" } });
    fireEvent.click(within(form).getByRole("button", { name: "حفظ" }));
    await waitFor(() =>
      expect(inv.requestTransfer).toHaveBeenCalledWith("a-1", { to_gouvernorat: 11, effective_on: null, reason: "[SIM] تعزيز وحدة الغوص" }),
    );
  });

  it("puts equipment on a vehicle of its unit", async () => {
    const inv = fakeInventoryApi();
    renderApp(<InventoryPage />, { api: fakeApi(inv), auth: fakeAuth(claims(["ops_manager"], "61")), lang: "ar" });
    fireEvent.click(await screen.findByRole("tab", { name: "المعدات" }));
    expect(await screen.findByText("في الوحدة")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "معدات جديدة" }));
    const form = screen.getByRole("form", { name: "معدات جديدة" });
    fireEvent.change(within(form).getByLabelText("الوحدة"), { target: { value: "u-1" } });
    fireEvent.change(within(form).getByLabelText("الصنف"), { target: { value: "pump" } });
    await waitFor(() => expect(within(form).getByRole("option", { name: /إطفاء 12/ })).toBeInTheDocument());
    fireEvent.change(within(form).getByLabelText("محمولة على"), { target: { value: "v-1" } });
    fireEvent.click(within(form).getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(inv.saveStock).toHaveBeenCalledWith(null, expect.objectContaining({ unit_id: "u-1", vehicle_id: "v-1" })));
  });

  // Phase R4b: a JSON file with its own columns, mapped from lists, then kept as a profile.
  it("maps the columns of a foreign JSON file from lists and keeps the mapping", async () => {
    const inv = fakeInventoryApi();
    inv.importInventory = vi.fn().mockResolvedValueOnce(FOREIGN_PREVIEW).mockResolvedValue(MAPPED_PREVIEW);
    renderApp(<InventoryPage />, { api: fakeApi(inv), auth: fakeAuth(claims(["ops_manager"], "61")), lang: "ar" });
    fireEvent.click(await screen.findByRole("tab", { name: "الاستيراد" }));
    const file = new File(["[]"], "unit.json");
    fireEvent.change(screen.getByLabelText("الملف (xlsx أو CSV أو JSON)"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("الملف يحتوي"), { target: { value: "stock" } });
    expect(await screen.findByRole("option", { name: "[SIM] ملف وحدة صفاقس" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "معاينة" }));
    const table = await screen.findByRole("table", { name: "المعدات" });
    fireEvent.change(within(table).getByRole("combobox", { name: "الوحدة الأصلية" }), { target: { value: "unit" } });
    fireEvent.change(within(table).getByRole("combobox", { name: "النوع" }), { target: { value: "category" } });
    fireEvent.change(within(table).getByRole("combobox", { name: "العدد" }), { target: { value: "qty_ready" } });
    // A field already chosen for one column is not offered for another.
    expect(within(within(table).getByRole("combobox", { name: "العدد" })).getByRole("option", { name: "الوحدة" })).toBeDisabled();
    const mapping = { stock: { "الوحدة الأصلية": "unit", "النوع": "category", "العدد": "qty_ready" } };
    fireEvent.click(screen.getByRole("button", { name: "إعادة المعاينة بهذا الربط" }));
    await waitFor(() => expect(inv.importInventory).toHaveBeenLastCalledWith(file, null, "stock", false, "", { profile: null, mapping }));
    fireEvent.change(screen.getByLabelText("حفظ الربط باسم"), { target: { value: "ملف الوحدة" } });
    fireEvent.click(screen.getByRole("button", { name: "حفظ النموذج" }));
    await waitFor(() => expect(inv.saveImportProfile).toHaveBeenCalledWith({ name: "ملف الوحدة", mapping, shared: false }));
  });
});
