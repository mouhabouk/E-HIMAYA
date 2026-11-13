/**
 * OS8 follow-ups in the browser (docs/phase-os8/design-os8.md §8 to §10): the address warnings layer of the interactive
 * map (grouped over a gouvernorat, one by one closer, personal marks only counted), the review reminder tab and its
 * morning toast, and the reveals log with how the owner was told and their objection. Screenshots land in
 * test-results/phase-os8-followups/.
 */
import { expect, test, type Page } from "@playwright/test";
import {
  API,
  baseMock,
  commonAnswer,
  json,
  signIn,
  type BaseMock,
} from "./phase7Helpers";

const SHOTS = "test-results/phase-os8-followups";
const ago = (minutes: number) =>
  new Date(Date.now() - minutes * 60_000).toISOString();
const day = (offset: number) =>
  new Date(Date.now() + offset * 86_400_000).toISOString().slice(0, 10);

const cat = (
  key: string,
  name: string,
  icon: string,
  colour: string,
  radius_m: number,
  review_months = 12,
) => ({
  key,
  name,
  icon,
  colour,
  personal: false,
  radius_m,
  review_months,
  team: true,
  critical_with: ["fire"],
  examples: [],
  updated_by_name: null,
});

const CATEGORIES = [
  cat("gas", "مخزن غاز", "flame", "amber", 150),
  cat("chem", "مواد خطرة", "flask", "amber", 250),
  cat("fuel", "خزان وقود", "drop", "amber", 200),
  cat("coll", "مبنى آيل للسقوط", "crack", "orange", 80, 6),
  cat("acc", "صعوبة الوصول", "road", "navy", 120),
  cat("dog", "حيوان خطر", "paw", "slate", 80, 6),
  cat("occ", "أشخاص كثيرون", "people", "purple", 150),
];

let n = 0;
const marker = (
  category: string,
  lat: number,
  lon: number,
  address: string,
  description: string,
  extra: object = {},
) => ({
  id: `k${++n}`,
  category,
  gouvernorat_code: 61,
  location: { lat, lon },
  address,
  description,
  source: "room",
  source_ref: null,
  org_id: null,
  incident_id: null,
  team_visible: true,
  hours: null,
  review_on: day(200),
  review_due: false,
  status: "active",
  created_at: ago(60 * 24 * 300),
  created_by_name: "Sami Operator",
  decided_at: ago(60 * 24 * 300),
  decided_by_name: "Sami Operator",
  decision_reason: null,
  confirmed_at: null,
  ...extra,
});

// Sfax city (around 34.74, 10.76) and a few délégations of the gouvernorat. [SIM]
const ITEMS = [
  marker(
    "gas",
    34.7406,
    10.7603,
    "نهج الحبيب بورقيبة 14، صفاقس",
    "مخزن قوارير غاز، نحو 60 قارورة",
  ),
  marker(
    "coll",
    34.7372,
    10.7651,
    "نهج المنجي سليم 3، المدينة العتيقة",
    "سقف الطابق الأول متصدّع",
    {
      review_on: day(-59),
      review_due: true,
    },
  ),
  marker(
    "acc",
    34.7352,
    10.7612,
    "زنقة 5، باب الجبلي",
    "زقاق ضيق: لا تدخله شاحنة الإطفاء",
  ),
  marker("dog", 34.7448, 10.7552, "حي الحبيب، نهج 12", "كلبا حراسة طليقان", {
    review_on: day(-7),
    review_due: true,
  }),
  marker(
    "occ",
    34.7465,
    10.7668,
    "روضة الياسمين، طريق المطار",
    "روضة أطفال: نحو 40 طفلا",
  ),
  marker(
    "chem",
    34.7051,
    10.7343,
    "المنطقة الصناعية بودريار، مصنع 7",
    "مواد تنظيف مركّزة",
  ),
  marker("fuel", 34.7712, 10.7215, "طريق تونس كلم 6", "محطة وقود، 3 خزانات"),
  marker(
    "gas",
    35.0381,
    10.8425,
    "المحرس، نهج الميناء",
    "مخزن غاز منزلي للبيع",
  ),
  marker(
    "chem",
    34.4361,
    10.5321,
    "الصخيرة، المنطقة الصناعية",
    "مواد كيميائية بالمجمع",
  ),
  marker(
    "chem",
    34.4402,
    10.5389,
    "الصخيرة، المجمع الكيميائي",
    "أحماض في خزانات",
  ),
  marker("fuel", 34.4311, 10.5289, "الصخيرة، المستودع", "خزانات محروقات"),
  marker("coll", 35.2405, 10.9812, "جبنيانة، المدينة", "منزل قديم آيل للسقوط", {
    review_on: day(-12),
    review_due: true,
  }),
];
const at = (i: number) => ITEMS[i] as (typeof ITEMS)[number];
const MARKERS = {
  items: ITEMS,
  counts: { active: ITEMS.length, pending: 0, review_due: 3, personal: 3 },
};

const reminderItem = (m: (typeof ITEMS)[number], days: number) => ({
  marker: m,
  days,
  level:
    days <= 0
      ? "soon"
      : days >= 30
        ? "central"
        : days >= 7
          ? "manager"
          : "room",
});
const REMINDERS = {
  late: [
    reminderItem(at(1), 59),
    reminderItem(at(11), 12),
    reminderItem(at(3), 7),
  ],
  soon: [reminderItem({ ...at(6), review_on: day(18) }, -18)],
  disputes: 1,
  settings: { hour: 8, ahead_days: 30, manager_days: 7, central_days: 30 },
};
const REVEALS = [
  {
    id: 7,
    at: ago(90),
    by_name: "Sami Operator",
    category: "mob",
    address: "نهج الحبيب بورقيبة 18، الطابق 2",
    incident_id: "i-1",
    reason: "للاتصال والتأكد من وجوده في المنزل",
    notified_via: "push",
    disputed_at: ago(30),
    dispute_note: "لم يتصل بي أحد ولم يقع شيء في بيتي",
  },
  {
    id: 6,
    at: ago(60 * 24 * 3),
    by_name: "Leila Manager",
    category: "deaf",
    address: "نهج القصبة 19",
    incident_id: "i-0",
    reason: "لإبلاغ الفريق باسمه للمناداة",
    notified_via: "sms",
    disputed_at: null,
    dispute_note: null,
  },
];

async function mockApi(page: Page): Promise<BaseMock & { checks: string[] }> {
  const m = await baseMock(page);
  const checks: string[] = [];
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
    const verb = request.method();
    const common = commonAnswer(verb, pathname, route);
    if (common) return common;
    const A = "/api/v1/staff/address-warnings";
    if (verb === "GET" && pathname === `${A}/categories`)
      return json(route, CATEGORIES);
    if (verb === "GET" && pathname === `${A}/markers`)
      return json(route, MARKERS);
    if (verb === "GET" && pathname === `${A}/reminders`)
      return json(route, REMINDERS);
    if (verb === "GET" && pathname === `${A}/reveals`)
      return json(route, REVEALS);
    const check = pathname.match(/\/markers\/([^/]+)\/check$/);
    if (verb === "POST" && check) {
      const id = check[1] ?? "";
      checks.push(id);
      const m0 = ITEMS.find((x) => x.id === id) ?? at(0);
      return json(route, {
        ...m0,
        check_requested_at: new Date().toISOString(),
        check_requested_by_name: "Sami Operator",
      });
    }
    if (verb === "GET")
      return json(route, {
        items: [],
        next_cursor: null,
        type: "FeatureCollection",
        features: [],
      });
    m.unexpected.push(`${verb} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return Object.assign(m, { checks });
}

async function asRoom(page: Page) {
  await signIn(page, ["operator"], "Sami Operator", {
    scope_level: "regional",
    gouvernorat_code: 61,
  });
  await page.addInitScript(() =>
    window.localStorage.setItem("ehimaya.lang", "ar"),
  );
}

test.describe("OS8 follow-ups", () => {
  test.use({ viewport: { width: 1440, height: 1000 } });

  test("OS8-1: the warnings layer of the interactive map, grouped then one by one", async ({
    page,
  }) => {
    await asRoom(page);
    await mockApi(page);
    await page.goto("/map");
    await page.getByRole("checkbox", { name: "تحذيرات العناوين" }).check();
    // Over the whole gouvernorat: groups with their count; personal marks only counted.
    const group = page.locator(".map-poi--aw_cluster").first();
    await expect(group).toBeVisible();
    await expect(
      page.getByText(/3 علامات شخصية لا تظهر على الخريطة/),
    ).toBeVisible();
    await page.evaluate(() =>
      document.querySelector(".aw-layer")?.scrollIntoView({ block: "start" }),
    );
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${SHOTS}/os8-1-map-gouvernorat.png` });
    // Past their review date only.
    await page
      .locator(".aw-layer")
      .getByRole("button", { name: /تجاوزت المراجعة/ })
      .click();
    await expect(page.getByText("علامات ظاهرة: 3")).toBeVisible();
    await page
      .locator(".aw-layer")
      .getByRole("button", { name: "الكل" })
      .click();
    // Closer: Sfax city, one mark by one, a red ring past the review date.
    // Wheel over the biggest group (Sfax city) until the marks come apart.
    for (
      let i = 0;
      i < 6 && (await page.locator(".map-poi--aw_due").count()) < 2;
      i++
    ) {
      // Read every group in one pass in the page: the markers are re-rendered while the map moves.
      const best = await page.evaluate(() => {
        let top: { x: number; y: number; n: number } | null = null;
        for (const el of document.querySelectorAll(".map-poi--aw_cluster")) {
          const n = Number(el.textContent.replace(/\D/g, "") || 0);
          const b = el.getBoundingClientRect();
          if (b.width > 0 && (!top || n > top.n)) top = { x: b.x + b.width / 2, y: b.y + b.height / 2, n };
        }
        return top;
      });
      if (!best) break;
      await page.mouse.move(best.x, best.y);
      for (let k = 0; k < 3; k++) await page.mouse.wheel(0, -300);
      await page.waitForTimeout(800);
    }
    await expect(page.locator(".map-poi--aw_due").first()).toBeVisible();
    await page.evaluate(() =>
      document.querySelector(".aw-layer")?.scrollIntoView({ block: "start" }),
    );
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${SHOTS}/os8-1-map-city.png` });
  });

  test("OS8-3: the review reminder, the morning toast and a field check", async ({
    page,
  }) => {
    await asRoom(page);
    const api = await mockApi(page);
    await page.goto("/address-warnings?tab=reminders");
    await expect(page.getByText("تجاوزت تاريخ المراجعة (3)")).toBeVisible();
    await expect(page.getByText("رُفع إلى القاعة المركزية")).toBeVisible();
    await expect.poll(() => api.live !== null).toBe(true);
    api.live?.send(
      JSON.stringify({
        type: "address_warnings.review_reminder",
        day: day(0),
        gouvernorat_code: 61,
        late: 3,
        soon: 1,
        manager: 2,
        central: 1,
      }),
    );
    await expect(
      page.getByText("تذكير الصباح: تحذيرات العناوين"),
    ).toBeVisible();
    await page.screenshot({
      path: `${SHOTS}/os8-3-reminders.png`,
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "اطلب تحققا من فريق" })
      .first()
      .click();
    await expect.poll(() => api.checks.length).toBe(1);
  });

  test("OS8-2: how the owner was told, and their objection", async ({
    page,
  }) => {
    await asRoom(page);
    await mockApi(page);
    await page.goto("/address-warnings?tab=reveals");
    await expect(page.getByText("أُشعر في التطبيق")).toBeVisible();
    await expect(page.getByText("أُشعر برسالة قصيرة")).toBeVisible();
    await expect(page.getByText(/اعترض صاحبها/)).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os8-2-reveals.png` });
  });
});
