/**
 * OS3 in the browser (docs/phase-os3/design-os3.md): the fleet and its maintenance, the live coverage with the
 * repositioning, and the access profiles of the system administrator. Screenshots for the phase report land in
 * test-results/phase-os3/.
 */
import { expect, test, type Page } from "@playwright/test";
import { makeSettings } from "../src/test/phase9Fixtures";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-os3";

// ┏━━ SIMULATION ━━ a gouvernorat of three units and five délégations, its vehicles and the coverage computed on them
// ┃ PRODUCTION: GET /api/v1/staff/inventory/vehicles, /inventory/vehicle-events and /coverage answer from the register,
// ┃ the routing engine and the SNACR targets.
// ┗━━━━━━━━━━━━━━━━
const UNITS = [
  { id: "u-1", name_ar: "وحدة صفاقس المدينة", name_fr: "Sfax Ville", lat: 34.74, lon: 10.76 },
  { id: "u-2", name_ar: "وحدة عقارب", name_fr: "Agareb", lat: 34.74, lon: 10.53 },
  { id: "u-3", name_ar: "وحدة جبنيانة", name_fr: "Jebiniana", lat: 35.03, lon: 10.91 },
];

function vehicle(id: string, label: string, state: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    unit_id: "u-1",
    unit_name: "وحدة صفاقس المدينة",
    gouvernorat_code: 61,
    category_key: null,
    kind: "ambulance",
    label,
    code: `SF-${id}`,
    specs: {},
    state,
    year: 2019,
    notes: null,
    plate: `${120 + Number(id) * 13} تونس ${3000 + Number(id) * 271}`,
    odometer_km: 40000 + Number(id) * 9300,
    version: 2,
    updated_at: "2026-11-11T07:30:00Z",
    ...extra,
  };
}

const VEHICLES = [
  vehicle("1", "إسعاف 1", "ready"),
  vehicle("2", "إسعاف 2", "assigned"),
  vehicle("3", "إسعاف 3", "reinforcement", { stationed_unit_id: "u-2", stationed_unit_name: "وحدة عقارب" }),
  vehicle("4", "إطفاء 1", "broken", { kind: "fire_engine", fault: "تسرب في المضخة" }),
  vehicle("5", "إطفاء 2", "maintenance", {
    kind: "fire_engine",
    workshop: "الورشة الجهوية بصفاقس",
    maint_reason: "تغيير الفرامل",
    maint_until: "2026-11-20",
  }),
  vehicle("6", "إنقاذ 1", "ready", { kind: "rescue_truck", unit_id: "u-3", unit_name: "وحدة جبنيانة" }),
  vehicle("7", "إسعاف قديم", "retired", { retired_on: "2026-09-30", retire_decision: "قرار 2026-41", retire_reason: "تجاوز العمر الافتراضي" }),
];

const EVENTS = [
  {
    id: "e-1",
    resource_id: "3",
    label: "إسعاف 3",
    plate: "137 تونس 4066",
    unit_name: "وحدة صفاقس المدينة",
    gouvernorat_code: 61,
    kind: "reinforce",
    from_state: "ready",
    to_state: "reinforcement",
    details: { host: "وحدة عقارب", suggested_gain: 41200 },
    created_by_name: "رئيس القاعة الجهوية",
    created_at: "2026-11-11T07:10:00Z",
  },
  {
    id: "e-2",
    resource_id: "5",
    label: "إطفاء 2",
    plate: "137 تونس 4077",
    unit_name: "وحدة صفاقس المدينة",
    gouvernorat_code: 61,
    kind: "maintenance_start",
    from_state: "broken",
    to_state: "maintenance",
    details: { workshop: "الورشة الجهوية بصفاقس", reason: "تغيير الفرامل" },
    created_by_name: "إدارة الصيانة",
    created_at: "2026-11-10T15:00:00Z",
  },
];

const PLACES = [
  { id: 1, name_ar: "صفاقس المدينة", name_fr: "Sfax Ville", population: 110000, zone: "urban", lat: 34.74, lon: 10.76 },
  { id: 2, name_ar: "ساقية الزيت", name_fr: "Sakiet Ezzit", population: 98000, zone: "urban", lat: 34.8, lon: 10.75 },
  { id: 3, name_ar: "عقارب", name_fr: "Agareb", population: 41200, zone: "rural", lat: 34.74, lon: 10.53 },
  { id: 4, name_ar: "جبنيانة", name_fr: "Jebiniana", population: 46000, zone: "periurban", lat: 35.03, lon: 10.91 },
  { id: 5, name_ar: "بئر علي بن خليفة", name_fr: "Bir Ali", population: 53000, zone: "rural", lat: 34.74, lon: 10.1 },
];

function cell(minutes: number | null, target: number, baseline: boolean, unit: string | null) {
  return { minutes, target, covered: minutes !== null && minutes <= target, baseline_covered: baseline, unit_name: unit };
}

const COVERAGE = {
  gouvernorat_code: 61,
  engine: "fallback",
  turnout_minutes: 2,
  targets: {
    medical: { urban: 10, periurban: 15, rural: 25 },
    road: { urban: 12, periurban: 18, rural: 30 },
    fire: { urban: 10, periurban: 15, rural: 25 },
    rescue: { urban: 15, periurban: 20, rural: 35 },
  },
  families: [
    { family: "medical", population: 348200, covered_population: 254000, covered_pct: 72.9, baseline_pct: 84.7, ready: 1, fleet: 3, out: 2 },
    { family: "road", population: 348200, covered_population: 254000, covered_pct: 72.9, baseline_pct: 84.7, ready: 1, fleet: 3, out: 2 },
    { family: "fire", population: 348200, covered_population: 208000, covered_pct: 59.7, baseline_pct: 84.7, ready: 0, fleet: 2, out: 2 },
    { family: "rescue", population: 348200, covered_population: 295000, covered_pct: 84.7, baseline_pct: 84.7, ready: 1, fleet: 1, out: 0 },
  ],
  delegations: PLACES.map((p) => ({
    ...p,
    families: {
      medical:
        p.id === 3
          ? cell(23, 25, true, "وحدة عقارب")
          : p.id === 4
            ? cell(31, 15, true, "وحدة صفاقس المدينة")
            : p.id === 5
              ? cell(48, 25, false, "وحدة عقارب")
              : cell(6, 10, true, "وحدة صفاقس المدينة"),
      road: cell(8, 12, true, "وحدة صفاقس المدينة"),
      fire: p.id <= 2 ? cell(null, 10, true, null) : cell(null, 25, p.id !== 5, null),
      rescue: cell(p.id === 5 ? 52 : 14, p.id === 5 ? 35 : 15, p.id !== 5, "وحدة جبنيانة"),
    },
  })),
  units: UNITS.map((u) => ({
    ...u,
    ready: { medical: u.id === "u-1" ? 1 : u.id === "u-2" ? 1 : 0, road: 0, fire: 0, rescue: u.id === "u-3" ? 1 : 0 },
    hosted: u.id === "u-2" ? 1 : 0,
  })),
  alerts: [
    { family: "medical", delegation_id: 4, delegation: "جبنيانة", population: 46000, minutes: 31, target: 15, baseline_minutes: 9 },
  ],
  suggestions: [
    {
      family: "medical",
      vehicle_id: "1",
      label: "إسعاف 1",
      from_unit_id: "u-1",
      from_unit: "وحدة صفاقس المدينة",
      to_unit_id: "u-3",
      to_unit: "وحدة جبنيانة",
      gain_population: 46000,
      newly_covered: ["جبنيانة"],
      lost: [],
      version: 2,
    },
  ],
  computed_at: "2026-11-11T08:00:00Z",
  assumptions: [],
};

const FEATURES = [
  { key: "fleet", kind: "page", names: { ar: "الأسطول والصيانة", fr: "Parc", en: "Fleet" }, parent: null, group: "fleet", nav: "/fleet", flags: [], roles: [], act_as: null, grantable: true, routes: [] },
  { key: "personnel", kind: "page", names: { ar: "الأعوان", fr: "Personnel", en: "Personnel" }, parent: null, group: "people", nav: "/personnel", flags: [], roles: [], act_as: null, grantable: true, routes: [] },
  { key: "inspections", kind: "page", names: { ar: "التفقديات", fr: "Inspections", en: "Inspections" }, parent: null, group: "people", nav: "/inspections", flags: [], roles: [], act_as: null, grantable: true, routes: [] },
  { key: "coverage", kind: "page", names: { ar: "التغطية الحية", fr: "Couverture", en: "Coverage" }, parent: null, group: "ops", nav: "/coverage", flags: [], roles: [], act_as: null, grantable: true, routes: [] },
];

function profile(id: string, name: string, description: string, page: string, mode: string, builtin: boolean, used: number) {
  const f = FEATURES.find((x) => x.key === page);
  return {
    id,
    name,
    description,
    builtin,
    items: [{ page, mode, known: true, names: f?.names ?? null, features: [page] }],
    active_assignments: used,
    updated_at: "2026-11-11T08:00:00Z",
  };
}

const PROFILES = [
  profile("p-1", "اطلاع على الوسائل", "الأسطول والأعطاب والصيانة والأرشيف، دون تصرف", "fleet", "read", true, 1),
  profile("p-2", "اطلاع على الأفراد", "قائمة الأعوان والغيابات والموجود العام، دون تصرف", "personnel", "read", true, 1),
  profile("p-3", "اطلاع على التفقديات", "المهمات والمحاضر والحسابات، دون تصرف", "inspections", "read", true, 0),
];

const ASSIGNMENTS = [
  {
    id: "a-1",
    profile_id: "p-1",
    target_kind: "user",
    target: "kc-inspector",
    target_name: "المتفقد العام",
    gouvernorat_code: null,
    reason: "متابعة جاهزية الأسطول",
    starts_at: null,
    ends_at: null,
    created_by_name: "مدير النظام",
    created_at: "2026-11-11T08:00:00Z",
    state: "active",
    features: ["fleet"],
  },
  {
    id: "a-2",
    profile_id: "p-2",
    target_kind: "role",
    target: "operator",
    target_name: null,
    gouvernorat_code: null,
    reason: "اطلاع القاعات على الموجود العام",
    starts_at: null,
    ends_at: null,
    created_by_name: "مدير النظام",
    created_at: "2026-11-11T08:00:00Z",
    state: "active",
    features: ["personnel"],
  },
];

async function mockApi(page: Page) {
  await baseMock(page);
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    if (pathname === "/api/v1/staff/settings") return json(route, { items: makeSettings(false), thresholds: [] });
    if (pathname === "/api/v1/staff/inventory/vehicles")
      return json(route, { items: VEHICLES, can_edit: true, can_set_state: false, can_maintain: true });
    if (pathname === "/api/v1/staff/inventory/vehicle-events") return json(route, { items: EVENTS });
    if (pathname === "/api/v1/staff/inventory/catalogue") return json(route, { items: [], can_manage: false });
    if (pathname === "/api/v1/staff/inventory/units") return json(route, { items: [] });
    if (pathname === "/api/v1/staff/coverage") return json(route, COVERAGE);
    if (pathname === "/api/v1/staff/features/catalogue") return json(route, FEATURES);
    if (pathname === "/api/v1/staff/features/profiles") return json(route, PROFILES);
    if (pathname === "/api/v1/staff/features/profile-assignments") return json(route, ASSIGNMENTS);
    if (pathname === "/api/v1/staff/features/rules") return json(route, []);
    if (pathname === "/api/v1/staff/features/preview") return json(route, []);
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    return json(route, method === "GET" ? { items: [], next_cursor: null } : { detail: "not_found" }, method === "GET" ? 200 : 404);
  });
}

test.describe("OS3: fleet, live coverage and access profiles", () => {
  test.use({ viewport: { width: 1280, height: 1600 } });
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("the maintenance directorate reads its fleet and its workshop", async ({ page }) => {
    await signIn(page, ["maintenance_officer"], "إدارة الصيانة");
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/fleet");
    await expect(page.getByRole("heading", { level: 1, name: "الأسطول والصيانة" })).toBeVisible();
    await expect(page.getByText(/تسرب في المضخة|إطفاء 2/).first()).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os3-fleet.png` });
    await page.goto("/fleet/vehicles");
    await expect(page.getByRole("row", { name: /إسعاف 3/ })).toContainText("تنتظر في وحدة عقارب");
    await page.screenshot({ path: `${SHOTS}/os3-vehicles.png` });
    await page.goto("/fleet/maintenance");
    await expect(page.getByText("الورشة الجهوية بصفاقس — تغيير الفرامل")).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os3-maintenance.png` });
  });

  test("the room sees the coverage it lost and the move that brings it back", async ({ page }) => {
    await signIn(page, ["operator"], "قاعة صفاقس", { scope_level: "regional", gouvernorat_code: 61 });
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/coverage");
    await expect(page.getByRole("heading", { level: 1, name: "التغطية الحية وإعادة التمركز" })).toBeVisible();
    await expect(page.getByText(/جبنيانة \(46/)).toBeVisible();
    await expect(page.getByRole("button", { name: "إرسال في تعزيز" })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os3-coverage.png` });
  });

  test("the system administrator grants a read-only profile", async ({ page }) => {
    await signIn(page, ["sysadmin"], "مدير النظام");
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/permissions");
    await expect(page.getByRole("heading", { name: "ملفات الصلاحيات" })).toBeVisible();
    await expect(page.getByText("اطلاع على الوسائل").first()).toBeVisible();
    await page.getByRole("heading", { name: "ملفات الصلاحيات" }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${SHOTS}/os3-profiles.png` });
  });
});
