import type { ApiClient } from "./api";
import type {
  BeachDetail,
  CoastalAlert,
  CoastalOverview,
  CoastalSettings,
  OverviewFilters,
} from "./coastal";
import type { Download } from "./layersApi";

const C = "/api/v1/staff/coastal";
const enc = encodeURIComponent;

export const coastalKeys = {
  all: ["coastal"] as const,
  overview: (f: OverviewFilters) => ["coastal", "overview", f] as const,
  alerts: (day: string | undefined) => ["coastal", "alerts", day ?? "today"] as const,
  beach: (id: string) => ["coastal", "beach", id] as const,
  settings: ["coastal", "settings"] as const,
};

/** Coastal safety (phase L1b): the dashboard, the alerts centre, the beach card, the rules and the bulletin. */
export function coastalApi(api: ApiClient) {
  return {
    coastalOverview: (f: OverviewFilters, signal?: AbortSignal) =>
      api.request<CoastalOverview>(`${C}/overview`, {
        query: {
          day: f.day,
          gouvernorat: f.gouvernorat ? String(f.gouvernorat) : undefined,
          classification: f.classification,
          guarded: f.guarded === undefined ? undefined : String(f.guarded),
          level: f.level,
        },
        signal,
      }),

    coastalAlerts: (day: string | undefined, signal?: AbortSignal) =>
      api.request<{ items: CoastalAlert[] }>(`${C}/alerts`, { query: { day }, signal }).then((b) => b.items),

    ackCoastalAlert: (id: string) => api.request<CoastalAlert>(`${C}/alerts/${enc(id)}/ack`, { method: "POST", body: {} }),

    coastalBeach: (id: string, signal?: AbortSignal) => api.request<BeachDetail>(`${C}/beaches/${enc(id)}`, { signal }),

    coastalSettings: (signal?: AbortSignal) => api.request<CoastalSettings>(`${C}/settings`, { signal }),

    saveCoastalSettings: (rules: Record<string, unknown>, reason: string) =>
      api.request<CoastalSettings>(`${C}/settings`, { method: "PUT", body: { rules, reason } }),

    coastalBulletin: async (day: string | undefined, lang: string, gouvernorat?: number): Promise<Download> => {
      const response = await api.requestRaw(`${C}/bulletin.pdf`, {
        query: { day, lang, gouvernorat: gouvernorat ? String(gouvernorat) : undefined },
        accept: "application/pdf",
      });
      return { blob: await response.blob(), filename: `bulletin-cotier-${day ?? "today"}.pdf` };
    },
  };
}
