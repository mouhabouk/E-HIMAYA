import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { crewKeys } from "../lib/crewApi";
import {
  COUNTERS,
  type CrewAlert,
  type CrewRef,
  type FieldAttachment,
  type FieldReport,
  type ReportTemplate,
  type Transport,
} from "../lib/crewTypes";
import { errorMessageKey } from "../lib/api";
import { useFormat, useLanguage } from "../lib/hooks";
import { localized } from "../lib/localized";
import type { Assignment, VehiclePosition } from "../lib/opsTypes";
import { queryKeys } from "../lib/staffApi";
import { canMarkCrewAlerts } from "../lib/roles";
import type { IncidentDetail } from "../lib/types";

/** Under a vehicle's assignment: the team leader on the staff app, crew size and whether the order was read. */
export function CrewLine({ crew }: { crew: CrewRef }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <div className="cell-sub crew-line">
      <span dir="auto">{t("crew.leader", { name: crew.leader_name ?? "—" })}</span>
      {" · "}
      <span>{t("crew.size", { count: crew.crew_size })}</span>
      {" · "}
      {crew.acknowledged_at ? (
        <span className="chip chip--crew-ack">
          {t("crew.acknowledged", { time: fmt.time(crew.acknowledged_at) })}
        </span>
      ) : (
        <span className="chip chip--crew-waiting">{t("crew.notAcknowledged")}</span>
      )}
      {(crew.unseen_alerts ?? 0) > 0 && (
        <>
          {" · "}
          <span className="chip chip--crew-waiting">{t("crew.unseenAlerts", { count: crew.unseen_alerts })}</span>
        </>
      )}
    </div>
  );
}

/** Phase P4d: where the vehicle was last seen by the leader's phone, and how far from the incident. */
export function PositionLine({ position }: { position: VehiclePosition }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  // "N min ago" moves on by itself between two refreshes of the incident.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);
  const seconds = Math.max(0, (now - new Date(position.at).getTime()) / 1000);
  const ago = fmt.duration(seconds < 60 ? seconds : Math.round(seconds / 60) * 60);
  return (
    <div className="cell-sub crew-position">
      <time dateTime={position.at}>
        {position.distance_m == null
          ? t("crew.lastPosition", { ago })
          : t("crew.lastPositionDistance", { ago, km: fmt.decimal(position.distance_m / 1000) })}
      </time>
    </div>
  );
}

/** Phase F: what the team's phone added to the mission: the nature it confirmed, the point the room picked, the
 * steps it skipped and why, the end without intervention, a mission opened from the field. */
export function FieldFlowLine({ assignment }: { assignment: Assignment }) {
  const { t } = useTranslation();
  const skipped = Object.entries(assignment.skipped ?? {});
  const parts: ReactNode[] = [];
  if (assignment.field_initiated) parts.push(<span className="chip chip--crew-waiting">{t("crew.flow.fieldInitiated")}</span>);
  if (assignment.crew_nature) parts.push(<span>{t("crew.flow.nature", { nature: t(`crew.nature.${assignment.crew_nature}`) })}</span>);
  if (assignment.target)
    parts.push(
      <span>
        {t("crew.flow.target")}{" "}
        <bdi dir="ltr">
          {assignment.target.lat.toFixed(5)}, {assignment.target.lon.toFixed(5)}
        </bdi>
        {assignment.target_note && <span dir="auto"> ({assignment.target_note})</span>}
      </span>,
    );
  for (const [step, reason] of skipped)
    parts.push(
      <span>
        {t("crew.flow.skipped", { step: t(`record.step.${step}_at`), reason: t(`crew.skipReason.${reason}`) })}
      </span>,
    );
  if (assignment.no_intervention_reason)
    parts.push(
      <span className="chip chip--crew-revoked">
        {t("crew.flow.noIntervention", { reason: t(`crew.noInterventionReason.${assignment.no_intervention_reason}`) })}
      </span>,
    );
  if (parts.length === 0) return null;
  return (
    <div className="cell-sub crew-flow">
      {parts.map((p, i) => (
        <span key={i}>
          {i > 0 && " · "}
          {p}
        </span>
      ))}
    </div>
  );
}

function TransportsTable({ rows, assignments }: { rows: Transport[]; assignments: Assignment[] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const vehicle = (id: string) => assignments.find((a) => a.id === id)?.resource?.label ?? "—";
  return (
    <div className="table-wrap">
      <table className="table">
        <caption className="visually-hidden">{t("crew.transports")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("crew.triage")}</th>
            <th scope="col">{t("crew.victim")}</th>
            <th scope="col">{t("crew.hospital")}</th>
            <th scope="col">{t("crew.vehicle")}</th>
            <th scope="col">{t("crew.at")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>
                <span className={`chip chip--triage-${r.triage}`}>{t(`crew.triageName.${r.triage}`)}</span>
              </td>
              <td>
                {t(`crew.age.${r.age_band}`)} · {t(`crew.sex.${r.sex}`)}
              </td>
              <td dir="auto">{r.hospital}</td>
              <td dir="auto">{vehicle(r.assignment_id)}</td>
              <td>
                <time dateTime={r.created_at}>{fmt.time(r.created_at)}</time>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A backup or danger alert: red until an operator marks it as seen, which the leader's phone then shows. */
function AlertRow({ alert, incidentId, canMark }: { alert: CrewAlert; incidentId: string; canMark: boolean }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api.markAlertSeen(alert.id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.incident(incidentId) });
      void qc.invalidateQueries({ queryKey: crewKeys.shifts });
    },
  });
  const items = alert.items.map((k) => t(`crew.${alert.kind}Kind.${k}`)).join(t("common.listSeparator"));
  const what = alert.kind === "backup" ? t("crew.backup") : t("crew.danger");
  const seen = alert.seen_at;
  return (
    <li className={`crew-alert crew-alert--${alert.kind}${seen ? " crew-alert--seen" : ""}`} role={seen ? undefined : "alert"}>
      <div>
        <strong dir="auto">{alert.resource_label ?? t("crew.vehicle")}</strong>
        {": "}
        {what}
        {items && <span> — {items}</span>}
        <div className="cell-sub">
          {alert.created_by_name && <span dir="auto">{alert.created_by_name} · </span>}
          <time dateTime={alert.created_at}>{fmt.time(alert.created_at)}</time>
          {alert.via === "sms" && (
            <>
              {" · "}
              <span className="chip chip--crew-waiting">{t("crew.viaSms")}</span>
            </>
          )}
          {seen && (
            <>
              {" · "}
              {t("crew.seenBy", { name: alert.seen_by_name ?? "—", time: fmt.time(seen) })}
            </>
          )}
        </div>
        {mutation.error ? (
          <p className="alert alert--error" role="alert">
            {t(errorMessageKey(mutation.error))}
          </p>
        ) : null}
      </div>
      {!seen && canMark && (
        <button
          type="button"
          className="btn btn--small btn--primary"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
          aria-label={t("crew.markSeenLabel", { what, vehicle: alert.resource_label ?? "" })}
        >
          {t("crew.markSeen")}
        </button>
      )}
    </li>
  );
}

/** A detailed report with the template's question labels (the version it answered). */
function DetailedReport({ report, templates }: { report: FieldReport; templates: ReportTemplate[] }) {
  const { t } = useTranslation();
  const lang = useLanguage();
  const fmt = useFormat();
  const template = templates.find((x) => x.id === report.template_id);
  const answers = report.answers ?? {};
  const label = (key: string) => {
    const field = template?.fields.find((f) => f.key === key);
    return field ? localized(field.label, lang) : key;
  };
  const value = (key: string, v: unknown): string => {
    const field = template?.fields.find((f) => f.key === key);
    const option = (o: unknown) => {
      const found = field?.options?.find((x) => x.key === o);
      return found ? localized(found.label, lang) : String(o);
    };
    if (typeof v === "boolean") return v ? t("common.yes") : t("common.no");
    if (Array.isArray(v)) return v.map(option).join(t("common.listSeparator"));
    if (typeof v === "number") return `${fmt.number(v)}${field?.unit ? ` ${localized(field.unit, lang)}` : ""}`;
    return option(v);
  };
  return (
    <div className="crew-detailed">
      <p className="muted">
        <strong dir="auto">{report.resource_label ?? "—"}</strong> ·{" "}
        {t("crew.templateVersion", { version: report.template_version ?? "—" })}
        {template?.simulated && <span className="tag tag--sim">[SIM]</span>}
        {" · "}
        {report.author_name && <span dir="auto">{report.author_name} · </span>}
        <time dateTime={report.created_at}>{fmt.time(report.created_at)}</time>
      </p>
      <dl className="crew-answers">
        {Object.entries(answers).map(([k, v]) => (
          <div key={k}>
            <dt>{label(k)}</dt>
            <dd dir={typeof v === "number" ? undefined : "auto"}>{value(k, v)}</dd>
          </div>
        ))}
      </dl>
      {report.note && (
        <p dir="auto">
          <strong>{t("crew.note")}: </strong>
          {report.note}
        </p>
      )}
    </div>
  );
}

function Attachments({ items }: { items: FieldAttachment[] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <ul className="crew-attachments">
      {items.map((a) => (
        <li key={a.id} className={`crew-attachment crew-attachment--${a.kind}`}>
          {a.kind === "photo" &&
            (a.url ? (
              <a href={a.url} target="_blank" rel="noreferrer">
                <img src={a.url} alt={t("crew.photoAlt", { time: fmt.time(a.created_at) })} loading="lazy" />
              </a>
            ) : (
              <span className="muted">{t("crew.photo")}</span>
            ))}
          {a.kind === "voice" &&
            (a.url ? (
              <audio controls preload="none" src={a.url} aria-label={t("crew.voice")} />
            ) : (
              <span className="muted">{t("crew.voice")}</span>
            ))}
          {a.kind === "text" && <p dir="auto">{a.body}</p>}
          <div className="cell-sub">
            {t(`crew.attachment.${a.kind}`)}
            {a.duration_s ? ` · ${t("crew.seconds", { count: Math.round(a.duration_s) })}` : ""}
            {" · "}
            {a.created_by_name && <span dir="auto">{a.created_by_name} · </span>}
            <time dateTime={a.created_at}>{fmt.time(a.created_at)}</time>
          </div>
        </li>
      ))}
    </ul>
  );
}

/**
 * F-DSH-35 (part, phases P4a and P4b): what the team leaders send from the scene — backup and danger alerts first
 * (with "seen" for the operator), the last situation report of each vehicle, the six live counters, the people taken
 * to hospital, the detailed reports with their template's labels, and the photos, voice notes and texts.
 */
export function FieldSection({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const { user } = useAuth();
  const canMark = canMarkCrewAlerts(user?.identity.roles ?? []);
  const reports = incident.field_reports ?? [];
  const casualties = incident.casualties;
  const transports = incident.transports ?? [];
  const alerts = incident.alerts ?? [];
  const attachments = incident.attachments ?? [];
  const situations = reports.filter((r) => r.kind !== "detailed" && r.kind !== "toll" && r.kind !== "report");
  // Phase F: the toll and the intervention report the team writes at the end (typed, or spoken and corrected).
  const closing = reports.filter((r) => r.kind === "toll" || r.kind === "report");
  const detailed = reports.filter((r) => r.kind === "detailed");
  const templates = useQuery({
    queryKey: crewKeys.templates(true),
    queryFn: ({ signal }) => api.reportTemplates(true, signal),
    enabled: detailed.length > 0,
    staleTime: 5 * 60_000,
  });
  const counted = casualties && COUNTERS.some((c) => casualties[c] > 0);
  if (
    situations.length === 0 &&
    detailed.length === 0 &&
    !counted &&
    transports.length === 0 &&
    alerts.length === 0 &&
    attachments.length === 0 &&
    closing.length === 0
  )
    return null;
  // The last situation report of each vehicle.
  const latest = new Map<string, FieldReport>();
  for (const r of situations) {
    const prev = latest.get(r.assignment_id);
    if (!prev || prev.created_at < r.created_at) latest.set(r.assignment_id, r);
  }
  const unseen = alerts.filter((a) => !a.seen_at);
  const seen = alerts.filter((a) => a.seen_at);
  return (
    <section className="card" aria-labelledby="sec-field">
      <h2 id="sec-field">{t("crew.fieldTitle")}</h2>
      {alerts.length > 0 && (
        <ul className="crew-alerts" aria-label={t("crew.alerts")}>
          {[...unseen, ...seen].map((a) => (
            <AlertRow key={a.id} alert={a} incidentId={incident.id} canMark={canMark} />
          ))}
        </ul>
      )}
      {casualties && (
        <dl className="crew-counters" aria-label={t("crew.casualties")}>
          {COUNTERS.map((c) => (
            <div key={c} className={`crew-counter crew-counter--${c}`}>
              <dt>{t(`crew.counter.${c}`)}</dt>
              <dd>{fmt.number(casualties[c])}</dd>
            </div>
          ))}
          <div className="crew-counter crew-counter--transported">
            <dt>{t("crew.counter.transported")}</dt>
            <dd>{fmt.number(casualties.transported ?? transports.length)}</dd>
          </div>
        </dl>
      )}
      {latest.size > 0 && (
        <>
          <h3>{t("crew.situations")}</h3>
          <ul className="crew-reports">
            {[...latest.values()].map((r) => (
              <li key={r.id}>
                <strong dir="auto">{r.resource_label ?? "—"}</strong> · {t(`category.${r.category}`)} ·{" "}
                {r.severity != null && (
                  <span className={`chip chip--severity-${r.severity}`}>{t(`crew.severity.${r.severity}`)}</span>
                )}{" "}
                {(r.backup_kinds ?? []).length > 0 && (
                  <span>
                    {t("crew.backup")}:{" "}
                    {(r.backup_kinds ?? []).map((k) => t(`crew.backupKind.${k}`)).join(t("common.listSeparator"))}{" "}
                  </span>
                )}
                <span className="muted">
                  {r.kind === "update" ? t("crew.update") : t("crew.first")} ·{" "}
                  {r.author_name && <span dir="auto">{r.author_name} · </span>}
                  <time dateTime={r.created_at}>{fmt.time(r.created_at)}</time>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      {transports.length > 0 && (
        <>
          <h3>{t("crew.transports")}</h3>
          <TransportsTable rows={transports} assignments={incident.assignments ?? []} />
        </>
      )}
      {detailed.length > 0 && (
        <>
          <h3>{t("crew.detailed")}</h3>
          {detailed.map((r) => (
            <DetailedReport key={r.id} report={r} templates={templates.data ?? []} />
          ))}
        </>
      )}
      {closing.length > 0 && (
        <>
          <h3>{t("crew.closing")}</h3>
          <ul className="crew-reports">
            {closing.map((r) => (
              <li key={r.id}>
                <strong dir="auto">{r.resource_label ?? "—"}</strong> ·{" "}
                {r.kind === "toll" ? t("crew.toll") : t("crew.interventionReport")}
                {r.kind === "toll" && typeof r.answers?.damage === "string" && (
                  <> · {t("crew.damage.label")}: {t(`crew.damage.${r.answers.damage}`)}</>
                )}
                {r.answers?.voice != null && <> <span className="chip chip--crew-ack">{t("crew.spoken")}</span></>}
                {r.note && (
                  <p className="report-text" dir="auto">
                    {r.note}
                  </p>
                )}
                <span className="muted">
                  {r.author_name && <span dir="auto">{r.author_name} · </span>}
                  <time dateTime={r.created_at}>{fmt.time(r.created_at)}</time>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      {attachments.length > 0 && (
        <>
          <h3>{t("crew.attachments")}</h3>
          <Attachments items={attachments} />
        </>
      )}
    </section>
  );
}

/** Timeline details of the events written from the phones. */
export function crewTimelineParts(
  kind: string,
  payload: Record<string, unknown>,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string[] {
  const parts: string[] = [];
  if (kind === "field_report") {
    if (payload.report === "update") parts.push(t("crew.update"));
    if (typeof payload.severity === "number") parts.push(t(`crew.severity.${payload.severity}`));
    if (payload.backup_needed === true) parts.push(t("crew.backup"));
    if (payload.crew_danger === true) parts.push(t("crew.danger"));
  } else if (kind === "casualties") {
    for (const c of COUNTERS) {
      if (typeof payload[c] === "number") parts.push(`${t(`crew.counter.${c}`)} ${payload[c]}`);
    }
  } else if (kind === "transport") {
    if (typeof payload.triage === "string") parts.push(t(`crew.triageName.${payload.triage}`));
    if (typeof payload.hospital === "string") parts.push(payload.hospital);
  } else if (kind === "crew_alert" || kind === "crew_alert_seen") {
    const alert = payload.alert === "danger" ? "danger" : "backup";
    parts.push(alert === "danger" ? t("crew.danger") : t("crew.backup"));
    if (Array.isArray(payload.items)) {
      parts.push(...payload.items.map((k) => t(`crew.${alert}Kind.${String(k)}`)));
    }
  } else if (kind === "field_attachment") {
    if (typeof payload.media === "string") parts.push(t(`crew.attachment.${payload.media}`));
  } else if (kind === "detailed_report") {
    if (typeof payload.template_version === "number")
      parts.push(t("crew.templateVersion", { version: payload.template_version }));
  }
  return parts;
}
