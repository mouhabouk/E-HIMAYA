import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "../../components/Badges";
import { ConfirmDialog, Dialog } from "../../components/Dialog";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useServices } from "../../context/services";
import { useFormat } from "../../lib/hooks";
import { queryKeys } from "../../lib/portalApi";
import { ACTIVITY_KINDS, type ActivityInput, type ActivityKind, type OrgActivity } from "../../lib/types";
import { isIntInRange, parseNumber } from "../../lib/validators";
import { BlockedNote, useOrg } from "./OrgWorkspace";
import { describedBy, Field, RequiredNote } from "./RegisterParts";

interface Draft {
  kind: ActivityKind;
  title: string;
  starts_on: string;
  ends_on: string;
  participants: string;
  notes: string;
}

/** Today in the browser's time zone, as `YYYY-MM-DD`. */
export function today(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Error keys by field; empty when the draft can be sent. The server checks the same rules. */
export function validateActivity(d: Draft, now: string = today()): Partial<Record<keyof Draft, string>> {
  const errors: Partial<Record<keyof Draft, string>> = {};
  if (!d.title.trim()) errors.title = "validation.required";
  if (!d.starts_on) errors.starts_on = "validation.required";
  else if (d.kind === "drill" && d.starts_on > now) errors.starts_on = "activities.drillInFuture";
  if (d.kind === "event" && d.ends_on && d.starts_on && d.ends_on < d.starts_on) errors.ends_on = "activities.endBeforeStart";
  if (d.participants.trim() && !isIntInRange(parseNumber(d.participants), 0, 1_000_000)) {
    errors.participants = "activities.participantsInvalid";
  }
  return errors;
}

function toInput(d: Draft): ActivityInput {
  return {
    kind: d.kind,
    title: d.title.trim(),
    starts_on: d.starts_on,
    ends_on: d.kind === "event" && d.ends_on ? d.ends_on : null,
    participants: d.participants.trim() ? parseNumber(d.participants) : null,
    notes: d.notes.trim() || null,
  };
}

function ActivityDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { org } = useOrg();
  const { api } = useServices();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>(() => ({
    kind: "drill",
    title: "",
    starts_on: today(),
    ends_on: "",
    participants: "",
    notes: "",
  }));
  const [errors, setErrors] = useState<Partial<Record<keyof Draft, string>>>({});
  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));
  const err = (k: keyof Draft) => (errors[k] ? t(errors[k]) : null);
  const save = useMutation({
    mutationFn: (input: ActivityInput) => api.addActivity(org.id, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.activities(org.id) });
      onClose();
    },
  });

  function submit(e: SubmitEvent) {
    e.preventDefault();
    const found = validateActivity(draft);
    setErrors(found);
    if (Object.keys(found).length) return;
    save.mutate(toInput(draft));
  }

  return (
    <Dialog title={t("activities.addTitle")} onClose={onClose}>
      <form className="form" onSubmit={submit} noValidate>
        <RequiredNote />
        <p className="muted">{t("activities.help")}</p>
        <div className="form-grid">
          <Field id="act-kind" label={t("activities.kind")}>
            <select id="act-kind" value={draft.kind} onChange={(e) => set({ kind: e.target.value as ActivityKind })}>
              {ACTIVITY_KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`activities.kinds.${k}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field id="act-title" label={t("activities.titleLabel")} required error={err("title")}>
            <input
              id="act-title"
              maxLength={120}
              value={draft.title}
              aria-invalid={!!errors.title}
              aria-describedby={describedBy("act-title", null, errors.title)}
              onChange={(e) => set({ title: e.target.value })}
            />
          </Field>
          <Field id="act-starts" label={t("activities.startsOn")} required error={err("starts_on")}>
            <input
              id="act-starts"
              type="date"
              value={draft.starts_on}
              aria-invalid={!!errors.starts_on}
              aria-describedby={describedBy("act-starts", null, errors.starts_on)}
              onChange={(e) => set({ starts_on: e.target.value })}
            />
          </Field>
          {draft.kind === "event" && (
            <Field id="act-ends" label={t("activities.endsOn")} error={err("ends_on")}>
              <input
                id="act-ends"
                type="date"
                value={draft.ends_on}
                aria-invalid={!!errors.ends_on}
                aria-describedby={describedBy("act-ends", null, errors.ends_on)}
                onChange={(e) => set({ ends_on: e.target.value })}
              />
            </Field>
          )}
          <Field id="act-participants" label={t("activities.participants")} error={err("participants")}>
            <input
              id="act-participants"
              inputMode="numeric"
              value={draft.participants}
              aria-invalid={!!errors.participants}
              aria-describedby={describedBy("act-participants", null, errors.participants)}
              onChange={(e) => set({ participants: e.target.value })}
            />
          </Field>
          <Field id="act-notes" label={t("activities.notes")}>
            <textarea id="act-notes" rows={3} maxLength={1000} value={draft.notes} onChange={(e) => set({ notes: e.target.value })} />
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

/** Phase P2b: drills held and public events declared, so the Office knows and can prepare. */
export function ActivitiesTab() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const fmt = useFormat();
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<OrgActivity | null>(null);
  const editable = can("editActivities");
  const list = useQuery({ queryKey: queryKeys.activities(org.id), queryFn: ({ signal }) => api.activities(org.id, signal) });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteActivity(org.id, id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.activities(org.id) });
      setDeleting(null);
    },
  });

  if (list.isPending) return <Loading />;
  if (list.isError) return <ErrorBox error={list.error} onRetry={() => void list.refetch()} />;

  return (
    <section className="card" aria-labelledby="activities-title">
      <div className="section-head">
        <h2 id="activities-title">{t("activities.title")}</h2>
        {editable && (
          <button type="button" className="btn btn--primary" onClick={() => setAdding(true)}>
            {t("activities.add")}
          </button>
        )}
      </div>
      <p className="muted">{t("activities.help")}</p>
      <BlockedNote action="editActivities" />
      {list.data.length === 0 ? (
        <p className="empty">{t("activities.empty")}</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("activities.titleLabel")}</th>
                <th scope="col">{t("activities.kind")}</th>
                <th scope="col">{t("activities.dates")}</th>
                <th scope="col" className="num">
                  {t("activities.participants")}
                </th>
                <th scope="col">{t("activities.createdBy")}</th>
                {editable && <th scope="col">{t("common.actions")}</th>}
              </tr>
            </thead>
            <tbody>
              {list.data.map((a) => (
                <tr key={a.id}>
                  <th scope="row" dir="auto">
                    {a.title}
                    {a.notes && <span className="muted cell-sub">{a.notes}</span>}
                  </th>
                  <td>
                    <Badge tone={a.kind === "event" ? "info" : "warn"}>{t(`activities.kinds.${a.kind}`)}</Badge>
                  </td>
                  <td>
                    {fmt.date(a.starts_on)}
                    {a.ends_on && ` – ${fmt.date(a.ends_on)}`}
                  </td>
                  <td className="num">{a.participants !== null ? fmt.number(a.participants) : "—"}</td>
                  <td>{a.created_by ?? "—"}</td>
                  {editable && (
                    <td>
                      <button
                        type="button"
                        className="btn btn--small"
                        aria-label={t("activities.deleteOne", { title: a.title })}
                        onClick={() => setDeleting(a)}
                      >
                        {t("common.delete")}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {adding && <ActivityDialog onClose={() => setAdding(false)} />}
      {deleting && (
        <ConfirmDialog
          title={t("activities.deleteTitle")}
          body={t("activities.deleteBody", { title: deleting.title })}
          confirmLabel={t("common.delete")}
          danger
          busy={remove.isPending}
          onConfirm={() => remove.mutate(deleting.id)}
          onClose={() => {
            remove.reset();
            setDeleting(null);
          }}
        >
          {remove.isError && <ErrorBox error={remove.error} />}
        </ConfirmDialog>
      )}
    </section>
  );
}
