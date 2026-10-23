/**
 * Personal safety on the report detail (phase B2). The medical file the reporter chose to attach is never sent with
 * the report: it is opened on request, and the API records every opening in the audit log. The 72-hour location
 * history search (a missing person) is shown only while the national setting turns the feature on.
 */
import { useMutation } from "@tanstack/react-query";
import { Fragment, useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat } from "../lib/hooks";
import { reasonValid, settingOf, usePlatformSettings } from "../lib/phase9";
import { canSearchLocationHistory } from "../lib/roles";
import {
  HISTORY_PHONE,
  HISTORY_REASON_RANGE,
  LOCATION_HISTORY_SETTING,
  MEDICAL_FIELDS,
  type MedicalFile,
} from "../lib/safetyApi";
import type { StaffReportDetail } from "../lib/types";
import { ReasonField } from "./Phase9Bits";

function medicalValue(
  t: (k: string) => string,
  date: (iso: string) => string,
  file: MedicalFile,
  key: (typeof MEDICAL_FIELDS)[number],
) {
  const v = file[key];
  if (v === null || v === undefined || v === "") return null;
  if (key === "sex") return t(`safety.medical.sex.${v}`);
  if (key === "birth_date") return date(v);
  return v;
}

/** "Medical file attached": opened only on request (audited), closed again in one click. */
export function MedicalSection({ report }: { report: Pick<StaffReportDetail, "id" | "medical_attached"> }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const open = useMutation({ mutationFn: () => api.reportMedical(report.id) });
  if (!report.medical_attached) return null;
  const opened = open.data;
  const rows = opened
    ? MEDICAL_FIELDS.map((k) => [k, medicalValue(t, (iso) => fmt.date(iso), opened.data, k)] as const).filter(
        ([, v]) => v !== null,
      )
    : [];

  return (
    <section className="card" aria-labelledby="sec-medical">
      <h2 id="sec-medical">{t("safety.medical.title")}</h2>
      {!opened ? (
        <>
          <p className="muted">{t("safety.medical.intro")}</p>
          <button type="button" className="btn" disabled={open.isPending} onClick={() => open.mutate()}>
            {t("safety.medical.open")}
          </button>
          {open.isError && (
            <p className="alert alert--error" role="alert">
              {t(errorMessageKey(open.error))}
            </p>
          )}
        </>
      ) : (
        <>
          <p className="muted">{t("safety.medical.attachedAt", { at: fmt.dateTime(opened.attached_at) })}</p>
          {rows.length === 0 ? (
            <p>{t("safety.medical.empty")}</p>
          ) : (
            <dl className="fields">
              {rows.map(([k, v]) => (
                <Fragment key={k}>
                  <dt>{t(`safety.medical.fields.${k}`)}</dt>
                  <dd dir={k === "contact_phone" || k === "blood_group" ? "ltr" : "auto"}>{v}</dd>
                </Fragment>
              ))}
            </dl>
          )}
          <p className="muted">{t("safety.medical.audited")}</p>
          <button type="button" className="btn btn--small" onClick={() => open.reset()}>
            {t("safety.medical.close")}
          </button>
        </>
      )}
    </section>
  );
}

const osm = (lat: number, lon: number) =>
  `https://www.openstreetmap.org/?mlat=${lat.toFixed(5)}&mlon=${lon.toFixed(5)}#map=17/${lat.toFixed(5)}/${lon.toFixed(5)}`;

/** Missing person: the operator gives the person's phone and a reason; the person is told through the app. */
export function LocationHistorySearch({ report }: { report: Pick<StaffReportDetail, "id"> }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const id = useId();
  const allowed = canSearchLocationHistory(user?.identity.roles ?? []);
  const settings = usePlatformSettings(allowed);
  const [phone, setPhone] = useState("");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const search = useMutation({
    mutationFn: () => api.searchLocationHistory({ phone: phone.trim(), report_id: report.id, reason: reason.trim() }),
  });
  if (!allowed || settingOf(settings.data, LOCATION_HISTORY_SETTING)?.value !== true) return null;

  const phoneOk = HISTORY_PHONE.test(phone.trim());
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (!phoneOk || !reasonValid(reason, HISTORY_REASON_RANGE)) return;
    search.mutate();
  };
  const result = search.data;

  return (
    <section className="card" aria-labelledby="sec-history-search">
      <h2 id="sec-history-search">{t("safety.history.title")}</h2>
      <p className="muted">{t("safety.history.intro")}</p>
      <form noValidate onSubmit={submit}>
        <div className="field">
          <label htmlFor={`${id}-phone`}>{t("safety.history.phone")}</label>
          <input
            id={`${id}-phone`}
            type="tel"
            dir="ltr"
            aria-required="true"
            value={phone}
            aria-invalid={tried && !phoneOk ? true : undefined}
            onChange={(e) => setPhone(e.target.value)}
          />
          {tried && !phoneOk && <p className="field__error">{t("safety.history.phoneInvalid")}</p>}
        </div>
        <ReasonField
          label={t("safety.history.reason")}
          value={reason}
          onChange={setReason}
          range={HISTORY_REASON_RANGE}
          showError={tried}
        />
        <button type="submit" className="btn btn--danger" disabled={search.isPending}>
          {t("safety.history.submit")}
        </button>
        <p className="muted">{t("safety.history.audited")}</p>
      </form>
      {search.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(search.error))}
        </p>
      )}
      <div role="status" aria-live="polite">
        {result && !result.found && <p className="alert alert--info">{t("safety.history.noAccount")}</p>}
        {result?.found && result.points.length === 0 && (
          <p className="alert alert--info">{result.enabled ? t("safety.history.noPoints") : t("safety.history.notEnabled")}</p>
        )}
      </div>
      {result?.found && result.points.length > 0 && (
        <table className="table">
          <caption>{t("safety.history.points", { count: result.points.length })}</caption>
          <thead>
            <tr>
              <th scope="col">{t("safety.history.at")}</th>
              <th scope="col">{t("safety.history.position")}</th>
              <th scope="col">{t("safety.history.accuracy")}</th>
            </tr>
          </thead>
          <tbody>
            {[...result.points].reverse().map((p) => (
              <tr key={p.at}>
                <td>{fmt.dateTime(p.at)}</td>
                <td dir="ltr">
                  <a href={osm(p.lat, p.lon)} target="_blank" rel="noreferrer noopener">
                    {p.lat.toFixed(5)}, {p.lon.toFixed(5)}
                  </a>
                </td>
                <td>{p.accuracy_m === null ? "—" : fmt.meters(p.accuracy_m)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
