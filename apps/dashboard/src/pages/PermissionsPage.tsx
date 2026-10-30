import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { InlineDialog, ReasonField } from "../components/Phase9Bits";
import { useServices } from "../context/services";
import { errorMessageKey, isApiError } from "../lib/api";
import type { Effect, Feature, FeatureRule, TargetKind } from "../lib/features";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { REASON_RANGE, reasonValid } from "../lib/phase9";
import { STAFF_ROLES } from "../lib/roles";

const KEYS = {
  catalogue: ["features", "catalogue"] as const,
  rules: (ended: boolean) => ["features", "rules", ended] as const,
  preview: (role: string, gouvernorat: string) => ["features", "preview", role, gouvernorat] as const,
};
const GROUPS = ["ops", "crisis", "disasters", "alerts", "people", "orgs", "knowledge", "system"] as const;

function useName() {
  const lang = useLanguage();
  return (f: Feature | undefined, key: string) => (f ? f.names[lang] || f.names.ar : key);
}

/** Pages with their tabs and buttons, in the order of the catalogue. */
function tree(features: Feature[]): { page: Feature; children: Feature[] }[] {
  return features
    .filter((f) => f.kind === "page")
    .map((page) => ({ page, children: features.filter((f) => f.parent === page.key) }));
}

function Flags({ feature }: { feature: Feature }) {
  const { t } = useTranslation();
  return (
    <>
      {feature.flags.map((flag) => (
        <span key={flag} className={`tag tag--flag-${flag}`} title={t(`permissions.flagHint.${flag}`)}>
          {t(`permissions.flag.${flag}`)}
        </span>
      ))}
    </>
  );
}

function RuleForm({ features }: { features: Feature[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const gouvernorats = useGouvernorats();
  const name = useName();
  const id = useId();
  const [key, setKey] = useState("");
  const [effect, setEffect] = useState<Effect>("grant");
  const [kind, setKind] = useState<TargetKind>("role");
  const [role, setRole] = useState("operator");
  const [account, setAccount] = useState("");
  const [accountName, setAccountName] = useState("");
  const [gouvernorat, setGouvernorat] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const feature = features.find((f) => f.key === key);
  const create = useMutation({
    mutationFn: () =>
      api.createFeatureRule({
        feature_key: key,
        effect,
        target_kind: kind,
        target: kind === "role" ? role : account.trim(),
        target_name: kind === "user" ? accountName.trim() || null : null,
        gouvernorat_code: kind === "role" && gouvernorat ? Number(gouvernorat) : null,
        reason: reason.trim(),
        starts_at: from ? new Date(from).toISOString() : null,
        ends_at: to ? new Date(to).toISOString() : null,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["features"] });
      setReason("");
      setTried(false);
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (!key || (kind === "user" && !account.trim()) || !reasonValid(reason)) return;
    create.mutate();
  };
  const refused = (() => {
    if (!create.isError) return null;
    const err = create.error;
    if (isApiError(err) && err.code === "ceiling") {
      const why = (err.body as { reason?: string } | undefined)?.reason ?? "fixed";
      return t(`permissions.ceiling.${why}`);
    }
    return t(errorMessageKey(err));
  })();
  return (
    <form className="card perm-form" noValidate onSubmit={submit}>
      <h2>{t("permissions.new")}</h2>
      <div className="field">
        <label htmlFor={`${id}-feature`}>{t("permissions.feature")}</label>
        <select id={`${id}-feature`} value={key} onChange={(e) => setKey(e.target.value)} aria-invalid={tried && !key}>
          <option value="">{t("permissions.choose")}</option>
          {tree(features).map(({ page, children }) => (
            <optgroup key={page.key} label={name(page, page.key)}>
              <option value={page.key}>{t("permissions.wholePage", { name: name(page, page.key) })}</option>
              {children.map((c) => (
                <option key={c.key} value={c.key}>
                  {t(`permissions.kind.${c.kind}`)}: {name(c, c.key)}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        {feature && !feature.grantable && effect === "grant" && (
          <p className="field__hint">{t("permissions.ceiling.fixed")}</p>
        )}
      </div>
      <fieldset className="perm-form__row">
        <legend>{t("permissions.effect")}</legend>
        {(["grant", "hide"] as const).map((v) => (
          <label key={v} className="radio">
            <input type="radio" name={`${id}-effect`} checked={effect === v} onChange={() => setEffect(v)} />{" "}
            {t(`permissions.effects.${v}`)}
          </label>
        ))}
      </fieldset>
      <fieldset className="perm-form__row">
        <legend>{t("permissions.target")}</legend>
        {(["role", "user"] as const).map((v) => (
          <label key={v} className="radio">
            <input type="radio" name={`${id}-kind`} checked={kind === v} onChange={() => setKind(v)} />{" "}
            {t(`permissions.targets.${v}`)}
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
            <input
              id={`${id}-account`}
              dir="ltr"
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              aria-invalid={tried && !account.trim()}
            />
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
      <button type="submit" className="btn btn--primary" disabled={create.isPending}>
        {t(`permissions.save.${effect}`)}
      </button>
      {tried && !key && (
        <p className="field__error" role="alert">
          {t("permissions.featureRequired")}
        </p>
      )}
      {refused && (
        <p className="alert alert--error" role="alert">
          {refused}
        </p>
      )}
      {create.isSuccess && (
        <p className="alert alert--success" role="status">
          {t("permissions.saved")}
        </p>
      )}
    </form>
  );
}

function RevokeRule({ rule }: { rule: FeatureRule }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const revoke = useMutation({
    mutationFn: () => api.revokeFeatureRule(rule.id, reason.trim()),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["features"] });
      setOpen(false);
    },
  });
  if (!open)
    return (
      <button type="button" className="btn btn--small" onClick={() => setOpen(true)}>
        {t("permissions.revoke")}
      </button>
    );
  return (
    <InlineDialog title={t("permissions.revokeTitle")} onClose={() => setOpen(false)}>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          setTried(true);
          if (reasonValid(reason)) revoke.mutate();
        }}
      >
        <ReasonField label={t("permissions.reason")} value={reason} onChange={setReason} showError={tried} />
        <button type="submit" className="btn btn--danger" disabled={revoke.isPending}>
          {t("permissions.revoke")}
        </button>
        {revoke.isError && (
          <p className="alert alert--error" role="alert">
            {t(errorMessageKey(revoke.error))}
          </p>
        )}
      </form>
    </InlineDialog>
  );
}

function Rules({ features }: { features: Feature[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const name = useName();
  const [ended, setEnded] = useState(false);
  const byKey = useMemo(() => new Map(features.map((f) => [f.key, f])), [features]);
  const q = useQuery({ queryKey: KEYS.rules(ended), queryFn: ({ signal }) => api.featureRules(ended, signal) });
  return (
    <section className="card" aria-labelledby="perm-rules">
      <div className="page__head">
        <h2 id="perm-rules">{t("permissions.rules")}</h2>
        <label className="checkbox">
          <input type="checkbox" checked={ended} onChange={(e) => setEnded(e.target.checked)} />{" "}
          {t("permissions.showEnded")}
        </label>
      </div>
      {q.isPending && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {q.isSuccess && q.data.length === 0 && <p className="muted">{t("permissions.noRules")}</p>}
      {q.isSuccess && q.data.length > 0 && (
        <ul className="perm-rules">
          {q.data.map((r) => {
            const f = byKey.get(r.feature_key);
            const parent = f?.parent ? byKey.get(f.parent) : undefined;
            const who =
              r.target_kind === "role"
                ? `${t(`roles.${r.target}`)}${r.gouvernorat_code ? ` · ${gouvernorats.nameOf(r.gouvernorat_code)}` : ""}`
                : (r.target_name ?? r.target);
            return (
              <li key={r.id} className={`perm-rule perm-rule--${r.effect}`}>
                <p>
                  <span className={`tag tag--effect-${r.effect}`}>{t(`permissions.effects.${r.effect}`)}</span>{" "}
                  <strong>
                    {parent ? `${name(parent, parent.key)} › ` : ""}
                    {name(f, r.feature_key)}
                  </strong>{" "}
                  · <span dir="auto">{who}</span> ·{" "}
                  <span className={`tag tag--rule-${r.state}`}>{t(`permissions.state.${r.state}`)}</span>
                </p>
                <p className="muted">
                  {r.starts_at || r.ends_at
                    ? t("permissions.period", {
                        from: r.starts_at ? fmt.dateTime(r.starts_at) : "…",
                        to: r.ends_at ? fmt.dateTime(r.ends_at) : "…",
                      })
                    : t("permissions.open")}
                  {" · "}
                  {t("permissions.by", { name: r.created_by_name ?? "", at: fmt.dateTime(r.created_at) })}
                </p>
                <blockquote dir="auto">{r.reason}</blockquote>
                {r.revoked_at && (
                  <p className="muted">
                    {t("permissions.revokedBy", { name: r.revoked_by_name ?? "", at: fmt.dateTime(r.revoked_at) })}
                    {r.revoke_reason ? ` · ${r.revoke_reason}` : ""}
                  </p>
                )}
                {(r.state === "active" || r.state === "scheduled") && <RevokeRule rule={r} />}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function Catalogue({ features }: { features: Feature[] }) {
  const { t } = useTranslation();
  const name = useName();
  const pages = tree(features);
  return (
    <section className="card" aria-labelledby="perm-catalogue">
      <h2 id="perm-catalogue">{t("permissions.catalogue")}</h2>
      <p className="muted">{t("permissions.catalogueIntro")}</p>
      {GROUPS.map((group) => {
        const inGroup = pages.filter((p) => p.page.group === group);
        if (inGroup.length === 0) return null;
        return (
          <details key={group} className="perm-group">
            <summary>
              {t(`nav.group.${group}`)} <span className="muted">({inGroup.length})</span>
            </summary>
            <ul className="perm-tree">
              {inGroup.map(({ page, children }) => (
                <li key={page.key}>
                  <p>
                    <strong>{name(page, page.key)}</strong> <Flags feature={page} />
                  </p>
                  <p className="muted">
                    {page.roles.length
                      ? t("permissions.heldBy", { roles: page.roles.map((r) => t(`roles.${r}`)).join("، ") })
                      : t("permissions.heldByAll")}
                  </p>
                  {children.length > 0 && (
                    <ul>
                      {children.map((c) => (
                        <li key={c.key}>
                          <span className="tag">{t(`permissions.kind.${c.kind}`)}</span> {name(c, c.key)}{" "}
                          <Flags feature={c} />
                          {c.act_as && c.grantable && (
                            <span className="muted"> · {t("permissions.actsAs", { role: t(`roles.${c.act_as}`) })}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </details>
        );
      })}
    </section>
  );
}

function Preview({ features }: { features: Feature[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const name = useName();
  const id = useId();
  const [role, setRole] = useState("operator");
  const [gouvernorat, setGouvernorat] = useState("");
  const q = useQuery({
    queryKey: KEYS.preview(role, gouvernorat),
    queryFn: ({ signal }) => api.featurePreview([role], gouvernorat ? Number(gouvernorat) : null, null, signal),
  });
  const byKey = useMemo(() => new Map(features.map((f) => [f.key, f])), [features]);
  const pages = (q.data ?? []).filter((row) => byKey.get(row.key)?.kind === "page");
  return (
    <section className="card" aria-labelledby="perm-preview">
      <h2 id="perm-preview">{t("permissions.preview")}</h2>
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
            <option value="">{t("permissions.national")}</option>
            {gouvernorats.list.map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {q.isPending && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {q.isSuccess && (
        <ul className="perm-preview">
          {pages.map((row) => (
            <li key={row.key} className={row.open ? "perm-preview__open" : "perm-preview__closed"}>
              <span>{name(byKey.get(row.key), row.key)}</span>
              <span className={`tag tag--preview-${row.hidden ? "hidden" : row.granted ? "granted" : row.open ? "open" : "closed"}`}>
                {t(`permissions.previewState.${row.hidden ? "hidden" : row.granted ? "granted" : row.open ? "open" : "closed"}`)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * Permissions (L4, design-l4.md §8): the system administrator grants or hides a page, a tab or a button, for an
 * account or a role, for a period; the fixed security rules stay a ceiling. Every change is audited.
 */
export function PermissionsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const q = useQuery({ queryKey: KEYS.catalogue, queryFn: ({ signal }) => api.featureCatalogue(signal), staleTime: Infinity });
  return (
    <div className="page perm-page">
      <div className="page__head">
        <PageTitle icon="adminPanelSettings" tone="slate">
          {t("permissions.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("permissions.intro")}</p>
      <p className="alert alert--info">{t("permissions.ceilingNote")}</p>
      {q.isPending && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {q.isSuccess && (
        <div className="perm-layout">
          <RuleForm features={q.data} />
          <Rules features={q.data} />
          <Preview features={q.data} />
          <Catalogue features={q.data} />
        </div>
      )}
    </div>
  );
}
