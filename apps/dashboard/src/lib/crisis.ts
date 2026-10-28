import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";
import type { ApiClient } from "./api";

/** Disaster and crisis axes (phase L3, docs/phase-l/design-l3.md). */

export const AXIS_KINDS = ["flood", "forest_fire", "storm", "earthquake", "technological", "health", "other"] as const;
export type AxisKind = (typeof AXIS_KINDS)[number];
export const AXIS_LEVELS = [1, 2, 3, 4] as const;
export const DIRECTIVE_CATEGORIES = [
  "evacuation",
  "resources",
  "closure",
  "shelter",
  "support",
  "plan",
  "public_information",
  "other",
] as const;
export type DirectiveCategory = (typeof DIRECTIVE_CATEGORIES)[number];
export const EXECUTORS = ["regional", "central", "partner"] as const;
export type Executor = (typeof EXECUTORS)[number];
export type DirectiveStatus = "issued" | "received" | "in_progress" | "done" | "failed";
export const NEXT_STATUS: Readonly<Record<DirectiveStatus, readonly DirectiveStatus[]>> = {
  issued: ["received", "in_progress", "done", "failed"],
  received: ["in_progress", "done", "failed"],
  in_progress: ["done", "failed"],
  done: [],
  failed: [],
};
export type Area = Polygon | MultiPolygon;

/** Level colours (design system tones): 1 watch sky, 2 alert amber, 3 wide intervention orange, 4 disaster red. */
export const LEVEL_TONE: Readonly<Record<number, string>> = { 1: "sky", 2: "amber", 3: "orange", 4: "red" };

export interface Figures {
  incidents: number;
  incidents_open: number;
  deceased: number;
  injured: number;
  injured_serious: number;
  rescued: number;
  trapped: number;
  evacuated: number;
  shelters: number;
  shelter_capacity: number;
  sheltered: number;
  resources: number;
  resources_by_kind: Record<string, number>;
  volunteers: number;
  needs_open: number;
  decisions: number;
  decisions_done: number;
  decisions_failed: number;
  done_share: number | null;
  mean_hours_to_done: number | null;
}

export interface Axis {
  id: string;
  number: string;
  name: string;
  kind: AxisKind;
  scope: "gouvernorat" | "national";
  parent_id: string | null;
  gouvernorat_code: number | null;
  gouvernorat_name: string | null;
  gouvernorats: number[];
  area: Area | null;
  level: number;
  plan: string;
  status: "open" | "closed";
  opened_by_name: string | null;
  opened_at: string;
  closed_by_name: string | null;
  closed_at: string | null;
  closing: (Figures & { hours: number; summary?: string }) | null;
  next_sitrep_at: string | null;
  memory_id: string | null;
  version: number;
  figures: Figures;
  children: Axis[];
  can_manage: boolean;
  can_command: boolean;
  can_issue: boolean;
}

export interface AxisIncident {
  id: string;
  axis_id: string | null;
  category: string;
  severity: number | null;
  status: string;
  gouvernorat_code: number | null;
  lat: number | null;
  lon: number | null;
  opened_at: string;
  title: string | null;
  deceased: number;
  injured: number;
  rescued: number;
  resources: number;
  attached_by_name: string | null;
  attached_at: string | null;
}

export interface Shelter {
  id: string;
  axis_id: string;
  name: string;
  lat: number | null;
  lon: number | null;
  capacity: number;
  occupants: number;
  updated_at: string;
}

export interface Evacuation {
  id: string;
  axis_id: string;
  name: string;
  area: Area | null;
  evacuated: number;
  updated_at: string;
}

export interface Need {
  id: string;
  axis_id: string;
  label: string;
  quantity: number;
  status: "raised" | "met";
  created_by_name: string | null;
  created_at: string;
  met_at: string | null;
}

export interface Directive {
  id: string;
  axis_id: string;
  axis_number: string;
  number: number;
  kind: "recommendation" | "decision";
  category: DirectiveCategory;
  body: string;
  area: Area | null;
  executor: Executor;
  executor_name: string | null;
  due_at: string | null;
  status: DirectiveStatus;
  status_reason: string | null;
  issuer_role: "governor" | "minister";
  issued_by_name: string | null;
  issued_at: string;
  signature: string | null;
  key_id: string | null;
  overridden_by: string | null;
  overdue: boolean;
  done_at: string | null;
  events: { status: string; reason: string | null; by_name: string | null; at: string }[];
  can_update: boolean;
}

export interface Sitrep {
  id: string;
  axis_id: string;
  number: number;
  figures: Partial<Figures> & { level?: number };
  assessment: string;
  status: "draft" | "sent";
  created_at: string;
  sent_by_name: string | null;
  sent_at: string | null;
}

export interface AxisEvent {
  at: string;
  actor_name: string | null;
  kind: string;
  payload: Record<string, unknown>;
}

export interface AxisDetail {
  axis: Axis;
  incidents: AxisIncident[];
  shelters: Shelter[];
  evacuations: Evacuation[];
  needs: Need[];
  directives: Directive[];
  sitreps: Sitrep[];
  timeline: AxisEvent[];
}

export interface DeclarationRequest {
  id: string;
  gouvernorat_code: number;
  gouvernorat_name: string | null;
  name: string;
  kind: AxisKind;
  level: number;
  facts: string;
  incident_ids: string[];
  area: Area | null;
  status: "pending" | "accepted" | "rejected";
  created_by_name: string | null;
  created_at: string;
  decided_by_name: string | null;
  decided_at: string | null;
  decision_reason: string | null;
  axis_id: string | null;
}

export interface GouvernoratState {
  code: number;
  name: string;
  level: number | null;
  axes: number;
  incidents_open: number;
  resources: number;
  weight: number | null;
  deceased: number;
  evacuated: number;
  needs_open: number;
}

export interface CommandOverview {
  role: "governor" | "minister";
  gouvernorat_code: number | null;
  totals: Figures;
  axes: Axis[];
  gouvernorats: GouvernoratState[];
  needs: Need[];
  directives: Directive[];
  sitreps: Sitrep[];
  closed: Axis[];
}

export interface AxisBody {
  name: string;
  kind: AxisKind;
  level: number;
  gouvernorat_code?: number | null;
  area?: Area | null;
  plan?: string;
  incident_ids?: string[];
  national?: boolean;
  gouvernorats?: number[];
}

export interface RequestBody {
  name: string;
  kind: AxisKind;
  level: number;
  facts: string;
  incident_ids?: string[];
  area?: Area | null;
}

export interface DirectiveBody {
  kind: "recommendation" | "decision";
  category: DirectiveCategory;
  body: string;
  executor: Executor;
  executor_name?: string | null;
  due_at?: string | null;
  area?: Area | null;
}

export const crisisKeys = {
  all: ["crisis"] as const,
  axes: (status: "open" | "closed") => ["crisis", "axes", status] as const,
  axis: (id: string) => ["crisis", "axis", id] as const,
  suggestions: (id: string) => ["crisis", "suggestions", id] as const,
  requests: (status: "pending" | "decided") => ["crisis", "requests", status] as const,
  command: ["crisis", "command"] as const,
  boundaries: ["crisis", "boundaries"] as const,
};

const C = "/api/v1/staff/crisis";
const enc = encodeURIComponent;

export function crisisApi(api: ApiClient) {
  const axis = (id: string) => `${C}/axes/${enc(id)}`;
  return {
    crisisAxes: (status: "open" | "closed", signal?: AbortSignal) =>
      api.request<{ items: Axis[] }>(`${C}/axes`, { query: { status }, signal }).then((b) => b.items),
    crisisAxis: (id: string, signal?: AbortSignal) => api.request<AxisDetail>(axis(id), { signal }),
    openAxis: (body: AxisBody) => api.request<Axis>(`${C}/axes`, { method: "POST", body }),
    updateAxis: (id: string, body: { version: number; level?: number; plan?: string; area?: Area; reason?: string }) =>
      api.request<Axis>(axis(id), { method: "PATCH", body }),
    escalateAxis: (id: string, gouvernorats: number[], reason: string) =>
      api.request<Axis>(`${axis(id)}/escalate`, { method: "POST", body: { gouvernorats, reason } }),
    closeAxis: (id: string, summary: string) =>
      api.request<Axis>(`${axis(id)}/close`, { method: "POST", body: { summary } }),
    axisSuggestions: (id: string, signal?: AbortSignal) =>
      api.request<{ items: AxisIncident[] }>(`${axis(id)}/suggestions`, { signal }).then((b) => b.items),
    attachAxisIncident: (id: string, incidentId: string) =>
      api.request<undefined>(`${axis(id)}/incidents`, { method: "POST", body: { incident_id: incidentId } }),
    detachAxisIncident: (id: string, incidentId: string, reason: string) =>
      api.request<undefined>(`${axis(id)}/incidents/${enc(incidentId)}/detach`, { method: "POST", body: { reason } }),
    dismissAxisSuggestion: (id: string, incidentId: string) =>
      api.request<undefined>(`${axis(id)}/suggestions/${enc(incidentId)}/dismiss`, { method: "POST", body: {} }),
    addShelter: (id: string, body: { name: string; capacity: number; occupants: number }) =>
      api.request<Shelter>(`${axis(id)}/shelters`, { method: "POST", body }),
    updateShelter: (id: string, shelterId: string, body: { capacity?: number; occupants?: number }) =>
      api.request<Shelter>(`${axis(id)}/shelters/${enc(shelterId)}`, { method: "PATCH", body }),
    addEvacuation: (id: string, body: { name: string; evacuated: number; area?: Area | null }) =>
      api.request<Evacuation>(`${axis(id)}/evacuations`, { method: "POST", body }),
    updateEvacuation: (id: string, evacuationId: string, evacuated: number) =>
      api.request<Evacuation>(`${axis(id)}/evacuations/${enc(evacuationId)}`, { method: "PATCH", body: { evacuated } }),
    raiseNeed: (id: string, body: { label: string; quantity: number }) =>
      api.request<Need>(`${axis(id)}/needs`, { method: "POST", body }),
    needMet: (id: string, needId: string) =>
      api.request<Need>(`${axis(id)}/needs/${enc(needId)}/met`, { method: "POST", body: {} }),
    issueAxisDirective: (id: string, body: DirectiveBody) =>
      api.request<Directive>(`${axis(id)}/directives`, { method: "POST", body }),
    axisDirectiveStatus: (directiveId: string, status: DirectiveStatus, reason: string) =>
      api.request<Directive>(`${C}/directives/${enc(directiveId)}/status`, { method: "POST", body: { status, reason } }),
    draftSitrep: (id: string) => api.request<Sitrep>(`${axis(id)}/sitreps`, { method: "POST", body: {} }),
    sendSitrep: (sitrepId: string, assessment: string) =>
      api.request<Sitrep>(`${C}/sitreps/${enc(sitrepId)}/send`, { method: "POST", body: { assessment } }),
    declarationRequests: (status: "pending" | "decided", signal?: AbortSignal) =>
      api.request<{ items: DeclarationRequest[] }>(`${C}/requests`, { query: { status }, signal }).then((b) => b.items),
    requestDeclaration: (body: RequestBody) =>
      api.request<DeclarationRequest>(`${C}/requests`, { method: "POST", body }),
    decideRequest: (requestId: string, accept: boolean, reason: string) =>
      api.request<DeclarationRequest>(`${C}/requests/${enc(requestId)}/decide`, {
        method: "POST",
        body: { accept, reason },
      }),
    crisisCommand: (signal?: AbortSignal) => api.request<CommandOverview>(`${C}/command`, { signal }),
    crisisBoundaries: (signal?: AbortSignal) => api.request<FeatureCollection>(`${C}/boundaries`, { signal }),
  };
}

/** Every axis of a family (a national root and its sub-axes) in one list. */
export function flatten(axes: readonly Axis[]): Axis[] {
  return axes.flatMap((a) => [a, ...a.children]);
}

/** Bounding box [w, s, e, n] of polygons, or null. */
export function areaBounds(areas: readonly (Area | null | undefined)[]): [number, number, number, number] | null {
  let w = Infinity;
  let s = Infinity;
  let e = -Infinity;
  let n = -Infinity;
  const visit = (ring: number[][]) => {
    for (const [x = 0, y = 0] of ring) {
      w = Math.min(w, x);
      e = Math.max(e, x);
      s = Math.min(s, y);
      n = Math.max(n, y);
    }
  };
  for (const area of areas) {
    if (!area) continue;
    const polygons = area.type === "Polygon" ? [area.coordinates] : area.coordinates;
    for (const polygon of polygons) for (const ring of polygon) visit(ring);
  }
  return Number.isFinite(w) ? [w, s, e, n] : null;
}

/** Hours until a time (negative when past). */
export function hoursUntil(iso: string | null, now = Date.now()): number | null {
  return iso ? (new Date(iso).getTime() - now) / 3_600_000 : null;
}
