import { describe, expect, it, vi } from "vitest";
import { ApiError, buildUrl, createApiClient, errorCodeFrom, errorMessageKey, type TokenSource } from "./api";

function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}

function tokens(initial = "t1", renewed: string | null = "t2") {
  let current: string | null = initial;
  const renew = vi.fn(() => {
    current = renewed;
    return Promise.resolve(renewed);
  });
  const source: TokenSource = { getAccessToken: () => current, renew };
  return { source, renew };
}

describe("buildUrl", () => {
  it("joins lists with commas and drops empty values", () => {
    const url = buildUrl("http://api:8000", "/api/v1/staff/reports", {
      status: ["received", "in_progress"],
      category: [],
      q: "",
      gouvernorat_code: 61,
      cursor: null,
      limit: 50,
    });
    expect(url).toBe("http://api:8000/api/v1/staff/reports?status=received%2Cin_progress&gouvernorat_code=61&limit=50");
  });
});

describe("error mapping", () => {
  it("keeps the contract's machine codes", () => {
    for (const code of ["org_not_found", "version_conflict", "last_admin", "consent_required", "incomplete", "certificate_outdated", "invalid_note"]) {
      expect(errorCodeFrom(409, code)).toBe(code);
    }
  });

  it("maps free-text details and unknown codes by status, never raw", () => {
    expect(errorCodeFrom(503, "identity provider unavailable")).toBe("identity_provider_unavailable");
    expect(errorCodeFrom(401, "invalid token")).toBe("invalid_token");
    expect(errorCodeFrom(422, [{ loc: ["body", "location"], msg: "x" }])).toBe("validation_error");
    expect(errorCodeFrom(403, "some text")).toBe("forbidden");
    expect(errorCodeFrom(409, "something_new")).toBe("conflict");
    expect(errorCodeFrom(428, null)).toBe("consent_required");
    expect(errorCodeFrom(413, "media_too_large")).toBe("document_too_large");
    expect(errorCodeFrom(500, null)).toBe("server_error");
    expect(errorCodeFrom(418, null)).toBe("unknown");
  });

  it("gives an i18n key for anything thrown", () => {
    expect(errorMessageKey(new ApiError(409, "last_admin"))).toBe("errors.last_admin");
    expect(errorMessageKey(new TypeError("Failed to fetch"))).toBe("errors.network_error");
    expect(errorMessageKey("??")).toBe("errors.unknown");
  });
});

describe("createApiClient", () => {
  it("adds the bearer token and parses JSON", async () => {
    const fetchImpl = vi.fn((_url: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(json(200, { ok: 1 })));
    const api = createApiClient("http://api", tokens().source, fetchImpl);
    await expect(api.request("/api/v1/me")).resolves.toEqual({ ok: 1 });
    const init = fetchImpl.mock.calls[0]?.[1];
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer t1");
  });

  it("sends JSON bodies", async () => {
    const fetchImpl = vi.fn((_url: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(json(200, {})));
    const api = createApiClient("http://api", tokens().source, fetchImpl);
    await api.request("/x", { method: "POST", body: { status: "in_progress" } });
    const init = fetchImpl.mock.calls[0]?.[1];
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe('{"status":"in_progress"}');
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("on 401 renews the token and retries once with the new token", async () => {
    const fetchImpl = vi
      .fn((_url: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(json(200, { ok: true })))
      .mockResolvedValueOnce(json(401, { detail: "authentication_required" }));
    const src = tokens();
    const api = createApiClient("http://api", src.source, fetchImpl);
    await expect(api.request("/x")).resolves.toEqual({ ok: true });
    expect(src.renew).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect((fetchImpl.mock.calls[1]?.[1]?.headers as Record<string, string>).Authorization).toBe("Bearer t2");
  });

  it("does not loop when the retry is also 401", async () => {
    const fetchImpl = vi.fn(() => Promise.resolve(json(401, { detail: "invalid token" })));
    const src = tokens();
    const api = createApiClient("http://api", src.source, fetchImpl);
    await expect(api.request("/x")).rejects.toMatchObject({ status: 401, code: "invalid_token" });
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(src.renew).toHaveBeenCalledTimes(1);
  });

  it("does not retry when renewal fails", async () => {
    const fetchImpl = vi.fn(() => Promise.resolve(json(401, {})));
    const api = createApiClient("http://api", tokens("t1", null).source, fetchImpl);
    await expect(api.request("/x")).rejects.toMatchObject({ code: "authentication_required" });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("maps 409 version_conflict and 429 with Retry-After", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(json(409, { detail: "version_conflict" }))
      .mockResolvedValueOnce(json(429, { detail: "rate_limited" }, { "Retry-After": "30" }));
    const api = createApiClient("http://api", tokens().source, fetchImpl);
    await expect(api.request("/x")).rejects.toMatchObject({ status: 409, code: "version_conflict" });
    await expect(api.request("/x")).rejects.toMatchObject({ status: 429, code: "rate_limited", retryAfterS: 30 });
  });

  it("handles non-JSON error bodies and network failures", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(new Response("<html>bad gateway</html>", { status: 502 }))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const api = createApiClient("http://api", tokens().source, fetchImpl);
    await expect(api.request("/x")).rejects.toMatchObject({ status: 502, code: "server_error" });
    await expect(api.request("/x")).rejects.toMatchObject({ status: 0, code: "network_error" });
  });
});
