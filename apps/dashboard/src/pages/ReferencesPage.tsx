// covers: the Office's reference lists (migration 0091, Yamen 2026-11-01): the vehicle types (CEE codes), the agent's
// status and post, the vehicle's state and situation, the parties of a road accident, the nature of a fire, the crops
// lost and their units, the places of the damages and of the programmes, the fields of intervention. Read by every
// staff member, kept by the central room (add, rename, retire), exported as a workbook or a CSV.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useLanguage } from "../lib/hooks";
import { saveDownload } from "../lib/layersApi";
import { referenceKeys, type DamageUnit, type RefItem, type RefList } from "../lib/references";

const UNITS: readonly DamageUnit[] = ["ha", "bale", "bag"];

function listName(list: RefList, lang: string): string {
  return lang === "fr" ? list.name_fr : lang === "en" ? list.name_en : list.name_ar;
}

function ItemRow({ item, list, manage }: { item: RefItem; list: RefList; manage: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const fmt = useFormat();
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(item.label_ar);
  const [labelFr, setLabelFr] = useState(item.label_fr ?? "");
  const [code, setCode] = useState(item.code ?? "");
  const change = useMutation({
    mutationFn: (body: Parameters<typeof api.changeReference>[1]) => api.changeReference(item.id, body),
    onSuccess: () => {
      setEditing(false);
      void qc.invalidateQueries({ queryKey: referenceKeys.all });
    },
  });
  const hasUnit = list.key === "crop_loss";
  return (
    <tr className={item.active ? undefined : "muted"}>
      <td className="num">
        {editing ? (
          <input aria-label={t("references.code")} value={code} maxLength={20} size={5} onChange={(e) => setCode(e.target.value)} />
        ) : (
          (item.code ?? "—")
        )}
      </td>
      <th scope="row">
        {editing ? (
          <input aria-label={t("references.label")} value={label} maxLength={160} dir="rtl" onChange={(e) => setLabel(e.target.value)} />
        ) : (
          <span lang="ar" dir="rtl">
            {item.label_ar}
          </span>
        )}
      </th>
      <td>
        {editing ? (
          <input aria-label={t("references.labelFr")} value={labelFr} maxLength={160} dir="ltr" onChange={(e) => setLabelFr(e.target.value)} />
        ) : (
          (item.label_fr ?? "—")
        )}
      </td>
      {hasUnit && (
        <td>
          {manage && !editing ? (
            <select
              aria-label={t("references.unit")}
              value={item.unit ?? ""}
              onChange={(e) => change.mutate({ unit: (e.target.value || null) as DamageUnit | null })}
            >
              <option value="">—</option>
              {UNITS.map((u) => (
                <option key={u} value={u}>
                  {t(`record.damages.units.${u}`)}
                </option>
              ))}
            </select>
          ) : item.unit ? (
            t(`record.damages.units.${item.unit}`)
          ) : (
            "—"
          )}
        </td>
      )}
      <td>{item.active ? t("references.active") : t("references.retired")}</td>
      <td className="muted">
        {item.updated_by_name ?? "—"} · {fmt.dateTime(item.updated_at)}
      </td>
      {manage && (
        <td className="actions">
          {editing ? (
            <>
              <button
                type="button"
                className="btn btn--small btn--primary"
                disabled={!label.trim() || change.isPending}
                onClick={() => change.mutate({ label_ar: label.trim(), label_fr: labelFr.trim() || null, code: code.trim() || null })}
              >
                {t("references.save")}
              </button>
              <button type="button" className="btn btn--small" onClick={() => setEditing(false)}>
                {t("references.cancel")}
              </button>
            </>
          ) : (
            <>
              <button type="button" className="btn btn--small" onClick={() => setEditing(true)}>
                {t("references.edit")}
              </button>
              <button
                type="button"
                className="btn btn--small"
                disabled={change.isPending}
                onClick={() => change.mutate({ active: !item.active })}
              >
                {item.active ? t("references.retire") : t("references.restore")}
              </button>
            </>
          )}
          {change.error ? (
            <span className="alert alert--error" role="alert">
              {t(errorMessageKey(change.error))}
            </span>
          ) : null}
        </td>
      )}
    </tr>
  );
}

export function ReferencesPage() {
  const { t } = useTranslation();
  const lang = useLanguage();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const refs = useQuery({ queryKey: referenceKeys.all, queryFn: ({ signal }) => api.references(signal) });
  const [key, setKey] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [code, setCode] = useState("");
  const [query, setQuery] = useState("");
  const lists = refs.data?.lists ?? [];
  const list = lists.find((l) => l.key === key) ?? lists[0];
  const manage = refs.data?.can_manage ?? false;
  const add = useMutation({
    mutationFn: () => api.addReference(list?.key ?? "", { label_ar: label.trim(), code: code.trim() || null }),
    onSuccess: () => {
      setLabel("");
      setCode("");
      void qc.invalidateQueries({ queryKey: referenceKeys.all });
    },
  });
  const exporter = useMutation({
    mutationFn: ({ format, only }: { format: "xlsx" | "csv"; only?: string }) => api.referencesExport(format, only),
    onSuccess: saveDownload,
  });
  const q = query.trim();
  const shown = (list?.items ?? []).filter((i) => !q || i.label_ar.includes(q) || (i.code ?? "") === q);
  return (
    <div className="page references-page">
      <div className="page__head">
        <PageTitle icon="menuBook" tone="slate">
          {t("references.title")}
        </PageTitle>
        <div className="actions">
          <button type="button" className="btn" disabled={exporter.isPending} onClick={() => exporter.mutate({ format: "xlsx" })}>
            {t("references.exportAll")}
          </button>
        </div>
      </div>
      <p className="muted">{t("references.intro")}</p>
      {refs.isPending && <Loading />}
      {refs.isError && <ErrorBox error={refs.error} onRetry={() => void refs.refetch()} />}
      {list && (
        <div className="references-layout">
          <nav aria-label={t("references.lists")} className="card references-lists">
            <ul>
              {lists.map((l) => (
                <li key={l.key}>
                  <button
                    type="button"
                    className={`references-lists__item${l.key === list.key ? " is-active" : ""}`}
                    aria-current={l.key === list.key ? "true" : undefined}
                    onClick={() => setKey(l.key)}
                  >
                    <span>{listName(l, lang)}</span>
                    <span className="muted">{l.items.filter((i) => i.active).length}</span>
                  </button>
                </li>
              ))}
            </ul>
          </nav>
          <section className="card" aria-labelledby={`${id}-h`}>
            <div className="page__head">
              <h2 id={`${id}-h`}>{listName(list, lang)}</h2>
              <div className="actions">
                <input
                  type="search"
                  aria-label={t("references.search")}
                  placeholder={t("references.search")}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <button
                  type="button"
                  className="btn btn--small"
                  disabled={exporter.isPending}
                  onClick={() => exporter.mutate({ format: "csv", only: list.key })}
                >
                  CSV
                </button>
                <button
                  type="button"
                  className="btn btn--small"
                  disabled={exporter.isPending}
                  onClick={() => exporter.mutate({ format: "xlsx", only: list.key })}
                >
                  Excel
                </button>
              </div>
            </div>
            <div className="table-wrap">
              <table className="table table--compact">
                <caption className="visually-hidden">{listName(list, lang)}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("references.code")}</th>
                    <th scope="col">{t("references.label")}</th>
                    <th scope="col">{t("references.labelFr")}</th>
                    {list.key === "crop_loss" && <th scope="col">{t("references.unit")}</th>}
                    <th scope="col">{t("references.state")}</th>
                    <th scope="col">{t("references.updated")}</th>
                    {manage && (
                      <th scope="col">
                        <span className="visually-hidden">{t("references.actions")}</span>
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {shown.map((i) => (
                    <ItemRow key={i.id} item={i} list={list} manage={manage} />
                  ))}
                </tbody>
              </table>
            </div>
            {manage && (
              <form
                className="filters__row"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (label.trim()) add.mutate();
                }}
              >
                <div className="field">
                  <label htmlFor={`${id}-code`}>{t("references.code")}</label>
                  <input id={`${id}-code`} value={code} maxLength={20} size={6} onChange={(e) => setCode(e.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor={`${id}-label`}>{t("references.newLabel")}</label>
                  <input id={`${id}-label`} value={label} maxLength={160} dir="rtl" onChange={(e) => setLabel(e.target.value)} />
                </div>
                <button type="submit" className="btn btn--primary" disabled={!label.trim() || add.isPending}>
                  {t("references.add")}
                </button>
                {add.error ? (
                  <p className="alert alert--error" role="alert">
                    {t(errorMessageKey(add.error))}
                  </p>
                ) : null}
              </form>
            )}
          </section>
        </div>
      )}
      {exporter.error ? (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(exporter.error))}
        </p>
      ) : null}
    </div>
  );
}
