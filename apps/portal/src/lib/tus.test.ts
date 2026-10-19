import { describe, expect, it, vi } from "vitest";
import { TusUpload, decodeMetadata, encodeMetadata, recallUpload, rememberUpload } from "./tus";

const ENDPOINT = "http://tus.test/api/v1/uploads/";

type Call = { url: string; method: string; headers: Record<string, string>; size: number | null };

/** Fake tusd: keeps the offset, records requests; `failPatchAt` makes one PATCH fail at the network. */
function fakeServer(opts: { initialOffset?: number; failPatchAt?: number; createStatus?: number; createBody?: unknown } = {}) {
  let offset = opts.initialOffset ?? 0;
  const calls: Call[] = [];
  let patches = 0;
  const fetchImpl = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const method = init?.method ?? "GET";
    const headers = init?.headers as Record<string, string>;
    const body = init?.body;
    calls.push({ url, method, headers, size: body instanceof Blob ? body.size : null });
    if (method === "POST") {
      if (opts.createStatus) return Promise.resolve(new Response(JSON.stringify(opts.createBody ?? {}), { status: opts.createStatus }));
      return Promise.resolve(new Response(null, { status: 201, headers: { Location: "/api/v1/uploads/abc123" } }));
    }
    if (method === "HEAD") return Promise.resolve(new Response(null, { status: 200, headers: { "Upload-Offset": String(offset) } }));
    if (method === "PATCH") {
      patches++;
      if (opts.failPatchAt === patches) return Promise.reject(new TypeError("Failed to fetch"));
      if (Number(headers["Upload-Offset"]) !== offset) return Promise.resolve(new Response(null, { status: 409 }));
      offset += (body as Blob).size;
      return Promise.resolve(new Response(null, { status: 204, headers: { "Upload-Offset": String(offset) } }));
    }
    return Promise.resolve(new Response(null, { status: 405 }));
  });
  return { fetchImpl, calls, offset: () => offset };
}

const file = new Blob([new Uint8Array(2500)]);
const meta = { target: "org_document", document_id: "d-1", sha256: "ab".repeat(32), filetype: "application/pdf", filename: "dossier é.pdf" };

describe("Upload-Metadata", () => {
  it("encodes key base64(UTF-8 value) pairs, skipping null values", () => {
    const header = encodeMetadata({ ...meta, note: null });
    expect(header.split(",")).toHaveLength(5);
    expect(header).toContain(`target ${btoa("org_document")}`);
    expect(decodeMetadata(header)).toEqual(meta);
    expect(encodeMetadata({ note: "ملاحظة" })).toBe(`note ${btoa(String.fromCharCode(...new TextEncoder().encode("ملاحظة")))}`);
    expect(() => encodeMetadata({ "bad key": "x" })).toThrow();
  });
});

describe("TusUpload", () => {
  it("creates the upload then sends the file in PATCH chunks with the identity headers", async () => {
    const server = fakeServer();
    const onUrl = vi.fn();
    const progress: number[] = [];
    const up = new TusUpload({
      endpoint: ENDPOINT,
      file,
      metadata: meta,
      chunkBytes: 1000,
      headers: () => ({ Authorization: "Bearer t" }),
      fetchImpl: server.fetchImpl,
      onUrl,
      onProgress: (sent) => progress.push(sent),
    });
    await up.start();
    const [create, ...patches] = server.calls;
    expect(create?.method).toBe("POST");
    expect(create?.url).toBe(ENDPOINT);
    expect(create?.headers["Upload-Length"]).toBe("2500");
    expect(create?.headers["Tus-Resumable"]).toBe("1.0.0");
    expect(create?.headers.Authorization).toBe("Bearer t");
    expect(decodeMetadata(create?.headers["Upload-Metadata"] ?? "")).toEqual(meta);
    expect(onUrl).toHaveBeenCalledWith("http://tus.test/api/v1/uploads/abc123");
    expect(patches.map((p) => [p.method, p.headers["Upload-Offset"], p.size])).toEqual([
      ["PATCH", "0", 1000],
      ["PATCH", "1000", 1000],
      ["PATCH", "2000", 500],
    ]);
    expect(patches[0]?.headers["Content-Type"]).toBe("application/offset+octet-stream");
    expect(progress).toEqual([0, 1000, 2000, 2500]);
    expect(server.offset()).toBe(2500);
  });

  it("resumes an existing upload from the HEAD offset without creating a new one", async () => {
    const server = fakeServer({ initialOffset: 1500 });
    const up = new TusUpload({
      endpoint: ENDPOINT,
      file,
      metadata: meta,
      chunkBytes: 1000,
      headers: () => ({}),
      uploadUrl: "http://tus.test/api/v1/uploads/abc123",
      fetchImpl: server.fetchImpl,
    });
    await up.start();
    expect(server.calls.map((c) => c.method)).toEqual(["HEAD", "PATCH"]);
    expect(server.calls[1]?.headers["Upload-Offset"]).toBe("1500");
    expect(server.calls[1]?.size).toBe(1000);
  });

  it("after a network failure, a retry asks HEAD and continues where the server stopped", async () => {
    const server = fakeServer({ failPatchAt: 2 });
    const up = new TusUpload({ endpoint: ENDPOINT, file, metadata: meta, chunkBytes: 1000, headers: () => ({}), fetchImpl: server.fetchImpl });
    await expect(up.start()).rejects.toMatchObject({ code: "network_error", status: 0 });
    expect(up.offset).toBe(1000);
    await up.start();
    const methods = server.calls.map((c) => c.method);
    expect(methods).toEqual(["POST", "PATCH", "PATCH", "HEAD", "PATCH", "PATCH"]);
    expect(server.offset()).toBe(2500);
  });

  it("pause aborts the request in flight; start resumes", async () => {
    const server = fakeServer();
    const up = new TusUpload({ endpoint: ENDPOINT, file, metadata: meta, chunkBytes: 1000, headers: () => ({}), fetchImpl: server.fetchImpl });
    const original = server.fetchImpl.getMockImplementation();
    if (!original) throw new Error("no fetch mock");
    server.fetchImpl.mockImplementationOnce((input, init) => original(input, init)); // POST
    server.fetchImpl.mockImplementationOnce(
      (_input, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
        }),
    );
    const running = up.start();
    await vi.waitFor(() => expect(server.fetchImpl).toHaveBeenCalledTimes(2));
    up.pause();
    await expect(running).rejects.toMatchObject({ name: "AbortError" });
    await up.start();
    expect(server.offset()).toBe(2500);
  });

  it("maps a refused creation to the contract's error code", async () => {
    const server = fakeServer({ createStatus: 403, createBody: { detail: "org_role_required" } });
    const up = new TusUpload({ endpoint: ENDPOINT, file, metadata: meta, headers: () => ({}), fetchImpl: server.fetchImpl });
    await expect(up.start()).rejects.toMatchObject({ status: 403, code: "org_role_required" });
    const big = fakeServer({ createStatus: 413, createBody: { detail: "document_too_large" } });
    await expect(new TusUpload({ endpoint: ENDPOINT, file, metadata: meta, headers: () => ({}), fetchImpl: big.fetchImpl }).start()).rejects.toMatchObject({
      code: "document_too_large",
    });
    const note = fakeServer({ createStatus: 400, createBody: { detail: "invalid_note" } });
    await expect(new TusUpload({ endpoint: ENDPOINT, file, metadata: meta, headers: () => ({}), fetchImpl: note.fetchImpl }).start()).rejects.toMatchObject({
      code: "invalid_note",
    });
  });

  it("remembers upload URLs for resuming after a reload", () => {
    rememberUpload("d-1:abc:2500", "http://tus.test/x");
    expect(recallUpload("d-1:abc:2500")).toBe("http://tus.test/x");
    expect(recallUpload("other")).toBeNull();
  });
});
