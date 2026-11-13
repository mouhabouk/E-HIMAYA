/**
 * OS14 in the browser (docs/phase-os14/design-os14.md): the people and places exposed on the area of a crisis axis, in
 * the axis's own tab and on its map, the line of the decision window, and the optional layer of the interactive map.
 * Screenshots for the phase report land in test-results/phase-os14/.
 */
import { expect, test, type Page } from "@playwright/test";
import { EXPOSURE, NABEUL_AXIS, NABEUL_DETAIL } from "../src/test/crisisData";
import { WINDOW_ACCESS_FULL, WINDOW_NOW } from "../src/test/windowData";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-os14";
const C = "/api/v1/staff/crisis";

// The axis area with its 1 km band (a slightly larger outline), and a few more places than the unit fixture.
const RING = {
  type: "MultiPolygon",
  coordinates: [
    [
      [
        [10.61, 36.37],
        [10.79, 36.35],
        [10.875, 36.45],
        [10.85, 36.57],
        [10.7, 36.61],
        [10.59, 36.53],
        [10.61, 36.37],
      ],
    ],
  ],
};
const place = (name: string, layer: string, lat: number, lon: number, zone: "core" | "ring") => ({ name, layer, lat, lon, zone });
const ESTIMATE = {
  ...EXPOSURE,
  ring: RING,
  groups: {
    ...EXPOSURE.groups,
    health: {
      count: 2,
      core: 1,
      sensitive: true,
      items: [
        place("المستشفى الجهوي محمد التلاتلي", "hospitals", 36.455, 10.735, "core"),
        place("مركز الصحة الأساسية بني خيار", "clinics", 36.465, 10.78, "ring"),
      ],
    },
    elderly: { count: 1, core: 0, sensitive: true, items: [place("دار المسنين بنابل", "elderly_homes", 36.42, 10.66, "ring")] },
    education: {
      count: 4,
      core: 3,
      sensitive: true,
      items: [
        place("المدرسة الابتدائية الوفاء", "schools", 36.46, 10.74, "core"),
        place("المعهد الثانوي الهادي شاكر", "institutes", 36.44, 10.72, "core"),
        place("المدرسة الإعدادية 2 مارس", "schools", 36.5, 10.7, "core"),
        place("المدرسة الابتدائية النخيل", "schools", 36.57, 10.72, "ring"),
      ],
    },
    hazardous: { count: 1, core: 1, sensitive: false, items: [place("محطة وقود الطريق 1", "fuel_stations", 36.43, 10.75, "core")] },
  },
  brief: { ...EXPOSURE.brief, health: 2, elderly: 1, education: 4 },
};
const STATE = { estimate: ESTIMATE, default_ring_m: 1000, rings: [0, 500, 1000, 2000, 5000], can_compute: true, has_area: true };
const NOW = {
  ...WINDOW_NOW,
  axes: [{ ...WINDOW_NOW.axes[0], id: "ax-nabeul", exposure: { ...ESTIMATE.brief, at: new Date(Date.now() - 20 * 60_000).toISOString() } }],
};
const NABEUL = { code: 21, iso_code: "TN-21", name: "نابل", name_ar: "نابل", name_fr: "Nabeul", delegation_count: 16 };

async function mockApi(page: Page) {
  const m = await baseMock(page);
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    if (pathname === "/api/v1/geo/gouvernorats") return json(route, [NABEUL]);
    if (pathname === "/api/v1/staff/window/access") return json(route, WINDOW_ACCESS_FULL);
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    if (pathname === `${C}/boundaries`) return json(route, { type: "FeatureCollection", features: [] });
    if (pathname === `${C}/axes`) return json(route, { items: [NABEUL_AXIS] });
    if (pathname === `${C}/axes/ax-nabeul`) return json(route, NABEUL_DETAIL);
    if (pathname === `${C}/axes/ax-nabeul/exposure`) return json(route, method === "POST" ? ESTIMATE : STATE);
    if (pathname === `${C}/exposure/map`) return json(route, { items: [ESTIMATE] });
    if (pathname === "/api/v1/staff/window/now") return json(route, NOW);
    if (method === "GET") return json(route, { items: [], next_cursor: null });
    m.unexpected.push(`${method} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return m;
}

const ROOM = { scope_level: "regional", gouvernorat_code: 21 };

test.describe("OS14: people and places exposed", () => {
  test.use({ viewport: { width: 1440, height: 1300 } });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
  });

  test("the room reads and recomputes the estimate in the axis tab", async ({ page }) => {
    const m = await mockApi(page);
    await signIn(page, ["ops_manager"], "Sami Operator", ROOM);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/axes/ax-nabeul?tab=exposure");
    await expect(page.getByText("المدرسة الابتدائية الوفاء")).toBeVisible();
    await page.waitForTimeout(800);
    const panel = page.locator(".exposure");
    // The tabs sit in the bottom drawer of the room (a short scrolling box): for the picture only, let it grow.
    await page.locator(".ops-bottom__body").evaluate((el) => {
      el.style.height = "auto";
      el.style.overflow = "visible";
    });
    await page.locator(".ops-room").evaluate((el) => {
      el.style.overflow = "visible";
      el.style.height = "auto";
    });
    await page.waitForTimeout(800);
    await panel.screenshot({ path: `${SHOTS}/os14-axis-tab.png` });
    const axisMap = page.locator(".maplibregl-map").first();
    await axisMap.scrollIntoViewIfNeeded();
    await page.waitForTimeout(800);
    await axisMap.screenshot({ path: `${SHOTS}/os14-axis-map.png` });
    const posted = page.waitForRequest((r) => r.method() === "POST" && r.url().endsWith("/axes/ax-nabeul/exposure"));
    await page.getByLabel("2 كم").check();
    await page.getByRole("button", { name: "أعد الحساب" }).click();
    expect((await posted).postDataJSON()).toEqual({ ring_m: 2000 });
    expect(m.unexpected).toEqual([]);
  });

  test("the decision window shows the figures under the axis", async ({ page }) => {
    await mockApi(page);
    await signIn(page, ["ops_manager"], "Sami Operator", ROOM);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/window");
    const line = page.locator(".win-axis__exposure");
    await expect(line).toBeVisible();
    await expect(line.getByRole("link")).toHaveAttribute("href", "/axes/ax-nabeul?tab=exposure");
    await page.locator(".win-axis").first().screenshot({ path: `${SHOTS}/os14-window.png` });
  });

  test("the interactive map shows the optional layer when it is ticked", async ({ page }) => {
    await mockApi(page);
    await signIn(page, ["ops_manager"], "Sami Operator", ROOM);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/map");
    await page.getByRole("button", { name: /الأزمات والمحاور/ }).click();
    const toggle = page.getByLabel("المعرّضون للخطر");
    await expect(toggle).not.toBeChecked();
    const asked = page.waitForRequest((r) => r.url().endsWith(`${C}/exposure/map`));
    await toggle.check();
    await asked;
    await page.waitForTimeout(1500);
    const map = page.locator(".maplibregl-map").first();
    await map.scrollIntoViewIfNeeded();
    await page.waitForTimeout(3000);
    await map.screenshot({ path: `${SHOTS}/os14-map-layer.png` });
  });
});
