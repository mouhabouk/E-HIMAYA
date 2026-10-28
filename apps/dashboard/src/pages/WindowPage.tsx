import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { FiguresView, Kpi, useCount } from "../components/WindowFigures";
import { PageTitle } from "../components/PageTitle";
import { InlineDialog, ReasonField } from "../components/Phase9Bits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { saveDownload } from "../lib/layersApi";
import { REASON_RANGE, reasonValid } from "../lib/phase9";
import { CATEGORIES } from "../lib/types";
import { canOpenAxes } from "../lib/roles";
import type {
  CompareMode,
  CompareQuery,
  CompareResult,
  Delegation,
  EventRef,
  SavedSearch,
  SearchResult,
  WindowAccess,
  WindowFilters,
} from "../lib/window";

export const WINDOW_KEYS = {
  access: ["window", "access"] as const,
  now: ["window", "now"] as const,
  search: (f: WindowFilters) => ["window", "search", f] as const,
  compare: (f: WindowFilters, c: CompareQuery) => ["window", "compare", f, c] as const,
  saved: ["window", "saved"] as const,
  synonyms: ["window", "synonyms"] as const,
  delegations: (ended: boolean) => ["window", "delegations", ended] as const,
  delegates: (q: string) => ["window", "delegates", q] as const,
};
const TABS = ["now", "search", "compare", "delegations", "dictionary"] as const;
type Tab = (typeof TABS)[number];
const SEVERITIES = [1, 2, 3, 4, 5] as const;
const SOURCES = ["app", "call", "sms", "portal", "iot"] as const;
// A rise of these is worse (red), a fall better (green); the others are left plain.
const WORSE_WHEN_UP = new Set(["incidents", "injured", "deceased", "burned_ha", "to_assignment_min", "to_on_scene_min", "category", "severity"]);

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function lastDays(n: number): { from: string; to: string } {
  const to = new Date();
  return { from: iso(new Date(to.getTime() - (n - 1) * 86_400_000)), to: iso(to) };
}

/** A count of the window: under the floor the API answers null, shown "<5". */

function ExportButtons({ build }: { build: (format: "pdf" | "xlsx") => Parameters<ReturnType<typeof useServices>["api"]["windowExport"]>[0] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const run = useMutation({
    mutationFn: (format: "pdf" | "xlsx") => api.windowExport(build(format)),
    onSuccess: saveDownload,
  });
  return (
    <div className="win-export">
      {(["pdf", "xlsx"] as const).map((format) => (
        <button key={format} type="button" className="btn btn--small" disabled={run.isPending} onClick={() => run.mutate(format)}>
          {t(`window.export.${format}`)}
        </button>
      ))}
      <span className="muted">{t("window.export.audited")}</span>
      {run.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(run.error))}
        </p>
      )}
    </div>
  );
}

/** The advisory written summary of what is shown (§9, item 1): asked for, labelled, never a decision. */
function SummaryPanel({ build }: { build: () => Parameters<ReturnType<typeof useServices>["api"]["windowSummary"]>[0] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const run = useMutation({ mutationFn: () => api.windowSummary(build()) });
  return (
    <div className="win-summary">
      <button type="button" className="btn btn--small" disabled={run.isPending} onClick={() => run.mutate()}>
        {t(run.data ? "window.summary.again" : "window.summary.ask")}
      </button>
      {run.isPending && <Loading />}
      {run.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(run.error))}
        </p>
      )}
      {run.data && (
        <section className="win-summary__body" aria-label={t("window.summary.label")}>
          <p>
            <span className="tag tag--ai">{t("window.summary.label")}</span>{" "}
            <span className="muted">
              {run.data.model} · {fmt.dateTime(run.data.generated_at)}
            </span>
          </p>
          <p dir="auto" className={run.data.supported ? "" : "muted"}>
            {run.data.text}
          </p>
          <p className="muted">{run.data.notice}</p>
        </section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- the situation now

function NowTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const { user } = useAuth();
  const q = useQuery({ queryKey: WINDOW_KEYS.now, queryFn: ({ signal }) => api.windowNow(signal), refetchInterval: 60_000 });
  // RS1: the rooms open the resources inside an axis area from here; a delegated view has no resources.
  const toAxis = canOpenAxes(user?.identity.roles ?? []);
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorBox error={q.error} onRetry={() => void q.refetch()} />;
  const now = q.data;
  return (
    <div className="win-now">
      <p className="muted">{t("window.now.at", { at: fmt.dateTime(now.at) })}</p>
      <section className="card" aria-labelledby="win-axes">
        <h2 id="win-axes">{t("window.now.axes")}</h2>
        {now.axes.length === 0 ? (
          <p className="muted">{t("window.now.noAxes")}</p>
        ) : (
          <ul className="win-axes">
            {now.axes.map((a) => (
              <li key={a.id} className={`win-axis win-axis--level-${a.level}`}>
                <p>
                  <span className={`tag tag--level-${a.level}`}>{t(`crisis.level.${a.level}`)}</span>{" "}
                  <strong dir="auto">
                    {a.number} · {a.name}
                  </strong>{" "}
                  <span className="muted">
                    {t(`crisis.kind.${a.kind}`, a.kind)}
                    {a.gouvernorat_code ? ` · ${gouvernorats.nameOf(a.gouvernorat_code) ?? ""}` : ` · ${t("window.national")}`}
                    {" · "}
                    {t("window.now.attached", { n: a.incidents })}
                  </span>
                </p>
                <p className="muted">
                  {a.plan_title
                    ? t("window.now.plan", { title: a.plan_title })
                    : a.plan
                      ? t("window.now.planText")
                      : t("window.now.noPlan")}
                </p>
                {toAxis && !now.delegated && (
                  <p>
                    <Link className="btn btn--small btn--ghost" to={`/axes/${a.id}?tab=resources`}>
                      {t("window.now.areaResources", { number: a.number })}
                    </Link>
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="card" aria-labelledby="win-open">
        <h2 id="win-open">{t("window.now.open", { n: now.open_total })}</h2>
        <dl className="kpis">
          {now.open_incidents.map((c) => (
            <Kpi
              key={c.key}
              label={c.key === "unknown" ? t("window.severityUnknown") : t("window.severity", { n: c.key })}
              value={fmt.number(c.count ?? 0)}
            />
          ))}
        </dl>
      </section>
      {now.resources && (
        <section className="card" aria-labelledby="win-res">
          <h2 id="win-res">{t("window.now.resources")}</h2>
          <div className="table-wrap">
            <table className="table table--compact">
              <thead>
                <tr>
                  <th scope="col">{t("window.now.kind")}</th>
                  <th scope="col">{t("window.now.available")}</th>
                  <th scope="col">{t("window.now.assigned")}</th>
                  <th scope="col">{t("window.now.outOfService")}</th>
                </tr>
              </thead>
              <tbody>
                {now.resources.map((r) => (
                  <tr key={r.kind}>
                    <th scope="row">{t(`resources.kind.${r.kind}`, r.kind)}</th>
                    <td>{fmt.number(r.available)}</td>
                    <td>{fmt.number(r.assigned)}</td>
                    <td>{fmt.number(r.out_of_service)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {now.progress && (
        <section className="card" aria-labelledby="win-prog">
          <h2 id="win-prog">{t("window.now.progress")}</h2>
          <div className="table-wrap">
            <table className="table table--compact">
              <thead>
                <tr>
                  <th scope="col">{t("window.gouvernorat")}</th>
                  <th scope="col">{t("window.now.today")}</th>
                  <th scope="col">{t("window.now.week")}</th>
                </tr>
              </thead>
              <tbody>
                {now.progress.map((p) => (
                  <tr key={p.gouvernorat_code}>
                    <th scope="row">{p.gouvernorat_name}</th>
                    <td>{p.day_rate === null ? "—" : `${fmt.percent(p.day_rate)} (${p.day_done}/${p.day_due})`}</td>
                    <td>{p.week_rate === null ? "—" : `${fmt.percent(p.week_rate)} (${p.week_done}/${p.week_due})`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <section className="card" aria-labelledby="win-dec">
        <h2 id="win-dec">{t("window.now.decisions")}</h2>
        {now.decisions.length === 0 ? (
          <p className="muted">{t("window.now.noDecisions")}</p>
        ) : (
          <ul className="win-decisions">
            {now.decisions.map((d) => (
              <li key={d.id}>
                <p>
                  <span className="tag">{t(`crisis.directive.kind.${d.kind}`, d.kind)}</span>{" "}
                  <strong>
                    {d.axis_number} · {t(`crisis.directive.cat.${d.category}`, d.category)}
                  </strong>{" "}
                  <span className="muted">
                    {t(`crisis.role.${d.issuer_role}`, d.issuer_role)} · {fmt.dateTime(d.issued_at)} ·{" "}
                    {t(`crisis.directive.status.${d.status}`, d.status)}
                  </span>
                </p>
                <p dir="auto">{d.body}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- the search

function FilterFields({ value, onChange, national, period = true }: {
  value: WindowFilters;
  onChange: (f: WindowFilters) => void;
  national: boolean;
  period?: boolean;
}) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const set = (patch: Partial<WindowFilters>) => onChange({ ...value, ...patch });
  const one = (v: string) => (v ? [v] : []);
  return (
    <div className="filters__row win-filters">
      {period && (
        <>
          <div className="field">
            <label htmlFor={`${id}-from`}>{t("window.from")}</label>
            <input id={`${id}-from`} type="date" value={value.from ?? ""} onChange={(e) => set({ from: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor={`${id}-to`}>{t("window.to")}</label>
            <input id={`${id}-to`} type="date" value={value.to ?? ""} onChange={(e) => set({ to: e.target.value })} />
          </div>
        </>
      )}
      {national && (
        <div className="field">
          <label htmlFor={`${id}-g`}>{t("window.gouvernorat")}</label>
          <select
            id={`${id}-g`}
            value={value.gouvernorats?.[0] ?? ""}
            onChange={(e) => set({ gouvernorats: e.target.value ? [Number(e.target.value)] : [] })}
          >
            <option value="">{t("window.allGouvernorats")}</option>
            {gouvernorats.list.map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="field">
        <label htmlFor={`${id}-c`}>{t("window.category")}</label>
        <select id={`${id}-c`} value={value.category?.[0] ?? ""} onChange={(e) => set({ category: one(e.target.value) })}>
          <option value="">{t("window.any")}</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {t(`category.${c}`)}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-s`}>{t("window.severityLabel")}</label>
        <select
          id={`${id}-s`}
          value={value.severity?.[0] ?? ""}
          onChange={(e) => set({ severity: e.target.value ? [Number(e.target.value)] : [] })}
        >
          <option value="">{t("window.any")}</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {t("window.severity", { n: s })}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-st`}>{t("window.status")}</label>
        <select id={`${id}-st`} value={value.status?.[0] ?? ""} onChange={(e) => set({ status: one(e.target.value) })}>
          <option value="">{t("window.any")}</option>
          {(["open", "closed"] as const).map((s) => (
            <option key={s} value={s}>
              {t(`incidents.status.${s}`)}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-src`}>{t("window.source")}</label>
        <select id={`${id}-src`} value={value.source?.[0] ?? ""} onChange={(e) => set({ source: one(e.target.value) })}>
          <option value="">{t("window.any")}</option>
          {SOURCES.map((s) => (
            <option key={s} value={s}>
              {t(`window.sources.${s}`)}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

function SavedSearches({ kind, current, onOpen }: {
  kind: "search" | "compare";
  current: Record<string, unknown>;
  onOpen: (s: SavedSearch) => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [name, setName] = useState("");
  const q = useQuery({ queryKey: WINDOW_KEYS.saved, queryFn: ({ signal }) => api.savedSearches(signal) });
  const save = useMutation({
    mutationFn: () => api.saveSearch({ name: name.trim(), kind, query: current }),
    onSuccess: () => {
      setName("");
      void qc.invalidateQueries({ queryKey: WINDOW_KEYS.saved });
    },
  });
  const remove = useMutation({
    mutationFn: (sid: string) => api.deleteSearch(sid),
    onSuccess: () => void qc.invalidateQueries({ queryKey: WINDOW_KEYS.saved }),
  });
  const mine = (q.data ?? []).filter((s) => s.kind === kind);
  return (
    <div className="win-saved">
      <form
        className="win-saved__form"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) save.mutate();
        }}
      >
        <label htmlFor={`${id}-name`}>{t("window.saved.name")}</label>
        <input id={`${id}-name`} value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
        <button type="submit" className="btn btn--small" disabled={!name.trim() || save.isPending}>
          {t("window.saved.save")}
        </button>
      </form>
      {mine.length > 0 && (
        <ul className="win-saved__list" aria-label={t("window.saved.list")}>
          {mine.map((s) => (
            <li key={s.id}>
              <button type="button" className="btn btn--link" onClick={() => onOpen(s)}>
                {s.name}
              </button>
              <button
                type="button"
                className="btn btn--small btn--ghost"
                aria-label={t("window.saved.delete", { name: s.name })}
                onClick={() => remove.mutate(s.id)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Understood({ result }: { result: SearchResult }) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  if (result.understood.length === 0) return null;
  const label = (kind: string, key: string | null) => {
    if (!key) return "";
    if (kind === "category") return t(`category.${key}`, key);
    if (kind === "gouvernorat") return gouvernorats.nameOf(Number(key)) ?? key;
    return key;
  };
  return (
    <p className="win-understood">
      <span className="muted">{t("window.understood")}</span>{" "}
      {result.understood.map((u, i) => (
        <span key={i} className={`tag tag--understood-${u.kind}`} title={t(`window.kind.${u.kind}`)}>
          {u.text}
          {u.key && u.kind !== "word" && u.kind !== "reference" ? ` → ${label(u.kind, u.key)}` : ""}
        </span>
      ))}
    </p>
  );
}

function SearchTab({ access }: { access: WindowAccess }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const national = Boolean(user?.identity.national);
  const [draft, setDraft] = useState<WindowFilters>(() => lastDays(30));
  const [filters, setFilters] = useState<WindowFilters>(draft);
  const q = useQuery({
    queryKey: WINDOW_KEYS.search(filters),
    queryFn: ({ signal }) => api.windowSearch(filters, signal),
    placeholderData: keepPreviousData,
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setFilters(draft);
  };
  return (
    <div className="win-search">
      <form className="card" role="search" onSubmit={submit}>
        <div className="win-quick">
          <label htmlFor={`${id}-q`}>{t("window.quick")}</label>
          <input
            id={`${id}-q`}
            type="search"
            value={draft.q ?? ""}
            maxLength={200}
            placeholder={t("window.quickHint")}
            onChange={(e) => setDraft({ ...draft, q: e.target.value })}
          />
          <button type="submit" className="btn btn--primary">
            {t("window.searchButton")}
          </button>
        </div>
        <details className="win-advanced">
          <summary>{t("window.advanced")}</summary>
          <FilterFields value={draft} onChange={setDraft} national={national} />
        </details>
        <SavedSearches
          kind="search"
          current={{ ...filters }}
          onOpen={(s) => {
            const f = s.query as WindowFilters;
            setDraft(f);
            setFilters(f);
          }}
        />
      </form>
      {q.isPending && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && (
        <section className="card" aria-labelledby={`${id}-r`}>
          <div className="page__head">
            <h2 id={`${id}-r`}>
              {t("window.results", { from: fmt.date(q.data.from), to: fmt.date(q.data.to) })}
            </h2>
            <ExportButtons build={(format) => ({ kind: "search", format, lang, filters })} />
          </div>
          {access.delegated && !access.full && <p className="alert alert--info">{t("window.delegatedScope")}</p>}
          <Understood result={q.data} />
          <SummaryPanel build={() => ({ kind: "search", lang, filters })} />
          <FiguresView figures={q.data.figures} minCell={q.data.min_cell} />
          <div className="table-wrap">
            <table className="table table--compact">
              <caption>
                {t("window.items", { n: q.data.items.length })}
                {q.data.truncated ? ` · ${t("window.truncated")}` : ""}
              </caption>
              <thead>
                <tr>
                  <th scope="col">{t("window.ref")}</th>
                  <th scope="col">{t("window.category")}</th>
                  <th scope="col">{t("window.severityLabel")}</th>
                  <th scope="col">{t("window.status")}</th>
                  <th scope="col">{t("window.gouvernorat")}</th>
                  <th scope="col">{t("window.opened")}</th>
                  <th scope="col">{t("window.axis")}</th>
                </tr>
              </thead>
              <tbody>
                {q.data.items.map((i) => (
                  <tr key={i.id}>
                    <td dir="ltr">{access.full ? <Link to={`/incidents/${encodeURIComponent(i.id)}`}>{i.ref}</Link> : i.ref}</td>
                    <td>{t(`category.${i.category}`, i.category)}</td>
                    <td>{i.severity ?? "—"}</td>
                    <td>{t(`incidents.status.${i.status}`, i.status)}</td>
                    <td>{i.gouvernorat_code ? gouvernorats.nameOf(i.gouvernorat_code) : "—"}</td>
                    <td>{fmt.dateTime(i.opened_at)}</td>
                    <td>{i.axis_number ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- the comparison

function CompareTable({ result }: { result: CompareResult }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const count = useCount(result.min_cell);
  const counts = new Set(["incidents", "injured", "deceased", "rescued", "reports", "confirmed", "category", "severity", "gouvernorat"]);
  const value = (metric: string, v: number | null) => {
    if (v === null) return counts.has(metric) ? count(null) : "—";
    if (metric.endsWith("rate")) return fmt.percent(v);
    return fmt.decimal(v);
  };
  const name = (metric: string, key: string | null) => {
    const base = t(`window.metric.${metric}`, metric);
    if (key === null) return base;
    if (metric === "category") return `${base}: ${t(`category.${key}`, key)}`;
    if (metric === "gouvernorat") return `${base}: ${gouvernorats.nameOf(Number(key)) ?? key}`;
    if (metric === "severity") return `${base}: ${key}`;
    return `${base}: ${key}`;
  };
  const side = (s: CompareResult["a"]) =>
    `${fmt.date(s.from)} – ${fmt.date(s.to)}${s.gouvernorats.length ? ` · ${s.gouvernorats.map((g) => gouvernorats.nameOf(g)).join("، ")}` : ""}`;
  return (
    <div className="table-wrap">
      <table className="table table--compact win-compare">
        <thead>
          <tr>
            <th scope="col">{t("window.compare.metric")}</th>
            <th scope="col">
              {t("window.compare.a")}
              <br />
              <span className="muted">{side(result.a)}</span>
            </th>
            <th scope="col">
              {t("window.compare.b")}
              <br />
              <span className="muted">{side(result.b)}</span>
            </th>
            <th scope="col">{t("window.compare.delta")}</th>
            <th scope="col">{t("window.compare.pct")}</th>
          </tr>
        </thead>
        <tbody>
          {result.rows.map((r) => (
            <tr key={`${r.metric}-${r.key ?? ""}`}>
              <th scope="row">{name(r.metric, r.key)}</th>
              <td>{value(r.metric, r.a)}</td>
              <td>{value(r.metric, r.b)}</td>
              <td className={r.delta === null || !WORSE_WHEN_UP.has(r.metric) ? "" : r.delta > 0 ? "win-up" : r.delta < 0 ? "win-down" : ""}>
                {r.delta === null ? "—" : fmt.signed(r.metric.endsWith("rate") ? r.delta * 100 : r.delta)}
              </td>
              <td>{r.pct === null ? "—" : fmt.signed(r.pct * 100) + "%"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CompareTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const national = Boolean(user?.identity.national);
  const year = new Date().getFullYear();
  const [mode, setMode] = useState<CompareMode>("periods");
  const [cmp, setCmp] = useState<CompareQuery>({
    mode: "periods",
    a_from: `${year - 1}-07-01`,
    a_to: `${year - 1}-08-31`,
    b_from: `${year}-07-01`,
    b_to: `${year}-08-31`,
  });
  const [filters, setFilters] = useState<WindowFilters>({ ...lastDays(30) });
  const [asked, setAsked] = useState<{ f: WindowFilters; c: CompareQuery } | null>(null);
  const q = useQuery({
    queryKey: asked ? WINDOW_KEYS.compare(asked.f, asked.c) : ["window", "compare", "idle"],
    queryFn: ({ signal }) => (asked ? api.windowCompare(asked.f, asked.c, signal) : Promise.resolve(null)),
    enabled: asked !== null,
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setAsked({ f: filters, c: { ...cmp, mode } });
  };
  const dates = (side: "a" | "b") => (
    <fieldset className="win-side">
      <legend>{t(`window.compare.${side}`)}</legend>
      <div className="field">
        <label htmlFor={`${id}-${side}-from`}>{t("window.from")}</label>
        <input
          id={`${id}-${side}-from`}
          type="date"
          value={cmp[`${side}_from`] ?? ""}
          onChange={(e) => setCmp({ ...cmp, [`${side}_from`]: e.target.value })}
        />
      </div>
      <div className="field">
        <label htmlFor={`${id}-${side}-to`}>{t("window.to")}</label>
        <input
          id={`${id}-${side}-to`}
          type="date"
          value={cmp[`${side}_to`] ?? ""}
          onChange={(e) => setCmp({ ...cmp, [`${side}_to`]: e.target.value })}
        />
      </div>
    </fieldset>
  );
  const place = (side: "a" | "b") => (
    <div className="field">
      <label htmlFor={`${id}-${side}-g`}>{t(`window.compare.${side}`)}</label>
      <select
        id={`${id}-${side}-g`}
        value={cmp[`${side}_gouvernorat`] ?? ""}
        onChange={(e) => setCmp({ ...cmp, [`${side}_gouvernorat`]: e.target.value ? Number(e.target.value) : null })}
      >
        <option value="">{t("window.choose")}</option>
        {gouvernorats.list.map((g) => (
          <option key={g.code} value={g.code}>
            {gouvernorats.nameOf(g.code)}
          </option>
        ))}
      </select>
    </div>
  );
  return (
    <div className="win-compare-tab">
      <form className="card" onSubmit={submit}>
        <fieldset className="segmented">
          <legend>{t("window.compare.mode")}</legend>
          {(national ? (["periods", "gouvernorats"] as const) : (["periods"] as const)).map((m) => (
            <label key={m} className="segmented__item">
              <input type="radio" name={`${id}-mode`} checked={mode === m} onChange={() => setMode(m)} />
              <span>{t(`window.compare.modes.${m}`)}</span>
            </label>
          ))}
        </fieldset>
        {mode === "periods" ? (
          <div className="win-sides">
            {dates("a")}
            {dates("b")}
          </div>
        ) : (
          <div className="filters__row">
            {place("a")}
            {place("b")}
          </div>
        )}
        <FilterFields value={filters} onChange={setFilters} national={national && mode === "periods"} period={mode === "gouvernorats"} />
        <button type="submit" className="btn btn--primary">
          {t("window.compare.run")}
        </button>
        <SavedSearches
          kind="compare"
          current={{ filters, compare: { ...cmp, mode } }}
          onOpen={(s) => {
            const saved = s.query as { filters?: WindowFilters; compare?: CompareQuery };
            if (saved.filters) setFilters(saved.filters);
            if (saved.compare) {
              setCmp(saved.compare);
              setMode(saved.compare.mode);
              setAsked({ f: saved.filters ?? {}, c: saved.compare });
            }
          }}
        />
      </form>
      {asked && q.isPending && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && asked && (
        <section className="card" aria-labelledby={`${id}-res`}>
          <div className="page__head">
            <h2 id={`${id}-res`}>{t("window.compare.title")}</h2>
            <ExportButtons build={(format) => ({ kind: "compare", format, lang, filters: asked.f, compare: { ...asked.c, filters: asked.f } })} />
          </div>
          <SummaryPanel build={() => ({ kind: "compare", lang, filters: asked.f, compare: { ...asked.c, filters: asked.f } })} />
          <CompareTable result={q.data} />
          <p className="muted">{t("window.floor", { n: q.data.min_cell })}</p>
        </section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- delegations

function GrantForm() {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const [search, setSearch] = useState("");
  const [grantee, setGrantee] = useState("");
  const [ends, setEnds] = useState("");
  const [reason, setReason] = useState("");
  const [axes, setAxes] = useState<string[]>([]);
  const [incidents, setIncidents] = useState("");
  const [tried, setTried] = useState(false);
  const delegates = useQuery({ queryKey: WINDOW_KEYS.delegates(search), queryFn: ({ signal }) => api.delegates(search, signal) });
  const now = useQuery({ queryKey: WINDOW_KEYS.now, queryFn: ({ signal }) => api.windowNow(signal) });
  const events: EventRef[] = [
    ...axes.map((a) => ({ kind: "axis" as const, id: a })),
    ...incidents
      .split(/[\s,،]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => ({ kind: "incident" as const, id: s })),
  ];
  const grant = useMutation({
    mutationFn: () =>
      api.grantDelegation({ grantee, reason: reason.trim(), ends_at: new Date(ends).toISOString(), events }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["window", "delegations"] });
      setReason("");
      setAxes([]);
      setIncidents("");
      setTried(false);
    },
  });
  const valid = grantee && ends && events.length > 0 && reasonValid(reason);
  return (
    <form
      className="card win-grant"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (valid) grant.mutate();
      }}
    >
      <h2>{t("window.delegation.new")}</h2>
      <p className="muted">{t("window.delegation.intro")}</p>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${id}-find`}>{t("window.delegation.find")}</label>
          <input id={`${id}-find`} type="search" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-who`}>{t("window.delegation.grantee")}</label>
          <select id={`${id}-who`} value={grantee} onChange={(e) => setGrantee(e.target.value)} aria-invalid={tried && !grantee}>
            <option value="">{t("window.choose")}</option>
            {(delegates.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} · {d.roles.map((r) => t(`roles.${r}`)).join("، ")}
                {d.gouvernorat_code ? ` · ${gouvernorats.nameOf(d.gouvernorat_code) ?? ""}` : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-ends`}>{t("window.delegation.ends")}</label>
          <input
            id={`${id}-ends`}
            type="datetime-local"
            value={ends}
            onChange={(e) => setEnds(e.target.value)}
            aria-invalid={tried && !ends}
          />
        </div>
      </div>
      <fieldset className="win-events">
        <legend>{t("window.delegation.events")}</legend>
        {(now.data?.axes ?? []).length === 0 && <p className="muted">{t("window.now.noAxes")}</p>}
        {(now.data?.axes ?? []).map((a) => (
          <label key={a.id} className="checkbox">
            <input
              type="checkbox"
              checked={axes.includes(a.id)}
              onChange={(e) => setAxes(e.target.checked ? [...axes, a.id] : axes.filter((x) => x !== a.id))}
            />{" "}
            {a.number} · {a.name}
          </label>
        ))}
        <div className="field">
          <label htmlFor={`${id}-inc`}>{t("window.delegation.incidents")}</label>
          <input id={`${id}-inc`} dir="ltr" value={incidents} onChange={(e) => setIncidents(e.target.value)} />
          <p className="field__hint">{t("window.delegation.incidentsHint")}</p>
        </div>
        {tried && events.length === 0 && (
          <p className="field__error" role="alert">
            {t("window.delegation.eventsRequired")}
          </p>
        )}
      </fieldset>
      <ReasonField label={t("window.delegation.reason")} value={reason} onChange={setReason} range={REASON_RANGE} showError={tried} />
      <button type="submit" className="btn btn--primary" disabled={grant.isPending}>
        {t("window.delegation.grant")}
      </button>
      {grant.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(grant.error))}
        </p>
      )}
      {grant.isSuccess && (
        <p className="alert alert--success" role="status">
          {t("window.delegation.granted")}
        </p>
      )}
    </form>
  );
}

function RevokeDelegation({ delegation }: { delegation: Delegation }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const revoke = useMutation({
    mutationFn: () => api.revokeDelegation(delegation.id, reason.trim()),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["window", "delegations"] });
      setOpen(false);
    },
  });
  if (!open)
    return (
      <button type="button" className="btn btn--small" onClick={() => setOpen(true)}>
        {t("window.delegation.revoke")}
      </button>
    );
  return (
    <InlineDialog title={t("window.delegation.revokeTitle")} onClose={() => setOpen(false)}>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          setTried(true);
          if (reasonValid(reason)) revoke.mutate();
        }}
      >
        <ReasonField label={t("window.delegation.reason")} value={reason} onChange={setReason} showError={tried} />
        <button type="submit" className="btn btn--danger" disabled={revoke.isPending}>
          {t("window.delegation.revoke")}
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

export function DelegationCard({ d, manage }: { d: Delegation; manage: boolean }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  return (
    <li className={`win-delegation win-delegation--${d.state}`}>
      <p>
        <strong dir="auto">{d.grantee_name ?? d.grantee}</strong>{" "}
        <span className="muted">
          {d.grantee_roles.map((r) => t(`roles.${r}`)).join("، ")}
          {d.grantee_gouvernorat ? ` · ${gouvernorats.nameOf(d.grantee_gouvernorat) ?? ""}` : ""}
        </span>{" "}
        <span className={`tag tag--rule-${d.state}`}>{t(`window.delegation.state.${d.state}`)}</span>
      </p>
      <p className="muted">
        {t("window.delegation.period", { from: fmt.dateTime(d.starts_at), to: fmt.dateTime(d.ends_at) })} ·{" "}
        {t("window.delegation.by", { name: d.granted_by_name ?? "" })}
      </p>
      <ul className="win-delegation__events">
        {d.events.map((e) => (
          <li key={`${e.kind}-${e.id}`}>
            <span className="tag">{t(`window.delegation.kind.${e.kind}`)}</span> <span dir="auto">{e.label}</span>
          </li>
        ))}
      </ul>
      <blockquote dir="auto">{d.reason}</blockquote>
      {d.revoked_at && (
        <p className="muted">
          {t("window.delegation.revokedBy", { name: d.revoked_by_name ?? "", at: fmt.dateTime(d.revoked_at) })}
          {d.revoke_reason ? ` · ${d.revoke_reason}` : ""}
        </p>
      )}
      {manage && (d.state === "active" || d.state === "scheduled") && <RevokeDelegation delegation={d} />}
    </li>
  );
}

function DelegationsTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const [ended, setEnded] = useState(false);
  const q = useQuery({ queryKey: WINDOW_KEYS.delegations(ended), queryFn: ({ signal }) => api.delegations(ended, signal) });
  return (
    <div className="win-delegations">
      <GrantForm />
      <section className="card" aria-labelledby="win-dl">
        <div className="page__head">
          <h2 id="win-dl">{t("window.delegation.list")}</h2>
          <label className="checkbox">
            <input type="checkbox" checked={ended} onChange={(e) => setEnded(e.target.checked)} /> {t("window.delegation.showEnded")}
          </label>
        </div>
        {q.isPending && <Loading />}
        {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
        {q.isSuccess && q.data.length === 0 && <p className="muted">{t("window.delegation.none")}</p>}
        {q.isSuccess && q.data.length > 0 && (
          <ul className="win-delegation-list">
            {q.data.map((d) => (
              <DelegationCard key={d.id} d={d} manage />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- the dictionary

function DictionaryTab() {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [meaning, setMeaning] = useState("");
  const [words, setWords] = useState("");
  const q = useQuery({ queryKey: WINDOW_KEYS.synonyms, queryFn: ({ signal }) => api.synonyms(signal) });
  const split = (s: string) => s.split(/[,،\n]+/).map((w) => w.trim()).filter(Boolean);
  const put = useMutation({
    mutationFn: () => api.putSynonym(meaning.trim(), split(words)),
    onSuccess: () => {
      setMeaning("");
      setWords("");
      void qc.invalidateQueries({ queryKey: WINDOW_KEYS.synonyms });
    },
  });
  const remove = useMutation({
    mutationFn: (sid: string) => api.deleteSynonym(sid),
    onSuccess: () => void qc.invalidateQueries({ queryKey: WINDOW_KEYS.synonyms }),
  });
  return (
    <div className="win-dictionary">
      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          if (meaning.trim() && split(words).length) put.mutate();
        }}
      >
        <h2>{t("window.dictionary.title")}</h2>
        <p className="muted">{t("window.dictionary.intro")}</p>
        <div className="filters__row">
          <div className="field">
            <label htmlFor={`${id}-m`}>{t("window.dictionary.meaning")}</label>
            <input id={`${id}-m`} value={meaning} maxLength={80} onChange={(e) => setMeaning(e.target.value)} />
            <p className="field__hint">{t("window.dictionary.meaningHint")}</p>
          </div>
          <div className="field">
            <label htmlFor={`${id}-w`}>{t("window.dictionary.words")}</label>
            <textarea id={`${id}-w`} rows={2} value={words} onChange={(e) => setWords(e.target.value)} />
          </div>
        </div>
        <button type="submit" className="btn btn--primary" disabled={put.isPending}>
          {t("window.dictionary.save")}
        </button>
        {put.isError && (
          <p className="alert alert--error" role="alert">
            {t(errorMessageKey(put.error))}
          </p>
        )}
      </form>
      <section className="card">
        {q.isPending && <Loading />}
        {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
        {q.isSuccess && (
          <ul className="win-synonyms">
            {q.data.map((s) => (
              <li key={s.id}>
                <p>
                  <strong>{t(`category.${s.meaning}`, s.meaning)}</strong>{" "}
                  <span className="muted" dir="ltr">
                    ({s.meaning})
                  </span>
                </p>
                <p dir="auto">{s.words.join("، ")}</p>
                <div className="win-synonyms__actions">
                  <button
                    type="button"
                    className="btn btn--small"
                    onClick={() => {
                      setMeaning(s.meaning);
                      setWords(s.words.join("، "));
                    }}
                  >
                    {t("window.dictionary.edit")}
                  </button>
                  <button type="button" className="btn btn--small btn--ghost" onClick={() => remove.mutate(s.id)}>
                    {t("window.dictionary.delete")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- the page

/**
 * The decision window (L4, design-l4.md §3): the situation now, the search, the comparison of two periods or two
 * gouvernorats, the reports. The central room and the gouvernorats' ops managers open it; the minister, a governor
 * or a committee only through a delegation, and only on its events (§5). Aggregates only, small counts hidden.
 */
export function WindowPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const q = useQuery({ queryKey: WINDOW_KEYS.access, queryFn: ({ signal }) => api.windowAccess(signal) });
  const [tab, setTab] = useState<Tab>("now");
  const head = (
    <div className="page__head">
      <PageTitle icon="insights" tone="navy">
        {t("window.title")}
      </PageTitle>
    </div>
  );
  if (q.isPending)
    return (
      <div className="page win-page">
        {head}
        <Loading />
      </div>
    );
  if (q.isError)
    return (
      <div className="page win-page">
        {head}
        <ErrorBox error={q.error} onRetry={() => void q.refetch()} />
      </div>
    );
  const access = q.data;
  if (!access.full && !access.delegated)
    return (
      <div className="page win-page">
        {head}
        <p className="alert alert--info">{t("window.noDelegation")}</p>
      </div>
    );
  const tabs = TABS.filter(
    (k) => (k !== "delegations" || access.may_delegate) && (k !== "dictionary" || access.keeps_dictionary),
  );
  const ends = access.delegations.map((d) => d.ends_at).sort()[0];
  return (
    <div className="page win-page">
      {head}
      <p className="muted">{t(access.full ? "window.intro" : "window.introDelegated")}</p>
      {access.delegated && !access.full && (
        <div className="alert alert--info">
          <p>{t("window.delegatedUntil", { at: ends ? fmt.dateTime(ends) : "" })}</p>
          <ul className="win-delegation__events">
            {access.delegations.flatMap((d) =>
              d.events.map((e) => (
                <li key={`${d.id}-${e.kind}-${e.id}`}>
                  <span className="tag">{t(`window.delegation.kind.${e.kind}`)}</span> <span dir="auto">{e.label}</span>
                </li>
              )),
            )}
          </ul>
        </div>
      )}
      <div role="tablist" aria-label={t("window.tabs.label")} className="tabs">
        {tabs.map((k) => (
          <button
            key={k}
            type="button"
            role="tab"
            aria-selected={tab === k}
            className={`tabs__tab${tab === k ? " tabs__tab--active" : ""}`}
            onClick={() => setTab(k)}
          >
            {t(`window.tabs.${k}`)}
          </button>
        ))}
      </div>
      <div role="tabpanel" aria-label={t(`window.tabs.${tab}`)}>
        {tab === "now" && <NowTab />}
        {tab === "search" && <SearchTab access={access} />}
        {tab === "compare" && <CompareTab />}
        {tab === "delegations" && access.may_delegate && <DelegationsTab />}
        {tab === "dictionary" && access.keeps_dictionary && <DictionaryTab />}
      </div>
    </div>
  );
}
