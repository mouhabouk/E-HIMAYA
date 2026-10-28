// Intervention plans by hazard (phase PL1, docs/phase-pl/design-plans.md §2): the hazards and the colour of their
// plan, the plan in force for each hazard nationally and in each gouvernorat, and the plan file read on the screen.
import type { ApiClient } from "./api";
import type { RegisterDocument } from "./register";

const R = "/api/v1/staff/register";
const enc = encodeURIComponent;

export interface Hazard {
  key: string;
  name: Record<"ar" | "fr" | "en", string>;
  colour: string;
  icon: string;
  position: number;
  active: boolean;
  updated_by_name: string | null;
  updated_at: string;
}

export interface HazardBody {
  name: Record<"ar" | "fr" | "en", string>;
  colour: string;
  icon: string;
  position: number;
  active: boolean;
}

export interface PlanEntry {
  document: RegisterDocument;
  /** Published versions of this plan (the one shown and those it repealed). */
  versions: number;
}

export interface HazardPlans {
  hazard: Hazard;
  national: PlanEntry | null;
  regional: PlanEntry[];
}

export interface PlansOverview {
  hazards: HazardPlans[];
  can_create: boolean;
  can_manage_hazards: boolean;
}

/** Icons a hazard may carry (Material Symbols embedded in the dashboard). */
export const HAZARD_ICONS = [
  "water",
  "localFireDepartment",
  "science",
  "medicalServices",
  "landslide",
  "thunderstorm",
  "warning",
  "healthAndSafety",
] as const;

export const planKeys = {
  all: ["plans"] as const,
  overview: ["plans", "overview"] as const,
  hazards: ["plans", "hazards"] as const,
  file: (id: string) => ["plans", "file", id] as const,
};

export function hazardName(h: Pick<Hazard, "name" | "key">, lang: string): string {
  const l = lang.slice(0, 2) as "ar" | "fr" | "en";
  return h.name[l] || h.name.ar || h.key;
}

/** Black or white text on the colour of a hazard, whichever reads better (WCAG relative luminance). */
export function textOn(colour: string): "#000000" | "#FFFFFF" {
  const c = [1, 3, 5].map((i) => parseInt(colour.slice(i, i + 2), 16) / 255);
  const [r = 0, g = 0, b = 0] = c.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  const l = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return (l + 0.05) / 0.05 > 1.05 / (l + 0.05) ? "#000000" : "#FFFFFF";
}

export function plansApi(api: ApiClient) {
  return {
    hazards: (signal?: AbortSignal) => api.request<Hazard[]>(`${R}/hazards`, { signal }),
    saveHazard: (key: string, body: HazardBody) =>
      api.request<Hazard>(`${R}/hazards/${enc(key)}`, { method: "PUT", body }),
    plans: (signal?: AbortSignal) => api.request<PlansOverview>(`${R}/plans`, { signal }),
    /** The bytes of a document's file, for the viewer (every opening is audited by the API). */
    documentFileBytes: (id: string, signal?: AbortSignal) =>
      api
        .requestRaw(`${R}/documents/${enc(id)}/file/content`, { signal, accept: "application/pdf" })
        .then((r) => r.arrayBuffer()),
  };
}
