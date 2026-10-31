/**
 * Types mirroring docs/api/phase-6-contract.md: live streams (§1, §4), detections (§1, §5) and the simulated
 * sources (§6). Coordinates of detection boxes are normalised to 0..1 of the analysed frame.
 */

/** `crew`: a team streams from the staff app (phase D, review point 17). */
export const STREAM_SOURCES = ["app", "drone", "camera", "sim", "crew"] as const;
export type StreamSource = (typeof STREAM_SOURCES)[number];

export const STREAM_STATUSES = ["pending", "live", "ended", "expired", "rejected"] as const;
export type StreamStatus = (typeof STREAM_STATUSES)[number];

export const STREAM_END_REASONS = ["publisher_stopped", "staff_stopped", "max_duration", "token_expired", "error"] as const;
export type StreamEndReason = (typeof STREAM_END_REASONS)[number];

export const DETECTION_LABELS = ["fire", "smoke", "person"] as const;
export type DetectionLabel = (typeof DETECTION_LABELS)[number];

/** Labels that raise an alert (§3 `/internal/vision/detections`): a confirmed fire or smoke. */
export const ALERT_LABELS = ["fire", "smoke"] as const;
export type AlertLabel = (typeof ALERT_LABELS)[number];

/** `status` filter of the staff list. */
export type StreamStatusFilter = "live" | "ended" | "all";

/** `[x1, y1, x2, y2, conf]`, normalised 0..1. */
export type DetectionBox = [number, number, number, number, number];

export interface LatLon {
  lat: number;
  lon: number;
}

/** One row of `GET /api/v1/staff/streams`. */
export interface StaffStream {
  id: string;
  report_id: string | null;
  tracking_code: string | null;
  source: StreamSource;
  /** Staff-given name of a fixed source (drone, camera, sim). */
  label: string | null;
  status: StreamStatus;
  started_at: string | null;
  ended_at: string | null;
  duration_s: number | null;
  gouvernorat_code: number | null;
  last_location: LatLon | null;
  /** 0..1, null before any analysed frame. */
  max_fire_confidence: number | null;
  max_smoke_confidence: number | null;
  recordings_count: number;
  /** `source = sim` (§6): never a real emergency. */
  simulated: boolean;
  /** A team's stream (phase D): its incident. */
  incident_id?: string | null;
  /** Not in the §4 list row, but kept when the API sends it (stream detail of §1). */
  end_reason?: StreamEndReason | null;
}

export interface StreamRecording {
  media_id: string;
  sha256: string;
  bytes: number | null;
  duration_s: number | null;
  created_at: string;
}

export interface StreamDetection {
  at: string;
  label: DetectionLabel;
  confidence: number;
  boxes: DetectionBox[];
}

export interface TrackPoint {
  at: string;
  lat: number;
  lon: number;
}

/** `GET /api/v1/staff/streams/{id}`. */
export interface StaffStreamDetail extends StaffStream {
  recordings: StreamRecording[];
  /** Latest 200. */
  detections: StreamDetection[];
  track: TrackPoint[];
}

/** `POST /api/v1/staff/streams/{id}/viewer`: a path-bound token, valid 5 minutes to start. */
export interface ViewerGrant {
  whep_url: string;
  hls_url: string | null;
  token: string;
  expires_at: string;
}

/** `media.analysis.vision` of an uploaded image (§5 `POST /v1/detect`). */
export interface VisionResult {
  model?: string | null;
  detections: { label: string; confidence: number; boxes?: DetectionBox[] | null }[];
}

export interface MediaAnalysis {
  /** "vision" for a frame stored by a confirmed detection on a stream (§3). */
  source?: string | null;
  vision?: VisionResult | null;
}

export function isStreamStatus(v: unknown): v is StreamStatus {
  return typeof v === "string" && (STREAM_STATUSES as readonly string[]).includes(v);
}

export function isDetectionLabel(v: unknown): v is DetectionLabel {
  return typeof v === "string" && (DETECTION_LABELS as readonly string[]).includes(v);
}

export function isAlertLabel(v: unknown): v is AlertLabel {
  return typeof v === "string" && (ALERT_LABELS as readonly string[]).includes(v);
}
