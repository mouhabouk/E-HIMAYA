import type { InfiniteData, QueryClient } from "@tanstack/react-query";
import type { StreamLiveEvent } from "./live";
import { queryKeys } from "./staffApi";
import { streamKeys } from "./streamsApi";
import type { StaffStream, StaffStreamDetail, StreamStatusFilter } from "./streamTypes";
import type { Page } from "./types";

type StreamsData = InfiniteData<Page<StaffStream>, string | null>;

/** Does a stream belong in a list with this status filter and gouvernorat? */
export function streamMatches(stream: StaffStream, status: StreamStatusFilter, gouvernorat: number | null): boolean {
  if (gouvernorat !== null && stream.gouvernorat_code !== gouvernorat) return false;
  if (status === "all") return true;
  if (status === "live") return stream.status === "live";
  return stream.status === "ended" || stream.status === "expired";
}

/** Apply `patch` to the stream wherever it is listed; returns the same object when nothing changed. */
export function patchStreamInPages(
  data: StreamsData | undefined,
  id: string,
  patch: (s: StaffStream) => StaffStream,
): StreamsData | undefined {
  if (!data || !Array.isArray(data.pages)) return data;
  if (!data.pages.some((page) => page.items.some((s) => s.id === id))) return data;
  const pages = data.pages.map((page) =>
    page.items.some((s) => s.id === id) ? { ...page, items: page.items.map((s) => (s.id === id ? patch(s) : s)) } : page,
  );
  return { ...data, pages };
}

/** Newest first: a started stream goes on top of the first page; a stream that no longer matches is removed. */
export function upsertStreamInPages(data: StreamsData | undefined, stream: StaffStream, matches: boolean): StreamsData | undefined {
  if (!data || !Array.isArray(data.pages) || data.pages.length === 0) return data;
  const listed = data.pages.some((p) => p.items.some((s) => s.id === stream.id));
  if (listed) {
    const pages = data.pages.map((p) => ({
      ...p,
      items: matches ? p.items.map((s) => (s.id === stream.id ? { ...s, ...stream } : s)) : p.items.filter((s) => s.id !== stream.id),
    }));
    return { ...data, pages };
  }
  const [first, ...rest] = data.pages;
  if (!matches || !first) return data;
  return { ...data, pages: [{ ...first, items: [stream, ...first.items] }, ...rest] };
}

function forEachList(qc: QueryClient, fn: (key: readonly unknown[], data: StreamsData | undefined, status: StreamStatusFilter, gouvernorat: number | null) => void) {
  for (const [key, data] of qc.getQueriesData<StreamsData>({ queryKey: streamKeys.listsAll })) {
    const status = key[1];
    const gouvernorat = key[2];
    if (status !== "live" && status !== "ended" && status !== "all") continue;
    fn(key, data, status, typeof gouvernorat === "number" ? gouvernorat : null);
  }
}

/** Any cached copy of a stream (list row or detail), e.g. to name it in an alert. */
export function findCachedStream(qc: QueryClient, id: string): StaffStream | null {
  const detail = qc.getQueryData<StaffStreamDetail>(streamKeys.detail(id));
  if (detail) return detail;
  for (const [, data] of qc.getQueriesData<StreamsData>({ queryKey: streamKeys.listsAll })) {
    for (const page of data?.pages ?? []) {
      const found = page.items.find((s) => s.id === id);
      if (found) return found;
    }
  }
  return null;
}

const maxOf = (a: number | null, b: number) => (a === null ? b : Math.max(a, b));

/**
 * Phase 6 live events (§4) → react-query caches: the live list, the archive, the wall and the stream detail.
 * Started/ended rows are patched in place when the event carries the row, otherwise the lists are reloaded.
 */
export function applyStreamEvent(qc: QueryClient, event: StreamLiveEvent): void {
  const id = event.stream_id;
  const detailKey = streamKeys.detail(id);
  switch (event.type) {
    case "stream.started":
    case "stream.ended": {
      const row = event.stream;
      if (row) {
        forEachList(qc, (key, data, status, gouvernorat) =>
          qc.setQueryData<StreamsData>(key, upsertStreamInPages(data, row, streamMatches(row, status, gouvernorat))),
        );
        // The archive is ordered by the server (and shows durations): reload it when a stream ends.
        if (event.type === "stream.ended") {
          forEachList(qc, (key, _data, status) => {
            if (status !== "live") void qc.invalidateQueries({ queryKey: key, exact: true });
          });
        }
      } else {
        void qc.invalidateQueries({ queryKey: streamKeys.listsAll });
      }
      const detail = qc.getQueryData<StaffStreamDetail>(detailKey);
      if (detail) {
        if (row) qc.setQueryData<StaffStreamDetail>(detailKey, { ...detail, ...row, recordings: detail.recordings, detections: detail.detections, track: detail.track });
        else if (event.type === "stream.ended") qc.setQueryData<StaffStreamDetail>(detailKey, { ...detail, status: "ended" });
        void qc.invalidateQueries({ queryKey: detailKey, exact: true });
      }
      return;
    }
    case "stream.location": {
      const location = { lat: event.lat, lon: event.lon };
      forEachList(qc, (key, data) =>
        qc.setQueryData<StreamsData>(key, patchStreamInPages(data, id, (s) => ({ ...s, last_location: location }))),
      );
      qc.setQueryData<StaffStreamDetail>(detailKey, (detail) =>
        detail
          ? {
              ...detail,
              last_location: location,
              track: [...detail.track, { at: event.at ?? new Date().toISOString(), lat: event.lat, lon: event.lon }],
            }
          : detail,
      );
      return;
    }
    case "stream.alert": {
      const field = event.label === "fire" ? "max_fire_confidence" : "max_smoke_confidence";
      const raise = (s: StaffStream): StaffStream => ({ ...s, [field]: maxOf(s[field], event.confidence) });
      forEachList(qc, (key, data) => qc.setQueryData<StreamsData>(key, patchStreamInPages(data, id, raise)));
      qc.setQueryData<StaffStreamDetail>(detailKey, (detail) => (detail ? raise(detail) as StaffStreamDetail : detail));
      // The alert carries no boxes: the detail (detections with boxes) is reloaded by the screens showing it.
      void qc.invalidateQueries({ queryKey: detailKey, exact: true });
      // The report's priority was raised and a vision frame stored on it (§3).
      if (event.report_id) void qc.invalidateQueries({ queryKey: queryKeys.report(event.report_id), exact: true });
      return;
    }
    case "stream.recording": {
      forEachList(qc, (key, data) =>
        qc.setQueryData<StreamsData>(key, patchStreamInPages(data, id, (s) => ({ ...s, recordings_count: s.recordings_count + 1 }))),
      );
      void qc.invalidateQueries({ queryKey: detailKey, exact: true });
      const reportId = event.report_id ?? findCachedStream(qc, id)?.report_id;
      if (reportId) void qc.invalidateQueries({ queryKey: queryKeys.report(reportId), exact: true });
      return;
    }
  }
}
