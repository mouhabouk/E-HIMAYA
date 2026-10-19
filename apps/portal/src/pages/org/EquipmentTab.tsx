import { useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";
import { MaintenanceBadge } from "../../components/Badges";
import { Dialog } from "../../components/Dialog";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useFormat } from "../../lib/hooks";
import { EQUIPMENT_KINDS, type Equipment, type EquipmentInput, type EquipmentKind } from "../../lib/types";
import { isIntInRange, parseNumber } from "../../lib/validators";
import { BlockedNote, useOrg } from "./OrgWorkspace";
import { Field, RowActions, describedBy } from "./RegisterParts";
import { useRegister } from "./useRegister";

interface Draft {
  kind: EquipmentKind;
  count: string;
  location: string;
  last_maintenance_on: string;
  maintenance_interval_months: string;
}

function toDraft(eq: Equipment | null): Draft {
  return {
    kind: eq?.kind ?? "extinguisher",
    count: eq ? String(eq.count) : "1",
    location: eq?.location ?? "",
    last_maintenance_on: eq?.last_maintenance_on ?? "",
    maintenance_interval_months: String(eq?.maintenance_interval_months ?? 12),
  };
}

function validate(d: Draft): Partial<Record<keyof Draft, string>> {
  const e: Partial<Record<keyof Draft, string>> = {};
  if (!isIntInRange(parseNumber(d.count), 1, 1_000_000)) e.count = "validation.integerPositive";
  if (!isIntInRange(parseNumber(d.maintenance_interval_months), 1, 120)) e.maintenance_interval_months = "validation.months120";
  return e;
}

function toInput(d: Draft): EquipmentInput {
  return {
    kind: d.kind,
    count: parseNumber(d.count) ?? 1,
    location: d.location.trim() || null,
    last_maintenance_on: d.last_maintenance_on || null,
    maintenance_interval_months: parseNumber(d.maintenance_interval_months) ?? 12,
  };
}

function EquipmentDialog({
  item,
  onClose,
  save,
}: {
  item: Equipment | null;
  onClose: () => void;
  save: ReturnType<typeof useRegister<"equipment">>["save"];
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(() => toDraft(item));
  const [errors, setErrors] = useState<Partial<Record<keyof Draft, string>>>({});
  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));
  const err = (k: keyof Draft) => (errors[k] ? t(errors[k]) : null);

  function submit(e: SubmitEvent) {
    e.preventDefault();
    const found = validate(draft);
    setErrors(found);
    if (Object.keys(found).length) return;
    save.mutate({ id: item?.id ?? null, input: toInput(draft) }, { onSuccess: onClose });
  }

  return (
    <Dialog title={item ? t("equipment.editTitle") : t("equipment.addTitle")} onClose={onClose}>
      <form className="form" onSubmit={submit} noValidate>
        <div className="form-grid">
          <Field id="eq-kind" label={t("equipment.kind")}>
            <select id="eq-kind" value={draft.kind} onChange={(e) => set({ kind: e.target.value as EquipmentKind })}>
              {EQUIPMENT_KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`equipmentKinds.${k}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field id="eq-count" label={t("equipment.count")} required error={err("count")}>
            <input id="eq-count" inputMode="numeric" value={draft.count} aria-invalid={!!errors.count} aria-describedby={describedBy("eq-count", null, errors.count)} onChange={(e) => set({ count: e.target.value })} />
          </Field>
          <Field id="eq-location" label={t("equipment.location")}>
            <input id="eq-location" value={draft.location} onChange={(e) => set({ location: e.target.value })} />
          </Field>
          <Field id="eq-last" label={t("equipment.lastMaintenance")}>
            <input id="eq-last" type="date" value={draft.last_maintenance_on} onChange={(e) => set({ last_maintenance_on: e.target.value })} />
          </Field>
          <Field id="eq-interval" label={t("equipment.interval")} hint={t("equipment.intervalHint")} error={err("maintenance_interval_months")}>
            <input id="eq-interval" inputMode="numeric" value={draft.maintenance_interval_months} aria-invalid={!!errors.maintenance_interval_months} aria-describedby={describedBy("eq-interval", true, errors.maintenance_interval_months)} onChange={(e) => set({ maintenance_interval_months: e.target.value })} />
          </Field>
        </div>
        {save.isError && <ErrorBox error={save.error} />}
        <div className="actions actions--end">
          <button type="button" className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button type="submit" className="btn btn--primary" disabled={save.isPending}>
            {t("common.save")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

/** Safety equipment register (FR-B-006) with maintenance status. */
export function EquipmentTab() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const fmt = useFormat();
  const { list, save, remove } = useRegister(org.id, "equipment");
  const [editing, setEditing] = useState<Equipment | "new" | null>(null);
  const editable = can("editRegisters");

  if (list.isPending) return <Loading />;
  if (list.isError) return <ErrorBox error={list.error} onRetry={() => void list.refetch()} />;

  return (
    <section className="card" aria-labelledby="equipment-title">
      <div className="section-head">
        <h2 id="equipment-title">{t("equipment.title")}</h2>
        {editable && (
          <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
            {t("equipment.add")}
          </button>
        )}
      </div>
      <p className="muted">{t("equipment.help")}</p>
      <BlockedNote action="editRegisters" />
      {list.data.length === 0 ? (
        <p className="empty">{t("equipment.empty")}</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("equipment.kind")}</th>
                <th scope="col" className="num">
                  {t("equipment.count")}
                </th>
                <th scope="col">{t("equipment.location")}</th>
                <th scope="col">{t("equipment.status")}</th>
                <th scope="col">{t("equipment.lastMaintenance")}</th>
                <th scope="col">{t("equipment.next")}</th>
                {editable && <th scope="col">{t("common.actions")}</th>}
              </tr>
            </thead>
            <tbody>
              {list.data.map((eq) => {
                const name = t(`equipmentKinds.${eq.kind}`);
                return (
                  <tr key={eq.id}>
                    <th scope="row">{name}</th>
                    <td className="num">{fmt.number(eq.count)}</td>
                    <td>{eq.location ?? "—"}</td>
                    <td>
                      <MaintenanceBadge status={eq.maintenance_status} />
                    </td>
                    <td>{fmt.date(eq.last_maintenance_on)}</td>
                    <td>{fmt.date(eq.next_maintenance_on)}</td>
                    {editable && (
                      <td>
                        <RowActions name={eq.location ? `${name} — ${eq.location}` : name} editable={editable} onEdit={() => setEditing(eq)} remove={remove} id={eq.id} />
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {editing && (
        <EquipmentDialog
          item={editing === "new" ? null : editing}
          save={save}
          onClose={() => {
            save.reset();
            setEditing(null);
          }}
        />
      )}
    </section>
  );
}
