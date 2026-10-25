import { useInfiniteQuery } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { CategorySelect, GouvernoratSelect, LoadMore } from "../components/Phase8Bits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useDebounced, useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { localized } from "../lib/localized";
import { p8Keys } from "../lib/phase8Api";
import { MEMORY_ACCESS, MEMORY_STATUSES, type MemoryAccess, type MemoryListQuery, type MemoryStatus } from "../lib/phase8Types";
import { canAuthorMemory } from "../lib/roles";
import { PageTitle } from "../components/PageTitle";

export function MemoryStatusTag({ status }: { status: MemoryStatus }) {
  const { t } = useTranslation();
  return <span className={`tag tag--memory-${status}`}>{t(`memory.status.${status}`)}</span>;
}

/** National memory (FR-C-22): the after-action reviews of past events, searchable and filtered by status. */
export function MemoryListPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const ids = { q: useId(), status: useId(), access: useId() };
  const [text, setText] = useState("");
  const q = useDebounced(text, 350);
  const [filters, setFilters] = useState<Omit<MemoryListQuery, "q">>({ status: "", access: "", event_type: "", gouvernorat: null });
  const query = useMemo(() => ({ ...filters, q }), [filters, q]);
  const list = useInfiniteQuery({
    queryKey: p8Keys.memoryList(query),
    queryFn: ({ pageParam, signal }) => api.memoryEntries(query, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const rows = list.data?.pages.flatMap((p) => p.items) ?? [];
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch }));
  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="historyEdu" tone="purple">{t("memory.title")}</PageTitle>
        {canAuthorMemory(user?.identity.roles ?? []) && (
          <Link className="btn btn--primary" to="/memory/new">
            {t("memory.new")}
          </Link>
        )}
      </div>
      <p className="muted">{t("memory.intro")}</p>
      <div className="filters" role="group" aria-label={t("memory.filters")}>
        <div className="filters__row">
          <div className="field field--search">
            <label htmlFor={ids.q}>{t("memory.search")}</label>
            <input id={ids.q} type="search" dir="auto" maxLength={200} value={text} onChange={(e) => setText(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={ids.status}>{t("memory.statusField")}</label>
            <select id={ids.status} value={filters.status} onChange={(e) => set({ status: e.target.value as MemoryStatus | "" })}>
              <option value="">{t("memory.allStatuses")}</option>
              {MEMORY_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`memory.status.${s}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={ids.access}>{t("memory.accessField")}</label>
            <select id={ids.access} value={filters.access} onChange={(e) => set({ access: e.target.value as MemoryAccess | "" })}>
              <option value="">{t("memory.allAccess")}</option>
              {MEMORY_ACCESS.map((a) => (
                <option key={a} value={a}>
                  {t(`memory.access.${a}`)}
                </option>
              ))}
            </select>
          </div>
          <CategorySelect
            value={filters.event_type || null}
            onChange={(c) => set({ event_type: c ?? "" })}
            label={t("memory.eventType")}
            allLabel={t("analytics.allCategories")}
          />
          {user?.identity.national && (
            <GouvernoratSelect
              value={filters.gouvernorat ?? null}
              onChange={(g) => set({ gouvernorat: g })}
              label={t("analytics.gouvernorat")}
              allLabel={t("filters.allGouvernorats")}
            />
          )}
        </div>
      </div>
      {list.isPending && <Loading />}
      {list.isError && <ErrorBox error={list.error} onRetry={() => void list.refetch()} />}
      {list.isSuccess && rows.length === 0 && <p className="muted">{t("memory.none")}</p>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("memory.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("memory.titleField")}</th>
                <th scope="col">{t("memory.eventType")}</th>
                <th scope="col">{t("memory.period")}</th>
                <th scope="col">{t("analytics.gouvernorat")}</th>
                <th scope="col">{t("memory.accessField")}</th>
                <th scope="col">{t("memory.statusField")}</th>
                <th scope="col">{t("memory.version")}</th>
                <th scope="col">{t("memory.updatedAt")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => (
                <tr key={m.id}>
                  <th scope="row">
                    <Link to={`/memory/${encodeURIComponent(m.id)}`} dir="auto">
                      {localized(m.title, lang) || t("memory.untitled")}
                    </Link>
                  </th>
                  <td>{t(`category.${m.event_type}`, { defaultValue: m.event_type })}</td>
                  <td>
                    {m.started_at ? fmt.date(m.started_at) : "—"}
                    {m.ended_at ? ` – ${fmt.date(m.ended_at)}` : ""}
                  </td>
                  <td>{m.gouvernorats.map((c) => gouvernorats.nameOf(c)).join(t("common.listSeparator")) || t("analytics.national")}</td>
                  <td>{t(`memory.access.${m.access}`)}</td>
                  <td>
                    <MemoryStatusTag status={m.status} />
                  </td>
                  <td>
                    v{m.version}
                    {m.published_version !== null && m.published_version !== m.version && (
                      <span className="cell-sub">{t("memory.publishedVersion", { v: m.published_version })}</span>
                    )}
                  </td>
                  <td>{m.updated_at ? fmt.dateTime(m.updated_at) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <LoadMore hasNext={list.hasNextPage} loading={list.isFetchingNextPage} onMore={() => void list.fetchNextPage()} />
    </div>
  );
}
