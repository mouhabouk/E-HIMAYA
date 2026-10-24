// covers: phase C1-a (docs/phase-c/design-medical-axis.md §11): the medical committee appointed by the sysadmin.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CommitteeMember, StaffDoctor } from "../lib/doctorsApi";
import { canManageMedicalCommittee } from "../lib/roles";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { MedicalCommitteePage } from "./MedicalCommitteePage";

const ADMIN = { ...OPERATOR_CLAIMS, realm_access: { roles: ["sysadmin"] }, scope_level: "national" };

const candidate: StaffDoctor = {
  id: "d-2",
  full_name: "Hichem Gharbi",
  kind: "civil_protection",
  specialties: ["emergency_medicine"],
  workplace: "Caserne de Gabès",
  gouvernorat_code: 61,
  cp_unit: "Direction régionale de Gabès",
  status: "approved",
  available: false,
  submitted_at: "2026-10-20T08:00:00Z",
  committee_until: null,
};

const member: CommitteeMember = {
  ...candidate,
  id: "d-1",
  full_name: "Salma Trabelsi",
  committee_since: "2026-10-24T08:00:00Z",
  committee_until: "2027-10-19T08:00:00Z",
};

describe("Medical committee", () => {
  it("appoints a Civil Protection doctor for the chosen term", async () => {
    const appointMember = vi.fn(() =>
      Promise.resolve({ members: [member, { ...candidate, committee_since: "2026-10-24T09:00:00Z" }], max_members: 7 }),
    );
    const api = fakeApi({
      medicalCommittee: vi.fn(() => Promise.resolve({ members: [member], max_members: 7 })),
      committeeCandidates: vi.fn(() => Promise.resolve([candidate])),
      appointMember,
    });
    renderApp(<MedicalCommitteePage />, { api, auth: fakeAuth(ADMIN), lang: "fr" });

    expect(await screen.findByText("Salma Trabelsi")).toBeInTheDocument();
    expect(screen.getByText("(1 sur 7)")).toBeInTheDocument();
    expect(screen.getByText(/l'administrateur ne lit aucun dossier/)).toBeInTheDocument();
    const section = screen.getByRole("region", { name: "Médecins de la Protection civile vérifiés" });
    await within(section).findByText("Hichem Gharbi");
    fireEvent.change(within(section).getByRole("combobox", { name: "Durée" }), { target: { value: "24" } });
    fireEvent.click(within(section).getByRole("button", { name: "Nommer Hichem Gharbi au comité médical" }));
    await waitFor(() => expect(appointMember).toHaveBeenCalledWith("d-2", 24));
    expect(await screen.findByText("(2 sur 7)")).toBeInTheDocument();
  });

  it("ends a term only with a reason and blocks appointments when the seats are taken", async () => {
    const revokeMember = vi.fn(() => Promise.resolve({ members: [], max_members: 1 }));
    const api = fakeApi({
      medicalCommittee: vi.fn(() => Promise.resolve({ members: [member], max_members: 1 })),
      committeeCandidates: vi.fn(() => Promise.resolve([candidate])),
      revokeMember,
    });
    renderApp(<MedicalCommitteePage />, { api, auth: fakeAuth(ADMIN), lang: "fr" });

    const section = await screen.findByRole("region", { name: "Médecins de la Protection civile vérifiés" });
    expect(within(section).getByText(/Tous les sièges sont occupés/)).toBeInTheDocument();
    expect(await within(section).findByRole("button", { name: /Nommer Hichem Gharbi/ })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Mettre fin au mandat" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la fin du mandat" }));
    expect(screen.getByText("Le motif est requis pour cette décision.")).toBeInTheDocument();
    expect(revokeMember).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Motif (envoyé au médecin)"), { target: { value: "Fin de mission" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la fin du mandat" }));
    await waitFor(() => expect(revokeMember).toHaveBeenCalledWith("d-1", "Fin de mission"));
    expect(await screen.findByText("Aucun membre pour l'instant.")).toBeInTheDocument();
  });

  it("is managed by a national system administrator only", () => {
    expect(canManageMedicalCommittee({ roles: ["sysadmin"], national: true })).toBe(true);
    expect(canManageMedicalCommittee({ roles: ["sysadmin"], national: false })).toBe(false);
    expect(canManageMedicalCommittee({ roles: ["medical_coordinator"], national: true })).toBe(false);
  });
});
