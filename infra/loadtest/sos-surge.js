// ء-حماية / e-Himaya — load test: a surge of SOS reports from anonymous phones (k6, infra/loadtest/README.md).
//
// Scenario: a major incident (earthquake, flash flood) makes many people press SOS within minutes. A pool of
// anonymous device identities (X-Device-Key, as the app sends it) accept the charter, then send reports at a rising
// arrival rate; 3 % of sends are retries of an already received client_uuid (flaky mobile network), and the app polls
// "my reports" after sending. Payloads match what apps/mobile sends (POST /api/v1/reports, contract phase 2).
//
// Pass/fail (thresholds): p95 of report creation < 2 s, failed requests < 1 %, checks > 99 %.
// Environment: API_URL (default http://localhost:8000), DEVICES (pool size, default 200), PEAK_RPS (default 20),
// HOLD (duration at peak, default 2m). Each device stays under the API's per-account limit (20 reports / 10 min):
// keep DEVICES >= PEAK_RPS × hold seconds / 20 for the run not to be throttled per device.
import http from "k6/http";
import { check, fail } from "k6";
import { Counter, Trend } from "k6/metrics";
import encoding from "k6/encoding";
import crypto from "k6/crypto";

const API = (__ENV.API_URL || "http://localhost:8000").replace(/\/+$/, "");
const DEVICES = Number(__ENV.DEVICES || 200);
const PEAK_RPS = Number(__ENV.PEAK_RPS || 20);
const HOLD = __ENV.HOLD || "2m";

export const options = {
  setupTimeout: "5m",
  scenarios: {
    sos_surge: {
      executor: "ramping-arrival-rate",
      startRate: 1,
      timeUnit: "1s",
      preAllocatedVUs: Math.max(20, PEAK_RPS * 2),
      maxVUs: Math.max(100, PEAK_RPS * 10),
      stages: [
        { target: PEAK_RPS, duration: "30s" }, // the news spreads
        { target: PEAK_RPS, duration: HOLD }, // peak
        { target: 0, duration: "30s" },
      ],
    },
  },
  thresholds: {
    "http_req_duration{name:create_report}": ["p(95)<2000", "p(99)<4000"],
    "http_req_duration{name:my_reports}": ["p(95)<1000"],
    http_req_failed: ["rate<0.01"],
    checks: ["rate>0.99"],
  },
  // Keep the refused-by-status breakdown in the summary.
  systemTags: ["status", "method", "name", "scenario", "expected_response"],
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

const reportsCreated = new Counter("reports_created");
const reportsReplayed = new Counter("reports_replayed");
const reportsFlagged = new Counter("reports_flagged");
const ingestLatency = new Trend("report_ingest_ms", true);
// Refused reports by HTTP status (429 = a device went over the per-account limit: raise DEVICES).
const reportsRefused = new Counter("reports_refused");

// Population centres the reports cluster around (lat, lon, spread in degrees), weighted by population.
const CITIES = [
  [36.8065, 10.1815, 0.08, 30], // Tunis
  [34.7406, 10.7603, 0.05, 12], // Sfax
  [35.8256, 10.6084, 0.04, 10], // Sousse
  [36.4561, 10.7376, 0.04, 6], // Nabeul
  [33.8869, 10.0982, 0.04, 5], // Gabès
  [35.6781, 10.0963, 0.05, 6], // Kairouan
  [37.2744, 9.8739, 0.04, 6], // Bizerte
  [36.1742, 8.7049, 0.05, 4], // Kasserine region
];
const CATEGORIES = [
  ["sos", 70],
  ["flood", 8],
  ["fire", 6],
  ["medical", 6],
  ["traffic_accident", 4],
  ["landslide", 3],
  ["other", 3],
];
const TEXTS = [
  ["ar", "نحتاج مساعدة عاجلة، المياه دخلت المنزل"],
  ["ar", "عائلة محاصرة في الطابق الثاني"],
  ["fr", "Personnes bloquées sur le toit, besoin d'aide"],
  ["fr", "Blessé grave, la route est coupée"],
  ["en", "Elderly person trapped, water rising"],
  [null, null], // SOS button only, no text
  [null, null],
];

function weighted(items) {
  const total = items.reduce((sum, item) => sum + item[item.length - 1], 0);
  let r = Math.random() * total;
  for (const item of items) {
    r -= item[item.length - 1];
    if (r <= 0) return item;
  }
  return items[items.length - 1];
}

function gaussian() {
  return Math.sqrt(-2 * Math.log(1 - Math.random())) * Math.cos(2 * Math.PI * Math.random());
}

function deviceKey() {
  return encoding.b64encode(crypto.randomBytes(32), "rawurl");
}

function uuid4() {
  const b = new Uint8Array(crypto.randomBytes(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

function headers(key) {
  return { "Content-Type": "application/json", "X-Device-Key": key, "Accept-Language": "ar" };
}

export function setup() {
  const live = http.get(`${API}/health/ready`);
  if (live.status !== 200) fail(`API not ready: ${live.status} ${live.body}`);
  const keys = [];
  for (let i = 0; i < DEVICES; i++) {
    const key = deviceKey();
    const r = http.post(
      `${API}/api/v1/consents`,
      JSON.stringify({ charter_version: "2026-10", locale: "ar", platform: i % 5 === 0 ? "ios" : "android" }),
      { headers: headers(key), tags: { name: "consent" } },
    );
    if (r.status !== 201) fail(`consent refused for device ${i}: ${r.status} ${r.body}`);
    keys.push(key);
  }
  return { keys };
}

export default function (data) {
  const key = data.keys[Math.floor(Math.random() * data.keys.length)];
  const [lat, lon, spread] = weighted(CITIES);
  const [category] = weighted(CATEGORIES);
  const [lang, text] = TEXTS[Math.floor(Math.random() * TEXTS.length)];
  const body = {
    client_uuid: uuid4(),
    category,
    location: {
      lat: lat + gaussian() * spread,
      lon: lon + gaussian() * spread,
      accuracy_m: Math.round(5 + Math.random() * 60),
    },
    created_at: new Date(Date.now() - Math.floor(Math.random() * 20000)).toISOString(),
  };
  if (text) {
    body.text = text;
    body.lang = lang;
  }
  const payload = JSON.stringify(body);
  const params = { headers: headers(key), tags: { name: "create_report" } };
  const r = http.post(`${API}/api/v1/reports`, payload, params);
  const ok = check(r, {
    "report accepted (201)": (res) => res.status === 201,
    "tracking code assigned": (res) => res.status !== 201 || /^EH-\d{2}-\d{2}-\d{7}$/.test(res.json("tracking_code")),
  });
  if (!ok) {
    reportsRefused.add(1, { status: String(r.status) });
    return;
  }
  reportsCreated.add(1);
  ingestLatency.add(r.timings.duration);
  if (r.json("needs_verification")) reportsFlagged.add(1);

  // Flaky network: the app did not get the answer and sends the same report again.
  if (Math.random() < 0.03) {
    const replay = http.post(`${API}/api/v1/reports`, payload, { ...params, tags: { name: "replay_report" } });
    check(replay, { "replay is idempotent (200, same code)": (res) => res.status === 200 && res.json("id") === r.json("id") });
    reportsReplayed.add(1);
  }
  // The app refreshes "my reports" once the report is sent.
  if (Math.random() < 0.5) {
    const mine = http.get(`${API}/api/v1/reports/mine?limit=20`, { headers: headers(key), tags: { name: "my_reports" } });
    check(mine, { "my reports listed": (res) => res.status === 200 });
  }
}
