import { vi } from "vitest";
import type { basemapApi } from "../lib/basemap";
import { BASEMAP, BASEMAP_SETTINGS } from "./basemapData";

export * from "./basemapData";

export function fakeBasemapApi(): ReturnType<typeof basemapApi> {
  return {
    basemap: vi.fn(() => Promise.resolve(BASEMAP)),
    basemapSettings: vi.fn(() => Promise.resolve(BASEMAP_SETTINGS)),
    saveBasemapSettings: vi.fn(() => Promise.resolve(BASEMAP_SETTINGS)),
    testBasemap: vi.fn(() => Promise.resolve({ ok: true, status: 200, content_type: "image/jpeg", ms: 214, error: null })),
  };
}
