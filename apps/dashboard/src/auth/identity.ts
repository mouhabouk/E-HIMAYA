/** Staff identity derived from the Keycloak access token (realm roles + geographic scope). */

export interface StaffIdentity {
  subject: string;
  /** Display name (name, preferred_username or subject). */
  name: string;
  roles: string[];
  /** Gouvernorat scope, or null for national scope. */
  gouvernoratCode: number | null;
  national: boolean;
  /** False when the account has neither a gouvernorat nor national scope (the API refuses it). */
  hasScope: boolean;
}

function base64UrlDecode(input: string): string {
  const b64 = input.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(input.length / 4) * 4, "=");
  const binary = atob(b64);
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

/** Decode (without verifying — the API verifies) the payload of a JWT. */
export function decodeJwtPayload(token: string): Record<string, unknown> {
  const part = token.split(".")[1];
  if (!part) throw new Error("not a JWT");
  const payload: unknown = JSON.parse(base64UrlDecode(part));
  if (!payload || typeof payload !== "object") throw new Error("invalid JWT payload");
  return payload as Record<string, unknown>;
}

function asString(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v : null;
}

export function identityFromClaims(claims: Record<string, unknown>): StaffIdentity {
  const realmAccess = claims.realm_access as { roles?: unknown } | undefined;
  const roles = Array.isArray(realmAccess?.roles)
    ? realmAccess.roles.filter((r): r is string => typeof r === "string")
    : [];
  const national = claims.scope_level === "national";
  let gouvernoratCode: number | null = null;
  if (!national) {
    const raw = claims.gouvernorat_code;
    const n = typeof raw === "number" ? raw : typeof raw === "string" ? Number.parseInt(raw, 10) : Number.NaN;
    gouvernoratCode = Number.isInteger(n) ? n : null;
  }
  return {
    subject: asString(claims.sub) ?? "",
    name: asString(claims.name) ?? asString(claims.preferred_username) ?? asString(claims.sub) ?? "",
    roles,
    gouvernoratCode,
    national,
    hasScope: national || gouvernoratCode !== null,
  };
}

export function identityFromToken(accessToken: string): StaffIdentity {
  return identityFromClaims(decodeJwtPayload(accessToken));
}
