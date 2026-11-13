/**
 * Crew accountability in danger zones (PAR, OS7, docs/phase-os7/design-os7.md): types and calls of
 * `/api/v1/staff/par`.
 */
import type { ApiClient } from "./api";
import { ApiError } from "./api";

export type ParZone = "hot" | "warm";
export type ParSituation = "controlled" | "progress" | "not_controlled";
export type ParTeamStatus = "ok" | "soon" | "late" | "alarm" | "missing" | "paused" | "out";
export type ParAwayWhy = "air" | "water_fuel" | "care" | "rest" | "other";
export type ParPauseWhy = "danger_over" | "defensive" | "ops_stopped" | "comms_failure" | "other";
export type ParCheckAllWhy = "collapse" | "defensive" | "evacuation" | "commander";
export type ParAutoEvent = "collapse" | "defensive" | "evacuation" | "severity";

export const PAR_HOT = [300, 600, 900] as const;
export const PAR_WARM = [600, 900, 1200] as const;
export const PAR_PAUSE_WHY: readonly ParPauseWhy[] = ["danger_over", "defensive", "ops_stopped", "comms_failure", "other"];
export const PAR_CHECK_ALL_WHY: readonly ParCheckAllWhy[] = ["collapse", "defensive", "evacuation", "commander"];
export const PAR_AUTO_EVENTS: readonly ParAutoEvent[] = ["collapse", "defensive", "evacuation", "severity"];
/** How far ahead the next check may be set (the API refuses more than 12 hours). */
export const PAR_MAX_AHEAD_MIN = 12 * 60;

export interface ParSetting {
  gouvernorat_code: number | null;
  hot_s: number;
  warm_s: number;
  grace_s: number;
  auto_events: ParAutoEvent[];
  remind_s: number;
  updated_at: string | null;
  updated_by_name: string | null;
}

export interface ParMember {
  key: string;
  name: string;
  role: string | null;
  away_why: ParAwayWhy | null;
  away_at: string | null;
}

export interface ParTeam {
  id: string;
  assignment_id: string;
  incident_id: string;
  label: string;
  task: string | null;
  zone: ParZone;
  status: ParTeamStatus;
  interval_s: number;
  due_at: string | null;
  remaining_s: number | null;
  last_confirmed_at: string;
  next_at: string | null;
  paused_at: string | null;
  pause_reason: string | null;
  out_at: string | null;
  out_count: number | null;
  entered_at: string;
  leader_name: string | null;
  members: ParMember[];
  present: number;
  away: number;
}

export interface ParMissing {
  id: string;
  team_id: string;
  team_label: string;
  resource: string;
  carrier: string;
  place: string | null;
  reported_at: string;
  reported_by_name: string | null;
  replacement_at: string | null;
  recovered_at: string | null;
  recovered_by_name: string | null;
}

export interface ParSitrep {
  id: number;
  team_id: string;
  team_label: string;
  at: string;
  situation: ParSituation;
  reinforcement: boolean;
  text: string | null;
  voice_seconds: number | null;
  edited: boolean;
  by_name: string | null;
}

export interface ParEvent {
  at: string;
  kind: string;
  text: string;
  by_name: string | null;
  team_id: string | null;
}

export interface ParBoard {
  incident_id: string;
  incident_kind: string;
  incident_status: string;
  gouvernorat_code: number | null;
  settings: ParSetting;
  kpis: { agents_in: number; teams_in: number; not_confirmed: number; missing_open: number };
  teams: ParTeam[];
  missing: ParMissing[];
  sitreps: ParSitrep[];
  events: ParEvent[];
  all_out: boolean;
  closure: {
    closed_at: string;
    closed_by_name: string | null;
    automatic: boolean;
    summary: Record<string, number>;
  } | null;
  now: string;
}

export interface ParIncidentRow {
  incident_id: string;
  incident_kind: string;
  gouvernorat_code: number | null;
  teams_in: number;
  agents_in: number;
  alarms: number;
  missing_open: number;
  last_sitrep: ParSituation | null;
  closed: boolean;
}

export interface ParSettingIn {
  hot_s: number;
  warm_s: number;
  grace_s: number;
  auto_events: ParAutoEvent[];
}

export const parKeys = {
  incidents: (closed: boolean) => ["par", "incidents", closed] as const,
  board: (id: string) => ["par", "board", id] as const,
  setting: ["par", "setting"] as const,
};

/** The colour of a team's state (design §2.3: OK green, warning amber, alarm and missing red, paused slate). */
export const PAR_STATUS_TONE = {
  ok: "green",
  soon: "amber",
  late: "amber",
  alarm: "red",
  missing: "red",
  paused: "slate",
  out: "navy",
} as const;

export const PAR_SITUATION_TONE = { controlled: "green", progress: "amber", not_controlled: "red" } as const;

/** mm:ss of a number of seconds (negative: late). */
export function mmss(seconds: number): string {
  const s = Math.abs(Math.round(seconds));
  const out = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  return seconds < 0 ? `-${out}` : out;
}

/** The seconds left of a team now, counted from the board's clock (a paused team keeps its frozen value). */
export function remainingNow(team: ParTeam, boardNow: string, now: number): number | null {
  if (team.remaining_s === null) return null;
  if (team.paused_at || !team.due_at) return team.remaining_s;
  const drift = (now - Date.parse(boardNow)) / 1000;
  return team.remaining_s - Math.max(0, drift);
}

/** The next whole times of the day a check may be set to: from the next minute, up to 12 hours ahead. */
export function nextAt(hour: number, minute: number, from: Date): Date {
  const d = new Date(from);
  d.setHours(hour, minute, 0, 0);
  if (d.getTime() <= from.getTime()) d.setDate(d.getDate() + 1);
  return d;
}

const P = "/api/v1/staff/par";
const enc = encodeURIComponent;

export function parApi(api: ApiClient) {
  const post = (incidentId: string, path: string, body?: unknown) =>
    api.request<ParBoard>(`${P}/incidents/${enc(incidentId)}/${path}`, { method: "POST", body: body ?? {} });
  return {
    parIncidents: (closed: boolean, signal?: AbortSignal) =>
      api.request<ParIncidentRow[]>(`${P}/incidents`, { query: { closed }, signal }),
    parBoard: (incidentId: string, signal?: AbortSignal) =>
      api.request<ParBoard>(`${P}/incidents/${enc(incidentId)}`, { signal }),
    parSetting: (signal?: AbortSignal) => api.request<ParSetting>(`${P}/settings`, { signal }),
    parSaveSetting: (body: ParSettingIn, gouvernorat?: number | null) =>
      api.request<ParSetting>(`${P}/settings`, {
        method: "PUT",
        body,
        query: { gouvernorat: gouvernorat ?? undefined },
      }),
    parSetNext: (incidentId: string, at: string, teamId: string | null) =>
      post(incidentId, "next", { at, team_id: teamId }),
    parClearNext: (incidentId: string, teamId: string | null) => post(incidentId, "next/clear", { team_id: teamId }),
    parPause: (incidentId: string, reason: ParPauseWhy, detail: string | null, teamId: string | null) =>
      post(incidentId, "pause", { reason, detail, team_id: teamId }),
    parResume: (incidentId: string, teamId: string | null) => post(incidentId, "resume", { team_id: teamId }),
    parCheckAll: (incidentId: string, reason: ParCheckAllWhy) => post(incidentId, "check-all", { reason }),
    parTeam: (incidentId: string, teamId: string, action: "radio" | "confirm" | "out") =>
      post(incidentId, `teams/${enc(teamId)}/${action}`),
    parMissing: (incidentId: string, missingId: string, action: "replacement" | "recovered") =>
      post(incidentId, `missing/${enc(missingId)}/${action}`),
    parClose: (incidentId: string) => post(incidentId, "close"),
  };
}

/** The code of an API refusal of the module (`time_passed`, `teams_inside` ...), or null. */
export function parErrorCode(error: unknown): string | null {
  return error instanceof ApiError && typeof error.detail === "string" ? error.detail : null;
}
