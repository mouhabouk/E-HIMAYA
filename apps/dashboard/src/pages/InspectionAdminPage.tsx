// covers: phase I2 (docs/phase-i/design-i.md §8): the system administrator alone deletes inspection reports (one, a
// period or all), with a reason of ten characters at least and the word «حذف» typed to confirm; a deleted report goes
// to the bin, from which it is restored. The bin prints and exports.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat } from "../lib/hooks";
import { CONFIRM_WORD, exportCsv, inspectionKeys, type DeleteInput } from "../lib/inspectionsApi";

export const MIN_DELETE_REASON = 10;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
type Scope = DeleteInput["scope"];

/** Whether the deletion form may be sent (the API checks it again). */
export function deleteReady(input: DeleteInput): boolean {
  if (input.reason.trim().length < MIN_DELETE_REASON || input.confirm.trim() !== CONFIRM_WORD) return false;
  if (input.scope === "one") return UUID.test(input.inspection_id?.trim() ?? "");
  if (input.scope === "period") return Boolean(input.from_date && input.to_date && input.from_date <= input.to_date);
  return true;
}

export function InspectionAdminPage() {
  const { t } = useTranslation();
  return (
    <div className="page inspections-page">
      <div className="page__head">
        <PageTitle print icon="delete" tone="red">
          {t("inspections.admin.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("inspections.admin.intro")}</p>
      <DeleteForm />
      <Bin />
    </div>
  );
}

function DeleteForm() {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const ids = { scope: useId(), one: useId(), from: useId(), to: useId(), reason: useId(), confirm: useId() };
  const [scope, setScope] = useState<Scope>("one");
  const [inspectionId, setInspectionId] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState<number | null>(null);
  const input: DeleteInput = {
    scope,
    inspection_id: scope === "one" ? inspectionId.trim() : null,
    from_date: scope === "period" ? from : null,
    to_date: scope === "period" ? to : null,
    reason: reason.trim(),
    confirm: confirm.trim(),
  };
  const remove = useMutation({
    mutationFn: () => api.deleteInspections(input),
    onSuccess: (r) => {
      setDone(r.deleted);
      setReason("");
      setConfirm("");
      setInspectionId("");
      void qc.invalidateQueries({ queryKey: inspectionKeys.bin });
      void qc.invalidateQueries({ queryKey: inspectionKeys.all });
      void qc.invalidateQueries({ queryKey: inspectionKeys.results });
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (deleteReady(input)) remove.mutate();
  };
  return (
    <section className="card no-print">
      <h2>{t("inspections.admin.deleteTitle")}</h2>
      <form className="form-grid" onSubmit={submit}>
        <div className="field">
          <label htmlFor={ids.scope}>{t("inspections.admin.scopeLabel")}</label>
          <select id={ids.scope} value={scope} onChange={(e) => setScope(e.target.value as Scope)}>
            <option value="one">{t("inspections.admin.scope.one")}</option>
            <option value="period">{t("inspections.admin.scope.period")}</option>
            <option value="all">{t("inspections.admin.scope.all")}</option>
          </select>
        </div>
        {scope === "one" && (
          <div className="field">
            <label htmlFor={ids.one}>{t("inspections.admin.reportId")}</label>
            <input id={ids.one} dir="ltr" value={inspectionId} onChange={(e) => setInspectionId(e.target.value)} />
          </div>
        )}
        {scope === "period" && (
          <>
            <div className="field">
              <label htmlFor={ids.from}>{t("inspections.from")}</label>
              <input id={ids.from} type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor={ids.to}>{t("inspections.to")}</label>
              <input id={ids.to} type="date" value={to} onChange={(e) => setTo(e.target.value)} />
            </div>
          </>
        )}
        {scope === "all" && (
          <p className="alert alert--warning" role="note">
            {t("inspections.admin.allWarning")}
          </p>
        )}
        <div className="field">
          <label htmlFor={ids.reason}>{t("inspections.admin.reason", { n: MIN_DELETE_REASON })}</label>
          <textarea id={ids.reason} rows={2} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={ids.confirm}>{t("inspections.admin.confirm", { word: CONFIRM_WORD })}</label>
          <input id={ids.confirm} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" />
        </div>
        <div className="actions">
          <button type="submit" className="btn btn--danger" disabled={!deleteReady(input) || remove.isPending}>
            <Icon name="delete" size={18} />
            {t("inspections.admin.delete")}
          </button>
        </div>
      </form>
      {remove.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(remove.error))}
        </p>
      )}
      {done !== null && !remove.isError && (
        <p className="alert alert--ok" role="status">
          {t("inspections.admin.deleted", { n: done })}
        </p>
      )}
    </section>
  );
}

function Bin() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: inspectionKeys.bin, queryFn: ({ signal }) => api.inspectionBin(signal) });
  const restore = useMutation({
    mutationFn: (id: string) => api.restoreInspection(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: inspectionKeys.bin });
      void qc.invalidateQueries({ queryKey: inspectionKeys.all });
      void qc.invalidateQueries({ queryKey: inspectionKeys.results });
    },
  });
  const rows = q.data ?? [];
  const exportRows = () =>
    exportCsv(
      "inspections-bin",
      [
        t("inspections.columns.place"),
        t("inspections.columns.submittedAt"),
        t("inspections.admin.deletedAt"),
        t("inspections.admin.deletedBy"),
        t("inspections.admin.reasonColumn"),
      ],
      rows.map((r) => [
        r.place,
        r.submitted_at ? fmt.dateTime(r.submitted_at) : "",
        fmt.dateTime(r.deleted_at),
        r.deleted_by_name,
        r.delete_reason,
      ]),
    );
  return (
    <section className="card">
      <div className="inspections-head">
        <h2>{t("inspections.admin.bin")}</h2>
        <button type="button" className="btn btn--ghost btn--small no-print" onClick={exportRows} disabled={rows.length === 0}>
          <Icon name="download" size={18} />
          {t("inspections.export")}
        </button>
      </div>
      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorBox error={q.error} />
      ) : rows.length === 0 ? (
        <p className="empty">{t("inspections.admin.binEmpty")}</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t("inspections.columns.place")}</th>
              <th scope="col">{t("inspections.columns.submittedAt")}</th>
              <th scope="col">{t("inspections.admin.deletedAt")}</th>
              <th scope="col">{t("inspections.admin.deletedBy")}</th>
              <th scope="col">{t("inspections.admin.reasonColumn")}</th>
              <th scope="col" className="no-print">
                <span className="visually-hidden">{t("inspections.admin.restore")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.place}</td>
                <td>{r.submitted_at ? fmt.dateTime(r.submitted_at) : "—"}</td>
                <td>{fmt.dateTime(r.deleted_at)}</td>
                <td>{r.deleted_by_name ?? "—"}</td>
                <td>{r.delete_reason ?? "—"}</td>
                <td className="no-print">
                  <button
                    type="button"
                    className="btn btn--ghost btn--small"
                    onClick={() => restore.mutate(r.id)}
                    disabled={restore.isPending}
                  >
                    {t("inspections.admin.restore")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {restore.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(restore.error))}
        </p>
      )}
    </section>
  );
}
