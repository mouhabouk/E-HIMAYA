import { vi } from "vitest";
import type { StreamsApi } from "../lib/streamsApi";
import type { StreamSessionOptions } from "../lib/streamSession";
import type { StaffStream, StaffStreamDetail, ViewerGrant } from "../lib/streamTypes";

const empty = { items: [], next_cursor: null };

/** Phase 6 calls of the fake API: no stream by default, override per test. */
export function fakeStreamsApi(): StreamsApi {
  return {
    streams: vi.fn(() => Promise.resolve(empty)),
    stream: vi.fn(),
    streamViewer: vi.fn(() => Promise.resolve(makeGrant())),
    stopStream: vi.fn(() => Promise.resolve({})),
    recordingDownload: vi.fn(() => Promise.resolve({ kind: "link" as const, url: "https://s3.example/rec.mp4?sig=x" })),
  };
}

export function makeStream(overrides: Partial<StaffStream> = {}): StaffStream {
  return {
    id: "s-1",
    report_id: "r-1",
    tracking_code: "EH-26-61-0004821",
    source: "app",
    label: null,
    status: "live",
    started_at: new Date(Date.now() - 95_000).toISOString(),
    ended_at: null,
    duration_s: null,
    gouvernorat_code: 61,
    last_location: { lat: 34.74, lon: 10.76 },
    max_fire_confidence: 0.82,
    max_smoke_confidence: 0.4,
    recordings_count: 1,
    simulated: false,
    ...overrides,
  };
}

export function makeStreamDetail(overrides: Partial<StaffStreamDetail> = {}): StaffStreamDetail {
  return {
    ...makeStream(overrides),
    recordings: [
      {
        media_id: "rec-1",
        sha256: "b".repeat(64),
        bytes: 5_242_880,
        duration_s: 60,
        created_at: new Date(Date.now() - 30_000).toISOString(),
      },
    ],
    detections: [
      { at: new Date(Date.now() - 20_000).toISOString(), label: "fire", confidence: 0.82, boxes: [[0.1, 0.2, 0.4, 0.6, 0.82]] },
      { at: new Date(Date.now() - 40_000).toISOString(), label: "smoke", confidence: 0.4, boxes: [[0.5, 0.1, 0.9, 0.5, 0.4]] },
    ],
    track: [
      { at: new Date(Date.now() - 90_000).toISOString(), lat: 34.739, lon: 10.759 },
      { at: new Date(Date.now() - 60_000).toISOString(), lat: 34.74, lon: 10.76 },
    ],
    ...overrides,
  };
}

export function makeGrant(overrides: Partial<ViewerGrant> = {}): ViewerGrant {
  return {
    whep_url: "https://media.example/live/s-1/whep",
    hls_url: "https://media.example/live/s-1/index.m3u8",
    token: "viewer-token",
    expires_at: new Date(Date.now() + 5 * 60_000).toISOString(),
    ...overrides,
  };
}

/** Stand-in for StreamSession in page tests (jsdom has no WebRTC or MSE): records what the page asked for. */
export class FakeStreamSession {
  static instances: FakeStreamSession[] = [];
  readonly options: StreamSessionOptions;
  started = false;
  stopped = false;
  suspended = 0;
  resumed = 0;
  retried = 0;

  constructor(options: StreamSessionOptions) {
    this.options = options;
    FakeStreamSession.instances.push(this);
  }

  static reset(): void {
    FakeStreamSession.instances = [];
  }

  start(): void {
    this.started = true;
    void this.options.requestGrant().then(
      () => this.options.onChange({ state: "playing", transport: "whep" }),
      () => this.options.onChange({ state: "forbidden", transport: null }),
    );
  }

  stop(): void {
    this.stopped = true;
  }

  suspend(): void {
    this.suspended += 1;
  }

  resume(): void {
    this.resumed += 1;
  }

  retryNow(): void {
    this.retried += 1;
  }
}
