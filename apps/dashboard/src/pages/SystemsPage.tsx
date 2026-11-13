// The subsystems page of the national system administrator (Yamen 2026-11-13: «أريد لمدير النظام التصرف في الأنظمة
// الفرعية»). Above the page, the tab and the button, the administrator acts on a whole system of the menu: hides it
// or suspends it with a message (for everyone, a role in every gouvernorat or one, an account), grants it read only or
// read and write, renames it, changes its colour and icon, and goes back to the menu's source at any time. The API
// keeps the fixed security ceiling and audits every change.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { IconTile, iconOr, toneOr, type IconName, type Tone } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { ReasonField } from "../components/Phase9Bits";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import type { FeatureRule, FeatureSystem, SystemGrantOut } from "../lib/features";
import { useGouvernorats, useLanguage } from "../lib/hooks";
import { localized } from "../lib/localized";
import { MENU_ORDER_KEY, menuOrderOf, type MenuOrder, type SystemOverride } from "../lib/menuOrder";
import { reasonValid, settingOf, usePlatformSettings } from "../lib/phase9";
import { p9Keys } from "../lib/phase9Api";
import { STAFF_ROLES } from "../lib/roles";
import { MENU, type SystemSpec } from "../menu/menu";

const KEY = ["features", "systems"] as const;
const TONES: readonly Tone[] = ["red", "navy", "purple", "green", "amber", "teal", "slate", "pink", "sky", "orange"];
/** The icons already used by the menu: the administrator picks among them. */
const ICONS: readonly IconName[] = [
  ...new Set(MENU.blocks.flatMap((b) => [b.icon, ...b.systems.flatMap((s) => [s.icon, ...s.items.map((i) => i.icon)])])),
].sort();

type Target = { kind: "everyone" | "role" | "user"; role: string; account: string; gouvernorat: string };

function TargetFields({
  value,
  onChange,
  everyone,
}: {
  value: Target;
  onChange: (v: Target) => void;
  everyone: boolean;
}) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  const id = useId();
  return (
    <div className="perm-form__row">
      <div className="field">
        <label htmlFor={`${id}-kind`}>{t("systems.target")}</label>
        <select
          id={`${id}-kind`}
          value={value.kind}
          onChange={(e) => onChange({ ...value, kind: e.target.value as Target["kind"] })}
        >
          {everyone && <option value="everyone">{t("systems.everyone")}</option>}
          <option value="role">{t("systems.role")}</option>
          <option value="user">{t("systems.account")}</option>
        </select>
      </div>
      {value.kind === "role" && (
        <>
          <div className="field">
            <label htmlFor={`${id}-role`}>{t("systems.role")}</label>
            <select id={`${id}-role`} value={value.role} onChange={(e) => onChange({ ...value, role: e.target.value })}>
              {STAFF_ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`roles.${r}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={`${id}-gov`}>{t("systems.gouvernorat")}</label>
            <select
              id={`${id}-gov`}
              value={value.gouvernorat}
              onChange={(e) => onChange({ ...value, gouvernorat: e.target.value })}
            >
              <option value="">{t("systems.allGouvernorats")}</option>
              {gouvernorats.list.map((g) => (
                <option key={g.code} value={String(g.code)}>
                  {gouvernorats.nameOf(g.code)}
                </option>
              ))}
            </select>
          </div>
        </>
      )}
      {value.kind === "user" && (
        <div className="field">
          <label htmlFor={`${id}-acc`}>{t("systems.accountId")}</label>
          <input
            id={`${id}-acc`}
            dir="ltr"
            value={value.account}
            onChange={(e) => onChange({ ...value, account: e.target.value })}
          />
        </div>
      )}
    </div>
  );
}

function targetBody(v: Target) {
  if (v.kind === "everyone") return { target_kind: "everyone" as const, target: "*" };
  if (v.kind === "role")
    return {
      target_kind: "role" as const,
      target: v.role,
      gouvernorat_code: v.gouvernorat ? Number(v.gouvernorat) : null,
    };
  return { target_kind: "user" as const, target: v.account.trim() };
}

const NEW_TARGET: Target = { kind: "everyone", role: "operator", account: "", gouvernorat: "" };

/** Hide the system, or suspend it with a message, for a target and a period. */
function CloseForm({ system }: { system: FeatureSystem }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [effect, setEffect] = useState<"hide" | "suspend">("suspend");
  const [target, setTarget] = useState<Target>(NEW_TARGET);
  const [message, setMessage] = useState({ ar: "", fr: "", en: "" });
  const [until, setUntil] = useState("");
  const [reason, setReason] = useState("");
  const save = useMutation({
    mutationFn: () =>
      api.createFeatureRule({
        feature_key: `system.${system.key}`,
        effect,
        ...targetBody(target),
        reason: reason.trim(),
        ends_at: until ? new Date(until).toISOString() : null,
        message: effect === "suspend" ? message : null,
      }),
    onSuccess: () => {
      setReason("");
      void qc.invalidateQueries({ queryKey: ["features"] });
    },
  });
  const ready =
    reasonValid(reason) &&
    (target.kind !== "user" || target.account.trim().length > 0) &&
    (effect === "hide" || Object.values(message).some((m) => m.trim()));
  return (
    <form
      className="perm-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) save.mutate();
      }}
    >
      <fieldset className="segmented">
        <legend>{t("systems.close")}</legend>
        {(["suspend", "hide"] as const).map((x) => (
          <label key={x}>
            <input type="radio" name={`${id}-effect`} checked={effect === x} onChange={() => setEffect(x)} />{" "}
            {t(`systems.effect.${x}`)}
          </label>
        ))}
      </fieldset>
      <TargetFields value={target} onChange={setTarget} everyone />
      {effect === "suspend" && (
        <div className="perm-form__row">
          {(["ar", "fr", "en"] as const).map((l) => (
            <div className="field" key={l}>
              <label htmlFor={`${id}-msg-${l}`}>{t(`systems.message.${l}`)}</label>
              <input
                id={`${id}-msg-${l}`}
                dir={l === "ar" ? "rtl" : "ltr"}
                maxLength={300}
                value={message[l]}
                onChange={(e) => setMessage({ ...message, [l]: e.target.value })}
              />
            </div>
          ))}
        </div>
      )}
      <div className="field">
        <label htmlFor={`${id}-until`}>{t("systems.until")}</label>
        <input id={`${id}-until`} type="datetime-local" value={until} onChange={(e) => setUntil(e.target.value)} />
      </div>
      <ReasonField label={t("systems.reason")} value={reason} onChange={setReason} />
      <button type="submit" className="btn btn--primary" disabled={!ready || save.isPending}>
        {t(`systems.apply.${effect}`)}
      </button>
      {save.isError && (
        <p role="alert" className="field__error">
          {t(errorMessageKey(save.error))}
        </p>
      )}
      {save.isSuccess && <p role="status">{t("systems.applied")}</p>}
    </form>
  );
}

/** Grant the whole system, read only or read and write, to a role or an account. */
function GrantForm({ system }: { system: FeatureSystem }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [mode, setMode] = useState<"read" | "write">("read");
  const [target, setTarget] = useState<Target>({ ...NEW_TARGET, kind: "role" });
  const [until, setUntil] = useState("");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<SystemGrantOut | null>(null);
  const save = useMutation({
    mutationFn: () => {
      const body = targetBody(target);
      if (body.target_kind === "everyone") throw new Error("everyone");
      return api.grantFeatureSystem(system.key, {
        mode,
        ...body,
        reason: reason.trim(),
        ends_at: until ? new Date(until).toISOString() : null,
      });
    },
    onSuccess: (out) => {
      setResult(out);
      setReason("");
      void qc.invalidateQueries({ queryKey: ["features"] });
    },
  });
  const ready = reasonValid(reason) && (target.kind !== "user" || target.account.trim().length > 0);
  return (
    <form
      className="perm-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) save.mutate();
      }}
    >
      <fieldset className="segmented">
        <legend>{t("systems.grant")}</legend>
        {(["read", "write"] as const).map((x) => (
          <label key={x}>
            <input type="radio" name={`${id}-mode`} checked={mode === x} onChange={() => setMode(x)} />{" "}
            {t(`systems.mode.${x}`)}
          </label>
        ))}
      </fieldset>
      <TargetFields value={target} onChange={setTarget} everyone={false} />
      <div className="field">
        <label htmlFor={`${id}-until`}>{t("systems.until")}</label>
        <input id={`${id}-until`} type="datetime-local" value={until} onChange={(e) => setUntil(e.target.value)} />
      </div>
      <ReasonField label={t("systems.reason")} value={reason} onChange={setReason} />
      <p className="muted">{t("systems.ceiling")}</p>
      <button type="submit" className="btn btn--primary" disabled={!ready || save.isPending}>
        {t("systems.grantButton")}
      </button>
      {save.isError && (
        <p role="alert" className="field__error">
          {t(errorMessageKey(save.error))}
        </p>
      )}
      {result && (
        <p role="status">
          {t("systems.granted", { count: result.features.length })}
          {result.skipped && result.skipped.length > 0 && ` · ${t("systems.skipped", { count: result.skipped.length })}`}
        </p>
      )}
    </form>
  );
}

/** Name, colour and icon of the system, saved over the menu's source (the `menu.order` setting). */
function LookForm({
  spec,
  order,
  onSave,
  pending,
}: {
  spec: SystemSpec;
  order: MenuOrder;
  onSave: (next: SystemOverride | null, reason: string) => void;
  pending: boolean;
}) {
  const { t } = useTranslation();
  const id = useId();
  const current = order.systems?.[spec.key] ?? {};
  const [names, setNames] = useState({ ar: current.names?.ar ?? "", fr: current.names?.fr ?? "", en: current.names?.en ?? "" });
  const [tone, setTone] = useState(current.tone ?? "");
  const [icon, setIcon] = useState(current.icon ?? "");
  const [reason, setReason] = useState("");
  const next: SystemOverride = {};
  const kept = Object.fromEntries(Object.entries(names).filter(([, v]) => v.trim()));
  if (Object.keys(kept).length > 0) next.names = kept;
  if (tone) next.tone = tone;
  if (icon) next.icon = icon;
  return (
    <form
      className="perm-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (reasonValid(reason)) onSave(Object.keys(next).length > 0 ? next : null, reason.trim());
      }}
    >
      <div className="perm-form__row">
        {(["ar", "fr", "en"] as const).map((l) => (
          <div className="field" key={l}>
            <label htmlFor={`${id}-n-${l}`}>{t(`systems.name.${l}`)}</label>
            <input
              id={`${id}-n-${l}`}
              dir={l === "ar" ? "rtl" : "ltr"}
              maxLength={80}
              placeholder={spec.names[l]}
              value={names[l]}
              onChange={(e) => setNames({ ...names, [l]: e.target.value })}
            />
          </div>
        ))}
      </div>
      <div className="perm-form__row">
        <div className="field">
          <label htmlFor={`${id}-tone`}>{t("systems.tone")}</label>
          <select id={`${id}-tone`} value={tone} onChange={(e) => setTone(e.target.value)}>
            <option value="">{t("systems.builtIn")}</option>
            {TONES.map((x) => (
              <option key={x} value={x}>
                {t(`systems.tones.${x}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-icon`}>{t("systems.icon")}</label>
          <select id={`${id}-icon`} value={icon} dir="ltr" onChange={(e) => setIcon(e.target.value)}>
            <option value="">{t("systems.builtIn")}</option>
            {ICONS.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
        </div>
        <IconTile name={iconOr(icon, spec.icon)} tone={toneOr(tone, spec.tone)} />
      </div>
      <ReasonField label={t("systems.reason")} value={reason} onChange={setReason} />
      <div className="form-row">
        <button type="submit" className="btn btn--primary" disabled={!reasonValid(reason) || pending}>
          {t("systems.saveLook")}
        </button>
        <button
          type="button"
          className="btn"
          disabled={!reasonValid(reason) || pending || !order.systems?.[spec.key]}
          onClick={() => onSave(null, reason.trim())}
        >
          {t("systems.resetLook")}
        </button>
      </div>
    </form>
  );
}

function RuleLine({ rule }: { rule: FeatureRule }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const revoke = useMutation({
    mutationFn: () => api.revokeFeatureRule(rule.id, t("systems.revokeReason")),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["features"] }),
  });
  const who =
    rule.target_kind === "everyone"
      ? t("systems.everyone")
      : rule.target_kind === "role"
        ? `${t(`roles.${rule.target}`)}${rule.gouvernorat_code ? ` · ${gouvernorats.nameOf(rule.gouvernorat_code)}` : ""}`
        : (rule.target_name ?? rule.target);
  return (
    <li>
      <span className={`tag ${rule.effect === "suspend" ? "tag--verify" : ""}`}>
        {t(`systems.effect.${rule.effect}`)}
      </span>{" "}
      {who}
      {rule.message && <span className="muted"> · «{localized(rule.message, lang)}»</span>}
      <span className="muted"> · {rule.reason}</span>{" "}
      <button type="button" className="btn btn--small" disabled={revoke.isPending} onClick={() => revoke.mutate()}>
        {t("systems.revoke")}
      </button>
    </li>
  );
}

function SystemCard({
  spec,
  system,
  order,
  onLook,
  pending,
}: {
  spec: SystemSpec;
  system: FeatureSystem | undefined;
  order: MenuOrder;
  onLook: (key: string, next: SystemOverride | null, reason: string) => void;
  pending: boolean;
}) {
  const { t } = useTranslation();
  const lang = useLanguage();
  const o = order.systems?.[spec.key];
  const label = (o?.names && localized(o.names, lang)) || localized(spec.names, lang);
  const [open, setOpen] = useState<"close" | "grant" | "look" | null>(null);
  const planned = spec.items.filter((i) => i.planned);
  return (
    <article className="card system-card" aria-labelledby={`sys-${spec.key}`} data-testid={`system-${spec.key}`}>
      <header className="system-card__head">
        <IconTile name={iconOr(o?.icon ?? "", spec.icon)} tone={toneOr(o?.tone ?? "", spec.tone)} />
        <h3 id={`sys-${spec.key}`}>
          <span className="muted">{spec.number}.</span> {label}
        </h3>
      </header>
      <p className="muted">
        {spec.items
          .filter((i) => !i.planned)
          .map((i) => t(`nav.${i.key}`))
          .join(t("common.listSeparator"))}
      </p>
      {planned.length > 0 && (
        <p className="muted">
          {t("systems.planned")}:{" "}
          {planned.map((i) => `${t(`nav.${i.key}`)}${i.ref ? ` (${i.ref})` : ""}`).join(t("common.listSeparator"))}
        </p>
      )}
      {system && system.rules.length > 0 && (
        <ul className="system-card__rules">
          {system.rules.map((r) => (
            <RuleLine key={r.id} rule={r} />
          ))}
        </ul>
      )}
      <div className="form-row">
        {(["close", "grant", "look"] as const).map((x) => (
          <button
            key={x}
            type="button"
            className={`btn btn--small ${open === x ? "btn--primary" : ""}`}
            aria-expanded={open === x}
            onClick={() => setOpen(open === x ? null : x)}
          >
            {t(`systems.actions.${x}`)}
          </button>
        ))}
      </div>
      {open === "close" && system && <CloseForm system={system} />}
      {open === "grant" && system && <GrantForm system={system} />}
      {open === "look" && (
        <LookForm spec={spec} order={order} pending={pending} onSave={(next, reason) => onLook(spec.key, next, reason)} />
      )}
    </article>
  );
}

export function SystemsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const lang = useLanguage();
  const systems = useQuery({ queryKey: KEY, queryFn: ({ signal }) => api.featureSystems(signal) });
  const settings = usePlatformSettings();
  const setting = settingOf(settings.data, MENU_ORDER_KEY);
  const order = menuOrderOf(setting?.value);
  const [resetReason, setResetReason] = useState("");
  const save = useMutation({
    mutationFn: ({ value, reason }: { value: MenuOrder; reason: string }) =>
      api.savePlatformSetting(MENU_ORDER_KEY, { value, version: setting?.version ?? 0, reason }),
    onSuccess: () => {
      setResetReason("");
      void qc.invalidateQueries({ queryKey: p9Keys.settings });
    },
  });
  if (systems.isPending || settings.isPending) return <Loading />;
  if (systems.isError) return <ErrorBox error={systems.error} onRetry={() => void systems.refetch()} />;
  const look = (key: string, next: SystemOverride | null, reason: string) => {
    const others = Object.entries(order.systems ?? {}).filter(([k]) => k !== key);
    const all: Record<string, SystemOverride> = Object.fromEntries(next ? [...others, [key, next]] : others);
    save.mutate({ value: { ...order, systems: all }, reason });
  };
  return (
    <div className="page systems-page">
      <div className="page__head">
        <PageTitle icon="hub" tone="slate">
          {t("systems.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("systems.intro")}</p>
      <p>
        <Link to="/settings/menu">{t("systems.toMenuOrder")}</Link>
        {" · "}
        <Link to="/permissions">{t("systems.toPermissions")}</Link>
      </p>
      {save.isError && (
        <p role="alert" className="field__error">
          {t(errorMessageKey(save.error))}
        </p>
      )}
      {save.isSuccess && <p role="status">{t("systems.saved")}</p>}
      {MENU.blocks.map((b) => (
        <section key={b.key} className="systems-block" aria-labelledby={`block-${b.key}`}>
          <h2 id={`block-${b.key}`}>
            <IconTile name={b.icon} tone={b.tone} size="sm" /> {localized(b.names, lang)}
          </h2>
          <div className="systems-grid">
            {b.systems.map((s) => (
              <SystemCard
                key={s.key}
                spec={s}
                system={systems.data.find((x) => x.key === s.key)}
                order={order}
                onLook={look}
                pending={save.isPending}
              />
            ))}
          </div>
        </section>
      ))}
      <section className="card" aria-labelledby="systems-reset">
        <h2 id="systems-reset">{t("systems.resetTitle")}</h2>
        <p className="muted">{t("systems.resetIntro")}</p>
        <ReasonField label={t("systems.reason")} value={resetReason} onChange={setResetReason} />
        <button
          type="button"
          className="btn"
          disabled={!reasonValid(resetReason) || save.isPending || !setting?.editable}
          onClick={() => save.mutate({ value: { groups: [], items: {}, systems: {} }, reason: resetReason.trim() })}
        >
          {t("systems.reset")}
        </button>
      </section>
    </div>
  );
}
