import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { Icon, IconTile, Pill, type IconName } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { useServices } from "../context/services";
import { ApiError } from "../lib/api";
import { useDebounced, useFormat } from "../lib/hooks";
import { saveDownload } from "../lib/layersApi";
import {
  resultAsTsv,
  sqlIdent,
  tableQuery,
  viewRows,
  type ColumnFilters,
  type ResultSort,
  sqlCellText,
  sqlKeys,
  statementAt,
  type SqlExample,
  type SqlExportFormat,
  type SqlHistoryEntry,
  type SqlHistoryView,
  type SqlProblem,
  type SqlResult,
  type SqlSchema,
} from "../lib/sqlApi";

const PAGE = 50;
const EXPORTS: { format: SqlExportFormat; label: string; icon: IconName }[] = [
  { format: "xlsx", label: "Excel", icon: "table" },
  { format: "csv", label: "CSV", icon: "description" },
  { format: "json", label: "JSON", icon: "description" },
  { format: "sql", label: "SQL", icon: "database" },
  { format: "html", label: "HTML", icon: "description" },
  { format: "md", label: "Markdown", icon: "description" },
];
const VIEWS: SqlHistoryView[] = ["all", "pinned", "errors"];

function problemOf(error: unknown): SqlProblem | null {
  if (!(error instanceof ApiError)) return null;
  const d = error.detail as Partial<SqlProblem> | null;
  return d && typeof d === "object" && typeof d.message === "string"
    ? { code: d.code ?? "", message: d.message, position: d.position ?? null }
    : null;
}

/** Where a database error's 1-based character position falls in the editor: "line 3, column 8". */
function lineOf(
  text: string,
  position: number,
): { line: number; column: number } {
  const before = text.slice(0, Math.max(0, position - 1));
  const lines = before.split("\n");
  return {
    line: lines.length,
    column: (lines[lines.length - 1]?.length ?? 0) + 1,
  };
}

/**
 * The SQL window (Yamen, 2026-11-09; docs/sql/console.md): the connection of each configured database, a query box,
 * the result as a table with its export, the tree of tables, and the administrator's own history of queries.
 * Read only: one reading statement at a time, in a READ ONLY transaction; every run is written to the audit log.
 */
export function SqlConsolePage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const client = useQueryClient();
  const base = useId();
  const editor = useRef<HTMLTextAreaElement>(null);
  const [connection, setConnection] = useState("");
  const [sql, setSql] = useState(
    "SELECT now() AS server_time, current_user, version();",
  );
  const [ran, setRan] = useState<{ sql: string; connection: string } | null>(
    null,
  );
  const [tab, setTab] = useState<"result" | "messages">("result");
  const [page, setPage] = useState(0);
  const [copied, setCopied] = useState(false);
  const [view, setView] = useState<SqlHistoryView>("all");
  const [search, setSearch] = useState("");
  const [tableFilter, setTableFilter] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  // Browsing a table (a click in the tree): its rows in the result, filtered and sorted there or by the database.
  const [browsing, setBrowsing] = useState<{ schema: string; table: string } | null>(null);
  const [filters, setFilters] = useState<ColumnFilters>({});
  const [sort, setSort] = useState<ResultSort | null>(null);
  const [columnSearch, setColumnSearch] = useState("");
  const keepView = useRef(false);
  const [editing, setEditing] = useState<{ id: string; title: string } | null>(
    null,
  );
  const q = useDebounced(search, 300);

  const connections = useQuery({
    queryKey: sqlKeys.connections,
    queryFn: ({ signal }) => api.sqlConnections(signal),
    retry: false,
  });
  const current =
    connections.data?.find((c) => c.name === connection) ??
    connections.data?.[0];

  const schema = useQuery({
    queryKey: sqlKeys.schema(current?.name ?? ""),
    queryFn: ({ signal }) => api.sqlSchema(current?.name ?? "", signal),
    enabled: Boolean(current),
    retry: false,
  });
  const examples = useQuery({
    queryKey: sqlKeys.examples,
    queryFn: ({ signal }) => api.sqlExamples(signal),
    retry: false,
  });
  const history = useQuery({
    queryKey: sqlKeys.history({ q, view }),
    queryFn: ({ signal }) => api.sqlHistory({ q, view }, signal),
    retry: false,
  });
  const refreshHistory = () =>
    void client.invalidateQueries({ queryKey: sqlKeys.allHistory });

  const ping = useMutation({
    mutationFn: (name: string) => api.sqlTestConnection(name),
  });
  const run = useMutation({
    mutationFn: (body: { connection: string; sql: string }) =>
      api.sqlQuery(body),
    onMutate: (body) => {
      setRan(body);
      setPage(0);
      if (!keepView.current) {
        setFilters({});
        setSort(null);
        setColumnSearch("");
      }
      keepView.current = false;
    },
    onSuccess: (r: SqlResult) =>
      setTab(r.notices.length && !r.columns.length ? "messages" : "result"),
    onSettled: refreshHistory,
  });
  const exporting = useMutation({
    mutationFn: (format: SqlExportFormat) =>
      api.sqlExport({
        connection: ran?.connection ?? current?.name ?? "",
        sql: ran?.sql ?? sql,
        format,
      }),
    onSuccess: saveDownload,
  });
  const edit = useMutation({
    mutationFn: (v: {
      id: string;
      body: { title?: string | null; sql?: string; pinned?: boolean };
    }) => api.sqlEditHistory(v.id, v.body),
    onSuccess: () => {
      setEditing(null);
      refreshHistory();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.sqlDeleteHistory(id),
    onSuccess: refreshHistory,
  });

  const execute = (text?: string) => {
    if (!current) return;
    const area = editor.current;
    const chosen =
      text ??
      (area && area.selectionEnd > area.selectionStart
        ? sql.slice(area.selectionStart, area.selectionEnd)
        : statementAt(sql, area?.selectionStart ?? sql.length));
    const statement = chosen.trim().replace(/;\s*$/, "");
    if (!statement) return;
    setBrowsing(null);
    run.mutate({ connection: current.name, sql: statement });
  };
  const browse = (schemaName: string, table: string) => {
    if (!current) return;
    const statement = tableQuery(schemaName, table, [], {}, null, 100);
    setSql(`${statement};`);
    setBrowsing({ schema: schemaName, table });
    run.mutate({ connection: current.name, sql: statement });
  };
  /** The filters and order of the table sent to the database, over the whole table. */
  const applyToTable = () => {
    if (!current || !browsing || !run.data) return;
    const statement = tableQuery(
      browsing.schema,
      browsing.table,
      run.data.columns.map((c) => c.name),
      filters,
      sort,
      current.max_rows,
    );
    setSql(`${statement};`);
    keepView.current = true;
    run.mutate({ connection: current.name, sql: statement });
  };
  const toggleSort = (column: number) => {
    setPage(0);
    setSort((s) =>
      s?.column !== column ? { column, desc: false } : s.desc ? null : { column, desc: true },
    );
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      execute();
    } else if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      const area = e.currentTarget;
      const { selectionStart: s, selectionEnd: end } = area;
      setSql(sql.slice(0, s) + "  " + sql.slice(end));
      requestAnimationFrame(() => area.setSelectionRange(s + 2, s + 2));
    }
  };
  const insert = (text: string) => {
    const area = editor.current;
    const at = area?.selectionStart ?? sql.length;
    setSql(sql.slice(0, at) + text + sql.slice(area?.selectionEnd ?? at));
    requestAnimationFrame(() => {
      area?.focus();
      area?.setSelectionRange(at + text.length, at + text.length);
    });
  };
  const load = (text: string) => {
    setSql(text.endsWith(";") ? text : `${text};`);
    editor.current?.focus();
  };

  const result = run.data;
  const problem = problemOf(run.error);
  const where =
    problem?.position && ran ? lineOf(ran.sql, problem.position) : null;
  const viewed = useMemo(
    () => (result ? viewRows(result.rows, filters, sort) : []),
    [result, filters, sort],
  );
  const visible = useMemo(() => {
    const f = columnSearch.trim().toLowerCase();
    return (result?.columns ?? [])
      .map((c, i) => ({ ...c, i }))
      .filter((c) => !f || c.name.toLowerCase().includes(f));
  }, [result, columnSearch]);
  const filtering = Object.values(filters).some((f) => f.trim()) || sort !== null;
  const pages = Math.max(1, Math.ceil(viewed.length / PAGE));
  const shown = viewed.slice(page * PAGE, page * PAGE + PAGE);
  const lines = sql.split("\n").length;
  const filteredSchema: SqlSchema[] = useMemo(() => {
    const f = tableFilter.trim().toLowerCase();
    if (!f) return schema.data ?? [];
    return (schema.data ?? [])
      .map((s) => ({
        ...s,
        tables: s.tables.filter(
          (tb) =>
            `${s.name}.${tb.name}`.includes(f) ||
            tb.columns.some((c) => c.name.toLowerCase().includes(f)),
        ),
      }))
      .filter((s) => s.tables.length > 0);
  }, [schema.data, tableFilter]);
  const exampleList = examples.data;
  const sections = useMemo(() => {
    const by = new Map<string, SqlExample[]>();
    for (const e of exampleList ?? [])
      by.set(e.section, [...(by.get(e.section) ?? []), e]);
    return [...by.entries()];
  }, [exampleList]);

  if (connections.isPending) return <Loading />;
  if (connections.isError) {
    const off =
      connections.error instanceof ApiError && connections.error.status === 503;
    return (
      <div className="page">
        <PageTitle icon="database" tone="slate">
          {t("sqlConsole.title")}
        </PageTitle>
        {off ? (
          <p className="alert alert--warning">{t("sqlConsole.off")}</p>
        ) : (
          <ErrorBox
            error={connections.error}
            onRetry={() => void connections.refetch()}
          />
        )}
      </div>
    );
  }

  return (
    <div className="page sql-console">
      <div className="page__head">
        <PageTitle icon="database" tone="slate">
          {t("sqlConsole.title")}
        </PageTitle>
        {current && (
          <div className="sql-console__limits">
            <Pill tone="green">{t("sqlConsole.readOnly")}</Pill>
            <Pill tone="slate">
              {t("sqlConsole.limits", {
                seconds: current.timeout_s,
                rows: current.max_rows,
              })}
            </Pill>
          </div>
        )}
      </div>
      <p className="muted">{t("sqlConsole.intro")}</p>

      <section className="card sql-connection" aria-labelledby={`${base}-conn`}>
        <h2 id={`${base}-conn`} className="sql-card-title">
          <IconTile name="database" tone="green" size="sm" />
          {t("sqlConsole.connection.title")}
        </h2>
        <div className="sql-connection__fields">
          <div className="field">
            <label htmlFor={`${base}-target`}>
              {t("sqlConsole.connection.name")}
            </label>
            <select
              id={`${base}-target`}
              value={current?.name ?? ""}
              onChange={(e) => {
                setConnection(e.target.value);
                ping.reset();
              }}
            >
              {connections.data.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          {(
            [
              ["host", current?.host],
              ["port", current?.port],
              ["database", current?.database],
              ["user", current?.user],
              [
                "ssl",
                current?.sslmode ?? t("sqlConsole.connection.sslDefault"),
              ],
            ] as const
          ).map(([k, v]) => (
            <div className="field" key={k}>
              <label htmlFor={`${base}-${k}`}>
                {t(`sqlConsole.connection.${k}`)}
              </label>
              <input
                id={`${base}-${k}`}
                dir="ltr"
                className="code"
                value={String(v ?? "")}
                readOnly
              />
            </div>
          ))}
          <div className="field">
            <label htmlFor={`${base}-pw`}>
              {t("sqlConsole.connection.password")}
            </label>
            <input
              id={`${base}-pw`}
              value={t("sqlConsole.connection.passwordKept")}
              readOnly
            />
          </div>
          <button
            type="button"
            className="btn btn--primary sql-connection__test"
            disabled={!current || ping.isPending}
            onClick={() => current && ping.mutate(current.name)}
          >
            {ping.isPending
              ? t("sqlConsole.connection.testing")
              : t("sqlConsole.connection.test")}
          </button>
        </div>
        <p className="muted sql-hint">{t("sqlConsole.connection.where")}</p>
        {ping.data && (
          <p
            className={`sql-status ${ping.data.ok ? "sql-status--ok" : "sql-status--error"}`}
            role="status"
          >
            <Icon name={ping.data.ok ? "check" : "warning"} />
            {ping.data.ok ? (
              <>
                <strong>{t("sqlConsole.connection.ok")}</strong>
                <span dir="ltr">{ping.data.version?.split(" on ")[0]}</span>
                <span>
                  {t("sqlConsole.connection.role")}{" "}
                  <b dir="ltr">{ping.data.role}</b>
                </span>
                <span>
                  {ping.data.can_write || ping.data.superuser
                    ? t("sqlConsole.connection.roleCanWrite")
                    : t("sqlConsole.connection.roleReadOnly")}
                </span>
                <span>
                  {t("sqlConsole.connection.size", { size: ping.data.size })}
                </span>
                <span>
                  {t("sqlConsole.connection.latency", {
                    ms: ping.data.latency_ms,
                  })}
                </span>
              </>
            ) : (
              <>
                <strong>{t("sqlConsole.connection.failed")}</strong>
                <span dir="ltr">{ping.data.error}</span>
              </>
            )}
          </p>
        )}
      </section>

      <div className="sql-console__grid">
        <aside className="card sql-tree" aria-labelledby={`${base}-tree`}>
          <h2 id={`${base}-tree`} className="sql-card-title">
            <IconTile name="table" tone="purple" size="sm" />
            {t("sqlConsole.tree.title")}
          </h2>
          <input
            type="search"
            className="sql-search"
            aria-label={t("sqlConsole.tree.search")}
            placeholder={t("sqlConsole.tree.search")}
            dir="ltr"
            value={tableFilter}
            onChange={(e) => setTableFilter(e.target.value)}
          />
          {schema.isPending && <Loading />}
          {schema.isError && (
            <ErrorBox
              error={schema.error}
              onRetry={() => void schema.refetch()}
            />
          )}
          <ul className="sql-tree__list" dir="ltr">
            {filteredSchema.map((s) => {
              const isOpen = open[s.name] ?? Boolean(tableFilter.trim());
              return (
                <li key={s.name}>
                  <button
                    type="button"
                    className="sql-tree__schema"
                    aria-expanded={isOpen}
                    onClick={() =>
                      setOpen((o) => ({ ...o, [s.name]: !isOpen }))
                    }
                  >
                    <span>{s.name}</span>
                    <span className="muted">{s.tables.length}</span>
                  </button>
                  {isOpen && (
                    <ul>
                      {s.tables.map((tb) => {
                        const key = `${s.name}.${tb.name}`;
                        return (
                          <li key={key}>
                            <button
                              type="button"
                              className="sql-tree__table"
                              title={tb.comment ?? undefined}
                              aria-expanded={Boolean(open[key])}
                              aria-current={
                                browsing?.schema === s.name &&
                                browsing.table === tb.name
                                  ? "true"
                                  : undefined
                              }
                              onClick={() => {
                                const opening = !open[key];
                                setOpen((o) => ({ ...o, [key]: opening }));
                                if (opening) browse(s.name, tb.name);
                              }}
                            >
                              <span>{tb.name}</span>
                              <span className="muted">
                                {tb.kind === "view"
                                  ? t("sqlConsole.tree.view")
                                  : fmt.number(tb.approx_rows)}
                              </span>
                            </button>
                            {open[key] && (
                              <ul className="sql-tree__columns">
                                <li>
                                  <button
                                    type="button"
                                    className="link-button"
                                    onClick={() => browse(s.name, tb.name)}
                                  >
                                    {t("sqlConsole.tree.first100")}
                                  </button>
                                </li>
                                {tb.columns.map((c) => (
                                  <li key={c.name}>
                                    <button
                                      type="button"
                                      className="sql-tree__column"
                                      onClick={() => insert(sqlIdent(c.name))}
                                    >
                                      <span>{c.name}</span>
                                      <span className="sql-type">{c.type}</span>
                                    </button>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
          <p className="muted sql-hint">{t("sqlConsole.tree.hint")}</p>
        </aside>

        <div className="sql-console__main">
          <section
            className="card sql-editor"
            aria-labelledby={`${base}-editor`}
          >
            <h2 id={`${base}-editor`} className="visually-hidden">
              {t("sqlConsole.editor.title")}
            </h2>
            <div className="sql-editor__bar">
              <button
                type="button"
                className="btn btn--primary sql-run"
                disabled={!current || run.isPending}
                onClick={() => execute()}
              >
                <Icon name="playArrow" />
                {run.isPending
                  ? t("sqlConsole.editor.running")
                  : t("sqlConsole.editor.run")}
                <kbd dir="ltr">Ctrl+Enter</kbd>
              </button>
              <button
                type="button"
                className="btn"
                disabled={!current || run.isPending}
                onClick={() => {
                  const statement = statementAt(
                    sql,
                    editor.current?.selectionStart ?? sql.length,
                  );
                  if (statement)
                    execute(
                      /^\s*explain\b/i.test(statement)
                        ? statement
                        : `EXPLAIN ${statement}`,
                    );
                }}
              >
                {t("sqlConsole.editor.explain")}
              </button>
              <button type="button" className="btn" onClick={() => setSql("")}>
                <Icon name="close" />
                {t("sqlConsole.editor.clear")}
              </button>
              <label className="sql-examples">
                <span className="visually-hidden">
                  {t("sqlConsole.editor.examples")}
                </span>
                <select
                  value=""
                  onChange={(e) => {
                    const found = examples.data?.find(
                      (x) => x.id === e.target.value,
                    );
                    if (found)
                      load(`-- ${found.id} · ${found.title}\n${found.sql}`);
                  }}
                >
                  <option value="">
                    {t("sqlConsole.editor.examplesCount", {
                      count: examples.data?.length ?? 0,
                    })}
                  </option>
                  {sections.map(([section, items]) => (
                    <optgroup key={section} label={section}>
                      {items.map((x) => (
                        <option key={x.id} value={x.id} title={x.description}>
                          {x.id} · {x.title}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </label>
            </div>
            <div className="sql-editor__box" dir="ltr">
              <pre className="sql-editor__gutter" aria-hidden="true">
                {Array.from({ length: lines }, (_, i) => i + 1).join("\n")}
              </pre>
              <textarea
                ref={editor}
                aria-label={t("sqlConsole.editor.label")}
                className="sql-editor__text"
                spellCheck={false}
                autoCapitalize="off"
                autoCorrect="off"
                value={sql}
                rows={Math.min(Math.max(lines + 1, 8), 22)}
                onChange={(e) => setSql(e.target.value)}
                onKeyDown={onKey}
              />
            </div>
            <p className="muted sql-hint">{t("sqlConsole.editor.hint")}</p>
          </section>

          <section
            className="card sql-result"
            aria-labelledby={`${base}-result`}
            aria-busy={run.isPending}
          >
            <h2 id={`${base}-result`} className="visually-hidden">
              {t("sqlConsole.result.title")}
            </h2>
            <div className="tabs" role="tablist">
              {(["result", "messages"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  role="tab"
                  aria-selected={tab === k}
                  className={`tabs__tab ${tab === k ? "tabs__tab--active" : ""}`}
                  onClick={() => setTab(k)}
                >
                  {t(`sqlConsole.result.${k}`)}
                  {k === "messages" && result?.notices.length
                    ? ` (${result.notices.length})`
                    : ""}
                </button>
              ))}
            </div>
            {run.isIdle && (
              <p className="muted sql-empty">{t("sqlConsole.result.idle")}</p>
            )}
            {run.isPending && <Loading />}
            {run.isError && (
              <div className="alert alert--error sql-problem" role="alert">
                <p>
                  <strong>
                    {problem
                      ? t("sqlConsole.result.refused")
                      : t("sqlConsole.result.failed")}
                  </strong>
                  {problem?.code && /^[0-9A-Z]{5}$/.test(problem.code) && (
                    <span className="code" dir="ltr">
                      {" "}
                      SQLSTATE {problem.code}
                    </span>
                  )}
                </p>
                {problem ? (
                  <pre dir="auto">{problem.message}</pre>
                ) : (
                  <ErrorBox error={run.error} />
                )}
                {where && <p>{t("sqlConsole.result.position", where)}</p>}
              </div>
            )}
            {result && tab === "messages" && (
              <ul className="sql-messages" dir="ltr">
                <li>
                  {result.command} ·{" "}
                  {t("sqlConsole.result.rows", { count: result.row_count })} ·{" "}
                  {result.duration_ms} ms · {fmt.dateTime(result.executed_at)}
                </li>
                {result.notices.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            )}
            {result && tab === "result" && (
              <>
                <div className="sql-result__bar">
                  <Pill tone="green">
                    {t("sqlConsole.result.rows", { count: result.row_count })}
                  </Pill>
                  <Pill tone="slate">{`${result.duration_ms} ms`}</Pill>
                  <Pill tone="slate">
                    {t("sqlConsole.result.columns", {
                      count: result.columns.length,
                    })}
                  </Pill>
                  {result.truncated && (
                    <Pill tone="amber">{t("sqlConsole.result.truncated")}</Pill>
                  )}
                  <span className="sql-result__export">
                    <span className="muted">
                      {t("sqlConsole.result.export")}
                    </span>
                    {EXPORTS.map((x) => (
                      <button
                        key={x.format}
                        type="button"
                        className="btn btn--small"
                        disabled={exporting.isPending || !result.columns.length}
                        onClick={() => exporting.mutate(x.format)}
                      >
                        <Icon name={x.icon} size={16} />
                        {x.label}
                      </button>
                    ))}
                    <button
                      type="button"
                      className="btn btn--small"
                      disabled={!result.columns.length}
                      onClick={() =>
                        void navigator.clipboard
                          .writeText(resultAsTsv(result))
                          .then(() => {
                            setCopied(true);
                            setTimeout(() => setCopied(false), 2000);
                          })
                      }
                    >
                      <Icon name="contentCopy" size={16} />
                      {copied
                        ? t("sqlConsole.result.copied")
                        : t("sqlConsole.result.copy")}
                    </button>
                  </span>
                </div>
                {exporting.isError && <ErrorBox error={exporting.error} />}
                {result.truncated && (
                  <p className="muted sql-hint">
                    {t("sqlConsole.result.truncatedHint", {
                      rows: current?.max_rows,
                      exportRows: current?.export_max_rows,
                    })}
                  </p>
                )}
                {result.columns.length > 0 && (
                  <div className="sql-view-bar">
                    {browsing && (
                      <Pill tone="purple">
                        <span dir="ltr">{`${browsing.schema}.${browsing.table}`}</span>
                      </Pill>
                    )}
                    <input
                      type="search"
                      className="sql-search sql-view-bar__search"
                      dir="auto"
                      aria-label={t("sqlConsole.view.columnSearch")}
                      placeholder={t("sqlConsole.view.columnSearch")}
                      value={columnSearch}
                      onChange={(e) => setColumnSearch(e.target.value)}
                    />
                    <span className="muted">
                      {t("sqlConsole.view.shown", {
                        rows: viewed.length,
                        total: result.rows.length,
                        columns: visible.length,
                        allColumns: result.columns.length,
                      })}
                    </span>
                    {(filtering || columnSearch) && (
                      <button
                        type="button"
                        className="btn btn--small"
                        onClick={() => {
                          setFilters({});
                          setSort(null);
                          setColumnSearch("");
                          setPage(0);
                        }}
                      >
                        <Icon name="close" size={16} />
                        {t("sqlConsole.view.clear")}
                      </button>
                    )}
                    {browsing && filtering && (
                      <button
                        type="button"
                        className="btn btn--small btn--primary"
                        disabled={run.isPending}
                        onClick={applyToTable}
                      >
                        <Icon name="search" size={16} />
                        {t("sqlConsole.view.applyToTable")}
                      </button>
                    )}
                  </div>
                )}
                {result.columns.length > 0 && (
                  <p className="muted sql-hint">
                    {browsing
                      ? t("sqlConsole.view.hintTable", { limit: current?.max_rows })
                      : t("sqlConsole.view.hint")}
                  </p>
                )}
                {result.columns.length === 0 ? (
                  <p className="muted sql-empty">
                    {t("sqlConsole.result.noColumns")}
                  </p>
                ) : (
                  <div className="table-wrap sql-table-wrap">
                    <table className="table table--compact sql-table" dir="ltr">
                      <caption className="visually-hidden">
                        {t("sqlConsole.result.caption")}
                      </caption>
                      <thead>
                        <tr>
                          <th scope="col" className="sql-table__n">
                            #
                          </th>
                          {visible.map((c) => (
                            <th
                              scope="col"
                              key={`${c.name}-${c.i}`}
                              aria-sort={
                                sort?.column === c.i
                                  ? sort.desc
                                    ? "descending"
                                    : "ascending"
                                  : undefined
                              }
                            >
                              <button
                                type="button"
                                className="sql-sort"
                                title={t("sqlConsole.view.sort")}
                                onClick={() => toggleSort(c.i)}
                              >
                                <span>
                                  {c.name}
                                  {sort?.column === c.i
                                    ? sort.desc
                                      ? " ▼"
                                      : " ▲"
                                    : ""}
                                </span>
                                <span className="sql-type">{c.type}</span>
                              </button>
                            </th>
                          ))}
                        </tr>
                        <tr className="sql-filters">
                          <td />
                          {visible.map((c) => (
                            <td key={`f-${c.name}-${c.i}`}>
                              <input
                                type="search"
                                dir="auto"
                                aria-label={t("sqlConsole.view.filter", {
                                  column: c.name,
                                })}
                                placeholder={t("sqlConsole.view.filterShort")}
                                value={filters[c.i] ?? ""}
                                onChange={(e) => {
                                  setPage(0);
                                  setFilters((f) => ({
                                    ...f,
                                    [c.i]: e.target.value,
                                  }));
                                }}
                              />
                            </td>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {shown.map((row, r) => (
                          <tr key={page * PAGE + r}>
                            <td className="sql-table__n">
                              {page * PAGE + r + 1}
                            </td>
                            {visible.map(({ i }) => {
                              const v = row[i];
                              return (
                              <td
                                key={i}
                                dir="auto"
                                className={
                                  v === null
                                    ? "sql-null"
                                    : typeof v === "number"
                                      ? "sql-number"
                                      : undefined
                                }
                              >
                                {sqlCellText(v)}
                              </td>
                              );
                            })}
                          </tr>
                        ))}
                        {shown.length === 0 && (
                          <tr>
                            <td
                              colSpan={visible.length + 1}
                              className="muted"
                            >
                              {t("sqlConsole.result.noRows")}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
                {pages > 1 && (
                  <div className="sql-paging">
                    <span className="muted">
                      {t("sqlConsole.result.range", {
                        from: page * PAGE + 1,
                        to: Math.min((page + 1) * PAGE, viewed.length),
                        total: viewed.length,
                      })}
                    </span>
                    <button
                      type="button"
                      className="btn btn--small"
                      disabled={page === 0}
                      onClick={() => setPage(page - 1)}
                    >
                      {t("sqlConsole.result.previous")}
                    </button>
                    <button
                      type="button"
                      className="btn btn--small"
                      disabled={page + 1 >= pages}
                      onClick={() => setPage(page + 1)}
                    >
                      {t("sqlConsole.result.next")}
                    </button>
                  </div>
                )}
              </>
            )}
          </section>
        </div>

        <aside className="card sql-history" aria-labelledby={`${base}-history`}>
          <h2 id={`${base}-history`} className="sql-card-title">
            <IconTile name="schedule" tone="navy" size="sm" />
            {t("sqlConsole.history.title")}
          </h2>
          <div
            className="sql-history__views"
            role="group"
            aria-label={t("sqlConsole.history.title")}
          >
            {VIEWS.map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                className={`sql-chip ${view === v ? "sql-chip--on" : ""}`}
                onClick={() => setView(v)}
              >
                {t(`sqlConsole.history.views.${v}`)}
              </button>
            ))}
          </div>
          <input
            type="search"
            className="sql-search"
            aria-label={t("sqlConsole.history.search")}
            placeholder={t("sqlConsole.history.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {history.isPending && <Loading />}
          {history.isError && (
            <ErrorBox
              error={history.error}
              onRetry={() => void history.refetch()}
            />
          )}
          {history.isSuccess && history.data.length === 0 && (
            <p className="muted sql-empty">{t("sqlConsole.history.empty")}</p>
          )}
          {(edit.isError || remove.isError) && (
            <ErrorBox error={edit.error ?? remove.error} />
          )}
          <ul className="sql-history__list">
            {(history.data ?? []).map((h: SqlHistoryEntry) => (
              <li
                key={h.id}
                className={`sql-entry ${h.pinned ? "sql-entry--pinned" : ""}`}
              >
                <div className="sql-entry__head">
                  {editing?.id === h.id ? (
                    <form
                      className="sql-entry__rename"
                      onSubmit={(e) => {
                        e.preventDefault();
                        edit.mutate({
                          id: h.id,
                          body: { title: editing.title.trim() || null },
                        });
                      }}
                    >
                      <input
                        aria-label={t("sqlConsole.history.titleLabel")}
                        value={editing.title}
                        maxLength={120}
                        autoFocus
                        onChange={(e) =>
                          setEditing({ id: h.id, title: e.target.value })
                        }
                      />
                      <button
                        type="submit"
                        className="btn btn--small btn--primary"
                      >
                        {t("sqlConsole.history.save")}
                      </button>
                      <button
                        type="button"
                        className="btn btn--small"
                        onClick={() => setEditing(null)}
                      >
                        {t("sqlConsole.history.cancel")}
                      </button>
                    </form>
                  ) : (
                    <strong dir="auto">
                      {h.title ?? t("sqlConsole.history.untitled")}
                    </strong>
                  )}
                  {h.status === "ok" ? (
                    <Pill tone="green">
                      {t("sqlConsole.result.rows", { count: h.rows ?? 0 })}
                    </Pill>
                  ) : (
                    <Pill tone="red">{t("sqlConsole.history.error")}</Pill>
                  )}
                </div>
                <code className="sql-entry__sql" dir="ltr" title={h.sql}>
                  {h.sql}
                </code>
                {h.error && (
                  <p className="sql-entry__error" dir="auto" title={h.error}>
                    {h.error}
                  </p>
                )}
                <p className="muted sql-entry__meta">
                  <span dir="ltr">{h.connection}</span> ·{" "}
                  {fmt.dateTime(h.last_run_at)} ·{" "}
                  {t("sqlConsole.history.runs", { count: h.run_count })}
                </p>
                <div className="sql-entry__actions">
                  <button
                    type="button"
                    className="btn btn--icon"
                    title={t("sqlConsole.history.run")}
                    aria-label={t("sqlConsole.history.run")}
                    onClick={() => {
                      setConnection(h.connection);
                      load(h.sql);
                      run.mutate({ connection: h.connection, sql: h.sql });
                    }}
                  >
                    <Icon name="playArrow" size={18} />
                  </button>
                  <button
                    type="button"
                    className="btn btn--icon"
                    title={t("sqlConsole.history.open")}
                    aria-label={t("sqlConsole.history.open")}
                    onClick={() => load(h.sql)}
                  >
                    <Icon name="edit" size={18} />
                  </button>
                  <button
                    type="button"
                    className="btn btn--icon"
                    title={t("sqlConsole.history.rename")}
                    aria-label={t("sqlConsole.history.rename")}
                    onClick={() =>
                      setEditing({ id: h.id, title: h.title ?? "" })
                    }
                  >
                    <Icon name="description" size={18} />
                  </button>
                  <button
                    type="button"
                    className="btn btn--icon"
                    aria-pressed={h.pinned}
                    title={
                      h.pinned
                        ? t("sqlConsole.history.unpin")
                        : t("sqlConsole.history.pin")
                    }
                    aria-label={
                      h.pinned
                        ? t("sqlConsole.history.unpin")
                        : t("sqlConsole.history.pin")
                    }
                    onClick={() =>
                      edit.mutate({ id: h.id, body: { pinned: !h.pinned } })
                    }
                  >
                    <Icon name="keep" size={18} />
                  </button>
                  {sql.trim().replace(/;\s*$/, "") !== h.sql && (
                    <button
                      type="button"
                      className="btn btn--icon"
                      title={t("sqlConsole.history.replace")}
                      aria-label={t("sqlConsole.history.replace")}
                      onClick={() =>
                        edit.mutate({
                          id: h.id,
                          body: { sql: sql.trim().replace(/;\s*$/, "") },
                        })
                      }
                    >
                      <Icon name="download" size={18} />
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn--icon btn--danger"
                    title={t("sqlConsole.history.delete")}
                    aria-label={t("sqlConsole.history.delete")}
                    onClick={() => {
                      if (window.confirm(t("sqlConsole.history.confirmDelete")))
                        remove.mutate(h.id);
                    }}
                  >
                    <Icon name="delete" size={18} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <p className="muted sql-hint">{t("sqlConsole.history.note")}</p>
        </aside>
      </div>
    </div>
  );
}
