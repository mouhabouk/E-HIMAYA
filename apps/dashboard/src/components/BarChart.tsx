import type { ReactNode } from "react";
import { useFormat } from "../lib/hooks";

export interface Bar {
  key: string;
  label: ReactNode;
  value: number;
  /** CSS class applied to the bar (e.g. a status colour). */
  tone?: string;
}

/**
 * Horizontal bar chart rendered as a table: screen readers get label/value pairs,
 * sighted users get proportional bars. Bars grow along the inline axis, so RTL works unchanged.
 */
export function BarChart({ caption, bars, emptyText }: { caption: string; bars: Bar[]; emptyText: string }) {
  const fmt = useFormat();
  const max = Math.max(0, ...bars.map((b) => b.value));
  return (
    <figure className="card chart">
      <table className="bars">
        <caption>{caption}</caption>
        <tbody>
          {bars.length === 0 || max === 0 ? (
            <tr>
              <td className="muted">{emptyText}</td>
            </tr>
          ) : (
            bars.map((b) => (
              <tr key={b.key}>
                <th scope="row" className="bars__label">
                  {b.label}
                </th>
                <td className="bars__track">
                  <span
                    className={`bars__bar ${b.tone ?? ""}`}
                    style={{ inlineSize: `${max ? (b.value / max) * 100 : 0}%` }}
                    aria-hidden="true"
                  />
                </td>
                <td className="bars__value">{fmt.number(b.value)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </figure>
  );
}
