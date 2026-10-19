/** Staff roles (contract section 5) and the permissions the dashboard derives from them. */

export const READ_ROLES = ["operator", "ops_manager", "field_commander", "local_committee", "central_committee"] as const;
export const STATUS_CHANGE_ROLES = ["operator", "ops_manager", "field_commander"] as const;
export type StaffRole = (typeof READ_ROLES)[number];

export function staffRoles(roles: readonly string[]): StaffRole[] {
  return READ_ROLES.filter((r) => roles.includes(r));
}

export function hasReadAccess(roles: readonly string[]): boolean {
  return READ_ROLES.some((r) => roles.includes(r));
}

export function canChangeStatus(roles: readonly string[]): boolean {
  return STATUS_CHANGE_ROLES.some((r) => roles.includes(r));
}
