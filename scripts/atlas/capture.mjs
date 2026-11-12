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

/** Regions a flowchart box can point at, in reading order (top to bottom, right to left). */
function regions() {
  const main = document.querySelector("main") ?? document.body;
  const out = [];
  const seen = new Set();
  const txt = (el) => (el?.innerText ?? "").replace(/\s+/g, " ").trim().slice(0, 90);
  const add = (kind, el, label) => {
    if (!el || seen.has(el)) return;
    const r = el.getBoundingClientRect();
    if (r.width < 24 || r.height < 12) return;
    seen.add(el);
    out.push({ kind, label: label || txt(el), x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY),
      w: Math.round(r.width), h: Math.round(r.height) });
  };
  const nav = document.querySelector("nav[aria-label]");
  if (nav) add("menu", nav, "القائمة الرئيسية");
  const h1 = main.querySelector("h1");
  if (h1) add("title", h1.closest("header") ?? h1, txt(h1));
  const lead = h1?.closest("header")?.parentElement?.querySelector(":scope > p, header + p, p.muted");
  if (lead) add("lead", lead);
  [...main.querySelectorAll("[role=tablist], .tabs, .segmented")].slice(0, 2).forEach((t) => add("tabs", t, txt(t)));
  [...main.querySelectorAll(".maplibregl-map")].slice(0, 1).forEach((m) => add("map", m, "الخريطة"));
  [...main.querySelectorAll("h2, h3")].slice(0, 9).forEach((h) => {
    const box = h.closest("section, article, .card, fieldset") ?? h;
    add("section", box, txt(h));
  });
  [...main.querySelectorAll("table")].slice(0, 2).forEach((t) => {
    const head = [...t.querySelectorAll("th")].map((th) => txt(th)).filter(Boolean).slice(0, 5).join("، ");
    add("table", t.closest(".table-wrap, .card") ?? t, head ? `جدول: ${head}` : "جدول");
  });
  [...main.querySelectorAll("form")].slice(0, 2).forEach((f) => add("form", f, txt(f.querySelector("legend, h2, h3, label")) || "استمارة"));
  [...main.querySelectorAll(".btn--primary, button[type=submit]")].slice(0, 3).forEach((b) => add("action", b, txt(b)));
  const lead2 = out.find((o) => o.kind === "lead");
  return { regions: out.sort((a, b) => (Math.abs(a.y - b.y) < 14 ? b.x - a.x : a.y - b.y)), lead: lead2?.label ?? "",
    height: Math.min(Math.max(document.documentElement.scrollHeight,
      ...[...document.querySelectorAll("main, main *")].filter((e) => /(auto|scroll)/.test(getComputedStyle(e).overflowY))
        .map((e) => e.scrollHeight + e.getBoundingClientRect().top)), 2400), title: txt(h1) };
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
        await page.setViewportSize({ width: 1440, height: info.height });
        await page.waitForTimeout(700);
        info = { ...(await page.evaluate(regions)), height: info.height };
      }
      const file = `shots/${id}.jpg`;
      await page.screenshot({ path: join(OUT, file), type: "jpeg", quality: 72 });
      await page.setViewportSize({ width: 1440, height: 900 });
      result[s.route] = { id, path, shot: file, ...info, access: {} };
      process.stdout.write(`✓ ${s.route} (${info.regions.length})\n`);
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
