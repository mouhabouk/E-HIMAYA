import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FakeWebSocket } from "../test/FakeWebSocket";
import { makeReport } from "../test/fixtures";
import { backoffDelay, LiveClient, type LiveClientOptions, type LiveState } from "./live";

function setup(overrides: Partial<LiveClientOptions> = {}) {
  let token: string | null = "token-1";
  const events: unknown[] = [];
  const states: LiveState[] = [];
  const renewToken = vi.fn(() => {
    token = "token-2";
    return Promise.resolve<string | null>(token);
  });
  const client = new LiveClient({
    url: "ws://api/api/v1/staff/live",
    getToken: () => token,
    renewToken,
    onEvent: (e) => events.push(e),
    onStateChange: (s) => states.push(s),
    createSocket: (url) => new FakeWebSocket(url),
    random: () => 0.5,
    baseDelayMs: 1000,
    maxDelayMs: 30000,
    ...overrides,
  });
  return {
    client,
    events,
    states,
    renewToken,
    setToken: (t: string | null) => {
      token = t;
    },
  };
}

beforeEach(() => {
  FakeWebSocket.reset();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("backoffDelay", () => {
  it("grows exponentially with equal jitter and is capped", () => {
    expect(backoffDelay(0, 1000, 30000, () => 0)).toBe(500);
    expect(backoffDelay(0, 1000, 30000, () => 1)).toBe(1000);
    expect(backoffDelay(3, 1000, 30000, () => 0.5)).toBe(6000);
    expect(backoffDelay(10, 1000, 30000, () => 1)).toBe(30000);
    expect(backoffDelay(10, 1000, 30000, () => 0)).toBe(15000);
  });
});

describe("LiveClient", () => {
  it("sends auth first on open and becomes open on ready", () => {
    const { client, states } = setup();
    client.start();
    const ws = FakeWebSocket.last();
    expect(ws.url).toBe("ws://api/api/v1/staff/live");
    expect(ws.sent).toEqual([]);
    ws.serverOpen();
    expect(ws.sent).toEqual([{ type: "auth", token: "token-1" }]);
    expect(client.state).toBe("connecting");
    ws.serverSend({ type: "ready" });
    expect(client.state).toBe("open");
    expect(states).toEqual(["connecting", "open"]);
  });

  it("sends keep-alive pings once ready and stops them on close", () => {
    const { client } = setup({ pingIntervalMs: 1000 });
    client.start();
    const ws = FakeWebSocket.last();
    ws.serverOpen();
    vi.advanceTimersByTime(3000);
    expect(ws.sent).toHaveLength(1);
    ws.serverSend({ type: "ready" });
    vi.advanceTimersByTime(2000);
    expect(ws.sent.slice(1)).toEqual([{ type: "ping" }, { type: "ping" }]);
    ws.serverSend({ type: "pong" });
    ws.serverClose(1006);
    vi.advanceTimersByTime(500);
    expect(ws.sent).toHaveLength(3);
  });

  it("re-sends auth after every token renewal", () => {
    const { client } = setup();
    client.start();
    const ws = FakeWebSocket.last();
    ws.serverOpen();
    ws.serverSend({ type: "ready" });
    client.updateToken("renewed-A");
    client.updateToken("renewed-B");
    expect(ws.sent).toEqual([
      { type: "auth", token: "token-1" },
      { type: "auth", token: "renewed-A" },
      { type: "auth", token: "renewed-B" },
    ]);
  });

  it("dispatches contract events and ignores malformed or unknown messages", () => {
    const { client, events } = setup();
    client.start();
    const ws = FakeWebSocket.last();
    ws.serverOpen();
    ws.serverSend({ type: "ready" });
    const report = makeReport();
    ws.serverSend({ type: "report.created", report });
    ws.serverSend({ type: "report.status_changed", report: { ...report, status: "in_progress" } });
    ws.serverSend({ type: "media.stored", report_id: report.id, media: { id: "m" } });
    ws.serverSend("not json");
    ws.serverSend({ type: "something.else" });
    ws.serverSend({ type: "report.created" });
    expect(events).toHaveLength(3);
    expect(events.map((e) => (e as { type: string }).type)).toEqual([
      "report.created",
      "report.status_changed",
      "media.stored",
    ]);
  });

  it("reconnects with exponential back-off after abnormal closes and resets after ready", () => {
    const { client } = setup();
    client.start();
    FakeWebSocket.last().serverClose(1006);
    expect(client.state).toBe("reconnecting");
    expect(FakeWebSocket.instances).toHaveLength(1);

    vi.advanceTimersByTime(749); // attempt 0: cap 1000 → 750 with random 0.5
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(2);

    FakeWebSocket.last().serverClose(1011);
    vi.advanceTimersByTime(1499); // attempt 1: cap 2000 → 1500
    expect(FakeWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(3);

    FakeWebSocket.last().serverClose(1006);
    vi.advanceTimersByTime(3000); // attempt 2: cap 4000 → 3000
    expect(FakeWebSocket.instances).toHaveLength(4);

    const ws = FakeWebSocket.last();
    ws.serverOpen();
    ws.serverSend({ type: "ready" });
    ws.serverClose(1006);
    vi.advanceTimersByTime(750); // back to attempt 0
    expect(FakeWebSocket.instances).toHaveLength(5);
  });

  it("on 4401 renews the token and reconnects with the new token", async () => {
    const { client, renewToken } = setup();
    client.start();
    const first = FakeWebSocket.last();
    first.serverOpen();
    first.serverSend({ type: "ready" });
    first.serverClose(4401, "token expired");
    await vi.waitFor(() => expect(renewToken).toHaveBeenCalledTimes(1));
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2));
    const second = FakeWebSocket.last();
    second.serverOpen();
    expect(second.sent).toEqual([{ type: "auth", token: "token-2" }]);
  });

  it("backs off when 4401 repeats right after a renewal", async () => {
    const { client, renewToken } = setup();
    client.start();
    FakeWebSocket.last().serverOpen();
    FakeWebSocket.last().serverClose(4401);
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2));
    FakeWebSocket.last().serverOpen();
    FakeWebSocket.last().serverClose(4401);
    await vi.waitFor(() => expect(renewToken).toHaveBeenCalledTimes(2));
    expect(FakeWebSocket.instances).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(750);
    expect(FakeWebSocket.instances).toHaveLength(3);
  });

  it("stops as unauthenticated when the token cannot be renewed", async () => {
    const { client } = setup({ renewToken: () => Promise.resolve(null) });
    client.start();
    FakeWebSocket.last().serverClose(4401);
    await vi.waitFor(() => expect(client.state).toBe("unauthenticated"));
    await vi.advanceTimersByTimeAsync(60000);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("stops on 4403 without reconnecting", async () => {
    const { client, states } = setup();
    client.start();
    FakeWebSocket.last().serverOpen();
    FakeWebSocket.last().serverClose(4403, "forbidden");
    expect(client.state).toBe("forbidden");
    await vi.advanceTimersByTimeAsync(120000);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(states.at(-1)).toBe("forbidden");
  });

  it("closes and retries when the server never says ready", () => {
    const { client } = setup({ readyTimeoutMs: 5000 });
    client.start();
    const ws = FakeWebSocket.last();
    ws.serverOpen();
    vi.advanceTimersByTime(5000);
    expect(ws.closedWith?.code).toBe(4000);
    ws.serverClose(4000);
    vi.advanceTimersByTime(750);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("stop() closes the socket and cancels pending reconnects", () => {
    const { client } = setup();
    client.start();
    FakeWebSocket.last().serverClose(1006);
    client.stop();
    vi.advanceTimersByTime(60000);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(client.state).toBe("stopped");

    client.start();
    const ws = FakeWebSocket.last();
    client.stop();
    expect(ws.closedWith?.code).toBe(1000);
  });

  it("reconnectNow() skips the pending back-off", () => {
    const { client } = setup();
    client.start();
    FakeWebSocket.last().serverClose(1006);
    client.reconnectNow();
    expect(FakeWebSocket.instances).toHaveLength(2);
  });
});
