import { canChangeStatus } from "./roles";
import { isReportStatus, type ReportStatus } from "./types";

/** Status lifecycle — the transition table of contract section 3 (FR-A-032). */
export const TRANSITIONS: Readonly<Record<ReportStatus, readonly ReportStatus[]>> = {
  received: ["in_progress", "rejected"],
  in_progress: ["intervened", "ongoing", "closed", "rejected"],
  intervened: ["ongoing", "closed"],
  ongoing: ["intervened", "closed"],
  closed: [],
  rejected: [],
};

export function isFinal(status: ReportStatus): boolean {
  return TRANSITIONS[status].length === 0;
}

export function canTransition(from: ReportStatus, to: ReportStatus): boolean {
  return TRANSITIONS[from].includes(to);
}

/** Next statuses the user may choose: empty when the role cannot change status or the status is final. */
export function allowedTransitions(from: ReportStatus, roles: readonly string[]): readonly ReportStatus[] {
  return canChangeStatus(roles) ? TRANSITIONS[from] : [];
}

/**
 * Choices for the status control on a report detail: the server's `allowed_transitions` when present
 * (authoritative), otherwise the contract table; always empty for roles that cannot change status.
 */
export function statusChoices(
  report: { status: ReportStatus; allowed_transitions?: readonly unknown[] | null },
  roles: readonly string[],
): readonly ReportStatus[] {
  if (!canChangeStatus(roles)) return [];
  if (Array.isArray(report.allowed_transitions)) {
    return report.allowed_transitions.filter(isReportStatus).filter((s) => s !== report.status);
  }
  return TRANSITIONS[report.status];
}
