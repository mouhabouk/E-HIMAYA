// covers: OS3 (docs/phase-os3/design-os3.md §2, Yamen 2026-11-11): the vehicles and their maintenance, a system of
// its own on the shared register. The maintenance department adds a vehicle, keeps its card (administrative number,
// plate number, odometer, acquisition date), sends it to the workshop, takes it back and decommissions it after the
// decision; the operations rooms read the fleet and set the operational state only (at its unit, reinforcement,
// broken). Every vehicle is shown within the reader's scope (its gouvernorat; the central room all of them).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { IconTile } from "../components/Icon";
import { categoryName, DeleteEntry, VehicleForm } from "../components/InventoryForms";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { fleetKeys, vehiclesByState, type RoomState, type VehicleEvent } from "../lib/fleet";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { inventoryKeys, STATE_TONE, VEHICLE_STATES, type Vehicle, type VehicleState } from "../lib/inventory";

export type FleetView = "dashboard" | "vehicles" | "maintenance" | "archive" | "log";
const TABS: readonly [FleetView, string][] = [
  ["dashboard", "/fleet"],
  ["vehicles", "/fleet/vehicles"],
  ["maintenance", "/fleet/maintenance"],
  ["archive", "/fleet/archive"],
  ["log", "/fleet/log"],
];
const MIN_REASON = 5;
type Action = { vehicle: Vehicle; kind: "edit" | "state" | "workshop" | "back" | "retire" } | { kind: "new" };

function Pill({ state }: { state: VehicleState }) {
  const { t } = useTranslation();
  return <span className={`pill tone-${STATE_TONE[state]}`}>{t(`inventory.state.${state}`)}</span>;
}

function Field({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
    </div>
  );
}

function useCatalogue() {
  const { api } = useServices();
  const q = useQuery({ queryKey: inventoryKeys.catalogue, queryFn: ({ signal }) => api.inventoryCatalogue(signal) });
  return useMemo(() => new Map((q.data?.items ?? []).map((c) => [c.key, c])), [q.data]);
}

export function FleetPage({ view }: { view: FleetView }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const gouvId = useId();
  const [gouvernorat, setGouvernorat] = useState<number | null>(null);
  const list = useQuery({
    queryKey: fleetKeys.vehicles(gouvernorat),
    queryFn: ({ signal }) => api.fleetVehicles(gouvernorat, signal),
  });
  const data = list.data;
  const national = user?.identity.national ?? false;
  return (
    <div className="page fleet-page">
      <div className="page__head">
        <PageTitle print icon="localShipping" tone="amber">
          {t("fleet.title")}
        </PageTitle>
      </div>
      <p className="muted">{t(data?.can_edit ? "fleet.introMaintenance" : "fleet.introRoom")}</p>
      <nav className="tabs" aria-label={t("fleet.tabs.label")}>
        {TABS.map(([key, to]) => (
          <NavLink key={key} to={to} end className={({ isActive }) => `tabs__tab${isActive ? " tabs__tab--active" : ""}`}>
            {t(`fleet.tabs.${key}`)}
          </NavLink>
        ))}
      </nav>
      {national && (
        <div className="filters__row">
          <div className="field">
            <label htmlFor={gouvId}>{t("filters.gouvernorat")}</label>
            <select
              id={gouvId}
              value={gouvernorat ?? ""}
              onChange={(e) => setGouvernorat(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">{t("filters.allGouvernorats")}</option>
              {gouvernorats.list.map((g) => (
                <option key={g.code} value={g.code}>
                  {gouvernorats.nameOf(g.code)}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {data && view === "dashboard" && <Dashboard items={data.items} gouvernorat={gouvernorat} />}
      {data && view === "vehicles" && (
        <Vehicles
          items={data.items.filter((v) => v.state !== "retired")}
          gouvernorat={gouvernorat}
          canEdit={data.can_edit}
          canSetState={data.can_set_state}
          canMaintain={data.can_maintain}
        />
      )}
      {data && view === "maintenance" && (
        <Vehicles
          items={data.items.filter((v) => v.state === "broken" || v.state === "maintenance")}
          gouvernorat={gouvernorat}
          canEdit={false}
          canSetState={false}
          canMaintain={data.can_maintain}
          workshop
        />
      )}
      {data && view === "archive" && <Archive items={data.items.filter((v) => v.state === "retired")} />}
      {view === "log" && <Log gouvernorat={gouvernorat} />}
    </div>
  );
}

// ---------------------------------------------------------------- dashboard

function Dashboard({ items, gouvernorat }: { items: Vehicle[]; gouvernorat: number | null }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const counts = vehiclesByState(items);
  const active = items.filter((v) => v.state !== "retired").length;
  const today = new Date().toISOString().slice(0, 10);
  const late = items.filter((v) => v.state === "maintenance" && v.maint_until && v.maint_until < today);
  const tone: Record<(typeof VEHICLE_STATES)[number], "green" | "sky" | "purple" | "red" | "amber" | "navy"> = {
    ready: "green",
    assigned: "sky",
    reinforcement: "purple",
    broken: "red",
    maintenance: "amber",
    retired: "navy",
  };
  return (
    <>
      <dl className="kpis">
        <div className="kpi kpi--with-icon card">
          <IconTile name="localShipping" tone="amber" soft />
          <dt className="kpi__label">{t("fleet.kpi.active")}</dt>
          <dd className="kpi__value">{fmt.number(active)}</dd>
        </div>
        {VEHICLE_STATES.map((s) => (
          <div key={s} className="kpi kpi--with-icon card">
            <IconTile name={s === "broken" || s === "maintenance" ? "warning" : "localShipping"} tone={tone[s]} soft />
            <dt className="kpi__label">{t(`inventory.state.${s}`)}</dt>
            <dd className="kpi__value">{fmt.number(counts[s] ?? 0)}</dd>
          </div>
        ))}
      </dl>
      {late.length > 0 && (
        <p className="alert alert--warning" role="status">
          {t("fleet.lateWorkshop", { n: fmt.number(late.length), labels: late.map((v) => v.label).join("، ") })}
        </p>
      )}
      <section className="card" aria-labelledby="fleet-recent">
        <h2 id="fleet-recent">{t("fleet.recent")}</h2>
        <Log gouvernorat={gouvernorat} limit={8} />
      </section>
    </>
  );
}

// ---------------------------------------------------------------- vehicles

function Vehicles({
  items,
  gouvernorat,
  canEdit,
  canSetState,
  canMaintain,
  workshop = false,
}: {
  items: Vehicle[];
  gouvernorat: number | null;
  canEdit: boolean;
  canSetState: boolean;
  canMaintain: boolean;
  workshop?: boolean;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const categories = useCatalogue();
  const searchId = useId();
  const stateId = useId();
  const [q, setQ] = useState("");
  const [state, setState] = useState<VehicleState | "">("");
  const [action, setAction] = useState<Action | null>(null);
  const shown = items.filter((v) => {
    const text = `${v.label} ${v.code ?? ""} ${v.plate ?? ""} ${v.unit_name}`.toLowerCase();
    return (!q.trim() || text.includes(q.trim().toLowerCase())) && (!state || v.state === state);
  });
  return (
    <>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={searchId}>{t("fleet.search")}</label>
          <input id={searchId} type="search" dir="auto" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {!workshop && (
          <div className="field">
            <label htmlFor={stateId}>{t("inventory.field.state")}</label>
            <select id={stateId} value={state} onChange={(e) => setState(e.target.value as VehicleState | "")}>
              <option value="">{t("fleet.allStates")}</option>
              {VEHICLE_STATES.filter((s) => s !== "retired").map((s) => (
                <option key={s} value={s}>
                  {t(`inventory.state.${s}`)}
                </option>
              ))}
            </select>
          </div>
        )}
        {canEdit && !workshop && action === null && (
          <button type="button" className="btn btn--primary" onClick={() => setAction({ kind: "new" })}>
            {t("fleet.add")}
          </button>
        )}
      </div>
      {action && <ActionPanel action={action} gouvernorat={gouvernorat} onDone={() => setAction(null)} />}
      {shown.length === 0 ? (
        <p className="card ops-empty">{t(workshop ? "fleet.workshopEmpty" : "inventory.empty")}</p>
      ) : (
        <div className="table-wrap">
          <table className="table inventory-table">
            <caption>{t("inventory.vehicles.count", { n: fmt.number(shown.length) })}</caption>
            <thead>
              <tr>
                <th scope="col">{t("inventory.field.label")}</th>
                <th scope="col">{t("fleet.field.plate")}</th>
                <th scope="col">{t("inventory.field.type")}</th>
                <th scope="col">{t("inventory.field.unit")}</th>
                <th scope="col">{t("inventory.field.state")}</th>
                <th scope="col">{workshop ? t("fleet.field.workshopInfo") : t("fleet.field.odometer")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("inventory.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((v) => (
                <tr key={v.id}>
                  <th scope="row" dir="auto">
                    {v.label}
                    {v.code && (
                      <span className="muted inventory-sub">
                        <bdi dir="ltr">{v.code}</bdi>
                      </span>
                    )}
                  </th>
                  <td dir="rtl">{v.plate ?? "—"}</td>
                  <td>{categoryName(v.category_key ? categories.get(v.category_key) : undefined, lang, t("inventory.otherType"))}</td>
                  <td dir="auto">
                    {v.unit_name}
                    {v.stationed_unit_name && (
                      <span className="muted inventory-sub">{t("fleet.waitsAt", { unit: v.stationed_unit_name })}</span>
                    )}
                  </td>
                  <td>
                    <Pill state={v.state} />
                  </td>
                  <td>
                    {workshop ? (
                      <span dir="auto">
                        {v.state === "broken" ? v.fault : `${v.workshop ?? ""} — ${v.maint_reason ?? ""}`}
                        {v.maint_until && (
                          <span className="muted inventory-sub">{t("fleet.until", { date: fmt.date(v.maint_until) })}</span>
                        )}
                      </span>
                    ) : v.odometer_km != null ? (
                      <span className="num">{t("fleet.km", { n: fmt.number(v.odometer_km) })}</span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    <div className="actions">
                      {canSetState && v.state !== "assigned" && v.state !== "maintenance" && (
                        <button type="button" className="btn btn--small" onClick={() => setAction({ vehicle: v, kind: "state" })}>
                          {t("fleet.action.state")}
                        </button>
                      )}
                      {canEdit && !workshop && (
                        <button type="button" className="btn btn--small" onClick={() => setAction({ vehicle: v, kind: "edit" })}>
                          {t("inventory.edit")}
                        </button>
                      )}
                      {canMaintain && v.state !== "assigned" && v.state !== "maintenance" && (
                        <button type="button" className="btn btn--small" onClick={() => setAction({ vehicle: v, kind: "workshop" })}>
                          {t("fleet.action.workshop")}
                        </button>
                      )}
                      {canMaintain && v.state === "maintenance" && (
                        <button type="button" className="btn btn--small btn--primary" onClick={() => setAction({ vehicle: v, kind: "back" })}>
                          {t("fleet.action.back")}
                        </button>
                      )}
                      {canMaintain && !workshop && v.state !== "assigned" && (
                        <button type="button" className="btn btn--small btn--ghost" onClick={() => setAction({ vehicle: v, kind: "retire" })}>
                          {t("fleet.action.retire")}
                        </button>
                      )}
                      {canEdit && !workshop && (
                        <DeleteEntry label={v.label} onDelete={(reason) => api.deleteVehicle(v.id, reason)} />
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function ActionPanel({ action, gouvernorat, onDone }: { action: Action; gouvernorat: number | null; onDone: () => void }) {
  const { api } = useServices();
  const units = useQuery({
    queryKey: inventoryKeys.units(gouvernorat),
    queryFn: ({ signal }) => api.inventoryUnits(gouvernorat, signal),
  });
  const catalogue = useQuery({ queryKey: inventoryKeys.catalogue, queryFn: ({ signal }) => api.inventoryCatalogue(signal) });
  if (action.kind === "new" || action.kind === "edit") {
    if (!units.data || !catalogue.data) return <Loading />;
    return (
      <VehicleForm
        vehicle={action.kind === "edit" ? action.vehicle : null}
        units={units.data.items}
        categories={catalogue.data.items}
        onDone={onDone}
      />
    );
  }
  return <Decision action={action} units={units.data?.items ?? []} onDone={onDone} />;
}

function Decision({
  action,
  units,
  onDone,
}: {
  action: Exclude<Action, { kind: "new" }>;
  units: { id: string; name_ar: string; name_fr: string; gouvernorat_code: number }[];
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const qc = useQueryClient();
  const id = useId();
  const v = action.vehicle;
  const [state, setState] = useState<RoomState>(v.state === "broken" ? "ready" : "broken");
  const [host, setHost] = useState("");
  const [text1, setText1] = useState("");
  const [text2, setText2] = useState("");
  const [day, setDay] = useState(action.kind === "retire" ? new Date().toISOString().slice(0, 10) : "");
  const [odometer, setOdometer] = useState("");
  const [tried, setTried] = useState(false);
  const missing =
    (action.kind === "state" && state === "broken" && text1.trim().length < 3) ||
    (action.kind === "state" && state === "reinforcement" && !host) ||
    (action.kind === "workshop" && (text1.trim().length < 2 || text2.trim().length < 3)) ||
    (action.kind === "retire" && (text1.trim().length < 2 || text2.trim().length < MIN_REASON || !day));
  const mutation = useMutation({
    mutationFn: () => {
      if (action.kind === "state")
        return api.setVehicleState(v.id, {
          state,
          host_unit_id: state === "reinforcement" ? host : null,
          fault: state === "broken" ? text1.trim() : null,
          note: text2.trim() || null,
          version: v.version,
        });
      if (action.kind === "workshop")
        return api.startMaintenance(v.id, { workshop: text1.trim(), reason: text2.trim(), until: day || null, version: v.version });
      if (action.kind === "back")
        return api.endMaintenance(v.id, {
          note: text2.trim() || null,
          odometer_km: odometer ? Number(odometer) : null,
          version: v.version,
        });
      return api.retireVehicle(v.id, { decision: text1.trim(), reason: text2.trim(), retired_on: day, version: v.version });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: inventoryKeys.all });
      void qc.invalidateQueries({ queryKey: ["coverage"] });
      onDone();
    },
  });
  const title = t(`fleet.action.${action.kind}Title`, { label: v.label });
  return (
    <form
      className="card form-card"
      aria-label={title}
      onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (!missing) mutation.mutate();
      }}
    >
      <h2>{title}</h2>
      {action.kind === "retire" && <p className="alert alert--warning">{t("fleet.retireWarning")}</p>}
      <div className="form-grid">
        {action.kind === "state" && (
          <Field id={`${id}-state`} label={t("inventory.field.state")}>
            <select id={`${id}-state`} value={state} onChange={(e) => setState(e.target.value as RoomState)}>
              {(["ready", "reinforcement", "broken"] as const).map((s) => (
                <option key={s} value={s}>
                  {t(`fleet.roomState.${s}`)}
                </option>
              ))}
            </select>
          </Field>
        )}
        {action.kind === "state" && state === "reinforcement" && (
          <Field id={`${id}-host`} label={t("fleet.field.host")}>
            <select id={`${id}-host`} value={host} aria-required="true" onChange={(e) => setHost(e.target.value)}>
              <option value="">—</option>
              {units
                .filter((u) => u.id !== v.unit_id)
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {lang === "ar" ? u.name_ar : u.name_fr}
                  </option>
                ))}
            </select>
          </Field>
        )}
        {(action.kind === "workshop" || action.kind === "retire" || (action.kind === "state" && state === "broken")) && (
          <Field id={`${id}-t1`} label={t(`fleet.field.${action.kind === "state" ? "fault" : action.kind === "workshop" ? "workshop" : "decision"}`)}>
            <input id={`${id}-t1`} dir="auto" maxLength={action.kind === "retire" ? 80 : 500} aria-required="true" value={text1} onChange={(e) => setText1(e.target.value)} />
          </Field>
        )}
        {(action.kind === "workshop" || action.kind === "retire") && (
          <Field id={`${id}-day`} label={t(action.kind === "retire" ? "fleet.field.retiredOn" : "fleet.field.until")}>
            <input id={`${id}-day`} type="date" dir="ltr" value={day} onChange={(e) => setDay(e.target.value)} />
          </Field>
        )}
        {action.kind === "back" && (
          <Field id={`${id}-odo`} label={t("fleet.field.odometer")}>
            <input id={`${id}-odo`} type="number" dir="ltr" min={v.odometer_km ?? 0} value={odometer} onChange={(e) => setOdometer(e.target.value)} />
          </Field>
        )}
      </div>
      <Field
        id={`${id}-t2`}
        label={t(action.kind === "workshop" ? "fleet.field.maintReason" : action.kind === "retire" ? "fleet.field.retireReason" : "fleet.field.note")}
      >
        <input id={`${id}-t2`} dir="auto" maxLength={500} value={text2} onChange={(e) => setText2(e.target.value)} />
      </Field>
      {tried && missing && <p className="alert alert--error">{t("inventory.form.missing")}</p>}
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {t("fleet.confirm")}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onDone}>
          {t("inventory.cancel")}
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------- archive and log

function Archive({ items }: { items: Vehicle[] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  if (items.length === 0) return <p className="card ops-empty">{t("fleet.archiveEmpty")}</p>;
  return (
    <div className="table-wrap">
      <table className="table inventory-table">
        <caption>{t("fleet.archiveCount", { n: fmt.number(items.length) })}</caption>
        <thead>
          <tr>
            <th scope="col">{t("inventory.field.label")}</th>
            <th scope="col">{t("fleet.field.plate")}</th>
            <th scope="col">{t("inventory.field.unit")}</th>
            <th scope="col">{t("fleet.field.decision")}</th>
            <th scope="col">{t("fleet.field.retiredOn")}</th>
            <th scope="col">{t("fleet.field.retireReason")}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((v) => (
            <tr key={v.id}>
              <th scope="row" dir="auto">
                {v.label}
              </th>
              <td dir="rtl">{v.plate ?? "—"}</td>
              <td dir="auto">{v.unit_name}</td>
              <td dir="auto">{v.retire_decision}</td>
              <td>{v.retired_on ? fmt.date(v.retired_on) : "—"}</td>
              <td dir="auto">{v.retire_reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function eventText(e: VehicleEvent, t: (k: string, o?: Record<string, unknown>) => string, num: (n: number) => string): string {
  const d = e.details;
  const parts = [t(`fleet.event.${e.kind}`)];
  if (d.host_unit_name) parts.push(String(d.host_unit_name));
  if (d.fault) parts.push(String(d.fault));
  if (d.workshop) parts.push(String(d.workshop));
  if (d.decision) parts.push(String(d.decision));
  if (typeof d.suggested_gain === "number") parts.push(t("fleet.event.gain", { n: num(d.suggested_gain) }));
  if (d.note) parts.push(String(d.note));
  return parts.join(" — ");
}

function Log({ gouvernorat, limit }: { gouvernorat: number | null; limit?: number }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const q = useQuery({
    queryKey: fleetKeys.events(gouvernorat, null),
    queryFn: ({ signal }) => api.vehicleEvents({ gouvernorat }, signal),
  });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorBox error={q.error} onRetry={() => void q.refetch()} />;
  const items = limit ? q.data.items.slice(0, limit) : q.data.items;
  if (items.length === 0) return <p className="muted">{t("fleet.logEmpty")}</p>;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">{t("fleet.field.when")}</th>
            <th scope="col">{t("inventory.field.label")}</th>
            <th scope="col">{t("fleet.field.change")}</th>
            <th scope="col">{t("fleet.field.what")}</th>
            <th scope="col">{t("fleet.field.by")}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((e) => (
            <tr key={e.id}>
              <td>{fmt.dateTime(e.created_at)}</td>
              <th scope="row" dir="auto">
                {e.label}
                <span className="muted inventory-sub">{e.unit_name}</span>
              </th>
              <td>
                <Pill state={e.from_state as VehicleState} /> ← <Pill state={e.to_state as VehicleState} />
              </td>
              <td dir="auto">{eventText(e, t, (n) => fmt.number(n))}</td>
              <td dir="auto">{e.created_by_name ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
