import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import type { AnalyticsFilters } from "../lib/analytics";
import { useFormat, useGouvernorats } from "../lib/hooks";
import {
  CROSS_DIMENSIONS,
  type CrossDimension,
  type CrossTab as CrossTabData,
} from "../lib/phase8Types";
import { ErrorBox, Loading } from "./Feedback";

/** Labels of a dimension's keys, from the vocabularies the dashboard already has. */
function useKeyLabel() {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  return (dim: CrossDimension, key: string): string => {
    switch (dim) {
      case "category":
        return t(`category.${key}`);
      case "classification":
        return t(`ops.classification.${key}`, {
          defaultValue: t(`category.${key}`, { defaultValue: key }),
        });
      case "gouvernorat":
        return gouvernorats.nameOf(Number(key)) ?? key;
      case "resource":
        return key === "none"
          ? t("analytics.cross.noResource")
          : t(`resources.kind.${key}`, { defaultValue: key });
      case "level":
        return t(`levels.name.${key}`, { defaultValue: key });
      case "month":
        return t(`analytics.cross.month.${key}`);
      case "quarter":
        return t("analytics.cross.quarter", { n: key });
      case "weekday":
        return t(`analytics.weekday.${key}`);
      case "hour":
        return `${key.padStart(2, "0")}:00`;
    }
  };
}

function Change({ pct }: { pct: number | null }) {
  const { t } = useTranslation();
  if (pct === null)
    return <span className="muted">{t("analytics.cross.new")}</span>;
  const tone = pct > 0 ? "cross__up" : pct < 0 ? "cross__down" : "muted";
  return (
    <span className={tone} dir="ltr">
      {pct > 0 ? "+" : ""}
      {pct}%
    </span>
  );
}

/** Cross-tabulations: interventions across two dimensions, each cell beside the same period one year earlier, and
 * the findings worth a sentence ("ارتفاع في عدد حرائق المحاصيل الزراعية بنسبة 15%"). */
export function CrossSection({ filters }: { filters: AnalyticsFilters }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const label = useKeyLabel();
  const id = useId();
  const [rows, setRows] = useState<CrossDimension>("classification");
  const [cols, setCols] = useState<CrossDimension>("month");
  const table = useQuery({
    queryKey: [
      "analytics",
      "crosstab",
      filters.from,
      filters.to,
      filters.gouvernorat,
      rows,
      cols,
    ],
    queryFn: ({ signal }) => api.analyticsCrosstab(filters, rows, cols, signal),
    placeholderData: keepPreviousData,
    enabled: rows !== cols,
  });
  const findings = useQuery({
    queryKey: [
      "analytics",
      "findings",
      filters.from,
      filters.to,
      filters.gouvernorat,
    ],
    queryFn: ({ signal }) => api.analyticsFindings(filters, signal),
  });
  const select = (
    value: CrossDimension,
    onChange: (d: CrossDimension) => void,
    labelKey: string,
  ) => (
    <div className="field">
      <label htmlFor={`${id}-${labelKey}`}>
        {t(`analytics.cross.${labelKey}`)}
      </label>
      <select
        id={`${id}-${labelKey}`}
        value={value}
        onChange={(e) => onChange(e.target.value as CrossDimension)}
      >
        {CROSS_DIMENSIONS.map((d) => (
          <option key={d} value={d}>
            {t(`analytics.cross.dim.${d}`)}
          </option>
        ))}
      </select>
    </div>
  );
  const data: CrossTabData | undefined = table.data;
  return (
    <section className="card" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{t("analytics.cross.title")}</h2>
      <p className="muted">{t("analytics.cross.intro")}</p>
      {findings.data && findings.data.length > 0 && (
        <ul
          className="cross__findings"
          aria-label={t("analytics.cross.findings")}
        >
          {findings.data.map((f) => (
            <li
              key={`${f.dimension}-${f.key}-${f.gouvernorat_code ?? 0}`}
              className={f.change_pct > 0 ? "cross__up" : "cross__down"}
            >
              {f.text_ar}
            </li>
          ))}
        </ul>
      )}
      <div className="filters__row">
        {select(rows, setRows, "rows")}
        {select(cols, setCols, "cols")}
      </div>
      {rows === cols && (
        <p className="alert alert--info">
          {t("analytics.cross.sameDimension")}
        </p>
      )}
      {table.isPending && rows !== cols && <Loading />}
      {table.isError && (
        <ErrorBox error={table.error} onRetry={() => void table.refetch()} />
      )}
      {data && data.row_keys.length === 0 && (
        <p className="muted">{t("analytics.noData")}</p>
      )}
      {data && data.row_keys.length > 0 && (
        <div className="table-wrap">
          <table className="table cross">
            <caption className="muted">
              {t("analytics.cross.caption", {
                from: fmt.date(data.from),
                to: fmt.date(data.to),
                pfrom: fmt.date(data.previous_from),
                pto: fmt.date(data.previous_to),
              })}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t(`analytics.cross.dim.${data.rows}`)}</th>
                {data.col_keys.map((c) => (
                  <th key={c} scope="col">
                    {label(data.cols, c)}
                  </th>
                ))}
                <th scope="col">{t("analytics.cross.total")}</th>
              </tr>
            </thead>
            <tbody>
              {data.row_keys.map((r, ri) => (
                <tr key={r}>
                  <th scope="row">{label(data.rows, r)}</th>
                  {(data.cells[ri] ?? []).map((cell, ci) => (
                    <td
                      key={data.col_keys[ci]}
                      title={t("analytics.cross.previous", {
                        n: cell.previous,
                      })}
                    >
                      <strong>{fmt.number(cell.count)}</strong>{" "}
                      {(cell.count > 0 || cell.previous > 0) && (
                        <Change pct={cell.change_pct} />
                      )}
                    </td>
                  ))}
                  <td>
                    <strong>
                      {fmt.number(data.row_totals[ri]?.count ?? 0)}
                    </strong>{" "}
                    <Change pct={data.row_totals[ri]?.change_pct ?? null} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
