/**
 * Live updates client for `WS /api/v1/staff/live` (contract section 5).
 *
 * Protocol: send {"type":"auth","token"} right after the socket opens and again after every token renewal;
 * the server answers {"type":"ready"} and then pushes report.created, report.status_changed and media.stored
 * (phase 2), report.enriched and incident.updated (phase 3).
 * Close code 4401 = token missing/expired → renew the token, then reconnect. 4403 = no access → stop.
 * Any other close (incl. 4408 "too slow" and 1013 "try later") → reconnect with exponential back-off and jitter.
 * Once ready, a {"type":"ping"} keep-alive is sent periodically (the API answers {"type":"pong"}, ignored).
 */
import type { IncidentSummary, Media, StaffReport } from "./types";

export type LiveEvent =
  | { type: "report.created"; report: StaffReport }
  | { type: "report.status_changed"; report: StaffReport }
  | { type: "media.stored"; report_id: string; media: Media }
  /** Scores, translation, suggestion or incident of a report changed (phase 3). */
  | { type: "report.enriched"; report: StaffReport }
  | { type: "incident.updated"; incident: IncidentSummary };

export type LiveState =
  | "idle"
  | "connecting"
  | "open"
  | "reconnecting"
  | "forbidden"
  | "unauthenticated"
  | "stopped";

/** Subset of the browser WebSocket used by the client, so tests can inject a fake. */
export interface WebSocketLike {
  readonly readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  onopen: ((ev: Event) => unknown) | null;
  onmessage: ((ev: MessageEvent) => unknown) | null;
  onclose: ((ev: CloseEvent) => unknown) | null;
  onerror: ((ev: Event) => unknown) | null;
}

export type WebSocketFactory = (url: string) => WebSocketLike;

export const CLOSE_UNAUTHORIZED = 4401;
export const CLOSE_FORBIDDEN = 4403;
/** Client-side close used when the server does not answer "ready" in time. */
export const CLOSE_READY_TIMEOUT = 4000;
const WS_OPEN = 1;

export interface LiveClientOptions {
  url: string;
  getToken: () => string | null;
  /** Renew the access token (e.g. refresh-token grant). Resolves to null when the session is over. */
  renewToken: () => Promise<string | null>;
  onEvent: (event: LiveEvent) => void;
  onStateChange?: (state: LiveState) => void;
  createSocket?: WebSocketFactory;
  random?: () => number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  readyTimeoutMs?: number;
  /** Keep-alive {"type":"ping"} interval once ready (the API answers "pong"); 0 disables it. */
  pingIntervalMs?: number;
}

/** "Equal jitter" back-off: a random delay in [cap/2, cap], cap = min(max, base·2^attempt). */
export function backoffDelay(attempt: number, baseMs: number, maxMs: number, random: () => number): number {
  const cap = Math.min(maxMs, baseMs * 2 ** Math.max(0, attempt));
  return Math.round(cap / 2 + (random() * cap) / 2);
}

function parseEvent(raw: unknown): LiveEvent | { type: "ready" } | null {
  if (typeof raw !== "string") return null;
  let msg: unknown;
  try {
    msg = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!msg || typeof msg !== "object") return null;
  const m = msg as Record<string, unknown>;
  switch (m.type) {
    case "ready":
      return { type: "ready" };
    case "report.created":
    case "report.status_changed":
    case "report.enriched":
      return m.report && typeof m.report === "object" ? (m as unknown as LiveEvent) : null;
    case "incident.updated":
      return m.incident && typeof m.incident === "object" ? (m as unknown as LiveEvent) : null;
    case "media.stored":
      return typeof m.report_id === "string" && m.media && typeof m.media === "object"
        ? (m as unknown as LiveEvent)
        : null;
    default:
      return null;
  }
}

export class LiveClient {
  private readonly opts: Required<Omit<LiveClientOptions, "onStateChange">> &
    Pick<LiveClientOptions, "onStateChange">;
  private socket: WebSocketLike | null = null;
  private running = false;
  private attempt = 0;
  private authFailures = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private readyTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private _state: LiveState = "idle";

  constructor(options: LiveClientOptions) {
    this.opts = {
      createSocket: (url) => new WebSocket(url),
      random: Math.random,
      baseDelayMs: 1000,
      maxDelayMs: 30000,
      readyTimeoutMs: 15000,
      pingIntervalMs: 25000,
      ...options,
    };
  }

  get state(): LiveState {
    return this._state;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.attempt = 0;
    this.authFailures = 0;
    this.connect();
  }

  stop(): void {
    this.running = false;
    this.clearTimers();
    this.closeSocket(1000, "client stop");
    this.setState("stopped");
  }

  /** Call after every token renewal: re-authenticates the open socket (contract step 4). */
  updateToken(token: string): void {
    if (this.socket && this.socket.readyState === WS_OPEN) {
      this.socket.send(JSON.stringify({ type: "auth", token }));
    }
  }

  /** Skip the pending back-off (e.g. when the tab becomes visible or the browser goes online). */
  reconnectNow(): void {
    if (!this.running || this._state !== "reconnecting") return;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.attempt = 0;
    this.connect();
  }

  private setState(state: LiveState): void {
    if (this._state === state) return;
    this._state = state;
    this.opts.onStateChange?.(state);
  }

  private clearTimers(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.readyTimer) clearTimeout(this.readyTimer);
    this.reconnectTimer = null;
    this.readyTimer = null;
    this.stopPing();
  }

  private stopPing(): void {
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.pingTimer = null;
  }

  private closeSocket(code: number, reason: string): void {
    const ws = this.socket;
    this.socket = null;
    if (!ws) return;
    ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null;
    try {
      ws.close(code, reason);
    } catch {
      /* already closed */
    }
  }

  private connect(): void {
    if (!this.running) return;
    const token = this.opts.getToken();
    if (!token) {
      void this.handleUnauthorized();
      return;
    }
    this.setState("connecting");
    let ws: WebSocketLike;
    try {
      ws = this.opts.createSocket(this.opts.url);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = ws;

    ws.onopen = () => {
      if (this.socket !== ws) return;
      // Always read the token at send time: it may have been renewed while connecting.
      const current = this.opts.getToken() ?? token;
      ws.send(JSON.stringify({ type: "auth", token: current }));
      this.readyTimer = setTimeout(() => {
        if (this.socket === ws) ws.close(CLOSE_READY_TIMEOUT, "ready timeout");
      }, this.opts.readyTimeoutMs);
    };

    ws.onmessage = (ev: MessageEvent) => {
      if (this.socket !== ws) return;
      const msg = parseEvent(ev.data);
      if (!msg) return;
      if (msg.type === "ready") {
        if (this.readyTimer) clearTimeout(this.readyTimer);
        this.readyTimer = null;
        this.attempt = 0;
        this.authFailures = 0;
        this.stopPing();
        if (this.opts.pingIntervalMs > 0) {
          this.pingTimer = setInterval(() => {
            if (this.socket === ws && ws.readyState === WS_OPEN) ws.send(JSON.stringify({ type: "ping" }));
          }, this.opts.pingIntervalMs);
        }
        this.setState("open");
        return;
      }
      this.opts.onEvent(msg);
    };

    ws.onerror = () => {
      /* a close event always follows; reconnection is handled there */
    };

    ws.onclose = (ev: CloseEvent) => {
      if (this.socket !== ws) return;
      this.socket = null;
      if (this.readyTimer) clearTimeout(this.readyTimer);
      this.readyTimer = null;
      this.stopPing();
      if (!this.running) return;
      if (ev.code === CLOSE_FORBIDDEN) {
        this.running = false;
        this.setState("forbidden");
        return;
      }
      if (ev.code === CLOSE_UNAUTHORIZED) {
        void this.handleUnauthorized();
        return;
      }
      this.scheduleReconnect();
    };
  }

  private async handleUnauthorized(): Promise<void> {
    this.authFailures += 1;
    this.setState("reconnecting");
    const token = await this.opts.renewToken().catch(() => null);
    if (!this.running) return;
    if (!token) {
      this.running = false;
      this.setState("unauthenticated");
      return;
    }
    // First rejection after a renewal: reconnect at once. Repeated rejections: back off.
    if (this.authFailures <= 1) this.connect();
    else this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (!this.running) return;
    const delay = backoffDelay(this.attempt, this.opts.baseDelayMs, this.opts.maxDelayMs, this.opts.random);
    this.attempt += 1;
    this.setState("reconnecting");
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }
}
