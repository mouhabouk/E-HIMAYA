import type { PublicCertificate } from "./types";

export type InvalidReason =
  | "rejected"
  | "revoked"
  | "not_approved"
  | "superseded"
  | "expired"
  | "suspended"
  | "signature";

/** Today as YYYY-MM-DD (UTC), to compare with `valid_until`. */
export function todayIso(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

/**
 * Why a public certificate is not valid. The contract gives `valid` and the facts, not the reason:
 * `valid` = approved, not superseded, not expired and institution active, so an approved, current,
 * unexpired certificate that is not valid means the institution is suspended.
 */
export function invalidReasons(c: PublicCertificate, today: string = todayIso()): InvalidReason[] {
  const reasons: InvalidReason[] = [];
  if (c.status === "rejected") reasons.push("rejected");
  else if (c.status === "revoked" || c.revoked) reasons.push("revoked");
  else if (c.status !== "approved") reasons.push("not_approved");
  if (c.superseded) reasons.push("superseded");
  if (c.valid_until && c.valid_until.slice(0, 10) < today) reasons.push("expired");
  if (!c.valid && reasons.length === 0) reasons.push("suspended");
  if (c.signature_valid === false) reasons.push("signature");
  return reasons;
}
