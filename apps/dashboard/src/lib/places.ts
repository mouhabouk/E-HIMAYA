import type { ApiClient } from "./api";

/** Saved places of the rooms (phase M, docs/phase-m/design-m.md §7): a point, a name, a kind and a note. */

export const PLACE_KINDS = ["critical", "important", "other"] as const;
export type PlaceKind = (typeof PLACE_KINDS)[number];

export interface SavedPlace {
  id: string;
  name: string;
  kind: PlaceKind;
  note: string | null;
  lat: number;
  lon: number;
  gouvernorat_code: number;
  delegation_id: number | null;
  created_by_name: string | null;
  created_at: string;
  updated_by_name: string | null;
  updated_at: string;
}

export interface PlaceBody {
  name: string;
  kind: PlaceKind;
  note: string | null;
}

/** Colours of the kinds on the map (docs/design-system.md: red emergency, orange accent, teal places). */
export const PLACE_COLOURS: Record<PlaceKind, string> = { critical: "#D7141A", important: "#C25E00", other: "#00806A" };

/** Bookmark with a dot: a place someone saved. */
export const PLACE_ICON = "M6 2h12a1 1 0 0 1 1 1v19l-7-4.5L5 22V3a1 1 0 0 1 1-1zm6 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6z";

export const placeKeys = { all: ["saved-places"] as const };

export function placesApi(api: ApiClient) {
  return {
    places: (signal?: AbortSignal) => api.request<SavedPlace[]>("/api/v1/staff/places", { signal }),
    createPlace: (body: PlaceBody & { lat: number; lon: number }) =>
      api.request<SavedPlace>("/api/v1/staff/places", { method: "POST", body }),
    updatePlace: (id: string, body: PlaceBody) =>
      api.request<SavedPlace>(`/api/v1/staff/places/${encodeURIComponent(id)}`, { method: "PUT", body }),
    deletePlace: (id: string) =>
      api.request<undefined>(`/api/v1/staff/places/${encodeURIComponent(id)}`, { method: "DELETE" }),
  };
}
