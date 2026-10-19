import type { WebSocketLike } from "../lib/live";

/** Minimal controllable WebSocket for tests. */
export class FakeWebSocket implements WebSocketLike {
  static instances: FakeWebSocket[] = [];
  readyState = 0;
  sent: unknown[] = [];
  closedWith: { code?: number; reason?: string } | null = null;
  onopen: ((ev: Event) => unknown) | null = null;
  onmessage: ((ev: MessageEvent) => unknown) | null = null;
  onclose: ((ev: CloseEvent) => unknown) | null = null;
  onerror: ((ev: Event) => unknown) | null = null;

  readonly url: string;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  static reset(): void {
    FakeWebSocket.instances = [];
  }

  static last(): FakeWebSocket {
    const ws = FakeWebSocket.instances.at(-1);
    if (!ws) throw new Error("no socket created");
    return ws;
  }

  send(data: string): void {
    this.sent.push(JSON.parse(data));
  }

  close(code?: number, reason?: string): void {
    this.closedWith = { code, reason };
    this.readyState = 3;
  }

  // --- server side helpers ---
  serverOpen(): void {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }

  serverSend(msg: unknown): void {
    this.onmessage?.(new MessageEvent("message", { data: typeof msg === "string" ? msg : JSON.stringify(msg) }));
  }

  serverClose(code: number, reason = ""): void {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close", { code, reason }));
  }
}
