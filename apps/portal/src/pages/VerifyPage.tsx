import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";
import { ElectronicSeal, StampList } from "../components/CertificateExtras";
import { ErrorBox, Loading } from "../components/Feedback";
import { FileDrop } from "../components/FileDrop";
import { useServices } from "../context/services";
import { isApiError } from "../lib/api";
import { invalidReasons } from "../lib/certificates";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { queryKeys } from "../lib/portalApi";
import { sameHash, sha256Hex } from "../lib/sha256";
import type { PublicCertificate } from "../lib/types";
import { VerifyCodeForm } from "./LandingPage";
import { PageTitle } from "../components/PageTitle";

type Comparison =
  | { state: "idle" }
  | { state: "hashing"; name: string; percent: number }
  | { state: "done"; name: string; hash: string; match: boolean }
  | { state: "error"; name: string };

/** Compares a PDF the visitor holds with the certificate's `pdf_sha256`; the file is hashed locally. */
function PdfCompare({ expected }: { expected: string }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const [cmp, setCmp] = useState<Comparison>({ state: "idle" });

  async function check(file: File) {
    setCmp({ state: "hashing", name: file.name, percent: 0 });
    try {
      const hash = await sha256Hex(file, {
        onProgress: (done, total) => setCmp({ state: "hashing", name: file.name, percent: total ? done / total : 1 }),
      });
      setCmp({ state: "done", name: file.name, hash, match: sameHash(hash, expected) });
    } catch {
      setCmp({ state: "error", name: file.name });
    }
  }

  return (
    <section className="card" aria-labelledby="pdf-compare-title">
      <h2 id="pdf-compare-title">{t("verify.compareTitle")}</h2>
      <p>{t("verify.compareBody")}</p>
      <FileDrop
        label={t("verify.dropLabel")}
        hint={t("verify.dropHint")}
        accept="application/pdf,.pdf"
        onFile={(f) => void check(f)}
        disabled={cmp.state === "hashing"}
      />
      <div aria-live="polite">
        {cmp.state === "hashing" && (
          <p>
            {t("verify.hashing", { name: cmp.name })} {fmt.percent(cmp.percent)}
          </p>
        )}
        {cmp.state === "done" && (
          <div className={`alert ${cmp.match ? "alert--ok" : "alert--error"}`}>
            <p>
              <strong>{cmp.match ? t("verify.match") : t("verify.mismatch")}</strong>
            </p>
            <p>{cmp.match ? t("verify.matchBody", { name: cmp.name }) : t("verify.mismatchBody", { name: cmp.name })}</p>
            <p className="muted">
              {t("verify.computedHash")} <span className="hash">{cmp.hash}</span>
            </p>
          </div>
        )}
        {cmp.state === "error" && (
          <div className="alert alert--error">
            <p>{t("verify.readError", { name: cmp.name })}</p>
          </div>
        )}
      </div>
    </section>
  );
}

/** Public signing key (contract §7), so anyone can check the Ed25519 signature independently. */
function SigningKey() {
  const { t } = useTranslation();
  const { api } = useServices();
  const key = useQuery({ queryKey: queryKeys.certificateKey, queryFn: ({ signal }) => api.certificateKey(signal), staleTime: Infinity, retry: false });
  if (!key.data) return null;
  return (
    <details className="card">
      <summary>{t("verify.keyTitle")}</summary>
      {key.data.public_key ? (
        <>
          <p>{t("verify.keyBody", { algorithm: key.data.algorithm, message: key.data.signed_message })}</p>
          <p className="hash">{key.data.public_key}</p>
          {key.data.key_id && <p className="muted">{t("verify.keyId", { id: key.data.key_id })}</p>}
        </>
      ) : (
        <p className="muted">{t("verify.keyNone")}</p>
      )}
    </details>
  );
}

function CertificateResult({ cert }: { cert: PublicCertificate }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { nameOf } = useGouvernorats();
  const reasons = invalidReasons(cert);
  const family = t(`family.${cert.classification.family}`);
  return (
    <>
      <section className={`card verdict verdict--${cert.valid ? "valid" : "invalid"}`} aria-labelledby="verdict-title">
        <h2 id="verdict-title">{cert.valid ? t("verify.valid") : t("verify.invalid")}</h2>
        {cert.valid ? (
          <p>{t("verify.validBody", { name: cert.org_name, date: fmt.date(cert.valid_until) })}</p>
        ) : (
          <>
            <p>{t("verify.invalidBody")}</p>
            {cert.revoked_at && <p>{t("verify.revokedOn", { date: fmt.date(cert.revoked_at) })}</p>}
            <ul>
              {reasons.map((r) => (
                <li key={r}>{t(`verify.reasons.${r}`)}</li>
              ))}
            </ul>
          </>
        )}
      </section>
      <section className="card">
        <h2>{t("verify.detailsTitle")}</h2>
        <dl className="fields">
          <dt>{t("verify.code")}</dt>
          <dd className="code">{cert.code}</dd>
          <dt>{t("verify.kind")}</dt>
          <dd>
            {cert.kind === "prevention" ? (
              <>
                {t("verify.kinds.prevention")} <span className="tag tag--sim">[SIM]</span>
                {cert.with_reservations && <> · {t("verify.withReservations")}</>}
              </>
            ) : (
              t("verify.kinds.safety")
            )}
          </dd>
          <dt>{t("verify.org")}</dt>
          <dd>{cert.org_name}</dd>
          <dt>{t("org.kind")}</dt>
          <dd>{t(`kinds.${cert.org_kind}`)}</dd>
          <dt>{t("org.gouvernorat")}</dt>
          <dd>{nameOf(cert.gouvernorat_code) ?? t("common.notAvailable")}</dd>
          <dt>{t("classification.family")}</dt>
          <dd>
            {cert.classification.category !== null
              ? t("classification.familyWithCategory", { family, category: cert.classification.category })
              : family}
          </dd>
          <dt>{t("certificate.status")}</dt>
          <dd>{t(`certificateStatus.${cert.status}`)}</dd>
          <dt>{t("certificate.issuedAt")}</dt>
          <dd>{fmt.date(cert.issued_at)}</dd>
          <dt>{t("certificate.validUntil")}</dt>
          <dd>{fmt.date(cert.valid_until)}</dd>
          <dt>{t("certificate.signature")}</dt>
          <dd>
            {cert.signature_valid === null
              ? t("common.notAvailable")
              : cert.signature_valid
                ? t("certificate.signatureValid")
                : t("certificate.signatureInvalid")}
          </dd>
          <dt>{t("certificate.fingerprint")}</dt>
          <dd className="hash">{cert.fingerprint}</dd>
          <dt>{t("certificate.pdfHash")}</dt>
          <dd className="hash">{cert.pdf_sha256 ?? t("common.notAvailable")}</dd>
        </dl>
      </section>
      {cert.status === "approved" && (
        <section className="card" aria-labelledby="seal-title">
          <h2 id="seal-title">{t("verify.sealTitle")}</h2>
          <p>{t("verify.sealBody")}</p>
          <ElectronicSeal issuedAt={cert.issued_at} keyId={cert.key_id} />
        </section>
      )}
      <section className="card" aria-labelledby="stamps-title">
        <h2 id="stamps-title">{t("certificate.stampsTitle")}</h2>
        <StampList stamps={cert.stamps ?? []} />
      </section>
      {cert.pdf_sha256 ? <PdfCompare expected={cert.pdf_sha256} /> : null}
      <SigningKey />
      <section className="card" aria-labelledby="disclaimer-title">
        <h2 id="disclaimer-title">{t("verify.disclaimerTitle")}</h2>
        <p>{cert.kind === "prevention" ? t("verify.preventionDisclaimer") : t("verify.disclaimer")}</p>
      </section>
    </>
  );
}

/** Public certificate verification (`/verify/:code`), no sign-in (contract §7). */
export function VerifyPage() {
  const { t } = useTranslation();
  const { code } = useParams();
  const { api } = useServices();
  const query = useQuery({
    queryKey: queryKeys.publicCertificate(code ?? ""),
    queryFn: ({ signal }) => api.publicCertificate(code ?? "", signal),
    enabled: !!code,
    retry: false,
  });

  return (
    <div className="page page--narrow">
      <div className="page__head">
        <PageTitle icon="verified" tone="green">{t("verify.title")}</PageTitle>
      </div>
      <section className="card">
        <p>{t("verify.intro")}</p>
        <VerifyCodeForm />
      </section>
      {code &&
        (query.isPending ? (
          <Loading />
        ) : query.isError ? (
          isApiError(query.error) && query.error.status === 404 ? (
            <section className="card verdict verdict--invalid" role="alert">
              <h2>{t("verify.notFoundTitle")}</h2>
              <p>{t("verify.notFoundBody", { code })}</p>
            </section>
          ) : (
            <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
          )
        ) : (
          <CertificateResult cert={query.data} />
        ))}
    </div>
  );
}
