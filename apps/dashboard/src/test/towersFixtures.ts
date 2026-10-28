import { vi } from "vitest";
import type { Tower, TowerCreated, TowerEvents, towersApi } from "../lib/towers";

/** Watch towers (L5b) [SIM]: one with a fire a moment ago, one quiet. */
export const TOWER: Tower = {
  id: "t-1",
  code: "JND-TWR-01",
  label: "برج عين دراهم [SIM]",
  gouvernorat_code: 32,
  lat: 36.78,
  lon: 8.69,
  bearing_deg: 90,
  fov_deg: 60,
  range_m: 8000,
  simulated: true,
  stream_status: "live",
  last_event: { at: new Date(Date.now() - 5 * 60_000).toISOString(), label: "fire", confidence: 0.86 },
  field_of_view: [
    [8.69, 36.78],
    [8.77, 36.74],
    [8.78, 36.78],
    [8.77, 36.82],
    [8.69, 36.78],
  ],
  created_by_name: "Salma Ben Ali",
  updated_at: "2026-10-28T20:55:00Z",
};

export const TOWERS: Tower[] = [
  {
    ...TOWER,
    id: "t-2",
    code: "JND-TWR-02",
    label: "برج فرنانة [SIM]",
    bearing_deg: 225,
    stream_status: "ended",
    last_event: null,
  },
  TOWER,
];

export const TOWER_CREATED: TowerCreated = {
  tower: TOWER,
  edge_key: "ef".repeat(32),
  publish_token: "publish-token-shown-once",
  publish_url_rtsp: "rtsp://10.0.0.5:8554/live/t-1",
  publish_url_rtmp: "rtmp://10.0.0.5:1935/live/t-1",
};

export const TOWER_EVENTS: TowerEvents = {
  tower_id: "t-1",
  items: [
    { at: "2026-10-28T20:55:00Z", label: "fire", confidence: 0.86, hits: 4, frames: 5, model: "SIM", media_id: null, suggestion_id: "sg-1" },
    { at: "2026-10-28T20:50:00Z", label: "smoke", confidence: 0.7, hits: 3, frames: 5, model: "SIM", media_id: null, suggestion_id: "sg-0" },
  ],
};

export function fakeTowersApi(): ReturnType<typeof towersApi> {
  return {
    towers: vi.fn(() => Promise.resolve({ items: TOWERS, can_manage: true })),
    createTower: vi.fn(() => Promise.resolve(TOWER_CREATED)),
    updateTower: vi.fn(() => Promise.resolve(TOWER)),
    rotateTowerKey: vi.fn(() => Promise.resolve({ tower: TOWER, edge_key: "12".repeat(32) })),
    towerEvents: vi.fn(() => Promise.resolve(TOWER_EVENTS)),
  };
}
