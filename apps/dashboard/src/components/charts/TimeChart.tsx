import { lazy, Suspense, useEffect, useId, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

const UPlotCanvas = lazy(() => import("./UPlotCanvas"));

export type ChartTone = "primary" | "secondary" | "baseline" | "capacity";

export interface ChartSeries {
  key: string;
  label: string;
  values: (number | null)[];
  tone: ChartTone;
  dashed?: boolean;
  /** Edge of a band (low/high): not drawn as a line, still listed in the data table. */
  edge?: boolean;
}

/** Shaded area between two series (indices into `series`), e.g. the seasonal range or the 10–90 % percentiles. */
export interface ChartBand {
  low: number;
  high: number;
  label: string;
}

interface TimeChartProps {
  caption: string;
  /** Plain-language summary read before the table (e.g. "Peak 42 on 12 March; 3 weeks above the usual range"). */
  summary?: ReactNode;
  /** Epoch seconds (time axis) or ordinal values (e.g. hour offsets). */
  x: number[];
  xKind?: "time" | "index";
  /** Label of each x value in the data table and on the axis. */
  xLabels: string[];
  xHeader: string;
  series: ChartSeries[];
  bands?: ChartBand[];
  /** Columns shaded on the chart and marked in the table (e.g. overload hours). */
  highlight?: boolean[];
  highlightLabel?: string;
  formatValue: (n: number) => string;
  height?: number;
  emptyText: string;
}

function currentTheme(): string {
  if (typeof document === "undefined") return "";
  const explicit = document.documentElement.dataset.theme ?? "";
  const dark = typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;
  return `${explicit}|${dark ? "dark" : "light"}`;
}

/** Follows theme changes (toggle or system) so the canvas re-reads its colour tokens. */
function useThemeKey(): string {
  const [key, setKey] = useState(currentTheme);
  useEffect(() => {
    const update = () => setKey(currentTheme());
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = typeof matchMedia === "function" ? matchMedia("(prefers-color-scheme: dark)") : null;
    mq?.addEventListener("change", update);
    return () => {
      observer.disconnect();
      mq?.removeEventListener("change", update);
    };
  }, []);
  return key;
}

/** Canvas charts need ResizeObserver and a 2D context; without them (old browsers, tests) only the table shows. */
const canDraw = typeof window !== "undefined" && "ResizeObserver" in window;

/**
 * A time series chart (uPlot) with an always available data table alternative (accessibility, contract §4): the
 * canvas is hidden from assistive technology; the caption, the summary, a legend in text and the table carry every
 * value. Bands and highlighted columns are listed in the table too.
 */
export function TimeChart(props: TimeChartProps) {
  const { t } = useTranslation();
  const tableId = useId();
  const themeKey = useThemeKey();
  const {
    caption,
    summary,
    x,
    xKind = "time",
    xLabels,
    xHeader,
    series,
    bands = [],
    highlight,
    highlightLabel,
    formatValue,
    height = 260,
    emptyText,
  } = props;
  const [showTable, setShowTable] = useState(!canDraw);
  const empty = x.length === 0 || series.every((s) => s.values.every((v) => v === null));
  const formatX = (v: number) => {
    const i = x.indexOf(v);
    if (i >= 0) return xLabels[i] ?? "";
    // Axis ticks between data points: nearest label.
    let best = 0;
    for (let k = 1; k < x.length; k += 1) if (Math.abs((x[k] ?? 0) - v) < Math.abs((x[best] ?? 0) - v)) best = k;
    return xLabels[best] ?? "";
  };
  return (
    <figure className="card chart time-chart">
      <figcaption className="time-chart__caption">{caption}</figcaption>
      {summary && <p className="time-chart__summary">{summary}</p>}
      {empty ? (
        <p className="muted">{emptyText}</p>
      ) : (
        <>
          <ul className="time-chart__legend">
            {series
              .filter((s) => !s.edge)
              .map((s) => (
                <li key={s.key}>
                  <span className={`swatch swatch--${s.tone}${s.dashed ? " swatch--dashed" : ""}`} aria-hidden="true" />
                  {s.label}
                </li>
              ))}
            {bands.map((b) => (
              <li key={b.label}>
                <span className="swatch swatch--band" aria-hidden="true" />
                {b.label}
              </li>
            ))}
            {highlight?.some(Boolean) && highlightLabel && (
              <li>
                <span className="swatch swatch--highlight" aria-hidden="true" />
                {highlightLabel}
              </li>
            )}
          </ul>
          {canDraw && (
            <Suspense fallback={<div className="time-chart__canvas" style={{ blockSize: height }} />}>
              <UPlotCanvas
                x={x}
                xKind={xKind}
                series={series}
                bands={bands}
                highlight={highlight}
                formatValue={formatValue}
                formatX={formatX}
                height={height}
                themeKey={themeKey}
              />
            </Suspense>
          )}
          {canDraw && (
            <button
              type="button"
              className="btn btn--ghost btn--small"
              aria-expanded={showTable}
              aria-controls={tableId}
              onClick={() => setShowTable((v) => !v)}
            >
              {showTable ? t("charts.hideTable") : t("charts.showTable")}
            </button>
          )}
          <div className="table-wrap" id={tableId} hidden={!showTable}>
            <table className="table table--compact">
              <caption className="visually-hidden">{t("charts.tableOf", { caption })}</caption>
              <thead>
                <tr>
                  <th scope="col">{xHeader}</th>
                  {series.map((s) => (
                    <th scope="col" key={s.key}>
                      {s.label}
                    </th>
                  ))}
                  {highlight && highlightLabel && <th scope="col">{highlightLabel}</th>}
                </tr>
              </thead>
              <tbody>
                {x.map((xv, i) => (
                  <tr key={xv} className={highlight?.[i] ? "row--highlight" : undefined}>
                    <th scope="row">{xLabels[i]}</th>
                    {series.map((s) => {
                      const v = s.values[i];
                      return <td key={s.key}>{v === null || v === undefined ? "—" : formatValue(v)}</td>;
                    })}
                    {highlight && highlightLabel && <td>{highlight[i] ? t("common.yes") : t("common.no")}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </figure>
  );
}
