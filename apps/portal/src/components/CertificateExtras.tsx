import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { Badge } from "./Badges";
import type { Formatters } from "../lib/format";
import { useFormat } from "../lib/hooks";
import type { CertificateChange } from "../lib/types";

/** A certified or current value of a change, in words (lists, positions, yes/no). */
export function changeValue(t: TFunction, fmt: Formatters, value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? t("common.yes") : t("common.no");
  if (typeof value === "number") return fmt.number(value);
  if (Array.isArray(value)) return value.length === 0 ? "—" : value.map((v) => changeValue(t, fmt, v)).join(" · ");
  if (typeof value === "object") {
    const { lat, lon } = value as { lat?: number; lon?: number };
    if (typeof lat === "number" && typeof lon === "number") return `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
    return JSON.stringify(value);
  }
  return typeof value === "string" ? value : "—";
}

/** What changed since the certificate was approved (phase P3a §3.4), section by section. */
export function CertificateChanges({ changes }: { changes: readonly CertificateChange[] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <table className="table cert-changes">
      <caption className="visually-hidden">{t("certificate.changesCaption")}</caption>
      <thead>
        <tr>
          <th scope="col">{t("certificate.section")}</th>
          <th scope="col">{t("certificate.certifiedValue")}</th>
          <th scope="col">{t("certificate.currentValue")}</th>
        </tr>
      </thead>
      <tbody>
        {changes.map((c) => (
          <tr key={`${c.section}.${c.field}`}>
            <th scope="row">
              {t(`certificate.sections.${c.section}`)}
              <span className="muted"> · {t(`certificate.fields.${c.field}`, { defaultValue: c.field })}</span>
            </th>
            <td dir="auto">{changeValue(t, fmt, c.certified)}</td>
            <td dir="auto">{changeValue(t, fmt, c.current)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Stamps put by hand at a regional administration: place and date, and the agent for the institution's members. */
export function StampList({ stamps }: { stamps: readonly { place: string; stamped_on: string; stamped_by_name?: string | null }[] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  if (stamps.length === 0) return <p className="muted">{t("certificate.noStamps")}</p>;
  return (
    <ul className="stamps">
      {stamps.map((s, i) => (
        <li key={`${s.place}.${s.stamped_on}.${i}`} className="stamp">
          <Badge tone="ok">{t("certificate.stamped")}</Badge> <b dir="auto">{s.place}</b> ·{" "}
          {fmt.date(s.stamped_on)}
          {s.stamped_by_name && <span className="muted"> · {t("certificate.stampedBy", { name: s.stamped_by_name })}</span>}
        </li>
      ))}
    </ul>
  );
}

/**
 * The Office's electronic seal as printed on the approved PDF (phase P3a §3.1): a picture of the Ed25519 signature,
 * not a second signature. A model [SIM] until the Office provides its official seal.
 */
export function ElectronicSeal({ issuedAt, keyId }: { issuedAt: string | null; keyId: string | null | undefined }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <figure className="seal" aria-labelledby="seal-caption">
      <div className="seal__ring" aria-hidden="true">
        <b>الديوان الوطني للحماية المدنية</b>
        <span>Office national de la protection civile</span>
        <span>{fmt.date(issuedAt)}</span>
        {keyId && (
          <span className="seal__key" dir="ltr">
            {keyId}
          </span>
        )}
      </div>
      <figcaption id="seal-caption">
        <span className="tag tag--sim">[SIM]</span> {t("verify.sealNote")}
      </figcaption>
    </figure>
  );
}
