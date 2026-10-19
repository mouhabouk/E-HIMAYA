/** Identity of a portal user, read from the `ehimaya-public` access token (for display only; the API verifies). */

export interface PortalIdentity {
  subject: string;
  /** Display name (name, preferred_username, e-mail or subject). */
  name: string;
  email: string | null;
  emailVerified: boolean;
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

export function identityFromClaims(claims: Record<string, unknown>): PortalIdentity {
  const email = asString(claims.email);
  return {
    subject: asString(claims.sub) ?? "",
    name: asString(claims.name) ?? asString(claims.preferred_username) ?? email ?? asString(claims.sub) ?? "",
    email,
    emailVerified: claims.email_verified === true,
  };
}

export function identityFromToken(accessToken: string): PortalIdentity {
  return identityFromClaims(decodeJwtPayload(accessToken));
}
