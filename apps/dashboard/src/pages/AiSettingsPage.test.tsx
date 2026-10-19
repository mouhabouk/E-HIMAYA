import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { AI_SETTINGS, AI_STATUS_READY } from "../test/fixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { AiSettingsPage } from "./AiSettingsPage";

const CENTRAL = { ...OPERATOR_CLAIMS, realm_access: { roles: ["central_committee"] }, scope_level: "national" };

function setup(overrides: Parameters<typeof fakeApi>[0] = {}, claims: Record<string, unknown> = CENTRAL) {
  const api = fakeApi({ aiSettings: vi.fn(() => Promise.resolve(AI_SETTINGS)), ...overrides });
  return renderApp(<AiSettingsPage />, { api, auth: fakeAuth(claims), lang: "fr" });
}

describe("AiSettingsPage", () => {
  it("validates like the API before saving and shows field errors", async () => {
    const { api } = setup();
    const weather = await screen.findByLabelText("Météo");
    fireEvent.change(weather, { target: { value: "150" } });
    fireEvent.change(screen.getByLabelText("Fenêtre de temps (minutes)", { selector: "[id$='-window']" }), {
      target: { value: "2.5" },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Enregistrer" }));

    expect(screen.getByText("La valeur doit être entre 0 et 100.")).toBeInTheDocument();
    expect(screen.getByText("Saisissez un nombre entier.")).toBeInTheDocument();
    expect(weather).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("Corrigez les champs signalés");
    expect(api.saveAiSettings).not.toHaveBeenCalled();
  });

  it("rejects all-zero weights", async () => {
    const { api } = setup();
    await screen.findByLabelText("Météo");
    for (const label of ["Gravité de la catégorie", "Vies en danger", "Victimes", "Nombre de signalants", "Crédibilité", "Sites sensibles à proximité", "Météo", "Niveau opérationnel"]) {
      fireEvent.change(screen.getByLabelText(label), { target: { value: "0" } });
    }
    fireEvent.click(await screen.findByRole("button", { name: "Enregistrer" }));
    expect(screen.getByText("Les pondérations ne peuvent pas être toutes nulles.")).toBeInTheDocument();
    expect(api.saveAiSettings).not.toHaveBeenCalled();
  });

  it("saves valid settings with PUT", async () => {
    const saved = { ...AI_SETTINGS, priority: { ...AI_SETTINGS.priority, weights: { ...AI_SETTINGS.priority.weights, weather: 8 } } };
    const { api } = setup({ saveAiSettings: vi.fn(() => Promise.resolve(saved)) });
    fireEvent.change(await screen.findByLabelText("Météo"), { target: { value: "8" } });
    fireEvent.click(await screen.findByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(api.saveAiSettings).toHaveBeenCalledWith(saved));
    expect(await screen.findByText("Réglages enregistrés.")).toBeInTheDocument();
  });

  it("shows 403 and 422 answers as translated messages", async () => {
    const save = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(403, "national_scope_required"))
      .mockRejectedValueOnce(new ApiError(422, "validation_error", [{ msg: "weights must…" }]));
    setup({ saveAiSettings: save });
    const button = await screen.findByRole("button", { name: "Enregistrer" });
    await screen.findByLabelText("Météo");
    fireEvent.click(button);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Échec de l’enregistrement des réglages");
    expect(alert).toHaveTextContent("exige un compte de périmètre national");
    fireEvent.click(button);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Certaines données envoyées sont invalides."));
    expect(screen.queryByText(/weights must/)).not.toBeInTheDocument();
  });

  it("is read-only for other roles and for a regional central committee", async () => {
    for (const claims of [OPERATOR_CLAIMS, { ...CENTRAL, scope_level: undefined, gouvernorat_code: "61" }]) {
      const { unmount } = setup({}, claims);
      expect(await screen.findByLabelText("Météo")).toHaveAttribute("readonly");
      expect(screen.getByText(/Consultation seule/)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Enregistrer" })).not.toBeInTheDocument();
      unmount();
    }
  });

  it("shows the AI status per capability", async () => {
    setup({
      aiStatus: vi.fn(() =>
        Promise.resolve({
          ...AI_STATUS_READY,
          capabilities: { ...AI_STATUS_READY.capabilities, extract: { ready: false, model: "qwen3:8b", detail: "down" } },
        }),
      ),
    });
    expect(await screen.findByText("Le service d’IA est configuré.")).toBeInTheDocument();
    const row = screen.getByRole("rowheader", { name: "Extraction par le modèle de langue" }).closest("tr") as HTMLElement;
    expect(within(row).getByText("Indisponible")).toBeInTheDocument();
    expect(within(row).getByText("qwen3:8b")).toBeInTheDocument();
  });

  it("says when the AI service is not configured", async () => {
    setup({ aiStatus: vi.fn(() => Promise.resolve({ configured: false, capabilities: {} })) });
    expect(await screen.findByText(/n’est pas configuré : scores et regroupement/)).toBeInTheDocument();
  });
});
