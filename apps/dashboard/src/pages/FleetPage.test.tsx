import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Coverage } from "../lib/fleet";
import type { Vehicle } from "../lib/inventory";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { CoveragePage } from "./CoveragePage";
import { FleetPage } from "./FleetPage";

// OS3: the rooms set the operational state, the maintenance directorate the workshop and the retirement.
const MAINTENANCE = { ...OPERATOR_CLAIMS, realm_access: { roles: ["maintenance_officer"] } };

function vehicle(over: Partial<Vehicle> = {}): Vehicle {
  return {
    id: "v-1",
    unit_id: "u-1",
    unit_name: "Unité Sfax Ville",
    gouvernorat_code: 61,
    category_key: null,
    kind: "ambulance",
    label: "AMB-1",
    code: "SF-01",
    specs: {},
    state: "ready",
    year: 2019,
    notes: null,
    plate: "245 تونس 1234",
    odometer_km: 81200,
    version: 3,
    updated_at: "2026-11-10T08:00:00Z",
    ...over,
  };
}

function setupFleet(claims: Record<string, unknown>, rights: { edit: boolean; state: boolean; maintain: boolean }) {
  const api = fakeApi({
    fleetVehicles: vi.fn(() =>
      Promise.resolve({
        items: [vehicle(), vehicle({ id: "v-2", label: "AMB-2", state: "retired", retired_on: "2026-10-01", retire_decision: "ق-12" })],
        can_edit: rights.edit,
        can_set_state: rights.state,
        can_maintain: rights.maintain,
      }),
    ),
    inventoryUnits: vi.fn(() => Promise.resolve({ items: [] })),
    inventoryCatalogue: vi.fn(() => Promise.resolve({ items: [], can_manage: false })),
    setVehicleState: vi.fn(() => Promise.resolve(vehicle({ state: "broken" }))),
    startMaintenance: vi.fn(() => Promise.resolve(vehicle({ state: "maintenance" }))),
  });
  renderApp(<FleetPage view="vehicles" />, { api, auth: fakeAuth(claims), lang: "fr" });
  return api;
}

describe("FleetPage", () => {
  it("lets a room declare a breakdown with its fault, never the workshop", async () => {
    const api = setupFleet(OPERATOR_CLAIMS, { edit: false, state: true, maintain: false });
    const row = (await screen.findByText("AMB-1")).closest("tr") as HTMLElement;
    expect(screen.queryByText("AMB-2")).not.toBeInTheDocument();
    expect(within(row).queryByRole("button", { name: "Vers l’atelier" })).not.toBeInTheDocument();
    fireEvent.click(within(row).getByRole("button", { name: "État" }));
    const form = screen.getByRole("heading", { name: "État de AMB-1" }).closest("form") as HTMLElement;
    fireEvent.change(within(form).getByLabelText("État"), { target: { value: "broken" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    expect(api.setVehicleState).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Description de la panne"), { target: { value: "Pompe hors service" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    await waitFor(() =>
      expect(api.setVehicleState).toHaveBeenCalledWith("v-1", expect.objectContaining({ state: "broken", fault: "Pompe hors service", version: 3 })),
    );
  });

  it("lets the maintenance directorate send a vehicle to the workshop", async () => {
    const api = setupFleet(MAINTENANCE, { edit: true, state: false, maintain: true });
    const row = (await screen.findByText("AMB-1")).closest("tr") as HTMLElement;
    expect(within(row).queryByRole("button", { name: "État" })).not.toBeInTheDocument();
    fireEvent.click(within(row).getByRole("button", { name: "Vers l’atelier" }));
    fireEvent.change(screen.getByLabelText("Atelier"), { target: { value: "Atelier régional" } });
    fireEvent.change(screen.getByLabelText("Motif de l’entretien"), { target: { value: "Vidange et freins" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    await waitFor(() =>
      expect(api.startMaintenance).toHaveBeenCalledWith("v-1", {
        workshop: "Atelier régional",
        reason: "Vidange et freins",
        until: null,
        version: 3,
      }),
    );
  });
});

const COVERAGE: Coverage = {
  gouvernorat_code: 61,
  engine: "fallback",
  turnout_minutes: 2,
  targets: {
    medical: { urban: 10, periurban: 15, rural: 25 },
    road: { urban: 12, periurban: 18, rural: 30 },
    fire: { urban: 10, periurban: 15, rural: 25 },
    rescue: { urban: 15, periurban: 20, rural: 35 },
  },
  families: [
    { family: "medical", population: 1000, covered_population: 700, covered_pct: 70, baseline_pct: 90, ready: 2, fleet: 3, out: 1 },
  ],
  delegations: [],
  units: [],
  alerts: [
    { family: "medical", delegation_id: 7, delegation: "Agareb", population: 300, minutes: 31, target: 25, baseline_minutes: 14 },
  ],
  suggestions: [
    {
      family: "medical",
      vehicle_id: "v-9",
      label: "AMB-9",
      from_unit_id: "u-1",
      from_unit: "Sfax Ville",
      to_unit_id: "u-2",
      to_unit: "Agareb",
      gain_population: 300,
      newly_covered: ["Agareb"],
      lost: [],
      version: 4,
    },
  ],
  computed_at: "2026-11-11T08:00:00Z",
  assumptions: [],
};

describe("CoveragePage", () => {
  it("shows the uncovered places and sends the suggested vehicle as reinforcement", async () => {
    const api = fakeApi({
      coverage: vi.fn(() => Promise.resolve(COVERAGE)),
      setVehicleState: vi.fn(() => Promise.resolve(vehicle({ id: "v-9", state: "reinforcement" }))),
    });
    renderApp(<CoveragePage />, { api, lang: "fr" });
    expect(await screen.findByText(/Agareb \(300 hab\.\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Envoyer en renfort" }));
    await waitFor(() =>
      expect(api.setVehicleState).toHaveBeenCalledWith(
        "v-9",
        expect.objectContaining({ state: "reinforcement", host_unit_id: "u-2", suggested_gain: 300, version: 4 }),
      ),
    );
  });
});
