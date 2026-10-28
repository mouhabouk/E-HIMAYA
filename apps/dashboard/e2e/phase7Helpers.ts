/**
 * Shared set-up of the phase 7 browser tests (weather layer, softphone): a signed-in staff session, the map style,
 * the live feed and a JSON helper. Every request leaving the *.e2e.test hosts is aborted and recorded.
 */
import type { Page, Route, WebSocketRoute } from "@playwright/test";
import { E2E_ENV } from "../playwright.config";
import { BASEMAP } from "../src/test/basemapData";

export const API = E2E_ENV.VITE_API_BASE_URL;

// ┏━━ SIMULATION ━━ signed-in staff session (unsigned JWT, national scope, roles given by the test)
// ┃ PRODUCTION: Keycloak (realm ehimaya-staff) issues a signed token after Authorization Code + PKCE and MFA; the
// ┃ API verifies it. To run against a real stack, remove this and sign in through the Keycloak login page first.
// ┗━━━━━━━━━━━━━━━━
export async function signIn(
  page: Page,
  roles: string[],
  name = "Sami Operator",
): Promise<void> {
  const b64url = (value: object) =>
    Buffer.from(JSON.stringify(value)).toString("base64url");
  const now = Math.floor(Date.now() / 1000);
  const token = `${b64url({ alg: "none", typ: "JWT" })}.${b64url({
    iss: E2E_ENV.VITE_OIDC_ISSUER,
    sub: "e2e-staff",
    name,
    exp: now + 3600,
    iat: now,
    realm_access: { roles },
    scope_level: "national",
  })}.`;
  const key = `oidc.user:${E2E_ENV.VITE_OIDC_ISSUER}:${E2E_ENV.VITE_OIDC_CLIENT_ID}`;
  const user = JSON.stringify({
    access_token: token,
    token_type: "Bearer",
    scope: "openid profile",
    profile: {
      sub: "e2e-staff",
      iss: E2E_ENV.VITE_OIDC_ISSUER,
      aud: E2E_ENV.VITE_OIDC_CLIENT_ID,
      exp: 0,
      iat: 0,
    },
    expires_at: now + 3600,
  });
  await page.addInitScript(
    ([storageKey, value]) => {
      window.sessionStorage.setItem(storageKey, value);
      window.localStorage.setItem("ehimaya.lang", "fr");
    },
    [key, user] as const,
  );
}

export const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });

export interface BaseMock {
  unexpected: string[];
  live: WebSocketRoute | null;
}

/**
 * Map style (one plain background layer), live feed (answers "ready") and the network fence. `extraHosts` lists
 * further mocked hosts (e.g. the SIP WebSocket).
 */
export async function baseMock(page: Page): Promise<BaseMock> {
  const m: BaseMock = { unexpected: [], live: null };
  await page.route(
    (url) =>
      url.hostname !== "localhost" && !url.hostname.endsWith(".e2e.test"),
    (route) => {
      m.unexpected.push(route.request().url());
      return route.abort();
    },
  );
  await page.route(E2E_ENV.VITE_MAP_STYLE_URL, (route) =>
    json(route, {
      version: 8,
      sources: {},
      layers: [
        {
          id: "background",
          type: "background",
          paint: { "background-color": "#e8eef2" },
        },
      ],
    }),
  );
  await page.routeWebSocket(
    `${API.replace("http", "ws")}/api/v1/staff/live`,
    (ws) => {
      m.live = ws;
      ws.onMessage((raw) => {
        const msg = JSON.parse(String(raw)) as { type?: string };
        if (msg.type === "auth") ws.send(JSON.stringify({ type: "ready" }));
      });
    },
  );
  return m;
}

/** Reference answers every screen asks for. */
export function commonAnswer(
  method: string,
  pathname: string,
  route: Route,
): Promise<void> | null {
  // Environment strip (backlog G3): production-like, no strip.
  if (method === "GET" && pathname === "/api/v1/app/environment") return json(route, { banner: null });
  if (method === "GET" && pathname === "/api/v1/geo/gouvernorats") {
    return json(route, [
      {
        code: 11,
        iso_code: "TN-11",
        name: "تونس",
        name_ar: "تونس",
        name_fr: "Tunis",
        delegation_count: 21,
      },
      {
        code: 61,
        iso_code: "TN-61",
        name: "صفاقس",
        name_ar: "صفاقس",
        name_fr: "Sfax",
        delegation_count: 16,
      },
    ]);
  }
  if (method === "GET" && pathname === "/api/v1/staff/levels")
    return json(route, []);
  if (method === "GET" && pathname === "/api/v1/staff/streams")
    return json(route, { items: [], next_cursor: null });
  // What the system administrator grants and hides (phase L4 §8): nothing here.
  if (method === "GET" && pathname === "/api/v1/staff/features/mine")
    return json(route, { granted: [], hidden: [], lent: {} });
  // The decision window (phase L4b): the menu asks whether a delegation opens it; none here.
  if (method === "GET" && pathname === "/api/v1/staff/window/access")
    return json(route, { full: false, delegated: false, may_delegate: false, keeps_dictionary: false, delegations: [] });
  // Active break-glass grants of the signed-in user (banner in the layout, phase 9).
  // National settings (priority bands, phase 9); an empty list keeps the built-in defaults.
  if (method === "GET" && pathname === "/api/v1/staff/settings")
    return json(route, { items: [] });
  // Map data layers (phase B1): none, so the map shows only its built-in layers.
  if (method === "GET" && pathname === "/api/v1/staff/layers") {
    return json(route, {
      items: [],
      can_manage: false,
      icons: [],
      palette: [],
      limits: { file_bytes: 10485760, rows: 50000 },
    });
  }
  // Map data layers (phase B1): none, so the map shows only its built-in layers.
  if (method === "GET" && pathname === "/api/v1/staff/layers") {
    return json(route, { items: [], can_manage: false, icons: [], palette: [], limits: { file_bytes: 10485760, rows: 50000 } });
  }
  // Map background (phase R): the open satellite source, read by the background switch of the map.
  if (method === "GET" && pathname === "/api/v1/staff/basemap") return json(route, BASEMAP);
  if (method === "GET" && pathname === "/api/v1/staff/break-glass")
    return json(route, { items: [], next_cursor: null });
  return null;
}
