import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { opsKeys } from "../lib/opsApi";
import {
  RESOURCE_KINDS,
  RESOURCE_STATUSES,
  UNIT_KINDS,
  type Resource,
  type ResourceBody,
  type ResourceFilters,
  type ResourceKind,
  type ResourceStatus,
  type Unit,
  type UnitBody,
  type UnitKind,
} from "../lib/opsTypes";
import { canManageResources } from "../lib/roles";
import type { Language } from "../i18n";
import { localizedName } from "../lib/localized";
import { PageTitle } from "../components/PageTitle";

const LAT = { min: 30, max: 37.6 };
const LON = { min: 7.4, max: 11.7 };

export function ResourceStatusChip({ status }: { status: ResourceStatus }) {
  const { t } = useTranslation();
  return <span className={`chip chip--resource-${status}`}>{t(`resources.status.${status}`)}</span>;
}

function unitName(unit: Pick<Unit, "name_ar" | "name_fr">, lang: Language): string {
  return localizedName(unit, lang);
}

function parseCoord(raw: string, range: { min: number; max: number }): number | null {
  if (!raw.trim()) return null;
  // French users type a decimal comma.
  const n = Number(raw.trim().replace(",", "."));
  return Number.isFinite(n) && n >= range.min && n <= range.max ? n : Number.NaN;
}

/** Two-step delete button (no browser dialog): the first click asks, the second confirms. */
function DeleteButton({ label, onConfirm, pending }: { label: string; onConfirm: () => void; pending: boolean }) {
  const { t } = useTranslation();
  const [asking, setAsking] = useState(false);
  if (!asking)
    return (
      <button type="button" className="btn btn--small" onClick={() => setAsking(true)} aria-label={label}>
        {t("resources.delete")}
      </button>
    );
  return (
    <span className="ops-row-actions">
      <button type="button" className="btn btn--small btn--primary" disabled={pending} onClick={onConfirm}>
        {t("resources.confirmDelete")}
      </button>
      <button type="button" className="btn btn--small" onClick={() => setAsking(false)}>
        {t("common.cancel")}
      </button>
    </span>
  );
}

// ---------------------------------------------------------------- summary

function Summary() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const query = useQuery({ queryKey: opsKeys.resourceSummary, queryFn: ({ signal }) => api.resourceSummary(signal) });
  if (query.isPending) return <Loading />;
  if (query.isError) return <ErrorBox error={query.error} onRetry={() => void query.refetch()} />;
  const kinds = RESOURCE_KINDS.filter((k) => query.data.by_kind[k]);
  if (kinds.length === 0) return <p className="muted">{t("resources.summary.empty")}</p>;
  return (
    <div className="table-wrap">
      <table className="table">
        <caption className="visually-hidden">{t("resources.summary.caption")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("resources.columns.kind")}</th>
            {RESOURCE_STATUSES.map((s) => (
              <th key={s} scope="col" className="num">
                {t(`resources.status.${s}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {kinds.map((k) => (
            <tr key={k}>
              <th scope="row">{t(`resources.kind.${k}`)}</th>
              {RESOURCE_STATUSES.map((s) => (
                <td key={s} className="num">
                  {fmt.number(query.data.by_kind[k]?.[s] ?? 0)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------- resource form

function ResourceForm({ units, resource, onDone }: { units: Unit[]; resource: Resource | null; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const qc = useQueryClient();
  const ids = { unit: useId(), kind: useId(), label: useId(), status: useId(), notes: useId(), lat: useId(), lon: useId() };
  const [unitId, setUnitId] = useState(resource?.unit_id ?? units[0]?.id ?? "");
  const [kind, setKind] = useState<ResourceKind>(resource?.kind ?? "fire_engine");
  const [label, setLabel] = useState(resource?.label ?? "");
  const [status, setStatus] = useState<"available" | "out_of_service">(
    resource?.status === "out_of_service" ? "out_of_service" : "available",
  );
  const [notes, setNotes] = useState(resource?.notes ?? "");
  const [lat, setLat] = useState(resource?.location ? String(resource.location.lat) : "");
  const [lon, setLon] = useState(resource?.location ? String(resource.location.lon) : "");
  const [invalid, setInvalid] = useState(false);
  const assigned = resource?.status === "assigned";

  const mutation = useMutation({
    mutationFn: (body: ResourceBody) => (resource ? api.updateResource(resource.id, body) : api.createResource(body)),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: opsKeys.resourcesAll });
      void qc.invalidateQueries({ queryKey: opsKeys.resourceSummary });
      void qc.invalidateQueries({ queryKey: opsKeys.units });
      onDone();
    },
  });

  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const la = parseCoord(lat, LAT);
    const lo = parseCoord(lon, LON);
    const badCoords = Number.isNaN(la) || Number.isNaN(lo) || (la === null) !== (lo === null);
    if (!unitId || !label.trim() || badCoords) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    mutation.mutate({
      unit_id: unitId,
      kind,
      label: label.trim(),
      // An assigned resource keeps its status: the server frees it when the assignment ends.
      status: assigned ? "available" : status,
      notes: notes.trim() || null,
      location: la !== null && lo !== null ? { lat: la, lon: lo } : null,
      version: resource?.version,
    });
  };

  return (
    <form
      className="ops-form card"
      onSubmit={submit}
      noValidate
      aria-label={resource ? t("resources.form.editTitle", { label: resource.label }) : t("resources.form.newTitle")}
    >
      <h3>{resource ? t("resources.form.editTitle", { label: resource.label }) : t("resources.form.newTitle")}</h3>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={ids.unit}>{t("resources.columns.unit")}</label>
          <select id={ids.unit} value={unitId} disabled={assigned} onChange={(e) => setUnitId(e.target.value)} required>
            {units.map((u) => (
              <option key={u.id} value={u.id}>
                {unitName(u, lang)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.kind}>{t("resources.columns.kind")}</label>
          <select id={ids.kind} value={kind} onChange={(e) => setKind(e.target.value as ResourceKind)}>
            {RESOURCE_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`resources.kind.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className={`field${invalid && !label.trim() ? " field--invalid" : ""}`}>
          <label htmlFor={ids.label}>{t("resources.columns.label")}</label>
          <input
            id={ids.label}
            value={label}
            maxLength={60}
            dir="ltr"
            required
            aria-invalid={(invalid && !label.trim()) || undefined}
            onChange={(e) => setLabel(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor={ids.status}>{t("resources.columns.status")}</label>
          <select
            id={ids.status}
            value={assigned ? "assigned" : status}
            disabled={assigned}
            onChange={(e) => setStatus(e.target.value as "available" | "out_of_service")}
          >
            {assigned && <option value="assigned">{t("resources.status.assigned")}</option>}
            <option value="available">{t("resources.status.available")}</option>
            <option value="out_of_service">{t("resources.status.out_of_service")}</option>
          </select>
        </div>
      </div>
      <div className="filters__row">
        <div className="field field--number">
          <label htmlFor={ids.lat}>{t("resources.form.lat")}</label>
          <input id={ids.lat} inputMode="decimal" dir="ltr" value={lat} onChange={(e) => setLat(e.target.value)} />
        </div>
        <div className="field field--number">
          <label htmlFor={ids.lon}>{t("resources.form.lon")}</label>
          <input id={ids.lon} inputMode="decimal" dir="ltr" value={lon} onChange={(e) => setLon(e.target.value)} />
        </div>
      </div>
      <p className="muted">{t("resources.form.locationHelp")}</p>
      <div className="field">
        <label htmlFor={ids.notes}>{t("resources.columns.notes")}</label>
        <textarea id={ids.notes} value={notes} maxLength={500} rows={2} dir="auto" onChange={(e) => setNotes(e.target.value)} />
      </div>
      {invalid && (
        <p className="alert alert--error" role="alert">
          {t("resources.form.invalid")}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {mutation.isPending ? t("ops.working") : t("resources.form.save")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </form>
  );
}

// ---------------------------------------------------------------- resources list

function ResourcesList({ units, canManage, national }: { units: Unit[]; canManage: boolean; national: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const qc = useQueryClient();
  const gouvernorats = useGouvernorats();
  const ids = { status: useId(), kind: useId(), unit: useId(), gouv: useId() };
  const [filters, setFilters] = useState<ResourceFilters>({ status: "", kind: "", unit_id: "", gouvernorat_code: null });
  const [editing, setEditing] = useState<Resource | "new" | null>(null);

  const query = useInfiniteQuery({
    queryKey: [...opsKeys.resources(filters), "list"],
    queryFn: ({ pageParam, signal }) => api.resources(filters, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteResource(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: opsKeys.resourcesAll });
      void qc.invalidateQueries({ queryKey: opsKeys.resourceSummary });
      void qc.invalidateQueries({ queryKey: opsKeys.units });
    },
  });
  const patch = (p: Partial<ResourceFilters>) => setFilters((f) => ({ ...f, ...p }));
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <section className="card" aria-labelledby="sec-resources">
      <div className="page__head">
        <h2 id="sec-resources">{t("resources.listTitle")}</h2>
        {canManage && units.length > 0 && editing === null && (
          <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
            {t("resources.add")}
          </button>
        )}
      </div>
      {canManage && units.length === 0 && <p className="muted">{t("resources.needUnit")}</p>}
      {editing !== null && (
        <ResourceForm
          key={editing === "new" ? "new" : editing.id}
          units={units}
          resource={editing === "new" ? null : editing}
          onDone={() => setEditing(null)}
        />
      )}
      <div className="filters__row" role="group" aria-label={t("resources.filters")}>
        <div className="field">
          <label htmlFor={ids.status}>{t("resources.columns.status")}</label>
          <select
            id={ids.status}
            value={filters.status ?? ""}
            onChange={(e) => patch({ status: e.target.value as ResourceFilters["status"] })}
          >
            <option value="">{t("resources.any")}</option>
            {RESOURCE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`resources.status.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.kind}>{t("resources.columns.kind")}</label>
          <select
            id={ids.kind}
            value={filters.kind ?? ""}
            onChange={(e) => patch({ kind: e.target.value as ResourceFilters["kind"] })}
          >
            <option value="">{t("resources.any")}</option>
            {RESOURCE_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`resources.kind.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.unit}>{t("resources.columns.unit")}</label>
          <select id={ids.unit} value={filters.unit_id ?? ""} onChange={(e) => patch({ unit_id: e.target.value })}>
            <option value="">{t("resources.any")}</option>
            {units.map((u) => (
              <option key={u.id} value={u.id}>
                {unitName(u, lang)}
              </option>
            ))}
          </select>
        </div>
        {national && (
          <div className="field">
            <label htmlFor={ids.gouv}>{t("filters.gouvernorat")}</label>
            <select
              id={ids.gouv}
              value={filters.gouvernorat_code ?? ""}
              onChange={(e) => patch({ gouvernorat_code: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">{t("filters.allGouvernorats")}</option>
              {gouvernorats.list.map((g) => (
                <option key={g.code} value={g.code}>
                  {gouvernorats.nameOf(g.code)}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="empty">{t("resources.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("resources.listTitle")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("resources.columns.label")}</th>
                <th scope="col">{t("resources.columns.kind")}</th>
                <th scope="col">{t("resources.columns.unit")}</th>
                <th scope="col">{t("resources.columns.status")}</th>
                <th scope="col">{t("resources.columns.notes")}</th>
                {canManage && <th scope="col">{t("resources.columns.actions")}</th>}
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id}>
                  <td className="code" dir="ltr">
                    {r.label}
                  </td>
                  <td>{t(`resources.kind.${r.kind}`)}</td>
                  <td dir="auto">{r.unit_name}</td>
                  <td>
                    <ResourceStatusChip status={r.status} />
                    {r.assignment && (
                      <div className="cell-sub">
                        <Link to={`/incidents/${encodeURIComponent(r.assignment.incident_id)}`}>
                          {t("resources.openIncident")}
                        </Link>
                      </div>
                    )}
                  </td>
                  <td dir="auto">{r.notes ?? "—"}</td>
                  {canManage && (
                    <td>
                      <span className="ops-row-actions">
                        <button
                          type="button"
                          className="btn btn--small"
                          onClick={() => setEditing(r)}
                          aria-label={t("resources.editLabel", { label: r.label })}
                        >
                          {t("resources.edit")}
                        </button>
                        <DeleteButton
                          label={t("resources.deleteLabel", { label: r.label })}
                          pending={remove.isPending}
                          onConfirm={() => remove.mutate(r.id)}
                        />
                      </span>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {remove.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(remove.error))}
        </p>
      )}
      {query.hasNextPage && (
        <div className="load-more">
          <button
            type="button"
            className="btn"
            onClick={() => void query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
          >
            {query.isFetchingNextPage ? t("common.loading") : t("reports.loadMore")}
          </button>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- units

function UnitForm({ unit, onDone }: { unit: Unit | null; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const national = user?.identity.national ?? false;
  const own = user?.identity.gouvernoratCode ?? null;
  const ids = { ar: useId(), fr: useId(), kind: useId(), gouv: useId(), lat: useId(), lon: useId(), phone: useId() };
  const [nameAr, setNameAr] = useState(unit?.name_ar ?? "");
  const [nameFr, setNameFr] = useState(unit?.name_fr ?? "");
  const [kind, setKind] = useState<UnitKind>(unit?.kind ?? "unit");
  const [gouv, setGouv] = useState<number | null>(unit?.gouvernorat_code ?? own);
  const [lat, setLat] = useState(unit ? String(unit.location.lat) : "");
  const [lon, setLon] = useState(unit ? String(unit.location.lon) : "");
  const [phone, setPhone] = useState(unit?.phone ?? "");
  const [invalid, setInvalid] = useState(false);
  const mutation = useMutation({
    mutationFn: (body: UnitBody) => (unit ? api.updateUnit(unit.id, body) : api.createUnit(body)),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: opsKeys.units });
      void qc.invalidateQueries({ queryKey: opsKeys.resourcesAll });
      onDone();
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const la = parseCoord(lat, LAT);
    const lo = parseCoord(lon, LON);
    if (nameAr.trim().length < 2 || nameFr.trim().length < 2 || gouv === null || la === null || lo === null || Number.isNaN(la) || Number.isNaN(lo)) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    mutation.mutate({
      name_ar: nameAr.trim(),
      name_fr: nameFr.trim(),
      kind,
      gouvernorat_code: gouv,
      location: { lat: la, lon: lo },
      phone: phone.trim() || null,
      version: unit?.version,
    });
  };
  const title = unit ? t("resources.units.editTitle") : t("resources.units.newTitle");
  return (
    <form className="ops-form card" onSubmit={submit} noValidate aria-label={title}>
      <h3>{title}</h3>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={ids.ar}>{t("resources.units.nameAr")}</label>
          <input id={ids.ar} lang="ar" dir="rtl" value={nameAr} maxLength={150} onChange={(e) => setNameAr(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={ids.fr}>{t("resources.units.nameFr")}</label>
          <input id={ids.fr} lang="fr" dir="ltr" value={nameFr} maxLength={150} onChange={(e) => setNameFr(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={ids.kind}>{t("resources.units.kindLabel")}</label>
          <select id={ids.kind} value={kind} onChange={(e) => setKind(e.target.value as UnitKind)}>
            {UNIT_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`resources.units.kind.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={ids.gouv}>{t("filters.gouvernorat")}</label>
          <select
            id={ids.gouv}
            value={gouv ?? ""}
            disabled={!national}
            onChange={(e) => setGouv(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t("resources.units.chooseGouvernorat")}</option>
            {gouvernorats.list.map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="filters__row">
        <div className="field field--number">
          <label htmlFor={ids.lat}>{t("resources.form.lat")}</label>
          <input id={ids.lat} inputMode="decimal" dir="ltr" value={lat} onChange={(e) => setLat(e.target.value)} />
        </div>
        <div className="field field--number">
          <label htmlFor={ids.lon}>{t("resources.form.lon")}</label>
          <input id={ids.lon} inputMode="decimal" dir="ltr" value={lon} onChange={(e) => setLon(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={ids.phone}>{t("resources.units.phone")}</label>
          <input id={ids.phone} type="tel" dir="ltr" value={phone} maxLength={20} onChange={(e) => setPhone(e.target.value)} />
        </div>
      </div>
      {invalid && (
        <p className="alert alert--error" role="alert">
          {t("resources.units.invalid")}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {mutation.isPending ? t("ops.working") : t("resources.form.save")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </form>
  );
}

function UnitsSection({ units, canManage }: { units: Unit[]; canManage: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Unit | "new" | null>(null);
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteUnit(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: opsKeys.units }),
  });
  return (
    <section className="card" aria-labelledby="sec-units">
      <div className="page__head">
        <h2 id="sec-units">{t("resources.units.title")}</h2>
        {canManage && editing === null && (
          <button type="button" className="btn" onClick={() => setEditing("new")}>
            {t("resources.units.add")}
          </button>
        )}
      </div>
      {editing !== null && (
        <UnitForm key={editing === "new" ? "new" : editing.id} unit={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
      )}
      {units.length === 0 ? (
        <p className="muted">{t("resources.units.empty")}</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("resources.units.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("resources.units.name")}</th>
                <th scope="col">{t("resources.units.kindLabel")}</th>
                <th scope="col">{t("filters.gouvernorat")}</th>
                <th scope="col">{t("resources.units.phone")}</th>
                <th scope="col" className="num">
                  {t("resources.units.resources")}
                </th>
                {canManage && <th scope="col">{t("resources.columns.actions")}</th>}
              </tr>
            </thead>
            <tbody>
              {units.map((u) => (
                <tr key={u.id}>
                  <td dir="auto">{unitName(u, lang)}</td>
                  <td>{t(`resources.units.kind.${u.kind}`)}</td>
                  <td>{gouvernorats.nameOf(u.gouvernorat_code)}</td>
                  <td dir="ltr">{u.phone ? <a href={`tel:${u.phone}`}>{u.phone}</a> : "—"}</td>
                  <td className="num">{fmt.number(u.resources)}</td>
                  {canManage && (
                    <td>
                      <span className="ops-row-actions">
                        <button
                          type="button"
                          className="btn btn--small"
                          onClick={() => setEditing(u)}
                          aria-label={t("resources.editLabel", { label: unitName(u, lang) })}
                        >
                          {t("resources.edit")}
                        </button>
                        <DeleteButton
                          label={t("resources.deleteLabel", { label: unitName(u, lang) })}
                          pending={remove.isPending}
                          onConfirm={() => remove.mutate(u.id)}
                        />
                      </span>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {remove.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(remove.error))}
        </p>
      )}
    </section>
  );
}

/** FR-C-09, FR-C-10: units and resources in the user's scope (managed by ops_manager and sysadmin). */
export function ResourcesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const canManage = canManageResources(user?.identity.roles ?? []);
  const national = user?.identity.national ?? false;
  const units = useQuery({ queryKey: opsKeys.units, queryFn: ({ signal }) => api.units(signal) });
  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="localShipping" tone="amber">{t("resources.title")}</PageTitle>
      </div>
      <p className="muted">{t("resources.intro")}</p>
      <section className="card" aria-labelledby="sec-summary">
        <h2 id="sec-summary">{t("resources.summary.title")}</h2>
        <Summary />
      </section>
      {units.isPending && <Loading />}
      {units.isError && <ErrorBox error={units.error} onRetry={() => void units.refetch()} />}
      {units.isSuccess && (
        <>
          <ResourcesList units={units.data} canManage={canManage} national={national} />
          <UnitsSection units={units.data} canManage={canManage} />
        </>
      )}
    </div>
  );
}
