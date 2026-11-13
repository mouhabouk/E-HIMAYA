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
  /** OS8-3: a field check asked from the review reminder (cleared by a confirm or an archive). */
  check_requested_at?: string | null;
  check_requested_by_name?: string | null;
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
  id: number;
  at: string;
  by_name: string | null;
  category: string;
  address: string;
  incident_id: string | null;
  reason: string;
  /** OS8-2: how the owner was told (none when the account has neither a phone for pushes nor a number). */
  notified_via?: "push" | "sms" | null;
  disputed_at?: string | null;
  dispute_note?: string | null;
}

/** OS8-3: the review reminder. days: past the review date (1 or more), or minus the days left (0 or less). */
export type AwReminderLevel = "soon" | "room" | "manager" | "central";

export interface AwReminderItem {
  marker: AwMarker;
  days: number;
  level: AwReminderLevel;
}

export interface AwReminders {
  late: AwReminderItem[];
  soon: AwReminderItem[];
  disputes: number;
  settings: { hour: number; ahead_days: number; manager_days: number; central_days: number };
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
  reminders: ["address-warnings", "reminders"] as const,
};

/** OS8-1: the groups of the map layer's filter (personal marks never appear on the layer). */
export const AW_GROUPS: Record<"haz" | "bld" | "ppl", readonly string[]> = {
  haz: ["gas", "chem", "fuel", "batt"],
  bld: ["coll", "acc"],
  ppl: ["occ", "dog"],
};

/** OS8-1: 24×24 map icons of the categories (the map draws its points itself). */
export const AW_MAP_ICONS: Record<string, string> = {
  flame: "M12 2c1 4 6 6 6 12a6 6 0 0 1-12 0c0-3 2-5 3-6 0 2 1 3 2 3 0-4-1-6 1-9z",
  flask: "M9 2h6v2h-1v5.2l5.6 9.3A2 2 0 0 1 17.9 21H6.1a2 2 0 0 1-1.7-2.5L10 9.2V4H9zm1.2 9.5L7.6 16h8.8l-2.6-4.5z",
  drop: "M12 2s7 7.5 7 12a7 7 0 0 1-14 0c0-4.5 7-12 7-12z",
  crack: "M4 21V6l8-4 8 4v15h-6.5l1.8-3.5-2.8-3 2-3.5-2.5-3-1.8 3 2 3.5-2.7 3 1.6 3.5z",
  paw: "M12 12c3 0 6 3.5 6 6.2 0 1.8-1.4 2.8-3 2.8-1.2 0-2-.6-3-.6s-1.8.6-3 .6c-1.6 0-3-1-3-2.8C6 15.5 9 12 12 12zM5.5 7.5a2 2.5 0 1 1 0 5 2 2.5 0 0 1 0-5zm13 0a2 2.5 0 1 1 0 5 2 2.5 0 0 1 0-5zM9 2.5a2 2.5 0 1 1 0 5 2 2.5 0 0 1 0-5zm6 0a2 2.5 0 1 1 0 5 2 2.5 0 0 1 0-5z",
  road: "M4 3h3L5 21H2zm13 0h3l2 18h-3zM11 4h2v3h-2zm0 6h2v4h-2zm0 7h2v4h-2z",
  bolt: "M13 2 4 14h6l-1 8 9-12h-6z",
  people:
    "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm0 2c-4 0-7 2-7 5v2h14v-2c0-3-3-5-7-5zm8-2a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm1 2c2.5.3 4 1.8 4 4v3h-4v-2c0-2-.8-3.6-2-4.6z",
};
export const AW_MAP_WARNING = "M12 2 1 21h22L12 2zm-1 7h2v6h-2zm0 8h2v2h-2z";

/** OS8-1: the map colours of the category tones (white icon on them, contrast 4.5:1 or more). */
export const AW_MAP_COLOURS: Record<string, string> = {
  amber: "#9A5B00",
  orange: "#C25E00",
  navy: "#1F3FA0",
  slate: "#5B6478",
  purple: "#7838A0",
  green: "#188038",
  teal: "#00806A",
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
    awReminders: (signal?: AbortSignal) => api.request<AwReminders>(`${A}/reminders`, { signal }),
    awRequestCheck: (id: string) => api.request<AwMarker>(`${A}/markers/${enc(id)}/check`, { method: "POST" }),
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
