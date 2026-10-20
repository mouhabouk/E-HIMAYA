import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { PriorityBadge } from "../components/AiBadges";
import { CategoryLabel } from "../components/CategoryIcon";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import type { MapPolygon } from "../components/MapView";
import { GeoStateTag, SlaBandTag } from "../components/Phase9Bits";
import { GeoVerifyForm } from "../components/ReportHandling";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { applyLiveEvent } from "../lib/liveCache";
import { accuracyCircle } from "../lib/phase9";
import { p9Keys } from "../lib/phase9Api";
import { GEO_REASONS } from "../lib/phase9Types";
import { canGeoVerify } from "../lib/roles";
import type { StaffReport } from "../lib/types";

/** Map of one queued report: its point and accuracy circle, with the candidate gouvernorats listed beside it. */
function CandidateMap({ report }: { report: StaffReport }) {
  const { t } = useTranslation();
  const { mapStyleUrl } = useServices();
  const lang = useLanguage();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const { lat, lon, accuracy_m: accuracy } = report.location;
  const polygons = useMemo<MapPolygon[]>(
    () =>
      typeof accuracy === "number"
        ? [{ id: `acc-${report.id}`, coordinates: [accuracyCircle(lat, lon, accuracy)], tone: "medium", outline: "dashed" }]
        : [],
    [report.id, lat, lon, accuracy],
  );
  const pad = Math.max((accuracy ?? 500) / 111_320, 0.01) * 1.6;
  const candidates = report.geo_candidates ?? [];
  return (
    <div className="geo-map">
      <Suspense fallback={<Loading />}>
        <LazyMapView
          className="map map--mini"
          markers={[
            {
              id: report.id,
              lon,
              lat,
              status: report.status,
              category: report.category,
              title: report.tracking_code,
              subtitle: t(`status.${report.status}`),
              highlight: true,
            },
          ]}
          polygons={polygons}
          bounds={[lon - pad, lat - pad, lon + pad, lat + pad]}
          ariaLabel={t("geo.mapLabel", { code: report.tracking_code })}
          styleUrl={mapStyleUrl}
          dir={directionOf(lang)}
        />
      </Suspense>
      <dl className="fields">
        <dt>{t("detail.fields.coordinates")}</dt>
        <dd dir="ltr" className="code">
          {lat.toFixed(5)}, {lon.toFixed(5)}
          {typeof accuracy === "number" ? ` (± ${fmt.meters(accuracy)})` : ""}
        </dd>
        <dt>{t("geo.candidates")}</dt>
        <dd>
          {candidates.length === 0
            ? t("geo.noCandidate")
            : candidates.map((c) => gouvernorats.nameOf(c)).join(t("common.listSeparator"))}
        </dd>
        {report.geo_reason && (GEO_REASONS as readonly string[]).includes(report.geo_reason) && (
          <>
            <dt>{t("geo.label")}</dt>
            <dd>{t(`geo.reasonCode.${report.geo_reason}`)}</dd>
          </>
        )}
      </dl>
    </div>
  );
}

/**
 * Geographic verification queue of the central room (phase 9 §4.5): reports whose location is not trusted (no
 * gouvernorat yet), critical first. Critical ones are also pushed to their candidate rooms so they are not delayed.
 */
export function GeoQueuePage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [verified, setVerified] = useState<string | null>(null);
  const query = useInfiniteQuery({
    queryKey: p9Keys.geoQueue,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.geoQueue({ cursor: pageParam, signal }),
    getNextPageParam: (last) => last.next_cursor,
    refetchInterval: 30_000,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  const current = items.find((r) => r.id === selected) ?? null;
  const verifier = user ? canGeoVerify(user.identity) : false;

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("geo.queueTitle")}</h1>
        <Link to="/reports/late">{t("nav.late")}</Link>
      </div>
      <p className="muted">{t("geo.queueIntro")}</p>
      <div role="status" aria-live="polite">
        {verified && <p className="alert alert--ok">{t("geo.verifiedCode", { code: verified })}</p>}
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("geo.empty")}</p>}
      <div className="geo-queue">
        {items.length > 0 && (
          <ul className="geo-queue__list">
            {items.map((r) => (
              <li key={r.id} className={r.id === selected ? "is-selected" : undefined}>
                <button
                  type="button"
                  className="btn btn--ghost geo-queue__item"
                  aria-pressed={r.id === selected}
                  onClick={() => setSelected(r.id)}
                >
                  <span dir="ltr" className="code">
                    {r.tracking_code}
                  </span>{" "}
                  <CategoryLabel category={r.category} /> <PriorityBadge score={r.priority_score} />{" "}
                  <SlaBandTag band={r.sla_band} /> <GeoStateTag state={r.geo_state} />
                  <span className="muted"> · {fmt.dateTime(r.received_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {current && (
          <section className="card" aria-labelledby="geo-current">
            <h2 id="geo-current">
              {t("geo.selected")}{" "}
              <Link to={`/reports/${encodeURIComponent(current.id)}`} dir="ltr" className="code">
                {current.tracking_code}
              </Link>
            </h2>
            <CandidateMap report={current} />
            {verifier ? (
              <GeoVerifyForm
                key={current.id}
                report={current}
                onDone={(updated) => {
                  applyLiveEvent(qc, { type: "report.status_changed", report: updated });
                  void qc.invalidateQueries({ queryKey: p9Keys.geoQueue });
                  setVerified(updated.tracking_code);
                  setSelected(null);
                }}
              />
            ) : (
              <p className="muted">{t("geo.readOnly")}</p>
            )}
          </section>
        )}
      </div>
      {query.hasNextPage && (
        <button type="button" className="btn" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
          {t("reports.loadMore")}
        </button>
      )}
    </div>
  );
}
