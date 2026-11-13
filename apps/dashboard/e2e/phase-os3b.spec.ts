/**
 * OS3 follow-ups in the browser (docs/phase-os3/design-os3b.md): the orders sent to the crews and the turnout per
 * unit on the coverage page, the neighbouring units for the central room, the monthly report of the fleet with the
 * cost of maintenance, and the same data as optional layers of the official map. Screenshots for the phase report
 * land in test-results/phase-os3b/.
 */
import { expect, test, type Page } from "@playwright/test";
import { makeSettings } from "../src/test/phase9Fixtures";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-os3b";

// ┏━━ SIMULATION ━━ Béja with a neighbouring unit of Jendouba, two orders to the crews and a six-month report
// ┃ PRODUCTION: GET /api/v1/staff/coverage, /coverage/orders and /inventory/fleet-report answer from the register,
// ┃ the vehicles' log, the missions (measured turnout) and the routing engine.
// ┗━━━━━━━━━━━━━━━━
function cell(minutes: number | null, target: number, baseline: boolean, unit: string | null, neighbour = false) {
  return { minutes, target, covered: minutes !== null && minutes <= target, baseline_covered: baseline, unit_name: unit, neighbour };
}

const PLACES = [
  { id: 1, name_ar: "باجة الشمالية", name_fr: "Béja Nord", population: 62000, zone: "urban", lat: 36.73, lon: 9.18 },
  { id: 2, name_ar: "مجاز الباب", name_fr: "Medjez el-Bab", population: 44000, zone: "periurban", lat: 36.65, lon: 9.61 },
  { id: 3, name_ar: "عمدون", name_fr: "Amdoun", population: 24000, zone: "rural", lat: 36.8, lon: 9.08 },
  { id: 4, name_ar: "نفزة", name_fr: "Nefza", population: 41000, zone: "rural", lat: 36.97, lon: 9.07 },
  { id: 5, name_ar: "تبرسق", name_fr: "Testour", population: 29000, zone: "rural", lat: 36.55, lon: 9.44 },
];

const MEDICAL: Record<number, ReturnType<typeof cell>> = {
  1: cell(7, 10, true, "وحدة باجة"),
  2: cell(13, 15, true, "وحدة مجاز الباب"),
  3: cell(19, 25, false, "وحدة بوسالم (جندوبة)", true),
  4: cell(34, 25, true, "وحدة باجة"),
  5: cell(21, 25, true, "وحدة مجاز الباب"),
};

const UNITS = [
  { id: "u-1", name_ar: "وحدة باجة", name_fr: "Béja", lat: 36.725, lon: 9.185, gouvernorat_code: 31, neighbour: false, turnout_minutes: 1.6, turnout_source: "measured", turnout_missions: 214, turnout_p90_minutes: 3.1 },
  { id: "u-2", name_ar: "وحدة مجاز الباب", name_fr: "Medjez el-Bab", lat: 36.65, lon: 9.6, gouvernorat_code: 31, neighbour: false, turnout_minutes: 2.4, turnout_source: "measured", turnout_missions: 96, turnout_p90_minutes: 4.8 },
  { id: "u-3", name_ar: "وحدة نفزة", name_fr: "Nefza", lat: 36.97, lon: 9.07, gouvernorat_code: 31, neighbour: false, turnout_minutes: 2, turnout_source: "default", turnout_missions: 7, turnout_p90_minutes: null },
  { id: "u-9", name_ar: "وحدة بوسالم", name_fr: "Bou Salem", lat: 36.61, lon: 8.97, gouvernorat_code: 32, neighbour: true, turnout_minutes: 1.9, turnout_source: "measured", turnout_missions: 120, turnout_p90_minutes: 3.6 },
].map((u) => ({ ...u, ready: { medical: u.id === "u-3" ? 0 : 1, road: 1, fire: 1, rescue: 0 }, hosted: 0 }));

const COVERAGE = {
  gouvernorat_code: 31,
  engine: "valhalla",
  turnout_minutes: 2,
  turnout_mode: "measured",
  neighbours: true,
  neighbour_m: 40000,
  targets: {
    medical: { urban: 10, periurban: 15, rural: 25 },
    road: { urban: 12, periurban: 18, rural: 30 },
    fire: { urban: 10, periurban: 15, rural: 25 },
    rescue: { urban: 15, periurban: 20, rural: 35 },
  },
  families: [
    { family: "medical", population: 200000, covered_population: 159000, covered_pct: 79.5, baseline_pct: 88, ready: 2, fleet: 4, out: 2, own_pct: 67.5 },
    { family: "road", population: 200000, covered_population: 176000, covered_pct: 88, baseline_pct: 88, ready: 3, fleet: 3, out: 0, own_pct: 88 },
    { family: "fire", population: 200000, covered_population: 150000, covered_pct: 75, baseline_pct: 82, ready: 3, fleet: 4, out: 1, own_pct: 71 },
    { family: "rescue", population: 200000, covered_population: 120000, covered_pct: 60, baseline_pct: 60, ready: 0, fleet: 1, out: 1, own_pct: 60 },
  ],
  delegations: PLACES.map((p) => ({
    ...p,
    families: { medical: MEDICAL[p.id], road: cell(9, 12, true, "وحدة باجة"), fire: cell(12, 10, true, "وحدة باجة"), rescue: cell(null, 15, false, null) },
  })),
  units: UNITS,
  alerts: [{ family: "medical", delegation_id: 4, delegation: "نفزة", population: 41000, minutes: 34, target: 25, baseline_minutes: 11 }],
  suggestions: [
    {
      family: "medical",
      vehicle_id: "v-9",
      label: "إسعاف بوسالم 2",
      from_unit_id: "u-9",
      from_unit: "وحدة بوسالم",
      to_unit_id: "u-3",
      to_unit: "وحدة نفزة",
      gain_population: 41000,
      newly_covered: ["نفزة"],
      lost: [],
      version: 3,
      from_gouvernorat_code: 32,
    },
  ],
  computed_at: "2026-11-13T08:00:00Z",
  assumptions: [],
};

function order(id: string, label: string, state: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    resource_id: `v-${id}`,
    label,
    plate: null,
    kind: "reinforce",
    from_unit_id: "u-1",
    from_unit: "وحدة باجة",
    to_unit_id: "u-3",
    to_unit: "وحدة نفزة",
    from_point: [9.185, 36.725],
    to_point: [9.07, 36.97],
    gouvernorat_code: 31,
    host_gouvernorat_code: 31,
    note: null,
    gain_population: 41000,
    leader_name: "رئيس الفريق علي",
    pushed: true,
    created_by_name: "قاعة باجة",
    created_at: "2026-11-13T07:40:00Z",
    seen_at: null,
    seen_by_name: null,
    departed_at: null,
    arrived_at: null,
    closed_at: null,
    close_reason: null,
    state,
    overdue: false,
    ...extra,
  };
}

const ORDERS = [
  order("1", "إسعاف باجة 3", "departed", { seen_at: "2026-11-13T07:41:00Z", seen_by_name: "علي", departed_at: "2026-11-13T07:43:00Z" }),
  order("2", "إسعاف مجاز 1", "sent", { from_unit: "وحدة مجاز الباب", from_point: [9.6, 36.65], to_unit: "وحدة باجة", to_point: [9.185, 36.725], overdue: true, created_at: "2026-11-13T07:52:00Z" }),
];

function series(base: number) {
  return ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"].map((month, i) => ({
    month,
    readiness_pct: Math.min(99, base + ([-6, -3, -8, 1, -2, 0][i] ?? 0)),
    cost_total: (1800 + i * 420 + base * 3).toFixed(3),
  }));
}

function row(code: number, ar: string, fr: string, point: [number, number], vehicles: number, pct: number, cost: number) {
  return {
    gouvernorat_code: code,
    name_ar: ar,
    name_fr: fr,
    point,
    vehicles,
    vehicle_days: vehicles * 13,
    down_days: Math.round(vehicles * 13 * (100 - pct)) / 100,
    readiness_pct: pct,
    workshop_entries: Math.round(vehicles / 4),
    retired: code === 61 ? 1 : 0,
    cost_parts: (cost * 0.6).toFixed(3),
    cost_labour: (cost * 0.3).toFixed(3),
    cost_external: (cost * 0.1).toFixed(3),
    cost_total: cost.toFixed(3),
    cost_per_vehicle: (cost / vehicles).toFixed(3),
    series: series(pct),
  };
}

const ROWS = [
  row(11, "تونس", "Tunis", [10.17, 36.8], 48, 91.4, 14250),
  row(31, "باجة", "Béja", [9.25, 36.72], 17, 83.2, 6120.5),
  row(32, "جندوبة", "Jendouba", [8.75, 36.5], 19, 78.6, 7480),
  row(61, "صفاقس", "Sfax", [10.6, 34.75], 41, 88.1, 11900),
];

const REPORT = {
  month: "2026-11",
  months: ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"],
  rows: ROWS,
  total: { ...row(0, "المجموع", "Total", [0, 0], 125, 87.3, 39750.5), point: null },
  costly: [
    { resource_id: "v-1", label: "إطفاء جندوبة 2", plate: "212 تونس 5531", gouvernorat_code: 32, cost_total: "3240.000", stays: 1 },
    { resource_id: "v-2", label: "إسعاف باجة 3", plate: "198 تونس 1120", gouvernorat_code: 31, cost_total: "1980.500", stays: 2 },
  ],
  red_below: 80,
  amber_below: 85,
  computed_at: "2026-11-13T08:00:00Z",
};

const EVENTS = [
  {
    id: "e-1",
    resource_id: "v-2",
    label: "إسعاف باجة 3",
    plate: "198 تونس 1120",
    unit_name: "وحدة باجة",
    gouvernorat_code: 31,
    kind: "maintenance_end",
    from_state: "maintenance",
    to_state: "ready",
    details: { note: "تغيير المكابح" },
    created_by_name: "إدارة الصيانة",
    created_at: "2026-11-12T15:00:00Z",
    maint_kind: "repair",
    cost_parts: "1240.500",
    cost_labour: "180.000",
    cost_external: null,
    invoice_ref: "ف-2026-311",
    cost_by_name: "إدارة الصيانة",
    cost_at: "2026-11-12T15:00:00Z",
  },
  {
    id: "e-2",
    resource_id: "v-3",
    label: "إطفاء باجة 1",
    plate: "201 تونس 4410",
    unit_name: "وحدة باجة",
    gouvernorat_code: 31,
    kind: "maintenance_end",
    from_state: "maintenance",
    to_state: "ready",
    details: {},
    created_by_name: "إدارة الصيانة",
    created_at: "2026-11-11T10:00:00Z",
  },
];

async function mockApi(page: Page) {
  await baseMock(page);
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    if (pathname === "/api/v1/staff/settings") return json(route, { items: makeSettings(false), thresholds: [] });
    if (pathname === "/api/v1/staff/coverage") return json(route, COVERAGE);
    if (pathname === "/api/v1/staff/coverage/orders") return json(route, { items: ORDERS, ack_minutes: 2 });
    if (pathname === "/api/v1/staff/inventory/fleet-report") return json(route, REPORT);
    if (pathname === "/api/v1/staff/inventory/vehicles")
      return json(route, { items: [], can_edit: true, can_set_state: false, can_maintain: true });
    if (pathname === "/api/v1/staff/inventory/vehicle-events") return json(route, { items: EVENTS });
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    return json(route, method === "GET" ? { items: [], next_cursor: null } : { detail: "not_found" }, method === "GET" ? 200 : 404);
  });
}

test.describe("OS3 follow-ups: crews, turnout, cost, neighbours, official map", () => {
  test.use({ viewport: { width: 1280, height: 1800 } });
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("the central room follows the orders, the turnout and the neighbouring units", async ({ page }) => {
    await signIn(page, ["operator"], "القاعة المركزية");
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/coverage");
    await expect(page.getByRole("heading", { level: 1, name: "التغطية الحية وإعادة التمركز" })).toBeVisible();
    await page.getByRole("checkbox", { name: "احتساب وحدات الولايات المجاورة" }).check();
    await expect(page.getByText(/لم يطّلع الطاقم بعد 2 د/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "زمن الخروج لكل وحدة" })).toBeVisible();
    await expect(page.getByText(/تعزيز بين ولايتين/)).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os3b-coverage.png`, fullPage: true });
  });

  test("the maintenance directorate reads the monthly report and the cost of the stays", async ({ page }) => {
    await signIn(page, ["maintenance_officer"], "إدارة الصيانة");
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/fleet/report");
    await expect(page.getByRole("heading", { name: /آخر 6 أشهر/ })).toBeVisible();
    await expect(page.getByRole("row", { name: /جندوبة/ })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os3b-report.png`, fullPage: true });
    await page.goto("/fleet/log");
    await expect(page.getByText(/الكلفة .* \(إصلاح عطب\)/)).toBeVisible();
    await page.getByRole("button", { name: "إضافة الكلفة" }).click();
    await expect(page.getByLabel("قطع الغيار (د)")).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os3b-cost.png` });
  });

  test("the official map shows the coverage, the orders and the readiness as layers", async ({ page }) => {
    await signIn(page, ["operator"], "القاعة المركزية");
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/map");
    await page.getByRole("button", { name: /موارد الحماية المدنية/ }).click();
    await page.getByRole("checkbox", { name: "طبقة التغطية الحية" }).check();
    await page.getByRole("checkbox", { name: "طبقة أوامر التمركز والوسائل في تعزيز" }).check();
    await page.getByRole("checkbox", { name: "طبقة جاهزية الأسطول حسب الولاية" }).check();
    await expect(page.getByRole("button", { name: /نفزة: فقدت التغطية/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /باجة: جاهزية/ })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os3b-map.png` });
    await page.getByRole("checkbox", { name: "طبقة التغطية الحية" }).uncheck();
    await expect(page.getByRole("button", { name: /نفزة: فقدت التغطية/ })).toHaveCount(0);
  });
});
