import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { BarChart, type Bar } from "../components/BarChart";
import { CategoryLabel } from "../components/CategoryIcon";
import { ErrorBox, Loading } from "../components/Feedback";
import { PeriodSelector } from "../components/FiltersBar";
import { StatusChip } from "../components/StatusChip";
import { useServices } from "../context/services";
import { periodSince, type Period } from "../lib/filters";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { queryKeys } from "../lib/staffApi";
import { CATEGORIES, REPORT_STATUSES, type Kpis } from "../lib/types";

function KpiCard({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className={`kpi card ${tone ?? ""}`}>
      <dt className="kpi__label">{label}</dt>
      <dd className="kpi__value">{value}</dd>
    </div>
  );
}

const IN_PROGRESS_STATUSES = ["in_progress", "intervened", "ongoing"] as const;

export function summarize(kpis: Kpis) {
  const s = kpis.by_status;
  return {
    total: kpis.total,
    received: s.received ?? 0,
    inProgress: IN_PROGRESS_STATUSES.reduce((n, k) => n + (s[k] ?? 0), 0),
    closed: s.closed ?? 0,
  };
}

/** FR-C-01: key indicators for the user's scope, refreshed on live events. */
export function HomePage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const [period, setPeriod] = useState<Period>("24h");

  const query = useQuery({
    queryKey: queryKeys.kpis(period),
    queryFn: ({ signal }) => api.kpis(periodSince(period), signal),
    refetchInterval: 5 * 60_000,
  });

  const charts = useMemo(() => {
    if (!query.data) return null;
    const k = query.data;
    const byStatus: Bar[] = REPORT_STATUSES.map((s) => ({
      key: s,
      label: <StatusChip status={s} />,
      value: k.by_status[s] ?? 0,
      tone: `bar--${s}`,
    }));
    const byCategory: Bar[] = CATEGORIES.map((c) => ({
      key: c,
      label: <CategoryLabel category={c} />,
      value: k.by_category[c] ?? 0,
    }))
      .filter((b) => b.value > 0)
      .sort((a, b) => b.value - a.value);
    const byGouvernorat: Bar[] = [...k.by_gouvernorat]
      .sort((a, b) => b.count - a.count)
      .map((g) => ({
        key: String(g.code ?? "none"),
        label: g.code === null ? t("kpi.outsideGouvernorats") : (gouvernorats.nameOf(g.code) ?? String(g.code)),
        value: g.count,
      }));
    return { byStatus, byCategory, byGouvernorat };
  }, [query.data, t, gouvernorats]);

  const summary = query.data ? summarize(query.data) : null;

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("kpi.title")}</h1>
        <PeriodSelector value={period} onChange={setPeriod} />
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && summary && charts && (
        <>
          <p className="muted">{t("kpi.since", { date: fmt.dateTime(query.data.since) })}</p>
          <dl className="kpis">
            <KpiCard label={t("kpi.total")} value={fmt.number(summary.total)} />
            <KpiCard label={t("kpi.received")} value={fmt.number(summary.received)} tone="kpi--received" />
            <KpiCard label={t("kpi.inProgress")} value={fmt.number(summary.inProgress)} tone="kpi--in_progress" />
            <KpiCard label={t("kpi.closed")} value={fmt.number(summary.closed)} tone="kpi--closed" />
            <KpiCard
              label={t("kpi.avgFirstResponse")}
              value={
                query.data.avg_first_response_s === null
                  ? t("common.notAvailable")
                  : fmt.duration(query.data.avg_first_response_s)
              }
            />
          </dl>
          <div className="charts">
            <BarChart caption={t("kpi.byStatus")} bars={charts.byStatus} emptyText={t("kpi.noData")} />
            <BarChart caption={t("kpi.byCategory")} bars={charts.byCategory} emptyText={t("kpi.noData")} />
            <BarChart caption={t("kpi.byGouvernorat")} bars={charts.byGouvernorat} emptyText={t("kpi.noData")} />
          </div>
        </>
      )}
    </div>
  );
}
