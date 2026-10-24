// covers: phase B2 (docs/phase-b/design-b2.md): attached medical file, missing-person search, safety settings.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import type { PlatformSetting } from "../lib/phase9Types";
import { makeDetail } from "../test/fixtures";
import { makeSettings } from "../test/phase9Fixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { ReportDetailPage } from "./ReportDetailPage";
import { SettingsPage } from "./SettingsPage";

vi.mock("../components/LazyMap", () => ({ LazyMapView: () => <div data-testid="map" /> }));

const route = "/reports/:id";
const base = { version: 1, updated_by_name: null, updated_at: null, editable: false };

function withHistory(on: boolean, editable = false): PlatformSetting[] {
  return [
    ...makeSettings(editable),
    { ...base, editable, key: "safety.live_max_minutes", value: 480 },
    { ...base, editable, key: "safety.check_max_hours", value: 24 },
    { ...base, editable, key: "safety.location_history", value: on },
  ];
}

describe("Report detail, phase B2", () => {
  it("opens the attached medical file only on request", async () => {
    const reportMedical = vi.fn(() =>
      Promise.resolve({
        data: { blood_group: "AB-", allergies: "Pénicilline", sex: "female" as const },
        attached_at: "2026-10-23T09:00:00Z",
      }),
    );
    const api = fakeApi({
      report: vi.fn(() => Promise.resolve(makeDetail({ id: "r1", medical_attached: true }))),
      reportMedical,
    });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r1", route, lang: "fr" });

    const section = (await screen.findByRole("heading", { name: "Dossier médical joint" })).closest("section");
    if (!section) throw new Error("no section");
    expect(within(section).queryByText("Pénicilline")).not.toBeInTheDocument();
    expect(reportMedical).not.toHaveBeenCalled();
    fireEvent.click(within(section).getByRole("button", { name: "Ouvrir le dossier médical" }));
    expect(await within(section).findByText("Pénicilline")).toBeInTheDocument();
    expect(reportMedical).toHaveBeenCalledWith("r1");
    expect(within(section).getByText("AB-")).toBeInTheDocument();
    expect(within(section).getByText("Femme")).toBeInTheDocument();
    expect(within(section).getByText(/inscrite au journal d'audit/)).toBeInTheDocument();
    fireEvent.click(within(section).getByRole("button", { name: "Masquer" }));
    await waitFor(() => expect(within(section).queryByText("Pénicilline")).not.toBeInTheDocument());
  });

  it("explains a refused opening and shows nothing without an attached file", async () => {
    const api = fakeApi({
      report: vi.fn(() => Promise.resolve(makeDetail({ id: "r1", medical_attached: true }))),
      reportMedical: vi.fn(() => Promise.reject(new ApiError(403, "forbidden"))),
    });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r1", route, lang: "en" });
    fireEvent.click(await screen.findByRole("button", { name: "Open the medical file" }));
    expect(await screen.findByText("You are not allowed to perform this action.")).toBeInTheDocument();
  });

  it("hides the medical section when nothing is attached", async () => {
    const api = fakeApi({ report: vi.fn(() => Promise.resolve(makeDetail({ id: "r1" }))) });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r1", route, lang: "en" });
    expect(await screen.findByText("EH-26-61-0004821")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Medical file attached" })).not.toBeInTheDocument();
  });

  it("hides the missing-person search while the location history is off", async () => {
    const api = fakeApi({
      report: vi.fn(() => Promise.resolve(makeDetail({ id: "r1" }))),
      platformSettings: vi.fn(() => Promise.resolve(withHistory(false))),
    });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r1", route, lang: "en" });
    expect(await screen.findByText("EH-26-61-0004821")).toBeInTheDocument();
    await waitFor(() => expect(api.platformSettings).toHaveBeenCalled());
    expect(screen.queryByRole("heading", { name: /Missing person/ })).not.toBeInTheDocument();
  });

  it("searches the history with a phone and a reason, newest position first", async () => {
    const searchLocationHistory = vi.fn(() =>
      Promise.resolve({
        found: true,
        enabled: true,
        points: [
          { lat: 34.74, lon: 10.76, accuracy_m: 20, at: "2026-10-23T08:00:00Z" },
          { lat: 34.75, lon: 10.77, accuracy_m: null, at: "2026-10-23T09:00:00Z" },
        ],
      }),
    );
    const api = fakeApi({
      report: vi.fn(() => Promise.resolve(makeDetail({ id: "r1" }))),
      platformSettings: vi.fn(() => Promise.resolve(withHistory(true))),
      searchLocationHistory,
    });
    renderApp(<ReportDetailPage />, { api, path: "/reports/r1", route, lang: "en" });

    const section = (await screen.findByRole("heading", { name: "Missing person: location history" })).closest(
      "section",
    );
    if (!section) throw new Error("no section");
    const scope = within(section);
    fireEvent.click(scope.getByRole("button", { name: "Search" }));
    expect(scope.getByText("Enter a phone number (8 to 20 digits).")).toBeInTheDocument();
    expect(searchLocationHistory).not.toHaveBeenCalled();

    fireEvent.change(scope.getByLabelText(/Person's phone number/), { target: { value: "20 123 456" } });
    fireEvent.change(scope.getByLabelText(/Reason for the search/), {
      target: { value: "Hiker missing since last night, family call" },
    });
    fireEvent.click(scope.getByRole("button", { name: "Search" }));
    expect(await scope.findByText("Positions found: 2")).toBeInTheDocument();
    expect(searchLocationHistory).toHaveBeenCalledWith({
      phone: "20 123 456",
      report_id: "r1",
      reason: "Hiker missing since last night, family call",
    });
    const links = scope.getAllByRole("link");
    expect(links[0]).toHaveTextContent("34.75000, 10.77000");
    expect(links[1]).toHaveTextContent("34.74000, 10.76000");
  });

  it("is not offered to roles outside the operations rooms", async () => {
    const api = fakeApi({
      report: vi.fn(() => Promise.resolve(makeDetail({ id: "r1" }))),
      platformSettings: vi.fn(() => Promise.resolve(withHistory(true))),
    });
    const auth = fakeAuth({ ...OPERATOR_CLAIMS, realm_access: { roles: ["local_committee"] } });
    renderApp(<ReportDetailPage />, { api, auth, path: "/reports/r1", route, lang: "en" });
    expect(await screen.findByText("EH-26-61-0004821")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Missing person/ })).not.toBeInTheDocument();
  });
});

describe("Settings, phase B2", () => {
  it("turns the location history on with a reason", async () => {
    const save = vi.fn((key: string, body: { value: unknown; version: number }) =>
      Promise.resolve({ key, value: body.value, version: 2, updated_by_name: "Admin", updated_at: null, editable: true }),
    );
    const api = fakeApi({
      platformSettings: vi.fn(() => Promise.resolve(withHistory(false, true))),
      savePlatformSetting: save,
    });
    const auth = fakeAuth({ ...OPERATOR_CLAIMS, realm_access: { roles: ["sysadmin"] }, scope_level: "national" });
    renderApp(<SettingsPage />, { api, auth, lang: "en" });

    expect(await screen.findByLabelText("Longest share")).toHaveValue(480);
    expect(screen.getByLabelText("Longest duration")).toHaveValue(24);
    const box = screen.getByLabelText("Turn on the location history");
    expect(box).not.toBeChecked();
    fireEvent.click(box);
    const section = box.closest("section");
    if (!section) throw new Error("no section");
    const scope = within(section);
    fireEvent.change(scope.getByLabelText(/Reason/), { target: { value: "Approved by the committee" } });
    fireEvent.click(scope.getByRole("button", { name: /Save/ }));
    await waitFor(() =>
      expect(save).toHaveBeenCalledWith("safety.location_history", {
        value: true,
        version: 1,
        reason: "Approved by the committee",
      }),
    );
  });
});
