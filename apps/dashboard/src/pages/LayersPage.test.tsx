// covers: phase B1 (docs/phase-b/design.md §2.3, §2.4): layers page and the live map switcher.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { LayerImportDetail, MapLayer, MapLayers } from "../lib/layers";
import { fakeApi, fakeAuth, fakeLayersApi, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { LayersPage } from "./LayersPage";

const SYSADMIN = { ...OPERATOR_CLAIMS, realm_access: { roles: ["sysadmin"] }, scope_level: "national" };

function layer(extra: Partial<MapLayer> = {}): MapLayer {
  return {
    id: "l1",
    key: "hopitaux",
    name: { ar: "المستشفيات", fr: "Hôpitaux", en: "Hospitals" },
    icon: "hospital",
    colour: "#C62828",
    audience: "public",
    source: "OpenStreetMap",
    licence: "ODbL",
    to_verify: true,
    simulated: false,
    staff_only: ["manager"],
    editors_allowed: false,
    enabled: true,
    version: 1,
    data_version: 1,
    feature_count: 3,
    hidden_count: 0,
    updated_by_name: "Admin",
    updated_at: "2026-10-23T09:00:00Z",
    last_import: null,
    can_manage: true,
    can_import: true,
    ...extra,
  };
}

function list(items: MapLayer[], canManage = true): MapLayers {
  return {
    items,
    can_manage: canManage,
    icons: [],
    palette: ["#C62828", "#2E7D32"],
    limits: { file_bytes: 10 * 1024 * 1024, rows: 50_000 },
  };
}

const PREVIEW: LayerImportDetail = {
  id: "imp1",
  file_name: "hopitaux.csv",
  format: "csv",
  mode: "merge",
  status: "preview",
  counts: { new: 2, updated: 1, unchanged: 0, removed: 0, rejected: 1, warnings: 0 },
  rejected: [{ line: 4, reason: "outside_tunisia", name: "Hors frontière" }],
  warnings: [],
  reason: null,
  created_by_name: "Admin",
  created_at: "2026-10-23T09:00:00Z",
  applied_at: null,
  undone_at: null,
  expired: false,
  can_apply: true,
  can_undo: false,
  points: [],
};

describe("LayersPage", () => {
  it("creates a layer: names in three languages, key proposed, reason required", async () => {
    const createLayer = vi.fn((body: { key: string }) => Promise.resolve(layer({ key: body.key })));
    const api = fakeApi({
      ...fakeLayersApi(),
      layers: vi.fn(() => Promise.resolve(list([]))),
      createLayer,
    });
    renderApp(<LayersPage />, { api, auth: fakeAuth(SYSADMIN), lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Nouvelle couche" }));
    fireEvent.change(screen.getByLabelText("Nom en arabe"), { target: { value: "مقرات الإيواء" } });
    fireEvent.change(screen.getByLabelText("Nom en français"), { target: { value: "Centres d’hébergement" } });
    fireEvent.change(screen.getByLabelText("Nom en anglais"), { target: { value: "Shelters" } });
    expect(screen.getByLabelText("Identifiant technique")).toHaveValue("centres_d_hebergement");
    fireEvent.click(screen.getByRole("radio", { name: "Hébergement" }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Données approximatives d'essai \[SIM\]/ }));
    fireEvent.click(screen.getByRole("button", { name: "Créer la couche" }));
    expect(createLayer).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Motif de la modification"), { target: { value: "Liste du ministère" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer la couche" }));
    await waitFor(() => expect(createLayer).toHaveBeenCalledTimes(1));
    expect(createLayer.mock.calls[0]?.[0]).toMatchObject({
      key: "centres_d_hebergement",
      icon: "shelter",
      audience: "staff",
      simulated: true,
      staff_only: ["manager"],
      reason: "Liste du ministère",
    });
  });

  it("marks a layer of approximate trial places with [SIM]", async () => {
    const api = fakeApi({
      ...fakeLayersApi(),
      layers: vi.fn(() => Promise.resolve(list([layer({ simulated: true }), layer({ key: "abris", id: "l2" })]))),
    });
    renderApp(<LayersPage />, { api, auth: fakeAuth(SYSADMIN), lang: "fr" });
    const rows = await screen.findAllByRole("row");
    const hopitaux = rows.find((r) => within(r).queryByText("Hôpitaux") && r.textContent.includes("[SIM]"));
    expect(hopitaux).toBeDefined();
    expect(screen.getAllByTitle("Lieux approximatifs inventés (simulation)").length).toBeGreaterThanOrEqual(1);
  });

  it("previews a file, shows the rejected rows, publishes with a reason", async () => {
    const previewImport = vi.fn(() => Promise.resolve(PREVIEW));
    const applyImport = vi.fn(() => Promise.resolve({ ...PREVIEW, status: "applied" as const }));
    const api = fakeApi({
      ...fakeLayersApi(),
      layers: vi.fn(() => Promise.resolve(list([layer()]))),
      previewImport,
      applyImport,
    });
    renderApp(<LayersPage />, { api, auth: fakeAuth(SYSADMIN), lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Ouvrir" }));
    const file = new File(["nom,lat,lon\nA,36.8,10.18\n"], "hopitaux.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("Fichier"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("radio", { name: /Remplacer/ }));
    fireEvent.click(screen.getByRole("button", { name: "Aperçu" }));
    await waitFor(() => expect(previewImport).toHaveBeenCalledWith("hopitaux", file, "replace"));
    const rejected = await screen.findByRole("region", { name: "Lignes rejetées" });
    expect(within(rejected).getByText("Position hors de Tunisie")).toBeInTheDocument();
    expect(within(rejected).getByText("Hors frontière")).toBeInTheDocument();

    const publish = screen.getByRole("button", { name: "Publier sur la carte" });
    const form = publish.closest("form");
    if (!form) throw new Error("no form");
    fireEvent.change(within(form).getByLabelText("Motif de la modification"), { target: { value: "Liste officielle" } });
    fireEvent.click(publish);
    await waitFor(() => expect(applyImport).toHaveBeenCalledWith("hopitaux", "imp1", "Liste officielle"));
    expect(await screen.findByText("Import publié.")).toBeInTheDocument();
  });

  it("a content editor without import rights only reads", async () => {
    const editor = { ...OPERATOR_CLAIMS, realm_access: { roles: ["content_editor"] }, scope_level: "national" };
    const api = fakeApi({
      ...fakeLayersApi(),
      layers: vi.fn(() => Promise.resolve(list([layer({ can_manage: false, can_import: false })], false))),
    });
    renderApp(<LayersPage />, { api, auth: fakeAuth(editor), lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Ouvrir" }));
    expect(await screen.findByText("Historique des imports")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nouvelle couche" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Fichier")).not.toBeInTheDocument();
    expect(screen.queryByText("Réglages de la couche")).not.toBeInTheDocument();
  });
});
