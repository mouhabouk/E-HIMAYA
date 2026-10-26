import { useTranslation } from "react-i18next";
import { COUNTERS, type CrewRef, type Transport } from "../lib/crewTypes";
import { useFormat } from "../lib/hooks";
import type { Assignment } from "../lib/opsTypes";
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

/**
 * F-DSH-35 (part, phase P4a): what the team leaders send from the scene — first reports (backup needed and danger to
 * the crew stand out), the live casualty counters and the victims taken to hospital.
 */
export function FieldSection({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const reports = incident.field_reports ?? [];
  const casualties = incident.casualties;
  const transports = incident.transports ?? [];
  const counted = casualties && COUNTERS.some((c) => casualties[c] > 0);
  if (reports.length === 0 && !counted && transports.length === 0) return null;
  const alarms = reports.filter((r) => r.crew_danger || r.backup_needed);
  return (
    <section className="card" aria-labelledby="sec-field">
      <h2 id="sec-field">{t("crew.fieldTitle")}</h2>
      {alarms.map((r) => (
        <p key={`alarm-${r.id}`} className="alert alert--error" role="alert">
          <strong dir="auto">{r.resource_label ?? t("crew.vehicle")}</strong>
          {": "}
          {[r.crew_danger && t("crew.danger"), r.backup_needed && t("crew.backup")].filter(Boolean).join(" · ")}
          {r.backup_note && (
            <span dir="auto">
              {" — "}
              {r.backup_note}
            </span>
          )}
        </p>
      ))}
      {casualties && (
        <dl className="crew-counters" aria-label={t("crew.casualties")}>
          {COUNTERS.map((c) => (
            <div key={c} className={`crew-counter crew-counter--${c}`}>
              <dt>{t(`crew.counter.${c}`)}</dt>
              <dd>{fmt.number(casualties[c])}</dd>
            </div>
          ))}
        </dl>
      )}
      {reports.length > 0 && (
        <>
          <h3>{t("crew.firstReports")}</h3>
          <ul className="crew-reports">
            {reports.map((r) => (
              <li key={r.id}>
                <strong dir="auto">{r.resource_label ?? "—"}</strong> · {t(`category.${r.category}`)} ·{" "}
                <span className={`chip chip--severity-${r.severity}`}>{t(`crew.severity.${r.severity}`)}</span>{" "}
                <span className="muted">
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
  }
  return parts;
}
