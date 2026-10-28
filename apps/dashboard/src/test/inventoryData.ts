import type { FeatureCollection } from "geojson";
import type {
  Agent,
  Catalogue,
  InventoryImport,
  Overview,
  SearchResult,
  StockLine,
  UnitRow,
  Vehicle,
} from "../lib/inventory";

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

/** Phase R2: fire engines of 2000 L or more across the country ([SIM] figures). */
export const SEARCH_RESULT: SearchResult = {
  what: "vehicles",
  total: 9,
  ready: 7,
  gouvernorats: [
    {
      code: 11,
      name_ar: "تونس",
      name_fr: "Tunis",
      name_en: "Tunis",
      lat: 36.82,
      lon: 10.17,
      total: 6,
      ready: 5,
      units: [
        { id: "u-11a", name_ar: "وحدة تونس المدينة", name_fr: "Unité Tunis ville", lat: 36.8, lon: 10.18, total: 4, ready: 3 },
        { id: "u-11b", name_ar: "وحدة باب سعدون", name_fr: "Unité Bab Saadoun", lat: 36.81, lon: 10.15, total: 2, ready: 2 },
      ],
    },
    {
      code: 61,
      name_ar: "صفاقس",
      name_fr: "Sfax",
      name_en: "Sfax",
      lat: 34.74,
      lon: 10.76,
      total: 3,
      ready: 2,
      units: [{ id: "u-1", name_ar: "وحدة صفاقس المدينة", name_fr: "Unité Sfax ville", lat: 34.74, lon: 10.76, total: 3, ready: 2 }],
    },
    { code: 23, name_ar: "بنزرت", name_fr: "Bizerte", name_en: "Bizerte", lat: 37.27, lon: 9.87, total: 0, ready: 0, units: [] },
  ],
};

const square = (lon: number, lat: number): [number, number][][] => [
  [
    [lon - 0.3, lat - 0.3],
    [lon + 0.3, lat - 0.3],
    [lon + 0.3, lat + 0.3],
    [lon - 0.3, lat + 0.3],
    [lon - 0.3, lat - 0.3],
  ],
];

export const BOUNDARIES: FeatureCollection = {
  type: "FeatureCollection",
  features: [
    { type: "Feature", id: 11, properties: { code: 11 }, geometry: { type: "Polygon", coordinates: square(10.17, 36.82) } },
    { type: "Feature", id: 61, properties: { code: 61 }, geometry: { type: "Polygon", coordinates: square(10.76, 34.74) } },
    { type: "Feature", id: 23, properties: { code: 23 }, geometry: { type: "Polygon", coordinates: square(9.87, 37.27) } },
  ],
};
