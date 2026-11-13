// The field layers of the interactive map (Yamen 2026-11-13, docs/phase-ml/design-ml.md §7): the places of the periodic
// inspections, the vehicles' last positions and the PAR teams, read from the tables of their own screens.
import type { ApiClient } from "./api";

const F = "/api/v1/staff/field-map";

export interface FieldPoint {
  lat: number;
  lon: number;
}

export interface InspectionSite {
  key: string;
  target: "room" | "unit";
  room: string | null;
  unit_kind: string | null;
  name: string;
  gouvernorat_code: number | null;
  location: FieldPoint;
  location_source: "unit" | "arrived" | "report" | "directorate";
  last_inspection_id: string | null;
  last_on: string | null;
  last_score: number | null;
  last_verdict: string | null;
  next_on: string | null;
}

export interface FieldVehicle {
  id: string;
  label: string;
  kind: string;
  status: string;
  unit_name: string;
  gouvernorat_code: number;
  location: FieldPoint;
  at: string | null;
  incident_id: string | null;
}

export interface ParTeamPosition {
  id: string;
  incident_id: string;
  gouvernorat_code: number | null;
  label: string;
  zone: string;
  leader_name: string | null;
  members: number;
  status: "ok" | "soon" | "late" | "alarm" | "paused" | "missing" | "out";
  entered_at: string;
  last_confirmed_at: string;
  location: FieldPoint | null;
  location_source: "crew" | "incident" | null;
  at: string | null;
}

export const fieldMapKeys = {
  inspections: ["field-map", "inspections"] as const,
  vehicles: ["field-map", "vehicles"] as const,
  par: ["field-map", "par"] as const,
};

export function fieldMapApi(api: ApiClient) {
  return {
    fieldInspectionSites: (signal?: AbortSignal) =>
      api.request<{ items: InspectionSite[]; unplaced: number }>(`${F}/inspections`, { signal }),
    fieldVehicles: (signal?: AbortSignal) =>
      api.request<{ items: FieldVehicle[]; unplaced: number }>(`${F}/vehicles`, { signal }),
    fieldParTeams: (signal?: AbortSignal) => api.request<{ items: ParTeamPosition[] }>(`${F}/par`, { signal }),
  };
}
