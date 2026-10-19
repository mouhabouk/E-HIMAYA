import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { IncidentStatusChip, PriorityBadge, ReportMarkers } from "../components/AiBadges";
import { CategoryLabel } from "../components/CategoryIcon";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import type { MapMarker } from "../components/MapView";
import { StatusChip } from "../components/StatusChip";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { errorMessageKey, isApiError } from "../lib/api";
import type { BBox } from "../lib/filters";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { canManageIncidents } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import { TIMELINE_KINDS, type IncidentDetail, type TimelineEntry } from "../lib/types";

const VIA = ["suggestion", "manual", "new"] as const;

/** Bounds around the centroid and every member report (at least ~1 km wide). */
export function incidentBounds(incident: IncidentDetail): BBox | null {
  const points = incident.reports.map((r) => [r.location.lon, r.location.lat] as const);
  if (incident.centroid) points.push([incident.centroid.lon, incident.centroid.lat]);
  if (points.length === 0) return null;
  const lons = points.map((p) => p[0]);
  const lats = points.map((p) => p[1]);
  const pad = 0.005;
  return [Math.min(...lons) - pad, Math.min(...lats) - pad, Math.max(...lons) + pad, Math.max(...lats) + pad];
}

function TimelineItem({ entry, incident }: { entry: TimelineEntry; incident: IncidentDetail }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { report_id: reportId, incident_id: otherId, via, reports } = entry.payload;
  const tracking =
    typeof reportId === "string" ? (incident.reports.find((r) => r.id === reportId)?.tracking_code ?? null) : null;
  return (
    <li>
      <strong>
        {(TIMELINE_KINDS as readonly string[]).includes(entry.kind)
          ? t(`incidents.timeline.${entry.kind}`)
          : t("incidents.timeline.other")}
      </strong>
      <time dateTime={entry.at}>{fmt.dateTime(entry.at)}</time>
      {entry.actor && <span className="muted">{t("detail.historyBy", { actor: entry.actor })}</span>}
      <p className="timeline__note">
        {typeof reportId === "string" && (
          <Link to={`/reports/${encodeURIComponent(reportId)}`} className={tracking ? "code" : undefined} dir="ltr">
            {tracking ?? t("incidents.detail.timelineReport")}
          </Link>
        )}
        {typeof via === "string" && (VIA as readonly string[]).includes(via) && (
          <span className="muted"> {t(`incidents.via.${via}`)}</span>
        )}
        {typeof otherId === "string" && (
          <Link to={`/incidents/${encodeURIComponent(otherId)}`}>{t("incidents.detail.timelineIncident")}</Link>
        )}
        {typeof reports === "number" && (
          <span className="muted"> {t("incidents.detail.timelineReports", { count: reports })}</span>
        )}
      </p>
    </li>
  );
}

/** Merge another open incident of the user's scope into this one, after an explicit confirmation. */
function MergeForm({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const selectId = useId();
  const [other, setOther] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState(false);

  const candidates = useQuery({
    queryKey: queryKeys.mergeCandidates,
    queryFn: ({ signal }) => api.incidents({ status: "open", limit: 200, signal }),
    select: (page) => page.items.filter((i) => i.id !== incident.id),
  });

  const mutation = useMutation({
    mutationFn: (otherId: string) => api.mergeIncident(incident.id, otherId),
    onSuccess: (updated, otherId) => {
      qc.setQueryData(queryKeys.incident(incident.id), updated);
      void qc.invalidateQueries({ queryKey: queryKeys.incident(otherId) });
      void qc.invalidateQueries({ queryKey: queryKeys.incidentsAll });
      void qc.invalidateQueries({ queryKey: queryKeys.mergeCandidates });
      void qc.invalidateQueries({ queryKey: queryKeys.reportsAll });
      setOther("");
      setConfirming(false);
      setDone(true);
    },
    onError: () => setConfirming(false),
  });

  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (!other) return;
    if (!confirming) {
      setDone(false);
      setConfirming(true);
      return;
    }
    mutation.mutate(other);
  };

  const list = candidates.data ?? [];
  return (
    <form className="merge-form" onSubmit={submit}>
      <p className="muted">{t("incidents.detail.mergeHelp")}</p>
      {candidates.isPending && <Loading />}
      {candidates.isError && <ErrorBox error={candidates.error} onRetry={() => void candidates.refetch()} />}
      {candidates.isSuccess && list.length === 0 && <p className="muted">{t("incidents.detail.mergeNoCandidate")}</p>}
      {list.length > 0 && (
        <>
          <div className="field">
            <label htmlFor={selectId}>{t("incidents.detail.mergePick")}</label>
            <select
              id={selectId}
              value={other}
              disabled={mutation.isPending}
              onChange={(e) => {
                setOther(e.target.value);
                setConfirming(false);
              }}
            >
              <option value="">{t("incidents.detail.mergeChoose")}</option>
              {list.map((i) => (
                <option key={i.id} value={i.id}>
                  {t("incidents.detail.mergeOption", {
                    category: t(`category.${i.category}`),
                    count: i.report_count,
                    date: fmt.dateTime(i.opened_at),
                  })}
                </option>
              ))}
            </select>
          </div>
          {confirming && (
            <p className="alert alert--warn" role="alert">
              {t("incidents.detail.mergeConfirmText")}
            </p>
          )}
          <div className="actions">
            <button type="submit" className="btn btn--primary" disabled={!other || mutation.isPending}>
              {mutation.isPending
                ? t("ai.grouping.working")
                : confirming
                  ? t("incidents.detail.mergeConfirm")
                  : t("incidents.detail.mergeAction")}
            </button>
            {confirming && (
              <button type="button" className="btn" onClick={() => setConfirming(false)}>
                {t("common.cancel")}
              </button>
            )}
          </div>
        </>
      )}
      <div aria-live="polite" role="status">
        {done && !mutation.isPending && <p className="alert alert--ok">{t("incidents.detail.merged")}</p>}
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </form>
  );
}

/** FR-C-02 (incident): summary, map, member reports, timeline and merge. */
export function IncidentDetailPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const canWrite = canManageIncidents(user?.identity.roles ?? []);

  const query = useQuery({
    queryKey: queryKeys.incident(id),
    queryFn: ({ signal }) => api.incident(id, signal),
    retry: (count, error) => !(isApiError(error) && [403, 404].includes(error.status)) && count < 2,
  });

  const incident = query.data;
  const markers = useMemo<MapMarker[]>(
    () =>
      (incident?.reports ?? []).map((r) => ({
        id: r.id,
        lon: r.location.lon,
        lat: r.location.lat,
        status: r.status,
        category: r.category,
        title: `${r.tracking_code} · ${t(`category.${r.category}`)}`,
        subtitle: `${t(`status.${r.status}`)} · ${fmt.dateTime(r.received_at)}`,
      })),
    [incident?.reports, t, fmt],
  );

  if (query.isPending) return <Loading />;
  if (query.isError || !incident)
    return (
      <div className="page">
        <Link to="/incidents">{t("incidents.detail.back")}</Link>
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );

  const bounds = incidentBounds(incident);

  return (
    <article className="page detail" aria-labelledby="incident-title">
      <p>
        <Link to="/incidents">{t("incidents.detail.back")}</Link>
      </p>
      <div className="page__head">
        <h1 id="incident-title">
          {t("incidents.detail.title")} · <CategoryLabel category={incident.category} />
        </h1>
        <IncidentStatusChip status={incident.status} />
        <PriorityBadge score={incident.severity} />
      </div>

      <div className="detail__grid">
        <section className="card" aria-labelledby="sec-summary">
          <h2 id="sec-summary">{t("incidents.detail.summary")}</h2>
          <dl className="fields">
            <dt>{t("incidents.columns.category")}</dt>
            <dd>
              <CategoryLabel category={incident.category} />
            </dd>
            <dt>{t("incidents.columns.severity")}</dt>
            <dd>
              <PriorityBadge score={incident.severity} />
            </dd>
            <dt>{t("incidents.columns.gouvernorat")}</dt>
            <dd>{gouvernorats.nameOf(incident.gouvernorat_code) ?? t("common.notAvailable")}</dd>
            <dt>{t("incidents.columns.reports")}</dt>
            <dd>{fmt.number(incident.report_count)}</dd>
            <dt>{t("incidents.columns.reporters")}</dt>
            <dd>{fmt.number(incident.reporter_count)}</dd>
            <dt>{t("incidents.detail.openedAt")}</dt>
            <dd>{fmt.dateTime(incident.opened_at)}</dd>
            <dt>{t("incidents.columns.updatedAt")}</dt>
            <dd>{fmt.dateTime(incident.updated_at)}</dd>
            {incident.closed_at && (
              <>
                <dt>{t("incidents.detail.closedAt")}</dt>
                <dd>{fmt.dateTime(incident.closed_at)}</dd>
              </>
            )}
            {incident.merged_into && (
              <>
                <dt>{t("incidents.detail.mergedInto")}</dt>
                <dd>
                  <Link to={`/incidents/${encodeURIComponent(incident.merged_into)}`}>
                    {t("incidents.detail.openMerged")}
                  </Link>
                </dd>
              </>
            )}
            {incident.centroid && (
              <>
                <dt>{t("incidents.detail.centroid")}</dt>
                <dd dir="ltr" className="code">
                  {incident.centroid.lat.toFixed(5)}, {incident.centroid.lon.toFixed(5)}
                </dd>
              </>
            )}
          </dl>
        </section>

        <section className="card" aria-labelledby="sec-incident-map">
          <h2 id="sec-incident-map">{t("detail.location")}</h2>
          {bounds ? (
            <Suspense fallback={<Loading />}>
              <LazyMapView
                className="map map--mini"
                markers={markers}
                bounds={bounds}
                zoom={15}
                ariaLabel={t("incidents.detail.map")}
                styleUrl={mapStyleUrl}
                dir={directionOf(lang)}
                centroid={
                  incident.centroid
                    ? { ...incident.centroid, label: t("incidents.detail.centroidMarker") }
                    : null
                }
              />
            </Suspense>
          ) : (
            <p className="muted">{t("common.notAvailable")}</p>
          )}
        </section>
      </div>

      <section className="card" aria-labelledby="sec-members">
        <h2 id="sec-members">
          {t("incidents.detail.reports")} ({fmt.number(incident.reports.length)})
        </h2>
        {incident.reports.length === 0 ? (
          <p className="muted">{t("incidents.detail.noReports")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">{t("incidents.detail.reports")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("reports.columns.priority")}</th>
                  <th scope="col">{t("reports.columns.trackingCode")}</th>
                  <th scope="col">{t("reports.columns.category")}</th>
                  <th scope="col">{t("reports.columns.status")}</th>
                  <th scope="col">{t("reports.columns.receivedAt")}</th>
                </tr>
              </thead>
              <tbody>
                {incident.reports.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <PriorityBadge score={r.priority_score} />
                    </td>
                    <td>
                      <Link to={`/reports/${encodeURIComponent(r.id)}`} className="code" dir="ltr">
                        {r.tracking_code}
                      </Link>
                      <ReportMarkers report={{ ...r, incident_id: null }} />
                    </td>
                    <td>
                      <CategoryLabel category={r.category} />
                    </td>
                    <td>
                      <StatusChip status={r.status} />
                    </td>
                    <td>
                      <time dateTime={r.received_at}>{fmt.dateTime(r.received_at)}</time>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="detail__grid">
        <section className="card" aria-labelledby="sec-timeline">
          <h2 id="sec-timeline">{t("incidents.detail.timeline")}</h2>
          {incident.timeline.length === 0 ? (
            <p className="muted">{t("detail.noHistory")}</p>
          ) : (
            <ol className="timeline">
              {incident.timeline.map((e, i) => (
                <TimelineItem key={`${e.at}-${i}`} entry={e} incident={incident} />
              ))}
            </ol>
          )}
        </section>

        {canWrite && incident.status === "open" && (
          <section className="card" aria-labelledby="sec-merge">
            <h2 id="sec-merge">{t("incidents.detail.merge")}</h2>
            <MergeForm incident={incident} />
          </section>
        )}
      </div>
    </article>
  );
}
