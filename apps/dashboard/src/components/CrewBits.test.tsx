import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CrewDevice, ReportTemplate, ShiftRow } from "../lib/crewTypes";
import { CrewPage } from "../pages/CrewPage";
import { ReportTemplatesPage } from "../pages/ReportTemplatesPage";
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
  unseen_alerts: 2,
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

const fireTemplate: ReportTemplate = {
  id: "tpl-1",
  category: "fire",
  classification: null,
  version: 1,
  status: "approved",
  simulated: true,
  fields: [
    {
      key: "place",
      type: "single",
      label: { ar: "المكان", fr: "Lieu", en: "Place" },
      required: true,
      options: [
        { key: "home", label: { ar: "مسكن", fr: "Logement", en: "Home" } },
        { key: "forest", label: { ar: "غابة", fr: "Forêt", en: "Forest" } },
      ],
    },
    { key: "spread_risk", type: "yesno", label: { ar: "خطر الانتشار", fr: "Risque de propagation", en: "Risk of spreading" } },
    { key: "area_ha", type: "count", label: { ar: "المساحة", fr: "Surface", en: "Area" }, unit: { fr: "ha" } },
  ],
  created_by_name: null,
  created_at: AT,
  updated_at: AT,
  approved_by_name: "Le Bureau",
  approved_at: AT,
};

const report = {
  assignment_id: "a-1",
  resource_label: "FPT-12",
  category: "fire" as const,
  classification: null,
  backup_note: null,
  crew_danger: false,
  author_name: "Sami Ben Ali",
  device_at: AT,
};

describe("staff app in the room (phases P4a and P4b)", () => {
  it("shows the crew, the alerts to mark as seen and what the scene sent", async () => {
    const incident = makeIncidentDetail({
      assignments: [
        makeAssignment({
          crew: { shift_id: "sh-1", leader_name: "Sami Ben Ali", crew_size: 5, acknowledged_at: AT, unseen_alerts: 1 },
          contact_phone: "+216 71 000 000",
        }),
      ],
      callouts: [],
      field_reports: [
        { ...report, id: "fr-1", kind: "first", severity: 2, backup_needed: false, created_at: AT },
        {
          ...report,
          id: "fr-2",
          kind: "update",
          severity: 3,
          backup_needed: true,
          backup_kinds: ["extrication"],
          created_at: "2026-10-26T09:10:00Z",
        },
        {
          ...report,
          id: "fr-3",
          kind: "detailed",
          severity: null,
          backup_needed: false,
          template_id: "tpl-1",
          template_version: 1,
          answers: { place: "forest", spread_risk: true, area_ha: 12 },
          note: "Vent fort",
          created_at: "2026-10-26T09:20:00Z",
        },
      ],
      casualties: {
        injured_light: 2,
        injured_serious: 1,
        deceased: 0,
        rescued: 3,
        trapped: 0,
        transported: 1,
        updated_by: "Sami",
        updated_at: AT,
      },
      transports: [
        {
          id: "t-1",
          assignment_id: "a-1",
          triage: "red",
          age_band: "under_12",
          sex: "unknown",
          hospital: "Hôpital Charles Nicolle",
          created_by_name: "Sami",
          device_at: AT,
          created_at: AT,
        },
      ],
      alerts: [
        {
          id: "al-1",
          assignment_id: "a-1",
          resource_label: "FPT-12",
          kind: "danger",
          items: ["collapse", "gas"],
          created_by_name: "Sami",
          device_at: AT,
          created_at: AT,
          seen_by_name: null,
          seen_at: null,
        },
        {
          id: "al-2",
          assignment_id: "a-1",
          resource_label: "FPT-12",
          kind: "backup",
          items: ["ambulance"],
          created_by_name: "Sami",
          device_at: AT,
          created_at: AT,
          seen_by_name: "Leila",
          seen_at: AT,
        },
      ],
      attachments: [
        {
          id: "f-1",
          assignment_id: "a-1",
          kind: "photo",
          body: null,
          content_type: "image/jpeg",
          bytes: 1000,
          duration_s: null,
          created_by_name: "Sami",
          device_at: AT,
          created_at: AT,
          url: "https://s3.example/p.jpg?sig=x",
        },
        {
          id: "f-2",
          assignment_id: "a-1",
          kind: "voice",
          body: null,
          content_type: "audio/mp4",
          bytes: 1000,
          duration_s: 12,
          created_by_name: "Sami",
          device_at: AT,
          created_at: AT,
          url: "https://s3.example/v.m4a?sig=x",
        },
        {
          id: "f-3",
          assignment_id: "a-1",
          kind: "text",
          body: "Toit instable",
          content_type: null,
          bytes: null,
          duration_s: null,
          created_by_name: "Sami",
          device_at: AT,
          created_at: AT,
        },
      ],
    });
    const api = fakeApi({
      markAlertSeen: vi.fn(() => new Promise<never>(() => undefined)),
      reportTemplates: vi.fn(() => Promise.resolve([fireTemplate])),
    });
    renderApp(<OperationsPanel incident={incident} />, { api, lang: "fr" });

    const table = screen.getByRole("table", { name: "Engagements actifs" });
    expect(within(table).getByText("Chef : Sami Ben Ali")).toBeInTheDocument();
    expect(within(table).getByText("Alertes non vues : 1")).toBeInTheDocument();
    expect(within(table).getByText("+216 71 000 000")).toBeInTheDocument();

    const field = screen.getByRole("region", { name: "Du terrain" });
    // The unseen danger comes first, as an alert; the seen backup says who saw it.
    const alarm = within(field).getByRole("alert");
    expect(alarm).toHaveTextContent("Danger pour l'équipage — Effondrement, Gaz ou matières dangereuses");
    expect(within(field).getByText(/vu par Leila/)).toBeInTheDocument();
    fireEvent.click(await within(alarm).findByRole("button", { name: /^Marquer comme vu/ }));
    await waitFor(() => expect(api.markAlertSeen).toHaveBeenCalledWith("al-1"));

    const counters = within(field).getByLabelText("Victimes");
    expect(within(counters).getByText("Blessés légers").nextSibling).toHaveTextContent("2");
    expect(within(counters).getByText("Blessés graves").nextSibling).toHaveTextContent("1");
    expect(within(counters).getByText("Évacués").nextSibling).toHaveTextContent("1");
    // Only the last situation report of the vehicle.
    expect(within(field).getByText("3 · Grave")).toBeInTheDocument();
    expect(within(field).queryByText("2 · Modéré")).not.toBeInTheDocument();
    expect(within(field).getByText(/Désincarcération/)).toBeInTheDocument();

    const transports = within(field).getByRole("table", { name: "Évacués vers l'hôpital" });
    expect(within(transports).getByText(/Moins de 12 ans/)).toBeInTheDocument();

    // The detailed report reads with the template's labels.
    expect(await within(field).findByText("Forêt")).toBeInTheDocument();
    expect(within(field).getByText("Risque de propagation").nextSibling).toHaveTextContent("Oui");
    expect(within(field).getByText("Surface").nextSibling).toHaveTextContent("12 ha");
    expect(within(field).getByText("Vent fort")).toBeInTheDocument();

    expect(within(field).getByRole("img", { name: /Photo des lieux/ })).toHaveAttribute(
      "src",
      "https://s3.example/p.jpg?sig=x",
    );
    expect(field.querySelector("audio")).toHaveAttribute("src", "https://s3.example/v.m4a?sig=x");
    expect(within(field).getByText("Toit instable")).toBeInTheDocument();
  });

  it("previews the templates for the room, read only", async () => {
    const api = fakeApi({ reportTemplates: vi.fn(() => Promise.resolve([fireTemplate])) });
    renderApp(<ReportTemplatesPage />, { api, lang: "fr" });
    expect(await screen.findByText(/Seul le Bureau/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Afficher" }));
    const preview = screen.getByLabelText("Aperçu comme sur le téléphone");
    expect(within(preview).getByText("Forêt")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nouvelle version (brouillon)" })).not.toBeInTheDocument();
  });

  it("lets the Office draft a new version, edit it and approve it", async () => {
    const draft: ReportTemplate = { ...fireTemplate, id: "tpl-2", version: 2, status: "draft", simulated: false };
    const reportTemplates = vi
      .fn()
      .mockResolvedValueOnce([fireTemplate])
      .mockResolvedValue([fireTemplate, draft]);
    const api = fakeApi({
      reportTemplates,
      createTemplate: vi.fn(() => Promise.resolve(draft)),
      editTemplate: vi.fn(() => Promise.resolve(draft)),
      approveTemplate: vi.fn(() => Promise.resolve({ ...draft, status: "approved" as const })),
    });
    const office = { ...OPERATOR_CLAIMS, realm_access: { roles: ["central_committee"] }, gouvernorat_code: undefined };
    renderApp(<ReportTemplatesPage />, { api, auth: fakeAuth(office), lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Nouvelle version (brouillon)" }));
    await waitFor(() => expect(api.createTemplate).toHaveBeenCalledWith("fire", null, fireTemplate.fields));
    expect(await screen.findByText("Question 3")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ajouter une question" }));
    const keys = screen.getAllByLabelText("Clé (a–z, 0–9, _)");
    fireEvent.change(keys[3] as HTMLElement, { target: { value: "smoke" } });
    fireEvent.change(screen.getAllByLabelText("Forme")[3] as HTMLElement, { target: { value: "yesno" } });
    fireEvent.change(screen.getAllByLabelText("Français").at(-1) as HTMLElement, { target: { value: "Fumée dense" } });
    fireEvent.click(screen.getByRole("button", { name: "Approuver" }));
    await waitFor(() => expect(api.approveTemplate).toHaveBeenCalledWith("tpl-2"));
    const saved = vi.mocked(api.editTemplate).mock.calls[0]?.[1];
    expect(saved?.[3]).toEqual({ key: "smoke", type: "yesno", label: { fr: "Fumée dense" }, options: [], required: false });
  });

  it("lists the teams on duty for the room", async () => {
    const api = fakeApi({ shifts: vi.fn(() => Promise.resolve([shift])) });
    renderApp(<CrewPage />, { api, lang: "fr" });
    const table = await screen.findByRole("table", { name: "En garde maintenant" });
    expect(within(table).getByText("FPT-12")).toBeInTheDocument();
    expect(within(table).getByText("Sami Ben Ali")).toBeInTheDocument();
    expect(within(table).getByText("Alertes non vues : 2")).toBeInTheDocument();
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
