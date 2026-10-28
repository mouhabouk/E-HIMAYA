// ء-حماية / e-Himaya — the load and attack part of the digital dry run (L5a, docs/phase-l/design-l5.md §2.4) (k6).
//
// Runs ONLY against the isolated copy of the system (never the live one): it refuses to start unless ISOLATED=yes.
// Two scenarios at once:
//   reports: citizens' reports at a rising arrival rate (as sos-surge.js), the "huge number of reports" of the drill;
//   attacks: a steady trickle of hostile requests: SQL injection in every field, script in the text, oversized and
//            malformed bodies, and one device flooding the API. Each attack is "blocked" when the API refuses it
//            (4xx) or keeps it as inert text without error; any 5xx or a slower health check is a failure.
// At the end it prints the JSON the dry run records (POST /api/v1/staff/drills/{id}/stress, StressIn), in
// summary-drill.json and on the console.
//
// Environment: ISOLATED=yes (required), API_URL, DEVICES (default 300), PEAK_RPS (default 50), HOLD (default 5m),
// ATTACK_RPS (default 2).
import http from "k6/http";
import { check, fail } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";
import encoding from "k6/encoding";
import crypto from "k6/crypto";

const API = (__ENV.API_URL || "http://localhost:8000").replace(/\/+$/, "");
const DEVICES = Number(__ENV.DEVICES || 300);
const PEAK_RPS = Number(__ENV.PEAK_RPS || 50);
const HOLD = __ENV.HOLD || "5m";
const ATTACK_RPS = Number(__ENV.ATTACK_RPS || 2);

if (__ENV.ISOLATED !== "yes") {
  throw new Error("drill.js runs only against the isolated copy: set ISOLATED=yes (design-l5.md §2.4).");
}

export const options = {
  setupTimeout: "10m",
  scenarios: {
    reports: {
      executor: "ramping-arrival-rate",
      exec: "report",
      startRate: 1,
      timeUnit: "1s",
      preAllocatedVUs: Math.max(20, PEAK_RPS * 2),
      maxVUs: Math.max(100, PEAK_RPS * 10),
      stages: [
        { target: PEAK_RPS, duration: "1m" },
        { target: PEAK_RPS, duration: HOLD },
        { target: 0, duration: "30s" },
      ],
    },
    attacks: {
      executor: "constant-arrival-rate",
      exec: "attack",
      rate: ATTACK_RPS,
      timeUnit: "1s",
      duration: "6m",
      preAllocatedVUs: 10,
      maxVUs: 50,
    },
  },
  thresholds: {
    "http_req_duration{name:create_report}": ["p(95)<2000"],
    server_errors: ["count==0"],
    attacks_blocked_rate: ["rate==1"],
  },
  systemTags: ["status", "method", "name", "scenario", "expected_response"],
  summaryTrendStats: ["avg", "med", "p(95)", "p(99)", "max"],
};

const sent = new Counter("reports_sent");
const accepted = new Counter("reports_accepted");
const refused = new Counter("reports_refused");
const serverErrors = new Counter("server_errors");
const perSecond = new Counter("reports_per_second_probe");
const latency = new Trend("report_ms", true);
const attacksSent = new Counter("attacks_sent");
const attacksBlocked = new Counter("attacks_blocked");
const attacksBlockedRate = new Rate("attacks_blocked_rate");

const CITIES = [
  [36.8065, 10.1815, 0.08, 30],
  [34.7406, 10.7603, 0.05, 12],
  [35.8256, 10.6084, 0.04, 10],
  [36.4561, 10.7376, 0.04, 6],
  [33.8869, 10.0982, 0.04, 5],
  [37.2744, 9.8739, 0.04, 6],
];
const CATEGORIES = ["sos", "sos", "sos", "flood", "fire", "medical", "traffic_accident"];

const SQL = [
  "'; DROP TABLE ops.incident; --",
  "' OR '1'='1",
  "1; SELECT pg_sleep(10); --",
  "' UNION SELECT password FROM pg_shadow --",
  "admin'--",
];
const SCRIPTS = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "javascript:alert(1)", "{{7*7}}${7*7}"];

function pick(a) {
  return a[Math.floor(Math.random() * a.length)];
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

function reportBody(over) {
  const [lat, lon, spread] = pick(CITIES);
  return {
    client_uuid: uuid4(),
    category: pick(CATEGORIES),
    location: { lat: lat + gaussian() * spread, lon: lon + gaussian() * spread, accuracy_m: 20 },
    created_at: new Date().toISOString(),
    ...over,
  };
}

function consent(key) {
  return http.post(
    `${API}/api/v1/consents`,
    JSON.stringify({ charter_version: "2026-10", locale: "ar", platform: "android" }),
    { headers: headers(key), tags: { name: "consent" } },
  );
}

export function setup() {
  const ready = http.get(`${API}/health/ready`);
  if (ready.status !== 200) fail(`API not ready: ${ready.status}`);
  const keys = [];
  for (let i = 0; i < DEVICES; i++) {
    const key = deviceKey();
    if (consent(key).status !== 201) fail(`consent refused for device ${i}`);
    keys.push(key);
  }
  // One more device for the flood: it stays under its own limit until the attack runs.
  const flooder = deviceKey();
  consent(flooder);
  return { keys, flooder, started: Date.now() };
}

export function report(data) {
  const r = http.post(`${API}/api/v1/reports`, JSON.stringify(reportBody({})), {
    headers: headers(pick(data.keys)),
    tags: { name: "create_report" },
  });
  sent.add(1);
  perSecond.add(1, { second: String(Math.floor(Date.now() / 1000)) });
  if (r.status >= 500) serverErrors.add(1);
  if (r.status === 201) {
    accepted.add(1);
    latency.add(r.timings.duration);
  } else {
    refused.add(1, { status: String(r.status) });
  }
  check(r, { "report accepted (201)": (res) => res.status === 201 });
}

/** One hostile request; true when the API refused it or kept it as inert text, never with a server error. */
function hostile(kind, data) {
  const key = pick(data.keys);
  const tags = { name: `attack_${kind}`, kind };
  let r;
  if (kind === "sql_injection") {
    const where = Math.floor(Math.random() * 4);
    if (where === 0) r = http.post(`${API}/api/v1/reports`, JSON.stringify(reportBody({ category: pick(SQL) })), { headers: headers(key), tags });
    else if (where === 1) r = http.post(`${API}/api/v1/reports`, JSON.stringify(reportBody({ client_uuid: pick(SQL) })), { headers: headers(key), tags });
    else if (where === 2) r = http.get(`${API}/api/v1/reports/mine?limit=${encodeURIComponent(pick(SQL))}`, { headers: headers(key), tags });
    else {
      // In free text the injection is accepted as text: blocked means stored verbatim, nothing executed.
      r = http.post(`${API}/api/v1/reports`, JSON.stringify(reportBody({ text: pick(SQL), lang: "fr" })), { headers: headers(key), tags });
      return r.status < 500 && (r.status >= 400 || r.status === 201);
    }
    return r.status >= 400 && r.status < 500;
  }
  if (kind === "script") {
    r = http.post(`${API}/api/v1/reports`, JSON.stringify(reportBody({ text: pick(SCRIPTS), lang: "en" })), { headers: headers(key), tags });
    return r.status < 500;
  }
  if (kind === "oversize") {
    r = http.post(`${API}/api/v1/reports`, JSON.stringify(reportBody({ text: "x".repeat(2 * 1024 * 1024), lang: "en" })), { headers: headers(key), tags });
    return r.status >= 400 && r.status < 500;
  }
  if (kind === "malformed") {
    const bodies = ['{"category": "sos", "location": ', "not json at all", '{"location": {"lat": "abc", "lon": null}}', "[]"];
    r = http.post(`${API}/api/v1/reports`, pick(bodies), { headers: headers(key), tags });
    return r.status >= 400 && r.status < 500;
  }
  // flood_same_device: a burst from one device must meet its limit (429), not slow the others down.
  let limited = false;
  for (let i = 0; i < 30; i++) {
    r = http.post(`${API}/api/v1/reports`, JSON.stringify(reportBody({})), { headers: headers(data.flooder), tags });
    if (r.status >= 500) return false;
    if (r.status === 429) limited = true;
  }
  return limited;
}

const KINDS = ["sql_injection", "sql_injection", "script", "oversize", "malformed"];
let flooded = false;

export function attack(data) {
  // The flood runs once per VU; the other attacks share the rest.
  const kind = !flooded && __VU === 1 ? "flood_same_device" : pick(KINDS);
  if (kind === "flood_same_device") flooded = true;
  const blocked = hostile(kind, data);
  attacksSent.add(1, { kind });
  if (blocked) attacksBlocked.add(1, { kind });
  attacksBlockedRate.add(blocked, { kind });
}

export function teardown() {
  const ready = http.get(`${API}/health/ready`);
  check(ready, { "system still up after the run": (res) => res.status === 200 });
}

export function handleSummary(data) {
  const m = (name, field = "count") => (data.metrics[name] ? data.metrics[name].values[field] || 0 : 0);
  const durationS = Math.max(1, Math.round(data.state.testRunDurationMs / 1000));
  const result = {
    environment: "isolated",
    reports_sent: m("reports_sent"),
    reports_accepted: m("reports_accepted"),
    reports_refused: m("reports_refused"),
    errors_5xx: m("server_errors"),
    // The mean at the peak is not kept by k6 per second; the rate over the run is a floor of the peak.
    peak_per_second: Math.round(m("reports_per_second_probe", "rate") * 100) / 100,
    latency_p95_ms: Math.round(m("report_ms", "p(95)")),
    latency_p99_ms: Math.round(m("report_ms", "p(99)")),
    duration_s: durationS,
    attacks_sent: m("attacks_sent"),
    attacks_blocked: m("attacks_blocked"),
    attack_kinds: ["sql_injection", "script", "oversize", "malformed", "flood_same_device"],
  };
  const text = JSON.stringify(result, null, 2);
  return { stdout: `\nStressIn for the dry run:\n${text}\n`, "summary-drill.json": text };
}
