import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makeVolunteerDetail } from "../test/opsFixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { VolunteerDetailPage } from "./VolunteerDetailPage";

const MANAGER = { ...OPERATOR_CLAIMS, realm_access: { roles: ["ops_manager"] } };

describe("VolunteerDetailPage", () => {
  const route = "/volunteers/:id";
  const path = "/volunteers/v-1";

  it("requires a reason to reject an application", async () => {
    const api = fakeApi({
      volunteer: vi.fn(() => Promise.resolve(makeVolunteerDetail())),
      reviewVolunteer: vi.fn(() => Promise.resolve(makeVolunteerDetail({ status: "rejected" }))),
    });
    renderApp(<VolunteerDetailPage />, { api, auth: fakeAuth(MANAGER), lang: "fr", route, path });

    expect(await screen.findByRole("heading", { level: 1, name: "Amel Jaziri" })).toBeInTheDocument();
    expect(screen.getByText("amel@example.tn")).toBeInTheDocument();
    const group = await screen.findByRole("group", { name: "Choisir la décision" });
    expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual(["Valider", "Refuser"]);
    fireEvent.click(within(group).getByRole("button", { name: "Refuser" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la décision" }));
    expect(screen.getByText("Le motif est requis pour cette décision.")).toBeInTheDocument();
    expect(api.reviewVolunteer).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Motif"), { target: { value: "Dossier incomplet" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la décision" }));
    await waitFor(() => expect(api.reviewVolunteer).toHaveBeenCalledWith("v-1", "reject", "Dossier incomplet"));
    expect(await screen.findByText("Décision enregistrée.")).toBeInTheDocument();
    expect(await screen.findByText("Refusé", { selector: ".chip" })).toBeInTheDocument();
  });

  it("approves without a reason", async () => {
    const api = fakeApi({
      volunteer: vi.fn(() => Promise.resolve(makeVolunteerDetail())),
      reviewVolunteer: vi.fn(() => Promise.resolve(makeVolunteerDetail({ status: "approved" }))),
    });
    renderApp(<VolunteerDetailPage />, { api, auth: fakeAuth(MANAGER), lang: "fr", route, path });
    fireEvent.click(await screen.findByRole("button", { name: "Valider" }));
    expect(screen.getByLabelText("Motif (facultatif)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la décision" }));
    await waitFor(() => expect(api.reviewVolunteer).toHaveBeenCalledWith("v-1", "approve", ""));
  });

  it("hides the review for an operator", async () => {
    const api = fakeApi({ volunteer: vi.fn(() => Promise.resolve(makeVolunteerDetail())) });
    renderApp(<VolunteerDetailPage />, { api, lang: "fr", route, path });
    expect(await screen.findByRole("heading", { level: 1, name: "Amel Jaziri" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Choisir la décision" })).not.toBeInTheDocument();
  });
});
