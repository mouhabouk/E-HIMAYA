import { vi } from "vitest";
import type { AgentListing, inventoryApi, Listing } from "../lib/inventory";
import { first } from "./crisisData";
import {
  AGENT,
  BOUNDARIES,
  CATALOGUE,
  IMPORT_PREVIEW,
  OVERVIEW,
  SEARCH_RESULT,
  STOCK,
  TRANSFER_IN,
  TRANSFER_OUT,
  UNITS,
  VEHICLE,
} from "./inventoryData";

export * from "./inventoryData";

type InventoryApi = ReturnType<typeof inventoryApi>;

const listing = <T,>(items: T[]): Listing<T> => ({ items, can_edit: true });
const agents: AgentListing = { items: [AGENT], can_edit: true, can_see_names: true, can_export_names: true };

export function fakeInventoryApi(): InventoryApi {
  const download = () => Promise.resolve({ blob: new Blob(["x"]), filename: "inventory.csv" });
  return {
    inventoryCatalogue: vi.fn(() => Promise.resolve(CATALOGUE)),
    createCategory: vi.fn(() => Promise.resolve(first(CATALOGUE.items))),
    updateCategory: vi.fn(() => Promise.resolve(first(CATALOGUE.items))),
    inventoryOverview: vi.fn(() => Promise.resolve(OVERVIEW)),
    inventoryUnits: vi.fn(() => Promise.resolve({ items: UNITS })),
    verifyUnit: vi.fn(() => Promise.resolve({ ...first(UNITS), stale: false, verified_at: "2026-10-28T09:00:00Z" })),
    vehicles: vi.fn(() => Promise.resolve(listing([VEHICLE]))),
    saveVehicle: vi.fn(() => Promise.resolve(VEHICLE)),
    deleteVehicle: vi.fn(() => Promise.resolve(undefined)),
    stock: vi.fn(() => Promise.resolve(listing([STOCK]))),
    saveStock: vi.fn(() => Promise.resolve(STOCK)),
    deleteStock: vi.fn(() => Promise.resolve(undefined)),
    agents: vi.fn(() => Promise.resolve(agents)),
    saveAgent: vi.fn(() => Promise.resolve(AGENT)),
    deleteAgent: vi.fn(() => Promise.resolve(undefined)),
    transfers: vi.fn(() => Promise.resolve([TRANSFER_IN, TRANSFER_OUT])),
    requestTransfer: vi.fn(() => Promise.resolve(TRANSFER_OUT)),
    acceptTransfer: vi.fn(() => Promise.resolve({ ...TRANSFER_IN, status: "accepted" as const, to_unit_name: "وحدة صفاقس المدينة" })),
    refuseTransfer: vi.fn(() => Promise.resolve({ ...TRANSFER_IN, status: "refused" as const })),
    cancelTransfer: vi.fn(() => Promise.resolve({ ...TRANSFER_OUT, status: "cancelled" as const })),
    inventoryRevisions: vi.fn(() => Promise.resolve({ items: [] })),
    importInventory: vi.fn(() => Promise.resolve(IMPORT_PREVIEW)),
    inventoryTemplate: vi.fn(download),
    exportInventory: vi.fn(download),
    searchInventory: vi.fn(() => Promise.resolve(SEARCH_RESULT)),
    inventoryBoundaries: vi.fn(() => Promise.resolve(BOUNDARIES)),
    exportSearch: vi.fn(download),
  };
}
