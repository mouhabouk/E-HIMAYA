import { defineConfig, devices } from "@playwright/test";

const PORT = 4174;

// ┏━━ SIMULATION ━━ API and identity provider hosts used by the end-to-end build
// ┃ PRODUCTION: the portal is built with the real VITE_API_BASE_URL and VITE_OIDC_ISSUER (see README). These
// ┃ *.e2e.test hosts do not exist: every request to them is answered by page.route in e2e/, so the tests need no API
// ┃ or Keycloak.
// ┗━━━━━━━━━━━━━━━━
export const E2E_ENV = {
  VITE_API_BASE_URL: "http://api.e2e.test",
  VITE_OIDC_ISSUER: "http://idp.e2e.test/realms/ehimaya-public",
  VITE_OIDC_CLIENT_ID: "ehimaya-portal",
  VITE_TUS_ENDPOINT: "http://api.e2e.test/api/v1/uploads/",
  VITE_MAP_STYLE_URL: "http://tiles.e2e.test/style.json",
};

/** Browser tests of the production bundle (accessibility, phase 10 §6.5), served by `vite preview`. */
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
        launchOptions: {
          args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
          // A preinstalled Chromium of another Playwright release (e.g. a sandbox image): its path, else the bundled one.
          executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
        },
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
