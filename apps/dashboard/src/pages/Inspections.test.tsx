// covers: phase I2 (docs/phase-i/design-i.md): the general inspectorate's page, the rooms' results and the system
// administrator's deletion and bin; a unit is named by its gouvernorat, kind and name; every table exports to CSV.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CONFIRM_WORD, toCsv } from "../lib/inspectionsApi";
import {
  canAdministerInspections,
  canManageInspections,
  canReadInspectionResults,
  hasDashboardAccess,
  landingPath,
} from "../lib/roles";
import { MISSION, RECORD_DETAIL } from "../test/inspectionsFixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { deleteReady, InspectionAdminPage } from "./InspectionAdminPage";
import { InspectionResultsPage } from "./InspectionResultsPage";
import { InspectionRecordPage, InspectionsPage } from "./InspectionsPage";

const GENERAL = { ...OPERATOR_CLAIMS, realm_access: { roles: ["inspector_general"] }, scope_level: "national" };
const NATIONAL_ROOM = { ...OPERATOR_CLAIMS, realm_access: { roles: ["operator"] }, scope_level: "national" };
const ADMIN = { ...OPERATOR_CLAIMS, realm_access: { roles: ["sysadmin"] }, scope_level: "national" };

describe("Inspections", () => {
  it("gives the inspectorate its space, the rooms a reading and the administrator the bin", () => {
    expect(canManageInspections(["inspector_general"])).toBe(true);
    expect(canManageInspections(["ops_manager"])).toBe(false);
    expect(canReadInspectionResults(["operator"])).toBe(true);
    expect(canReadInspectionResults(["inspector_general"])).toBe(false);
    expect(canAdministerInspections(["sysadmin"])).toBe(true);
    expect(canAdministerInspections(["inspector_general"])).toBe(false);
    expect(hasDashboardAccess(["inspector_general"])).toBe(true);
    expect(landingPath(["inspector_general"])).toBe("/inspections");
  });

  it("writes a CSV that a spreadsheet reads as UTF-8, quoting what needs it", () => {
    const csv = toCsv(["a", "b"], [["x,y", 'say "hi"'], [null, 3]]);
    expect(csv.charCodeAt(0)).toBe(0xfeff);
    expect(csv.slice(1)).toBe('a,b\r\n"x,y","say ""hi"""\r\n,3\r\n');
  });

  it("shows the state of every place with a print button and an export", async () => {
    renderApp(<InspectionsPage tab="overview" />, { auth: fakeAuth(GENERAL), lang: "fr" });
    expect(await screen.findByText("القاعة الجهوية بباجة")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Exporter CSV/ })).toBeEnabled();
    expect(screen.getByRole("link", { name: "Missions et ordres" })).toHaveAttribute("href", "/inspections/missions");
  });

  it("plans a unit as gouvernorat, kind and typed name", async () => {
    const createInspectionMission = vi.fn(() => Promise.resolve(MISSION));
    const api = fakeApi({ createInspectionMission });
    renderApp(<InspectionsPage tab="missions" />, { api, auth: fakeAuth(GENERAL), lang: "fr" });
    expect(await screen.findByText("OM-2026-0001")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Planifier une mission/ }));
    const form = await screen.findByRole("form", { name: "Nouvelle mission d'inspection" });
    await waitFor(() => expect(within(form).getByRole("option", { name: "سامي المتفقد [SIM]" })).toBeInTheDocument());
    fireEvent.change(within(form).getByLabelText("Inspecteur"), { target: { value: "i-1" } });
    await waitFor(() => expect(within(form).getByRole("option", { name: "Sfax" })).toBeInTheDocument());
    fireEvent.change(within(form).getByLabelText("Gouvernorat"), { target: { value: "61" } });
    fireEvent.change(within(form).getByLabelText("Type d'unité"), { target: { value: "guard_post" } });
    fireEvent.change(within(form).getByLabelText("Nom de l'unité"), { target: { value: "نقطة حراسة الشاطئ" } });
    fireEvent.click(within(form).getByRole("button", { name: /Enregistrer et émettre l'ordre/ }));
    await waitFor(() => expect(createInspectionMission).toHaveBeenCalled());
    expect(createInspectionMission).toHaveBeenCalledWith(
      expect.objectContaining({
        inspector_id: "i-1",
        sites: [
          { target: "unit", gouvernorat_code: 61, unit_kind: "guard_post", unit_name: "نقطة حراسة الشاطئ", sections: [] },
        ],
      }),
    );
  });

  it("lets the inspectorate decide what each room reads of a room's report", async () => {
    renderApp(<InspectionRecordPage />, {
      auth: fakeAuth(GENERAL),
      lang: "fr",
      route: "/inspections/records/:id",
      path: "/inspections/records/x-1",
    });
    expect(await screen.findByText("تحيين سجل المكالمات يوميا")).toBeInTheDocument();
    expect(screen.getByText("Ce que voient les salles")).toBeInTheDocument();
    expect(RECORD_DETAIL.target).toBe("room");
  });

  it("shows a room only what was disclosed, and the programme to a national room", async () => {
    renderApp(<InspectionResultsPage tab="results" />, { auth: fakeAuth(NATIONAL_ROOM), lang: "fr" });
    const row = (await screen.findByText("القاعة الجهوية بباجة")).closest("tr");
    if (!row) throw new Error("no row");
    expect(within(row).getByText("جيد")).toBeInTheDocument();
    expect(within(row).getByText("تحيين سجل المكالمات يوميا")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Programme à venir" })).toBeInTheDocument();
    // The inspections in progress are dormant until granted.
    expect(screen.queryByRole("link", { name: "Inspections en cours" })).not.toBeInTheDocument();
  });

  it("asks the administrator for a reason and the confirmation word before deleting", async () => {
    expect(deleteReady({ scope: "all", reason: "court", confirm: CONFIRM_WORD })).toBe(false);
    expect(deleteReady({ scope: "all", reason: "rapport en double", confirm: "oui" })).toBe(false);
    expect(deleteReady({ scope: "all", reason: "rapport en double", confirm: CONFIRM_WORD })).toBe(true);
    expect(deleteReady({ scope: "one", inspection_id: "x", reason: "rapport en double", confirm: CONFIRM_WORD })).toBe(false);
    expect(
      deleteReady({ scope: "period", from_date: "2026-11-10", to_date: "2026-11-01", reason: "rapport en double", confirm: CONFIRM_WORD }),
    ).toBe(false);

    const restoreInspection = vi.fn(() => Promise.resolve(undefined));
    renderApp(<InspectionAdminPage />, { api: fakeApi({ restoreInspection }), auth: fakeAuth(ADMIN), lang: "fr" });
    const row = (await screen.findByText("مركز قديم")).closest("tr");
    if (!row) throw new Error("no row");
    fireEvent.click(within(row).getByRole("button", { name: "Restaurer" }));
    await waitFor(() => expect(restoreInspection).toHaveBeenCalledWith("x-9"));
  });
});
