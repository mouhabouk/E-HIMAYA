import type { ApiClient } from "./api";
import type {
  AssistantAnswer,
  CommandBoard,
  CommandCard,
  CommandTextResult,
  DecideBody,
  FireForecastBody,
  ForecastRun,
  Recommendations,
  RespondersResult,
  RouteProfile,
  RouteResult,
} from "./decisionTypes";
import { bboxParam, type BBox } from "./filters";
import type { RecordingDownload } from "./streamsApi";
import type {
  CallFilters,
  CallLinkBody,
  Conference,
  DialBody,
  DialResult,
  SipCredentials,
  StaffCall,
} from "./telephonyTypes";
import type { Page } from "./types";
import type { WeatherGrid, WeatherPointDetail, WeatherSuggestion } from "./weatherTypes";
import type { Language } from "../i18n";

const enc = encodeURIComponent;
const incidentPath = (id: string) => `/api/v1/staff/incidents/${enc(id)}`;
const suggestionPath = (id: string) => `/api/v1/staff/weather/suggestions/${enc(id)}`;
const callPath = (id: string) => `/api/v1/staff/calls/${enc(id)}`;
const point = (p: { lat: number; lon: number }) => `${p.lat.toFixed(6)},${p.lon.toFixed(6)}`;

/** A list answered as a page or as a bare array (the contract does not fix it). */
function items<T>(body: Page<T> | T[] | { items: T[] }): T[] {
  return Array.isArray(body) ? body : body.items;
}

/** Typed calls for docs/api/phase-7-contract.md §1–§4 (weather, forecast, decision support, telephony). */
export function phase7Api(api: ApiClient) {
  return {
    // ---------- §1 weather ----------
    /** Map layer; `hour` = hours from now (0 = current, up to 47). */
    weatherGrid: (bbox: BBox, hour: number, signal?: AbortSignal) =>
      api.request<WeatherGrid>("/api/v1/staff/weather/grid", { query: { bbox: bboxParam(bbox), hour }, signal }),

    weatherAt: (lat: number, lon: number, signal?: AbortSignal) =>
      api.request<WeatherPointDetail>("/api/v1/staff/weather/at", {
        query: { lat: lat.toFixed(5), lon: lon.toFixed(5) },
        signal,
      }),

    weatherSuggestions: async (signal?: AbortSignal) =>
      items(
        await api.request<Page<WeatherSuggestion> | WeatherSuggestion[]>("/api/v1/staff/weather/suggestions", {
          signal,
        }),
      ),

    /** Records the acceptance (audited); the alert itself is sent only from the alert form after review. */
    acceptWeatherSuggestion: (id: string) => api.request<unknown>(`${suggestionPath(id)}/accept`, { method: "POST" }),

    dismissWeatherSuggestion: (id: string, reason: string) =>
      api.request<unknown>(`${suggestionPath(id)}/dismiss`, { method: "POST", body: { reason } }),

    // ---------- §2 spread forecast ----------
    fireForecast: (incidentId: string, body: FireForecastBody) =>
      api.request<ForecastRun>(`${incidentPath(incidentId)}/forecast/fire`, { method: "POST", body }),

    floodForecast: (incidentId: string) =>
      api.request<ForecastRun>(`${incidentPath(incidentId)}/forecast/flood`, { method: "POST", body: {} }),

    // ---------- §3 decision support ----------
    recommendations: (incidentId: string, signal?: AbortSignal) =>
      api.request<Recommendations>(`${incidentPath(incidentId)}/recommendations`, { signal }),

    route: (
      from: { lat: number; lon: number },
      to: { lat: number; lon: number },
      profile: RouteProfile = "car",
      signal?: AbortSignal,
    ) =>
      api.request<RouteResult>("/api/v1/staff/route", {
        query: { from: point(from), to: point(to), profile },
        signal,
      }),

    responders: async (incidentId: string, signal?: AbortSignal) =>
      items(
        await api.request<RespondersResult | RespondersResult["items"]>(`${incidentPath(incidentId)}/responders`, {
          signal,
        }),
      ),

    /** The assistant answers in ar or fr (phase 7 §1): an English interface asks for French. */
    askAssistant: (incidentId: string, question: string, lang: Language) =>
      api.request<AssistantAnswer>(`${incidentPath(incidentId)}/assistant`, {
        method: "POST",
        body: { question, lang: lang === "ar" ? "ar" : "fr" },
      }),

    // ---------- AI5a commander's assistant ----------
    commandBoard: (incidentId: string, signal?: AbortSignal) =>
      api.request<CommandBoard>(`${incidentPath(incidentId)}/command`, { signal }),

    /** A typed (or dictated) text in ar or fr: an English interface sends French. */
    commandText: (incidentId: string, text: string, lang: Language) =>
      api.request<CommandTextResult>(`${incidentPath(incidentId)}/command`, {
        method: "POST",
        body: { text, lang: lang === "ar" ? "ar" : "fr" },
      }),

    decideCommand: (decisionId: string, body: DecideBody) =>
      api.request<CommandCard>(`/api/v1/staff/command/decisions/${enc(decisionId)}`, { method: "POST", body }),

    // ---------- §4 telephony ----------
    sipCredentials: () => api.request<SipCredentials>("/api/v1/staff/telephony/credentials", { method: "POST" }),

    calls: (filters: CallFilters, opts: { cursor?: string | null; signal?: AbortSignal } = {}) =>
      api.request<Page<StaffCall>>("/api/v1/staff/calls", {
        query: { status: filters.status || undefined, cursor: opts.cursor ?? undefined },
        signal: opts.signal,
      }),

    call: (id: string, signal?: AbortSignal) => api.request<StaffCall>(callPath(id), { signal }),

    linkCall: (id: string, body: CallLinkBody) =>
      api.request<StaffCall>(`${callPath(id)}/link`, { method: "POST", body }),

    /** Scenario 2 only: `409 transfer_disabled` unless the API enables it. */
    transferTo198: (id: string) => api.request<StaffCall>(`${callPath(id)}/transfer-198`, { method: "POST" }),

    dial: (body: DialBody) => api.request<DialResult>("/api/v1/staff/calls/dial", { method: "POST", body }),

    /**
     * Recording: `302` to a pre-signed link (audited), followed by the browser, or `{"url"}` (same handling as the
     * stream recordings of phase 6).
     */
    callRecording: async (id: string): Promise<RecordingDownload> => {
      const response = await api.requestRaw(`${callPath(id)}/recording`, {
        accept: "application/json, audio/*;q=0.9, */*;q=0.8",
      });
      const type = response.headers.get("Content-Type") ?? "";
      if (type.includes("application/json")) {
        const body = (await response.json()) as { url?: unknown };
        if (typeof body.url === "string") return { kind: "link", url: body.url };
      }
      return { kind: "file", blob: await response.blob(), url: response.url };
    },

    conferences: async (incidentId: string, signal?: AbortSignal) =>
      items(
        await api.request<Conference[] | { items: Conference[] }>(`${incidentPath(incidentId)}/conference`, { signal }),
      ),

    startConference: (incidentId: string) =>
      api.request<Conference>(`${incidentPath(incidentId)}/conference`, { method: "POST" }),

    endConference: (incidentId: string, room: string) =>
      api.request<unknown>(`${incidentPath(incidentId)}/conference/${enc(room)}`, { method: "DELETE" }),
  };
}

export type Phase7Api = ReturnType<typeof phase7Api>;

export const p7Keys = {
  weatherGridAll: ["weather-grid"] as const,
  weatherGrid: (bbox: BBox, hour: number) => ["weather-grid", bbox.map((n) => Number(n.toFixed(2))), hour] as const,
  weatherAt: (lat: number, lon: number) => ["weather-at", lat.toFixed(3), lon.toFixed(3)] as const,
  suggestions: ["weather-suggestions"] as const,
  recommendations: (incidentId: string) => ["recommendations", incidentId] as const,
  commandBoard: (incidentId: string) => ["command-board", incidentId] as const,
  responders: (incidentId: string) => ["responders", incidentId] as const,
  forecast: (incidentId: string, kind: "fire" | "flood") => ["forecast", incidentId, kind] as const,
  route: (from: string, to: string, profile: string) => ["route", from, to, profile] as const,
  callsAll: ["calls"] as const,
  calls: (filters: CallFilters) => ["calls", filters.status] as const,
  call: (id: string) => ["call", id] as const,
  conferences: (incidentId: string) => ["conferences", incidentId] as const,
};
