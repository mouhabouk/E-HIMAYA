import { useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";
import { TrainingBadge } from "../../components/Badges";
import { Dialog } from "../../components/Dialog";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useFormat } from "../../lib/hooks";
import { TEAM_ROLES, type TeamMember, type TeamMemberInput, type TeamRole } from "../../lib/types";
import { isIntInRange, isValidEmail, isValidPhone, normalizePhone, parseNumber } from "../../lib/validators";
import { BlockedNote, useOrg } from "./OrgWorkspace";
import { Field, RowActions, describedBy } from "./RegisterParts";
import { useRegister } from "./useRegister";

interface Draft {
  full_name: string;
  team_role: TeamRole;
  position: string;
  phone: string;
  email: string;
  last_training_on: string;
  training_valid_months: string;
}

function toDraft(m: TeamMember | null, defaultRole: TeamRole): Draft {
  return {
    full_name: m?.full_name ?? "",
    team_role: m?.team_role ?? defaultRole,
    position: m?.position ?? "",
    phone: m?.phone ?? "",
    email: m?.email ?? "",
    last_training_on: m?.last_training_on ?? "",
    training_valid_months: String(m?.training_valid_months ?? 24),
  };
}

function validate(d: Draft): Partial<Record<keyof Draft, string>> {
  const e: Partial<Record<keyof Draft, string>> = {};
  if (!d.full_name.trim()) e.full_name = "validation.required";
  if (d.phone.trim() && !isValidPhone(d.phone)) e.phone = "validation.phone";
  if (d.email.trim() && !isValidEmail(d.email)) e.email = "validation.email";
  if (!isIntInRange(parseNumber(d.training_valid_months), 1, 120)) e.training_valid_months = "validation.months120";
  return e;
}

function toInput(d: Draft): TeamMemberInput {
  return {
    full_name: d.full_name.trim(),
    team_role: d.team_role,
    position: d.position.trim() || null,
    phone: d.phone.trim() ? normalizePhone(d.phone) : null,
    email: d.email.trim() || null,
    last_training_on: d.last_training_on || null,
    training_valid_months: parseNumber(d.training_valid_months) ?? 24,
  };
}

function MemberDialog({
  member,
  hasOtherRepresentative,
  onClose,
  save,
}: {
  member: TeamMember | null;
  hasOtherRepresentative: boolean;
  onClose: () => void;
  save: ReturnType<typeof useRegister<"team">>["save"];
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(() => toDraft(member, hasOtherRepresentative ? "member" : "representative"));
  const [errors, setErrors] = useState<Partial<Record<keyof Draft, string>>>({});
  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));

  function submit(e: SubmitEvent) {
    e.preventDefault();
    const found = validate(draft);
    setErrors(found);
    if (Object.keys(found).length) return;
    save.mutate({ id: member?.id ?? null, input: toInput(draft) }, { onSuccess: onClose });
  }
  const err = (k: keyof Draft) => (errors[k] ? t(errors[k]) : null);

  return (
    <Dialog title={member ? t("team.editTitle") : t("team.addTitle")} onClose={onClose}>
      <form className="form" onSubmit={submit} noValidate>
        <div className="form-grid">
          <Field id="tm-name" label={t("team.fullName")} required error={err("full_name")}>
            <input id="tm-name" value={draft.full_name} aria-invalid={!!errors.full_name} aria-describedby={describedBy("tm-name", null, errors.full_name)} onChange={(e) => set({ full_name: e.target.value })} />
          </Field>
          <fieldset className="field">
            <legend>{t("team.teamRole")}</legend>
            <div className="radios">
              {TEAM_ROLES.map((r) => (
                <label key={r} className="radio">
                  <input
                    type="radio"
                    name="team_role"
                    value={r}
                    checked={draft.team_role === r}
                    disabled={r === "representative" && hasOtherRepresentative}
                    onChange={() => set({ team_role: r })}
                  />
                  {t(`teamRoles.${r}`)}
                </label>
              ))}
            </div>
            {hasOtherRepresentative && <span className="field__hint">{t("team.oneRepresentative")}</span>}
          </fieldset>
          <Field id="tm-position" label={t("team.position")}>
            <input id="tm-position" value={draft.position} onChange={(e) => set({ position: e.target.value })} />
          </Field>
          <Field id="tm-phone" label={t("team.phone")} hint={t("org.phoneHint")} error={err("phone")}>
            <input id="tm-phone" type="tel" dir="ltr" value={draft.phone} aria-invalid={!!errors.phone} aria-describedby={describedBy("tm-phone", true, errors.phone)} onChange={(e) => set({ phone: e.target.value })} />
          </Field>
          <Field id="tm-email" label={t("team.email")} error={err("email")}>
            <input id="tm-email" type="email" dir="ltr" value={draft.email} aria-invalid={!!errors.email} aria-describedby={describedBy("tm-email", null, errors.email)} onChange={(e) => set({ email: e.target.value })} />
          </Field>
          <Field id="tm-training" label={t("team.lastTraining")}>
            <input id="tm-training" type="date" value={draft.last_training_on} onChange={(e) => set({ last_training_on: e.target.value })} />
          </Field>
          <Field id="tm-months" label={t("team.validMonths")} hint={t("team.validMonthsHint")} error={err("training_valid_months")}>
            <input id="tm-months" inputMode="numeric" value={draft.training_valid_months} aria-invalid={!!errors.training_valid_months} aria-describedby={describedBy("tm-months", true, errors.training_valid_months)} onChange={(e) => set({ training_valid_months: e.target.value })} />
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

/** Safety team (FR-B-005): representative + members with their training status. */
export function TeamTab() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const fmt = useFormat();
  const { list, save, remove } = useRegister(org.id, "team");
  const [editing, setEditing] = useState<TeamMember | "new" | null>(null);
  const editable = can("editRegisters");

  if (list.isPending) return <Loading />;
  if (list.isError) return <ErrorBox error={list.error} onRetry={() => void list.refetch()} />;
  const team = list.data;
  const representative = team.find((m) => m.team_role === "representative");
  const current = editing === "new" ? null : editing;

  return (
    <section className="card" aria-labelledby="team-title">
      <div className="section-head">
        <h2 id="team-title">{t("team.title")}</h2>
        {editable && (
          <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
            {t("team.add")}
          </button>
        )}
      </div>
      <p className="muted">{t("team.help")}</p>
      <BlockedNote action="editRegisters" />
      {!representative && <p className="alert alert--warn">{t("team.noRepresentative")}</p>}
      {team.length === 0 ? (
        <p className="empty">{t("team.empty")}</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("team.fullName")}</th>
                <th scope="col">{t("team.teamRole")}</th>
                <th scope="col">{t("team.position")}</th>
                <th scope="col">{t("team.contact")}</th>
                <th scope="col">{t("team.training")}</th>
                <th scope="col">{t("team.expires")}</th>
                {editable && <th scope="col">{t("common.actions")}</th>}
              </tr>
            </thead>
            <tbody>
              {team.map((m) => (
                <tr key={m.id}>
                  <th scope="row">{m.full_name}</th>
                  <td>{t(`teamRoles.${m.team_role}`)}</td>
                  <td>{m.position ?? "—"}</td>
                  <td>
                    {m.phone && (
                      <a href={`tel:${m.phone}`} dir="ltr">
                        {m.phone}
                      </a>
                    )}
                    {m.email && <div className="muted">{m.email}</div>}
                  </td>
                  <td>
                    <TrainingBadge status={m.training_status} />
                    {m.last_training_on && <div className="muted">{t("team.trainedOn", { date: fmt.date(m.last_training_on) })}</div>}
                  </td>
                  <td>{fmt.date(m.training_expires_on)}</td>
                  {editable && (
                    <td>
                      <RowActions name={m.full_name} editable={editable} onEdit={() => setEditing(m)} remove={remove} id={m.id} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && (
        <MemberDialog
          member={current}
          hasOtherRepresentative={!!representative && representative.id !== current?.id}
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
