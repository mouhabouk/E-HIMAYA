/**
 * Operator softphone (phase 7 §4) in Chromium: the real JsSIP stack registers over a WebSocket answered by the test
 * (a minimal SIP registrar / Asterisk stand-in), and the media is real WebRTC: the "caller" is a second
 * RTCPeerConnection in the page that sends a tone, like the WHEP answerer of the phase 6 stream tests. jsdom has
 * neither, so the unit tests use a fake SIP engine; this checks the JsSIP wiring end to end.
 */
import { expect, test, type Page, type WebSocketRoute } from "@playwright/test";
import type { SipCredentials, StaffCall } from "../src/lib/telephonyTypes";
import { API, baseMock, commonAnswer, json, signIn } from "./phase7Helpers";

// ┏━━ SIMULATION ━━ Asterisk's PJSIP WebSocket (WSS) answered in the browser by FakeSipServer
// ┃ PRODUCTION: services/telephony (Asterisk 22, PJSIP WebRTC endpoints, queue `operators`) serves SIP over WSS
// ┃ at the ws_url the API returns with the credentials. To run against a real stack, point the API at it and drop
// ┃ the SIP mock (the call-sim service of the `sim` profile then places the calls).
// ┗━━━━━━━━━━━━━━━━
const SIP_WS = "ws://sip.e2e.test/ws";
const SIP_DOMAIN = "ehimaya.test";

// Headless Chromium: plain host candidates for the in-page peer, and a fake microphone without a prompt.
test.use({
  launchOptions: {
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
    args: [
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
      "--disable-features=WebRtcHideLocalIpsWithMdns",
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
    ],
  },
  permissions: ["microphone"],
});

interface SipMessage {
  start: string;
  headers: [string, string][];
  body: string;
}

function parse(raw: string): SipMessage {
  const [head = "", ...rest] = raw.split("\r\n\r\n");
  const [start = "", ...lines] = head.split("\r\n");
  const headers = lines.map((l): [string, string] => {
    const i = l.indexOf(":");
    return [l.slice(0, i).trim(), l.slice(i + 1).trim()];
  });
  return { start, headers, body: rest.join("\r\n\r\n") };
}

const header = (m: SipMessage, name: string) => m.headers.find(([k]) => k.toLowerCase() === name.toLowerCase())?.[1] ?? "";
const allHeaders = (m: SipMessage, name: string) => m.headers.filter(([k]) => k.toLowerCase() === name.toLowerCase()).map(([, v]) => v);
const method = (m: SipMessage) => (m.start.startsWith("SIP/2.0") ? null : (m.start.split(" ")[0] ?? null));
const status = (m: SipMessage) => (m.start.startsWith("SIP/2.0") ? Number(m.start.split(" ")[1]) : null);

function build(start: string, headers: [string, string][], body = ""): string {
  const lines = [start, ...headers.map(([k, v]) => `${k}: ${v}`), `Content-Length: ${Buffer.byteLength(body, "utf8")}`];
  return `${lines.join("\r\n")}\r\n\r\n${body}`;
}

/** The in-page caller: a peer connection that sends a tone (an oscillator) and answers re-INVITEs. */
async function callerOffer(page: Page): Promise<string> {
  return page.evaluate(async () => {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const dest = ctx.createMediaStreamDestination();
    osc.connect(dest);
    osc.start();
    const pc = new RTCPeerConnection();
    (window as unknown as { caller: RTCPeerConnection }).caller = pc;
    for (const track of dest.stream.getAudioTracks()) pc.addTrack(track, dest.stream);
    await pc.setLocalDescription(await pc.createOffer());
    await new Promise<void>((resolve) => {
      if (pc.iceGatheringState === "complete") resolve();
      pc.addEventListener("icegatheringstatechange", () => {
        if (pc.iceGatheringState === "complete") resolve();
      });
      setTimeout(resolve, 3000);
    });
    return pc.localDescription?.sdp ?? "";
  });
}

async function callerAccept(page: Page, sdp: string): Promise<void> {
  await page.evaluate(async (answer) => {
    await (window as unknown as { caller: RTCPeerConnection }).caller.setRemoteDescription({ type: "answer", sdp: answer });
  }, sdp);
}

async function callerAnswerReinvite(page: Page, sdp: string): Promise<string> {
  return page.evaluate(async (offer) => {
    const pc = (window as unknown as { caller: RTCPeerConnection }).caller;
    await pc.setRemoteDescription({ type: "offer", sdp: offer });
    await pc.setLocalDescription(await pc.createAnswer());
    return pc.localDescription?.sdp ?? "";
  }, sdp);
}

/** A peer that answers an INVITE from the softphone (the conference bridge). */
async function bridgeAnswer(page: Page, offer: string): Promise<string> {
  return page.evaluate(async (sdp) => {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const dest = ctx.createMediaStreamDestination();
    osc.connect(dest);
    osc.start();
    const pc = new RTCPeerConnection();
    (window as unknown as { caller: RTCPeerConnection }).caller = pc;
    for (const track of dest.stream.getAudioTracks()) pc.addTrack(track, dest.stream);
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

class FakeSipServer {
  ws: WebSocketRoute | null = null;
  received: SipMessage[] = [];
  registrations: { authorization: string; contact: string; expires: string }[] = [];
  private seq = 1;
  private readonly page: Page;
  /** Last INVITE we sent and the dialog's To (with the softphone's tag). */
  invite: SipMessage | null = null;
  reinvites = 0;
  byes = 0;
  /** Outgoing INVITEs of the softphone (conference join). */
  outgoing: SipMessage[] = [];

  constructor(page: Page) {
    this.page = page;
  }

  async install(): Promise<void> {
    await this.page.routeWebSocket(SIP_WS, (ws) => {
      this.ws = ws;
      ws.onMessage((raw) => void this.onMessage(String(raw)));
    });
  }

  private send(text: string): void {
    this.ws?.send(text);
  }

  /** Echo the dialog headers of a request in a response. */
  private respond(req: SipMessage, code: number, reason: string, extra: [string, string][] = [], body = ""): void {
    const to = header(req, "To");
    const headers: [string, string][] = [
      ...allHeaders(req, "Via").map((v): [string, string] => ["Via", v]),
      ["From", header(req, "From")],
      ["To", to.includes(";tag=") ? to : `${to};tag=srv${this.seq++}`],
      ["Call-ID", header(req, "Call-ID")],
      ["CSeq", header(req, "CSeq")],
      ...extra,
    ];
    this.send(build(`SIP/2.0 ${code} ${reason}`, headers, body));
  }

  private async onMessage(raw: string): Promise<void> {
    const m = parse(raw);
    this.received.push(m);
    switch (method(m)) {
      case "REGISTER":
        this.registrations.push({
          authorization: header(m, "Authorization"),
          contact: header(m, "Contact"),
          expires: header(m, "Expires"),
        });
        this.respond(m, 200, "OK", [["Contact", `${header(m, "Contact")};expires=600`]]);
        return;
      case "INVITE": {
        if (header(m, "To").includes(";tag=")) {
          // re-INVITE (hold / resume): answered by the caller's peer connection.
          this.reinvites += 1;
          const sdp = await callerAnswerReinvite(this.page, m.body);
          this.respond(m, 200, "OK", [["Contact", `<sip:8000@${SIP_DOMAIN};transport=ws>`], ["Content-Type", "application/sdp"]], sdp);
          return;
        }
        // A new call from the softphone (conference join).
        this.outgoing.push(m);
        this.respond(m, 100, "Trying");
        const sdp = await bridgeAnswer(this.page, m.body);
        this.respond(m, 200, "OK", [["Contact", `<sip:conf@${SIP_DOMAIN};transport=ws>`], ["Content-Type", "application/sdp"]], sdp);
        return;
      }
      case "BYE":
        this.byes += 1;
        this.respond(m, 200, "OK");
        return;
      case "ACK":
        return;
      case null:
        await this.onResponse(m);
        return;
      default:
        this.respond(m, 200, "OK");
    }
  }

  private async onResponse(m: SipMessage): Promise<void> {
    if (!this.invite || header(m, "Call-ID") !== header(this.invite, "Call-ID")) return;
    if (status(m) === 200 && header(m, "CSeq").endsWith("INVITE")) {
      await callerAccept(this.page, m.body);
      const contact = /<([^>]+)>/.exec(header(m, "Contact"))?.[1] ?? `sip:op-1@${SIP_DOMAIN}`;
      this.send(
        build(`ACK ${contact} SIP/2.0`, [
          ["Via", `SIP/2.0/WS 192.0.2.1:8088;branch=z9hG4bKack${this.seq++}`],
          ["Max-Forwards", "70"],
          ["From", header(this.invite, "From")],
          ["To", header(m, "To")],
          ["Call-ID", header(m, "Call-ID")],
          ["CSeq", "1 ACK"],
        ]),
      );
    }
  }

  /** Ring the softphone like the `operators` queue does (Asterisk adds the API call id). */
  async ring(callId: string, from = "+21698000042"): Promise<void> {
    const sdp = await callerOffer(this.page);
    const msg = build(
      `INVITE sip:op-1@${SIP_DOMAIN};transport=ws SIP/2.0`,
      [
        ["Via", `SIP/2.0/WS 192.0.2.1:8088;branch=z9hG4bKinv${this.seq++}`],
        ["Max-Forwards", "70"],
        ["From", `"${from}" <sip:${from}@${SIP_DOMAIN}>;tag=caller${this.seq++}`],
        ["To", `<sip:op-1@${SIP_DOMAIN}>`],
        ["Call-ID", `call-${callId}-${this.seq++}`],
        ["CSeq", "1 INVITE"],
        ["Contact", `<sip:8000@192.0.2.1:8088;transport=ws>`],
        ["X-EHimaya-Call-Id", callId],
        ["Content-Type", "application/sdp"],
      ],
      sdp,
    );
    this.invite = parse(msg);
    this.send(msg);
  }

  responsesTo(cseqMethod: string): number[] {
    return this.received.filter((m) => status(m) !== null && header(m, "CSeq").endsWith(cseqMethod)).map((m) => status(m) ?? 0);
  }
}

function credentials(overrides: Partial<SipCredentials> = {}): SipCredentials {
  return {
    ws_url: SIP_WS,
    sip_uri: `sip:op-1@${SIP_DOMAIN}`,
    username: "op-1",
    password: "pw-1",
    expires_at: new Date(Date.now() + 10 * 60_000).toISOString(),
    ice_servers: [],
    simulated: true,
    ...overrides,
  };
}

function callRow(overrides: Partial<StaffCall> = {}): StaffCall {
  return {
    id: "call-7",
    direction: "inbound",
    caller_number: "+216 ** *** *42",
    started_at: new Date(Date.now() - 20_000).toISOString(),
    answered_at: null,
    ended_at: null,
    operator_user_id: null,
    queue: "operators",
    status: "ringing",
    report_id: null,
    incident_id: null,
    tracking_code: null,
    recording_media_id: null,
    transferred_to: null,
    end_reason: null,
    simulated: true,
    ...overrides,
  };
}

async function mockApi(page: Page, creds: SipCredentials) {
  const base = await baseMock(page);
  // Same object as `base`: its `live` socket is set later, when the page connects.
  const m = Object.assign(base, { credentials: 0, links: [] as unknown[], transfers: [] as string[], conferences: [] as string[] });
  // ┏━━ SIMULATION ━━ e-Himaya API answered in the browser (contract phase 7 §4)
  // ┃ PRODUCTION: services/api (module telephony) issues the credentials and drives Asterisk over ARI.
  // ┗━━━━━━━━━━━━━━━━
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const verb = request.method();
    const common = commonAnswer(verb, pathname, route);
    if (common) return common;
    if (verb === "POST" && pathname === "/api/v1/staff/telephony/credentials") {
      m.credentials += 1;
      return json(route, creds);
    }
    if (verb === "POST" && pathname === "/api/v1/staff/calls/call-7/link") {
      m.links.push(request.postDataJSON());
      return json(route, callRow({ report_id: "r-1", tracking_code: "EH-26-11-0000042", status: "answered" }));
    }
    if (verb === "POST" && pathname === "/api/v1/staff/calls/call-7/transfer-198") {
      m.transfers.push("call-7");
      return json(route, callRow({ status: "transferred", transferred_to: "198" }));
    }
    if (verb === "GET" && pathname === "/api/v1/staff/reports") return json(route, { items: [], next_cursor: null });
    // Incident page (conference).
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1") {
      return json(route, {
        id: "i-1",
        category: "fire",
        status: "open",
        gouvernorat_code: 11,
        centroid: { lat: 36.8, lon: 10.18 },
        severity: 80,
        report_count: 0,
        reporter_count: 0,
        opened_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        closed_at: null,
        merged_into: null,
        reports: [],
        timeline: [],
        assignments: [],
        callouts: [],
      });
    }
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1/recommendations") {
      return json(route, { generated_at: new Date().toISOString(), items: [] });
    }
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1/responders") return json(route, { items: [] });
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1/volunteer-suggestions") return json(route, []);
    if (verb === "GET" && pathname === "/api/v1/staff/incidents/i-1/conference") return json(route, []);
    if (verb === "POST" && pathname === "/api/v1/staff/incidents/i-1/conference") {
      m.conferences.push("crisis-i-1");
      return json(route, { room: "crisis-i-1", join_uri: `sip:crisis-i-1@${SIP_DOMAIN}` });
    }
    if (verb === "GET" && pathname === "/api/v1/staff/resources") return json(route, { items: [], next_cursor: null });
    if (verb === "GET" && pathname === "/api/v1/staff/incidents") return json(route, { items: [], next_cursor: null });
    m.unexpected.push(`${verb} ${pathname}`);
    return json(route, { detail: "not_found" }, 404);
  });
  return m;
}

async function switchOn(page: Page) {
  const dock = page.getByRole("complementary", { name: "Téléphone" });
  await dock.getByRole("button", { name: /^Téléphone/ }).click();
  await dock.getByRole("button", { name: "Activer le téléphone" }).click();
  await expect(dock.getByRole("button", { name: /^Téléphone/ })).toContainText("disponible", { timeout: 15_000 });
  return dock;
}

const remoteAudioLive = (page: Page) =>
  page.getByLabel("Son de l’appel").evaluate((el: HTMLAudioElement) => {
    const stream = el.srcObject as MediaStream | null;
    return Boolean(stream && stream.getAudioTracks().some((t) => t.readyState === "live"));
  });

const callerConnected = (page: Page) =>
  page.evaluate(() => (window as unknown as { caller?: RTCPeerConnection }).caller?.connectionState ?? "none");

test.describe("softphone", () => {
  test("registers, rings with queue info, answers with real audio, holds, links and hangs up (scenario 1)", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await signIn(page, ["operator"]);
    const sip = new FakeSipServer(page);
    await sip.install();
    const api = await mockApi(page, credentials());

    await page.goto("/map");
    const dock = await switchOn(page);
    expect(api.credentials).toBe(1);
    expect(sip.registrations.length).toBeGreaterThan(0);
    expect(sip.registrations[0]?.contact).toContain("sip:");
    await expect(dock.getByText("[SIM]")).toBeVisible();

    // The queue rings this operator; the live feed carries the queue state.
    await expect.poll(() => api.live !== null).toBe(true);
    api.live?.send(JSON.stringify({ type: "call.ringing", call: callRow(), queue: { name: "operators", waiting: 2 } }));
    await sip.ring("call-7");
    const incoming = dock.getByRole("alert", { name: "Appel entrant" });
    await expect(incoming).toBeVisible();
    await expect(incoming.getByText("+216 ** *** *42")).toBeVisible();
    await expect(incoming.getByText("operators")).toBeVisible();
    await expect.poll(() => sip.responsesTo("INVITE")).toContain(180);

    await incoming.getByRole("button", { name: "Répondre" }).click();
    const active = dock.getByRole("region", { name: "Appel en cours" });
    await expect(active).toBeVisible();
    await expect.poll(() => sip.responsesTo("INVITE")).toContain(200);
    await expect.poll(() => callerConnected(page), { timeout: 20_000 }).toBe("connected");
    await expect.poll(() => remoteAudioLive(page), { timeout: 20_000 }).toBe(true);

    // Hold → a re-INVITE answered by the caller's peer connection; resume → another one.
    await active.getByRole("button", { name: "Mettre en attente" }).click();
    await expect.poll(() => sip.reinvites).toBe(1);
    await expect(active.getByRole("button", { name: "Reprendre" })).toHaveAttribute("aria-pressed", "true");
    await active.getByRole("button", { name: "Reprendre" }).click();
    await expect.poll(() => sip.reinvites).toBe(2);
    await active.getByRole("button", { name: "Couper le micro" }).click();
    await expect(active.getByRole("button", { name: "Rétablir le micro" })).toHaveAttribute("aria-pressed", "true");

    // Scenario 1: no transfer button, the 198 instruction.
    await expect(active.getByRole("button", { name: "Transférer au 198" })).toHaveCount(0);
    await expect(active.getByText(/appelez le 198 depuis votre propre téléphone/)).toBeVisible();
    await expect(active.getByText("198", { exact: true })).toBeVisible();

    // Link to a report by tracking code.
    await active.getByLabel("Valeur").fill("eh-26-11-0000042");
    await active.getByRole("button", { name: "Lier" }).click();
    await expect(active.getByRole("link", { name: "EH-26-11-0000042" })).toHaveAttribute("href", "/reports/r-1");
    expect(api.links).toEqual([{ tracking_code: "EH-26-11-0000042" }]);

    await active.getByRole("button", { name: "Raccrocher" }).click();
    // The softphone sent the BYE (our server answered it).
    await expect.poll(() => sip.byes).toBe(1);
    await expect(dock.getByRole("region", { name: "Appel terminé" })).toBeVisible();

    expect(api.unexpected).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("scenario 2: transfer to 198 only when the API enables it", async ({ page }) => {
    await signIn(page, ["operator"]);
    const sip = new FakeSipServer(page);
    await sip.install();
    const api = await mockApi(page, credentials({ transfer_198_enabled: true }));
    await page.goto("/map");
    const dock = await switchOn(page);
    await sip.ring("call-7");
    await dock.getByRole("button", { name: "Répondre" }).click();
    const active = dock.getByRole("region", { name: "Appel en cours" });
    await expect(active.getByText(/appelez le 198/)).toHaveCount(0);
    await active.getByRole("button", { name: "Transférer au 198" }).click();
    await active.getByRole("button", { name: "Confirmer le transfert" }).click();
    await expect(active.getByText("Appel transféré au 198.")).toBeVisible();
    expect(api.transfers).toEqual(["call-7"]);
  });

  test("joins the incident's crisis conference from the softphone", async ({ page }) => {
    await signIn(page, ["operator"]);
    const sip = new FakeSipServer(page);
    await sip.install();
    const api = await mockApi(page, credentials());
    await page.goto("/incidents/i-1");
    const panel = page.getByRole("region", { name: "Conférence de crise" });
    await panel.getByRole("button", { name: "Ouvrir une conférence" }).click();
    await expect(panel.getByText("Conférence rejointe.")).toBeVisible({ timeout: 20_000 });
    expect(api.conferences).toEqual(["crisis-i-1"]);
    await expect.poll(() => sip.outgoing.length).toBe(1);
    expect(sip.outgoing[0]?.start).toBe(`INVITE sip:crisis-i-1@${SIP_DOMAIN} SIP/2.0`);
    const dock = page.getByRole("complementary", { name: "Téléphone" });
    await expect(dock.getByRole("region", { name: "Conférence crisis-i-1" })).toBeVisible();
    await expect.poll(() => callerConnected(page), { timeout: 20_000 }).toBe("connected");
    await dock.getByRole("button", { name: "Raccrocher" }).click();
    await expect.poll(() => sip.byes).toBe(1);
    expect(api.unexpected).toEqual([]);
  });
});
