/**
 * OS2-3 and OS2-4 in the browser (docs/phase-os2b/design-os2b.md): the statistics of the call-taking cards and the
 * review of the nine [SIM] cards. The figures are demonstration data [SIM]. Screenshots for the phase report land in
 * test-results/phase-os2b/.
 */
import { expect, test, type Page } from "@playwright/test";
import type { CallCard, CardStats, ReviewItem } from "../src/lib/callCards";
import { SIM_CALL_CARDS } from "../src/test/callCardsData";
import { makeSettings } from "../src/test/phase9Fixtures";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-os2b";

const GOUVERNORATS = [
  [11, "تونس", "Tunis"],
  [61, "صفاقس", "Sfax"],
  [51, "سوسة", "Sousse"],
  [21, "نابل", "Nabeul"],
  [23, "بنزرت", "Bizerte"],
  [41, "القيروان", "Kairouan"],
].map(([code, ar, fr]) => ({ code, iso_code: `TN-${code}`, name: ar, name_ar: ar, name_fr: fr, delegation_count: 10 }));

const card = (category: string) => SIM_CALL_CARDS.find((c) => c.category === category) as CallCard;

function room(room: string, entered: number, share: number, withS: number, withoutS: number, p90: number, match: number) {
  const checked = Math.round(entered * share * 0.6);
  return {
    room,
    entered,
    with_card: Math.round(entered * share),
    median_with_s: withS,
    median_without_s: withoutS,
    p90_s: p90,
    field_checked: checked,
    field_confirmed: Math.round(checked * match),
  };
}

const ROOMS = [
  room("central", 212, 0.84, 112, 151, 220, 0.88),
  room("g:11", 248, 0.79, 118, 155, 235, 0.85),
  room("g:61", 176, 0.73, 124, 164, 250, 0.83),
  room("g:51", 151, 0.68, 130, 158, 245, 0.81),
  room("g:21", 139, 0.66, 132, 169, 260, 0.8),
  room("g:23", 118, 0.61, 141, 172, 275, 0.74),
  room("g:41", 97, 0.44, 150, 161, 305, 0.71),
];

function cardFigures(category: string, used: number, median: number, keyUnknown: number, checks: number[]) {
  const c = card(category);
  const [confirmed = 0, nature = 0, lives = 0, injured = 0, band = 0] = checks;
  return {
    category: c.category,
    title: c.content.title,
    used,
    median_s: median,
    key_unknown: keyUnknown,
    key_answered: 100,
    field_checked: confirmed + nature + lives + injured + band,
    checks: {
      confirmed,
      nature_differs: nature,
      lives_not_on_card: lives,
      injured_not_on_card: injured,
      band_below_toll: band,
    },
    questions: c.content.questions.map((q, i) => {
      const unknown = q.id === "breathing" ? 31 : [13, 9, 6, 1, 4][i % 5] ?? 5;
      const yes = q.id === "breathing" ? 52 : [38, 27, 12, 20, 9][i % 5] ?? 20;
      return {
        id: q.id,
        text: q.text,
        key: q.key,
        yes,
        no: 100 - yes - unknown,
        unknown,
        field_changed: q.key ? 9 : 2,
        field_answered: 60,
      };
    }),
    read: Object.fromEntries(Object.keys(c.content.instructions).map((k, i) => [k, [21, 64, 38][i] ?? 10])),
    instruction_titles: Object.fromEntries(Object.entries(c.content.instructions).map(([k, v]) => [k, v.title])),
  };
}

const total = ROOMS.reduce(
  (a, r) => ({
    entered: a.entered + r.entered,
    with_card: a.with_card + r.with_card,
    field_checked: a.field_checked + r.field_checked,
    field_confirmed: a.field_confirmed + r.field_confirmed,
  }),
  { entered: 0, with_card: 0, field_checked: 0, field_confirmed: 0 },
);

const STATS: CardStats = {
  days: 30,
  since: "2026-10-14T00:00:00Z",
  room: null,
  total: { ...total, median_with_s: 125, median_without_s: 160, p90_s: 250 },
  national: { ...total, median_with_s: 125, median_without_s: 160, p90_s: 250 },
  rooms: ROOMS,
  cards: [
    cardFigures("medical", 288, 135, 14, [72, 4, 6, 13, 5]),
    cardFigures("fire", 201, 118, 6, [86, 3, 5, 4, 2]),
    cardFigures("traffic_accident", 187, 122, 11, [78, 2, 4, 12, 4]),
    cardFigures("drowning", 64, 100, 5, [89, 2, 6, 3, 0]),
    cardFigures("flood", 52, 140, 8, [83, 9, 5, 3, 0]),
    cardFigures("chemical_leak", 41, 110, 22, [70, 18, 7, 0, 5]),
    cardFigures("landslide", 23, 128, 9, [80, 10, 10, 0, 0]),
    cardFigures("sos", 95, 75, 12, [60, 0, 0, 0, 0]),
    cardFigures("other", 33, 90, 0, [0, 0, 0, 0, 0]),
  ] as CardStats["cards"],
};

// The review [SIM]: fire and flood done, the medical card waiting for the doctor, drowning with the Office, traffic
// accident waiting for approval, the rest not started.
const at = "2026-11-20T09:30:00Z";
const approvedV2 = (category: string, unchanged = false): CallCard => ({
  ...card(category),
  id: `${category}-2`,
  version: 2,
  sim: false,
  unchanged,
  approved_by: "رئيس العمليات",
  approved_at: at,
});
const medicalDraft = (): CallCard => {
  const c = structuredClone(card("medical"));
  const breathing = c.content.questions.find((q) => q.id === "breathing");
  if (breathing) breathing.help = "ضع يدك على صدره: هل يرتفع وينخفض؟ عُدّ معي حتى 10.";
  c.content.questions.splice(1, 0, {
    id: "faint",
    text: "هل فقد المريض الوعي ثم استعاده (إغماء)؟",
    help: null,
    key: true,
    when: null,
    effects: {
      yes: { why: "إغماء", band: "high", flag: null, means: ["سيارة إسعاف"], instruction: null, lives: false, injured: false },
    },
  });
  const recovery = c.content.instructions.recovery;
  if (recovery) recovery.steps.splice(1, 0, "افتح فمه بلطف إن تقيّأ.");
  return {
    ...c,
    id: "medical-2",
    version: 2,
    status: "draft",
    sim: false,
    medical_validated_at: null,
    medical_validated_by: null,
    medical_reason: null,
    approved_by: null,
    approved_at: null,
    approval_reason: null,
    created_by_name: "مكتب الوقاية",
    updated_by_name: "مكتب الوقاية",
    submitted_at: at,
    submitted_by_name: "مكتب الوقاية",
    notes: {
      breathing: "صيغة أسهل للمتصل حسب أرقام «لا يعرف».",
      faint: "13% من حالات «مصابون لم تتوقعهم» كانت إغماء.",
    },
    updated_at: at,
  };
};

function item(category: string, stage: ReviewItem["stage"], over: Partial<ReviewItem> = {}): ReviewItem {
  const c = card(category);
  return {
    category: c.category,
    title: c.content.title,
    stage,
    medical: ["medical", "drowning"].includes(category),
    approved: c,
    draft: null,
    office: stage === "not_started" ? null : "مكتب الوقاية",
    doctor: ["medical", "drowning"].includes(category) ? "د. الطبيب المنسق" : null,
    ...over,
  };
}

const REVIEW = {
  items: [
    item("fire", "done", { approved: approvedV2("fire") }),
    item("flood", "done", { approved: approvedV2("flood", true) }),
    item("medical", "doctor", { draft: medicalDraft() }),
    item("drowning", "office", {
      draft: { ...card("drowning"), id: "drowning-2", version: 2, status: "draft", sim: false, updated_at: at },
    }),
    item("traffic_accident", "approval", {
      draft: {
        ...card("traffic_accident"),
        id: "traffic-2",
        version: 2,
        status: "draft",
        sim: false,
        submitted_at: at,
        updated_at: at,
      },
    }),
    item("chemical_leak", "not_started"),
    item("landslide", "not_started"),
    item("sos", "not_started"),
    item("other", "not_started"),
  ],
  done: 2,
  total: 9,
};

async function mockApi(page: Page) {
  await baseMock(page);
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    if (pathname === "/api/v1/staff/settings") return json(route, { items: makeSettings(false), thresholds: [] });
    if (pathname === "/api/v1/geo/gouvernorats") return json(route, GOUVERNORATS);
    if (pathname === "/api/v1/staff/call-cards/stats") return json(route, STATS);
    if (pathname === "/api/v1/staff/call-cards/review") return json(route, REVIEW);
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    return json(route, method === "GET" ? { items: [], next_cursor: null } : { detail: "not_found" }, method === "GET" ? 200 : 404);
  });
}

test.describe("OS2-3 and OS2-4: statistics and review of the call-taking cards", () => {
  test.use({ viewport: { width: 1280, height: 2000 } });
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("the head of operations reads the statistics per room and per card", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 2700 });
    await signIn(page, ["ops_manager"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/call-cards");
    await page.getByRole("tab", { name: "الإحصاء" }).click();
    await expect(page.getByRole("heading", { name: "حسب القاعة" })).toBeVisible();
    await expect(page.getByRole("row", { name: /القيروان/ })).toBeVisible();
    await page.getByRole("button", { name: /إسعاف/ }).first().click();
    await expect(page.getByText(/أعلى نسبة/)).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os2b-stats.png`, fullPage: true });
  });

  test("the doctor reviews the medical card the Office handed over", async ({ page }) => {
    await signIn(page, ["medical_coordinator"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await page.goto("/call-cards");
    await page.getByRole("tab", { name: "مراجعة البطاقات التجريبية" }).click();
    await expect(page.getByRole("heading", { name: "مراجعة البطاقات التجريبية" })).toBeVisible();
    await expect(page.getByText("هل فقد المريض الوعي ثم استعاده (إغماء)؟")).toBeVisible();
    await expect(page.getByRole("button", { name: "تصديق طبي" })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/os2b-review.png`, fullPage: true });
  });
});
