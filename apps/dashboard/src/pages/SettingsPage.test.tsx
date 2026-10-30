// covers: phase A (docs/phase-a/design.md §2.4, §2.6): release and refused words in the national settings.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { PlatformSetting } from "../lib/phase9Types";
import { makeSettings } from "../test/phase9Fixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { SettingsPage } from "./SettingsPage";

const SYSADMIN = { ...OPERATOR_CLAIMS, realm_access: { roles: ["sysadmin"] }, scope_level: "national" };

function settings(editable: boolean): PlatformSetting[] {
  const base = { version: 1, updated_by_name: null, updated_at: null, editable };
  return [
    ...makeSettings(editable),
    {
      ...base,
      key: "app.release",
      value: {
        latest_version: "0.2.0",
        latest_build: 1,
        min_build: 1,
        notes: { ar: "", fr: "", en: "" },
        channel: "server",
        download_url: null,
      },
    },
    { ...base, key: "moderation.extra_terms", value: ["mot1"] },
  ];
}

function setup(editable = true) {
  const save = vi.fn((key: string, body: { value: unknown; version: number }) =>
    Promise.resolve({ key, value: body.value, version: body.version + 1, updated_by_name: "Admin", updated_at: "2026-10-23T09:00:00Z", editable }),
  );
  const api = fakeApi({
    platformSettings: vi.fn(() => Promise.resolve(settings(editable))),
    savePlatformSetting: save,
  });
  renderApp(<SettingsPage />, { api, auth: fakeAuth(SYSADMIN), lang: "fr" });
  return save;
}

const REASON = "Publication de la version 0.3.0";

/** The setting card holding [el]: its reason and its save button. */
function card(el: HTMLElement) {
  const section = el.closest("section");
  if (!section) throw new Error("not inside a setting card");
  const scope = within(section);
  return {
    reason: (text: string) => fireEvent.change(scope.getByLabelText("Motif de la modification"), { target: { value: text } }),
    save: () => fireEvent.click(scope.getByRole("button", { name: "Enregistrer" })),
  };
}

describe("SettingsPage, phase A", () => {
  it("publishes a release: a server release needs its download address", async () => {
    const save = setup();
    const latest = await screen.findByLabelText("Numéro de build le plus récent");
    const form = card(latest);
    fireEvent.change(screen.getByLabelText("Dernière version"), { target: { value: "0.3.0" } });
    fireEvent.change(latest, { target: { value: "2" } });
    form.reason(REASON);
    form.save();
    expect(await screen.findByText("Une version sur notre serveur a besoin de son adresse de téléchargement.")).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Adresse de téléchargement (https)"), {
      target: { value: "https://apk.ehimaya.tn/ehimaya-0.3.0.apk" },
    });
    fireEvent.change(screen.getByLabelText("Nouveautés (français)"), { target: { value: "Connexion par SMS" } });
    form.save();
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(save).toHaveBeenCalledWith("app.release", {
      reason: REASON,
      version: 1,
      value: {
        latest_version: "0.3.0",
        latest_build: 2,
        min_build: 1,
        channel: "server",
        download_url: "https://apk.ehimaya.tn/ehimaya-0.3.0.apk",
        notes: { ar: "", fr: "Connexion par SMS", en: "" },
      },
    });
  });

  it("refuses a minimum build above the latest one", async () => {
    const save = setup();
    const min = await screen.findByLabelText("Build minimal autorisé");
    fireEvent.change(min, { target: { value: "5" } });
    const form = card(min);
    form.reason(REASON);
    form.save();
    expect(await screen.findByText("Le build minimal ne peut pas dépasser le build le plus récent.")).toBeInTheDocument();
    expect(min).toHaveAttribute("aria-invalid", "true");
    expect(save).not.toHaveBeenCalled();
  });

  it("saves the refused words, one per line, without duplicates", async () => {
    const save = setup();
    const words = await screen.findByLabelText("Un mot ou une expression par ligne");
    expect(words).toHaveValue("mot1");
    fireEvent.change(words, { target: { value: "mot1\nmot2\n\nmot2" } });
    const form = card(words);
    form.reason("Ajout de deux mots signalés");
    form.save();
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(save).toHaveBeenCalledWith("moderation.extra_terms", expect.objectContaining({ value: ["mot1", "mot2"] }));
  });

  it("required fields: a note and aria-required", async () => {
    setup();
    const version = await screen.findByLabelText("Dernière version");
    expect(version).toHaveAttribute("aria-required", "true");
    expect(screen.getAllByText("Les champs marqués * sont obligatoires.").length).toBeGreaterThanOrEqual(2);
  });

  it("read-only without the right", async () => {
    const save = setup(false);
    const version = await screen.findByLabelText("Dernière version");
    expect(version).toBeDisabled();
    expect(screen.queryByText("Les champs marqués * sont obligatoires.")).not.toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
  });
});

describe("SettingsPage, phase N thresholds", () => {
  it("edits the operational thresholds of one group within their bounds and sends the whole setting", async () => {
    const save = vi.fn((key: string, body: { value: unknown; version: number }) =>
      Promise.resolve({ key, value: body.value, version: body.version + 1, updated_by_name: "Admin", updated_at: "2026-10-30T09:00:00Z", editable: true }),
    );
    const base = { version: 1, updated_by_name: null, updated_at: null, editable: true };
    const api = fakeApi({
      platformSettings: vi.fn(() =>
        Promise.resolve([
          ...settings(true),
          { ...base, key: "operations.thresholds", value: { "alerts.max_days": 7, "doctors.committee_max": 7 } },
        ]),
      ),
      thresholdSpecs: vi.fn(() =>
        Promise.resolve([
          { name: "alerts.max_days", group: "alerts" as const, unit: "days" as const, default: 7, low: 1, high: 30 },
          { name: "doctors.committee_max", group: "partners" as const, unit: "count" as const, default: 7, low: 1, high: 30 },
        ]),
      ),
      savePlatformSetting: save,
    });
    renderApp(<SettingsPage />, { api, auth: fakeAuth(SYSADMIN), lang: "fr" });
    const title = await screen.findByRole("heading", { name: "Seuils des alertes" });
    expect(screen.getByRole("heading", { name: "Seuils des médecins et des établissements" })).toBeInTheDocument();
    const input = screen.getByRole("spinbutton", { name: "Durée maximale d’une alerte" });
    expect(screen.getByText("jours · entre 1 et 30 · par défaut 7")).toBeInTheDocument();
    const c = card(title);
    // Above the bound, the field stops at it; below, the card refuses to save.
    fireEvent.change(input, { target: { value: "45" } });
    expect(input).toHaveValue(30);
    fireEvent.change(input, { target: { value: "0" } });
    c.reason("Alertes de longue durée en hiver");
    c.save();
    expect(await screen.findByText("Chaque valeur est un entier dans les bornes indiquées à côté.")).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "10" } });
    c.save();
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save.mock.calls[0]?.[0]).toBe("operations.thresholds");
    expect(save.mock.calls[0]?.[1].value).toEqual({ "alerts.max_days": 10, "doctors.committee_max": 7 });
  });
});
