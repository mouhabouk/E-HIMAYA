/**
 * OS7 in the browser (docs/phase-os7/design-os7.md), crew accountability in danger zones: the board of the teams in a
 * danger zone, the next-check time picker, the pause with its reason and the settings. Screenshots for the phase report
 * land in test-results/phase-os7/.
 */
import { expect, test, type Page } from "@playwright/test";
import { API, baseMock, commonAnswer, json, liaisonAnswer, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-os7";
const ago = (seconds: number) => new Date(Date.now() - seconds * 1000).toISOString();
const ahead = (seconds: number) => new Date(Date.now() + seconds * 1000).toISOString();
const P = "/api/v1/staff/par";

const member = (key: string, name: string, role = "", away: string | null = null) => ({
  key,
  name,
  role,
  away_why: away,
  away_at: away ? ago(240) : null,
});

const team = (id: string, label: string, task: string, zone: "hot" | "warm", extra: object = {}) => ({
  id,
  assignment_id: `a-${id}`,
  incident_id: "i-1",
  label,
  task,
  zone,
  status: "ok",
  interval_s: zone === "hot" ? 600 : 900,
  due_at: ahead(405),
  remaining_s: 405,
  last_confirmed_at: ago(195),
  next_at: null,
  paused_at: null,
  pause_reason: null,
  out_at: null,
  out_count: null,
  entered_at: ago(900),
  leader_name: "الرقيب سامي بن علي",
  members: [
    member("m0", "الرقيب سامي بن علي", "رئيس الفريق"),
    member("m1", "العريف أنيس الحمدي", "خرطوم أول"),
    member("m2", "العون مروان الجلاصي", "خرطوم ثان", "air"),
    member("m3", "العون ياسين الكافي", "جهاز تنفّس · بحث"),
  ],
  present: 3,
  away: 1,
  ...extra,
});

const SETTINGS = {
  gouvernorat_code: 61,
  hot_s: 600,
  warm_s: 900,
  grace_s: 60,
  auto_events: ["collapse", "defensive", "evacuation"],
  remind_s: 60,
  updated_at: ago(86_400),
  updated_by_name: "قائد العمليات هشام الدريدي",
};

function board(paused: boolean) {
  const teams = [
    team("t1", "FPT 12 · الفريق 1", "إطفاء الطابق 3 · هجوم داخلي", "hot", {
      next_at: ahead(420),
      ...(paused ? { status: "paused", paused_at: ago(30), pause_reason: "تحوّل إلى الدفاع خارج المبنى" } : {}),
    }),
    team("t2", "VSR 4 · الفريق 2", "بحث وإنقاذ في الطابقين 4 و5", "hot", {
      status: paused ? "paused" : "alarm",
      remaining_s: -95,
      last_confirmed_at: ago(695),
      ...(paused ? { paused_at: ago(30), pause_reason: "تحوّل إلى الدفاع خارج المبنى" } : {}),
    }),
    team("t3", "CCF 7 · الفريق 3", "خط تزوّد من الحنفية H-14", "warm", { remaining_s: 48, status: paused ? "paused" : "soon" }),
  ];
  return {
    incident_id: "i-1",
    incident_kind: "fire",
    incident_status: "open",
    gouvernorat_code: 61,
    settings: SETTINGS,
    kpis: { agents_in: 9, teams_in: 3, not_confirmed: paused ? 0 : 1, missing_open: 1 },
    teams,
    missing: [
      {
        id: "x1",
        team_id: "t1",
        team_label: "FPT 12 · الفريق 1",
        resource: "جهاز لاسلكي",
        carrier: "العريف أنيس الحمدي",
        place: "الطابق الثالث، الرواق الشرقي",
        reported_at: ago(120),
        reported_by_name: "الرقيب سامي بن علي",
        replacement_at: null,
        recovered_at: null,
        recovered_by_name: null,
      },
    ],
    sitreps: [
      {
        id: 1,
        team_id: "t1",
        team_label: "FPT 12 · الفريق 1",
        at: ago(60),
        situation: "progress",
        reinforcement: true,
        text: "الحريق محصور في الطابق الثالث، الدخان كثيف في الرواق. نحتاج خطا ثانيا.",
        voice_seconds: 14,
        edited: true,
        by_name: "الرقيب سامي بن علي",
      },
    ],
    events: [
      ...(paused
        ? [{ at: ago(30), kind: "pause", text: "أُوقف التفقّد · كل الفرق في المنطقة · السبب: تحوّل إلى الدفاع خارج المبنى", by_name: "قائد العمليات هشام الدريدي", team_id: null }]
        : []),
      { at: ago(60), kind: "sitrep", text: "ردّ خبر من FPT 12 · في طريق السيطرة · طلب تعزيز · رسالة صوتية محوّلة إلى نص", by_name: "الرقيب سامي بن علي", team_id: "t1" },
      { at: ago(120), kind: "missing", text: "مورد مفقود · جهاز لاسلكي · كان مع العريف أنيس الحمدي (FPT 12)", by_name: "الرقيب سامي بن علي", team_id: "t1" },
      { at: ago(240), kind: "away", text: "خروج مؤقت · العون مروان الجلاصي (FPT 12) · تزوّد بالهواء", by_name: "الرقيب سامي بن علي", team_id: "t1" },
      { at: ago(900), kind: "enter", text: "FPT 12 دخل المنطقة الساخنة · 4 أعوان · بدأ العدّاد (10 د)", by_name: "الرقيب سامي بن علي", team_id: "t1" },
    ],
    all_out: false,
    closure: null,
    now: new Date().toISOString(),
  };
}

const ROWS = [
  {
    incident_id: "i-1",
    incident_kind: "fire",
    gouvernorat_code: 61,
    teams_in: 3,
    agents_in: 9,
    alarms: 1,
    missing_open: 1,
    last_sitrep: "progress",
    closed: false,
  },
];

async function mockApi(page: Page) {
  const m = await baseMock(page);
  let paused = false;
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
    const verb = request.method();
    const common = commonAnswer(verb, pathname, route);
    if (common) return common;
    const liaison = liaisonAnswer(verb, pathname, route);
    if (liaison) return liaison;
    if (verb === "GET" && pathname === `${P}/settings`) return json(route, SETTINGS);
    if (verb === "GET" && pathname === `${P}/incidents`) return json(route, ROWS);
    if (verb === "GET" && pathname === `${P}/incidents/i-1`) return json(route, board(paused));
    if (verb === "POST" && pathname === `${P}/incidents/i-1/pause`) {
      paused = true;
      return json(route, board(true));
    }
    if (verb === "POST" && pathname === `${P}/incidents/i-1/next`) return json(route, board(paused));
    if (verb === "GET") return json(route, { items: [], next_cursor: null });
    m.unexpected.push(`${verb} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return m;
}

test.describe("OS7: crew accountability in danger zones", () => {
  test.use({ viewport: { width: 1440, height: 2000 } });

  test("the board of the teams in the danger zone", async ({ page }) => {
    await signIn(page, ["field_commander"], "قائد العمليات هشام الدريدي", { scope_level: "regional", gouvernorat_code: 61 });
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.goto("/par");
    await expect(page.getByRole("heading", { level: 1, name: "تفقّد الأعوان في منطقة الخطر" })).toBeVisible();
    await expect(page.getByRole("article", { name: "VSR 4 · الفريق 2" })).toBeVisible();
    await expect(page.getByRole("alert").first()).toContainText("لم يؤكّد الحضور");
    await page.getByRole("navigation").getByRole("button", { name: "العمليات اليومية" }).click();
    await expect(page.getByRole("navigation").getByRole("link", { name: "تفقّد الأعوان" })).toBeVisible();
    await page.getByRole("navigation").getByRole("button", { name: "العمليات اليومية" }).click();
    await page.screenshot({ path: `${SHOTS}/os7-board.png` });
  });

  test("the next-check time picker blocks the past", async ({ page }) => {
    await signIn(page, ["field_commander"], "قائد العمليات هشام الدريدي", { scope_level: "regional", gouvernorat_code: 61 });
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.goto("/par");
    await page.getByRole("button", { name: /اختر الساعة والدقيقة/ }).click();
    const dialog = page.getByRole("dialog", { name: "اختر الساعة والدقيقة" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "+10 د" }).click();
    const card = await dialog.locator("xpath=ancestor::section[1]").boundingBox();
    const box = await dialog.boundingBox();
    if (card && box) {
      const x = Math.min(card.x, box.x) - 8;
      const y = card.y - 8;
      const width = Math.max(card.x + card.width, box.x + box.width) - x + 8;
      const height = Math.max(card.y + card.height, box.y + box.height) - y + 8;
      await page.screenshot({ path: `${SHOTS}/os7-next-picker.png`, clip: { x, y, width, height } });
    }
    await dialog.getByRole("button", { name: "موافق" }).click();
    await expect(page.getByRole("button", { name: "تطبيق التوقيت" })).toBeEnabled();
  });

  test("a pause with its reason", async ({ page }) => {
    await signIn(page, ["field_commander"], "قائد العمليات هشام الدريدي", { scope_level: "regional", gouvernorat_code: 61 });
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.goto("/par");
    const pauseButton = page.getByRole("button", { name: "إيقاف التفقّد" });
    await expect(pauseButton).toBeDisabled();
    await page.getByRole("button", { name: "تحوّل إلى الدفاع خارج المبنى" }).click();
    await pauseButton.click();
    await expect(page.getByRole("button", { name: "استئناف التفقّد" })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os7-paused.png` });
  });

  test("the settings of the gouvernorat", async ({ page }) => {
    await signIn(page, ["field_commander"], "قائد العمليات هشام الدريدي", { scope_level: "regional", gouvernorat_code: 61 });
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.goto("/par");
    await page.getByRole("button", { name: "إعدادات التفقّد" }).click();
    await expect(page.getByText("المدة بين تفقّدين")).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os7-settings.png` });
  });
});
