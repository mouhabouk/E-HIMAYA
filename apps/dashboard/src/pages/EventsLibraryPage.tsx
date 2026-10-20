import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { Excerpt, LoadMore, Markdown } from "../components/Phase8Bits";
import { useServices } from "../context/services";
import { isIsoDate } from "../lib/analytics";
import { useDebounced, useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { localized } from "../lib/localized";
import { p8Keys } from "../lib/phase8Api";
import {
  LIBRARY_KINDS,
  TREE_AXES,
  type Bucket,
  type LibraryFacets,
  type LibraryKind,
  type LibraryQuery,
  type TreeAxis,
  type TreeNode,
} from "../lib/phase8Types";

const VIEWS = ["results", "calendar", "tree"] as const;
type View = (typeof VIEWS)[number];

/** Search state shared in the URL (q, kinds, from, to, gouvernorat, category, view). */
export function libraryQueryFromParams(params: URLSearchParams): LibraryQuery & { view: View } {
  const kinds = (params.get("kinds") ?? "")
    .split(",")
    .filter((k): k is LibraryKind => (LIBRARY_KINDS as readonly string[]).includes(k));
  const g = Number(params.get("gouvernorat"));
  const view = params.get("view");
  return {
    q: (params.get("q") ?? "").slice(0, 200),
    kinds,
    from: isIsoDate(params.get("from")) ? (params.get("from") as string) : undefined,
    to: isIsoDate(params.get("to")) ? (params.get("to") as string) : undefined,
    gouvernorat: Number.isInteger(g) && g > 0 ? g : null,
    category: params.get("category") || null,
    view: (VIEWS as readonly string[]).includes(view ?? "") ? (view as View) : "results",
  };
}

export function libraryParams(q: LibraryQuery & { view: View }): URLSearchParams {
  const p = new URLSearchParams();
  if (q.q) p.set("q", q.q);
  if (q.kinds.length) p.set("kinds", q.kinds.join(","));
  if (q.from) p.set("from", q.from);
  if (q.to) p.set("to", q.to);
  if (q.gouvernorat !== null && q.gouvernorat !== undefined) p.set("gouvernorat", String(q.gouvernorat));
  if (q.category) p.set("category", q.category);
  if (q.view !== "results") p.set("view", q.view);
  return p;
}

const lastDay = (y: number, m: number) => new Date(y, m, 0).getDate();
const pad = (n: number) => String(n).padStart(2, "0");

/** Filter a tree node opens (period → dates, type → kind and category, gouvernorat → code and kind). */
export function treeNodeFilter(
  by: TreeAxis,
  path: string[],
): Partial<Pick<LibraryQuery, "from" | "to" | "kinds" | "category" | "gouvernorat">> {
  const [top, child] = path;
  if (by === "period") {
    const year = Number(top);
    if (!Number.isInteger(year)) return {};
    const month = child === undefined ? null : Number(child.includes("-") ? child.split("-")[1] : child);
    if (month === null || !Number.isInteger(month) || month < 1 || month > 12) return { from: `${year}-01-01`, to: `${year}-12-31` };
    return { from: `${year}-${pad(month)}-01`, to: `${year}-${pad(month)}-${pad(lastDay(year, month))}` };
  }
  if (by === "type") {
    const kinds = (LIBRARY_KINDS as readonly string[]).includes(top ?? "") ? [top as LibraryKind] : [];
    return { kinds, ...(child ? { category: child } : {}) };
  }
  const g = Number(top);
  const kinds = child && (LIBRARY_KINDS as readonly string[]).includes(child) ? [child as LibraryKind] : [];
  return { gouvernorat: Number.isInteger(g) ? g : null, kinds };
}

function FacetGroup({
  title,
  buckets,
  label,
  selected,
  onToggle,
}: {
  title: string;
  buckets: Bucket[];
  label: (key: string) => string;
  selected: (key: string) => boolean;
  onToggle: (key: string) => void;
}) {
  const fmt = useFormat();
  if (buckets.length === 0) return null;
  return (
    <fieldset className="facet">
      <legend>{title}</legend>
      <ul>
        {buckets.map((b) => (
          <li key={b.key}>
            <label className="checkbox">
              <input type="checkbox" checked={selected(b.key)} onChange={() => onToggle(b.key)} />
              <span>
                {label(b.key)} <span className="muted">({fmt.number(b.count)})</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </fieldset>
  );
}

function Facets({
  facets,
  query,
  update,
}: {
  facets: LibraryFacets | undefined;
  query: LibraryQuery;
  update: (patch: Partial<LibraryQuery>) => void;
}) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  const kindBuckets = facets?.kind.length ? facets.kind : LIBRARY_KINDS.map((k) => ({ key: k, count: 0 }));
  const year = query.from && query.to && query.from.slice(0, 4) === query.to.slice(0, 4) && query.from.endsWith("-01-01") && query.to.endsWith("-12-31")
    ? query.from.slice(0, 4)
    : null;
  return (
    <aside className="facets" aria-label={t("events.facets")}>
      <FacetGroup
        title={t("events.facet.kind")}
        buckets={kindBuckets}
        label={(k) => t(`events.kind.${k}`, { defaultValue: k })}
        selected={(k) => query.kinds.includes(k as LibraryKind)}
        onToggle={(k) =>
          update({
            kinds: query.kinds.includes(k as LibraryKind)
              ? query.kinds.filter((x) => x !== k)
              : [...query.kinds, k as LibraryKind],
          })
        }
      />
      <FacetGroup
        title={t("events.facet.year")}
        buckets={facets?.year ?? []}
        label={(k) => k}
        selected={(k) => year === k}
        onToggle={(k) => (year === k ? update({ from: undefined, to: undefined }) : update({ from: `${k}-01-01`, to: `${k}-12-31` }))}
      />
      <FacetGroup
        title={t("events.facet.gouvernorat")}
        buckets={facets?.gouvernorat ?? []}
        label={(k) => gouvernorats.nameOf(Number(k)) ?? k}
        selected={(k) => String(query.gouvernorat ?? "") === k}
        onToggle={(k) => update({ gouvernorat: String(query.gouvernorat ?? "") === k ? null : Number(k) })}
      />
      <FacetGroup
        title={t("events.facet.category")}
        buckets={facets?.category ?? []}
        label={(k) => t(`category.${k}`, { defaultValue: k })}
        selected={(k) => query.category === k}
        onToggle={(k) => update({ category: query.category === k ? null : k })}
      />
    </aside>
  );
}

function useLibrarySearch(query: LibraryQuery) {
  const { api } = useServices();
  return useInfiniteQuery({
    queryKey: p8Keys.librarySearch(query),
    queryFn: ({ pageParam, signal }) => api.librarySearch(query, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    placeholderData: keepPreviousData,
  });
}

function Results({ search }: { search: ReturnType<typeof useLibrarySearch> }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const first = search.data?.pages[0];
  const hits = search.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <section aria-labelledby="events-results" className="events-results">
      <h2 id="events-results" className="visually-hidden">
        {t("events.results")}
      </h2>
      <p className="muted" role="status" aria-live="polite">
        {search.isFetching ? t("common.loading") : t("events.count", { n: fmt.number(hits.length) })}
        {first?.backend === "postgres" && <> · {t("events.fallback")}</>}
      </p>
      {search.isPending && <Loading />}
      {search.isError && <ErrorBox error={search.error} onRetry={() => void search.refetch()} />}
      {search.isSuccess && hits.length === 0 && <p className="muted">{t("events.none")}</p>}
      <ol className="hits">
        {hits.map((h) => (
          <li key={`${h.kind}-${h.id}`} className="card hit">
            <p className="hit__meta">
              <span className="tag">{t(`events.kind.${h.kind}`, { defaultValue: h.kind })}</span>
              {h.date && <time dateTime={h.date}>{fmt.date(h.date)}</time>}
              {h.gouvernorat !== null && <span>{gouvernorats.nameOf(h.gouvernorat)}</span>}
              {h.category && <span>{t(`category.${h.category}`, { defaultValue: h.category })}</span>}
            </p>
            <h3>
              <Link to={`/library/items/${encodeURIComponent(h.kind)}/${encodeURIComponent(h.id)}`} dir="auto">
                {h.title || t("events.untitled")}
              </Link>
            </h3>
            {h.excerpt && <Excerpt text={h.excerpt} />}
            {h.incident_id && (
              <Link to={`/incidents/${encodeURIComponent(h.incident_id)}`} className="cell-sub">
                {t("events.openIncident")}
              </Link>
            )}
          </li>
        ))}
      </ol>
      <LoadMore hasNext={search.hasNextPage} loading={search.isFetchingNextPage} onMore={() => void search.fetchNextPage()} />
    </section>
  );
}

function CalendarView({ query, onDay }: { query: LibraryQuery; onDay: (date: string) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const now = new Date();
  const [ym, setYm] = useState(() => {
    const anchor = query.from ?? query.to;
    return anchor ? { y: Number(anchor.slice(0, 4)), m: Number(anchor.slice(5, 7)) } : { y: now.getFullYear(), m: now.getMonth() + 1 };
  });
  const cal = useQuery({
    queryKey: p8Keys.libraryCalendar(ym.y, ym.m, query),
    queryFn: ({ signal }) => api.libraryCalendar(ym.y, ym.m, query, signal),
    placeholderData: keepPreviousData,
  });
  const counts = new Map((cal.data?.days ?? []).map((d) => [d.date, d.count]));
  const monthName = new Intl.DateTimeFormat(lang === "ar" ? "ar-TN-u-nu-latn" : "fr-TN", { month: "long", year: "numeric" }).format(
    new Date(ym.y, ym.m - 1, 1),
  );
  // Weeks start on Monday (ISO); leading blanks before the 1st.
  const first = (new Date(ym.y, ym.m - 1, 1).getDay() + 6) % 7;
  const days = lastDay(ym.y, ym.m);
  const cells: (number | null)[] = [...Array<null>(first).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)];
  while (cells.length % 7) cells.push(null);
  const weeks = Array.from({ length: cells.length / 7 }, (_, w) => cells.slice(w * 7, w * 7 + 7));
  const shift = (d: number) => setYm(({ y, m }) => (m + d < 1 ? { y: y - 1, m: 12 } : m + d > 12 ? { y: y + 1, m: 1 } : { y, m: m + d }));
  return (
    <section className="card calendar" aria-labelledby="events-calendar">
      <div className="calendar__head">
        <button type="button" className="btn btn--small" onClick={() => shift(-1)} aria-label={t("events.calendar.prev")}>
          {lang === "ar" ? "→" : "←"}
        </button>
        <h2 id="events-calendar" aria-live="polite">
          {monthName}
        </h2>
        <button type="button" className="btn btn--small" onClick={() => shift(1)} aria-label={t("events.calendar.next")}>
          {lang === "ar" ? "←" : "→"}
        </button>
      </div>
      {cal.isError && <ErrorBox error={cal.error} onRetry={() => void cal.refetch()} />}
      <table className="calendar__grid">
        <caption className="visually-hidden">{t("events.calendar.caption", { month: monthName })}</caption>
        <thead>
          <tr>
            {[1, 2, 3, 4, 5, 6, 7].map((d) => (
              <th key={d} scope="col">
                <abbr title={t(`analytics.weekday.${d}`)}>{t(`events.calendar.short.${d}`)}</abbr>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weeks.map((week, w) => (
            <tr key={w}>
              {week.map((day, i) => {
                if (day === null) return <td key={i} />;
                const date = `${ym.y}-${pad(ym.m)}-${pad(day)}`;
                const n = counts.get(date) ?? 0;
                return (
                  <td key={i} className={n > 0 ? "calendar__day calendar__day--busy" : "calendar__day"}>
                    {n > 0 ? (
                      <button type="button" onClick={() => onDay(date)} aria-label={t("events.calendar.day", { date: fmt.date(date), n: fmt.number(n) })}>
                        <span className="calendar__num">{day}</span>
                        <span className="calendar__count">{fmt.number(n)}</span>
                      </button>
                    ) : (
                      <span className="calendar__num">{day}</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function TreeList({
  nodes,
  by,
  path,
  onPick,
}: {
  nodes: TreeNode[];
  by: TreeAxis;
  path: string[];
  onPick: (path: string[]) => void;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const label = (n: TreeNode, depth: number) => {
    const l = localized(n.label, lang);
    if (l) return l;
    if (by === "gouvernorat" && depth === 0) return gouvernorats.nameOf(Number(n.key)) ?? n.key;
    if ((by === "type" && depth === 0) || (by === "gouvernorat" && depth === 1)) return t(`events.kind.${n.key}`, { defaultValue: n.key });
    if (by === "type" && depth === 1) return t(`category.${n.key}`, { defaultValue: n.key });
    return n.key;
  };
  return (
    <ul className="tree" role={path.length === 0 ? undefined : "group"}>
      {nodes.map((n) => {
        const here = [...path, n.key];
        return (
          <li key={n.key}>
            {n.children?.length ? (
              <details>
                <summary>
                  {label(n, path.length)} <span className="muted">({fmt.number(n.count)})</span>
                </summary>
                <button type="button" className="btn btn--small btn--ghost" onClick={() => onPick(here)}>
                  {t("events.tree.showAll", { label: label(n, path.length) })}
                </button>
                <TreeList nodes={n.children} by={by} path={here} onPick={onPick} />
              </details>
            ) : (
              <button type="button" className="btn btn--small btn--ghost tree__leaf" onClick={() => onPick(here)}>
                {label(n, path.length)} <span className="muted">({fmt.number(n.count)})</span>
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function TreeView({ query, onPick }: { query: LibraryQuery; onPick: (patch: Partial<LibraryQuery>) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const base = useId();
  const [by, setBy] = useState<TreeAxis>("period");
  const tree = useQuery({ queryKey: p8Keys.libraryTree(by, query), queryFn: ({ signal }) => api.libraryTree(by, query, signal) });
  return (
    <section className="card" aria-labelledby={`${base}-h`}>
      <h2 id={`${base}-h`}>{t("events.tree.title")}</h2>
      <fieldset className="segmented">
        <legend>{t("events.tree.by")}</legend>
        {TREE_AXES.map((a) => (
          <label key={a} className="segmented__item">
            <input type="radio" name={`${base}-by`} checked={by === a} onChange={() => setBy(a)} />
            <span>{t(`events.tree.axis.${a}`)}</span>
          </label>
        ))}
      </fieldset>
      {tree.isPending && <Loading />}
      {tree.isError && <ErrorBox error={tree.error} onRetry={() => void tree.refetch()} />}
      {tree.data && tree.data.nodes.length === 0 && <p className="muted">{t("events.none")}</p>}
      {tree.data && <TreeList nodes={tree.data.nodes} by={by} path={[]} onPick={(path) => onPick(treeNodeFilter(by, path))} />}
    </section>
  );
}

/** Events library (FR-C-23): one search over memory, reports, incidents, transcripts and procedures. */
export function EventsLibraryPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const state = useMemo(() => libraryQueryFromParams(params), [params]);
  const id = useId();
  const [text, setText] = useState(state.q);
  const debounced = useDebounced(text, 350);
  const update = (patch: Partial<LibraryQuery & { view: View }>) => setParams(libraryParams({ ...state, ...patch }), { replace: true });
  // Push the typed text once it settles (only when it changed, so a reset is not undone by a late debounce).
  const lastDebounced = useRef(debounced);
  useEffect(() => {
    if (lastDebounced.current === debounced) return;
    lastDebounced.current = debounced;
    if (debounced !== state.q) setParams(libraryParams({ ...state, q: debounced }), { replace: true });
  }, [debounced, state, setParams]);
  const search = useLibrarySearch(state);
  const first = search.data?.pages[0];
  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("events.title")}</h1>
      </div>
      <p className="muted">{t("events.intro")}</p>
      <form role="search" className="filters" onSubmit={(e) => e.preventDefault()}>
        <div className="filters__row">
          <div className="field field--search">
            <label htmlFor={id}>{t("events.search")}</label>
            <input
              id={id}
              type="search"
              dir="auto"
              maxLength={200}
              value={text}
              placeholder={t("events.searchPlaceholder")}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
          {(state.from || state.to) && (
            <p className="muted">
              {t("events.dateFilter", { from: state.from ?? "…", to: state.to ?? "…" })}{" "}
              <button type="button" className="btn btn--small btn--ghost" onClick={() => update({ from: undefined, to: undefined })}>
                {t("events.clearDates")}
              </button>
            </p>
          )}
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              setText("");
              setParams(new URLSearchParams(), { replace: true });
            }}
          >
            {t("filters.reset")}
          </button>
        </div>
      </form>
      <nav className="tabs" aria-label={t("events.views")}>
        {VIEWS.map((v) => (
          <button
            key={v}
            type="button"
            className={`tabs__tab${state.view === v ? " tabs__tab--active" : ""}`}
            aria-pressed={state.view === v}
            onClick={() => update({ view: v })}
          >
            {t(`events.view.${v}`)}
          </button>
        ))}
      </nav>
      <div className="events-layout">
        <Facets facets={first?.facets} query={state} update={update} />
        <div>
          {state.view === "results" && <Results search={search} />}
          {state.view === "calendar" && <CalendarView query={state} onDay={(date) => update({ from: date, to: date, view: "results" })} />}
          {state.view === "tree" && <TreeView query={state} onPick={(patch) => update({ ...patch, view: "results" })} />}
        </div>
      </div>
    </div>
  );
}

function MediaView({ m }: { m: { id: string; kind: string; content_type?: string | null; url?: string | null; duration_s?: number | null } }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  if (!m.url) return <p className="muted">{t("events.item.mediaUnavailable")}</p>;
  const label = `${t(`events.item.mediaKind.${m.kind}`, { defaultValue: m.kind })}${m.duration_s ? ` · ${fmt.duration(m.duration_s)}` : ""}`;
  if (m.kind === "image") return <img src={m.url} alt={label} className="media__preview" loading="lazy" />;
  if (m.kind === "video" || m.kind === "recording")
    return <video src={m.url} controls preload="metadata" className="media__preview" aria-label={label} />;
  if (m.kind === "audio") return <audio src={m.url} controls preload="metadata" aria-label={label} />;
  return (
    <a href={m.url} target="_blank" rel="noopener noreferrer">
      {label}
    </a>
  );
}

const MARKDOWN_KINDS: readonly LibraryKind[] = ["memory", "procedure", "report_doc"];

/** One library item with its linked media (pre-signed links, audited by the API). */
export function LibraryItemPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const { kind = "", id = "" } = useParams();
  const valid = (LIBRARY_KINDS as readonly string[]).includes(kind);
  const query = useQuery({
    queryKey: p8Keys.libraryItem(kind, id),
    queryFn: ({ signal }) => api.libraryItem(kind as LibraryKind, id, signal),
    enabled: valid,
    // Media links are pre-signed for 10 minutes.
    staleTime: 5 * 60_000,
  });
  const item = query.data;
  return (
    <article className="page" aria-labelledby="item-title">
      <p>
        <Link to="/library">{t("events.back")}</Link>
      </p>
      {!valid && <p className="alert alert--error">{t("errors.not_found")}</p>}
      {query.isLoading && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {item && (
        <>
          <div className="page__head">
            <h1 id="item-title" dir="auto">
              {item.title || t("events.untitled")}
            </h1>
            <span className="tag">{t(`events.kind.${item.kind}`, { defaultValue: item.kind })}</span>
          </div>
          <dl className="fields fields--compact">
            {item.date && (
              <>
                <dt>{t("events.item.date")}</dt>
                <dd>{fmt.dateTime(item.date)}</dd>
              </>
            )}
            <dt>{t("analytics.gouvernorat")}</dt>
            <dd>
              {(item.gouvernorats?.length ? item.gouvernorats : item.gouvernorat !== null ? [item.gouvernorat] : [])
                .map((c) => gouvernorats.nameOf(c))
                .join(t("common.listSeparator")) || "—"}
            </dd>
            {item.category && (
              <>
                <dt>{t("analytics.category")}</dt>
                <dd>{t(`category.${item.category}`, { defaultValue: item.category })}</dd>
              </>
            )}
            {Object.entries(item.fields ?? {})
              .filter(([, v]) => v !== null && v !== undefined && typeof v !== "object")
              .map(([k, v]) => (
                <div key={k} className="fields__pair">
                  <dt className="code">{k.replace(/_/g, " ")}</dt>
                  <dd dir="auto">{String(v as string | number | boolean)}</dd>
                </div>
              ))}
          </dl>
          {item.incident_id && (
            <p>
              <Link to={`/incidents/${encodeURIComponent(item.incident_id)}`}>{t("events.openIncident")}</Link>
            </p>
          )}
          {item.kind === "memory" && (
            <p>
              <Link to={`/memory/${encodeURIComponent(item.id)}`}>{t("events.item.openMemory")}</Link>
            </p>
          )}
          <section className="card" aria-labelledby="item-body">
            <h2 id="item-body">{t("events.item.content")}</h2>
            {MARKDOWN_KINDS.includes(item.kind) ? (
              <Markdown source={item.body} />
            ) : (
              <p className="report-text" dir="auto">
                {item.body}
              </p>
            )}
          </section>
          <section className="card" aria-labelledby="item-media">
            <h2 id="item-media">{t("events.item.media")}</h2>
            {item.media.length === 0 ? (
              <p className="muted">{t("events.item.noMedia")}</p>
            ) : (
              <ul className="gallery">
                {item.media.map((m) => (
                  <li key={m.id} className="media">
                    <MediaView m={m} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </article>
  );
}
