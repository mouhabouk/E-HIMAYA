/**
 * Operations room wall view (map/room) in Chromium with the real MapLibre: the street style is restyled for the dark
 * wall without a console error, the 3D layers are built, the day's figures, readiness and alerts come from the staff
 * API, and a report picked in the list opens its card. Set OPS_ROOM_SHOT=<file.png> to also save a screenshot.
 */
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { E2E_ENV } from "../playwright.config";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

// ┏━━ SIMULATION ━━ reports, figures, means and alerts of a Tunis operations room
// ┃ PRODUCTION: the same endpoints answered by the API (reports, kpis, analytics hotspots, resources, alerts).
// ┃ The map style is built here from the repository's own geography (gouvernorat boundaries and OpenStreetMap
// ┃ layers) because the test has no tile server; production uses the self-hosted vector tiles (infra/maps).
// ┗━━━━━━━━━━━━━━━━

const BBOX = [9.9, 36.6, 10.45, 37.05] as const;
type Geo = { type: "FeatureCollection"; features: { geometry: { type: string; coordinates: unknown } | null; properties: Record<string, unknown> }[] };

function inBox(c: unknown): boolean {
  if (Array.isArray(c) && typeof c[0] === "number") {
    const [x, y] = c as number[];
    return x !== undefined && y !== undefined && x >= BBOX[0] && x <= BBOX[2] && y >= BBOX[1] && y <= BBOX[3];
  }
  return Array.isArray(c) && c.some(inBox);
}

function layer(path: string): Geo {
  const all = JSON.parse(readFileSync(new URL(`../../../${path}`, import.meta.url), "utf8")) as Geo;
  return { type: "FeatureCollection", features: all.features.filter((f) => f.geometry && inBox(f.geometry.coordinates)) };
}

/** A street-style stand-in with the layer ids of infra/maps/styles/ehimaya-streets.json the room restyles. */
function style() {
  return {
    version: 8,
    sources: {
      gov: { type: "geojson", data: layer("services/api/seed/geo/tn_gouvernorats.geojson") },
      lakes: { type: "geojson", data: layer("data/osm/layers/lakes_enriched.geojson") },
      rivers: { type: "geojson", data: layer("data/osm/layers/rivers_enriched.geojson") },
      rail: { type: "geojson", data: layer("data/osm/layers/railways_enriched.geojson") },
      forests: { type: "geojson", data: layer("data/osm/layers/forests_enriched.geojson") },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#e8eef2" } },
      { id: "landuse-residential", type: "fill", source: "gov", paint: { "fill-color": "#f2efe9" } },
      { id: "landcover-wood", type: "fill", source: "forests", paint: { "fill-color": "#cfe3c3" } },
      { id: "water", type: "fill", source: "lakes", paint: { "fill-color": "#a9d3f5" } },
      { id: "waterway", type: "line", source: "rivers", paint: { "line-color": "#7fb6e8", "line-width": 1.2 } },
      { id: "railway", type: "line", source: "rail", paint: { "line-color": "#999", "line-width": 1, "line-dasharray": [3, 2] } },
      { id: "boundary-state", type: "line", source: "gov", paint: { "line-color": "#999", "line-width": 1.2 } },
    ],
  };
}

const CATS = ["traffic_accident", "medical", "fire", "traffic_accident", "medical", "flood", "fire", "sos", "other"] as const;
const STATUSES = ["closed", "closed", "received", "in_progress", "closed", "intervened", "ongoing", "closed"] as const;

function reports() {
  const now = Date.now();
  const centres: [number, number][] = [
    [10.18, 36.81],
    [10.12, 36.85],
    [10.23, 36.75],
    [10.06, 36.79],
    [10.3, 36.86],
  ];
  return Array.from({ length: 96 }, (_, i) => {
    const c = centres[i % centres.length] ?? [10.18, 36.8];
    const a = (i * 137.5 * Math.PI) / 180;
    const r = 0.004 + ((i * 7) % 23) * 0.0012;
    const status = STATUSES[i % STATUSES.length] ?? "closed";
    return {
      id: `r-${i}`,
      tracking_code: `EH-${String(4100 + i)}`,
      category: CATS[i % CATS.length] ?? "other",
      status,
      text: null,
      lang: null,
      location: { lon: c[0] + Math.cos(a) * r, lat: c[1] + Math.sin(a) * r * 0.8 },
      gouvernorat_code: 11,
      delegation_id: null,
      created_at: new Date(now - ((i * 977) % 86_000) * 1000).toISOString(),
      received_at: new Date(now - ((i * 977) % 86_000) * 1000).toISOString(),
      updated_at: new Date(now).toISOString(),
      reporter_kind: "citizen",
      media_count: 0,
      text_ar: null,
      priority_score: status === "closed" ? null : 40 + ((i * 13) % 60),
      credibility_score: null,
      analysis_state: null,
      lives_at_risk: null,
      suggested_category: null,
      incident_id: null,
      has_suggestion: false,
    };
  });
}

function hexes() {
  const r = 0.0055;
  const features = [];
  for (let i = 0; i < 9; i += 1) {
    for (let j = 0; j < 7; j += 1) {
      const cx = 10.11 + i * r * 1.75 + (j % 2) * r * 0.87;
      const cy = 36.77 + j * r * 1.5;
      const d = Math.hypot(cx - 10.17, (cy - 36.8) * 1.2);
      const count = Math.max(0, Math.round(14 - d * 120 + ((i * 3 + j * 5) % 4)));
      if (count === 0) continue;
      const ring = Array.from({ length: 7 }, (_, k) => {
        const t = (Math.PI / 3) * k + Math.PI / 6;
        return [cx + r * 0.95 * Math.cos(t), cy + r * 0.8 * Math.sin(t)];
      });
      features.push({ type: "Feature", properties: { count }, geometry: { type: "Polygon", coordinates: [ring] } });
    }
  }
  return { type: "FeatureCollection", features, cell_size_m: 1000 };
}

function units() {
  const cp = layer("data/osm/layers/civil_protection_enriched.geojson");
  return {
    type: "FeatureCollection",
    features: cp.features
      .filter((f) => f.geometry?.type === "Point")
      .map((f, i) => ({
        type: "Feature",
        geometry: f.geometry,
        properties: { layer: "unit", id: `u-${i}`, name: `Unité ${i + 1}`, name_fr: `Unité ${i + 1}`, kind: "station", phone: null },
      })),
  };
}

async function mockRoom(page: Page) {
  const base = await baseMock(page);
  const rows = reports();
  const byStatus: Record<string, number> = {};
  const byCategory: Record<string, number> = {};
  for (const r of rows) {
    byStatus[r.status] = (byStatus[r.status] ?? 0) + 1;
    byCategory[r.category] = (byCategory[r.category] ?? 0) + 1;
  }
  await page.route(E2E_ENV.VITE_MAP_STYLE_URL, (route) => json(route, style()));
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    if (method !== "GET") {
      base.unexpected.push(`${method} ${pathname}`);
      return json(route, { detail: "not_found" }, 404);
    }
    if (pathname === "/api/v1/staff/reports") return json(route, { items: rows, next_cursor: null });
    if (pathname === "/api/v1/staff/kpis")
      return json(route, {
        since: new Date().toISOString(),
        total: rows.length,
        by_status: byStatus,
        by_category: byCategory,
        by_gouvernorat: [{ code: 11, count: rows.length }],
        avg_first_response_s: 412,
        high_priority: 7,
        analysis_pending: 0,
      });
    if (pathname === "/api/v1/staff/analytics/hotspots") return json(route, hexes());
    if (pathname === "/api/v1/staff/resources/summary")
      return json(route, {
        by_kind: {
          ambulance: { available: 18, assigned: 3, out_of_service: 2 },
          fire_engine: { available: 9, assigned: 4, out_of_service: 1 },
          rescue_vehicle: { available: 11, assigned: 2 },
        },
      });
    if (pathname === "/api/v1/staff/resources/map") return json(route, units());
    if (pathname === "/api/v1/staff/alerts/active")
      return json(route, [
        {
          id: "m-1",
          kind: "alert",
          status: "published",
          title: { ar: "نشرة متابعة: أمطار رعدية على تونس الكبرى", fr: "Vigilance orages sur le Grand Tunis" },
          body: { ar: "", fr: "" },
          channels: ["push"],
          topic: null,
          audience: null,
          user_id: null,
          severity: "medium",
          category: "weather",
          hazard: null,
          expires_at: null,
          area: { kind: "gouvernorats", gouvernorats: [11] },
          created_by: null,
          created_at: new Date().toISOString(),
          published_by: null,
          published_at: new Date(Date.now() - 50 * 60_000).toISOString(),
          cancelled_at: null,
          version: 1,
          stats: {},
        },
      ]);
    base.unexpected.push(`${method} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return base;
}

test("the operations room shows the day's figures and a 3D map, and opens a report's card", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(e.message));
  await signIn(page, ["operator"], "Salle Tunis", { scope_level: "regional", gouvernorat_code: 11 });
  await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
  const mock = await mockRoom(page);
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto("/map/room");

  await expect(page.getByRole("heading", { level: 1, name: "غرفة العمليات" })).toBeVisible();
  await expect(page.getByRole("region", { name: /خريطة غرفة العمليات/ }).locator("canvas")).toBeVisible();
  await expect(page.getByText("بلاغات اليوم", { exact: true })).toBeVisible();
  await expect(page.getByText("96", { exact: true })).toBeVisible();
  await expect(page.getByText("نشرة متابعة: أمطار رعدية على تونس الكبرى")).toBeVisible();
  await expect(page.getByText("سيارة إسعاف")).toBeVisible();

  // The top open report of the list opens its card on the map.
  const list = page.getByRole("region", { name: "بلاغات مفتوحة حسب الأولوية" });
  await list.getByRole("button").first().click();
  const card = page.getByRole("complementary", { name: "البلاغ المحدد" });
  await expect(card).toBeVisible();
  await expect(card.getByText(/^EH-\d+$/)).toBeVisible();
  await expect(card.getByRole("link", { name: "فتح البلاغ" })).toHaveAttribute("href", /\/reports\/r-\d+$/);

  // 2D and back: the switch is a pressed toggle.
  const toggle = page.getByRole("button", { name: "3D" });
  await expect(toggle).toHaveAttribute("aria-pressed", "true");

  const box = await page.locator(".ops-room__map canvas").boundingBox();
  expect(box?.height ?? 0).toBeGreaterThan(400);
  await page.waitForTimeout(2500);
  const shot = process.env.OPS_ROOM_SHOT;
  if (shot) await page.screenshot({ path: shot });
  expect(errors).toEqual([]);
  expect(mock.unexpected).toEqual([]);
});
