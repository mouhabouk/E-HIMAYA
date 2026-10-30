import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { PriorityBadge, VerificationBadge } from "../components/AiBadges";
import { AnalysisPanel } from "../components/AnalysisPanel";
import { ReporterSection } from "../components/BreakGlass";
import { LocationHistorySearch, MedicalSection } from "../components/SafetyReportBits";
import { CategoryLabel } from "../components/CategoryIcon";
import { ErrorBox, Loading } from "../components/Feedback";
import { GroupingSection } from "../components/GroupingSection";
import { LazyMapView } from "../components/LazyMap";
import { LinkedStreams } from "../components/LinkedStreams";
import { VisionImage, VisionSummary, visionDetections } from "../components/VisionResults";
import { OrganizationCardPanel } from "../components/OrganizationCardPanel";
import { ClaimBadge, EscalationTag, GeoStateTag } from "../components/Phase9Bits";
import { ReportHandling } from "../components/ReportHandling";
import { LearningLabelSection } from "../components/LearningLabel";
import { featureKindLabel, MapLegend, orgKindLabel, orgPois, pointsBounds, useLegendItems } from "../components/OrgBits";
import { StatusChip } from "../components/StatusChip";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { applyLiveEvent } from "../lib/liveCache";
import { localizedName } from "../lib/localized";
import { directionOf } from "../i18n";
import { statusChoices, TRANSITIONS } from "../lib/status";
import { canChangeStatus } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import type { Media, ReportStatus, StaffReportDetail } from "../lib/types";
import { useDraft } from "../lib/drafts";
import { PageTitle } from "../components/PageTitle";
import { MaskedText } from "../components/MaskedText";

function MediaItem({ media, onBroken }: { media: Media; onBroken: () => void }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const label = t(`detail.mediaKind.${media.kind}`);
  const playable = media.status === "stored" && media.url;
  return (
    <li className="media card">
      <div className="media__preview">
        {playable && media.kind === "image" && (
          <a href={media.url ?? undefined} target="_blank" rel="noopener noreferrer">
            <VisionImage src={media.url ?? ""} alt={label} detections={visionDetections(media.analysis)} onError={onBroken} />
          </a>
        )}
        {playable && (media.kind === "video" || media.kind === "recording") && (
          <video controls preload="metadata" aria-label={label} onError={onBroken}>
            <source src={media.url ?? undefined} type={media.content_type ?? undefined} onError={onBroken} />
          </video>
        )}
        {playable && media.kind === "audio" && (
          <audio controls preload="metadata" aria-label={label} onError={onBroken}>
            <source src={media.url ?? undefined} type={media.content_type ?? undefined} onError={onBroken} />
          </audio>
        )}
        {!playable && media.status === "quarantined" && (
          <>
            <p className="muted">{t("detail.mediaQuarantined")}</p>
            {media.url && (
              <a href={media.url} rel="noopener noreferrer" download>
                {t("detail.mediaDownload")}
              </a>
            )}
          </>
        )}
        {!playable && media.status !== "quarantined" && <p className="muted">{t("detail.mediaUnavailable")}</p>}
      </div>
      <dl className="media__meta">
        <dt>{t("detail.mediaType")}</dt>
        <dd>{label}</dd>
        <dt>{t("detail.mediaStatusLabel")}</dt>
        <dd>
          <span className={`tag tag--media-${media.status}`}>{t(`detail.mediaStatus.${media.status}`)}</span>
        </dd>
        {media.rejection_reason && (
          <>
            <dt>{t("detail.mediaRejectionLabel")}</dt>
            <dd>{t(`detail.mediaRejection.${media.rejection_reason}`)}</dd>
          </>
        )}
        <dt>{t("detail.size")}</dt>
        <dd>{media.bytes === null ? t("common.notAvailable") : fmt.bytes(media.bytes)}</dd>
        {typeof media.duration_s === "number" && (
          <>
            <dt>{t("streams.columns.duration")}</dt>
            <dd>{fmt.duration(media.duration_s)}</dd>
          </>
        )}
        {media.stream_id && (
          <>
            <dt>{t("streams.report.stream")}</dt>
            <dd>
              <Link to={`/streams/${encodeURIComponent(media.stream_id)}`}>{t("streams.report.openStream")}</Link>
            </dd>
          </>
        )}
        <dt>{t("detail.sha256")}</dt>
        <dd className="hash" dir="ltr">
          {media.sha256}
        </dd>
      </dl>
      <VisionSummary analysis={media.analysis} />
    </li>
  );
}

function StatusChangeForm({ report }: { report: StaffReportDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const roles = user?.identity.roles ?? [];
  const options = statusChoices(report, roles);
  const [next, setNext] = useState<ReportStatus | "">("");
  const [note, setNote, clearNote] = useDraft(`report:${report.id}:status-note`);
  const [done, setDone] = useState(false);
  // Backlog G4: the status this operator was looking at when they started writing; a live change shows a notice.
  const [seenStatus, setSeenStatus] = useState(report.status);
  const noteId = useId();
  const groupName = useId();
  const key = queryKeys.report(report.id);

  const mutation = useMutation({
    mutationFn: (v: { status: ReportStatus; note: string }) => api.changeStatus(report.id, v.status, v.note),
    onMutate: async (v) => {
      await qc.cancelQueries({ queryKey: key });
      const previous = qc.getQueryData<StaffReportDetail>(key);
      if (previous) {
        qc.setQueryData<StaffReportDetail>(key, {
          ...previous,
          status: v.status,
          allowed_transitions: [...TRANSITIONS[v.status]],
          history: [
            ...previous.history,
            { status: v.status, at: new Date().toISOString(), actor: null, note: v.note || null },
          ],
        });
      }
      return { previous };
    },
    onError: (error, _v, context) => {
      // Roll back the optimistic status; on 409 someone else changed it first — fetch the truth.
      if (context?.previous) qc.setQueryData(key, context.previous);
      if (isApiError(error) && error.status === 409) void qc.invalidateQueries({ queryKey: key });
    },
    onSuccess: (updated) => {
      qc.setQueryData(key, updated);
      applyLiveEvent(qc, { type: "report.status_changed", report: updated });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
      setNext("");
      clearNote();
      setSeenStatus(updated.status);
      setDone(true);
    },
  });
  // The optimistic update changes the status while the request runs; only a change from elsewhere counts.
  const changedUnderneath = !mutation.isPending && note.trim() !== "" && report.status !== seenStatus;

  if (!canChangeStatus(roles)) return <p className="muted">{t("detail.readOnly")}</p>;
  if (options.length === 0) return <p className="muted">{t("detail.final")}</p>;

  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (!next) return;
    setDone(false);
    mutation.mutate({ status: next, note: note.trim() });
  };

  return (
    <form className="status-form" onSubmit={submit}>
      {changedUnderneath && (
        <div className="alert alert--warn" role="status" data-testid="draft-changed">
          <p>{t("drafts.changedWhileTyping")}</p>
          <button type="button" className="btn" onClick={() => setSeenStatus(report.status)}>
            {t("drafts.acknowledge")}
          </button>
        </div>
      )}
      <fieldset>
        <legend>{t("detail.newStatus")}</legend>
        {options.map((s) => (
          <label key={s} className="radio">
            <input
              type="radio"
              name={groupName}
              value={s}
              checked={next === s}
              onChange={() => setNext(s)}
              disabled={mutation.isPending}
            />
            <StatusChip status={s} />
          </label>
        ))}
      </fieldset>
      <div className="field">
        <label htmlFor={noteId}>{t("detail.note")}</label>
        <textarea
          id={noteId}
          value={note}
          maxLength={1000}
          rows={3}
          onChange={(e) => setNote(e.target.value)}
          disabled={mutation.isPending}
          dir="auto"
        />
      </div>
      <button type="submit" className="btn btn--primary" disabled={!next || mutation.isPending}>
        {mutation.isPending ? t("detail.applying") : t("detail.apply")}
      </button>
      <div aria-live="polite" role="status">
        {done && !mutation.isPending && <p className="alert alert--ok">{t("detail.changed")}</p>}
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </form>
  );
}

/** FR-C-02 (detail): every field of a report, its media, history, the status control and the AI analysis. */
export function ReportDetailPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const navigate = useNavigate();

  const query = useQuery({
    queryKey: queryKeys.report(id),
    queryFn: ({ signal }) => api.report(id, signal),
    // Media URLs are pre-signed for 10 minutes: keep them fresh while the page is open.
    staleTime: 60_000,
    refetchInterval: 8 * 60_000,
    retry: (count, error) => !(isApiError(error) && [403, 404].includes(error.status)) && count < 2,
  });

  // Institution and its features (evacuation points, water points, alarms) drawn on the report's map.
  const card = query.data?.organization_card ?? null;
  const pois = useMemo(
    () =>
      card
        ? orgPois(card, card.hazmat.length > 0, card.features, (f) => f.label ?? featureKindLabel(t, f.kind), orgKindLabel(t, card.kind)).map(
            (p) => (p.id === card.id ? { ...p, href: `/orgs/${encodeURIComponent(card.id)}` } : p),
          )
        : [],
    [card, t],
  );
  const legend = useLegendItems((card?.hazmat.length ?? 0) > 0);

  if (query.isPending) return <Loading />;
  if (query.isError)
    return (
      <div className="page">
        <Link to="/reports">{t("detail.back")}</Link>
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );

  const r = query.data;
  const { lon, lat, accuracy_m } = r.location;
  const delta = 0.01;
  const withOrg = pointsBounds([{ lon, lat }, ...pois], 0.004);
  const bounds = withOrg && pois.length > 0 ? withOrg : ([lon - delta, lat - delta, lon + delta, lat + delta] as const);

  return (
    <article className="page detail" aria-labelledby="detail-title">
      <p>
        <Link to="/reports">{t("detail.back")}</Link>
      </p>
      <div className="page__head">
        <PageTitle icon="description" tone="red" id="detail-title">
          {t("detail.title")} <span dir="ltr" className="code">{r.tracking_code}</span>
        </PageTitle>
        <StatusChip status={r.status} />
        <PriorityBadge score={r.priority_score} />
        <VerificationBadge report={r} />
        <ClaimBadge report={r} />
        <EscalationTag state={r.escalation_state} />
        <GeoStateTag state={r.geo_state} />
        {r.organization && (
          <Link to={`/orgs/${encodeURIComponent(r.organization.id)}`} className="tag tag--org">
            {t("orgs.reportOnBehalf", { name: r.organization.name })}
          </Link>
        )}
      </div>

      <div className="detail__grid">
        <section className="card" aria-labelledby="sec-info">
          <h2 id="sec-info">{t("detail.info")}</h2>
          <dl className="fields">
            <dt>{t("detail.fields.category")}</dt>
            <dd>
              <CategoryLabel category={r.category} />
            </dd>
            <dt>{t("detail.fields.receivedAt")}</dt>
            <dd>{fmt.dateTime(r.received_at)}</dd>
            <dt>{t("detail.fields.createdAt")}</dt>
            <dd>{fmt.dateTime(r.created_at)}</dd>
            <dt>{t("detail.fields.updatedAt")}</dt>
            <dd>{fmt.dateTime(r.updated_at)}</dd>
            <dt>{t("detail.fields.gouvernorat")}</dt>
            <dd>{gouvernorats.nameOf(r.gouvernorat_code) ?? t("common.notAvailable")}</dd>
            <dt>{t("detail.fields.delegation")}</dt>
            <dd dir="auto">{r.address?.delegation ? localizedName(r.address.delegation, lang) : t("common.notAvailable")}</dd>
            <dt>{t("detail.fields.sector")}</dt>
            <dd dir="auto">{r.address?.sector ? localizedName(r.address.sector, lang) : t("common.notAvailable")}</dd>
            <dt>{t("detail.fields.municipality")}</dt>
            <dd dir="auto">
              {r.address?.municipality ? localizedName(r.address.municipality, lang) : t("common.notAvailable")}
            </dd>
            <dt>{t("detail.fields.reporterKind")}</dt>
            <dd>{t(`reporterKind.${r.reporter_kind}`)}</dd>
            <dt>{t("detail.fields.coordinates")}</dt>
            <dd dir="ltr" className="code">
              {lat.toFixed(5)}, {lon.toFixed(5)}
              {typeof accuracy_m === "number" && ` (± ${fmt.meters(accuracy_m)})`}
            </dd>
          </dl>
        </section>

        <section className="card" aria-labelledby="sec-location">
          <h2 id="sec-location">{t("detail.location")}</h2>
          <Suspense fallback={<Loading />}>
            <LazyMapView
              className="map map--mini"
              markers={[
                {
                  id: r.id,
                  lon,
                  lat,
                  status: r.status,
                  category: r.category,
                  title: r.tracking_code,
                  subtitle: t(`status.${r.status}`),
                },
              ]}
              bounds={bounds}
              zoom={15}
              ariaLabel={t("detail.mapLabel")}
              styleUrl={mapStyleUrl}
              dir={directionOf(lang)}
              pois={pois}
              poiOpenLabel={t("orgs.layer.open")}
              onOpenPoi={(href) => void navigate(href)}
            />
          </Suspense>
          {pois.length > 0 && <MapLegend items={legend} />}
        </section>

        {r.organization_card && <OrganizationCardPanel card={r.organization_card} />}

        <section className="card" aria-labelledby="sec-text">
          <h2 id="sec-text">{t("detail.text")}</h2>
          {r.text ? (
            <>
              <p className="muted">
                {t("detail.textLang", { lang: r.lang ? t(`languages.${r.lang}`) : t("common.notAvailable") })}
              </p>
              <blockquote className="report-text" lang={r.lang ?? undefined} dir="auto">
                <MaskedText text={r.text} masks={r.text_masks} />
              </blockquote>
              {r.text_ar && (
                <>
                  <p className="muted translation-label">{t("ai.translation")}</p>
                  <blockquote className="report-text report-text--translation" lang="ar" dir="rtl">
                    <MaskedText text={r.text_ar} masks={r.text_ar_masks} />
                  </blockquote>
                </>
              )}
            </>
          ) : (
            <p className="muted">{t("detail.noText")}</p>
          )}
        </section>

        <ReporterSection report={r} />
        <MedicalSection report={r} />
        <LocationHistorySearch report={r} />

        <ReportHandling report={r} />

        <section className="card" aria-labelledby="sec-status">
          <h2 id="sec-status">{t("detail.statusChange")}</h2>
          <StatusChangeForm report={r} />
        </section>

        <LearningLabelSection report={r} />

        <GroupingSection report={r} />

        <section className="card" aria-labelledby="sec-history">
          <h2 id="sec-history">{t("detail.history")}</h2>
          {r.history.length === 0 ? (
            <p className="muted">{t("detail.noHistory")}</p>
          ) : (
            <ol className="timeline">
              {r.history.map((h, i) => (
                <li key={`${h.at}-${i}`}>
                  <StatusChip status={h.status} />
                  <time dateTime={h.at}>{fmt.dateTime(h.at)}</time>
                  {h.actor && (
                    <span className="muted">
                      {t("detail.historyBy", { actor: h.actor })}
                    </span>
                  )}
                  {h.note && (
                    <p className="timeline__note" dir="auto">
                      {h.note}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <AnalysisPanel report={r} />

      <LinkedStreams report={r} />

      <section className="card" aria-labelledby="sec-media">
        <h2 id="sec-media">
          {t("detail.media")} ({fmt.number(r.media.length)})
        </h2>
        {r.media.length === 0 ? (
          <p className="muted">{t("detail.noMedia")}</p>
        ) : (
          <ul className="gallery">
            {r.media.map((m) => (
              <MediaItem
                key={m.id}
                media={m}
                onBroken={() => {
                  // An expired pre-signed URL: fetch fresh ones, at most once a minute.
                  if (Date.now() - query.dataUpdatedAt > 60_000) void query.refetch();
                }}
              />
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}
