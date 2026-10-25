import { useInfiniteQuery, useMutation, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { CertificateChip, DownloadButton, requirementLabel } from "../components/OrgBits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { validateValidUntil, validUntilBounds, type ValidUntilError } from "../lib/orgs";
import { canReviewOrgs } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import { isOneOf, type CertificateReviewBody, type Page, type QueueCertificate } from "../lib/types";
import { PageTitle } from "../components/PageTitle";

/** Statuses the staff queue accepts (§9): the review queue itself, then decided certificates. */
export const QUEUE_STATUSES = ["submitted", "approved", "rejected", "revoked"] as const;
type QueueStatus = (typeof QUEUE_STATUSES)[number];

type QueueData = InfiniteData<Page<QueueCertificate>, string | null>;
type Mode = "approve" | "reject";

function reviewErrorText(t: (k: string) => string, error: unknown): string {
  if (isApiError(error) && error.code === "invalid_transition") return t("orgs.certs.invalidTransition");
  return t(errorMessageKey(error));
}

/** Approve (with `valid_until`, tomorrow … 5 years, default +1 year) or reject (with a reason), after confirmation. */
function CertificateReview({ cert, onDone }: { cert: QueueCertificate; onDone: (message: string) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const base = useId();
  const [bounds] = useState(() => validUntilBounds());
  const [mode, setMode] = useState<Mode | null>(null);
  const [validUntil, setValidUntil] = useState(bounds.default);
  const [reason, setReason] = useState("");
  const [dateError, setDateError] = useState<ValidUntilError | null>(null);
  const [reasonError, setReasonError] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const mutation = useMutation({
    mutationFn: (body: CertificateReviewBody) => api.reviewCertificate(cert.id, body),
    onSuccess: (_updated, body) => {
      // Leave the queue at once; the live event and the refetch confirm it.
      for (const [key, data] of qc.getQueriesData<QueueData>({ queryKey: queryKeys.certificatesAll })) {
        if (!data) continue;
        qc.setQueryData<QueueData>(key, {
          ...data,
          pages: data.pages.map((p) => ({ ...p, items: p.items.filter((c) => c.id !== cert.id) })),
        });
      }
      void qc.invalidateQueries({ queryKey: queryKeys.org(cert.org_id), exact: true, refetchType: "active" });
      void qc.invalidateQueries({ queryKey: queryKeys.certificates(body.decision === "approve" ? "approved" : "rejected") });
      void qc.invalidateQueries({ queryKey: queryKeys.orgsAll });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
      onDone(
        body.decision === "approve"
          ? t("orgs.certs.approved", { code: cert.code })
          : t("orgs.certs.rejected", { code: cert.code }),
      );
    },
    onError: (error) => {
      setConfirming(false);
      if (isApiError(error) && error.status === 409) void qc.invalidateQueries({ queryKey: queryKeys.certificatesAll });
    },
  });

  const choose = (m: Mode) => {
    setMode(m);
    setConfirming(false);
    setDateError(null);
    setReasonError(false);
    mutation.reset();
  };

  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (!mode) return;
    if (mode === "approve") {
      const err = validateValidUntil(validUntil);
      setDateError(err);
      if (err) return;
    } else if (!reason.trim()) {
      setReasonError(true);
      return;
    }
    if (!confirming) {
      setConfirming(true);
      return;
    }
    mutation.mutate(
      mode === "approve"
        ? { decision: "approve", valid_until: validUntil }
        : { decision: "reject", reason: reason.trim() },
    );
  };

  const dateId = `${base}-date`;
  const reasonId = `${base}-reason`;
  return (
    <div className="cert-review">
      <div className="actions">
        <button
          type="button"
          className="btn btn--primary"
          aria-pressed={mode === "approve"}
          disabled={mutation.isPending}
          onClick={() => choose("approve")}
        >
          {t("orgs.certs.approve")}
        </button>
        <button
          type="button"
          className="btn"
          aria-pressed={mode === "reject"}
          disabled={mutation.isPending}
          onClick={() => choose("reject")}
        >
          {t("orgs.certs.reject")}
        </button>
      </div>
      {mode && (
        <form onSubmit={submit} noValidate className="review__confirm">
          {mode === "approve" ? (
            <div className={`field${dateError ? " field--invalid" : ""}`}>
              <label htmlFor={dateId}>{t("orgs.certs.validUntil")}</label>
              <input
                id={dateId}
                type="date"
                value={validUntil}
                min={bounds.min}
                max={bounds.max}
                dir="ltr"
                aria-invalid={dateError ? true : undefined}
                aria-describedby={`${dateId}-help${dateError ? ` ${dateId}-error` : ""}`}
                disabled={mutation.isPending}
                onChange={(e) => {
                  setValidUntil(e.target.value);
                  setDateError(null);
                  setConfirming(false);
                }}
              />
              <span id={`${dateId}-help`} className="muted">
                {t("orgs.certs.validUntilHelp", { min: fmt.date(bounds.min), max: fmt.date(bounds.max) })}
              </span>
              {dateError && (
                <span id={`${dateId}-error`} className="field__error">
                  {t(`orgs.certs.validation.${dateError}`)}
                </span>
              )}
            </div>
          ) : (
            <div className={`field${reasonError ? " field--invalid" : ""}`}>
              <label htmlFor={reasonId}>{t("orgs.certs.reason")}</label>
              <textarea
                id={reasonId}
                value={reason}
                rows={3}
                maxLength={1000}
                dir="auto"
                required
                aria-invalid={reasonError || undefined}
                aria-describedby={reasonError ? `${reasonId}-error` : undefined}
                disabled={mutation.isPending}
                onChange={(e) => {
                  setReason(e.target.value);
                  setReasonError(false);
                  setConfirming(false);
                }}
              />
              {reasonError && (
                <span id={`${reasonId}-error`} className="field__error">
                  {t("orgs.certs.validation.reasonRequired")}
                </span>
              )}
            </div>
          )}
          {confirming && (
            <p className="alert alert--warn" role="alert">
              {mode === "approve"
                ? t("orgs.certs.confirmApprove", { code: cert.code, date: fmt.date(validUntil) })
                : t("orgs.certs.confirmReject", { code: cert.code })}
            </p>
          )}
          <div className="actions">
            <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
              {mutation.isPending
                ? t("orgs.certs.working")
                : confirming
                  ? t("orgs.certs.confirm")
                  : mode === "approve"
                    ? t("orgs.certs.approve")
                    : t("orgs.certs.reject")}
            </button>
            <button type="button" className="btn" disabled={mutation.isPending} onClick={() => setMode(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {reviewErrorText(t, mutation.error)}
        </p>
      )}
    </div>
  );
}

/** Revoke an approved certificate (phase 10 §4.1): a reason, then a confirmation. Invalid at once on the public page. */
function CertificateRevoke({ cert, onDone }: { cert: QueueCertificate; onDone: (message: string) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const reasonId = useId();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const mutation = useMutation({
    mutationFn: (text: string) => api.revokeCertificate(cert.id, text),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.certificatesAll });
      void qc.invalidateQueries({ queryKey: queryKeys.org(cert.org_id), exact: true, refetchType: "active" });
      void qc.invalidateQueries({ queryKey: queryKeys.orgsAll });
      onDone(t("orgs.certs.revokedDone", { code: cert.code }));
    },
    onError: () => setConfirming(false),
  });

  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setReasonError(true);
      return;
    }
    if (!confirming) {
      setConfirming(true);
      return;
    }
    mutation.mutate(reason.trim());
  };

  if (!open) {
    return (
      <div className="actions">
        <button type="button" className="btn btn--danger" onClick={() => setOpen(true)}>
          {t("orgs.certs.revoke")}
        </button>
      </div>
    );
  }
  return (
    <form onSubmit={submit} noValidate className="review__confirm">
      <div className={`field${reasonError ? " field--invalid" : ""}`}>
        <label htmlFor={reasonId}>{t("orgs.certs.revokeReason")}</label>
        <textarea
          id={reasonId}
          value={reason}
          rows={3}
          maxLength={1000}
          dir="auto"
          required
          aria-invalid={reasonError || undefined}
          aria-describedby={reasonError ? `${reasonId}-error` : undefined}
          disabled={mutation.isPending}
          onChange={(e) => {
            setReason(e.target.value);
            setReasonError(false);
            setConfirming(false);
          }}
        />
        {reasonError && (
          <span id={`${reasonId}-error`} className="field__error">
            {t("orgs.certs.revokeReasonRequired")}
          </span>
        )}
      </div>
      {confirming && (
        <p className="alert alert--warn" role="alert">
          {t("orgs.certs.confirmRevoke", { code: cert.code })}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--danger" disabled={mutation.isPending}>
          {mutation.isPending ? t("orgs.certs.working") : confirming ? t("orgs.certs.confirm") : t("orgs.certs.revoke")}
        </button>
        <button type="button" className="btn" disabled={mutation.isPending} onClick={() => setOpen(false)}>
          {t("common.cancel")}
        </button>
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {isApiError(mutation.error) && mutation.error.code === "already_revoked"
            ? t("orgs.certs.alreadyRevoked")
            : reviewErrorText(t, mutation.error)}
        </p>
      )}
    </form>
  );
}

/** Certificate review queue (FR-B-008): oldest submission first; decisions for `org_auditor` only. */
export function CertificatesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const canReview = canReviewOrgs(user?.identity.roles ?? []);
  const [message, setMessage] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  const rawStatus = params.get("status");
  const status: QueueStatus = isOneOf(QUEUE_STATUSES, rawStatus) ? rawStatus : "submitted";
  const statusId = useId();

  const query = useInfiniteQuery({
    queryKey: queryKeys.certificates(status),
    queryFn: ({ pageParam, signal }) => api.certificates({ status, cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="workspacePremium" tone="amber">{t("orgs.certs.title")}</PageTitle>
        <Link to="/orgs">{t("orgs.detail.back")}</Link>
      </div>
      <p className="muted">{t("orgs.certs.intro")}</p>
      <div className="filters card filters__row">
        <div className="field">
          <label htmlFor={statusId}>{t("orgs.certs.statusFilter")}</label>
          <select
            id={statusId}
            value={status}
            onChange={(e) => {
              setMessage(null);
              setParams(e.target.value === "submitted" ? {} : { status: e.target.value }, { replace: true });
            }}
          >
            {QUEUE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`orgs.certificate.${s}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {!canReview && status === "submitted" && <p className="alert alert--info">{t("orgs.certs.readOnly")}</p>}
      <div aria-live="polite" role="status">
        {message && <p className="alert alert--ok">{message}</p>}
      </div>

      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && (
        <p className="card empty">{status === "submitted" ? t("orgs.certs.empty") : t("orgs.certs.emptyDecided")}</p>
      )}
      {items.length > 0 && (
        <ol
          className="queue"
          aria-label={
            status === "submitted" ? t("orgs.certs.caption") : `${t("orgs.certs.title")} — ${t(`orgs.certificate.${status}`)}`
          }
        >
          {items.map((c) => {
            const missing = c.completeness?.missing ?? [];
            return (
              <li key={c.id} className="card queue__item">
                <p className="cert__head">
                  <span className="code" dir="ltr">
                    {c.code}
                  </span>
                  <Link to={`/orgs/${encodeURIComponent(c.org_id)}`} dir="auto">
                    {c.org_name}
                  </Link>{" "}
                  <CertificateChip status={c.status} />
                </p>
                <dl className="fields">
                  <dt>{t("orgs.certs.columns.gouvernorat")}</dt>
                  <dd>{gouvernorats.nameOf(c.gouvernorat_code) ?? t("common.notAvailable")}</dd>
                  <dt>{t("orgs.certs.columns.submittedAt")}</dt>
                  <dd>{c.submitted_at ? fmt.dateTime(c.submitted_at) : t("common.notAvailable")}</dd>
                  <dt>{t("orgs.certs.columns.completeness")}</dt>
                  <dd>
                    {!c.completeness ? (
                      t("common.notAvailable")
                    ) : c.completeness.ok ? (
                      <span className="tag tag--level-ok">{t("orgs.detail.complete")}</span>
                    ) : (
                      <span className="tag tag--level-bad">
                        {t("orgs.certs.missing", {
                          items: missing.map((m) => requirementLabel(t, m)).join(t("common.listSeparator")),
                        })}
                      </span>
                    )}
                  </dd>
                  <dt>{t("orgs.certs.columns.pdf")}</dt>
                  <dd>
                    <DownloadButton
                      label={`${t("orgs.detail.pdf")} ${c.code}`}
                      fetchLink={() => api.certificatePdf(c.org_id, c.id)}
                    />
                  </dd>
                </dl>
                {canReview && c.status === "submitted" && (
                  <CertificateReview
                    cert={c}
                    onDone={(m) => {
                      setMessage(m);
                    }}
                  />
                )}
                {canReview && c.status === "approved" && <CertificateRevoke cert={c} onDone={setMessage} />}
              </li>
            );
          })}
        </ol>
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
    </div>
  );
}
