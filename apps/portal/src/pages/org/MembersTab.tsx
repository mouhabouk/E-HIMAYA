import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { RoleBadge } from "../../components/Badges";
import { CopyButton } from "../../components/CopyButton";
import { ConfirmDialog, Dialog } from "../../components/Dialog";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useAuth } from "../../context/auth";
import { useServices } from "../../context/services";
import { useFormat } from "../../lib/hooks";
import { queryKeys } from "../../lib/portalApi";
import { ORG_ROLES, type CreatedInvitation, type Member, type OrgRole } from "../../lib/types";
import { isValidEmail } from "../../lib/validators";
import { BlockedNote, useOrg } from "./OrgWorkspace";
import { Field } from "./RegisterParts";

/**
 * The caller's own membership. The contract identifies members by the API's `user_id`, which the token
 * does not carry, so the verified e-mail of the token is matched (members' e-mails come from their claims).
 */
export function findMe(members: readonly Member[], email: string | null | undefined): Member | null {
  if (!email) return null;
  const e = email.toLowerCase();
  return members.find((m) => m.email?.toLowerCase() === e) ?? null;
}

function MemberRow({ member, isMe, admin }: { member: Member; isMe: boolean; admin: boolean }) {
  const { t } = useTranslation();
  const { org } = useOrg();
  const { api } = useServices();
  const fmt = useFormat();
  const queryClient = useQueryClient();
  const [removing, setRemoving] = useState(false);
  const name = member.display_name ?? member.email ?? t("members.unnamed");
  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.members(org.id) });
  const setRole = useMutation({
    mutationFn: (role: OrgRole) => api.setMemberRole(org.id, member.user_id, role),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: () => api.removeMember(org.id, member.user_id), onSuccess: refresh });

  return (
    <tr>
      <th scope="row">
        {name}
        {isMe && <span className="tag">{t("members.you")}</span>}
      </th>
      <td dir="ltr" className="cell-start">
        {member.email ?? "—"}
      </td>
      <td>
        {admin ? (
          <>
            <label className="visually-hidden" htmlFor={`role-${member.user_id}`}>
              {t("members.roleOf", { name })}
            </label>
            <select
              id={`role-${member.user_id}`}
              value={member.role}
              disabled={setRole.isPending}
              onChange={(e) => setRole.mutate(e.target.value as OrgRole)}
            >
              {ORG_ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`roles.${r}`)}
                </option>
              ))}
            </select>
            {setRole.isError && <ErrorBox error={setRole.error} />}
          </>
        ) : (
          <RoleBadge role={member.role} />
        )}
      </td>
      <td>{fmt.date(member.joined_at)}</td>
      {admin && (
        <td>
          {!isMe && (
            <button type="button" className="btn btn--small btn--danger-ghost" onClick={() => setRemoving(true)} aria-label={t("members.removeNamed", { name })}>
              {t("members.remove")}
            </button>
          )}
          {removing && (
            <ConfirmDialog
              title={t("members.remove")}
              body={t("members.confirmRemove", { name })}
              confirmLabel={t("members.remove")}
              danger
              busy={remove.isPending}
              onConfirm={() => remove.mutate(undefined, { onSuccess: () => setRemoving(false) })}
              onClose={() => {
                remove.reset();
                setRemoving(false);
              }}
            >
              {remove.isError && <ErrorBox error={remove.error} />}
            </ConfirmDialog>
          )}
        </td>
      )}
    </tr>
  );
}

function InviteForm() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<OrgRole>("member");
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreatedInvitation | null>(null);
  const invite = useMutation({
    mutationFn: () => api.invite(org.id, email.trim(), role),
    onSuccess: (inv) => {
      setCreated(inv);
      setEmail("");
      void queryClient.invalidateQueries({ queryKey: queryKeys.invitations(org.id) });
    },
  });
  const allowed = can("invite");

  function submit(e: SubmitEvent) {
    e.preventDefault();
    if (!isValidEmail(email)) {
      setError("validation.email");
      return;
    }
    setError(null);
    invite.mutate();
  }

  return (
    <form className="form" onSubmit={submit} noValidate>
      <h3>{t("members.inviteTitle")}</h3>
      <BlockedNote action="invite" />
      <div className="form-row">
        <Field id="inv-email" label={t("members.inviteEmail")} required error={error ? t(error) : null}>
          <input id="inv-email" type="email" dir="ltr" value={email} disabled={!allowed} aria-invalid={!!error} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field id="inv-role" label={t("members.inviteRole")}>
          <select id="inv-role" value={role} disabled={!allowed} onChange={(e) => setRole(e.target.value as OrgRole)}>
            {ORG_ROLES.map((r) => (
              <option key={r} value={r}>
                {t(`roles.${r}`)}
              </option>
            ))}
          </select>
        </Field>
        <button type="submit" className="btn btn--primary" disabled={!allowed || invite.isPending}>
          {t("members.invite")}
        </button>
      </div>
      <p className="muted">{t(`roleHelp.${role}`)}</p>
      {invite.isError && <ErrorBox error={invite.error} />}
      {created && (
        <Dialog title={t("members.linkTitle")} onClose={() => setCreated(null)}>
          <p>{t("members.linkBody", { email: created.email, role: t(`roles.${created.role}`) })}</p>
          <p className="alert alert--warn">{t("members.linkOnce")}</p>
          <label htmlFor="invite-link" className="field__label">
            {t("members.link")}
          </label>
          <input id="invite-link" className="code link-box" dir="ltr" readOnly value={created.accept_url} onFocus={(e) => e.target.select()} />
          <div className="actions">
            <CopyButton text={created.accept_url} label={t("members.copyLink")} />
          </div>
          <div className="actions actions--end">
            <button type="button" className="btn btn--primary" onClick={() => setCreated(null)}>
              {t("common.done")}
            </button>
          </div>
        </Dialog>
      )}
    </form>
  );
}

function Invitations() {
  const { t } = useTranslation();
  const { org } = useOrg();
  const { api } = useServices();
  const fmt = useFormat();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: queryKeys.invitations(org.id), queryFn: ({ signal }) => api.invitations(org.id, signal) });
  const revoke = useMutation({
    mutationFn: (id: string) => api.revokeInvitation(org.id, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.invitations(org.id) }),
  });
  return (
    <section className="card" aria-labelledby="inv-title">
      <h2 id="inv-title">{t("members.invitationsTitle")}</h2>
      <InviteForm />
      <h3>{t("members.pending")}</h3>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      ) : query.data.length === 0 ? (
        <p className="empty">{t("members.noPending")}</p>
      ) : (
        <ul className="plain-list">
          {query.data.map((inv) => (
            <li key={inv.id} className="plain-list__item">
              <span dir="ltr">{inv.email}</span>
              <RoleBadge role={inv.role} />
              <span className="muted">{t("members.expires", { date: fmt.dateTime(inv.expires_at) })}</span>
              <button
                type="button"
                className="btn btn--small btn--danger-ghost"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate(inv.id)}
                aria-label={t("members.revokeNamed", { email: inv.email })}
              >
                {t("members.revoke")}
              </button>
            </li>
          ))}
        </ul>
      )}
      {revoke.isError && <ErrorBox error={revoke.error} />}
    </section>
  );
}

function LeaveSection({ me }: { me: Member | null }) {
  const { t } = useTranslation();
  const { org } = useOrg();
  const { api } = useServices();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const leave = useMutation({
    mutationFn: () => api.removeMember(org.id, me?.user_id ?? ""),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: queryKeys.org(org.id) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.myOrgs });
      void navigate("/orgs/mine");
    },
  });
  return (
    <section className="card" aria-labelledby="leave-title">
      <h2 id="leave-title">{t("members.leaveTitle")}</h2>
      <p className="muted">{t("members.leaveBody")}</p>
      {!me && <p className="muted">{t("members.leaveUnavailable")}</p>}
      <button type="button" className="btn btn--danger" disabled={!me} onClick={() => setConfirm(true)}>
        {t("members.leave")}
      </button>
      {confirm && (
        <ConfirmDialog
          title={t("members.leaveTitle")}
          body={t("members.confirmLeave", { name: org.name })}
          confirmLabel={t("members.leave")}
          danger
          busy={leave.isPending}
          onConfirm={() => leave.mutate()}
          onClose={() => {
            leave.reset();
            setConfirm(false);
          }}
        >
          {leave.isError && <ErrorBox error={leave.error} />}
        </ConfirmDialog>
      )}
    </section>
  );
}

/** Members, roles and invitations (FR-B-009). */
export function MembersTab() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const { user } = useAuth();
  const query = useQuery({ queryKey: queryKeys.members(org.id), queryFn: ({ signal }) => api.members(org.id, signal) });
  const admin = can("manageMembers");

  if (query.isPending) return <Loading />;
  if (query.isError) return <ErrorBox error={query.error} onRetry={() => void query.refetch()} />;
  const me = findMe(query.data, user?.identity.email);

  return (
    <div className="stack">
      <section className="card" aria-labelledby="members-title">
        <h2 id="members-title">{t("members.title")}</h2>
        <p className="muted">{t("members.help")}</p>
        <BlockedNote action="manageMembers" />
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("members.name")}</th>
                <th scope="col">{t("members.email")}</th>
                <th scope="col">{t("members.role")}</th>
                <th scope="col">{t("members.joined")}</th>
                {admin && <th scope="col">{t("common.actions")}</th>}
              </tr>
            </thead>
            <tbody>
              {query.data.map((m) => (
                <MemberRow key={m.user_id} member={m} isMe={m.user_id === me?.user_id} admin={admin} />
              ))}
            </tbody>
          </table>
        </div>
        <dl className="role-help">
          {ORG_ROLES.map((r) => (
            <div key={r}>
              <dt>{t(`roles.${r}`)}</dt>
              <dd>{t(`roleHelp.${r}`)}</dd>
            </div>
          ))}
        </dl>
      </section>
      {admin && <Invitations />}
      <LeaveSection me={me} />
    </div>
  );
}
