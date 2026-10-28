import type { ApiClient } from "./api";

/**
 * Satellite background of the maps (docs/phase-r/design-basemap.md): the open source (Sentinel-2 cloudless) by
 * default, or the paid provider the national system administrator chose, whose key stays in the API.
 */

export const BASEMAP_MODES = ["map", "satellite", "hybrid"] as const;
export type BasemapMode = (typeof BASEMAP_MODES)[number];
export const PROVIDERS = ["esri", "maxar", "mapbox", "google", "other"] as const;
export type Provider = (typeof PROVIDERS)[number];

export interface TileSource {
  tiles: string[];
  attribution: string;
  max_zoom: number;
}

export interface Basemap {
  source: "open" | "paid";
  satellite: TileSource;
  labels: TileSource;
  open: TileSource;
}

/** What a map draws under its layers: the street map of its style, or imagery (with the place names in hybrid). */
export interface BasemapView {
  mode: BasemapMode;
  satellite: TileSource;
  labels: TileSource;
}

export interface BasemapSettings {
  configured: boolean;
  provider: Provider | null;
  url_template: string | null;
  key_hint: string | null;
  key_header: string | null;
  attribution: string | null;
  max_zoom: number;
  enabled: boolean;
  last_test_ok: boolean | null;
  last_test_at: string | null;
  updated_by_name: string | null;
  updated_at: string | null;
}

export interface BasemapSettingsBody {
  provider: Provider;
  url_template: string;
  /** null keeps the stored key, "" removes it. */
  api_key: string | null;
  key_header: string | null;
  attribution: string;
  max_zoom: number;
  enabled: boolean;
}

export interface BasemapTest {
  ok: boolean;
  status: number | null;
  content_type: string | null;
  ms: number;
  error: string | null;
}

/** Address examples shown in the settings (the exact one comes with the provider's contract). */
export const PROVIDER_EXAMPLES: Partial<Record<Provider, { url: string; attribution: string }>> = {
  esri: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?token={key}",
    attribution: "Esri, Maxar, Earthstar Geographics",
  },
  mapbox: {
    url: "https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.jpg90?access_token={key}",
    attribution: "© Mapbox © Maxar",
  },
};

export const basemapKeys = {
  view: ["basemap"] as const,
  settings: ["basemap", "settings"] as const,
};

const MODE_KEY = "ehimaya.basemap";

export function storedMode(): BasemapMode {
  try {
    const v = localStorage.getItem(MODE_KEY);
    return v === "satellite" || v === "hybrid" ? v : "map";
  } catch {
    return "map";
  }
}

export function storeMode(mode: BasemapMode): void {
  try {
    localStorage.setItem(MODE_KEY, mode);
  } catch {
    /* ignore: the choice still applies until the page is reloaded */
  }
}

const B = "/api/v1/staff/basemap";

export function basemapApi(api: ApiClient) {
  const absolute = (s: TileSource): TileSource => ({
    ...s,
    tiles: s.tiles.map((t) => (t.startsWith("/") && api.resolve ? api.resolve(t).replace(/%7B/g, "{").replace(/%7D/g, "}") : t)),
  });
  return {
    basemap: async (signal?: AbortSignal): Promise<Basemap> => {
      const b = await api.request<Basemap>(B, { signal });
      return { ...b, satellite: absolute(b.satellite) };
    },
    basemapSettings: (signal?: AbortSignal) => api.request<BasemapSettings>(`${B}/settings`, { signal }),
    saveBasemapSettings: (body: BasemapSettingsBody) =>
      api.request<BasemapSettings>(`${B}/settings`, { method: "PUT", body }),
    testBasemap: (body: BasemapSettingsBody) => api.request<BasemapTest>(`${B}/settings/test`, { method: "POST", body }),
  };
}
