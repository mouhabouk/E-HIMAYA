/**
 * Fetch wrapper for the e-Himaya API (copied from apps/dashboard): adds the bearer token, retries once after a token renewal on 401,
 * and turns every failure into an ApiError carrying a stable machine code (contract `detail` codes).
 */

/** Machine codes the portal knows how to translate (`errors.<code>` in the i18n files). */
export const ERROR_CODES = [
  // phase 2 (identities, reports, uploads)
  "authentication_required",
  "invalid_token",
  "identity_provider_unavailable",
  "account_suspended",
  "reporter_realm_required",
  "consent_required",
  "unknown_charter_version",
  "client_uuid_conflict",
  "rate_limited",
  "invalid_sha256",
  "upload_length_required",
  "unsupported_media_type",
  // phase 4 (institutions)
  "realm_not_allowed",
  "org_not_found",
  "org_role_required",
  "org_not_active",
  "version_conflict",
  "email_not_verified",
  "too_many_orgs",
  "identifier_already_registered",
  "invalid_identifier",
  "invalid_phone",
  "last_admin",
  "too_many_invitations",
  "invitation_not_found",
  "invitation_expired",
  "invitation_email_mismatch",
  "representative_exists",
  "invalid_un_number",
  "invalid_document",
  "feature_too_far",
  "too_many_features",
  "document_not_found",
  "document_in_use",
  "document_too_large",
  "incomplete",
  "certificate_outdated",
  "signing_key_missing",
  "invalid_note",
  "invalid_transition",
  // Phase P2b: Office messages, drills and events.
  "message_not_found",
  "ack_not_required",
  "drill_in_future",
  "invalid_dates",
  "not_found",
  // generic, derived from the HTTP status
  "forbidden",
  "validation_error",
  "bad_request",
  "conflict",
  "server_error",
  "network_error",
  "unknown",
] as const;
export type ErrorCode = (typeof ERROR_CODES)[number];

/**
 * Free-text `detail` values the API emits today that are not machine codes (services/api/app/core/security.py),
 * and phase 2 upload codes that mean the same thing for a document. Mapped so they are never shown raw.
 */
const DETAIL_ALIASES: Readonly<Record<string, ErrorCode>> = {
  "identity provider unavailable": "identity_provider_unavailable",
  "invalid token": "invalid_token",
  "authentication required": "authentication_required",
  "insufficient role": "forbidden",
  insufficient_role: "forbidden",
  "unknown issuer": "invalid_token",
  "Not authenticated": "authentication_required",
  "Not Found": "not_found",
  media_too_large: "document_too_large",
};

function codeFromStatus(status: number): ErrorCode {
  if (status === 400) return "bad_request";
  if (status === 401) return "authentication_required";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422) return "validation_error";
  if (status === 429) return "rate_limited";
  if (status === 413) return "document_too_large";
  if (status === 415) return "unsupported_media_type";
  if (status === 428) return "consent_required";
  if (status >= 500) return "server_error";
  return "unknown";
}

export function errorCodeFrom(status: number, detail: unknown): ErrorCode {
  if (typeof detail === "string") {
    if ((ERROR_CODES as readonly string[]).includes(detail)) return detail as ErrorCode;
    const alias = DETAIL_ALIASES[detail];
    if (alias) return alias;
  }
  return codeFromStatus(status);
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  readonly detail: unknown;
  readonly retryAfterS: number | null;

  constructor(status: number, code: ErrorCode, detail: unknown = null, retryAfterS: number | null = null) {
    super(`API error ${status}: ${code}`);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.retryAfterS = retryAfterS;
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

/** i18n key for any thrown value. */
export function errorMessageKey(e: unknown): `errors.${ErrorCode}` {
  if (isApiError(e)) return `errors.${e.code}`;
  if (e instanceof TypeError) return "errors.network_error";
  return "errors.unknown";
}

export type QueryValue = string | number | boolean | null | undefined | readonly (string | number)[];

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Record<string, QueryValue>;
  body?: unknown;
  signal?: AbortSignal;
  /** Skip the Authorization header (public endpoints). */
  anonymous?: boolean;
}

export interface TokenSource {
  /** Current access token, or null when signed out. */
  getAccessToken(): string | null;
  /** Renew the access token; resolves with the new token or null when renewal is impossible. */
  renew(): Promise<string | null>;
}

export interface ApiClient {
  request<T>(path: string, options?: RequestOptions): Promise<T>;
}

export function buildUrl(baseUrl: string, path: string, query?: Record<string, QueryValue>): string {
  const url = new URL(path, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`);
  if (query) {
    for (const [key, raw] of Object.entries(query)) {
      if (raw === undefined || raw === null || raw === "") continue;
      if (Array.isArray(raw)) {
        if (raw.length === 0) continue;
        url.searchParams.set(key, raw.join(","));
      } else {
        url.searchParams.set(key, String(raw));
      }
    }
  }
  return url.toString();
}

function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return seconds;
  const date = Date.parse(value);
  return Number.isNaN(date) ? null : Math.max(0, Math.round((date - Date.now()) / 1000));
}

async function readDetail(response: Response): Promise<unknown> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) return body.detail;
    return null;
  } catch {
    return null;
  }
}

export function createApiClient(
  baseUrl: string,
  tokens: TokenSource,
  fetchImpl: typeof fetch = (...args) => globalThis.fetch(...args),
): ApiClient {
  async function send(url: string, options: RequestOptions, token: string | null): Promise<Response> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token && !options.anonymous) headers.Authorization = `Bearer ${token}`;
    let body: string | undefined;
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }
    try {
      return await fetchImpl(url, { method: options.method ?? "GET", headers, body, signal: options.signal });
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") throw e;
      throw new ApiError(0, "network_error", null);
    }
  }

  return {
    async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
      const url = buildUrl(baseUrl, path, options.query);
      let response = await send(url, options, tokens.getAccessToken());
      if (response.status === 401 && !options.anonymous) {
        const renewed = await tokens.renew().catch(() => null);
        if (renewed) response = await send(url, options, renewed);
      }
      if (!response.ok) {
        const detail = await readDetail(response);
        throw new ApiError(
          response.status,
          errorCodeFrom(response.status, detail),
          detail,
          parseRetryAfter(response.headers.get("Retry-After")),
        );
      }
      if (response.status === 204) return undefined as T;
      return (await response.json()) as T;
    },
  };
}
