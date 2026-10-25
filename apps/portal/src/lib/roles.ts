/** Institution roles (contract phase 4 §0, FR-B-009) and what the portal lets each one do. */
import type { OrgRole, OrgStatus } from "./types";

export type OrgAction =
  | "read"
  | "report"
  | "editCard"
  | "editRegisters"
  | "uploadDocuments"
  | "generateCertificate"
  | "deleteDocuments"
  | "manageMembers"
  | "invite"
  | "submitCertificate"
  | "resubmit"
  | "acknowledge"
  | "editActivities";

const RANK: Readonly<Record<OrgRole, number>> = { member: 0, editor: 1, admin: 2 };

const NEEDED: Readonly<Record<OrgAction, OrgRole>> = {
  read: "member",
  report: "member",
  editCard: "editor",
  editRegisters: "editor",
  uploadDocuments: "editor",
  generateCertificate: "editor",
  deleteDocuments: "admin",
  manageMembers: "admin",
  invite: "admin",
  submitCertificate: "admin",
  resubmit: "admin",
  // Phase P2b: confirming an Office message was read, recording drills and declaring events.
  acknowledge: "editor",
  editActivities: "editor",
};

/** Actions that also need an approved (`active`) institution (`409 org_not_active`). */
const NEEDS_ACTIVE: ReadonlySet<OrgAction> = new Set<OrgAction>(["report", "invite", "submitCertificate"]);

export function roleAllows(role: OrgRole, action: OrgAction): boolean {
  return RANK[role] >= RANK[NEEDED[action]];
}

/** Why an action is unavailable: the role, the institution's status, or null when allowed. */
export function blockedReason(role: OrgRole, status: OrgStatus, action: OrgAction): "role" | "status" | null {
  if (!roleAllows(role, action)) return "role";
  if (NEEDS_ACTIVE.has(action) && status !== "active") return "status";
  if (action === "resubmit" && status !== "rejected") return "status";
  return null;
}

export function can(role: OrgRole, status: OrgStatus, action: OrgAction): boolean {
  return blockedReason(role, status, action) === null;
}
