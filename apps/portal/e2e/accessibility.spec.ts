/**
 * Accessibility of the portal (phase 10 §6.5, U21): axe-core with the WCAG 2.2 A/AA rules on the production bundle,
 * in Arabic and in French, for the public pages (landing, certificate check) and the institution pages. A violation
 * of impact "serious" or "critical" fails the test; the others are printed so they can be planned.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";
import { E2E_ENV } from "../playwright.config";
import { GOUVERNORATS, MY_ORGS, makeCertificate, makeOrg, makePublicCertificate } from "../src/test/fixtures";

const API = E2E_ENV.VITE_API_BASE_URL;
const CODE = "EHC-26-61-000123";

const PUBLIC_SCREENS = ["/", "/verify", `/verify/${CODE}`, "/verify/EHC-26-61-000999"];
const SIGNED_IN_SCREENS = [
  "/orgs/mine",
  "/orgs/new",
  "/orgs/o-1",
  "/orgs/o-1/card",
  "/orgs/o-1/team",
  "/orgs/o-1/documents",
  "/orgs/o-1/members",
  "/orgs/o-1/certificate",
  "/orgs/o-1/prevention",
];

/** An approved certificate that needs updating, with a hand stamp (phase P3a). */
const P3A_CERTIFICATE = makeCertificate({
  status: "approved",
  reviewed_at: "2026-10-03T08:00:00Z",
  valid_until: "2099-10-03",
  needs_update: true,
  changes: [{ section: "building", field: "capacity", certified: 300, current: 420 }],
  stamps: [
    {
      id: "s-1",
      place: "Sfax",
      gouvernorat_code: 61,
      stamped_on: "2026-10-20",
      note: null,
      stamped_by_name: "Leila",
      recorded_at: "2026-10-20T09:00:00Z",
      has_photo: false,
      changes: [],
    },
  ],
});

/** A prevention visit decided with one reservation, and the year's report (phase P3b). */
const P3B_VISIT = {
  id: "v-1",
  org_id: "o-1",
  origin: "request",
  status: "decided",
  request_note: null,
  requested_by_name: "Amira Ben Salah",
  requested_at: "2026-10-01T08:00:00Z",
  scheduled_on: "2026-10-20",
  inspector_name: "Cdt Ben Salah",
  inspected_on: "2026-10-20",
  attendees: null,
  comparison: {
    items: [
      { key: "building.capacity", section: "building", declared: 300, result: "nonconform", observed: "420", note: null },
      { key: "site.exits", section: "site", declared: null, result: "conform", observed: null, note: null },
    ],
    conform: 1,
    nonconform: 1,
    not_checked: 0,
    missing: [],
    changes: [],
    suggested: "approved_with_reservations",
  },
  decision: "approved_with_reservations",
  decision_reason: null,
  decided_by_name: "Cdt Ben Salah",
  decided_at: "2026-10-22T10:00:00Z",
  certificate: makeCertificate({ id: "c-9", kind: "prevention", code: "EHP-26-61-000009", status: "approved", valid_until: "2099-10-22" }),
  reservations: [
    {
      id: "r-1",
      visit_id: "v-1",
      item_key: "building.capacity",
      text: "Mettre à jour la capacité déclarée",
      due_on: "2099-11-22",
      state: "open",
      response_note: null,
      responded_by_name: null,
      responded_at: null,
      lifted_by_name: null,
      lift_note: null,
      lifted_at: null,
    },
  ],
  has_report: true,
  cancel_reason: null,
  cancelled_at: null,
  created_at: "2026-10-01T08:00:00Z",
};
const P3B_ANNUAL = {
  year: new Date().getFullYear(),
  org_id: "o-1",
  org_name: "Société X",
  generated_on: "2026-10-25",
  drills: [],
  events: [],
  participants: 0,
  maintenance: 3,
  training: { valid: 2, expiring: 0, expired: 1, unknown: 0 },
  visits: [P3B_VISIT],
  reservations: { opened: 1, lifted: 0, open: 1, overdue: 0 },
  certificates: [P3B_VISIT.certificate],
  stamps: 0,
  reports: 2,
};

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

// ┏━━ SIMULATION ━━ signed-in institution user (unsigned JWT stored where oidc-client-ts keeps the session)
// ┃ PRODUCTION: Keycloak (realm ehimaya-public) issues a signed token after Authorization Code + PKCE; the API
// ┃ verifies it. To run against a real stack, remove this and sign in through the Keycloak login page first.
// ┗━━━━━━━━━━━━━━━━
async function signIn(page: Page): Promise<void> {
  const b64url = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  const now = Math.floor(Date.now() / 1000);
  const claims = { iss: E2E_ENV.VITE_OIDC_ISSUER, sub: "kc-1", name: "Amira Ben Salah", email: "amira@x.tn" };
  const token = `${b64url({ alg: "none", typ: "JWT" })}.${b64url({ ...claims, exp: now + 3600, iat: now })}.`;
  const key = `oidc.user:${E2E_ENV.VITE_OIDC_ISSUER}:${E2E_ENV.VITE_OIDC_CLIENT_ID}`;
  const user = JSON.stringify({
    access_token: token,
    token_type: "Bearer",
    scope: "openid profile email",
    profile: { ...claims, aud: E2E_ENV.VITE_OIDC_CLIENT_ID, exp: 0, iat: 0 },
    expires_at: now + 3600,
  });
  await page.addInitScript(([storageKey, value]) => window.sessionStorage.setItem(storageKey, value), [key, user] as const);
}

/** Every request leaving localhost and the *.e2e.test hosts is aborted and recorded. */
async function mock(page: Page): Promise<string[]> {
  const unexpected: string[] = [];
  await page.route(
    (url) => url.hostname !== "localhost" && !url.hostname.endsWith(".e2e.test"),
    (route) => {
      unexpected.push(route.request().url());
      return route.abort();
    },
  );
  await page.route(E2E_ENV.VITE_MAP_STYLE_URL, (route) =>
    json(route, {
      version: 8,
      sources: {},
      layers: [{ id: "background", type: "background", paint: { "background-color": "#e8eef2" } }],
    }),
  );
  await page.route(`${API}/**`, (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    if (request.method() !== "GET") return json(route, {}, 204);
    if (pathname === "/api/v1/geo/gouvernorats") return json(route, GOUVERNORATS);
    if (pathname === "/api/v1/charter") return json(route, { version: "1" });
    if (pathname === "/api/v1/orgs/mine") return json(route, MY_ORGS);
    if (pathname === "/api/v1/orgs/o-1") return json(route, makeOrg());
    if (pathname === `/api/v1/public/certificates/${CODE}`) {
      // Phase P3a: the electronic seal [SIM] and a hand stamp are part of the checked page.
      return json(route, makePublicCertificate({ key_id: "k-2026", stamps: [{ place: "Sfax", stamped_on: "2026-10-20" }] }));
    }
    if (pathname === "/api/v1/orgs/o-1/certificates") return json(route, [P3A_CERTIFICATE]);
    if (pathname.startsWith("/api/v1/public/certificates/")) {
      return json(route, makePublicCertificate({ code: "EHC-26-61-000999", status: "revoked", valid: false }));
    }
    if (pathname === "/api/v1/public/certificate-key") {
      return json(route, { algorithm: "Ed25519", public_key: "MCowBQYDK2VwAyEA" + "A".repeat(43) + "=", signed_message: "code|fingerprint|pdf_sha256" });
    }
    if (pathname === "/api/v1/orgs/o-1/prevention/visits") return json(route, [P3B_VISIT]);
    if (pathname === "/api/v1/orgs/o-1/annual-report") return json(route, P3B_ANNUAL);
    if (pathname.endsWith("/reports")) return json(route, { items: [], next_cursor: null });
    // Registers, documents, members, invitations and certificates of the institution: empty lists.
    return json(route, []);
  });
  return unexpected;
}

async function audit(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await expect(page.locator("main").first()).toBeVisible();
  await expect(page.locator("h1").first()).toBeVisible();
  // Let pending requests settle so the scan sees the finished screen.
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    // The map canvas is drawn by MapLibre (WebGL); its own controls are checked, not the pixels.
    .exclude(".maplibregl-canvas")
    .analyze();
  console.log(`[axe-run] ${path}: ${results.passes.length} rules passed, ${results.violations.length} violated`);
  const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  for (const v of results.violations) {
    const targets = v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ");
    console.log(`[axe ${v.impact ?? "?"}] ${path}: ${v.id} (${v.nodes.length}) ${targets}`);
  }
  expect(
    blocking.map((v) => `${v.id}: ${v.help} → ${v.nodes.map((n) => n.target.join(" ")).slice(0, 5).join(", ")}`),
  ).toEqual([]);
}

for (const lang of ["ar", "fr"] as const) {
  test.describe(`accessibility (${lang})`, () => {
    for (const path of [...PUBLIC_SCREENS, ...SIGNED_IN_SCREENS]) {
      test(`${path} has no serious or critical violation`, async ({ page }) => {
        if (SIGNED_IN_SCREENS.includes(path)) await signIn(page);
        await page.addInitScript((l) => window.localStorage.setItem("ehimaya.portal.lang", l), lang);
        const unexpected = await mock(page);
        await audit(page, path);
        expect(unexpected).toEqual([]);
      });
    }
  });
}
