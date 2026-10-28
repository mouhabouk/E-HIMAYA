// covers: phase L3b (docs/phase-l/design-l3b.md §5, §6): the register of plans, decisions and instructions, its
// advanced search (words, kind, level, status, gouvernorat, topic, issuer, period, in force on a day, file) with the
// counts by kind, level and status, and recording a document.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { DocumentCard, DocumentForm } from "../components/RegisterBits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useDebounced, useFormat, useGouvernorats } from "../lib/hooks";
import {
  DEFAULT_QUERY,
  DOCUMENT_KINDS,
  DOCUMENT_LEVELS,
  DOCUMENT_STATUSES,
  registerKeys,
  TOPICS,
  type RegisterQuery,
  type RegisterSearch,
} from "../lib/register";

function toggle<T>(list: readonly T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function FacetGroup<T extends string>({
  title,
  keys,
  counts,
  selected,
  label,
  onToggle,
}: {
  title: string;
  keys: readonly T[];
  counts: { key: string; count: number }[] | undefined;
  selected: readonly T[];
  label: (k: T) => string;
  onToggle: (k: T) => void;
}) {
  const fmt = useFormat();
  const count = (k: string) => counts?.find((c) => c.key === k)?.count ?? 0;
  return (
    <fieldset className="facet">
      <legend>{title}</legend>
      <ul>
        {keys.map((k) => (
          <li key={k}>
            <label className="checkbox">
              <input type="checkbox" checked={selected.includes(k)} onChange={() => onToggle(k)} />
              <span>
                {label(k)} <span className="muted">({fmt.number(count(k))})</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </fieldset>
  );
}

function Advanced({ q, update, national }: { q: RegisterQuery; update: (p: Partial<RegisterQuery>) => void; national: boolean }) {
  const { t } = useTranslation();
  const { list } = useGouvernorats();
  const id = useId();
  const [issuer, setIssuer] = useState(q.issuer);
  const debounced = useDebounced(issuer, 350);
  useEffect(() => {
    if (debounced !== q.issuer) update({ issuer: debounced });
  }, [debounced, q.issuer, update]);
  return (
    <div className="register-advanced">
      <div className="form-grid">
        {national && (
          <div className="field">
            <label htmlFor={`${id}-g`}>{t("register.field.gouvernorat")}</label>
            <select id={`${id}-g`} value={q.gouvernorat ?? ""} onChange={(e) => update({ gouvernorat: e.target.value ? Number(e.target.value) : null })}>
              <option value="">{t("register.search.anyGouvernorat")}</option>
              {list.map((g) => (
                <option key={g.code} value={g.code}>
                  {g.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="field">
          <label htmlFor={`${id}-t`}>{t("register.field.topic")}</label>
          <select id={`${id}-t`} value={q.topic ?? ""} onChange={(e) => update({ topic: e.target.value || null })}>
            <option value="">{t("register.search.anyTopic")}</option>
            {TOPICS.map((k) => (
              <option key={k} value={k}>
                {t(`register.topic.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-i`}>{t("register.field.issuer")}</label>
          <input id={`${id}-i`} value={issuer} dir="auto" maxLength={200} onChange={(e) => setIssuer(e.target.value)} />
        </div>
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-df`}>{t("register.search.dateField")}</label>
          <select id={`${id}-df`} value={q.dateField} onChange={(e) => update({ dateField: e.target.value as RegisterQuery["dateField"] })}>
            <option value="issued">{t("register.search.byIssued")}</option>
            <option value="effective">{t("register.search.byEffective")}</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-f`}>{t("register.search.from")}</label>
          <input id={`${id}-f`} type="date" value={q.from ?? ""} onChange={(e) => update({ from: e.target.value || null })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-to`}>{t("register.search.to")}</label>
          <input id={`${id}-to`} type="date" value={q.to ?? ""} onChange={(e) => update({ to: e.target.value || null })} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-on`}>{t("register.search.inForceOn")}</label>
          <input id={`${id}-on`} type="date" value={q.inForceOn ?? ""} onChange={(e) => update({ inForceOn: e.target.value || null })} />
        </div>
      </div>
      <label className="checkbox">
        <input type="checkbox" checked={q.hasFile === true} onChange={(e) => update({ hasFile: e.target.checked ? true : null })} />
        {t("register.search.withFile")}
      </label>
    </div>
  );
}

function Results({ search, q }: { search: { data?: RegisterSearch; isPending: boolean; isFetching: boolean; isError: boolean; error: unknown; refetch: () => unknown }; q: RegisterQuery }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const data = search.data;
  return (
    <section aria-labelledby="register-results">
      <h2 id="register-results" className="visually-hidden">
        {t("register.search.results")}
      </h2>
      <p className="muted" role="status" aria-live="polite">
        {search.isFetching ? t("common.loading") : t("register.search.count", { n: fmt.number(data?.total ?? 0) })}
        {q.inForceOn && <> · {t("register.search.inForceOnNote", { date: fmt.date(q.inForceOn) })}</>}
      </p>
      {search.isPending && <Loading />}
      {search.isError && <ErrorBox error={search.error} onRetry={() => void search.refetch()} />}
      {data && data.items.length === 0 && <p className="card ops-empty">{t("register.search.none")}</p>}
      <ol className="hits">
        {data?.items.map((d) => (
          <DocumentCard key={d.id} d={d} />
        ))}
      </ol>
    </section>
  );
}

export function RegisterPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const national = Boolean(user?.identity.national);
  const id = useId();
  const [q, setQ] = useState<RegisterQuery>(DEFAULT_QUERY);
  const [text, setText] = useState("");
  const [advanced, setAdvanced] = useState(false);
  // A plan of a hazard opened from the plans page: /register?new=plan&hazard=floods.
  const [params] = useSearchParams();
  const prefill = params.get("new") === "plan" ? { kind: "plan" as const, hazard_key: params.get("hazard") || null } : undefined;
  const [creating, setCreating] = useState(Boolean(prefill));
  const debounced = useDebounced(text, 350);
  const [resets, setResets] = useState(0);
  const update = useCallback((patch: Partial<RegisterQuery>) => setQ((x) => ({ ...x, ...patch })), []);
  const effective = useMemo(() => ({ ...q, q: debounced }), [q, debounced]);
  const search = useQuery({
    queryKey: registerKeys.search(effective),
    queryFn: ({ signal }) => api.registerSearch(effective, signal),
    placeholderData: keepPreviousData,
  });
  const data = search.data;
  return (
    <div className="page register-page">
      <div className="page__head">
        <PageTitle icon="folderOpen" tone="navy">
          {t("register.title")}
        </PageTitle>
        {data?.can_create && !creating && (
          <button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>
            {t("register.new")}
          </button>
        )}
      </div>
      <p className="muted">{t("register.intro")}</p>
      {creating && <DocumentForm canCentral={Boolean(data?.can_create_central)} initial={prefill} onClose={() => setCreating(false)} />}
      <form role="search" className="filters" onSubmit={(e) => e.preventDefault()}>
        <div className="filters__row">
          <div className="field field--search">
            <label htmlFor={`${id}-q`}>{t("register.search.label")}</label>
            <input
              id={`${id}-q`}
              type="search"
              dir="auto"
              maxLength={300}
              value={text}
              placeholder={t("register.search.placeholder")}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor={`${id}-s`}>{t("register.search.sort")}</label>
            <select id={`${id}-s`} value={q.sort} onChange={(e) => update({ sort: e.target.value as RegisterQuery["sort"] })}>
              {(["relevance", "newest", "oldest"] as const).map((s) => (
                <option key={s} value={s}>
                  {t(`register.search.sortBy.${s}`)}
                </option>
              ))}
            </select>
          </div>
          <button type="button" className="btn" aria-expanded={advanced} onClick={() => setAdvanced((a) => !a)}>
            {t("register.search.advanced")}
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              setText("");
              setQ(DEFAULT_QUERY);
              setResets((n) => n + 1);
            }}
          >
            {t("filters.reset")}
          </button>
        </div>
        {advanced && <Advanced key={resets} q={q} update={update} national={national} />}
      </form>
      <div className="events-layout">
        <aside className="facets" aria-label={t("register.search.facets")}>
          <FacetGroup
            title={t("register.field.status")}
            keys={DOCUMENT_STATUSES}
            counts={data?.facets.status}
            selected={q.statuses}
            label={(k) => t(`register.status.${k}`)}
            onToggle={(k) => update({ statuses: toggle(q.statuses, k) })}
          />
          <FacetGroup
            title={t("register.field.level")}
            keys={DOCUMENT_LEVELS}
            counts={data?.facets.level}
            selected={q.levels}
            label={(k) => t(`register.level.${k}`)}
            onToggle={(k) => update({ levels: toggle(q.levels, k) })}
          />
          <FacetGroup
            title={t("register.field.kind")}
            keys={DOCUMENT_KINDS}
            counts={data?.facets.kind}
            selected={q.kinds}
            label={(k) => t(`register.kind.${k}`)}
            onToggle={(k) => update({ kinds: toggle(q.kinds, k) })}
          />
        </aside>
        <Results search={search} q={effective} />
      </div>
    </div>
  );
}
