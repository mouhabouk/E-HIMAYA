import { describe, expect, it } from "vitest";
import { makeStaffOrg } from "../test/fixtures";
import {
  DEFAULT_ORG_FILTERS,
  decisionNeedsReason,
  matchesOrgFilters,
  orgFiltersFromSearch,
  orgFiltersToSearch,
  reviewDecisions,
  validateValidUntil,
  validUntilBounds,
} from "./orgs";

describe("institution list filters", () => {
  it("round-trips through the URL and ignores unknown values", () => {
    const f = { status: "suspended", kind: "tourism", gouvernorat: 11, certificate: "none", hasHazmat: true, q: "nz" } as const;
    const params = orgFiltersToSearch(f);
    expect(params.toString()).toBe("status=suspended&kind=tourism&gouvernorat_code=11&certificate=none&has_hazmat=true&q=nz");
    expect(orgFiltersFromSearch(params)).toEqual(f);
    expect(orgFiltersFromSearch(new URLSearchParams("status=bogus&kind=x&has_hazmat=maybe&certificate=zz"))).toEqual(
      DEFAULT_ORG_FILTERS,
    );
    expect(orgFiltersToSearch(DEFAULT_ORG_FILTERS).toString()).toBe("");
  });

  it("matches an institution like the server filters", () => {
    const org = makeStaffOrg({ status: "pending_review", hazmat_count: 0, certificate_status: "none" });
    expect(matchesOrgFilters(org, DEFAULT_ORG_FILTERS)).toBe(true);
    expect(matchesOrgFilters(org, { ...DEFAULT_ORG_FILTERS, status: "pending_review" })).toBe(true);
    expect(matchesOrgFilters(org, { ...DEFAULT_ORG_FILTERS, status: "active" })).toBe(false);
    expect(matchesOrgFilters(org, { ...DEFAULT_ORG_FILTERS, hasHazmat: true })).toBe(false);
    expect(matchesOrgFilters(org, { ...DEFAULT_ORG_FILTERS, hasHazmat: false })).toBe(true);
    expect(matchesOrgFilters(org, { ...DEFAULT_ORG_FILTERS, certificate: "none" })).toBe(true);
    expect(matchesOrgFilters(org, { ...DEFAULT_ORG_FILTERS, kind: "tourism" })).toBe(false);
    expect(matchesOrgFilters(org, { ...DEFAULT_ORG_FILTERS, gouvernorat: 11 })).toBe(false);
    expect(matchesOrgFilters(org, { ...DEFAULT_ORG_FILTERS, q: "chimique" })).toBe(true);
    expect(matchesOrgFilters(org, { ...DEFAULT_ORG_FILTERS, q: "1234567a" })).toBe(true);
    expect(matchesOrgFilters(org, { ...DEFAULT_ORG_FILTERS, q: "hôtel" })).toBe(false);
  });
});

describe("registration review transitions (§9)", () => {
  it("offers only the allowed decisions per status", () => {
    expect(reviewDecisions("pending_review")).toEqual(["approve", "reject"]);
    expect(reviewDecisions("active")).toEqual(["suspend"]);
    expect(reviewDecisions("suspended")).toEqual(["reinstate"]);
    expect(reviewDecisions("rejected")).toEqual([]);
  });

  it("requires a reason for reject and suspend only", () => {
    expect(decisionNeedsReason("reject")).toBe(true);
    expect(decisionNeedsReason("suspend")).toBe(true);
    expect(decisionNeedsReason("approve")).toBe(false);
    expect(decisionNeedsReason("reinstate")).toBe(false);
  });
});

describe("certificate valid_until (tomorrow … 5 years, default +1 year)", () => {
  const today = new Date(2026, 9, 19);

  it("computes the bounds and the default from the local date", () => {
    expect(validUntilBounds(today)).toEqual({ min: "2026-10-20", max: "2031-10-19", default: "2027-10-19" });
    expect(validUntilBounds(new Date(2028, 1, 29)).default).toBe("2029-03-01");
  });

  it("validates like the server", () => {
    expect(validateValidUntil("", today)).toBe("required");
    expect(validateValidUntil("19/10/2027", today)).toBe("format");
    expect(validateValidUntil("2027-02-30", today)).toBe("format");
    expect(validateValidUntil("2026-10-19", today)).toBe("range");
    expect(validateValidUntil("2031-10-20", today)).toBe("range");
    expect(validateValidUntil("2026-10-20", today)).toBeNull();
    expect(validateValidUntil("2031-10-19", today)).toBeNull();
  });
});
