/**
 * WHEP (WebRTC-HTTP Egress Protocol, RFC 9725) viewer on the browser's own RTCPeerConnection, as served by
 * MediaMTX (`…/live/<id>/whep`, contract phase 6 §3–4). No library: one recvonly offer, the full SDP after ICE
 * gathering (no trickle, so a single POST), the answer from the `201` body, and a `DELETE` of the session resource
 * (the `Location` header) when the viewer leaves.
 */

export class WhepError extends Error {
  /** HTTP status of the WHEP endpoint, or null for a network / WebRTC failure. */
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "WhepError";
    this.status = status;
  }
}

export interface WhepDeps {
  fetch: typeof fetch;
  createPeerConnection: (config: RTCConfiguration) => RTCPeerConnection;
}

export interface WhepConnection {
  pc: RTCPeerConnection;
  /** Session resource for the teardown `DELETE`, when the server gave one. */
  resourceUrl: string | null;
  close(): void;
}

export interface WhepOptions {
  onTrack: (event: RTCTrackEvent) => void;
  iceServers?: RTCIceServer[];
  /** Upper bound on waiting for ICE candidates before sending the offer (whatever was gathered is sent). */
  iceGatheringTimeoutMs?: number;
  signal?: AbortSignal;
}

export function webRtcSupported(): boolean {
  return typeof globalThis.RTCPeerConnection === "function";
}

function waitForIceGathering(pc: RTCPeerConnection, timeoutMs: number): Promise<void> {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      pc.removeEventListener("icegatheringstatechange", onChange);
      resolve();
    };
    const onChange = () => {
      if (pc.iceGatheringState === "complete") done();
    };
    const timer = setTimeout(done, timeoutMs);
    pc.addEventListener("icegatheringstatechange", onChange);
  });
}

/** Negotiate a receive-only session; rejects with WhepError (and closes the peer connection) on any failure. */
export async function startWhep(url: string, token: string, deps: WhepDeps, options: WhepOptions): Promise<WhepConnection> {
  const pc = deps.createPeerConnection({ iceServers: options.iceServers ?? [] });
  let resourceUrl: string | null = null;
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    pc.ontrack = null;
    pc.close();
    if (resourceUrl) {
      // Best effort: MediaMTX also drops the session once the peer connection is gone.
      deps
        .fetch(resourceUrl, { method: "DELETE", headers: { Authorization: `Bearer ${token}` }, keepalive: true })
        .catch(() => undefined);
    }
  };
  try {
    pc.ontrack = options.onTrack;
    pc.addTransceiver("video", { direction: "recvonly" });
    pc.addTransceiver("audio", { direction: "recvonly" });
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await waitForIceGathering(pc, options.iceGatheringTimeoutMs ?? 2000);
    const sdp = pc.localDescription?.sdp ?? offer.sdp;
    if (!sdp) throw new WhepError("empty offer");
    let response: Response;
    try {
      response = await deps.fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/sdp", Authorization: `Bearer ${token}` },
        body: sdp,
        signal: options.signal,
      });
    } catch (e) {
      throw new WhepError(e instanceof Error ? e.message : "network error");
    }
    if (response.status !== 201 && response.status !== 200) {
      throw new WhepError(`WHEP answered ${response.status}`, response.status);
    }
    const location = response.headers.get("Location");
    if (location) resourceUrl = new URL(location, url).toString();
    const answer = await response.text();
    if (!answer.trim()) throw new WhepError("empty answer", response.status);
    await pc.setRemoteDescription({ type: "answer", sdp: answer });
    return { pc, resourceUrl, close };
  } catch (e) {
    close();
    if (e instanceof WhepError) throw e;
    throw new WhepError(e instanceof Error ? e.message : "WebRTC failure");
  }
}
