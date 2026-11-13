// Screenshots and on-screen regions of every dashboard screen, and who can open it (Yamen, 2026-11-13).
//
// Runs against a real stack: the API on a local database and the dashboard built against it (scripts/atlas/run.sh
// starts both). Each persona signs in with a token from scripts/atlas/mint.py; the administrator persona holds every
// role, so its screenshot is the "mother dashboard". For each screen the script records the regions a flowchart box
// points at (title, tabs, sections, tables, map, main buttons) with their boxes on the screenshot.
//
//   node scripts/atlas/capture.mjs <inventory.json> <out-dir>
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { regions } from "./regions.mjs";

const { chromium } = createRequire(import.meta.url)("playwright");
const HERE = dirname(fileURLToPath(import.meta.url));
const [, , INV, OUT] = process.argv;
const BASE = process.env.ATLAS_DASHBOARD_URL ?? "http://localhost:4174";
const ISSUER = process.env.ATLAS_ISSUER ?? "http://localhost:8099/realms/ehimaya-staff";
const PY = process.env.ATLAS_PYTHON ?? "python3";
const MAX_H = 2200;

// ┏━━ SIMULATION ━━ personas: tokens signed by a local key that only this script's API instance trusts
// ┗━━ PRODUCTION: never run against a production API; the atlas is built on a local copy.
const ALL = ["sysadmin", "operator", "ops_manager", "field_commander", "central_committee", "local_committee",
  "personnel_officer", "maintenance_officer", "inspector_general", "content_editor", "org_auditor", "ai_admin",
  "security_admin", "regional_account_admin", "medical_coordinator"];
const REGIONAL = { scope_level: "regional", gouvernorat_code: 61 };
export const PERSONAS = {
  admin: { label: "مدير النظام", roles: ALL, claims: {} },
  central: { label: "القاعة المركزية", roles: ["operator", "ops_manager"], claims: {} },
  central_committee: { label: "اللجنة الوطنية", roles: ["central_committee"], claims: {} },
  regional: { label: "القاعة الجهوية", roles: ["operator", "ops_manager"], claims: REGIONAL },
  commander: { label: "القائد الميداني", roles: ["field_commander"], claims: REGIONAL },
  local_committee: { label: "اللجنة الجهوية", roles: ["local_committee"], claims: REGIONAL },
  agents: {
    label: "بقية الأعوان والمصالح",
    roles: ["personnel_officer", "maintenance_officer", "inspector_general", "content_editor", "org_auditor",
      "medical_coordinator"],
    claims: REGIONAL,
  },
};

function token(p) {
  return execFileSync(PY, ["-I", join(HERE, "mint.py"), p.roles.join(","), JSON.stringify({ name: p.label, ...p.claims })])
    .toString().trim();
}

async function context(browser, persona) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, locale: "ar-TN" });
  const now = Math.floor(Date.now() / 1000);
  const user = JSON.stringify({ access_token: token(persona), token_type: "Bearer", scope: "openid profile",
    profile: { sub: "atlas", iss: ISSUER, aud: "ehimaya-dashboard", exp: 0, iat: 0 }, expires_at: now + 3 * 3600 });
  await ctx.addInitScript(([k, v]) => {
    sessionStorage.setItem(k, v);
    localStorage.setItem("ehimaya.lang", "ar");
    localStorage.setItem("ehimaya.theme", "light");
  }, [`oidc.user:${ISSUER}:ehimaya-dashboard`, user]);
  return ctx;
}

const settle = (page, ms = 2200) => page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {})
  .then(() => page.waitForTimeout(ms));

/** The concrete path of a route with parameters: the first matching link on its parent list page. */
async function resolve(page, route) {
  if (!route.includes(":")) return route;
  const parent = route.split("/:")[0];
  const re = "^" + route.replace(/:[^/]+/g, "[^/]+") + "$";
  await page.goto(BASE + parent);
  await settle(page, 1500);
  const href = await page.evaluate((src) => {
    const rx = new RegExp(src);
    const a = [...document.querySelectorAll("main a[href]")].map((x) => x.getAttribute("href")).find((h) => rx.test(h));
    return a ?? null;
  }, re);
  return href;
}

// Windows of a screen (Yamen, 2026-11-13: «بكل تفاصيل النوافذ»): each tab that is not shown first, and each dialog a
// button of the page opens (add, new, edit, upload, invite…). Found on the page itself, so a new tab or dialog joins the
// atlas on the next run. Deleting buttons are never pressed; a dialog is closed with Escape before the next one.
// A button opens a window when, after the click, a dialog shows or the page gains fields (the dashboard opens its
// forms as inline panels). Buttons that write or leave are never pressed.
const NEVER = /(حذف|إلغاء|تأكيد|أكّد|أكد|إرسال|أرسل|حفظ|احفظ|موافقة|رفض|اعتماد|اعتمد|إغلاق|أغلق|خروج|تنفيذ|نفّذ|إطلاق|أطلق|تشغيل|إيقاف|تحديث|السابق|التالي|طباعة|تنزيل|نسخ|Delete|Save|Send)/;
const MAX_TABS = 8, MAX_DIALOGS = 4;

async function panelInfo(page, before) {
  const win = await page.evaluate(() => {
    const d = [...document.querySelectorAll('dialog[open], [role="dialog"], [aria-modal="true"]')].pop();
    if (!d) return null;
    const r = d.getBoundingClientRect();
    const h = d.querySelector("h1,h2,h3");
    return { kind: "window", label: (h?.textContent || d.textContent || "").trim().slice(0, 90),
      x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height) };
  });
  const fields = await page.$$eval("main input:not([type=hidden]), main textarea, main select", (x) => x.length);
  if (!win && fields <= before) return null;
  return win;
}

async function shoot(page, file, win) {
  let info = await page.evaluate(regions);
  if (win) info = { ...info, regions: [win, ...info.regions.filter((r) => r.y >= win.y && r.y < win.y + win.h)] };
  if (info.height > 900) {
    await page.setViewportSize({ width: 1440, height: Math.min(MAX_H, Math.ceil(info.height)) });
    await page.waitForTimeout(500);
    const again = await page.evaluate(regions);
    info = { ...(win ? { ...again, regions: [win, ...again.regions.filter((r) => r.y >= win.y && r.y < win.y + win.h)] } : again),
      height: Math.min(MAX_H, Math.ceil(info.height)) };
  }
  await page.screenshot({ path: join(OUT, file), type: "jpeg", quality: 72 });
  await page.setViewportSize({ width: 1440, height: 900 });
  return info;
}

async function windows(page, id, path, routes) {
  const out = [];
  // Tabs that are links (nav.tabs): a tab whose path is not a screen of its own becomes a window of this screen.
  const links = await page.$$eval("main nav.tabs a[href], main .tabs a[href]", (as) => as.map((a) => ({
    href: a.getAttribute("href"), label: a.textContent.trim().replace(/\s+/g, " "), on: a.classList.contains("tabs__tab--active") })));
  for (const [i, l] of links.entries()) {
    if (l.on || !l.href || routes.has(l.href) || l.href === path || i >= MAX_TABS) continue;
    try {
      await page.goto(BASE + l.href);
      await settle(page, 1200);
      const file = `shots/${id}~link${i}.jpg`;
      out.push({ id: `${id}~link${i}`, kind: "tab", label: l.label.slice(0, 60), shot: file, path: l.href, ...(await shoot(page, file, null)) });
    } catch { /* left out */ }
  }
  const tabSel = 'main [role="tab"], main [role="group"] button[aria-pressed="false"]';
  const tabs = await page.$$eval(tabSel, (ts) => ts.map((t, i) => ({ i, label: t.textContent.trim().replace(/\s+/g, " "),
    sel: t.getAttribute("aria-selected") === "true" })));
  for (const t of tabs.filter((x) => !x.sel && x.label && !NEVER.test(x.label)).slice(0, MAX_TABS)) {
    try {
      await page.goto(BASE + path);
      await settle(page, 1200);
      await page.locator(tabSel).nth(t.i).click({ timeout: 4000 });
      await settle(page, 1200);
      const file = `shots/${id}~tab${t.i}.jpg`;
      out.push({ id: `${id}~tab${t.i}`, kind: "tab", label: t.label.slice(0, 60), shot: file, ...(await shoot(page, file, null)) });
    } catch { /* a tab that does not answer is left out */ }
  }
  await page.goto(BASE + path);
  await settle(page, 1200);
  const labels = await page.$$eval('main button:not([disabled]):not([role="tab"]):not([aria-pressed])',
    (bs) => bs.map((b) => b.textContent.trim().replace(/\s+/g, " ")));
  const openers = [...new Set(labels.filter((l) => l.length > 1 && l.length < 50 && !NEVER.test(l)))].slice(0, 12);
  let k = 0;
  for (const label of openers) {
    if (k >= MAX_DIALOGS) break;
    try {
      await page.goto(BASE + path);
      await settle(page, 1200);
      const before = await page.$$eval("main input:not([type=hidden]), main textarea, main select", (x) => x.length);
      const urlBefore = page.url();
      await page.locator('main button:not([disabled]):not([role="tab"]):not([aria-pressed])', { hasText: label }).first()
        .click({ timeout: 4000 });
      await page.waitForTimeout(900);
      if (page.url() !== urlBefore) continue; // a link to another screen, which has its own card
      const fields = await page.$$eval("main input:not([type=hidden]), main textarea, main select", (x) => x.length);
      const win = await panelInfo(page, before);
      if (!win && fields <= before) continue;
      const file = `shots/${id}~win${k}.jpg`;
      out.push({ id: `${id}~win${k}`, kind: "dialog", label, shot: file, ...(await shoot(page, file, win)) });
      k++;
      await page.keyboard.press("Escape");
    } catch { /* a button that opens no window is not a window */ }
  }
  return out;
}

async function main() {
  const inv = JSON.parse(readFileSync(INV, "utf8"));
  const screens = [{ route: "/", page: "apps/dashboard/src/pages/HomePage.tsx", components: [], menu: { group: "العمليات اليومية", item: "الرئيسية", group_key: "ops" }, api: [] }, ...inv.screens.filter((s) => s.route !== "/*")];
  mkdirSync(join(OUT, "shots"), { recursive: true });
  const browser = await chromium.launch();
  const result = {};
  // 1. The administrator: every screen, screenshot and regions.
  const ctx = await context(browser, PERSONAS.admin);
  const page = await ctx.newPage();
  for (const s of screens) {
    const id = s.route === "/" ? "home" : s.route.slice(1).replace(/[/:]+/g, "-");
    try {
      const path = await resolve(page, s.route);
      if (!path) { result[s.route] = { id, missing: "no_item" }; continue; }
      await page.goto(BASE + path);
      await settle(page);
      let info = await page.evaluate(regions);
      // The dashboard scrolls inside its frame, so a long page is shown whole by making the window as tall as it.
      if (info.height > 900) {
        await page.setViewportSize({ width: 1440, height: Math.ceil(info.height) });
        await page.waitForTimeout(700);
        info = { ...(await page.evaluate(regions)), height: Math.ceil(info.height) };
      }
      const file = `shots/${id}.jpg`;
      await page.screenshot({ path: join(OUT, file), type: "jpeg", quality: 72 });
      await page.setViewportSize({ width: 1440, height: 900 });
      const wins = process.env.ATLAS_NO_WINDOWS ? [] : await windows(page, id, path, new Set(screens.map((x) => x.route)));
      result[s.route] = { id, path, shot: file, ...info, access: {}, windows: wins };
      process.stdout.write(`✓ ${s.route} (${info.regions.length}, ${wins.length} windows)\n`);
    } catch (e) {
      result[s.route] = { id, missing: String(e).slice(0, 120) };
      process.stdout.write(`✗ ${s.route} ${String(e).slice(0, 80)}\n`);
    }
  }
  await ctx.close();
  // 2. Who opens what: each persona on each screen without parameters (a detail screen follows its list).
  // ATLAS_ACCESS_FROM=<older capture.json> reuses its answers, to retake only the screenshots.
  const prior = process.env.ATLAS_ACCESS_FROM
    ? Object.fromEntries(JSON.parse(readFileSync(process.env.ATLAS_ACCESS_FROM, "utf8")).screens.map((s) => [s.route, s.access ?? {}]))
    : null;
  if (prior) for (const s of screens) if (result[s.route]?.shot) result[s.route].access = prior[s.route] ?? {};
  for (const [key, persona] of Object.entries(prior ? {} : PERSONAS)) {
    if (key === "admin") continue;
    const c = await context(browser, persona);
    const p = await c.newPage();
    for (const s of screens) {
      if (s.route.includes(":") || !result[s.route]?.shot) continue;
      await p.goto(BASE + s.route);
      await settle(p, 900);
      const denied = await p.evaluate(() => Boolean(document.getElementById("no-access-title")));
      const landed = new URL(p.url()).pathname;
      result[s.route].access[key] = !denied && landed === s.route;
    }
    await c.close();
    process.stdout.write(`persona ${key} done\n`);
  }
  for (const s of prior ? [] : screens) {
    if (!s.route.includes(":") || !result[s.route]?.shot) continue;
    const parent = result[s.route.split("/:")[0]];
    result[s.route].access = { ...(parent?.access ?? {}) };
  }
  await browser.close();
  writeFileSync(join(OUT, "capture.json"), JSON.stringify({ personas: Object.fromEntries(Object.entries(PERSONAS)
    .map(([k, v]) => [k, v.label])), screens: screens.map((s) => ({ ...s, ...result[s.route] })) }, null, 1));
}

main();
