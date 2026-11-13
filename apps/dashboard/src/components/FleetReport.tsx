// covers: OS3-3 (docs/phase-os3/design-os3b.md §3, Yamen 2026-11-13): the monthly report of the fleet, readiness
// and the cost of maintenance per gouvernorat, the trend of the last months and the costliest vehicles; and the cost
// of a stay in the workshop, entered at the exit or later when the invoice arrives.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { errorMessageKey } from "../lib/api";
import {
  fleetKeys,
  MAINT_KINDS,
  readinessTone,
  type CostBody,
  type FleetReport,
  type FleetReportRow,
  type MaintKind,
  type VehicleEvent,
} from "../lib/fleet";
import { useFormat, useLanguage } from "../lib/hooks";
import { exportCsv } from "../lib/inspectionsApi";
import { inventoryKeys } from "../lib/inventory";
import { useServices } from "../context/services";
import { ErrorBox, Loading } from "./Feedback";

const MONEY = /^\d{1,9}([.,]\d{1,3})?$/;

function thisMonth(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Tunis", year: "numeric", month: "2-digit" }).format(new Date());
}

function money(value: string | null | undefined): number {
  return value ? Number(value) : 0;
}

// ---------------------------------------------------------------- the cost of a stay

export interface CostState {
  kind: MaintKind | "";
  parts: string;
  labour: string;
  external: string;
  invoice: string;
}

export const EMPTY_COST: CostState = { kind: "", parts: "", labour: "", external: "", invoice: "" };

export function costOf(e: VehicleEvent): CostState {
  return {
    kind: e.maint_kind ?? "",
    parts: e.cost_parts ?? "",
    labour: e.cost_labour ?? "",
    external: e.cost_external ?? "",
    invoice: e.invoice_ref ?? "",
  };
}

export function costValid(c: CostState): boolean {
  return [c.parts, c.labour, c.external].every((v) => !v.trim() || MONEY.test(v.trim()));
}

export function costBody(c: CostState): CostBody {
  const amount = (v: string) => (v.trim() ? v.trim().replace(",", ".") : null);
  return {
    maint_kind: c.kind || null,
    cost_parts: amount(c.parts),
    cost_labour: amount(c.labour),
    cost_external: amount(c.external),
    invoice_ref: c.invoice.trim() || null,
  };
}

/** The four amounts and the invoice, inside a form of the caller. */
export function CostFields({ value, onChange }: { value: CostState; onChange: (c: CostState) => void }) {
  const { t } = useTranslation();
  const id = useId();
  const set = (k: keyof CostState) => (e: { target: { value: string } }) => onChange({ ...value, [k]: e.target.value });
  return (
    <fieldset className="fleet-cost">
      <legend>{t("fleet.cost.title")}</legend>
      <div className="field">
        <label htmlFor={`${id}-k`}>{t("fleet.cost.kind")}</label>
        <select id={`${id}-k`} value={value.kind} onChange={set("kind")}>
          <option value="">—</option>
          {MAINT_KINDS.map((k) => (
            <option key={k} value={k}>
              {t(`fleet.cost.kinds.${k}`)}
            </option>
          ))}
        </select>
      </div>
      {(["parts", "labour", "external"] as const).map((k) => (
        <div className="field" key={k}>
          <label htmlFor={`${id}-${k}`}>{t(`fleet.cost.${k}`)}</label>
          <input
            id={`${id}-${k}`}
            dir="ltr"
            inputMode="decimal"
            value={value[k]}
            aria-invalid={value[k].trim() !== "" && !MONEY.test(value[k].trim())}
            onChange={set(k)}
          />
        </div>
      ))}
      <div className="field">
        <label htmlFor={`${id}-i`}>{t("fleet.cost.invoice")}</label>
        <input id={`${id}-i`} dir="auto" maxLength={60} value={value.invoice} onChange={set("invoice")} />
      </div>
      <p className="muted">{t("fleet.cost.help")}</p>
    </fieldset>
  );
}

/** The cost of a past stay (the line of the log), added or corrected when the invoice arrives. */
export function CostEditor({ event, onDone }: { event: VehicleEvent; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const [cost, setCost] = useState<CostState>(costOf(event));
  const [tried, setTried] = useState(false);
  const save = useMutation({
    mutationFn: () => api.setEventCost(event.id, costBody(cost)),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: inventoryKeys.all });
      onDone();
    },
  });
  return (
    <form
      className="card form-card"
      aria-label={t("fleet.cost.edit")}
      onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (costValid(cost)) save.mutate();
      }}
    >
      <h3 dir="auto">{event.label}</h3>
      <CostFields value={cost} onChange={setCost} />
      {tried && !costValid(cost) && <p className="alert alert--error">{t("fleet.cost.invalid")}</p>}
      {save.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(save.error))}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary btn--small" disabled={save.isPending}>
          {t("fleet.confirm")}
        </button>
        <button type="button" className="btn btn--ghost btn--small" onClick={onDone}>
          {t("inventory.cancel")}
        </button>
      </div>
    </form>
  );
}

/** «الكلفة 1 240,500 د (إصلاح عطب)» for a stay that has one, else null. */
export function costLine(e: VehicleEvent, t: (k: string, o?: Record<string, unknown>) => string, num: (n: number) => string): string | null {
  if (e.kind !== "maintenance_end" || (e.cost_parts == null && e.cost_labour == null && e.cost_external == null)) return null;
  const total = money(e.cost_parts) + money(e.cost_labour) + money(e.cost_external);
  return t("fleet.cost.line", { total: num(total), kind: e.maint_kind ? t(`fleet.cost.kinds.${e.maint_kind}`) : "—" });
}

// ---------------------------------------------------------------- the monthly report

export function FleetReportView({ gouvernorat }: { gouvernorat: number | null }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const monthId = useId();
  const [month, setMonth] = useState(thisMonth());
  const q = useQuery({
    queryKey: fleetKeys.report(month, gouvernorat),
    queryFn: ({ signal }) => api.fleetReport({ month, gouvernorat }, signal),
  });
  const r = q.data;
  const name = (row: FleetReportRow) => (row.gouvernorat_code === 0 ? t("fleet.report.total") : lang === "ar" ? row.name_ar : row.name_fr);
  const dinars = (v: string | null) => (v === null ? "—" : t("fleet.report.dinars", { n: fmt.number(Number(v)) }));
  const headline = r ? (r.total ?? r.rows[0] ?? null) : null;
  return (
    <>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={monthId}>{t("fleet.report.month")}</label>
          <input id={monthId} type="month" dir="ltr" max={thisMonth()} value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} />
        </div>
        {r && r.rows.length > 0 && (
          <button type="button" className="btn btn--ghost" onClick={() => exportReport(r, name, t)}>
            {t("fleet.report.csv")}
          </button>
        )}
      </div>
      {q.isPending && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {r && <p className="muted">{t("fleet.report.intro", { red: r.red_below, amber: r.amber_below })}</p>}
      {r && r.rows.length === 0 && <p className="card ops-empty">{t("fleet.report.none")}</p>}
      {r && headline && (
        <>
          <dl className="kpis">
            <div className="kpi card">
              <dt className="kpi__label">{t("fleet.report.readiness")}</dt>
              <dd className="kpi__value">
                <span className={`pill tone-${readinessTone(headline.readiness_pct, r)}`}>
                  {headline.readiness_pct === null ? "—" : fmt.percent(headline.readiness_pct / 100)}
                </span>
              </dd>
              <dd className="muted">{t("fleet.report.downDays")}: {fmt.number(headline.down_days)}</dd>
            </div>
            <div className="kpi card">
              <dt className="kpi__label">{t("fleet.report.cost")}</dt>
              <dd className="kpi__value">{dinars(headline.cost_total)}</dd>
              <dd className="muted">
                {t("fleet.report.split", {
                  parts: fmt.number(Number(headline.cost_parts)),
                  labour: fmt.number(Number(headline.cost_labour)),
                  external: fmt.number(Number(headline.cost_external)),
                })}
              </dd>
            </div>
            <div className="kpi card">
              <dt className="kpi__label">{t("fleet.report.vehicles")}</dt>
              <dd className="kpi__value">{fmt.number(headline.vehicles)}</dd>
              <dd className="muted">
                {t("fleet.report.perVehicle")}: {dinars(headline.cost_per_vehicle)}
              </dd>
            </div>
            <div className="kpi card">
              <dt className="kpi__label">{t("fleet.report.entries")}</dt>
              <dd className="kpi__value">{fmt.number(headline.workshop_entries)}</dd>
              <dd className="muted">
                {t("fleet.report.retired")}: {fmt.number(headline.retired)}
              </dd>
            </div>
          </dl>
          <section className="card" aria-labelledby="fleet-trend">
            <h2 id="fleet-trend">{t("fleet.report.trendOf", { name: name(headline), n: r.months.length })}</h2>
            <div className="fleet-report__bars" role="list">
              {headline.series.map((m) => (
                <div key={m.month} role="listitem" className={`fleet-report__bar tone-${readinessTone(m.readiness_pct, r)}`}>
                  <strong>{m.readiness_pct === null ? "—" : fmt.percent(m.readiness_pct / 100)}</strong>
                  <span aria-hidden="true" style={{ blockSize: `${((m.readiness_pct ?? 0) * 6) / 100}rem` }} />
                  <span dir="ltr">{m.month}</span>
                  <span className="muted">{dinars(m.cost_total)}</span>
                </div>
              ))}
            </div>
          </section>
          <section className="card" aria-labelledby="fleet-by-gouv">
            <h2 id="fleet-by-gouv">{t("fleet.report.gouvernorat")}</h2>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("fleet.report.gouvernorat")}</th>
                    <th scope="col">{t("fleet.report.vehicles")}</th>
                    <th scope="col">{t("fleet.report.readiness")}</th>
                    <th scope="col">{t("fleet.report.downDays")}</th>
                    <th scope="col">{t("fleet.report.entries")}</th>
                    <th scope="col">{t("fleet.report.retired")}</th>
                    <th scope="col">{t("fleet.report.cost")}</th>
                    <th scope="col">{t("fleet.report.perVehicle")}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...r.rows, ...(r.total ? [r.total] : [])].map((row) => (
                    <tr key={row.gouvernorat_code}>
                      <th scope="row">{name(row)}</th>
                      <td className="num">{fmt.number(row.vehicles)}</td>
                      <td>
                        <span className={`pill tone-${readinessTone(row.readiness_pct, r)}`}>
                          {row.readiness_pct === null ? "—" : fmt.percent(row.readiness_pct / 100)}
                        </span>
                      </td>
                      <td className="num">{fmt.number(row.down_days)}</td>
                      <td className="num">{fmt.number(row.workshop_entries)}</td>
                      <td className="num">{fmt.number(row.retired)}</td>
                      <td className="num">{dinars(row.cost_total)}</td>
                      <td className="num">{dinars(row.cost_per_vehicle)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {r.costly.length > 0 && (
            <section className="card" aria-labelledby="fleet-costly">
              <h2 id="fleet-costly">{t("fleet.report.costly")}</h2>
              <ol>
                {r.costly.map((v) => (
                  <li key={v.resource_id}>
                    <strong dir="auto">{v.label}</strong> {v.plate && <bdi dir="rtl">{v.plate}</bdi>} · {dinars(v.cost_total)} ·{" "}
                    {t("fleet.report.stays", { n: v.stays })}
                  </li>
                ))}
              </ol>
            </section>
          )}
          <p className="muted">{fmt.dateTime(r.computed_at)}</p>
        </>
      )}
    </>
  );
}

function exportReport(r: FleetReport, name: (row: FleetReportRow) => string, t: (k: string) => string) {
  const rows = [...r.rows, ...(r.total ? [r.total] : [])];
  exportCsv(
    `fleet-report-${r.month}`,
    [
      t("fleet.report.gouvernorat"),
      t("fleet.report.vehicles"),
      t("fleet.report.readiness"),
      t("fleet.report.downDays"),
      t("fleet.report.entries"),
      t("fleet.report.retired"),
      t("fleet.cost.parts"),
      t("fleet.cost.labour"),
      t("fleet.cost.external"),
      t("fleet.report.cost"),
      t("fleet.report.perVehicle"),
    ],
    rows.map((row) => [
      name(row),
      row.vehicles,
      row.readiness_pct,
      row.down_days,
      row.workshop_entries,
      row.retired,
      row.cost_parts,
      row.cost_labour,
      row.cost_external,
      row.cost_total,
      row.cost_per_vehicle,
    ]),
  );
}
