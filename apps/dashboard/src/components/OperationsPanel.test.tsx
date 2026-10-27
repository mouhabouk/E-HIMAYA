import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makeIncidentDetail } from "../test/fixtures";
import { makeAssignment, makeCallout, makeResource } from "../test/opsFixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { OperationsPanel } from "./OperationsPanel";

const MANAGER = { ...OPERATOR_CLAIMS, realm_access: { roles: ["ops_manager"] } };
const LOCAL = { sub: "l-1", name: "Karim Local", realm_access: { roles: ["local_committee"] }, gouvernorat_code: "61" };

describe("OperationsPanel", () => {
  it("assigns an available resource with an order", async () => {
    const api = fakeApi({
      resources: vi.fn(() => Promise.resolve({ items: [makeResource()], next_cursor: null })),
      createAssignment: vi.fn(() => Promise.resolve(makeAssignment())),
    });
    renderApp(<OperationsPanel incident={makeIncidentDetail({ assignments: [], callouts: [] })} />, { api, lang: "fr" });

    expect(screen.getByText("Aucun engagement actif.")).toBeInTheDocument();
    const form = await screen.findByRole("form", { name: "Engager un moyen" });
    const select = within(form).getByLabelText("Moyen");
    await within(select).findByRole("option", { name: /FPT-12 · Fourgon d’incendie/ });
    fireEvent.change(select, { target: { value: "res-1" } });
    fireEvent.change(within(form).getByLabelText("Ordre"), { target: { value: "Rejoindre le dépôt" } });
    fireEvent.click(within(form).getByRole("button", { name: "Émettre l’ordre" }));
    await waitFor(() => expect(api.createAssignment).toHaveBeenCalledWith("i-1", "res-1", "Rejoindre le dépôt", ""));
    expect(api.resources).toHaveBeenCalledWith({ status: "available" }, expect.objectContaining({ limit: 200 }));
  });

  it("moves an assignment along its allowed transitions", async () => {
    const api = fakeApi({ updateAssignment: vi.fn(() => Promise.resolve(makeAssignment({ status: "en_route" }))) });
    renderApp(<OperationsPanel incident={makeIncidentDetail({ assignments: [makeAssignment()], callouts: [] })} />, {
      api,
      lang: "fr",
    });

    const table = screen.getByRole("table", { name: "Engagements actifs" });
    expect(within(table).getByText("Ordonné", { selector: ".chip" })).toBeInTheDocument();
    expect(within(table).queryByRole("button", { name: /Terminé$/ })).not.toBeInTheDocument();
    fireEvent.change(await within(table).findByLabelText("Note (facultative)"), { target: { value: "Départ" } });
    fireEvent.click(within(table).getByRole("button", { name: "FPT-12 · Fourgon d’incendie : En route" }));
    await waitFor(() => expect(api.updateAssignment).toHaveBeenCalledWith("a-1", "en_route", "Départ"));
  });

  it("calls the nearest volunteers out, or the picked ones", async () => {
    const api = fakeApi({
      volunteerSuggestions: vi.fn(() =>
        Promise.resolve([
          { volunteer_id: "v-2", full_name: "Nour Ben Ali", phone: null, distance_m: 2500, skills: ["first_aid" as const], busy: true },
        ]),
      ),
      createCallout: vi.fn(() => Promise.resolve(makeCallout())),
    });
    renderApp(
      <OperationsPanel incident={makeIncidentDetail({ assignments: [], callouts: [makeCallout()] })} />,
      { api, lang: "fr" },
    );

    const callout = screen.getByRole("article", { name: "Appel : Premiers secours" });
    expect(within(callout).getByText("Acceptations : 1 sur 2")).toBeInTheDocument();
    expect(await within(callout).findByRole("button", { name: "Confirmer l’arrivée de Amel Jaziri" })).toBeInTheDocument();

    const form = screen.getByRole("form", { name: "Nouvel appel" });
    const pick = await within(form).findByRole("checkbox", { name: /Nour Ben Ali/ });
    expect(within(form).getByText(/occupé par un autre appel/)).toBeInTheDocument();
    fireEvent.click(pick);
    fireEvent.click(within(form).getByRole("button", { name: "Appeler la sélection (1)" }));
    await waitFor(() =>
      expect(api.createCallout).toHaveBeenCalledWith("i-1", {
        skill: "first_aid",
        requested: 2,
        radius_km: 30,
        message: null,
        volunteer_ids: ["v-2"],
      }),
    );
    expect(await within(form).findByText("Appel envoyé.")).toBeInTheDocument();
  });

  it("blocks closing while assignments are active", async () => {
    renderApp(<OperationsPanel incident={makeIncidentDetail({ assignments: [makeAssignment()], callouts: [] })} />, {
      auth: fakeAuth(MANAGER),
      lang: "fr",
    });
    expect(await screen.findByText(/Des engagements sont actifs \(1\)/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Clôturer l’incident" })).not.toBeInTheDocument();
  });

  it("closes with a summary after a confirmation", async () => {
    const closed = makeIncidentDetail({ status: "closed", assignments: [], callouts: [] });
    const api = fakeApi({ closeIncident: vi.fn(() => Promise.resolve(closed)) });
    renderApp(
      <OperationsPanel
        incident={makeIncidentDetail({ assignments: [makeAssignment({ status: "released" })], callouts: [] })}
      />,
      { api, auth: fakeAuth(MANAGER), lang: "fr" },
    );

    fireEvent.click(await screen.findByRole("button", { name: "Clôturer l’incident" }));
    expect(screen.getByText(/La synthèse fait entre 10 et 5000 caractères/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Synthèse de l’intervention"), {
      target: { value: "Feu maîtrisé en 40 minutes, pas de victime." },
    });
    fireEvent.change(screen.getByLabelText("Secourus"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Clôturer l’incident" }));
    expect(api.closeIncident).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/seront clos/);
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la clôture" }));
    await waitFor(() =>
      expect(api.closeIncident).toHaveBeenCalledWith("i-1", {
        outcome: "resolved",
        summary: "Feu maîtrisé en 40 minutes, pas de victime.",
        casualties: { rescued: 3, injured: 0, deceased: 0, evacuated: 0 },
        lessons: null,
      }),
    );
  });

  it("is read-only for a local committee", () => {
    renderApp(
      <OperationsPanel
        incident={makeIncidentDetail({
          title: "Feu au dépôt",
          assignments: [makeAssignment()],
          callouts: [makeCallout()],
        })}
      />,
      { auth: fakeAuth(LOCAL), lang: "fr" },
    );
    expect(screen.getByText("Feu au dépôt")).toBeInTheDocument();
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByText("Texte de la note")).not.toBeInTheDocument();
  });
});
