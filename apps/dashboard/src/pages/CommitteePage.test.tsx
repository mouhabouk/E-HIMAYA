import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { makeDirective, makeLevel, makePerformance, makePerformanceRow } from "../test/opsFixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { CommitteePage, sinceFor } from "./CommitteePage";

const CENTRAL = { sub: "c-1", name: "Hela Central", realm_access: { roles: ["central_committee"] }, scope_level: "national" };
const LOCAL = { sub: "l-1", name: "Karim Local", realm_access: { roles: ["local_committee"] }, gouvernorat_code: "61" };
const MANAGER = { ...OPERATOR_CLAIMS, realm_access: { roles: ["ops_manager"] } };

const LEVELS = [
  makeLevel({ gouvernorat_code: 11, level: "crisis", reason: "فيضانات", set_by: "Hela Central" }),
  makeLevel({ gouvernorat_code: 61 }),
];

function setup(claims: Record<string, unknown>, overrides: Parameters<typeof fakeApi>[0] = {}) {
  const api = fakeApi({ levels: vi.fn(() => Promise.resolve(LEVELS)), ...overrides });
  return renderApp(<CommitteePage />, { api, auth: fakeAuth(claims), lang: "fr", path: "/committee" });
}

describe("CommitteePage", () => {
  it("shows every gouvernorat's level and lets the central committee declare a disaster after confirmation", async () => {
    const setLevels = vi.fn(() =>
      Promise.resolve([makeLevel({ gouvernorat_code: 61, level: "disaster", reason: "Inondations majeures" })]),
    );
    const { api } = setup(CENTRAL, { setLevels });
    const table = await screen.findByRole("table", { name: "Niveaux opérationnels des gouvernorats" });
    const tunis = within(table).getByRole("row", { name: /Tunis/ });
    expect(within(tunis).getByText("Crise")).toHaveClass("level-tag--crisis");
    expect(within(tunis).getByText("Hela Central")).toBeInTheDocument();

    const form = screen.getByRole("form", { name: "Changer le niveau" });
    fireEvent.click(within(form).getByRole("button", { name: "Appliquer" }));
    expect(within(form).getByText("Choisissez au moins un gouvernorat.")).toBeInTheDocument();
    expect(within(form).getByText("Choisissez le niveau.")).toBeInTheDocument();

    fireEvent.click(within(form).getByLabelText("Sfax"));
    fireEvent.click(within(form).getByLabelText("Catastrophe"));
    fireEvent.change(within(form).getByLabelText(/Motif/), { target: { value: "Inondations majeures" } });
    fireEvent.click(within(form).getByRole("button", { name: "Appliquer" }));
    expect(within(form).getByRole("alert")).toHaveTextContent("regroupé automatiquement");
    expect(setLevels).not.toHaveBeenCalled();
    fireEvent.click(within(form).getByRole("button", { name: "Confirmer le changement" }));
    await waitFor(() =>
      expect(setLevels).toHaveBeenCalledWith({ gouvernorat_codes: [61], level: "disaster", reason: "Inondations majeures" }),
    );
    const sfax = within(table).getByRole("row", { name: /Sfax/ });
    expect(await within(sfax).findByText("Catastrophe")).toHaveClass("level-tag--disaster");
    expect(api.performance).toHaveBeenCalled();
  });

  it("limits a local committee to its own gouvernorat, normal or crisis, and shows the server's refusal", async () => {
    const setLevels = vi.fn(() => Promise.reject(new ApiError(403, "level_not_allowed", "level_not_allowed")));
    setup(LOCAL, { setLevels });
    const form = await screen.findByRole("form", { name: "Changer le niveau" });
    expect(within(form).getByLabelText("Sfax")).toBeChecked();
    expect(within(form).queryByLabelText("Tunis")).not.toBeInTheDocument();
    expect(within(form).queryByLabelText("Catastrophe")).not.toBeInTheDocument();
    fireEvent.click(within(form).getByLabelText("Crise"));
    fireEvent.change(within(form).getByLabelText(/Motif/), { target: { value: "abc" } });
    fireEvent.click(within(form).getByRole("button", { name: "Appliquer" }));
    expect(within(form).getByText("Le motif compte entre 5 et 500 caractères.")).toBeInTheDocument();
    fireEvent.change(within(form).getByLabelText(/Motif/), { target: { value: "Pluies torrentielles" } });
    fireEvent.click(within(form).getByRole("button", { name: "Appliquer" }));
    fireEvent.click(within(form).getByRole("button", { name: "Confirmer le changement" }));
    expect(await within(form).findByText("Votre rôle ne permet pas ce niveau ou ce gouvernorat.")).toBeInTheDocument();
    expect(setLevels).toHaveBeenCalledWith({ gouvernorat_codes: [61], level: "crisis", reason: "Pluies torrentielles" });
  });

  it("lists directives with acknowledgements and lets the targeted local committee acknowledge", async () => {
    const directive = makeDirective({ title: "Renforcer la permanence", body: "Doubler les équipes de nuit." });
    const acknowledgeDirective = vi.fn(() => Promise.resolve({ ...directive, pending_acks: [] }));
    const directives = vi.fn(() => Promise.resolve({ items: [directive], next_cursor: null }));
    setup(LOCAL, { directives, acknowledgeDirective });
    const list = await screen.findByRole("list", { name: "Directives" });
    const item = within(list).getByText("Renforcer la permanence").closest("li") as HTMLElement;
    expect(within(item).getByText("Urgente")).toBeInTheDocument();
    expect(within(item).getByText("En attente :")).toBeInTheDocument();
    fireEvent.change(within(item).getByLabelText("Note (facultative)"), { target: { value: "Bien reçu" } });
    fireEvent.click(within(item).getByRole("button", { name: "Accuser réception" }));
    await waitFor(() => expect(acknowledgeDirective).toHaveBeenCalledWith("d-1", "Bien reçu"));

    fireEvent.click(screen.getByLabelText("En attente d’accusé de réception seulement"));
    await waitFor(() => expect(directives).toHaveBeenCalledWith(expect.objectContaining({ pending: true })));
  });

  it("issues a national directive (no selection = all gouvernorats)", async () => {
    const issueDirective = vi.fn(() => Promise.resolve(makeDirective()));
    setup(CENTRAL, { issueDirective });
    const form = await screen.findByRole("form", { name: "Émettre une directive" });
    fireEvent.click(within(form).getByRole("button", { name: "Émettre" }));
    expect(within(form).getByText("Le titre compte entre 3 et 150 caractères.")).toBeInTheDocument();
    fireEvent.change(within(form).getByLabelText("Titre"), { target: { value: "Vigilance orange" } });
    fireEvent.change(within(form).getByLabelText("Texte de la directive"), { target: { value: "Mobiliser les unités." } });
    fireEvent.click(within(form).getByLabelText("Urgente"));
    fireEvent.click(within(form).getByRole("button", { name: "Émettre" }));
    await waitFor(() =>
      expect(issueDirective).toHaveBeenCalledWith({
        title: "Vigilance orange",
        body: "Mobiliser les unités.",
        urgency: "urgent",
        gouvernorat_codes: [],
      }),
    );
    expect(await screen.findByText(/Directive émise/)).toBeInTheDocument();
  });

  it("shows performance per gouvernorat with a national total, and no directives for an operations manager", async () => {
    const performance = vi.fn(() =>
      Promise.resolve(
        makePerformance([makePerformanceRow(), makePerformanceRow({ gouvernorat_code: 11, level: "crisis", reports: 30 })]),
      ),
    );
    setup(MANAGER, { performance });
    const table = await screen.findByRole("table", { name: "Suivi de la performance" });
    const sfax = within(table).getByRole("row", { name: /Sfax/ });
    expect(within(sfax).getByText("4 min")).toBeInTheDocument();
    expect(within(sfax).getByText("1 h 30 min")).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /Total/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Directives" })).not.toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Changer le niveau" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Période"), { target: { value: "7" } });
    await waitFor(() => expect(performance).toHaveBeenCalledTimes(2));
  });

  it("rounds the performance window to the hour", () => {
    const since = sinceFor(7, Date.parse("2026-10-19T10:37:12Z"));
    expect(new Date(since).getMinutes()).toBe(0);
    expect(Date.parse("2026-10-19T10:37:12Z") - Date.parse(since)).toBeGreaterThanOrEqual(7 * 86_400_000);
  });
});
