import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makeVolunteer } from "../test/opsFixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { VolunteersPage } from "./VolunteersPage";

vi.mock("../components/LazyMap", () => ({ LazyMapView: () => <div data-testid="map" /> }));

const MANAGER = { ...OPERATOR_CLAIMS, realm_access: { roles: ["ops_manager"] } };

describe("VolunteersPage", () => {
  it("lists volunteers with status, skills and readiness", async () => {
    const api = fakeApi({
      volunteers: vi.fn(() =>
        Promise.resolve({
          items: [
            makeVolunteer(),
            makeVolunteer({ id: "v-2", full_name: "Nour Ben Ali", status: "approved", ready: true, ready_until: null }),
          ],
          next_cursor: null,
        }),
      ),
    });
    renderApp(<VolunteersPage />, { api, auth: fakeAuth(MANAGER), lang: "fr" });

    const table = await screen.findByRole("table", { name: "Liste des volontaires" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    const first = rows[0] as HTMLElement;
    expect(within(first).getByRole("link", { name: "Amel Jaziri" })).toHaveAttribute("href", "/volunteers/v-1");
    expect(within(first).getByText("En attente", { selector: ".chip" })).toBeInTheDocument();
    expect(within(first).getByRole("list", { name: "Compétences" })).toHaveTextContent(/Premiers secours.*Recherche et sauvetage/);
    expect(within(first).getByText("Non disponible")).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText("Disponible", { selector: ".tag" })).toBeInTheDocument();
    expect(screen.getByTestId("map")).toBeInTheDocument();
  });

  it("filters by status, skill, readiness and search text", async () => {
    const api = fakeApi();
    renderApp(<VolunteersPage />, { api, auth: fakeAuth(MANAGER), lang: "fr" });
    expect(await screen.findByText("Aucun volontaire avec ces critères.")).toBeInTheDocument();
    const filters = screen.getByRole("region", { name: "Filtrer les volontaires" });
    fireEvent.change(within(filters).getByLabelText("Statut"), { target: { value: "pending" } });
    fireEvent.change(within(filters).getByLabelText("Compétences"), { target: { value: "diving" } });
    fireEvent.change(within(filters).getByLabelText("Disponibilité immédiate"), { target: { value: "true" } });
    fireEvent.change(within(filters).getByLabelText("Recherche par nom ou téléphone"), { target: { value: "Amel" } });
    await waitFor(() =>
      expect(api.volunteers).toHaveBeenCalledWith(
        { status: "pending", skill: "diving", ready: true, gouvernorat_code: null, q: "Amel" },
        expect.objectContaining({ cursor: null }),
      ),
    );
  });
});
