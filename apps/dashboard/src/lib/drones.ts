import type { ApiClient } from "./api";

/**
 * Drones as read-only sources (L5b, docs/phase-l/design-l5.md §3.3, docs/sensor-gateway.md §8): the drone's video
 * through MediaMTX, its position and camera read from the KLV of its stream (MISB ST 0601) or a read-only bridge, the
 * work areas and no-fly zones the room draws, and the alerts they raise. Nothing is ever sent to a drone: the pilot
 * alone flies it.
 */

export type DroneAlertKind = "left_work_area" | "near_no_fly" | "in_no_fly" | "low_battery";
export type ZoneKind = "work" | "no_fly";

export interface Telemetry {
  at: string;
  lat: number;
  lon: number;
  alt_m: number | null;
  heading_deg: number | null;
  sensor_az_deg: number | null;
  sensor_hfov_deg: number | null;
  battery_pct: number | null;
  mode: string | null;
}

export interface Drone {
  /** The drone's stream id: the stream wall shows the same video. */
  id: string;
  label: string;
  gouvernorat_code: number | null;
  stream_status: string;
  last: Telemetry | null;
  /** The camera's view on the map (closed ring of [lon, lat]) when the source gives its direction and opening. */
  camera_view: [number, number][] | null;
  open_alerts: number;
}

export interface DronePage {
  items: Drone[];
  can_register: boolean;
}

/** The new drone and its publish token, shown this once. */
export interface DroneCreated {
  drone: Drone;
  publish_token: string;
  publish_url_rtsp: string;
  publish_url_rtmp: string;
}

export interface DroneTrack {
  drone_id: string;
  items: Telemetry[];
}

export interface Zone {
  id: string;
  kind: ZoneKind;
  name: string;
  gouvernorat_code: number;
  /** Closed GeoJSON ring of [lon, lat]. */
  ring: [number, number][];
  margin_m: number;
  active: boolean;
  created_by_name: string | null;
  updated_at: string;
}

export interface ZoneIn {
  kind: ZoneKind;
  name: string;
  ring: [number, number][];
  margin_m: number;
  gouvernorat_code: number | null;
}

export interface ZoneUpdate {
  name: string;
  ring: [number, number][];
  margin_m: number;
  active: boolean;
}

export interface DroneAlert {
  id: number;
  drone_id: string;
  drone_label: string;
  at: string;
  kind: DroneAlertKind;
  zone_name: string | null;
  detail: Record<string, number | string | null>;
  acknowledged_by_name: string | null;
  acknowledged_at: string | null;
}

const D = "/api/v1/staff/drones";
const enc = encodeURIComponent;

export const droneKeys = {
  all: ["drones"] as const,
  list: ["drones", "list"] as const,
  zones: ["drones", "zones"] as const,
  alerts: ["drones", "alerts"] as const,
  track: (id: string, minutes: number) => ["drones", "track", id, minutes] as const,
};

/** A position older than this is shown as "last seen", and the drone is no longer drawn as flying. */
export const FRESH_MS = 120_000;
/** How much of the path is drawn on the map. */
export const TRACK_MINUTES = 30;
/** The API's limit on a zone (101 positions once closed). */
export const MAX_ZONE_VERTICES = 100;

export function isFresh(drone: Drone, now: number): boolean {
  return drone.last !== null && now - Date.parse(drone.last.at) < FRESH_MS;
}

export function dronesApi(api: ApiClient) {
  return {
    drones: (signal?: AbortSignal) => api.request<DronePage>(D, { signal }),
    registerDrone: (body: { label: string; gouvernorat_code: number | null }) =>
      api.request<DroneCreated>(D, { method: "POST", body }),
    droneTrack: (id: string, minutes: number, signal?: AbortSignal) =>
      api.request<DroneTrack>(`${D}/${enc(id)}/track`, { query: { minutes }, signal }),
    droneAlerts: (signal?: AbortSignal) => api.request<DroneAlert[]>(`${D}/alerts`, { signal }),
    acknowledgeDroneAlert: (id: number) => api.request<undefined>(`${D}/alerts/${id}/ack`, { method: "POST" }),
    droneZones: (signal?: AbortSignal) => api.request<Zone[]>(`${D}/zones`, { signal }),
    createZone: (body: ZoneIn) => api.request<Zone>(`${D}/zones`, { method: "POST", body }),
    updateZone: (id: string, body: ZoneUpdate) =>
      api.request<Zone>(`${D}/zones/${enc(id)}`, { method: "PUT", body }),
  };
}
