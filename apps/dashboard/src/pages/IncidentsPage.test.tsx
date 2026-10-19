import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { makeIncident, makeIncidentDetail } from "../test/fixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { IncidentDetailPage } from "./IncidentDetailPage";
import { IncidentsPage } from "./IncidentsPage";

vi.mock("../components/LazyMap", () => ({ LazyMapView: () => <div data-testid="map" /> }));

describe("IncidentsPage", () => {
  it("lists open incidents by default with category, severity, counts and updated time", async () => {
    const api = fakeApi({
      incidents: vi.fn(() =>
        Promise.resolve({
          items: [
            makeIncident({ id: "i-1", severity: 82, report_count: 3, reporter_count: 2 }),
            makeIncident({ id: "i-2", category: "flood", severity: null, report_count: 1, reporter_count: 1 }),
          ],
          next_cursor: null,
        }),
      ),
    });
    renderApp(<IncidentsPage />, { api, lang: "fr" });

    const table = await screen.findByRole("table", { name: /Liste des incidents/ });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    const first = rows[0] as HTMLElement;
    expect(within(first).getByText("Incendie")).toBeInTheDocument();
    expect(within(first).getByTitle("Priorité 82 (haute)")).toBeInTheDocument();
    expect(within(first).getByText("3")).toBeInTheDocument();
    expect(within(first).getByText("Ouvert")).toBeInTheDocument();
    expect(within(first).getByRole("link")).toHaveAttribute("href", "/incidents/i-1");
    expect(within(rows[1] as HTMLElement).getByText("Priorité non encore évaluée")).toBeInTheDocument();
    expect(await within(first).findByText("Sfax")).toBeInTheDocument();
    expect(api.incidents).toHaveBeenCalledWith(expect.objectContaining({ status: "open", cursor: null }));
  });

  it("changes the status filter", async () => {
    const api = fakeApi();
    renderApp(<IncidentsPage />, { api, lang: "fr" });
    expect(await screen.findByText("Aucun incident avec ce statut.")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Tous"));
    await waitFor(() => expect(api.incidents).toHaveBeenCalledWith(expect.objectContaining({ status: "all" })));
    fireEvent.click(screen.getByLabelText("Fusionné"));
    await waitFor(() => expect(api.incidents).toHaveBeenCalledWith(expect.objectContaining({ status: "merged" })));
  });

  it("renders in Arabic", async () => {
    const api = fakeApi({ incidents: vi.fn(() => Promise.resolve({ items: [makeIncident()], next_cursor: null })) });
    renderApp(<IncidentsPage />, { api, lang: "ar" });
    expect(await screen.findByRole("heading", { name: "الحوادث" })).toBeInTheDocument();
    expect(await screen.findByText("مفتوحة", { selector: ".chip" })).toBeInTheDocument();
  });
});

describe("IncidentDetailPage", () => {
  const route = "/incidents/:id";

  it("shows the summary, member reports and a translated timeline", async () => {
    const api = fakeApi({ incident: vi.fn(() => Promise.resolve(makeIncidentDetail())) });
    renderApp(<IncidentDetailPage />, { api, path: "/incidents/i-1", route, lang: "fr" });

    expect(await screen.findByRole("heading", { name: /Incident/, level: 1 })).toBeInTheDocument();
    const members = screen.getByRole("table", { name: "Signalements de l’incident" });
    expect(within(members).getByRole("link", { name: "EH-26-61-0004822" })).toHaveAttribute("href", "/reports/r-2");
    expect(screen.getByText("Création de l’incident")).toBeInTheDocument();
    expect(screen.getByText("Signalement ajouté")).toBeInTheDocument();
    expect(screen.getByText("(suggestion confirmée)")).toBeInTheDocument();
    expect(screen.getByTestId("map")).toBeInTheDocument();
  });

  it("merges another open incident after confirmation", async () => {
    const api = fakeApi({
      incident: vi.fn(() => Promise.resolve(makeIncidentDetail())),
      incidents: vi.fn(() =>
        Promise.resolve({ items: [makeIncident(), makeIncident({ id: "i-2", category: "flood" })], next_cursor: null }),
      ),
      mergeIncident: vi.fn(() => Promise.resolve(makeIncidentDetail({ report_count: 3 }))),
    });
    renderApp(<IncidentDetailPage />, { api, path: "/incidents/i-1", route, lang: "fr" });

    const select = await screen.findByLabelText("Incident à fusionner");
    // The incident itself is not a candidate.
    expect(within(select).getAllByRole("option")).toHaveLength(2);
    fireEvent.change(select, { target: { value: "i-2" } });
    fireEvent.click(screen.getByRole("button", { name: "Fusionner" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Confirmez-vous la fusion");
    expect(api.mergeIncident).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la fusion" }));
    await waitFor(() => expect(api.mergeIncident).toHaveBeenCalledWith("i-1", "i-2"));
    expect(await screen.findByText("Fusion effectuée.")).toBeInTheDocument();
  });

  it("offers no merge to read-only roles", async () => {
    const api = fakeApi({ incident: vi.fn(() => Promise.resolve(makeIncidentDetail())) });
    const auth = fakeAuth({ ...OPERATOR_CLAIMS, realm_access: { roles: ["local_committee"] } });
    renderApp(<IncidentDetailPage />, { api, auth, path: "/incidents/i-1", route, lang: "fr" });
    await screen.findByText("Création de l’incident");
    expect(screen.queryByText("Fusionner un autre incident dans celui-ci")).not.toBeInTheDocument();
  });

  it("shows a translated not-found error", async () => {
    const api = fakeApi({ incident: vi.fn(() => Promise.reject(new ApiError(404, "not_found"))) });
    renderApp(<IncidentDetailPage />, { api, path: "/incidents/x", route, lang: "fr" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Élément introuvable");
  });
});
