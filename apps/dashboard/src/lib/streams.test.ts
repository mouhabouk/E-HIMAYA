import { QueryClient, type InfiniteData } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { makeStream, makeStreamDetail } from "../test/streamFixtures";
import { createApiClient } from "./api";
import { boxRect, confidenceBand, containRect, latestFrame, strongestByLabel } from "./detections";
import { FakeWebSocket } from "../test/FakeWebSocket";
import { LiveClient, parseStreamEvent, type LiveEvent } from "./live";
import { applyLiveEvent } from "./liveCache";
import { queryKeys } from "./staffApi";
import { streamKeys, streamsApi } from "./streamsApi";
import { applyStreamEvent, findCachedStream, streamMatches } from "./streamsCache";
import type { StaffStream, StaffStreamDetail } from "./streamTypes";
import type { Page } from "./types";
import { arrangeWall, byDanger, loadWall, pinStream, pinToFreeTile, saveWall } from "./wall";
import { matchesArchiveFilters } from "../pages/StreamArchivePage";

type Data = InfiniteData<Page<StaffStream>, string | null>;
const pages = (...items: StaffStream[][]): Data => ({
  pages: items.map((list, i) => ({ items: list, next_cursor: i < items.length - 1 ? `c${i}` : null })),
  pageParams: items.map((_, i) => (i === 0 ? null : `c${i - 1}`)),
});
const ids = (d: Data | undefined) => d?.pages.flatMap((p) => p.items.map((s) => s.id));

describe("parseStreamEvent (phase 6 §4 live events)", () => {
  it("accepts the alert and recording payloads of the contract", () => {
    expect(
      parseStreamEvent({ type: "stream.alert", stream_id: "s-1", label: "fire", confidence: 0.81, report_id: "r-1" }),
    ).toEqual({ type: "stream.alert", stream_id: "s-1", label: "fire", confidence: 0.81, report_id: "r-1" });
    expect(parseStreamEvent({ type: "stream.recording", stream_id: "s-1", media_id: "m-9" })).toEqual({
      type: "stream.recording",
      stream_id: "s-1",
      media_id: "m-9",
    });
  });

  it("keeps the supersets of the implementation notes (simulated, frame, time, report of a recording)", () => {
    expect(
      parseStreamEvent({
        type: "stream.alert",
        stream_id: "s-1",
        gouvernorat_code: 11,
        label: "smoke",
        confidence: 0.7,
        report_id: null,
        media_id: "m-frame",
        simulated: true,
        at: "2026-10-19T10:00:00Z",
      }),
    ).toEqual({
      type: "stream.alert",
      stream_id: "s-1",
      label: "smoke",
      confidence: 0.7,
      report_id: null,
      media_id: "m-frame",
      simulated: true,
      at: "2026-10-19T10:00:00Z",
    });
    expect(
      parseStreamEvent({ type: "stream.recording", stream_id: "s-1", media_id: "m-2", report_id: "r-1", sha256: "x", duration_s: 60 }),
    ).toEqual({ type: "stream.recording", stream_id: "s-1", media_id: "m-2", report_id: "r-1" });
  });

  it("accepts a stream row or a bare id for started/ended, and flat or nested locations", () => {
    const row = makeStream({ id: "s-2" });
    expect(parseStreamEvent({ type: "stream.started", stream: row })).toEqual({ type: "stream.started", stream_id: "s-2", stream: row });
    expect(parseStreamEvent({ type: "stream.ended", stream_id: "s-3" })).toEqual({ type: "stream.ended", stream_id: "s-3", stream: null });
    expect(parseStreamEvent({ type: "stream.location", stream_id: "s-1", lat: 36.8, lon: 10.18, at: "2026-10-19T10:00:00Z" })).toMatchObject({
      lat: 36.8,
      lon: 10.18,
      at: "2026-10-19T10:00:00Z",
    });
    expect(parseStreamEvent({ type: "stream.location", stream_id: "s-1", location: { lat: 1, lon: 2 } })).toMatchObject({ lat: 1, lon: 2, at: null });
  });

  it("drops malformed events (no id, person alerts, bad numbers)", () => {
    expect(parseStreamEvent({ type: "stream.started" })).toBeNull();
    expect(parseStreamEvent({ type: "stream.alert", stream_id: "s", label: "person", confidence: 0.9 })).toBeNull();
    expect(parseStreamEvent({ type: "stream.alert", stream_id: "s", label: "fire", confidence: "high" })).toBeNull();
    expect(parseStreamEvent({ type: "stream.location", stream_id: "s", lat: "36" })).toBeNull();
    expect(parseStreamEvent({ type: "stream.recording", stream_id: "s" })).toBeNull();
  });
});

describe("LiveClient with phase 6 events", () => {
  it("delivers normalised stream events and ignores invalid ones", () => {
    FakeWebSocket.reset();
    const events: LiveEvent[] = [];
    const client = new LiveClient({
      url: "ws://test",
      getToken: () => "t",
      renewToken: () => Promise.resolve("t"),
      onEvent: (e) => events.push(e),
      createSocket: (url) => new FakeWebSocket(url),
      pingIntervalMs: 0,
    });
    client.start();
    const ws = FakeWebSocket.last();
    ws.serverOpen();
    ws.serverSend({ type: "ready" });
    ws.serverSend({ type: "stream.alert", stream_id: "s-1", label: "smoke", confidence: 0.7, report_id: null, extra: 1 });
    ws.serverSend({ type: "stream.alert", stream_id: "s-1", label: "smoke" });
    ws.serverSend({ type: "stream.recording", stream_id: "s-1", media_id: "m-1" });
    expect(events).toEqual([
      { type: "stream.alert", stream_id: "s-1", label: "smoke", confidence: 0.7, report_id: null },
      { type: "stream.recording", stream_id: "s-1", media_id: "m-1" },
    ]);
    client.stop();
  });
});

describe("stream caches", () => {
  function client() {
    const qc = new QueryClient();
    const liveKey = streamKeys.list({ status: "live", gouvernorat: null });
    const sfaxKey = streamKeys.list({ status: "live", gouvernorat: 61 });
    const archiveKey = streamKeys.list({ status: "ended", gouvernorat: null });
    qc.setQueryData<Data>(liveKey, pages([makeStream({ id: "s-1" })]));
    qc.setQueryData<Data>(sfaxKey, pages([makeStream({ id: "s-1" })]));
    qc.setQueryData<Data>(archiveKey, pages([makeStream({ id: "s-0", status: "ended" })]));
    return { qc, liveKey, sfaxKey, archiveKey };
  }

  it("matches lists by status and gouvernorat", () => {
    const s = makeStream({ gouvernorat_code: 11 });
    expect(streamMatches(s, "live", null)).toBe(true);
    expect(streamMatches(s, "live", 61)).toBe(false);
    expect(streamMatches({ ...s, status: "ended" }, "ended", 11)).toBe(true);
    expect(streamMatches({ ...s, status: "expired" }, "ended", null)).toBe(true);
    expect(streamMatches(s, "ended", null)).toBe(false);
    expect(streamMatches(s, "all", null)).toBe(true);
  });

  it("puts a started stream on top of matching live lists only", () => {
    const { qc, liveKey, sfaxKey, archiveKey } = client();
    applyLiveEvent(qc, { type: "stream.started", stream_id: "s-9", stream: makeStream({ id: "s-9", gouvernorat_code: 11 }) });
    expect(ids(qc.getQueryData<Data>(liveKey))).toEqual(["s-9", "s-1"]);
    expect(ids(qc.getQueryData<Data>(sfaxKey))).toEqual(["s-1"]);
    expect(ids(qc.getQueryData<Data>(archiveKey))).toEqual(["s-0"]);
  });

  it("removes an ended stream from live lists, reloads the archive, and reloads lists for a bare id", () => {
    const { qc, liveKey, archiveKey } = client();
    const spy = vi.spyOn(qc, "invalidateQueries");
    applyStreamEvent(qc, { type: "stream.ended", stream_id: "s-1", stream: makeStream({ id: "s-1", status: "ended" }) });
    expect(ids(qc.getQueryData<Data>(liveKey))).toEqual([]);
    expect(spy).toHaveBeenCalledWith({ queryKey: archiveKey, exact: true });
    spy.mockClear();
    applyStreamEvent(qc, { type: "stream.ended", stream_id: "s-7", stream: null });
    expect(spy).toHaveBeenCalledWith({ queryKey: streamKeys.listsAll });
  });

  it("moves the position, appends to the track and raises confidences", () => {
    const { qc, liveKey } = client();
    qc.setQueryData<StaffStreamDetail>(streamKeys.detail("s-1"), makeStreamDetail({ id: "s-1", max_fire_confidence: 0.5 }));
    applyStreamEvent(qc, { type: "stream.location", stream_id: "s-1", lat: 35, lon: 10, at: "2026-10-19T10:00:00Z" });
    expect(qc.getQueryData<Data>(liveKey)?.pages[0]?.items[0]?.last_location).toEqual({ lat: 35, lon: 10 });
    const detail = qc.getQueryData<StaffStreamDetail>(streamKeys.detail("s-1"));
    expect(detail?.track.at(-1)).toEqual({ at: "2026-10-19T10:00:00Z", lat: 35, lon: 10 });

    const spy = vi.spyOn(qc, "invalidateQueries");
    applyStreamEvent(qc, { type: "stream.alert", stream_id: "s-1", label: "fire", confidence: 0.93, report_id: "r-1" });
    expect(qc.getQueryData<Data>(liveKey)?.pages[0]?.items[0]?.max_fire_confidence).toBe(0.93);
    expect(qc.getQueryData<StaffStreamDetail>(streamKeys.detail("s-1"))?.max_fire_confidence).toBe(0.93);
    // A weaker alert never lowers the maximum.
    applyStreamEvent(qc, { type: "stream.alert", stream_id: "s-1", label: "fire", confidence: 0.61, report_id: null });
    expect(qc.getQueryData<Data>(liveKey)?.pages[0]?.items[0]?.max_fire_confidence).toBe(0.93);
    expect(spy).toHaveBeenCalledWith({ queryKey: streamKeys.detail("s-1"), exact: true });
    expect(spy).toHaveBeenCalledWith({ queryKey: queryKeys.report("r-1"), exact: true });
  });

  it("counts a new recording and reloads the stream and its report", () => {
    const { qc, liveKey } = client();
    const spy = vi.spyOn(qc, "invalidateQueries");
    applyStreamEvent(qc, { type: "stream.recording", stream_id: "s-1", media_id: "m-2" });
    expect(qc.getQueryData<Data>(liveKey)?.pages[0]?.items[0]?.recordings_count).toBe(2);
    expect(spy).toHaveBeenCalledWith({ queryKey: queryKeys.report("r-1"), exact: true });
    expect(findCachedStream(qc, "s-1")?.id).toBe("s-1");
    expect(findCachedStream(qc, "nope")).toBeNull();
  });
});

describe("streamsApi (phase 6 §4)", () => {
  function setup(response: () => Response) {
    const fetchImpl = vi.fn((_url: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(response()));
    const api = streamsApi(createApiClient("http://api", { getAccessToken: () => "t", renew: () => Promise.resolve(null) }, fetchImpl));
    const call = (i = 0) => {
      const c = fetchImpl.mock.calls[i];
      const raw = c?.[0];
      return { url: new URL(typeof raw === "string" ? raw : raw instanceof URL ? raw.href : (raw?.url ?? "")), init: c?.[1] };
    };
    return { api, call };
  }
  const json = (body: unknown) => () => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });

  it("lists with status, gouvernorat and cursor; reads, views and stops on the staff paths", async () => {
    const { api, call } = setup(json({ items: [], next_cursor: null }));
    await api.streams({ status: "ended", gouvernorat: 61 }, { cursor: "abc" });
    expect(call(0).url.pathname).toBe("/api/v1/staff/streams");
    expect(Object.fromEntries(call(0).url.searchParams)).toEqual({ status: "ended", gouvernorat: "61", cursor: "abc" });
    await api.streams({ status: "live", gouvernorat: null });
    expect(Object.fromEntries(call(1).url.searchParams)).toEqual({ status: "live" });
    await api.stream("s/1");
    expect(call(2).url.pathname).toBe("/api/v1/staff/streams/s%2F1");
    await api.streamViewer("s-1");
    expect(call(3).url.pathname).toBe("/api/v1/staff/streams/s-1/viewer");
    expect(call(3).init?.method).toBe("POST");
    await api.stopStream("s-1");
    expect(call(4).url.pathname).toBe("/api/v1/staff/streams/s-1/stop");
    expect(call(4).init?.method).toBe("POST");
    expect((call(4).init?.headers as Record<string, string>).Authorization).toBe("Bearer t");
  });

  it("downloads a recording: the redirected file, or a JSON link", async () => {
    const file = setup(() => new Response("mp4-bytes", { headers: { "Content-Type": "video/mp4" } }));
    const got = await file.api.recordingDownload("s-1", "m-1");
    expect(file.call().url.pathname).toBe("/api/v1/staff/streams/s-1/recordings/m-1");
    expect(got.kind).toBe("file");
    const link = setup(json({ url: "https://s3.example/rec.mp4?sig=1" }));
    expect(await link.api.recordingDownload("s-1", "m-1")).toEqual({ kind: "link", url: "https://s3.example/rec.mp4?sig=1" });
  });

  it("maps errors (stream_not_active, 403) to codes", async () => {
    const { api } = setup(() => new Response(JSON.stringify({ detail: "stream_not_active" }), { status: 409 }));
    await expect(api.stopStream("s-1")).rejects.toMatchObject({ status: 409, code: "stream_not_active" });
  });
});

describe("detections", () => {
  it("bands confidences on the contract thresholds", () => {
    expect(confidenceBand(0.6)).toBe("high");
    expect(confidenceBand(0.59)).toBe("medium");
    expect(confidenceBand(0.45)).toBe("medium");
    expect(confidenceBand(0.2)).toBe("low");
  });

  it("places a contained frame inside its box (letterbox and pillarbox)", () => {
    expect(containRect(1600, 900, 1280, 720)).toEqual({ x: 0, y: 0, width: 1600, height: 900 });
    expect(containRect(1600, 900, 720, 1280)).toEqual({ x: 546.875, y: 0, width: 506.25, height: 900 });
    expect(containRect(400, 400, 1280, 720)).toEqual({ x: 0, y: 87.5, width: 400, height: 225 });
    expect(containRect(400, 300, 0, 0)).toEqual({ x: 0, y: 0, width: 400, height: 300 });
  });

  it("normalises boxes and groups the latest frame", () => {
    expect(boxRect([0.4, 0.6, 0.1, 0.2, 0.8])).toEqual({ x: 0.1, y: 0.2, width: 0.30000000000000004, height: 0.39999999999999997, confidence: 0.8 });
    expect(boxRect([-0.2, 0.5, 1.4, 0.7, 0.5])).toMatchObject({ x: 0, width: 1 });
    const frame = latestFrame([
      { at: "2026-10-19T10:00:01Z", label: "fire", confidence: 0.7, boxes: [] },
      { at: "2026-10-19T10:00:02Z", label: "fire", confidence: 0.8, boxes: [] },
      { at: "2026-10-19T10:00:02Z", label: "smoke", confidence: 0.5, boxes: [] },
    ]);
    expect(frame.map((d) => d.label)).toEqual(["fire", "smoke"]);
    expect(latestFrame([])).toEqual([]);
    expect([...strongestByLabel([{ label: "fire", confidence: 0.5 }, { label: "fire", confidence: 0.7 }])]).toEqual([["fire", 0.7]]);
  });
});

describe("wall", () => {
  const live = [
    makeStream({ id: "a", max_fire_confidence: null, max_smoke_confidence: null, started_at: "2026-10-19T10:00:00Z" }),
    makeStream({ id: "b", max_fire_confidence: 0.9, started_at: "2026-10-19T09:00:00Z" }),
    makeStream({ id: "c", max_fire_confidence: null, max_smoke_confidence: null, started_at: "2026-10-19T11:00:00Z" }),
  ];

  it("orders the free tiles by danger, then newest", () => {
    expect([...live].sort(byDanger).map((s) => s.id)).toEqual(["b", "c", "a"]);
    expect(arrangeWall({ layout: 4, pinned: [] }, live)).toEqual([
      { slot: 0, streamId: "b", pinned: false },
      { slot: 1, streamId: "c", pinned: false },
      { slot: 2, streamId: "a", pinned: false },
      { slot: 3, streamId: null, pinned: false },
    ]);
  });

  it("keeps pinned streams in place (even when no longer live) and fills around them", () => {
    const tiles = arrangeWall({ layout: 4, pinned: [null, "a", "gone"] }, live);
    expect(tiles.map((t) => [t.streamId, t.pinned])).toEqual([
      ["b", false],
      ["a", true],
      ["gone", true],
      ["c", false],
    ]);
    expect(arrangeWall({ layout: 1, pinned: [null, "a"] }, live)).toEqual([{ slot: 0, streamId: "b", pinned: false }]);
  });

  it("pins, moves and unpins", () => {
    let state = pinStream({ layout: 4, pinned: [] }, 2, "a");
    expect(state.pinned).toEqual([null, null, "a"]);
    state = pinStream(state, 0, "a");
    expect(state.pinned).toEqual(["a"]);
    state = pinToFreeTile(state, "b");
    expect(state.pinned).toEqual(["a", "b"]);
    expect(pinToFreeTile(state, "b")).toBe(state);
    const full = { layout: 1 as const, pinned: ["a"] };
    expect(pinToFreeTile(full, "c").pinned).toEqual(["c"]);
    expect(pinStream(state, 1, null).pinned).toEqual(["a"]);
  });

  it("survives broken storage", () => {
    localStorage.setItem("ehimaya.streamWall", "{not json");
    expect(loadWall()).toEqual({ layout: 4, pinned: [] });
    saveWall({ layout: 9, pinned: ["x", null] });
    expect(loadWall()).toEqual({ layout: 9, pinned: ["x", null] });
  });
});

describe("archive filters", () => {
  const s = makeStream({ status: "ended", started_at: new Date(2026, 9, 10, 14, 0).toISOString(), max_fire_confidence: 0.7, max_smoke_confidence: 0.5 });

  it("filters by local date range, inclusive", () => {
    expect(matchesArchiveFilters(s, { from: "2026-10-10", to: "2026-10-10", detection: "any" })).toBe(true);
    expect(matchesArchiveFilters(s, { from: "2026-10-11", to: "", detection: "any" })).toBe(false);
    expect(matchesArchiveFilters(s, { from: "", to: "2026-10-09", detection: "any" })).toBe(false);
  });

  it("counts fire or smoke from the alert threshold", () => {
    expect(matchesArchiveFilters(s, { from: "", to: "", detection: "fire" })).toBe(true);
    expect(matchesArchiveFilters(s, { from: "", to: "", detection: "smoke" })).toBe(false);
    expect(matchesArchiveFilters(s, { from: "", to: "", detection: "fire_or_smoke" })).toBe(true);
    expect(matchesArchiveFilters(s, { from: "", to: "", detection: "none" })).toBe(false);
    const quiet = { ...s, max_fire_confidence: null, max_smoke_confidence: null };
    expect(matchesArchiveFilters(quiet, { from: "", to: "", detection: "none" })).toBe(true);
  });
});
