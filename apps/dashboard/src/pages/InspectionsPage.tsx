// covers: phase I2 (docs/phase-i/design-i.md): the general inspectorate's page: the dashboard and the state of every
// place, the mission orders (a unit is named by its gouvernorat, kind and name; or an operations room) and their PDF,
// the reports and what each room reads of the rooms' reports, the inspectors' app accounts, the calculation model,
// the order notes and the disclosure policy. Every tab prints and exports its table.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useDebounced, useFormat, useGouvernorats } from "../lib/hooks";
import {
  AUDIENCES,
  INSPECTOR_STATES,
  UNIT_KINDS,
  exportCsv,
  inspectionKeys,
  verdictTone,
  type Audience,
  type Inspector,
  type InspectorStatus,
  type Kind,
  type Mission,
  type Policy,
  type ProfileConfig,
  type RecordFilters,
  type RoomDisclosure,
  type RoomKind,
  type SiteInput,
  type Target,
  type UnitKind,
} from "../lib/inspectionsApi";

export type InspectionsTab = "overview" | "missions" | "records" | "accounts" | "settings";
const TABS: readonly [InspectionsTab, string][] = [
  ["overview", "/inspections"],
  ["missions", "/inspections/missions"],
  ["records", "/inspections/records"],
  ["accounts", "/inspections/accounts"],
  ["settings", "/inspections/settings"],
];
const MIN_REASON = 3;

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function shiftDays(day: string, days: number): string {
  const [y = 1970, m = 1, d = 1] = day.split("-").map(Number);
  const date = new Date(y, m - 1, d + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => void qc.invalidateQueries({ queryKey: inspectionKeys.all });
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
    </div>
  );
}

function Problem({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (error === null || error === undefined) return null;
  return (
    <p className="alert alert--error" role="alert">
      {t(errorMessageKey(error))}
    </p>
  );
}

/** The export button of a tab: the table as it is shown, in CSV. */
function ExportButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  const { t } = useTranslation();
  return (
    <button type="button" className="btn btn--ghost btn--small no-print" onClick={onClick} disabled={disabled}>
      <Icon name="download" size={18} />
      {t("inspections.export")}
    </button>
  );
}

function GouvernoratSelect({
  id,
  value,
  onChange,
  any,
}: {
  id: string;
  value: number | null;
  onChange: (v: number | null) => void;
  any?: string;
}) {
  const gouvernorats = useGouvernorats();
  return (
    <select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
      <option value="">{any ?? "—"}</option>
      {gouvernorats.list.map((g) => (
        <option key={g.code} value={g.code}>
          {gouvernorats.nameOf(g.code)}
        </option>
      ))}
    </select>
  );
}

/** A verdict as a coloured chip (its level's colour in the model; neutral when unknown). */
function Verdict({ verdict, score }: { verdict: string | null; score?: number | null }) {
  const tone = verdictTone(verdict);
  if (!verdict && (score === null || score === undefined)) return <span className="muted">—</span>;
  return (
    <span className={`chip chip--insp-${tone}`}>
      {verdict ?? "—"}
      {score !== null && score !== undefined && <strong dir="ltr"> {score}%</strong>}
    </span>
  );
}

export function InspectionsPage({ tab }: { tab: InspectionsTab }) {
  const { t } = useTranslation();
  return (
    <div className="page inspections-page">
      <div className="page__head">
        <PageTitle print icon="verified" tone="navy">
          {t("inspections.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("inspections.intro")}</p>
      <nav className="tabs no-print" aria-label={t("inspections.tabs.label")}>
        {TABS.map(([key, to]) => (
          <NavLink
            key={key}
            to={to}
            end
            className={({ isActive }) => `tabs__tab${isActive ? " tabs__tab--active" : ""}`}
          >
            {t(`inspections.tabs.${key}`)}
          </NavLink>
        ))}
      </nav>
      {tab === "overview" && <OverviewTab />}
      {tab === "missions" && <MissionsTab />}
      {tab === "records" && <RecordsTab />}
      {tab === "accounts" && <AccountsTab />}
      {tab === "settings" && <SettingsTab />}
    </div>
  );
}

// ---------------------------------------------------------------- overview

function OverviewTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const gouvId = useId();
  const [gouvernorat, setGouvernorat] = useState<number | null>(null);
  const board = useQuery({ queryKey: inspectionKeys.dashboard, queryFn: ({ signal }) => api.inspectionDashboard(signal) });
  const places = useQuery({
    queryKey: inspectionKeys.places(gouvernorat),
    queryFn: ({ signal }) => api.inspectionPlaces(gouvernorat, signal),
  });
  const rows = places.data ?? [];
  const kindOf = (p: (typeof rows)[number]) =>
    p.target === "room" ? t(`inspections.room.${p.room ?? "central"}`) : t(`inspections.unitKind.${p.unit_kind ?? "other"}`);
  const exportPlaces = () =>
    exportCsv(
      "inspections-places",
      [
        t("inspections.columns.place"),
        t("inspections.columns.kind"),
        t("filters.gouvernorat"),
        t("inspections.columns.lastOn"),
        t("inspections.columns.verdict"),
        t("inspections.columns.score"),
        t("inspections.columns.nextOn"),
      ],
      rows.map((p) => [
        p.name,
        kindOf(p),
        gouvernorats.nameOf(p.gouvernorat_code) ?? "",
        p.last_on ? fmt.date(p.last_on) : "",
        p.last_verdict,
        p.last_score,
        p.next_on ? fmt.date(p.next_on) : "",
      ]),
    );
  return (
    <>
      {board.isPending && <Loading />}
      {board.isError && <ErrorBox error={board.error} onRetry={() => void board.refetch()} />}
      {board.data && (
        <ul className="kpis" aria-label={t("inspections.kpis.label")}>
          <li className="card kpi kpi--insp">
            <span className="kpi__label">{t("inspections.kpis.month")}</span>
            <p className="kpi__value">{fmt.number(board.data.month_missions)}</p>
          </li>
          <li className="card kpi kpi--insp">
            <span className="kpi__label">{t("inspections.kpis.done")}</span>
            <p className="kpi__value">{fmt.number(board.data.month_done)}</p>
          </li>
          <li className="card kpi kpi--insp">
            <span className="kpi__label">{t("inspections.kpis.planned")}</span>
            <p className="kpi__value">{fmt.number(board.data.month_planned)}</p>
          </li>
          <li className="card kpi kpi--insp">
            <span className="kpi__label">{t("inspections.kpis.average")}</span>
            <p className="kpi__value" dir="ltr">
              {board.data.average_score === null ? "—" : `${board.data.average_score}%`}
            </p>
          </li>
          <li className="card kpi kpi--insp">
            <span className="kpi__label">{t("inspections.kpis.roomsWithoutPlan")}</span>
            <p className="kpi__value">{fmt.number(board.data.rooms_without_plan)}</p>
          </li>
        </ul>
      )}
      {board.data && Object.keys(board.data.levels).length > 0 && (
        <section className="card" aria-labelledby={`${gouvId}-levels`}>
          <h2 id={`${gouvId}-levels`}>{t("inspections.levels")}</h2>
          <ul className="inspections-levels">
            {Object.entries(board.data.levels).map(([name, count]) => (
              <li key={name}>
                <Verdict verdict={name || null} /> <strong>{fmt.number(count)}</strong>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="card" aria-labelledby={`${gouvId}-places`}>
        <div className="inspections-head">
          <h2 id={`${gouvId}-places`}>{t("inspections.places")}</h2>
          <ExportButton onClick={exportPlaces} disabled={rows.length === 0} />
        </div>
        <div className="filters__row no-print">
          <Field id={gouvId} label={t("filters.gouvernorat")}>
            <GouvernoratSelect id={gouvId} value={gouvernorat} onChange={setGouvernorat} any={t("filters.allGouvernorats")} />
          </Field>
        </div>
        {places.isPending && <Loading />}
        {places.isError && <ErrorBox error={places.error} onRetry={() => void places.refetch()} />}
        {rows.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("inspections.columns.place")}</th>
                  <th scope="col">{t("inspections.columns.kind")}</th>
                  <th scope="col">{t("filters.gouvernorat")}</th>
                  <th scope="col">{t("inspections.columns.lastOn")}</th>
                  <th scope="col">{t("inspections.columns.verdict")}</th>
                  <th scope="col">{t("inspections.columns.nextOn")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={`${p.target}:${p.room}:${p.gouvernorat_code}:${p.unit_kind}:${p.unit_name}`}>
                    <td dir="auto">
                      {p.last_inspection_id ? (
                        <Link to={`/inspections/records/${encodeURIComponent(p.last_inspection_id)}`}>{p.name}</Link>
                      ) : (
                        p.name
                      )}
                    </td>
                    <td>{kindOf(p)}</td>
                    <td>{gouvernorats.nameOf(p.gouvernorat_code) ?? "—"}</td>
                    <td>{p.last_on ? fmt.date(p.last_on) : <span className="muted">{t("inspections.never")}</span>}</td>
                    <td>
                      <Verdict verdict={p.last_verdict} score={p.last_score} />
                    </td>
                    <td>{p.next_on ? fmt.date(p.next_on) : <span className="muted">{t("inspections.notPlanned")}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

// ---------------------------------------------------------------- missions

function MissionsTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const ids = { from: useId(), to: useId() };
  const [from, setFrom] = useState(() => shiftDays(today(), -30));
  const [to, setTo] = useState(() => shiftDays(today(), 60));
  const [planning, setPlanning] = useState(false);
  const missions = useQuery({
    queryKey: inspectionKeys.missions(from, to),
    queryFn: ({ signal }) => api.inspectionMissions(from, to, signal),
  });
  const rows = missions.data ?? [];
  const exportMissions = () =>
    exportCsv(
      "inspections-missions",
      [
        t("inspections.columns.ref"),
        t("inspections.columns.date"),
        t("inspections.columns.time"),
        t("inspections.columns.missionKind"),
        t("inspections.columns.inspector"),
        t("inspections.columns.places"),
        t("inspections.columns.status"),
      ],
      rows.map((m) => [
        m.ref,
        fmt.date(m.on_date),
        m.at_time.slice(0, 5),
        t(`inspections.kind.${m.kind}`),
        m.inspector_name,
        m.sites.map((s) => s.name).join(" · "),
        t(`inspections.missionState.${m.status}`),
      ]),
    );
  return (
    <>
      <section className="filters card no-print" aria-label={t("inspections.filters")}>
        <div className="filters__row">
          <Field id={ids.from} label={t("inspections.from")}>
            <input id={ids.from} type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field id={ids.to} label={t("inspections.to")}>
            <input id={ids.to} type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </Field>
        </div>
        <div className="actions">
          {!planning && (
            <button type="button" className="btn btn--primary" onClick={() => setPlanning(true)}>
              {t("inspections.plan")}
            </button>
          )}
          <ExportButton onClick={exportMissions} disabled={rows.length === 0} />
        </div>
      </section>
      {planning && <MissionForm onDone={() => setPlanning(false)} />}
      {missions.isPending && <Loading />}
      {missions.isError && <ErrorBox error={missions.error} onRetry={() => void missions.refetch()} />}
      {missions.isSuccess && rows.length === 0 && <p className="card empty">{t("inspections.noMissions")}</p>}
      {rows.map((m) => (
        <MissionCard key={m.id} mission={m} />
      ))}
    </>
  );
}

function MissionCard({ mission }: { mission: Mission }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const invalidate = useInvalidate();
  const reasonId = useId();
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState("");
  const pdf = useMutation({ mutationFn: () => api.downloadMissionOrder(mission) });
  const cancel = useMutation({
    mutationFn: () => api.cancelInspectionMission(mission.id, reason.trim()),
    onSuccess: () => {
      setCancelling(false);
      invalidate();
    },
  });
  return (
    <article className="card inspections-mission" aria-label={mission.ref}>
      <div className="inspections-head">
        <h3>
          <span dir="ltr">{mission.ref}</span> · {fmt.date(mission.on_date)}{" "}
          <span dir="ltr">{mission.at_time.slice(0, 5)}</span>
        </h3>
        <span className={`chip chip--insp-mission-${mission.status}`}>{t(`inspections.missionState.${mission.status}`)}</span>
      </div>
      <p>
        {t(`inspections.kind.${mission.kind}`)} · {t("inspections.columns.inspector")}: <strong>{mission.inspector_name}</strong>
        {mission.published && <> · {t("inspections.published")}</>}
      </p>
      <ol className="inspections-sites">
        {mission.sites.map((s) => (
          <li key={s.id}>
            <strong dir="auto">{s.name}</strong>
            {s.gouvernorat_code !== null && s.target === "unit" && <> · {gouvernorats.nameOf(s.gouvernorat_code)}</>}
            {s.sections.length > 0 && <span className="muted"> · {s.sections.join("، ")}</span>}
            {s.inspection_id && (
              <>
                {" "}
                <Link to={`/inspections/records/${encodeURIComponent(s.inspection_id)}`}>
                  {t(`inspections.reportState.${s.inspection_status ?? "in_progress"}`)}
                </Link>
              </>
            )}
            {s.arrived_at && (
              <span className="muted">
                {" · "}
                {t("inspections.arrivedAt", { time: fmt.dateTime(s.arrived_at) })}
                {s.arrived_offline && <> ({t("inspections.offlineMark")})</>}
              </span>
            )}
            {s.left_at && (
              <span className="muted">
                {" · "}
                {t("inspections.leftAt", { time: fmt.dateTime(s.left_at) })}
                {s.left_offline && <> ({t("inspections.offlineMark")})</>}
              </span>
            )}
          </li>
        ))}
      </ol>
      {mission.cancel_reason && (
        <p className="muted">
          {t("inspections.cancelReason")}: {mission.cancel_reason}
        </p>
      )}
      <div className="actions no-print">
        <button type="button" className="btn btn--small" onClick={() => pdf.mutate()} disabled={pdf.isPending}>
          <Icon name="pictureAsPdf" size={18} />
          {t("inspections.orderPdf")}
        </button>
        {mission.status === "planned" && !cancelling && (
          <button type="button" className="btn btn--small btn--danger" onClick={() => setCancelling(true)}>
            {t("inspections.cancelMission")}
          </button>
        )}
      </div>
      <Problem error={pdf.error} />
      {cancelling && (
        <form
          className="inspections-inline no-print"
          onSubmit={(e) => {
            e.preventDefault();
            cancel.mutate();
          }}
        >
          <Field id={reasonId} label={t("inspections.cancelReason")}>
            <input id={reasonId} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
          </Field>
          <div className="actions">
            <button type="submit" className="btn btn--danger" disabled={reason.trim().length < MIN_REASON || cancel.isPending}>
              {t("inspections.confirmCancel")}
            </button>
            <button type="button" className="btn" onClick={() => setCancelling(false)}>
              {t("common.cancel")}
            </button>
          </div>
          <Problem error={cancel.error} />
        </form>
      )}
    </article>
  );
}

interface SiteDraft {
  target: Target;
  room: RoomKind;
  gouvernorat: number | null;
  unitKind: UnitKind;
  unitName: string;
  sections: string[];
}

const emptySite = (): SiteDraft => ({
  target: "unit",
  room: "regional",
  gouvernorat: null,
  unitKind: "centre",
  unitName: "",
  sections: [],
});

function siteInput(s: SiteDraft): SiteInput {
  if (s.target === "room") {
    return { target: "room", room: s.room, gouvernorat_code: s.room === "central" ? null : s.gouvernorat, sections: s.sections };
  }
  return {
    target: "unit",
    gouvernorat_code: s.gouvernorat,
    unit_kind: s.unitKind,
    unit_name: s.unitName.trim(),
    sections: s.sections,
  };
}

function siteReady(s: SiteDraft): boolean {
  if (s.target === "room") return s.room === "central" || s.gouvernorat !== null;
  return s.gouvernorat !== null && s.unitName.trim().length >= 2;
}

function MissionForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const invalidate = useInvalidate();
  const id = useId();
  const [onDate, setOnDate] = useState(today());
  const [atTime, setAtTime] = useState("09:00");
  const [kind, setKind] = useState<Kind>("periodic");
  const [inspector, setInspector] = useState("");
  const [publish, setPublish] = useState(false);
  const [sites, setSites] = useState<SiteDraft[]>([emptySite()]);
  const inspectors = useQuery({
    queryKey: inspectionKeys.inspectors("active"),
    queryFn: ({ signal }) => api.inspectors("active", signal),
  });
  const profile = useQuery({ queryKey: inspectionKeys.profile, queryFn: ({ signal }) => api.inspectionProfile(signal) });
  const sections = profile.data?.config.sections ?? [];
  const save = useMutation({
    mutationFn: () =>
      api.createInspectionMission({
        on_date: onDate,
        at_time: atTime,
        kind,
        inspector_id: inspector,
        sites: sites.map(siteInput),
        publish,
      }),
    onSuccess: () => {
      invalidate();
      onDone();
    },
  });
  const set = (i: number, patch: Partial<SiteDraft>) => setSites((all) => all.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const ready = inspector !== "" && onDate !== "" && sites.length > 0 && sites.every(siteReady);
  return (
    <form
      noValidate
      className="card inspections-form"
      aria-labelledby={`${id}-title`}
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) save.mutate();
      }}
    >
      <h3 id={`${id}-title`}>{t("inspections.newMission")}</h3>
      <div className="form-grid">
        <Field id={`${id}-date`} label={t("inspections.columns.date")}>
          <input id={`${id}-date`} type="date" min={today()} value={onDate} onChange={(e) => setOnDate(e.target.value)} />
        </Field>
        <Field id={`${id}-time`} label={t("inspections.columns.time")}>
          <input id={`${id}-time`} type="time" value={atTime} onChange={(e) => setAtTime(e.target.value)} />
        </Field>
        <Field id={`${id}-kind`} label={t("inspections.columns.missionKind")}>
          <select id={`${id}-kind`} value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
            <option value="periodic">{t("inspections.kind.periodic")}</option>
            <option value="surprise">{t("inspections.kind.surprise")}</option>
          </select>
        </Field>
        <Field id={`${id}-inspector`} label={t("inspections.columns.inspector")}>
          <select id={`${id}-inspector`} value={inspector} onChange={(e) => setInspector(e.target.value)}>
            <option value="">{t("inspections.pickInspector")}</option>
            {(inspectors.data ?? []).map((i) => (
              <option key={i.id} value={i.id}>
                {i.name}
                {i.kind === "external" ? ` (${t("inspections.external")})` : ""}
              </option>
            ))}
          </select>
        </Field>
      </div>
      {inspectors.isSuccess && inspectors.data.length === 0 && <p className="alert">{t("inspections.noActiveInspector")}</p>}
      <fieldset className="inspections-sitesform">
        <legend>{t("inspections.columns.places")}</legend>
        {sites.map((s, i) => (
          <div key={i} className="inspections-site card">
            <div className="form-grid">
              <Field id={`${id}-target-${i}`} label={t("inspections.target")}>
                <select
                  id={`${id}-target-${i}`}
                  value={s.target}
                  onChange={(e) => set(i, { target: e.target.value as Target })}
                >
                  <option value="unit">{t("inspections.targetKind.unit")}</option>
                  <option value="room">{t("inspections.targetKind.room")}</option>
                </select>
              </Field>
              {s.target === "room" && (
                <Field id={`${id}-room-${i}`} label={t("inspections.roomLabel")}>
                  <select id={`${id}-room-${i}`} value={s.room} onChange={(e) => set(i, { room: e.target.value as RoomKind })}>
                    <option value="central">{t("inspections.room.central")}</option>
                    <option value="regional">{t("inspections.room.regional")}</option>
                  </select>
                </Field>
              )}
              {(s.target === "unit" || s.room === "regional") && (
                <Field id={`${id}-gouv-${i}`} label={t("filters.gouvernorat")}>
                  <GouvernoratSelect id={`${id}-gouv-${i}`} value={s.gouvernorat} onChange={(v) => set(i, { gouvernorat: v })} />
                </Field>
              )}
              {s.target === "unit" && (
                <>
                  <Field id={`${id}-ukind-${i}`} label={t("inspections.unitKindLabel")}>
                    <select
                      id={`${id}-ukind-${i}`}
                      value={s.unitKind}
                      onChange={(e) => set(i, { unitKind: e.target.value as UnitKind })}
                    >
                      {UNIT_KINDS.map((k) => (
                        <option key={k} value={k}>
                          {t(`inspections.unitKind.${k}`)}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field id={`${id}-uname-${i}`} label={t("inspections.unitName")}>
                    <input
                      id={`${id}-uname-${i}`}
                      dir="auto"
                      value={s.unitName}
                      maxLength={160}
                      onChange={(e) => set(i, { unitName: e.target.value })}
                    />
                  </Field>
                </>
              )}
            </div>
            {sections.length > 0 && (
              <fieldset className="inspections-sections">
                <legend>{t("inspections.sections")}</legend>
                {sections.map((sec) => (
                  <label key={sec} className="checkbox">
                    <input
                      type="checkbox"
                      checked={s.sections.includes(sec)}
                      onChange={(e) =>
                        set(i, { sections: e.target.checked ? [...s.sections, sec] : s.sections.filter((x) => x !== sec) })
                      }
                    />{" "}
                    {sec}
                  </label>
                ))}
                <p className="muted">{t("inspections.sectionsHint")}</p>
              </fieldset>
            )}
            {sites.length > 1 && (
              <button
                type="button"
                className="btn btn--ghost btn--small"
                onClick={() => setSites((all) => all.filter((_, j) => j !== i))}
              >
                {t("inspections.removeSite")}
              </button>
            )}
          </div>
        ))}
        {sites.length < 10 && (
          <button type="button" className="btn btn--small" onClick={() => setSites((all) => [...all, emptySite()])}>
            {t("inspections.addSite")}
          </button>
        )}
      </fieldset>
      <label className="checkbox">
        <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} /> {t("inspections.publish")}
      </label>
      <Problem error={save.error} />
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={!ready || save.isPending}>
          {t("inspections.saveMission")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------- records

function RecordsTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const ids = { g: useId(), target: useId(), ukind: useId(), q: useId(), from: useId(), to: useId() };
  const [gouvernorat, setGouvernorat] = useState<number | null>(null);
  const [target, setTarget] = useState<Target | "">("");
  const [unitKind, setUnitKind] = useState<UnitKind | "">("");
  const [text, setText] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const search = useDebounced(text, 350);
  const filters: RecordFilters = useMemo(
    () => ({ gouvernorat_code: gouvernorat, target, unit_kind: unitKind, search, from_date: from, to_date: to }),
    [gouvernorat, target, unitKind, search, from, to],
  );
  const records = useQuery({
    queryKey: inspectionKeys.records(filters),
    queryFn: ({ signal }) => api.inspectionRecords(filters, signal),
  });
  const rows = records.data ?? [];
  const exportRecords = () =>
    exportCsv(
      "inspections-records",
      [
        t("inspections.columns.date"),
        t("inspections.columns.place"),
        t("filters.gouvernorat"),
        t("inspections.columns.missionKind"),
        t("inspections.columns.inspector"),
        t("inspections.columns.score"),
        t("inspections.columns.previous"),
        t("inspections.columns.verdict"),
        t("inspections.columns.receipt"),
      ],
      rows.map((r) => [
        fmt.dateTime(r.submitted_at ?? r.started_at),
        r.place,
        gouvernorats.nameOf(r.gouvernorat_code) ?? "",
        t(`inspections.kind.${r.kind}`),
        r.inspector_name,
        r.score,
        r.previous_score,
        r.verdict,
        r.receipt,
      ]),
    );
  return (
    <>
      <section className="filters card no-print" aria-label={t("inspections.filters")}>
        <div className="filters__row">
          <Field id={ids.q} label={t("inspections.search")}>
            <input id={ids.q} type="search" value={text} maxLength={80} onChange={(e) => setText(e.target.value)} />
          </Field>
          <Field id={ids.g} label={t("filters.gouvernorat")}>
            <GouvernoratSelect id={ids.g} value={gouvernorat} onChange={setGouvernorat} any={t("filters.allGouvernorats")} />
          </Field>
          <Field id={ids.target} label={t("inspections.target")}>
            <select id={ids.target} value={target} onChange={(e) => setTarget(e.target.value as Target | "")}>
              <option value="">{t("inspections.any")}</option>
              <option value="unit">{t("inspections.targetKind.unit")}</option>
              <option value="room">{t("inspections.targetKind.room")}</option>
            </select>
          </Field>
          <Field id={ids.ukind} label={t("inspections.unitKindLabel")}>
            <select id={ids.ukind} value={unitKind} onChange={(e) => setUnitKind(e.target.value as UnitKind | "")}>
              <option value="">{t("inspections.any")}</option>
              {UNIT_KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`inspections.unitKind.${k}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field id={ids.from} label={t("inspections.from")}>
            <input id={ids.from} type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field id={ids.to} label={t("inspections.to")}>
            <input id={ids.to} type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </Field>
        </div>
        <div className="actions">
          <ExportButton onClick={exportRecords} disabled={rows.length === 0} />
        </div>
      </section>
      {records.isPending && <Loading />}
      {records.isError && <ErrorBox error={records.error} onRetry={() => void records.refetch()} />}
      {records.isSuccess && rows.length === 0 && <p className="card empty">{t("inspections.noRecords")}</p>}
      {rows.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <caption className="visually-hidden">{t("inspections.tabs.records")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("inspections.columns.date")}</th>
                <th scope="col">{t("inspections.columns.place")}</th>
                <th scope="col">{t("filters.gouvernorat")}</th>
                <th scope="col">{t("inspections.columns.inspector")}</th>
                <th scope="col">{t("inspections.columns.verdict")}</th>
                <th scope="col">{t("inspections.columns.previous")}</th>
                <th scope="col">{t("inspections.columns.receipt")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{fmt.dateTime(r.submitted_at ?? r.started_at)}</td>
                  <td dir="auto">
                    <Link to={`/inspections/records/${encodeURIComponent(r.id)}`}>{r.place}</Link>
                  </td>
                  <td>{gouvernorats.nameOf(r.gouvernorat_code) ?? "—"}</td>
                  <td>{r.inspector_name}</td>
                  <td>
                    {r.status === "submitted" ? (
                      <Verdict verdict={r.verdict} score={r.score} />
                    ) : (
                      <span className="chip chip--insp-amber">{t("inspections.reportState.in_progress")}</span>
                    )}
                  </td>
                  <td dir="ltr">{r.previous_score === null ? "—" : `${r.previous_score}%`}</td>
                  <td dir="ltr">{r.receipt ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

/** One report: its answers, its recommendations and what each room reads of it. */
export function InspectionRecordPage() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const record = useQuery({ queryKey: inspectionKeys.record(id), queryFn: ({ signal }) => api.inspectionRecord(id, signal) });
  const r = record.data;
  return (
    <div className="page inspections-page">
      <div className="page__head">
        <PageTitle print icon="verified" tone="navy">
          {r ? r.place : t("inspections.record")}
        </PageTitle>
      </div>
      <p className="no-print">
        <Link to="/inspections/records">{t("inspections.back")}</Link>
      </p>
      {record.isPending && <Loading />}
      {record.isError && <ErrorBox error={record.error} onRetry={() => void record.refetch()} />}
      {r && (
        <>
          <section className="card">
            <dl className="facts inspections-facts">
              <dt>{t("inspections.columns.ref")}</dt>
              <dd dir="ltr">{r.mission_ref}</dd>
              <dt>{t("filters.gouvernorat")}</dt>
              <dd>{gouvernorats.nameOf(r.gouvernorat_code) ?? "—"}</dd>
              <dt>{t("inspections.columns.missionKind")}</dt>
              <dd>{t(`inspections.kind.${r.kind}`)}</dd>
              <dt>{t("inspections.columns.inspector")}</dt>
              <dd>{r.inspector_name}</dd>
              <dt>{t("inspections.startedAt")}</dt>
              <dd>{fmt.dateTime(r.started_at)}</dd>
              <dt>{t("inspections.signedAt")}</dt>
              <dd>{r.signed_at ? fmt.dateTime(r.signed_at) : "—"}</dd>
              <dt>{t("inspections.head")}</dt>
              <dd>{r.head_name ?? "—"}</dd>
              <dt>{t("inspections.columns.verdict")}</dt>
              <dd>
                <Verdict verdict={r.verdict} score={r.score} />
                {r.previous_score !== null && (
                  <span className="muted" dir="ltr">
                    {" "}
                    ({t("inspections.columns.previous")} {r.previous_score}%)
                  </span>
                )}
              </dd>
              <dt>{t("inspections.presence")}</dt>
              <dd dir="ltr">{r.present !== null && r.expected !== null ? `${r.present} / ${r.expected}` : "—"}</dd>
              <dt>{t("inspections.exit")}</dt>
              <dd>{r.exit_seconds !== null ? fmt.duration(r.exit_seconds) : "—"}</dd>
              <dt>{t("inspections.columns.receipt")}</dt>
              <dd dir="ltr">{r.receipt ?? "—"}</dd>
              <dt>{t("inspections.model")}</dt>
              <dd>
                {r.profile_name} (v{r.profile_version})
              </dd>
            </dl>
            {r.summary && (
              <>
                <h2>{t("inspections.summary")}</h2>
                <p dir="auto">{r.summary}</p>
              </>
            )}
          </section>
          <Answers answers={r.answers} />
          {r.target === "room" ? (
            r.status === "submitted" && <Disclosure id={r.id} disclosure={r.disclosure} recommendations={r.recommendations} />
          ) : (
            <>
              <RecommendationList recommendations={r.recommendations} />
              <p className="card muted">{t("inspections.unitNeverDisclosed")}</p>
            </>
          )}
        </>
      )}
    </div>
  );
}

function Answers({ answers }: { answers: Record<string, string> }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const profile = useQuery({ queryKey: inspectionKeys.profile, queryFn: ({ signal }) => api.inspectionProfile(signal) });
  const items = profile.data?.config.items ?? [];
  const keys = Object.keys(answers);
  if (keys.length === 0) return null;
  const textOf = (key: string) => items.find((i) => i.key === key)?.text ?? key;
  return (
    <section className="card">
      <h2>{t("inspections.answers")}</h2>
      <ul className="inspections-answers">
        {keys.map((k) => (
          <li key={k}>
            <span className={`chip chip--insp-${answers[k] === "ok" ? "green" : answers[k] === "note" ? "amber" : "red"}`}>
              {t(`inspections.answer.${answers[k]}`)}
            </span>{" "}
            {textOf(k)}
          </li>
        ))}
      </ul>
    </section>
  );
}

function RecommendationList({ recommendations }: { recommendations: { id: string; text: string; priority: string | null }[] }) {
  const { t } = useTranslation();
  if (recommendations.length === 0) return null;
  return (
    <section className="card">
      <h2>{t("inspections.recommendations")}</h2>
      <ol>
        {recommendations.map((x) => (
          <li key={x.id} dir="auto">
            {x.priority && <span className="chip">{t(`inspections.priority.${x.priority}`)}</span>} {x.text}
          </li>
        ))}
      </ol>
    </section>
  );
}

function Disclosure({
  id,
  disclosure,
  recommendations,
}: {
  id: string;
  disclosure: Partial<Record<RoomKind, RoomDisclosure>>;
  recommendations: { id: string; text: string; priority: string | null; audience: Audience; kind: string }[];
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const refresh = () => void qc.invalidateQueries({ queryKey: inspectionKeys.all });
  const change = useMutation({
    mutationFn: (body: { room: RoomKind } & Partial<RoomDisclosure>) => api.setInspectionDisclosure(id, body),
    onSuccess: refresh,
  });
  const audience = useMutation({
    mutationFn: ({ ids, value }: { ids: string[]; value: Audience }) => api.setRecommendationAudience(id, ids, value),
    onSuccess: refresh,
  });
  return (
    <section className="card">
      <h2>{t("inspections.disclosure")}</h2>
      <p className="muted">{t("inspections.disclosureHint")}</p>
      <table className="table">
        <thead>
          <tr>
            <th scope="col">{t("inspections.roomLabel")}</th>
            <th scope="col">{t("inspections.discloseInspection")}</th>
            <th scope="col">{t("inspections.columns.verdict")}</th>
            <th scope="col">{t("inspections.columns.score")}</th>
          </tr>
        </thead>
        <tbody>
          {(["central", "regional"] as const).map((room) => {
            const view = disclosure[room] ?? { inspection: false, verdict: false, score: false };
            return (
              <tr key={room}>
                <th scope="row">{t(`inspections.room.${room}`)}</th>
                {(["inspection", "verdict", "score"] as const).map((field) => (
                  <td key={field}>
                    <input
                      type="checkbox"
                      aria-label={`${t(`inspections.room.${room}`)}: ${t(`inspections.disclose.${field}`)}`}
                      checked={view[field]}
                      disabled={change.isPending}
                      onChange={(e) => change.mutate({ room, [field]: e.target.checked })}
                    />
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      <Problem error={change.error} />
      {recommendations.length > 0 && (
        <>
          <h3>{t("inspections.recommendations")}</h3>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("inspections.recommendation")}</th>
                <th scope="col">{t("inspections.audience")}</th>
              </tr>
            </thead>
            <tbody>
              {recommendations.map((x) => (
                <tr key={x.id}>
                  <td dir="auto">
                    {x.priority && <span className="chip">{t(`inspections.priority.${x.priority}`)}</span>} {x.text}
                  </td>
                  <td>
                    <select
                      aria-label={t("inspections.audience")}
                      value={x.audience}
                      disabled={audience.isPending}
                      onChange={(e) => audience.mutate({ ids: [x.id], value: e.target.value as Audience })}
                    >
                      {AUDIENCES.map((a) => (
                        <option key={a} value={a}>
                          {t(`inspections.audienceKind.${a}`)}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Problem error={audience.error} />
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- accounts

function AccountsTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const stateId = useId();
  const [state, setState] = useState<InspectorStatus | "">("");
  const inspectors = useQuery({
    queryKey: inspectionKeys.inspectors(state),
    queryFn: ({ signal }) => api.inspectors(state, signal),
  });
  const rows = inspectors.data ?? [];
  const exportAccounts = () =>
    exportCsv(
      "inspections-accounts",
      [
        t("inspections.columns.name"),
        t("inspections.columns.matricule"),
        t("inspections.columns.accountKind"),
        t("inspections.columns.contact"),
        t("inspections.columns.status"),
        t("inspections.columns.expires"),
        t("inspections.columns.lastSeen"),
      ],
      rows.map((i) => [
        i.name,
        i.matricule,
        i.kind === "external" ? `${t("inspections.external")} · ${i.organisation ?? ""}` : t("inspections.internal"),
        i.via === "sms" ? i.phone : i.email,
        t(`inspections.accountState.${i.status}`),
        i.expires_on ? fmt.date(i.expires_on) : "",
        i.last_seen_at ? fmt.dateTime(i.last_seen_at) : "",
      ]),
    );
  return (
    <>
      <p className="muted">{t("inspections.accountsIntro")}</p>
      <section className="filters card no-print" aria-label={t("inspections.filters")}>
        <div className="filters__row">
          <Field id={stateId} label={t("inspections.columns.status")}>
            <select id={stateId} value={state} onChange={(e) => setState(e.target.value as InspectorStatus | "")}>
              <option value="">{t("inspections.any")}</option>
              {INSPECTOR_STATES.map((s) => (
                <option key={s} value={s}>
                  {t(`inspections.accountState.${s}`)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="actions">
          <ExportButton onClick={exportAccounts} disabled={rows.length === 0} />
        </div>
      </section>
      {inspectors.isPending && <Loading />}
      {inspectors.isError && <ErrorBox error={inspectors.error} onRetry={() => void inspectors.refetch()} />}
      {inspectors.isSuccess && rows.length === 0 && <p className="card empty">{t("inspections.noAccounts")}</p>}
      {rows.map((i) => (
        <AccountCard key={i.id} inspector={i} />
      ))}
    </>
  );
}

function AccountCard({ inspector: i }: { inspector: Inspector }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const invalidate = useInvalidate();
  const id = useId();
  const [expires, setExpires] = useState(i.expires_on ?? "");
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const act = useMutation({
    mutationFn: (action: "activate" | "reject" | "code" | "lost" | "close") => {
      if (action === "activate") return api.activateInspector(i.id, expires || null);
      if (action === "reject") return api.rejectInspector(i.id, reason.trim());
      if (action === "code") return api.renewInspectorCode(i.id);
      if (action === "lost") return api.reportInspectorLost(i.id);
      return api.closeInspector(i.id);
    },
    onSuccess: () => {
      setRejecting(false);
      invalidate();
    },
  });
  const tone = i.status === "active" ? "green" : i.status === "pending" || i.status === "code_sent" ? "amber" : "red";
  return (
    <article className="card inspections-account" aria-labelledby={`${id}-name`}>
      <div className="inspections-head">
        <h3 id={`${id}-name`}>
          {i.name} <span className="muted" dir="ltr">({i.matricule})</span>
        </h3>
        <span className={`chip chip--insp-${tone}`}>{t(`inspections.accountState.${i.status}`)}</span>
      </div>
      <p>
        {i.kind === "external" ? `${t("inspections.external")} · ${i.organisation ?? ""}` : t("inspections.internal")}
        {" · "}
        {t(`inspections.via.${i.via}`)}: <span dir="ltr">{i.via === "sms" ? i.phone : i.email}</span>
        {i.matched_agent && <> · {t("inspections.matchedAgent")}</>}
      </p>
      <p className="muted">
        {t("inspections.requestedAt")}: {fmt.dateTime(i.requested_at)}
        {i.requested_device && <> · {i.requested_device}</>}
        {i.code_expires_at && i.status === "code_sent" && (
          <>
            {" · "}
            {t("inspections.codeUntil")}: {fmt.dateTime(i.code_expires_at)}
          </>
        )}
        {i.last_seen_at && (
          <>
            {" · "}
            {t("inspections.columns.lastSeen")}: {fmt.dateTime(i.last_seen_at)}
          </>
        )}
        {i.reject_reason && (
          <>
            {" · "}
            {t("inspections.rejectReason")}: {i.reject_reason}
          </>
        )}
      </p>
      <div className="actions no-print">
        {i.status === "pending" && (
          <>
            {i.kind === "external" && (
              <Field id={`${id}-exp`} label={t("inspections.columns.expires")}>
                <input id={`${id}-exp`} type="date" min={today()} value={expires} onChange={(e) => setExpires(e.target.value)} />
              </Field>
            )}
            <button
              type="button"
              className="btn btn--primary btn--small"
              disabled={act.isPending || (i.kind === "external" && !expires)}
              onClick={() => act.mutate("activate")}
            >
              {t("inspections.activate")}
            </button>
            {!rejecting && (
              <button type="button" className="btn btn--small" onClick={() => setRejecting(true)}>
                {t("inspections.reject")}
              </button>
            )}
          </>
        )}
        {(i.status === "code_sent" || i.status === "active" || i.status === "blocked") && (
          <button type="button" className="btn btn--small" disabled={act.isPending} onClick={() => act.mutate("code")}>
            {t("inspections.newCode")}
          </button>
        )}
        {i.status === "active" && (
          <button type="button" className="btn btn--small btn--danger" disabled={act.isPending} onClick={() => act.mutate("lost")}>
            {t("inspections.lost")}
          </button>
        )}
        {i.status !== "closed" && i.status !== "rejected" && i.status !== "pending" && (
          <button type="button" className="btn btn--small btn--danger" disabled={act.isPending} onClick={() => act.mutate("close")}>
            {t("inspections.close")}
          </button>
        )}
      </div>
      {rejecting && (
        <form
          className="inspections-inline no-print"
          onSubmit={(e) => {
            e.preventDefault();
            act.mutate("reject");
          }}
        >
          <Field id={`${id}-reason`} label={t("inspections.rejectReason")}>
            <input id={`${id}-reason`} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
          </Field>
          <div className="actions">
            <button type="submit" className="btn btn--danger" disabled={reason.trim().length < MIN_REASON || act.isPending}>
              {t("inspections.reject")}
            </button>
            <button type="button" className="btn" onClick={() => setRejecting(false)}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}
      <Problem error={act.error} />
    </article>
  );
}

// ---------------------------------------------------------------- settings

function SettingsTab() {
  return (
    <>
      <ModelSettings />
      <PolicySettings />
      <NotesSettings />
    </>
  );
}

function ModelSettings() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const invalidate = useInvalidate();
  const id = useId();
  const profile = useQuery({ queryKey: inspectionKeys.profile, queryFn: ({ signal }) => api.inspectionProfile(signal) });
  const [draft, setDraft] = useState<{ name: string; config: ProfileConfig } | null>(null);
  const save = useMutation({
    mutationFn: () => (draft ? api.saveInspectionProfile(draft.name, draft.config) : Promise.reject(new Error("no_draft"))),
    onSuccess: () => {
      setDraft(null);
      invalidate();
    },
  });
  const p = profile.data;
  const config = draft?.config ?? p?.config;
  const edit = (change: (c: ProfileConfig) => ProfileConfig) =>
    setDraft((d) => {
      const base = d ?? (p ? { name: p.name, config: structuredClone(p.config) } : null);
      return base ? { ...base, config: change(structuredClone(base.config)) } : null;
    });
  const num = (v: string) => Math.max(0, Math.min(100, Number(v) || 0));
  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{t("inspections.modelTitle")}</h2>
      {profile.isPending && <Loading />}
      {profile.isError && <ErrorBox error={profile.error} onRetry={() => void profile.refetch()} />}
      {p && config && (
        <>
          <p className="muted">
            {t("inspections.modelVersion", { name: p.name, version: p.version })}
            {p.created_by_name && <> · {p.created_by_name}</>} · {fmt.dateTime(p.created_at)}
          </p>
          <p className="muted">{t("inspections.modelHint")}</p>
          <h3>{t("inspections.weights")}</h3>
          <div className="form-grid">
            {(["items", "presence", "exit"] as const).map((k) => (
              <Field key={k} id={`${id}-w-${k}`} label={t(`inspections.weight.${k}`)}>
                <input
                  id={`${id}-w-${k}`}
                  type="number"
                  min={0}
                  max={100}
                  value={config.weights[k]}
                  onChange={(e) => edit((c) => ({ ...c, weights: { ...c.weights, [k]: num(e.target.value) } }))}
                />
              </Field>
            ))}
          </div>
          {config.axes.map((axis, ai) => (
            <div key={axis.key}>
              <h3>
                {axis.name}{" "}
                <input
                  type="number"
                  aria-label={t("inspections.axisWeight", { name: axis.name })}
                  min={0}
                  max={100}
                  value={axis.weight}
                  onChange={(e) =>
                    edit((c) => ({ ...c, axes: c.axes.map((a, j) => (j === ai ? { ...a, weight: num(e.target.value) } : a)) }))
                  }
                />
              </h3>
              <table className="table">
                <tbody>
                  {config.items
                    .filter((it) => it.axis === axis.key)
                    .map((it) => (
                      <tr key={it.key}>
                        <td dir="auto">{it.text}</td>
                        <td>
                          <input
                            type="number"
                            aria-label={t("inspections.itemWeight", { text: it.text })}
                            min={0}
                            max={100}
                            value={it.weight}
                            onChange={(e) =>
                              edit((c) => ({
                                ...c,
                                items: c.items.map((x) => (x.key === it.key ? { ...x, weight: num(e.target.value) } : x)),
                              }))
                            }
                          />
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          ))}
          <h3>{t("inspections.levelsTitle")}</h3>
          <ul className="inspections-levels">
            {config.levels.map((l) => (
              <li key={l.name}>
                <Verdict verdict={l.name} /> ≥ <span dir="ltr">{l.min}%</span>
              </li>
            ))}
          </ul>
          <Problem error={save.error} />
          {draft && (
            <div className="actions no-print">
              <button type="button" className="btn btn--primary" disabled={save.isPending} onClick={() => save.mutate()}>
                {t("inspections.saveModel")}
              </button>
              <button type="button" className="btn" onClick={() => setDraft(null)}>
                {t("common.cancel")}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function PolicySettings() {
  const { t } = useTranslation();
  const { api } = useServices();
  const invalidate = useInvalidate();
  const id = useId();
  const policy = useQuery({ queryKey: inspectionKeys.policy, queryFn: ({ signal }) => api.inspectionPolicy(signal) });
  const [draft, setDraft] = useState<Policy | null>(null);
  const save = useMutation({
    mutationFn: () => (draft ? api.saveInspectionPolicy(draft) : Promise.reject(new Error("no_draft"))),
    onSuccess: () => {
      setDraft(null);
      invalidate();
    },
  });
  const apply = useMutation({ mutationFn: () => api.applyInspectionPolicy(), onSuccess: invalidate });
  const p = draft ?? policy.data;
  const edit = (change: (p: Policy) => Policy) =>
    setDraft((d) => {
      const base = d ?? policy.data;
      return base ? change(structuredClone(base)) : null;
    });
  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{t("inspections.policyTitle")}</h2>
      <p className="muted">{t("inspections.policyHint")}</p>
      {policy.isPending && <Loading />}
      {policy.isError && <ErrorBox error={policy.error} onRetry={() => void policy.refetch()} />}
      {p && (
        <>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("inspections.roomLabel")}</th>
                <th scope="col">{t("inspections.discloseInspection")}</th>
                <th scope="col">{t("inspections.columns.verdict")}</th>
                <th scope="col">{t("inspections.columns.score")}</th>
              </tr>
            </thead>
            <tbody>
              {(["central", "regional"] as const).map((room) => (
                <tr key={room}>
                  <th scope="row">{t(`inspections.room.${room}`)}</th>
                  {(["inspection", "verdict", "score"] as const).map((field) => (
                    <td key={field}>
                      <input
                        type="checkbox"
                        aria-label={`${t(`inspections.room.${room}`)}: ${t(`inspections.disclose.${field}`)}`}
                        checked={p[room][field]}
                        onChange={(e) => edit((x) => ({ ...x, [room]: { ...x[room], [field]: e.target.checked } }))}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="form-grid">
            {(["high", "medium", "low", "general"] as const).map((k) => (
              <Field key={k} id={`${id}-rec-${k}`} label={t(`inspections.recRule.${k}`)}>
                <select
                  id={`${id}-rec-${k}`}
                  value={p.recommendations[k]}
                  onChange={(e) =>
                    edit((x) => ({ ...x, recommendations: { ...x.recommendations, [k]: e.target.value as Audience } }))
                  }
                >
                  {AUDIENCES.map((a) => (
                    <option key={a} value={a}>
                      {t(`inspections.audienceKind.${a}`)}
                    </option>
                  ))}
                </select>
              </Field>
            ))}
          </div>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={p.publish_programme}
              onChange={(e) => edit((x) => ({ ...x, publish_programme: e.target.checked }))}
            />{" "}
            {t("inspections.publishProgramme")}
          </label>
          <h3>{t("inspections.alertsTitle")}</h3>
          <p className="muted">{t("inspections.alertsHint")}</p>
          <div className="form-grid">
            <Field id={`${id}-notice`} label={t("inspections.noticeDays")}>
              <input
                id={`${id}-notice`}
                type="number"
                min={1}
                max={60}
                value={p.notice_days}
                onChange={(e) => edit((x) => ({ ...x, notice_days: Number(e.target.value) }))}
              />
            </Field>
            <Field id={`${id}-reminder`} label={t("inspections.reminderDays")}>
              <input
                id={`${id}-reminder`}
                type="number"
                min={0}
                max={14}
                value={p.reminder_days}
                onChange={(e) => edit((x) => ({ ...x, reminder_days: Number(e.target.value) }))}
              />
            </Field>
          </div>
          <Problem error={save.error ?? apply.error} />
          {apply.isSuccess && <p className="alert">{t("inspections.applied", { n: apply.data.deleted })}</p>}
          <div className="actions no-print">
            {draft && (
              <>
                <button type="button" className="btn btn--primary" disabled={save.isPending} onClick={() => save.mutate()}>
                  {t("inspections.savePolicy")}
                </button>
                <button type="button" className="btn" onClick={() => setDraft(null)}>
                  {t("common.cancel")}
                </button>
              </>
            )}
            {!draft && (
              <button type="button" className="btn btn--small" disabled={apply.isPending} onClick={() => apply.mutate()}>
                {t("inspections.applyPolicy")}
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function NotesSettings() {
  const { t } = useTranslation();
  const { api } = useServices();
  const invalidate = useInvalidate();
  const id = useId();
  const notes = useQuery({ queryKey: inspectionKeys.notes, queryFn: ({ signal }) => api.orderNotes(signal) });
  const [draft, setDraft] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () =>
      api.saveOrderNotes(
        (draft ?? "")
          .split("\n")
          .map((l) => l.trim())
          .filter((l) => l.length >= 2),
      ),
    onSuccess: () => {
      setDraft(null);
      invalidate();
    },
  });
  const text = draft ?? (notes.data?.notes ?? []).join("\n");
  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{t("inspections.notesTitle")}</h2>
      <p className="muted">{t("inspections.notesHint")}</p>
      {notes.isPending && <Loading />}
      {notes.isError && <ErrorBox error={notes.error} onRetry={() => void notes.refetch()} />}
      {notes.data && (
        <>
          <label htmlFor={`${id}-notes`} className="visually-hidden">
            {t("inspections.notesTitle")}
          </label>
          <textarea id={`${id}-notes`} dir="auto" rows={6} value={text} onChange={(e) => setDraft(e.target.value)} />
          <Problem error={save.error} />
          {draft !== null && (
            <div className="actions no-print">
              <button type="button" className="btn btn--primary" disabled={save.isPending} onClick={() => save.mutate()}>
                {t("inspections.saveNotes")}
              </button>
              <button type="button" className="btn" onClick={() => setDraft(null)}>
                {t("common.cancel")}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
