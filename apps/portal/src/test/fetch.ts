import { vi } from "vitest";

/** A canned answer: JSON body (or null for 204) with a status and headers. */
export interface Reply {
  status?: number;
  body?: unknown;
  headers?: Record<string, string>;
}

export type Handler = Reply | ((req: { url: URL; method: string; body: unknown; headers: Record<string, string> }) => Reply);

export function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  if (status === 204) return new Response(null, { status, headers });
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}

/**
 * Mocked fetch that routes "METHOD /path" to canned replies. A handler given as an array is consumed
 * one reply per call (the last one repeats). Unrouted calls answer 404 and are recorded.
 */
export function mockFetch(routes: Record<string, Handler | Handler[]>) {
  const counters = new Map<string, number>();
  const fn = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const raw = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(raw);
    const method = (init?.method ?? "GET").toUpperCase();
    const key = `${method} ${url.pathname}`;
    const route = routes[key];
    if (!route) return Promise.resolve(json(404, { detail: "Not Found" }));
    let handler: Handler;
    if (Array.isArray(route)) {
      const i = counters.get(key) ?? 0;
      counters.set(key, i + 1);
      handler = route[Math.min(i, route.length - 1)] as Handler;
    } else handler = route;
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
    const reply = typeof handler === "function" ? handler({ url, method, body, headers: (init?.headers ?? {}) as Record<string, string> }) : handler;
    return Promise.resolve(json(reply.status ?? 200, reply.body ?? null, reply.headers));
  });
  /** Calls made to "METHOD /path", with their parsed JSON bodies. */
  const calls = (key: string) =>
    fn.mock.calls
      .filter(([input, init]) => {
        const raw = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        return `${(init?.method ?? "GET").toUpperCase()} ${new URL(raw).pathname}` === key;
      })
      .map(([input, init]) => ({
        url: new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url),
        body: typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined,
      }));
  return { fetch: fn as unknown as typeof fetch & typeof fn, calls };
}
