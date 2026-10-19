import { describe, expect, it, vi } from "vitest";
import { AI_SETTINGS } from "../test/fixtures";
import { createApiClient } from "./api";
import { DEFAULT_FILTERS } from "./filters";
import { DEFAULT_ORG_FILTERS } from "./orgs";
import { queryKeys, staffApi } from "./staffApi";

function setup(body: unknown = {}, status = 200) {
  const fetchImpl = vi.fn((_url: RequestInfo | URL, _init?: RequestInit) =>
    Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })),
  );
  const api = staffApi(createApiClient("http://api", { getAccessToken: () => "t", renew: () => Promise.resolve(null) }, fetchImpl));
  const call = (i = 0) => {
    const c = fetchImpl.mock.calls[i];
    const body = c?.[1]?.body;
    const raw = c?.[0];
    return {
      url: new URL(typeof raw === "string" ? raw : raw instanceof URL ? raw.href : (raw?.url ?? "")),
      method: c?.[1]?.method,
      body: typeof body === "string" ? (JSON.parse(body) as unknown) : undefined,
    };
  };
  return { api, call };
}

describe("staffApi (phase 3)", () => {
  it("lists reports by priority and by incident; the default sort sends no parameter", async () => {
    const { api, call } = setup({ items: [], next_cursor: null });
    await api.reports(DEFAULT_FILTERS, { sort: "priority", incidentId: "i-1", cursor: "c1" });
    expect(call().url.pathname).toBe("/api/v1/staff/reports");
    expect(call().url.searchParams.get("sort")).toBe("priority");
    expect(call().url.searchParams.get("incident_id")).toBe("i-1");
    expect(call().url.searchParams.get("cursor")).toBe("c1");

    await api.reports(DEFAULT_FILTERS);
    expect(call(1).url.searchParams.has("sort")).toBe(false);
    expect(call(1).url.searchParams.has("incident_id")).toBe(false);
  });

  it("lists incidents (default status open) and reads one", async () => {
    const { api, call } = setup({ items: [], next_cursor: null });
    await api.incidents();
    expect(call().url.pathname).toBe("/api/v1/staff/incidents");
    expect(call().url.searchParams.get("status")).toBe("open");
    expect(call().url.searchParams.get("limit")).toBe("50");
    await api.incidents({ status: "all", cursor: "n" });
    expect(call(1).url.searchParams.get("status")).toBe("all");
    expect(call(1).url.searchParams.get("cursor")).toBe("n");
    await api.incident("i/1");
    expect(call(2).url.pathname).toBe("/api/v1/staff/incidents/i%2F1");
  });

  it("links, detaches and dismisses with the contract's methods and bodies", async () => {
    const { api, call } = setup();
    await api.linkIncident("r1", { action: "accept_suggestion" });
    expect(call(0)).toMatchObject({ method: "POST", body: { action: "accept_suggestion" } });
    expect(call(0).url.pathname).toBe("/api/v1/staff/reports/r1/incident");
    await api.linkIncident("r1", { action: "link", incident_id: "i-2" });
    expect(call(1).body).toEqual({ action: "link", incident_id: "i-2" });
    await api.linkIncident("r1", { action: "new" });
    expect(call(2).body).toEqual({ action: "new" });
    await api.detachIncident("r1");
    expect(call(3)).toMatchObject({ method: "DELETE", body: undefined });
    expect(call(3).url.pathname).toBe("/api/v1/staff/reports/r1/incident");
    await api.dismissSuggestion("r1");
    expect(call(4).method).toBe("POST");
    expect(call(4).url.pathname).toBe("/api/v1/staff/reports/r1/suggestion/dismiss");
  });

  it("merges another incident into the target", async () => {
    const { api, call } = setup();
    await api.mergeIncident("target", "other");
    expect(call().url.pathname).toBe("/api/v1/staff/incidents/target/merge");
    expect(call()).toMatchObject({ method: "POST", body: { incident_id: "other" } });
  });

  it("reads and writes AI settings and reads the AI status", async () => {
    const { api, call } = setup(AI_SETTINGS);
    await expect(api.aiSettings()).resolves.toEqual(AI_SETTINGS);
    expect(call(0)).toMatchObject({ method: "GET" });
    expect(call(0).url.pathname).toBe("/api/v1/staff/ai/settings");
    await api.saveAiSettings(AI_SETTINGS);
    expect(call(1)).toMatchObject({ method: "PUT", body: AI_SETTINGS });
    await api.aiStatus();
    expect(call(2).url.pathname).toBe("/api/v1/staff/ai/status");
  });

  it("maps the phase 3 error codes", async () => {
    const { api } = setup({ detail: "national_scope_required" }, 403);
    await expect(api.saveAiSettings(AI_SETTINGS)).rejects.toMatchObject({ status: 403, code: "national_scope_required" });
    const conflict = setup({ detail: "suggestion_outdated" }, 409);
    await expect(conflict.api.linkIncident("r", { action: "accept_suggestion" })).rejects.toMatchObject({
      code: "suggestion_outdated",
    });
  });
});

describe("staffApi (phase 4 institutions)", () => {
  it("lists institutions with the contract's filters, as strings, and the cursor", async () => {
    const { api, call } = setup({ items: [], next_cursor: null });
    await api.orgs(
      { status: "pending_review", kind: "hotel", gouvernorat: 61, certificate: "expired", hasHazmat: false, q: " Sfax " },
      { cursor: "c2" },
    );
    const p = call().url.searchParams;
    expect(call().url.pathname).toBe("/api/v1/staff/orgs");
    expect(Object.fromEntries(p)).toEqual({
      status: "pending_review",
      kind: "hotel",
      gouvernorat_code: "61",
      certificate: "expired",
      has_hazmat: "false",
      q: "Sfax",
      limit: "50",
      cursor: "c2",
    });
    await api.orgs(DEFAULT_ORG_FILTERS);
    expect(Object.fromEntries(call(1).url.searchParams)).toEqual({ limit: "50" });
  });

  it("reads a detail, its reports and pre-signed links on the staff paths", async () => {
    const { api, call } = setup({ items: [], next_cursor: null });
    await api.org("o/1");
    expect(call(0).url.pathname).toBe("/api/v1/staff/orgs/o%2F1");
    await api.orgReports("o-1", { cursor: "n" });
    expect(call(1).url.pathname).toBe("/api/v1/staff/orgs/o-1/reports");
    expect(call(1).url.searchParams.get("cursor")).toBe("n");
    await api.orgDocumentDownload("o-1", "d-1", 3);
    expect(call(2).url.pathname).toBe("/api/v1/staff/orgs/o-1/documents/d-1/versions/3/download");
    await api.certificatePdf("o-1", "c-1");
    expect(call(3).url.pathname).toBe("/api/v1/staff/orgs/o-1/certificates/c-1/pdf");
    await api.orgDocumentVersions("o-1", "d-1");
    expect(call(4).url.pathname).toBe("/api/v1/staff/orgs/o-1/documents/d-1/versions");
  });

  it("fetches the map layer by bbox (minLon,minLat,maxLon,maxLat)", async () => {
    const { api, call } = setup({ type: "FeatureCollection", features: [] });
    await api.orgsMap([10.1, 34.2, 11, 35]);
    expect(call().url.pathname).toBe("/api/v1/staff/orgs/map");
    expect(call().url.searchParams.get("bbox")).toBe("10.10000,34.20000,11.00000,35.00000");
  });

  it("posts registration and certificate reviews with the contract's bodies", async () => {
    const { api, call } = setup({});
    await api.reviewOrg("o-1", { decision: "reject", reason: "  Identifiant invalide " });
    expect(call(0)).toMatchObject({ method: "POST", body: { decision: "reject", reason: "Identifiant invalide" } });
    expect(call(0).url.pathname).toBe("/api/v1/staff/orgs/o-1/review");
    await api.reviewOrg("o-1", { decision: "approve", reason: "  " });
    expect(call(1).body).toEqual({ decision: "approve" });
    await api.reviewCertificate("c-1", { decision: "approve", valid_until: "2027-10-19" });
    expect(call(2)).toMatchObject({ method: "POST", body: { decision: "approve", valid_until: "2027-10-19" } });
    expect(call(2).url.pathname).toBe("/api/v1/staff/certificates/c-1/review");
  });

  it("reads the certificate queue (status submitted by default)", async () => {
    const { api, call } = setup({ items: [], next_cursor: null });
    await api.certificates();
    expect(call().url.pathname).toBe("/api/v1/staff/certificates");
    expect(call().url.searchParams.get("status")).toBe("submitted");
    expect(call().url.searchParams.get("limit")).toBe("50");
  });

  it("maps the phase 4 error codes", async () => {
    for (const [status, code] of [
      [422, "reason_required"],
      [422, "invalid_valid_until"],
      [403, "insufficient_role"],
      [404, "org_not_found"],
    ] as const) {
      const { api } = setup({ detail: code }, status);
      await expect(api.reviewOrg("o", { decision: "reject" })).rejects.toMatchObject({ status, code });
    }
  });

  it("keeps detail ('org') and list ('orgs') query keys apart, lists keyed by normalized filters", () => {
    expect(queryKeys.org("o-1")).toEqual(["org", "o-1"]);
    expect(queryKeys.orgs({ ...DEFAULT_ORG_FILTERS, q: " x " })).toEqual(["orgs", { ...DEFAULT_ORG_FILTERS, q: "x" }]);
    expect(queryKeys.orgsMap([10.12345, 34.2, 11, 35])).toEqual(["orgs-map", [10.123, 34.2, 11, 35]]);
    expect(queryKeys.certificates("submitted")).toEqual(["certificates", "submitted"]);
    expect(queryKeys.orgReports("o-1")).toEqual(["org-reports", "o-1"]);
  });
});
