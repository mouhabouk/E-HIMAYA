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
// ---------- Phase 5 (contract §0) ----------
/** Units and resources: managed by `ops_manager` and `sysadmin`, read by the report read roles too. */
export const LOGISTICS_ROLES = ["ops_manager", "sysadmin"] as const;
export const LOGISTICS_READ_ROLES = [...READ_ROLES, "sysadmin"] as const;
/** Closing and evaluating an incident. */
export const CLOSE_ROLES = ["ops_manager", "field_commander"] as const;
export const VOLUNTEER_REVIEW_ROLES = ["ops_manager", "local_committee", "central_committee"] as const;
export const COMMITTEE_ROLES = ["local_committee", "central_committee"] as const;
/** Committee performance: the committees and the operations manager. */
export const MONITOR_ROLES = [...COMMITTEE_ROLES, "ops_manager"] as const;
/** Notifications register and composer (alerts are drafted by `ops_manager` too). */
export const NOTIFY_ROLES = ["content_editor", "ops_manager", "local_committee", "central_committee"] as const;
export const INFO_ROLES = ["content_editor", "local_committee", "central_committee"] as const;
export const ALERT_PUBLISH_ROLES = INFO_ROLES;
export const TIPS_ROLES = ["content_editor"] as const;
// ---------- Phase 6 (contract §4) ----------
/** Live streams are read with the report read roles; ending one for everyone is for the dispatch roles. */
export const STREAM_STOP_ROLES = ["operator", "ops_manager", "field_commander"] as const;

// ---------- Phase 7 ----------
/** Weather alert suggestions (§1): reviewed by those who draft alerts — editors, the ops manager and committees. */
export const WEATHER_SUGGESTION_ROLES = NOTIFY_ROLES;
/** Spread forecasts are run by the dispatch roles (audited); everyone who reads the incident sees them. */
export const FORECAST_ROLES = INCIDENT_WRITE_ROLES;
/** Softphone (§4): the operators' queue, outbound calls, linking and transfer. */
export const TELEPHONY_ROLES = ["operator", "ops_manager", "field_commander"] as const;
/** Crisis conference rooms: the dispatch roles and both committees. */
export const CONFERENCE_ROLES = [...TELEPHONY_ROLES, ...COMMITTEE_ROLES] as const;

// ---------- Phase 8 ----------
/** Analytics, trends, hotspots and the reports library are read with the report read roles (§1). */
export const ANALYTICS_ROLES = READ_ROLES;
/** Generating a report and running a what-if scenario. */
export const REPORT_CREATE_ROLES = ["ops_manager", "field_commander", ...COMMITTEE_ROLES] as const;
export const SCENARIO_ROLES = REPORT_CREATE_ROLES;
/** Scheduled reports. */
export const SCHEDULE_ROLES = ["ops_manager", ...COMMITTEE_ROLES] as const;
/** National memory and events library (§2): the report read roles and the content editors. */
export const KNOWLEDGE_READ_ROLES = [...READ_ROLES, "content_editor"] as const;
export const MEMORY_AUTHOR_ROLES = ["ops_manager", "field_commander", ...COMMITTEE_ROLES, "content_editor"] as const;
/** Reviewers publish (never their own entry: the API refuses it), request changes and archive. */
export const MEMORY_REVIEW_ROLES = ["ops_manager", ...COMMITTEE_ROLES] as const;
/** Rewards (§3): read by the report read roles; badges, nominations and certificates managed by these. */
export const REWARDS_READ_ROLES = READ_ROLES;
export const REWARDS_MANAGE_ROLES = ["ops_manager", ...COMMITTEE_ROLES] as const;
/** Rules: changed by the central committee or a system administrator, always with national scope. */
export const REWARD_RULE_ROLES = ["central_committee", "sysadmin"] as const;

/** Every role the dashboard knows (shown in the header). */
export const STAFF_ROLES = [...ORG_READ_ROLES, "content_editor", "sysadmin"] as const;
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

/** May open the dashboard at all: reports, institutions, logistics or content. */
export function hasDashboardAccess(roles: readonly string[]): boolean {
  return hasReadAccess(roles) || canReadOrgs(roles) || canReadResources(roles) || canUseNotifications(roles);
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

const any = (allowed: readonly string[], roles: readonly string[]) => allowed.some((r) => roles.includes(r));

export function canReadResources(roles: readonly string[]): boolean {
  return any(LOGISTICS_READ_ROLES, roles);
}

export function canManageResources(roles: readonly string[]): boolean {
  return any(LOGISTICS_ROLES, roles);
}

/** Assign resources, update assignments, call volunteers out, add timeline notes. */
export function canDispatch(roles: readonly string[]): boolean {
  return any(INCIDENT_WRITE_ROLES, roles);
}

export function canCloseIncidents(roles: readonly string[]): boolean {
  return any(CLOSE_ROLES, roles);
}

export function canReviewVolunteers(roles: readonly string[]): boolean {
  return any(VOLUNTEER_REVIEW_ROLES, roles);
}

export function isCommittee(roles: readonly string[]): boolean {
  return any(COMMITTEE_ROLES, roles);
}

export function canMonitorPerformance(roles: readonly string[]): boolean {
  return any(MONITOR_ROLES, roles);
}

/** Levels the user may set (§1): a local committee only `normal`/`crisis` for its own gouvernorat. */
export function settableLevels(identity: { roles: readonly string[] }): readonly ("normal" | "crisis" | "disaster")[] {
  if (identity.roles.includes("central_committee")) return ["normal", "crisis", "disaster"];
  if (identity.roles.includes("local_committee")) return ["normal", "crisis"];
  return [];
}

/** Directives: issued by both committees, acknowledged by the local committee of a target gouvernorat. */
export function canIssueDirectives(roles: readonly string[]): boolean {
  return isCommittee(roles);
}

export function canAcknowledgeDirectives(roles: readonly string[]): boolean {
  return roles.includes("local_committee");
}

export function canUseNotifications(roles: readonly string[]): boolean {
  return any(NOTIFY_ROLES, roles);
}

export function canDraftMessage(roles: readonly string[], kind: "info" | "alert"): boolean {
  return any(kind === "info" ? INFO_ROLES : NOTIFY_ROLES, roles);
}

export function canPublishMessage(roles: readonly string[], kind: "info" | "alert"): boolean {
  return any(kind === "info" ? INFO_ROLES : ALERT_PUBLISH_ROLES, roles);
}

export function canEditTips(roles: readonly string[]): boolean {
  return any(TIPS_ROLES, roles);
}

/** Stop a live stream (`POST /api/v1/staff/streams/{id}/stop`). */
export function canStopStreams(roles: readonly string[]): boolean {
  return any(STREAM_STOP_ROLES, roles);
}

export function canReviewWeatherSuggestions(roles: readonly string[]): boolean {
  return any(WEATHER_SUGGESTION_ROLES, roles);
}

export function canRunForecast(roles: readonly string[]): boolean {
  return any(FORECAST_ROLES, roles);
}

/** Answer queue calls, dial out, link and transfer calls. */
export function canUseTelephony(roles: readonly string[]): boolean {
  return any(TELEPHONY_ROLES, roles);
}

/** Start or join an incident's crisis conference (also loads the softphone). */
export function canJoinConference(roles: readonly string[]): boolean {
  return any(CONFERENCE_ROLES, roles);
}

/** The softphone is loaded for anyone who may call or join a conference. */
export function hasSoftphone(roles: readonly string[]): boolean {
  return canUseTelephony(roles) || canJoinConference(roles);
}

/** Pages a user lands on when the KPIs are not theirs: the first area their roles open. */
export function landingPath(roles: readonly string[]): string {
  if (hasReadAccess(roles)) return "/";
  if (canReadOrgs(roles)) return "/orgs";
  if (canUseNotifications(roles)) return "/notifications";
  if (canEditTips(roles)) return "/safety-tips";
  if (canReadResources(roles)) return "/resources";
  return "/";
}

export function canReadAnalytics(roles: readonly string[]): boolean {
  return any(ANALYTICS_ROLES, roles);
}

export function canCreateReports(roles: readonly string[]): boolean {
  return any(REPORT_CREATE_ROLES, roles);
}

export function canRunScenarios(roles: readonly string[]): boolean {
  return any(SCENARIO_ROLES, roles);
}

export function canManageSchedules(roles: readonly string[]): boolean {
  return any(SCHEDULE_ROLES, roles);
}

export function canReadKnowledge(roles: readonly string[]): boolean {
  return any(KNOWLEDGE_READ_ROLES, roles);
}

export function canAuthorMemory(roles: readonly string[]): boolean {
  return any(MEMORY_AUTHOR_ROLES, roles);
}

export function canReviewMemory(roles: readonly string[]): boolean {
  return any(MEMORY_REVIEW_ROLES, roles);
}

/** The rewards area: the read roles, and system administrators for the rules and settings. */
export function canReadRewards(roles: readonly string[]): boolean {
  return any(REWARDS_READ_ROLES, roles) || roles.includes("sysadmin");
}

/** Badges, nominations, certificates and the leaderboard (gouvernorat scope applied by the API). */
export function canSeeRewardActivity(roles: readonly string[]): boolean {
  return any(REWARDS_READ_ROLES, roles);
}

export function canManageRewards(roles: readonly string[]): boolean {
  return any(REWARDS_MANAGE_ROLES, roles);
}

export function canEditRewardRules(identity: { roles: readonly string[]; national: boolean }): boolean {
  return identity.national && any(REWARD_RULE_ROLES, identity.roles);
}
