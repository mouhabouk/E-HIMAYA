import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { makeResource, makeUnit } from "../test/opsFixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { ResourcesPage } from "./ResourcesPage";

const MANAGER = { ...OPERATOR_CLAIMS, realm_access: { roles: ["ops_manager"] } };

function setup(claims: Record<string, unknown> = MANAGER, overrides: Parameters<typeof fakeApi>[0] = {}) {
  const api = fakeApi({
    units: vi.fn(() => Promise.resolve([makeUnit()])),
    resources: vi.fn(() =>
      Promise.resolve({
        items: [
          makeResource(),
          makeResource({
            id: "res-2",
            label: "AMB-3",
            kind: "ambulance",
            status: "assigned",
            assignment: { id: "a-1", incident_id: "i-7", status: "en_route" },
          }),
        ],
        next_cursor: null,
      }),
    ),
    resourceSummary: vi.fn(() =>
      Promise.resolve({ by_kind: { fire_engine: { available: 1 }, ambulance: { assigned: 1 } } }),
    ),
    ...overrides,
  });
  return renderApp(<ResourcesPage />, { api, auth: fakeAuth(claims), lang: "fr" });
}

describe("ResourcesPage", () => {
  it("shows the availability summary, resources and units", async () => {
    setup();
    const summary = await screen.findByRole("table", { name: "Nombre de moyens par type et statut" });
    const ambulance = within(summary).getByRole("row", { name: /Ambulance/ });
    expect(within(ambulance).getAllByRole("cell").map((c) => c.textContent)).toEqual(["0", "1", "0"]);

    const list = await screen.findByRole("table", { name: "Moyens" });
    const rows = within(list).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    expect(within(rows[0] as HTMLElement).getByText("Disponible", { selector: ".chip" })).toBeInTheDocument();
    const busy = rows[1] as HTMLElement;
    expect(within(busy).getByText("Engagé", { selector: ".chip" })).toBeInTheDocument();
    expect(within(busy).getByRole("link", { name: "Ouvrir l’incident" })).toHaveAttribute("href", "/incidents/i-7");

    const units = screen.getByRole("table", { name: "Unités" });
    expect(within(units).getByText("Unité Sfax Ville")).toBeInTheDocument();
  });

  it("filters the list by status", async () => {
    const { api } = setup();
    await screen.findByRole("table", { name: "Moyens" });
    const group = screen.getByRole("group", { name: "Filtrer les moyens" });
    fireEvent.change(within(group).getByLabelText("Statut"), { target: { value: "out_of_service" } });
    await waitFor(() =>
      expect(api.resources).toHaveBeenCalledWith(
        expect.objectContaining({ status: "out_of_service" }),
        expect.objectContaining({ cursor: null }),
      ),
    );
  });

  it("creates a resource and validates the coordinates", async () => {
    const { api } = setup(MANAGER, { createResource: vi.fn(() => Promise.resolve(makeResource({ id: "res-9" }))) });
    fireEvent.click(await screen.findByRole("button", { name: "Ajouter un moyen" }));
    const form = screen.getByRole("form", { name: "Nouveau moyen" });
    fireEvent.change(within(form).getByLabelText("Indicatif"), { target: { value: "CIT-4" } });
    fireEvent.change(within(form).getByLabelText("Type"), { target: { value: "water_tanker" } });
    fireEvent.change(within(form).getByLabelText("Latitude"), { target: { value: "34,75" } });
    fireEvent.click(within(form).getByRole("button", { name: "Enregistrer" }));
    expect(within(form).getByRole("alert")).toHaveTextContent(/vérifiez les coordonnées/);
    expect(api.createResource).not.toHaveBeenCalled();

    fireEvent.change(within(form).getByLabelText("Longitude"), { target: { value: "10.77" } });
    fireEvent.click(within(form).getByRole("button", { name: "Enregistrer" }));
    await waitFor(() =>
      expect(api.createResource).toHaveBeenCalledWith({
        unit_id: "u-1",
        kind: "water_tanker",
        label: "CIT-4",
        status: "available",
        notes: null,
        location: { lat: 34.75, lon: 10.77 },
        version: undefined,
      }),
    );
    await waitFor(() => expect(screen.queryByRole("form", { name: "Nouveau moyen" })).not.toBeInTheDocument());
  });

  it("shows the label_taken error", async () => {
    setup(MANAGER, { createResource: vi.fn(() => Promise.reject(new ApiError(409, "label_taken"))) });
    fireEvent.click(await screen.findByRole("button", { name: "Ajouter un moyen" }));
    const form = screen.getByRole("form", { name: "Nouveau moyen" });
    fireEvent.change(within(form).getByLabelText("Indicatif"), { target: { value: "FPT-12" } });
    fireEvent.click(within(form).getByRole("button", { name: "Enregistrer" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("Cet indicatif est déjà utilisé");
  });

  it("keeps an assigned resource's status and unit locked when editing", async () => {
    setup();
    fireEvent.click(await screen.findByRole("button", { name: "Modifier AMB-3" }));
    const form = screen.getByRole("form", { name: "Modifier le moyen AMB-3" });
    expect(within(form).getByLabelText("Statut")).toBeDisabled();
    expect(within(form).getByLabelText("Unité")).toBeDisabled();
  });

  it("is read-only for an operator", async () => {
    setup(OPERATOR_CLAIMS);
    await screen.findByRole("table", { name: "Moyens" });
    expect(screen.queryByRole("button", { name: "Ajouter un moyen" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Modifier/ })).not.toBeInTheDocument();
  });
});
