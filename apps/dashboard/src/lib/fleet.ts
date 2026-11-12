import type { ApiClient } from "./api";
import type { Vehicle } from "./inventory";

/**
 * OS3 (docs/phase-os3/design-os3.md): the fleet and its maintenance, the live coverage and the repositioning, and
 * the permission profiles of the system administrator.
 */

export type RoomState = "ready" | "reinforcement" | "broken";
export const COVERAGE_FAMILIES = ["medical", "road", "fire", "rescue"] as const;
export type CoverageFamily = (typeof COVERAGE_FAMILIES)[number];
export type Zone = "urban" | "periurban" | "rural";

export interface VehicleStateBody {
  state: RoomState;
  host_unit_id?: string | null;
  fault?: string | null;
  note?: string | null;
  suggested_gain?: number | null;
  version?: number;
}

export interface MaintenanceBody {
  workshop: string;
  reason: string;
  until?: string | null;
  version?: number;
}

export interface MaintenanceEndBody {
  note?: string | null;
  odometer_km?: number | null;
  version?: number;
}

export interface RetireBody {
  decision: string;
  retired_on: string;
  reason: string;
  version?: number;
}

export type VehicleEventKind =
  | "state"
  | "maintenance_start"
  | "maintenance_end"
  | "retire"
  | "reinforce"
  | "reinforce_end";

export interface VehicleEvent {
  id: string;
  resource_id: string;
  label: string;
  plate: string | null;
  unit_name: string;
  gouvernorat_code: number;
  kind: VehicleEventKind;
  from_state: string;
  to_state: string;
  details: Record<string, string | number | boolean | null>;
  created_by_name: string | null;
  created_at: string;
}

export interface FamilyCell {
  minutes: number | null;
  target: number;
  covered: boolean;
  baseline_covered: boolean;
  unit_name: string | null;
}

export interface CoveragePlace {
  id: number;
  name_ar: string;
  name_fr: string;
  population: number;
  zone: Zone;
  lat: number;
  lon: number;
  families: Record<CoverageFamily, FamilyCell>;
}

export interface CoverageFamilyRow {
  family: CoverageFamily;
  population: number;
  covered_population: number;
  covered_pct: number;
  baseline_pct: number;
  ready: number;
  fleet: number;
  out: number;
}

export interface CoverageUnit {
  id: string;
  name_ar: string;
  name_fr: string;
  lat: number;
  lon: number;
  ready: Record<CoverageFamily, number>;
  hosted: number;
}

export interface CoverageAlert {
  family: CoverageFamily;
  delegation_id: number;
  delegation: string;
  population: number;
  minutes: number | null;
  target: number;
  baseline_minutes: number | null;
}

export interface CoverageSuggestion {
  family: CoverageFamily;
  vehicle_id: string;
  label: string;
  from_unit_id: string;
  from_unit: string;
  to_unit_id: string;
  to_unit: string;
  gain_population: number;
  newly_covered: string[];
  lost: string[];
  version: number;
}

export interface Coverage {
  gouvernorat_code: number;
  engine: string;
  turnout_minutes: number;
  targets: Record<CoverageFamily, Record<Zone, number>>;
  families: CoverageFamilyRow[];
  delegations: CoveragePlace[];
  units: CoverageUnit[];
  alerts: CoverageAlert[];
  suggestions: CoverageSuggestion[];
  computed_at: string;
  assumptions: string[];
}

export type ProfileMode = "read" | "write";

export interface ProfileItem {
  page: string;
  mode: ProfileMode;
}

export interface Profile {
  id: string;
  name: string;
  description: string | null;
  builtin: boolean;
  items: (ProfileItem & { known: boolean; names: { ar: string; fr: string; en: string } | null; features: string[] })[];
  active_assignments: number;
  updated_at: string;
}

export interface ProfileBody {
  name: string;
  description: string | null;
  items: ProfileItem[];
}

export interface AssignBody {
  target_kind: "user" | "role";
  target: string;
  target_name?: string | null;
  gouvernorat_code?: number | null;
  reason: string;
  starts_at?: string | null;
  ends_at?: string | null;
}

export interface ProfileAssignment {
  id: string;
  profile_id: string | null;
  target_kind: "user" | "role";
  target: string;
  target_name: string | null;
  gouvernorat_code: number | null;
  reason: string;
  starts_at: string | null;
  ends_at: string | null;
  created_by_name: string | null;
  created_at: string;
  state: string;
  features: string[];
  skipped?: { feature_key: string; reason: string }[];
}

const I = "/api/v1/staff/inventory";
const F = "/api/v1/staff/features";
const enc = encodeURIComponent;

export const fleetKeys = {
  all: ["inventory", "fleet"] as const,
  vehicles: (gouvernorat: number | null) => ["inventory", "fleet", "vehicles", gouvernorat] as const,
  events: (gouvernorat: number | null, vehicle: string | null) =>
    ["inventory", "fleet", "events", gouvernorat, vehicle] as const,
  coverage: (gouvernorat: number | null) => ["coverage", gouvernorat] as const,
  profiles: ["feature-profiles"] as const,
  assignments: ["feature-profile-assignments"] as const,
};

export function fleetApi(api: ApiClient) {
  return {
    fleetVehicles: (gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<{ items: Vehicle[]; can_edit: boolean; can_set_state: boolean; can_maintain: boolean }>(
        `${I}/vehicles`,
        { query: { gouvernorat }, signal },
      ),
    setVehicleState: (id: string, body: VehicleStateBody) =>
      api.request<Vehicle>(`${I}/vehicles/${enc(id)}/state`, { method: "POST", body }),
    startMaintenance: (id: string, body: MaintenanceBody) =>
      api.request<Vehicle>(`${I}/vehicles/${enc(id)}/maintenance`, { method: "POST", body }),
    endMaintenance: (id: string, body: MaintenanceEndBody) =>
      api.request<Vehicle>(`${I}/vehicles/${enc(id)}/maintenance/end`, { method: "POST", body }),
    retireVehicle: (id: string, body: RetireBody) =>
      api.request<Vehicle>(`${I}/vehicles/${enc(id)}/retire`, { method: "POST", body }),
    vehicleEvents: (q: { gouvernorat?: number | null; vehicle?: string | null }, signal?: AbortSignal) =>
      api.request<{ items: VehicleEvent[] }>(`${I}/vehicle-events`, {
        query: { gouvernorat: q.gouvernorat ?? undefined, vehicle_id: q.vehicle ?? undefined },
        signal,
      }),
    coverage: (gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<Coverage>("/api/v1/staff/coverage", { query: { gouvernorat: gouvernorat ?? undefined }, signal }),
    featureProfiles: (signal?: AbortSignal) => api.request<Profile[]>(`${F}/profiles`, { signal }),
    saveFeatureProfile: (id: string | null, body: ProfileBody) =>
      id
        ? api.request<Profile>(`${F}/profiles/${enc(id)}`, { method: "PATCH", body })
        : api.request<Profile>(`${F}/profiles`, { method: "POST", body }),
    deleteFeatureProfile: (id: string) => api.request<undefined>(`${F}/profiles/${enc(id)}`, { method: "DELETE" }),
    assignFeatureProfile: (id: string, body: AssignBody) =>
      api.request<ProfileAssignment>(`${F}/profiles/${enc(id)}/assign`, { method: "POST", body }),
    profileAssignments: (signal?: AbortSignal) =>
      api.request<ProfileAssignment[]>(`${F}/profile-assignments`, { signal }),
    revokeProfileAssignment: (id: string, reason: string) =>
      api.request<undefined>(`${F}/profile-assignments/${enc(id)}/revoke`, { method: "POST", body: { reason } }),
  };
}

/** Plate number (رقم منجمي): series, «تونس», number — the API checks the same. */
export const PLATE = /^\d{1,3} ?تونس ?\d{1,4}$/;

export function vehiclesByState(items: readonly Vehicle[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const v of items) out[v.state] = (out[v.state] ?? 0) + 1;
  return out;
}
