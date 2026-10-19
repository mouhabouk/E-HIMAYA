import type { AiStatus, StaffReport } from "./types";

/** Priority bands of BR-20 as shown to operators: ≥ 70 high, 40–69 medium, < 40 low. */
export const PRIORITY_HIGH = 70;
export const PRIORITY_MEDIUM = 40;

export type PriorityBand = "high" | "medium" | "low";

/** Band of a 0..100 priority score; null when the report has no score yet. */
export function priorityBand(score: number | null | undefined): PriorityBand | null {
  if (score === null || score === undefined || !Number.isFinite(score)) return null;
  if (score >= PRIORITY_HIGH) return "high";
  if (score >= PRIORITY_MEDIUM) return "medium";
  return "low";
}

/** "awaiting" while the analysis is queued or running, "incomplete" when it failed, null otherwise. */
export function analysisFlag(state: StaffReport["analysis_state"]): "awaiting" | "incomplete" | null {
  if (state === "pending" || state === "running") return "awaiting";
  if (state === "failed") return "incomplete";
  return null;
}

/**
 * Ordering of `sort=priority` lists (contract §2): highest priority first, then newest.
 * Reports without a score come last.
 */
export function comparePriority(a: StaffReport, b: StaffReport): number {
  const pa = a.priority_score ?? -1;
  const pb = b.priority_score ?? -1;
  if (pa !== pb) return pb - pa;
  return Date.parse(b.received_at) - Date.parse(a.received_at);
}

/** True when scores come from the rules only: no AI service, or one of its capabilities is down. */
export function aiDegraded(status: AiStatus | undefined): "notConfigured" | "capabilityDown" | null {
  if (!status) return null;
  if (!status.configured) return "notConfigured";
  const caps = Object.values(status.capabilities);
  if (caps.length === 0 || caps.some((c) => !c?.ready)) return "capabilityDown";
  return null;
}
