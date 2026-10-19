import { describe, expect, it } from "vitest";
import { identityFromClaims, identityFromToken } from "../auth/identity";
import { fakeJwt } from "../test/fixtures";
import { canChangeStatus, hasReadAccess, staffRoles } from "./roles";

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

  it("keeps only staff roles for display", () => {
    expect(staffRoles(["offline_access", "ops_manager", "operator"])).toEqual(["operator", "ops_manager"]);
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
