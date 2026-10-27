/** Staff roles (contract section 5, phase 4 §0) and the permissions the dashboard derives from them. */

export const READ_ROLES = ["operator", "ops_manager", "field_commander", "local_committee", "central_committee"] as const;
export const STATUS_CHANGE_ROLES = ["operator", "ops_manager", "field_commander"] as const;
/** Incident grouping actions (link, split, dismiss, merge) use the same write roles as status changes. */
export const INCIDENT_WRITE_ROLES = STATUS_CHANGE_ROLES;
/**
 * AI settings editors, always with national scope (403 national_scope_required otherwise). Phase 9 §2: the central
 * committee or the AI administrator; the system administrator no longer edits them.
 */
export const AI_SETTINGS_ROLES = ["central_committee", "ai_admin"] as const;
/** Institutions (phase 4 §0): the report read roles plus `org_auditor`, restricted to the token's scope. */
export const ORG_READ_ROLES = [...READ_ROLES, "org_auditor"] as const;
/** Registration and certificate reviews are `org_auditor` only. */
export const ORG_REVIEW_ROLES = ["org_auditor"] as const;
// ---------- Phase 5 (contract §0) ----------
/**
 * Units and resources: managed by `ops_manager` (of the unit's gouvernorat; phase 9 §10 removed `sysadmin`), read by
 * the report read roles and `sysadmin` too.
 */
export const LOGISTICS_ROLES = ["ops_manager"] as const;
export const LOGISTICS_READ_ROLES = [...READ_ROLES, "sysadmin"] as const;
/** Closing and evaluating an incident. */
export const CLOSE_ROLES = ["ops_manager", "field_commander"] as const;
export const VOLUNTEER_REVIEW_ROLES = ["ops_manager", "local_committee", "central_committee"] as const;
/** Phase C1-a: who checks the doctors' registrations (the medical coordinator, and the volunteer reviewers). */
export const DOCTOR_REVIEW_ROLES = ["medical_coordinator", ...VOLUNTEER_REVIEW_ROLES] as const;
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
/** Rules: changed by the central committee only, with national scope (phase 9 §10 removed `sysadmin`). */
export const REWARD_RULE_ROLES = ["central_committee"] as const;

// ---------- Phase 9 (contract §1) ----------
/** The three technical roles added by phase 9; technical roles never grant operational rights. */
export const PHASE9_TECHNICAL_ROLES = ["security_admin", "ai_admin", "regional_account_admin"] as const;
export const TECHNICAL_ROLES = ["sysadmin", ...PHASE9_TECHNICAL_ROLES] as const;
/** Function families of §1.1 (derived from roles, as the API does). */
export const FUNCTION_ROLES = {
  command: ["central_committee", "local_committee", "field_commander"],
  operations: ["operator", "ops_manager"],
  technical: TECHNICAL_ROLES,
  support: ["content_editor", "org_auditor", "medical_coordinator"],
  /** Phase P4a: team leaders use the staff app only, never the dashboard. */
  field: ["team_leader"],
} as const;
export type StaffFunction = keyof typeof FUNCTION_ROLES;
/** `report.claim`, `report.status`, `report.link` (§1.2). */
export const CLAIM_ROLES = FUNCTION_ROLES.operations;
/** `report.refer` and `report.geo_verify`: national room only. */
export const REFER_ROLES = ["operator", "ops_manager", "central_committee"] as const;
/** `report.referral_decide`: the target regional room. */
export const REFERRAL_DECIDE_ROLES = ["operator", "ops_manager", "local_committee"] as const;
/** `incident.participants`: ops_manager and local_committee of the lead room, ops_manager and central_committee nationally. */
export const PARTICIPANT_ROLES = ["ops_manager", "local_committee", "central_committee"] as const;
/** `incident.lead_transfer` and `incident.command_level`: national only. */
export const LEAD_ROLES = ["ops_manager", "central_committee"] as const;
/** `resource_request.create`: every report read role (lead or participating room, or national). */
export const RESOURCE_REQUEST_ROLES = READ_ROLES;
/** `resource_request.decide`: the owning region; the central committee when the incident is at central level. */
export const RESOURCE_DECIDE_ROLES = ["ops_manager", "local_committee", "central_committee"] as const;
/** `breakglass.request`: the report read roles (never technical roles). */
export const BREAKGLASS_REQUEST_ROLES = READ_ROLES;
/** `audit.read_scoped`: regional ops_manager, local_committee and security_admin. */
export const SCOPED_AUDIT_ROLES = ["ops_manager", "local_committee", "security_admin"] as const;
/** Roles a regional account administrator may grant (§6.2). */
export const REGIONAL_GRANTABLE_ROLES = [
  "operator",
  "ops_manager",
  "field_commander",
  "local_committee",
  "content_editor",
  "medical_coordinator",
  "team_leader",
] as const;
/** Added for a national regional account administrator. */
export const NATIONAL_GRANTABLE_ROLES = [...REGIONAL_GRANTABLE_ROLES, "central_committee", "org_auditor"] as const;

/** Every role the dashboard knows (shown in the header). */
export const STAFF_ROLES = [
  ...ORG_READ_ROLES,
  "content_editor",
  "medical_coordinator",
  ...TECHNICAL_ROLES,
  "team_leader",
] as const;
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

/** May open the dashboard at all: reports, institutions, logistics, content or a phase 9 technical area. */
export function hasDashboardAccess(roles: readonly string[]): boolean {
  return (
    hasReadAccess(roles) ||
    canReadOrgs(roles) ||
    canReadResources(roles) ||
    canUseNotifications(roles) ||
    PHASE9_TECHNICAL_ROLES.some((r) => roles.includes(r))
  );
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

/** Doctors' registrations (phase C1-a): the list shows registration numbers, so only those who decide see it. */
/** The medical committee is appointed by a national system administrator (the API answers 403 otherwise). */
export function canManageMedicalCommittee(identity: { roles: readonly string[]; national: boolean }): boolean {
  return identity.national && identity.roles.includes("sysadmin");
}

export function canReviewDoctors(roles: readonly string[]): boolean {
  return any(DOCTOR_REVIEW_ROLES, roles);
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

/**
 * Map data layers page (phase B1): the system administrator creates layers; content editors import into the layers
 * opened to them (the API decides per layer). Every staff member sees the layers on the live map.
 */
export const LAYERS_PAGE_ROLES = ["sysadmin", "content_editor"] as const;

export function canOpenLayers(roles: readonly string[]): boolean {
  return any(LAYERS_PAGE_ROLES, roles);
}

/** Contact us inbox (phase B1): operations manager, both committees and content editors, in their scope. */
export const CONTACT_ROLES = ["ops_manager", "local_committee", "central_committee", "content_editor"] as const;

export function canHandleContact(roles: readonly string[]): boolean {
  return any(CONTACT_ROLES, roles);
}

/**
 * Missing-person search in the 72-hour location history (phase B2): the operations rooms, and only while the national
 * setting turns the feature on. The API checks the report is theirs and audits every search.
 */
export const LOCATION_HISTORY_ROLES = ["operator", "ops_manager"] as const;

export function canSearchLocationHistory(roles: readonly string[]): boolean {
  return any(LOCATION_HISTORY_ROLES, roles);
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
  if (roles.includes("regional_account_admin")) return "/accounts";
  if (roles.includes("security_admin")) return "/break-glass";
  if (roles.includes("ai_admin")) return "/settings/ai";
  if (roles.includes("medical_coordinator")) return "/doctors";
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

// ---------- Phase 9 (contract §1.2 action matrix; the UI only hides what the API refuses) ----------

interface Who {
  roles: readonly string[];
  national: boolean;
  gouvernoratCode: number | null;
}

/** Functions of §1.1 derived from the roles (a token may carry roles of two families). */
export function functionsOf(roles: readonly string[]): StaffFunction[] {
  return (Object.keys(FUNCTION_ROLES) as StaffFunction[]).filter((f) => any(FUNCTION_ROLES[f], roles));
}

/** The caller's room: `central` for national scope, `g:<code>` otherwise (null without scope). */
export function roomOf(who: Pick<Who, "national" | "gouvernoratCode">): string | null {
  if (who.national) return "central";
  return who.gouvernoratCode === null ? null : `g:${who.gouvernoratCode}`;
}

/** Gouvernorat code of a `g:<code>` room (null for `central` or no room). */
export function roomGouvernorat(room: string | null | undefined): number | null {
  if (!room?.startsWith("g:")) return null;
  const n = Number.parseInt(room.slice(2), 10);
  return Number.isInteger(n) ? n : null;
}

/**
 * National settings page (§2): the API lets every staff member read it and `editable` decides the form; the menu
 * shows it to the operations and command roles and to the technical roles (not to institution or content roles).
 */
export function canReadPlatformSettings(roles: readonly string[]): boolean {
  return hasReadAccess(roles) || TECHNICAL_ROLES.some((r) => roles.includes(r));
}

/** Claim, release and status changes come from the operations function (§1.2). */
export function canClaimReports(roles: readonly string[]): boolean {
  return any(CLAIM_ROLES, roles);
}

/**
 * Whether the claim button is offered for a report: regional room of the report or a candidate room of a critical
 * geo-pending report; the central room only when the report is late, geo-pending or under central command.
 */
export function mayClaim(
  who: Who,
  report: {
    gouvernorat_code: number | null;
    geo_state?: string;
    geo_candidates?: number[];
    sla_band?: string | null;
    category?: string;
    late?: boolean;
    escalation_state?: string;
  },
  incidentCommandLevel?: string | null,
): boolean {
  if (!canClaimReports(who.roles)) return false;
  const pending = report.geo_state === "pending" || report.geo_state === "contradictory";
  if (who.national) {
    const late = Boolean(report.late) || (report.escalation_state !== undefined && report.escalation_state !== "none");
    return late || pending || incidentCommandLevel === "central";
  }
  if (who.gouvernoratCode === null) return false;
  if (report.gouvernorat_code === who.gouvernoratCode) return true;
  const critical = report.sla_band === "critical" || report.category === "sos";
  return pending && critical && (report.geo_candidates ?? []).includes(who.gouvernoratCode);
}

/** Release a claim: the operations manager of the claiming room, or national operations staff (§4.3). */
export function mayReleaseClaim(who: Who, claimedRoom: string | null | undefined): boolean {
  if (!claimedRoom) return false;
  if (who.national) return canClaimReports(who.roles);
  return who.roles.includes("ops_manager") && roomOf(who) === claimedRoom;
}

/** Late list and geo-verification queue: national read roles (§4.4, §4.5). */
export function canSeeNationalQueues(who: Pick<Who, "roles" | "national">): boolean {
  return who.national && hasReadAccess(who.roles);
}

/** Refer a late report to a region, or verify the location of a pending one: national room only. */
export function canReferReports(who: Pick<Who, "roles" | "national">): boolean {
  return who.national && any(REFER_ROLES, who.roles);
}

export function canGeoVerify(who: Pick<Who, "roles" | "national">): boolean {
  return canReferReports(who);
}

/** Accept or refuse a referral: the target regional room. */
export function mayDecideReferral(who: Who, report: { escalation_state?: string; referred_to?: number | null }): boolean {
  return (
    !who.national &&
    report.escalation_state === "referred" &&
    report.referred_to !== null &&
    report.referred_to !== undefined &&
    report.referred_to === who.gouvernoratCode &&
    any(REFERRAL_DECIDE_ROLES, who.roles)
  );
}

/** Add or remove participating gouvernorats: the lead room (ops_manager, local_committee) or national. */
export function mayManageParticipants(who: Who, leadCode: number | null | undefined): boolean {
  if (who.national) return who.roles.includes("ops_manager") || who.roles.includes("central_committee");
  return (
    (who.roles.includes("ops_manager") || who.roles.includes("local_committee")) &&
    leadCode !== null &&
    leadCode !== undefined &&
    leadCode === who.gouvernoratCode
  );
}

/** Transfer the lead or set the command level: national ops_manager or central_committee. */
export function canDirectIncidents(who: Pick<Who, "roles" | "national">): boolean {
  return who.national && any(LEAD_ROLES, who.roles);
}

/** Request resources from another gouvernorat: lead or participating room, or national. */
export function mayRequestResources(
  who: Who,
  incident: { gouvernorat_code: number | null; lead_gouvernorat_code?: number | null; participating_gouvernorats?: number[] },
): boolean {
  if (who.national) return any(RESOURCE_REQUEST_ROLES, who.roles);
  if (!any(["operator", "ops_manager", "field_commander", "local_committee"], who.roles)) return false;
  const lead = incident.lead_gouvernorat_code ?? incident.gouvernorat_code;
  return who.gouvernoratCode !== null && (lead === who.gouvernoratCode || (incident.participating_gouvernorats ?? []).includes(who.gouvernoratCode));
}

/** Approve or refuse a request: the owning region; nationally the central committee for central-level incidents. */
export function mayDecideResourceRequest(
  who: Who,
  request: { to_gouvernorat_code: number; status: string; incident_command_level?: string | null },
  incidentCommandLevel?: string | null,
): boolean {
  if (request.status !== "pending") return false;
  if (who.national) {
    const level = incidentCommandLevel ?? request.incident_command_level ?? null;
    return who.roles.includes("central_committee") && level === "central";
  }
  return (
    (who.roles.includes("ops_manager") || who.roles.includes("local_committee")) &&
    who.gouvernoratCode === request.to_gouvernorat_code
  );
}

/** Cancel a request: the requesting room. */
export function mayCancelResourceRequest(who: Who, request: { from_room: string; status: string }): boolean {
  return request.status === "pending" && roomOf(who) === request.from_room && any(RESOURCE_REQUEST_ROLES, who.roles);
}

export function canRequestBreakGlass(roles: readonly string[]): boolean {
  return any(BREAKGLASS_REQUEST_ROLES, roles);
}

/** Review break-glass grants and read the raw audit: national security administrators. */
export function canReviewBreakGlass(who: Pick<Who, "roles" | "national">): boolean {
  return who.national && who.roles.includes("security_admin");
}

/** The break-glass page: reviewers, and requesters for their own grants. */
export function canOpenBreakGlass(who: Pick<Who, "roles" | "national">): boolean {
  return canReviewBreakGlass(who) || canRequestBreakGlass(who.roles);
}

/** Scoped, redacted audit view of the caller's gouvernorat (§7.3): regional rooms only. */
export function canReadScopedAudit(who: Pick<Who, "roles" | "national">): boolean {
  return !who.national && any(SCOPED_AUDIT_ROLES, who.roles);
}

/** Accounts page: regional account administrators, and national security administrators for technical roles. */
export function canManageAccounts(who: Pick<Who, "roles" | "national">): boolean {
  return who.roles.includes("regional_account_admin") || (who.national && who.roles.includes("security_admin"));
}

/** Phase P4a: team leaders' phones (list and remote wipe), as the API's `crew-devices` endpoints. */
export const CREW_DEVICE_ROLES = ["regional_account_admin", "security_admin"] as const;
export function canManageCrewDevices(roles: readonly string[]): boolean {
  return any(CREW_DEVICE_ROLES, roles);
}

/** Teams on duty page: the report read roles see the shifts, the device administrators the phones too. */
export function canOpenCrew(roles: readonly string[]): boolean {
  return hasReadAccess(roles) || canManageCrewDevices(roles);
}

/** Roles the caller may grant in the accounts page (§6.2); the API refuses others with `role_not_grantable`. */
export function grantableRoles(who: Pick<Who, "roles" | "national">): string[] {
  const out = new Set<string>();
  if (who.roles.includes("regional_account_admin")) {
    for (const r of who.national ? NATIONAL_GRANTABLE_ROLES : REGIONAL_GRANTABLE_ROLES) out.add(r);
  }
  if (who.national && who.roles.includes("security_admin")) for (const r of TECHNICAL_ROLES) out.add(r);
  return STAFF_ROLES.filter((r) => out.has(r));
}

/** Phase P4b: marking a team's backup or danger alert as seen (the room and central command). */
export function canMarkCrewAlerts(roles: readonly string[]): boolean {
  return canDispatch(roles) || roles.includes("central_committee");
}

/** Phase P4b: detailed-report templates are edited and approved by the Office (central command or a national manager). */
export function canEditReportTemplates(identity: { roles: readonly string[]; national: boolean }): boolean {
  return identity.roles.includes("central_committee") || (identity.national && identity.roles.includes("ops_manager"));
}
