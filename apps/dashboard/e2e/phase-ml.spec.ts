/**
 * The interactive map gathers the layers of the system (Yamen 2026-11-13, docs/phase-ml/design-ml.md): every datum a
 * screen draws on its own map is an optional layer in a folder of the panel, read from that screen's own request, with
 * a link back to it; a source screen opens the map on its layer (`/map?layers=…`).
 * Screenshots for the phase report land in test-results/phase-ml/.
 */
import { expect, test, type Page } from "@playwright/test";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-ml";
const C = "/api/v1/staff/crisis";
const NABEUL = { code: 21, iso_code: "TN-21", name: "نابل", name_ar: "نابل", name_fr: "Nabeul", delegation_count: 16 };
const ROOM = { scope_level: "regional", gouvernorat_code: 21 };
const now = new Date().toISOString();

const square = (lon: number, lat: number, d: number) => ({
  type: "Polygon",
  coordinates: [
    [
      [lon - d, lat - d],
      [lon + d, lat - d],
      [lon + d, lat + d],
      [lon - d, lat + d],
      [lon - d, lat - d],
    ],
  ],
});

const AXIS = { id: "ax-nabeul", number: 3, name: "فيضان وادي سوحيل", kind: "flood", level: 3, status: "open", gouvernorat_code: 21 };
const DISASTER_MAP = {
  figures: {},
  areas: [{ id: "ax-nabeul", level: 3, area: square(10.73, 36.46, 0.05) }],
  incidents: [],
  shelters: [
    { id: "sh-1", axis_id: "ax-nabeul", name: "ملجأ دار الشباب بنابل", lat: 36.47, lon: 10.69, capacity: 200, occupants: 85, updated_at: now },
  ],
  evacuations: [{ id: "ev-1", axis_id: "ax-nabeul", name: "حي المهيري", area: square(10.75, 36.45, 0.015), evacuated: 40, updated_at: now }],
};
const INCIDENTS = {
  items: [
    {
      id: "inc-1",
      category: "flood",
      status: "open",
      gouvernorat_code: 21,
      centroid: { lat: 36.452, lon: 10.738 },
      severity: 82,
      report_count: 6,
      reporter_count: 5,
      opened_at: now,
      updated_at: now,
      closed_at: null,
      merged_into: null,
      title: "مياه في الطابق الأرضي",
    },
  ],
  next_cursor: null,
};
const beach = (id: string, name: string, lat: number, lon: number, level: "green" | "yellow" | "red", score: number) => ({
  id,
  name,
  lat,
  lon,
  gouvernorat_code: 21,
  level,
  score,
  factors: [],
  wave_height_m: null,
  sea_temp_c: null,
  current_kmh: null,
  classification: null,
  guarded: true,
  crowd: null,
  present: null,
});
const COASTAL = {
  day: now.slice(0, 10),
  computed_at: now,
  simulated: true,
  attribution: [],
  kpis: {},
  top_dangerous: [],
  top_touristic: [],
  by_gouvernorat: [],
  beaches: [beach("b1", "شاطئ نابل", 36.44, 10.745, "red", 78), beach("b2", "شاطئ الحمامات", 36.39, 10.6, "yellow", 45)],
  heat_risk: [],
  heat_drownings: [],
};
const STREAMS = {
  items: [
    {
      id: "st-1",
      report_id: null,
      tracking_code: null,
      source: "crew",
      label: "شاحنة إطفاء نابل 2",
      status: "live",
      started_at: now,
      ended_at: null,
      duration_s: 120,
      gouvernorat_code: 21,
      last_location: { lat: 36.458, lon: 10.72 },
      max_fire_confidence: null,
      max_smoke_confidence: null,
      recordings_count: 0,
      simulated: true,
    },
  ],
  next_cursor: null,
};

async function mockApi(page: Page) {
  const m = await baseMock(page);
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    if (pathname === "/api/v1/geo/gouvernorats") return json(route, [NABEUL]);
    if (pathname === "/api/v1/staff/streams") return json(route, STREAMS);
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    if (pathname === `${C}/axes`) return json(route, { items: [AXIS] });
    if (pathname === `${C}/disasters/map`) return json(route, DISASTER_MAP);
    if (pathname === `${C}/exposure/map`) return json(route, { items: [] });
    if (pathname === "/api/v1/staff/incidents") return json(route, INCIDENTS);
    if (pathname === "/api/v1/staff/coastal/overview") return json(route, COASTAL);
    if (method === "GET") return json(route, { items: [], next_cursor: null });
    m.unexpected.push(`${method} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return m;
}

test.describe("Interactive map: the layers of the system in their folders", () => {
  test.use({ viewport: { width: 1440, height: 1300 } });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
  });

  test("each folder holds the layers of the screens, read from their own requests, with a link back", async ({ page }) => {
    await mockApi(page);
    await signIn(page, ["ops_manager"], "Sami Operator", ROOM);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/map");

    await page.getByRole("button", { name: /البلاغات والتدخّلات/ }).click();
    await page.getByRole("checkbox", { name: "التدخّلات المفتوحة" }).check();
    await expect(page.getByRole("link", { name: "المصدر: التدخّلات" })).toHaveAttribute("href", "/incidents");
    await expect(page.getByRole("button", { name: /^مياه في الطابق الأرضي —/ })).toBeVisible();

    await page.getByRole("button", { name: /الأزمات والمحاور/ }).click();
    await page.getByRole("checkbox", { name: /المحاور المفتوحة/ }).check();
    await expect(page.getByRole("button", { name: /^ملجأ دار الشباب بنابل — ملجأ · 85 من 200/ })).toBeVisible();

    await page.getByRole("button", { name: /المواسم والسواحل/ }).click();
    await page.getByRole("checkbox", { name: "الشواطئ ورايات الخطر" }).check();
    await expect(page.getByRole("button", { name: /^شاطئ نابل \[SIM\] —/ })).toBeVisible();

    await page.getByRole("button", { name: /الرصد والاستشعار/ }).click();
    await page.getByRole("checkbox", { name: "البث المباشر والكاميرات" }).check();
    await expect(page.getByRole("button", { name: /^شاحنة إطفاء نابل 2 \[SIM\] —/ })).toBeVisible();

    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SHOTS}/ml-map-layers.png`, fullPage: true });
    const map = page.locator(".maplibregl-map").first();
    await map.scrollIntoViewIfNeeded();
    await page.waitForTimeout(2500);
    await map.screenshot({ path: `${SHOTS}/ml-map-drawn.png` });
  });

  test("a source screen opens the map with its layer on and its folder open", async ({ page }) => {
    await mockApi(page);
    await signIn(page, ["ops_manager"], "Sami Operator", ROOM);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/incidents");
    const link = page.getByRole("link", { name: "اعرضها على الخريطة التفاعلية" });
    await expect(link).toHaveAttribute("href", "/map?layers=incidents");
    await link.click();
    await expect(page.getByRole("checkbox", { name: "التدخّلات المفتوحة" })).toBeChecked();
    await expect(page.getByRole("button", { name: /^مياه في الطابق الأرضي —/ })).toBeVisible();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${SHOTS}/ml-from-source.png` });
  });
});
