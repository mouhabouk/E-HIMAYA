/**
 * Operator softphone (phase 7 §4, ADR-10 scenarios 1 and 2): a WebRTC SIP endpoint registered on Asterisk with
 * short-lived credentials from the API, renewed before they expire.
 *
 * The SIP stack is behind `SipEngine` so the controller (state, renewal, call ↔ API call matching, auto-answer of
 * the operator leg of an outbound call) is tested without WebRTC; lib/jssipEngine.ts is the JsSIP implementation,
 * loaded only when the softphone is switched on.
 *
 * Matching a SIP call to its `telephony.call` row: Asterisk adds `X-EHimaya-Call-Id` to the INVITE it sends to the
 * operator (docs/api/phase-7-contract.md, implementation notes); without that header the latest `call.ringing`
 * event of the live feed is used.
 */
import { isApiError, type ErrorCode } from "./api";
import type { DialBody, DialResult, QueueInfo, SipCredentials, StaffCall } from "./telephonyTypes";

export const CALL_ID_HEADER = "x-ehimaya-call-id";

export type RegistrationState = "connecting" | "registered" | "unregistered" | "failed";

export interface SipCallHandlers {
  onAccepted?: () => void;
  onEnded?: (cause: string) => void;
  onHold?: (onHold: boolean) => void;
  onRemoteStream?: (stream: MediaStream) => void;
}

/** One SIP dialog, as the controller needs it. */
export interface SipCall {
  readonly direction: "incoming" | "outgoing";
  /** Caller (incoming) or callee (outgoing) as SIP shows it: display name or user part. */
  readonly remote: string;
  /** Request headers of an incoming INVITE, lower-case names. */
  readonly headers: Readonly<Record<string, string>>;
  setHandlers(handlers: SipCallHandlers): void;
  answer(): void;
  hangup(): void;
  hold(on: boolean): void;
  mute(on: boolean): void;
}

export interface SipEngineEvents {
  onRegistration: (state: RegistrationState, cause?: string) => void;
  onIncoming: (call: SipCall) => void;
}

export interface SipEngine {
  start(credentials: SipCredentials, events: SipEngineEvents): void;
  /** New password (and possibly socket) before the old one expires; re-registers without dropping calls. */
  updateCredentials(credentials: SipCredentials): void;
  call(target: string): SipCall;
  stop(): void;
}

export type SipEngineFactory = () => Promise<SipEngine>;

export type CallPhase = "ringing" | "dialing" | "active" | "ended";

export interface SoftphoneCall {
  key: string;
  direction: "incoming" | "outgoing";
  /** What the call is: a queue call, the operator leg of a dial-out, or a crisis conference. */
  purpose: "queue" | "dial" | "conference";
  remote: string;
  phase: CallPhase;
  onHold: boolean;
  muted: boolean;
  /** `telephony.call` id, once known (header, live event or dial answer). */
  apiCallId: string | null;
  /** Latest row of the call from the live feed (number masked for roles without call access). */
  apiCall: StaffCall | null;
  queue: QueueInfo | null;
  conferenceRoom: string | null;
  startedAt: number;
  answeredAt: number | null;
  endCause: string | null;
  remoteStream: MediaStream | null;
}

export type SoftphoneStatus = "off" | "connecting" | "ready" | "error";

export interface SoftphoneState {
  status: SoftphoneStatus;
  error: ErrorCode | "registration_failed" | "microphone" | null;
  /** Scenario 2 (transfer through the trunk) is enabled by the API. */
  transfer198: boolean;
  simulated: boolean;
  credentialsExpireAt: number | null;
  calls: SoftphoneCall[];
}

export interface SoftphoneApi {
  sipCredentials(): Promise<SipCredentials>;
  dial(body: DialBody): Promise<DialResult>;
}

export interface SoftphoneOptions {
  api: SoftphoneApi;
  createEngine: SipEngineFactory;
  now?: () => number;
  /** Renew this long before expiry (at least; 20 % of the lifetime when that is longer). */
  renewMarginMs?: number;
  /** Retry delay after a failed renewal. */
  retryMs?: number;
  /** How long a dial-out waits for its operator leg to ring the softphone. */
  dialWaitMs?: number;
  /** How long an ended call stays on screen. */
  endedLingerMs?: number;
  onRingingChange?: (ringing: boolean) => void;
}

const INITIAL: SoftphoneState = {
  status: "off",
  error: null,
  transfer198: false,
  simulated: false,
  credentialsExpireAt: null,
  calls: [],
};

/** Delay before renewing credentials that expire at `expiresAt`. */
export function renewDelay(issuedAt: number, expiresAt: number, marginMs: number): number {
  const lifetime = Math.max(0, expiresAt - issuedAt);
  return Math.max(1_000, lifetime - Math.max(marginMs, lifetime * 0.2));
}

export class Softphone {
  private state: SoftphoneState = INITIAL;
  private readonly listeners = new Set<() => void>();
  private readonly sessions = new Map<string, SipCall>();
  private engine: SipEngine | null = null;
  private renewTimer: ReturnType<typeof setTimeout> | null = null;
  private seq = 0;
  private generation = 0;
  private pendingDial: { apiCallId: string; until: number } | null = null;
  /** `call.ringing` events not yet matched to a SIP call, newest last. */
  private ringingEvents: { callId: string; call: StaffCall | null; queue: QueueInfo | null; at: number }[] = [];
  private readonly opts: Required<Omit<SoftphoneOptions, "onRingingChange">> &
    Pick<SoftphoneOptions, "onRingingChange">;
  private wasRinging = false;

  constructor(options: SoftphoneOptions) {
    this.opts = {
      now: () => Date.now(),
      renewMarginMs: 60_000,
      retryMs: 15_000,
      dialWaitMs: 30_000,
      endedLingerMs: 4_000,
      ...options,
    };
  }

  // ---------------------------------------------------------------- store

  getState = (): SoftphoneState => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  private set(patch: Partial<SoftphoneState>): void {
    this.state = { ...this.state, ...patch };
    const ringing = this.state.calls.some(
      (c) => c.phase === "ringing" && c.direction === "incoming" && c.purpose === "queue",
    );
    if (ringing !== this.wasRinging) {
      this.wasRinging = ringing;
      this.opts.onRingingChange?.(ringing);
    }
    for (const l of this.listeners) l();
  }

  private patchCall(key: string, patch: Partial<SoftphoneCall>): void {
    this.set({ calls: this.state.calls.map((c) => (c.key === key ? { ...c, ...patch } : c)) });
  }

  private call(key: string): SoftphoneCall | undefined {
    return this.state.calls.find((c) => c.key === key);
  }

  // ---------------------------------------------------------------- registration

  /** Fetch credentials, load the SIP stack and register. Safe to call again while connecting or ready. */
  async connect(): Promise<void> {
    if (this.state.status === "connecting" || this.state.status === "ready") return;
    const gen = ++this.generation;
    this.set({ status: "connecting", error: null });
    let credentials: SipCredentials;
    let engine: SipEngine;
    try {
      [credentials, engine] = await Promise.all([this.opts.api.sipCredentials(), this.opts.createEngine()]);
    } catch (e) {
      if (gen !== this.generation) return;
      this.set({ status: "error", error: isApiError(e) ? e.code : "telephony_unavailable" });
      return;
    }
    if (gen !== this.generation) {
      return;
    }
    this.engine = engine;
    this.applyCredentials(credentials);
    try {
      engine.start(credentials, {
        onRegistration: (state, cause) => {
          if (gen !== this.generation) return;
          if (state === "registered") this.set({ status: "ready", error: null });
          else if (state === "failed")
            this.set({ status: "error", error: cause === "microphone" ? "microphone" : "registration_failed" });
          else if (this.state.status === "ready") this.set({ status: "connecting" });
        },
        onIncoming: (call) => {
          if (gen === this.generation) this.addIncoming(call);
        },
      });
    } catch {
      this.engine = null;
      this.set({ status: "error", error: "telephony_unavailable" });
    }
  }

  /** Unregister and drop every call. */
  disconnect(): void {
    this.generation += 1;
    if (this.renewTimer) clearTimeout(this.renewTimer);
    this.renewTimer = null;
    for (const s of this.sessions.values()) {
      try {
        s.hangup();
      } catch {
        /* already gone */
      }
    }
    this.sessions.clear();
    try {
      this.engine?.stop();
    } catch {
      /* already stopped */
    }
    this.engine = null;
    this.pendingDial = null;
    this.ringingEvents = [];
    this.set({ ...INITIAL });
  }

  private currentEngine(): SipEngine | null {
    return this.engine;
  }

  private applyCredentials(credentials: SipCredentials): void {
    const expiresAt = Date.parse(credentials.expires_at);
    this.set({
      transfer198: credentials.transfer_198_enabled === true,
      simulated: credentials.simulated === true,
      credentialsExpireAt: Number.isNaN(expiresAt) ? null : expiresAt,
    });
    if (this.renewTimer) clearTimeout(this.renewTimer);
    this.renewTimer = null;
    if (Number.isNaN(expiresAt)) return;
    this.scheduleRenewal(renewDelay(this.opts.now(), expiresAt, this.opts.renewMarginMs));
  }

  private scheduleRenewal(delay: number): void {
    const gen = this.generation;
    this.renewTimer = setTimeout(() => void this.renew(gen), delay);
  }

  private async renew(gen: number): Promise<void> {
    this.renewTimer = null;
    if (gen !== this.generation || !this.engine) return;
    try {
      const credentials = await this.opts.api.sipCredentials();
      // The softphone may have been switched off while waiting.
      const engine = this.currentEngine();
      if (gen !== this.generation || !engine) return;
      engine.updateCredentials(credentials);
      this.applyCredentials(credentials);
    } catch {
      if (gen !== this.generation) return;
      const expiresAt = this.state.credentialsExpireAt;
      if (expiresAt !== null && this.opts.now() >= expiresAt) {
        this.set({ status: "error", error: "telephony_unavailable" });
        return;
      }
      this.scheduleRenewal(this.opts.retryMs);
    }
  }

  // ---------------------------------------------------------------- calls

  private newCall(sip: SipCall, init: Partial<SoftphoneCall>): SoftphoneCall {
    this.seq += 1;
    const key = `c${this.seq}`;
    this.sessions.set(key, sip);
    const call: SoftphoneCall = {
      key,
      direction: sip.direction,
      purpose: "queue",
      remote: sip.remote,
      phase: sip.direction === "incoming" ? "ringing" : "dialing",
      onHold: false,
      muted: false,
      apiCallId: null,
      apiCall: null,
      queue: null,
      conferenceRoom: null,
      startedAt: this.opts.now(),
      answeredAt: null,
      endCause: null,
      remoteStream: null,
      ...init,
    };
    sip.setHandlers({
      onAccepted: () => this.patchCall(key, { phase: "active", answeredAt: this.opts.now() }),
      onEnded: (cause) => this.ended(key, cause),
      onHold: (onHold) => this.patchCall(key, { onHold }),
      onRemoteStream: (remoteStream) => this.patchCall(key, { remoteStream }),
    });
    this.set({ calls: [...this.state.calls, call] });
    return call;
  }

  private addIncoming(sip: SipCall): void {
    const now = this.opts.now();
    const headerId = sip.headers[CALL_ID_HEADER] ?? null;
    const dial = this.pendingDial && this.pendingDial.until >= now ? this.pendingDial : null;
    // The operator leg of a dial-out: answered at once (the operator asked for it a moment ago).
    if (dial && (headerId === null || headerId === dial.apiCallId)) {
      this.pendingDial = null;
      const call = this.newCall(sip, { purpose: "dial", apiCallId: dial.apiCallId, direction: "outgoing" });
      this.answer(call.key);
      return;
    }
    this.ringingEvents = this.ringingEvents.filter((e) => now - e.at < 60_000);
    const event = headerId ? this.ringingEvents.find((e) => e.callId === headerId) : this.ringingEvents.at(-1);
    if (event) this.ringingEvents = this.ringingEvents.filter((e) => e !== event);
    this.newCall(sip, {
      apiCallId: headerId ?? event?.callId ?? null,
      apiCall: event?.call ?? null,
      queue: event?.queue ?? (event?.call?.queue ? { name: event.call.queue, waiting: null } : null),
    });
  }

  private ended(key: string, cause: string): void {
    this.sessions.delete(key);
    if (!this.call(key)) return;
    this.patchCall(key, { phase: "ended", endCause: cause, remoteStream: null });
    setTimeout(() => this.set({ calls: this.state.calls.filter((c) => c.key !== key) }), this.opts.endedLingerMs);
  }

  answer(key: string): void {
    const sip = this.sessions.get(key);
    const call = this.call(key);
    if (!sip || !call || call.phase !== "ringing") return;
    // One conversation at a time: the others are put on hold.
    for (const other of this.state.calls) {
      if (other.key !== key && other.phase === "active" && !other.onHold) this.hold(other.key, true);
    }
    sip.answer();
  }

  hangup(key: string): void {
    const sip = this.sessions.get(key);
    if (!sip) return;
    sip.hangup();
  }

  hold(key: string, on: boolean): void {
    const sip = this.sessions.get(key);
    if (!sip) return;
    sip.hold(on);
    this.patchCall(key, { onHold: on });
  }

  mute(key: string, on: boolean): void {
    const sip = this.sessions.get(key);
    if (!sip) return;
    sip.mute(on);
    this.patchCall(key, { muted: on });
  }

  /**
   * Outbound call (FR-C-10 "contact from the map"): the API validates and audits the number, then rings this
   * softphone; that leg is answered automatically and bridged to the callee.
   */
  async dial(body: DialBody): Promise<DialResult> {
    await this.ensureReady();
    const result = await this.opts.api.dial(body);
    this.pendingDial = { apiCallId: result.id, until: this.opts.now() + this.opts.dialWaitMs };
    return result;
  }

  /** Join a crisis conference room (ConfBridge) from the softphone. */
  async joinConference(room: string, joinUri: string): Promise<void> {
    await this.ensureReady();
    if (!this.engine) throw new Error("softphone_not_registered");
    if (this.state.calls.some((c) => c.conferenceRoom === room && c.phase !== "ended")) return;
    for (const other of this.state.calls) {
      if (other.phase === "active" && !other.onHold) this.hold(other.key, true);
    }
    const sip = this.engine.call(joinUri);
    this.newCall(sip, { purpose: "conference", conferenceRoom: room, remote: room });
  }

  private async ensureReady(): Promise<void> {
    if (this.state.status !== "ready") await this.connect();
    if (this.state.status === "ready") return;
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        unsubscribe();
        reject(new Error("softphone_not_registered"));
      }, 15_000);
      const check = () => {
        if (this.state.status === "ready") {
          clearTimeout(timer);
          unsubscribe();
          resolve();
        } else if (this.state.status === "error" || this.state.status === "off") {
          clearTimeout(timer);
          unsubscribe();
          reject(new Error("softphone_not_registered"));
        }
      };
      const unsubscribe = this.subscribe(check);
      check();
    });
  }

  // ---------------------------------------------------------------- live feed

  /** `call.*` events: queue info and the API id of the ringing call, then row updates (link, transfer). */
  noteCallEvent(event: { type: string; call_id: string; call: StaffCall | null; queue: QueueInfo | null }): void {
    if (event.type === "call.ringing") {
      const waiting = this.state.calls.find(
        (c) => c.phase === "ringing" && c.apiCallId === null && c.purpose === "queue",
      );
      if (waiting) {
        this.patchCall(waiting.key, {
          apiCallId: event.call_id,
          apiCall: event.call,
          queue: event.queue ?? waiting.queue,
        });
      } else {
        this.ringingEvents.push({ callId: event.call_id, call: event.call, queue: event.queue, at: this.opts.now() });
      }
      // Queue size changes are shown on every ringing call.
      if (event.queue) {
        const queue = event.queue;
        this.set({
          calls: this.state.calls.map((c) =>
            c.phase === "ringing" && c.purpose === "queue" ? { ...c, queue: { ...c.queue, ...queue } } : c,
          ),
        });
      }
      return;
    }
    const call = this.state.calls.find((c) => c.apiCallId === event.call_id);
    if (call && event.call) this.patchCall(call.key, { apiCall: event.call });
    if (event.type === "call.ended") this.ringingEvents = this.ringingEvents.filter((e) => e.callId !== event.call_id);
  }

  /** The API row of a call changed after a link or transfer request. */
  noteCallRow(row: StaffCall): void {
    const call = this.state.calls.find((c) => c.apiCallId === row.id);
    if (call) this.patchCall(call.key, { apiCall: row });
  }
}
