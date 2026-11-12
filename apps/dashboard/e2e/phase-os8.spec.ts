/**
 * OS8 in the browser (docs/phase-os8/design-os8.md): the register of dangerous addresses, the national settings of the
 * categories, and the warnings in an incident's file with the name of a personal mark shown on request. Screenshots
 * for the phase report land in test-results/phase-os8/.
 */
import { expect, test, type Page } from "@playwright/test";
import { API, baseMock, commonAnswer, json, liaisonAnswer, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-os8";
const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

const cat = (
  key: string,
  name: string,
  icon: string,
  colour: string,
  radius_m: number,
  critical_with: string[],
  personal = false,
  review_months = 12,
) => ({
  key,
  name,
  icon,
  colour,
  personal,
  radius_m,
  review_months,
  team: true,
  critical_with,
  examples: [],
  updated_by_name: null,
});

const CATEGORIES = [
  cat("gas", "مخزن غاز", "flame", "amber", 150, ["fire", "chemical_leak"]),
  cat("chem", "مواد خطرة", "flask", "amber", 250, ["fire", "chemical_leak"]),
  cat("fuel", "خزان وقود", "drop", "amber", 200, ["fire"]),
  cat("batt", "بطاريات وكهرباء", "bolt", "amber", 100, ["fire", "flood"]),
  cat("coll", "مبنى آيل للسقوط", "crack", "orange", 80, ["fire", "landslide", "flood", "sos"], false, 6),
  cat("acc", "صعوبة الوصول", "road", "navy", 120, ["fire"]),
  cat("dog", "حيوان خطر", "paw", "slate", 80, [], false, 6),
  cat("occ", "أشخاص كثيرون", "people", "purple", 150, ["fire", "chemical_leak"]),
  cat("mob", "يحتاج مساعدة على الإخلاء", "wheel", "green", 60, ["fire", "flood"], true),
  cat("oxy", "جهاز أكسجين منزلي", "o2", "green", 60, ["fire"], true),
  cat("deaf", "لا يسمع الإنذار", "ear", "green", 60, ["fire", "flood"], true),
];

const marker = (id: string, category: string, address: string, description: string, extra: object = {}) => ({
  id,
  category,
  gouvernorat_code: 61,
  location: { lat: 34.74, lon: 10.76 },
  address,
  description,
  source: "room",
  source_ref: null,
  org_id: null,
  incident_id: null,
  team_visible: true,
  hours: null,
  review_on: "2027-06-01",
  review_due: false,
  status: "active",
  created_at: ago(60 * 24 * 40),
  created_by_name: "Sami Operator",
  decided_at: ago(60 * 24 * 40),
  decided_by_name: "Sami Operator",
  decision_reason: null,
  confirmed_at: null,
  ...extra,
});

const MARKERS = {
  items: [
    marker("k1", "gas", "نهج الحبيب بورقيبة 14، صفاقس", "مخزن قوارير غاز في الطابق الأرضي، نحو 60 قارورة"),
    marker("k2", "coll", "نهج المنجي سليم 3، المدينة العتيقة", "سقف الطابق الأول متصدّع، لا تُستعمل الدرج الداخلية", {
      review_on: "2026-10-01",
      review_due: true,
    }),
    marker("k3", "occ", "روضة الياسمين، طريق المطار كلم 2", "روضة أطفال: نحو 40 طفلا", { hours: { start: 450, end: 1080 } }),
    marker("k4", "dog", "حي الحبيب، نهج 12", "كلبا حراسة طليقان في الفناء", { team_visible: true }),
    marker("k5", "chem", "المنطقة الصناعية بودريار، مصنع 7", "مواد تنظيف مركّزة (هيبوكلوريت) في مخزن خلفي", {
      status: "pending",
      source: "org",
      source_ref: "سجل المؤسسات: شركة النقاء",
      decided_at: null,
      decided_by_name: null,
    }),
    marker("k6", "acc", "زنقة 5، حي الرياض", "زقاق ضيق: لا تدخله شاحنة الإطفاء، خرطوم 40 م من النهج الرئيسي", {
      status: "pending",
      source: "team",
      source_ref: "اقتراح من الميدان · فريق صفاقس 2",
      decided_at: null,
      decided_by_name: null,
    }),
  ],
  counts: { active: 4, pending: 2, review_due: 1, personal: 3 },
};

const warning = (id: string, category: string, description: string, distance_m: number, extra: object = {}) => ({
  marker_id: id,
  category,
  category_name: CATEGORIES.find((c) => c.key === category)?.name ?? category,
  personal: false,
  location: { lat: 34.74, lon: 10.76 },
  address: "نهج الحبيب بورقيبة، صفاقس",
  description,
  source: "room",
  source_ref: null,
  team_visible: true,
  distance_m,
  critical: false,
  off_hours: false,
  hours: null,
  review_on: "2027-06-01",
  room_ack_at: null,
  room_ack_by: null,
  team_ack_at: null,
  team_ack_by: null,
  revealed: false,
  ...extra,
});

const WARNINGS = {
  incident_id: "i-1",
  incident_kind: "fire",
  location: { lat: 34.74, lon: 10.76 },
  items: [
    warning("k1", "gas", "مخزن قوارير غاز في الطابق الأرضي، نحو 60 قارورة", 35, { critical: true }),
    warning("p1", "mob", "مسنّة على كرسي متحرك في الطابق الثاني، تحتاج شخصين", 48, {
      personal: true,
      critical: true,
      source: "citizen",
      address: "نهج الحبيب بورقيبة 18، الطابق 2",
    }),
    warning("k4", "dog", "كلبا حراسة طليقان في الفناء", 70, { team_ack_at: ago(2) }),
    warning("k3", "occ", "روضة أطفال: نحو 40 طفلا", 120, {
      off_hours: true,
      hours: { start: 450, end: 1080 },
      room_ack_at: ago(6),
      room_ack_by: "Sami Operator",
    }),
  ],
  unread: 3,
};

async function mockApi(page: Page) {
  const m = await baseMock(page);
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
    const verb = request.method();
    const common = commonAnswer(verb, pathname, route);
    if (common) return common;
    const liaison = liaisonAnswer(verb, pathname, route);
    if (liaison) return liaison;
    const A = "/api/v1/staff/address-warnings";
    if (verb === "GET" && pathname === `${A}/categories`) return json(route, CATEGORIES);
    if (verb === "GET" && pathname === `${A}/markers`) {
      const status = url.searchParams.get("status");
      return json(route, { ...MARKERS, items: status ? MARKERS.items.filter((x) => x.status === status) : MARKERS.items });
    }
    if (verb === "GET" && pathname === `${A}/reveals`) return json(route, []);
    if (verb === "GET" && pathname === `${A}/incidents/i-1`) return json(route, WARNINGS);
    if (verb === "POST" && pathname === `${A}/incidents/i-1/reveal/p1`) {
      return json(route, { name: "فاطمة بن صالح", phone: "+216 98 000 000" });
    }
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1") {
      return json(route, {
        id: "i-1",
        category: "fire",
        status: "open",
        gouvernorat_code: 61,
        centroid: { lat: 34.74, lon: 10.76 },
        severity: 70,
        report_count: 2,
        reporter_count: 2,
        opened_at: ago(12),
        updated_at: ago(2),
        closed_at: null,
        merged_into: null,
        reports: [],
        timeline: [],
        assignments: [],
        callouts: [],
      });
    }
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1/recommendations") {
      return json(route, { generated_at: new Date().toISOString(), items: [] });
    }
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1/command") {
      return json(route, { incident_id: "i-1", generated_at: new Date().toISOString(), proposals: [], decided: [], simulated: false });
    }
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1/media") return json(route, { counts: {}, live_streams: 0, items: [] });
    if (verb === "GET" && pathname.startsWith("/api/v1/staff/incidents/i-1/")) return json(route, []);
    if (verb === "GET") return json(route, { items: [], next_cursor: null });
    m.unexpected.push(`${verb} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return m;
}

test.describe("OS8: address warnings", () => {
  test.use({ viewport: { width: 1440, height: 2100 } });

  test("the room reads the register and the pending marks", async ({ page }) => {
    await signIn(page, ["operator"], "Sami Operator", { scope_level: "regional", gouvernorat_code: 61 });
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.setViewportSize({ width: 1440, height: 1440 });
    await page.goto("/address-warnings");
    await expect(page.getByRole("heading", { level: 1, name: "تحذيرات العناوين" })).toBeVisible();
    await expect(page.getByRole("table").getByText("مخزن قوارير غاز في الطابق الأرضي، نحو 60 قارورة")).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os8-register.png` });
  });

  test("the central room sets the categories", async ({ page }) => {
    await signIn(page, ["ops_manager"], "Leila Manager");
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.goto("/address-warnings");
    await page.getByRole("button", { name: "إعدادات الأصناف" }).click();
    await expect(page.getByText("مبنى آيل للسقوط").first()).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os8-settings.png` });
  });

  test("the warnings of a fire, and the name of a personal mark shown with a reason", async ({ page }) => {
    await signIn(page, ["operator"], "Sami Operator", { scope_level: "regional", gouvernorat_code: 61 });
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.goto("/incidents/i-1");
    await page.addStyleTag({ content: "header, aside.softphone { display: none !important; }" });
    const panel = page.locator(".aw-panel");
    await expect(panel.getByText("مخزن قوارير غاز في الطابق الأرضي، نحو 60 قارورة")).toBeVisible();
    await panel.screenshot({ path: `${SHOTS}/os8-incident.png` });
    await panel.getByRole("button", { name: "الاسم والهاتف" }).click();
    await panel.getByRole("button", { name: "للاتصال والتأكد من وجوده في المنزل" }).click();
    await panel.getByRole("button", { name: "اكشف" }).click();
    await expect(panel.getByText(/فاطمة بن صالح/)).toBeVisible();
    await panel.screenshot({ path: `${SHOTS}/os8-reveal.png` });
  });
});
