/**
 * Live streams (phase 6) in Chromium: real WebRTC, real layout. jsdom has neither, so unit tests replace the player
 * with a stand-in; here the WHEP endpoint is answered by a second RTCPeerConnection in the same page that sends a
 * canvas video, so the dashboard's own WHEP client, <video> playback, detection boxes, alert toast and off-screen
 * pausing all run for real.
 */
import { expect, test, type Page, type Route, type WebSocketRoute } from "@playwright/test";
import type { StaffStream, StaffStreamDetail, StreamDetection, ViewerGrant } from "../src/lib/streamTypes";
import { E2E_ENV } from "../playwright.config";

const API = E2E_ENV.VITE_API_BASE_URL;
// ┏━━ SIMULATION ━━ MediaMTX's WHEP endpoint, answered in the browser (see answerOffer)
// ┃ PRODUCTION: MediaMTX serves WHEP/HLS on its own host (contract phase 6 §3–4), authorising the viewer token
// ┃ through the API's /internal/mediamtx/auth. To run against a real stack, point the API at it and drop mockMedia.
// ┗━━━━━━━━━━━━━━━━
const MEDIA = "http://media.e2e.test";

// Headless Chromium hides host candidates behind mDNS names; the in-page answerer needs plain ones to connect.
test.use({
  launchOptions: {
    args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--disable-features=WebRtcHideLocalIpsWithMdns"],
  },
});

// ┏━━ SIMULATION ━━ signed-in staff session (unsigned JWT: operator, national scope)
// ┃ PRODUCTION: Keycloak (realm ehimaya-staff) issues a signed token after Authorization Code + PKCE and MFA; the
// ┃ API verifies it. To run against a real stack, remove this and sign in through the Keycloak login page first.
// ┗━━━━━━━━━━━━━━━━
async function signIn(page: Page): Promise<void> {
  const b64url = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  const now = Math.floor(Date.now() / 1000);
  const token = `${b64url({ alg: "none", typ: "JWT" })}.${b64url({
    iss: E2E_ENV.VITE_OIDC_ISSUER,
    sub: "e2e-operator",
    name: "Sami Operator",
    exp: now + 3600,
    iat: now,
    realm_access: { roles: ["operator"] },
    scope_level: "national",
  })}.`;
  const key = `oidc.user:${E2E_ENV.VITE_OIDC_ISSUER}:${E2E_ENV.VITE_OIDC_CLIENT_ID}`;
  const user = JSON.stringify({
    access_token: token,
    token_type: "Bearer",
    scope: "openid profile",
    profile: { sub: "e2e-operator", iss: E2E_ENV.VITE_OIDC_ISSUER, aud: E2E_ENV.VITE_OIDC_CLIENT_ID, exp: 0, iat: 0 },
    expires_at: now + 3600,
  });
  await page.addInitScript(
    ([storageKey, value]) => {
      window.sessionStorage.setItem(storageKey, value);
      window.localStorage.setItem("ehimaya.lang", "fr");
    },
    [key, user] as const,
  );
}

function stream(id: string, overrides: Partial<StaffStream> = {}): StaffStream {
  return {
    id,
    report_id: `r-${id}`,
    tracking_code: `EH-26-11-${id.toUpperCase()}`,
    source: "app",
    label: null,
    status: "live",
    started_at: new Date(Date.now() - 60_000).toISOString(),
    ended_at: null,
    duration_s: null,
    gouvernorat_code: 11,
    last_location: { lat: 36.8, lon: 10.18 },
    max_fire_confidence: null,
    max_smoke_confidence: null,
    recordings_count: 0,
    simulated: false,
    ...overrides,
  };
}

interface Mock {
  streams: StaffStream[];
  detections: StreamDetection[];
  viewerRequests: string[];
  whepOffers: { url: string; auth: string | null; type: string | null; body: string }[];
  whepDeletes: string[];
  stops: string[];
  unexpected: string[];
  live: WebSocketRoute | null;
}

/** The answering side of WHEP: a peer connection in the page that sends a moving canvas. */
async function answerOffer(page: Page, offer: string): Promise<string> {
  return page.evaluate(async (sdp) => {
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 360;
    const ctx = canvas.getContext("2d");
    let n = 0;
    const draw = () => {
      if (!ctx) return;
      ctx.fillStyle = n % 2 ? "#7f1d1d" : "#1e3a8a";
      ctx.fillRect(0, 0, 640, 360);
      n += 1;
    };
    draw();
    setInterval(draw, 100);
    const media = canvas.captureStream(10);
    const pc = new RTCPeerConnection();
    (window as unknown as { answerers?: RTCPeerConnection[] }).answerers ??= [];
    (window as unknown as { answerers: RTCPeerConnection[] }).answerers.push(pc);
    for (const track of media.getTracks()) pc.addTrack(track, media);
    await pc.setRemoteDescription({ type: "offer", sdp });
    await pc.setLocalDescription(await pc.createAnswer());
    await new Promise<void>((resolve) => {
      if (pc.iceGatheringState === "complete") resolve();
      pc.addEventListener("icegatheringstatechange", () => {
        if (pc.iceGatheringState === "complete") resolve();
      });
      setTimeout(resolve, 3000);
    });
    return pc.localDescription?.sdp ?? "";
  }, offer);
}

const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Expose-Headers": "Location" };

async function mock(page: Page, streams: StaffStream[]): Promise<Mock> {
  const m: Mock = { streams, detections: [], viewerRequests: [], whepOffers: [], whepDeletes: [], stops: [], unexpected: [], live: null };
  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

  // Nothing leaves the test hosts.
  await page.route(
    (url) => url.hostname !== "localhost" && !url.hostname.endsWith(".e2e.test"),
    (route) => {
      m.unexpected.push(route.request().url());
      return route.abort();
    },
  );
  await page.route(E2E_ENV.VITE_MAP_STYLE_URL, (route) =>
    json(route, { version: 8, sources: {}, layers: [{ id: "background", type: "background", paint: { "background-color": "#e8eef2" } }] }),
  );
  await page.routeWebSocket(`${API.replace("http", "ws")}/api/v1/staff/live`, (ws) => {
    m.live = ws;
    ws.onMessage((raw) => {
      const msg = JSON.parse(String(raw)) as { type?: string };
      if (msg.type === "auth") ws.send(JSON.stringify({ type: "ready" }));
    });
  });

  // ┏━━ SIMULATION ━━ e-Himaya API answered in the browser (contract phase 6 §4)
  // ┃ PRODUCTION: services/api (module streams) serves these; its own tests cover that side.
  // ┗━━━━━━━━━━━━━━━━
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname, searchParams } = new URL(request.url());
    const method = request.method();
    if (method === "GET" && pathname === "/api/v1/geo/gouvernorats") {
      return json(route, [{ code: 11, iso_code: "TN-11", name: "تونس", name_ar: "تونس", name_fr: "Tunis", delegation_count: 21 }]);
    }
    if (method === "GET" && pathname === "/api/v1/staff/levels") return json(route, []);
    if (method === "GET" && pathname === "/api/v1/staff/break-glass") return json(route, { items: [], next_cursor: null });
    if (method === "GET" && pathname === "/api/v1/staff/streams") {
      const status = searchParams.get("status");
      return json(route, { items: m.streams.filter((s) => status !== "live" || s.status === "live"), next_cursor: null });
    }
    const match = /^\/api\/v1\/staff\/streams\/([^/]+)(\/viewer|\/stop)?$/.exec(pathname);
    const found = match ? m.streams.find((s) => s.id === match[1]) : undefined;
    if (match && found) {
      if (method === "GET" && !match[2]) {
        const detail: StaffStreamDetail = {
          ...found,
          recordings: [],
          detections: m.detections,
          track: [{ at: found.started_at ?? "", lat: 36.8, lon: 10.18 }],
        };
        return json(route, detail);
      }
      if (method === "POST" && match[2] === "/viewer") {
        m.viewerRequests.push(found.id);
        const grant: ViewerGrant = {
          whep_url: `${MEDIA}/live/${found.id}/whep`,
          hls_url: null,
          token: `viewer-${found.id}`,
          expires_at: new Date(Date.now() + 5 * 60_000).toISOString(),
        };
        return json(route, grant);
      }
      if (method === "POST" && match[2] === "/stop") {
        m.stops.push(found.id);
        found.status = "ended";
        return json(route, { ...found });
      }
    }
    m.unexpected.push(`${method} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });

  await page.route(`${MEDIA}/**`, async (route) => {
    const request = route.request();
    const method = request.method();
    if (method === "OPTIONS") {
      return route.fulfill({
        status: 204,
        headers: { ...CORS, "Access-Control-Allow-Methods": "POST, DELETE", "Access-Control-Allow-Headers": "Authorization, Content-Type" },
      });
    }
    if (method === "POST" && request.url().endsWith("/whep")) {
      const headers = await request.allHeaders();
      const body = request.postData() ?? "";
      m.whepOffers.push({ url: request.url(), auth: headers.authorization ?? null, type: headers["content-type"] ?? null, body });
      const answer = await answerOffer(page, body);
      return route.fulfill({
        status: 201,
        headers: { ...CORS, "Content-Type": "application/sdp", Location: `${new URL(request.url()).pathname}/session-${m.whepOffers.length}` },
        body: answer,
      });
    }
    if (method === "DELETE") {
      m.whepDeletes.push(request.url());
      return route.fulfill({ status: 200, headers: CORS });
    }
    m.unexpected.push(`${method} ${request.url()}`);
    return route.fulfill({ status: 404, headers: CORS });
  });
  return m;
}

async function isPlaying(page: Page, name: string): Promise<boolean> {
  return page.getByLabel(name).evaluate((v: HTMLVideoElement) => !v.paused && v.readyState >= 2 && v.videoWidth > 0);
}

test.describe("live streams", () => {
  test("plays a stream over WHEP, draws fresh detections, raises the alert and stops the stream", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await signIn(page);
    const api = await mock(page, [stream("s1")]);

    await page.goto("/streams/s1");
    await expect(page.getByRole("heading", { name: "Diffusion EH-26-11-S1", level: 1 })).toBeVisible();
    const video = page.getByLabel("Vidéo en direct : EH-26-11-S1");
    await expect.poll(() => isPlaying(page, "Vidéo en direct : EH-26-11-S1"), { timeout: 20_000 }).toBe(true);
    expect(await video.evaluate((v: HTMLVideoElement) => v.muted)).toBe(true);
    await expect(page.getByText("WebRTC")).toBeVisible();

    expect(api.viewerRequests).toEqual(["s1"]);
    expect(api.whepOffers).toHaveLength(1);
    expect(api.whepOffers[0]).toMatchObject({ url: `${MEDIA}/live/s1/whep`, auth: "Bearer viewer-s1", type: "application/sdp" });
    expect(api.whepOffers[0]?.body).toMatch(/^v=0/);
    expect(api.whepOffers[0]?.body).toContain("a=recvonly");

    // A confirmed fire: the alert arrives on the live feed, the detail (with boxes) is reloaded.
    api.detections = [{ at: new Date().toISOString(), label: "fire", confidence: 0.88, boxes: [[0.25, 0.25, 0.75, 0.75, 0.88]] }];
    api.live?.send(JSON.stringify({ type: "stream.alert", stream_id: "s1", label: "fire", confidence: 0.88, report_id: "r-s1" }));
    const toast = page.getByRole("alert").filter({ hasText: "Feu détecté sur une diffusion en direct" });
    await expect(toast).toBeVisible();
    await expect(toast.getByRole("link", { name: "Ouvrir le signalement" })).toHaveAttribute("href", "/reports/r-s1");

    const box = page.locator("svg.det-overlay rect.det-box--fire");
    await expect(box).toBeVisible();
    const frame = await video.boundingBox();
    const drawn = await box.boundingBox();
    if (!frame || !drawn) throw new Error("no layout");
    // 640×360 frame contained in a 16:9 tile: the box covers the middle half of the picture.
    expect(Math.abs(drawn.width - frame.width / 2)).toBeLessThan(4);
    expect(Math.abs(drawn.height - frame.height / 2)).toBeLessThan(4);
    expect(Math.abs(drawn.x - (frame.x + frame.width / 4))).toBeLessThan(4);
    expect(Math.abs(drawn.y - (frame.y + frame.height / 4))).toBeLessThan(4);

    await toast.getByRole("button", { name: /^Fermer l’alerte/ }).click();
    await expect(toast).toBeHidden();

    await page.getByRole("button", { name: "Activer le son" }).click();
    expect(await video.evaluate((v: HTMLVideoElement) => v.muted)).toBe(false);

    await page.getByRole("button", { name: "Arrêter la diffusion" }).click();
    await page.getByRole("button", { name: "Confirmer l’arrêt" }).click();
    await expect(page.getByText("Diffusion terminée.")).toBeVisible();
    expect(api.stops).toEqual(["s1"]);
    // The viewer left: its WHEP session was deleted.
    await expect.poll(() => api.whepDeletes.length).toBe(1);
    expect(api.whepDeletes[0]).toBe(`${MEDIA}/live/s1/whep/session-1`);

    expect(api.unexpected).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("the wall starts only on-screen tiles and pauses tiles scrolled away", async ({ page }) => {
    // The first row of tiles fits in the window, the second is below the fold.
    await page.setViewportSize({ width: 1280, height: 900 });
    await signIn(page);
    await page.addInitScript(() => window.localStorage.setItem("ehimaya.streamWall", JSON.stringify({ layout: 4, pinned: ["a", "b", "c", "d"] })));
    const api = await mock(page, [stream("a"), stream("b"), stream("c"), stream("d", { simulated: true, source: "sim", label: "Sim Tunis" })]);

    await page.goto("/streams/wall");
    await expect(page.getByRole("heading", { name: "Mur d’écrans", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: /^Écran \d/ })).toHaveCount(4);
    await expect.poll(() => isPlaying(page, "Vidéo en direct : EH-26-11-A"), { timeout: 20_000 }).toBe(true);
    await expect.poll(() => isPlaying(page, "Vidéo en direct : EH-26-11-B"), { timeout: 20_000 }).toBe(true);
    // The second row is below the fold: no viewer token, no WebRTC session yet.
    expect([...api.viewerRequests].sort()).toEqual(["a", "b"]);

    const last = page.getByLabel("Vidéo en direct : Sim Tunis");
    await last.scrollIntoViewIfNeeded();
    await expect.poll(() => isPlaying(page, "Vidéo en direct : Sim Tunis"), { timeout: 20_000 }).toBe(true);
    await expect(page.getByRole("note", { name: "Mode simulation" })).toBeAttached();
    expect(api.viewerRequests).toContain("d");
    // The wall page is shorter than two viewports: a spacer after the app root lets the first row scroll fully away.
    await page.evaluate(() => {
      const spacer = document.createElement("div");
      spacer.style.height = "2000px";
      document.body.append(spacer);
      window.scrollTo(0, document.documentElement.scrollHeight);
    });
    await expect
      .poll(() => page.getByLabel("Vidéo en direct : EH-26-11-A").evaluate((v) => v.getBoundingClientRect().bottom))
      .toBeLessThan(0);
    // The first row is now off screen: paused at once, its sessions released after 10 s.
    await expect
      .poll(() => page.getByLabel("Vidéo en direct : EH-26-11-A").evaluate((v: HTMLVideoElement) => v.paused))
      .toBe(true);
    await expect.poll(() => api.whepDeletes.some((u) => u.includes("/live/a/")), { timeout: 20_000 }).toBe(true);

    // Back on screen: it reconnects and plays again.
    await page.getByLabel("Vidéo en direct : EH-26-11-A").scrollIntoViewIfNeeded();
    await expect.poll(() => isPlaying(page, "Vidéo en direct : EH-26-11-A"), { timeout: 20_000 }).toBe(true);
    expect(api.unexpected).toEqual([]);
  });
});
