/**
 * OS20 in the browser (docs/phase-os20/design-os20.md): the contact system of a regional and of the central room, the
 * level of a report and the bodies informed by phone, the picker (suggestions, search, several at once, history) and
 * the record of a call. Screenshots for the phase report land in test-results/phase-os20/.
 */
import { expect, test, type Page } from "@playwright/test";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-os20";
const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

const official = (id: string, body: string, name: string, role: string, phone: string, position = 1, duty = "24/24") => ({
  id,
  body_id: body,
  name,
  role,
  phones: [phone],
  email: null,
  duty,
  position,
  status: "active",
  updated_at: ago(3000),
  updated_by_name: "عون القاعة الجهوية",
});

const body = (
  id: string,
  gov: number | null,
  category: string,
  name: string,
  domain: string,
  officials: ReturnType<typeof official>[],
  extra: object = {},
) => ({
  id,
  gouvernorat_code: gov,
  category,
  kind: "external",
  agency: null,
  name,
  domain,
  address: gov ? "صفاقس" : "تونس",
  location: null,
  public_phone: null,
  status: "active",
  created_by_name: "عون",
  updated_at: ago(2880),
  updated_by_name: gov ? "عون القاعة الجهوية بصفاقس" : "القاعة المركزية",
  version: 1,
  editable: false,
  officials,
  ...extra,
});

function bodies(central: boolean) {
  const mine = (gov: number | null) => (central ? gov === null : gov === 61);
  const list = [
    body("central", null, "civil", "القاعة المركزية للعمليات", "قيادة العمليات على المستوى الوطني", [
      official("o-c1", "central", "رئيس القاعة المركزية", "رئيس القاعة", "71 000 100"),
    ], { kind: "internal", agency: "central_room" }),
    body("dg", null, "civil", "المدير العام للديوان الوطني للحماية المدنية", "الإدارة العامة", [
      official("o-dg", "dg", "المدير العام", "المدير العام", "71 000 101", 1, "عند الأزمة"),
    ], { kind: "internal", agency: "director_general" }),
    body("min-eq", null, "ministry", "وزارة التجهيز والإسكان", "الطرقات والجسور", [
      official("o-eq", "min-eq", "خلية الأزمة", "منسق الخلية", "71 000 300", 1, "8:00-17:00"),
    ]),
    body("police", 61, "security", "إقليم الأمن الوطني بصفاقس", "الأمن العام والمرور", [
      official("o-p1", "police", "ر. ع.", "رئيس قاعة العمليات", "74 000 197"),
      official("o-p2", "police", "م. س.", "نائب رئيس الإقليم", "74 000 198", 2),
    ], { agency: "police", public_phone: "197" }),
    body("garde", 61, "security", "إقليم الحرس الوطني بصفاقس", "الحرس والطرقات خارج المدن", [
      official("o-g1", "garde", "ف. ب.", "ضابط الاستمرار", "74 000 193"),
    ], { agency: "garde_nationale", public_phone: "193" }),
    body("samu", 61, "security", "الإسعاف الطبي الاستعجالي بصفاقس", "الإسعاف", [
      official("o-s1", "samu", "طبيب الاستمرار", "طبيب منظم", "74 000 190"),
    ], { agency: "samu", public_phone: "190" }),
    body("gov", 61, "regional", "ولاية صفاقس", "الإدارة الجهوية", [
      official("o-w1", "gov", "الكاتب العام للولاية", "الكاتب العام", "74 000 650", 1, "8:00-17:00"),
    ]),
    body("hosp", 61, "public", "المستشفى الجامعي الحبيب بورقيبة", "الصحة", [
      official("o-h1", "hosp", "رئيس قسم الاستعجالي", "رئيس القسم", "74 000 241"),
    ]),
  ];
  return list.map((b) => ({ ...b, editable: mine(b.gouvernorat_code) }));
}

const SUGGESTIONS = [
  { agency: "samu", kind: "external", body_id: "samu", name: "الإسعاف الطبي الاستعجالي بصفاقس", public_phone: "190", reason: { ar: "أرواح في خطر أو مصابون", fr: "vies en danger" }, missing: false, in_report: true },
  { agency: "police", kind: "external", body_id: "police", name: "إقليم الأمن الوطني بصفاقس", public_phone: "197", reason: { ar: "تأمين الطوق وتنظيم المرور", fr: "périmètre" }, missing: false, in_report: true },
  { agency: "steg", kind: "external", body_id: null, name: "الشركة التونسية للكهرباء والغاز", public_phone: null, reason: { ar: "قطع الغاز والكهرباء عن المباني المتضررة", fr: "coupure" }, missing: true, in_report: false },
];

const call = (id: string, party: string, bodyName: string, who: string, result: string, minutes: number, extra: object = {}) => ({
  id,
  incident_id: "i-1",
  party_id: party,
  body_name: bodyName,
  official_id: null,
  official_name: who,
  number: "74 000 197",
  via: "softphone",
  telephony_call_id: null,
  duration_s: 48,
  result,
  asked: null,
  promised: null,
  eta_min: null,
  note: null,
  follow_up_at: null,
  follow_up_done_at: null,
  follow_up_due: false,
  by_name: "سامي (القاعة الجهوية)",
  at: ago(minutes),
  incident_title: "حريق مستودع · طريق المطار",
  incident_category: "fire",
  ...extra,
});

const PARTIES = [
  {
    id: "p-samu", body_id: "samu", official_id: "o-s1", body_name: "الإسعاف الطبي الاستعجالي بصفاقس", official_name: "طبيب الاستمرار",
    official_role: "طبيب منظم", phones: ["74 000 190"], public_phone: "190", agency: "samu", category: "security", suggested: true,
    reason: "أرواح في خطر", added_by_name: "سامي", added_at: ago(9), removed_at: null, last_result: "answered",
    calls: [call("c1", "p-samu", "الإسعاف الطبي الاستعجالي بصفاقس", "طبيب الاستمرار", "answered", 8, { promised: "سيارتا إسعاف", eta_min: 12, asked: "إسعاف مصابين اثنين" })],
  },
  {
    id: "p-police", body_id: "police", official_id: "o-p2", body_name: "إقليم الأمن الوطني بصفاقس", official_name: "م. س.",
    official_role: "نائب رئيس الإقليم", phones: ["74 000 198"], public_phone: "197", agency: "police", category: "security", suggested: true,
    reason: "تأمين الطوق", added_by_name: "سامي", added_at: ago(9), removed_at: null, last_result: "no_answer",
    calls: [call("c2", "p-police", "إقليم الأمن الوطني بصفاقس", "ر. ع.", "no_answer", 6, { follow_up_at: ago(1), follow_up_due: true })],
  },
  {
    id: "p-central", body_id: "central", official_id: "o-c1", body_name: "القاعة المركزية للعمليات", official_name: "رئيس القاعة المركزية",
    official_role: "رئيس القاعة", phones: ["71 000 100"], public_phone: null, agency: "central_room", category: "civil", suggested: false,
    reason: null, added_by_name: "سامي", added_at: ago(7), removed_at: null, last_result: null, calls: [],
  },
];

const HISTORY = [
  { incident_id: "i-1", title: "حريق مستودع · طريق المطار", category: "fire", gouvernorat_code: 61, status: "open", opened_at: ago(12), level: 2,
    parties: [
      { body_id: "samu", official_id: "o-s1", body_name: "الإسعاف الطبي الاستعجالي بصفاقس", official_name: "طبيب الاستمرار", official_role: "طبيب منظم", last_result: "answered", calls: 1 },
      { body_id: "police", official_id: "o-p2", body_name: "إقليم الأمن الوطني بصفاقس", official_name: "م. س.", official_role: "نائب رئيس الإقليم", last_result: "no_answer", calls: 1 },
      { body_id: "central", official_id: "o-c1", body_name: "القاعة المركزية للعمليات", official_name: "رئيس القاعة المركزية", official_role: "رئيس القاعة", last_result: null, calls: 0 },
    ] },
  { incident_id: "i-0", title: "حريق غابة · جبل عقارب", category: "fire", gouvernorat_code: 61, status: "closed", opened_at: ago(60 * 26), level: 2,
    parties: [
      { body_id: "garde", official_id: "o-g1", body_name: "إقليم الحرس الوطني بصفاقس", official_name: "ف. ب.", official_role: "ضابط الاستمرار", last_result: "answered", calls: 2 },
      { body_id: "gov", official_id: "o-w1", body_name: "ولاية صفاقس", official_name: "الكاتب العام للولاية", official_role: "الكاتب العام", last_result: "answered", calls: 1 },
    ] },
  { incident_id: "i-00", title: "تسرب ماء · نهج المنجي سليم", category: "flood", gouvernorat_code: 61, status: "closed", opened_at: ago(60 * 50), level: 1, parties: [] },
];

async function mockApi(page: Page, central = false) {
  const m = await baseMock(page);
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
    const verb = request.method();
    const common = commonAnswer(verb, pathname, route);
    if (common) return common;
    const L = "/api/v1/staff/liaison";
    if (verb === "GET" && pathname === `${L}/bodies`) {
      const gov = url.searchParams.get("gouvernorat");
      const q = url.searchParams.get("q");
      let list = bodies(central).filter((b) => central || b.gouvernorat_code === null || b.gouvernorat_code === 61);
      if (gov) list = list.filter((b) => b.gouvernorat_code === null || b.gouvernorat_code === Number(gov));
      if (q) list = list.filter((b) => JSON.stringify(b).includes(q));
      return json(route, list);
    }
    if (verb === "GET" && pathname.startsWith(`${L}/bodies/`)) {
      return json(route, bodies(central).find((b) => b.id === pathname.split("/").pop()));
    }
    if (verb === "GET" && pathname === `${L}/incidents/i-1`) {
      return json(route, {
        incident_id: "i-1",
        gouvernorat_code: 61,
        level: { level: 2, note: null, set_by_name: "سامي (القاعة الجهوية)", set_at: ago(10) },
        parties: PARTIES,
        suggestions: SUGGESTIONS,
      });
    }
    if (verb === "GET" && pathname === `${L}/incidents/i-1/picker`) {
      return json(route, {
        suggestions: SUGGESTIONS,
        used_before: [{ body_id: "garde", official_id: "o-g1", body_name: "إقليم الحرس الوطني بصفاقس", official_name: "ف. ب.", times: 3, last_incident_id: "i-0", last_at: ago(60 * 26) }],
        history: HISTORY.slice(1),
      });
    }
    if (verb === "GET" && pathname === `${L}/follow-ups`) return json(route, PARTIES[1]?.calls ?? []);
    if (verb === "GET" && pathname === `${L}/history`) return json(route, HISTORY);
    if (verb === "GET" && pathname === `${L}/calls`) return json(route, [...PARTIES.flatMap((p) => p.calls)].reverse());
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1") {
      return json(route, {
        id: "i-1",
        title: "حريق مستودع · طريق المطار",
        category: "fire",
        status: "open",
        gouvernorat_code: 61,
        centroid: { lat: 34.74, lon: 10.76 },
        severity: 82,
        report_count: 3,
        reporter_count: 3,
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
    if (verb === "GET" && pathname === "/api/v1/staff/address-warnings/categories") return json(route, []);
    if (verb === "GET" && pathname === "/api/v1/staff/address-warnings/incidents/i-1") {
      return json(route, { incident_id: "i-1", incident_kind: "fire", location: null, items: [], unread: 0 });
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

const REGIONAL = { scope_level: "regional", gouvernorat_code: 61 };

test.describe("OS20: informing the partner bodies by phone", () => {
  test.use({ viewport: { width: 1440, height: 1500 } });

  test("a regional room reads its gouvernorat and the national bodies", async ({ page }) => {
    await signIn(page, ["operator"], "Sami Operator", REGIONAL);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.goto("/liaison");
    await expect(page.getByRole("heading", { level: 1, name: "نظام الاتصال" })).toBeVisible();
    await expect(page.getByText("إقليم الأمن الوطني بصفاقس")).toBeVisible();
    await expect(page.getByText("للاطلاع: تحيّنها القاعة المعنية").first()).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os20-contacts-regional.png` });
  });

  test("the central room reads every body and keeps the national ones", async ({ page }) => {
    await signIn(page, ["operator"], "Leila Central");
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page, true);
    await page.goto("/liaison");
    await expect(page.getByText("وزارة التجهيز والإسكان")).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os20-contacts-central.png` });
    await page.getByRole("button", { name: "سجل البلاغات" }).click();
    await expect(page.getByText("حريق غابة · جبل عقارب")).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os20-history.png` });
    await page.getByRole("button", { name: "سجل المكالمات" }).click();
    await expect(page.getByText("سيارتا إسعاف", { exact: false })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os20-call-log.png` });
  });

  test("the report: level 2, the bodies informed, the picker and a call", async ({ page }) => {
    await signIn(page, ["operator"], "Sami Operator", REGIONAL);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.goto("/incidents/i-1");
    await page.addStyleTag({ content: "header, aside.softphone { display: none !important; }" });
    const panel = page.locator(".liaison-panel");
    await expect(panel.getByText("سيارتا إسعاف", { exact: false })).toBeVisible();
    await panel.screenshot({ path: `${SHOTS}/os20-incident.png` });

    await panel.getByRole("button", { name: "اختيار المشاركين" }).click();
    const picker = panel.getByRole("dialog", { name: "اختيار المشاركين في البلاغ" });
    await expect(picker.getByText("إقليم الحرس الوطني بصفاقس")).toBeVisible();
    await picker.screenshot({ path: `${SHOTS}/os20-picker.png` });
    await picker.getByRole("searchbox").fill("المستشفى");
    await picker.getByRole("checkbox", { name: /رئيس قسم الاستعجالي/ }).check();
    await picker.getByRole("searchbox").fill("");
    await picker.getByRole("checkbox", { name: /ف\. ب\./ }).check();
    await expect(picker.getByText("2 مختار")).toBeVisible();
    await picker.screenshot({ path: `${SHOTS}/os20-picker-selected.png` });
    await picker.getByRole("radio", { name: "من سجل البلاغات" }).check();
    await expect(picker.getByText("مشاركون أُبلغوا في بلاغات سابقة")).toBeVisible();
    await picker.screenshot({ path: `${SHOTS}/os20-picker-history.png` });
    await picker.getByRole("button", { name: "إغلاق" }).click();

    const police = panel.locator(".liaison-party").filter({ hasText: "إقليم الأمن الوطني بصفاقس" });
    await police.getByRole("button", { name: "اتصال يدوي ثم تسجيل" }).click();
    const rec = police.getByRole("dialog");
    await rec.getByRole("radio", { name: "لا رد" }).check();
    await expect(rec.getByText(/المسؤول التالي/)).toBeVisible();
    await rec.screenshot({ path: `${SHOTS}/os20-call-no-answer.png` });
    await rec.getByRole("radio", { name: "رُدّ" }).check();
    await rec.getByLabel("المطلوب").fill("تأمين الطوق وتحويل المرور");
    await rec.getByLabel("الالتزام").fill("دورية في الطريق");
    await rec.getByRole("radio", { name: "بعد 15 د" }).check();
    await rec.screenshot({ path: `${SHOTS}/os20-call-answered.png` });
  });
});
