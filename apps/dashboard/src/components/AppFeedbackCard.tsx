/**
 * Ratings of the mobile app (phase P5b, F-APP-143): the average, the share of each star, the average per build and
 * the latest remarks over a period. For the system administrator and the content editor; every reading is audited.
 * A rating is not a request: an answer goes through "contact us".
 */
import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { appFeedbackKeys, APP_FEEDBACK_PERIODS, starShares } from "../lib/appFeedback";
import { useFormat } from "../lib/hooks";
import { BarChart } from "./BarChart";
import { ErrorBox, Loading } from "./Feedback";

const STARS = [5, 4, 3, 2, 1] as const;

export function AppFeedbackCard() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const id = useId();
  const [days, setDays] = useState<number>(90);
  const query = useQuery({
    queryKey: appFeedbackKeys.summary(days),
    queryFn: ({ signal }) => api.appFeedback(days, signal),
  });
  const data = query.data;
  const shares = data ? starShares(data) : null;
  return (
    <section className="card" aria-labelledby={`${id}-title`} data-testid="app-feedback">
      <h2 id={`${id}-title`}>{t("settings.appFeedback.title")}</h2>
      <p className="muted">{t("settings.appFeedback.help")}</p>
      <label className="field" htmlFor={`${id}-period`}>
        <span>{t("settings.appFeedback.period")}</span>
        <select id={`${id}-period`} value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {APP_FEEDBACK_PERIODS.map((d) => (
            <option key={d} value={d}>
              {t("settings.appFeedback.days", { n: d })}
            </option>
          ))}
        </select>
      </label>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} />}
      {data && shares && (
        <>
          <dl className="kpis">
            <div className="card kpi">
              <dt className="kpi__label">{t("settings.appFeedback.average")}</dt>
              <dd className="kpi__value">
                {data.average === null ? t("common.notAvailable") : `${fmt.number(data.average)} / 5`}
              </dd>
            </div>
            <div className="card kpi">
              <dt className="kpi__label">{t("settings.appFeedback.count")}</dt>
              <dd className="kpi__value">{fmt.number(data.count)}</dd>
            </div>
          </dl>
          <BarChart
            caption={t("settings.appFeedback.byStars")}
            emptyText={t("settings.appFeedback.empty")}
            bars={STARS.map((s) => ({
              key: String(s),
              label: `${t("settings.appFeedback.stars", { n: s })} (${shares[s]}%)`,
              value: data.by_stars[String(s)] ?? 0,
            }))}
          />
          {data.by_build.length > 0 && (
            <div className="table-wrap">
              <table className="table">
                <caption>{t("settings.appFeedback.byBuild")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("settings.appFeedback.version")}</th>
                    <th scope="col">{t("settings.appFeedback.count")}</th>
                    <th scope="col">{t("settings.appFeedback.average")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_build.map((b) => (
                    <tr key={String(b.build)}>
                      <td>{b.version ?? (b.build === null ? t("common.notAvailable") : String(b.build))}</td>
                      <td>{fmt.number(b.count)}</td>
                      <td>{fmt.number(b.average)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <h3>{t("settings.appFeedback.remarks")}</h3>
          {data.remarks.length === 0 ? (
            <p className="muted">{t("settings.appFeedback.noRemarks")}</p>
          ) : (
            <ul className="remarks">
              {data.remarks.map((r, i) => (
                <li key={`${r.created_at}-${i}`}>
                  <strong>{t("settings.appFeedback.stars", { n: r.stars })}</strong>
                  <span className="muted">
                    {" · "}
                    {fmt.dateTime(r.created_at)}
                    {r.version ? ` · ${r.version}` : ""}
                  </span>
                  <p dir="auto">{r.remark}</p>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
