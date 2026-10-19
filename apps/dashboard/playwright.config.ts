import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;

// ┏━━ SIMULATION ━━ API, identity provider and map style hosts used by the end-to-end build
// ┃ PRODUCTION: the dashboard is built with the real VITE_API_BASE_URL, VITE_OIDC_ISSUER and VITE_MAP_STYLE_URL
// ┃ (see README). These *.e2e.test hosts do not exist: every request to them is answered by page.route in e2e/,
// ┃ so the tests need no API, Keycloak or tile server. To run against a real stack, build with the real values,
// ┃ sign in through Keycloak and drop the mocks.
// ┗━━━━━━━━━━━━━━━━
export const E2E_ENV = {
  VITE_API_BASE_URL: "http://api.e2e.test",
  VITE_OIDC_ISSUER: "http://idp.e2e.test/realms/ehimaya-staff",
  VITE_OIDC_CLIENT_ID: "ehimaya-dashboard",
  VITE_MAP_STYLE_URL: "http://tiles.e2e.test/style.json",
};

/**
 * Browser tests of what jsdom cannot run (MapLibre needs WebGL2): the production bundle is built into dist-e2e and
 * served by `vite preview`. Locally the preinstalled Chromium is used (PLAYWRIGHT_BROWSERS_PATH); CI installs it with
 * `npx playwright install --with-deps chromium`.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 60_000,
  use: {
    baseURL: `http://localhost:${PORT}`,
    locale: "fr-FR",
    viewport: { width: 1280, height: 900 },
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 900 },
        // Software WebGL2 in headless Chromium (CI runners have no GPU).
        launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] },
      },
    },
  ],
  webServer: {
    command: `vite build --outDir dist-e2e --emptyOutDir && vite preview --outDir dist-e2e --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    env: E2E_ENV,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
