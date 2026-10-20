import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./api";
import { renewDelay, Softphone, type SoftphoneApi } from "./softphone";
import { FakeSipEngine, makeCall, makeCredentials } from "../test/phase7Fixtures";

function setup(overrides: Partial<SoftphoneApi> = {}) {
  const engine = new FakeSipEngine();
  const sipCredentials = vi.fn<SoftphoneApi["sipCredentials"]>(() => Promise.resolve(makeCredentials()));
  const dial = vi.fn<SoftphoneApi["dial"]>(() => Promise.resolve({ id: "out-1" }));
  const api: SoftphoneApi = { sipCredentials, dial, ...overrides };
  const ringing = vi.fn();
  const phone = new Softphone({
    api,
    createEngine: () => Promise.resolve(engine),
    onRingingChange: ringing,
    endedLingerMs: 10,
  });
  return { engine, api: { sipCredentials, dial }, phone, ringing };
}

async function flush() {
  for (let i = 0; i < 5; i += 1) await Promise.resolve();
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"] });
  vi.setSystemTime(new Date("2026-10-20T10:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("renewDelay", () => {
  it("renews a minute (or 20 % of the lifetime) before expiry", () => {
    expect(renewDelay(0, 10 * 60_000, 60_000)).toBe(8 * 60_000);
    expect(renewDelay(0, 2 * 60_000, 60_000)).toBe(60_000);
    expect(renewDelay(0, 500, 60_000)).toBe(1_000);
  });
});

describe("Softphone", () => {
  it("registers with fresh credentials and renews them before they expire", async () => {
    const { engine, api, phone } = setup();
    await phone.connect();
    await flush();
    expect(phone.getState().status).toBe("ready");
    expect(engine.started).toHaveLength(1);
    expect(engine.started[0]?.password).toBe("secret-1");

    api.sipCredentials.mockResolvedValueOnce(
      makeCredentials({ password: "secret-2", expires_at: new Date(Date.now() + 18 * 60_000).toISOString() }),
    );
    // 10 min lifetime: renewed after 8 min.
    await vi.advanceTimersByTimeAsync(8 * 60_000 - 1);
    expect(engine.updated).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(2);
    expect(engine.updated.map((c) => c.password)).toEqual(["secret-2"]);
    expect(phone.getState().status).toBe("ready");
  });

  it("retries a failed renewal and reports the error once the credentials expired", async () => {
    const { engine, api, phone } = setup();
    await phone.connect();
    await flush();
    api.sipCredentials.mockRejectedValue(new ApiError(503, "server_error"));
    await vi.advanceTimersByTimeAsync(8 * 60_000 + 1);
    expect(phone.getState().status).toBe("ready");
    await vi.advanceTimersByTimeAsync(2 * 60_000 + 15_000);
    expect(engine.updated).toHaveLength(0);
    expect(phone.getState()).toMatchObject({ status: "error", error: "telephony_unavailable" });
  });

  it("reports an API refusal of credentials", async () => {
    const { phone } = setup({ sipCredentials: vi.fn(() => Promise.reject(new ApiError(403, "forbidden"))) });
    await phone.connect();
    expect(phone.getState()).toMatchObject({ status: "error", error: "forbidden" });
  });

  it("matches a ringing SIP call with its API call (header, else the live event) and rings", async () => {
    const { engine, phone, ringing } = setup();
    await phone.connect();
    await flush();
    phone.noteCallEvent({
      type: "call.ringing",
      call_id: "c-9",
      call: makeCall({ id: "c-9" }),
      queue: { name: "operators", waiting: 4 },
    });
    const sip = engine.ring("+21698000042");
    let call = phone.getState().calls[0];
    expect(call).toMatchObject({
      phase: "ringing",
      apiCallId: "c-9",
      queue: { name: "operators", waiting: 4 },
      purpose: "queue",
    });
    expect(ringing).toHaveBeenLastCalledWith(true);

    // A header names the call: the event can come later.
    const sip2 = engine.ring("+21698000043", { "x-ehimaya-call-id": "c-10" });
    expect(phone.getState().calls[1]?.apiCallId).toBe("c-10");

    if (!call) throw new Error("no call");
    phone.answer(call.key);
    expect(sip.answered).toBe(true);
    call = phone.getState().calls[0];
    expect(call?.phase).toBe("active");

    // Answering the second puts the first on hold.
    const second = phone.getState().calls[1];
    if (!second) throw new Error("no call");
    phone.answer(second.key);
    expect(sip.holds).toEqual([true]);
    expect(sip2.answered).toBe(true);
    expect(ringing).toHaveBeenLastCalledWith(false);

    phone.mute(second.key, true);
    expect(sip2.mutes).toEqual([true]);
    expect(phone.getState().calls[1]?.muted).toBe(true);
    phone.hangup(second.key);
    expect(phone.getState().calls[1]?.phase).toBe("ended");
    await vi.advanceTimersByTimeAsync(20);
    expect(phone.getState().calls).toHaveLength(1);
  });

  it("a later call.ringing event fills the API id of a call already ringing", async () => {
    const { engine, phone } = setup();
    await phone.connect();
    await flush();
    engine.ring("anonymous");
    expect(phone.getState().calls[0]?.apiCallId).toBeNull();
    phone.noteCallEvent({ type: "call.ringing", call_id: "c-1", call: null, queue: null });
    expect(phone.getState().calls[0]?.apiCallId).toBe("c-1");
    phone.noteCallRow(makeCall({ id: "c-1", report_id: "r-1" }));
    expect(phone.getState().calls[0]?.apiCall?.report_id).toBe("r-1");
  });

  it("dials out through the API and answers its own leg at once", async () => {
    const { engine, api, phone, ringing } = setup();
    const dialled = phone.dial({ volunteer_id: "v-1" });
    await vi.advanceTimersByTimeAsync(0);
    await dialled;
    expect(api.dial).toHaveBeenCalledWith({ volunteer_id: "v-1" });
    const leg = engine.ring("8000", { "x-ehimaya-call-id": "out-1" });
    expect(leg.answered).toBe(true);
    expect(phone.getState().calls[0]).toMatchObject({
      purpose: "dial",
      apiCallId: "out-1",
      direction: "outgoing",
      phase: "active",
    });
    expect(ringing).not.toHaveBeenCalledWith(true);
    // Another call afterwards rings normally.
    engine.ring("+21698000001");
    expect(phone.getState().calls[1]?.phase).toBe("ringing");
  });

  it("joins a conference room and drops everything when switched off", async () => {
    const { engine, phone } = setup();
    await phone.connect();
    await flush();
    await phone.joinConference("crisis-1", "sip:crisis-1@ehimaya.test");
    expect(engine.dialled.map((d) => d.target)).toEqual(["sip:crisis-1@ehimaya.test"]);
    expect(phone.getState().calls[0]).toMatchObject({ purpose: "conference", conferenceRoom: "crisis-1" });
    // Joining twice does not open a second leg.
    await phone.joinConference("crisis-1", "sip:crisis-1@ehimaya.test");
    expect(engine.dialled).toHaveLength(1);
    phone.disconnect();
    expect(engine.stopped).toBe(true);
    expect(engine.dialled[0]?.call.hungUp).toBe(true);
    expect(phone.getState()).toMatchObject({ status: "off", calls: [] });
  });

  it("exposes the scenario 2 switch from the credentials", async () => {
    const { phone } = setup({
      sipCredentials: vi.fn(() => Promise.resolve(makeCredentials({ transfer_198_enabled: true, simulated: true }))),
    });
    await phone.connect();
    expect(phone.getState()).toMatchObject({ transfer198: true, simulated: true });
  });
});
