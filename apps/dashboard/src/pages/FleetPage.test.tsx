import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Coverage, FleetReport, RepositionOrder } from "../lib/fleet";
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

function setupFleet(
  claims: Record<string, unknown>,
  rights: { edit: boolean; state: boolean; maintain: boolean },
  view: "vehicles" | "maintenance" = "vehicles",
  first: Partial<Vehicle> = {},
) {
  const api = fakeApi({
    fleetVehicles: vi.fn(() =>
      Promise.resolve({
        items: [vehicle(first), vehicle({ id: "v-2", label: "AMB-2", state: "retired", retired_on: "2026-10-01", retire_decision: "ق-12" })],
        can_edit: rights.edit,
        can_set_state: rights.state,
        can_maintain: rights.maintain,
      }),
    ),
    inventoryUnits: vi.fn(() => Promise.resolve({ items: [] })),
    inventoryCatalogue: vi.fn(() => Promise.resolve({ items: [], can_manage: false })),
    setVehicleState: vi.fn(() => Promise.resolve(vehicle({ state: "broken" }))),
    startMaintenance: vi.fn(() => Promise.resolve(vehicle({ state: "maintenance" }))),
    endMaintenance: vi.fn(() => Promise.resolve(vehicle({ state: "ready" }))),
  });
  renderApp(<FleetPage view={view} />, { api, auth: fakeAuth(claims), lang: "fr" });
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

describe("FleetPage, OS3-3", () => {
  it("takes the cost of the stay at the exit of the workshop", async () => {
    const api = setupFleet(MAINTENANCE, { edit: true, state: false, maintain: true }, "maintenance", { state: "maintenance" });
    const row = (await screen.findByText("AMB-1")).closest("tr") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Sortie d’atelier" }));
    fireEvent.change(screen.getByLabelText("Type d'entretien"), { target: { value: "repair" } });
    fireEvent.change(screen.getByLabelText("Pièces (DT)"), { target: { value: "12,5x" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    expect(await screen.findByText("Montant positif, trois décimales au plus.")).toBeInTheDocument();
    expect(api.endMaintenance).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Pièces (DT)"), { target: { value: "1240,500" } });
    fireEvent.change(screen.getByLabelText("Main-d'œuvre (DT)"), { target: { value: "180" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    await waitFor(() =>
      expect(api.endMaintenance).toHaveBeenCalledWith(
        "v-1",
        expect.objectContaining({ maint_kind: "repair", cost_parts: "1240.500", cost_labour: "180", cost_external: null, version: 3 }),
      ),
    );
  });

  it("shows the monthly readiness and cost per gouvernorat", async () => {
    const row = {
      gouvernorat_code: 61,
      name_ar: "صفاقس",
      name_fr: "Sfax",
      point: [10.7, 34.8] as [number, number],
      vehicles: 12,
      vehicle_days: 360,
      down_days: 54,
      readiness_pct: 85,
      workshop_entries: 3,
      retired: 1,
      cost_parts: "2000.000",
      cost_labour: "500.000",
      cost_external: "0.000",
      cost_total: "2500.000",
      cost_per_vehicle: "208.333",
      series: [
        { month: "2026-10", readiness_pct: 78.2, cost_total: "900.000" },
        { month: "2026-11", readiness_pct: 85, cost_total: "2500.000" },
      ],
    };
    const report: FleetReport = {
      month: "2026-11",
      months: ["2026-10", "2026-11"],
      rows: [row],
      total: null,
      costly: [{ resource_id: "v-1", label: "AMB-1", plate: null, gouvernorat_code: 61, cost_total: "1420.500", stays: 1 }],
      red_below: 80,
      amber_below: 85,
      computed_at: "2026-11-13T08:00:00Z",
    };
    const api = fakeApi({ fleetReport: vi.fn(() => Promise.resolve(report)) });
    renderApp(<FleetPage view="report" />, { api, auth: fakeAuth(MAINTENANCE), lang: "fr" });
    const table = (await screen.findByRole("heading", { name: "Gouvernorat" })).closest("section") as HTMLElement;
    const line = within(table).getByText("Sfax").closest("tr") as HTMLElement;
    expect(within(line).getByText("12")).toBeInTheDocument();
    expect(within(line).getByText(/85/).className).toContain("tone-green");
    expect(screen.getByText(/AMB-1/)).toBeInTheDocument();
    expect(api.fleetReport).toHaveBeenCalledWith(expect.objectContaining({ gouvernorat: null }), expect.anything());
  });
});

const COVERAGE: Coverage = {
  gouvernorat_code: 61,
  engine: "fallback",
  turnout_minutes: 2,
  turnout_mode: "measured",
  neighbours: false,
  neighbour_m: 40000,
  targets: {
    medical: { urban: 10, periurban: 15, rural: 25 },
    road: { urban: 12, periurban: 18, rural: 30 },
    fire: { urban: 10, periurban: 15, rural: 25 },
    rescue: { urban: 15, periurban: 20, rural: 35 },
  },
  families: [
    { family: "medical", population: 1000, covered_population: 700, covered_pct: 70, baseline_pct: 90, ready: 2, fleet: 3, out: 1, own_pct: 70 },
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
      from_gouvernorat_code: 61,
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

describe("CoveragePage, OS3-1", () => {
  it("follows the orders sent to the crews and flags the one nobody opened", async () => {
    const order: RepositionOrder = {
      id: "o-1",
      resource_id: "v-9",
      label: "AMB-9",
      plate: null,
      kind: "reinforce",
      from_unit_id: "u-1",
      from_unit: "Sfax Ville",
      to_unit_id: "u-2",
      to_unit: "Agareb",
      from_point: null,
      to_point: null,
      gouvernorat_code: 61,
      host_gouvernorat_code: 61,
      note: null,
      gain_population: 300,
      leader_name: "Ali",
      pushed: true,
      created_by_name: "Salle Sfax",
      created_at: "2026-11-13T08:00:00Z",
      seen_at: null,
      seen_by_name: null,
      departed_at: null,
      arrived_at: null,
      closed_at: null,
      close_reason: null,
      state: "sent",
      overdue: true,
    };
    const api = fakeApi({
      coverage: vi.fn(() => Promise.resolve(COVERAGE)),
      repositionOrders: vi.fn(() => Promise.resolve({ items: [order], ack_minutes: 2 })),
    });
    renderApp(<CoveragePage />, { api, lang: "fr" });
    expect(await screen.findByText("AMB-9 : de Sfax Ville à Agareb")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Non vu après 2 min");
  });
});
