/**
 * Minimal tus 1.0 client (core + `creation` extension) over fetch, for document uploads (contract phase 4 §6,
 * phase 2 §4): POST creates the upload, PATCH sends the file in chunks, HEAD reads the server offset to
 * resume after a pause, a disconnect or a page reload.
 */
import { errorCodeFrom, type ErrorCode } from "./api";

export const TUS_VERSION = "1.0.0";
export const DEFAULT_CHUNK_BYTES = 2 * 1024 * 1024;

export class TusError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  readonly detail: unknown;

  constructor(status: number, code: ErrorCode, detail: unknown = null) {
    super(`tus error ${status}: ${code}`);
    this.name = "TusError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export function isTusError(e: unknown): e is TusError {
  return e instanceof TusError;
}

function base64Utf8(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

/** `Upload-Metadata`: comma-separated `key base64(value)` pairs (UTF-8). Keys must be ASCII without spaces or commas. */
export function encodeMetadata(metadata: Readonly<Record<string, string | null | undefined>>): string {
  const pairs: string[] = [];
  for (const [key, value] of Object.entries(metadata)) {
    if (!/^[\x21-\x2b\x2d-\x7e]+$/.test(key)) throw new Error(`invalid tus metadata key: ${key}`);
    if (value === null || value === undefined) continue;
    pairs.push(value === "" ? key : `${key} ${base64Utf8(value)}`);
  }
  return pairs.join(",");
}

/** Inverse of encodeMetadata (used by tests and debugging). */
export function decodeMetadata(header: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const pair of header.split(",")) {
    const [key, b64] = pair.trim().split(" ");
    if (!key) continue;
    const binary = b64 ? atob(b64) : "";
    out[key] = new TextDecoder().decode(Uint8Array.from(binary, (c) => c.charCodeAt(0)));
  }
  return out;
}

export interface TusUploadOptions {
  endpoint: string;
  file: Blob;
  metadata: Readonly<Record<string, string | null | undefined>>;
  /** Identity headers (Authorization), read before every request so renewed tokens are used. */
  headers: () => Record<string, string>;
  /** Renew the credentials after a 401; resolves true when a retry makes sense. */
  renewAuth?: () => Promise<boolean>;
  chunkBytes?: number;
  /** Upload URL of an earlier attempt, to resume instead of creating a new upload. */
  uploadUrl?: string | null;
  onUrl?: (url: string) => void;
  onProgress?: (sentBytes: number, totalBytes: number) => void;
  fetchImpl?: typeof fetch;
}

async function readDetail(response: Response): Promise<unknown> {
  try {
    const text = await response.text();
    if (!text) return null;
    const body: unknown = JSON.parse(text);
    return body && typeof body === "object" && "detail" in body ? body.detail : text.trim();
  } catch {
    return null;
  }
}

/**
 * One resumable upload. `start()` resolves when the server holds the whole file; `pause()` aborts the
 * request in flight (start() then rejects with an AbortError) and a later `start()` resumes from HEAD.
 */
export class TusUpload {
  url: string | null;
  offset = 0;
  private controller: AbortController | null = null;
  private readonly opts: TusUploadOptions;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: TusUploadOptions) {
    this.opts = opts;
    this.url = opts.uploadUrl ?? null;
    this.fetchImpl = opts.fetchImpl ?? ((...args) => globalThis.fetch(...args));
  }

  get total(): number {
    return this.opts.file.size;
  }

  pause(): void {
    this.controller?.abort();
    this.controller = null;
  }

  async start(): Promise<void> {
    const controller = new AbortController();
    this.controller = controller;
    const signal = controller.signal;
    if (this.url) {
      const offset = await this.head(signal);
      if (offset === null) this.url = null; // gone or expired on the server: start again
      else this.offset = offset;
    }
    if (!this.url) await this.create(signal);
    this.opts.onProgress?.(this.offset, this.total);

    let conflicts = 0;
    while (this.offset < this.total) {
      const end = Math.min(this.total, this.offset + (this.opts.chunkBytes ?? DEFAULT_CHUNK_BYTES));
      const response = await this.send(
        this.url ?? "",
        {
          method: "PATCH",
          headers: { "Upload-Offset": String(this.offset), "Content-Type": "application/offset+octet-stream" },
          body: this.opts.file.slice(this.offset, end),
        },
        signal,
      );
      if (response.status === 409 && conflicts++ < 3) {
        // Offset mismatch (e.g. a previous chunk landed but its answer was lost): ask the server.
        const offset = await this.head(signal);
        if (offset === null) throw new TusError(404, "not_found");
        this.offset = offset;
        continue;
      }
      if (!response.ok) throw await this.failure(response);
      const next = Number(response.headers.get("Upload-Offset"));
      this.offset = Number.isFinite(next) && next > this.offset ? next : end;
      this.opts.onProgress?.(this.offset, this.total);
    }
    if (this.controller === controller) this.controller = null;
  }

  /** Current server offset, or null when the upload no longer exists. */
  private async head(signal: AbortSignal): Promise<number | null> {
    const response = await this.send(this.url ?? "", { method: "HEAD" }, signal);
    if (response.status === 404 || response.status === 410 || response.status === 403) return null;
    if (!response.ok) throw await this.failure(response);
    const offset = Number(response.headers.get("Upload-Offset"));
    return Number.isFinite(offset) && offset >= 0 ? offset : null;
  }

  private async create(signal: AbortSignal): Promise<void> {
    const response = await this.send(
      this.opts.endpoint,
      {
        method: "POST",
        headers: { "Upload-Length": String(this.total), "Upload-Metadata": encodeMetadata(this.opts.metadata) },
      },
      signal,
    );
    if (response.status !== 201) throw await this.failure(response);
    const location = response.headers.get("Location");
    if (!location) throw new TusError(response.status, "server_error");
    this.url = new URL(location, this.opts.endpoint).toString();
    this.offset = 0;
    this.opts.onUrl?.(this.url);
  }

  private async failure(response: Response): Promise<TusError> {
    const detail = await readDetail(response);
    return new TusError(response.status, errorCodeFrom(response.status, detail), detail);
  }

  private async send(url: string, init: RequestInit, signal: AbortSignal): Promise<Response> {
    const attempt = () =>
      this.fetchImpl(url, {
        ...init,
        signal,
        headers: { "Tus-Resumable": TUS_VERSION, ...this.opts.headers(), ...(init.headers as Record<string, string>) },
      });
    try {
      let response = await attempt();
      if (response.status === 401 && this.opts.renewAuth && (await this.opts.renewAuth())) response = await attempt();
      return response;
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") throw e;
      throw new TusError(0, "network_error");
    }
  }
}

// ---------------------------------------------------------------- resume after reload

const STORE_PREFIX = "ehimaya.portal.tus.";

/** Upload URL remembered for a (document, file hash) pair, so a reload resumes instead of restarting. */
export function recallUpload(key: string): string | null {
  try {
    return localStorage.getItem(STORE_PREFIX + key);
  } catch {
    return null;
  }
}

export function rememberUpload(key: string, url: string): void {
  try {
    localStorage.setItem(STORE_PREFIX + key, url);
  } catch {
    /* storage unavailable: resuming works within this page only */
  }
}

export function forgetUpload(key: string): void {
  try {
    localStorage.removeItem(STORE_PREFIX + key);
  } catch {
    /* ignore */
  }
}
