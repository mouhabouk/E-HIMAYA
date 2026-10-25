import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { CategoryLabel } from "../components/CategoryIcon";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import {
  alertLabel,
  CertificateChip,
  DownloadButton,
  equipmentKindLabel,
  familyLabel,
  featureKindLabel,
  formatDay,
  hazmatQuantity,
  MaintenanceBadge,
  MapLegend,
  orgKindLabel,
  orgPois,
  OrgStatusChip,
  pointsBounds,
  requirementLabel,
  TrainingBadge,
  useLegendItems,
} from "../components/OrgBits";
import { StatusChip } from "../components/StatusChip";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { decisionNeedsReason, reviewDecisions } from "../lib/orgs";
import { canReviewOrgs } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import {
  DOCUMENT_KINDS,
  isOneOf,
  MEMBER_ROLES,
  TEAM_ROLES,
  type DocumentVersion,
  type OrgDecision,
  type OrgDocument,
  type StaffOrgDetail,
} from "../lib/types";
import { PageTitle } from "../components/PageTitle";

function Phone({ phone }: { phone: string | null | undefined }) {
  const { t } = useTranslation();
  if (!phone) return <>{t("common.notAvailable")}</>;
  return (
    <a href={`tel:${phone}`} dir="ltr">
      {phone}
    </a>
  );
}

function Email({ email }: { email: string | null | undefined }) {
  const { t } = useTranslation();
  if (!email) return <>{t("common.notAvailable")}</>;
  return (
    <a href={`mailto:${email}`} dir="ltr">
      {email}
    </a>
  );
}

// ---------- Registration review (org_auditor only) ----------

function OrgReviewSection({ org }: { org: StaffOrgDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const fmt = useFormat();
  const reasonId = useId();
  const canReview = canReviewOrgs(user?.identity.roles ?? []);
  const decisions = reviewDecisions(org.status);
  const [decision, setDecision] = useState<OrgDecision | null>(null);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState(false);
  const [done, setDone] = useState(false);
  const key = queryKeys.org(org.id);

  const mutation = useMutation({
    mutationFn: (v: { decision: OrgDecision; reason: string }) => api.reviewOrg(org.id, v),
    onSuccess: (updated) => {
      qc.setQueryData(key, updated);
      void qc.invalidateQueries({ queryKey: queryKeys.orgsAll });
      void qc.invalidateQueries({ queryKey: queryKeys.orgsMapAll });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
      setDecision(null);
      setReason("");
      setDone(true);
    },
    onError: (error) => {
      // Someone else decided first: load the current state (this detail is on screen).
      if (isApiError(error) && error.status === 409) void qc.invalidateQueries({ queryKey: key, exact: true });
    },
  });

  const lastDecision =
    (org.status === "rejected" || org.status === "suspended") && org.review?.reason ? (
      <p className="alert alert--warn">
        <strong>{t("orgs.detail.lastDecision")}: </strong>
        <span dir="auto">{org.review.reason}</span>
        {org.review.at && <span className="muted"> · {fmt.dateTime(org.review.at)}</span>}
      </p>
    ) : null;

  if (!canReview) {
    return (
      <>
        {lastDecision}
        <p className="muted">{t("orgs.review.readOnly")}</p>
      </>
    );
  }

  const needsReason = decision !== null && decisionNeedsReason(decision);
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (!decision) return;
    if (needsReason && !reason.trim()) {
      setReasonError(true);
      return;
    }
    mutation.mutate({ decision, reason: reason.trim() });
  };
  const errorText = mutation.isError
    ? isApiError(mutation.error) && mutation.error.code === "invalid_transition"
      ? t("orgs.review.invalidTransition")
      : t(errorMessageKey(mutation.error))
    : null;

  return (
    <div className="review">
      {lastDecision}
      {decisions.length === 0 ? (
        <p className="muted">{t("orgs.review.none")}</p>
      ) : (
        <div className="actions">
          {decisions.map((d) => (
            <button
              key={d}
              type="button"
              className={`btn${d === "approve" || d === "reinstate" ? " btn--primary" : ""}`}
              aria-pressed={decision === d}
              disabled={mutation.isPending}
              onClick={() => {
                setDecision(d);
                setReasonError(false);
                setDone(false);
                mutation.reset();
              }}
            >
              {t(`orgs.review.decision.${d}`)}
            </button>
          ))}
        </div>
      )}
      {decision && (
        <form className="review__confirm" onSubmit={submit} noValidate>
          <p className="alert alert--warn" role="alert">
            {t(`orgs.review.confirmText.${decision}`)}
          </p>
          <div className={`field${reasonError ? " field--invalid" : ""}`}>
            <label htmlFor={reasonId}>{needsReason ? t("orgs.review.reason") : t("orgs.review.reasonOptional")}</label>
            <textarea
              id={reasonId}
              value={reason}
              rows={3}
              maxLength={1000}
              dir="auto"
              required={needsReason}
              aria-invalid={reasonError || undefined}
              aria-describedby={reasonError ? `${reasonId}-error` : undefined}
              disabled={mutation.isPending}
              onChange={(e) => {
                setReason(e.target.value);
                if (e.target.value.trim()) setReasonError(false);
              }}
            />
            {reasonError && (
              <span id={`${reasonId}-error`} className="field__error">
                {t("orgs.review.reasonRequired")}
              </span>
            )}
          </div>
          <div className="actions">
            <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
              {mutation.isPending ? t("orgs.review.working") : t("orgs.review.confirm")}
            </button>
            <button type="button" className="btn" disabled={mutation.isPending} onClick={() => setDecision(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}
      <div aria-live="polite" role="status">
        {done && !mutation.isPending && <p className="alert alert--ok">{t("orgs.review.done")}</p>}
      </div>
      {errorText && (
        <p className="alert alert--error" role="alert">
          {errorText}
        </p>
      )}
    </div>
  );
}

// ---------- Documents ----------

function VersionMeta({ v }: { v: DocumentVersion }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <dl className="media__meta">
      <dt>{t("orgs.detail.file")}</dt>
      <dd dir="auto">{v.filename ?? t("common.notAvailable")}</dd>
      <dt>{t("orgs.detail.fileStatus")}</dt>
      <dd>
        <span className={`tag tag--media-${v.status}`}>
          {isOneOf(["uploading", "verifying", "stored", "rejected"] as const, v.status)
            ? t(`detail.mediaStatus.${v.status}`)
            : v.status}
        </span>
      </dd>
      <dt>{t("orgs.detail.uploadedAt")}</dt>
      <dd>{v.uploaded_at ? fmt.dateTime(v.uploaded_at) : t("common.notAvailable")}</dd>
      <dt>{t("orgs.detail.uploadedBy")}</dt>
      <dd dir="auto">{v.uploaded_by ?? t("common.notAvailable")}</dd>
      {v.note && (
        <>
          <dt>{t("orgs.detail.note")}</dt>
          <dd dir="auto">{v.note}</dd>
        </>
      )}
      <dt>{t("orgs.detail.size")}</dt>
      <dd>{v.bytes === null ? t("common.notAvailable") : fmt.bytes(v.bytes)}</dd>
      <dt>{t("orgs.detail.sha256")}</dt>
      <dd className="hash" dir="ltr">
        {v.sha256 ?? "—"}
      </dd>
    </dl>
  );
}

function DocumentHistory({ orgId, doc }: { orgId: string; doc: OrgDocument }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const query = useQuery({
    queryKey: queryKeys.orgDocumentVersions(orgId, doc.id),
    queryFn: ({ signal }) => api.orgDocumentVersions(orgId, doc.id, signal),
    enabled: !doc.versions,
    staleTime: 5 * 60_000,
  });
  const versions = doc.versions ?? query.data;
  if (!doc.versions && query.isPending) return <Loading />;
  if (versions) {
    return (
      <ol className="versions">
        {versions.map((v) => (
          <li key={v.version}>
            <strong>{t("orgs.detail.version", { version: v.version })}</strong>
            <VersionMeta v={v} />
            {v.status === "stored" && (
              <DownloadButton
                label={`${doc.title} — ${t("orgs.detail.version", { version: v.version })}`}
                fetchLink={() => api.orgDocumentDownload(orgId, doc.id, v.version)}
              />
            )}
          </li>
        ))}
      </ol>
    );
  }
  // History endpoint unavailable: every version stays downloadable by its number.
  const last = doc.current_version?.version ?? doc.versions_count;
  return (
    <>
      <p className="muted">{t("orgs.detail.historyUnavailable")}</p>
      <ol className="versions">
        {Array.from({ length: last }, (_, i) => last - i).map((n) => (
          <li key={n}>
            <strong>{t("orgs.detail.version", { version: n })}</strong>{" "}
            <DownloadButton
              label={`${doc.title} — ${t("orgs.detail.version", { version: n })}`}
              fetchLink={() => api.orgDocumentDownload(orgId, doc.id, n)}
            />
          </li>
        ))}
      </ol>
    </>
  );
}

function DocumentItem({ orgId, doc }: { orgId: string; doc: OrgDocument }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const [open, setOpen] = useState(false);
  const current = doc.current_version;
  return (
    <li className="card doc">
      <h3 dir="auto">{doc.title}</h3>
      <p className="muted">
        {isOneOf(DOCUMENT_KINDS, doc.kind) ? t(`orgs.docKind.${doc.kind}`) : t("orgs.docKind.other")}
        {current && <> · {t("orgs.detail.currentVersion", { version: current.version })}</>}
      </p>
      {current ? (
        <>
          <VersionMeta v={current} />
          {current.status === "stored" && (
            <DownloadButton label={doc.title} fetchLink={() => api.orgDocumentDownload(orgId, doc.id, current.version)} />
          )}
        </>
      ) : (
        <p className="muted">{t("orgs.detail.noVersion")}</p>
      )}
      {doc.versions_count > 0 && (
        <details onToggle={(e) => setOpen(e.currentTarget.open)}>
          <summary>{t("orgs.detail.history", { count: doc.versions_count })}</summary>
          {open && <DocumentHistory orgId={orgId} doc={doc} />}
        </details>
      )}
    </li>
  );
}

// ---------- Reports of the institution ----------

function OrgReports({ orgId }: { orgId: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const query = useInfiniteQuery({
    queryKey: queryKeys.orgReports(orgId),
    queryFn: ({ pageParam, signal }) => api.orgReports(orgId, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("orgs.detail.noReports")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("orgs.detail.reports")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("reports.columns.receivedAt")}</th>
                <th scope="col">{t("reports.columns.trackingCode")}</th>
                <th scope="col">{t("reports.columns.category")}</th>
                <th scope="col">{t("reports.columns.status")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id}>
                  <td>
                    <time dateTime={r.received_at}>{fmt.dateTime(r.received_at)}</time>
                  </td>
                  <td>
                    <Link to={`/reports/${encodeURIComponent(r.id)}`} className="code" dir="ltr">
                      {r.tracking_code}
                    </Link>
                  </td>
                  <td>
                    <CategoryLabel category={r.category} />
                  </td>
                  <td>
                    <StatusChip status={r.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && (
        <div className="load-more">
          <button
            type="button"
            className="btn"
            onClick={() => void query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
          >
            {query.isFetchingNextPage ? t("common.loading") : t("reports.loadMore")}
          </button>
        </div>
      )}
    </>
  );
}

// ---------- Page ----------

/** FR-C-05 (detail): the institution's card, registers, documents, certificates and reports; reviews for auditors. */
export function OrgDetailPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const navigate = useNavigate();
  const gouvernorats = useGouvernorats();

  const query = useQuery({
    queryKey: queryKeys.org(id),
    queryFn: ({ signal }) => api.org(id, signal),
    // Each fetch writes an audit entry: no background refetch; live events refetch it while it is on screen.
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    retry: (count, error) => !(isApiError(error) && [403, 404].includes(error.status)) && count < 2,
  });

  const org = query.data;
  const pois = useMemo(
    () =>
      org
        ? orgPois(org, org.hazmat.length > 0, org.features, (f) => f.label ?? featureKindLabel(t, f.kind), orgKindLabel(t, org.kind))
        : [],
    [org, t],
  );
  const legend = useLegendItems((org?.hazmat.length ?? 0) > 0);

  if (query.isPending) return <Loading />;
  if (query.isError || !org)
    return (
      <div className="page">
        <Link to="/orgs">{t("orgs.detail.back")}</Link>
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );

  const c = org.classification;
  const required = c?.required ?? [];
  const missing = org.completeness?.missing ?? [];
  const checklist = [...required, ...missing.filter((m) => !required.includes(m))];
  const bounds = pointsBounds(pois);
  const sds = new Map(org.documents.map((d) => [d.id, d]));
  const refName = (ref: string | null) =>
    ref
      ? (org.team.find((m) => m.id === ref)?.full_name ??
        (() => {
          const e = org.equipment.find((x) => x.id === ref);
          return e ? equipmentKindLabel(t, e.kind) : null;
        })())
      : null;

  return (
    <article className="page detail" aria-labelledby="org-title">
      <p>
        <Link to="/orgs">{t("orgs.detail.back")}</Link>
      </p>
      <div className="page__head">
        <PageTitle icon="apartment" tone="navy" id="org-title" dir="auto">
          {org.name}
        </PageTitle>
        <OrgStatusChip status={org.status} />
        <span className="tag">{orgKindLabel(t, org.kind)}</span>
      </div>

      <div className="detail__grid">
        <section className="card" aria-labelledby="sec-org-card">
          <h2 id="sec-org-card">{t("orgs.detail.card")}</h2>
          <dl className="fields">
            <dt>{t("orgs.detail.identifier")}</dt>
            <dd>
              {isOneOf(["mf", "rne"] as const, org.identifier_type)
                ? t(`orgs.identifierType.${org.identifier_type}`)
                : org.identifier_type}
              {" · "}
              <span className="code" dir="ltr">
                {org.identifier}
              </span>
            </dd>
            <dt>{t("orgs.columns.kind")}</dt>
            <dd>{orgKindLabel(t, org.kind)}</dd>
            <dt>{t("orgs.detail.activitySector")}</dt>
            <dd dir="auto">{org.activity_sector ?? t("common.notAvailable")}</dd>
            <dt>{t("orgs.detail.activityType")}</dt>
            <dd dir="auto">{org.activity_type ?? t("common.notAvailable")}</dd>
            <dt>{t("orgs.detail.capacity")}</dt>
            <dd>{org.capacity === null ? t("common.notAvailable") : fmt.number(org.capacity)}</dd>
            <dt>{t("orgs.detail.floors")}</dt>
            <dd>{org.floors === null ? t("common.notAvailable") : fmt.number(org.floors)}</dd>
            <dt>{t("orgs.detail.height")}</dt>
            <dd>{org.height_m === null ? t("common.notAvailable") : fmt.meters(org.height_m)}</dd>
            <dt>{t("orgs.detail.receivesPublic")}</dt>
            <dd>
              {org.receives_public === null ? t("common.notAvailable") : org.receives_public ? t("common.yes") : t("common.no")}
            </dd>
            <dt>{t("orgs.detail.address")}</dt>
            <dd dir="auto">{org.address ?? t("common.notAvailable")}</dd>
            <dt>{t("orgs.detail.gouvernorat")}</dt>
            <dd>{gouvernorats.nameOf(org.gouvernorat_code) ?? t("common.notAvailable")}</dd>
            {org.location && (
              <>
                <dt>{t("orgs.detail.coordinates")}</dt>
                <dd dir="ltr" className="code">
                  {org.location.lat.toFixed(5)}, {org.location.lon.toFixed(5)}
                </dd>
              </>
            )}
            <dt>{t("orgs.detail.createdAt")}</dt>
            <dd>{fmt.dateTime(org.created_at)}</dd>
            <dt>{t("orgs.detail.updatedAt")}</dt>
            <dd>{fmt.dateTime(org.updated_at)}</dd>
          </dl>
        </section>

        <section className="card" aria-labelledby="sec-org-contacts">
          <h2 id="sec-org-contacts">{t("orgs.detail.contacts")}</h2>
          <h3 className="subhead">{t("orgs.detail.manager")}</h3>
          <dl className="fields">
            <dt>{t("orgs.detail.name")}</dt>
            <dd dir="auto">{org.manager?.full_name ?? t("common.notAvailable")}</dd>
            <dt>{t("orgs.detail.phone")}</dt>
            <dd>
              <Phone phone={org.manager?.phone} />
            </dd>
            <dt>{t("orgs.detail.email")}</dt>
            <dd>
              <Email email={org.manager?.email} />
            </dd>
          </dl>
          <h3 className="subhead">{t("orgs.detail.title")}</h3>
          <dl className="fields">
            <dt>{t("orgs.detail.contactPhone")}</dt>
            <dd>
              <Phone phone={org.contact_phone} />
            </dd>
            <dt>{t("orgs.detail.contactEmail")}</dt>
            <dd>
              <Email email={org.contact_email} />
            </dd>
          </dl>
        </section>

        <section className="card" aria-labelledby="sec-org-class">
          <h2 id="sec-org-class">{t("orgs.detail.classification")}</h2>
          <dl className="fields">
            <dt>{t("orgs.detail.family")}</dt>
            <dd>{c ? familyLabel(t, c.family) : t("common.notAvailable")}</dd>
            {typeof c?.category === "number" && (
              <>
                <dt>{t("orgs.detail.category")}</dt>
                <dd>{fmt.number(c.category)}</dd>
              </>
            )}
            {c?.high_rise && (
              <>
                <dt>{t("orgs.detail.highRise")}</dt>
                <dd>{t("common.yes")}</dd>
              </>
            )}
          </dl>
          {(c?.provisional ?? true) && (
            <p className="alert alert--info provisional" role="note">
              {t("orgs.detail.provisional")}
            </p>
          )}
          <h3 className="subhead">
            {t("orgs.detail.completeness")}:{" "}
            <span className={`tag ${org.completeness?.ok ? "tag--level-ok" : "tag--level-bad"}`}>
              {org.completeness?.ok ? t("orgs.detail.complete") : t("orgs.detail.incomplete")}
            </span>
          </h3>
          <ul className="checklist" aria-label={t("orgs.detail.required")}>
            {checklist.map((code) => {
              const isMissing = missing.includes(code);
              return (
                <li key={code} className={isMissing ? "checklist__missing" : "checklist__ok"}>
                  <span aria-hidden="true">{isMissing ? "✗" : "✓"}</span> {requirementLabel(t, code)}
                  <span className="visually-hidden">
                    {" "}
                    ({isMissing ? t("orgs.detail.itemMissing") : t("orgs.detail.itemPresent")})
                  </span>
                </li>
              );
            })}
          </ul>
        </section>

        <section className="card" aria-labelledby="sec-org-review">
          <h2 id="sec-org-review">{t("orgs.review.title")}</h2>
          <OrgReviewSection org={org} />
        </section>

        <section className="card" aria-labelledby="sec-org-alerts">
          <h2 id="sec-org-alerts">
            {t("orgs.detail.alerts")} ({fmt.number(org.alerts.length)})
          </h2>
          {org.alerts.length === 0 ? (
            <p className="muted">{t("orgs.detail.noAlerts")}</p>
          ) : (
            <ul className="alerts-list">
              {org.alerts.map((a, i) => {
                const name = refName(a.ref);
                return (
                  <li key={`${a.kind}-${a.ref ?? i}`}>
                    <span className="tag tag--level-bad">{alertLabel(t, a.kind)}</span>
                    {name && <span dir="auto"> {name}</span>}
                    {a.since && <span className="muted"> · {t("orgs.detail.alertSince", { date: fmt.date(a.since) })}</span>}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="card" aria-labelledby="sec-org-map">
          <h2 id="sec-org-map">{t("orgs.detail.map")}</h2>
          {bounds ? (
            <>
              <Suspense fallback={<Loading />}>
                <LazyMapView
                  className="map map--mini"
                  markers={[]}
                  pois={pois}
                  bounds={bounds}
                  zoom={16}
                  ariaLabel={t("orgs.detail.mapLabel")}
                  styleUrl={mapStyleUrl}
                  dir={directionOf(lang)}
                  onOpenPoi={(href) => void navigate(href)}
                />
              </Suspense>
              <MapLegend items={legend} />
            </>
          ) : (
            <p className="muted">{t("orgs.detail.noLocation")}</p>
          )}
          <h3 className="subhead">{t("orgs.detail.features")}</h3>
          {org.features.length === 0 ? (
            <p className="muted">{t("orgs.detail.noFeatures")}</p>
          ) : (
            <ul className="feature-list">
              {org.features.map((f) => (
                <li key={f.id}>
                  {featureKindLabel(t, f.kind)}
                  {f.label && <span dir="auto"> — {f.label}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="card" aria-labelledby="sec-org-team">
        <h2 id="sec-org-team">
          {t("orgs.detail.team")} ({fmt.number(org.team.length)})
        </h2>
        {org.team.length === 0 ? (
          <p className="muted">{t("orgs.detail.noTeam")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">{t("orgs.detail.team")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("orgs.detail.name")}</th>
                  <th scope="col">{t("orgs.detail.teamRoleLabel")}</th>
                  <th scope="col">{t("orgs.detail.position")}</th>
                  <th scope="col">{t("orgs.detail.phone")}</th>
                  <th scope="col">{t("orgs.detail.training")}</th>
                  <th scope="col">{t("orgs.detail.lastTraining")}</th>
                  <th scope="col">{t("orgs.detail.trainingExpires")}</th>
                </tr>
              </thead>
              <tbody>
                {org.team.map((m) => (
                  <tr key={m.id}>
                    <th scope="row" dir="auto">
                      {m.full_name}
                    </th>
                    <td>{isOneOf(TEAM_ROLES, m.team_role) ? t(`orgs.teamRole.${m.team_role}`) : m.team_role}</td>
                    <td dir="auto">{m.position ?? "—"}</td>
                    <td>
                      <Phone phone={m.phone} />
                    </td>
                    <td>
                      <TrainingBadge status={m.training_status} />
                    </td>
                    <td>{formatDay(fmt, m.last_training_on, "—")}</td>
                    <td>{formatDay(fmt, m.training_expires_on, "—")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className={`card${org.hazmat.length > 0 ? " hazard" : ""}`} aria-labelledby="sec-org-hazmat">
        <h2 id="sec-org-hazmat">
          {t("orgs.detail.hazmat")} ({fmt.number(org.hazmat.length)})
        </h2>
        {org.hazmat.length === 0 ? (
          <p className="muted">{t("orgs.detail.noHazmat")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">{t("orgs.detail.hazmat")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("orgs.detail.hazmatName")}</th>
                  <th scope="col">{t("orgs.detail.unNumber")}</th>
                  <th scope="col">{t("orgs.detail.hazardClass")}</th>
                  <th scope="col" className="num">
                    {t("orgs.detail.quantity")}
                  </th>
                  <th scope="col">{t("orgs.detail.storage")}</th>
                  <th scope="col">{t("orgs.detail.sds")}</th>
                </tr>
              </thead>
              <tbody>
                {org.hazmat.map((h, i) => {
                  const doc = h.sds_document_id ? sds.get(h.sds_document_id) : undefined;
                  const current = doc?.current_version;
                  return (
                    <tr key={h.id ?? i}>
                      <th scope="row" dir="auto">
                        {h.name}
                      </th>
                      <td className="code" dir="ltr">
                        {h.un_number ? `UN ${h.un_number}` : "—"}
                      </td>
                      <td dir="ltr">{h.hazard_class ?? "—"}</td>
                      <td className="num">{hazmatQuantity(t, fmt, h)}</td>
                      <td dir="auto">{h.storage_location ?? "—"}</td>
                      <td>
                        {doc && current?.status === "stored" ? (
                          <DownloadButton
                            label={`${t("orgs.detail.sds")} — ${h.name}`}
                            fetchLink={() => api.orgDocumentDownload(org.id, doc.id, current.version)}
                          />
                        ) : (
                          <span className="tag tag--level-bad">{t("orgs.detail.sdsMissing")}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card" aria-labelledby="sec-org-equipment">
        <h2 id="sec-org-equipment">
          {t("orgs.detail.equipment")} ({fmt.number(org.equipment.length)})
        </h2>
        {org.equipment.length === 0 ? (
          <p className="muted">{t("orgs.detail.noEquipment")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">{t("orgs.detail.equipment")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("orgs.detail.equipmentKindLabel")}</th>
                  <th scope="col" className="num">
                    {t("orgs.detail.count")}
                  </th>
                  <th scope="col">{t("orgs.detail.location")}</th>
                  <th scope="col">{t("orgs.detail.maintenance")}</th>
                  <th scope="col">{t("orgs.detail.lastMaintenance")}</th>
                  <th scope="col">{t("orgs.detail.nextMaintenance")}</th>
                </tr>
              </thead>
              <tbody>
                {org.equipment.map((e) => (
                  <tr key={e.id}>
                    <th scope="row">{equipmentKindLabel(t, e.kind)}</th>
                    <td className="num">{e.count === null ? "—" : fmt.number(e.count)}</td>
                    <td dir="auto">{e.location ?? "—"}</td>
                    <td>
                      <MaintenanceBadge status={e.maintenance_status} />
                    </td>
                    <td>{formatDay(fmt, e.last_maintenance_on, "—")}</td>
                    <td>{formatDay(fmt, e.next_maintenance_on, "—")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card" aria-labelledby="sec-org-docs">
        <h2 id="sec-org-docs">
          {t("orgs.detail.documents")} ({fmt.number(org.documents.length)})
        </h2>
        {org.documents.length === 0 ? (
          <p className="muted">{t("orgs.detail.noDocuments")}</p>
        ) : (
          <ul className="docs">
            {org.documents.map((d) => (
              <DocumentItem key={d.id} orgId={org.id} doc={d} />
            ))}
          </ul>
        )}
      </section>

      <section className="card" aria-labelledby="sec-org-certs">
        <h2 id="sec-org-certs">
          {t("orgs.detail.certificates")} ({fmt.number(org.certificates.length)})
        </h2>
        {org.certificates.length === 0 ? (
          <p className="muted">{t("orgs.detail.noCertificates")}</p>
        ) : (
          <ul className="certs">
            {org.certificates.map((cert) => (
              <li key={cert.id} className="card cert">
                <p className="cert__head">
                  <span className="code" dir="ltr">
                    {cert.code}
                  </span>
                  <CertificateChip status={cert.status} />
                  {cert.superseded && <span className="tag">{t("orgs.detail.superseded")}</span>}
                </p>
                <dl className="fields">
                  <dt>{t("orgs.detail.validUntilLabel")}</dt>
                  <dd>{formatDay(fmt, cert.valid_until, "—")}</dd>
                  <dt>{t("orgs.detail.submittedAt")}</dt>
                  <dd>{cert.submitted_at ? fmt.dateTime(cert.submitted_at) : "—"}</dd>
                  <dt>{t("orgs.detail.reviewedAt")}</dt>
                  <dd>{cert.reviewed_at ? fmt.dateTime(cert.reviewed_at) : "—"}</dd>
                  {cert.review_reason && (
                    <>
                      <dt>{t("orgs.detail.reviewReason")}</dt>
                      <dd dir="auto">{cert.review_reason}</dd>
                    </>
                  )}
                  <dt>{t("orgs.detail.fingerprint")}</dt>
                  <dd className="hash" dir="ltr">
                    {cert.fingerprint ?? "—"}
                  </dd>
                  <dt>{t("orgs.detail.pdfSha256")}</dt>
                  <dd className="hash" dir="ltr">
                    {cert.pdf_sha256 ?? "—"}
                  </dd>
                  {cert.verify_url && cert.status !== "draft" && (
                    <>
                      <dt>{t("orgs.detail.verify")}</dt>
                      <dd>
                        <a href={cert.verify_url} target="_blank" rel="noopener noreferrer" dir="ltr">
                          {cert.verify_url}
                        </a>
                      </dd>
                    </>
                  )}
                </dl>
                <DownloadButton
                  label={`${t("orgs.detail.pdf")} ${cert.code}`}
                  fetchLink={() => api.certificatePdf(org.id, cert.id)}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="detail__grid">
        <section className="card" aria-labelledby="sec-org-members">
          <h2 id="sec-org-members">
            {t("orgs.detail.members")} ({fmt.number(org.members.length)})
          </h2>
          {org.members.length === 0 ? (
            <p className="muted">{t("orgs.detail.noMembers")}</p>
          ) : (
            <table className="table">
              <caption className="visually-hidden">{t("orgs.detail.members")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("orgs.detail.name")}</th>
                  <th scope="col">{t("orgs.detail.email")}</th>
                  <th scope="col">{t("orgs.detail.memberRoleLabel")}</th>
                </tr>
              </thead>
              <tbody>
                {org.members.map((m, i) => (
                  <tr key={`${m.email ?? ""}-${i}`}>
                    <td dir="auto">{m.display_name ?? t("common.notAvailable")}</td>
                    <td>
                      <Email email={m.email} />
                    </td>
                    <td>{isOneOf(MEMBER_ROLES, m.role) ? t(`orgs.memberRole.${m.role}`) : m.role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="card" aria-labelledby="sec-org-reports">
          <h2 id="sec-org-reports">{t("orgs.detail.reports")}</h2>
          <OrgReports orgId={org.id} />
        </section>
      </div>
    </article>
  );
}
