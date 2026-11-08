// covers: phase H1 (docs/phase-h/design-h.md): the personnel department records the staff, their file and their
// absences; the operations rooms read the kind of an absence and the general strength, never the references.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Absence, AgentFile, PersonnelAgent, Strength } from "../lib/personnelApi";
import { canManagePersonnel, canReadPersonnel, hasDashboardAccess, landingPath } from "../lib/roles";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { PersonnelFilePage, PersonnelPage } from "./PersonnelPage";

const OFFICER = { ...OPERATOR_CLAIMS, realm_access: { roles: ["personnel_officer"] } };

function agent(overrides: Partial<PersonnelAgent> = {}): PersonnelAgent {
  return {
    id: "a-1",
    matricule: "P1234",
    full_name: "Amine Ben Salah",
    rank: "Caporal",
    post: "Conducteur",
    category: "intervention",
    unit_id: "u-1",
    unit_name: "Unité de Gabès",
    gouvernorat_code: 61,
    phone: null,
    absence: { id: "ab-1", kind: "mission", starts_on: "2026-11-07", ends_on: "2026-11-12" },
    version: 1,
    ...overrides,
  };
}

function absence(overrides: Partial<Absence> = {}): Absence {
  return {
    id: "ab-1",
    agent_id: "a-1",
    matricule: "P1234",
    full_name: "Amine Ben Salah",
    unit_id: "u-1",
    unit_name: "Unité de Gabès",
    gouvernorat_code: 61,
    kind: "sick",
    starts_on: "2026-11-03",
    ends_on: "2026-11-05",
    days: 3,
    reference: null,
    note: null,
    created_by_name: null,
    created_at: null,
    cancelled_at: null,
    cancel_reason: null,
    version: 1,
    ...overrides,
  };
}

describe("Personnel", () => {
  it("gives the personnel department its own space and the rooms a reading", () => {
    expect(canManagePersonnel(["personnel_officer"])).toBe(true);
    expect(canManagePersonnel(["ops_manager"])).toBe(false);
    expect(canReadPersonnel(["operator"])).toBe(true);
    expect(canReadPersonnel(["sysadmin"])).toBe(false);
    expect(canReadPersonnel(["governor"])).toBe(false);
    expect(hasDashboardAccess(["personnel_officer"])).toBe(true);
    expect(landingPath(["personnel_officer"])).toBe("/personnel");
  });

  it("shows a room the kind of absence, without a link to the file", async () => {
    const api = fakeApi({
      personnelAgents: vi.fn(() => Promise.resolve({ on: "2026-11-08", items: [agent()], can_edit: false })),
    });
    renderApp(<PersonnelPage tab="agents" />, { api, lang: "fr" });
    const row = (await screen.findByText("Amine Ben Salah")).closest("tr");
    if (!row) throw new Error("no row");
    expect(within(row).getByText("En mission")).toBeInTheDocument();
    expect(within(row).queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ajouter un agent" })).not.toBeInTheDocument();
  });

  it("lets the department record an absence", async () => {
    const createAbsence = vi.fn(() => Promise.resolve(absence()));
    const api = fakeApi({
      personnelAgents: vi.fn(() =>
        Promise.resolve({ on: "2026-11-08", items: [agent({ absence: null })], can_edit: true }),
      ),
      createAbsence,
    });
    renderApp(<PersonnelPage tab="absences" />, { api, auth: fakeAuth(OFFICER), lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Saisir une absence" }));
    const form = (await screen.findByRole("heading", { name: "Saisir une absence" })).closest("form");
    if (!form) throw new Error("no form");
    const select = within(form).getByRole("combobox", { name: "Nom" });
    await screen.findByRole("option", { name: /Amine Ben Salah/ });
    fireEvent.change(select, { target: { value: "a-1" } });
    fireEvent.change(within(form).getByRole("combobox", { name: "Nature" }), { target: { value: "sick" } });
    expect(screen.getByText(/Aucun diagnostic/)).toBeInTheDocument();
    fireEvent.click(within(form).getByRole("button", { name: "Enregistrer" }));
    await waitFor(() =>
      expect(createAbsence).toHaveBeenCalledWith(expect.objectContaining({ agent_id: "a-1", kind: "sick" })),
    );
  });

  it("counts room staff apart from those ready to intervene", async () => {
    const count = (total: number, absent: number) => ({ total, absent, present: total - absent, by_kind: {} });
    const data: Strength = {
      on: "2026-11-08",
      units: [
        {
          unit_id: "u-1",
          unit_name: "Unité de Gabès",
          gouvernorat_code: 61,
          intervention: { ...count(12, 3), by_kind: { annual: 2, mission: 1 } },
          room: count(4, 0),
          admin: count(2, 1),
        },
      ],
      total: {
        unit_id: null,
        unit_name: "",
        gouvernorat_code: 61,
        intervention: { ...count(12, 3), by_kind: { annual: 2, mission: 1 } },
        room: count(4, 0),
        admin: count(2, 1),
      },
    };
    renderApp(<PersonnelPage tab="strength" />, { api: fakeApi({ strength: vi.fn(() => Promise.resolve(data)) }), lang: "fr" });
    const ready = (await screen.findByText("Prêts à intervenir")).closest(".kpi");
    if (!ready) throw new Error("no kpi");
    expect(within(ready as HTMLElement).getByText("9")).toBeInTheDocument();
    expect(screen.getByText("Congé annuel: 2")).toBeInTheDocument();
  });

  it("shows the department the file with its sanctions, rewards and references", async () => {
    const file: AgentFile = {
      agent: agent({ phone: "+21698000000" }),
      events: [
        {
          id: "e-1",
          kind: "sanction",
          effective_on: "2026-10-01",
          title: "Blâme",
          unit_id: null,
          unit_name: null,
          from_unit_id: null,
          from_unit_name: null,
          reference: "Décision 12",
          note: null,
          created_by_name: "Service RH",
          created_at: "2026-10-01T08:00:00Z",
          cancelled_at: null,
          cancelled_by_name: null,
          cancel_reason: null,
        },
      ],
      absences: [absence({ reference: "Certificat 77" })],
    };
    renderApp(<PersonnelFilePage />, {
      api: fakeApi({ agentFile: vi.fn(() => Promise.resolve(file)) }),
      auth: fakeAuth(OFFICER),
      lang: "fr",
      route: "/personnel/agents/:id",
      path: "/personnel/agents/a-1",
    });
    expect(await screen.findByRole("heading", { level: 1, name: "Amine Ben Salah" })).toBeInTheDocument();
    expect(screen.getByText("Blâme")).toBeInTheDocument();
    expect(screen.getByText("Réf. : Décision 12")).toBeInTheDocument();
    expect(screen.getByText("Certificat 77")).toBeInTheDocument();
  });

  it("keeps the file closed to the rooms", () => {
    renderApp(<PersonnelFilePage />, { lang: "fr", route: "/personnel/agents/:id", path: "/personnel/agents/a-1" });
    expect(screen.getByText("Le dossier administratif relève du service du personnel.")).toBeInTheDocument();
  });
});
