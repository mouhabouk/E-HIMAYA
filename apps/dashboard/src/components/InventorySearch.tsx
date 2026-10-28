// covers: phase R2 (docs/phase-r/design-resources.md §2.3 and §2.4): one question across the gouvernorats the caller sees ("the
// fire trucks of 2000 L or more", "the divers of level 2"), answered with counts by gouvernorat and unit (no name), sent
// to the map into the «موارد الحماية المدنية» folder or exported as CSV.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import {
  EMPTY_SEARCH,
  inventoryKeys,
  searchParam,
  type Category,
  type CategoryKind,
  type Entity,
  type SearchGouvernorat,
  type SearchQuery,
  type SpecCondition,
} from "../lib/inventory";
import { saveDownload } from "../lib/layersApi";
import { hasReadAccess } from "../lib/roles";
import { ErrorBox, Loading } from "./Feedback";
import { categoryName } from "./InventoryForms";

const KIND_OF: Readonly<Record<Entity, CategoryKind>> = { vehicles: "vehicle", stock: "equipment", agents: "skill" };
const ENTITIES: readonly Entity[] = ["vehicles", "stock", "agents"];

export function GouvernoratPicker({
  value,
  onChange,
  any,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  any: string;
}) {
  const { t } = useTranslation();
  const { list } = useGouvernorats();
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{t("inventory.field.gouvernorat")}</label>
      <select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">{any}</option>
        {list.map((g) => (
          <option key={g.code} value={g.code}>
            {g.name}
          </option>
        ))}
      </select>
    </div>
  );
}

/** "2 000 L or more": the lower and upper bounds of a numeric specification, or "required" for a yes/no one. */
function SpecConditions({
  category,
  value,
  onChange,
}: {
  category: Category;
  value: Record<string, SpecCondition>;
  onChange: (v: Record<string, SpecCondition>) => void;
}) {
  const { t } = useTranslation();
  const lang = useLanguage();
  const id = useId();
  const set = (key: string, condition: SpecCondition | null) => {
    const { [key]: _old, ...rest } = value;
    onChange(condition === null ? rest : { ...rest, [key]: condition });
  };
  const bound = (raw: string) => (raw.trim() === "" || Number.isNaN(Number(raw)) ? null : Number(raw));
  if (category.specs.length === 0) return null;
  return (
    <fieldset className="inventory-search__specs">
      <legend>{t("inventory.search.specs")}</legend>
      {category.specs.map((d) => {
        const name = d.name[lang] || d.name.ar;
        if (d.type === "bool") {
          return (
            <label key={d.key} className="checkbox">
              <input type="checkbox" checked={value[d.key] === true} onChange={(e) => set(d.key, e.target.checked ? true : null)} />
              <span>{t("inventory.search.required", { spec: name })}</span>
            </label>
          );
        }
        const current: [number | null, number | null] = Array.isArray(value[d.key])
          ? (value[d.key] as [number | null, number | null])
          : [null, null];
        const update = (i: 0 | 1, raw: string) => {
          const next: [number | null, number | null] = [current[0], current[1]];
          next[i] = bound(raw);
          set(d.key, next[0] === null && next[1] === null ? null : next);
        };
        const unit = d.unit ? ` (${d.unit})` : "";
        return (
          <div key={d.key} className="inventory-search__range">
            <div className="field">
              <label htmlFor={`${id}-${d.key}-min`}>{t("inventory.search.min", { spec: name + unit })}</label>
              <input
                id={`${id}-${d.key}-min`}
                type="number"
                inputMode="decimal"
                min={0}
                value={current[0] ?? ""}
                onChange={(e) => update(0, e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor={`${id}-${d.key}-max`}>{t("inventory.search.max", { spec: name + unit })}</label>
              <input
                id={`${id}-${d.key}-max`}
                type="number"
                inputMode="decimal"
                min={0}
                value={current[1] ?? ""}
                onChange={(e) => update(1, e.target.value)}
              />
            </div>
          </div>
        );
      })}
    </fieldset>
  );
}

function ResultRow({ g, readyLabel }: { g: SearchGouvernorat; readyLabel: string }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const lang = useLanguage();
  const name = lang === "ar" ? g.name_ar : lang === "fr" ? g.name_fr : g.name_en;
  return (
    <tr>
      <th scope="row">
        {name}
        <details className="inventory-search__units">
          <summary>{t("inventory.search.unitsOf", { count: fmt.number(g.units.length) })}</summary>
          <ul>
            {g.units.map((u) => (
              <li key={u.id}>
                <span dir="auto">{lang === "ar" ? u.name_ar : u.name_fr || u.name_ar}</span>
                {" · "}
                {t("inventory.search.unitCount", { total: fmt.number(u.total), ready: fmt.number(u.ready), label: readyLabel })}
              </li>
            ))}
          </ul>
        </details>
      </th>
      <td className="num">{fmt.number(g.total)}</td>
      <td className="num">{fmt.number(g.ready)}</td>
    </tr>
  );
}

/** The search tab of the register: open to the governor and the minister too (counts, never names). */
export function SearchTab({ catalogue, national }: { catalogue: Category[]; national: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const navigate = useNavigate();
  const { user } = useAuth();
  // The live map is the operations rooms' screen; the governor and the minister read the counts in the table.
  const mapAllowed = hasReadAccess(user?.identity.roles ?? []);
  const id = useId();
  const [draft, setDraft] = useState<SearchQuery>(EMPTY_SEARCH);
  const [asked, setAsked] = useState<SearchQuery | null>(null);
  const result = useQuery({
    queryKey: asked ? inventoryKeys.search(asked) : ["inventory", "search", "none"],
    enabled: asked !== null,
    queryFn: ({ signal }) => {
      if (!asked) throw new Error("no search");
      return api.searchInventory(asked, signal);
    },
  });
  const exporting = useMutation({ mutationFn: (q: SearchQuery) => api.exportSearch(q), onSuccess: saveDownload });

  const kinds = catalogue.filter((c) => c.kind === KIND_OF[draft.what] && c.active);
  const category = catalogue.find((c) => c.key === draft.category);
  const patch = (p: Partial<SearchQuery>) => setDraft((d) => ({ ...d, ...p }));
  const onSubmit = (e: SyntheticEvent) => {
    e.preventDefault();
    setAsked(draft);
  };
  const readyLabel = t(`inventory.search.ready.${asked?.what ?? draft.what}`);
  const found = (result.data?.gouvernorats ?? []).filter((g) => g.total > 0);

  return (
    <section className="inventory-search" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="visually-hidden">
        {t("inventory.tabs.search")}
      </h2>
      <p className="muted">{t("inventory.search.intro")}</p>
      <form className="card inventory-form" onSubmit={onSubmit}>
        <fieldset className="inventory-search__what">
          <legend>{t("inventory.search.what")}</legend>
          {ENTITIES.map((e) => (
            <label key={e} className="checkbox">
              <input
                type="radio"
                name={`${id}-what`}
                checked={draft.what === e}
                onChange={() => setDraft({ ...EMPTY_SEARCH, what: e, gouvernorats: draft.gouvernorats })}
              />
              <span>{t(`inventory.tabs.${e}`)}</span>
            </label>
          ))}
        </fieldset>
        <div className="filters__row">
          <div className="field">
            <label htmlFor={`${id}-category`}>
              {t(draft.what === "agents" ? "inventory.field.skill" : "inventory.field.type")}
            </label>
            <select
              id={`${id}-category`}
              value={draft.category ?? ""}
              onChange={(e) => patch({ category: e.target.value || null, specs: {}, min_level: null })}
            >
              <option value="">{t("inventory.anyType")}</option>
              {kinds.map((c) => (
                <option key={c.key} value={c.key}>
                  {categoryName(c, lang)}
                </option>
              ))}
            </select>
          </div>
          {draft.what === "agents" && category && category.levels > 0 && (
            <div className="field">
              <label htmlFor={`${id}-level`}>{t("inventory.search.minLevel")}</label>
              <select
                id={`${id}-level`}
                value={draft.min_level ?? ""}
                onChange={(e) => patch({ min_level: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">{t("inventory.search.anyLevel")}</option>
                {Array.from({ length: category.levels }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    {fmt.number(n)}
                  </option>
                ))}
              </select>
            </div>
          )}
          {national && (
            <GouvernoratPicker
              value={draft.gouvernorats?.[0] ?? null}
              onChange={(g) => patch({ gouvernorats: g === null ? null : [g] })}
              any={t("inventory.allGouvernorats")}
            />
          )}
        </div>
        {draft.what !== "agents" && category && (
          <SpecConditions category={category} value={draft.specs} onChange={(specs) => patch({ specs })} />
        )}
        <div className="filters__row">
          <label className="checkbox">
            <input type="checkbox" checked={draft.ready_only} onChange={(e) => patch({ ready_only: e.target.checked })} />
            <span>{t(`inventory.search.readyOnly.${draft.what}`)}</span>
          </label>
          {draft.what === "agents" && draft.category && (
            <label className="checkbox">
              <input type="checkbox" checked={draft.valid_cert} onChange={(e) => patch({ valid_cert: e.target.checked })} />
              <span>{t("inventory.search.validCert")}</span>
            </label>
          )}
        </div>
        <div className="actions">
          <button type="submit" className="btn btn--primary">
            {t("inventory.search.submit")}
          </button>
        </div>
      </form>

      {result.isFetching && <Loading />}
      {result.isError && <ErrorBox error={result.error} onRetry={() => void result.refetch()} />}
      {asked && result.data && (
        <section className="card inventory-search__result" aria-live="polite">
          <p className="inventory-search__total">
            <strong>{t("inventory.search.total", { total: fmt.number(result.data.total) })}</strong>
            {" · "}
            {t("inventory.search.readyCount", { ready: fmt.number(result.data.ready), label: readyLabel })}
            {" · "}
            {t("inventory.search.inGouvernorats", { count: fmt.number(found.length) })}
          </p>
          <div className="actions">
            {mapAllowed && (
              <button
                type="button"
                className="btn btn--primary"
                disabled={found.length === 0}
                onClick={() => void navigate(`/map?resources=${encodeURIComponent(searchParam(asked))}`)}
              >
                {t("inventory.search.toMap")}
              </button>
            )}
            <button type="button" className="btn" disabled={exporting.isPending} onClick={() => exporting.mutate(asked)}>
              {t("inventory.search.export")}
            </button>
            {exporting.isError && (
              <span className="field__error" role="alert">
                {t(errorMessageKey(exporting.error))}
              </span>
            )}
          </div>
          {!mapAllowed && <p className="muted">{t("inventory.search.mapRoomsOnly")}</p>}
          {found.length === 0 ? (
            <p className="muted">{t("inventory.search.none")}</p>
          ) : (
            <div className="table-wrap">
              <table className="table inventory-table">
                <caption className="visually-hidden">{t("inventory.search.caption")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("inventory.field.gouvernorat")}</th>
                    <th scope="col">{t("inventory.search.count")}</th>
                    <th scope="col">{readyLabel}</th>
                  </tr>
                </thead>
                <tbody>
                  {found.map((g) => (
                    <ResultRow key={g.code} g={g} readyLabel={readyLabel} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </section>
  );
}
