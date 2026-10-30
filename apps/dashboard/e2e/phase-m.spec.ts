/**
 * Phase M on the real MapLibre map (docs/phase-m/design-m.md §4, §7): glass report markers by incident type, the
 * délégation boundaries coloured by reports per 10,000 inhabitants, a saved place recorded by clicking the map, and
 * the focus view a double click opens and closes. Screenshots for the phase report land in test-results/phase-m/.
 */
import { expect, test, type Page } from "@playwright/test";
import type { SavedPlace } from "../src/lib/places";
import type { Category, ReportStatus } from "../src/lib/types";
import { makeReport } from "../src/test/fixtures";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-m";

/** Reports around Sfax, one of each incident type. */
const REPORTS: [Category, ReportStatus, number, number][] = [
  ["fire", "received", 10.76, 34.74],
  ["flood", "in_progress", 10.71, 34.77],
  ["traffic_accident", "intervened", 10.8, 34.72],
  ["drowning", "received", 10.84, 34.76],
  ["medical", "closed", 10.73, 34.71],
  ["chemical_leak", "ongoing", 10.68, 34.74],
  ["landslide", "received", 10.78, 34.79],
  ["sos", "received", 10.75, 34.76],
];

/** Four délégations of Sfax as squares (the real outlines come from Map Tunisia). */
function delegations() {
  const square = (lon: number, lat: number) => [
    [
      [lon, lat],
      [lon + 0.06, lat],
      [lon + 0.06, lat + 0.04],
      [lon, lat + 0.04],
      [lon, lat],
    ],
  ];
  const units = [
    [6114, "صفاقس المدينة", "Sfax Ville", 10.73, 34.73, 102_000],
    [6112, "صفاقس الغربية", "Sfax Ouest", 10.67, 34.73, 98_000],
    [6113, "صفاقس الجنوبية", "Sfax Sud", 10.73, 34.69, 120_000],
    [6110, "ساقية الدائر", "Sakiet Eddaïer", 10.79, 34.77, 70_000],
  ] as const;
  return {
    type: "FeatureCollection",
    attribution: "© OpenStreetMap contributors · Map Tunisia by Alaa Taieb",
    features: units.map(([id, ar, fr, lon, lat, pop]) => ({
      type: "Feature",
      id,
      properties: { id, name_ar: ar, name_fr: fr, name_en: fr, ins_code: String(id), population_2024: pop, area_km2: 20 },
      geometry: { type: "Polygon", coordinates: square(lon, lat) },
    })),
  };
}

async function mockApi(page: Page) {
  const base = await baseMock(page);
  const places: SavedPlace[] = [];
  // ┏━━ SIMULATION ━━ e-Himaya API answered in the browser (phase M)
  // ┃ PRODUCTION: services/api serves these (modules reports, geo, places); its own tests cover them.
  // ┗━━━━━━━━━━━━━━━━
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    // Before the common answers, which give an empty list of places.
    if (method === "GET" && pathname === "/api/v1/staff/places") return json(route, places);
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    if (method === "GET" && pathname === "/api/v1/staff/reports") {
      const items = REPORTS.map(([category, status, lon, lat], i) =>
        makeReport({ id: `r-${i}`, tracking_code: `SFX-${100 + i}`, category, status, location: { lon, lat }, gouvernorat_code: 61 }),
      );
      return json(route, { items, next_cursor: null });
    }
    if (method === "GET" && pathname === "/api/v1/geo/boundaries/delegations") return json(route, delegations());
    if (method === "GET" && pathname === "/api/v1/staff/kpis/delegations") {
      return json(route, [
        { delegation_id: 6114, count: 12 },
        { delegation_id: 6112, count: 3 },
        { delegation_id: 6113, count: 6 },
      ]);
    }
    if (method === "POST" && pathname === "/api/v1/staff/places") {
      const body = request.postDataJSON() as Pick<SavedPlace, "name" | "kind" | "note" | "lat" | "lon">;
      const place: SavedPlace = {
        id: `p-${places.length + 1}`,
        ...body,
        gouvernorat_code: 61,
        delegation_id: 6114,
        created_by_name: "Sami Operator",
        created_at: new Date().toISOString(),
        updated_by_name: "Sami Operator",
        updated_at: new Date().toISOString(),
      };
      places.push(place);
      return json(route, place, 201);
    }
    return json(route, method === "GET" ? [] : { detail: "not_found" }, method === "GET" ? 200 : 404);
  });
  return { ...base, places };
}

test.describe("phase M map", () => {
  test("glass markers, boundaries by rate, a saved place and the focus view", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await signIn(page, ["operator"]);
    await page.addInitScript(() => {
      window.localStorage.setItem("ehimaya.lang", "ar");
      window.sessionStorage.setItem("ehimaya.mapAdminLayer", "1");
      window.sessionStorage.setItem("ehimaya.mapAdminLevel", "delegations");
      window.sessionStorage.setItem("ehimaya.mapAdminRate", "1");
    });
    const api = await mockApi(page);
    await page.goto("/map");

    // One glass hexagon per incident type, named for screen readers.
    const markers = page.locator(".map-marker");
    await expect(markers).toHaveCount(REPORTS.length);
    for (const [category] of REPORTS) await expect(page.locator(`.map-marker--${category}`)).toHaveCount(1);
    await expect(page.getByRole("heading", { name: "الأماكن الهامة" })).toBeVisible();
    const frame = page.locator(".map-frame").first();
    await frame.scrollIntoViewIfNeeded();
    // Zoom on Sfax with the wheel, over the fire.
    const fire = await page.locator(".map-marker--fire").boundingBox();
    if (!fire) throw new Error("no marker");
    await page.mouse.move(fire.x + fire.width / 2, fire.y + fire.height / 2);
    for (let i = 0; i < 9; i++) {
      await page.mouse.wheel(0, -400);
      await page.waitForTimeout(250);
    }
    await expect(markers).toHaveCount(REPORTS.length);
    await page.waitForTimeout(1500);
    await frame.screenshot({ path: `${SHOTS}/m-map-markers-rate.png` });

    // Save a place: switch on, click the map, fill the form.
    await page.getByRole("button", { name: "تسجيل مكان" }).click();
    const map = page.locator(".maplibregl-canvas");
    const box = await map.boundingBox();
    if (!box) throw new Error("no map");
    await map.click({ position: { x: box.width * 0.3, y: box.height * 0.35 } });
    await page.locator(".place-form").getByLabel("الاسم").fill("مستودع المحروقات");
    const form = page.locator(".place-form");
    await form.getByLabel("حرج").check();
    await page.getByLabel("معلومات إضافية").fill("المدخل من طريق قابس، خزانات بسعة 200 ألف لتر");
    await frame.screenshot({ path: `${SHOTS}/m-place-form.png` });
    await page.getByRole("button", { name: "حفظ" }).click();
    await expect.poll(() => api.places.length).toBe(1);
    expect(api.places[0]?.kind).toBe("critical");
    await expect(page.locator(".saved-places__item--critical")).toHaveCount(1);

    // Focus view: a double click on the fire lifts its place in 3D and dims the rest; the button goes back.
    await page.locator(".map-marker--fire").dblclick();
    const exit = page.getByRole("button", { name: "العودة إلى العرض العادي" });
    await expect(exit).toBeVisible();
    await expect(page.locator(".map--focused")).toHaveCount(1);
    await page.waitForTimeout(1800);
    await frame.screenshot({ path: `${SHOTS}/m-focus-3d.png` });
    await page.locator(".saved-places").screenshot({ path: `${SHOTS}/m-places-list.png` });
    await exit.click();
    await expect(page.locator(".map--focused")).toHaveCount(0);
    expect(errors).toEqual([]);
    expect(api.unexpected).toEqual([]);
  });
});
