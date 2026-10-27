import { vi } from "vitest";
import type { Beach, BeachDetail, CoastalAlert, CoastalOverview, CoastalSettings } from "../lib/coastal";
import type { coastalApi } from "../lib/coastalApi";

type CoastalApi = ReturnType<typeof coastalApi>;

export const BEACH_RED: Beach = {
  id: "b-north",
  name: "Plage de la Corniche",
  lat: 37.2745,
  lon: 9.8739,
  gouvernorat_code: 17,
  level: "red",
  score: 75,
  factors: [
    { code: "waves", points: 55, value: 2.8 },
    { code: "season", points: 10, value: 7 },
    { code: "unguarded", points: 10, value: false },
  ],
  wave_height_m: 2.8,
  sea_temp_c: 24.1,
  current_kmh: 2.4,
  classification: "local",
  guarded: false,
  crowd: null,
  present: 12,
};

export const BEACH_GREEN: Beach = {
  ...BEACH_RED,
  id: "b-sousse",
  name: "Plage Boujaafar",
  lat: 35.83,
  lon: 10.64,
  gouvernorat_code: 51,
  level: "green",
  score: 10,
  factors: [{ code: "season", points: 10, value: 7 }],
  wave_height_m: 0.4,
  classification: "touristic",
  guarded: true,
  crowd: "medium",
  present: 40,
};

export const OVERVIEW: CoastalOverview = {
  day: "2026-07-04",
  computed_at: "2026-07-04T07:00:00Z",
  simulated: true,
  attribution: ["[SIM] Simulated marine weather (e-Himaya simulator), not real data"],
  kpis: {
    beaches: 2,
    red: 1,
    yellow: 0,
    green: 1,
    unknown: 0,
    average_score: 42.5,
    guarded: 1,
    drownings_season: 3,
    present: 52,
  },
  top_dangerous: [BEACH_RED, BEACH_GREEN],
  top_touristic: [BEACH_GREEN],
  by_gouvernorat: [
    { code: 17, beaches: 1, red: 1, yellow: 0, green: 0, average_score: 75, crowd_high: 0, crowd_medium: 0, crowd_low: 0 },
    { code: 51, beaches: 1, red: 0, yellow: 0, green: 1, average_score: 10, crowd_high: 0, crowd_medium: 1, crowd_low: 0 },
  ],
  beaches: [BEACH_RED, BEACH_GREEN],
  heat_risk: [
    [37.2745, 9.8739, 0.75],
    [35.83, 10.64, 0.1],
  ],
  heat_drownings: [[37.275, 9.874, 1]],
};

export const ALERT: CoastalAlert = {
  id: "a-1",
  feature_id: BEACH_RED.id,
  name: BEACH_RED.name,
  day: "2026-07-04",
  level: "red",
  previous_level: "green",
  score: 75,
  gouvernorat_code: 17,
  simulated: true,
  created_at: "2026-07-04T07:00:00Z",
  acked_by_name: null,
  acked_at: null,
};

export const DETAIL: BeachDetail = {
  beach: BEACH_RED,
  days: [
    {
      day: "2026-07-04",
      level: "red",
      score: 75,
      factors: BEACH_RED.factors,
      wave_height_m: 2.8,
      sea_temp_c: 24.1,
      current_kmh: 2.4,
      onshore_wind_kmh: 18,
      max_temperature_c: 31,
    },
    {
      day: "2026-07-05",
      level: "green",
      score: 20,
      factors: [{ code: "season", points: 10, value: 7 }, { code: "unguarded", points: 10, value: false }],
      wave_height_m: 0.4,
      sea_temp_c: 24.3,
      current_kmh: 0.8,
      onshore_wind_kmh: null,
      max_temperature_c: 30,
    },
  ],
  card: { classification: "local", guarded: "False", blue_flag: "no" },
  sources: { classification: { source: "ONTT", date: "2026-06-01" } },
  length_m: 1200,
  seaward_deg: 350,
  simulated: true,
  attribution: ["[SIM] Simulated marine weather (e-Himaya simulator), not real data"],
};

export const DEFAULT_RULES: Record<string, unknown> = {
  waves: [
    [0.5, 0],
    [1.0, 10],
    [1.5, 25],
    [2.5, 40],
    [null, 55],
  ],
  onshore_angle_deg: 60,
  onshore_kmh: 25,
  onshore_points: 10,
  strong_onshore_kmh: 40,
  strong_onshore_points: 15,
  current_kmh: 1.8,
  current_points: 10,
  season_months: [6, 7, 8, 9],
  hot_c: 30,
  season_points: 10,
  crowd_high_points: 5,
  unguarded_points: 10,
  incident_radius_m: 500,
  incident_years: 5,
  incident_points: 5,
  incident_max: 15,
  yellow: 35,
  red: 60,
  first_hour: 10,
  last_hour: 19,
};

export const SETTINGS: CoastalSettings = {
  rules: DEFAULT_RULES,
  defaults: DEFAULT_RULES,
  updated_by: null,
  updated_at: null,
};

/** Phase L1b calls of the fake API: a simulated day with one red and one green beach. */
export function fakeCoastalApi(): CoastalApi {
  return {
    coastalOverview: vi.fn(() => Promise.resolve(OVERVIEW)),
    coastalAlerts: vi.fn(() => Promise.resolve([ALERT])),
    ackCoastalAlert: vi.fn(() =>
      Promise.resolve({ ...ALERT, acked_by_name: "Salma", acked_at: "2026-07-04T07:05:00Z" }),
    ),
    coastalBeach: vi.fn(() => Promise.resolve(DETAIL)),
    coastalSettings: vi.fn(() => Promise.resolve(SETTINGS)),
    saveCoastalSettings: vi.fn((rules: Record<string, unknown>) => Promise.resolve({ ...SETTINGS, rules })),
    coastalBulletin: vi.fn(() => Promise.resolve({ blob: new Blob(["%PDF"]), filename: "bulletin.pdf" })),
  };
}
