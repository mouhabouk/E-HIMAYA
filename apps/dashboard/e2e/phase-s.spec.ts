/**
 * Phase S in the browser (docs/phase-s/design-s.md): the strategies menu and an item the system administrator adds,
 * and the SNACR page of Nabeul on the [SIM] years (aggregates drawn from the development database: no record, no
 * name). Screenshots for the phase report land in test-results/phase-s/.
 */
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

const SHOTS = "test-results/phase-s";
const SIM = JSON.parse(readFileSync(new URL("./fixtures/snacr-nabeul-sim.json", import.meta.url), "utf8")) as {
  analysis: { years: number[] };
  boundaries: unknown;
};

const ITEM = {
  key: "snrrc_2030",
  name: { ar: "الاستراتيجية الوطنية للحد من مخاطر الكوارث 2030", fr: "Stratégie nationale de réduction des risques 2030", en: "National DRR strategy 2030" },
  summary: { ar: "المحاور الأربعة لإطار سنداي كما تبنّتها تونس" },
  body: {
    ar: "## المحاور\n\n1. فهم مخاطر الكوارث\n2. تعزيز حوكمة المخاطر\n3. الاستثمار في الحد من المخاطر\n4. التأهب للاستجابة الفعالة\n\n## صلتها بالمنصة\n\nيبني **مخطط تحليل المخاطر وتغطيتها** سجل المخاطر الخاصة على هذه المحاور.",
  },
  link: null,
  icon: "policy",
  tone: "teal",
  roles: [],
  position: 10,
  active: true,
  updated_by_name: "مدير النظام",
  updated_at: "2026-10-30T09:00:00Z",
};

const METHOD = {
  goal: 90,
  urban: 1000,
  periurban: 150,
  targets: {
    medical: { urban: 10, periurban: 15, rural: 25 },
    road: { urban: 12, periurban: 18, rural: 30 },
    fire: { urban: 10, periurban: 15, rural: 25 },
    rescue: { urban: 15, periurban: 20, rural: 35 },
  },
  review_months: 12,
  validity_years: 5,
};

const REFERENCES = [
  ["TN-91-39", "Loi n° 91-39 du 8 juin 1991 relative à la lutte contre les calamités", "legal_basis"],
  ["TN-93-942", "Décret n° 93-942 du 26 avril 1993 (commissions nationale et régionales)", "committees_and_review"],
  ["FR-SDACR", "Schéma départemental d'analyse et de couverture des risques (CGCT L1424-7)", "structure_everyday_special_coverage"],
  ["UK-NFCC-CRMP", "NFCC Community Risk Management Planning, Strategic Framework", "plan_cycle"],
  ["US-NFPA-1710", "NFPA 1710, Standard for career fire departments (2020)", "percentile_indicators"],
  ["UN-SENDAI", "Sendai Framework for Disaster Risk Reduction 2015-2030", "special_risks"],
  ["ISO-31000", "ISO 31000:2018 Risk management, Guidelines", "matrix"],
].map(([code, title, use]) => ({ code, title, use, url: null }));

async function mockApi(page: Page) {
  const m = await baseMock(page);
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    if (pathname === "/api/v1/geo/gouvernorats") {
      return json(route, [
        { code: 11, iso_code: "TN-11", name: "تونس", name_ar: "تونس", name_fr: "Tunis", delegation_count: 21 },
        { code: 21, iso_code: "TN-21", name: "نابل", name_ar: "نابل", name_fr: "Nabeul", delegation_count: 16 },
      ]);
    }
    if (pathname === "/api/v1/staff/strategies") return json(route, { items: [ITEM], can_manage: true });
    const common = commonAnswer(method, pathname, route);
    if (common) return common;
    if (pathname === "/api/v1/staff/strategies/snrrc_2030") return json(route, ITEM);
    if (pathname === "/api/v1/staff/snacr") {
      return json(route, {
        datasets: SIM.analysis.years.map((year, i) => ({
          id: `d${year}`,
          year,
          source: "simulated",
          simulated: true,
          file_name: null,
          rows: [151000, 164000, 182000][i],
          quality: {},
          imported_by_name: "النظام",
          imported_at: "2026-10-30T08:00:00Z",
        })),
        default_years: SIM.analysis.years,
        method: METHOD,
        references: REFERENCES,
        can_import: true,
        can_edit_national: true,
      });
    }
    if (pathname === "/api/v1/staff/snacr/analysis") return json(route, SIM.analysis);
    if (pathname === "/api/v1/geo/boundaries/delegations") return json(route, SIM.boundaries);
    if (pathname === "/api/v1/staff/snacr/unmatched") return json(route, [{ gouvernorat_code: 43, raw: "سيدي بوزيد المدينة", rows: 1184 }]);
    if (pathname === "/api/v1/staff/snacr/special-risks") {
      return json(route, [
        ["flood", 4, 4, "high", true],
        ["forest_fire", 3, 4, "medium", true],
        ["coastal", 4, 3, "medium", true],
        ["industrial", 2, 3, "low", true],
      ].map(([hazard, probability, gravity, level, simulated], i) => ({
        id: `r${i}`, gouvernorat_code: 21, hazard, probability, gravity, level, note: null, simulated, updated_by_name: null, updated_at: null,
      })));
    }
    if (pathname === "/api/v1/staff/snacr/plans") return json(route, []);
    if (pathname === "/api/v1/staff/features/mine") return json(route, { granted: [], hidden: [], lent: {} });
    return json(route, {});
  });
  return m;
}

test.describe("phase S", () => {
  test("the strategies menu and an item the administrator adds", async ({ page }) => {
    await signIn(page, ["central_committee", "sysadmin"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.goto("/strategies");
    await expect(page.getByRole("link", { name: /الاستراتيجية الوطنية للحد/ })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/s-strategies.png`, fullPage: true });
    await page.getByRole("tab", { name: "إدارة العناصر" }).click();
    await page.getByRole("button", { name: "إحداث عنصر" }).click();
    await page.getByLabel("المعرّف").fill("heat_plan");
    await page.getByLabel("الاسم (العربية)").fill("خطة مجابهة موجات الحر");
    await page.screenshot({ path: `${SHOTS}/s-strategies-manage.png`, fullPage: true });
    await page.goto("/strategies/snrrc_2030");
    await expect(page.getByRole("heading", { name: "المحاور" })).toBeVisible();
    await page.screenshot({ path: `${SHOTS}/s-strategy-item.png`, fullPage: true });
  });

  test("the SNACR analysis of Nabeul", async ({ page }) => {
    await signIn(page, ["central_committee"]);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.lang", "ar"));
    await mockApi(page);
    await page.goto("/snacr");
    await page.getByLabel("الولاية").selectOption("21");
    await expect(page.getByRole("rowheader", { name: "قرمبالية" })).toBeVisible();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SHOTS}/s-snacr-indicators.png`, fullPage: true });
    for (const [tab, shot] of [
      ["مصفوفة الأولويات", "s-snacr-matrix"],
      ["المواسم والساعات", "s-snacr-seasons"],
      ["المخاطر الخاصة", "s-snacr-special"],
      ["الأرشيف", "s-snacr-archive"],
      ["المنهجية والمراجع", "s-snacr-method"],
    ] as const) {
      await page.getByRole("tab", { name: tab }).click();
      await page.screenshot({ path: `${SHOTS}/${shot}.png`, fullPage: true });
    }
  });
});
