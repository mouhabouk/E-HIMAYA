import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { CategoryLabel } from "../components/CategoryIcon";
import { ErrorBox, Loading } from "../components/Feedback";
import { ClaimBadge, EscalationTag, SlaBandTag, SlaCountdown } from "../components/Phase9Bits";
import { ClaimError } from "../components/ReportHandling";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { applyLiveEvent } from "../lib/liveCache";
import { useNow } from "../lib/phase9";
import { p9Keys } from "../lib/phase9Api";
import { mayClaim, roomOf } from "../lib/roles";
import type { StaffReport } from "../lib/types";

function ClaimButton({ report }: { report: StaffReport }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const claim = useMutation({
    mutationFn: () => api.claimReport(report.id),
    onSuccess: (updated) => {
      applyLiveEvent(qc, { type: "report.status_changed", report: updated });
      void qc.invalidateQueries({ queryKey: p9Keys.lateAll });
    },
  });
  return (
    <>
      <button
        type="button"
        className="btn btn--small btn--primary"
        disabled={claim.isPending}
        aria-label={t("late.claimLabel", { code: report.tracking_code })}
        onClick={() => claim.mutate()}
      >
        {t("late.claim")}
      </button>
      {claim.isError && <ClaimError error={claim.error} />}
    </>
  );
}

/**
 * Late list of the central room (phase 9 §4.4): reports past their claim deadline, the oldest deadline first, with
 * a live countdown. The central room may take over the answer (claim) and refer the report to a region from its
 * detail page.
 */
export function LateReportsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const now = useNow(1000);
  const base = useId();
  const [gouvernorat, setGouvernorat] = useState<number | null>(null);

  const query = useInfiniteQuery({
    queryKey: p9Keys.late(gouvernorat),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.lateReports({ cursor: pageParam, gouvernorat, signal }),
    getNextPageParam: (last) => last.next_cursor,
    refetchInterval: 30_000,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  const identity = user?.identity;
  const ownRoom = identity ? roomOf(identity) : null;

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("late.title")}</h1>
        <Link to="/reports/geo-queue">{t("nav.geoQueue")}</Link>
      </div>
      <p className="muted">{t("late.intro")}</p>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${base}-g`}>{t("filters.gouvernorat")}</label>
          <select
            id={`${base}-g`}
            value={gouvernorat ?? ""}
            onChange={(e) => setGouvernorat(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t("filters.allGouvernorats")}</option>
            {gouvernorats.list.map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("late.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("late.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("reports.columns.trackingCode")}</th>
                <th scope="col">{t("reports.columns.category")}</th>
                <th scope="col">{t("reports.columns.gouvernorat")}</th>
                <th scope="col">{t("sla.bandLabel")}</th>
                <th scope="col">{t("sla.deadline")}</th>
                <th scope="col">{t("escalation.label")}</th>
                <th scope="col">{t("claim.handledBy")}</th>
                <th scope="col">{t("late.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link to={`/reports/${encodeURIComponent(r.id)}`} dir="ltr" className="code">
                      {r.tracking_code}
                    </Link>
                    <div className="muted">{fmt.dateTime(r.received_at)}</div>
                  </td>
                  <td>
                    <CategoryLabel category={r.category} />
                  </td>
                  <td>{gouvernorats.nameOf(r.gouvernorat_code) ?? t("geo.unverified")}</td>
                  <td>
                    <SlaBandTag band={r.sla_band} />
                  </td>
                  <td>
                    <SlaCountdown dueAt={r.sla_due_at} now={now} />
                  </td>
                  <td>
                    <EscalationTag state={r.escalation_state} />
                  </td>
                  <td>
                    <ClaimBadge report={r} />
                  </td>
                  <td>
                    {identity && r.claimed_room !== ownRoom && mayClaim(identity, r) && <ClaimButton report={r} />}{" "}
                    <Link className="btn btn--small" to={`/reports/${encodeURIComponent(r.id)}`}>
                      {t("late.open")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && (
        <button type="button" className="btn" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
          {t("reports.loadMore")}
        </button>
      )}
    </div>
  );
}
