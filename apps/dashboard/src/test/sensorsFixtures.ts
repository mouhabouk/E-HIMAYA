import { vi } from "vitest";
import type { Sensor, SensorKey, SensorReadings, sensorsApi } from "../lib/sensors";

/** Sensors of the local network (L5b) [SIM]: one in alarm, one silent, one normal. */
export const SENSOR: Sensor = {
  id: "s-1",
  code: "SFX-RAIN-01",
  name: "مقياس مطر وادي الشعبوني [SIM]",
  kind: "rain_1h",
  unit: "mm",
  gouvernorat_code: 61,
  lat: 34.74,
  lon: 10.76,
  provider: "المعهد الوطني للرصد الجوي",
  watch_threshold: 20,
  alarm_threshold: 40,
  silent_after_min: 30,
  enabled: true,
  simulated: true,
  last_value: 46.5,
  last_at: "2026-10-28T20:55:00Z",
  state: "alarm",
  level_since: "2026-10-28T20:55:00Z",
  created_by_name: "Salma Ben Ali",
  updated_at: "2026-10-28T20:55:00Z",
};

export const SENSORS: Sensor[] = [
  { ...SENSOR, id: "s-3", code: "SFX-TEMP-01", name: "حرارة صفاقس المدينة [SIM]", kind: "temperature", unit: "°C", watch_threshold: 40, alarm_threshold: 45, last_value: 24, state: "normal", level_since: null },
  SENSOR,
  { ...SENSOR, id: "s-2", code: "SFX-WADI-01", name: "منسوب وادي الشعبوني [SIM]", kind: "water_level", unit: "m", watch_threshold: 2, alarm_threshold: 3.5, last_value: 0.8, last_at: "2026-10-28T18:00:00Z", state: "silent", level_since: null },
];

export const SENSOR_KEY: SensorKey = { sensor: SENSOR, key: "ab".repeat(32) };

export const READINGS: SensorReadings = {
  sensor_id: "s-1",
  unit: "mm",
  watch_threshold: 20,
  alarm_threshold: 40,
  items: [
    { at: "2026-10-28T20:45:00Z", value: 12 },
    { at: "2026-10-28T20:50:00Z", value: 27.5 },
    { at: "2026-10-28T20:55:00Z", value: 46.5 },
  ],
};

export function fakeSensorsApi(): ReturnType<typeof sensorsApi> {
  return {
    sensors: vi.fn(() => Promise.resolve({ items: SENSORS, can_manage: true })),
    createSensor: vi.fn(() => Promise.resolve(SENSOR_KEY)),
    updateSensor: vi.fn(() => Promise.resolve(SENSOR)),
    rotateSensorKey: vi.fn(() => Promise.resolve({ ...SENSOR_KEY, key: "cd".repeat(32) })),
    sensorReadings: vi.fn(() => Promise.resolve(READINGS)),
  };
}
