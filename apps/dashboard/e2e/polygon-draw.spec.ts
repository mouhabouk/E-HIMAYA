/**
 * Drawing an alert area on the real MapLibre map (FR-C-18), in Chromium: unit tests replace the map with a stand-in
 * (jsdom has no WebGL), so this checks the clicks → vertices → request body path end to end.
 */
import { expect, test, type Locator, type Page, type Route } from "@playwright/test";
import type { Message, MessageBody } from "../src/lib/opsTypes";
import { E2E_ENV } from "../playwright.config";

const API = E2E_ENV.VITE_API_BASE_URL;
interface Bounds {
  west: number;
  south: number;
  east: number;
  north: number;
}
/** National editor: a new area is drawn on the whole country (TUNISIA_BOUNDS). */
const TUNISIA: Bounds = { west: 7.4, south: 30.2, east: 11.7, north: 37.6 };
/** A saved area reopens fitted to its vertices with this margin (verticesBounds). */
const AREA_MARGIN = 0.02;
/** fitBoundsOptions of PolygonDrawMap. */
const FIT_PADDING = 24;
const TILE_SIZE = 512;

type Pixel = [x: number, y: number];
type Position = [lon: number, lat: number];

// ┏━━ SIMULATION ━━ signed-in staff session (unsigned JWT with the content_editor role, national scope)
// ┃ PRODUCTION: Keycloak (realm ehimaya-staff) issues a signed token after Authorization Code + PKCE and MFA; the
// ┃ API verifies it. To run against a real stack, remove this and sign in through the Keycloak login page first.
// ┗━━━━━━━━━━━━━━━━
function fakeAccessToken(): string {
  const b64url = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  const now = Math.floor(Date.now() / 1000);
  const claims = {
    iss: E2E_ENV.VITE_OIDC_ISSUER,
    sub: "e2e-editor",
    name: "Rim Editor",
    exp: now + 3600,
    iat: now,
    realm_access: { roles: ["content_editor"] },
    scope_level: "national",
  };
  return `${b64url({ alg: "none", typ: "JWT" })}.${b64url(claims)}.`;
}

async function signIn(page: Page): Promise<void> {
  const key = `oidc.user:${E2E_ENV.VITE_OIDC_ISSUER}:${E2E_ENV.VITE_OIDC_CLIENT_ID}`;
  const user = JSON.stringify({
    access_token: fakeAccessToken(),
    token_type: "Bearer",
    scope: "openid profile",
    profile: { sub: "e2e-editor", iss: E2E_ENV.VITE_OIDC_ISSUER, aud: E2E_ENV.VITE_OIDC_CLIENT_ID, exp: 0, iat: 0 },
    expires_at: Math.floor(Date.now() / 1000) + 3600,
  });
  await page.addInitScript(
    ([storageKey, value]) => {
      window.sessionStorage.setItem(storageKey, value);
      window.localStorage.setItem("ehimaya.lang", "fr");
    },
    [key, user] as const,
  );
}

// ┏━━ SIMULATION ━━ e-Himaya API (notifications, gouvernorats, levels, live events) answered in the browser
// ┃ PRODUCTION: services/api (FastAPI + PostGIS) validates and stores the polygon (§7 of docs/api/phase-5-contract.md);
// ┃ its own tests cover that side (services/api/tests/test_notifications.py). To run against a real stack, point
// ┃ VITE_API_BASE_URL at it and remove mockApi.
// ┗━━━━━━━━━━━━━━━━
interface ApiMock {
  created: MessageBody[];
  updated: MessageBody[];
  unexpected: string[];
}

function messageFrom(body: MessageBody, version: number): Message {
  return {
    id: "m-e2e",
    kind: body.kind,
    status: "draft",
    title: { ar: body.title.ar, fr: body.title.fr, en: body.title.en },
    body: { ar: body.body.ar, fr: body.body.fr, en: body.body.en },
    channels: body.channels,
    topic: null,
    audience: null,
    user_id: null,
    severity: body.severity ?? null,
    category: body.category ?? null,
    hazard: body.hazard ?? null,
    expires_at: body.expires_at ?? null,
    area: { gouvernorat_codes: body.area.gouvernorat_codes, polygon: body.area.polygon ?? null },
    created_by: "Rim Editor",
    created_at: new Date().toISOString(),
    published_by: null,
    published_at: null,
    cancelled_at: null,
    version,
    stats: {},
  };
}

async function mockApi(page: Page): Promise<ApiMock> {
  const mock: ApiMock = { created: [], updated: [], unexpected: [] };
  let stored: Message | null = null;
  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

  await page.routeWebSocket(`${API.replace("http", "ws")}/api/v1/staff/live`, () => {
    // Accept the connection and stay silent: no live event is needed here.
  });
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    if (method === "GET" && pathname === "/api/v1/geo/gouvernorats") {
      return json(route, [
        { code: 11, iso_code: "TN-11", name: "تونس", name_ar: "تونس", name_fr: "Tunis", delegation_count: 21 },
        { code: 61, iso_code: "TN-61", name: "صفاقس", name_ar: "صفاقس", name_fr: "Sfax", delegation_count: 16 },
      ]);
    }
    if (method === "GET" && pathname === "/api/v1/staff/levels") return json(route, []);
    if (method === "GET" && pathname === "/api/v1/app/environment") return json(route, { banner: null });
    if (method === "POST" && pathname === "/api/v1/staff/notifications") {
      const body = request.postDataJSON() as MessageBody;
      mock.created.push(body);
      stored = messageFrom(body, 1);
      return json(route, stored, 201);
    }
    if (pathname === "/api/v1/staff/notifications/m-e2e") {
      if (method === "GET" && stored) return json(route, stored);
      if (method === "PUT" && stored) {
        const body = request.postDataJSON() as MessageBody;
        mock.updated.push(body);
        stored = messageFrom(body, stored.version + 1);
        return json(route, stored);
      }
    }
    if (method === "GET" && pathname === "/api/v1/staff/notifications/m-e2e/audience") {
      return json(route, { push: 120, sms: 0, email: 0 });
    }
    mock.unexpected.push(`${method} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return mock;
}

// ┏━━ SIMULATION ━━ map style: a blank background, no tiles, glyphs or sprites
// ┃ PRODUCTION: VITE_MAP_STYLE_URL points at the self-hosted vector style, or the OpenStreetMap raster fallback is
// ┃ used (src/lib/mapStyle.ts). Drawing does not depend on what the base map shows.
// ┗━━━━━━━━━━━━━━━━
async function mockMapStyle(page: Page): Promise<void> {
  await page.route(E2E_ENV.VITE_MAP_STYLE_URL, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        version: 8,
        sources: {},
        layers: [{ id: "background", type: "background", paint: { "background-color": "#e8eef2" } }],
      }),
    }),
  );
}

/** Any other host is refused: the test must never depend on the network. */
async function blockOtherHosts(page: Page, blocked: string[]): Promise<void> {
  await page.route(
    (url) => url.hostname !== "localhost" && !url.hostname.endsWith(".e2e.test"),
    (route) => {
      blocked.push(route.request().url());
      return route.abort();
    },
  );
}

// Web Mercator, as MapLibre computes it: positions ↔ pixels of a map whose camera was fitted to some bounds.
const mercX = (lon: number) => (lon + 180) / 360;
const mercY = (lat: number) => (1 - Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) / Math.PI) / 2;
const latOf = (my: number) => (360 / Math.PI) * Math.atan(Math.exp(Math.PI * (1 - 2 * my))) - 90;

interface Camera {
  /** Centre in Mercator units (0–1). */
  cx: number;
  cy: number;
  /** Size of the whole world in pixels. */
  world: number;
  width: number;
  height: number;
}

/** The camera of `new Map({ bounds, fitBoundsOptions: { padding: 24, maxZoom: 13 } })` in a canvas of this size. */
function fitted(bounds: Bounds, width: number, height: number): Camera {
  const [x0, x1, y0, y1] = [mercX(bounds.west), mercX(bounds.east), mercY(bounds.north), mercY(bounds.south)];
  const world = Math.min(
    (width - 2 * FIT_PADDING) / (x1 - x0),
    (height - 2 * FIT_PADDING) / (y1 - y0),
    TILE_SIZE * 2 ** 13,
  );
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, world, width, height };
}

function positionAt(c: Camera, [x, y]: Pixel): Position {
  return [(c.cx + (x - c.width / 2) / c.world) * 360 - 180, latOf(c.cy + (y - c.height / 2) / c.world)];
}

function pixelAt(c: Camera, [lon, lat]: Position): Pixel {
  return [c.width / 2 + (mercX(lon) - c.cx) * c.world, c.height / 2 + (mercY(lat) - c.cy) * c.world];
}

interface DrawingMap {
  /** The map canvas: clicks and pixel positions are relative to it. */
  map: Locator;
  at: (dx: number, dy: number) => Pixel;
  positionAt: (pixel: Pixel) => Position;
  pixelAt: (position: Position) => Pixel;
  /** About a pixel and a half, in degrees of longitude: a click lands on whole CSS pixels and MapLibre rounds too. */
  tolerance: number;
}

async function drawingMap(page: Page, bounds: Bounds): Promise<DrawingMap> {
  const region = page.getByRole("region", { name: "Carte de la zone d’alerte" });
  const map = region.locator("canvas.maplibregl-canvas");
  await expect(map).toBeVisible();
  // MapLibre 6 renders with WebGL2 only: the canvas must hold such a context (getContext returns the existing one).
  expect(await map.evaluate((c: HTMLCanvasElement) => c.getContext("webgl2") !== null)).toBe(true);
  const box = await map.boundingBox();
  if (!box) throw new Error("map has no size");
  const camera = fitted(bounds, box.width, box.height);
  return {
    map,
    at: (dx, dy) => [Math.round(box.width / 2 + dx), Math.round(box.height / 2 + dy)],
    positionAt: (pixel) => positionAt(camera, pixel),
    pixelAt: (position) => pixelAt(camera, position),
    tolerance: 1.5 * (360 / camera.world),
  };
}

async function clickMap(map: Locator, [x, y]: Pixel): Promise<void> {
  await map.click({ position: { x, y } });
}

function expectRing(actual: number[][] | undefined, expected: Position[], tolerance: number): void {
  expect(actual).toBeDefined();
  const ring = actual ?? [];
  // Closed ring: the first position is repeated at the end.
  expect(ring).toHaveLength(expected.length + 1);
  expect(ring.at(-1)).toEqual(ring[0]);
  ring.slice(0, -1).forEach(([lon = Number.NaN, lat = Number.NaN], i) => {
    const [eLon, eLat] = expected[i] ?? [Number.NaN, Number.NaN];
    expect(Math.abs(lon - eLon), `longitude of vertex ${i}`).toBeLessThanOrEqual(tolerance);
    // A pixel spans fewer degrees of latitude than of longitude (Mercator).
    expect(Math.abs(lat - eLat), `latitude of vertex ${i}`).toBeLessThanOrEqual(tolerance * Math.cos((eLat * Math.PI) / 180));
  });
}

test.describe("alert area drawn on the map", () => {
  let api: ApiMock;
  const blocked: string[] = [];

  test.beforeEach(async ({ page }) => {
    blocked.length = 0;
    await blockOtherHosts(page, blocked);
    await mockMapStyle(page);
    api = await mockApi(page);
    await signIn(page);
  });

  test.afterEach(() => {
    expect(api.unexpected, "API calls without a mock").toEqual([]);
    expect(blocked, "requests outside the test hosts").toEqual([]);
  });

  test("draws, undoes, clears and closes a polygon, then saves and edits it", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));

    await page.goto("/notifications/new?kind=alert");
    await expect(page.getByRole("heading", { name: "Nouvelle alerte" })).toBeVisible();
    await page.getByLabel("Titre (arabe)").fill("تنبيه أمطار غزيرة");
    await page.getByLabel("Texte (arabe)").fill("تجنبوا الأودية");
    await page.getByLabel("Niveau de vigilance").selectOption("high");
    await page.getByLabel("Catégorie").selectOption("weather");
    await page.getByLabel("Phénomène").selectOption("heavy_rain");
    const expires = new Date(Date.now() + 24 * 3600 * 1000);
    const local = new Date(expires.getTime() - expires.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
    await page.getByLabel("Fin de validité").fill(local);

    // The radio is visually hidden under its label (segmented control): click the visible label, as a user does.
    await page.locator(".segmented__item", { hasText: "Zone dessinée" }).click();
    await expect(page.getByRole("radio", { name: "Zone dessinée" })).toBeChecked();
    const { map, at, positionAt: toPosition, tolerance } = await drawingMap(page, TUNISIA);
    const points = page.getByRole("status").filter({ hasText: "Sommets" });
    const finish = page.getByRole("button", { name: "Terminer la zone" });
    const undo = page.getByRole("button", { name: "Annuler le dernier point" });
    const clear = page.getByRole("button", { name: "Effacer la zone" });
    await expect(map).toHaveCSS("cursor", "crosshair");

    // A first attempt: two points, then cleared.
    await clickMap(map, at(-60, -80));
    await clickMap(map, at(60, -80));
    await expect(points).toHaveText(/Sommets : 2/);
    await expect(finish).toBeDisabled();
    await clear.click();
    await expect(points).toHaveText(/Sommets : 0/);
    await expect(undo).toBeDisabled();

    // A square, a stray fifth click, undone.
    // The country is fitted by its height, so a horizontal pixel spans many degrees: keep the clicks inside Tunisia.
    const square: Pixel[] = [at(-40, -60), at(40, -60), at(40, 60), at(-40, 60)];
    for (const pixel of square) await clickMap(map, pixel);
    await clickMap(map, at(0, 0));
    await expect(points).toHaveText(/Sommets : 5/);
    await undo.click();
    await expect(points).toHaveText(/Sommets : 4/);

    await finish.click();
    await expect(points).toHaveText(/Sommets : 4 · zone fermée/);
    await expect(map).not.toHaveCSS("cursor", "crosshair");
    // Clicks on a closed area add nothing.
    await clickMap(map, at(0, 0));
    await expect(points).toHaveText(/Sommets : 4 · zone fermée/);

    await page.getByRole("button", { name: "Enregistrer le brouillon" }).click();
    await expect(page).toHaveURL(/\/notifications\/m-e2e$/);
    expect(api.created).toHaveLength(1);
    const created = api.created[0];
    expect(created).toMatchObject({ kind: "alert", severity: "high", category: "weather", hazard: "heavy_rain" });
    expect(created?.area.gouvernorat_codes).toEqual([]);
    expect(created?.area.polygon?.type).toBe("Polygon");
    const expected = square.map(toPosition);
    expectRing(created?.area.polygon?.coordinates[0], expected, tolerance);
    // Screen order: west → east along the top edge, north → south along the east edge.
    expect(expected[1]?.[0]).toBeGreaterThan(expected[0]?.[0] ?? Infinity);
    expect(expected[2]?.[1]).toBeLessThan(expected[1]?.[1] ?? -Infinity);

    // The saved draft reopens on its closed area; resuming adds a fifth vertex, sent with the version.
    const saved = (created?.area.polygon?.coordinates[0] ?? []).slice(0, -1) as Position[];
    const lons = saved.map(([lon]) => lon);
    const lats = saved.map(([, lat]) => lat);
    const draft = await drawingMap(page, {
      west: Math.min(...lons) - AREA_MARGIN,
      south: Math.min(...lats) - AREA_MARGIN,
      east: Math.max(...lons) + AREA_MARGIN,
      north: Math.max(...lats) + AREA_MARGIN,
    });
    const draftPoints = page.getByRole("status").filter({ hasText: "Sommets" });
    await expect(draftPoints).toHaveText(/Sommets : 4 · zone fermée/);
    await page.getByRole("button", { name: "Reprendre le tracé" }).click();
    // West of the square's west edge, half-way down: inserted after the last vertex, the ring stays simple.
    const [westEdge] = draft.pixelAt(saved[0] ?? [0, 0]);
    const extra: Pixel = [Math.round(westEdge - 40), draft.at(0, 0)[1]];
    await clickMap(draft.map, extra);
    await expect(draftPoints).toHaveText(/Sommets : 5/);
    await page.getByRole("button", { name: "Terminer la zone" }).click();
    await page.getByRole("button", { name: "Enregistrer le brouillon" }).click();
    await expect(page.getByText("Brouillon enregistré.")).toBeVisible();
    expect(api.updated).toHaveLength(1);
    expect(api.updated[0]?.version).toBe(1);
    expectRing(api.updated[0]?.area.polygon?.coordinates[0], [...saved, draft.positionAt(extra)], draft.tolerance);

    expect(errors).toEqual([]);
  });
});
