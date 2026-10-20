// ء-حماية / e-Himaya — builds the Content-Security-Policy of a static web app (dashboard, portal) at image build time.
//
// The policy allows exactly what the built app loads: its own files, the inline pre-paint script of index.html
// (by SHA-256 hash, never 'unsafe-inline'), the API (HTTPS + WebSocket), the Keycloak issuer, the tus endpoint,
// the map style and tiles, and the media store for pre-signed links. Origins come from the same VITE_* values the
// bundle was built with, so the policy can never drift from the configuration.
//
//   node csp.mjs <dist dir> <output caddy snippet>
// Environment: VITE_API_BASE_URL, VITE_OIDC_ISSUER, VITE_TUS_ENDPOINT, VITE_MAP_STYLE_URL (all optional),
//   CSP_MEDIA_SRC  space-separated origins of pre-signed media links (S3_PUBLIC_ENDPOINT_URL)
//   CSP_MAP_SRC    space-separated origins of tiles, glyphs and sprites of a custom map style
//   CSP_STREAM_SRC space-separated origins of the live stream viewers (MediaMTX WHEP and HLS, phase 6); the WebRTC
//                  media itself is not governed by the CSP, only the WHEP/HLS HTTP requests are
//   CSP_TELEPHONY_SRC space-separated origins of the SIP-over-WebSocket server of the softphone (phase 7, e.g.
//                  wss://sip.example.tn); the RTP media itself is not governed by the CSP
//   CSP_MICROPHONE  "self" lets the app's own pages use the microphone (dashboard softphone); empty = denied
// The output also carries the Permissions-Policy header (no camera, geolocation, payment or USB in any case).
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const [dist, output] = process.argv.slice(2);
if (!dist || !output) {
  console.error("usage: node csp.mjs <dist dir> <output file>");
  process.exit(2);
}

// The apps' development defaults (src/config.ts), used when a value is not given at build time.
const DEFAULTS = { VITE_API_BASE_URL: "http://localhost:8000" };
// Fallback map style of both apps (src/lib/mapStyle.ts): OpenStreetMap raster tiles.
const OSM_TILES = "https://tile.openstreetmap.org";

function env(name) {
  const value = (process.env[name] ?? "").trim();
  return value || DEFAULTS[name] || "";
}

function origin(url) {
  if (!url) return null;
  try {
    return new URL(url).origin;
  } catch {
    console.error(`csp: ${url} is not an absolute URL`);
    process.exit(1);
  }
}

function list(name) {
  return env(name)
    .split(/\s+/)
    .filter(Boolean)
    .map((value) => origin(value));
}

const api = origin(env("VITE_API_BASE_URL"));
const ws = api.replace(/^http/, "ws");
const issuer = origin(env("VITE_OIDC_ISSUER"));
const tus = origin(env("VITE_TUS_ENDPOINT"));
const styleUrl = env("VITE_MAP_STYLE_URL");
const map = styleUrl ? [origin(styleUrl), ...list("CSP_MAP_SRC")] : [OSM_TILES];
const media = list("CSP_MEDIA_SRC");
const streams = list("CSP_STREAM_SRC");
// SIP WebSocket (ws:/wss:): origin() keeps the scheme.
const telephony = list("CSP_TELEPHONY_SRC");
const microphone = env("CSP_MICROPHONE");
if (microphone && microphone !== "self") {
  console.error(`csp: CSP_MICROPHONE must be empty or "self", not ${microphone}`);
  process.exit(1);
}

// Inline scripts of index.html (the pre-paint language/theme script), allowed by hash.
const html = readFileSync(join(dist, "index.html"), "utf8");
const hashes = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(
  (match) => `'sha256-${createHash("sha256").update(match[1], "utf8").digest("base64")}'`,
);

const unique = (values) => [...new Set(values.filter(Boolean))].join(" ");
const directives = {
  "default-src": "'self'",
  "script-src": unique(["'self'", ...hashes]),
  "style-src": "'self'",
  "img-src": unique(["'self'", "data:", "blob:", ...map, ...media]),
  // blob: = hls.js (MediaSource); stream origins = native HLS playback.
  "media-src": unique(["'self'", "blob:", ...media, ...streams]),
  "font-src": "'self'",
  // Media origins: a stream recording download follows the API's redirect to its pre-signed link (fetch).
  // Stream origins: WHEP offers / session teardown and hls.js playlist and segment requests.
  // Telephony origins: the softphone's SIP WebSocket.
  "connect-src": unique(["'self'", api, ws, issuer, tus, ...map, ...media, ...streams, ...telephony]),
  // MapLibre's worker is a same-origin chunk (src/lib/maplibre.ts).
  "worker-src": "'self'",
  "frame-src": "'none'",
  "frame-ancestors": "'none'",
  "object-src": "'none'",
  "base-uri": "'self'",
  "form-action": unique(["'self'", issuer]),
  "manifest-src": "'self'",
};
let policy = Object.entries(directives)
  .map(([name, value]) => `${name} ${value}`)
  .join("; ");
if (api.startsWith("https:")) policy += "; upgrade-insecure-requests";
if (policy.includes('"')) {
  console.error("csp: refusing a policy with a double quote");
  process.exit(1);
}

const permissions = `camera=(), microphone=(${microphone}), geolocation=(), payment=(), usb=()`;
writeFileSync(
  output,
  `header Content-Security-Policy "${policy}"\nheader Permissions-Policy "${permissions}"\n`,
);
console.log(policy);
console.log(`Permissions-Policy: ${permissions}`);
