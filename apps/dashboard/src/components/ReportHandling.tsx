/**
 * Handling of a report across rooms (phase 9 §4): claim and release, the SLA countdown, the central referral to a
 * region and its acceptance or refusal by the target room, geographic verification, and the escalation trail.
 * Buttons follow the §1.2 action matrix; the API decides (404/403/409 are shown as they come).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { applyLiveEvent } from "../lib/liveCache";
import { REASON_RANGE, reasonValid } from "../lib/phase9";
import { p9Keys } from "../lib/phase9Api";
import { ESCALATION_KINDS, GEO_REASONS, type Escalation, type ReferBody } from "../lib/phase9Types";
import {
  canGeoVerify,
  canReferReports,
  mayClaim,
  mayDecideReferral,
  mayReleaseClaim,
  roomOf,
} from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import type { StaffReport, StaffReportDetail } from "../lib/types";
import {
  ClaimBadge,
  EscalationTag,
  GeoStateTag,
  InlineDialog,
  ReasonField,
  SlaBandTag,
  SlaCountdown,
  useRoomName,
} from "./Phase9Bits";

type Panel = "release" | "refer" | "accept" | "refuse" | "geo" | null;

const REFERABLE = new Set(["late", "central_responding", "referral_refused"]);

/** Message of a failed claim: `409 already_claimed` names the room and the person holding it. */
export function ClaimError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const roomName = useRoomName();
  if (isApiError(error) && error.code === "already_claimed" && error.body) {
    const room = typeof error.body.claimed_room === "string" ? error.body.claimed_room : null;
    const name = typeof error.body.claimed_by_name === "string" ? error.body.claimed_by_name : null;
    return (
      <p className="alert alert--error" role="alert">
        {t("claim.alreadyClaimedBy", { name: name || t("claim.someone"), room: roomName(room) })}
      </p>
    );
  }
  return (
    <p className="alert alert--error" role="alert">
      {t(errorMessageKey(error))}
    </p>
  );
}

function EscalationItem({ e }: { e: Escalation }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const roomName = useRoomName();
  const known = (ESCALATION_KINDS as readonly string[]).includes(e.kind);
  return (
    <li>
      <strong>{known ? t(`escalation.kind.${e.kind}`) : e.kind}</strong>{" "}
      <time dateTime={e.at}>{fmt.dateTime(e.at)}</time>
      {(e.from_room || e.to_room) && (
        <span className="muted"> · {t("escalation.fromTo", { from: roomName(e.from_room), to: roomName(e.to_room) })}</span>
      )}
      {e.actor_name && <span className="muted"> · {t("escalation.by", { actor: e.actor_name })}</span>}
      {e.reason && (
        <p className="timeline__note" dir="auto">
          {e.reason}
        </p>
      )}
    </li>
  );
}

function ReferForm({ report, onDone }: { report: StaffReportDetail; onDone: (r: StaffReportDetail) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const [to, setTo] = useState<string>(report.gouvernorat_code ? String(report.gouvernorat_code) : "");
  const [reason, setReason] = useState("");
  const [withDirective, setWithDirective] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [urgency, setUrgency] = useState<"normal" | "urgent">("urgent");
  const [tried, setTried] = useState(false);
  const mutation = useMutation({
    mutationFn: (b: ReferBody) => api.referReport(report.id, b),
    onSuccess: onDone,
  });
  const directiveOk = !withDirective || (title.trim().length >= 3 && title.trim().length <= 150 && body.trim().length > 0);
  const valid = to !== "" && reasonValid(reason) && directiveOk;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (!valid) return;
    mutation.mutate({
      to_gouvernorat_code: Number(to),
      reason: reason.trim(),
      directive: withDirective ? { title: title.trim(), body: body.trim(), urgency } : null,
    });
  };
  return (
    <form onSubmit={submit} noValidate>
      <div className="field">
        <label htmlFor={`${id}-to`}>{t("referral.to")}</label>
        <select id={`${id}-to`} value={to} onChange={(e) => setTo(e.target.value)} aria-invalid={tried && !to ? true : undefined}>
          <option value="">{t("referral.choose")}</option>
          {gouvernorats.list.map((g) => (
            <option key={g.code} value={g.code}>
              {gouvernorats.nameOf(g.code)}
            </option>
          ))}
        </select>
      </div>
      <ReasonField label={t("referral.reason")} value={reason} onChange={setReason} showError={tried} />
      <label className="checkbox">
        <input type="checkbox" checked={withDirective} onChange={(e) => setWithDirective(e.target.checked)} />{" "}
        {t("referral.withDirective")}
      </label>
      {withDirective && (
        <fieldset>
          <legend>{t("referral.directive")}</legend>
          <div className="field">
            <label htmlFor={`${id}-title`}>{t("committee.directives.fieldTitle")}</label>
            <input id={`${id}-title`} value={title} maxLength={150} dir="auto" onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={`${id}-body`}>{t("committee.directives.fieldBody")}</label>
            <textarea id={`${id}-body`} rows={3} value={body} dir="auto" onChange={(e) => setBody(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={`${id}-urgency`}>{t("committee.directives.urgency")}</label>
            <select id={`${id}-urgency`} value={urgency} onChange={(e) => setUrgency(e.target.value as "normal" | "urgent")}>
              <option value="normal">{t("committee.urgency.normal")}</option>
              <option value="urgent">{t("committee.urgency.urgent")}</option>
            </select>
          </div>
          {tried && !directiveOk && <p className="field__error">{t("committee.directives.titleLength")}</p>}
        </fieldset>
      )}
      <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
        {t("referral.submit")}
      </button>
      {mutation.isError && <ClaimError error={mutation.error} />}
    </form>
  );
}

/** Verified gouvernorat of a geo-pending report (candidates first) with the reason; national room only. */
export function GeoVerifyForm({
  report,
  onDone,
}: {
  report: Pick<StaffReport, "id" | "geo_candidates">;
  onDone: (r: StaffReportDetail) => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const candidates = report.geo_candidates ?? [];
  const [code, setCode] = useState<string>(candidates[0] !== undefined ? String(candidates[0]) : "");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const mutation = useMutation({
    mutationFn: () => api.geoVerify(report.id, Number(code), reason.trim()),
    onSuccess: onDone,
  });
  const others = gouvernorats.list.filter((g) => !candidates.includes(g.code));
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (code && reasonValid(reason)) mutation.mutate();
      }}
    >
      <div className="field">
        <label htmlFor={`${id}-code`}>{t("geo.verifiedGouvernorat")}</label>
        <select id={`${id}-code`} value={code} onChange={(e) => setCode(e.target.value)}>
          <option value="">{t("referral.choose")}</option>
          {candidates.length > 0 && (
            <optgroup label={t("geo.candidates")}>
              {candidates.map((c) => (
                <option key={c} value={c}>
                  {gouvernorats.nameOf(c)}
                </option>
              ))}
            </optgroup>
          )}
          <optgroup label={t("geo.otherGouvernorats")}>
            {others.map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
          </optgroup>
        </select>
      </div>
      <ReasonField label={t("geo.reason")} value={reason} onChange={setReason} showError={tried} />
      <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
        {t("geo.verify")}
      </button>
      {mutation.isError && <ClaimError error={mutation.error} />}
    </form>
  );
}

/** Handling panel of the report detail page. */
export function ReportHandling({ report }: { report: StaffReportDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const [panel, setPanel] = useState<Panel>(null);
  const [text, setText] = useState("");
  const [tried, setTried] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const identity = user?.identity;
  const key = queryKeys.report(report.id);

  const settle = (updated: StaffReportDetail, message: string) => {
    qc.setQueryData(key, updated);
    applyLiveEvent(qc, { type: "report.status_changed", report: updated });
    void qc.invalidateQueries({ queryKey: p9Keys.lateAll });
    void qc.invalidateQueries({ queryKey: p9Keys.geoQueue });
    setPanel(null);
    setText("");
    setTried(false);
    setDone(message);
  };
  const onError = (error: unknown) => {
    if (isApiError(error) && error.status === 409) void qc.invalidateQueries({ queryKey: key });
  };

  const claim = useMutation({
    mutationFn: () => api.claimReport(report.id),
    onSuccess: (r) => settle(r, t("claim.claimed")),
    onError,
  });
  const decide = useMutation({
    mutationFn: (v: { action: "release" | "accept" | "refuse"; text: string }) =>
      v.action === "release"
        ? api.releaseClaim(report.id, v.text)
        : v.action === "accept"
          ? api.acceptReferral(report.id, v.text)
          : api.refuseReferral(report.id, v.text),
    onSuccess: (r, v) => settle(r, t(`claim.done.${v.action}`)),
    onError,
  });

  if (!identity) return null;
  const ownRoom = roomOf(identity);
  const claimable =
    report.status === "received" || report.status === "in_progress" ? mayClaim(identity, report) : false;
  const showClaim = claimable && report.claimed_room !== ownRoom;
  const showRelease = mayReleaseClaim(identity, report.claimed_room);
  const showRefer = canReferReports(identity) && REFERABLE.has(report.escalation_state ?? "none");
  const showDecide = mayDecideReferral(identity, report);
  const geoPending = report.geo_state === "pending" || report.geo_state === "contradictory";
  const showGeo = canGeoVerify(identity) && geoPending;
  const waiting = report.status === "received" && !report.claimed_room;
  const escalations = report.escalations ?? [];
  const busy = claim.isPending || decide.isPending;

  const open = (p: Panel) => {
    setPanel(p);
    setText("");
    setTried(false);
    setDone(null);
  };
  const submitText = (action: "release" | "accept" | "refuse") => (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    // The acceptance note is optional; a release or refusal needs a reason.
    if (action !== "accept" && !reasonValid(text)) return;
    decide.mutate({ action, text: text.trim() });
  };

  return (
    <section className="card" aria-labelledby="sec-handling">
      <h2 id="sec-handling">{t("claim.title")}</h2>
      <dl className="fields">
        <dt>{t("claim.handledBy")}</dt>
        <dd>
          <ClaimBadge report={report} />
          {report.claimed_at && (
            <span className="muted">
              {" "}
              · <time dateTime={report.claimed_at}>{fmt.dateTime(report.claimed_at)}</time>
            </span>
          )}
        </dd>
        {report.sla_band && (
          <>
            <dt>{t("sla.bandLabel")}</dt>
            <dd>
              <SlaBandTag band={report.sla_band} />
            </dd>
          </>
        )}
        {waiting && report.sla_due_at && (
          <>
            <dt>{t("sla.deadline")}</dt>
            <dd>
              <SlaCountdown dueAt={report.sla_due_at} />
            </dd>
          </>
        )}
        {report.escalation_state && report.escalation_state !== "none" && (
          <>
            <dt>{t("escalation.label")}</dt>
            <dd>
              <EscalationTag state={report.escalation_state} />
              {report.referred_to !== null && report.referred_to !== undefined && (
                <span className="muted"> · {t("referral.referredTo", { name: gouvernorats.nameOf(report.referred_to) })}</span>
              )}
            </dd>
          </>
        )}
        {geoPending && (
          <>
            <dt>{t("geo.label")}</dt>
            <dd>
              <GeoStateTag state={report.geo_state} />
              {report.geo_reason && (GEO_REASONS as readonly string[]).includes(report.geo_reason) && (
                <span className="muted"> · {t(`geo.reasonCode.${report.geo_reason}`)}</span>
              )}
              {(report.geo_candidates ?? []).length > 0 && (
                <span className="muted">
                  {" "}
                  ·{" "}
                  {t("geo.candidatesList", {
                    list: (report.geo_candidates ?? []).map((c) => gouvernorats.nameOf(c)).join(t("common.listSeparator")),
                  })}
                </span>
              )}
            </dd>
          </>
        )}
      </dl>

      <div className="actions">
        {showClaim && (
          <button type="button" className="btn btn--primary" disabled={busy} onClick={() => claim.mutate()}>
            {t("claim.claim")}
          </button>
        )}
        {showRelease && (
          <button type="button" className="btn" disabled={busy} onClick={() => open("release")}>
            {t("claim.release")}
          </button>
        )}
        {showDecide && (
          <>
            <button type="button" className="btn btn--primary" disabled={busy} onClick={() => open("accept")}>
              {t("referral.accept")}
            </button>
            <button type="button" className="btn" disabled={busy} onClick={() => open("refuse")}>
              {t("referral.refuse")}
            </button>
          </>
        )}
        {showRefer && (
          <button type="button" className="btn" onClick={() => open("refer")}>
            {t("referral.open")}
          </button>
        )}
        {showGeo && (
          <button type="button" className="btn" onClick={() => open("geo")}>
            {t("geo.open")}
          </button>
        )}
      </div>

      {(panel === "release" || panel === "accept" || panel === "refuse") && (
        <InlineDialog title={t(`claim.dialog.${panel}`)} onClose={() => setPanel(null)}>
          <form noValidate onSubmit={submitText(panel)}>
            {panel === "accept" ? (
              <div className="field">
                <label htmlFor={`note-${report.id}`}>{t("referral.note")}</label>
                <textarea
                  id={`note-${report.id}`}
                  rows={2}
                  maxLength={REASON_RANGE.max}
                  dir="auto"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              </div>
            ) : (
              <ReasonField label={t("claim.reason")} value={text} onChange={setText} showError={tried} />
            )}
            <button type="submit" className="btn btn--primary" disabled={busy}>
              {t(`claim.confirm.${panel}`)}
            </button>
          </form>
        </InlineDialog>
      )}
      {panel === "refer" && (
        <InlineDialog title={t("referral.title")} onClose={() => setPanel(null)}>
          <ReferForm report={report} onDone={(r) => settle(r, t("referral.sent"))} />
        </InlineDialog>
      )}
      {panel === "geo" && (
        <InlineDialog title={t("geo.dialogTitle")} onClose={() => setPanel(null)}>
          <GeoVerifyForm report={report} onDone={(r) => settle(r, t("geo.verified"))} />
        </InlineDialog>
      )}

      <div aria-live="polite" role="status">
        {done && !busy && <p className="alert alert--ok">{done}</p>}
      </div>
      {claim.isError && <ClaimError error={claim.error} />}
      {decide.isError && <ClaimError error={decide.error} />}

      <h3>{t("escalation.trail")}</h3>
      {escalations.length === 0 ? (
        <p className="muted">{t("escalation.none")}</p>
      ) : (
        <ol className="timeline">
          {escalations.map((e, i) => (
            <EscalationItem key={`${e.at}-${i}`} e={e} />
          ))}
        </ol>
      )}
    </section>
  );
}
