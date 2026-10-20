import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { boxRect, containRect, strongestByLabel, type Rect } from "../lib/detections";
import { isDetectionLabel, type DetectionBox, type MediaAnalysis } from "../lib/streamTypes";
import { DetectionBadge } from "./StreamBits";

interface Detection {
  label: string;
  confidence: number;
  boxes?: DetectionBox[] | null;
}

/** Detections of an image (`media.analysis.vision`, phase 6 §5), or [] when it was not analysed. */
export function visionDetections(analysis: MediaAnalysis | null | undefined): Detection[] {
  const list = analysis?.vision?.detections;
  return Array.isArray(list) ? list.filter((d) => typeof d.label === "string" && typeof d.confidence === "number") : [];
}

/** An image with its detection boxes drawn over the picture (object-fit: contain, so the bars are excluded). */
export function VisionImage({
  src,
  alt,
  detections,
  onError,
}: {
  src: string;
  alt: string;
  detections: Detection[];
  onError?: () => void;
}) {
  const img = useRef<HTMLImageElement>(null);
  const [area, setArea] = useState<Rect | null>(null);
  useEffect(() => {
    const el = img.current;
    if (!el) return;
    const measure = () =>
      setArea(el.naturalWidth > 0 ? containRect(el.clientWidth, el.clientHeight, el.naturalWidth, el.naturalHeight) : null);
    el.addEventListener("load", measure);
    if (el.complete) measure();
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(measure) : null;
    observer?.observe(el);
    return () => {
      el.removeEventListener("load", measure);
      observer?.disconnect();
    };
  }, [src]);
  const boxes = detections.flatMap((d, i) =>
    (d.boxes ?? []).map((b, j) => ({ key: `${i}-${j}`, label: d.label, rect: boxRect(b) })),
  );
  return (
    <span className="vision-frame">
      <img ref={img} src={src} alt={alt} loading="lazy" onError={onError} />
      {area && boxes.length > 0 && (
        <svg
          className="det-overlay"
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          aria-hidden="true"
          style={{ left: area.x, top: area.y, width: area.width, height: area.height }}
        >
          {boxes.map(({ key, label, rect }) => (
            <rect
              key={key}
              className={`det-box det-box--${isDetectionLabel(label) ? label : "other"}`}
              x={rect.x}
              y={rect.y}
              width={rect.width}
              height={rect.height}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>
      )}
    </span>
  );
}

/** "Vision: fire 82 %, smoke 51 %" under an analysed image; a stored stream frame says so. */
export function VisionSummary({ analysis }: { analysis: MediaAnalysis | null | undefined }) {
  const { t } = useTranslation();
  const detections = visionDetections(analysis);
  const fromStream = analysis?.source === "vision";
  if (!analysis?.vision && !fromStream) return null;
  const strongest = [...strongestByLabel(detections)];
  return (
    <div className="vision">
      <p className="vision__title">
        <strong>{fromStream ? t("streams.vision.frame") : t("streams.vision.title")}</strong>
        {analysis.vision?.model && <span className="muted"> · {t("streams.vision.model", { model: analysis.vision.model })}</span>}
      </p>
      {strongest.length === 0 ? (
        <p className="muted">{t("streams.vision.nothing")}</p>
      ) : (
        <p className="dets">
          {strongest.map(([label, confidence]) => (
            <DetectionBadge key={label} label={label} confidence={confidence} />
          ))}
        </p>
      )}
      <p className="muted vision__note">{t("streams.vision.note")}</p>
    </div>
  );
}
