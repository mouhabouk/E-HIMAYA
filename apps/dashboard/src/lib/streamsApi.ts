import type { ApiClient } from "./api";
import type { Page } from "./types";
import type { StaffStream, StaffStreamDetail, StreamStatusFilter, ViewerGrant } from "./streamTypes";

const enc = encodeURIComponent;
const streamPath = (id: string) => `/api/v1/staff/streams/${enc(id)}`;

/** List filters the API understands (§4): status and gouvernorat; the cursor pages through the rest. */
export interface StreamListFilters {
  status: StreamStatusFilter;
  gouvernorat: number | null;
}

/** Recording download: a pre-signed link to open, or the file itself when the API redirected straight to it. */
export type RecordingDownload = { kind: "link"; url: string } | { kind: "file"; blob: Blob; url: string };

export interface CameraInput {
  label: string;
  gouvernorat_code: number;
  org_id: string | null;
  lat?: number | null;
  lon?: number | null;
}

export interface RegisteredSource {
  id: string;
  path: string;
  publish_url_rtsp: string;
  publish_url_rtmp: string;
  publish_token: string;
}

/** Review point 25: what an institution's camera saw, and what became of it. */
export interface Prealert {
  id: string;
  org_id: string;
  org_name: string | null;
  stream_id: string | null;
  source: "camera" | "sensor";
  label: "fire" | "smoke";
  confidence: number;
  simulated: boolean;
  state: "pending" | "cancelled" | "confirmed" | "escalated";
  raised_at: string;
  deadline_at: string;
  seconds_left: number;
  reason: string | null;
  report_id: string | null;
  has_frame: boolean;
}

/** Typed calls for docs/api/phase-6-contract.md §4 (staff streams). */
export function streamsApi(api: ApiClient) {
  return {
    streams: (filters: StreamListFilters, opts: { cursor?: string | null; signal?: AbortSignal } = {}) =>
      api.request<Page<StaffStream>>("/api/v1/staff/streams", {
        query: { status: filters.status, gouvernorat: filters.gouvernorat ?? undefined, cursor: opts.cursor ?? undefined },
        signal: opts.signal,
      }),

    stream: (id: string, signal?: AbortSignal) => api.request<StaffStreamDetail>(streamPath(id), { signal }),

    /** Viewer token for WHEP/HLS (audited `stream.view`); valid 5 minutes to start, bound to the stream's path. */
    streamViewer: (id: string) => api.request<ViewerGrant>(`${streamPath(id)}/viewer`, { method: "POST" }),

    /** Ends a stream for everyone (operators, ops managers, field commanders; audited). */
    /**
     * Review point 25 (phase D): registers a fixed camera, here one of an institution. The publish token is shown
     * once; a camera that only offers RTSP (Tapo C200 and the like) is relayed by `infra/camera-relay`.
     */
    registerCamera: (body: CameraInput) =>
      api.request<RegisteredSource>("/api/v1/staff/streams", { method: "POST", body: { source: "camera", ...body } }),

    /** The pre-alerts of the institutions in scope, the false alarms included (newest first). */
    prealerts: (gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<Prealert[]>("/api/v1/staff/prealerts", { query: { gouvernorat: gouvernorat ?? undefined }, signal }),

    stopStream: (id: string) => api.request<unknown>(`${streamPath(id)}/stop`, { method: "POST" }),

    /**
     * `GET …/recordings/{media_id}` answers `302` to a short-lived pre-signed URL (audited
     * `stream.recording.download`). The browser follows the redirect: the file comes back with its final URL. If
     * the API answers `{"url"}` instead (like the other staff downloads), that link is returned as is.
     */
    recordingDownload: async (streamId: string, mediaId: string): Promise<RecordingDownload> => {
      const response = await api.requestRaw(`${streamPath(streamId)}/recordings/${enc(mediaId)}`, {
        accept: "application/json, video/mp4;q=0.9, */*;q=0.8",
      });
      const type = response.headers.get("Content-Type") ?? "";
      if (type.includes("application/json")) {
        const body = (await response.json()) as { url?: unknown };
        if (typeof body.url === "string") return { kind: "link", url: body.url };
      }
      return { kind: "file", blob: await response.blob(), url: response.url };
    },
  };
}

export type StreamsApi = ReturnType<typeof streamsApi>;

export const streamKeys = {
  listsAll: ["streams"] as const,
  list: (filters: StreamListFilters) => ["streams", filters.status, filters.gouvernorat] as const,
  detailAll: ["stream"] as const,
  detail: (id: string) => ["stream", id] as const,
  prealerts: (gouvernorat: number | null) => ["prealerts", gouvernorat] as const,
};
