import { useQuery } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { Badge } from "../../components/Badges";
import { Dialog } from "../../components/Dialog";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useServices } from "../../context/services";
import { useFormat } from "../../lib/hooks";
import { queryKeys } from "../../lib/portalApi";
import { HAZMAT_UNITS, type Hazmat, type HazmatInput, type HazmatUnit, type OrgDocument } from "../../lib/types";
import { isValidUnNumber, parseNumber } from "../../lib/validators";
import { BlockedNote, useOrg } from "./OrgWorkspace";
import { describedBy, Field, RequiredNote, RowActions } from "./RegisterParts";
import { useRegister } from "./useRegister";

interface Draft {
  name: string;
  un_number: string;
  hazard_class: string;
  quantity: string;
  unit: HazmatUnit;
  storage_location: string;
  sds_document_id: string;
}

function toDraft(h: Hazmat | null): Draft {
  return {
    name: h?.name ?? "",
    un_number: h?.un_number ?? "",
    hazard_class: h?.hazard_class ?? "",
    quantity: h ? String(h.quantity) : "",
    unit: h?.unit ?? "kg",
    storage_location: h?.storage_location ?? "",
    sds_document_id: h?.sds_document_id ?? "",
  };
}

export function validateHazmat(d: Draft): Partial<Record<keyof Draft, string>> {
  const e: Partial<Record<keyof Draft, string>> = {};
  if (!d.name.trim()) e.name = "validation.required";
  if (!isValidUnNumber(d.un_number)) e.un_number = "validation.unNumber";
  if (d.hazard_class.trim().length > 8) e.hazard_class = "validation.hazardClass";
  const q = parseNumber(d.quantity);
  if (q === null) e.quantity = "validation.required";
  else if (!(q >= 0)) e.quantity = "validation.positiveNumber";
  return e;
}

function toInput(d: Draft): HazmatInput {
  return {
    name: d.name.trim(),
    un_number: d.un_number.trim() || null,
    hazard_class: d.hazard_class.trim() || null,
    quantity: parseNumber(d.quantity) ?? 0,
    unit: d.unit,
    storage_location: d.storage_location.trim() || null,
    sds_document_id: d.sds_document_id || null,
  };
}

function HazmatDialog({
  item,
  sdsDocuments,
  onClose,
  save,
}: {
  item: Hazmat | null;
  sdsDocuments: OrgDocument[];
  onClose: () => void;
  save: ReturnType<typeof useRegister<"hazmat">>["save"];
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(() => toDraft(item));
  const [errors, setErrors] = useState<Partial<Record<keyof Draft, string>>>({});
  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));
  const err = (k: keyof Draft) => (errors[k] ? t(errors[k]) : null);

  function submit(e: SubmitEvent) {
    e.preventDefault();
    const found = validateHazmat(draft);
    setErrors(found);
    if (Object.keys(found).length) return;
    save.mutate({ id: item?.id ?? null, input: toInput(draft) }, { onSuccess: onClose });
  }

  return (
    <Dialog title={item ? t("hazmat.editTitle") : t("hazmat.addTitle")} onClose={onClose}>
      <form className="form" onSubmit={submit} noValidate>
        <RequiredNote />
        <div className="form-grid">
          <Field id="hz-name" label={t("hazmat.name")} required error={err("name")}>
            <input id="hz-name" value={draft.name} aria-invalid={!!errors.name} aria-describedby={describedBy("hz-name", null, errors.name)} onChange={(e) => set({ name: e.target.value })} />
          </Field>
          <Field id="hz-un" label={t("hazmat.unNumber")} hint={t("hazmat.unHint")} error={err("un_number")}>
            <input id="hz-un" inputMode="numeric" dir="ltr" maxLength={4} value={draft.un_number} aria-invalid={!!errors.un_number} aria-describedby={describedBy("hz-un", true, errors.un_number)} onChange={(e) => set({ un_number: e.target.value })} />
          </Field>
          <Field id="hz-class" label={t("hazmat.hazardClass")} hint={t("hazmat.classHint")} error={err("hazard_class")}>
            <input id="hz-class" dir="ltr" value={draft.hazard_class} aria-invalid={!!errors.hazard_class} aria-describedby={describedBy("hz-class", true, errors.hazard_class)} onChange={(e) => set({ hazard_class: e.target.value })} />
          </Field>
          <Field id="hz-qty" label={t("hazmat.quantity")} required error={err("quantity")}>
            <input id="hz-qty" inputMode="decimal" value={draft.quantity} aria-invalid={!!errors.quantity} aria-describedby={describedBy("hz-qty", null, errors.quantity)} onChange={(e) => set({ quantity: e.target.value })} />
          </Field>
          <Field id="hz-unit" label={t("hazmat.unit")}>
            <select id="hz-unit" value={draft.unit} onChange={(e) => set({ unit: e.target.value as HazmatUnit })}>
              {HAZMAT_UNITS.map((u) => (
                <option key={u} value={u}>
                  {t(`units.${u}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field id="hz-storage" label={t("hazmat.storage")}>
            <input id="hz-storage" value={draft.storage_location} onChange={(e) => set({ storage_location: e.target.value })} />
          </Field>
          <Field id="hz-sds" label={t("hazmat.sds")} hint={t("hazmat.sdsHint")}>
            <select id="hz-sds" value={draft.sds_document_id} aria-describedby="hz-sds-hint" onChange={(e) => set({ sds_document_id: e.target.value })}>
              <option value="">{t("hazmat.noSds")}</option>
              {sdsDocuments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
            </select>
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

/** Hazardous materials register (FR-B-006), each linked to its safety data sheet. */
export function HazmatTab() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const fmt = useFormat();
  const { list, save, remove } = useRegister(org.id, "hazmat");
  const documents = useQuery({ queryKey: queryKeys.documents(org.id), queryFn: ({ signal }) => api.documents(org.id, signal) });
  const [editing, setEditing] = useState<Hazmat | "new" | null>(null);
  const editable = can("editRegisters");

  if (list.isPending) return <Loading />;
  if (list.isError) return <ErrorBox error={list.error} onRetry={() => void list.refetch()} />;
  const sdsDocuments = (documents.data ?? []).filter((d) => d.kind === "sds");
  const titleOf = (id: string | null) => sdsDocuments.find((d) => d.id === id)?.title ?? null;

  return (
    <section className="card" aria-labelledby="hazmat-title">
      <div className="section-head">
        <h2 id="hazmat-title">{t("hazmat.title")}</h2>
        {editable && (
          <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
            {t("hazmat.add")}
          </button>
        )}
      </div>
      <p className="muted">
        {t("hazmat.help")} <Link to="../documents">{t("hazmat.manageSds")}</Link>
      </p>
      <BlockedNote action="editRegisters" />
      {list.data.length === 0 ? (
        <p className="empty">{t("hazmat.empty")}</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("hazmat.name")}</th>
                <th scope="col">{t("hazmat.unNumber")}</th>
                <th scope="col">{t("hazmat.hazardClass")}</th>
                <th scope="col" className="num">
                  {t("hazmat.quantity")}
                </th>
                <th scope="col">{t("hazmat.storage")}</th>
                <th scope="col">{t("hazmat.sds")}</th>
                {editable && <th scope="col">{t("common.actions")}</th>}
              </tr>
            </thead>
            <tbody>
              {list.data.map((h) => (
                <tr key={h.id}>
                  <th scope="row">{h.name}</th>
                  <td className="code">{h.un_number ? `UN ${h.un_number}` : "—"}</td>
                  <td>{h.hazard_class ?? "—"}</td>
                  <td className="num">
                    {fmt.number(h.quantity)} {t(`units.${h.unit}`)}
                  </td>
                  <td>{h.storage_location ?? "—"}</td>
                  <td>{h.sds_document_id ? (titleOf(h.sds_document_id) ?? t("hazmat.sdsLinked")) : <Badge tone="danger">{t("hazmat.sdsMissing")}</Badge>}</td>
                  {editable && (
                    <td>
                      <RowActions name={h.name} editable={editable} onEdit={() => setEditing(h)} remove={remove} id={h.id} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && (
        <HazmatDialog
          item={editing === "new" ? null : editing}
          sdsDocuments={sdsDocuments}
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
