import { QueryClient, QueryObserver, type InfiniteData } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import {
  makeAnalysis,
  makeDetail,
  makeIncident,
  makeIncidentDetail,
  makeOrgDetail,
  makeQueueCertificate,
  makeReport,
  makeStaffOrg,
} from "../test/fixtures";
import { DEFAULT_FILTERS } from "./filters";
import { DEFAULT_ORG_FILTERS } from "./orgs";
import { applyLiveEvent, listKey, mapKey } from "./liveCache";
import { queryKeys } from "./staffApi";
import type {
  IncidentDetail,
  IncidentSummary,
  OrgMapCollection,
  Page,
  QueueCertificate,
  StaffOrg,
  StaffOrgDetail,
  StaffReport,
  StaffReportDetail,
} from "./types";

type Data = InfiniteData<Page<StaffReport>, string | null>;
const page = (items: StaffReport[]): Data => ({ pages: [{ items, next_cursor: null }], pageParams: [null] });
type IData = InfiniteData<Page<IncidentSummary>, string | null>;
const ipage = (items: IncidentSummary[]): IData => ({ pages: [{ items, next_cursor: null }], pageParams: [null] });

describe("applyLiveEvent", () => {
  it("prepends created reports only to lists whose filters match", () => {
    const qc = new QueryClient();
    const existing = makeReport({ id: "old" });
    const fireKey = listKey({ ...DEFAULT_FILTERS, categories: ["fire"] });
    const floodKey = listKey({ ...DEFAULT_FILTERS, categories: ["flood"] });
    qc.setQueryData(fireKey, page([existing]));
    qc.setQueryData(floodKey, page([]));

    applyLiveEvent(qc, { type: "report.created", report: makeReport({ id: "new", category: "fire" }) });

    expect(qc.getQueryData<Data>(fireKey)?.pages[0]?.items.map((r) => r.id)).toEqual(["new", "old"]);
    expect(qc.getQueryData<Data>(floodKey)?.pages[0]?.items).toEqual([]);
  });

  it("does not duplicate a report already listed", () => {
    const qc = new QueryClient();
    const key = listKey(DEFAULT_FILTERS);
    qc.setQueryData(key, page([makeReport({ id: "a" })]));
    applyLiveEvent(qc, { type: "report.created", report: makeReport({ id: "a" }) });
    expect(qc.getQueryData<Data>(key)?.pages[0]?.items).toHaveLength(1);
  });

  it("updates status in lists and drops rows that no longer match", () => {
    const qc = new QueryClient();
    const all = listKey(DEFAULT_FILTERS);
    const receivedOnly = listKey({ ...DEFAULT_FILTERS, statuses: ["received"] });
    qc.setQueryData(all, page([makeReport({ id: "a" })]));
    qc.setQueryData(receivedOnly, page([makeReport({ id: "a" })]));
    applyLiveEvent(qc, { type: "report.status_changed", report: makeReport({ id: "a", status: "in_progress" }) });
    expect(qc.getQueryData<Data>(all)?.pages[0]?.items[0]?.status).toBe("in_progress");
    expect(qc.getQueryData<Data>(receivedOnly)?.pages[0]?.items).toEqual([]);
  });

  it("adds reports to map queries only inside their bbox", () => {
    const qc = new QueryClient();
    const sfax = mapKey(DEFAULT_FILTERS, [10, 34, 11, 35]);
    const north = mapKey(DEFAULT_FILTERS, [8, 36, 9, 37]);
    qc.setQueryData(sfax, page([]));
    qc.setQueryData(north, page([]));
    applyLiveEvent(qc, { type: "report.created", report: makeReport({ id: "x" }) });
    expect(qc.getQueryData<Data>(sfax)?.pages[0]?.items).toHaveLength(1);
    expect(qc.getQueryData<Data>(north)?.pages[0]?.items).toHaveLength(0);
  });

  it("patches a cached detail while keeping history, media and reporter", () => {
    const qc = new QueryClient();
    const detail = makeDetail({ id: "d" });
    qc.setQueryData(queryKeys.report("d"), detail);
    applyLiveEvent(qc, { type: "report.status_changed", report: makeReport({ id: "d", status: "in_progress" }) });
    const after = qc.getQueryData<StaffReportDetail>(queryKeys.report("d"));
    expect(after?.status).toBe("in_progress");
    expect(after?.allowed_transitions).toEqual(["intervened", "ongoing", "closed", "rejected"]);
    expect(after?.media).toBe(detail.media);
    expect(after?.reporter).toBe(detail.reporter);
  });

  it("invalidates the detail on media.stored", () => {
    const qc = new QueryClient();
    qc.setQueryData(queryKeys.report("d"), makeDetail({ id: "d" }));
    applyLiveEvent(qc, {
      type: "media.stored",
      report_id: "d",
      media: { id: "m2", kind: "video", bytes: 1, sha256: "b", status: "stored" },
    });
    expect(qc.getQueryState(queryKeys.report("d"))?.isInvalidated).toBe(true);
  });
});

describe("applyLiveEvent — report.enriched (phase 3)", () => {
  it("merges new scores and markers into lists without inserting unknown reports", () => {
    const qc = new QueryClient();
    const key = listKey(DEFAULT_FILTERS);
    qc.setQueryData(key, page([makeReport({ id: "a", priority_score: null, analysis_state: "pending" })]));
    applyLiveEvent(qc, {
      type: "report.enriched",
      report: makeReport({ id: "a", priority_score: 82, analysis_state: "done", lives_at_risk: true, text_ar: "نص" }),
    });
    applyLiveEvent(qc, { type: "report.enriched", report: makeReport({ id: "unknown" }) });
    const items = qc.getQueryData<Data>(key)?.pages[0]?.items;
    expect(items).toHaveLength(1);
    expect(items?.[0]).toMatchObject({ priority_score: 82, analysis_state: "done", lives_at_risk: true, text_ar: "نص" });
  });

  it("re-ranks priority-sorted lists and inserts created reports at their rank", () => {
    const qc = new QueryClient();
    const key = listKey(DEFAULT_FILTERS, "priority");
    const t0 = "2026-10-19T10:00:00Z";
    qc.setQueryData(
      key,
      page([
        makeReport({ id: "hi", priority_score: 90, received_at: t0 }),
        makeReport({ id: "mid", priority_score: 50, received_at: t0 }),
        makeReport({ id: "lo", priority_score: 20, received_at: t0 }),
      ]),
    );
    applyLiveEvent(qc, { type: "report.enriched", report: makeReport({ id: "lo", priority_score: 95, received_at: t0 }) });
    applyLiveEvent(qc, { type: "report.created", report: makeReport({ id: "new", priority_score: 60 }) });
    expect(qc.getQueryData<Data>(key)?.pages[0]?.items.map((r) => r.id)).toEqual(["lo", "hi", "new", "mid"]);
  });

  it("patches the cached detail, keeps its analysis until the refetch, and invalidates it", () => {
    const qc = new QueryClient();
    const detail = makeDetail({ id: "d", analysis: makeAnalysis() });
    qc.setQueryData(queryKeys.report("d"), detail);
    applyLiveEvent(qc, {
      type: "report.enriched",
      report: makeReport({ id: "d", priority_score: 91, has_suggestion: true, incident_id: null }),
    });
    const after = qc.getQueryData<StaffReportDetail>(queryKeys.report("d"));
    expect(after?.priority_score).toBe(91);
    expect(after?.has_suggestion).toBe(true);
    expect(after?.analysis).toBe(detail.analysis);
    expect(after?.history).toBe(detail.history);
    expect(qc.getQueryState(queryKeys.report("d"))?.isInvalidated).toBe(true);
  });

  it("keeps cached incident member lists in line with the report's incident", () => {
    const qc = new QueryClient();
    qc.setQueryData(queryKeys.incident("i-1"), makeIncidentDetail({ id: "i-1" }));
    qc.setQueryData(queryKeys.incident("i-2"), makeIncidentDetail({ id: "i-2", reports: [] }));
    // r-2 moves from i-1 to i-2.
    applyLiveEvent(qc, { type: "report.enriched", report: makeReport({ id: "r-2", incident_id: "i-2" }) });
    expect(qc.getQueryData<IncidentDetail>(queryKeys.incident("i-1"))?.reports.map((r) => r.id)).toEqual(["r-1"]);
    expect(qc.getQueryState(queryKeys.incident("i-1"))?.isInvalidated).toBe(true);
    expect(qc.getQueryState(queryKeys.incident("i-2"))?.isInvalidated).toBe(true);
    // A member's new score is patched in place.
    applyLiveEvent(qc, { type: "report.enriched", report: makeReport({ id: "r-1", incident_id: "i-1", priority_score: 99 }) });
    expect(qc.getQueryData<IncidentDetail>(queryKeys.incident("i-1"))?.reports[0]?.priority_score).toBe(99);
  });
});

describe("applyLiveEvent — incident.updated (phase 3)", () => {
  it("moves an updated incident to the top of matching lists and removes it from others", () => {
    const qc = new QueryClient();
    const open = queryKeys.incidents("open");
    const closed = queryKeys.incidents("closed");
    const all = queryKeys.incidents("all");
    qc.setQueryData(open, ipage([makeIncident({ id: "x" }), makeIncident({ id: "i-1" })]));
    qc.setQueryData(closed, ipage([]));
    qc.setQueryData(all, ipage([makeIncident({ id: "x" }), makeIncident({ id: "i-1" })]));

    applyLiveEvent(qc, { type: "incident.updated", incident: makeIncident({ id: "i-1", report_count: 5 }) });
    expect(qc.getQueryData<IData>(open)?.pages[0]?.items.map((i) => [i.id, i.report_count])).toEqual([
      ["i-1", 5],
      ["x", 2],
    ]);

    applyLiveEvent(qc, { type: "incident.updated", incident: makeIncident({ id: "i-1", status: "closed" }) });
    expect(qc.getQueryData<IData>(open)?.pages[0]?.items.map((i) => i.id)).toEqual(["x"]);
    expect(qc.getQueryData<IData>(closed)?.pages[0]?.items.map((i) => i.id)).toEqual(["i-1"]);
    expect(qc.getQueryData<IData>(all)?.pages[0]?.items.map((i) => [i.id, i.status])).toEqual([
      ["i-1", "closed"],
      ["x", "open"],
    ]);
  });

  it("patches a cached incident detail, keeps members and timeline, and invalidates it", () => {
    const qc = new QueryClient();
    const detail = makeIncidentDetail();
    qc.setQueryData(queryKeys.incident("i-1"), detail);
    applyLiveEvent(qc, { type: "incident.updated", incident: makeIncident({ severity: 95, reporter_count: 3 }) });
    const after = qc.getQueryData<IncidentDetail>(queryKeys.incident("i-1"));
    expect(after).toMatchObject({ severity: 95, reporter_count: 3 });
    expect(after?.reports).toBe(detail.reports);
    expect(after?.timeline).toBe(detail.timeline);
    expect(qc.getQueryState(queryKeys.incident("i-1"))?.isInvalidated).toBe(true);
  });
});

describe("applyLiveEvent — org.updated (phase 4)", () => {
  type OData = InfiniteData<Page<StaffOrg>, string | null>;
  const opage = (items: StaffOrg[], next: string | null = null): OData => ({
    pages: [{ items, next_cursor: next }],
    pageParams: [null],
  });

  it("re-places an institution by name in matching lists and drops it from the others", () => {
    const qc = new QueryClient();
    const all = queryKeys.orgs(DEFAULT_ORG_FILTERS);
    const pending = queryKeys.orgs({ ...DEFAULT_ORG_FILTERS, status: "pending_review" });
    qc.setQueryData(all, opage([makeStaffOrg({ id: "a", name: "Alpha" }), makeStaffOrg({ id: "z", name: "Zeta" })]));
    qc.setQueryData(pending, opage([makeStaffOrg({ id: "m", name: "Mu", status: "pending_review" })]));

    // A new registration (pending) appears in both, at its rank.
    applyLiveEvent(qc, { type: "org.updated", org: makeStaffOrg({ id: "n", name: "Nova", status: "pending_review" }) });
    expect(qc.getQueryData<OData>(all)?.pages[0]?.items.map((o) => o.id)).toEqual(["a", "n", "z"]);
    expect(qc.getQueryData<OData>(pending)?.pages[0]?.items.map((o) => o.id)).toEqual(["m", "n"]);

    // Approved: leaves the pending list, stays (updated) in the full list.
    applyLiveEvent(qc, { type: "org.updated", org: makeStaffOrg({ id: "n", name: "Nova", status: "active" }) });
    expect(qc.getQueryData<OData>(pending)?.pages[0]?.items.map((o) => o.id)).toEqual(["m"]);
    expect(qc.getQueryData<OData>(all)?.pages[0]?.items.find((o) => o.id === "n")?.status).toBe("active");
  });

  it("does not append past the loaded range when more pages exist", () => {
    const qc = new QueryClient();
    const all = queryKeys.orgs(DEFAULT_ORG_FILTERS);
    qc.setQueryData(all, opage([makeStaffOrg({ id: "a", name: "Alpha" })], "next"));
    applyLiveEvent(qc, { type: "org.updated", org: makeStaffOrg({ id: "y", name: "Yankee" }) });
    expect(qc.getQueryData<OData>(all)?.pages[0]?.items.map((o) => o.id)).toEqual(["a"]);
  });

  it("patches a cached detail but refetches it only when it is on screen (audited endpoint)", async () => {
    const qc = new QueryClient();
    const fetchActive = vi.fn(() => Promise.resolve(makeOrgDetail({ id: "o-1", status: "active" })));
    const fetchIdle = vi.fn(() => Promise.resolve(makeOrgDetail({ id: "o-2" })));
    // o-1 has an observer (the open detail page); o-2 is only cached.
    const observer = new QueryObserver(qc, { queryKey: queryKeys.org("o-1"), queryFn: fetchActive, staleTime: Infinity });
    const unsubscribe = observer.subscribe(() => undefined);
    await vi.waitFor(() => expect(qc.getQueryData(queryKeys.org("o-1"))).toBeDefined());
    qc.setQueryData(queryKeys.org("o-2"), makeOrgDetail({ id: "o-2", team: [] }));

    applyLiveEvent(qc, { type: "org.updated", org: makeStaffOrg({ id: "o-1", status: "suspended" }) });
    applyLiveEvent(qc, { type: "org.updated", org: makeStaffOrg({ id: "o-2", name: "Renamed", status: "suspended" }) });

    const idle = qc.getQueryData<StaffOrgDetail>(queryKeys.org("o-2"));
    expect(idle).toMatchObject({ name: "Renamed", status: "suspended", team: [] });
    expect(qc.getQueryState(queryKeys.org("o-2"))?.isInvalidated).toBe(true);
    await vi.waitFor(() => expect(fetchActive).toHaveBeenCalledTimes(2));
    expect(fetchIdle).not.toHaveBeenCalled();
    unsubscribe();
  });

  it("upserts active institutions in the map layer and removes suspended ones", () => {
    const qc = new QueryClient();
    const key = queryKeys.orgsMap([10, 34, 11, 35]);
    const elsewhere = queryKeys.orgsMap([8, 36, 9, 37]);
    qc.setQueryData<OrgMapCollection>(key, { type: "FeatureCollection", features: [] });
    qc.setQueryData<OrgMapCollection>(elsewhere, { type: "FeatureCollection", features: [] });
    applyLiveEvent(qc, { type: "org.updated", org: makeStaffOrg({ id: "o-1", hazmat_count: 3 }) });
    const f = qc.getQueryData<OrgMapCollection>(key)?.features;
    expect(f).toHaveLength(1);
    expect(f?.[0]?.properties).toMatchObject({ id: "o-1", hazmat_count: 3, family: "industrial" });
    expect(qc.getQueryData<OrgMapCollection>(elsewhere)?.features).toHaveLength(0);
    applyLiveEvent(qc, { type: "org.updated", org: makeStaffOrg({ id: "o-1", status: "suspended" }) });
    expect(qc.getQueryData<OrgMapCollection>(key)?.features).toHaveLength(0);
  });
});

describe("applyLiveEvent — certificate.updated (phase 4)", () => {
  type QData = InfiniteData<Page<QueueCertificate>, string | null>;
  const cert = (status: QueueCertificate["status"]) => ({
    id: "c-1",
    code: "EHC-26-61-000123",
    status,
    org_id: "o-1",
    org_name: "Société Chimique du Sud",
    gouvernorat_code: 61,
  });

  it("removes a reviewed certificate from the queue and reloads the queue for a new submission", () => {
    const qc = new QueryClient();
    const key = queryKeys.certificates("submitted");
    qc.setQueryData<QData>(key, {
      pages: [{ items: [makeQueueCertificate(), makeQueueCertificate({ id: "c-2" })], next_cursor: null }],
      pageParams: [null],
    });
    applyLiveEvent(qc, { type: "certificate.updated", certificate: cert("approved") });
    expect(qc.getQueryData<QData>(key)?.pages[0]?.items.map((c) => c.id)).toEqual(["c-2"]);
    expect(qc.getQueryState(key)?.isInvalidated).toBe(false);

    applyLiveEvent(qc, { type: "certificate.updated", certificate: { ...cert("submitted"), id: "c-3" } });
    expect(qc.getQueryState(key)?.isInvalidated).toBe(true);
  });

  it("patches the institution's cached detail and lists showing it", () => {
    const qc = new QueryClient();
    qc.setQueryData(queryKeys.org("o-1"), makeOrgDetail());
    const listKey = queryKeys.orgs(DEFAULT_ORG_FILTERS);
    const otherKey = queryKeys.orgs({ ...DEFAULT_ORG_FILTERS, kind: "tourism" });
    qc.setQueryData(listKey, { pages: [{ items: [makeStaffOrg()], next_cursor: null }], pageParams: [null] });
    qc.setQueryData(otherKey, { pages: [{ items: [], next_cursor: null }], pageParams: [null] });

    applyLiveEvent(qc, { type: "certificate.updated", certificate: cert("rejected") });
    expect(qc.getQueryData<StaffOrgDetail>(queryKeys.org("o-1"))?.certificates[0]?.status).toBe("rejected");
    expect(qc.getQueryState(queryKeys.org("o-1"))?.isInvalidated).toBe(true);
    expect(qc.getQueryState(listKey)?.isInvalidated).toBe(true);
    expect(qc.getQueryState(otherKey)?.isInvalidated).toBe(false);
  });
});

describe("applyLiveEvent — reports of an institution (phase 4)", () => {
  it("adds a new report made on behalf of an institution to its reports list", () => {
    const qc = new QueryClient();
    const key = queryKeys.orgReports("o-1");
    qc.setQueryData(key, page([makeReport({ id: "old", organization: { id: "o-1", name: "X" } })]));
    applyLiveEvent(qc, {
      type: "report.created",
      report: makeReport({ id: "new", organization: { id: "o-1", name: "X", kind: "industrial" } }),
    });
    applyLiveEvent(qc, { type: "report.created", report: makeReport({ id: "other" }) });
    expect(qc.getQueryData<Data>(key)?.pages[0]?.items.map((r) => r.id)).toEqual(["new", "old"]);
  });
});
