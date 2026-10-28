import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useFormat, useGouvernorats } from "../lib/hooks";
import type { Cell, Figures } from "../lib/windowTypes";

/** The indicators of a period (L4 §3 and L4a): the decision window and the library calendar show them alike. */
export function useCount(minCell: number) {
  const fmt = useFormat();
  return (n: number | null | undefined) => (n === null || n === undefined ? `\u200e<${minCell}\u200e` : fmt.number(n));
}

export function Kpi({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="kpi">
      <dt className="kpi__label">{label}</dt>
      <dd className="kpi__value">{value}</dd>
    </div>
  );
}

export function Cells({ caption, cells, label, minCell }: { caption: string; cells: Cell[]; label: (key: string) => string; minCell: number }) {
  const { t } = useTranslation();
  const count = useCount(minCell);
  const max = Math.max(minCell, ...cells.map((c) => c.count ?? 0));
  return (
    <figure className="card chart">
      <table className="bars">
        <caption>{caption}</caption>
        <tbody>
          {cells.length === 0 ? (
            <tr>
              <td className="muted">{t("window.none")}</td>
            </tr>
          ) : (
            cells.map((c) => (
              <tr key={c.key}>
                <th scope="row" className="bars__label">
                  {label(c.key)}
                </th>
                <td className="bars__track">
                  <span
                    className={`bars__bar${c.count === null ? " win-bar--hidden" : ""}`}
                    style={{ inlineSize: `${((c.count ?? minCell / 2) / max) * 100}%` }}
                    aria-hidden="true"
                  />
                </td>
                <td className="bars__value">{count(c.count)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </figure>
  );
}

export function FiguresView({ figures, minCell }: { figures: Figures; minCell: number }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const count = useCount(minCell);
  const minutes = (m: number | null) => (m === null ? "—" : t("window.minutes", { n: fmt.decimal(m) }));
  return (
    <>
      <dl className="kpis">
        <Kpi label={t("window.metric.incidents")} value={count(figures.incidents)} />
        <Kpi label={t("window.metric.injured")} value={count(figures.injured)} />
        <Kpi label={t("window.metric.deceased")} value={count(figures.deceased)} />
        <Kpi label={t("window.metric.rescued")} value={count(figures.rescued)} />
        <Kpi label={t("window.metric.burned_ha")} value={figures.burned_ha === null ? "—" : fmt.decimal(figures.burned_ha)} />
        <Kpi label={t("window.metric.to_assignment_min")} value={minutes(figures.to_assignment_min)} />
        <Kpi label={t("window.metric.to_on_scene_min")} value={minutes(figures.to_on_scene_min)} />
        <Kpi
          label={t("window.metric.confirmed_rate")}
          value={figures.confirmed_rate === null ? "—" : fmt.percent(figures.confirmed_rate)}
        />
      </dl>
      <div className="win-charts">
        <Cells caption={t("window.byCategory")} cells={figures.by_category} label={(k) => t(`category.${k}`, k)} minCell={minCell} />
        <Cells caption={t("window.bySeverity")} cells={figures.by_severity} label={(k) => t("window.severity", { n: k })} minCell={minCell} />
        <Cells
          caption={t("window.byGouvernorat")}
          cells={figures.by_gouvernorat}
          label={(k) => gouvernorats.nameOf(Number(k)) ?? k}
          minCell={minCell}
        />
        <Cells
          caption={t(`window.series.${figures.series_step}`)}
          cells={figures.series}
          label={(k) => (figures.series_step === "month" ? k.slice(0, 7) : fmt.date(k))}
          minCell={minCell}
        />
      </div>
      <p className="muted">{t("window.floor", { n: minCell })}</p>
    </>
  );
}
