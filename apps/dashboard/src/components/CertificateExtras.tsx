import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { useFormat } from "../lib/hooks";
import type { Formatters } from "../lib/format";
import type { CertificateChange, CertificateStamp } from "../lib/types";
import { DownloadButton, formatDay } from "./OrgBits";

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
  if (changes.length === 0) return <p className="tag tag--level-ok">{t("orgs.counter.matches")}</p>;
  return (
    <div className="cert-changes">
      <p className="tag tag--level-warn">{t("orgs.counter.needsUpdate", { count: changes.length })}</p>
      <table className="table">
        <caption className="visually-hidden">{t("orgs.counter.changesCaption")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("orgs.counter.section")}</th>
            <th scope="col">{t("orgs.counter.certified")}</th>
            <th scope="col">{t("orgs.counter.current")}</th>
          </tr>
        </thead>
        <tbody>
          {changes.map((c) => (
            <tr key={`${c.section}.${c.field}`}>
              <th scope="row">
                {t(`orgs.counter.sections.${c.section}`)}
                <span className="muted"> · {t(`orgs.counter.fields.${c.field}`, { defaultValue: c.field })}</span>
              </th>
              <td dir="auto">{changeValue(t, fmt, c.certified)}</td>
              <td dir="auto">{changeValue(t, fmt, c.current)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Stamps put by hand at a regional administration, newest first, with the photo of the paper for staff. */
export function CertificateStamps({ certId, stamps }: { certId: string; stamps: readonly CertificateStamp[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  if (stamps.length === 0) return <p className="muted">{t("orgs.counter.noStamps")}</p>;
  return (
    <ul className="stamps">
      {stamps.map((s) => (
        <li key={s.id} className="stamp">
          <p className="stamp__head">
            <span className="tag tag--stamp">{t("orgs.counter.stamped")}</span>{" "}
            <b dir="auto">{s.place}</b> · {formatDay(fmt, s.stamped_on, "—")}
          </p>
          <p className="muted">
            {t("orgs.counter.stampedBy", { name: s.stamped_by_name ?? t("common.notAvailable") })}
            {s.changes.length > 0 && ` · ${t("orgs.counter.stampedWithChanges", { count: s.changes.length })}`}
          </p>
          {s.note && <p dir="auto">{s.note}</p>}
          {s.has_photo && (
            <DownloadButton
              label={`${t("orgs.counter.photo")} ${formatDay(fmt, s.stamped_on, "")}`}
              fetchLink={() => api.stampPhoto(certId, s.id)}
            />
          )}
        </li>
      ))}
    </ul>
  );
}
