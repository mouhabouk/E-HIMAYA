import type { ApiClient } from "./api";
import type { Download } from "./layersApi";

/**
 * Resources register of every gouvernorat (phase R1, docs/phase-r/design-resources.md §2): the national catalogue,
 * vehicles with their specifications, equipment by quantity, staff with their specialities.
 */

export type CategoryKind = "vehicle" | "equipment" | "skill";
export const FAMILIES = ["vehicles", "equipment", "boats", "air", "ppe"] as const;
export type Family = (typeof FAMILIES)[number];
export const VEHICLE_STATES = ["ready", "assigned", "maintenance", "broken"] as const;
export type VehicleState = (typeof VEHICLE_STATES)[number];
export const WRITABLE_STATES = ["ready", "maintenance", "broken"] as const;
export type WritableState = (typeof WRITABLE_STATES)[number];
export const AVAILABILITY = ["on_duty", "rest", "leave"] as const;
export type Availability = (typeof AVAILABILITY)[number];
export type Entity = "vehicles" | "stock" | "agents";
export type SpecValue = number | boolean;

/** State colours (design system tones). */
export const STATE_TONE: Readonly<Record<VehicleState, string>> = {
  ready: "green",
  assigned: "sky",
  maintenance: "amber",
  broken: "red",
};

export interface Names {
  ar: string;
  fr: string;
  en: string;
}

export interface SpecDef {
  key: string;
  unit: string;
  type: "number" | "bool";
  name: Names;
}

export interface Category {
  key: string;
  kind: CategoryKind;
  family: Family | null;
  name: Names;
  specs: SpecDef[];
  levels: number;
  position: number;
  active: boolean;
}

export interface Catalogue {
  items: Category[];
  can_manage: boolean;
}

export interface CategoryBody {
  key: string;
  kind: CategoryKind;
  family: Family | null;
  name: Names;
  specs: SpecDef[];
  levels: number;
  position: number;
}

export type CategoryPatch = Partial<Omit<CategoryBody, "key" | "kind">> & { active?: boolean };

export interface UnitRow {
  id: string;
  name_ar: string;
  name_fr: string;
  kind: string;
  gouvernorat_code: number;
  vehicles: number;
  vehicles_ready: number;
  equipment_ready: number;
  equipment_broken: number;
  agents: number;
  agents_on_duty: number;
  verified_at: string | null;
  verified_by_name: string | null;
  stale: boolean;
  can_edit: boolean;
}

export interface Tally {
  ready: number;
  assigned: number;
  maintenance: number;
  broken: number;
}

export interface GouvernoratRow {
  code: number;
  name_ar: string;
  name_fr: string;
  name_en: string;
  units: number;
  stale_units: number;
  vehicles: Tally;
  equipment: Tally;
  agents: number;
  agents_on_duty: number;
}

export interface CategoryTotal extends Tally {
  key: string;
  kind: CategoryKind;
}

export interface SkillTotal {
  key: string;
  agents: number;
  ready: number;
  expired: number;
}

export interface Overview {
  gouvernorats: GouvernoratRow[];
  categories: CategoryTotal[];
  skills: SkillTotal[];
  can_list: boolean;
  can_edit: boolean;
  can_see_names: boolean;
}

export interface Vehicle {
  id: string;
  unit_id: string;
  unit_name: string;
  gouvernorat_code: number;
  category_key: string | null;
  kind: string;
  label: string;
  code: string | null;
  specs: Record<string, SpecValue>;
  state: VehicleState;
  year: number | null;
  notes: string | null;
  version: number;
  updated_at: string;
}

export interface VehicleBody {
  unit_id: string;
  category_key: string;
  label: string;
  code: string | null;
  specs: Record<string, SpecValue>;
  state: WritableState;
  year: number | null;
  notes: string | null;
  reason: string;
  version?: number;
}

export interface StockLine {
  id: string;
  unit_id: string;
  unit_name: string;
  gouvernorat_code: number;
  category_key: string;
  specs: Record<string, SpecValue>;
  qty_ready: number;
  qty_broken: number;
  notes: string | null;
  version: number;
  updated_at: string;
}

export interface StockBody {
  unit_id: string;
  category_key: string;
  specs: Record<string, SpecValue>;
  qty_ready: number;
  qty_broken: number;
  notes: string | null;
  reason: string;
  version?: number;
}

export interface Skill {
  skill_key: string;
  level: number;
  cert_expires: string | null;
}

export interface AgentSkill extends Skill {
  expired: boolean;
}

export interface Agent {
  id: string;
  unit_id: string;
  unit_name: string;
  gouvernorat_code: number;
  /** Personal data: null outside the operations rooms. */
  matricule: string | null;
  full_name: string | null;
  phone: string | null;
  rank: string | null;
  availability: Availability;
  skills: AgentSkill[];
  notes: string | null;
  version: number;
  updated_at: string;
}

export interface AgentBody {
  unit_id: string;
  matricule: string;
  full_name: string;
  rank: string | null;
  phone: string | null;
  availability: Availability;
  skills: Skill[];
  notes: string | null;
  reason: string;
  version?: number;
}

export interface Listing<T> {
  items: T[];
  can_edit: boolean;
}

export interface AgentListing extends Listing<Agent> {
  can_see_names: boolean;
  can_export_names: boolean;
}

export interface InventoryRevision {
  id: string;
  entity: "vehicle" | "stock" | "agent";
  entity_id: string;
  action: "create" | "update" | "delete" | "import";
  snapshot: Record<string, unknown>;
  reason: string | null;
  created_by_name: string | null;
  created_at: string;
}

export interface ImportProblem {
  code: string;
  entity: string;
  line?: number | null;
  value?: string | null;
}

export interface ImportCounts {
  new: number;
  changed: number;
  unchanged: number;
}

export interface InventoryImport {
  format: "xlsx" | "csv";
  gouvernorat_code: number;
  applied: boolean;
  vehicles: ImportCounts;
  stock: ImportCounts;
  agents: ImportCounts;
  errors: ImportProblem[];
  warnings: ImportProblem[];
}

export interface ListQuery {
  gouvernorat: number | null;
  unit: string | null;
  category: string | null;
}

export const inventoryKeys = {
  all: ["inventory"] as const,
  catalogue: ["inventory", "catalogue"] as const,
  overview: ["inventory", "overview"] as const,
  units: (g: number | null) => ["inventory", "units", g] as const,
  list: (entity: Entity, q: ListQuery) => ["inventory", entity, q] as const,
  revisions: (id: string) => ["inventory", "revisions", id] as const,
};

/** "2 000 L · 4x4": the specifications of a vehicle or a stock line, as the catalogue names them. */
export function specText(
  specs: Record<string, SpecValue>,
  category: Category | undefined,
  lang: keyof Names,
  number: (n: number) => string,
  yes: string,
): string {
  const defs = category?.specs ?? [];
  return defs
    .filter((d) => specs[d.key] !== undefined && specs[d.key] !== false)
    .map((d) => {
      const v = specs[d.key];
      return typeof v === "boolean" ? `${d.name[lang]}: ${yes}` : `${number(v as number)} ${d.unit}`.trim();
    })
    .join(" · ");
}

const I = "/api/v1/staff/inventory";
const enc = encodeURIComponent;

function filenameOf(response: Response, fallback: string): string {
  const match = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "");
  return match?.[1] ?? fallback;
}

function listQuery(q: ListQuery, key: "category" | "skill" = "category") {
  return { gouvernorat: q.gouvernorat, unit_id: q.unit, [key]: q.category };
}

export function inventoryApi(api: ApiClient) {
  return {
    inventoryCatalogue: (signal?: AbortSignal) => api.request<Catalogue>(`${I}/catalogue`, { signal }),
    createCategory: (body: CategoryBody) => api.request<Category>(`${I}/catalogue`, { method: "POST", body }),
    updateCategory: (key: string, body: CategoryPatch) =>
      api.request<Category>(`${I}/catalogue/${enc(key)}`, { method: "PATCH", body }),
    inventoryOverview: (signal?: AbortSignal) => api.request<Overview>(`${I}/overview`, { signal }),
    inventoryUnits: (gouvernorat: number | null, signal?: AbortSignal) =>
      api.request<{ items: UnitRow[] }>(`${I}/units`, { query: { gouvernorat }, signal }),
    verifyUnit: (id: string) => api.request<UnitRow>(`${I}/units/${enc(id)}/verify`, { method: "POST", body: {} }),
    vehicles: (q: ListQuery, signal?: AbortSignal) =>
      api.request<Listing<Vehicle>>(`${I}/vehicles`, { query: listQuery(q), signal }),
    saveVehicle: (id: string | null, body: VehicleBody) =>
      id
        ? api.request<Vehicle>(`${I}/vehicles/${enc(id)}`, { method: "PATCH", body })
        : api.request<Vehicle>(`${I}/vehicles`, { method: "POST", body }),
    deleteVehicle: (id: string, reason: string) =>
      api.request<undefined>(`${I}/vehicles/${enc(id)}`, { method: "DELETE", body: { reason } }),
    stock: (q: ListQuery, signal?: AbortSignal) =>
      api.request<Listing<StockLine>>(`${I}/stock`, { query: listQuery(q), signal }),
    saveStock: (id: string | null, body: StockBody) =>
      id
        ? api.request<StockLine>(`${I}/stock/${enc(id)}`, { method: "PATCH", body })
        : api.request<StockLine>(`${I}/stock`, { method: "POST", body }),
    deleteStock: (id: string, reason: string) =>
      api.request<undefined>(`${I}/stock/${enc(id)}`, { method: "DELETE", body: { reason } }),
    agents: (q: ListQuery, signal?: AbortSignal) =>
      api.request<AgentListing>(`${I}/agents`, { query: listQuery(q, "skill"), signal }),
    saveAgent: (id: string | null, body: AgentBody) =>
      id
        ? api.request<Agent>(`${I}/agents/${enc(id)}`, { method: "PATCH", body })
        : api.request<Agent>(`${I}/agents`, { method: "POST", body }),
    deleteAgent: (id: string, reason: string) =>
      api.request<undefined>(`${I}/agents/${enc(id)}`, { method: "DELETE", body: { reason } }),
    inventoryRevisions: (entityId: string, signal?: AbortSignal) =>
      api.request<{ items: InventoryRevision[] }>(`${I}/revisions`, { query: { entity_id: entityId }, signal }),
    importInventory: (file: File, gouvernorat: number | null, entity: Entity | null, apply: boolean, reason = "") =>
      api.request<InventoryImport>(`${I}/imports`, {
        method: "POST",
        query: {
          file_name: file.name,
          gouvernorat,
          entity,
          apply,
          reason: apply ? reason : undefined,
        },
        rawBody: file,
      }),
    inventoryTemplate: async (gouvernorat: number | null): Promise<Download> => {
      const response = await api.requestRaw(`${I}/template`, { query: { gouvernorat }, accept: "*/*" });
      return { blob: await response.blob(), filename: filenameOf(response, "inventory.xlsx") };
    },
    exportInventory: async (entity: Entity, gouvernorat: number | null): Promise<Download> => {
      const response = await api.requestRaw(`${I}/export`, { query: { entity, gouvernorat }, accept: "*/*" });
      return { blob: await response.blob(), filename: filenameOf(response, `inventory-${entity}.csv`) };
    },
  };
}
