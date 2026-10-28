// covers: phase R1 (docs/phase-r/design-resources.md §2.2): recording a vehicle with its specifications, a line of
// equipment counted by quantity and a member of staff with their specialities, deleting with a reason, and the
// versions of each entry.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type ReactNode, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Stepper } from "./Stepper";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import {
  AVAILABILITY,
  inventoryKeys,
  specStep,
  WRITABLE_STATES,
  type Agent,
  type Availability,
  type Category,
  type Names,
  type Skill,
  type SpecValue,
  type StockLine,
  type Transfer,
  type UnitRow,
  type Vehicle,
  type WritableState,
} from "../lib/inventory";

const MIN_REASON = 5;

export function categoryName(c: Category | undefined, lang: string, fallback = "—"): string {
  return c ? c.name[lang as keyof Names] || c.name.ar : fallback;
}

function useSaved(onDone: () => void) {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: inventoryKeys.all });
    onDone();
  };
}

function Field({ id, label, help, children }: { id: string; label: string; help?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {help && (
        <p id={`${id}-help`} className="muted">
          {help}
        </p>
      )}
    </div>
  );
}

function UnitSelect({ id, units, value, onChange }: { id: string; units: UnitRow[]; value: string; onChange: (v: string) => void }) {
  const { t } = useTranslation();
  const lang = useLanguage();
  return (
    <select id={id} aria-required="true" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{t("inventory.form.pickUnit")}</option>
      {units
        .filter((u) => u.can_edit)
        .map((u) => (
          <option key={u.id} value={u.id}>
            {lang === "ar" ? u.name_ar : u.name_fr}
          </option>
        ))}
    </select>
  );
}

function CategorySelect({
  id,
  categories,
  value,
  onChange,
}: {
  id: string;
  categories: Category[];
  value: string;
  onChange: (v: string) => void;
}) {
  const { t } = useTranslation();
  const lang = useLanguage();
  return (
    <select id={id} aria-required="true" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{t("inventory.form.pickType")}</option>
      {categories
        .filter((c) => c.active || c.key === value)
        .map((c) => (
          <option key={c.key} value={c.key}>
            {categoryName(c, lang)}
          </option>
        ))}
    </select>
  );
}

/** The specification fields of a catalogue type (capacity in litres, four-wheel drive...). */
function SpecFields({
  id,
  category,
  specs,
  onChange,
}: {
  id: string;
  category: Category | undefined;
  specs: Record<string, SpecValue>;
  onChange: (specs: Record<string, SpecValue>) => void;
}) {
  const lang = useLanguage();
  if (!category || category.specs.length === 0) return null;
  return (
    <fieldset className="inventory-specs">
      <legend>{categoryName(category, lang)}</legend>
      {category.specs.map((d) =>
        d.type === "bool" ? (
          <label key={d.key} className="checkbox">
            <input
              type="checkbox"
              checked={specs[d.key] === true}
              onChange={(e) => onChange({ ...specs, [d.key]: e.target.checked })}
            />
            {d.name[lang]}
          </label>
        ) : (
          <div className="field" key={d.key}>
            <label htmlFor={`${id}-${d.key}`}>
              {d.name[lang]}
              {d.unit && <span className="muted"> ({d.unit})</span>}
            </label>
            <Stepper
              id={`${id}-${d.key}`}
              min={0}
              step={specStep(d.unit)}
              value={typeof specs[d.key] === "number" ? (specs[d.key] as number) : null}
              label={d.name[lang]}
              unit={d.unit || undefined}
              onChange={(n) => onChange({ ...specs, [d.key]: n })}
              onClear={() => {
                const { [d.key]: _old, ...rest } = specs;
                onChange(rest);
              }}
            />
          </div>
        ),
      )}
    </fieldset>
  );
}

function ReasonField({ id, value, onChange, required, tried }: { id: string; value: string; onChange: (v: string) => void; required: boolean; tried: boolean }) {
  const { t } = useTranslation();
  const invalid = tried && required && value.trim().length < MIN_REASON;
  return (
    <div className="field">
      <label htmlFor={id}>{t(required ? "inventory.form.reason" : "inventory.form.reasonOptional")}</label>
      <input
        id={id}
        dir="auto"
        maxLength={500}
        aria-required={required || undefined}
        aria-invalid={invalid || undefined}
        aria-describedby={`${id}-help`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <p id={`${id}-help`} className={invalid ? "field__error" : "muted"}>
        {t("inventory.form.reasonHelp")}
      </p>
    </div>
  );
}

function FormShell({
  title,
  onSubmit,
  pending,
  error,
  problem,
  onCancel,
  children,
}: {
  title: string;
  onSubmit: () => void;
  pending: boolean;
  error: unknown;
  problem: string | null;
  onCancel: () => void;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const id = useId();
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    onSubmit();
  };
  return (
    <form noValidate className="card inventory-form" aria-labelledby={`${id}-title`} onSubmit={submit}>
      <h3 id={`${id}-title`}>{title}</h3>
      {children}
      {problem && (
        <p className="alert alert--error" role="alert">
          {problem}
        </p>
      )}
      {error !== null && error !== undefined && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(error))}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={pending}>
          {pending ? t("aiSettings.saving") : t("aiSettings.save")}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------- vehicles

export function VehicleForm({
  vehicle,
  units,
  categories,
  onDone,
}: {
  vehicle: Vehicle | null;
  units: UnitRow[];
  categories: Category[];
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const saved = useSaved(onDone);
  const [unit, setUnit] = useState(vehicle?.unit_id ?? "");
  const [category, setCategory] = useState(vehicle?.category_key ?? "");
  const [label, setLabel] = useState(vehicle?.label ?? "");
  const [code, setCode] = useState(vehicle?.code ?? "");
  const [specs, setSpecs] = useState<Record<string, SpecValue>>(vehicle?.specs ?? {});
  const [state, setState] = useState<WritableState>(
    vehicle && vehicle.state !== "assigned" ? vehicle.state : "ready",
  );
  const [year, setYear] = useState(vehicle?.year ? String(vehicle.year) : "");
  const [notes, setNotes] = useState(vehicle?.notes ?? "");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const types = categories.filter((c) => c.kind === "vehicle");
  const current = types.find((c) => c.key === category);
  const missing = !unit || !category || label.trim() === "" || (vehicle !== null && reason.trim().length < MIN_REASON);
  const mutation = useMutation({
    mutationFn: () =>
      api.saveVehicle(vehicle?.id ?? null, {
        unit_id: unit,
        category_key: category,
        label: label.trim(),
        code: code.trim() || null,
        specs: Object.fromEntries(Object.entries(specs).filter(([k]) => current?.specs.some((d) => d.key === k))),
        state,
        year: year ? Number(year) : null,
        notes: notes.trim() || null,
        reason: reason.trim(),
        version: vehicle?.version,
      }),
    onSuccess: saved,
  });
  return (
    <FormShell
      title={vehicle ? t("inventory.vehicles.editTitle", { label: vehicle.label }) : t("inventory.vehicles.newTitle")}
      onSubmit={() => {
        setTried(true);
        if (!missing) mutation.mutate();
      }}
      pending={mutation.isPending}
      error={mutation.error}
      problem={tried && missing ? t("inventory.form.missing") : null}
      onCancel={onDone}
    >
      <div className="form-grid">
        <Field id={`${id}-unit`} label={t("inventory.field.unit")}>
          <UnitSelect id={`${id}-unit`} units={units} value={unit} onChange={setUnit} />
        </Field>
        <Field id={`${id}-type`} label={t("inventory.field.type")}>
          <CategorySelect id={`${id}-type`} categories={types} value={category} onChange={setCategory} />
        </Field>
        <Field id={`${id}-label`} label={t("inventory.field.label")}>
          <input id={`${id}-label`} dir="auto" maxLength={60} aria-required="true" value={label} onChange={(e) => setLabel(e.target.value)} />
        </Field>
        <Field id={`${id}-code`} label={t("inventory.field.code")}>
          <input id={`${id}-code`} dir="ltr" maxLength={40} value={code} onChange={(e) => setCode(e.target.value)} />
        </Field>
        <Field id={`${id}-state`} label={t("inventory.field.state")}>
          {vehicle?.state === "assigned" ? (
            <p id={`${id}-state`} className="muted">
              {t("inventory.vehicles.assignedNote")}
            </p>
          ) : (
            <select id={`${id}-state`} value={state} onChange={(e) => setState(e.target.value as WritableState)}>
              {WRITABLE_STATES.map((s) => (
                <option key={s} value={s}>
                  {t(`inventory.state.${s}`)}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field id={`${id}-year`} label={t("inventory.field.year")}>
          <Stepper
            id={`${id}-year`}
            min={1950}
            max={2100}
            start={new Date().getFullYear()}
            value={year ? Number(year) : null}
            label={t("inventory.field.year")}
            onChange={(n) => setYear(String(n))}
            onClear={() => setYear("")}
          />
        </Field>
      </div>
      <SpecFields id={`${id}-spec`} category={current} specs={specs} onChange={setSpecs} />
      <Field id={`${id}-notes`} label={t("inventory.field.notes")}>
        <input id={`${id}-notes`} dir="auto" maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>
      <ReasonField id={`${id}-reason`} value={reason} onChange={setReason} required={vehicle !== null} tried={tried} />
      {vehicle && <Revisions entityId={vehicle.id} />}
    </FormShell>
  );
}

// ---------------------------------------------------------------- equipment

export function StockForm({
  line,
  units,
  categories,
  onDone,
}: {
  line: StockLine | null;
  units: UnitRow[];
  categories: Category[];
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const saved = useSaved(onDone);
  const [unit, setUnit] = useState(line?.unit_id ?? "");
  const [category, setCategory] = useState(line?.category_key ?? "");
  const [specs, setSpecs] = useState<Record<string, SpecValue>>(line?.specs ?? {});
  const [ready, setReady] = useState(String(line?.qty_ready ?? 0));
  const [broken, setBroken] = useState(String(line?.qty_broken ?? 0));
  const [notes, setNotes] = useState(line?.notes ?? "");
  const [carrier, setCarrier] = useState(line?.vehicle_id ?? "");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const lang = useLanguage();
  // R3: the vehicles of the chosen unit, one of which may carry this equipment.
  const unitVehicles = useQuery({
    queryKey: inventoryKeys.list("vehicles", { gouvernorat: null, unit: unit || null, category: null }),
    queryFn: ({ signal }) => api.vehicles({ gouvernorat: null, unit, category: null }, signal),
    enabled: Boolean(unit),
  });
  const types = categories.filter((c) => c.kind === "equipment");
  const current = types.find((c) => c.key === category);
  const missing = !unit || !category || (line !== null && reason.trim().length < MIN_REASON);
  const count = (v: string) => Math.max(0, Math.min(100_000, Math.trunc(Number(v) || 0)));
  const mutation = useMutation({
    mutationFn: () =>
      api.saveStock(line?.id ?? null, {
        unit_id: unit,
        category_key: category,
        specs: Object.fromEntries(Object.entries(specs).filter(([k]) => current?.specs.some((d) => d.key === k))),
        qty_ready: count(ready),
        qty_broken: count(broken),
        notes: notes.trim() || null,
        vehicle_id: carrier || null,
        reason: reason.trim(),
        version: line?.version,
      }),
    onSuccess: saved,
  });
  return (
    <FormShell
      title={line ? t("inventory.stock.editTitle") : t("inventory.stock.newTitle")}
      onSubmit={() => {
        setTried(true);
        if (!missing) mutation.mutate();
      }}
      pending={mutation.isPending}
      error={mutation.error}
      problem={tried && missing ? t("inventory.form.missing") : null}
      onCancel={onDone}
    >
      <div className="form-grid">
        <Field id={`${id}-unit`} label={t("inventory.field.unit")}>
          <UnitSelect
            id={`${id}-unit`}
            units={units}
            value={unit}
            onChange={(v) => {
              setUnit(v);
              setCarrier("");
            }}
          />
        </Field>
        <Field id={`${id}-type`} label={t("inventory.field.type")}>
          <CategorySelect id={`${id}-type`} categories={types} value={category} onChange={setCategory} />
        </Field>
        <Field id={`${id}-carrier`} label={t("inventory.field.carrier")}>
          <select id={`${id}-carrier`} value={carrier} disabled={!unit} onChange={(e) => setCarrier(e.target.value)}>
            <option value="">{t("inventory.stock.atUnit")}</option>
            {(unitVehicles.data?.items ?? []).map((v) => (
              <option key={v.id} value={v.id}>
                {v.label}
                {v.code ? ` (${v.code})` : ""} · {categoryName(categories.find((c) => c.key === v.category_key), lang)}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${id}-ready`} label={t("inventory.field.qtyReady")}>
          <Stepper
            id={`${id}-ready`}
            min={0}
            max={100000}
            value={ready === "" ? null : Number(ready)}
            label={t("inventory.field.qtyReady")}
            onChange={(n) => setReady(String(n))}
            onClear={() => setReady("")}
          />
        </Field>
        <Field id={`${id}-broken`} label={t("inventory.field.qtyBroken")}>
          <Stepper
            id={`${id}-broken`}
            min={0}
            max={100000}
            value={broken === "" ? null : Number(broken)}
            label={t("inventory.field.qtyBroken")}
            onChange={(n) => setBroken(String(n))}
            onClear={() => setBroken("")}
          />
        </Field>
      </div>
      <SpecFields id={`${id}-spec`} category={current} specs={specs} onChange={setSpecs} />
      <Field id={`${id}-notes`} label={t("inventory.field.notes")}>
        <input id={`${id}-notes`} dir="auto" maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>
      <ReasonField id={`${id}-reason`} value={reason} onChange={setReason} required={line !== null} tried={tried} />
      {line && <Revisions entityId={line.id} />}
    </FormShell>
  );
}

// ---------------------------------------------------------------- staff

export function AgentForm({
  agent,
  units,
  categories,
  onDone,
}: {
  agent: Agent | null;
  units: UnitRow[];
  categories: Category[];
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const id = useId();
  const saved = useSaved(onDone);
  const [unit, setUnit] = useState(agent?.unit_id ?? "");
  const [matricule, setMatricule] = useState(agent?.matricule ?? "");
  const [name, setName] = useState(agent?.full_name ?? "");
  const [rank, setRank] = useState(agent?.rank ?? "");
  const [phone, setPhone] = useState(agent?.phone ?? "");
  const [availability, setAvailability] = useState<Availability>(agent?.availability ?? "on_duty");
  const [skills, setSkills] = useState<Skill[]>(
    agent?.skills.map(({ skill_key, level, cert_expires }) => ({ skill_key, level, cert_expires })) ?? [],
  );
  const [notes, setNotes] = useState(agent?.notes ?? "");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const specialities = categories.filter((c) => c.kind === "skill" && (c.active || skills.some((s) => s.skill_key === c.key)));
  const missing = !unit || matricule.trim().length < 2 || name.trim().length < 2;
  const setSkill = (key: string, patch: Partial<Skill> | null) =>
    setSkills((list) => {
      const rest = list.filter((s) => s.skill_key !== key);
      if (patch === null) return rest;
      const before = list.find((s) => s.skill_key === key) ?? { skill_key: key, level: 0, cert_expires: null };
      return [...rest, { ...before, ...patch }];
    });
  const mutation = useMutation({
    mutationFn: () =>
      api.saveAgent(agent?.id ?? null, {
        unit_id: unit,
        matricule: matricule.trim(),
        full_name: name.trim(),
        rank: rank.trim() || null,
        phone: phone.trim() || null,
        availability,
        skills,
        notes: notes.trim() || null,
        reason: reason.trim(),
        version: agent?.version,
      }),
    onSuccess: saved,
  });
  return (
    <FormShell
      title={agent ? t("inventory.agents.editTitle", { name: agent.full_name ?? "" }) : t("inventory.agents.newTitle")}
      onSubmit={() => {
        setTried(true);
        if (!missing) mutation.mutate();
      }}
      pending={mutation.isPending}
      error={mutation.error}
      problem={tried && missing ? t("inventory.form.missing") : null}
      onCancel={onDone}
    >
      <p className="muted">{t("inventory.agents.privacy")}</p>
      <div className="form-grid">
        <Field id={`${id}-unit`} label={t("inventory.field.unit")}>
          <UnitSelect id={`${id}-unit`} units={units} value={unit} onChange={setUnit} />
        </Field>
        <Field id={`${id}-mat`} label={t("inventory.field.matricule")}>
          <input id={`${id}-mat`} dir="ltr" maxLength={30} aria-required="true" value={matricule} onChange={(e) => setMatricule(e.target.value)} />
        </Field>
        <Field id={`${id}-name`} label={t("inventory.field.fullName")}>
          <input id={`${id}-name`} dir="auto" maxLength={120} aria-required="true" autoComplete="off" value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field id={`${id}-rank`} label={t("inventory.field.rank")}>
          <input id={`${id}-rank`} dir="auto" maxLength={60} value={rank} onChange={(e) => setRank(e.target.value)} />
        </Field>
        <Field id={`${id}-phone`} label={t("inventory.field.phone")}>
          <input id={`${id}-phone`} type="tel" dir="ltr" maxLength={30} autoComplete="off" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </Field>
        <Field id={`${id}-avail`} label={t("inventory.field.availability")}>
          <select id={`${id}-avail`} value={availability} onChange={(e) => setAvailability(e.target.value as Availability)}>
            {AVAILABILITY.map((a) => (
              <option key={a} value={a}>
                {t(`inventory.availability.${a}`)}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <fieldset className="inventory-skills">
        <legend>{t("inventory.field.skills")}</legend>
        {specialities.map((c) => {
          const held = skills.find((s) => s.skill_key === c.key);
          return (
            <div key={c.key} className="inventory-skill">
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={Boolean(held)}
                  onChange={(e) => setSkill(c.key, e.target.checked ? { level: c.levels ? 1 : 0 } : null)}
                />
                {categoryName(c, lang)}
              </label>
              {held && c.levels > 0 && (
                <select
                  aria-label={t("inventory.agents.levelOf", { skill: categoryName(c, lang) })}
                  value={held.level}
                  onChange={(e) => setSkill(c.key, { level: Number(e.target.value) })}
                >
                  {Array.from({ length: c.levels }, (_, i) => i + 1).map((lv) => (
                    <option key={lv} value={lv}>
                      {t("inventory.agents.level", { level: lv })}
                    </option>
                  ))}
                </select>
              )}
              {held && (
                <input
                  type="date"
                  aria-label={t("inventory.agents.expiresOf", { skill: categoryName(c, lang) })}
                  value={held.cert_expires ?? ""}
                  onChange={(e) => setSkill(c.key, { cert_expires: e.target.value || null })}
                />
              )}
            </div>
          );
        })}
      </fieldset>
      <Field id={`${id}-notes`} label={t("inventory.field.notes")}>
        <input id={`${id}-notes`} dir="auto" maxLength={500} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>
      <ReasonField id={`${id}-reason`} value={reason} onChange={setReason} required={false} tried={tried} />
      {agent && <Revisions entityId={agent.id} />}
    </FormShell>
  );
}

// ---------------------------------------------------------------- deleting and versions

/** Delete with a reason (sold, scrapped, retired): the entry stays in the versions. */
export function DeleteEntry({ label, onDelete }: { label: string; onDelete: (reason: string) => Promise<unknown> }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const mutation = useMutation({
    mutationFn: () => onDelete(reason.trim()),
    onSuccess: () => void qc.invalidateQueries({ queryKey: inventoryKeys.all }),
  });
  if (!open) {
    return (
      <button type="button" className="btn btn--small btn--danger" aria-label={t("inventory.deleteNamed", { label })} onClick={() => setOpen(true)}>
        {t("inventory.delete")}
      </button>
    );
  }
  return (
    <span className="inventory-delete">
      <label htmlFor={`${id}-r`} className="visually-hidden">
        {t("inventory.form.reason")}
      </label>
      <input
        id={`${id}-r`}
        dir="auto"
        maxLength={500}
        placeholder={t("inventory.form.deleteReason")}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <button
        type="button"
        className="btn btn--small btn--danger"
        disabled={reason.trim().length < MIN_REASON || mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {t("inventory.confirmDelete")}
      </button>
      <button type="button" className="btn btn--small" onClick={() => setOpen(false)}>
        {t("common.cancel")}
      </button>
      {mutation.isError && (
        <span className="field__error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </span>
      )}
    </span>
  );
}

function Revisions({ entityId }: { entityId: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const [open, setOpen] = useState(false);
  const query = useQuery({
    queryKey: inventoryKeys.revisions(entityId),
    queryFn: ({ signal }) => api.inventoryRevisions(entityId, signal),
    enabled: open,
  });
  return (
    <details className="inventory-revisions" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>{t("inventory.revisions.title")}</summary>
      {query.data && query.data.items.length === 0 && <p className="muted">{t("inventory.revisions.none")}</p>}
      <ol>
        {query.data?.items.map((r) => (
          <li key={r.id}>
            <time dateTime={r.created_at}>{fmt.dateTime(r.created_at)}</time> · {t(`inventory.revisions.${r.action}`)}
            {r.created_by_name && <> · {r.created_by_name}</>}
            {r.reason && (
              <>
                {" "}
                · <span dir="auto">{r.reason}</span>
              </>
            )}
          </li>
        ))}
      </ol>
    </details>
  );
}

// ---------------------------------------------------------------- transfers between gouvernorats (R3)

/** The room of the gouvernorat the member of staff leaves sends the transfer; the joining room decides. */
export function TransferForm({ agent, onDone }: { agent: Agent; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const saved = useSaved(onDone);
  const geo = useGouvernorats();
  const [to, setTo] = useState("");
  const [on, setOn] = useState("");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const missing = !to || reason.trim().length < MIN_REASON;
  const mutation = useMutation({
    mutationFn: () => api.requestTransfer(agent.id, { to_gouvernorat: Number(to), effective_on: on || null, reason: reason.trim() }),
    onSuccess: saved,
  });
  return (
    <FormShell
      title={t("inventory.transfer.newTitle", { name: agent.full_name ?? agent.rank ?? "" })}
      onSubmit={() => {
        setTried(true);
        if (!missing) mutation.mutate();
      }}
      pending={mutation.isPending}
      error={mutation.error}
      problem={tried && missing ? t("inventory.form.missing") : null}
      onCancel={onDone}
    >
      <p className="muted">{t("inventory.transfer.intro")}</p>
      <div className="form-grid">
        <Field id={`${id}-to`} label={t("inventory.transfer.to")}>
          <select id={`${id}-to`} aria-required="true" value={to} onChange={(e) => setTo(e.target.value)}>
            <option value="">—</option>
            {geo.list
              .filter((g) => g.code !== agent.gouvernorat_code)
              .map((g) => (
                <option key={g.code} value={g.code}>
                  {geo.nameOf(g.code)}
                </option>
              ))}
          </select>
        </Field>
        <Field id={`${id}-on`} label={t("inventory.transfer.effectiveOn")}>
          <input id={`${id}-on`} type="date" value={on} onChange={(e) => setOn(e.target.value)} />
        </Field>
      </div>
      <ReasonField id={`${id}-reason`} value={reason} onChange={setReason} required tried={tried} />
    </FormShell>
  );
}

const TRANSFER_TONE: Record<Transfer["status"], string> = {
  pending: "tone-amber",
  accepted: "tone-green",
  refused: "tone-red",
  cancelled: "tone-slate",
};

function TransferRow({ transfer, units }: { transfer: Transfer; units: UnitRow[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const geo = useGouvernorats();
  const qc = useQueryClient();
  const id = useId();
  const [unit, setUnit] = useState("");
  const [reason, setReason] = useState("");
  const done = () => void qc.invalidateQueries({ queryKey: inventoryKeys.all });
  const accept = useMutation({ mutationFn: () => api.acceptTransfer(transfer.id, unit, reason.trim()), onSuccess: done });
  const refuse = useMutation({ mutationFn: () => api.refuseTransfer(transfer.id, reason.trim()), onSuccess: done });
  const cancel = useMutation({ mutationFn: () => api.cancelTransfer(transfer.id, reason.trim()), onSuccess: done });
  const error = accept.error ?? refuse.error ?? cancel.error;
  const joining = units.filter((u) => u.gouvernorat_code === transfer.to_gouvernorat && u.can_edit);
  const reasoned = reason.trim().length >= MIN_REASON;
  return (
    <li className="card inventory-transfer">
      <div className="inventory-transfer__head">
        <strong dir="auto">{transfer.full_name ?? t("inventory.agents.hidden")}</strong>
        {transfer.rank && <span className="muted"> · {transfer.rank}</span>}{" "}
        <span className={`pill ${TRANSFER_TONE[transfer.status]}`}>{t(`inventory.transfer.status.${transfer.status}`)}</span>
      </div>
      <p>
        {t("inventory.transfer.route", {
          from: `${geo.nameOf(transfer.from_gouvernorat) ?? ""} (${transfer.from_unit_name})`,
          to: `${geo.nameOf(transfer.to_gouvernorat) ?? ""}${transfer.to_unit_name ? ` (${transfer.to_unit_name})` : ""}`,
        })}
        {transfer.effective_on && <> · {t("inventory.transfer.on", { date: fmt.date(transfer.effective_on) })}</>}
      </p>
      <p className="muted" dir="auto">
        {transfer.reason} · {transfer.requested_by_name ?? "—"} · {fmt.dateTime(transfer.requested_at)}
      </p>
      {transfer.decision_reason && (
        <p className="muted" dir="auto">
          {transfer.decided_by_name ?? "—"}: {transfer.decision_reason}
        </p>
      )}
      {(transfer.can_decide || transfer.can_cancel) && (
        <div className="inventory-transfer__decide">
          {transfer.can_decide && (
            <div className="field">
              <label htmlFor={`${id}-unit`}>{t("inventory.transfer.newUnit")}</label>
              <select id={`${id}-unit`} value={unit} onChange={(e) => setUnit(e.target.value)}>
                <option value="">{t("inventory.form.pickUnit")}</option>
                {joining.map((u) => (
                  <option key={u.id} value={u.id}>
                    {lang === "ar" ? u.name_ar : u.name_fr}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="field">
            <label htmlFor={`${id}-reason`}>{t("inventory.transfer.decisionReason")}</label>
            <input id={`${id}-reason`} dir="auto" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <div className="actions">
            {transfer.can_decide && (
              <>
                <button type="button" className="btn btn--primary btn--small" disabled={!unit || accept.isPending} onClick={() => accept.mutate()}>
                  {t("inventory.transfer.accept")}
                </button>
                <button type="button" className="btn btn--small" disabled={!reasoned || refuse.isPending} onClick={() => refuse.mutate()}>
                  {t("inventory.transfer.refuse")}
                </button>
              </>
            )}
            {transfer.can_cancel && (
              <button type="button" className="btn btn--small btn--danger" disabled={!reasoned || cancel.isPending} onClick={() => cancel.mutate()}>
                {t("inventory.transfer.cancel")}
              </button>
            )}
          </div>
          {error !== null && (
            <p className="field__error" role="alert">
              {t(errorMessageKey(error))}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

/** The transfers the room sends and receives: the pending ones open, the decided ones folded. */
export function TransfersPanel({ units }: { units: UnitRow[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const list = useQuery({ queryKey: inventoryKeys.transfers, queryFn: ({ signal }) => api.transfers(signal) });
  const items = list.data ?? [];
  if (items.length === 0) return null;
  const pending = items.filter((x) => x.status === "pending");
  const decided = items.filter((x) => x.status !== "pending");
  return (
    <section className="inventory-transfers" aria-labelledby="inventory-transfers">
      <h3 id="inventory-transfers">{t("inventory.transfer.title", { n: pending.length })}</h3>
      <ul className="inventory-transfers__list">
        {pending.map((x) => (
          <TransferRow key={x.id} transfer={x} units={units} />
        ))}
      </ul>
      {decided.length > 0 && (
        <details>
          <summary>{t("inventory.transfer.decided", { n: decided.length })}</summary>
          <ul className="inventory-transfers__list">
            {decided.map((x) => (
              <TransferRow key={x.id} transfer={x} units={units} />
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
