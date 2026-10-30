// covers: phase S (docs/phase-s/design-s.md §2): the strategies menu (its pages also kept in their own groups, the
// items the national system administrator adds), and the SNACR page: indicators, matrix, specific risks, plan.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { navGroups } from "../components/Navigation";
import { identityFromClaims } from "../auth/identity";
import type { SnacrAnalysis, SnacrOverview, SnacrPlanSummary } from "../lib/snacr";
import type { StrategyItem } from "../lib/strategies";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { SnacrPage } from "./SnacrPage";
import { StrategiesPage, StrategyItemPage } from "./StrategiesPage";

vi.mock("../components/LazyMap", () => ({ LazyMapView: () => <div data-testid="map" /> }));

const claims = (roles: string[], gouvernorat?: string) => ({
  sub: `u-${roles[0]}`,
  name: "Test",
  realm_access: { roles },
  ...(gouvernorat ? { gouvernorat_code: gouvernorat } : { scope_level: "national" }),
});

const ITEM: StrategyItem = {
  key: "snrrc_2030",
  name: { ar: "[SIM] الاستراتيجية الوطنية للحد من مخاطر الكوارث", fr: "[SIM] SNRRC 2030", en: "[SIM] NDRR strategy" },
  summary: { ar: "المحاور والأهداف إلى 2030" },
  body: { ar: "## المحاور\n\n1. فهم المخاطر" },
  link: null,
  icon: "policy",
  tone: "teal",
  roles: [],
  position: 10,
  active: true,
  updated_by_name: "مدير النظام",
  updated_at: "2026-10-30T09:00:00Z",
};

describe("the strategies menu", () => {
  it("gathers the strategies and keeps each page in its own group", () => {
    const identity = identityFromClaims(claims(["central_committee"]));
    const t = ((k: string) => k) as never;
    const groups = navGroups(identity, t, undefined, false, [
      { to: "/strategies/snrrc_2030", icon: "policy", tone: "teal", label: "SNRRC" },
      { to: "/plans", icon: "menuBook", tone: "sky", label: "twice" },
    ]);
    const of = (key: string) => groups.find((g) => g.key === key)?.items.map((i) => i.to) ?? [];
    expect(of("strategies")).toEqual(["/strategies", "/snacr", "/plans", "/programmes", "/memory", "/strategies/snrrc_2030"]);
    expect(of("crisis")).toContain("/plans");
    expect(of("crisis")).toContain("/programmes");
    expect(of("knowledge")).toContain("/memory");
    const operator = navGroups(identityFromClaims(claims(["operator"], "21")), t);
    expect(operator.find((g) => g.key === "strategies")?.items.map((i) => i.to)).not.toContain("/snacr");
  });

  it("lets the national system administrator create an item", async () => {
    const api = fakeApi({
      strategyItems: vi.fn(() => Promise.resolve({ items: [ITEM], can_manage: true })),
      saveStrategyItem: vi.fn((key: string) => Promise.resolve({ ...ITEM, key })),
    });
    renderApp(<StrategiesPage />, { api, auth: fakeAuth(claims(["sysadmin"])), lang: "ar", path: "/strategies" });
    expect(await screen.findByText("[SIM] الاستراتيجية الوطنية للحد من مخاطر الكوارث")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "إدارة العناصر" }));
    fireEvent.click(screen.getByRole("button", { name: "إحداث عنصر" }));
    const form = within(screen.getByRole("heading", { name: "إحداث عنصر", level: 3 }).closest("form") as HTMLElement);
    fireEvent.change(form.getByLabelText("المعرّف"), { target: { value: "heat_plan" } });
    fireEvent.change(form.getByLabelText("الاسم (العربية)"), { target: { value: "خطة موجات الحر" } });
    fireEvent.change(form.getByLabelText("الاسم (الفرنسية)"), { target: { value: "Plan canicule" } });
    fireEvent.change(form.getByLabelText("الاسم (الإنجليزية)"), { target: { value: "Heatwave plan" } });
    const save = form.getByRole("button", { name: "حفظ" });
    expect(save).toBeDisabled();
    fireEvent.change(form.getByLabelText("الرابط"), { target: { value: "/programmes" } });
    fireEvent.click(form.getByLabelText("اللجنة الجهوية"));
    fireEvent.click(save);
    await waitFor(() =>
      expect(api.saveStrategyItem).toHaveBeenCalledWith(
        "heat_plan",
        expect.objectContaining({ link: "/programmes", roles: ["governor"], name: { ar: "خطة موجات الحر", fr: "Plan canicule", en: "Heatwave plan" } }),
      ),
    );
  });

  it("shows no management to the other staff", async () => {
    renderApp(<StrategiesPage />, {
      api: fakeApi({ strategyItems: vi.fn(() => Promise.resolve({ items: [ITEM], can_manage: false })) }),
      auth: fakeAuth(claims(["central_committee"])),
      lang: "ar",
      path: "/strategies",
    });
    expect(await screen.findByRole("link", { name: /الاستراتيجية الوطنية/ })).toHaveAttribute("href", "/strategies/snrrc_2030");
    expect(screen.getByRole("link", { name: /تحليل المخاطر وتغطيتها/ })).toHaveAttribute("href", "/snacr");
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });

  it("reads an item on its own page", async () => {
    renderApp(<StrategyItemPage />, {
      api: fakeApi({ strategyItem: vi.fn(() => Promise.resolve(ITEM)) }),
      auth: fakeAuth(claims(["operator"], "21")),
      lang: "ar",
      path: "/strategies/snrrc_2030",
      route: "/strategies/:key",
    });
    expect(await screen.findByRole("heading", { name: "المحاور" })).toBeInTheDocument();
    expect(screen.getByText("المحاور والأهداف إلى 2030")).toBeInTheDocument();
  });
});

const FIG = { rows: 300, completeness_pct: 82, recorded_pct: 85, compliance_pct: 64 };
const OVERVIEW: SnacrOverview = {
  datasets: [2023, 2024, 2025].map((year) => ({
    id: `d${year}`,
    year,
    source: "simulated",
    simulated: true,
    file_name: null,
    rows: 1000,
    quality: { read: 1010 },
    imported_by_name: "النظام",
    imported_at: "2026-10-30T08:00:00Z",
  })),
  default_years: [2023, 2024, 2025],
  method: {
    goal: 90,
    urban: 1000,
    periurban: 150,
    targets: {
      medical: { urban: 10, periurban: 15, rural: 25 },
      road: { urban: 12, periurban: 18, rural: 30 },
      fire: { urban: 10, periurban: 15, rural: 25 },
      rescue: { urban: 15, periurban: 20, rural: 35 },
    },
    review_months: 12,
    validity_years: 5,
  },
  references: [{ code: "US-NFPA-1710", title: "NFPA 1710", use: "percentile_indicators", url: "https://www.nfpa.org" }],
  can_import: true,
  can_edit_national: true,
};
const ANALYSIS: SnacrAnalysis = {
  years: [2023, 2024, 2025],
  codes: [21],
  simulated: true,
  datasets: [],
  method: OVERVIEW.method,
  breaks: [5, 10, 15, 20],
  totals: { ...FIG, unmatched: 4, annual: 1000, population: 900000, rate_per_1000: 1.1 },
  by_year: [],
  gouvernorats: [{ ...FIG, code: 21, unmatched: 4, annual: 1000, rate_per_1000: 1.1, families: { fire: { ...FIG, arrival_p90: 31 } } }],
  delegations: [
    {
      ...FIG,
      id: 2104,
      gouvernorat_code: 21,
      name_ar: "دار شعبان",
      name_fr: "Dar Chaabane",
      population: 60000,
      area_km2: 40,
      zone: "urban",
      annual: 120,
      rate_per_1000: 2,
      frequency_level: 5,
      coverage_level: 4,
      priority: "high",
      families: { medical: { ...FIG, arrival_median: 14, arrival_p90: 29, target: 10 } },
    },
  ],
  matrix: [
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 1, 0],
  ],
  month: { fire: [1, 2, 3, 4, 5, 9, 20, 18, 6, 3, 2, 1] },
  weekday_hour: { fire: Array.from({ length: 7 }, () => Array.from({ length: 24 }, () => 1)) },
  subtypes: { fire: [{ subtype: "بمواد غابية و أعشاب", rows: 40 }] },
  mission: {
    fire: {
      rows: 12,
      returned_pct: 83,
      hospital_rows: 2,
      crew_mean: 4.5,
      turnout_median: 2,
      turnout_p90: 4,
      travel_median: 9,
      travel_p90: 17,
      on_scene_median: 45,
      on_scene_p90: 90,
      transport_median: null,
      transport_p90: null,
      length_median: 75,
      length_p90: 140,
    },
  },
};
const PLAN: SnacrPlanSummary = {
  id: "p1",
  gouvernorat_code: 21,
  version: 1,
  years: [2023, 2024, 2025],
  status: "draft",
  simulated: true,
  created_by_name: "اللجنة الجهوية",
  created_at: "2026-10-30T09:00:00Z",
  approved_by_name: null,
  approved_at: null,
  review_due: null,
  valid_until: null,
  objectives: 6,
  can_approve: true,
};

describe("SnacrPage", () => {
  it("reads the indicators, the matrix and approves the plan of its gouvernorat", async () => {
    const api = fakeApi({
      snacr: vi.fn(() => Promise.resolve({ ...OVERVIEW, can_import: false })),
      snacrAnalysis: vi.fn(() => Promise.resolve(ANALYSIS)),
      snacrPlans: vi.fn(() => Promise.resolve([PLAN])),
      approveSnacrPlan: vi.fn(),
    });
    renderApp(<SnacrPage />, { api, auth: fakeAuth(claims(["local_committee"], "21")), lang: "ar", path: "/snacr" });
    expect(await screen.findByRole("rowheader", { name: "دار شعبان" })).toBeInTheDocument();
    expect(api.snacrAnalysis).toHaveBeenCalledWith([2023, 2024, 2025], null, expect.anything());
    expect(screen.getByText("أولوية عالية")).toBeInTheDocument();
    expect(await screen.findByTestId("map")).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "الأرشيف" })).not.toBeInTheDocument();
    // Phase S2: the whole mission from the rooms' records.
    const mission = screen.getByRole("table", { name: /مراحل المهمة من سجلات القاعات/ });
    expect(within(mission).getByRole("rowheader", { name: "الحرائق" })).toBeInTheDocument();
    expect(within(mission).getByText(/^4[.,]5$/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "مصفوفة الأولويات" }));
    const row = screen.getByRole("rowheader", { name: "تواتر 5" }).closest("tr") as HTMLElement;
    expect(within(row).getAllByRole("cell")[3]).toHaveTextContent("1");

    fireEvent.click(screen.getByRole("tab", { name: "المخطط" }));
    fireEvent.click(await screen.findByRole("button", { name: "اعتماد" }));
    await waitFor(() => expect(api.approveSnacrPlan).toHaveBeenCalledWith("p1"));
    expect(screen.getByRole("button", { name: /إعداد مسودة مخطط ولاية/ })).toBeInTheDocument();
  });

  it("gives the national room the archive and the references", async () => {
    const api = fakeApi({
      snacr: vi.fn(() => Promise.resolve(OVERVIEW)),
      snacrAnalysis: vi.fn(() => Promise.resolve(ANALYSIS)),
      snacrUnmatched: vi.fn(() => Promise.resolve([{ gouvernorat_code: 43, raw: "سيدي بوزيد المدينة", rows: 12 }])),
      simulateSnacr: vi.fn(),
    });
    renderApp(<SnacrPage />, { api, auth: fakeAuth(claims(["ops_manager"])), lang: "ar", path: "/snacr" });
    fireEvent.click(await screen.findByRole("tab", { name: "الأرشيف" }));
    expect(await screen.findByText("سيدي بوزيد المدينة")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("السنة"), { target: { value: "2026" } });
    fireEvent.click(screen.getByRole("button", { name: "توليد سنة 2026 [SIM]" }));
    await waitFor(() => expect(api.simulateSnacr).toHaveBeenCalledWith(2026));
    fireEvent.click(screen.getByRole("button", { name: "بناء سنة 2026 من سجلات القاعات" }));
    await waitFor(() => expect(api.liveSnacr).toHaveBeenCalledWith(2026));

    fireEvent.click(screen.getByRole("tab", { name: "المنهجية والمراجع" }));
    expect(screen.getByRole("link", { name: "NFPA 1710" })).toHaveAttribute("href", "https://www.nfpa.org");
    expect(screen.getByRole("rowheader", { name: "الحرائق" })).toBeInTheDocument();
  });
});
