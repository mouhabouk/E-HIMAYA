import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { InlineDialog } from "../components/Phase9Bits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useDebounced, useGouvernorats } from "../lib/hooks";
import { p9Keys } from "../lib/phase9Api";
import type { AccountCreateBody, AccountFilters, ScopeLevel, StaffAccount } from "../lib/phase9Types";
import { grantableRoles, STAFF_ROLES } from "../lib/roles";

const USERNAME = /^[a-z0-9._-]{3,64}$/;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function RolePicker({
  name,
  grantable,
  value,
  onChange,
  locked = [],
}: {
  name: string;
  grantable: string[];
  value: string[];
  onChange: (roles: string[]) => void;
  /** Roles the account holds but the caller may not change (kept as they are). */
  locked?: string[];
}) {
  const { t } = useTranslation();
  return (
    <fieldset>
      <legend>{t("accounts.roles")}</legend>
      {grantable.map((r) => (
        <label key={r} className="checkbox">
          <input
            type="checkbox"
            name={name}
            checked={value.includes(r)}
            onChange={(e) => onChange(e.target.checked ? [...value, r] : value.filter((x) => x !== r))}
          />{" "}
          {t(`roles.${r}`)}
        </label>
      ))}
      {locked.length > 0 && (
        <p className="muted">{t("accounts.lockedRoles", { list: locked.map((r) => t(`roles.${r}`)).join(t("common.listSeparator")) })}</p>
      )}
    </fieldset>
  );
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => void qc.invalidateQueries({ queryKey: p9Keys.accountsAll });
}

function CreateAccountForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const invalidate = useInvalidate();
  const id = useId();
  const identity = user?.identity;
  const national = identity?.national ?? false;
  const grantable = identity ? grantableRoles(identity) : [];
  const [form, setForm] = useState({ username: "", email: "", first_name: "", last_name: "" });
  const [roles, setRoles] = useState<string[]>([]);
  const [scope, setScope] = useState<ScopeLevel>("gouvernorat");
  const [code, setCode] = useState<string>(identity?.gouvernoratCode ? String(identity.gouvernoratCode) : "");
  const [tried, setTried] = useState(false);
  const create = useMutation({
    mutationFn: (b: AccountCreateBody) => api.createAccount(b),
    onSuccess: () => {
      invalidate();
      onDone();
    },
  });
  // A regional administrator creates accounts of its own gouvernorat only (the API forces it too).
  const gouvernorat = national ? (scope === "national" ? null : code ? Number(code) : null) : (identity?.gouvernoratCode ?? null);
  const errors = {
    username: !USERNAME.test(form.username.trim()),
    email: !EMAIL.test(form.email.trim()),
    first_name: !form.first_name.trim(),
    last_name: !form.last_name.trim(),
    roles: roles.length === 0,
    gouvernorat: scope === "gouvernorat" && gouvernorat === null,
  };
  const valid = !Object.values(errors).some(Boolean);
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (!valid) return;
    create.mutate({
      username: form.username.trim(),
      email: form.email.trim(),
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      roles,
      scope_level: national ? scope : "gouvernorat",
      gouvernorat_code: national && scope === "national" ? null : gouvernorat,
    });
  };
  const text = (k: keyof typeof form, type = "text") => (
    <div className={`field${tried && errors[k] ? " field--invalid" : ""}`}>
      <label htmlFor={`${id}-${k}`}>{t(`accounts.fields.${k}`)}</label>
      <input
        id={`${id}-${k}`}
        type={type}
        value={form[k]}
        dir={k === "username" || k === "email" ? "ltr" : "auto"}
        aria-invalid={tried && errors[k] ? true : undefined}
        onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))}
      />
    </div>
  );
  return (
    <form noValidate onSubmit={submit}>
      {text("username")}
      {text("email", "email")}
      {text("first_name")}
      {text("last_name")}
      <RolePicker name={`${id}-roles`} grantable={grantable} value={roles} onChange={setRoles} />
      {national ? (
        <>
          <fieldset className="segmented">
            <legend>{t("accounts.scope")}</legend>
            {(["gouvernorat", "national"] as const).map((s) => (
              <label key={s} className="segmented__item">
                <input type="radio" name={`${id}-scope`} checked={scope === s} onChange={() => setScope(s)} />
                <span>{t(`accounts.scopeLevel.${s}`)}</span>
              </label>
            ))}
          </fieldset>
          {scope === "gouvernorat" && (
            <div className="field">
              <label htmlFor={`${id}-g`}>{t("filters.gouvernorat")}</label>
              <select id={`${id}-g`} value={code} onChange={(e) => setCode(e.target.value)}>
                <option value="">{t("referral.choose")}</option>
                {gouvernorats.list.map((g) => (
                  <option key={g.code} value={g.code}>
                    {gouvernorats.nameOf(g.code)}
                  </option>
                ))}
              </select>
            </div>
          )}
        </>
      ) : (
        <p className="muted">{t("accounts.ownGouvernorat", { name: gouvernorats.nameOf(identity?.gouvernoratCode) ?? "" })}</p>
      )}
      <p className="muted">{t("accounts.requiredActions")}</p>
      {tried && !valid && (
        <p className="field__error" role="alert">
          {t("accounts.invalid")}
        </p>
      )}
      <button type="submit" className="btn btn--primary" disabled={create.isPending}>
        {t("accounts.create")}
      </button>
      {create.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(create.error))}
        </p>
      )}
    </form>
  );
}

function AccountRow({ account }: { account: StaffAccount }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const invalidate = useInvalidate();
  const [editing, setEditing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const identity = user?.identity;
  const grantable = identity ? grantableRoles(identity) : [];
  const self = identity?.subject === account.id;
  const locked = account.roles.filter((r) => (STAFF_ROLES as readonly string[]).includes(r) && !grantable.includes(r));
  const [roles, setRoles] = useState<string[]>(account.roles.filter((r) => grantable.includes(r)));
  const update = useMutation({
    mutationFn: (b: { roles?: string[]; enabled?: boolean }) => api.updateAccount(account.id, b),
    onSuccess: () => {
      invalidate();
      setEditing(false);
      setNotice(t("accounts.updated"));
    },
  });
  const reset = useMutation({
    mutationFn: () => api.resetAccountCredentials(account.id),
    onSuccess: () => setNotice(t("accounts.resetDone")),
  });
  const name = [account.first_name, account.last_name].filter(Boolean).join(" ");
  const error = update.error ?? reset.error;
  return (
    <tr>
      <td dir="ltr" className="code">
        {account.username}
      </td>
      <td dir="auto">{name || "—"}</td>
      <td dir="ltr">{account.email ?? "—"}</td>
      <td>{account.roles.filter((r) => (STAFF_ROLES as readonly string[]).includes(r)).map((r) => t(`roles.${r}`)).join(t("common.listSeparator"))}</td>
      <td>
        {account.scope_level === "national"
          ? t("header.national")
          : (gouvernorats.nameOf(account.gouvernorat_code) ?? t("common.notAvailable"))}
      </td>
      <td>{account.enabled ? t("accounts.enabled") : t("accounts.disabled")}</td>
      <td>{account.mfa_configured ? t("common.yes") : t("common.no")}</td>
      <td>
        {self ? (
          <span className="muted">{t("accounts.self")}</span>
        ) : (
          <div className="actions">
            <button type="button" className="btn btn--small" onClick={() => setEditing((v) => !v)}>
              {t("accounts.editRoles")}
            </button>
            <button
              type="button"
              className="btn btn--small"
              disabled={update.isPending}
              onClick={() => update.mutate({ enabled: !account.enabled })}
            >
              {account.enabled ? t("accounts.disable") : t("accounts.enable")}
            </button>
            <button type="button" className="btn btn--small" disabled={reset.isPending} onClick={() => reset.mutate()}>
              {t("accounts.reset")}
            </button>
          </div>
        )}
        {editing && (
          <InlineDialog title={t("accounts.editRolesOf", { name: account.username })} onClose={() => setEditing(false)}>
            <form
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                if (roles.length + locked.length > 0) update.mutate({ roles: [...roles, ...locked] });
              }}
            >
              <RolePicker name={`roles-${account.id}`} grantable={grantable} value={roles} onChange={setRoles} locked={locked} />
              <button type="submit" className="btn btn--primary" disabled={update.isPending}>
                {t("accounts.save")}
              </button>
            </form>
          </InlineDialog>
        )}
        <span role="status" aria-live="polite">
          {notice && <span className="muted">{notice}</span>}
        </span>
        {error && (
          <span className="field__error" role="alert">
            {t(errorMessageKey(error))}
          </span>
        )}
      </td>
    </tr>
  );
}

/**
 * Staff accounts of the administrator's gouvernorat (phase 9 §6.2, Keycloak through the API): create, change roles,
 * enable or disable, reset credentials. A national administrator sees every gouvernorat; nobody edits their own.
 */
export function AccountsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const base = useId();
  const national = user?.identity.national ?? false;
  const [filters, setFilters] = useState<AccountFilters>({ gouvernorat: null, role: "", q: "" });
  const [creating, setCreating] = useState(false);
  const q = useDebounced(filters.q ?? "", 300);
  const effective = { ...filters, q };
  const query = useInfiniteQuery({
    queryKey: p9Keys.accounts(effective),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => api.accounts(effective, { cursor: pageParam, signal }),
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("accounts.title")}</h1>
        <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>
          {t("accounts.new")}
        </button>
      </div>
      <p className="muted">
        {national
          ? t("accounts.introNational")
          : t("accounts.intro", { name: gouvernorats.nameOf(user?.identity.gouvernoratCode) ?? "" })}
      </p>
      {creating && (
        <InlineDialog title={t("accounts.new")} onClose={() => setCreating(false)}>
          <CreateAccountForm onDone={() => setCreating(false)} />
        </InlineDialog>
      )}
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${base}-q`}>{t("filters.search")}</label>
          <input id={`${base}-q`} type="search" value={filters.q ?? ""} onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} />
        </div>
        <div className="field">
          <label htmlFor={`${base}-role`}>{t("accounts.role")}</label>
          <select id={`${base}-role`} value={filters.role ?? ""} onChange={(e) => setFilters((f) => ({ ...f, role: e.target.value }))}>
            <option value="">{t("notify.filters.all")}</option>
            {STAFF_ROLES.map((r) => (
              <option key={r} value={r}>
                {t(`roles.${r}`)}
              </option>
            ))}
          </select>
        </div>
        {national && (
          <div className="field">
            <label htmlFor={`${base}-g`}>{t("filters.gouvernorat")}</label>
            <select
              id={`${base}-g`}
              value={filters.gouvernorat ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, gouvernorat: e.target.value ? Number(e.target.value) : null }))}
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
      {query.isSuccess && items.length === 0 && <p className="muted">{t("accounts.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("accounts.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("accounts.fields.username")}</th>
                <th scope="col">{t("detail.name")}</th>
                <th scope="col">{t("accounts.fields.email")}</th>
                <th scope="col">{t("accounts.roles")}</th>
                <th scope="col">{t("accounts.scope")}</th>
                <th scope="col">{t("accounts.state")}</th>
                <th scope="col">{t("accounts.mfa")}</th>
                <th scope="col">{t("late.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <AccountRow key={a.id} account={a} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && (
        <button type="button" className="btn" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
          {t("reports.loadMore")}
        </button>
      )}
    </div>
  );
}
