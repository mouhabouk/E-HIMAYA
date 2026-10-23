// covers: phase B1 (docs/phase-b/design.md §2ter): contact us inbox by kind, status and gouvernorat; answer and note.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ContactDetail, ContactSummary } from "../lib/contact";
import { allowedActions } from "../lib/contact";
import { canHandleContact } from "../lib/roles";
import { fakeApi, fakeAuth, fakeContactApi, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { ContactInboxPage } from "./ContactInboxPage";

const MANAGER = { ...OPERATOR_CLAIMS, realm_access: { roles: ["ops_manager"] } };

const SUMMARY: ContactSummary = {
  id: "c1",
  number: "CT-2026-000042",
  kind: "access_info",
  status: "received",
  subject: "Budget des centres",
  gouvernorat_code: 61,
  created_at: "2026-10-01T09:00:00Z",
  updated_at: "2026-10-01T09:00:00Z",
  due_at: "2026-10-21T09:00:00Z",
  overdue: true,
  assigned_name: null,
  anonymous: false,
  version: 1,
};

const DETAIL: ContactDetail = {
  ...SUMMARY,
  name: "Karim Trabelsi",
  phone: "+21622333444",
  email: null,
  message: "Je souhaite consulter le budget 2025 des centres de Sfax.",
  answer: null,
  answered_at: null,
  closed_at: null,
  locale: "fr",
  platform: "android",
  events: [
    {
      id: "e1",
      action: "created",
      status: "received",
      gouvernorat_code: 61,
      at: "2026-10-01T09:00:00Z",
      note: null,
      visible: true,
      actor_name: null,
    },
  ],
};

function setup(overrides: Partial<ReturnType<typeof fakeContactApi>> = {}) {
  const contact = fakeContactApi();
  contact.contactInbox.mockResolvedValue({
    items: [SUMMARY],
    truncated: false,
    open_by_kind: { access_info: 1, hazard: 0, question: 0, suggestion: 0, app_problem: 0, partnership: 0 },
    overdue: 1,
  });
  contact.contactRequest.mockResolvedValue(DETAIL);
  const api = fakeApi({ ...contact, ...overrides });
  renderApp(<ContactInboxPage />, { api, auth: fakeAuth(MANAGER), lang: "fr" });
  return { api, contact };
}

describe("contact rules", () => {
  it("actions follow the status, roles open the inbox", () => {
    expect(allowedActions("received")).toEqual(["take", "answer", "note", "move", "close", "reject"]);
    expect(allowedActions("closed")).toEqual(["note", "reopen"]);
    expect(canHandleContact(["operator"])).toBe(false);
    expect(canHandleContact(["content_editor"])).toBe(true);
  });
});

describe("ContactInboxPage", () => {
  it("lists requests with their deadline and filters by kind", async () => {
    const { contact } = setup();
    expect(await screen.findByText("CT-2026-000042")).toBeInTheDocument();
    expect(screen.getAllByText("En retard").length).toBeGreaterThan(0);
    expect(screen.getByText("En retard uniquement (1)")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "hazard" } });
    await waitFor(() =>
      expect(contact.contactInbox).toHaveBeenLastCalledWith(
        expect.objectContaining({ kind: "hazard", status: "open" }),
        expect.anything(),
      ),
    );
  });

  it("opens a request, answers it and refuses an empty note", async () => {
    const contactAct = vi.fn(() =>
      Promise.resolve({ ...DETAIL, status: "answered" as const, answer: "Voici le budget.", version: 2 }),
    );
    setup({ contactAct });
    fireEvent.click(await screen.findByText("CT-2026-000042"));
    expect(await screen.findByText("Karim Trabelsi")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Ajouter une note" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    expect(await screen.findByText("Entre 5 et 3000 caractères.")).toBeInTheDocument();
    expect(contactAct).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Annuler" }));

    fireEvent.click(screen.getByRole("button", { name: "Répondre" }));
    fireEvent.change(screen.getByLabelText("Réponse au demandeur"), { target: { value: "Voici le budget." } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    await waitFor(() =>
      expect(contactAct).toHaveBeenCalledWith("c1", { version: 1, action: "answer", text: "Voici le budget." }),
    );
    expect(await screen.findByText("Réponse envoyée")).toBeInTheDocument();
  });
});
