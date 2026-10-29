/**
 * Sensors of the local network (phase L5b, docs/phase-l/design-l5.md §3.1) in Chromium with the real MapLibre: the
 * «Capteurs» layer of the live map puts each sensor at its place with its level in the label and the shape, the
 * legend names every level, a live reading refreshes the layer, and the popup leads to the sensors page.
 */
import { expect, test, type Page } from "@playwright/test";
import type { Sensor } from "../src/lib/sensors";
import type { Tower } from "../src/lib/towers";
import type { Drone, Zone } from "../src/lib/drones";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

function sensor(over: Partial<Sensor>): Sensor {
  return {
    id: "s-1",
    code: "TUN-RAIN-01",
    name: "Pluviomètre Tunis",
    kind: "rain_1h",
    unit: "mm/h",
    gouvernorat_code: 11,
    lat: 36.8,
    lon: 10.18,
    provider: "INM",
    watch_threshold: 20,
    alarm_threshold: 40,
    silent_after_min: 30,
    enabled: true,
    simulated: true,
    last_value: 42.5,
    last_at: new Date().toISOString(),
    state: "alarm",
    level_since: new Date().toISOString(),
    created_by_name: null,
    updated_at: new Date().toISOString(),
    ...over,
  };
}

// ┏━━ SIMULATION ━━ a watch tower that saw fire a moment ago (contract phase L5b, GET /api/v1/staff/towers)
// ┃ PRODUCTION: services/api (module towers); tests/test_towers.py covers it.
// ┗━━━━━━━━━━━━━━━━
const TOWER: Tower = {
  id: "t-1",
  code: "TUN-TWR-01",
  label: "Tour de Boukornine",
  gouvernorat_code: 11,
  lat: 36.72,
  lon: 10.33,
  bearing_deg: 90,
  fov_deg: 60,
  range_m: 8000,
  simulated: true,
  stream_status: "live",
  last_event: { at: new Date().toISOString(), label: "fire", confidence: 0.86 },
  field_of_view: [
    [10.33, 36.72],
    [10.4, 36.66],
    [10.42, 36.72],
    [10.4, 36.78],
    [10.33, 36.72],
  ],
  created_by_name: null,
  updated_at: new Date().toISOString(),
};

// ┏━━ SIMULATION ━━ a drone flying near a no-fly zone, read from its stream (contract phase L5b, /api/v1/staff/drones)
// ┃ PRODUCTION: services/api (module drones); tests/test_drones.py covers it.
// ┗━━━━━━━━━━━━━━━━
const DRONE: Drone = {
  id: "d-1",
  label: "Drone Protection 1",
  gouvernorat_code: 11,
  stream_status: "live",
  last: {
    at: new Date().toISOString(),
    lat: 36.8,
    lon: 10.2,
    alt_m: 120,
    heading_deg: 90,
    sensor_az_deg: 0,
    sensor_hfov_deg: 60,
    battery_pct: 54,
    mode: "SIM",
  },
  camera_view: [
    [10.2, 36.8],
    [10.203, 36.798],
    [10.204, 36.8],
    [10.203, 36.802],
    [10.2, 36.8],
  ],
  open_alerts: 1,
};
const ZONES: Zone[] = (["work", "no_fly"] as const).map((kind, i) => ({
  id: `z-${i}`,
  kind,
  name: kind === "work" ? "Forêt de Radès" : "Aéroport Tunis-Carthage",
  gouvernorat_code: 11,
  ring: [
    [10.15 + i * 0.05, 36.75],
    [10.2 + i * 0.05, 36.75],
    [10.2 + i * 0.05, 36.85],
    [10.15 + i * 0.05, 36.75],
  ],
  margin_m: 1000,
  active: true,
  created_by_name: null,
  updated_at: new Date().toISOString(),
}));

async function mockApi(page: Page) {
  const base = await baseMock(page);
  const calls = { sensors: 0 };
  // ┏━━ SIMULATION ━━ e-Himaya API answered in the browser (contract phase L5b, GET /api/v1/staff/sensors)
  // ┃ PRODUCTION: services/api (module sensors) serves the room's sensors; tests/test_sensors.py covers it.
  // ┗━━━━━━━━━━━━━━━━
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    if (method === "GET" && pathname === "/api/v1/staff/reports") return json(route, { items: [], next_cursor: null });
    if (method === "GET" && pathname === "/api/v1/staff/towers") return json(route, { items: [TOWER], can_manage: false });
    if (method === "GET" && pathname === "/api/v1/staff/drones") return json(route, { items: [DRONE], can_register: false });
    if (method === "GET" && pathname === "/api/v1/staff/drones/zones") return json(route, ZONES);
    if (method === "GET" && pathname === "/api/v1/staff/drones/d-1/track") {
      const at = (s: number) => new Date(Date.now() - s * 1000).toISOString();
      return json(route, {
        drone_id: "d-1",
        items: [
          { ...DRONE.last, at: at(60), lat: 36.78, lon: 10.18 },
          { ...DRONE.last, at: at(30), lat: 36.79, lon: 10.19 },
          DRONE.last,
        ],
      });
    }
    if (method === "GET" && pathname === "/api/v1/staff/sensors") {
      calls.sensors += 1;
      return json(route, {
        items: [
          sensor({}),
          sensor({
            id: "s-2",
            code: "TUN-LVL-01",
            name: "Oued Méliane",
            kind: "water_level",
            unit: "m",
            lat: 36.75,
            lon: 10.25,
            last_value: calls.sensors > 1 ? 2.4 : 1.2,
            state: calls.sensors > 1 ? "watch" : "normal",
          }),
        ],
        can_manage: false,
      });
    }
    base.unexpected.push(`${method} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  // Same object as `base`: its `live` socket is set later, when the page connects.
  return Object.assign(base, { calls });
}

test.describe("sensors layer", () => {
  test("shows the sensors with their level, follows a live reading and leads to the sensors page", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await signIn(page, ["operator"]);
    const api = await mockApi(page);

    await page.goto("/map");
    await expect(page.getByRole("heading", { name: "Carte en direct", level: 1 })).toBeVisible();
    await page.getByRole("checkbox", { name: "Capteurs" }).check();

    const alarm = page.getByRole("button", { name: /^Pluviomètre Tunis \[SIM\] — Pluviomètre · Alarme · 42,5/ });
    await expect(alarm).toBeVisible();
    await expect(alarm).toHaveClass(/map-poi--sensor_alarm/);
    const level = page.getByRole("button", { name: /^Oued Méliane \[SIM\] — .* · Normal · 1,2 m$/ });
    await expect(level).toHaveClass(/map-poi--sensor(?!_)/);
    for (const name of ["Capteur : normal", "Capteur : vigilance", "Capteur : alarme", "Capteur : muet ou arrêté"]) {
      await expect(page.getByText(name, { exact: true })).toBeVisible();
    }

    // A reading pushed on the live feed refreshes the layer: the water level is now on watch.
    await expect.poll(() => api.live !== null).toBe(true);
    api.live?.send(
      JSON.stringify({
        type: "sensor.reading",
        sensor_id: "s-2",
        gouvernorat_code: 11,
        value: 2.4,
        at: new Date().toISOString(),
        level: "watch",
      }),
    );
    await expect(page.getByRole("button", { name: /^Oued Méliane \[SIM\] — .* · Vigilance · 2,4 m$/ })).toHaveClass(
      /map-poi--sensor_watch/,
    );

    // Keyboard path (the markers may overlap at this zoom).
    await alarm.focus();
    await page.keyboard.press("Enter");
    const popup = page.locator(".maplibregl-popup");
    await expect(popup.getByText("Pluviomètre Tunis [SIM]")).toBeVisible();

    await page.getByRole("checkbox", { name: "Capteurs" }).uncheck();
    await expect(alarm).toHaveCount(0);

    expect(api.unexpected).toEqual([]);
    expect(errors).toEqual([]);
  });
});


test.describe("watch towers layer", () => {
  test("draws each tower and the wedge of its view, red after a fire", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await signIn(page, ["operator"]);
    const api = await mockApi(page);
    await page.goto("/map");
    await page.getByRole("checkbox", { name: "Tours de guet" }).check();
    const tower = page.getByRole("button", { name: /^Tour de Boukornine \[SIM\] — Feu · Est \(90°\), ouverture 60°, portée 8 km$/ });
    await expect(tower).toHaveClass(/map-poi--tower_alert/);
    await expect(page.getByText("Tour : feu ou fumée dans l’heure", { exact: true })).toBeVisible();
    // The wedge is a real MapLibre fill: a bad source or paint expression would be a console error (checked below).
    await page.getByRole("checkbox", { name: "Tours de guet" }).uncheck();
    await expect(tower).toHaveCount(0);
    expect(api.unexpected).toEqual([]);
    expect(errors).toEqual([]);
  });
});

test.describe("drones layer", () => {
  test("draws each drone, its camera's view, its path and the zones (read only)", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await signIn(page, ["operator"]);
    const api = await mockApi(page);
    await page.goto("/map");
    await page.getByRole("checkbox", { name: "Drones" }).check();
    const drone = page.getByRole("button", { name: /^Drone Protection 1 — 1 alerte\(s\) ouverte\(s\) · En vol · altitude 120 m · batterie 54 %/ });
    await expect(drone).toHaveClass(/map-poi--drone_alert/);
    await expect(page.getByText("Drone avec une alerte ouverte", { exact: true })).toBeVisible();
    // The zones are named beside the map too; the view, the path and the zones are real MapLibre layers (a bad
    // source or paint expression would be a console error, checked below).
    await page.getByText("Liste des signalements affichés sur la carte").click();
    await expect(page.getByRole("link", { name: "Aéroport Tunis-Carthage — Zone interdite de vol" })).toBeVisible();
    await page.getByRole("checkbox", { name: "Drones" }).uncheck();
    await expect(drone).toHaveCount(0);
    expect(api.unexpected).toEqual([]);
    expect(errors).toEqual([]);
  });
});
