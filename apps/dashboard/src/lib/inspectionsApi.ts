import type { ApiClient } from "./api";
import { saveDownload } from "./layersApi";

/**
 * Phase I2 (docs/phase-i/design-i.md): the periodic inspections. The general inspectorate plans the missions, activates
 * the inspectors' app accounts, reads the reports and decides what each operations room reads of the rooms' reports;
 * the rooms read what is disclosed to them; the system administrator alone deletes and restores.
 */
const S = "/api/v1/staff/inspections";
const R = "/api/v1/staff/inspection-results";
const A = "/api/v1/staff/inspection-admin";
const enc = encodeURIComponent;

/** The kinds of unit a planner picks before typing the unit's name (Yamen 2026-11-11). */
export const UNIT_KINDS = [
  "regional_directorate",
  "brigade",
  "centre",
  "advanced_centre",
  "guard_post",
  "beach",
  "other",
] as const;
export type UnitKind = (typeof UNIT_KINDS)[number];
export type Target = "unit" | "room";
export type RoomKind = "central" | "regional";
export type Kind = "periodic" | "surprise";
export type Answer = "ok" | "note" | "ko";
export type Priority = "high" | "medium" | "low";
export const AUDIENCES = ["none", "regional", "central", "both"] as const;
export type Audience = (typeof AUDIENCES)[number];
export const INSPECTOR_STATES = ["pending", "code_sent", "active", "blocked", "rejected", "closed"] as const;
export type InspectorStatus = (typeof INSPECTOR_STATES)[number];
export type MissionState = "planned" | "live" | "done" | "cancelled";

export interface ProfileConfig {
  axes: { key: string; name: string; weight: number }[];
  items: { key: string; axis: string; text: string; weight: number }[];
  values: { ok: number; note: number; ko: number };
  weights: { items: number; presence: number; exit: number };
  exit: { fast: number; ok: number; fast_value: number; ok_value: number; slow_value: number };
  levels: { name: string; min: number; colour: "green" | "amber" | "orange" | "red" }[];
  sections: string[];
}

export interface Profile {
  id: string;
  name: string;
  version: number;
  config: ProfileConfig;
  created_by_name: string | null;
  created_at: string;
}

export interface RoomDisclosure {
  inspection: boolean;
  verdict: boolean;
  score: boolean;
}

export interface Policy {
  central: RoomDisclosure;
  regional: RoomDisclosure;
  recommendations: { high: Audience; medium: Audience; low: Audience; general: Audience };
  publish_programme: boolean;
  updated_by_name?: string | null;
  updated_at?: string;
}

export interface Inspector {
  id: string;
  kind: "internal" | "external";
  matricule: string;
  name: string;
  organisation: string | null;
  phone: string | null;
  email: string | null;
  via: "sms" | "email";
  status: InspectorStatus;
  expires_on: string | null;
  matched_agent: boolean;
  requested_device: string | null;
  requested_at: string;
  decided_at: string | null;
  decided_by_name: string | null;
  reject_reason: string | null;
  code_expires_at: string | null;
  activated_at: string | null;
  device_model: string | null;
  last_seen_at: string | null;
  lost_at: string | null;
}

export interface SiteInput {
  target: Target;
  unit_kind?: UnitKind | null;
  unit_name?: string | null;
  room?: RoomKind | null;
  gouvernorat_code?: number | null;
  sections: string[];
}

export interface MissionInput {
  on_date: string;
  at_time: string;
  kind: Kind;
  inspector_id: string;
  sites: SiteInput[];
  publish: boolean;
}

export interface Site {
  id: string;
  position: number;
  target: Target;
  unit_kind: UnitKind | null;
  unit_name: string | null;
  unit_id: string | null;
  room: RoomKind | null;
  name: string;
  gouvernorat_code: number | null;
  sections: string[];
  inspection_id: string | null;
  inspection_status: "in_progress" | "submitted" | null;
}

export interface Mission {
  id: string;
  ref: string;
  on_date: string;
  at_time: string;
  kind: Kind;
  inspector_id: string;
  inspector_name: string;
  status: MissionState;
  cancel_reason: string | null;
  published: boolean;
  sites: Site[];
  created_by_name: string | null;
  created_at: string;
}

export interface Recommendation {
  id: string;
  kind: "detailed" | "general";
  item_key: string | null;
  text: string;
  priority: Priority | null;
  audience: Audience;
}

export interface RecordRow {
  id: string;
  mission_ref: string;
  kind: Kind;
  target: Target;
  unit_kind: UnitKind | null;
  room: RoomKind | null;
  place: string;
  gouvernorat_code: number | null;
  inspector_name: string;
  status: "in_progress" | "submitted";
  started_at: string;
  submitted_at: string | null;
  score: number | null;
  verdict: string | null;
  previous_score: number | null;
  receipt: string | null;
}

export interface RecordDetail extends RecordRow {
  answers: Record<string, Answer>;
  present: number | null;
  expected: number | null;
  exit_seconds: number | null;
  summary: string | null;
  head_name: string | null;
  signed_at: string | null;
  profile_name: string;
  profile_version: number;
  disclosure: Partial<Record<RoomKind, RoomDisclosure>>;
  recommendations: Recommendation[];
}

export interface RecordFilters {
  gouvernorat_code?: number | null;
  target?: Target | "";
  kind?: Kind | "";
  unit_kind?: UnitKind | "";
  search?: string;
  from_date?: string;
  to_date?: string;
}

export interface Dashboard {
  month_missions: number;
  month_done: number;
  month_planned: number;
  rooms_without_plan: number;
  average_score: number | null;
  by_month: { month: string; count: number }[];
  levels: Record<string, number>;
}

export interface PlaceStatus {
  target: Target;
  unit_kind: UnitKind | null;
  unit_name: string | null;
  room: RoomKind | null;
  name: string;
  gouvernorat_code: number | null;
  last_inspection_id: string | null;
  last_on: string | null;
  last_score: number | null;
  last_verdict: string | null;
  next_on: string | null;
}

export interface RoomResult {
  id: string;
  room: RoomKind;
  place: string;
  gouvernorat_code: number | null;
  kind: Kind;
  submitted_at: string;
  verdict: string | null;
  score: number | null;
  recommendations: Recommendation[];
}

export interface RoomLive {
  id: string;
  room: RoomKind;
  place: string;
  gouvernorat_code: number | null;
  inspector_name: string;
  started_at: string;
  answered: number;
  items: number;
  score: number | null;
}

export interface RoomUpcoming {
  ref: string;
  room: RoomKind;
  place: string;
  gouvernorat_code: number | null;
  on_date: string;
  kind: Kind;
}

export interface DeleteInput {
  scope: "one" | "period" | "all";
  inspection_id?: string | null;
  from_date?: string | null;
  to_date?: string | null;
  reason: string;
  confirm: string;
}

export interface BinRow {
  id: string;
  place: string;
  submitted_at: string | null;
  deleted_at: string;
  deleted_by_name: string | null;
  delete_reason: string | null;
}

/** The word the system administrator types to confirm a deletion (design-i §8). */
export const CONFIRM_WORD = "حذف";

export const inspectionKeys = {
  all: ["inspections"] as const,
  dashboard: ["inspections", "dashboard"] as const,
  places: (g: number | null) => ["inspections", "places", g] as const,
  missions: (from: string, to: string) => ["inspections", "missions", from, to] as const,
  records: (f: RecordFilters) => ["inspections", "records", f] as const,
  record: (id: string) => ["inspections", "record", id] as const,
  inspectors: (state: string) => ["inspections", "inspectors", state] as const,
  profile: ["inspections", "profile"] as const,
  notes: ["inspections", "notes"] as const,
  policy: ["inspections", "policy"] as const,
  results: ["inspection-results"] as const,
  live: ["inspection-results", "live"] as const,
  upcoming: ["inspection-results", "upcoming"] as const,
  bin: ["inspection-admin", "bin"] as const,
};

export function inspectionsApi(api: ApiClient) {
  return {
    inspectionDashboard: (signal?: AbortSignal) => api.request<Dashboard>(`${S}/dashboard`, { signal }),
    inspectionPlaces: (gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<PlaceStatus[]>(`${S}/places`, { query: { gouvernorat_code: gouvernorat ?? undefined }, signal }),
    inspectionMissions: (from: string, to: string, signal?: AbortSignal) =>
      api.request<Mission[]>(`${S}/missions`, { query: { from_date: from || undefined, to_date: to || undefined }, signal }),
    createInspectionMission: (body: MissionInput) => api.request<Mission>(`${S}/missions`, { method: "POST", body }),
    cancelInspectionMission: (id: string, reason: string) =>
      api.request<Mission>(`${S}/missions/${enc(id)}/cancel`, { method: "POST", body: { reason } }),
    /** The mission order (A4 PDF with its QR code), handed to the browser. */
    downloadMissionOrder: async (mission: Pick<Mission, "id" | "ref">) => {
      const response = await api.requestRaw(`${S}/missions/${enc(mission.id)}/order.pdf`, { accept: "application/pdf" });
      saveDownload({ blob: await response.blob(), filename: `${mission.ref}.pdf` });
    },
    inspectionRecords: (f: RecordFilters, signal?: AbortSignal) =>
      api.request<RecordRow[]>(`${S}/records`, {
        query: {
          gouvernorat_code: f.gouvernorat_code ?? undefined,
          target: f.target || undefined,
          kind: f.kind || undefined,
          unit_kind: f.unit_kind || undefined,
          search: f.search?.trim() || undefined,
          from_date: f.from_date || undefined,
          to_date: f.to_date || undefined,
        },
        signal,
      }),
    inspectionRecord: (id: string, signal?: AbortSignal) => api.request<RecordDetail>(`${S}/records/${enc(id)}`, { signal }),
    setInspectionDisclosure: (id: string, body: { room: RoomKind } & Partial<RoomDisclosure>) =>
      api.request<RecordDetail>(`${S}/records/${enc(id)}/disclosure`, { method: "PUT", body }),
    setRecommendationAudience: (id: string, ids: string[], audience: Audience) =>
      api.request<RecordDetail>(`${S}/records/${enc(id)}/audience`, { method: "PUT", body: { ids, audience } }),
    inspectors: (state: InspectorStatus | "", signal?: AbortSignal) =>
      api.request<Inspector[]>(`${S}/inspectors`, { query: { state: state || undefined }, signal }),
    activateInspector: (id: string, expiresOn: string | null) =>
      api.request<Inspector>(`${S}/inspectors/${enc(id)}/activate`, { method: "POST", body: { expires_on: expiresOn } }),
    rejectInspector: (id: string, reason: string) =>
      api.request<Inspector>(`${S}/inspectors/${enc(id)}/reject`, { method: "POST", body: { reason } }),
    renewInspectorCode: (id: string) => api.request<Inspector>(`${S}/inspectors/${enc(id)}/code`, { method: "POST" }),
    reportInspectorLost: (id: string) => api.request<Inspector>(`${S}/inspectors/${enc(id)}/lost`, { method: "POST" }),
    closeInspector: (id: string) => api.request<Inspector>(`${S}/inspectors/${enc(id)}/close`, { method: "POST" }),
    inspectionProfile: (signal?: AbortSignal) => api.request<Profile>(`${S}/profile`, { signal }),
    saveInspectionProfile: (name: string, config: ProfileConfig) =>
      api.request<Profile>(`${S}/profile`, { method: "PUT", body: { name, config } }),
    orderNotes: (signal?: AbortSignal) => api.request<{ notes: string[] }>(`${S}/order-notes`, { signal }),
    saveOrderNotes: (notes: string[]) => api.request<{ notes: string[] }>(`${S}/order-notes`, { method: "PUT", body: { notes } }),
    inspectionPolicy: (signal?: AbortSignal) => api.request<Policy>(`${S}/policy`, { signal }),
    saveInspectionPolicy: (body: Policy) => {
      const { central, regional, recommendations, publish_programme } = body;
      return api.request<Policy>(`${S}/policy`, {
        method: "PUT",
        body: { central, regional, recommendations, publish_programme },
      });
    },
    applyInspectionPolicy: () => api.request<{ deleted: number }>(`${S}/policy/apply`, { method: "POST" }),
    roomResults: (signal?: AbortSignal) => api.request<RoomResult[]>(R, { signal }),
    roomLive: (signal?: AbortSignal) => api.request<RoomLive[]>(`${R}/live`, { signal }),
    roomUpcoming: (signal?: AbortSignal) => api.request<RoomUpcoming[]>(`${R}/upcoming`, { signal }),
    deleteInspections: (body: DeleteInput) => api.request<{ deleted: number }>(`${A}/delete`, { method: "POST", body }),
    inspectionBin: (signal?: AbortSignal) => api.request<BinRow[]>(`${A}/bin`, { signal }),
    restoreInspection: (id: string) => api.request<undefined>(`${A}/bin/${enc(id)}/restore`, { method: "POST" }),
  };
}

/** A CSV cell: quoted when it holds a separator, a quote or a line break. */
function cell(value: string | number | null | undefined): string {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",;\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** The CSV of a table, with a byte order mark so that a spreadsheet reads the Arabic as UTF-8. */
export function toCsv(head: string[], rows: (string | number | null | undefined)[][]): string {
  return "﻿" + [head, ...rows].map((r) => r.map(cell).join(",")).join("\r\n") + "\r\n";
}

/** Hands a table to the browser as `e-himaya-<name>-<day>.csv`. */
export function exportCsv(name: string, head: string[], rows: (string | number | null | undefined)[][]): void {
  const day = new Date().toISOString().slice(0, 10);
  saveDownload({
    blob: new Blob([toCsv(head, rows)], { type: "text/csv;charset=utf-8" }),
    filename: `e-himaya-${name}-${day}.csv`,
  });
}
