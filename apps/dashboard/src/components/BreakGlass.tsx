/**
 * Sensitive reporter data and break-glass access (phase 9 §1.3, §6.1). The API masks the reporter unless the
 * caller's room handles the report; a justified, time-limited break-glass grant reveals it read-only, and every
 * reveal is audited. Nothing is unmasked by the dashboard itself.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { p9Keys } from "../lib/phase9Api";
import {
  BREAKGLASS_DURATIONS,
  BREAKGLASS_MAX_JUSTIFICATION,
  BREAKGLASS_MIN_JUSTIFICATION,
  type BreakGlassBody,
  type BreakGlassGrant,
  type BreakGlassTarget,
} from "../lib/phase9Types";
import { canRequestBreakGlass } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import type { StaffReportDetail } from "../lib/types";
import { InlineDialog, ReasonField } from "./Phase9Bits";
import { CallButton } from "./Softphone";

/** Active grants of the signed-in user (`GET /staff/break-glass?status=active`). */
export function useActiveGrants() {
  const { api } = useServices();
  const { user } = useAuth();
  const enabled = canRequestBreakGlass(user?.identity.roles ?? []);
  return useQuery({
    queryKey: p9Keys.grants("active"),
    queryFn: ({ signal }) => api.breakGlassGrants({ status: "active", signal }),
    enabled,
    staleTime: 30_000,
    select: (page) => page.items.filter((g) => !g.revoked_at && Date.parse(g.expires_at) > Date.now()),
  });
}

/** Whether a grant covers a report (its id, its incident or its gouvernorat). */
export function grantCovers(
  grant: BreakGlassGrant,
  report: Pick<StaffReportDetail, "id" | "incident_id" | "gouvernorat_code">,
): boolean {
  if (grant.target_kind === "report") return grant.target_id === report.id;
  if (grant.target_kind === "incident") return Boolean(report.incident_id) && grant.target_id === report.incident_id;
  return grant.gouvernorat_code !== null && grant.gouvernorat_code === report.gouvernorat_code;
}

export function RevokeButton({ grant }: { grant: BreakGlassGrant }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const revoke = useMutation({
    mutationFn: () => api.revokeBreakGlass(grant.id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: p9Keys.grantsAll });
      void qc.invalidateQueries({ queryKey: queryKeys.reportsAll });
      void qc.invalidateQueries({ queryKey: ["report"] });
    },
  });
  return (
    <>
      <button type="button" className="btn btn--small" disabled={revoke.isPending} onClick={() => revoke.mutate()}>
        {t("breakGlass.revoke")}
      </button>
      {revoke.isError && (
        <span className="field__error" role="alert">
          {t(errorMessageKey(revoke.error))}
        </span>
      )}
    </>
  );
}

/** Banner shown while the user holds active break-glass grants (every reveal is audited). */
export function ActiveGrantBanner({ report }: { report?: Pick<StaffReportDetail, "id" | "incident_id" | "gouvernorat_code"> }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const grants = useActiveGrants();
  const shown = (grants.data ?? []).filter((g) => !report || grantCovers(g, report));
  if (shown.length === 0) return null;
  return (
    <div className="alert alert--warn grant-banner" role="status">
      <strong>{t("breakGlass.activeTitle")}</strong>
      <ul>
        {shown.map((g) => (
          <li key={g.id}>
            {t(`breakGlass.target.${g.target_kind}`)} · {t("breakGlass.until", { time: fmt.dateTime(g.expires_at) })}{" "}
            <RevokeButton grant={g} />
          </li>
        ))}
      </ul>
      <p className="muted">{t("breakGlass.audited")}</p>
    </div>
  );
}

/** Justified, time-limited request for read-only access (15–240 minutes, 20–1000 characters of justification). */
export function BreakGlassForm({
  report,
  onDone,
}: {
  report: Pick<StaffReportDetail, "id" | "incident_id" | "gouvernorat_code">;
  onDone: (grant: BreakGlassGrant) => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const [target, setTarget] = useState<BreakGlassTarget>("report");
  const [justification, setJustification] = useState("");
  const [duration, setDuration] = useState(60);
  const [tried, setTried] = useState(false);
  const mutation = useMutation({ mutationFn: (b: BreakGlassBody) => api.requestBreakGlass(b), onSuccess: onDone });
  const range = { min: BREAKGLASS_MIN_JUSTIFICATION, max: BREAKGLASS_MAX_JUSTIFICATION };
  const targets: BreakGlassTarget[] = ["report"];
  if (report.incident_id) targets.push("incident");
  if (report.gouvernorat_code !== null) targets.push("gouvernorat");
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    const n = justification.trim().length;
    if (n < range.min || n > range.max) return;
    mutation.mutate({
      target_kind: target,
      target_id: target === "report" ? report.id : target === "incident" ? (report.incident_id ?? null) : null,
      gouvernorat_code: target === "gouvernorat" ? report.gouvernorat_code : null,
      justification: justification.trim(),
      duration_min: duration,
    });
  };
  return (
    <form noValidate onSubmit={submit}>
      <p className="muted">{t("breakGlass.intro")}</p>
      <fieldset>
        <legend>{t("breakGlass.targetLabel")}</legend>
        {targets.map((k) => (
          <label key={k} className="radio">
            <input type="radio" name={`${id}-target`} checked={target === k} onChange={() => setTarget(k)} />{" "}
            {k === "gouvernorat"
              ? t("breakGlass.targetGouvernorat", { name: gouvernorats.nameOf(report.gouvernorat_code) ?? "" })
              : t(`breakGlass.target.${k}`)}
          </label>
        ))}
      </fieldset>
      <ReasonField
        label={t("breakGlass.justification")}
        value={justification}
        onChange={setJustification}
        range={range}
        showError={tried}
      />
      <div className="field">
        <label htmlFor={`${id}-duration`}>{t("breakGlass.duration")}</label>
        <select id={`${id}-duration`} value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
          {BREAKGLASS_DURATIONS.map((m) => (
            <option key={m} value={m}>
              {t("breakGlass.minutes", { count: m })}
            </option>
          ))}
        </select>
      </div>
      <button type="submit" className="btn btn--danger" disabled={mutation.isPending}>
        {t("breakGlass.submit")}
      </button>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </form>
  );
}

/** Reporter card of the report detail: full data for the handling room, masked otherwise, with break-glass. */
export function ReporterSection({ report }: { report: StaffReportDetail }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const qc = useQueryClient();
  const gouvernorats = useGouvernorats();
  const [open, setOpen] = useState(false);
  const [granted, setGranted] = useState(false);
  const reporter = report.reporter;
  const masked = reporter.masked === true;
  const mayRequest = canRequestBreakGlass(user?.identity.roles ?? []);
  const context = report.reporter_context ?? null;

  return (
    <section className="card" aria-labelledby="sec-reporter">
      <h2 id="sec-reporter">{t("detail.reporter")}</h2>
      <ActiveGrantBanner report={report} />
      {masked && <p className="alert alert--info">{t("reporterMask.notice")}</p>}
      {reporter.kind === "anonymous" && !masked ? (
        <p>{t("detail.anonymous")}</p>
      ) : (
        <dl className="fields">
          <dt>{t("detail.fields.reporterKind")}</dt>
          <dd>{t(`reporterKind.${reporter.kind}`)}</dd>
          <dt>{t("detail.name")}</dt>
          <dd dir="auto">
            {masked
              ? t("reporterMask.hidden")
              : [reporter.first_name, reporter.last_name].filter(Boolean).join(" ") || t("common.notAvailable")}
          </dd>
          <dt>{t("detail.phone")}</dt>
          <dd>
            {masked ? (
              <>
                <span dir="ltr" className="code" aria-label={t("reporterMask.maskedPhone")}>
                  {reporter.phone ?? t("reporterMask.hidden")}
                </span>{" "}
                <CallButton body={{ report_id: report.id }} label={t("reporterMask.callWithoutNumber")} />
              </>
            ) : reporter.phone ? (
              <>
                <a href={`tel:${reporter.phone}`} dir="ltr">
                  {reporter.phone}
                </a>{" "}
                <CallButton body={{ report_id: report.id }} label={t("phone.callReporter")} />
              </>
            ) : (
              t("common.notAvailable")
            )}
          </dd>
          {context && (
            <>
              <dt>{t("reporterMask.context")}</dt>
              <dd>
                {context.source === "profile" && context.reporter_gouvernorat_code !== null
                  ? t("reporterMask.contextProfile", { name: gouvernorats.nameOf(context.reporter_gouvernorat_code) })
                  : t("reporterMask.contextNone")}
              </dd>
            </>
          )}
        </dl>
      )}
      {masked && mayRequest && !open && (
        <button type="button" className="btn" onClick={() => setOpen(true)}>
          {t("breakGlass.open")}
        </button>
      )}
      {open && (
        <InlineDialog title={t("breakGlass.title")} onClose={() => setOpen(false)}>
          <BreakGlassForm
            report={report}
            onDone={() => {
              setOpen(false);
              setGranted(true);
              void qc.invalidateQueries({ queryKey: p9Keys.grantsAll });
              void qc.invalidateQueries({ queryKey: queryKeys.report(report.id) });
            }}
          />
        </InlineDialog>
      )}
      <div role="status" aria-live="polite">
        {granted && <p className="alert alert--ok">{t("breakGlass.granted")}</p>}
      </div>
    </section>
  );
}
