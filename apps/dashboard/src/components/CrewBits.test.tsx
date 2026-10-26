import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CrewDevice, ShiftRow } from "../lib/crewTypes";
import { CrewPage } from "../pages/CrewPage";
import { makeIncidentDetail } from "../test/fixtures";
import { makeAssignment } from "../test/opsFixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { OperationsPanel } from "./OperationsPanel";

const AT = "2026-10-26T09:00:00Z";

const shift: ShiftRow = {
  id: "sh-1",
  resource: { id: "res-1", label: "FPT-12", kind: "fire_engine", unit_name: "Unité Tunis-Centre" },
  crew_size: 5,
  crew_names: "Sami, Amel",
  started_at: AT,
  ended_at: null,
  leader_name: "Sami Ben Ali",
  gouvernorat_code: 11,
};

const device: CrewDevice = {
  id: "dev-1",
  holder_name: "Sami Ben Ali",
  label: "Samsung A15",
  platform: "android",
  app_build: 17,
  created_at: AT,
  last_seen_at: AT,
  revoked_at: null,
  on_shift: true,
  gouvernorat_code: 11,
};

describe("staff app in the room (phase P4a)", () => {
  it("shows the crew under the assignment and what the scene sent", () => {
    const incident = makeIncidentDetail({
      assignments: [
        makeAssignment({
          crew: { shift_id: "sh-1", leader_name: "Sami Ben Ali", crew_size: 5, acknowledged_at: AT },
        }),
      ],
      callouts: [],
      field_reports: [
        {
          id: "fr-1",
          assignment_id: "a-1",
          resource_label: "FPT-12",
          category: "fire",
          classification: null,
          severity: 3,
          backup_needed: true,
          backup_note: "Une citerne",
          crew_danger: true,
          author_name: "Sami Ben Ali",
          device_at: AT,
          created_at: AT,
        },
      ],
      casualties: { injured: 2, deceased: 1, rescued: 0, trapped: 0, updated_by: "Sami", updated_at: AT },
      transports: [
        {
          id: "t-1",
          assignment_id: "a-1",
          triage: "red",
          age_band: "child",
          sex: "unknown",
          hospital: "Hôpital Charles Nicolle",
          created_by_name: "Sami",
          device_at: AT,
          created_at: AT,
        },
      ],
    });
    renderApp(<OperationsPanel incident={incident} />, { lang: "fr" });

    const table = screen.getByRole("table", { name: "Engagements actifs" });
    expect(within(table).getByText("Chef : Sami Ben Ali")).toBeInTheDocument();
    expect(within(table).getByText(/^Reçu /)).toBeInTheDocument();

    const field = screen.getByRole("region", { name: "Du terrain" });
    const alarm = within(field).getByRole("alert");
    expect(alarm).toHaveTextContent("Danger pour l'équipage · Demande un renfort");
    expect(alarm).toHaveTextContent("Une citerne");
    const counters = within(field).getByLabelText("Victimes");
    expect(within(counters).getByText("Blessés").nextSibling).toHaveTextContent("2");
    expect(within(field).getByText("3 · Grave")).toBeInTheDocument();
    const transports = within(field).getByRole("table", { name: "Évacués vers l'hôpital" });
    expect(within(transports).getByText("Rouge · immédiat")).toBeInTheDocument();
    expect(within(transports).getByText("Hôpital Charles Nicolle")).toBeInTheDocument();
  });

  it("lists the teams on duty for the room", async () => {
    const api = fakeApi({ shifts: vi.fn(() => Promise.resolve([shift])) });
    renderApp(<CrewPage />, { api, lang: "fr" });
    const table = await screen.findByRole("table", { name: "En garde maintenant" });
    expect(within(table).getByText("FPT-12")).toBeInTheDocument();
    expect(within(table).getByText("Sami Ben Ali")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Téléphones des chefs d'agrès" })).not.toBeInTheDocument();
  });

  it("lets the account administrator wipe a leader's phone after a confirmation", async () => {
    const admin = { ...OPERATOR_CLAIMS, realm_access: { roles: ["regional_account_admin"] }, gouvernorat_code: "11" };
    const api = fakeApi({
      shifts: vi.fn(() => Promise.resolve([])),
      crewDevices: vi.fn(() => Promise.resolve([device])),
      revokeCrewDevice: vi.fn(() => Promise.resolve({ ...device, revoked_at: AT, on_shift: false })),
    });
    renderApp(<CrewPage />, { api, auth: fakeAuth(admin), lang: "fr" });
    const table = await screen.findByRole("table", { name: "Téléphones des chefs d'agrès" });
    expect(screen.queryByRole("region", { name: "En garde maintenant" })).not.toBeInTheDocument();
    fireEvent.click(within(table).getByRole("button", { name: "Retirer et effacer le téléphone de Sami Ben Ali" }));
    expect(api.revokeCrewDevice).not.toHaveBeenCalled();
    fireEvent.click(within(table).getByRole("button", { name: "Oui, effacer" }));
    await waitFor(() => expect(api.revokeCrewDevice).toHaveBeenCalledWith("dev-1"));
    expect(api.crewDevices).toHaveBeenCalledWith(false, expect.anything());
  });
});
