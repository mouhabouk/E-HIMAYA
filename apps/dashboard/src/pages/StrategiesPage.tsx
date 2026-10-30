// covers: phase S (docs/phase-s/design-s.md §2): the strategies gathered in one place (SNACR, the intervention plans,
// the seasonal programmes, the dry runs, the lessons learned, each also kept in its own menu), and the items the
// national system administrator adds: a strategy, a programme or a reference, with its own page or a link.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { IconTile, iconOr, toneOr, type IconName, type Tone } from "../components/Icon";
import { navGroups } from "../components/Navigation";
import { PageTitle } from "../components/PageTitle";
import { Markdown } from "../components/Phase8Bits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useMyFeatures } from "../lib/features";
import { useFormat, useLanguage } from "../lib/hooks";
import { localized, localizedLanguage } from "../lib/localized";
import { STAFF_ROLES } from "../lib/roles";
import {
  itemPath,
  KEY_PATTERN,
  LINK_PATTERN,
  strategyKeys,
  type StrategyItem,
  type StrategyItemIn,
} from "../lib/strategies";

const LANGS = ["ar", "fr", "en"] as const;
const TONES: readonly Tone[] = ["purple", "navy", "teal", "green", "sky", "orange", "amber", "red", "pink", "slate"];
const ICONS: readonly IconName[] = [
  "insights",
  "menuBook",
  "policy",
  "analytics",
  "schedule",
  "healthAndSafety",
  "warning",
  "historyEdu",
  "militaryTech",
  "groups",
  "water",
];
/** The platform's own pages of the menu, and the line that says what each is for. */
const ABOUT: Record<string, string> = {
  "/snacr": "snacr",
  "/plans": "plans",
  "/programmes": "programmes",
  "/drills": "drills",
  "/memory": "lessons",
};

const EMPTY: StrategyItemIn = {
  name: { ar: "", fr: "", en: "" },
  summary: {},
  body: {},
  link: null,
  icon: "insights",
  tone: "purple",
  roles: [],
  position: 100,
  active: true,
};

function ItemForm({ item, onDone }: { item: StrategyItem | null; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [key, setKey] = useState(item?.key ?? "");
  const [f, setF] = useState<StrategyItemIn>(() => (item ? { ...EMPTY, ...item } : EMPTY));
  const save = useMutation({
    mutationFn: () => api.saveStrategyItem(key, { ...f, link: f.link?.trim() || null }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: strategyKeys.all });
      onDone();
    },
  });
  const keyOk = KEY_PATTERN.test(key);
  const namesOk = LANGS.every((l) => f.name[l].trim().length >= 2);
  const link = f.link?.trim() ?? "";
  const linkOk = !link || LINK_PATTERN.test(link);
  const hasBody = LANGS.some((l) => f.body[l]?.trim());
  const ok = keyOk && namesOk && linkOk && (hasBody || Boolean(link));
  const text = (field: "name" | "summary", l: (typeof LANGS)[number], value: string) =>
    setF((p) => ({ ...p, [field]: { ...p[field], [l]: value } }));
  return (
    <form
      className="card strategy-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (ok) save.mutate();
      }}
    >
      <h3>{item ? t("strategies.manage.edit", { name: item.name.ar }) : t("strategies.manage.add")}</h3>
      <div className="form-grid">
        {!item && (
          <div className="field">
            <label htmlFor={`${id}-key`}>{t("strategies.manage.key")}</label>
            <input
              id={`${id}-key`}
              dir="ltr"
              value={key}
              maxLength={40}
              required
              pattern="[a-z][a-z0-9_]{1,39}"
              onChange={(e) => setKey(e.target.value)}
            />
            <p className="field__hint">{t("strategies.manage.keyHint")}</p>
          </div>
        )}
        {LANGS.map((l) => (
          <div className="field" key={`n-${l}`}>
            <label htmlFor={`${id}-n-${l}`}>{t("strategies.manage.name", { lang: t(`languages.${l}`) })}</label>
            <input
              id={`${id}-n-${l}`}
              lang={l}
              dir={l === "ar" ? "rtl" : "ltr"}
              value={f.name[l]}
              maxLength={80}
              required
              onChange={(e) => text("name", l, e.target.value)}
            />
          </div>
        ))}
        {LANGS.map((l) => (
          <div className="field" key={`s-${l}`}>
            <label htmlFor={`${id}-s-${l}`}>{t("strategies.manage.summary", { lang: t(`languages.${l}`) })}</label>
            <input
              id={`${id}-s-${l}`}
              lang={l}
              dir={l === "ar" ? "rtl" : "ltr"}
              value={f.summary[l] ?? ""}
              maxLength={300}
              onChange={(e) => text("summary", l, e.target.value)}
            />
          </div>
        ))}
      </div>
      {LANGS.map((l) => (
        <div className="field" key={`b-${l}`}>
          <label htmlFor={`${id}-b-${l}`}>{t("strategies.manage.body", { lang: t(`languages.${l}`) })}</label>
          <textarea
            id={`${id}-b-${l}`}
            lang={l}
            dir={l === "ar" ? "rtl" : "ltr"}
            rows={l === "ar" ? 8 : 4}
            maxLength={20000}
            value={f.body[l] ?? ""}
            onChange={(e) => setF((p) => ({ ...p, body: { ...p.body, [l]: e.target.value } }))}
          />
        </div>
      ))}
      <p className="field__hint">{t("strategies.manage.bodyHint")}</p>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-link`}>{t("strategies.manage.link")}</label>
          <input
            id={`${id}-link`}
            dir="ltr"
            value={f.link ?? ""}
            maxLength={500}
            aria-invalid={!linkOk}
            onChange={(e) => setF((p) => ({ ...p, link: e.target.value }))}
          />
          <p className="field__hint">{t("strategies.manage.linkHint")}</p>
        </div>
        <div className="field">
          <label htmlFor={`${id}-icon`}>{t("strategies.manage.icon")}</label>
          <select id={`${id}-icon`} value={f.icon} onChange={(e) => setF((p) => ({ ...p, icon: e.target.value }))}>
            {ICONS.map((i) => (
              <option key={i} value={i}>
                {t(`strategies.icons.${i}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-tone`}>{t("strategies.manage.tone")}</label>
          <select id={`${id}-tone`} value={f.tone} onChange={(e) => setF((p) => ({ ...p, tone: e.target.value }))}>
            {TONES.map((c) => (
              <option key={c} value={c}>
                {t(`strategies.tones.${c}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-pos`}>{t("strategies.manage.position")}</label>
          <input
            id={`${id}-pos`}
            type="number"
            min={0}
            max={999}
            value={f.position}
            onChange={(e) => setF((p) => ({ ...p, position: Number(e.target.value) }))}
          />
        </div>
      </div>
      <fieldset className="chips">
        <legend>{t("strategies.manage.roles")}</legend>
        {STAFF_ROLES.map((r) => (
          <label key={r} className="chip-toggle">
            <input
              type="checkbox"
              checked={f.roles.includes(r)}
              onChange={(e) =>
                setF((p) => ({ ...p, roles: e.target.checked ? [...p.roles, r] : p.roles.filter((x) => x !== r) }))
              }
            />
            <span>{t(`roles.${r}`)}</span>
          </label>
        ))}
      </fieldset>
      <p className="field__hint">{t("strategies.manage.rolesHint")}</p>
      <label className="checkbox">
        <input type="checkbox" checked={f.active} onChange={(e) => setF((p) => ({ ...p, active: e.target.checked }))} />
        {t("strategies.manage.active")}
      </label>
      {!hasBody && !link && <p className="field__hint">{t("strategies.manage.needOne")}</p>}
      {save.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(save.error))}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={!ok || save.isPending}>
          {t("strategies.manage.save")}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

function ManageTab({ items }: { items: StrategyItem[] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const fmt = useFormat();
  const lang = useLanguage();
  const [editing, setEditing] = useState<StrategyItem | "new" | null>(null);
  const remove = useMutation({
    mutationFn: (key: string) => api.deleteStrategyItem(key),
    onSuccess: () => void qc.invalidateQueries({ queryKey: strategyKeys.all }),
  });
  return (
    <section className="strategy-manage" aria-labelledby="strategy-manage">
      <div className="page__head">
        <h2 id="strategy-manage">{t("strategies.manage.title")}</h2>
        {editing === null && (
          <button type="button" className="btn btn--primary" onClick={() => setEditing("new")}>
            {t("strategies.manage.add")}
          </button>
        )}
      </div>
      <p className="muted">{t("strategies.manage.intro")}</p>
      {editing !== null && (
        <ItemForm key={editing === "new" ? "new" : editing.key} item={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
      )}
      {items.length === 0 ? (
        <p className="card ops-empty">{t("strategies.manage.none")}</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t("strategies.manage.colName")}</th>
              <th scope="col">{t("strategies.manage.colKind")}</th>
              <th scope="col">{t("strategies.manage.colRoles")}</th>
              <th scope="col">{t("strategies.manage.colState")}</th>
              <th scope="col">{t("strategies.manage.colUpdated")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("strategies.manage.colActions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.key}>
                <td>
                  <span className="strategy-name">
                    <IconTile name={iconOr(i.icon, "insights")} tone={toneOr(i.tone, "purple")} size="sm" />
                    <span dir="auto">{localized(i.name, lang)}</span>
                  </span>
                </td>
                <td>{i.link ? <bdi dir="ltr">{i.link}</bdi> : t("strategies.manage.ownPage")}</td>
                <td>{i.roles.length ? i.roles.map((r) => t(`roles.${r}`)).join(t("common.listSeparator")) : t("strategies.manage.everyone")}</td>
                <td>{i.active ? t("strategies.manage.shown") : t("strategies.manage.hidden")}</td>
                <td className="muted">
                  {i.updated_by_name ?? "—"} · {fmt.dateTime(i.updated_at)}
                </td>
                <td className="actions">
                  <button type="button" className="btn btn--small" onClick={() => setEditing(i)}>
                    {t("strategies.manage.editShort")}
                  </button>
                  <button
                    type="button"
                    className="btn btn--small btn--danger"
                    disabled={remove.isPending}
                    onClick={() => {
                      if (window.confirm(t("strategies.manage.confirmDelete", { name: localized(i.name, lang) }))) {
                        remove.mutate(i.key);
                      }
                    }}
                  >
                    {t("strategies.manage.delete")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export function StrategiesPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const access = useMyFeatures();
  const lang = useLanguage();
  const [tab, setTab] = useState<"all" | "manage">("all");
  const list = useQuery({ queryKey: strategyKeys.all, queryFn: ({ signal }) => api.strategyItems(signal), staleTime: 5 * 60_000 });
  if (!user) return null;
  const builtIn =
    navGroups(user.identity, t, access)
      .find((g) => g.key === "strategies")
      ?.items.filter((i) => ABOUT[i.to]) ?? [];
  const data = list.data;
  const shown = (data?.items ?? []).filter((i) => i.active);
  return (
    <div className="page strategies-page">
      <div className="page__head">
        <PageTitle icon="insights" tone="purple">
          {t("strategies.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("strategies.intro")}</p>
      {data?.can_manage && (
        <div role="tablist" aria-label={t("strategies.tabs.label")} className="tabs">
          {(["all", "manage"] as const).map((k) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={tab === k}
              className={`tabs__tab${tab === k ? " tabs__tab--active" : ""}`}
              onClick={() => setTab(k)}
            >
              {t(`strategies.tabs.${k}`)}
            </button>
          ))}
        </div>
      )}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {tab === "manage" && data?.can_manage ? (
        <ManageTab items={data.items} />
      ) : (
        <>
          <ul className="strategy-cards">
            {builtIn.map((e) => (
              <li key={e.to} className="card strategy-card">
                <Link to={e.to} className="strategy-card__link">
                  <IconTile name={e.icon} tone={e.tone} />
                  <span>
                    <strong>{e.label}</strong>
                    <span className="muted">{t(`strategies.about.${ABOUT[e.to] ?? "snacr"}`)}</span>
                  </span>
                </Link>
              </li>
            ))}
            {shown.map((i) => (
              <li key={i.key} className="card strategy-card">
                <Link to={itemPath(i)} className="strategy-card__link">
                  <IconTile name={iconOr(i.icon, "insights")} tone={toneOr(i.tone, "purple")} />
                  <span>
                    <strong dir="auto">{localized(i.name, lang)}</strong>
                    {localized(i.summary, lang) && (
                      <span className="muted" dir="auto">
                        {localized(i.summary, lang)}
                      </span>
                    )}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          {list.isPending && <Loading />}
        </>
      )}
    </div>
  );
}

/** An item the administrator added, read on its own page. */
export function StrategyItemPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const { key = "" } = useParams();
  const q = useQuery({ queryKey: strategyKeys.one(key), queryFn: ({ signal }) => api.strategyItem(key, signal) });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorBox error={q.error} onRetry={() => void q.refetch()} />;
  const item = q.data;
  const bodyLang = localizedLanguage(item.body, lang);
  return (
    <div className="page strategy-item-page">
      <p>
        <Link to="/strategies">{t("strategies.back")}</Link>
      </p>
      <div className="page__head">
        <PageTitle icon={iconOr(item.icon, "insights")} tone={toneOr(item.tone, "purple")}>
          <span dir="auto">{localized(item.name, lang)}</span>
        </PageTitle>
      </div>
      {localized(item.summary, lang) && (
        <p className="muted" dir="auto">
          {localized(item.summary, lang)}
        </p>
      )}
      {item.link && (
        <p>
          {item.link.startsWith("/") ? (
            <Link className="btn btn--primary" to={item.link}>
              {t("strategies.open")}
            </Link>
          ) : (
            <a className="btn btn--primary" href={item.link} target="_blank" rel="noopener noreferrer">
              {t("strategies.openSite")}
            </a>
          )}
        </p>
      )}
      {bodyLang && <Markdown className="card strategy-body" source={localized(item.body, lang)} lang={bodyLang} />}
    </div>
  );
}
