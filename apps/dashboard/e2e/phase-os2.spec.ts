/**
 * OS2 in the browser (docs/phase-os2/design-os2.md): the guided call-taking card in the room's intake form, the
 * Office's cards page and the room agent's guide. Screenshots for the phase report land in test-results/phase-os2/.
 */
import { expect, test, type Page } from "@playwright/test";
import { makeSettings } from "../src/test/phase9Fixtures";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-os2";

async function mockApi(page: Page) {
  await baseMock(page);
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    if (pathname === "/api/v1/staff/settings") return json(route, { items: makeSettings(false), thresholds: [] });
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    return json(route, method === "GET" ? { items: [], next_cursor: null } : { detail: "not_found" }, method === "GET" ? 200 : 404);
  });
}

test.describe("OS2: guided call-taking cards", () => {
  test.use({ viewport: { width: 1280, height: 2000 } });
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("the room agent takes a call for an unconscious person with the card", async ({ page }) => {
    await signIn(page, ["operator"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/reports/new");
    await page.locator(".intake-cats__tile", { hasText: "إسعاف" }).click();
    const conscious = page.getByRole("group", { name: /هل المريض فاقد للوعي/ });
    await conscious.getByText("نعم", { exact: true }).click();
    const breathing = page.getByRole("group", { name: /هل يتنفس تنفسا طبيعيا/ });
    await breathing.getByText("لا", { exact: true }).click();
    await expect(page.getByText("المستوى: حرج")).toBeVisible();
    await expect(page.getByText(/110 ضغطة في الدقيقة/)).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os2-room-card.png` });
  });

  test("the Office reads the cards and tries one", async ({ page }) => {
    await signIn(page, ["content_editor"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/call-cards");
    await expect(page.getByRole("heading", { level: 1, name: "بطاقات الاستقبال الموجّهة" })).toBeVisible();
    await page.getByRole("button", { name: /غرق/ }).first().click();
    await page.screenshot({ path: `${SHOTS}/os2-cards.png` });
  });

  test("the room agent reads the guide from the menu", async ({ page }) => {
    await signIn(page, ["operator"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/room-guide");
    await expect(page.getByRole("heading", { level: 1, name: "دليل إجراءات عون القاعة" })).toBeVisible();
    await expect(page.getByText("القيم من الإعدادات الوطنية الحالية.")).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os2-room-guide.png` });
    await page.getByRole("button", { name: "العمليات اليومية" }).click();
    await expect(page.getByRole("link", { name: "دليل إجراءات عون القاعة" })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os2-menu.png` });
  });
});
