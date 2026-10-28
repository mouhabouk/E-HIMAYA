/**
 * Accessibility of the main screens (phase 10 §6.5, U21): axe-core with the WCAG 2.2 A/AA rules on the production
 * bundle, in French and in Arabic. A violation of impact "serious" or "critical" fails the test; the others are
 * printed so they can be planned.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { DIRECTIVE_ALL_DETAIL, DISPATCH_PAGE, PLAN_DETAIL, REVISIONS, SEARCH } from "../src/test/registerData";
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
];

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
    const common = commonAnswer(request.method(), pathname, route);
    if (common) return common;
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
    unanswered.push(pathname);
    return json(route, PAGE);
  });
  return unanswered;
}

async function audit(page: Page, path: string, ready: string): Promise<void> {
  await page.goto(path);
  await expect(page.locator(ready).first()).toBeVisible();
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
