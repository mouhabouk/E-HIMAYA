import type { ApiClient } from "./api";
import type { Download } from "./layersApi";

/**
 * The Office's reference lists (migration 0091): vehicle types with their CEE code, the agent's status and post, the
 * vehicle's state and situation, the parties of a road accident, the nature of a fire, the crops lost and their units,
 * the places of the damages and of the programmes, the fields of intervention. Every staff member reads them; the
 * central room adds, renames and retires items (never deletes them).
 */

export type DamageUnit = "ha" | "bale" | "bag";

export interface RefItem {
  id: string;
  code: string | null;
  label_ar: string;
  label_fr: string | null;
  unit: DamageUnit | null;
  sort: number;
  active: boolean;
  updated_by_name: string | null;
  updated_at: string;
}

export interface RefList {
  key: string;
  name_ar: string;
  name_fr: string;
  name_en: string;
  items: RefItem[];
}

export interface RefLists {
  lists: RefList[];
  can_manage: boolean;
}

export interface RefItemIn {
  code?: string | null;
  label_ar: string;
  label_fr?: string | null;
  unit?: DamageUnit | null;
}

export type RefItemPatch = Partial<RefItemIn> & { active?: boolean; sort?: number };

const R = "/api/v1/staff/references";
const enc = encodeURIComponent;

export const referenceKeys = { all: ["references"] as const };

export function referencesApi(api: ApiClient) {
  return {
    references: (signal?: AbortSignal) => api.request<RefLists>(R, { signal }),
    addReference: (key: string, body: RefItemIn) =>
      api.request<RefItem>(`${R}/${enc(key)}/items`, { method: "POST", body }),
    changeReference: (id: string, body: RefItemPatch) =>
      api.request<RefItem>(`${R}/items/${enc(id)}`, { method: "PATCH", body }),
    referencesExport: async (format: "xlsx" | "csv", key?: string): Promise<Download> => {
      const accept = format === "csv" ? "text/csv" : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      const response = await api.requestRaw(`${R}/export`, { query: { format, key }, accept });
      return { blob: await response.blob(), filename: `references-${key ?? "all"}.${format}` };
    },
  };
}
