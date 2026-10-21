/**
 * Accessibility of the main screens (phase 10 §6.5, U21): axe-core with the WCAG 2.2 A/AA rules on the production
 * bundle, in French and in Arabic. A violation of impact "serious" or "critical" fails the test; the others are
 * printed so they can be planned.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
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
  { path: "/accounts", ready: "main h1" },
  { path: "/audit", ready: "main h1" },
  { path: "/settings", ready: "main h1" },
];

const PAGE = { items: [], next_cursor: null, total: 0 };

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
    if (pathname === "/api/v1/staff/alerts/active") return json(route, []);
    if (pathname === "/api/v1/staff/volunteers/map") return json(route, { type: "FeatureCollection", features: [] });
    if (pathname === "/api/v1/staff/reports/map") return json(route, { type: "FeatureCollection", features: [] });
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
