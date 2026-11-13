/**
 * The field layers of the interactive map (Yamen 2026-11-13, docs/phase-ml/design-ml.md §7): the places of the periodic
 * inspections for the inspector general, the vehicles' last positions and the PAR teams for the inspector general, the
 * head of the room and the field commander only; the system administrator hides or reveals each one.
 * ┏━━ SIMULATION ━━ the places, vehicles and teams are invented for the pictures.
 * ┃ PRODUCTION: the layers read /api/v1/staff/field-map; the background is the map style of the deployment.
 * ┗━━━━━━━━━━━━━━━━
 */
import { expect, test, type Page } from "@playwright/test";
import { routeGeoStyle } from "./geoStyle";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-ml";
const F = "/api/v1/staff/field-map";
const now = Date.now();
const ago = (minutes: number) => new Date(now - minutes * 60_000).toISOString();
const day = (days: number) => new Date(now + days * 86_400_000).toISOString().slice(0, 10);

const site = (
  key: string,
  name: string,
  lat: number,
  lon: number,
  verdict: string | null,
  score: number | null,
  extra: Record<string, unknown> = {},
) => ({
  key,
  target: "unit",
  room: null,
  unit_kind: "centre",
  name,
  gouvernorat_code: 61,
  location: { lat, lon },
  location_source: "unit",
  last_inspection_id: verdict ? `insp-${key}` : null,
  last_on: verdict ? ago(60 * 24 * 20) : null,
  last_score: score,
  last_verdict: verdict,
  next_on: null,
  ...extra,
});
const SITES = {
  items: [
    site("u1", "مركز الحماية المدنية بصفاقس المدينة", 34.74, 10.76, "مطابق", 92),
    site("u2", "مركز الحماية المدنية بساقية الزيت", 34.8, 10.75, "مطابق بتحفّظ", 71, { next_on: day(5) }),
    site("u3", "مركز الحماية المدنية بالمحرس", 34.53, 10.5, "غير مطابق", 44),
    site("u4", "مركز الحماية المدنية بقرقنة", 34.71, 11.17, null, null, { next_on: day(12) }),
    {
      ...site("r1", "القاعة الجهوية بصفاقس", 34.76, 10.72, "مطابق", 88),
      target: "room",
      room: "regional",
      unit_kind: null,
      location_source: "directorate",
    },
  ],
  unplaced: 1,
};
const vehicle = (id: string, label: string, lat: number, lon: number, minutes: number | null, incident: string | null) => ({
  id,
  label,
  kind: "fire_engine",
  status: incident ? "assigned" : "available",
  unit_name: "الوحدة الجهوية بصفاقس",
  gouvernorat_code: 61,
  location: { lat, lon },
  at: minutes === null ? null : ago(minutes),
  incident_id: incident,
});
const VEHICLES = {
  items: [
    vehicle("v1", "FPT-61-02", 34.765, 10.69, 2, "inc-1"),
    vehicle("v2", "CCF-61-07", 34.78, 10.71, 4, "inc-1"),
    vehicle("v3", "VSAV-61-11", 34.73, 10.79, 1, null),
    vehicle("v4", "FPT-61-05", 34.6, 10.55, 95, null),
  ],
  unplaced: 3,
};
const team = (id: string, label: string, lat: number, lon: number, status: string) => ({
  id,
  incident_id: "inc-1",
  gouvernorat_code: 61,
  label,
  zone: "hot",
  leader_name: "سامي الطرابلسي",
  members: 4,
  status,
  entered_at: ago(25),
  last_confirmed_at: ago(6),
  location: { lat, lon },
  location_source: "crew",
  at: ago(1),
});
const PAR = { items: [team("t1", "FPT-61-02", 34.7655, 10.6905, "ok"), team("t2", "CCF-61-07", 34.7795, 10.7105, "alarm")] };

interface Mock {
  unexpected: string[];
  asked: string[];
}

async function mockApi(page: Page, hidden: string[] = []): Promise<Mock> {
  const m = await baseMock(page);
  await routeGeoStyle(page);
  const asked: string[] = [];
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    asked.push(pathname);
    if (pathname === "/api/v1/staff/features/mine") return json(route, { granted: [], hidden, lent: {} });
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    if (pathname === `${F}/inspections`) return json(route, SITES);
    if (pathname === `${F}/vehicles`) return json(route, VEHICLES);
    if (pathname === `${F}/par`) return json(route, PAR);
    if (pathname === "/api/v1/staff/resources/map") return json(route, { type: "FeatureCollection", features: [] });
    if (method === "GET") return json(route, { items: [], next_cursor: null });
    m.unexpected.push(`${method} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return { unexpected: m.unexpected, asked };
}

const box = (page: Page, name: string) => page.getByRole("checkbox", { name, exact: true });
const civil = (page: Page) => page.getByRole("button", { name: /موارد الحماية المدنية/ });

test.describe("Interactive map: the field layers by role", () => {
  test.use({ viewport: { width: 1600, height: 1400 } });

  test("the inspector general sees the places of the inspections, the vehicles and the PAR teams", async ({ page }) => {
    test.setTimeout(120_000);
    const m = await mockApi(page);
    await signIn(page, ["inspector_general"], "المتفقد العام");
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/map?layers=inspections,vehicles,par");
    await expect(box(page, "أماكن التفقّدات الدورية")).toBeChecked();
    await expect(box(page, "آخر موقع للآليات")).toBeChecked();
    await expect(box(page, "فرق PAR داخل مناطق الخطر")).toBeChecked();
    await expect(page.getByRole("button", { name: /^مركز الحماية المدنية بالمحرس — .*غير مطابق/ })).toBeVisible();
    // The inspector general opens neither the interventions nor the PAR board: the points have no link.
    await expect(page.getByRole("img", { name: /^VSAV-61-11 · .* — متاح/ })).toBeVisible();
    await expect(page.getByRole("img", { name: /^CCF-61-07 · منطقة ساخنة — لم يؤكّد/ })).toBeVisible();
    await expect(page.getByText("الأماكن المعروضة: 5 · 1 بلا موقع معروف بعد")).toBeVisible();
    // The map of the inspector general reads the field layers only: no reports, no room's layers.
    expect(m.asked.filter((p) => p.startsWith("/api/v1/staff/reports") || p === "/api/v1/staff/places")).toEqual([]);
    expect(m.unexpected).toEqual([]);

    // The panel with the three switches and their legends, then the map zoomed on Sfax.
    await civil(page).scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${SHOTS}/ml-field-general-panel.png` });
    const map = page.locator(".maplibregl-map").first();
    await map.scrollIntoViewIfNeeded();
    const point = await page.getByRole("img", { name: /^VSAV-61-11 · / }).boundingBox();
    if (point) {
      await page.mouse.move(point.x + point.width / 2, point.y + point.height / 2);
      for (let i = 0; i < 6; i += 1) {
        await page.mouse.wheel(0, -400);
        await page.waitForTimeout(300);
      }
    }
    await page.waitForTimeout(3000);
    await map.screenshot({ path: `${SHOTS}/ml-field-general-map.png` });
  });

  test("the head of the room sees the vehicles and the PAR teams, not the inspections", async ({ page }) => {
    test.setTimeout(120_000);
    const m = await mockApi(page);
    await signIn(page, ["ops_manager"], "رئيس القاعة", { scope_level: "regional", gouvernorat_code: 61 });
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/map");
    await civil(page).click();
    await expect(box(page, "أماكن التفقّدات الدورية")).toHaveCount(0);
    await box(page, "آخر موقع للآليات").check();
    await box(page, "فرق PAR داخل مناطق الخطر").check();
    await expect(page.getByRole("button", { name: /^FPT-61-05 · .* — متاح/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^CCF-61-07 · منطقة ساخنة — لم يؤكّد/ })).toBeVisible();
    await expect(page.getByRole("link", { name: "المصدر: مساءلة الفرق PAR" })).toHaveAttribute("href", "/par");
    expect(m.asked).not.toContain(`${F}/inspections`);
    const map = page.locator(".maplibregl-map").first();
    await map.scrollIntoViewIfNeeded();
    await page.waitForTimeout(3000);
    await map.screenshot({ path: `${SHOTS}/ml-field-room-map.png` });
  });

  test("an operator of the room has none of the three", async ({ page }) => {
    await mockApi(page);
    await signIn(page, ["operator"], "عون القاعة", { scope_level: "regional", gouvernorat_code: 61 });
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/map");
    await civil(page).click();
    await expect(box(page, "آخر موقع للآليات")).toHaveCount(0);
    await expect(box(page, "فرق PAR داخل مناطق الخطر")).toHaveCount(0);
    await expect(box(page, "أماكن التفقّدات الدورية")).toHaveCount(0);
  });

  test("hidden by the administrator, the vehicles' layer leaves the commander's panel", async ({ page }) => {
    await mockApi(page, ["map.vehicles"]);
    await signIn(page, ["field_commander"], "القائد الميداني", { scope_level: "regional", gouvernorat_code: 61 });
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/map");
    await civil(page).click();
    await expect(box(page, "فرق PAR داخل مناطق الخطر")).toBeVisible();
    await expect(box(page, "آخر موقع للآليات")).toHaveCount(0);
  });
});
