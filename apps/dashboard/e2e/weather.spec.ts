/**
 * Weather layer of the live map (phase 7 §1, FR-C-08 / FR-C-10) in Chromium with the real MapLibre: the layer's
 * sources and paint expressions are built for real (a bad expression is a console error), the time slider drives
 * the `hour` of the grid requests, and a click on the map opens the point popup with the forecast values, the
 * Open-Meteo attribution and the simulation marker.
 */
import { expect, test, type Page } from "@playwright/test";
import type { WeatherGrid, WeatherPointDetail } from "../src/lib/weatherTypes";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

/** A 5×5 grid around Tunis (0.25°), the centre point in extreme fire danger with a north-west wind. */
function grid(hour: number): WeatherGrid {
  const features: WeatherGrid["features"] = [];
  for (let i = -2; i <= 2; i += 1) {
    for (let j = -2; j <= 2; j += 1) {
      const centre = i === 0 && j === 0;
      features.push({
        type: "Feature",
        geometry: { type: "Point", coordinates: [10.18 + i * 0.25, 36.8 + j * 0.25] },
        properties: {
          wind_speed_kmh: 20 + hour,
          wind_gust_kmh: 40 + hour,
          wind_direction_deg: 315,
          temperature_c: 30,
          humidity_pct: 20,
          precipitation_mm_h: centre ? 0 : 6,
          rain_24h_mm: centre ? 0 : 55,
          fwi: centre ? 70 : 20,
          fire_danger: centre ? "extreme" : "moderate",
          rain_level: centre ? "none" : "warning",
        },
      });
    }
  }
  return {
    type: "FeatureCollection",
    features,
    generated_at: new Date().toISOString(),
    simulated: true,
    attribution: { text: "Open-Meteo.com", url: "https://open-meteo.com/", licence: "CC BY 4.0" },
  };
}

function detail(lat: number, lon: number): WeatherPointDetail {
  const now = new Date();
  now.setMinutes(0, 0, 0);
  return {
    lat,
    lon,
    current: grid(0).features[12]?.properties ?? {},
    hourly: Array.from({ length: 48 }, (_, h) => ({
      time: new Date(now.getTime() + h * 3_600_000).toISOString(),
      ...(grid(h).features[12]?.properties ?? {}),
    })),
    alerts: [{ id: "a-1", title: { ar: "خطر حرائق", fr: "Risque d’incendie extrême" }, severity: "high" }],
    attribution: { text: "Open-Meteo.com", url: "https://open-meteo.com/", licence: "CC BY 4.0" },
    simulated: true,
  };
}

async function mockApi(page: Page) {
  const base = await baseMock(page);
  const hours: number[] = [];
  const points: { lat: number; lon: number }[] = [];
  // ┏━━ SIMULATION ━━ e-Himaya API answered in the browser (contract phase 7 §1)
  // ┃ PRODUCTION: services/api (module weather) serves these from the Open-Meteo snapshot; its own tests cover it.
  // ┗━━━━━━━━━━━━━━━━
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname, searchParams } = new URL(request.url());
    const method = request.method();
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    if (method === "GET" && pathname === "/api/v1/staff/reports") return json(route, { items: [], next_cursor: null });
    if (method === "GET" && pathname === "/api/v1/staff/weather/grid") {
      const hour = Number(searchParams.get("hour"));
      hours.push(hour);
      expect(searchParams.get("bbox")).toMatch(/^-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+$/);
      return json(route, grid(hour));
    }
    if (method === "GET" && pathname === "/api/v1/staff/weather/at") {
      const lat = Number(searchParams.get("lat"));
      const lon = Number(searchParams.get("lon"));
      points.push({ lat, lon });
      return json(route, detail(lat, lon));
    }
    base.unexpected.push(`${method} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return { ...base, hours, points };
}

test.describe("weather layer", () => {
  test("draws the layer, follows the 48 h slider and opens the point popup", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await signIn(page, ["operator"]);
    // Start on Tunis (the gouvernorat of a regional user would do the same).
    await page.addInitScript(() => window.sessionStorage.setItem("ehimaya.mapWeatherLayer", "0"));
    const api = await mockApi(page);

    await page.goto("/map");
    await expect(page.getByRole("heading", { name: "Carte en direct", level: 1 })).toBeVisible();
    await page.getByRole("checkbox", { name: "Météo" }).check();

    const panel = page.getByRole("region", { name: "Couche météo" });
    await expect(panel).toBeVisible();
    await expect.poll(() => api.hours).toContain(0);
    await expect(panel.getByRole("note", { name: "Mode simulation" })).toBeVisible();
    await expect(panel.getByText("Points de grille affichés : 25")).toBeVisible();
    await expect(panel.getByRole("link", { name: "Open-Meteo.com" })).toHaveAttribute("href", "https://open-meteo.com/");
    await expect(panel.getByRole("link", { name: "CC BY 4.0" })).toHaveAttribute(
      "href",
      "https://creativecommons.org/licenses/by/4.0/",
    );
    // Legend: every colour is named.
    for (const name of ["Faible", "Modéré", "Élevé", "Très élevé", "Extrême", "Vigilance pluie", "Alerte pluie"]) {
      await expect(panel.getByRole("group", { name: "Légende de la couche météo" }).getByText(name, { exact: true })).toBeVisible();
    }

    // Time slider: keyboard, value text announced, grid reloaded for that hour (debounced).
    const slider = panel.getByRole("slider", { name: "Heure de prévision (48 h)" });
    await slider.focus();
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    await expect(slider).toHaveValue("3");
    await expect(panel.locator("output")).toContainText("+3 h");
    await expect.poll(() => api.hours.at(-1)).toBe(3);
    await page.keyboard.press("End");
    await expect(slider).toHaveValue("47");
    await expect.poll(() => api.hours.at(-1)).toBe(47);
    await page.keyboard.press("Home");
    await expect(panel.locator("output")).toContainText("Maintenant");
    // Hour 0 was loaded a moment ago: served from the cache, not requested again.
    expect(api.hours.filter((h) => h === 0)).toHaveLength(1);

    // Views can be switched off and on (layer visibility).
    await panel.getByRole("checkbox", { name: "Vent" }).uncheck();
    await panel.getByRole("checkbox", { name: "Vent" }).check();

    // Keyboard path: weather at the map centre.
    await panel.getByRole("button", { name: "Météo au centre de la carte" }).click();
    const popup = page.locator(".maplibregl-popup");
    await expect(popup.getByText("Météo du point")).toBeVisible();
    await expect(popup.getByText("Extrême", { exact: true })).toBeVisible();
    await expect(popup.getByText("IFM 70")).toBeVisible();
    await expect(popup.getByText(/venant du nord-ouest \(315°\)/)).toBeVisible();
    await expect(popup.getByText("Risque d’incendie extrême")).toBeVisible();
    await expect(popup.getByRole("link", { name: "Open-Meteo.com" })).toBeVisible();
    await expect(popup.getByText("[SIM]")).toBeVisible();
    await popup.getByRole("button", { name: /close|fermer/i }).click();
    await expect(popup).toHaveCount(0);

    // Pointer path: a click on the map background asks for the weather of that point.
    const map = page.getByRole("region", { name: /carte/i }).locator("canvas");
    const box = await map.boundingBox();
    if (!box) throw new Error("no map");
    await page.mouse.click(box.x + box.width / 3, box.y + box.height / 3);
    await expect(popup.getByText("Météo du point")).toBeVisible();
    await expect.poll(() => api.points.length).toBe(2);
    // Up and to the left of the centre point asked first: north-west of it.
    const [centre, clicked] = api.points;
    if (!centre || !clicked) throw new Error("no points");
    expect(clicked.lat).toBeGreaterThan(centre.lat);
    expect(clicked.lon).toBeLessThan(centre.lon);

    // Switching the layer off removes the panel and the popup.
    await page.getByRole("checkbox", { name: "Météo" }).uncheck();
    await expect(panel).toHaveCount(0);
    await expect(popup).toHaveCount(0);

    expect(api.unexpected).toEqual([]);
    expect(errors).toEqual([]);
  });
});
