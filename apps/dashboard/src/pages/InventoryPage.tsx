// covers: phase R1 (docs/phase-r/design-resources.md §2) and the search of phase R2 (§2.3, §2.4): the resources register of every gouvernorat. The counts by
// gouvernorat and by type (all that the governor and the minister see), the units with their last confirmation, the
// vehicles, the equipment and the staff of the gouvernorat, the import from the xlsx template, and the catalogue the
// central room keeps.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { AgentForm, categoryName, DeleteEntry, StockForm, TransferForm, TransfersPanel, VehicleForm } from "../components/InventoryForms";
import { GouvernoratPicker, SearchTab } from "../components/InventorySearch";
import { PageTitle } from "../components/PageTitle";
import { Stepper } from "../components/Stepper";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import {
  FAMILIES,
  inventoryKeys,
  specText,
  STATE_TONE,
  type Agent,
  type Category,
  type CategoryKind,
  type Entity,
  type Family,
  type ColumnMapping,
  type InventoryImport,
  type ImportProblem,
  type ListQuery,
  type Names,
  type Overview,
  type SpecDef,
  type StockLine,
  type UnitRow,
  type Vehicle,
} from "../lib/inventory";
import { saveDownload } from "../lib/layersApi";

const TABS = ["overview", "search", "units", "vehicles", "stock", "agents", "import", "catalogue"] as const;
type Tab = (typeof TABS)[number];
const MAX_FILE = 10 * 1024 * 1024;

function useCatalogue() {
  const { api } = useServices();
  const query = useQuery({ queryKey: inventoryKeys.catalogue, queryFn: ({ signal }) => api.inventoryCatalogue(signal) });
  const byKey = useMemo(() => new Map((query.data?.items ?? []).map((c) => [c.key, c])), [query.data]);
  return { query, items: query.data?.items ?? [], byKey };
}

function ExportButton({ entity, gouvernorat, names }: { entity: Entity; gouvernorat: number | null; names?: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const mutation = useMutation({
    mutationFn: () => api.exportInventory(entity, gouvernorat),
    onSuccess: saveDownload,
  });
  return (
    <>
      <button type="button" className="btn" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        {t("inventory.export")}
      </button>
      {names !== undefined && <span className="muted">{t(names ? "inventory.exportWithNames" : "inventory.exportNoNames")}</span>}
      {mutation.isError && (
        <span className="field__error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </span>
      )}
    </>
  );
}

// ---------------------------------------------------------------- overview

function OverviewTab({ data, categories }: { data: Overview; categories: Map<string, Category> }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const lang = useLanguage();
  const name = (g: Overview["gouvernorats"][number]) => (lang === "ar" ? g.name_ar : lang === "fr" ? g.name_fr : g.name_en);
  const total = data.gouvernorats.reduce(
    (acc, g) => ({
      units: acc.units + g.units,
      ready: acc.ready + g.vehicles.ready,
      assigned: acc.assigned + g.vehicles.assigned,
      out: acc.out + g.vehicles.maintenance + g.vehicles.broken,
      eqReady: acc.eqReady + g.equipment.ready,
      eqBroken: acc.eqBroken + g.equipment.broken,
      agents: acc.agents + g.agents,
      onDuty: acc.onDuty + g.agents_on_duty,
    }),
    { units: 0, ready: 0, assigned: 0, out: 0, eqReady: 0, eqBroken: 0, agents: 0, onDuty: 0 },
  );
  const n = (v: number) => fmt.number(v);
  return (
    <>
      {!data.can_list && <p className="alert alert--info">{t("inventory.countsOnly")}</p>}
      <ul className="kpi-row inventory-kpis">
        <li className="card kpi">
          <span className="kpi__value">{n(total.ready)}</span>
          <span className="kpi__label">{t("inventory.kpi.vehiclesReady", { total: n(total.ready + total.assigned + total.out) })}</span>
        </li>
        <li className="card kpi">
          <span className="kpi__value">{n(total.eqReady)}</span>
          <span className="kpi__label">{t("inventory.kpi.equipmentReady", { broken: n(total.eqBroken) })}</span>
        </li>
        <li className="card kpi">
          <span className="kpi__value">{n(total.onDuty)}</span>
          <span className="kpi__label">{t("inventory.kpi.agentsOnDuty", { total: n(total.agents) })}</span>
        </li>
        <li className="card kpi">
          <span className="kpi__value">{n(total.units)}</span>
          <span className="kpi__label">{t("inventory.kpi.units")}</span>
        </li>
      </ul>
      <div className="table-wrap">
        <table className="table inventory-table">
          <caption>{t("inventory.overview.byGouvernorat")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("inventory.field.gouvernorat")}</th>
              <th scope="col">{t("inventory.overview.units")}</th>
              <th scope="col">{t("inventory.state.ready")}</th>
              <th scope="col">{t("inventory.state.assigned")}</th>
              <th scope="col">{t("inventory.overview.out")}</th>
              <th scope="col">{t("inventory.overview.equipment")}</th>
              <th scope="col">{t("inventory.overview.agents")}</th>
            </tr>
          </thead>
          <tbody>
            {data.gouvernorats.map((g) => (
              <tr key={g.code}>
                <th scope="row">{name(g)}</th>
                <td className="num">
                  {n(g.units)}
                  {g.stale_units > 0 && (
                    <>
                      {" "}
                      <span className="pill tone-amber">{t("inventory.overview.stale", { n: n(g.stale_units) })}</span>
                    </>
                  )}
                </td>
                <td className="num">{n(g.vehicles.ready)}</td>
                <td className="num">{n(g.vehicles.assigned)}</td>
                <td className="num">{n(g.vehicles.maintenance + g.vehicles.broken)}</td>
                <td className="num">
                  {n(g.equipment.ready)}
                  {g.equipment.broken > 0 && <span className="muted"> {t("inventory.overview.broken", { n: n(g.equipment.broken) })}</span>}
                </td>
                <td className="num">{t("inventory.overview.agentsOf", { on: n(g.agents_on_duty), all: n(g.agents) })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="inventory-columns">
        <div className="table-wrap">
          <table className="table inventory-table">
            <caption>{t("inventory.overview.byType")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("inventory.field.type")}</th>
                <th scope="col">{t("inventory.state.ready")}</th>
                <th scope="col">{t("inventory.state.assigned")}</th>
                <th scope="col">{t("inventory.state.maintenance")}</th>
                <th scope="col">{t("inventory.state.broken")}</th>
              </tr>
            </thead>
            <tbody>
              {data.categories.length === 0 && (
                <tr>
                  <td colSpan={5} className="muted">
                    {t("inventory.empty")}
                  </td>
                </tr>
              )}
              {data.categories.map((c) => (
                <tr key={`${c.kind}-${c.key}`}>
                  <th scope="row">{categoryName(categories.get(c.key), lang, t("inventory.otherType"))}</th>
                  <td className="num">{n(c.ready)}</td>
                  <td className="num">{c.kind === "vehicle" ? n(c.assigned) : "—"}</td>
                  <td className="num">{c.kind === "vehicle" ? n(c.maintenance) : "—"}</td>
                  <td className="num">{n(c.broken)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="table-wrap">
          <table className="table inventory-table">
            <caption>{t("inventory.overview.bySkill")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("inventory.field.skill")}</th>
                <th scope="col">{t("inventory.overview.agents")}</th>
                <th scope="col">{t("inventory.overview.skillReady")}</th>
                <th scope="col">{t("inventory.overview.expired")}</th>
              </tr>
            </thead>
            <tbody>
              {data.skills.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    {t("inventory.empty")}
                  </td>
                </tr>
              )}
              {data.skills.map((s) => (
                <tr key={s.key}>
                  <th scope="row">{categoryName(categories.get(s.key), lang, s.key)}</th>
                  <td className="num">{n(s.agents)}</td>
                  <td className="num">{n(s.ready)}</td>
                  <td className="num">{s.expired > 0 ? <span className="pill tone-amber">{n(s.expired)}</span> : n(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------- units

function UnitsTab({ units }: { units: UnitRow[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const fmt = useFormat();
  const lang = useLanguage();
  const { nameOf } = useGouvernorats();
  const verify = useMutation({
    mutationFn: (id: string) => api.verifyUnit(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: inventoryKeys.all }),
  });
  const stale = units.filter((u) => u.stale).length;
  return (
    <>
      <p className="muted">{t("inventory.units.intro")}</p>
      {stale > 0 && (
        <p className="alert alert--info" role="status">
          {t("inventory.units.staleCount", { n: fmt.number(stale) })}
        </p>
      )}
      {verify.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(verify.error))}
        </p>
      )}
      <div className="table-wrap">
        <table className="table inventory-table">
          <caption className="visually-hidden">{t("inventory.tabs.units")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("inventory.field.unit")}</th>
              <th scope="col">{t("inventory.field.gouvernorat")}</th>
              <th scope="col">{t("inventory.units.vehicles")}</th>
              <th scope="col">{t("inventory.overview.equipment")}</th>
              <th scope="col">{t("inventory.overview.agents")}</th>
              <th scope="col">{t("inventory.units.verified")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("inventory.actions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {units.map((u) => {
              const unitName = lang === "ar" ? u.name_ar : u.name_fr;
              return (
                <tr key={u.id}>
                  <th scope="row" dir="auto">
                    {unitName}
                  </th>
                  <td>{nameOf(u.gouvernorat_code)}</td>
                  <td className="num">{t("inventory.overview.agentsOf", { on: fmt.number(u.vehicles_ready), all: fmt.number(u.vehicles) })}</td>
                  <td className="num">
                    {fmt.number(u.equipment_ready)}
                    {u.equipment_broken > 0 && <span className="muted"> {t("inventory.overview.broken", { n: fmt.number(u.equipment_broken) })}</span>}
                  </td>
                  <td className="num">{t("inventory.overview.agentsOf", { on: fmt.number(u.agents_on_duty), all: fmt.number(u.agents) })}</td>
                  <td>
                    {u.verified_at ? <time dateTime={u.verified_at}>{fmt.date(u.verified_at)}</time> : t("inventory.units.never")}
                    {u.stale && (
                      <>
                        {" "}
                        <span className="pill tone-amber">{t("inventory.units.stale")}</span>
                      </>
                    )}
                  </td>
                  <td>
                    {u.can_edit && (
                      <button
                        type="button"
                        className="btn btn--small"
                        disabled={verify.isPending}
                        aria-label={t("inventory.units.verifyNamed", { unit: unitName })}
                        onClick={() => verify.mutate(u.id)}
                      >
                        {t("inventory.units.verify")}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {units.length === 0 && <p className="card ops-empty">{t("inventory.units.none")}</p>}
    </>
  );
}

// ---------------------------------------------------------------- lists

function TypeFilter({ kind, value, onChange, categories }: { kind: CategoryKind; value: string | null; onChange: (v: string | null) => void; categories: Category[] }) {
  const { t } = useTranslation();
  const lang = useLanguage();
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{t(kind === "skill" ? "inventory.field.skill" : "inventory.field.type")}</label>
      <select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}>
        <option value="">{t("inventory.anyType")}</option>
        {categories
          .filter((c) => c.kind === kind)
          .map((c) => (
            <option key={c.key} value={c.key}>
              {categoryName(c, lang)}
            </option>
          ))}
      </select>
    </div>
  );
}

function VehiclesTab({ q, units, catalogue }: { q: ListQuery; units: UnitRow[]; catalogue: ReturnType<typeof useCatalogue> }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const [type, setType] = useState<string | null>(null);
  const [editing, setEditing] = useState<Vehicle | "new" | null>(null);
  const query = { ...q, category: type };
  const list = useQuery({ queryKey: inventoryKeys.list("vehicles", query), queryFn: ({ signal }) => api.vehicles(query, signal) });
  const data = list.data;
  return (
    <>
      <div className="filters__row">
        <TypeFilter kind="vehicle" value={type} onChange={setType} categories={catalogue.items} />
        <ExportButton entity="vehicles" gouvernorat={q.gouvernorat} />
        {data?.can_edit && editing === null && (
          <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
            {t("inventory.vehicles.newTitle")}
          </button>
        )}
      </div>
      {editing !== null && (
        <VehicleForm
          key={editing === "new" ? "new" : editing.id}
          vehicle={editing === "new" ? null : editing}
          units={units}
          categories={catalogue.items}
          onDone={() => setEditing(null)}
        />
      )}
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {data && data.items.length === 0 && <p className="card ops-empty">{t("inventory.empty")}</p>}
      {data && data.items.length > 0 && (
        <div className="table-wrap">
          <table className="table inventory-table">
            <caption>{t("inventory.vehicles.count", { n: fmt.number(data.items.length) })}</caption>
            <thead>
              <tr>
                <th scope="col">{t("inventory.field.label")}</th>
                <th scope="col">{t("inventory.field.type")}</th>
                <th scope="col">{t("inventory.field.specs")}</th>
                <th scope="col">{t("inventory.field.unit")}</th>
                <th scope="col">{t("inventory.field.state")}</th>
                <th scope="col">{t("inventory.field.year")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("inventory.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((v) => {
                const category = v.category_key ? catalogue.byKey.get(v.category_key) : undefined;
                return (
                  <tr key={v.id}>
                    <th scope="row" dir="auto">
                      {v.label}
                      {v.code && (
                        <span className="muted inventory-sub">
                          <bdi dir="ltr">{v.code}</bdi>
                        </span>
                      )}
                    </th>
                    <td>{categoryName(category, lang, t("inventory.otherType"))}</td>
                    <td>{specText(v.specs, category, lang, (v) => fmt.number(v), t("inventory.yes")) || "—"}</td>
                    <td dir="auto">{v.unit_name}</td>
                    <td>
                      <span className={`pill tone-${STATE_TONE[v.state]}`}>{t(`inventory.state.${v.state}`)}</span>
                    </td>
                    <td className="num">{v.year ? String(v.year) : "—"}</td>
                    <td>
                      {data.can_edit && (
                        <div className="actions">
                          <button type="button" className="btn btn--small" aria-label={t("inventory.editNamed", { label: v.label })} onClick={() => setEditing(v)}>
                            {t("inventory.edit")}
                          </button>
                          <DeleteEntry label={v.label} onDelete={(reason) => api.deleteVehicle(v.id, reason)} />
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function StockTab({ q, units, catalogue }: { q: ListQuery; units: UnitRow[]; catalogue: ReturnType<typeof useCatalogue> }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const [type, setType] = useState<string | null>(null);
  const [editing, setEditing] = useState<StockLine | "new" | null>(null);
  const query = { ...q, category: type };
  const list = useQuery({ queryKey: inventoryKeys.list("stock", query), queryFn: ({ signal }) => api.stock(query, signal) });
  const data = list.data;
  return (
    <>
      <div className="filters__row">
        <TypeFilter kind="equipment" value={type} onChange={setType} categories={catalogue.items} />
        <ExportButton entity="stock" gouvernorat={q.gouvernorat} />
        {data?.can_edit && editing === null && (
          <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
            {t("inventory.stock.newTitle")}
          </button>
        )}
      </div>
      {editing !== null && (
        <StockForm
          key={editing === "new" ? "new" : editing.id}
          line={editing === "new" ? null : editing}
          units={units}
          categories={catalogue.items}
          onDone={() => setEditing(null)}
        />
      )}
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {data && data.items.length === 0 && <p className="card ops-empty">{t("inventory.empty")}</p>}
      {data && data.items.length > 0 && (
        <div className="table-wrap">
          <table className="table inventory-table">
            <caption className="visually-hidden">{t("inventory.tabs.stock")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("inventory.field.type")}</th>
                <th scope="col">{t("inventory.field.specs")}</th>
                <th scope="col">{t("inventory.field.unit")}</th>
                <th scope="col">{t("inventory.field.carrier")}</th>
                <th scope="col">{t("inventory.field.qtyReady")}</th>
                <th scope="col">{t("inventory.field.qtyBroken")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("inventory.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((s) => {
                const category = catalogue.byKey.get(s.category_key);
                const label = `${categoryName(category, lang)} · ${s.unit_name}`;
                return (
                  <tr key={s.id}>
                    <th scope="row">{categoryName(category, lang)}</th>
                    <td>{specText(s.specs, category, lang, (v) => fmt.number(v), t("inventory.yes")) || "—"}</td>
                    <td dir="auto">{s.unit_name}</td>
                    <td dir="auto">{s.vehicle_label ?? <span className="muted">{t("inventory.stock.atUnit")}</span>}</td>
                    <td className="num">{fmt.number(s.qty_ready)}</td>
                    <td className="num">{s.qty_broken > 0 ? <span className="pill tone-red">{fmt.number(s.qty_broken)}</span> : fmt.number(0)}</td>
                    <td>
                      {data.can_edit && (
                        <div className="actions">
                          <button type="button" className="btn btn--small" aria-label={t("inventory.editNamed", { label })} onClick={() => setEditing(s)}>
                            {t("inventory.edit")}
                          </button>
                          <DeleteEntry label={label} onDelete={(reason) => api.deleteStock(s.id, reason)} />
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function SkillChips({ agent, catalogue }: { agent: Agent; catalogue: Map<string, Category> }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const lang = useLanguage();
  if (agent.skills.length === 0) return <>—</>;
  return (
    <ul className="inventory-chips">
      {agent.skills.map((s) => (
        <li key={s.skill_key} className={`pill ${s.expired ? "tone-amber" : "tone-teal"}`}>
          {categoryName(catalogue.get(s.skill_key), lang, s.skill_key)}
          {s.level > 0 && ` ${t("inventory.agents.level", { level: s.level })}`}
          {s.expired && s.cert_expires && ` · ${t("inventory.agents.expiredOn", { date: fmt.date(s.cert_expires) })}`}
        </li>
      ))}
    </ul>
  );
}

function AgentsTab({ q, units, catalogue }: { q: ListQuery; units: UnitRow[]; catalogue: ReturnType<typeof useCatalogue> }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const [skill, setSkill] = useState<string | null>(null);
  const [editing, setEditing] = useState<Agent | "new" | null>(null);
  const [moving, setMoving] = useState<Agent | null>(null);
  const query = { ...q, category: skill };
  const list = useQuery({ queryKey: inventoryKeys.list("agents", query), queryFn: ({ signal }) => api.agents(query, signal) });
  const data = list.data;
  return (
    <>
      <div className="filters__row">
        <TypeFilter kind="skill" value={skill} onChange={setSkill} categories={catalogue.items} />
        {data && <ExportButton entity="agents" gouvernorat={q.gouvernorat} names={data.can_export_names} />}
        {data?.can_edit && editing === null && (
          <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
            {t("inventory.agents.newTitle")}
          </button>
        )}
      </div>
      {data && !data.can_see_names && <p className="alert alert--info">{t("inventory.agents.namesHidden")}</p>}
      {data?.can_edit && data.can_see_names && <TransfersPanel units={units} />}
      {moving && <TransferForm key={moving.id} agent={moving} onDone={() => setMoving(null)} />}
      {editing !== null && (
        <AgentForm
          key={editing === "new" ? "new" : editing.id}
          agent={editing === "new" ? null : editing}
          units={units}
          categories={catalogue.items}
          onDone={() => setEditing(null)}
        />
      )}
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {data && data.items.length === 0 && <p className="card ops-empty">{t("inventory.empty")}</p>}
      {data && data.items.length > 0 && (
        <div className="table-wrap">
          <table className="table inventory-table">
            <caption>{t("inventory.agents.count", { n: fmt.number(data.items.length) })}</caption>
            <thead>
              <tr>
                <th scope="col">{t("inventory.field.fullName")}</th>
                <th scope="col">{t("inventory.field.rank")}</th>
                <th scope="col">{t("inventory.field.unit")}</th>
                <th scope="col">{t("inventory.field.skills")}</th>
                <th scope="col">{t("inventory.field.availability")}</th>
                {data.can_see_names && <th scope="col">{t("inventory.field.phone")}</th>}
                <th scope="col">
                  <span className="visually-hidden">{t("inventory.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((a) => {
                const label = a.full_name ?? a.rank ?? a.unit_name;
                return (
                  <tr key={a.id}>
                    <th scope="row" dir="auto">
                      {a.full_name ?? <span className="muted">{t("inventory.agents.hidden")}</span>}
                      {a.matricule && (
                        <span className="muted inventory-sub">
                          <bdi dir="ltr">{a.matricule}</bdi>
                        </span>
                      )}
                    </th>
                    <td dir="auto">{a.rank ?? "—"}</td>
                    <td dir="auto">{a.unit_name}</td>
                    <td>
                      <SkillChips agent={a} catalogue={catalogue.byKey} />
                    </td>
                    <td>{t(`inventory.availability.${a.availability}`)}</td>
                    {data.can_see_names && (
                      <td dir="ltr" className="num">
                        {a.phone ?? "—"}
                      </td>
                    )}
                    <td>
                      {data.can_edit && data.can_see_names && (
                        <div className="actions">
                          <button type="button" className="btn btn--small" aria-label={t("inventory.editNamed", { label })} onClick={() => setEditing(a)}>
                            {t("inventory.edit")}
                          </button>
                          <button type="button" className="btn btn--small" aria-label={t("inventory.transfer.openNamed", { label })} onClick={() => setMoving(a)}>
                            {t("inventory.transfer.open")}
                          </button>
                          <DeleteEntry label={label} onDelete={(reason) => api.deleteAgent(a.id, reason)} />
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------- import

function ProblemItems({ title, items, tone }: { title: string; items: ImportProblem[]; tone: "error" | "warning" }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  if (items.length === 0) return null;
  return (
    <details className={`card programme-problems programme-problems--${tone}`} open={tone === "error"}>
      <summary>
        {title} ({fmt.number(items.length)})
      </summary>
      <ul>
        {items.map((p, i) => (
          <li key={i} dir="auto">
            {t(`inventory.import.sheet.${p.entity}`, { defaultValue: p.entity })}
            {p.line ? ` · ${t("inventory.import.line", { line: p.line })}` : ""} · {t(`inventory.import.problem.${p.code}`, { defaultValue: p.code })}
            {p.value ? ` «${p.value}»` : ""}
          </li>
        ))}
      </ul>
    </details>
  );
}

function ImportTab({ national, gouvernorat }: { national: boolean; gouvernorat: number | null }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const fmt = useFormat();
  const { nameOf } = useGouvernorats();
  const id = useId();
  const [target, setTarget] = useState<number | null>(gouvernorat);
  const [file, setFile] = useState<File | null>(null);
  const [entity, setEntity] = useState<Entity>("vehicles");
  const [preview, setPreview] = useState<InventoryImport | null>(null);
  const [reason, setReason] = useState("");
  // R4b: a saved mapping, and the one chosen on screen for the columns the preview did not recognise.
  const [profile, setProfile] = useState<string | null>(null);
  const [mapping, setMapping] = useState<ColumnMapping>({});
  const profiles = useQuery({ queryKey: inventoryKeys.profiles, queryFn: ({ signal }) => api.importProfiles(signal) });
  const lower = file?.name.toLowerCase() ?? "";
  const json = lower.endsWith(".json");
  const csv = lower.endsWith(".csv") || json;
  const tooLarge = Boolean(file && file.size > MAX_FILE);
  const where = national ? target : null;
  const template = useMutation({ mutationFn: () => api.inventoryTemplate(where), onSuccess: saveDownload });
  const check = useMutation({
    mutationFn: (f: File) => api.importInventory(f, where, csv ? entity : null, false, "", { profile, mapping }),
    onSuccess: setPreview,
  });
  const apply = useMutation({
    mutationFn: (f: File) => api.importInventory(f, where, csv ? entity : null, true, reason.trim(), { profile, mapping }),
    onSuccess: (result) => {
      setPreview(result);
      void qc.invalidateQueries({ queryKey: inventoryKeys.all });
    },
  });
  const needsPlace = national && target === null;
  const blocked = !preview || preview.errors.length > 0 || preview.applied;
  const reset = () => {
    setPreview(null);
    check.reset();
    apply.reset();
  };
  return (
    <section className="card programme-import" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{t("inventory.import.title")}</h2>
      <p className="muted">{t("inventory.import.intro")}</p>
      {national && (
        <GouvernoratPicker
          value={target}
          onChange={(v) => {
            setTarget(v);
            reset();
          }}
          any={t("inventory.import.pickGouvernorat")}
        />
      )}
      <div className="actions">
        <button type="button" className="btn" disabled={needsPlace || template.isPending} onClick={() => template.mutate()}>
          {t("inventory.import.template")}
        </button>
      </div>
      <div className="field">
        <label htmlFor={`${id}-file`}>{t("inventory.import.file")}</label>
        <input
          id={`${id}-file`}
          type="file"
          accept=".xlsx,.csv,.json"
          aria-describedby={`${id}-file-help`}
          aria-invalid={tooLarge || undefined}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setMapping({});
            reset();
          }}
        />
        <p id={`${id}-file-help`} className={tooLarge ? "field__error" : "muted"}>
          {t(tooLarge ? "inventory.import.tooLarge" : "inventory.import.fileHelp")}
        </p>
      </div>
      {csv && (
        <div className="field">
          <label htmlFor={`${id}-entity`}>{t("inventory.import.csvOf")}</label>
          <select id={`${id}-entity`} value={entity} aria-describedby={json ? `${id}-json-help` : undefined} onChange={(e) => setEntity(e.target.value as Entity)}>
            {(["vehicles", "stock", "agents"] as const).map((k) => (
              <option key={k} value={k}>
                {t(`inventory.import.sheet.${k}`)}
              </option>
            ))}
          </select>
          {json && (
            <p id={`${id}-json-help`} className="muted">
              {t("inventory.import.jsonHelp")}
            </p>
          )}
        </div>
      )}
      {(profiles.data?.length ?? 0) > 0 && (
        <div className="field">
          <label htmlFor={`${id}-profile`}>{t("inventory.import.profile")}</label>
          <select
            id={`${id}-profile`}
            value={profile ?? ""}
            onChange={(e) => {
              setProfile(e.target.value || null);
              reset();
            }}
          >
            <option value="">{t("inventory.import.noProfile")}</option>
            {profiles.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.gouvernorat_code === null ? ` (${t("inventory.import.shared")})` : ""}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="actions">
        <button type="button" className="btn btn--primary" disabled={!file || tooLarge || needsPlace || check.isPending} onClick={() => file && check.mutate(file)}>
          {t("inventory.import.check")}
        </button>
      </div>
      {(check.isError || apply.isError || template.isError) && (
        <p role="alert" className="alert alert--error">
          {t(errorMessageKey(check.error ?? apply.error ?? template.error))}
        </p>
      )}
      {preview && (
        <div aria-live="polite">
          {preview.applied && (
            <p role="status" className="alert alert--ok">
              {t("inventory.import.applied", { gouvernorat: nameOf(preview.gouvernorat_code) })}
            </p>
          )}
          {!preview.applied && (
            <MappingPanel
              preview={preview}
              mapping={mapping}
              national={national}
              onChange={setMapping}
              onRecheck={() => file && check.mutate(file)}
              busy={check.isPending}
            />
          )}
          <ProblemItems title={t("inventory.import.errors")} items={preview.errors} tone="error" />
          <ProblemItems title={t("inventory.import.warnings")} items={preview.warnings} tone="warning" />
          <table className="table inventory-table">
            <caption>{t("inventory.import.summary", { gouvernorat: nameOf(preview.gouvernorat_code), format: preview.format.toUpperCase() })}</caption>
            <thead>
              <tr>
                <th scope="col">{t("inventory.import.what")}</th>
                <th scope="col">{t("inventory.import.new")}</th>
                <th scope="col">{t("inventory.import.changed")}</th>
                <th scope="col">{t("inventory.import.unchanged")}</th>
              </tr>
            </thead>
            <tbody>
              {(["vehicles", "stock", "agents"] as const).map((k) => (
                <tr key={k}>
                  <th scope="row">{t(`inventory.import.sheet.${k}`)}</th>
                  <td className="num">{fmt.number(preview[k].new)}</td>
                  <td className="num">{fmt.number(preview[k].changed)}</td>
                  <td className="num">{fmt.number(preview[k].unchanged)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!preview.applied && preview.errors.length > 0 && <p className="muted">{t("inventory.import.fixFirst")}</p>}
          {!blocked && (
            <form
              noValidate
              className="actions"
              onSubmit={(e) => {
                e.preventDefault();
                if (file && reason.trim().length >= 5) apply.mutate(file);
              }}
            >
              <div className="field">
                <label htmlFor={`${id}-reason`}>{t("inventory.form.reason")}</label>
                <input id={`${id}-reason`} dir="auto" maxLength={500} aria-required="true" value={reason} onChange={(e) => setReason(e.target.value)} />
              </div>
              <button type="submit" className="btn btn--primary" disabled={reason.trim().length < 5 || apply.isPending}>
                {t("inventory.import.apply")}
              </button>
            </form>
          )}
        </div>
      )}
    </section>
  );
}

/**
 * R4b: the columns of the file that match no field of the register, each with a list of the fields (no typing), then
 * a new preview with this mapping and, if wanted, the mapping kept by name for the next file.
 */
function MappingPanel({
  preview,
  mapping,
  national,
  onChange,
  onRecheck,
  busy,
}: {
  preview: InventoryImport;
  mapping: ColumnMapping;
  national: boolean;
  onChange: (m: ColumnMapping) => void;
  onRecheck: () => void;
  busy: boolean;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [name, setName] = useState("");
  const [shared, setShared] = useState(false);
  const save = useMutation({
    mutationFn: () => api.saveImportProfile({ name: name.trim(), mapping, shared: national && shared }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: inventoryKeys.profiles }),
  });
  const sheets = (["vehicles", "stock", "agents"] as const).filter(
    (e) => (preview.unknown[e]?.length ?? 0) > 0 || Object.keys(mapping[e] ?? {}).length > 0,
  );
  if (sheets.length === 0) return null;
  const pick = (entity: Entity, heading: string, field: string) => {
    const pairs = Object.fromEntries(Object.entries(mapping[entity] ?? {}).filter(([h]) => h !== heading));
    onChange({ ...mapping, [entity]: field ? { ...pairs, [heading]: field } : pairs });
  };
  const mapped = Object.values(mapping).some((p) => Object.keys(p).length > 0);
  return (
    <section className="inventory-mapping" aria-labelledby={`${id}-t`}>
      <h3 id={`${id}-t`}>{t("inventory.import.mapping.title")}</h3>
      <p className="muted">{t("inventory.import.mapping.intro")}</p>
      {sheets.map((entity) => {
        const pairs = mapping[entity] ?? {};
        const columns = [...new Set([...(preview.unknown[entity] ?? []), ...Object.keys(pairs)])];
        const taken = new Set(Object.values(pairs));
        return (
          <table key={entity} className="table inventory-table">
            <caption>{t(`inventory.import.sheet.${entity}`)}</caption>
            <thead>
              <tr>
                <th scope="col">{t("inventory.import.mapping.column")}</th>
                <th scope="col">{t("inventory.import.mapping.field")}</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((heading, n) => (
                <tr key={heading}>
                  <th scope="row" dir="auto" id={`${id}-${entity}-${n}`}>
                    {heading}
                  </th>
                  <td>
                    <select
                      aria-labelledby={`${id}-${entity}-${n}`}
                      value={pairs[heading] ?? ""}
                      onChange={(e) => pick(entity, heading, e.target.value)}
                    >
                      <option value="">{t("inventory.import.mapping.none")}</option>
                      {(preview.fields[entity] ?? []).map((f) => (
                        <option key={f} value={f} disabled={taken.has(f) && pairs[heading] !== f}>
                          {t(`inventory.import.fieldName.${f}`, { defaultValue: f })}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        );
      })}
      <div className="actions">
        <button type="button" className="btn btn--primary" disabled={!mapped || busy} onClick={onRecheck}>
          {t("inventory.import.mapping.recheck")}
        </button>
      </div>
      {mapped && (
        <form
          noValidate
          className="actions"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim().length >= 2) save.mutate();
          }}
        >
          <div className="field">
            <label htmlFor={`${id}-name`}>{t("inventory.import.mapping.saveAs")}</label>
            <input id={`${id}-name`} dir="auto" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          {national && (
            <label className="checkbox">
              <input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} />
              {t("inventory.import.mapping.share")}
            </label>
          )}
          <button type="submit" className="btn" disabled={name.trim().length < 2 || save.isPending}>
            {t("inventory.import.mapping.save")}
          </button>
        </form>
      )}
      {save.isSuccess && (
        <p role="status" className="alert alert--ok">
          {t("inventory.import.mapping.saved", { name: save.data.name })}
        </p>
      )}
      {save.isError && (
        <p role="alert" className="alert alert--error">
          {t(errorMessageKey(save.error))}
        </p>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- catalogue

const STANDARD_SPECS: SpecDef[] = [
  { key: "capacity_l", unit: "L", type: "number", name: { ar: "السعة", fr: "Capacité", en: "Capacity" } },
  { key: "flow_lpm", unit: "L/min", type: "number", name: { ar: "الصبيب", fr: "Débit", en: "Flow" } },
  { key: "length_m", unit: "m", type: "number", name: { ar: "الطول", fr: "Longueur", en: "Length" } },
  { key: "seats", unit: "", type: "number", name: { ar: "عدد الأشخاص", fr: "Places", en: "Seats" } },
  { key: "power_kva", unit: "kVA", type: "number", name: { ar: "القدرة", fr: "Puissance", en: "Power" } },
  { key: "four_wd", unit: "", type: "bool", name: { ar: "دفع رباعي", fr: "4x4", en: "Four-wheel drive" } },
];

function CategoryForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const lang = useLanguage();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [kind, setKind] = useState<CategoryKind>("vehicle");
  const [family, setFamily] = useState<Family>("vehicles");
  const [name, setName] = useState<Names>({ ar: "", fr: "", en: "" });
  const [key, setKey] = useState("");
  const [specs, setSpecs] = useState<string[]>([]);
  const [levels, setLevels] = useState(0);
  const [tried, setTried] = useState(false);
  const missing = !/^[a-z][a-z0-9_]{1,39}$/.test(key) || (["ar", "fr", "en"] as const).some((l) => name[l].trim() === "");
  const mutation = useMutation({
    mutationFn: () =>
      api.createCategory({
        key,
        kind,
        family: kind === "skill" ? null : family,
        name: { ar: name.ar.trim(), fr: name.fr.trim(), en: name.en.trim() },
        specs: kind === "skill" ? [] : STANDARD_SPECS.filter((s) => specs.includes(s.key)),
        levels: kind === "skill" ? levels : 0,
        position: 500,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: inventoryKeys.all });
      onDone();
    },
  });
  return (
    <form
      noValidate
      className="card inventory-form"
      aria-labelledby={`${id}-title`}
      onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (!missing) mutation.mutate();
      }}
    >
      <h3 id={`${id}-title`}>{t("inventory.catalogue.newTitle")}</h3>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-kind`}>{t("inventory.catalogue.kind")}</label>
          <select id={`${id}-kind`} value={kind} onChange={(e) => setKind(e.target.value as CategoryKind)}>
            {(["vehicle", "equipment", "skill"] as const).map((k) => (
              <option key={k} value={k}>
                {t(`inventory.kind.${k}`)}
              </option>
            ))}
          </select>
        </div>
        {kind !== "skill" && (
          <div className="field">
            <label htmlFor={`${id}-family`}>{t("inventory.catalogue.family")}</label>
            <select id={`${id}-family`} value={family} onChange={(e) => setFamily(e.target.value as Family)}>
              {FAMILIES.map((f) => (
                <option key={f} value={f}>
                  {t(`inventory.family.${f}`)}
                </option>
              ))}
            </select>
          </div>
        )}
        {(["ar", "fr", "en"] as const).map((l) => (
          <div className="field" key={l}>
            <label htmlFor={`${id}-${l}`}>{t(`layers.form.name_${l}`)}</label>
            <input
              id={`${id}-${l}`}
              lang={l}
              dir={l === "ar" ? "rtl" : "ltr"}
              maxLength={100}
              aria-required="true"
              value={name[l]}
              onChange={(e) => {
                setName({ ...name, [l]: e.target.value });
                if (l === "en") setKey(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40));
              }}
            />
          </div>
        ))}
        <div className="field">
          <label htmlFor={`${id}-key`}>{t("inventory.catalogue.key")}</label>
          <input id={`${id}-key`} dir="ltr" maxLength={40} aria-required="true" value={key} onChange={(e) => setKey(e.target.value)} />
        </div>
        {kind === "skill" && (
          <div className="field">
            <label htmlFor={`${id}-levels`}>{t("inventory.catalogue.levels")}</label>
            <Stepper id={`${id}-levels`} min={0} max={5} value={levels} label={t("inventory.catalogue.levels")} onChange={setLevels} />
          </div>
        )}
      </div>
      {kind !== "skill" && (
        <fieldset className="layer-groups">
          <legend>{t("inventory.field.specs")}</legend>
          {STANDARD_SPECS.map((s) => (
            <label key={s.key} className="chip-toggle">
              <input type="checkbox" checked={specs.includes(s.key)} onChange={() => setSpecs((x) => (x.includes(s.key) ? x.filter((k) => k !== s.key) : [...x, s.key]))} />
              <span>
                {s.name[lang]}
                {s.unit && ` (${s.unit})`}
              </span>
            </label>
          ))}
        </fieldset>
      )}
      {tried && missing && (
        <p className="alert alert--error" role="alert">
          {t("inventory.form.missing")}
        </p>
      )}
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {t("aiSettings.save")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

function CatalogueTab({ catalogue, canManage }: { catalogue: Category[]; canManage: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const lang = useLanguage();
  const [creating, setCreating] = useState(false);
  const toggle = useMutation({
    mutationFn: (c: Category) => api.updateCategory(c.key, { active: !c.active }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: inventoryKeys.all }),
  });
  return (
    <>
      <p className="muted">{t("inventory.catalogue.intro")}</p>
      {canManage && !creating && (
        <div className="actions">
          <button type="button" className="btn" onClick={() => setCreating(true)}>
            {t("inventory.catalogue.newTitle")}
          </button>
        </div>
      )}
      {creating && <CategoryForm onDone={() => setCreating(false)} />}
      {toggle.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(toggle.error))}
        </p>
      )}
      {(["vehicle", "equipment", "skill"] as const).map((kind) => (
        <div className="table-wrap" key={kind}>
          <table className="table inventory-table">
            <caption>{t(`inventory.kind.${kind}`)}</caption>
            <thead>
              <tr>
                <th scope="col">{t("inventory.field.type")}</th>
                <th scope="col">{kind === "skill" ? t("inventory.catalogue.levels") : t("inventory.field.specs")}</th>
                <th scope="col">{t("inventory.catalogue.state")}</th>
                {canManage && (
                  <th scope="col">
                    <span className="visually-hidden">{t("inventory.actions")}</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {catalogue
                .filter((c) => c.kind === kind)
                .map((c) => (
                  <tr key={c.key}>
                    <th scope="row">
                      {categoryName(c, lang)}
                      {c.family && <span className="muted"> · {t(`inventory.family.${c.family}`)}</span>}
                    </th>
                    <td>
                      {kind === "skill"
                        ? c.levels > 0
                          ? t("inventory.catalogue.levelsOf", { n: c.levels })
                          : "—"
                        : c.specs.map((s) => `${s.name[lang]}${s.unit ? ` (${s.unit})` : ""}`).join(t("common.listSeparator")) || "—"}
                    </td>
                    <td>
                      <span className={`pill ${c.active ? "tone-green" : "tone-slate"}`}>
                        {t(c.active ? "inventory.catalogue.active" : "inventory.catalogue.inactive")}
                      </span>
                    </td>
                    {canManage && (
                      <td>
                        <button type="button" className="btn btn--small" disabled={toggle.isPending} onClick={() => toggle.mutate(c)}>
                          {t(c.active ? "inventory.catalogue.switchOff" : "inventory.catalogue.switchOn", { name: categoryName(c, lang) })}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      ))}
    </>
  );
}

// ---------------------------------------------------------------- page

export function InventoryPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const national = Boolean(user?.identity.national);
  const [tab, setTab] = useState<Tab>("overview");
  const [gouvernorat, setGouvernorat] = useState<number | null>(null);
  const catalogue = useCatalogue();
  const overview = useQuery({ queryKey: inventoryKeys.overview, queryFn: ({ signal }) => api.inventoryOverview(signal) });
  const lists = Boolean(overview.data?.can_list);
  const units = useQuery({
    queryKey: inventoryKeys.units(gouvernorat),
    queryFn: ({ signal }) => api.inventoryUnits(gouvernorat, signal),
    enabled: lists,
  });
  const q: ListQuery = { gouvernorat, unit: null, category: null };
  const shown = lists ? TABS : (["overview", "search"] as const);
  const unitRows = units.data?.items ?? [];
  return (
    <div className="page inventory-page">
      <div className="page__head">
        <PageTitle icon="inventory2" tone="teal">
          {t("inventory.title")}
        </PageTitle>
      </div>
      <p className="muted">{t(national ? "inventory.introCentral" : "inventory.introRegional")}</p>
      {overview.isPending && <Loading />}
      {overview.isError && <ErrorBox error={overview.error} onRetry={() => void overview.refetch()} />}
      {overview.data && (
        <>
          {shown.length > 1 && (
            <div role="tablist" aria-label={t("inventory.tabs.label")} className="tabs">
              {shown.map((k) => (
                <button
                  key={k}
                  type="button"
                  role="tab"
                  aria-selected={tab === k}
                  className={`tabs__tab${tab === k ? " tabs__tab--active" : ""}`}
                  onClick={() => setTab(k)}
                >
                  {t(`inventory.tabs.${k}`)}
                </button>
              ))}
            </div>
          )}
          {national && lists && ["units", "vehicles", "stock", "agents"].includes(tab) && (
            <div className="filters__row">
              <GouvernoratPicker value={gouvernorat} onChange={setGouvernorat} any={t("inventory.allGouvernorats")} />
            </div>
          )}
          {tab === "overview" && <OverviewTab data={overview.data} categories={catalogue.byKey} />}
          {tab === "search" && <SearchTab catalogue={catalogue.items} national={national} />}
          {lists && tab === "units" && <UnitsTab units={unitRows} />}
          {lists && tab === "vehicles" && <VehiclesTab q={q} units={unitRows} catalogue={catalogue} />}
          {lists && tab === "stock" && <StockTab q={q} units={unitRows} catalogue={catalogue} />}
          {lists && tab === "agents" && <AgentsTab q={q} units={unitRows} catalogue={catalogue} />}
          {lists && tab === "import" && (overview.data.can_edit ? <ImportTab national={national} gouvernorat={gouvernorat} /> : <p className="muted">{t("inventory.import.editorsOnly")}</p>)}
          {lists && tab === "catalogue" && <CatalogueTab catalogue={catalogue.items} canManage={Boolean(catalogue.query.data?.can_manage)} />}
        </>
      )}
    </div>
  );
}
