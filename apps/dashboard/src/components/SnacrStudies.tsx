// covers: SNACR studies in the Office's format (methodology note e-Himaya_Methodologie_SNACR, 2026-11-01): launch a
// study with its settings (the years chosen on the page, day and night or the whole day, the travel-time ceiling),
// the six tables SEC_GLOB, SAP, SR, LCI, SB, DIV per unit and délégation, the archive of the earlier studies, and the
// PDF and Excel exports of any of them.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { saveDownload } from "../lib/layersApi";
import { useFormat, useGouvernorats } from "../lib/hooks";
import {
  STUDY_TABLES,
  snacrKeys,
  type SnacrStudy,
  type SnacrStudySummary,
  type StudyDamages,
  type StudyFigures,
  type StudyFindings,
  type StudyPeriod,
  type StudyTable,
  type StudyTableKey,
} from "../lib/snacr";
import { BarChart } from "./BarChart";
import { SimBadge } from "./crisis/CrisisBits";
import { ErrorBox, Loading } from "./Feedback";

const LAUNCHERS = ["ops_manager", "local_committee", "central_committee"];

/** 6.91 minutes → "6:55". */
export function minutesSeconds(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const total = Math.round(v * 60);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function Figures({ f, years, periods }: { f: StudyFigures; years: number[]; periods: StudyPeriod[] }) {
  const fmt = useFormat();
  return (
    <>
      {years.flatMap((y) => {
        const per = f.counts[String(y)];
        return periods.map((p) => (
          <td key={`${y}-${p}`} className="num">
            {per === null || per === undefined ? "*" : fmt.number(per[p] ?? 0)}
          </td>
        ));
      })}
      {periods.map((p) => {
        const m = f.mean[p];
        return (
          <td key={`m-${p}`} className="num">
            {m === null || m === undefined ? "*" : fmt.number(m)}
          </td>
        );
      })}
      {periods.map((p) => (
        <td key={`t-${p}`} className="num">
          <bdi dir="ltr">{minutesSeconds(f.travel[p])}</bdi>
        </td>
      ))}
      <td className="num">{fmt.number(f.total)}</td>
    </>
  );
}

function StudyTableView({ table, years, periods }: { table: StudyTable; years: number[]; periods: StudyPeriod[] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const glob = table.key === "SEC_GLOB";
  const extra = glob ? 3 : 0;
  const head = (
    <thead>
      <tr>
        <th scope="col" rowSpan={2}>{t("snacr.study.unit")}</th>
        <th scope="col" rowSpan={2}>{t("snacr.study.delegation")}</th>
        {glob && (
          <>
            <th scope="col" rowSpan={2}>{t("snacr.study.area")}</th>
            <th scope="col" rowSpan={2}>{t("snacr.study.population")}</th>
            <th scope="col" rowSpan={2}>{t("snacr.study.density")}</th>
          </>
        )}
        {years.map((y) => (
          <th key={y} scope="colgroup" colSpan={periods.length}>{y}</th>
        ))}
        <th scope="colgroup" colSpan={periods.length}>{t("snacr.study.mean")}</th>
        <th scope="colgroup" colSpan={periods.length}>{t("snacr.study.travel")}</th>
        <th scope="col" rowSpan={2}>{t("snacr.study.total")}</th>
      </tr>
      <tr>
        {Array.from({ length: years.length + 2 }).flatMap((_, i) =>
          periods.map((p) => (
            <th key={`${i}-${p}`} scope="col">{t(`snacr.study.period.${p}`)}</th>
          )),
        )}
      </tr>
    </thead>
  );
  return (
    <>
      {table.gouvernorats.map((block) => (
        <div key={block.gouvernorat_code} className="table-wrap">
          <table className="table table--compact snacr-study">
            <caption>
              {table.key} · {t(`snacr.study.tables.${table.key}`)} · {block.gouvernorat}
            </caption>
            {head}
            <tbody>
              {block.units.flatMap((u) => [
                ...u.rows.map((r, i) => (
                  <tr key={`${u.unit}-${r.delegation}`}>
                    {i === 0 && (
                      <th scope="rowgroup" rowSpan={u.rows.length}>{u.unit}</th>
                    )}
                    <th scope="row">{r.delegation}</th>
                    {glob && (
                      <>
                        <td className="num">{r.area_km2 === null ? "—" : fmt.number(r.area_km2)}</td>
                        <td className="num">{r.population === null ? "—" : fmt.number(r.population)}</td>
                        <td className="num">{r.density === null ? "—" : fmt.number(r.density)}</td>
                      </>
                    )}
                    <Figures f={r} years={years} periods={periods} />
                  </tr>
                )),
                <tr key={`${u.unit}-sub`} className="snacr-study__sub">
                  <th scope="row" colSpan={2}>
                    {t("snacr.study.subtotal", { count: u.subtotal.delegations })}
                  </th>
                  {glob && (
                    <>
                      <td className="num">{u.subtotal.area_km2 === null ? "—" : fmt.number(u.subtotal.area_km2)}</td>
                      <td />
                      <td />
                    </>
                  )}
                  <Figures f={u.subtotal} years={years} periods={periods} />
                </tr>,
              ])}
              <tr className="snacr-study__total">
                <th scope="row" colSpan={2 + extra}>{t("snacr.study.gouvernoratTotal")}</th>
                <Figures f={block.total} years={years} periods={periods} />
              </tr>
            </tbody>
          </table>
        </div>
      ))}
      {table.gouvernorats.length > 1 && (
        <div className="table-wrap">
          <table className="table table--compact snacr-study">
            <caption>{t("snacr.study.nationalTotal")}</caption>
            {head}
            <tbody>
              <tr className="snacr-study__total">
                <th scope="row" colSpan={2 + extra}>{t("snacr.study.nationalTotal")}</th>
                <Figures f={table.total} years={years} periods={periods} />
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Quality({ study }: { study: SnacrStudy }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const q = study.quality;
  const n = (k: string) => fmt.number(typeof q[k] === "number" ? q[k] : 0);
  return (
    <p className="muted">
      {t("snacr.study.quality", {
        rows: n("rows"),
        white: n("white"),
        kept: n("travel_kept"),
        missing: n("travel_missing"),
        negative: n("travel_negative"),
        over: n("travel_over"),
        max: study.travel_max,
      })}
    </p>
  );
}

function Pct({ v, signed = false }: { v: number | null | undefined; signed?: boolean }) {
  const fmt = useFormat();
  if (v === null || v === undefined) return <>—</>;
  return <bdi dir="ltr">{signed ? `${fmt.signed(v)}%` : `${fmt.decimal(v)}%`}</bdi>;
}

/** The statistical board and the technical notes of a study (read by the API from the study's own tables). */
/** The damages joined to the study's interventions: the burnt forest (hectares) and the farm losses, per year. */
function DamageTables({ damages, years }: { damages: StudyDamages; years: number[] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const groups = (["forest", "agri"] as const).filter((k) => damages[k].length > 0);
  if (groups.length === 0) return <p className="muted">{t("snacr.board.damages.none")}</p>;
  return (
    <>
      {groups.map((k) => (
        <div key={k} className="table-wrap">
          <table className="table table--compact snacr-study">
            <caption>{t(`snacr.board.damages.${k}`)}</caption>
            <thead>
              <tr>
                <th scope="col">{t("snacr.board.damages.label")}</th>
                <th scope="col">{t("snacr.board.damages.unit")}</th>
                {years.map((y) => (
                  <th key={y} scope="col">{y}</th>
                ))}
                <th scope="col">{t("snacr.study.total")}</th>
                <th scope="col">{t("snacr.board.damages.outings")}</th>
              </tr>
            </thead>
            <tbody>
              {damages[k].map((l) => (
                <tr key={`${l.label}-${l.unit}`}>
                  <th scope="row">{l.label}</th>
                  <td>{t(`record.damages.units.${l.unit}`)}</td>
                  {years.map((y) => (
                    <td key={y} className="num">
                      {fmt.number(l.per_year[String(y)] ?? 0)}
                    </td>
                  ))}
                  <td className="num">{fmt.number(l.total)}</td>
                  <td className="num">{fmt.number(l.outings)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </>
  );
}

export function StudyBoard({ findings, years }: { findings: StudyFindings; years: number[] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const [all, setAll] = useState(false);
  const glob = findings.classes.find((c) => c.key === "SEC_GLOB");
  if (!glob) return null;
  const night = glob.night_pct !== null;
  const travelValues = Object.values(glob.travel).filter((v): v is number => typeof v === "number");
  const travel = travelValues.length ? travelValues.reduce((a, b) => a + b, 0) / travelValues.length : null;
  const shown = all ? findings.delegations : findings.delegations.slice(0, 10);
  return (
    <section className="snacr-board" aria-label={t("snacr.board.title")}>
      <h3>{t("snacr.board.title")}</h3>
      <dl className="kpis">
        <div className="kpi kpi--analysis">
          <dt className="kpi__label">{t("snacr.board.total", { from: years[0], to: years[years.length - 1] })}</dt>
          <dd className="kpi__value">{fmt.number(glob.total)}</dd>
        </div>
        <div className="kpi">
          <dt className="kpi__label">{t("snacr.board.yearly")}</dt>
          <dd className="kpi__value">{fmt.number(Math.round(glob.total / Math.max(years.length, 1)))}</dd>
        </div>
        {glob.change_pct !== null && (
          <div className={`kpi ${glob.change_pct > 0 ? "kpi--up" : "kpi--down"}`}>
            <dt className="kpi__label">{t("snacr.board.change", { from: years[0], to: years[years.length - 1] })}</dt>
            <dd className="kpi__value">
              <Pct v={glob.change_pct} signed />
            </dd>
          </div>
        )}
        {night && (
          <div className="kpi">
            <dt className="kpi__label">{t("snacr.board.night")}</dt>
            <dd className="kpi__value">
              <Pct v={glob.night_pct} />
            </dd>
          </div>
        )}
        <div className="kpi">
          <dt className="kpi__label">{t("snacr.board.travel")}</dt>
          <dd className="kpi__value">
            <bdi dir="ltr">{minutesSeconds(travel)}</bdi>
          </dd>
        </div>
      </dl>
      <div className="charts">
        <BarChart
          caption={t("snacr.board.byYear")}
          emptyText={t("snacr.noData")}
          bars={years.map((y) => ({ key: String(y), label: String(y), value: glob.per_year[String(y)] ?? 0 }))}
        />
        <BarChart
          caption={t("snacr.board.byClass")}
          emptyText={t("snacr.noData")}
          bars={findings.classes
            .filter((c) => c.key !== "SEC_GLOB")
            .map((c) => ({ key: c.key, label: `${c.key} · ${t(`snacr.study.tables.${c.key}`)}`, value: c.total }))}
        />
      </div>
      <h4>{t("snacr.board.notes")}</h4>
      <ul className="snacr-notes" lang="ar" dir="rtl">
        {findings.notes.map((n, i) => (
          <li key={i} className={`snacr-notes__item snacr-notes__item--${n.tone}`}>
            <span className="visually-hidden">{t(`snacr.board.tone.${n.tone}`)}: </span>
            {n.text_ar}
          </li>
        ))}
      </ul>
      <div className="table-wrap">
        <table className="table table--compact snacr-study">
          <caption>{t("snacr.board.classes")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("snacr.board.class")}</th>
              {years.map((y) => (
                <th key={y} scope="col">{y}</th>
              ))}
              <th scope="col">{t("snacr.study.total")}</th>
              <th scope="col">{t("snacr.board.share")}</th>
              <th scope="col">{t("snacr.board.evolution")}</th>
              {night && <th scope="col">{t("snacr.board.night")}</th>}
            </tr>
          </thead>
          <tbody>
            {findings.classes.map((c) => (
              <tr key={c.key} className={c.key === "SEC_GLOB" ? "snacr-study__total" : undefined}>
                <th scope="row">
                  {c.key} · {t(`snacr.study.tables.${c.key}`)}
                </th>
                {years.map((y) => (
                  <td key={y} className="num">
                    {fmt.number(c.per_year[String(y)] ?? 0)}
                  </td>
                ))}
                <td className="num">{fmt.number(c.total)}</td>
                <td className="num">
                  <Pct v={c.share_pct} />
                </td>
                <td className={`num ${c.change_pct === null ? "" : c.change_pct > 0 ? "trend--up" : "trend--down"}`}>
                  <Pct v={c.change_pct} signed />
                </td>
                {night && (
                  <td className="num">
                    <Pct v={c.night_pct} />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {findings.damages && (
        <>
          <h4>{t("snacr.board.damages.title")}</h4>
          <DamageTables damages={findings.damages} years={years} />
        </>
      )}
      <div className="table-wrap">
        <table className="table table--compact snacr-study">
          <caption>{t("snacr.board.delegations")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("snacr.study.delegation")}</th>
              <th scope="col">{t("snacr.study.unit")}</th>
              {years.map((y) => (
                <th key={y} scope="col">{y}</th>
              ))}
              <th scope="col">{t("snacr.study.mean")}</th>
              <th scope="col">{t("snacr.board.rate")}</th>
              <th scope="col">{t("snacr.board.evolution")}</th>
              <th scope="col">{t("snacr.board.travel")}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((d) => (
              <tr key={`${d.gouvernorat}-${d.delegation}`}>
                <th scope="row">{d.delegation}</th>
                <td>{[...new Set(d.units)].join("، ")}</td>
                {years.map((y) => (
                  <td key={y} className="num">
                    {d.per_year[String(y)] === null ? "*" : fmt.number(d.per_year[String(y)] ?? 0)}
                  </td>
                ))}
                <td className="num">{fmt.decimal(d.mean)}</td>
                <td className="num">{d.rate_per_1000 === null ? "—" : fmt.decimal(d.rate_per_1000)}</td>
                <td className={`num ${d.change_pct === null ? "" : d.change_pct > 0 ? "trend--up" : "trend--down"}`}>
                  <Pct v={d.change_pct} signed />
                </td>
                <td className="num">
                  <bdi dir="ltr">{minutesSeconds(d.travel)}</bdi>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {findings.delegations.length > 10 && (
        <button type="button" className="btn btn--small" onClick={() => setAll((v) => !v)}>
          {all ? t("snacr.board.fewer") : t("snacr.board.all", { count: findings.delegations.length })}
        </button>
      )}
    </section>
  );
}

export function StudiesTab({ gouvernorat, years }: { gouvernorat: number | null; years: readonly number[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const fmt = useFormat();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const roles = user?.identity.roles ?? [];
  const scope = user?.identity.national ? gouvernorat : (user?.identity.gouvernoratCode ?? null);
  const canLaunch = roles.some((r) => LAUNCHERS.includes(r));
  const [split, setSplit] = useState(true);
  const [travelMax, setTravelMax] = useState(60);
  const [selected, setSelected] = useState<string | null>(null);
  const [table, setTable] = useState<StudyTableKey>("SEC_GLOB");
  const list = useQuery({
    queryKey: snacrKeys.studies(scope),
    queryFn: ({ signal }) => api.snacrStudies(scope, signal),
  });
  const shownId = selected ?? list.data?.[0]?.id ?? null;
  const study = useQuery({
    queryKey: snacrKeys.study(shownId ?? ""),
    queryFn: ({ signal }) => api.snacrStudy(shownId ?? "", signal),
    enabled: shownId !== null,
  });
  const launch = useMutation({
    mutationFn: () => api.launchSnacrStudy({ gouvernorat_code: scope, years, split, travel_max: travelMax }),
    onSuccess: (s) => {
      setSelected(s.id);
      void qc.invalidateQueries({ queryKey: snacrKeys.all });
    },
  });
  const exporter = useMutation({
    mutationFn: ({ s, format }: { s: SnacrStudySummary; format: "pdf" | "xlsx" }) => api.snacrStudyExport(s, format),
    onSuccess: saveDownload,
  });
  const error = launch.error ?? exporter.error;
  const scopeName = scope === null ? t("snacr.plan.national") : gouvernorats.nameOf(scope);
  const shown = study.data;
  const current = shown?.tables.tables.find((x) => x.key === table);
  return (
    <>
      <p className="muted">{t("snacr.study.intro")}</p>
      {canLaunch && (
        <form
          className="filters__row card"
          onSubmit={(e) => {
            e.preventDefault();
            launch.mutate();
          }}
        >
          <fieldset className="segmented">
            <legend>{t("snacr.study.split")}</legend>
            <label className="segmented__item">
              <input type="radio" name={`${id}-split`} checked={split} onChange={() => setSplit(true)} />
              <span>{t("snacr.study.splitTwo")}</span>
            </label>
            <label className="segmented__item">
              <input type="radio" name={`${id}-split`} checked={!split} onChange={() => setSplit(false)} />
              <span>{t("snacr.study.splitDay")}</span>
            </label>
          </fieldset>
          <div className="field">
            <label htmlFor={`${id}-max`}>{t("snacr.study.travelMax")}</label>
            <input
              id={`${id}-max`}
              type="number"
              min={5}
              max={600}
              value={travelMax}
              onChange={(e) => setTravelMax(Number(e.target.value) || 60)}
            />
          </div>
          <button type="submit" className="btn btn--primary" disabled={launch.isPending || years.length === 0}>
            {t("snacr.study.launch", { scope: scopeName, years: years.join("، ") })}
          </button>
        </form>
      )}
      {error && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(error))}
        </p>
      )}
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {list.data && list.data.length === 0 && <p className="card ops-empty">{t("snacr.study.none")}</p>}
      {list.data && list.data.length > 0 && (
        <div className="table-wrap">
          <table className="table table--compact">
            <caption>{t("snacr.study.list", { scope: scopeName })}</caption>
            <thead>
              <tr>
                <th scope="col">{t("snacr.study.number")}</th>
                <th scope="col">{t("snacr.plan.status")}</th>
                <th scope="col">{t("snacr.plan.years")}</th>
                <th scope="col">{t("snacr.study.split")}</th>
                <th scope="col">{t("snacr.study.launched")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("snacr.special.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((s) => (
                <tr key={s.id} aria-current={s.id === shownId ? "true" : undefined}>
                  <th scope="row">{s.number}</th>
                  <td>
                    {t(`snacr.study.status.${s.status}`)} {s.simulated && <SimBadge />}
                  </td>
                  <td>{s.years.join("، ")}</td>
                  <td>{s.split ? t("snacr.study.splitTwo") : t("snacr.study.splitDay")}</td>
                  <td className="muted">
                    {s.created_by_name ?? "—"} · {fmt.dateTime(s.created_at)}
                  </td>
                  <td className="actions">
                    <button type="button" className="btn btn--small" onClick={() => setSelected(s.id)}>
                      {t("snacr.study.show")}
                    </button>
                    <button
                      type="button"
                      className="btn btn--small"
                      disabled={exporter.isPending}
                      onClick={() => exporter.mutate({ s, format: "pdf" })}
                    >
                      PDF
                    </button>
                    <button
                      type="button"
                      className="btn btn--small"
                      disabled={exporter.isPending}
                      onClick={() => exporter.mutate({ s, format: "xlsx" })}
                    >
                      Excel
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {study.isPending && shownId !== null && <Loading />}
      {study.isError && <ErrorBox error={study.error} onRetry={() => void study.refetch()} />}
      {shown && (
        <section className="card" aria-labelledby={`${id}-st`}>
          <h2 id={`${id}-st`}>
            {t("snacr.study.title", { number: shown.number, scope: scopeName })} {shown.simulated && <SimBadge />}
          </h2>
          <Quality study={shown} />
          <StudyBoard findings={shown.findings} years={shown.tables.years} />
          <h3>{t("snacr.board.tables")}</h3>
          <fieldset className="segmented">
            <legend>{t("snacr.study.table")}</legend>
            {STUDY_TABLES.map((k) => (
              <label key={k} className="segmented__item">
                <input type="radio" name={`${id}-table`} checked={table === k} onChange={() => setTable(k)} />
                <span>
                  {k} · {t(`snacr.study.tables.${k}`)}
                </span>
              </label>
            ))}
          </fieldset>
          {current && <StudyTableView table={current} years={shown.tables.years} periods={shown.tables.periods} />}
          <p className="muted">{t("snacr.study.legend")}</p>
        </section>
      )}
    </>
  );
}
