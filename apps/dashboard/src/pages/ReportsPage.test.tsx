import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makeReport } from "../test/fixtures";
import { fakeApi, renderApp } from "../test/render";
import { ReportsPage } from "./ReportsPage";

const REPORTS = [
  makeReport({
    id: "a",
    tracking_code: "EH-26-61-0000001",
    priority_score: 85,
    lives_at_risk: true,
    incident_id: "i-1",
    text: "Incendie dans un immeuble",
    lang: "fr",
    text_ar: "حريق في عمارة",
  }),
  makeReport({ id: "b", tracking_code: "EH-26-61-0000002", priority_score: 45, analysis_state: "running", has_suggestion: true }),
  makeReport({ id: "c", tracking_code: "EH-26-61-0000003", priority_score: 12, analysis_state: "failed" }),
  makeReport({ id: "d", tracking_code: "EH-26-61-0000004", priority_score: null, analysis_state: "pending" }),
];

function rowOf(code: string): HTMLElement {
  return screen.getByRole("link", { name: code }).closest("tr") as HTMLElement;
}

describe("ReportsPage (phase 3)", () => {
  it("shows priority bands, analysis chips, markers and the Arabic translation", async () => {
    const api = fakeApi({ reports: vi.fn(() => Promise.resolve({ items: REPORTS, next_cursor: null })) });
    renderApp(<ReportsPage />, { api, lang: "fr" });
    await screen.findByRole("link", { name: "EH-26-61-0000001" });

    const a = rowOf("EH-26-61-0000001");
    expect(within(a).getByTitle("Priorité 85 (haute)")).toHaveClass("prio--high");
    expect(within(a).getByText("Vies en danger")).toBeInTheDocument();
    expect(within(a).getByText("Rattaché à un incident")).toBeInTheDocument();
    expect(within(a).getByText("Incendie dans un immeuble")).toBeInTheDocument();
    expect(within(a).getByText("Traduction")).toBeInTheDocument();
    expect(within(a).getByText(/حريق في عمارة/)).toHaveAttribute("lang", "ar");

    const b = rowOf("EH-26-61-0000002");
    expect(within(b).getByTitle("Priorité 45 (moyenne)")).toHaveClass("prio--medium");
    expect(within(b).getByText("En attente d'analyse")).toBeInTheDocument();
    expect(within(b).getByText("Regroupement suggéré")).toBeInTheDocument();

    const c = rowOf("EH-26-61-0000003");
    expect(within(c).getByTitle("Priorité 12 (basse)")).toHaveClass("prio--low");
    expect(within(c).getByText("Analyse incomplète")).toBeInTheDocument();

    const d = rowOf("EH-26-61-0000004");
    expect(within(d).getByText("—")).toBeInTheDocument();
    expect(within(d).getByText("En attente d'analyse")).toBeInTheDocument();
  });

  it("switches the sort to priority (and remembers it for the tab)", async () => {
    const api = fakeApi();
    renderApp(<ReportsPage />, { api, lang: "fr" });
    await screen.findByText("Aucun signalement ne correspond aux filtres.");
    expect(api.reports).toHaveBeenLastCalledWith(expect.anything(), expect.objectContaining({ sort: "received" }));
    fireEvent.click(screen.getByLabelText("Priorité d’abord"));
    await waitFor(() =>
      expect(api.reports).toHaveBeenLastCalledWith(expect.anything(), expect.objectContaining({ sort: "priority" })),
    );
    expect(sessionStorage.getItem("ehimaya.reportsSort")).toBe("priority");
  });
});
