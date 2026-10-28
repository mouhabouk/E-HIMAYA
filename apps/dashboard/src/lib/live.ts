/**
 * Live updates client for `WS /api/v1/staff/live` (contract section 5).
 *
 * Protocol: send {"type":"auth","token"} right after the socket opens and again after every token renewal;
 * the server answers {"type":"ready"} and then pushes report.created, report.status_changed and media.stored
 * (phase 2), report.enriched and incident.updated (phase 3), org.updated and certificate.updated (phase 4),
 * and the operations events of phase 5 (§10): levels, directives, assignments, call-outs, resources, volunteers,
 * notifications and alerts, and the live stream events of phase 6 (§4): stream.started, stream.ended,
 * stream.location, stream.alert and stream.recording, and the phase 7 events: weather.suggestion and
 * call.ringing, call.answered, call.ended, call.recording (scoped; the caller number is masked for roles without
 * call access).
 * Close code 4401 = token missing/expired → renew the token, then reconnect. 4403 = no access → stop.
 * Any other close (incl. 4408 "too slow" and 1013 "try later") → reconnect with exponential back-off and jitter.
 * Once ready, a {"type":"ping"} keep-alive is sent periodically (the API answers {"type":"pong"}, ignored).
 */
import type { Assignment, Callout, Directive, LevelRow, Message, Resource, StaffVolunteer } from "./opsTypes";
import { isAlertLabel, type AlertLabel, type StaffStream } from "./streamTypes";
import type { QueueInfo, StaffCall } from "./telephonyTypes";
import type { CertificateEvent, IncidentSummary, Media, StaffOrg, StaffReport } from "./types";
import type { WeatherSuggestion } from "./weatherTypes";

export type LiveEvent =
  | { type: "report.created"; report: StaffReport }
  | { type: "report.status_changed"; report: StaffReport }
  | { type: "media.stored"; report_id: string; media: Media }
  /** Scores, translation, suggestion or incident of a report changed (phase 3). */
  | { type: "report.enriched"; report: StaffReport }
  | { type: "incident.updated"; incident: IncidentSummary }
  /** Registration, review or card change of an institution (phase 4). */
  | { type: "org.updated"; org: StaffOrg }
  | { type: "certificate.updated"; certificate: CertificateEvent }
  // Phase 5 (§10).
  | { type: "oplevel.changed"; level: LevelRow }
  | { type: "directive.issued"; directive: Directive }
  | { type: "assignment.updated"; assignment: Assignment; gouvernorat_code: number | null }
  | { type: "callout.updated"; callout: Callout; gouvernorat_code: number | null }
  | { type: "resource.updated"; resource: Resource }
  | { type: "volunteer.updated"; volunteer: StaffVolunteer }
  | { type: "notification.updated"; message: Message }
  | { type: "alert.issued"; message: Message }
  // Phase 10 §5: an alert published alone in an emergency, and an alert channel that did not deliver.
  | { type: "alert.review_needed"; message: Message }
  | {
      type: "alert.delivery_degraded";
      message: Message;
      channel: string;
      reason: "failures" | "not_configured";
      sent: number;
      failed: number;
    }
  // Phase 6 (§4), normalised by parseStreamEvent: the contract fixes the payload of alert and recording only.
  /** `stream` is the list row when the API sends it (else only the id is known and lists are reloaded). */
  | { type: "stream.started" | "stream.ended"; stream_id: string; stream: StaffStream | null }
  | { type: "stream.location"; stream_id: string; lat: number; lon: number; at: string | null }
  /** A confirmed fire or smoke (3 of the last 5 analysed frames ≥ the alert confidence). */
  | {
      type: "stream.alert";
      stream_id: string;
      label: AlertLabel;
      confidence: number;
      report_id: string | null;
      /** Implementation-note supersets: the stored frame, the simulation flag and the time of the frame. */
      simulated?: boolean;
      media_id?: string | null;
      at?: string | null;
    }
  | { type: "stream.recording"; stream_id: string; media_id: string; report_id?: string | null }
  // Phase 7, normalised by parsePhase7Event (the contract names the events, not their payload).
  /** A threshold rule produced a suggested weather alert (`suggestion` when the API sends the row). */
  | { type: "weather.suggestion"; suggestion_id: string; suggestion: WeatherSuggestion | null }
  /** Phase L1b: a beach turned yellow or red today (once per beach, day and level). */
  | {
      type: "coastal.alert";
      id: string;
      feature_id: string;
      name: string;
      level: "yellow" | "red";
      score: number;
      day: string;
      gouvernorat_code: number | null;
      simulated: boolean;
    }
  /** Phase L5b: a reading of a sensor of the local network, with its level after it. */
  | {
      type: "sensor.reading";
      sensor_id: string;
      gouvernorat_code: number;
      value: number;
      at: string;
      level: "normal" | "watch" | "alarm";
    }
  | {
      type: "call.ringing" | "call.answered" | "call.ended" | "call.recording";
      call_id: string;
      call: StaffCall | null;
      queue: QueueInfo | null;
      media_id: string | null;
    };

export type CallLiveEvent = Extract<LiveEvent, { type: `call.${string}` }>;

export type StreamLiveEvent = Extract<LiveEvent, { type: `stream.${string}` }>;

export function isStreamEvent(event: LiveEvent): event is StreamLiveEvent {
  return event.type.startsWith("stream.");
}

/** Phase 5 events and the object each one carries (validated as an object with a string `id`, or a level row). */
const OPS_EVENT_FIELDS: Readonly<Record<string, string>> = {
  "directive.issued": "directive",
  "assignment.updated": "assignment",
  "callout.updated": "callout",
  "resource.updated": "resource",
  "volunteer.updated": "volunteer",
  "notification.updated": "message",
  "alert.issued": "message",
  "alert.review_needed": "message",
  "alert.delivery_degraded": "message",
};

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

const isObject = (v: unknown): v is Record<string, unknown> => Boolean(v) && typeof v === "object";
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/**
 * Phase 6 events. Accepted shapes: `{"stream": {row}}` or a flat `{"stream_id"}` for started/ended;
 * `{"stream_id","lat","lon","at"?}` or `{"stream_id","location":{"lat","lon"}}` for location;
 * alert and recording as fixed by §4. Anything else is dropped.
 */
export function parseStreamEvent(m: Record<string, unknown>): StreamLiveEvent | null {
  const stream = isObject(m.stream) && typeof m.stream.id === "string" ? (m.stream as unknown as StaffStream) : null;
  const streamId = typeof m.stream_id === "string" ? m.stream_id : (stream?.id ?? null);
  if (!streamId) return null;
  switch (m.type) {
    case "stream.started":
    case "stream.ended":
      return { type: m.type, stream_id: streamId, stream };
    case "stream.location": {
      const loc = isObject(m.location) ? m.location : isObject(m.last_location) ? m.last_location : m;
      if (!finite(loc.lat) || !finite(loc.lon)) return null;
      return { type: "stream.location", stream_id: streamId, lat: loc.lat, lon: loc.lon, at: typeof m.at === "string" ? m.at : null };
    }
    case "stream.alert":
      if (!isAlertLabel(m.label) || !finite(m.confidence)) return null;
      return {
        type: "stream.alert",
        stream_id: streamId,
        label: m.label,
        confidence: m.confidence,
        report_id: typeof m.report_id === "string" ? m.report_id : null,
        ...(typeof m.simulated === "boolean" ? { simulated: m.simulated } : {}),
        ...(typeof m.media_id === "string" ? { media_id: m.media_id } : {}),
        ...(typeof m.at === "string" ? { at: m.at } : {}),
      };
    case "stream.recording":
      if (typeof m.media_id !== "string") return null;
      return {
        type: "stream.recording",
        stream_id: streamId,
        media_id: m.media_id,
        ...(typeof m.report_id === "string" ? { report_id: m.report_id } : {}),
      };
    default:
      return null;
  }
}

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

/** Phase 7 events: `{"suggestion": {row}}` or `{"suggestion_id"}`; `{"call": {row}, "queue"?}` or `{"call_id"}`. */
export function parsePhase7Event(m: Record<string, unknown>): LiveEvent | null {
  if (m.type === "weather.suggestion") {
    const row = isObject(m.suggestion) && typeof m.suggestion.id === "string" ? (m.suggestion as unknown as WeatherSuggestion) : null;
    const id = str(m.suggestion_id) ?? row?.id ?? str(m.id);
    return id ? { type: "weather.suggestion", suggestion_id: id, suggestion: row } : null;
  }
  if (m.type === "call.ringing" || m.type === "call.answered" || m.type === "call.ended" || m.type === "call.recording") {
    const call = isObject(m.call) && typeof m.call.id === "string" ? (m.call as unknown as StaffCall) : null;
    const id = str(m.call_id) ?? call?.id ?? null;
    if (!id) return null;
    const q = isObject(m.queue) ? m.queue : null;
    const queue: QueueInfo | null =
      q || typeof m.queue === "string" || finite(m.waiting) || finite(m.queue_size)
        ? {
            name: str(q?.name) ?? str(m.queue) ?? call?.queue ?? null,
            waiting: finite(q?.waiting) ? q.waiting : finite(m.waiting) ? m.waiting : finite(m.queue_size) ? m.queue_size : null,
          }
        : null;
    return {
      type: m.type,
      call_id: id,
      call,
      queue,
      media_id: str(m.media_id) ?? call?.recording_media_id ?? null,
    };
  }
  return null;
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
    case "org.updated":
      return m.org && typeof m.org === "object" && typeof (m.org as { id?: unknown }).id === "string"
        ? (m as unknown as LiveEvent)
        : null;
    case "certificate.updated":
      return m.certificate &&
        typeof m.certificate === "object" &&
        typeof (m.certificate as { id?: unknown }).id === "string"
        ? (m as unknown as LiveEvent)
        : null;
    case "oplevel.changed":
      return m.level && typeof m.level === "object" && typeof (m.level as { gouvernorat_code?: unknown }).gouvernorat_code === "number"
        ? (m as unknown as LiveEvent)
        : null;
    case "directive.issued":
    case "assignment.updated":
    case "callout.updated":
    case "resource.updated":
    case "volunteer.updated":
    case "notification.updated":
    case "alert.issued":
    case "alert.review_needed":
    case "alert.delivery_degraded": {
      const field = m[OPS_EVENT_FIELDS[m.type] ?? ""];
      return field && typeof field === "object" && typeof (field as { id?: unknown }).id === "string"
        ? (m as unknown as LiveEvent)
        : null;
    }
    case "media.stored":
      return typeof m.report_id === "string" && m.media && typeof m.media === "object"
        ? (m as unknown as LiveEvent)
        : null;
    case "stream.started":
    case "stream.ended":
    case "stream.location":
    case "stream.alert":
    case "stream.recording":
      return parseStreamEvent(m);
    case "coastal.alert":
      return typeof m.id === "string" &&
        typeof m.feature_id === "string" &&
        (m.level === "yellow" || m.level === "red") &&
        typeof m.score === "number"
        ? (m as unknown as LiveEvent)
        : null;
    case "sensor.reading":
      return typeof m.sensor_id === "string" && typeof m.value === "number" && typeof m.at === "string"
        ? (m as unknown as LiveEvent)
        : null;
    case "weather.suggestion":
    case "call.ringing":
    case "call.answered":
    case "call.ended":
    case "call.recording":
      return parsePhase7Event(m);
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
      random: Math.random,
      baseDelayMs: 1000,
      maxDelayMs: 30000,
      readyTimeoutMs: 15000,
      pingIntervalMs: 25000,
      ...options,
      // LiveProvider passes `createSocket: undefined` outside tests: an explicit undefined must not erase the default.
      createSocket: options.createSocket ?? ((url) => new WebSocket(url)),
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
