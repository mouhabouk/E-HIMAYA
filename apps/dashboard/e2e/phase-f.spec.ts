/**
 * Phase F in the browser (docs/phase-f/design-f.md): the room chief adds a field agent and hands over the one-time
 * activation code; the list shows each agent's phone, SIM, last position and charter.
 * Screenshots for the phase report land in test-results/phase-f/.
 */
import { expect, test, type Page } from "@playwright/test";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-f";
const ago = (minutes: number) =>
  new Date(Date.now() - minutes * 60_000).toISOString();

const base = {
  gouvernorat_code: 21,
  shift_label: "النوبة أ",
  phone: null,
  code_expires_at: null,
  disabled_at: null,
  disabled_reason: null,
};
const AGENTS = [
  {
    ...base,
    id: "ag-1",
    matricule: "NB1042",
    name: "قائد الفريق 1",
    function: "leader",
    status: "active",
    charter_accepted_at: ago(3000),
    activated_at: ago(3000),
    device: {
      id: "d-1",
      model: "Samsung A15",
      platform: "android",
      device_ref: "a1b2c3",
      sim_number: "+216 98 *** 412",
      imei: null,
      created_at: ago(3000),
      last_seen_at: ago(4),
      revoked_at: null,
    },
    last_position: { lat: 36.45, lon: 10.73, at: ago(4) },
  },
  {
    ...base,
    id: "ag-2",
    matricule: "NB1077",
    name: "سائق 1",
    function: "driver",
    status: "active",
    charter_accepted_at: null,
    activated_at: ago(60),
    device: {
      id: "d-2",
      model: "Redmi 13C",
      platform: "android",
      device_ref: "d4e5f6",
      sim_number: null,
      imei: "35 209900 176148 1",
      created_at: ago(60),
      last_seen_at: ago(50),
      revoked_at: null,
    },
    last_position: null,
  },
  {
    ...base,
    id: "ag-3",
    matricule: "NB0981",
    name: "عون 2",
    function: "agent",
    status: "disabled",
    charter_accepted_at: ago(9000),
    activated_at: ago(9000),
    disabled_at: ago(120),
    disabled_reason: "هاتف ضائع",
    device: null,
    last_position: null,
  },
];

async function mockApi(page: Page) {
  const m = await baseMock(page);
  const agents = [...AGENTS];
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const verb = request.method();
    const common = commonAnswer(verb, pathname, route);
    if (common) return common;
    if (verb === "GET" && pathname === "/api/v1/staff/field-agents")
      return json(route, agents);
    if (verb === "POST" && pathname === "/api/v1/staff/field-agents") {
      const body = request.postDataJSON() as Record<string, unknown>;
      const made = {
        ...base,
        ...body,
        id: "ag-new",
        status: "pending",
        code: "K7QM-4RTX",
        code_expires_at: new Date(Date.now() + 72 * 3600_000).toISOString(),
        charter_accepted_at: null,
        activated_at: null,
        device: null,
        last_position: null,
      };
      agents.unshift(made);
      return json(route, made, 201);
    }
    m.unexpected.push(`${verb} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return m;
}

test.describe("phase F: the field agents", () => {
  test("the room chief adds an agent and hands over the activation code", async ({
    page,
  }) => {
    await signIn(page, ["ops_manager"], "Sami Operator", {
      scope_level: "regional",
      gouvernorat_code: 21,
    });
    await page.addInitScript(() =>
      window.localStorage.setItem("ehimaya.lang", "ar"),
    );
    await mockApi(page);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto("/crew/agents");
    await expect(page.getByText("NB1042")).toBeVisible();
    await page.addStyleTag({
      content: "aside.softphone { display: none !important; }",
    });
    await page.screenshot({ path: `${SHOTS}/f-dash-agents.png` });

    await page.getByLabel("الرقم المهني").fill("NB1103");
    await page.getByLabel("الاسم واللقب").fill("عون 3");
    await page.getByRole("button", { name: "إضافة وتوليد الرمز" }).click();
    await expect(page.getByText("K7QM-4RTX")).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/f-dash-code.png` });
  });
});
