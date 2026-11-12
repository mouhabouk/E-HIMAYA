/**
 * Address warnings (OS8, docs/phase-os8/design-os8.md): types and calls of `/api/v1/staff/address-warnings`.
 * A mark on a dangerous address shows for every incident inside its category's circle; personal marks come from
 * their owner's citizen app only and never carry a name (the name is shown on request, with a reason, and kept).
 */
import type { ApiClient } from "./api";
import type { IconName, Tone } from "../components/Icon";

export interface AwPoint {
  lat: number;
  lon: number;
}

export interface AwHours {
  start: number;
  end: number;
}

export interface AwCategory {
  key: string;
  name: string;
  icon: string;
  colour: string;
  personal: boolean;
  radius_m: number;
  review_months: number;
  team: boolean;
  critical_with: string[];
  examples: string[];
  updated_by_name: string | null;
}

export type AwStatus = "pending" | "active" | "archived" | "rejected" | "withdrawn";
export type AwSource = "room" | "team" | "org" | "municipality" | "report" | "citizen";

export interface AwMarker {
  id: string;
  category: string;
  gouvernorat_code: number | null;
  location: AwPoint;
  address: string;
  description: string;
  source: AwSource;
  source_ref: string | null;
  org_id: string | null;
  incident_id: string | null;
  team_visible: boolean;
  hours: AwHours | null;
  review_on: string;
  review_due: boolean;
  status: AwStatus;
  created_at: string;
  created_by_name: string | null;
  decided_at: string | null;
  decided_by_name: string | null;
  decision_reason: string | null;
  confirmed_at: string | null;
}

export interface AwPage {
  items: AwMarker[];
  counts: { active: number; pending: number; review_due: number; personal: number };
}

export interface AwWarning {
  marker_id: string;
  category: string;
  personal: boolean;
  location: AwPoint;
  address: string;
  description: string;
  source: AwSource;
  source_ref: string | null;
  team_visible: boolean;
  distance_m: number;
  critical: boolean;
  off_hours: boolean;
  hours: AwHours | null;
  review_on: string;
  room_ack_at: string | null;
  room_ack_by: string | null;
  team_ack_at: string | null;
  team_ack_by: string | null;
  revealed: boolean;
}

export interface AwIncident {
  incident_id: string;
  incident_kind: string;
  location: AwPoint | null;
  items: AwWarning[];
  unread: number;
}

export interface AwRevealRow {
  at: string;
  by_name: string | null;
  category: string;
  address: string;
  incident_id: string | null;
  reason: string;
}

export interface AwMarkerBody {
  category: string;
  location: AwPoint;
  address: string;
  description: string;
  source: Exclude<AwSource, "team" | "citizen">;
  source_ref?: string | null;
  team_visible: boolean;
  hours?: AwHours | null;
}

export type AwFilter = "pending" | "active" | "review_due" | "archived" | "rejected" | "";

/** The kinds of incident a category can be critical with (the room's report categories). */
export const AW_INCIDENT_KINDS = [
  "fire",
  "chemical_leak",
  "landslide",
  "flood",
  "traffic_accident",
  "drowning",
  "medical",
  "sos",
  "other",
] as const;

const ICONS: Record<string, IconName> = {
  flame: "propaneTank",
  flask: "science",
  drop: "localGasStation",
  bolt: "bolt",
  crack: "domainDisabled",
  road: "removeRoad",
  paw: "pets",
  people: "groups",
  wheel: "accessible",
  o2: "pulmonology",
  ear: "hearingDisabled",
};
const TONES: Record<string, Tone> = {
  amber: "amber",
  orange: "orange",
  navy: "navy",
  slate: "slate",
  purple: "purple",
  green: "green",
  teal: "teal",
};

export function awIcon(category: AwCategory | undefined): IconName {
  return (category && ICONS[category.icon]) || "warning";
}

export function awTone(category: AwCategory | undefined): Tone {
  return (category && TONES[category.colour]) || "amber";
}

/** «07:30» from minutes of the day. */
export function hhmm(minutes: number): string {
  const m = ((minutes % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

export const awKeys = {
  all: ["address-warnings"] as const,
  categories: ["address-warnings", "categories"] as const,
  markers: (filter: AwFilter) => ["address-warnings", "markers", filter] as const,
  incident: (id: string) => ["address-warnings", "incident", id] as const,
  reveals: ["address-warnings", "reveals"] as const,
};

const A = "/api/v1/staff/address-warnings";
const enc = encodeURIComponent;

export function addressWarningsApi(api: ApiClient) {
  return {
    awCategories: (signal?: AbortSignal) => api.request<AwCategory[]>(`${A}/categories`, { signal }),
    awSaveCategory: (
      key: string,
      body: { radius_m: number; review_months: number; team: boolean; critical_with: string[] },
    ) => api.request<AwCategory>(`${A}/categories/${enc(key)}`, { method: "PUT", body }),
    awMarkers: (filter: AwFilter, signal?: AbortSignal) =>
      api.request<AwPage>(`${A}/markers`, { query: filter ? { status: filter } : {}, signal }),
    awCreate: (body: AwMarkerBody) => api.request<AwMarker>(`${A}/markers`, { method: "POST", body }),
    awDecide: (id: string, action: "approve" | "reject" | "archive" | "confirm", reason?: string) =>
      api.request<AwMarker>(`${A}/markers/${enc(id)}/${action}`, {
        method: "POST",
        body: reason ? { reason } : {},
      }),
    awImportOrgs: () => api.request<{ created: number }>(`${A}/import-orgs`, { method: "POST" }),
    awReveals: (signal?: AbortSignal) => api.request<AwRevealRow[]>(`${A}/reveals`, { signal }),
    awIncident: (incidentId: string, signal?: AbortSignal) =>
      api.request<AwIncident>(`${A}/incidents/${enc(incidentId)}`, { signal }),
    awAck: (incidentId: string, markerIds: string[] = []) =>
      api.request<AwIncident>(`${A}/incidents/${enc(incidentId)}/ack`, {
        method: "POST",
        body: { marker_ids: markerIds },
      }),
    awReveal: (incidentId: string, markerId: string, reason: string) =>
      api.request<{ name: string | null; phone: string | null }>(
        `${A}/incidents/${enc(incidentId)}/reveal/${enc(markerId)}`,
        { method: "POST", body: { reason } },
      ),
  };
}
