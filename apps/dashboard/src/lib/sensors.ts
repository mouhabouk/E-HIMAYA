import type { ApiClient } from "./api";

/**
 * Sensors of the local network (L5b, docs/phase-l/design-l5.md §3.0 and §3.1, docs/sensor-gateway.md): rain gauges,
 * water levels and temperatures whose signed readings reach the API through the gateway beside MediaMTX. A crossed
 * threshold becomes a suggestion in the alert centre; nothing reaches a citizen from here.
 */

export const SENSOR_KINDS = ["rain_1h", "water_level", "temperature"] as const;
export type SensorKind = (typeof SENSOR_KINDS)[number];
export type SensorState = "normal" | "watch" | "alarm" | "silent" | "disabled";

/** Plausible range of a reading and the step of the threshold counters, by kind (the API checks the same range). */
export const KIND_RANGE: Record<SensorKind, { min: number; max: number; step: number }> = {
  rain_1h: { min: 0, max: 300, step: 1 },
  water_level: { min: -10, max: 100, step: 0.1 },
  temperature: { min: -30, max: 60, step: 1 },
};

export interface Sensor {
  id: string;
  code: string;
  name: string;
  kind: SensorKind;
  unit: string;
  gouvernorat_code: number;
  lat: number;
  lon: number;
  provider: string;
  watch_threshold: number;
  alarm_threshold: number;
  silent_after_min: number;
  enabled: boolean;
  simulated: boolean;
  last_value: number | null;
  last_at: string | null;
  state: SensorState;
  level_since: string | null;
  created_by_name: string | null;
  updated_at: string;
}

export interface SensorPage {
  items: Sensor[];
  can_manage: boolean;
}

export interface SensorIn {
  code: string;
  name: string;
  kind: SensorKind;
  gouvernorat_code: number | null;
  lat: number;
  lon: number;
  provider: string;
  watch_threshold: number;
  alarm_threshold: number;
  silent_after_min: number;
  simulated: boolean;
}

export interface SensorUpdate {
  name: string;
  lat: number;
  lon: number;
  provider: string;
  watch_threshold: number;
  alarm_threshold: number;
  silent_after_min: number;
  enabled: boolean;
}

/** The sensor and its signing key, shown this once. */
export interface SensorKey {
  sensor: Sensor;
  key: string;
}

export interface SensorReadings {
  sensor_id: string;
  unit: string;
  watch_threshold: number;
  alarm_threshold: number;
  items: { at: string; value: number }[];
}

const S = "/api/v1/staff/sensors";
const enc = encodeURIComponent;

export const sensorKeys = {
  all: ["sensors"] as const,
  readings: (id: string, hours: number) => ["sensors", id, "readings", hours] as const,
};

/** Order of the list: what needs eyes first. */
export const STATE_ORDER: Record<SensorState, number> = { alarm: 0, watch: 1, silent: 2, normal: 3, disabled: 4 };

export function sensorsApi(api: ApiClient) {
  return {
    sensors: (signal?: AbortSignal) => api.request<SensorPage>(S, { signal }),
    createSensor: (body: SensorIn) => api.request<SensorKey>(S, { method: "POST", body }),
    updateSensor: (id: string, body: SensorUpdate) =>
      api.request<Sensor>(`${S}/${enc(id)}`, { method: "PUT", body }),
    rotateSensorKey: (id: string) => api.request<SensorKey>(`${S}/${enc(id)}/key`, { method: "POST" }),
    sensorReadings: (id: string, hours: number, signal?: AbortSignal) =>
      api.request<SensorReadings>(`${S}/${enc(id)}/readings`, { query: { hours }, signal }),
  };
}
