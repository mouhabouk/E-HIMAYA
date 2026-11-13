import type { ApiClient } from "./api";

// The four screens the menu of 20 systems lacked (2026-11-13): image analysis (7), forecasting (5), citizens (17)
// and the administrator's mother board (19). Each answer stays in the caller's scope.

export type DangerLevel = "high" | "medium" | "low";

export interface VisionItem {
  at: string;
  label: string;
  confidence: number;
  confirmed: boolean;
  danger: DangerLevel;
  /** "report_image", or the stream's source ("tower", "drone", "phone" ...). */
  origin: string;
  stream_id: string | null;
  stream_label: string | null;
  report_id: string | null;
  gouvernorat_code: number | null;
  model: string | null;
}

export interface VisionOverview {
  hours: number;
  counts: { fire: number; smoke: number; person: number };
  confirmed: number;
  danger: Record<DangerLevel, number>;
  watching: number;
  alert_confidence: number;
  items: VisionItem[];
}

export interface ForecastGov {
  gouvernorat_code: number;
  fwi: number | null;
  fire_danger: string | null;
  fire_at: string | null;
  rain: string;
  rain_24h_mm: number | null;
  gust_kmh: number | null;
}

export interface ForecastRunRow {
  id: string;
  incident_id: string;
  incident_title: string | null;
  gouvernorat_code: number | null;
  kind: string;
  model: string;
  at: string;
  simulated: boolean;
  summary: Record<string, number | string>;
}

export interface ForecastOverview {
  hours: number;
  from: string;
  simulated: boolean;
  gouvernorats: ForecastGov[];
  runs: ForecastRunRow[];
}

export interface CitizensGov {
  gouvernorat_code: number;
  reporters: number;
  reports: number;
  rejected: number;
  kept: number;
  volunteers: number;
}

export interface CitizensOverview {
  days: number;
  /** Empty for a regional caller. */
  national: {
    citizens?: number;
    anonymous?: number;
    organizations?: number;
    rating?: number | null;
    ratings?: number;
  };
  gouvernorats: CitizensGov[];
}

export type ServiceState = "ok" | "error" | "unreachable" | "not_configured" | "real" | "simulated";

export interface AdminBoardOverview {
  services: Record<"database" | "ai" | "vision" | "telephony" | "notifications", ServiceState>;
  accounts_week: Record<string, number>;
  rules: { grants: number; hidden: number; assignments: number };
  systems: {
    key: string;
    number: number | null;
    effect: string;
    target_kind: string;
    target: string | null;
    message: Record<string, string> | null;
    ends_at: string | null;
  }[];
  recent: { at: string; action: string; target: string | null; reason: string | null }[];
}

const S = "/api/v1/staff";

export const boardsKeys = {
  vision: (hours: number) => ["boards", "vision", hours] as const,
  forecast: ["boards", "forecast"] as const,
  citizens: (days: number) => ["boards", "citizens", days] as const,
  admin: ["boards", "admin"] as const,
};

export function boardsApi(api: ApiClient) {
  return {
    visionOverview: (hours: number, signal?: AbortSignal) =>
      api.request<VisionOverview>(`${S}/vision/overview`, { query: { hours: String(hours) }, signal }),
    forecastOverview: (signal?: AbortSignal) => api.request<ForecastOverview>(`${S}/forecast/overview`, { signal }),
    citizensOverview: (days: number, signal?: AbortSignal) =>
      api.request<CitizensOverview>(`${S}/citizens/overview`, { query: { days: String(days) }, signal }),
    adminBoardOverview: (signal?: AbortSignal) =>
      api.request<AdminBoardOverview>(`${S}/admin-board/overview`, { signal }),
  };
}
