import { vi } from "vitest";
import type { Drone, DroneAlert, DroneCreated, DroneTrack, dronesApi, Telemetry, Zone } from "../lib/drones";

/** Drones (L5b) [SIM]: one flying with two open alerts, one on the ground; a work area and a no-fly zone. */
const at = (minutesAgo: number) => new Date(Date.now() - minutesAgo * 60_000).toISOString();

const LAST: Telemetry = {
  at: at(0.2),
  lat: 36.885,
  lon: 8.7,
  alt_m: 120,
  heading_deg: 90,
  sensor_az_deg: 0,
  sensor_hfov_deg: 60,
  battery_pct: 24,
  mode: "SIM",
};

export const DRONE: Drone = {
  id: "d-1",
  label: "درون الحماية 1 [SIM]",
  gouvernorat_code: 32,
  stream_status: "live",
  last: LAST,
  camera_view: [
    [8.7, 36.885],
    [8.703, 36.884],
    [8.704, 36.886],
    [8.7, 36.885],
  ],
  open_alerts: 2,
};

export const DRONES: Drone[] = [
  DRONE,
  {
    ...DRONE,
    id: "d-2",
    label: "درون الحماية 2 [SIM]",
    stream_status: "ended",
    last: null,
    camera_view: null,
    open_alerts: 0,
  },
];

export const DRONE_CREATED: DroneCreated = {
  drone: { ...DRONE, id: "d-3", label: "درون جديد [SIM]", last: null, camera_view: null, open_alerts: 0 },
  publish_token: "drone-publish-token-shown-once",
  publish_url_rtsp: "rtsp://10.0.0.5:8554/live/d-3",
  publish_url_rtmp: "rtmp://10.0.0.5:1935/live/d-3",
};

export const DRONE_ALERTS: DroneAlert[] = [
  {
    id: 2,
    drone_id: "d-1",
    drone_label: DRONE.label,
    at: at(0.3),
    kind: "near_no_fly",
    zone_name: "منطقة محظورة [SIM]",
    detail: { lat: 36.885, lon: 8.7, distance_m: 1668 },
    acknowledged_by_name: null,
    acknowledged_at: null,
  },
  {
    id: 1,
    drone_id: "d-1",
    drone_label: DRONE.label,
    at: at(0.4),
    kind: "low_battery",
    zone_name: null,
    detail: { lat: 36.885, lon: 8.7, battery_pct: 24 },
    acknowledged_by_name: null,
    acknowledged_at: null,
  },
  {
    id: 0,
    drone_id: "d-1",
    drone_label: DRONE.label,
    at: at(30),
    kind: "left_work_area",
    zone_name: null,
    detail: {},
    acknowledged_by_name: "Salma Ben Ali",
    acknowledged_at: at(29),
  },
];

export const ZONES: Zone[] = [
  {
    id: "z-1",
    kind: "work",
    name: "غابة عين دراهم [SIM]",
    gouvernorat_code: 32,
    ring: [
      [8.64, 36.73],
      [8.74, 36.73],
      [8.74, 36.83],
      [8.64, 36.83],
      [8.64, 36.73],
    ],
    margin_m: 500,
    active: true,
    created_by_name: "Salma Ben Ali",
    updated_at: "2026-10-28T20:00:00Z",
  },
  {
    id: "z-2",
    kind: "no_fly",
    name: "منطقة محظورة [SIM]",
    gouvernorat_code: 32,
    ring: [
      [8.69, 36.9],
      [8.71, 36.9],
      [8.71, 36.92],
      [8.69, 36.92],
      [8.69, 36.9],
    ],
    margin_m: 2000,
    active: true,
    created_by_name: "Salma Ben Ali",
    updated_at: "2026-10-28T20:00:00Z",
  },
];

export const TRACK: DroneTrack = {
  drone_id: "d-1",
  items: [
    { ...LAST, at: at(1), lat: 36.78, lon: 8.69 },
    { ...LAST, at: at(0.5), lat: 36.83, lon: 8.695 },
    LAST,
  ],
};

export function fakeDronesApi(): ReturnType<typeof dronesApi> {
  return {
    drones: vi.fn(() => Promise.resolve({ items: DRONES, can_register: true })),
    registerDrone: vi.fn(() => Promise.resolve(DRONE_CREATED)),
    droneTrack: vi.fn(() => Promise.resolve(TRACK)),
    droneAlerts: vi.fn(() => Promise.resolve(DRONE_ALERTS)),
    acknowledgeDroneAlert: vi.fn(() => Promise.resolve(undefined)),
    droneZones: vi.fn(() => Promise.resolve(ZONES)),
    createZone: vi.fn(() => Promise.resolve(ZONES[0] as Zone)),
    updateZone: vi.fn(() => Promise.resolve(ZONES[1] as Zone)),
  };
}
