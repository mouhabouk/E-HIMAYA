import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { makeGrant } from "../test/streamFixtures";
import { ApiError } from "./api";
import { StreamSession, withToken, type HlsConstructor, type PlayerSnapshot, type StreamSessionOptions } from "./streamSession";
import type { ViewerGrant } from "./streamTypes";

/** RTCPeerConnection stand-in: jsdom has no WebRTC. */
class FakePC extends EventTarget {
  static instances: FakePC[] = [];
  readonly config: RTCConfiguration;
  iceGatheringState: RTCIceGatheringState = "complete";
  connectionState: RTCPeerConnectionState = "new";
  localDescription: RTCSessionDescriptionInit | null = null;
  remoteDescription: RTCSessionDescriptionInit | null = null;
  ontrack: ((e: RTCTrackEvent) => void) | null = null;
  transceivers: [string, string | undefined][] = [];
  closed = false;

  constructor(config: RTCConfiguration) {
    super();
    this.config = config;
    FakePC.instances.push(this);
  }
  addTransceiver(kind: string, init?: RTCRtpTransceiverInit) {
    this.transceivers.push([kind, init?.direction]);
  }
  createOffer() {
    return Promise.resolve({ type: "offer" as const, sdp: "v=0 offer" });
  }
  setLocalDescription(d: RTCSessionDescriptionInit) {
    this.localDescription = d;
    return Promise.resolve();
  }
  setRemoteDescription(d: RTCSessionDescriptionInit) {
    this.remoteDescription = d;
    return Promise.resolve();
  }
  close() {
    this.closed = true;
    this.connectionState = "closed";
  }
  setState(s: RTCPeerConnectionState) {
    this.connectionState = s;
    this.dispatchEvent(new Event("connectionstatechange"));
  }
  static last(): FakePC {
    const pc = FakePC.instances.at(-1);
    if (!pc) throw new Error("no peer connection");
    return pc;
  }
}

class FakeHls {
  static instances: FakeHls[] = [];
  static supported = true;
  static Events = { ERROR: "hlsError" };
  static isSupported() {
    return FakeHls.supported;
  }
  readonly config: Record<string, unknown>;
  source: string | null = null;
  media: HTMLMediaElement | null = null;
  destroyed = false;
  private handlers = new Map<string, (e: string, d: { fatal?: boolean }) => void>();
  constructor(config: Record<string, unknown>) {
    this.config = config;
    FakeHls.instances.push(this);
  }
  loadSource(url: string) {
    this.source = url;
  }
  attachMedia(media: HTMLMediaElement) {
    this.media = media;
  }
  on(event: string, listener: (e: string, d: { fatal?: boolean }) => void) {
    this.handlers.set(event, listener);
  }
  destroy() {
    this.destroyed = true;
  }
  fatal() {
    this.handlers.get(FakeHls.Events.ERROR)?.(FakeHls.Events.ERROR, { fatal: true });
  }
}

type FetchArgs = [RequestInfo | URL, RequestInit | undefined];

function setup(
  overrides: Partial<StreamSessionOptions> = {},
  whep: (init: RequestInit | undefined) => Response = () =>
    new Response("v=0 answer", { status: 201, headers: { Location: "/live/s-1/whep/session-1" } }),
) {
  const video = document.createElement("video");
  video.play = vi.fn(() => Promise.resolve());
  const pause = vi.fn();
  video.pause = pause;
  video.load = vi.fn();
  const states: PlayerSnapshot[] = [];
  const requestGrant = vi.fn((): Promise<ViewerGrant> => Promise.resolve(makeGrant()));
  const fetchImpl = vi.fn((_url: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(init?.method === "DELETE" ? new Response(null, { status: 200 }) : whep(init)),
  );
  const session = new StreamSession({
    video,
    requestGrant,
    onChange: (s) => states.push(s),
    fetch: fetchImpl,
    createPeerConnection: (config) => new FakePC(config) as unknown as RTCPeerConnection,
    loadHls: () => Promise.resolve(FakeHls as unknown as HlsConstructor),
    random: () => 0,
    ...overrides,
  });
  const calls = () => fetchImpl.mock.calls as FetchArgs[];
  const urlOf = (u: RequestInfo | URL | undefined) => (typeof u === "string" ? u : u instanceof URL ? u.href : (u?.url ?? ""));
  return { session, video, pause, states, requestGrant, fetchImpl, calls, urlOf, last: () => states.at(-1) };
}

beforeEach(() => {
  FakePC.instances = [];
  FakeHls.instances = [];
  FakeHls.supported = true;
});

afterEach(() => {
  vi.useRealTimers();
});

describe("StreamSession", () => {
  it("plays over WHEP with the viewer token, then tears the session down", async () => {
    const { session, video, requestGrant, calls, urlOf, last } = setup();
    session.start();
    await vi.waitFor(() => expect(last()).toEqual({ state: "connecting", transport: "whep" }));
    expect(requestGrant).toHaveBeenCalledTimes(1);
    const pc = FakePC.last();
    expect(pc.transceivers).toEqual([
      ["video", "recvonly"],
      ["audio", "recvonly"],
    ]);
    const [url, init] = calls()[0] ?? [];
    expect(urlOf(url)).toBe("https://media.example/live/s-1/whep");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe("v=0 offer");
    expect(init?.headers).toEqual({ "Content-Type": "application/sdp", Authorization: "Bearer viewer-token" });
    expect(pc.remoteDescription).toEqual({ type: "answer", sdp: "v=0 answer" });

    video.dispatchEvent(new Event("playing"));
    expect(last()).toEqual({ state: "playing", transport: "whep" });

    session.stop();
    expect(pc.closed).toBe(true);
    const [delUrl, delInit] = calls()[1] ?? [];
    expect(urlOf(delUrl)).toBe("https://media.example/live/s-1/whep/session-1");
    expect(delInit).toMatchObject({ method: "DELETE", headers: { Authorization: "Bearer viewer-token" } });
    expect(last()?.state).toBe("idle");
  });

  it("falls back to HLS (hls.js, token in a header) when WHEP fails", async () => {
    const { session, last } = setup({}, () => new Response("busy", { status: 500 }));
    session.start();
    await vi.waitFor(() => expect(last()).toEqual({ state: "connecting", transport: "hls" }));
    expect(FakePC.last().closed).toBe(true);
    const hls = FakeHls.instances[0];
    expect(hls?.source).toBe("https://media.example/live/s-1/index.m3u8");
    expect(hls?.config).toMatchObject({ enableWorker: false, lowLatencyMode: true });
    const xhr = { setRequestHeader: vi.fn() };
    (hls?.config.xhrSetup as (x: unknown) => void)(xhr);
    expect(xhr.setRequestHeader).toHaveBeenCalledWith("Authorization", "Bearer viewer-token");
    session.stop();
    expect(hls?.destroyed).toBe(true);
  });

  it("uses native HLS with the token in the query where the browser plays HLS itself", async () => {
    const { session, video, last } = setup({}, () => new Response("", { status: 404 }));
    video.canPlayType = vi.fn(() => "maybe" as const);
    session.start();
    await vi.waitFor(() => expect(last()?.transport).toBe("hls"));
    expect(video.src).toBe("https://media.example/live/s-1/index.m3u8?token=viewer-token");
    expect(FakeHls.instances).toHaveLength(0);
    expect(withToken("https://m/x.m3u8?token=a", "b")).toBe("https://m/x.m3u8?token=a");
  });

  it("reconnects with back-off after a WebRTC failure, reusing a still valid token", async () => {
    vi.useFakeTimers();
    const { session, requestGrant, last } = setup({ baseDelayMs: 1000 });
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(last()?.transport).toBe("whep");
    FakePC.last().setState("failed");
    expect(FakePC.last().closed).toBe(true);
    expect(last()).toEqual({ state: "reconnecting", transport: null });
    await vi.advanceTimersByTimeAsync(500); // equal jitter with random() = 0: half of 1 s
    expect(FakePC.instances).toHaveLength(2);
    expect(last()).toEqual({ state: "connecting", transport: "whep" });
    expect(requestGrant).toHaveBeenCalledTimes(1);

    // A short "disconnected" is tolerated; a long one is a failure.
    FakePC.last().setState("disconnected");
    await vi.advanceTimersByTimeAsync(2000);
    FakePC.last().setState("connected");
    await vi.advanceTimersByTimeAsync(5000);
    expect(FakePC.instances).toHaveLength(2);
    FakePC.last().setState("disconnected");
    await vi.advanceTimersByTimeAsync(5000);
    expect(FakePC.last().closed).toBe(true);
    session.stop();
  });

  it("renews the viewer token before it expires", async () => {
    vi.useFakeTimers();
    const { session, requestGrant } = setup({ renewMarginMs: 60_000 });
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(requestGrant).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(3 * 60_000);
    expect(requestGrant).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(60_000 + 10);
    expect(requestGrant).toHaveBeenCalledTimes(2);
    session.stop();
  });

  it("stops for good when the viewer token is refused (403) or the stream is gone (404)", async () => {
    const forbidden = setup({ requestGrant: () => Promise.reject(new ApiError(403, "forbidden")) });
    forbidden.session.start();
    await vi.waitFor(() => expect(forbidden.last()).toEqual({ state: "forbidden", transport: null }));
    const gone = setup({ requestGrant: () => Promise.reject(new ApiError(404, "not_found")) });
    gone.session.start();
    await vi.waitFor(() => expect(gone.last()?.state).toBe("unavailable"));
    expect(FakePC.instances).toHaveLength(0);
  });

  it("pauses off screen, releases the session after a while and reconnects when back", async () => {
    vi.useFakeTimers();
    const { session, pause, last } = setup({ suspendTeardownMs: 10_000 });
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    const first = FakePC.last();
    session.suspend();
    expect(pause).toHaveBeenCalled();
    expect(last()?.state).toBe("suspended");
    // Back quickly: the same session plays on.
    session.resume();
    expect(first.closed).toBe(false);
    session.suspend();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(first.closed).toBe(true);
    expect(last()).toEqual({ state: "suspended", transport: null });
    session.resume();
    await vi.advanceTimersByTimeAsync(0);
    expect(FakePC.instances).toHaveLength(2);
    expect(last()).toEqual({ state: "connecting", transport: "whep" });
    session.stop();
  });

  it("restarts after a fatal HLS error", async () => {
    vi.useFakeTimers();
    const { session, last } = setup({ maxWhepFailures: 1 }, () => new Response("", { status: 500 }));
    session.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(last()?.transport).toBe("hls");
    FakeHls.instances[0]?.fatal();
    expect(FakeHls.instances[0]?.destroyed).toBe(true);
    expect(last()?.state).toBe("reconnecting");
    await vi.advanceTimersByTimeAsync(1000);
    // After the WHEP failure limit, the session goes straight to HLS.
    expect(FakeHls.instances).toHaveLength(2);
    expect(FakePC.instances).toHaveLength(1);
    session.stop();
  });
});
