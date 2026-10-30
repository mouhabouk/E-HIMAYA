/**
 * Phase N in the browser (docs/phase-n/design-n.md §3, §5, §8, §9): the disaster view of the national committee on the
 * real map, a report entered by a room, a volunteer's availability calendar and the operational thresholds. Screenshots
 * for the phase report land in test-results/phase-n/.
 */
import { expect, test, type Page } from "@playwright/test";
import { JENDOUBA_AXIS, NABEUL_AXIS, NABEUL_DETAIL, SOUSSE_AXIS } from "../src/test/crisisData";
import { makeVolunteerDetail } from "../src/test/opsFixtures";
import { makeSettings } from "../src/test/phase9Fixtures";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-n";

const THRESHOLDS = [
  ["crisis.disaster_map_max", "crisis", "count", 30, 1, 100],
  ["decision.unit_radius_m", "crisis", "metres", 60000, 1000, 300000],
  ["alerts.max_days", "alerts", "days", 7, 1, 30],
  ["alerts.inbox_days", "alerts", "days", 30, 1, 365],
  ["sensors.suggestion_hours", "rooms", "hours", 6, 1, 72],
  ["doctors.committee_max", "partners", "count", 7, 1, 30],
] as const;

async function mockApi(page: Page) {
  await baseMock(page);
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    // Before the common answers, which know Tunis and Sfax only.
    if (pathname === "/api/v1/geo/gouvernorats") {
      return json(route, [
        { code: 21, iso_code: "TN-21", name: "نابل", name_ar: "نابل", name_fr: "Nabeul", delegation_count: 16 },
        { code: 32, iso_code: "TN-32", name: "جندوبة", name_ar: "جندوبة", name_fr: "Jendouba", delegation_count: 9 },
        { code: 51, iso_code: "TN-51", name: "سوسة", name_ar: "سوسة", name_fr: "Sousse", delegation_count: 16 },
        { code: 61, iso_code: "TN-61", name: "صفاقس", name_ar: "صفاقس", name_fr: "Sfax", delegation_count: 16 },
      ]);
    }
    // Before the common answers, which give an empty list of settings.
    if (pathname === "/api/v1/staff/settings") {
      const base = { version: 3, updated_by_name: "مدير النظام", updated_at: "2026-10-30T08:00:00Z", editable: true };
      return json(route, {
        items: [
          ...makeSettings(true),
          { ...base, key: "operations.thresholds", value: { "alerts.max_days": 5, "doctors.committee_max": 7 } },
        ],
        thresholds: THRESHOLDS.map(([name, group, unit, def, low, high]) => ({ name, group, unit, default: def, low, high })),
      });
    }
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    if (pathname === "/api/v1/staff/crisis/boundaries") return json(route, { type: "FeatureCollection", features: [] });
    if (pathname === "/api/v1/staff/crisis/axes") return json(route, { items: [NABEUL_AXIS, JENDOUBA_AXIS, SOUSSE_AXIS] });
    if (pathname === "/api/v1/staff/crisis/disasters/map") {
      return json(route, {
        figures: NABEUL_AXIS.figures,
        areas: [{ id: NABEUL_AXIS.id, level: NABEUL_AXIS.level, area: NABEUL_AXIS.area }],
        incidents: NABEUL_DETAIL.incidents,
        shelters: NABEUL_DETAIL.shelters,
        evacuations: NABEUL_DETAIL.evacuations,
      });
    }
    if (pathname === "/api/v1/staff/volunteers/v-1") {
      return json(
        route,
        makeVolunteerDetail({
          calendar: {
            role: "volunteer",
            planned_now: "unavailable",
            slots: [
              { id: "s1", kind: "available", weekdays: [6, 7], starts_on: "2026-11-01", ends_on: null, from_time: "08:00:00", to_time: "20:00:00" },
              { id: "s2", kind: "available", weekdays: [], starts_on: "2026-11-01", ends_on: "2027-03-31", from_time: "20:00:00", to_time: "06:00:00" },
              { id: "s3", kind: "unavailable", weekdays: [], starts_on: "2026-10-29", ends_on: "2026-11-02", from_time: "00:00:00", to_time: "23:59:00" },
            ],
          },
        }),
      );
    }
    if (pathname === "/api/v1/staff/app-feedback") {
      return json(route, { days: 90, count: 0, average: null, by_stars: {}, by_build: [], remarks: [] });
    }
    return json(route, method === "GET" ? { items: [], next_cursor: null } : { detail: "not_found" }, method === "GET" ? 200 : 404);
  });
}

test.describe("phase N", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("the national committee reads the disasters on the map", async ({ page }) => {
    await signIn(page, ["central_committee"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/disasters");
    await expect(page.getByRole("heading", { level: 1, name: "الكوارث: الحوصلة والخريطة" })).toBeVisible();
    await expect(page.getByText("اللجنة الوطنية برئاسة السيد وزير الداخلية")).toBeVisible();
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${SHOTS}/n-disasters.png`, fullPage: true });
  });

  test("a room enters a report that came by telephone", async ({ page }) => {
    await signIn(page, ["operator"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/reports/new");
    await expect(page.getByRole("radio", { name: "هاتف" })).toBeChecked();
    await page.getByLabel("النوع").selectOption("flood");
    await page.getByLabel("ما قاله المبلّغ").fill("[SIM] المياه تغمر الطريق قرب وادي سوحيل، عائلة على سطح منزلها");
    await page.getByLabel("خط العرض").fill("36.4561");
    await page.getByLabel("خط الطول").fill("10.7376");
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SHOTS}/n-room-report.png`, fullPage: true });
  });

  test("the room reads a volunteer's calendar", async ({ page }) => {
    await signIn(page, ["ops_manager"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/volunteers/v-1");
    const card = page.locator("section", { has: page.getByRole("heading", { name: "رزنامة التوفر" }) });
    await expect(card.getByText(/غير متوفر الآن/)).toBeVisible();
    await card.screenshot({ path: `${SHOTS}/n-volunteer-calendar.png` });
  });

  test("the administrator tunes the operational thresholds", async ({ page }) => {
    await signIn(page, ["sysadmin"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/settings");
    const card = page.locator("section", { has: page.getByRole("heading", { name: "عتبات الإنذارات" }) });
    await expect(card).toBeVisible();
    await card.screenshot({ path: `${SHOTS}/n-thresholds.png` });
  });
});
