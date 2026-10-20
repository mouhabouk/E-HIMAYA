/**
 * One viewer of a live stream (phase 6 §4) attached to a <video>: obtains and renews the viewer token, plays over
 * WHEP (native RTCPeerConnection) and falls back to HLS, reconnects with back-off after a failure, and releases the
 * network session while the tile is off screen.
 *
 *   start() → token → WHEP ──fail──► HLS (hls.js, loaded on demand; native HLS where the browser has it)
 *                       │                │
 *                       └──── failure ───┴──► back-off (equal jitter, 1 s … 30 s) → token (renewed if needed) → …
 *   suspend() pauses at once and closes the session after `suspendTeardownMs`; resume() plays or reconnects.
 */
import { isApiError } from "./api";
import { backoffDelay } from "./live";
import type { ViewerGrant } from "./streamTypes";
import { startWhep, webRtcSupported, WhepError, type WhepConnection, type WhepDeps } from "./whep";

export type PlayerState =
  | "idle"
  | "connecting"
  | "playing"
  | "reconnecting"
  | "suspended"
  /** The API refused the viewer token (403): not retried. */
  | "forbidden"
  /** The stream does not exist or is no longer live (404/409/410): not retried. */
  | "unavailable";

export type Transport = "whep" | "hls";

export interface PlayerSnapshot {
  state: PlayerState;
  transport: Transport | null;
}

/** The part of hls.js the session uses (so tests can inject a fake). */
export interface HlsInstance {
  loadSource(url: string): void;
  attachMedia(media: HTMLMediaElement): void;
  on(event: string, listener: (event: string, data: { fatal?: boolean }) => void): void;
  destroy(): void;
}

export interface HlsConstructor {
  new (config: Record<string, unknown>): HlsInstance;
  isSupported(): boolean;
  Events: { ERROR: string };
}

export interface StreamSessionOptions {
  video: HTMLVideoElement;
  requestGrant: () => Promise<ViewerGrant>;
  onChange: (snapshot: PlayerSnapshot) => void;
  fetch?: typeof fetch;
  createPeerConnection?: WhepDeps["createPeerConnection"];
  /** hls.js light build, loaded on first use only. */
  loadHls?: () => Promise<HlsConstructor>;
  now?: () => number;
  random?: () => number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  /** Renew the token this long before it expires. */
  renewMarginMs?: number;
  /** Off-screen time after which the network session is closed. */
  suspendTeardownMs?: number;
  /** A WebRTC "disconnected" state that lasts longer than this is treated as a failure. */
  disconnectGraceMs?: number;
  /** Consecutive WHEP failures after which the session sticks to HLS (when the stream has an HLS URL). */
  maxWhepFailures?: number;
}

const HLS_MIME = "application/vnd.apple.mpegurl";

export const defaultLoadHls = (): Promise<HlsConstructor> =>
  // The light build (no subtitles, alternate audio or DRM) is enough for MediaMTX's low-latency HLS.
  import("hls.js/light").then((m) => m.default as unknown as HlsConstructor);

/** Native HLS (Safari) cannot send headers: the token goes in the query, as MediaMTX also accepts it there. */
export function withToken(url: string, token: string): string {
  const u = new URL(url);
  if (!u.searchParams.has("token")) u.searchParams.set("token", token);
  return u.toString();
}

function play(video: HTMLVideoElement): void {
  try {
    const p = video.play() as Promise<void> | undefined;
    // Muted autoplay is allowed; a refusal (tab in background) is retried on the next resume.
    p?.catch(() => undefined);
  } catch {
    /* not supported (tests) */
  }
}

export class StreamSession {
  private readonly o: Required<Omit<StreamSessionOptions, "createPeerConnection">> &
    Pick<StreamSessionOptions, "createPeerConnection">;
  private grant: ViewerGrant | null = null;
  private running = false;
  private suspended = false;
  private generation = 0;
  private attempt = 0;
  private whepFailures = 0;
  private whep: WhepConnection | null = null;
  private hls: HlsInstance | null = null;
  private nativeHls = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private renewTimer: ReturnType<typeof setTimeout> | null = null;
  private suspendTimer: ReturnType<typeof setTimeout> | null = null;
  private disconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private snapshot: PlayerSnapshot = { state: "idle", transport: null };

  constructor(options: StreamSessionOptions) {
    this.o = {
      fetch: (...args) => globalThis.fetch(...args),
      loadHls: defaultLoadHls,
      now: Date.now,
      random: Math.random,
      baseDelayMs: 1000,
      maxDelayMs: 30_000,
      renewMarginMs: 60_000,
      suspendTeardownMs: 10_000,
      disconnectGraceMs: 5000,
      maxWhepFailures: 2,
      ...options,
    };
  }

  get state(): PlayerSnapshot {
    return this.snapshot;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.attempt = 0;
    const { video } = this.o;
    video.addEventListener("playing", this.onPlaying);
    video.addEventListener("error", this.onMediaError);
    void this.connect();
  }

  stop(): void {
    this.running = false;
    this.generation += 1;
    this.clearTimer("reconnectTimer");
    this.clearTimer("renewTimer");
    this.clearTimer("suspendTimer");
    this.teardown();
    const { video } = this.o;
    video.removeEventListener("playing", this.onPlaying);
    video.removeEventListener("error", this.onMediaError);
    this.set("idle", null);
  }

  /** Off screen or tab hidden: pause now, release the session if it lasts. */
  suspend(): void {
    if (!this.running || this.suspended) return;
    this.suspended = true;
    this.clearTimer("reconnectTimer");
    try {
      this.o.video.pause();
    } catch {
      /* not supported (tests) */
    }
    this.set("suspended", this.snapshot.transport);
    this.suspendTimer = setTimeout(() => {
      this.suspendTimer = null;
      this.generation += 1;
      this.clearTimer("renewTimer");
      this.teardown();
      this.set("suspended", null);
    }, this.o.suspendTeardownMs);
  }

  resume(): void {
    if (!this.running || !this.suspended) return;
    this.suspended = false;
    this.clearTimer("suspendTimer");
    if (this.whep || this.hls || this.nativeHls) {
      this.set("connecting", this.snapshot.transport);
      play(this.o.video);
      return;
    }
    this.attempt = 0;
    void this.connect();
  }

  /** Retry at once (a "retry" button, or the browser coming back online). */
  retryNow(): void {
    if (!this.running && this.snapshot.state === "unavailable") {
      // The stream was not available (yet): try again on request.
      this.running = true;
    }
    if (!this.running || this.suspended) return;
    this.clearTimer("reconnectTimer");
    this.attempt = 0;
    this.teardown();
    void this.connect();
  }

  // ---------- internals ----------

  private readonly onPlaying = () => {
    if (!this.running || this.suspended) return;
    this.attempt = 0;
    this.set("playing", this.snapshot.transport);
  };

  private readonly onMediaError = () => {
    // The element's own error (native HLS, or a decode failure): start over.
    if (this.nativeHls || this.whep) this.fail();
  };

  private set(next: PlayerState, transport: Transport | null): void {
    // A connection finishing while the tile is off screen does not show as "connecting".
    const state = this.suspended && (next === "connecting" || next === "playing" || next === "reconnecting") ? "suspended" : next;
    if (this.snapshot.state === state && this.snapshot.transport === transport) return;
    this.snapshot = { state, transport };
    this.o.onChange(this.snapshot);
  }

  private clearTimer(name: "reconnectTimer" | "renewTimer" | "suspendTimer" | "disconnectTimer"): void {
    const timer = this[name];
    if (timer) clearTimeout(timer);
    this[name] = null;
  }

  private teardown(): void {
    this.clearTimer("disconnectTimer");
    this.whep?.close();
    this.whep = null;
    this.hls?.destroy();
    this.hls = null;
    const { video } = this.o;
    if (this.nativeHls) {
      video.removeAttribute("src");
      try {
        video.load();
      } catch {
        /* not supported (tests) */
      }
    }
    this.nativeHls = false;
    video.srcObject = null;
  }

  /** A grant that is still valid for `renewMarginMs`, or a new one. */
  private async ensureGrant(): Promise<ViewerGrant> {
    const current = this.grant;
    if (current && Date.parse(current.expires_at) - this.o.now() > this.o.renewMarginMs) return current;
    const grant = await this.o.requestGrant();
    this.grant = grant;
    this.scheduleRenewal(grant);
    return grant;
  }

  /** Keep a fresh token for HLS segment requests and for a quick reconnection. */
  private scheduleRenewal(grant: ViewerGrant): void {
    this.clearTimer("renewTimer");
    const due = Date.parse(grant.expires_at) - this.o.renewMarginMs - this.o.now();
    this.renewTimer = setTimeout(
      () => {
        this.renewTimer = null;
        if (!this.running || this.suspended) return;
        this.o
          .requestGrant()
          .then((next) => {
            if (!this.running) return;
            this.grant = next;
            this.scheduleRenewal(next);
          })
          .catch(() => {
            // Try again shortly; the current token may still be valid for a while.
            if (this.running) this.renewTimer = setTimeout(() => this.grant && this.scheduleRenewal(this.grant), 15_000);
          });
      },
      Math.max(5000, Number.isFinite(due) ? due : 0),
    );
  }

  private async connect(): Promise<void> {
    if (!this.running || this.suspended) return;
    const gen = ++this.generation;
    this.set(this.attempt === 0 ? "connecting" : "reconnecting", null);
    let grant: ViewerGrant;
    try {
      grant = await this.ensureGrant();
    } catch (e) {
      if (gen !== this.generation) return;
      if (isApiError(e) && e.status === 403) return this.halt("forbidden");
      if (isApiError(e) && [404, 409, 410].includes(e.status)) return this.halt("unavailable");
      this.scheduleReconnect();
      return;
    }
    if (gen !== this.generation) return;

    const tryWhep = webRtcSupported() || this.o.createPeerConnection !== undefined;
    if (tryWhep && (this.whepFailures < this.o.maxWhepFailures || !grant.hls_url)) {
      try {
        await this.startWhep(grant, gen);
        return;
      } catch (e) {
        if (gen !== this.generation) return;
        this.whepFailures += 1;
        // A refused token: get a new one next time.
        if (e instanceof WhepError && (e.status === 401 || e.status === 403)) this.grant = null;
      }
    }
    if (grant.hls_url) {
      try {
        await this.startHls(grant, gen);
        return;
      } catch {
        if (gen !== this.generation) return;
      }
    }
    this.scheduleReconnect();
  }

  private async startWhep(grant: ViewerGrant, gen: number): Promise<void> {
    const { video } = this.o;
    const conn = await startWhep(
      grant.whep_url,
      grant.token,
      {
        fetch: this.o.fetch,
        createPeerConnection: this.o.createPeerConnection ?? ((config) => new RTCPeerConnection(config)),
      },
      {
        onTrack: (event) => {
          const stream = event.streams[0] ?? new MediaStream([event.track]);
          if (video.srcObject !== stream) video.srcObject = stream;
          play(video);
        },
      },
    );
    if (gen !== this.generation) {
      conn.close();
      return;
    }
    this.whep = conn;
    this.whepFailures = 0;
    this.set("connecting", "whep");
    conn.pc.addEventListener("connectionstatechange", () => {
      if (this.whep !== conn) return;
      const s = conn.pc.connectionState;
      if (s === "failed") this.fail();
      else if (s === "disconnected") {
        this.clearTimer("disconnectTimer");
        this.disconnectTimer = setTimeout(() => {
          this.disconnectTimer = null;
          if (this.whep === conn && conn.pc.connectionState !== "connected") this.fail();
        }, this.o.disconnectGraceMs);
      } else if (s === "connected") this.clearTimer("disconnectTimer");
    });
  }

  private async startHls(grant: ViewerGrant, gen: number): Promise<void> {
    const url = grant.hls_url;
    if (!url) throw new Error("no HLS URL");
    const { video } = this.o;
    if (video.canPlayType(HLS_MIME)) {
      this.nativeHls = true;
      video.src = withToken(url, grant.token);
      this.set("connecting", "hls");
      play(video);
      return;
    }
    const Hls = await this.o.loadHls();
    if (gen !== this.generation) return;
    if (!Hls.isSupported()) throw new Error("HLS not supported");
    const hls = new Hls({
      enableWorker: false, // the CSP allows no blob: workers
      lowLatencyMode: true,
      backBufferLength: 30,
      xhrSetup: (xhr: XMLHttpRequest) => {
        // Always the newest token: it is renewed while the stream plays.
        xhr.setRequestHeader("Authorization", `Bearer ${this.grant?.token ?? grant.token}`);
      },
    });
    hls.on(Hls.Events.ERROR, (_event, data) => {
      if (data.fatal && this.hls === hls) this.fail();
    });
    this.hls = hls;
    hls.loadSource(url);
    hls.attachMedia(video);
    this.set("connecting", "hls");
    play(video);
  }

  private fail(): void {
    if (!this.running) return;
    this.generation += 1;
    this.teardown();
    if (this.suspended) return;
    this.scheduleReconnect();
  }

  private halt(state: "forbidden" | "unavailable"): void {
    this.running = false;
    this.clearTimer("renewTimer");
    this.teardown();
    this.set(state, null);
  }

  private scheduleReconnect(): void {
    if (!this.running || this.suspended) return;
    const delay = backoffDelay(this.attempt, this.o.baseDelayMs, this.o.maxDelayMs, this.o.random);
    this.attempt += 1;
    this.set("reconnecting", null);
    this.clearTimer("reconnectTimer");
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      void this.connect();
    }, delay);
  }
}
