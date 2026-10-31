/**
 * Phase S2 in the browser (docs/phase-s/design-s2.md): the record of a mission in the operations room, its times in
 * order with the source of each one, and the times read from a note and a pasted radio log, applied on a click.
 * Screenshots for the phase report land in test-results/phase-s2/.
 */
import { expect, test, type Page } from "@playwright/test";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-s2";
const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000);
const clock = (at: Date) => `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
const minute = (at: Date) => new Date(Math.floor(at.getTime() / 60_000) * 60_000);

const hospital = minute(ago(6));
const free = minute(ago(2));

const ASSIGNMENT = {
  id: "a-1",
  incident_id: "i-1",
  kind: "resource",
  resource: { id: "res-1", label: "FPT-12", kind: "fire_engine", unit_name: "وحدة نابل" },
  volunteer: null,
  order: "حادث مرور على الطريق الحزامية",
  status: "on_scene",
  created_by: "Sami Operator",
  created_at: ago(52).toISOString(),
  en_route_at: ago(50).toISOString(),
  on_scene_at: ago(41).toISOString(),
  left_scene_at: ago(14).toISOString(),
  at_hospital_at: null,
  available_at: null,
  back_at_unit_at: null,
  released_at: null,
  cancelled_at: null,
  crew_count: 5,
  consumables: { water_m3: 2, absorbent_kg: 10 },
  time_sources: { en_route_at: "app", on_scene_at: "app", left_scene_at: "sms" },
  record_warnings: [],
};

const SUGGESTIONS = [
  {
    step: "at_hospital_at",
    at: hospital.toISOString(),
    source: "room_note",
    words: `اللاسلكي: FPT-12 وصلوا للسبيطار ${clock(hospital)}`,
    written_at: ago(5).toISOString(),
    conflict: null,
  },
  {
    step: "available_at",
    at: free.toISOString(),
    source: "pasted",
    words: `FPT-12 متاحين في طريق العودة ${clock(free)}`,
    written_at: new Date().toISOString(),
    conflict: null,
  },
];

async function mockApi(page: Page) {
  const m = await baseMock(page);
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const verb = request.method();
    const common = commonAnswer(verb, pathname, route);
    if (common) return common;
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1") {
      return json(route, {
        id: "i-1",
        category: "traffic_accident",
        status: "open",
        gouvernorat_code: 21,
        centroid: { lat: 36.45, lon: 10.73 },
        severity: 60,
        report_count: 1,
        reporter_count: 1,
        opened_at: ago(55).toISOString(),
        updated_at: ago(5).toISOString(),
        closed_at: null,
        merged_into: null,
        reports: [],
        timeline: [
          {
            id: 1,
            at: ago(5).toISOString(),
            actor: "Sami Operator",
            kind: "note",
            payload: { text: SUGGESTIONS[0]?.words },
          },
        ],
        assignments: [ASSIGNMENT],
        callouts: [],
      });
    }
    if (verb === "POST" && pathname === "/api/v1/staff/assignments/a-1/record/suggestions") return json(route, SUGGESTIONS);
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1/recommendations") {
      return json(route, { generated_at: new Date().toISOString(), items: [] });
    }
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1/command") {
      return json(route, { incident_id: "i-1", generated_at: new Date().toISOString(), proposals: [], decided: [], simulated: false });
    }
    // The incident's media gallery (phase D, review point 21): empty.
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1/media") return json(route, { counts: {}, live_streams: 0, items: [] });
    if (verb === "GET" && pathname.startsWith("/api/v1/staff/incidents/i-1/")) return json(route, []);
    if (verb === "GET" && pathname === "/api/v1/staff/resources") return json(route, { items: [], next_cursor: null });
    if (verb === "GET" && pathname === "/api/v1/staff/incidents") return json(route, { items: [], next_cursor: null });
    m.unexpected.push(`${verb} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return m;
}

test.describe("phase S2: the record of a mission", () => {
  test("the room's record, and the times read from the notes and the radio log", async ({ page }) => {
    await signIn(page, ["operator"], "Sami Operator", { scope_level: "regional", gouvernorat_code: 21 });
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.goto("/incidents/i-1");
    // The bar of the menu stays at the top of the window: kept out of the shots of the editor.
    await page.addStyleTag({ content: "header, aside.softphone { display: none !important; }" });
    await page.getByRole("button", { name: "سجل المهمة" }).first().click();
    const editor = page.getByRole("form", { name: /سجل المهمة/ });
    await expect(editor).toBeVisible();
    await editor.screenshot({ path: `${SHOTS}/s2-record-editor.png` });

    await editor.getByText("اقتراح التواقيت من الملاحظات وسجل اللاسلكي").click();
    await editor.getByLabel("سجل اللاسلكي أو أي نص (اختياري)").fill(SUGGESTIONS[1]?.words ?? "");
    await editor.getByRole("button", { name: "اقرأ التواقيت" }).click();
    await expect(editor.getByRole("button", { name: "اعتمد" })).toHaveCount(2);
    await editor.locator(".record-suggest").screenshot({ path: `${SHOTS}/s2-suggestions.png` });

    await editor.getByRole("button", { name: "اعتمد" }).first().click();
    await editor.getByRole("button", { name: "اعتمد" }).first().click();
    await expect(editor.getByRole("textbox", { name: "الوصول للمستشفى" })).toHaveValue(`${clock(hospital)}:00`);
    await expect(editor.getByRole("textbox", { name: "متاحون في طريق العودة" })).toHaveValue(`${clock(free)}:00`);
    await editor.screenshot({ path: `${SHOTS}/s2-record-applied.png` });
  });
});
