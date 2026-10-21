/**
 * Phase 8 screens in Chromium (docs/api/phase-8-contract.md §4): the uPlot charts draw on a real canvas with their
 * data tables, the hotspot hexagons go through MapLibre's real style validation (a bad paint expression is a console
 * error), Markdown from the national memory never executes script, the events library search and calendar work,
 * and the rewards screens show no cash configuration. Arabic is checked for direction.
 */
import { expect, test, type Page } from "@playwright/test";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const ring = (lon: number, lat: number, r = 0.05): [number, number][] => {
  const pts: [number, number][] = [];
  for (let i = 0; i < 6; i += 1) pts.push([lon + r * Math.cos((Math.PI / 3) * i), lat + r * Math.sin((Math.PI / 3) * i)]);
  pts.push(pts[0] as [number, number]);
  return pts;
};

const OVERVIEW = {
  from: "2026-07-23",
  to: "2026-10-20",
  gouvernorats: [],
  category: null,
  totals: { received: 1240, verified: 980, in_progress: 42, closed: 900, rejected: 61 },
  response_time: {
    to_assignment: { mean_s: 312, p90_s: 840, n: 950 },
    to_on_scene: { mean_s: 1260, p90_s: 2400, n: 870 },
    to_closed: { mean_s: 7200, p90_s: 20000, n: 860 },
  },
  by_category: [{ key: "fire", count: 610 }],
  by_gouvernorat: [{ key: 61, count: 700 }],
  by_status: [{ key: "closed", count: 900 }],
  by_source: [{ key: "app", count: 800 }],
  by_hour: [{ key: 14, count: 120 }],
  by_weekday: [{ key: 1, count: 200 }],
  min_cell: 5,
};

const TRENDS = {
  metric: "reports",
  interval: "week",
  baseline_available: true,
  unit: "count",
  points: Array.from({ length: 12 }, (_, i) => {
    const d = new Date(Date.UTC(2026, 7, 3 + i * 7));
    return {
      period_start: d.toISOString().slice(0, 10),
      value: 70 + ((i * 17) % 40),
      last_year: 65 + ((i * 11) % 30),
      expected: 75,
      low: 60,
      high: 92,
    };
  }),
};

const HOTSPOTS = {
  type: "FeatureCollection",
  cell_size_m: 5000,
  features: [
    { type: "Feature", properties: { id: "1:1", count: 42 }, geometry: { type: "Polygon", coordinates: [ring(10.76, 34.74)] } },
    { type: "Feature", properties: { id: "2:1", count: 7 }, geometry: { type: "Polygon", coordinates: [ring(10.18, 36.8)] } },
    { type: "Feature", properties: { id: "3:1", count: 1 }, geometry: { type: "Polygon", coordinates: [ring(9.5, 35.5)] } },
  ],
};

const MEMORY = {
  id: "mem-1",
  title: { ar: "حرائق غابات الكاف 2026", fr: "Feux de forêt du Kef 2026" },
  event_type: "fire",
  started_at: "2026-08-02T10:00:00Z",
  ended_at: null,
  gouvernorats: [61],
  geometry: null,
  incident_ids: [],
  summary: {
    ar: "ملخص **الحدث**",
    fr: 'Résumé **gras**\n\n<script>window.__xss = 1</script>\n\n<img src=x onerror="window.__xss = 2">\n\n[clic](javascript:window.__xss=3)',
  },
  strengths: { ar: "", fr: "- Mobilisation rapide" },
  weaknesses: { ar: "", fr: "" },
  lessons: { ar: "", fr: "" },
  recommendations: { ar: "", fr: "" },
  sources: [],
  access: "national",
  status: "draft",
  version: 1,
  published_version: null,
  author: { id: "x", name: "Amel" },
  reviewers: [],
  can_edit: true,
  can_review: false,
};

async function mockApi(page: Page) {
  const base = await baseMock(page);
  const calls: string[] = [];
  // ┏━━ SIMULATION ━━ e-Himaya API answered in the browser (contract phase 8 §1–§3)
  // ┃ PRODUCTION: services/api (modules analytics, knowledge, rewards) serves these; its own tests cover them.
  // ┗━━━━━━━━━━━━━━━━
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname, search } = new URL(request.url());
    const method = request.method();
    calls.push(`${method} ${pathname}${search}`);
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    if (pathname === "/api/v1/staff/analytics/overview") return json(route, OVERVIEW);
    if (pathname === "/api/v1/staff/analytics/trends") return json(route, TRENDS);
    if (pathname === "/api/v1/staff/analytics/hotspots") return json(route, HOTSPOTS);
    if (pathname === "/api/v1/staff/analytics/notifications") return json(route, { items: [], next_cursor: null, unread: 0 });
    if (pathname === "/api/v1/staff/reports-library") return json(route, { items: [], next_cursor: null });
    if (pathname === "/api/v1/staff/memory/mem-1") return json(route, MEMORY);
    if (pathname === "/api/v1/staff/memory/mem-1/versions") return json(route, { items: [] });
    if (pathname === "/api/v1/staff/library/search")
      return json(route, {
        items: [
          {
            kind: "memory",
            id: "mem-1",
            title: "Feux de forêt du Kef 2026",
            excerpt: "Les <mark>feux</mark> &lt;img src=x onerror=alert(1)&gt; du Kef",
            date: "2026-08-02",
            gouvernorat: 61,
            category: "fire",
            incident_id: null,
            score: 1,
          },
        ],
        facets: { kind: [{ key: "memory", count: 1 }], year: [{ key: "2026", count: 1 }], gouvernorat: [], category: [] },
        backend: "opensearch",
        next_cursor: null,
      });
    if (pathname === "/api/v1/staff/library/calendar")
      return json(route, { year: 2026, month: 8, days: [{ date: "2026-08-02", count: 3 }] });
    if (pathname === "/api/v1/staff/rewards/settings")
      return json(route, { daily_cap: 200, thresholds: { bronze: 100, silver: 500, gold: 2000, ambassador: 10000 }, paused_gouvernorats: [] });
    if (pathname === "/api/v1/staff/rewards/rules")
      return json(route, [
        { id: "r-1", reason: "report_verified", category: null, points: 50, multiplier: null, enabled: true, is_default: true },
        { id: "r-2", reason: "accurate_category", category: null, points: null, multiplier: 1.5, enabled: true, is_default: true },
      ]);
    base.unexpected.push(`${method} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return { ...base, calls };
}

function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  return errors;
}

test.describe("phase 8 screens", () => {
  test("analytics: canvas charts with data tables, hexagon layer, filters in the URL", async ({ page }) => {
    const errors = collectErrors(page);
    await signIn(page, ["ops_manager"]);
    const api = await mockApi(page);
    await page.goto("/analytics?category=fire");
    await expect(page.getByRole("heading", { name: "Analyses", level: 1 })).toBeVisible();

    const chart = page.locator("figure.time-chart").first();
    // uPlot drew on a real canvas, hidden from assistive technology.
    await expect(chart.locator(".time-chart__canvas canvas").first()).toBeVisible();
    await expect(chart.locator(".time-chart__canvas")).toHaveAttribute("aria-hidden", "true");
    // The table alternative is one button away and lists every point, band edges included.
    const toggle = chart.getByRole("button", { name: "Afficher les données (tableau)" });
    await toggle.click();
    await expect(chart.getByRole("button", { name: "Masquer le tableau" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    const table = chart.getByRole("table", { name: "Données : Évolution : Signalements" });
    await expect(table.getByRole("row")).toHaveCount(13);
    await expect(table.getByRole("columnheader", { name: "Bas de la plage habituelle" })).toBeVisible();

    // Hexagons on the real MapLibre map, with their legend and table.
    await expect(page.getByRole("region", { name: "Carte des zones de concentration (hexagones)" }).locator("canvas")).toBeVisible();
    await expect(page.getByRole("list", { name: "Légende des hexagones" }).getByRole("listitem")).not.toHaveCount(0);
    await page.getByRole("combobox", { name: "Taille des cellules" }).selectOption("10");
    await expect.poll(() => api.calls.some((c) => c.includes("/hotspots") && c.includes("size_km=10"))).toBe(true);

    // Filters live in the URL. They are controlled by the search params, which react-router 8 updates in a
    // transition: click, then wait for the new state (check() reads the state right after the click).
    await page.getByRole("radio", { name: "Mois" }).click();
    await expect(page.getByRole("radio", { name: "Mois" })).toBeChecked();
    await expect(page).toHaveURL(/interval=month/);
    await expect(page).toHaveURL(/category=fire/);
    await expect.poll(() => api.calls.some((c) => c.includes("/trends") && c.includes("interval=month"))).toBe(true);

    await page.getByRole("button", { name: "Exporter (rapport)" }).click();
    await expect(page).toHaveURL(/\/reports-library\?new=1&kind=period_summary/);
    await expect(page.getByRole("form", { name: "Générer un rapport" })).toBeVisible();

    expect(api.unexpected).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("analytics in Arabic: right-to-left page, left-to-right plot", async ({ page }) => {
    const errors = collectErrors(page);
    await signIn(page, ["ops_manager"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.goto("/analytics");
    await expect(page.getByRole("heading", { name: "التحليلات", level: 1 })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.locator(".time-chart__canvas").first()).toHaveAttribute("dir", "ltr");
    expect(errors).toEqual([]);
  });

  test("national memory: Markdown is rendered side by side and never runs script", async ({ page }) => {
    const errors = collectErrors(page);
    await signIn(page, ["content_editor"]);
    const api = await mockApi(page);
    await page.goto("/memory/mem-1");
    const summary = page.getByRole("region", { name: "Résumé" });
    await expect(summary.locator("strong", { hasText: "gras" })).toBeVisible();
    await expect(summary.locator('[lang="ar"]')).toHaveAttribute("dir", "rtl");
    await expect(summary.locator('[lang="fr"]')).toHaveAttribute("dir", "ltr");
    await expect(summary.locator("script, img")).toHaveCount(0);
    await expect(summary.locator("a")).toHaveCount(0);
    await expect(summary).toContainText("<script>window.__xss = 1</script>");
    expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined();

    // The editor's preview goes through the same sanitizer.
    await page.getByRole("button", { name: "Modifier" }).click();
    const group = page.getByRole("group", { name: "Résumé" });
    await group.getByRole("button", { name: "Aperçu" }).click();
    await expect(group.locator(".md-preview strong", { hasText: "gras" })).toBeVisible();
    await expect(group.locator("script, img")).toHaveCount(0);
    expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined();

    expect(api.unexpected).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("events library: search with highlights, facets and calendar", async ({ page }) => {
    const errors = collectErrors(page);
    await signIn(page, ["content_editor"]);
    const api = await mockApi(page);
    await page.goto("/library");
    await page.getByRole("searchbox", { name: "Rechercher" }).fill("feux");
    await expect(page).toHaveURL(/q=feux/);
    const hit = page.getByRole("listitem").filter({ has: page.getByRole("link", { name: "Feux de forêt du Kef 2026" }) });
    await expect(hit.locator("mark")).toHaveText("feux");
    await expect(hit.locator("img")).toHaveCount(0);
    await expect(hit).toContainText("<img src=x onerror=alert(1)>");

    await page.getByRole("checkbox", { name: /Mémoire nationale/ }).click();
    await expect(page.getByRole("checkbox", { name: /Mémoire nationale/ })).toBeChecked();
    await expect(page).toHaveURL(/kinds=memory/);

    await page.getByRole("button", { name: "Calendrier" }).click();
    await page.getByRole("button", { name: "Mois précédent" }).click();
    await expect.poll(() => api.calls.some((c) => c.includes("/library/calendar"))).toBe(true);
    expect(api.unexpected).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("rewards: read-only daily cap, rules, safety notice, no cash settings", async ({ page }) => {
    const errors = collectErrors(page);
    await signIn(page, ["central_committee"]);
    const api = await mockApi(page);
    await page.goto("/rewards");
    await expect(page.getByRole("heading", { name: "Récompenses", level: 1 })).toBeVisible();
    await expect(page.getByText("200 points")).toBeVisible();
    await expect(page.getByText(/Aucune récompense en argent/)).toBeVisible();
    await expect(page.getByRole("note")).toContainText("198");
    await expect(page.getByRole("spinbutton", { name: "Valeur : Catégorie exacte" })).toHaveValue("1.5");
    await expect(page.getByRole("spinbutton", { name: /prix|argent|cash/i })).toHaveCount(0);
    expect(api.unexpected).toEqual([]);
    expect(errors).toEqual([]);
  });
});
