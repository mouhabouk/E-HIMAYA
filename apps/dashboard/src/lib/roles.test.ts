import { describe, expect, it } from "vitest";
import { identityFromClaims, identityFromToken } from "../auth/identity";
import { fakeJwt } from "../test/fixtures";
import {
  canAcknowledgeDirectives,
  canChangeStatus,
  canCloseIncidents,
  canDispatch,
  canDraftMessage,
  canEditTips,
  canManageResources,
  canMonitorPerformance,
  canPublishMessage,
  canReadResources,
  canReviewVolunteers,
  landingPath,
  settableLevels,
  canEditAiSettings,
  canManageIncidents,
  canReadOrgs,
  canReviewOrgs,
  hasDashboardAccess,
  hasReadAccess,
  staffRoles,
} from "./roles";

describe("role gating (contract §5)", () => {
  it("grants read access to the five staff read roles only", () => {
    for (const r of ["operator", "ops_manager", "field_commander", "local_committee", "central_committee"]) {
      expect(hasReadAccess([r]), r).toBe(true);
    }
    expect(hasReadAccess([])).toBe(false);
    expect(hasReadAccess(["offline_access", "uma_authorization"])).toBe(false);
    expect(hasReadAccess(["sysadmin", "content_editor", "org_auditor"])).toBe(false);
  });

  it("allows status changes to operator, ops_manager and field_commander only", () => {
    expect(canChangeStatus(["operator"])).toBe(true);
    expect(canChangeStatus(["ops_manager"])).toBe(true);
    expect(canChangeStatus(["field_commander"])).toBe(true);
    expect(canChangeStatus(["local_committee"])).toBe(false);
    expect(canChangeStatus(["central_committee"])).toBe(false);
    expect(canChangeStatus(["sysadmin"])).toBe(false);
  });

  it("allows incident grouping actions to the status-change roles only (phase 3)", () => {
    for (const r of ["operator", "ops_manager", "field_commander"]) expect(canManageIncidents([r]), r).toBe(true);
    for (const r of ["local_committee", "central_committee", "sysadmin"]) expect(canManageIncidents([r]), r).toBe(false);
  });

  it("allows AI settings changes to the central committee or sysadmin with national scope", () => {
    expect(canEditAiSettings({ roles: ["central_committee"], national: true })).toBe(true);
    expect(canEditAiSettings({ roles: ["central_committee"], national: false })).toBe(false);
    expect(canEditAiSettings({ roles: ["sysadmin", "operator"], national: true })).toBe(true);
    expect(canEditAiSettings({ roles: ["sysadmin"], national: false })).toBe(false);
    expect(canEditAiSettings({ roles: ["ops_manager", "local_committee"], national: true })).toBe(false);
  });

  it("keeps only staff roles for display", () => {
    expect(staffRoles(["offline_access", "ops_manager", "operator"])).toEqual(["operator", "ops_manager"]);
    expect(staffRoles(["org_auditor", "uma_authorization"])).toEqual(["org_auditor"]);
  });

  it("lets the five read roles and org_auditor read institutions (phase 4 §0)", () => {
    for (const r of ["operator", "ops_manager", "field_commander", "local_committee", "central_committee", "org_auditor"]) {
      expect(canReadOrgs([r]), r).toBe(true);
    }
    expect(canReadOrgs(["sysadmin", "content_editor", "org_admin", "org_member"])).toBe(false);
  });

  it("reserves registration and certificate reviews to org_auditor", () => {
    expect(canReviewOrgs(["org_auditor"])).toBe(true);
    for (const r of ["operator", "ops_manager", "central_committee", "sysadmin", "org_admin"]) {
      expect(canReviewOrgs([r]), r).toBe(false);
    }
  });

  it("opens the dashboard to an institutions auditor without report roles", () => {
    expect(hasDashboardAccess(["org_auditor"])).toBe(true);
    expect(hasReadAccess(["org_auditor"])).toBe(false);
    expect(hasDashboardAccess(["org_admin", "offline_access"])).toBe(false);
  });
});

describe("phase 5 permissions (contract §0)", () => {
  it("opens logistics to sysadmin and content pages to content_editor", () => {
    expect(hasDashboardAccess(["sysadmin"])).toBe(true);
    expect(canReadResources(["sysadmin"])).toBe(true);
    expect(canManageResources(["sysadmin"])).toBe(true);
    expect(canManageResources(["operator"])).toBe(false);
    expect(hasDashboardAccess(["content_editor"])).toBe(true);
    expect(canEditTips(["content_editor"])).toBe(true);
    expect(canEditTips(["central_committee"])).toBe(false);
    expect(landingPath(["content_editor"])).toBe("/notifications");
    expect(landingPath(["sysadmin"])).toBe("/resources");
    expect(landingPath(["operator"])).toBe("/");
  });

  it("lets ops_manager draft alerts but only editors and committees publish them", () => {
    expect(canDraftMessage(["ops_manager"], "alert")).toBe(true);
    expect(canPublishMessage(["ops_manager"], "alert")).toBe(false);
    expect(canDraftMessage(["ops_manager"], "info")).toBe(false);
    for (const r of ["content_editor", "local_committee", "central_committee"]) {
      expect(canPublishMessage([r], "alert"), r).toBe(true);
      expect(canPublishMessage([r], "info"), r).toBe(true);
    }
  });

  it("limits incident closing, volunteer review and levels to their roles", () => {
    expect(canCloseIncidents(["field_commander"])).toBe(true);
    expect(canCloseIncidents(["operator"])).toBe(false);
    expect(canDispatch(["operator"])).toBe(true);
    expect(canReviewVolunteers(["local_committee"])).toBe(true);
    expect(canReviewVolunteers(["operator"])).toBe(false);
    expect(settableLevels({ roles: ["local_committee"] })).toEqual(["normal", "crisis"]);
    expect(settableLevels({ roles: ["central_committee"] })).toEqual(["normal", "crisis", "disaster"]);
    expect(settableLevels({ roles: ["ops_manager"] })).toEqual([]);
    expect(canAcknowledgeDirectives(["central_committee"])).toBe(false);
    expect(canMonitorPerformance(["ops_manager"])).toBe(true);
  });
});

describe("identity from the access token", () => {
  it("reads realm roles and a string gouvernorat_code claim", () => {
    const id = identityFromClaims({
      sub: "abc",
      preferred_username: "sami",
      realm_access: { roles: ["operator"] },
      gouvernorat_code: "61",
    });
    expect(id).toMatchObject({ name: "sami", roles: ["operator"], gouvernoratCode: 61, national: false, hasScope: true });
  });

  it("recognises national scope", () => {
    const id = identityFromClaims({ sub: "x", realm_access: { roles: ["central_committee"] }, scope_level: "national" });
    expect(id).toMatchObject({ national: true, gouvernoratCode: null, hasScope: true });
  });

  it("flags accounts without any scope", () => {
    const id = identityFromClaims({ sub: "x", realm_access: { roles: ["operator"] } });
    expect(id.hasScope).toBe(false);
  });

  it("decodes a base64url JWT payload with non-ASCII names", () => {
    const id = identityFromToken(fakeJwt({ sub: "u", name: "سامي", realm_access: { roles: [] }, scope_level: "national" }));
    expect(id.name).toBe("سامي");
  });
});
