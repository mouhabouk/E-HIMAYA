/**
 * SipEngine on JsSIP (MIT, pinned in package.json): SIP over WebSocket (WSS) with WebRTC audio (DTLS-SRTP), as
 * Asterisk's PJSIP WebRTC endpoints expect. Loaded with a dynamic import so the SIP stack is only downloaded when an
 * operator switches the softphone on.
 */
import type { RTCSession } from "jssip/lib/RTCSession";
import type { RTCSessionEvent, UA } from "jssip/lib/UA";
import type { RegistrationState, SipCall, SipCallHandlers, SipEngine, SipEngineEvents } from "./softphone";
import type { SipCredentials } from "./telephonyTypes";

const AUDIO_ONLY: MediaStreamConstraints = { audio: true, video: false };

/** Headers Asterisk may set on the INVITE to the operator (lower-case names). */
const KNOWN_HEADERS = ["X-EHimaya-Call-Id", "X-EHimaya-Queue"];

function remoteName(session: RTCSession): string {
  const identity = session.remote_identity;
  return identity.display_name || identity.uri.user || "";
}

class JsSipCall implements SipCall {
  readonly direction: "incoming" | "outgoing";
  readonly remote: string;
  readonly headers: Readonly<Record<string, string>>;
  private handlers: SipCallHandlers = {};
  private remoteStream: MediaStream | null = null;
  private readonly session: RTCSession;
  private readonly pcConfig: () => RTCConfiguration;

  constructor(session: RTCSession, pcConfig: () => RTCConfiguration, headers: Record<string, string>) {
    this.session = session;
    this.pcConfig = pcConfig;
    this.direction = (session.direction as string) === "incoming" ? "incoming" : "outgoing";
    this.remote = remoteName(session);
    this.headers = headers;
    session.on("accepted", () => this.handlers.onAccepted?.());
    session.on("ended", (e) => this.handlers.onEnded?.(e.cause));
    session.on("failed", (e) => this.handlers.onEnded?.(e.cause));
    session.on("hold", () => this.handlers.onHold?.(true));
    session.on("unhold", () => this.handlers.onHold?.(false));
    const watch = (pc: RTCPeerConnection) =>
      pc.addEventListener("track", (ev) => {
        const stream = ev.streams[0] ?? new MediaStream([ev.track]);
        this.remoteStream = stream;
        this.handlers.onRemoteStream?.(stream);
      });
    // Outgoing sessions already have their peer connection; incoming ones create it on answer.
    const pc = session.connection as RTCPeerConnection | undefined;
    if (pc) watch(pc);
    else session.on("peerconnection", (e) => watch(e.peerconnection));
  }

  setHandlers(handlers: SipCallHandlers): void {
    this.handlers = handlers;
    if (this.remoteStream) handlers.onRemoteStream?.(this.remoteStream);
  }

  answer(): void {
    this.session.answer({ mediaConstraints: AUDIO_ONLY, pcConfig: this.pcConfig() });
  }

  hangup(): void {
    if (!this.session.isEnded()) this.session.terminate();
  }

  hold(on: boolean): void {
    if (on) this.session.hold();
    else this.session.unhold();
  }

  mute(on: boolean): void {
    if (on) this.session.mute({ audio: true });
    else this.session.unmute({ audio: true });
  }
}

export async function createJsSipEngine(): Promise<SipEngine> {
  const JsSIP = await import("jssip");
  let ua: UA | null = null;
  let iceServers: RTCIceServer[] = [];
  let wsUrl = "";
  let username = "";
  const pcConfig = (): RTCConfiguration => ({ iceServers });

  function build(credentials: SipCredentials, events: SipEngineEvents): UA {
    const socket = new JsSIP.WebSocketInterface(credentials.ws_url);
    const next = new JsSIP.UA({
      sockets: [socket],
      uri: credentials.sip_uri,
      authorization_user: credentials.username,
      password: credentials.password,
      register: true,
      session_timers: false,
      user_agent: "e-Himaya dashboard",
    });
    const state = (s: RegistrationState, cause?: string) => events.onRegistration(s, cause);
    next.on("connecting", () => state("connecting"));
    next.on("registered", () => state("registered"));
    next.on("unregistered", () => state("unregistered"));
    next.on("registrationFailed", (e: { cause?: string }) => state("failed", e.cause));
    next.on("newRTCSession", (e: RTCSessionEvent) => {
      if ((e.originator as string) !== "remote" || !("getHeader" in e.request)) return;
      const headers: Record<string, string> = {};
      for (const name of KNOWN_HEADERS) {
        const value = e.request.getHeader(name);
        if (value) headers[name.toLowerCase()] = value;
      }
      events.onIncoming(new JsSipCall(e.session, pcConfig, headers));
    });
    return next;
  }

  let events: SipEngineEvents | null = null;
  return {
    start(credentials, handlers) {
      events = handlers;
      iceServers = credentials.ice_servers;
      wsUrl = credentials.ws_url;
      username = credentials.username;
      ua = build(credentials, handlers);
      ua.start();
    },
    updateCredentials(credentials) {
      iceServers = credentials.ice_servers;
      if (!ua || !events) return;
      if (credentials.ws_url !== wsUrl || credentials.username !== username) {
        // A new socket or identity (the API normally keeps both for a session): a fresh agent; calls of the old one
        // end with it.
        wsUrl = credentials.ws_url;
        username = credentials.username;
        const old = ua;
        ua = build(credentials, events);
        ua.start();
        old.stop();
        return;
      }
      // Same endpoint, new password: JsSIP re-registers with it (the dialogs in progress are kept).
      ua.set("password", credentials.password);
      ua.register();
    },
    call(target) {
      if (!ua) throw new Error("softphone_not_registered");
      const session = ua.call(target, { mediaConstraints: AUDIO_ONLY, pcConfig: pcConfig() });
      return new JsSipCall(session, pcConfig, {});
    },
    stop() {
      ua?.stop();
      ua = null;
      events = null;
    },
  };
}
