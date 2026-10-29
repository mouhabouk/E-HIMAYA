// covers: phase L1b (docs/phase-l/design-l1b-coastal.md §4): coastal dashboard, alerts centre, beach card, rules.
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { rulesProblem } from "../lib/coastal";
import { ALERT, DEFAULT_RULES, fakeCoastalApi } from "../test/coastalFixtures";
import { FakeWebSocket } from "../test/FakeWebSocket";
import { CENTRAL_COMMITTEE_CLAIMS } from "../test/phase9Fixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { CoastalPage } from "./CoastalPage";

vi.mock("../components/LazyMap", () => ({
  LazyMapView: (props: { ariaLabel: string; pois?: { title: string; colour?: string }[]; heat?: unknown[] }) => (
    <div data-testid="map" aria-label={props.ariaLabel} data-heat={props.heat?.length ?? 0}>
      {props.pois?.map((p) => (
        <span key={p.title}>{`${p.title} ${p.colour ?? ""}`}</span>
      ))}
    </div>
  ),
}));

describe("CoastalPage", () => {
  it("shows the KPIs, the beaches by colour, the reasons and the [SIM] band", async () => {
    renderApp(<CoastalPage />, { lang: "fr" });
    expect(await screen.findByRole("heading", { name: "Sécurité côtière" })).toBeInTheDocument();
    const kpis = await screen.findByLabelText("Indicateurs des plages");
    expect(within(kpis).getByText("Noyades cette saison").nextSibling).toHaveTextContent("3");
    expect(screen.getByRole("note")).toHaveTextContent("Météo marine simulée");
    // The map draws each beach in its level's colour (design tokens) and the risk heat.
    const map = screen.getByTestId("map");
    expect(map).toHaveTextContent("Plage de la Corniche #D7141A");
    expect(map).toHaveTextContent("Plage Boujaafar #188038");
    expect(map).toHaveAttribute("data-heat", "2");
    // Top 10 with the reasons in words.
    const top = screen.getByRole("table", { name: "Les 10 plages les plus dangereuses" });
    expect(within(top).getByText(/Vagues 2,8 m: \+55/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Noyades (5 ans)" }));
    expect(screen.getByTestId("map")).toHaveAttribute("data-heat", "1");
  });

  it("filters by level and acknowledges an alert", async () => {
    const coastal = fakeCoastalApi();
    renderApp(<CoastalPage />, { lang: "fr", api: fakeApi(coastal) });
    await screen.findByRole("heading", { name: /Centre des alertes côtières/ });
    fireEvent.change(screen.getByLabelText("Niveau de risque"), { target: { value: "red" } });
    await waitFor(() => expect(coastal.coastalOverview).toHaveBeenLastCalledWith({ level: "red" }, expect.anything()));
    fireEvent.click(await screen.findByRole("button", { name: "Vu" }));
    expect(await screen.findByText(/Vu par Salma/)).toBeInTheDocument();
    expect(coastal.ackCoastalAlert).toHaveBeenCalledWith(ALERT.id);
  });

  it("opens the beach card with four days, sources and translated values", async () => {
    renderApp(<CoastalPage />, { lang: "fr" });
    const alerts = await screen.findByRole("heading", { name: /Centre des alertes côtières/ });
    const centre = alerts.closest("section");
    fireEvent.click(await within(centre as HTMLElement).findByRole("button", { name: "Plage de la Corniche" }));
    const card = await screen.findByRole("heading", { name: "Fiche de la plage" });
    const panel = card.closest("section") as HTMLElement;
    expect(within(panel).getByText("Locale")).toBeInTheDocument();
    expect(within(panel).getByText(/Source : ONTT, 2026-06-01/)).toBeInTheDocument();
    expect(within(panel).getAllByText("Non")).toHaveLength(2); // "False" and "no" from the imported file
    const days = within(panel).getByRole("table", { name: "Les quatre prochains jours" });
    expect(days.querySelectorAll("tbody tr")).toHaveLength(2);
    // The drowning model in shadow, beside the rule, for comparison only (L5, design-l5.md §4.2).
    expect(within(days).getByRole("columnheader", { name: /Modèle en ombre/ })).toBeInTheDocument();
    expect(within(days).getByText("12 %")).toBeInTheDocument();
    expect(within(panel).getByText(/sert à comparer/)).toBeInTheDocument();
  });

  it("announces a live coastal alert", async () => {
    FakeWebSocket.reset();
    const coastal = fakeCoastalApi();
    renderApp(<CoastalPage />, { lang: "fr", api: fakeApi(coastal) });
    await screen.findByRole("heading", { name: /Centre des alertes côtières/ });
    await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0));
    const ws = FakeWebSocket.last();
    act(() => {
      ws.serverOpen();
      ws.serverSend({ type: "ready" });
      ws.serverSend({ ...ALERT, type: "coastal.alert", id: "a-2", level: "yellow" });
    });
    expect(await screen.findByText("Nouvelle alerte côtière : Plage de la Corniche (Jaune : vigilance)")).toBeInTheDocument();
    await waitFor(() => expect(coastal.coastalAlerts).toHaveBeenCalledTimes(2));
  });

  it("lets a national committee change the rules with a reason, and others only read them", async () => {
    const coastal = fakeCoastalApi();
    renderApp(<CoastalPage />, { lang: "fr", api: fakeApi(coastal), auth: fakeAuth(CENTRAL_COMMITTEE_CLAIMS) });
    fireEvent.click(await screen.findByText("Règles du calcul du risque"));
    const red = await screen.findByLabelText("Seuil rouge");
    fireEvent.change(red, { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer les règles" }));
    expect(await screen.findByText(/La règle « Seuil rouge » n'est pas valide/)).toBeInTheDocument();
    fireEvent.change(red, { target: { value: "70" } });
    fireEvent.change(screen.getByLabelText("Motif du changement"), { target: { value: "saison 2026" } });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer les règles" }));
    await waitFor(() =>
      expect(coastal.saveCoastalSettings).toHaveBeenCalledWith(expect.objectContaining({ red: 70 }), "saison 2026"),
    );
  });

  it("shows the rules read-only to a regional operator", async () => {
    renderApp(<CoastalPage />, { lang: "fr", auth: fakeAuth(OPERATOR_CLAIMS) });
    fireEvent.click(await screen.findByText("Règles du calcul du risque"));
    expect(await screen.findByLabelText("Seuil rouge")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Enregistrer les règles" })).not.toBeInTheDocument();
  });
});

describe("rulesProblem", () => {
  it("mirrors the API checks", () => {
    expect(rulesProblem(DEFAULT_RULES)).toBeNull();
    expect(rulesProblem({ ...DEFAULT_RULES, yellow: 70 })).toBe("red");
    expect(rulesProblem({ ...DEFAULT_RULES, waves: [[1, 10], [0.5, 20], [null, 30]] })).toBe("waves");
    expect(rulesProblem({ ...DEFAULT_RULES, waves: [[1, 10]] })).toBe("waves");
    expect(rulesProblem({ ...DEFAULT_RULES, season_months: [13] })).toBe("season_months");
  });
});
