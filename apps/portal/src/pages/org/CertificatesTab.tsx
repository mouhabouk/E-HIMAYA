import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { Badge, CertificateStatusBadge } from "../../components/Badges";
import { CopyButton } from "../../components/CopyButton";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useServices } from "../../context/services";
import { isApiError } from "../../lib/api";
import { todayIso } from "../../lib/certificates";
import { useFormat } from "../../lib/hooks";
import { openPresigned } from "../../lib/openUrl";
import { queryKeys } from "../../lib/portalApi";
import { REQUIREMENTS, isOneOf, type Certificate } from "../../lib/types";
import { BlockedNote, useOrg } from "./OrgWorkspace";
import { REQUIREMENT_TAB } from "./OverviewTab";

/** Public verification link of a certificate (the server's `verify_url`, else this portal's /verify/:code). */
export function verifyLink(c: Certificate): string {
  return c.verify_url || `${window.location.origin}/verify/${encodeURIComponent(c.code)}`;
}

function MissingList({ missing }: { missing: readonly string[] }) {
  const { t } = useTranslation();
  return (
    <div className="alert alert--error" role="alert">
      <p>{t("errors.incomplete")}</p>
      <ul>
        {missing.map((m) => (
          <li key={m}>
            {isOneOf(REQUIREMENTS, m) ? (
              <>
                {t(`requirements.${m}`)} — <Link to={`../${REQUIREMENT_TAB[m]}`}>{t("completeness.fix")}</Link>
              </>
            ) : (
              m
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CertificateItem({ cert }: { cert: Certificate }) {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const fmt = useFormat();
  const queryClient = useQueryClient();
  const [fallback, setFallback] = useState<string | null>(null);
  const [missing, setMissing] = useState<string[] | null>(null);
  const pdf = useMutation({
    mutationFn: () => openPresigned(() => api.certificatePdf(org.id, cert.id)),
    onSuccess: setFallback,
  });
  const submit = useMutation({
    mutationFn: () => api.submitCertificate(org.id, cert.id),
    onSuccess: () => {
      setMissing(null);
      void queryClient.invalidateQueries({ queryKey: queryKeys.certificates(org.id) });
    },
    onError: async (e) => {
      if (isApiError(e) && e.code === "incomplete") {
        // The 409 carries only the code: the current list comes from the institution itself.
        const fresh = await api.org(org.id).catch(() => null);
        if (fresh) {
          queryClient.setQueryData(queryKeys.org(org.id), fresh);
          setMissing(fresh.completeness.missing);
        } else setMissing(org.completeness.missing);
      }
    },
  });
  const expired = cert.status === "approved" && !!cert.valid_until && cert.valid_until.slice(0, 10) < todayIso();
  const isDraft = cert.status === "draft";

  return (
    <li className="cert card">
      <div className="cert__head">
        <h3 className="code" dir="ltr">
          {cert.code}
        </h3>
        <CertificateStatusBadge status={cert.status} />
        {cert.superseded && <Badge tone="neutral">{t("certificate.superseded")}</Badge>}
        {expired && <Badge tone="danger">{t("certificate.expired")}</Badge>}
      </div>
      <dl className="fields">
        <dt>{t("certificate.createdAt")}</dt>
        <dd>{fmt.dateTime(cert.created_at)}</dd>
        {cert.submitted_at && (
          <>
            <dt>{t("certificate.submittedAt")}</dt>
            <dd>{fmt.dateTime(cert.submitted_at)}</dd>
          </>
        )}
        {cert.reviewed_at && (
          <>
            <dt>{t("certificate.reviewedAt")}</dt>
            <dd>{fmt.dateTime(cert.reviewed_at)}</dd>
          </>
        )}
        {cert.review_reason && (
          <>
            <dt>{t("certificate.reviewReason")}</dt>
            <dd>{cert.review_reason}</dd>
          </>
        )}
        <dt>{t("certificate.validUntil")}</dt>
        <dd>{fmt.date(cert.valid_until)}</dd>
        <dt>{t("certificate.fingerprint")}</dt>
        <dd className="hash">{cert.fingerprint}</dd>
        {cert.pdf_sha256 && (
          <>
            <dt>{t("certificate.pdfHash")}</dt>
            <dd className="hash">{cert.pdf_sha256}</dd>
          </>
        )}
      </dl>
      {isDraft && <p className="muted">{t("certificate.draftNote")}</p>}
      {!isDraft && (
        <div className="verify-link">
          <span className="muted">{t("certificate.verifyLink")}</span>{" "}
          <a href={verifyLink(cert)} target="_blank" rel="noopener noreferrer" dir="ltr">
            {verifyLink(cert)}
          </a>{" "}
          <CopyButton text={verifyLink(cert)} label={t("certificate.copyLink")} />
        </div>
      )}
      <div className="actions">
        <button type="button" className="btn" disabled={pdf.isPending} onClick={() => pdf.mutate()}>
          {t("certificate.openPdf")}
        </button>
        {fallback && (
          <a href={fallback} target="_blank" rel="noopener noreferrer">
            {t("documents.downloadLink")}
          </a>
        )}
        {isDraft && can("submitCertificate") && (
          <button type="button" className="btn btn--primary" disabled={submit.isPending} onClick={() => submit.mutate()}>
            {t("certificate.submit")}
          </button>
        )}
      </div>
      {isDraft && <BlockedNote action="submitCertificate" />}
      {pdf.isError && <ErrorBox error={pdf.error} />}
      {missing ? <MissingList missing={missing} /> : submit.isError && <ErrorBox error={submit.error} />}
    </li>
  );
}

/** Digital safety certificate (FR-B-008): draft, PDF, submission, statuses and public verification link. */
export function CertificatesTab() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: queryKeys.certificates(org.id), queryFn: ({ signal }) => api.certificates(org.id, signal) });
  const generate = useMutation({
    mutationFn: () => api.generateCertificate(org.id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.certificates(org.id) }),
  });

  return (
    <section className="card" aria-labelledby="cert-title">
      <div className="section-head">
        <h2 id="cert-title">{t("certificate.title")}</h2>
        {can("generateCertificate") && (
          <button type="button" className="btn btn--primary" disabled={generate.isPending} onClick={() => generate.mutate()}>
            {t("certificate.generate")}
          </button>
        )}
      </div>
      <p className="muted">{t("certificate.help")}</p>
      <BlockedNote action="generateCertificate" />
      {!org.completeness.ok && (
        <p className="alert alert--warn">
          {t("certificate.incompleteWarning", { n: org.completeness.missing.length })} <Link to="..">{t("certificate.seeChecklist")}</Link>
        </p>
      )}
      {generate.isError && <ErrorBox error={generate.error} />}
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      ) : query.data.length === 0 ? (
        <p className="empty">{t("certificate.empty")}</p>
      ) : (
        <ul className="certs">
          {query.data.map((c) => (
            <CertificateItem key={c.id} cert={c} />
          ))}
        </ul>
      )}
    </section>
  );
}
