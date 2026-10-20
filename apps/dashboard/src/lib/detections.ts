/** Helpers for the vision results (phase 6 §1, §5): confidence bands, frame grouping and box placement. */
import type { DetectionBox, StreamDetection } from "./streamTypes";

/** §3 defaults: detections under 0.45 are dropped, an alert needs 0.6 (confirmed over 3 of 5 frames). */
export const MIN_CONFIDENCE = 0.45;
export const ALERT_CONFIDENCE = 0.6;

export type ConfidenceBand = "high" | "medium" | "low";

export function confidenceBand(confidence: number): ConfidenceBand {
  if (confidence >= ALERT_CONFIDENCE) return "high";
  if (confidence >= MIN_CONFIDENCE) return "medium";
  return "low";
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Where a `object-fit: contain` frame of `media` size is drawn inside a `box`: the overlay must cover exactly that
 * area, not the letterbox bars.
 */
export function containRect(boxWidth: number, boxHeight: number, mediaWidth: number, mediaHeight: number): Rect {
  if (boxWidth <= 0 || boxHeight <= 0 || mediaWidth <= 0 || mediaHeight <= 0) {
    return { x: 0, y: 0, width: Math.max(0, boxWidth), height: Math.max(0, boxHeight) };
  }
  const scale = Math.min(boxWidth / mediaWidth, boxHeight / mediaHeight);
  const width = mediaWidth * scale;
  const height = mediaHeight * scale;
  return { x: (boxWidth - width) / 2, y: (boxHeight - height) / 2, width, height };
}

const clamp01 = (n: number) => Math.min(1, Math.max(0, n));

/** A normalised `[x1,y1,x2,y2,conf]` box as a rectangle in the 0..1 frame (corners in any order, clamped). */
export function boxRect(box: DetectionBox): Rect & { confidence: number } {
  const [x1, y1, x2, y2, confidence] = box;
  const left = clamp01(Math.min(x1, x2));
  const top = clamp01(Math.min(y1, y2));
  return {
    x: left,
    y: top,
    width: clamp01(Math.max(x1, x2)) - left,
    height: clamp01(Math.max(y1, y2)) - top,
    confidence,
  };
}

/** Detections of the latest analysed frame (they share its `at`), or [] when there is none. */
export function latestFrame(detections: readonly StreamDetection[]): StreamDetection[] {
  let latest = Number.NEGATIVE_INFINITY;
  for (const d of detections) latest = Math.max(latest, Date.parse(d.at));
  if (!Number.isFinite(latest)) return [];
  return detections.filter((d) => Date.parse(d.at) === latest);
}

/** Strongest confidence per label, for the badges. */
export function strongestByLabel(detections: readonly { label: string; confidence: number }[]): Map<string, number> {
  const out = new Map<string, number>();
  for (const d of detections) out.set(d.label, Math.max(out.get(d.label) ?? 0, d.confidence));
  return out;
}
