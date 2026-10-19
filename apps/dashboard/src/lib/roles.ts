/** Staff roles (contract section 5, phase 4 §0) and the permissions the dashboard derives from them. */

export const READ_ROLES = ["operator", "ops_manager", "field_commander", "local_committee", "central_committee"] as const;
export const STATUS_CHANGE_ROLES = ["operator", "ops_manager", "field_commander"] as const;
/** Incident grouping actions (link, split, dismiss, merge) use the same write roles as status changes. */
export const INCIDENT_WRITE_ROLES = STATUS_CHANGE_ROLES;
/** AI settings editors (phase 3 §4), always with national scope (403 national_scope_required otherwise). */
export const AI_SETTINGS_ROLES = ["central_committee", "sysadmin"] as const;
/** Institutions (phase 4 §0): the report read roles plus `org_auditor`, restricted to the token's scope. */
export const ORG_READ_ROLES = [...READ_ROLES, "org_auditor"] as const;
/** Registration and certificate reviews are `org_auditor` only. */
export const ORG_REVIEW_ROLES = ["org_auditor"] as const;
/** Every role the dashboard knows (shown in the header). */
export const STAFF_ROLES = ORG_READ_ROLES;
export type StaffRole = (typeof STAFF_ROLES)[number];

export function staffRoles(roles: readonly string[]): StaffRole[] {
  return STAFF_ROLES.filter((r) => roles.includes(r));
}

/** Reads reports, incidents, the live map and the KPIs (the five phase 2 read roles). */
export function hasReadAccess(roles: readonly string[]): boolean {
  return READ_ROLES.some((r) => roles.includes(r));
}

export function canReadOrgs(roles: readonly string[]): boolean {
  return ORG_READ_ROLES.some((r) => roles.includes(r));
}

export function canReviewOrgs(roles: readonly string[]): boolean {
  return ORG_REVIEW_ROLES.some((r) => roles.includes(r));
}

/** May open the dashboard at all: reports or institutions. */
export function hasDashboardAccess(roles: readonly string[]): boolean {
  return hasReadAccess(roles) || canReadOrgs(roles);
}

export function canChangeStatus(roles: readonly string[]): boolean {
  return STATUS_CHANGE_ROLES.some((r) => roles.includes(r));
}

export function canManageIncidents(roles: readonly string[]): boolean {
  return INCIDENT_WRITE_ROLES.some((r) => roles.includes(r));
}

/** The API refuses settings changes outside national scope, for both roles (`national_scope_required`). */
export function canEditAiSettings(identity: { roles: readonly string[]; national: boolean }): boolean {
  return identity.national && AI_SETTINGS_ROLES.some((r) => identity.roles.includes(r));
}
