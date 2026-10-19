import { describe, expect, it } from "vitest";
import { invalidReasons } from "./certificates";
import { blockedReason, can, roleAllows } from "./roles";
import { makePublicCertificate } from "../test/fixtures";

describe("institution roles (§0)", () => {
  it("ranks admin > editor > member", () => {
    expect(roleAllows("member", "read")).toBe(true);
    expect(roleAllows("member", "report")).toBe(true);
    expect(roleAllows("member", "editRegisters")).toBe(false);
    expect(roleAllows("editor", "editCard")).toBe(true);
    expect(roleAllows("editor", "generateCertificate")).toBe(true);
    expect(roleAllows("editor", "submitCertificate")).toBe(false);
    expect(roleAllows("editor", "deleteDocuments")).toBe(false);
    expect(roleAllows("admin", "manageMembers")).toBe(true);
  });

  it("needs an active institution to report, invite and submit (409 org_not_active)", () => {
    expect(blockedReason("admin", "pending_review", "invite")).toBe("status");
    expect(blockedReason("admin", "pending_review", "manageMembers")).toBeNull();
    expect(blockedReason("member", "rejected", "report")).toBe("status");
    expect(blockedReason("member", "active", "submitCertificate")).toBe("role");
    expect(can("editor", "pending_review", "editCard")).toBe(true);
    expect(can("admin", "rejected", "resubmit")).toBe(true);
    expect(can("admin", "active", "resubmit")).toBe(false);
  });
});

describe("certificate invalid reasons", () => {
  const today = "2026-10-19";
  it("explains why a public certificate is not valid", () => {
    expect(invalidReasons(makePublicCertificate(), today)).toEqual([]);
    expect(invalidReasons(makePublicCertificate({ valid: false, valid_until: "2026-01-01" }), today)).toEqual(["expired"]);
    expect(invalidReasons(makePublicCertificate({ valid: false, superseded: true }), today)).toEqual(["superseded"]);
    expect(invalidReasons(makePublicCertificate({ valid: false, status: "rejected", valid_until: null }), today)).toEqual(["rejected"]);
    expect(invalidReasons(makePublicCertificate({ valid: false }), today)).toEqual(["suspended"]);
    expect(invalidReasons(makePublicCertificate({ valid: false, signature_valid: false }), today)).toEqual(["suspended", "signature"]);
  });
});
