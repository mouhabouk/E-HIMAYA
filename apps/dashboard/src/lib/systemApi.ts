/**
 * The technical administrators' two windows (Yamen, 2026-11-08; docs/phase-h/design-h5.md):
 * the system logs (Loki behind the API) and the change journal ("mouchard", audit.change).
 * National system or security administrators only; every read is written to the audit log.
 */
import type { ApiClient } from "./api";

const A = "/api/v1/admin";

export type LogLevel = "debug" | "info" | "warning" | "error" | "critical";

export interface LogLine {
  at: string;
  service: string;
  level: string | null;
  event: string | null;
  request_id: string | null;
  fields: Record<string, unknown> | null;
  text: string | null;
}

export interface LogPage {
  items: LogLine[];
  query: string;
}

export interface ServiceCount {
  service: string;
  errors: number;
  warnings: number;
}

export interface LogSummary {
  hours: number;
  services: ServiceCount[];
}

export interface LogFilters {
  service?: string;
  level?: LogLevel | "";
  request_id?: string;
  contains?: string;
  minutes?: number;
}

export type ChangeOp = "I" | "U" | "D";
export type ActorKind = "staff" | "public" | "system" | "database";

export interface ChangeEntry {
  id: number;
  at: string;
  op: ChangeOp;
  schema_name: string;
  table_name: string;
  row_key: Record<string, unknown>;
  columns: string[];
  hidden: string[];
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  actor_kind: ActorKind;
  actor: string;
  actor_name: string | null;
  request_id: string | null;
  gouvernorat_code: number | null;
}

export interface ChangePage {
  items: ChangeEntry[];
  next_cursor: string | null;
}

export interface Count {
  key: string;
  count: number;
}

export interface ChangeSummary {
  hours: number;
  total: number;
  by_op: Count[];
  by_schema: Count[];
  by_actor_kind: Count[];
  tables: string[];
}

export interface ChangeFilters {
  schema?: string;
  table?: string;
  op?: ChangeOp | "";
  actor?: string;
  actor_kind?: ActorKind | "";
  request_id?: string;
  row?: string;
  from?: string;
  to?: string;
}

const clean = (v: string | undefined | null) =>
  v && v.trim() ? v.trim() : undefined;

export function systemApi(api: ApiClient) {
  return {
    systemLogs: (f: LogFilters, signal?: AbortSignal) =>
      api.request<LogPage>(`${A}/logs`, {
        query: {
          service: clean(f.service),
          level: f.level || undefined,
          request_id: clean(f.request_id),
          contains: clean(f.contains),
          minutes: f.minutes ?? 60,
          limit: 300,
        },
        signal,
      }),
    systemLogSummary: (hours = 24, signal?: AbortSignal) =>
      api.request<LogSummary>(`${A}/logs/summary`, {
        query: { hours },
        signal,
      }),
    changes: (
      f: ChangeFilters,
      opts: { cursor?: string | null; signal?: AbortSignal } = {},
    ) =>
      api.request<ChangePage>(`${A}/changes`, {
        query: {
          schema: clean(f.schema),
          table: clean(f.table),
          op: f.op || undefined,
          actor: clean(f.actor),
          actor_kind: f.actor_kind || undefined,
          request_id: clean(f.request_id),
          row: clean(f.row),
          from: f.from || undefined,
          to: f.to || undefined,
          cursor: opts.cursor ?? undefined,
          limit: 50,
        },
        signal: opts.signal,
      }),
    changeSummary: (hours = 24, signal?: AbortSignal) =>
      api.request<ChangeSummary>(`${A}/changes/summary`, {
        query: { hours },
        signal,
      }),
  };
}

export const systemKeys = {
  logs: (f: LogFilters) => ["system", "logs", f] as const,
  logSummary: (hours: number) => ["system", "logs", "summary", hours] as const,
  changes: (f: ChangeFilters) => ["system", "changes", f] as const,
  changeSummary: (hours: number) =>
    ["system", "changes", "summary", hours] as const,
};

/** The two windows: national system or security administrators (technical roles, no operational rights). */
export function canReadSystemTrail(who: {
  roles: readonly string[];
  national: boolean;
}): boolean {
  return (
    who.national &&
    (who.roles.includes("sysadmin") || who.roles.includes("security_admin"))
  );
}

/** A value of the journal as short text. */
export function valueText(v: unknown): string {
  if (v === null || v === undefined) return "∅";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}
