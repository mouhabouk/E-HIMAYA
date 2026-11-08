import type { ApiClient } from "./api";

const P = "/api/v1/staff/personnel";
const enc = encodeURIComponent;

/** Phase H1 (docs/phase-h/design-h.md): personnel management, apart from the operations rooms. */
export const CATEGORIES = ["intervention", "room", "admin"] as const;
export type Category = (typeof CATEGORIES)[number];
export const ABSENCE_KINDS = [
  "annual",
  "rest",
  "compensatory",
  "sick",
  "paternity",
  "maternity",
  "mission",
  "training",
  "other",
] as const;
export type AbsenceKind = (typeof ABSENCE_KINDS)[number];
export const EVENT_KINDS = ["rank", "appointment", "transfer", "sanction", "reward"] as const;
export type EventKind = (typeof EVENT_KINDS)[number];

export interface PersonnelUnit {
  id: string;
  name: string;
  gouvernorat_code: number;
}

export interface AbsenceBrief {
  id: string;
  kind: AbsenceKind;
  starts_on: string;
  ends_on: string;
}

export interface PersonnelAgent {
  id: string;
  matricule: string;
  full_name: string;
  rank: string | null;
  post: string | null;
  category: Category;
  unit_id: string;
  unit_name: string;
  gouvernorat_code: number;
  /** The personnel department only. */
  phone: string | null;
  /** The absence of the day asked for; null: present. */
  absence: AbsenceBrief | null;
  version: number;
}

export interface PersonnelAgents {
  on: string;
  items: PersonnelAgent[];
  can_edit: boolean;
}

export interface AgentFilters {
  gouvernorat?: number | null;
  unit_id?: string | null;
  category?: Category | "";
  q?: string;
}

export interface AgentInput {
  unit_id: string;
  matricule: string;
  full_name: string;
  rank?: string | null;
  post?: string | null;
  category: Category;
  phone?: string | null;
}

export interface AgentEdit {
  matricule: string;
  full_name: string;
  category: Category;
  phone: string | null;
  version: number;
}

export interface PersonnelEvent {
  id: string;
  kind: EventKind;
  effective_on: string;
  title: string | null;
  unit_id: string | null;
  unit_name: string | null;
  from_unit_id: string | null;
  from_unit_name: string | null;
  reference: string | null;
  note: string | null;
  created_by_name: string | null;
  created_at: string;
  cancelled_at: string | null;
  cancelled_by_name: string | null;
  cancel_reason: string | null;
}

export interface EventInput {
  kind: EventKind;
  effective_on: string;
  title?: string | null;
  unit_id?: string | null;
  reference?: string | null;
  note?: string | null;
}

export interface Absence {
  id: string;
  agent_id: string;
  matricule: string;
  full_name: string;
  unit_id: string;
  unit_name: string;
  gouvernorat_code: number;
  kind: AbsenceKind;
  starts_on: string;
  ends_on: string;
  days: number;
  /** The personnel department only (null for the operations rooms). */
  reference: string | null;
  note: string | null;
  created_by_name: string | null;
  created_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  version: number;
}

export interface Absences {
  start: string;
  end: string;
  items: Absence[];
  can_edit: boolean;
}

export interface AbsenceFilters {
  start: string;
  end: string;
  gouvernorat?: number | null;
  unit_id?: string | null;
  kind?: AbsenceKind | "";
}

export interface AbsenceInput {
  agent_id: string;
  kind: AbsenceKind;
  starts_on: string;
  ends_on: string;
  reference?: string | null;
  note?: string | null;
  version?: number;
}

export interface AgentFile {
  agent: PersonnelAgent;
  events: PersonnelEvent[];
  absences: Absence[];
}

export interface StrengthCount {
  total: number;
  absent: number;
  present: number;
  by_kind: Partial<Record<AbsenceKind, number>>;
}

export interface StrengthRow {
  unit_id: string | null;
  unit_name: string;
  gouvernorat_code: number | null;
  intervention: StrengthCount;
  room: StrengthCount;
  admin: StrengthCount;
}

export interface Strength {
  on: string;
  units: StrengthRow[];
  total: StrengthRow;
}

export const personnelKeys = {
  all: ["personnel"] as const,
  units: (g: number | null) => ["personnel", "units", g] as const,
  agents: (f: AgentFilters) => ["personnel", "agents", f] as const,
  file: (id: string) => ["personnel", "file", id] as const,
  absences: (f: AbsenceFilters) => ["personnel", "absences", f] as const,
  strength: (on: string, g: number | null) => ["personnel", "strength", on, g] as const,
};

const blank = (v: string | null | undefined) => (v?.trim() ? v.trim() : null);

export function personnelApi(api: ApiClient) {
  return {
    personnelUnits: (gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<PersonnelUnit[]>(`${P}/units`, { query: { gouvernorat: gouvernorat ?? undefined }, signal }),
    personnelAgents: (f: AgentFilters, signal?: AbortSignal) =>
      api.request<PersonnelAgents>(`${P}/agents`, {
        query: {
          gouvernorat: f.gouvernorat ?? undefined,
          unit_id: f.unit_id || undefined,
          category: f.category || undefined,
          q: f.q?.trim() || undefined,
        },
        signal,
      }),
    createPersonnelAgent: (body: AgentInput) =>
      api.request<PersonnelAgent>(`${P}/agents`, {
        method: "POST",
        body: { ...body, rank: blank(body.rank), post: blank(body.post), phone: blank(body.phone) },
      }),
    updatePersonnelAgent: (id: string, body: AgentEdit) =>
      api.request<PersonnelAgent>(`${P}/agents/${enc(id)}`, { method: "PATCH", body }),
    /** Opening a file is written to the audit log (`personnel.file.view`). */
    agentFile: (id: string, signal?: AbortSignal) => api.request<AgentFile>(`${P}/agents/${enc(id)}`, { signal }),
    addPersonnelEvent: (agentId: string, body: EventInput) =>
      api.request<PersonnelEvent>(`${P}/agents/${enc(agentId)}/events`, {
        method: "POST",
        body: { ...body, title: blank(body.title), reference: blank(body.reference), note: blank(body.note) },
      }),
    cancelPersonnelEvent: (id: string, reason: string) =>
      api.request<PersonnelEvent>(`${P}/events/${enc(id)}/cancel`, { method: "POST", body: { reason: reason.trim() } }),
    absences: (f: AbsenceFilters, signal?: AbortSignal) =>
      api.request<Absences>(`${P}/absences`, {
        query: {
          start: f.start,
          end: f.end,
          gouvernorat: f.gouvernorat ?? undefined,
          unit_id: f.unit_id || undefined,
          kind: f.kind || undefined,
        },
        signal,
      }),
    createAbsence: (body: AbsenceInput) =>
      api.request<Absence>(`${P}/absences`, {
        method: "POST",
        body: { ...body, reference: blank(body.reference), note: blank(body.note) },
      }),
    updateAbsence: (id: string, body: AbsenceInput) =>
      api.request<Absence>(`${P}/absences/${enc(id)}`, {
        method: "PATCH",
        body: { ...body, reference: blank(body.reference), note: blank(body.note) },
      }),
    cancelAbsence: (id: string, reason: string) =>
      api.request<Absence>(`${P}/absences/${enc(id)}/cancel`, { method: "POST", body: { reason: reason.trim() } }),
    strength: (on: string, gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<Strength>(`${P}/strength`, { query: { on, gouvernorat: gouvernorat ?? undefined }, signal }),
  };
}

/** Local calendar date as YYYY-MM-DD. */
export function isoDay(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** First and last day of the month of `day` (YYYY-MM-DD). */
export function monthRange(day: string): { start: string; end: string } {
  const [y = 1970, m = 1] = day.split("-").map(Number);
  return { start: isoDay(new Date(y, m - 1, 1)), end: isoDay(new Date(y, m, 0)) };
}
