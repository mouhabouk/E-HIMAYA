/**
 * The SQL window of the national system administrator (Yamen, 2026-11-09; docs/sql/console.md): the configured
 * connections, one reading statement at a time, the result as a table, its export, and the administrator's history.
 */
import type { ApiClient } from "./api";
import type { Download } from "./layersApi";

const S = "/api/v1/admin/sql";

export interface SqlConnection {
  name: string;
  host: string;
  port: number;
  database: string;
  user: string;
  sslmode: string | null;
  read_only: boolean;
  timeout_s: number;
  max_rows: number;
  export_max_rows: number;
}

export interface SqlPing {
  name: string;
  ok: boolean;
  version?: string | null;
  role?: string | null;
  database?: string | null;
  size?: string | null;
  superuser?: boolean | null;
  can_write?: boolean | null;
  latency_ms?: number | null;
  server_time?: string | null;
  error?: string | null;
}

export interface SqlColumn {
  name: string;
  type: string;
}

export interface SqlResult {
  command: string;
  columns: SqlColumn[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  duration_ms: number;
  notices: string[];
  executed_at: string;
}

/** The refusal or error the API sends back for a query (`detail`). */
export interface SqlProblem {
  code: string;
  message: string;
  position: number | null;
}

export interface SqlTable {
  name: string;
  kind: "table" | "view";
  approx_rows: number;
  comment: string | null;
  columns: { name: string; type: string; not_null: boolean }[];
}

export interface SqlSchema {
  name: string;
  tables: SqlTable[];
}

export interface SqlExample {
  id: string;
  section: string;
  title: string;
  description: string;
  sql: string;
}

export interface SqlHistoryEntry {
  id: string;
  connection: string;
  sql: string;
  title: string | null;
  pinned: boolean;
  status: "ok" | "error";
  command: string | null;
  rows: number | null;
  truncated: boolean;
  duration_ms: number | null;
  error: string | null;
  run_count: number;
  created_at: string;
  last_run_at: string;
  updated_at: string;
}

export type SqlExportFormat = "xlsx" | "csv" | "json" | "sql" | "html" | "md";
export type SqlHistoryView = "all" | "pinned" | "errors";

export function sqlApi(api: ApiClient) {
  return {
    sqlConnections: (signal?: AbortSignal) =>
      api.request<SqlConnection[]>(`${S}/connections`, { signal }),
    sqlTestConnection: (name: string) =>
      api.request<SqlPing>(
        `${S}/connections/${encodeURIComponent(name)}/test`,
        { method: "POST" },
      ),
    sqlSchema: (name: string, signal?: AbortSignal) =>
      api.request<SqlSchema[]>(
        `${S}/connections/${encodeURIComponent(name)}/schema`,
        { signal },
      ),
    sqlExamples: (signal?: AbortSignal) =>
      api.request<SqlExample[]>(`${S}/examples`, { signal }),
    sqlQuery: (body: { connection: string; sql: string; max_rows?: number }) =>
      api.request<SqlResult>(`${S}/query`, { method: "POST", body }),
    sqlExport: async (body: {
      connection: string;
      sql: string;
      format: SqlExportFormat;
    }): Promise<Download> => {
      const response = await api.requestRaw(`${S}/export`, {
        method: "POST",
        body,
        accept: "*/*",
      });
      const match = /filename="([^"]+)"/.exec(
        response.headers.get("Content-Disposition") ?? "",
      );
      return {
        blob: await response.blob(),
        filename: match?.[1] ?? `ehimaya-query.${body.format}`,
      };
    },
    sqlHistory: (
      f: { q?: string; view?: SqlHistoryView },
      signal?: AbortSignal,
    ) =>
      api.request<SqlHistoryEntry[]>(`${S}/history`, {
        query: {
          q: f.q?.trim() || undefined,
          only: f.view && f.view !== "all" ? f.view : undefined,
        },
        signal,
      }),
    sqlEditHistory: (
      id: string,
      body: { title?: string | null; sql?: string; pinned?: boolean },
    ) =>
      api.request<SqlHistoryEntry>(`${S}/history/${id}`, {
        method: "PATCH",
        body,
      }),
    sqlDeleteHistory: (id: string) =>
      api.request<undefined>(`${S}/history/${id}`, { method: "DELETE" }),
  };
}

export const sqlKeys = {
  connections: ["sql", "connections"] as const,
  schema: (name: string) => ["sql", "schema", name] as const,
  examples: ["sql", "examples"] as const,
  history: (f: { q?: string; view?: SqlHistoryView }) =>
    ["sql", "history", f] as const,
  allHistory: ["sql", "history"] as const,
};

/** The window: the national system administrator only (security administrators read the trail, not the data). */
export function canUseSqlConsole(who: {
  roles: readonly string[];
  national: boolean;
}): boolean {
  return who.national && who.roles.includes("sysadmin");
}

/** A cell as text: NULL shown apart, objects as JSON. */
export function sqlCellText(v: unknown): string {
  if (v === null || v === undefined) return "NULL";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

/** The result as tab-separated text for the clipboard (a spreadsheet pastes it as cells). */
export function resultAsTsv(
  result: Pick<SqlResult, "columns" | "rows">,
): string {
  const clean = (s: string) => s.replace(/[\t\n\r]+/g, " ");
  const head = result.columns.map((c) => clean(c.name)).join("\t");
  const body = result.rows.map((r) =>
    r.map((v) => (v === null ? "" : clean(sqlCellText(v)))).join("\t"),
  );
  return [head, ...body].join("\n");
}

/** The statement under the cursor when the editor holds several (split on `;` outside quotes and comments). */
export function statementAt(text: string, cursor: number): string {
  const parts: { start: number; end: number }[] = [];
  let start = 0;
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    const next = text[i + 1];
    if (c === "-" && next === "-") {
      const nl = text.indexOf("\n", i);
      i = nl === -1 ? text.length : nl + 1;
      continue;
    }
    if (c === "/" && next === "*") {
      const close = text.indexOf("*/", i + 2);
      i = close === -1 ? text.length : close + 2;
      continue;
    }
    if (c === "'" || c === '"') {
      let j = i + 1;
      while (j < text.length) {
        if (text[j] === c && text[j + 1] === c) j += 2;
        else if (text[j] === c) break;
        else j += 1;
      }
      i = j + 1;
      continue;
    }
    if (c === "$") {
      const tag = /^\$[A-Za-z_]*\$/.exec(text.slice(i));
      if (tag) {
        const close = text.indexOf(tag[0], i + tag[0].length);
        i = close === -1 ? text.length : close + tag[0].length;
        continue;
      }
    }
    if (c === ";") {
      parts.push({ start, end: i });
      start = i + 1;
    }
    i += 1;
  }
  parts.push({ start, end: text.length });
  const meaningful = parts.filter((p) =>
    text
      .slice(p.start, p.end)
      .replace(/--[^\n]*/g, "")
      .trim(),
  );
  if (meaningful.length <= 1)
    return (
      meaningful[0] ? text.slice(meaningful[0].start, meaningful[0].end) : text
    ).trim();
  const hit =
    meaningful.find((p) => cursor >= p.start && cursor <= p.end + 1) ??
    meaningful[meaningful.length - 1];
  return hit ? text.slice(hit.start, hit.end).trim() : text.trim();
}

/** A name as PostgreSQL reads it: bare when it is a plain lower-case name, quoted otherwise. */
export function sqlIdent(name: string): string {
  return /^[a-z_][a-z0-9_]*$/.test(name) ? name : `"${name.replace(/"/g, '""')}"`;
}

/** Filters of the result's columns, by column position: the text a cell must contain ("NULL" for an empty cell). */
export type ColumnFilters = Record<number, string>;
export interface ResultSort {
  column: number;
  desc: boolean;
}

function cellMatches(value: unknown, filter: string): boolean {
  const f = filter.trim();
  if (!f) return true;
  if (f.toUpperCase() === "NULL") return value === null || value === undefined;
  if (value === null || value === undefined) return false;
  return sqlCellText(value).toLocaleLowerCase().includes(f.toLocaleLowerCase());
}

function compare(a: unknown, b: unknown): number {
  if (a === b) return 0;
  if (a === null || a === undefined) return 1;
  if (b === null || b === undefined) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return sqlCellText(a).localeCompare(sqlCellText(b), undefined, { numeric: true });
}

/** The rows the table shows: those every column filter keeps, in the chosen order (empty cells last). */
export function viewRows(rows: unknown[][], filters: ColumnFilters, sort: ResultSort | null): unknown[][] {
  const active = Object.entries(filters).filter(([, f]) => f.trim());
  const kept = active.length ? rows.filter((r) => active.every(([i, f]) => cellMatches(r[Number(i)], f))) : rows;
  if (!sort) return kept;
  const sorted = [...kept].sort((a, b) => {
    const nulls = a[sort.column] === null ? 1 : 0;
    const nullsB = b[sort.column] === null ? 1 : 0;
    if (nulls !== nullsB) return nulls - nullsB;
    return compare(a[sort.column], b[sort.column]) * (sort.desc ? -1 : 1);
  });
  return sorted;
}

const likeLiteral = (text: string) =>
  "'%" + text.replace(/\\/g, "\\\\").replace(/%/g, "\\%").replace(/_/g, "\\_").replace(/'/g, "''") + "%'";

/**
 * The same filters and order applied by the database to the whole table (not only the rows already read):
 * `column::text ILIKE '%…%'` for each filter, `IS NULL` for "NULL".
 */
export function tableQuery(
  schema: string,
  table: string,
  columns: string[],
  filters: ColumnFilters,
  sort: ResultSort | null,
  limit: number,
): string {
  const where = Object.entries(filters)
    .filter(([i, f]) => f.trim() && columns[Number(i)] !== undefined)
    .map(([i, f]) => {
      const col = sqlIdent(columns[Number(i)] ?? "");
      return f.trim().toUpperCase() === "NULL" ? `${col} IS NULL` : `${col}::text ILIKE ${likeLiteral(f.trim())}`;
    });
  const lines = [`SELECT *`, `FROM ${sqlIdent(schema)}.${sqlIdent(table)}`];
  if (where.length) lines.push(`WHERE ${where.join("\n  AND ")}`);
  const sorted = sort ? columns[sort.column] : undefined;
  if (sort && sorted !== undefined) lines.push(`ORDER BY ${sqlIdent(sorted)} ${sort.desc ? "DESC" : "ASC"} NULLS LAST`);
  lines.push(`LIMIT ${limit}`);
  return lines.join("\n");
}
