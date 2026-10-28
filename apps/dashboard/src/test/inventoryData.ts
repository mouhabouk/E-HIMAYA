import type { Agent, Catalogue, InventoryImport, Overview, StockLine, UnitRow, Vehicle } from "../lib/inventory";

/** Resources register data (phase R1) shared by the unit tests and the accessibility run. */

const names = (ar: string, fr: string, en: string) => ({ ar, fr, en });

export const CATALOGUE: Catalogue = {
  can_manage: false,
  items: [
    {
      key: "fire_engine",
      kind: "vehicle",
      family: "vehicles",
      name: names("شاحنة إطفاء", "Camion d'incendie", "Fire engine"),
      specs: [
        { key: "capacity_l", unit: "L", type: "number", name: names("السعة", "Capacité", "Capacity") },
        { key: "four_wd", unit: "", type: "bool", name: names("دفع رباعي", "4x4", "Four-wheel drive") },
      ],
      levels: 0,
      position: 1,
      active: true,
    },
    {
      key: "pump",
      kind: "equipment",
      family: "equipment",
      name: names("مضخة", "Motopompe", "Pump"),
      specs: [{ key: "flow_lpm", unit: "L/min", type: "number", name: names("الصبيب", "Débit", "Flow") }],
      levels: 0,
      position: 2,
      active: true,
    },
    {
      key: "diving",
      kind: "skill",
      family: null,
      name: names("غوص", "Plongée", "Diving"),
      specs: [],
      levels: 3,
      position: 3,
      active: true,
    },
  ],
};

export const OVERVIEW: Overview = {
  gouvernorats: [
    {
      code: 61,
      name_ar: "صفاقس",
      name_fr: "Sfax",
      name_en: "Sfax",
      units: 3,
      stale_units: 1,
      vehicles: { ready: 7, assigned: 2, maintenance: 1, broken: 0 },
      equipment: { ready: 12, assigned: 0, maintenance: 0, broken: 2 },
      agents: 40,
      agents_on_duty: 31,
    },
  ],
  categories: [{ key: "fire_engine", kind: "vehicle", ready: 5, assigned: 2, maintenance: 1, broken: 0 }],
  skills: [{ key: "diving", agents: 6, ready: 4, expired: 1 }],
  can_list: true,
  can_edit: true,
  can_see_names: true,
};

export const UNITS: UnitRow[] = [
  {
    id: "u-1",
    name_ar: "وحدة صفاقس المدينة",
    name_fr: "Unité Sfax ville",
    kind: "unit",
    gouvernorat_code: 61,
    vehicles: 4,
    vehicles_ready: 3,
    equipment_ready: 6,
    equipment_broken: 1,
    agents: 20,
    agents_on_duty: 15,
    verified_at: null,
    verified_by_name: null,
    stale: true,
    can_edit: true,
  },
];

export const VEHICLE: Vehicle = {
  id: "v-1",
  unit_id: "u-1",
  unit_name: "وحدة صفاقس المدينة",
  gouvernorat_code: 61,
  category_key: "fire_engine",
  kind: "fire_engine",
  label: "إطفاء 12",
  code: "SF-12",
  specs: { capacity_l: 2000, four_wd: true },
  state: "ready",
  year: 2019,
  notes: null,
  version: 1,
  updated_at: "2026-10-20T08:00:00Z",
};

export const STOCK: StockLine = {
  id: "s-1",
  unit_id: "u-1",
  unit_name: "وحدة صفاقس المدينة",
  gouvernorat_code: 61,
  category_key: "pump",
  specs: { flow_lpm: 800 },
  qty_ready: 4,
  qty_broken: 1,
  notes: null,
  version: 1,
  updated_at: "2026-10-20T08:00:00Z",
};

export const AGENT: Agent = {
  id: "a-1",
  unit_id: "u-1",
  unit_name: "وحدة صفاقس المدينة",
  gouvernorat_code: 61,
  matricule: "M1234",
  full_name: "سامي الغواص",
  phone: "20000000",
  rank: "رقيب",
  availability: "on_duty",
  skills: [{ skill_key: "diving", level: 2, cert_expires: "2030-01-01", expired: false }],
  notes: null,
  version: 1,
  updated_at: "2026-10-20T08:00:00Z",
};

export const IMPORT_PREVIEW: InventoryImport = {
  format: "xlsx",
  gouvernorat_code: 61,
  applied: false,
  vehicles: { new: 2, changed: 1, unchanged: 0 },
  stock: { new: 1, changed: 0, unchanged: 0 },
  agents: { new: 3, changed: 0, unchanged: 1 },
  errors: [],
  warnings: [{ code: "year_invalid", entity: "vehicles", line: 4, value: "1900" }],
};
