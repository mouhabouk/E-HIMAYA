import type { ApiClient } from "./api";

/**
 * Watch towers (L5b, docs/phase-l/design-l5.md §3.2, docs/sensor-gateway.md): a fixed camera of the Office on a tower,
 * its field of view on the map, and the fire or smoke its edge computer confirms in 3 of 5 frames. An event becomes a
 * suggestion in the alert centre, never an automatic report.
 */

export type TowerLabel = "fire" | "smoke";

export interface Tower {
  /** The camera's stream id: the stream wall shows the same camera. */
  id: string;
  code: string;
  label: string;
  gouvernorat_code: number;
  lat: number;
  lon: number;
  /** Degrees clockwise from north, the opening of the view, and how far it sees. */
  bearing_deg: number;
  fov_deg: number;
  range_m: number;
  simulated: boolean;
  stream_status: string;
  last_event: { at: string; label: TowerLabel; confidence: number } | null;
  /** Closed GeoJSON ring of [lon, lat]. */
  field_of_view: [number, number][];
  created_by_name: string | null;
  updated_at: string;
}

export interface TowerPage {
  items: Tower[];
  can_manage: boolean;
}

export interface TowerUpdate {
  label: string;
  lat: number;
  lon: number;
  bearing_deg: number;
  fov_deg: number;
  range_m: number;
}

export interface TowerIn extends TowerUpdate {
  code: string;
  gouvernorat_code: number | null;
  simulated: boolean;
}

/** The new tower with the edge key and the camera's publish token, shown this once. */
export interface TowerCreated {
  tower: Tower;
  edge_key: string;
  publish_token: string;
  publish_url_rtsp: string;
  publish_url_rtmp: string;
}

export interface TowerKey {
  tower: Tower;
  edge_key: string;
}

export interface TowerEvents {
  tower_id: string;
  items: {
    at: string;
    label: TowerLabel;
    confidence: number;
    hits: number;
    frames: number;
    model: string | null;
    media_id: string | null;
    suggestion_id: string | null;
  }[];
}

const T = "/api/v1/staff/towers";
const enc = encodeURIComponent;

export const towerKeys = {
  all: ["towers"] as const,
  events: (id: string, hours: number) => ["towers", id, "events", hours] as const,
};

/** A fire or smoke seen in the last hour keeps the tower at the top of the list and in red on the map. */
export const RECENT_MS = 3_600_000;

export function recentEvent(tower: Tower, now: number): TowerLabel | null {
  const e = tower.last_event;
  return e && now - Date.parse(e.at) < RECENT_MS ? e.label : null;
}

const COMPASS = ["n", "ne", "e", "se", "s", "sw", "w", "nw"] as const;

/** The compass word of a bearing (north, north-east…), so the number is never read alone. */
export function compassOf(bearing: number): (typeof COMPASS)[number] {
  return COMPASS[Math.round((((bearing % 360) + 360) % 360) / 45) % 8] ?? "n";
}

export function towersApi(api: ApiClient) {
  return {
    towers: (signal?: AbortSignal) => api.request<TowerPage>(T, { signal }),
    createTower: (body: TowerIn) => api.request<TowerCreated>(T, { method: "POST", body }),
    updateTower: (id: string, body: TowerUpdate) => api.request<Tower>(`${T}/${enc(id)}`, { method: "PUT", body }),
    rotateTowerKey: (id: string) => api.request<TowerKey>(`${T}/${enc(id)}/key`, { method: "POST" }),
    towerEvents: (id: string, hours: number, signal?: AbortSignal) =>
      api.request<TowerEvents>(`${T}/${enc(id)}/events`, { query: { hours }, signal }),
  };
}
