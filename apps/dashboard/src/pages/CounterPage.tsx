import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useRef, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { CertificateChanges, CertificateStamps } from "../components/CertificateExtras";
import { ErrorBox, Loading } from "../components/Feedback";
import { CertificateChip, DownloadButton, formatDay, orgKindLabel } from "../components/OrgBits";
import { PageTitle } from "../components/PageTitle";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { isoDate } from "../lib/orgs";
import type { CounterView } from "../lib/types";

/** Same limits as the API (docs/phase-p3/design-certificates.md §3.2). */
export const STAMP_PHOTO_TYPES = ["image/jpeg", "image/png"] as const;
export const STAMP_PHOTO_MAX_BYTES = 5 * 1024 * 1024;
const CODE = /EH[CP]-\d{2}-\d{2}-\d{6}/i;

/** The certificate code typed, scanned by a USB reader (the whole verification URL) or by the camera. */
export function counterCode(raw: string): string | null {
  const found = CODE.exec(raw.trim());
  return found ? found[0].toUpperCase() : null;
}

export function photoProblem(file: File | null): "type" | "size" | null {
  if (!file) return null;
  if (!(STAMP_PHOTO_TYPES as readonly string[]).includes(file.type)) return "type";
  return file.size > STAMP_PHOTO_MAX_BYTES ? "size" : null;
}

interface Detector {
  detect(source: CanvasImageSource): Promise<{ rawValue: string }[]>;
}
type DetectorClass = new (options: { formats: string[] }) => Detector;

function barcodeDetector(): DetectorClass | null {
  const ctor = (globalThis as { BarcodeDetector?: DetectorClass }).BarcodeDetector;
  return typeof ctor === "function" ? ctor : null;
}

/** Reads the QR code from the camera where the browser can (BarcodeDetector); stops the camera when closed. */
function CameraScan({ onCode, onClose }: { onCode: (raw: string) => void; onClose: () => void }) {
  const { t } = useTranslation();
  const video = useRef<HTMLVideoElement>(null);
  const [Detector] = useState(() => ("mediaDevices" in navigator ? barcodeDetector() : null));
  const [failed, setFailed] = useState(Detector === null);

  useEffect(() => {
    if (!Detector) return;
    let stream: MediaStream | null = null;
    let timer: ReturnType<typeof setInterval> | undefined;
    let stopped = false;
    const detector = new Detector({ formats: ["qr_code"] });
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } }).then(
      (s) => {
        if (stopped) return s.getTracks().forEach((track) => track.stop());
        stream = s;
        if (video.current) {
          video.current.srcObject = s;
          void video.current.play().catch(() => undefined);
        }
        timer = setInterval(() => {
          if (!video.current || video.current.readyState < 2) return;
          detector.detect(video.current).then(
            (codes) => {
              const hit = codes.find((c) => counterCode(c.rawValue));
              if (hit) onCode(hit.rawValue);
            },
            () => undefined,
          );
        }, 300);
      },
      () => setFailed(true),
    );
    return () => {
      stopped = true;
      clearInterval(timer);
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [Detector, onCode]);

  return (
    <div className="counter__camera">
      {failed ? (
        <p className="alert alert--info">{t("orgs.counter.cameraUnavailable")}</p>
      ) : (
        <video ref={video} muted playsInline aria-label={t("orgs.counter.cameraLabel")} />
      )}
      <button type="button" className="btn" onClick={onClose}>
        {t("orgs.counter.closeCamera")}
      </button>
    </div>
  );
}

function StampForm({ view, onStamped }: { view: CounterView; onStamped: (message: string) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const ids = useId();
  const today = isoDate(new Date());
  const approvedOn = view.certificate.reviewed_at ? view.certificate.reviewed_at.slice(0, 10) : today;
  // The place follows the institution's gouvernorat, the agent's scope (its name may still be loading), until edited.
  const [edited, setPlace] = useState<string | null>(null);
  const place =
    edited ?? t("orgs.counter.defaultPlace", { gouvernorat: gouvernorats.nameOf(view.gouvernorat_code) ?? "" });
  const [day, setDay] = useState(today);
  const [note, setNote] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [checked, setChecked] = useState(false);

  const mutation = useMutation({
    mutationFn: async () => {
      const stamp = await api.addStamp(view.certificate.id, { place: place.trim(), stamped_on: day, note: note.trim() || null });
      return photo ? api.putStampPhoto(view.certificate.id, stamp.id, photo) : stamp;
    },
    onSuccess: () => onStamped(t("orgs.counter.stampedOk", { code: view.certificate.code })),
  });

  const problem = photoProblem(photo);
  const dayInvalid = !day || day > today || day < approvedOn;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setChecked(true);
    if (!place.trim() || dayInvalid || problem) return;
    mutation.mutate();
  };

  return (
    <form className="card stamp-form" onSubmit={submit} noValidate aria-labelledby={`${ids}-title`}>
      <h2 id={`${ids}-title`}>{t("orgs.counter.stampTitle")}</h2>
      <p className="muted">{t("orgs.counter.stampHelp")}</p>
      <div className="field">
        <label htmlFor={`${ids}-place`}>{t("orgs.counter.place")}</label>
        <input id={`${ids}-place`} value={place} maxLength={200} onChange={(e) => setPlace(e.target.value)} />
        {checked && !place.trim() && <p className="field__error">{t("errors.place_required")}</p>}
      </div>
      <div className="field">
        <label htmlFor={`${ids}-day`}>{t("orgs.counter.stampedOn")}</label>
        <input id={`${ids}-day`} type="date" value={day} min={approvedOn} max={today} onChange={(e) => setDay(e.target.value)} />
        {checked && dayInvalid && <p className="field__error">{t("errors.invalid_stamp_date")}</p>}
      </div>
      <div className="field">
        <label htmlFor={`${ids}-note`}>{t("orgs.counter.note")}</label>
        <textarea id={`${ids}-note`} value={note} maxLength={500} rows={2} onChange={(e) => setNote(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor={`${ids}-photo`}>{t("orgs.counter.photoOptional")}</label>
        <input
          id={`${ids}-photo`}
          type="file"
          accept={STAMP_PHOTO_TYPES.join(",")}
          onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
        />
        {problem && (
          <p className="field__error">{t(problem === "type" ? "errors.unsupported_media_type" : "errors.photo_too_large")}</p>
        )}
      </div>
      {mutation.isError && <ErrorBox error={mutation.error} />}
      <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
        {mutation.isPending ? t("common.loading") : t("orgs.counter.stamp")}
      </button>
    </form>
  );
}

function CounterResult({ view, onStamped }: { view: CounterView; onStamped: (m: string) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const cert = view.certificate;
  return (
    <>
      <section className="card counter__result" aria-labelledby="counter-result">
        <h2 id="counter-result" className="cert__head">
          <span className="code" dir="ltr">
            {cert.code}
          </span>
          <CertificateChip status={cert.status} />
          <span className={`tag ${view.valid ? "tag--level-ok" : "tag--level-bad"}`}>
            {view.valid ? t("orgs.counter.valid") : t("orgs.counter.invalid")}
          </span>
        </h2>
        {view.reasons.length > 0 && (
          <ul className="counter__reasons">
            {view.reasons.map((r) => (
              <li key={r}>{t(`orgs.counter.reasons.${r}`)}</li>
            ))}
          </ul>
        )}
        <dl className="fields">
          <dt>{t("orgs.counter.org")}</dt>
          <dd>
            <Link to={`/orgs/${encodeURIComponent(view.org_id)}`} dir="auto">
              {view.org_name}
            </Link>{" "}
            · {orgKindLabel(t, view.org_kind)}
          </dd>
          <dt>{t("orgs.certs.columns.gouvernorat")}</dt>
          <dd>{gouvernorats.nameOf(view.gouvernorat_code) ?? t("common.notAvailable")}</dd>
          <dt>{t("orgs.detail.address")}</dt>
          <dd dir="auto">{view.org_address ?? "—"}</dd>
          <dt>{t("orgs.detail.validUntilLabel")}</dt>
          <dd>{formatDay(fmt, cert.valid_until, "—")}</dd>
          <dt>{t("orgs.detail.reviewedAt")}</dt>
          <dd>{cert.reviewed_at ? fmt.dateTime(cert.reviewed_at) : "—"}</dd>
          <dt>{t("orgs.counter.signature")}</dt>
          <dd>{view.signature_valid ? t("orgs.counter.signatureOk") : t("orgs.counter.signatureBad")}</dd>
        </dl>
        <DownloadButton label={`${t("orgs.detail.pdf")} ${cert.code}`} fetchLink={() => api.certificatePdf(view.org_id, cert.id)} />
      </section>
      <section className="card" aria-labelledby="counter-compare">
        <h2 id="counter-compare">{t("orgs.counter.compareTitle")}</h2>
        <p className="muted">{t("orgs.counter.compareHelp")}</p>
        {cert.needs_update === null || cert.needs_update === undefined ? (
          <p className="muted">{t("orgs.counter.noComparison")}</p>
        ) : (
          <CertificateChanges changes={cert.changes ?? []} />
        )}
      </section>
      <section className="card" aria-labelledby="counter-stamps">
        <h2 id="counter-stamps">{t("orgs.counter.stampsTitle")}</h2>
        <CertificateStamps certId={cert.id} stamps={cert.stamps ?? []} />
      </section>
      {view.can_stamp && <StampForm key={cert.id} view={view} onStamped={onStamped} />}
    </>
  );
}

/** F-POR-07: the counter of a regional administration. Read the certificate, compare it, stamp it by hand. */
export function CounterPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const inputId = useId();
  const [raw, setRaw] = useState("");
  const [code, setCode] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [camera, setCamera] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const canScan = barcodeDetector() !== null;

  const query = useQuery({
    queryKey: ["counter", code],
    queryFn: ({ signal }) => api.certificateLookup(code ?? "", signal),
    enabled: code !== null,
    retry: false,
  });

  // Stable, so the camera is not restarted at every render while it reads.
  const look = useCallback((value: string) => {
    const found = counterCode(value);
    setInvalid(found === null);
    setMessage(null);
    if (found) {
      setRaw(found);
      setCode(found);
      setCamera(false);
    }
  }, []);

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="verified" tone="green">
          {t("orgs.counter.title")}
        </PageTitle>
        <Link to="/orgs/certificates">{t("orgs.counter.toQueue")}</Link>
      </div>
      <p className="muted">{t("orgs.counter.intro")}</p>
      <form
        className="card counter__lookup"
        onSubmit={(e) => {
          e.preventDefault();
          look(raw);
        }}
      >
        <div className="field field--grow">
          <label htmlFor={inputId}>{t("orgs.counter.codeLabel")}</label>
          <input
            id={inputId}
            value={raw}
            dir="ltr"
            autoComplete="off"
            placeholder="EHC-26-61-000123"
            aria-invalid={invalid}
            onChange={(e) => setRaw(e.target.value)}
          />
          {invalid && <p className="field__error">{t("errors.invalid_code")}</p>}
        </div>
        <button type="submit" className="btn btn--primary">
          {t("orgs.counter.check")}
        </button>
        {canScan && (
          <button type="button" className="btn" onClick={() => setCamera(true)}>
            {t("orgs.counter.scan")}
          </button>
        )}
      </form>
      {camera && <CameraScan onCode={look} onClose={() => setCamera(false)} />}
      <div aria-live="polite" role="status">
        {message && <p className="alert alert--ok">{message}</p>}
      </div>
      {query.isFetching && !query.data && <Loading />}
      {query.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(query.error))}
        </p>
      )}
      {query.data && (
        <CounterResult
          view={query.data}
          onStamped={(m) => {
            setMessage(m);
            void qc.invalidateQueries({ queryKey: ["counter", code] });
            void qc.invalidateQueries({ queryKey: ["org", query.data.org_id] });
          }}
        />
      )}
    </div>
  );
}
