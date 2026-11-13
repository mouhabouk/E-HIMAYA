// Screenshots and on-screen regions of the public portal's screens for the flowchart atlas (Yamen, 2026-11-13).
//
// Runs against the portal built on the local API of scripts/atlas/run.sh. A visitor opens the public pages; a citizen
// signed in with a local token (scripts/atlas/mint.py, realm ehimaya-public) opens the institution pages, on an
// institution the script registers itself through the API [SIM]. The API requests each page sends while it opens are
// recorded too: the atlas shows what the screen reads and writes.
//
//   node scripts/atlas/capture_portal.mjs <screens.json> <out-dir>
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { regions } from "./regions.mjs";

const { chromium } = createRequire(import.meta.url)("playwright");
const [, , SPEC, OUT] = process.argv;
const BASE = process.env.ATLAS_PORTAL_URL ?? "http://localhost:4175";
const API = process.env.ATLAS_API_URL ?? "http://localhost:8000";
const ISSUER = process.env.ATLAS_PUBLIC_ISSUER ?? "http://localhost:8099/realms/ehimaya-public";
const TOKEN = readFileSync(process.env.ATLAS_CITIZEN_TOKEN, "utf8").trim();

async function api(path, init = {}) {
  const r = await fetch(API + path, { ...init, headers: { authorization: `Bearer ${TOKEN}`, "content-type": "application/json", ...(init.headers ?? {}) } });
  if (!r.ok) throw new Error(`${init.method ?? "GET"} ${path}: ${r.status} ${await r.text()}`);
  return r.json();
}

/** The institution of the screenshots [SIM]: the citizen's own, registered once. */
async function institution() {
  const mine = await api("/api/v1/orgs/mine");
  if (mine.length) return mine[0].id ?? mine[0].organization?.id ?? mine[0].org?.id;
  const org = await api("/api/v1/orgs", { method: "POST", body: JSON.stringify({
    name: "مصحة النور [SIM]", kind: "health", identifier_type: "rne", identifier: "1234567A", capacity: 120, floors: 4,
    receives_public: true, address: "شارع الحبيب بورقيبة، صفاقس", location: { lat: 34.74, lon: 10.76 },
    manager: { full_name: "سامي بن علي" }, contact_phone: "+21674000000" }) });
  return org.id;
}

async function context(browser, signedIn) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 1, locale: "ar-TN" });
  const now = Math.floor(Date.now() / 1000);
  const user = JSON.stringify({ access_token: TOKEN, token_type: "Bearer", scope: "openid profile email",
    profile: { sub: "atlas-citizen", iss: ISSUER, aud: "ehimaya-portal", exp: 0, iat: 0 }, expires_at: now + 3 * 3600 });
  await ctx.addInitScript(([k, v, on]) => {
    if (on) sessionStorage.setItem(k, v);
    localStorage.setItem("ehimaya.portal.lang", "ar");
    localStorage.setItem("ehimaya.theme", "light");
  }, [`oidc.user:${ISSUER}:ehimaya-portal`, user, signedIn]);
  return ctx;
}

const settle = (page, ms = 1800) => page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {})
  .then(() => page.waitForTimeout(ms));

async function main() {
  const spec = JSON.parse(readFileSync(SPEC, "utf8"));
  const orgId = await institution();
  mkdirSync(join(OUT, "shots"), { recursive: true });
  const browser = await chromium.launch();
  const out = [];
  for (const signedIn of [false, true]) {
    const ctx = await context(browser, signedIn);
    const page = await ctx.newPage();
    let calls = [];
    page.on("request", (r) => {
      const u = new URL(r.url());
      if (u.origin === new URL(API).origin && u.pathname.startsWith("/api/")) calls.push({ verb: r.method(), path: u.pathname });
    });
    for (const s of spec.filter((x) => Boolean(x.signedIn) === signedIn)) {
      const path = s.path.replace(":orgId", orgId);
      try {
        calls = [];
        await page.goto(BASE + path);
        await settle(page);
        // A window: the buttons that open it, clicked in order (their visible text).
        for (const name of s.click || []) {
          await page.getByRole("button", { name, exact: false }).first().click({ timeout: 5000 });
          await settle(page, 700);
        }
        let info = await page.evaluate(regions);
        const win = await page.evaluate(() => {
          const d = [...document.querySelectorAll('dialog[open], [role="dialog"], [aria-modal="true"]')].pop();
          if (!d) return null;
          const r = d.getBoundingClientRect();
          const h = d.querySelector("h1,h2,h3");
          return { kind: "window", label: (h?.textContent || d.textContent || "").trim().slice(0, 90),
                   x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) };
        });
        if (win) info = { ...info, regions: [win, ...info.regions.filter((r) => r.y >= win.y && r.y < win.y + win.h)] };
        if (info.height > 860 && !win) {
          await page.setViewportSize({ width: 1280, height: Math.ceil(info.height) });
          await page.waitForTimeout(500);
          info = { ...(await page.evaluate(regions)), height: Math.ceil(info.height) };
        }
        const file = `shots/${s.id}.jpg`;
        await page.screenshot({ path: join(OUT, file), type: "jpeg", quality: 74, fullPage: !win });
        await page.setViewportSize({ width: 1280, height: 860 });
        const seen = [...new Map(calls.map((c) => [`${c.verb} ${c.path}`, c])).values()]
          .map((c) => ({ ...c, path: c.path.replace(orgId, "{org_id}") }));
        out.push({ ...s, path, shot: file, ...info, api: seen });
        process.stdout.write(`✓ ${s.id} ${path} (${info.regions.length})\n`);
      } catch (e) {
        out.push({ ...s, missing: String(e).slice(0, 120) });
        process.stdout.write(`✗ ${s.id} ${String(e).slice(0, 80)}\n`);
      }
    }
    await ctx.close();
  }
  await browser.close();
  writeFileSync(join(OUT, "capture.json"), JSON.stringify({ screens: out }, null, 1));
}

main();
