/**
 * Accessibility of the main screens (phase 10 §6.5, U21): axe-core with the WCAG 2.2 A/AA rules on the production
 * bundle, in French and in Arabic. A violation of impact "serious" or "critical" fails the test; the others are
 * printed so they can be planned.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import {
  AGENT,
  BOUNDARIES,
  CATALOGUE,
  IMPORT_PREVIEW,
  OVERVIEW,
  SEARCH_RESULT,
  STOCK,
  UNITS,
  VEHICLE,
} from "../src/test/inventoryData";
import { BASEMAP, BASEMAP_SETTINGS } from "../src/test/basemapData";
import { fakeFigures, fakeGrid } from "../src/test/libraryCalendarData";
import type { CalendarLevel } from "../src/lib/phase8Types";
import { FEATURE_RULES, FEATURES, NO_FEATURES, PREVIEW } from "../src/test/featuresData";
import {
  WINDOW_ACCESS_FULL,
  WINDOW_COMPARE,
  WINDOW_DELEGATES,
  WINDOW_DELEGATION,
  WINDOW_NOW,
  WINDOW_SAVED,
  WINDOW_SEARCH,
  WINDOW_SUMMARY,
  WINDOW_SYNONYMS,
} from "../src/test/windowData";
import { SCHEDULE_OPTIONS, SCHEDULE_PROGRESS, SCHEDULE_SETTINGS, SCHEDULE_SLOT, SCHEDULE_TEMPLATES } from "../src/test/scheduleData";
import { DIRECTIVE_ALL_DETAIL, DISPATCH_PAGE, HAZARDS, PLAN_DETAIL, PLANS, REVISIONS, SEARCH } from "../src/test/registerData";
import { JENDOUBA_AXIS, NABEUL_AXIS, NABEUL_DETAIL, overview, REQUEST, SOUSSE_AXIS, SUGGESTIONS } from "../src/test/crisisData";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const ROLES = ["operator", "ops_manager", "central_committee", "security_admin", "content_editor", "org_auditor"];

const SCREENS: { path: string; ready: string }[] = [
  { path: "/", ready: "main h1" },
  { path: "/reports", ready: "main h1" },
  { path: "/incidents", ready: "main h1" },
  { path: "/volunteers", ready: "main h1" },
  { path: "/notifications", ready: "main h1" },
  { path: "/notifications/new", ready: "main h1" },
  { path: "/orgs/certificates", ready: "main h1" },
  { path: "/orgs/certificates/counter", ready: "main h1" },
  { path: "/orgs/prevention", ready: "main h1" },
  { path: "/accounts", ready: "main h1" },
  { path: "/audit", ready: "main h1" },
  { path: "/settings", ready: "main h1" },
  { path: "/coastal", ready: "main h1" },
  { path: "/programmes", ready: "main table" },
  { path: "/programmes/p1", ready: "main table" },
  { path: "/command", ready: "main .ops-topbar" },
  { path: "/axes", ready: "main .axis-grid li" },
  { path: "/axes/ax-nabeul", ready: "main .ops-topbar" },
  // Phase L3b: the register of plans and recommendations, and the directives with their replies.
  { path: "/register", ready: "main .register-card" },
  { path: "/register/reg-plan", ready: "main .recommendations" },
  { path: "/register/dispatches", ready: "main .dispatch-card" },
  { path: "/register/dispatches/dsp-all", ready: "main .thread" },
  // Phase PL1: the plans by hazard, and one read on the screen.
  { path: "/plans", ready: "main .plan-card" },
  { path: "/plans/reg-plan", ready: "main .pdf-viewer canvas" },
  // Phase PL2: the progress of the programmes (the national user lands on it).
  { path: "/schedule", ready: "main .rate" },
  // Phase L5b: the sensors of the local network, by urgency.
  { path: "/sensors", ready: "main table" },
];

// ┏━━ SIMULATION ━━ sensors of the local network (phase L5b), one per level
// ┃ PRODUCTION: services/api (module sensors); tests/test_sensors.py covers it.
// ┗━━━━━━━━━━━━━━━━
const SENSORS = (["alarm", "watch", "silent", "normal", "disabled"] as const).map((state, i) => ({
  id: `s-${i}`,
  code: `TUN-RAIN-0${i}`,
  name: `Pluviomètre ${i}`,
  kind: "rain_1h",
  unit: "mm/h",
  gouvernorat_code: 11,
  lat: 36.8,
  lon: 10.18,
  provider: "INM",
  watch_threshold: 20,
  alarm_threshold: 40,
  silent_after_min: 30,
  enabled: state !== "disabled",
  simulated: true,
  last_value: state === "silent" ? null : 10 * i,
  last_at: state === "silent" ? null : "2026-10-28T20:00:00Z",
  state,
  level_since: "2026-10-28T19:00:00Z",
  created_by_name: null,
  updated_at: "2026-10-28T19:00:00Z",
}));

/** A one-page PDF ([SIM]) for the plan viewer; PDF.js rebuilds the missing cross-reference table. */
const SAMPLE_PDF = [
  "%PDF-1.4",
  "1 0 obj <</Type/Catalog/Pages 2 0 R>> endobj",
  "2 0 obj <</Type/Pages/Kids[3 0 R]/Count 1>> endobj",
  "3 0 obj <</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>> endobj",
  "4 0 obj <</Length 52>> stream",
  "BT /F1 24 Tf 72 760 Td ([SIM] Plan bleu - inondations) Tj ET",
  "endstream endobj",
  "5 0 obj <</Type/Font/Subtype/Type1/BaseFont/Helvetica>> endobj",
  "trailer <</Root 1 0 R>>",
  "%%EOF",
].join("\n");

const PAGE = { items: [], next_cursor: null, total: 0 };
const BEACH = {
  id: "b1",
  name: "Plage de la Corniche",
  lat: 37.27,
  lon: 9.87,
  gouvernorat_code: 17,
  level: "red",
  score: 75,
  factors: [{ code: "waves", points: 55, value: 2.8 }],
  wave_height_m: 2.8,
  sea_temp_c: 24,
  current_kmh: 2.4,
  classification: "local",
  guarded: false,
  crowd: null,
  present: 4,
};
const COASTAL_OVERVIEW = {
  day: "2026-07-04",
  computed_at: "2026-07-04T07:00:00Z",
  simulated: true,
  attribution: ["[SIM] Simulated marine weather"],
  kpis: { beaches: 1, red: 1, yellow: 0, green: 0, unknown: 0, average_score: 75, guarded: 0, drownings_season: 1, present: 4 },
  top_dangerous: [BEACH],
  top_touristic: [],
  by_gouvernorat: [{ code: 17, beaches: 1, red: 1, yellow: 0, green: 0, average_score: 75, crowd_high: 0, crowd_medium: 0, crowd_low: 0 }],
  beaches: [BEACH],
  heat_risk: [[37.27, 9.87, 0.75]],
  heat_drownings: [],
};

const PROGRAMME = {
  id: "p1",
  code: "BEACH-2026",
  kind: "beach",
  title: "Plan de surveillance des plages 2026",
  season: "Été 2026",
  valid_from: "2026-06-15",
  valid_to: "2026-09-15",
  status: "approved",
  version: 2,
  source_document: "",
  declared: {},
  approved_by_name: "Salma",
  approved_at: "2026-06-01T09:00:00Z",
  cancel_reason: null,
  layer_key: "prog_beach_2026",
  live: true,
  updated_by_name: "Salma",
  updated_at: "2026-06-01T09:00:00Z",
  figures: { points: 1, unlocated: 0, open: 1, gouvernorats: 1, staff: 20, lifeguards_planned: 8, lifeguards_deployed: 2 },
  can_edit: true,
  can_follow_up: true,
};
const PROGRAMME_POINT = {
  id: "pt1",
  ref: "BEACH-2026-001",
  gouvernorat_code: 17,
  place_name: "Plage de la Corniche",
  sub_points: null,
  lat: 37.27,
  lon: 9.87,
  geo_confidence: "confirmed",
  geo_note: null,
  staff_count: 20,
  staff_composition: null,
  supervisors: 1,
  lifeguards_planned: 8,
  lifeguards_deployed: 2,
  equipment: null,
  hours: "08:00-19:00",
  opening_date: null,
  closing_date: null,
  status: "open",
  supervisor_name: "Responsable",
  supervisor_phone: "+216 70 000 000",
  notes: null,
  updated_at: "2026-06-01T09:00:00Z",
  can_follow_up: true,
};

async function mockApi(page: Page): Promise<string[]> {
  const unanswered: string[] = [];
  await page.route(`${API}/**`, (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    // The decision window answers its own access (full view) before the common default (no delegation).
    if (pathname === "/api/v1/staff/window/access") return json(route, WINDOW_ACCESS_FULL);
    const common = commonAnswer(request.method(), pathname, route);
    if (common) return common;
    // Phase R2: the search of the resources register is a POST that answers.
    if (pathname === "/api/v1/staff/inventory/search") return json(route, SEARCH_RESULT);
    // Phase L4 §9: the written summary of the decision window is a POST that answers.
    if (pathname === "/api/v1/staff/window/summary") return json(route, WINDOW_SUMMARY);
    if (request.method() !== "GET") return json(route, {}, 204);
    if (pathname === "/api/v1/staff/kpis") {
      return json(route, {
        since: new Date().toISOString(),
        total: 3,
        by_status: { received: 2, in_progress: 1 },
        by_category: { fire: 2, flood: 1 },
        by_gouvernorat: [{ code: 61, count: 3 }],
        avg_first_response_s: 240,
        high_priority: 1,
        analysis_pending: 0,
      });
    }
    if (pathname === "/api/v1/staff/ai/status") return json(route, { configured: false, capabilities: {} });
    if (pathname === "/api/v1/staff/app-feedback") {
      return json(route, { days: 30, count: 0, average: null, by_stars: {}, by_build: [], remarks: [] });
    }
    if (pathname === "/api/v1/staff/alerts/active") return json(route, []);
    if (pathname === "/api/v1/staff/volunteers/map") return json(route, { type: "FeatureCollection", features: [] });
    if (pathname === "/api/v1/staff/reports/map") return json(route, { type: "FeatureCollection", features: [] });
    // Coastal safety (phase L1b): one simulated red beach.
    if (pathname === "/api/v1/staff/coastal/overview") return json(route, COASTAL_OVERVIEW);
    if (pathname === "/api/v1/staff/coastal/alerts") return json(route, { items: [] });
    if (pathname === "/api/v1/staff/coastal/settings") {
      return json(route, { rules: { yellow: 35, red: 60, waves: [[1, 10], [null, 40]] }, defaults: {}, updated_by: null, updated_at: null });
    }
    // Seasonal programmes (phase L2): one approved programme with one point.
    if (pathname === "/api/v1/staff/programmes") return json(route, { items: [PROGRAMME], can_create: true });
    if (pathname === "/api/v1/staff/programmes/p1") {
      return json(route, { programme: PROGRAMME, points: [PROGRAMME_POINT], computed: { staff: 20 } });
    }
    if (pathname === "/api/v1/staff/programmes/p1/revisions") {
      const revision = { action: "approve", reason: null, created_by_name: "Salma", created_at: "2026-06-01T09:00:00Z", points: 1 };
      return json(route, { items: [{ ...revision, number: 2 }, { ...revision, number: 1, action: "import" }] });
    }
    // Disaster and crisis axes (phase L3): the [SIM] Nabeul floods and two other axes.
    if (pathname === "/api/v1/staff/crisis/command") return json(route, overview("minister"));
    if (pathname === "/api/v1/staff/crisis/boundaries") return json(route, { type: "FeatureCollection", features: [] });
    if (pathname === "/api/v1/staff/crisis/axes") return json(route, { items: [NABEUL_AXIS, JENDOUBA_AXIS, SOUSSE_AXIS] });
    if (pathname === "/api/v1/staff/crisis/requests") return json(route, { items: [REQUEST] });
    if (pathname === "/api/v1/staff/crisis/axes/ax-nabeul") return json(route, NABEUL_DETAIL);
    if (pathname === "/api/v1/staff/crisis/axes/ax-nabeul/suggestions") return json(route, { items: SUGGESTIONS });
    // Register of plans and recommendations, directives and replies (phase L3b), [SIM] data.
    if (pathname === "/api/v1/staff/register/documents") return json(route, SEARCH);
    if (pathname === "/api/v1/staff/register/documents/reg-plan") return json(route, PLAN_DETAIL);
    if (pathname === "/api/v1/staff/register/documents/reg-plan/revisions") return json(route, REVISIONS);
    if (pathname === "/api/v1/staff/register/dispatches") return json(route, DISPATCH_PAGE);
    if (pathname === "/api/v1/staff/register/dispatches/dsp-all") return json(route, DIRECTIVE_ALL_DETAIL);
    if (pathname === "/api/v1/staff/register/plans") return json(route, PLANS);
    // The administrator's permissions (phase L4 §8), [SIM] data.
    if (pathname === "/api/v1/staff/features/mine") return json(route, NO_FEATURES);
    if (pathname === "/api/v1/staff/features/catalogue") return json(route, FEATURES);
    if (pathname === "/api/v1/staff/features/rules") return json(route, FEATURE_RULES);
    if (pathname === "/api/v1/staff/features/preview") return json(route, PREVIEW);
    // The decision window (phase L4 §3 and §5), [SIM] data.
    const decisionWindow: Record<string, unknown> = {
      "/api/v1/staff/window/access": WINDOW_ACCESS_FULL,
      "/api/v1/staff/window/now": WINDOW_NOW,
      "/api/v1/staff/window/search": WINDOW_SEARCH,
      "/api/v1/staff/window/compare": WINDOW_COMPARE,
      "/api/v1/staff/window/searches": WINDOW_SAVED,
      "/api/v1/staff/window/synonyms": WINDOW_SYNONYMS,
      "/api/v1/staff/window/delegates": WINDOW_DELEGATES,
      "/api/v1/staff/window/delegations": [WINDOW_DELEGATION],
    };
    if (pathname in decisionWindow) return json(route, decisionWindow[pathname]);
    // The six-level calendar of the events library (phase L4a), [SIM] data.
    if (pathname === "/api/v1/staff/library/search")
      return json(route, { items: [], facets: { kind: [], year: [], gouvernorat: [], category: [] }, backend: "postgres", semantic: false, next_cursor: null });
    if (pathname === "/api/v1/staff/library/calendar/grid") {
      const q = new URL(route.request().url()).searchParams;
      return json(route, fakeGrid((q.get("level") ?? "month") as CalendarLevel, q.get("on") ?? "2026-08-12"));
    }
    if (pathname === "/api/v1/staff/library/calendar/figures") {
      const q = new URL(route.request().url()).searchParams;
      return json(route, fakeFigures(q.get("from") ?? "2026-08-01", q.get("to") ?? "2026-08-31"));
    }
    if (pathname === "/api/v1/staff/schedule/slot") return json(route, SCHEDULE_SLOT);
    if (pathname === "/api/v1/staff/schedule/progress") return json(route, SCHEDULE_PROGRESS);
    if (pathname === "/api/v1/staff/schedule/settings") return json(route, SCHEDULE_SETTINGS);
    if (pathname === "/api/v1/staff/schedule/options") return json(route, SCHEDULE_OPTIONS);
    if (pathname === "/api/v1/staff/schedule/templates") return json(route, SCHEDULE_TEMPLATES);
    if (pathname === "/api/v1/staff/register/hazards") return json(route, HAZARDS);
    if (pathname === "/api/v1/staff/register/documents/reg-plan/file/content")
      return route.fulfill({ status: 200, contentType: "application/pdf", body: SAMPLE_PDF });
    // Resources register (phase R1).
    const inventory: Record<string, unknown> = {
      "/api/v1/staff/inventory/catalogue": CATALOGUE,
      "/api/v1/staff/inventory/overview": OVERVIEW,
      "/api/v1/staff/inventory/units": { items: UNITS },
      "/api/v1/staff/inventory/vehicles": { items: [VEHICLE], can_edit: true },
      "/api/v1/staff/inventory/stock": { items: [STOCK], can_edit: true },
      "/api/v1/staff/inventory/agents": { items: [AGENT], can_edit: true, can_see_names: true, can_export_names: true },
      // Phase R2: the search across the gouvernorats and the outlines it colours on the map.
      "/api/v1/staff/inventory/search": SEARCH_RESULT,
      "/api/v1/staff/inventory/boundaries": BOUNDARIES,
      // Phase R3 and R4b: no transfer waiting, no saved column mapping.
      "/api/v1/staff/inventory/transfers": [],
      "/api/v1/staff/inventory/import-profiles": [],
      // Satellite background (phase R).
      "/api/v1/staff/basemap": BASEMAP,
      "/api/v1/staff/basemap/settings": BASEMAP_SETTINGS,
      // Phase L5b: sensors ([SIM]) at every level.
      "/api/v1/staff/sensors": { items: SENSORS, can_manage: true },
    };
    if (pathname in inventory) return json(route, inventory[pathname]);
    unanswered.push(pathname);
    return json(route, PAGE);
  });
  return unanswered;
}

async function audit(page: Page, path: string, ready: string): Promise<void> {
  await page.goto(path);
  await expect(page.locator(ready).first()).toBeVisible();
  await scan(page, path);
}

/** The scan of the screen as it stands (after clicks that a fresh navigation would undo). */
async function scan(page: Page, path: string): Promise<void> {
  // Let pending requests settle so the scan sees the finished screen.
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    // The map canvas is drawn by MapLibre (WebGL); its own controls are checked, not the pixels.
    .exclude(".maplibregl-canvas")
    .analyze();
  console.log(`[axe-run] ${path}: ${results.passes.length} rules passed, ${results.violations.length} violated`);
  const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  for (const v of results.violations) {
    const targets = v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ");
    console.log(`[axe ${v.impact ?? "?"}] ${path}: ${v.id} (${v.nodes.length}) ${targets}`);
  }
  expect(
    blocking.map((v) => `${v.id}: ${v.help} → ${v.nodes.map((n) => n.target.join(" ")).slice(0, 5).join(", ")}`),
  ).toEqual([]);
}

for (const lang of ["fr", "ar"] as const) {
  test.describe(`accessibility (${lang})`, () => {
    for (const screen of SCREENS) {
      test(`${screen.path} has no serious or critical violation`, async ({ page }) => {
        await signIn(page, ROLES, "Salma Ben Ali");
        if (lang === "ar") await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
        const fence = await baseMock(page);
        await mockApi(page);
        await audit(page, screen.path, screen.ready);
        expect(fence.unexpected).toEqual([]);
      });
    }
  });
}

// Phase PL2: a week of a gouvernorat on the calendar, an activity open and the approval tab, in both modes.
test.describe("accessibility of the programmes (ar)", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`week, activity, templates and approval, ${theme}, have no serious or critical violation`, async ({ page }) => {
      await signIn(page, ROLES, "Salma Ben Ali");
      await page.addInitScript((t) => {
        window.localStorage.setItem("ehimaya.lang", "ar");
        window.localStorage.setItem("ehimaya.theme", t);
      }, theme);
      const fence = await baseMock(page);
      await mockApi(page);
      await page.goto("/schedule");
      await page.getByRole("button", { name: "فتح برمجة نابل" }).click();
      await expect(page.locator("main .sched-week").first()).toBeVisible();
      await page.getByRole("button", { name: /دورية الشريط الساحلي/ }).click();
      await expect(page.locator("main .sched-panel")).toBeVisible();
      await scan(page, `/schedule week ${theme}`);
      await page.getByRole("tab", { name: "النماذج" }).click();
      await expect(page.locator("main #sched-templates")).toBeVisible();
      await scan(page, `/schedule templates ${theme}`);
      await page.getByRole("tab", { name: "طريقة الاعتماد" }).click();
      await expect(page.locator("main #sched-settings")).toBeVisible();
      await scan(page, `/schedule approval ${theme}`);
      expect(fence.unexpected).toEqual([]);
    });
  }
});

// Phase L4 §8: the permissions page of the system administrator, the catalogue open, in both modes.
test.describe("accessibility of the permissions (ar)", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`rules, preview and catalogue, ${theme}, have no serious or critical violation`, async ({ page }) => {
      await signIn(page, [...ROLES, "sysadmin"], "Salma Ben Ali");
      await page.addInitScript((t) => {
        window.localStorage.setItem("ehimaya.lang", "ar");
        window.localStorage.setItem("ehimaya.theme", t);
      }, theme);
      const fence = await baseMock(page);
      await mockApi(page);
      await page.goto("/permissions");
      await expect(page.locator("main .perm-rule").first()).toBeVisible();
      await page.locator("main .perm-group summary").first().click();
      await scan(page, `/permissions ${theme}`);
      expect(fence.unexpected).toEqual([]);
    });
  }
});

// Phase L4 §3: the decision window (the situation now, a search, a comparison, the delegations), in both modes.
test.describe("accessibility of the decision window (ar)", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`now, search, comparison and delegations, ${theme}, have no serious or critical violation`, async ({ page }) => {
      await signIn(page, ["ops_manager"], "Salma Ben Ali");
      await page.addInitScript((t) => {
        window.localStorage.setItem("ehimaya.lang", "ar");
        window.localStorage.setItem("ehimaya.theme", t);
      }, theme);
      const fence = await baseMock(page);
      await mockApi(page);
      await page.goto("/window");
      await expect(page.locator("main .win-axis").first()).toBeVisible();
      await scan(page, `/window now ${theme}`);
      await page.getByRole("tab", { name: "البحث" }).click();
      await expect(page.locator("main .win-understood")).toBeVisible();
      await page.getByRole("button", { name: "اكتب ملخصا (ذكاء اصطناعي)" }).click();
      await expect(page.locator("main .win-summary__body")).toBeVisible();
      await scan(page, `/window search ${theme}`);
      await page.getByRole("tab", { name: "المقارنة" }).click();
      await page.getByRole("button", { name: "قارن" }).click();
      await expect(page.locator("main .win-compare")).toBeVisible();
      await scan(page, `/window compare ${theme}`);
      await page.getByRole("tab", { name: "التفويضات" }).click();
      await expect(page.locator("main .win-delegation").first()).toBeVisible();
      await scan(page, `/window delegations ${theme}`);
      expect(fence.unexpected).toEqual([]);
    });
  }
});

test.describe("accessibility of the library calendar (ar)", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`the month, year and day levels with their indicators, ${theme}, have no serious or critical violation`, async ({ page }) => {
      await signIn(page, ["ops_manager"], "Salma Ben Ali");
      await page.addInitScript((t) => {
        window.localStorage.setItem("ehimaya.lang", "ar");
        window.localStorage.setItem("ehimaya.theme", t);
      }, theme);
      const fence = await baseMock(page);
      await mockApi(page);
      await page.goto("/library?view=calendar&from=2026-08-12");
      await expect(page.locator("main .calendar__grid")).toBeVisible();
      await expect(page.locator("main .calendar__figures .kpis")).toBeVisible();
      await scan(page, `/library calendar month ${theme}`);
      await page.getByRole("button", { name: "سنة", exact: true }).click();
      await expect(page.locator("main .calendar__cells--month")).toBeVisible();
      await scan(page, `/library calendar year ${theme}`);
      await page.getByRole("button", { name: "يوم", exact: true }).click();
      await expect(page.locator("main .calendar__cells--hour")).toBeVisible();
      await scan(page, `/library calendar day ${theme}`);
      expect(fence.unexpected).toEqual([]);
    });
  }
});

// Phase UI-3: the main menu in each shape and position, with a group and the account menu open, in both modes.
const MENUS = [
  { shape: "grouped", position: "top", theme: "light" },
  { shape: "grouped", position: "right", theme: "dark" },
  { shape: "grouped", position: "left", theme: "light" },
  { shape: "flat", position: "top", theme: "dark" },
  { shape: "flat", position: "right", theme: "light" },
  { shape: "flat", position: "left", theme: "dark" },
] as const;

test.describe("accessibility of the main menu (ar)", () => {
  for (const m of MENUS) {
    test(`${m.shape} ${m.position} ${m.theme} has no serious or critical violation`, async ({ page }) => {
      await signIn(page, ROLES, "Salma Ben Ali");
      await page.addInitScript((menu) => {
        window.localStorage.setItem("ehimaya.lang", "ar");
        window.localStorage.setItem("ehimaya.theme", menu.theme);
        window.localStorage.setItem("ehimaya.menu", JSON.stringify({ shape: menu.shape, position: menu.position }));
      }, m);
      const fence = await baseMock(page);
      await mockApi(page);
      await page.goto("/register");
      await expect(page.locator("main .register-card").first()).toBeVisible();
      if (m.shape === "grouped") {
        const group = page.getByRole("button", { name: "الأزمات والقيادة" });
        await group.click();
        await expect(group).toHaveAttribute("aria-expanded", "true");
        await expect(page.getByRole("link", { name: "التوجيهات والردود" })).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(group).toHaveAttribute("aria-expanded", "false");
      }
      await page.getByRole("button", { name: /حسابي والإعدادات/ }).click();
      await expect(page.getByRole("radio", { name: "مجمّعة" })).toBeAttached();
      await audit(page, "/register", "main .register-card");
      expect(fence.unexpected).toEqual([]);
    });
  }
});

// Phase UI-3b: the map's layers in folders (one open, with a mixed "show all" switch), and the administrator's
// folders tab, in both modes.
const FOLDER = (key: string, ar: string, icon: string, tone: string, position: number, count: number) => ({
  key,
  name: { ar, fr: ar, en: ar },
  icon,
  tone,
  position,
  sensitive: false,
  layer_count: count,
});
const MAP_LAYER = (key: string, ar: string, icon: string, colour: string, group: string) => ({
  id: key,
  key,
  name: { ar, fr: ar, en: ar },
  icon,
  colour,
  audience: "staff",
  source: "OpenStreetMap",
  licence: "ODbL",
  to_verify: false,
  simulated: true,
  staff_only: [],
  editors_allowed: false,
  enabled: true,
  version: 1,
  data_version: 1,
  feature_count: 0,
  hidden_count: 0,
  updated_by_name: null,
  updated_at: "2026-10-28T08:00:00Z",
  last_import: null,
  can_manage: true,
  can_import: true,
  status: "published",
  audiences: ["room", "command"],
  scope: [],
  default_on: key === "hospitals",
  sensitive: false,
  fields: {},
  actions: { call: true, directions: true },
  geometry: "point",
  quality: { suggested: 0, duplicates: 0, deleted: 0 },
  deleted_at: null,
  delete_reason: null,
  purge_at: null,
  group,
});
const FOLDERED = {
  groups: [
    FOLDER("civil_protection", "موارد الحماية المدنية", "localFireDepartment", "red", 1, 1),
    FOLDER("health", "المؤسسات الصحية", "medicalServices", "pink", 2, 2),
    FOLDER("other", "طبقات أخرى", "layers", "slate", 12, 0),
  ],
  items: [
    MAP_LAYER("hydrants", "نقاط التزود بالماء", "water", "#B71C1C", "civil_protection"),
    MAP_LAYER("hospitals", "المستشفيات", "hospital", "#C62828", "health"),
    MAP_LAYER("pharmacies", "الصيدليات", "pharmacy", "#2E7D32", "health"),
  ],
  deleted: [],
  can_manage: true,
  icons: ["hospital", "pharmacy", "water", "pin"],
  palette: ["#C62828", "#2E7D32", "#B71C1C"],
  limits: { file_bytes: 10485760, rows: 50000 },
};

test.describe("accessibility of the resources register (ar)", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`overview, vehicles, staff and import, ${theme}, have no serious or critical violation`, async ({ page }) => {
      await signIn(page, ROLES, "Salma Ben Ali");
      await page.addInitScript((mode) => {
        window.localStorage.setItem("ehimaya.lang", "ar");
        window.localStorage.setItem("ehimaya.theme", mode);
      }, theme);
      const fence = await baseMock(page);
      await mockApi(page);
      await page.route(`${API}/api/v1/staff/inventory/imports**`, (route) => json(route, IMPORT_PREVIEW));
      await audit(page, "/inventory", "main table");
      const scan = async () => {
        const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
        expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
      };
      await page.getByRole("tab", { name: "الآليات" }).click();
      await page.getByRole("button", { name: "آلية جديدة" }).click();
      const form = page.getByRole("form", { name: "آلية جديدة" });
      await form.getByLabel("الصنف").selectOption("fire_engine");
      await expect(form.getByRole("spinbutton", { name: /السعة/ })).toBeVisible();
      await scan();
      await page.getByRole("tab", { name: "الأعوان" }).click();
      await page.getByRole("button", { name: "عون جديد" }).click();
      await page.getByRole("checkbox", { name: "غوص" }).check();
      await scan();
      await page.getByRole("tab", { name: "الاستيراد" }).click();
      // The central room names the gouvernorat it imports for.
      await page.getByRole("region", { name: "الاستيراد من نموذج الولاية" }).getByLabel("الولاية").selectOption({ index: 1 });
      await page.getByLabel("الملف (xlsx أو CSV أو JSON)").setInputFiles({ name: "sfax.xlsx", mimeType: "application/octet-stream", buffer: Buffer.from("PK") });
      await page.getByRole("button", { name: "معاينة" }).click();
      await expect(page.getByRole("table", { name: /ما في الملف/ })).toBeVisible();
      await scan();
      // Phase R2: the search across the gouvernorats, then its result in the «موارد الحماية المدنية» folder of the map.
      await page.getByRole("tab", { name: "البحث عبر الولايات" }).click();
      await page.getByLabel("الصنف").selectOption("fire_engine");
      await page.getByRole("spinbutton", { name: "السعة (L): من" }).fill("2000");
      await page.getByRole("button", { name: "بحث", exact: true }).click();
      await expect(page.getByRole("table", { name: "نتيجة البحث حسب الولاية" })).toBeVisible();
      await page.getByRole("row", { name: /تونس/ }).getByText(/الوحدات/).click();
      await scan();
      await page.getByRole("button", { name: "عرض على الخريطة" }).click();
      await expect(page.getByRole("checkbox", { name: /نتيجة البحث: شاحنة إطفاء/ })).toBeChecked();
      await expect(page.getByText("إزالة نتيجة البحث")).toBeVisible();
      await scan();
      expect(fence.unexpected).toEqual([]);
    });
  }
});

test.describe("accessibility of the layer folders (ar)", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`map and folders tab, ${theme}, have no serious or critical violation`, async ({ page }) => {
      await signIn(page, [...ROLES, "sysadmin"], "Salma Ben Ali");
      await page.addInitScript((mode) => {
        window.localStorage.setItem("ehimaya.lang", "ar");
        window.localStorage.setItem("ehimaya.theme", mode);
      }, theme);
      const fence = await baseMock(page);
      await mockApi(page);
      await page.route(`${API}/api/v1/staff/layers`, (route) => json(route, FOLDERED));
      await page.route(`${API}/api/v1/staff/layers/*/features**`, (route) => json(route, { items: [], truncated: false }));
      await page.goto("/map");
      const health = page.getByRole("button", { name: /المؤسسات الصحية/ });
      await expect(health).toHaveAttribute("aria-expanded", "true");
      await expect(page.getByRole("checkbox", { name: "إظهار كل طبقات المؤسسات الصحية" })).toHaveJSProperty("indeterminate", true);
      await page.getByRole("button", { name: /موارد الحماية المدنية/ }).click();
      await expect(page.getByRole("checkbox", { name: /نقاط التزود بالماء/ })).toBeVisible();
      await audit(page, "/map", "main .layer-folder");
      // The satellite background, chosen beside the layers.
      await page.getByRole("radio", { name: "قمر صناعي" }).check({ force: true });
      await expect(page.getByText("صور Sentinel‑2 المفتوحة")).toBeVisible();
      const onMap = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
      expect(onMap.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);

      await page.goto("/layers");
      await page.getByRole("tab", { name: "خلفية الخريطة" }).click();
      await expect(page.getByRole("button", { name: "تجربة الاتصال" })).toBeVisible();
      const background = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
      expect(background.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
      await page.getByRole("tab", { name: /مجلدات الخريطة/ }).click();
      await expect(page.getByRole("button", { name: "تعديل المجلد المؤسسات الصحية" })).toBeVisible();
      await page.getByRole("button", { name: "مجلد جديد" }).click();
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
      expect(results.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
      expect(fence.unexpected).toEqual([]);
    });
  }
});
