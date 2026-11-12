// covers: OS3 (Yamen 2026-11-11: «Profil للقراءة والكتابة أو للقراءة فقط لمنحه للمتفقد العام مثلا أو غيره»): a profile
// gathers pages, each read only (the page and its tabs) or read and write (its buttons too); the system administrator
// grants it in one go to an account or a role, and revokes it in one go. The fixed ceiling still holds: what the target
// may never receive is skipped and listed.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "./Feedback";
import { ReasonField } from "./Phase9Bits";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import type { Feature } from "../lib/features";
import { fleetKeys, type Profile, type ProfileAssignment, type ProfileMode } from "../lib/fleet";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { REASON_RANGE, reasonValid } from "../lib/phase9";
import { STAFF_ROLES } from "../lib/roles";

function useInvalidate() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: fleetKeys.profiles });
    void qc.invalidateQueries({ queryKey: fleetKeys.assignments });
    void qc.invalidateQueries({ queryKey: ["features"] });
  };
}

function ProfileForm({ features, profile, onDone }: { features: Feature[]; profile: Profile | null; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const invalidate = useInvalidate();
  const id = useId();
  const pages = features.filter((f) => f.kind === "page" && f.grantable && f.nav);
  const [name, setName] = useState(profile?.name ?? "");
  const [description, setDescription] = useState(profile?.description ?? "");
  const [modes, setModes] = useState<Record<string, ProfileMode | "">>(
    Object.fromEntries((profile?.items ?? []).map((i) => [i.page, i.mode])),
  );
  const [tried, setTried] = useState(false);
  const items = Object.entries(modes)
    .filter(([, m]) => m)
    .map(([page, mode]) => ({ page, mode: mode as ProfileMode }));
  const missing = name.trim().length < 3 || items.length === 0;
  const save = useMutation({
    mutationFn: () => api.saveFeatureProfile(profile?.id ?? null, { name: name.trim(), description: description.trim() || null, items }),
    onSuccess: () => {
      invalidate();
      onDone();
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (!missing) save.mutate();
  };
  return (
    <form className="card perm-form" noValidate onSubmit={submit}>
      <h3>{profile ? t("profiles.editTitle", { name: profile.name }) : t("profiles.newTitle")}</h3>
      <div className="perm-form__row">
        <div className="field">
          <label htmlFor={`${id}-name`}>{t("profiles.name")}</label>
          <input id={`${id}-name`} dir="auto" maxLength={120} value={name} aria-invalid={tried && name.trim().length < 3} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-desc`}>{t("profiles.description")}</label>
          <input id={`${id}-desc`} dir="auto" maxLength={500} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
      </div>
      <div className="table-wrap">
        <table className="table">
          <caption>{t("profiles.pages")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("profiles.page")}</th>
              <th scope="col">{t("profiles.mode")}</th>
            </tr>
          </thead>
          <tbody>
            {pages.map((p) => (
              <tr key={p.key}>
                <th scope="row">{p.names[lang] || p.names.ar}</th>
                <td>
                  <select
                    aria-label={t("profiles.modeOf", { page: p.names[lang] || p.names.ar })}
                    value={modes[p.key] ?? ""}
                    onChange={(e) => setModes({ ...modes, [p.key]: e.target.value as ProfileMode | "" })}
                  >
                    <option value="">{t("profiles.modes.none")}</option>
                    <option value="read">{t("profiles.modes.read")}</option>
                    <option value="write">{t("profiles.modes.write")}</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {tried && missing && (
        <p className="field__error" role="alert">
          {t("profiles.missing")}
        </p>
      )}
      {save.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(save.error))}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={save.isPending}>
          {t("profiles.save")}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onDone}>
          {t("profiles.cancel")}
        </button>
      </div>
    </form>
  );
}

function AssignForm({ profile, onDone }: { profile: Profile; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const invalidate = useInvalidate();
  const id = useId();
  const [kind, setKind] = useState<"user" | "role">("user");
  const [role, setRole] = useState("operator");
  const [account, setAccount] = useState("");
  const [accountName, setAccountName] = useState("");
  const [gouvernorat, setGouvernorat] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const assign = useMutation({
    mutationFn: () =>
      api.assignFeatureProfile(profile.id, {
        target_kind: kind,
        target: kind === "role" ? role : account.trim(),
        target_name: kind === "user" ? accountName.trim() || null : null,
        gouvernorat_code: kind === "role" && gouvernorat ? Number(gouvernorat) : null,
        reason: reason.trim(),
        starts_at: from ? new Date(from).toISOString() : null,
        ends_at: to ? new Date(to).toISOString() : null,
      }),
    onSuccess: invalidate,
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if ((kind === "user" && !account.trim()) || !reasonValid(reason)) return;
    assign.mutate();
  };
  const skipped = assign.data?.skipped ?? [];
  const refused = (() => {
    if (!assign.isError) return null;
    const err = assign.error;
    if (isApiError(err) && err.code === "profile_grants_nothing") return t("profiles.grantsNothing");
    return t(errorMessageKey(err));
  })();
  return (
    <form className="card perm-form" noValidate onSubmit={submit}>
      <h3>{t("profiles.assignTitle", { name: profile.name })}</h3>
      <fieldset className="perm-form__row">
        <legend>{t("permissions.target")}</legend>
        {(["user", "role"] as const).map((v) => (
          <label key={v} className="radio">
            <input type="radio" name={`${id}-kind`} checked={kind === v} onChange={() => setKind(v)} /> {t(`permissions.targets.${v}`)}
          </label>
        ))}
      </fieldset>
      {kind === "role" ? (
        <div className="perm-form__row">
          <div className="field">
            <label htmlFor={`${id}-role`}>{t("permissions.role")}</label>
            <select id={`${id}-role`} value={role} onChange={(e) => setRole(e.target.value)}>
              {STAFF_ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`roles.${r}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={`${id}-gouv`}>{t("permissions.gouvernorat")}</label>
            <select id={`${id}-gouv`} value={gouvernorat} onChange={(e) => setGouvernorat(e.target.value)}>
              <option value="">{t("permissions.everyGouvernorat")}</option>
              {gouvernorats.list.map((g) => (
                <option key={g.code} value={g.code}>
                  {gouvernorats.nameOf(g.code)}
                </option>
              ))}
            </select>
          </div>
        </div>
      ) : (
        <div className="perm-form__row">
          <div className="field">
            <label htmlFor={`${id}-account`}>{t("permissions.account")}</label>
            <input id={`${id}-account`} dir="ltr" value={account} aria-invalid={tried && !account.trim()} onChange={(e) => setAccount(e.target.value)} />
            <p className="field__hint">{t("permissions.accountHint")}</p>
          </div>
          <div className="field">
            <label htmlFor={`${id}-account-name`}>{t("permissions.accountName")}</label>
            <input id={`${id}-account-name`} value={accountName} onChange={(e) => setAccountName(e.target.value)} />
          </div>
        </div>
      )}
      <div className="perm-form__row">
        <div className="field">
          <label htmlFor={`${id}-from`}>{t("permissions.from")}</label>
          <input id={`${id}-from`} type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-to`}>{t("permissions.to")}</label>
          <input id={`${id}-to`} type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      </div>
      <ReasonField label={t("permissions.reason")} value={reason} onChange={setReason} range={REASON_RANGE} showError={tried} />
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={assign.isPending}>
          {t("profiles.assign")}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onDone}>
          {t("profiles.cancel")}
        </button>
      </div>
      {refused && (
        <p className="alert alert--error" role="alert">
          {refused}
        </p>
      )}
      {assign.isSuccess && (
        <p className="alert alert--success" role="status">
          {t("profiles.assigned", { n: assign.data.features.length })}
          {skipped.length > 0 && ` ${t("profiles.skipped", { keys: skipped.map((s) => s.feature_key).join("، ") })}`}
        </p>
      )}
    </form>
  );
}

function Assignments({ profiles }: { profiles: Profile[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const invalidate = useInvalidate();
  const q = useQuery({ queryKey: fleetKeys.assignments, queryFn: ({ signal }) => api.profileAssignments(signal) });
  const revoke = useMutation({
    mutationFn: (a: ProfileAssignment) => api.revokeProfileAssignment(a.id, t("profiles.revokeReason")),
    onSuccess: invalidate,
  });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorBox error={q.error} onRetry={() => void q.refetch()} />;
  if (q.data.length === 0) return <p className="muted">{t("profiles.noAssignment")}</p>;
  return (
    <div className="table-wrap">
      <table className="table">
        <caption>{t("profiles.assignments")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("profiles.profile")}</th>
            <th scope="col">{t("permissions.target")}</th>
            <th scope="col">{t("permissions.to")}</th>
            <th scope="col">{t("permissions.reason")}</th>
            <th scope="col">
              <span className="visually-hidden">{t("profiles.revoke")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {q.data.map((a) => (
            <tr key={a.id}>
              <th scope="row">{profiles.find((p) => p.id === a.profile_id)?.name ?? "—"}</th>
              <td dir="auto">
                {a.target_kind === "role" ? t(`roles.${a.target}`) : (a.target_name ?? a.target)}
              </td>
              <td>{a.ends_at ? fmt.dateTime(a.ends_at) : t("profiles.noEnd")}</td>
              <td dir="auto">{a.reason}</td>
              <td>
                <button type="button" className="btn btn--small btn--ghost" disabled={revoke.isPending} onClick={() => revoke.mutate(a)}>
                  {t("profiles.revoke")}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ProfilesPanel({ features }: { features: Feature[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const invalidate = useInvalidate();
  const q = useQuery({ queryKey: fleetKeys.profiles, queryFn: ({ signal }) => api.featureProfiles(signal) });
  const [editing, setEditing] = useState<Profile | "new" | null>(null);
  const [assigning, setAssigning] = useState<Profile | null>(null);
  const remove = useMutation({ mutationFn: (p: Profile) => api.deleteFeatureProfile(p.id), onSuccess: invalidate });
  return (
    <section className="card" aria-labelledby="perm-profiles">
      <div className="card__head">
        <h2 id="perm-profiles">{t("profiles.title")}</h2>
        {editing === null && (
          <button type="button" className="btn btn--primary btn--small" onClick={() => setEditing("new")}>
            {t("profiles.new")}
          </button>
        )}
      </div>
      <p className="muted">{t("profiles.intro")}</p>
      {editing && <ProfileForm features={features} profile={editing === "new" ? null : editing} onDone={() => setEditing(null)} />}
      {assigning && <AssignForm profile={assigning} onDone={() => setAssigning(null)} />}
      {q.isPending && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && (
        <ul className="profile-list">
          {q.data.map((p) => (
            <li key={p.id} className="profile-item">
              <p>
                <strong dir="auto">{p.name}</strong>
                {p.builtin && <span className="pill tone-navy">{t("profiles.builtin")}</span>}
                {p.active_assignments > 0 && (
                  <span className="pill tone-green">{t("profiles.inUse", { n: p.active_assignments })}</span>
                )}
              </p>
              {p.description && <p className="muted">{p.description}</p>}
              <p className="muted">
                {p.items
                  .map((i) => `${i.names ? i.names[lang] || i.names.ar : i.page} (${t(`profiles.modes.${i.mode}`)}${i.known ? "" : ` — ${t("profiles.unknown")}`})`)
                  .join("، ")}
              </p>
              <div className="actions">
                <button type="button" className="btn btn--small btn--primary" onClick={() => setAssigning(p)}>
                  {t("profiles.assign")}
                </button>
                <button type="button" className="btn btn--small" onClick={() => setEditing(p)}>
                  {t("profiles.edit")}
                </button>
                {!p.builtin && p.active_assignments === 0 && (
                  <button type="button" className="btn btn--small btn--ghost" onClick={() => remove.mutate(p)}>
                    {t("profiles.delete")}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {q.data && <Assignments profiles={q.data} />}
    </section>
  );
}
