import { QueryClient, type InfiniteData } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { makeDetail, makeReport } from "../test/fixtures";
import { DEFAULT_FILTERS } from "./filters";
import { applyLiveEvent, listKey, mapKey } from "./liveCache";
import { queryKeys } from "./staffApi";
import type { Page, StaffReport, StaffReportDetail } from "./types";

type Data = InfiniteData<Page<StaffReport>, string | null>;
const page = (items: StaffReport[]): Data => ({ pages: [{ items, next_cursor: null }], pageParams: [null] });

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
