// covers: phase B1 (docs/phase-b/design.md §2.3, §2.4): layers page and the live map switcher.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { LayerImportDetail, MapLayer, MapLayers } from "../lib/layers";
import { fakeApi, fakeAuth, fakeLayersApi, LAYER_L1A, OPERATOR_CLAIMS, renderApp } from "../test/render";
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
    ...LAYER_L1A,
    audiences: [...LAYER_L1A.audiences],
    scope: [],
    fields: { manager: [...LAYER_L1A.fields.manager] },
    ...extra,
  };
}

function list(items: MapLayer[], canManage = true): MapLayers {
  return {
    items,
    deleted: [],
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
    expect(await screen.findByText("Lieux (3)")).toBeInTheDocument();
    // Since phase L1a the imports, the export and the settings are for the administrator and the layer's editors.
    expect(screen.queryByText("Historique des imports")).not.toBeInTheDocument();
    expect(screen.queryByText("Qui voit la couche")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Supprimer la couche" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nouvelle couche" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Fichier")).not.toBeInTheDocument();
    expect(screen.queryByText("Réglages de la couche")).not.toBeInTheDocument();
  });

  it("publishes a draft for some audiences, with a reason (phase L1a)", async () => {
    const updateLayer = vi.fn(() => Promise.resolve(layer({ status: "published" })));
    const api = fakeApi({
      ...fakeLayersApi(),
      layers: vi.fn(() =>
        Promise.resolve(list([layer({ status: "draft", enabled: false, quality: { suggested: 4, duplicates: 0, deleted: 0 } })])),
      ),
      updateLayer,
    });
    renderApp(<LayersPage />, { api, auth: fakeAuth(SYSADMIN), lang: "fr" });
    expect(await screen.findByText("Brouillon")).toBeInTheDocument();
    expect(screen.getByText("Noms à revoir : 4")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ouvrir" }));
    const card = (await screen.findByText("Qui voit la couche")).closest("form");
    expect(card).not.toBeNull();
    const form = within(card as HTMLElement);
    fireEvent.click(form.getByRole("radio", { name: "Publiée" }));
    fireEvent.click(form.getByRole("checkbox", { name: "Citoyen" }));
    fireEvent.click(form.getByRole("checkbox", { name: "Administration et soutien" }));
    fireEvent.change(form.getByLabelText("Motif de la modification"), { target: { value: "Liste vérifiée" } });
    fireEvent.click(form.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(updateLayer).toHaveBeenCalledTimes(1));
    expect(updateLayer.mock.calls[0]).toMatchObject([
      "hopitaux",
      { status: "published", audiences: ["room", "field", "command"], version: 1, reason: "Liste vérifiée" },
    ]);
  });

  it("a sensitive layer: no audience to choose, the minister alone", async () => {
    const api = fakeApi({ ...fakeLayersApi(), layers: vi.fn(() => Promise.resolve(list([layer()]))) });
    renderApp(<LayersPage />, { api, auth: fakeAuth(SYSADMIN), lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Ouvrir" }));
    fireEvent.click(await screen.findByRole("checkbox", { name: "Couche sensible (le ministre seul)" }));
    expect(screen.getByText(/jamais le gouverneur/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Citoyen" })).toBeDisabled();
  });

  it("deletes a layer with a reason chip, then restores it from the deleted tab", async () => {
    const deleted = layer({ deleted_at: "2026-10-27T08:00:00Z", delete_reason: "En double", purge_at: "2026-11-26T08:00:00Z" });
    const deleteLayer = vi.fn(() => Promise.resolve(deleted));
    const restoreLayer = vi.fn(() => Promise.resolve(layer({ status: "paused" })));
    const api = fakeApi({
      ...fakeLayersApi(),
      layers: vi.fn(() => Promise.resolve({ ...list([layer()]), deleted: [{ ...deleted, key: "old", id: "l9" }] })),
      deleteLayer,
      restoreLayer,
    });
    renderApp(<LayersPage />, { api, auth: fakeAuth(SYSADMIN), lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Ouvrir" }));
    fireEvent.click(await screen.findByRole("button", { name: "Supprimer la couche" }));
    const confirm = screen.getByRole("button", { name: "Confirmer la suppression de « Hôpitaux »" });
    fireEvent.click(confirm);
    expect(await screen.findByText("Choisissez le motif.")).toBeInTheDocument();
    expect(deleteLayer).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("radio", { name: "En double" }));
    fireEvent.click(confirm);
    await waitFor(() => expect(deleteLayer).toHaveBeenCalledWith("hopitaux", "En double"));

    fireEvent.click(screen.getByRole("tab", { name: "Supprimées (1)" }));
    fireEvent.click(await screen.findByRole("button", { name: "Restaurer" }));
    fireEvent.change(screen.getByLabelText("Motif de la modification"), { target: { value: "Supprimée par erreur" } });
    fireEvent.click(screen.getByRole("button", { name: "Restaurer (revient suspendue)" }));
    await waitFor(() => expect(restoreLayer).toHaveBeenCalledWith("old", "Supprimée par erreur"));
  });

  it("moves a layer to another folder and manages the folders (phase UI-3b)", async () => {
    const folder = (key: string, fr: string, position: number, count: number, sensitive = false) => ({
      key,
      name: { ar: fr, fr, en: fr },
      icon: "medicalServices",
      tone: "pink",
      position,
      sensitive,
      layer_count: count,
    });
    const groups = [
      folder("health", "Établissements de santé", 2, 1),
      folder("transport", "Transports", 6, 0),
      folder("sensitive", "Couches sensibles", 11, 0, true),
      folder("other", "Autres couches", 12, 0),
    ];
    const updateLayer = vi.fn(() => Promise.resolve(layer({ group: "transport" })));
    const createLayerGroup = vi.fn(() => Promise.resolve(folder("depots", "Dépôts", 13, 0)));
    const deleteLayerGroup = vi.fn(() => Promise.resolve(undefined));
    const api = fakeApi({
      ...fakeLayersApi(),
      layers: vi.fn(() => Promise.resolve({ ...list([layer({ group: "health" })]), groups })),
      updateLayer,
      createLayerGroup,
      deleteLayerGroup,
    });
    renderApp(<LayersPage />, { api, auth: fakeAuth(SYSADMIN), lang: "fr" });
    expect(await screen.findByRole("cell", { name: "Établissements de santé" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ouvrir" }));
    // The sensitive folder is not offered for an ordinary layer.
    const pick = await screen.findByRole("combobox", { name: "Dossier sur la carte" });
    expect(within(pick).queryByRole("option", { name: "Couches sensibles" })).not.toBeInTheDocument();
    fireEvent.change(pick, { target: { value: "transport" } });
    const card = pick.closest("form") as HTMLElement;
    fireEvent.change(within(card).getByLabelText("Motif de la modification"), { target: { value: "Bon dossier" } });
    fireEvent.click(within(card).getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(updateLayer).toHaveBeenCalledTimes(1));
    expect(updateLayer.mock.calls[0]).toMatchObject(["hopitaux", { group_key: "transport", reason: "Bon dossier" }]);

    fireEvent.click(screen.getByRole("tab", { name: "Dossiers de la carte (4)" }));
    // A folder with layers, and the permanent folders, cannot be deleted; an empty one can.
    expect(screen.getByText("Contient des couches")).toBeInTheDocument();
    expect(screen.getAllByText("Dossier permanent")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Supprimer le dossier Transports" }));
    await waitFor(() => expect(deleteLayerGroup).toHaveBeenCalledWith("transport"));

    fireEvent.click(screen.getByRole("button", { name: "Nouveau dossier" }));
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(await screen.findByText(/Saisissez le nom du dossier/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Nom en arabe"), { target: { value: "المستودعات" } });
    fireEvent.change(screen.getByLabelText("Nom en français"), { target: { value: "Dépôts" } });
    fireEvent.change(screen.getByLabelText("Nom en anglais"), { target: { value: "Depots" } });
    fireEvent.click(screen.getByRole("radio", { name: "Stocks" }));
    fireEvent.click(screen.getByRole("radio", { name: "Ambre" }));
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() =>
      expect(createLayerGroup).toHaveBeenCalledWith({
        key: "depots",
        name: { ar: "المستودعات", fr: "Dépôts", en: "Depots" },
        icon: "inventory2",
        tone: "amber",
        position: 13,
      }),
    );
  });

  it("reviews suggested names: accepts every high one at once", async () => {
    const suggested = {
      id: "f1",
      ref: "osm:node/1",
      name: "Établissement près de Sahloul",
      kind: null,
      phone: null,
      lat: 35.8,
      lon: 10.6,
      gouvernorat_code: 51,
      delegation_id: null,
      props: {},
      hidden: false,
      version: 1,
      updated_at: "2026-10-27T08:00:00Z",
      geometry: "point" as const,
      name_status: "suggested" as const,
      suggested_name: "Établissement près de Sahloul",
      name_confidence: "high" as const,
      name_source: "localité la plus proche",
      source_url: "https://www.openstreetmap.org/node/1",
      snapshot_at: "2026-10-27",
      possible_duplicate: false,
      deleted_at: null,
      delete_reason: null,
    };
    const review = vi.fn(() => Promise.resolve({ accepted: 1, edited: 0, rejected: 0, kept: 0, merged: 0 }));
    const api = fakeApi({
      ...fakeLayersApi(),
      layers: vi.fn(() => Promise.resolve(list([layer({ quality: { suggested: 1, duplicates: 0, deleted: 0 } })]))),
      reviewQueue: vi.fn(() => Promise.resolve({ items: [suggested], counts: { high: 1, duplicates: 0 }, total: 1 })),
      review,
    });
    renderApp(<LayersPage />, { api, auth: fakeAuth(SYSADMIN), lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Ouvrir" }));
    expect(await screen.findByText("Établissement près de Sahloul")).toBeInTheDocument();
    const section = (await screen.findByText("Revue des noms")).closest("section") as HTMLElement;
    fireEvent.change(within(section).getByLabelText("Motif de la modification"), { target: { value: "Noms vérifiés" } });
    fireEvent.click(within(section).getByRole("button", { name: "Accepter les confirmés et élevés (1)" }));
    await waitFor(() =>
      expect(review).toHaveBeenCalledWith("hopitaux", { accept_confidence: ["confirmed", "high"], reason: "Noms vérifiés" }),
    );
    expect(await within(section).findByText(/1 accepté/)).toBeInTheDocument();
  });
});
