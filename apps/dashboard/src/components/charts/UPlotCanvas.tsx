/**
 * The canvas half of TimeChart (uPlot, MIT, docs/versions.md), loaded on demand so the main bundle stays small.
 * It is decorative for assistive technology: the figure caption, the text summary and the data table carry the
 * information (TimeChart).
 */
import { useEffect, useLayoutEffect, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import type { ChartBand, ChartSeries, ChartTone } from "./TimeChart";

export interface UPlotCanvasProps {
  x: number[];
  xKind: "time" | "index";
  series: ChartSeries[];
  bands: ChartBand[];
  highlight?: boolean[];
  formatValue: (n: number) => string;
  formatX: (x: number) => string;
  height: number;
  /** Changes when the theme changes, to re-read the colour tokens. */
  themeKey: string;
}

const TOKEN: Record<ChartTone, string> = {
  primary: "--chart-primary",
  secondary: "--chart-secondary",
  baseline: "--chart-baseline",
  capacity: "--chart-capacity",
};

function token(el: Element, name: string, fallback: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim() || fallback;
}

export default function UPlotCanvas(props: UPlotCanvasProps) {
  const { x, xKind, series, bands, highlight, formatValue, formatX, height, themeKey } = props;
  const ref = useRef<HTMLDivElement>(null);
  // Formatters change identity on every parent render: read them through a ref, and rebuild the plot only when
  // the data, the size or the theme change.
  const fmt = useRef({ formatValue, formatX });
  useLayoutEffect(() => {
    fmt.current = { formatValue, formatX };
  });
  const dataKey = JSON.stringify([x, xKind, series, bands, highlight, height, themeKey]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const axisColour = token(el, "--muted", "#55606c");
    const gridColour = token(el, "--border", "#d3d9df");
    const bandFill = token(el, "--chart-band", "rgba(37, 99, 235, 0.15)");
    const highlightFill = token(el, "--chart-highlight", "rgba(220, 38, 38, 0.12)");
    const opts: uPlot.Options = {
      width: Math.max(280, el.clientWidth),
      height,
      legend: { show: false },
      cursor: { drag: { x: false, y: false } },
      scales: { x: { time: xKind === "time" } },
      axes: [
        {
          stroke: axisColour,
          grid: { stroke: gridColour, width: 1 },
          ticks: { stroke: gridColour },
          values: (_u, splits) => splits.map((v) => fmt.current.formatX(v)),
        },
        {
          stroke: axisColour,
          grid: { stroke: gridColour, width: 1 },
          ticks: { stroke: gridColour },
          size: 60,
          values: (_u, splits) => splits.map((v) => fmt.current.formatValue(v)),
        },
      ],
      series: [
        {},
        ...series.map((s) => ({
          label: s.label,
          stroke: s.edge ? "transparent" : token(el, TOKEN[s.tone], "#2563eb"),
          width: s.edge ? 0 : s.tone === "primary" ? 2.5 : 1.5,
          dash: s.dashed ? [6, 4] : undefined,
          points: { show: !s.edge && x.length <= 60, size: 4 },
          spanGaps: false,
        })),
      ],
      bands: bands.map((b) => ({ series: [b.high + 1, b.low + 1] as [number, number], fill: bandFill })),
      hooks: {
        drawClear: [
          (u) => {
            if (!highlight?.some(Boolean)) return;
            const ctx = u.ctx;
            ctx.save();
            ctx.fillStyle = highlightFill;
            const step = x.length > 1 ? (x[1] ?? 0) - (x[0] ?? 0) : 1;
            highlight.forEach((on, i) => {
              if (!on) return;
              const left = u.valToPos((x[i] ?? 0) - step / 2, "x", true);
              const right = u.valToPos((x[i] ?? 0) + step / 2, "x", true);
              ctx.fillRect(left, u.bbox.top, right - left, u.bbox.height);
            });
            ctx.restore();
          },
        ],
      },
    };
    const data: uPlot.AlignedData = [x, ...series.map((s) => s.values.map((v) => (v === null ? null : v)))];
    const plot = new uPlot(opts, data, el);
    const observer = new ResizeObserver(() => plot.setSize({ width: Math.max(280, el.clientWidth), height }));
    observer.observe(el);
    return () => {
      observer.disconnect();
      plot.destroy();
    };
    // dataKey stands for every input read above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataKey]);

  return <div ref={ref} className="time-chart__canvas" dir="ltr" aria-hidden="true" />;
}
