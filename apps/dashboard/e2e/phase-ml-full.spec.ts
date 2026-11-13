/**
 * A full picture of the interactive map for the phase report (Yamen 2026-11-13): the national room with the layers of
 * the system on, over a background drawn from the repository's own geodata (gouvernorats, délégations, lakes and
 * lagoons, wadis, railways, forests), since the browser tests reach no tile server.
 * ┏━━ SIMULATION ━━ the interventions, hotspots, axes, beaches and streams are invented for the picture.
 * ┃ PRODUCTION: the same layers read the API; the background is the map style of the deployment.
 * ┗━━━━━━━━━━━━━━━━
 */
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { expect, test, type Page } from "@playwright/test";
import { E2E_ENV } from "../playwright.config";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-ml";
const C = "/api/v1/staff/crisis";
const ROOT = "../..";
const now = new Date().toISOString();
const GEO = "http://tiles.e2e.test/geo";

const seed = (name: string) => readFileSync(`${ROOT}/services/api/seed/geo/admin/${name}.geojson.gz`);
const osm = (name: string) => readFileSync(`${ROOT}/data/osm/layers/${name}_enriched.geojson`);
const GEO_FILES: Record<string, () => Buffer> = {
  governorates: () => gunzipSync(seed("governorates")),
  delegations: () => gunzipSync(seed("delegations")),
  water: () => gunzipSync(seed("water")),
  rivers: () => osm("rivers"),
  railways: () => osm("railways"),
  forests: () => osm("forests"),
};

const STYLE = {
  version: 8,
  sources: Object.fromEntries(Object.keys(GEO_FILES).map((k) => [k, { type: "geojson", data: `${GEO}/${k}.json` }])),
  layers: [
    { id: "sea", type: "background", paint: { "background-color": "#cfe1ef" } },
    { id: "land", type: "fill", source: "governorates", paint: { "fill-color": "#f6f3ec" } },
    { id: "forests", type: "fill", source: "forests", paint: { "fill-color": "#cfe5c4", "fill-opacity": 0.8 } },
    { id: "water", type: "fill", source: "water", paint: { "fill-color": "#b9d4ea" } },
    { id: "rivers", type: "line", source: "rivers", paint: { "line-color": "#8fb8dc", "line-width": 0.8 } },
    { id: "rail", type: "line", source: "railways", paint: { "line-color": "#9aa0aa", "line-width": 1, "line-dasharray": [3, 2] } },
    { id: "delegations", type: "line", source: "delegations", paint: { "line-color": "#d3cfc4", "line-width": 0.5 } },
    { id: "governorates", type: "line", source: "governorates", paint: { "line-color": "#a7a194", "line-width": 1.2 } },
  ],
};

const square = (lon: number, lat: number, d: number) => ({
  type: "Polygon",
  coordinates: [
    [
      [lon - d, lat - d * 0.8],
      [lon + d, lat - d * 0.8],
      [lon + d * 1.1, lat + d * 0.8],
      [lon - d * 0.9, lat + d * 0.8],
      [lon - d, lat - d * 0.8],
    ],
  ],
});

// Two open axes: a flood in Nabeul (level 3) and a forest fire in Jendouba (level 4).
const AXES = [
  { id: "ax-nabeul", number: 3, name: "فيضان وادي سوحيل", kind: "flood", level: 3, status: "open", gouvernorat_code: 21 },
  { id: "ax-jendouba", number: 4, name: "حريق غابة عين دراهم", kind: "fire", level: 4, status: "open", gouvernorat_code: 32 },
];
const DISASTER_MAP = {
  figures: {},
  areas: [
    { id: "ax-nabeul", level: 3, area: square(10.66, 36.52, 0.2) },
    { id: "ax-jendouba", level: 4, area: square(8.78, 36.72, 0.22) },
  ],
  incidents: [],
  shelters: [
    { id: "sh-1", axis_id: "ax-nabeul", name: "ملجأ دار الشباب بنابل", lat: 36.5, lon: 10.62, capacity: 200, occupants: 85, updated_at: now },
    { id: "sh-2", axis_id: "ax-jendouba", name: "ملجأ المعهد الثانوي بجندوبة", lat: 36.62, lon: 8.78, capacity: 300, occupants: 140, updated_at: now },
  ],
  evacuations: [
    { id: "ev-1", axis_id: "ax-nabeul", name: "حي المهيري", area: square(10.72, 36.46, 0.07), evacuated: 40, updated_at: now },
    { id: "ev-2", axis_id: "ax-jendouba", name: "دوار الحمّام", area: square(8.7, 36.8, 0.08), evacuated: 65, updated_at: now },
  ],
};

const incident = (id: string, category: string, title: string, lat: number, lon: number, severity: number, gov: number) => ({
  id,
  category,
  status: "open",
  gouvernorat_code: gov,
  centroid: { lat, lon },
  severity,
  report_count: 2 + (severity % 7),
  reporter_count: 2,
  opened_at: now,
  updated_at: now,
  closed_at: null,
  merged_into: null,
  title,
});
const INCIDENTS = {
  items: [
    incident("i1", "flood", "مياه في الطابق الأرضي", 36.45, 10.74, 82, 21),
    incident("i2", "fire", "حريق غابة", 36.79, 8.7, 91, 32),
    incident("i3", "traffic_accident", "حادث على الطريق السيارة A1", 36.13, 10.37, 55, 13),
    incident("i4", "fire", "حريق مستودع", 34.76, 10.73, 74, 61),
    incident("i5", "drowning", "غرق في شاطئ بوجعفر", 35.84, 10.64, 66, 51),
    incident("i6", "medical", "حالة صحية طارئة", 33.88, 10.1, 35, 81),
    incident("i7", "chemical_leak", "تسرب غاز في المنطقة الصناعية", 33.87, 10.12, 88, 81),
    incident("i8", "landslide", "انزلاق أرضي", 36.17, 8.71, 47, 33),
    incident("i9", "flood", "فيضان وادي", 35.04, 8.7, 52, 41),
    incident("i10", "fire", "حريق في منزل", 36.81, 10.18, 61, 11),
  ],
  next_cursor: null,
};

function hexes() {
  const centres: [number, number, number][] = [
    [10.18, 36.8, 14],
    [10.63, 35.83, 9],
    [10.74, 34.75, 11],
    [10.11, 33.88, 6],
  ];
  const r = 0.045;
  const features = [];
  for (const [lon0, lat0, peak] of centres) {
    for (let i = -2; i <= 2; i += 1) {
      for (let j = -2; j <= 2; j += 1) {
        const cx = lon0 + i * r * 1.75 + (j % 2) * r * 0.87;
        const cy = lat0 + j * r * 1.5;
        const count = Math.max(0, Math.round(peak - Math.hypot(i, j) * peak * 0.38));
        if (count === 0) continue;
        const ring = Array.from({ length: 7 }, (_, k) => {
          const a = (Math.PI / 3) * k + Math.PI / 6;
          return [cx + r * 0.95 * Math.cos(a), cy + r * 0.8 * Math.sin(a)];
        });
        features.push({ type: "Feature", properties: { count }, geometry: { type: "Polygon", coordinates: [ring] } });
      }
    }
  }
  return { type: "FeatureCollection", features, cell_size_m: 1000 };
}

const beach = (id: string, name: string, lat: number, lon: number, level: "green" | "yellow" | "red", score: number) => ({
  id,
  name,
  lat,
  lon,
  gouvernorat_code: null,
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
  beaches: [
    beach("b1", "شاطئ بنزرت", 37.29, 9.87, "green", 22),
    beach("b2", "شاطئ قمرت", 36.92, 10.29, "yellow", 48),
    beach("b3", "شاطئ الحمامات", 36.39, 10.6, "yellow", 45),
    beach("b4", "شاطئ بوجعفر", 35.83, 10.64, "red", 78),
    beach("b5", "شاطئ المنستير", 35.77, 10.83, "green", 30),
    beach("b6", "شاطئ المهدية", 35.51, 11.07, "yellow", 51),
    beach("b7", "شاطئ جربة سيدي محرز", 33.88, 10.97, "green", 18),
    beach("b8", "شاطئ طبرقة", 36.96, 8.75, "red", 81),
  ],
  heat_risk: [],
  heat_drownings: [],
};

const stream = (id: string, label: string, source: string, lat: number, lon: number, fire: number | null) => ({
  id,
  report_id: null,
  tracking_code: null,
  source,
  label,
  status: "live",
  started_at: now,
  ended_at: null,
  duration_s: 300,
  gouvernorat_code: null,
  last_location: { lat, lon },
  max_fire_confidence: fire,
  max_smoke_confidence: null,
  recordings_count: 0,
  simulated: true,
});
const STREAMS = {
  items: [
    stream("s1", "شاحنة إطفاء نابل 2", "crew", 36.47, 10.7, null),
    stream("s2", "كاميرا برج عين دراهم", "camera", 36.77, 8.68, 0.86),
    stream("s3", "طائرة مسيّرة صفاقس", "drone", 34.78, 10.7, null),
    stream("s4", "مواطن في سوسة", "app", 35.83, 10.6, null),
  ],
  next_cursor: null,
};

async function mockApi(page: Page) {
  const m = await baseMock(page);
  await page.route(E2E_ENV.VITE_MAP_STYLE_URL, (route) => json(route, STYLE));
  await page.route(`${GEO}/*.json`, (route) => {
    const name = new URL(route.request().url()).pathname.split("/").pop()?.replace(".json", "") ?? "";
    const file = GEO_FILES[name];
    return file ? route.fulfill({ status: 200, contentType: "application/json", body: file() }) : route.abort();
  });
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    if (pathname === "/api/v1/staff/streams") return json(route, STREAMS);
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    if (pathname === `${C}/axes`) return json(route, { items: AXES });
    if (pathname === `${C}/disasters/map`) return json(route, DISASTER_MAP);
    if (pathname === `${C}/exposure/map`) return json(route, { items: [] });
    if (pathname === "/api/v1/staff/incidents") return json(route, INCIDENTS);
    if (pathname === "/api/v1/staff/analytics/hotspots") return json(route, hexes());
    if (pathname === "/api/v1/staff/coastal/overview") return json(route, COASTAL);
    if (method === "GET") return json(route, { items: [], next_cursor: null });
    m.unexpected.push(`${method} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return m;
}

test.describe("Interactive map: full picture", () => {
  test.use({ viewport: { width: 1600, height: 1500 } });

  test("the national room sees the layers of the system on the whole country", async ({ page }) => {
    test.setTimeout(120_000);
    await mockApi(page);
    await signIn(page, ["operator"], "القاعة الوطنية");
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/map?layers=incidents,hotspots,crisis,coastal,streams");
    await expect(page.getByRole("checkbox", { name: "التدخّلات المفتوحة" })).toBeChecked();
    await expect(page.getByRole("button", { name: /^حريق غابة —/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^شاطئ طبرقة \[SIM\] —/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^كاميرا برج عين دراهم \[SIM\] —/ })).toBeVisible();
    const map = page.locator(".maplibregl-map").first();
    await map.scrollIntoViewIfNeeded();
    await page.waitForTimeout(6000);
    await map.screenshot({ path: `${SHOTS}/ml-full-map.png` });
    await page.screenshot({ path: `${SHOTS}/ml-full-page.png`, fullPage: true });
  });
});
