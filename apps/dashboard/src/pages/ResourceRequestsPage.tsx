import { useInfiniteQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { ResourceRequestItem } from "../components/ResourceRequests";
import { useServices } from "../context/services";
import { p9Keys } from "../lib/phase9Api";
import { RESOURCE_REQUEST_STATUSES, type ResourceRequestDirection, type ResourceRequestStatus } from "../lib/phase9Types";
import { PageTitle } from "../components/PageTitle";

/**
 * Resource requests between gouvernorats (phase 9 §5.4): incoming requests (to the user's gouvernorat, decided by
 * its ops manager or local committee) and outgoing ones (made by the user's room).
 */
export function ResourceRequestsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const base = useId();
  const [direction, setDirection] = useState<ResourceRequestDirection>("incoming");
  const [status, setStatus] = useState<ResourceRequestStatus | "">("pending");
  const query = useInfiniteQuery({
    queryKey: p9Keys.resourceRequests(direction, status),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.resourceRequests({ direction, status, cursor: pageParam, signal }),
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="inventory2" tone="amber">{t("resourceRequests.pageTitle")}</PageTitle>
      </div>
      <p className="muted">{t("resourceRequests.intro")}</p>
      <div className="filters__row">
        <fieldset className="segmented">
          <legend>{t("resourceRequests.direction")}</legend>
          {(["incoming", "outgoing"] as const).map((d) => (
            <label key={d} className="segmented__item">
              <input type="radio" name={`${base}-dir`} checked={direction === d} onChange={() => setDirection(d)} />
              <span>{t(`resourceRequests.${d}`)}</span>
            </label>
          ))}
        </fieldset>
        <div className="field">
          <label htmlFor={`${base}-status`}>{t("filters.status")}</label>
          <select id={`${base}-status`} value={status} onChange={(e) => setStatus(e.target.value as ResourceRequestStatus | "")}>
            <option value="">{t("notify.filters.all")}</option>
            {RESOURCE_REQUEST_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`resourceRequests.status.${s}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("resourceRequests.none")}</p>}
      {items.length > 0 && (
        <ul className="rr-list card">
          {items.map((r) => (
            <ResourceRequestItem key={r.id} request={r} showIncident />
          ))}
        </ul>
      )}
      {query.hasNextPage && (
        <button type="button" className="btn" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
          {t("reports.loadMore")}
        </button>
      )}
    </div>
  );
}
