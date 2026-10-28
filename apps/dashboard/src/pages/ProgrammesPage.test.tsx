// covers: phase L2 (docs/phase-l/design-l2.md §2.2 to §2.7): programme list, new draft, import with preview and diff,
// programme page with filters, map, life cycle, daily follow-up, points and versions.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { filterPoints, isLowCoverage, totalGaps } from "../lib/programmes";
import { OPS_MANAGER_CLAIMS } from "../test/phase9Fixtures";
import { DETAIL, fakeProgrammesApi, POINT_OPEN, POINT_UNLOCATED, PREVIEW, PROGRAMME } from "../test/programmeFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { ProgrammeDetailPage } from "./ProgrammeDetailPage";
import { ProgrammesPage } from "./ProgrammesPage";

vi.mock("../components/LazyMap", () => ({
  LazyMapView: (props: { ariaLabel: string; pois?: { title: string; colour?: string }[] }) => (
    <div data-testid="map" aria-label={props.ariaLabel}>
      {props.pois?.map((p) => (
        <span key={p.title}>{`${p.title} ${p.colour ?? ""}`}</span>
      ))}
    </div>
  ),
}));

vi.mock("../components/LazyPolygonMap", () => ({
  LazyPolygonDrawMap: ({
    onAddVertex,
    ariaLabel,
  }: {
    onAddVertex?: (lon: number, lat: number) => void;
    ariaLabel: string;
  }) => (
    <div role="img" aria-label={ariaLabel}>
      <button type="button" onClick={() => onAddVertex?.(10.1234567, 36.7654321)}>
        map click
      </button>
    </div>
  ),
}));

const NATIONAL_MANAGER = { ...OPS_MANAGER_CLAIMS, gouvernorat_code: undefined, scope_level: "national" };

function detailPage(api = fakeProgrammesApi(), claims: Record<string, unknown> = NATIONAL_MANAGER) {
  renderApp(<ProgrammeDetailPage />, {
    lang: "fr",
    api: fakeApi(api),
    auth: fakeAuth(claims),
    path: `/programmes/${PROGRAMME.id}`,
    route: "/programmes/:id",
  });
  return api;
}

describe("programme helpers", () => {
  it("filters points and flags low coverage and total gaps", () => {
    expect(isLowCoverage(POINT_OPEN)).toBe(true); // 2 of 8
    expect(isLowCoverage(POINT_UNLOCATED)).toBe(false); // 2 of 2
    expect(filterPoints(DETAIL.points, { confidence: "unlocated" }).map((p) => p.ref)).toEqual(["BEACH-2026-002"]);
    expect(filterPoints(DETAIL.points, { lowCoverage: true, text: "corniche" })).toHaveLength(1);
    expect(filterPoints(DETAIL.points, { gouvernorat: 51, status: "open" })).toHaveLength(0);
    expect(totalGaps({ lifeguards_planned: 2154, staff: 30 }, { lifeguards_planned: 2127, staff: 30 })).toEqual([
      ["lifeguards_planned", 2154, 2127],
    ]);
  });
});

describe("ProgrammesPage", () => {
  it("lists the programmes with their status, dates and lifeguard coverage", async () => {
    renderApp(<ProgrammesPage />, { lang: "fr" });
    expect(await screen.findByRole("heading", { name: "Programmes saisonniers" })).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: "Les programmes" });
    const row = within(table).getByRole("link", { name: PROGRAMME.title }).closest("tr") as HTMLElement;
    expect(within(row).getByText("Approuvé")).toBeInTheDocument();
    expect(within(row).getByText("Sur la carte")).toBeInTheDocument();
    expect(within(row).getByText(/40\s?%/)).toBeInTheDocument();
    expect(within(row).getByText("1 sans position")).toBeInTheDocument();
    expect(within(table).getByText("Brouillon")).toBeInTheDocument();
  });

  it("checks a new programme before creating the draft", async () => {
    const api = fakeProgrammesApi();
    renderApp(<ProgrammesPage />, { lang: "fr", api: fakeApi(api) });
    fireEvent.click(await screen.findByRole("button", { name: "Nouveau programme" }));
    fireEvent.change(screen.getByLabelText("Identifiant"), { target: { value: "road 2026" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer le brouillon" }));
    expect(screen.getByLabelText("Identifiant")).toHaveAttribute("aria-invalid", "true");
    expect(api.createProgramme).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Identifiant"), { target: { value: "road-2027" } });
    fireEvent.change(screen.getByLabelText("Intitulé"), { target: { value: "Secours routier 2027" } });
    fireEvent.change(screen.getByLabelText("Début"), { target: { value: "2027-06-15" } });
    fireEvent.change(screen.getByLabelText("Fin"), { target: { value: "2027-09-15" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer le brouillon" }));
    await waitFor(() =>
      expect(api.createProgramme).toHaveBeenCalledWith(
        expect.objectContaining({ code: "ROAD-2027", kind: "road", valid_from: "2027-06-15" }),
      ),
    );
  });

  it("previews an import: errors, warnings, totals gap and the differences of a new version", async () => {
    const api = fakeProgrammesApi();
    renderApp(<ProgrammesPage />, { lang: "fr", api: fakeApi(api) });
    fireEvent.click(await screen.findByRole("button", { name: "Importer un fichier" }));
    const file = new File(["x"], "programmes.xlsx");
    fireEvent.change(screen.getByLabelText("Fichier"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Vérifier le fichier" }));
    expect(await screen.findByText(/Coordonnées hors de Tunisie \(48.1,2.3\) \(ligne 12/)).toBeInTheDocument();
    expect(screen.getByText(/Le total des sauveteurs prévus déclaré diffère/)).toBeInTheDocument();
    expect(
      screen.getByText(/sauveteurs prévus : 2\s?154 déclarés, 2\s?127 d’après les points/),
    ).toBeInTheDocument();
    expect(screen.getByText("Nouvelle version")).toBeInTheDocument();
    expect(screen.getByText("1 ajoutés, 0 retirés, 1 modifiés")).toBeInTheDocument();
    // With errors, nothing can be saved: the file is corrected first.
    expect(screen.queryByRole("button", { name: "Enregistrer l’import" })).not.toBeInTheDocument();
    expect(screen.getByText(/Corrigez les erreurs/)).toBeInTheDocument();
    expect(api.importProgrammes).toHaveBeenCalledWith(file, false);
  });

  it("saves a clean import with its reason", async () => {
    const api = fakeProgrammesApi();
    api.importProgrammes = vi.fn((_f: File, apply: boolean) =>
      Promise.resolve({ ...PREVIEW, errors: [], applied: apply }),
    );
    renderApp(<ProgrammesPage />, { lang: "fr", api: fakeApi(api) });
    fireEvent.click(await screen.findByRole("button", { name: "Importer un fichier" }));
    fireEvent.change(screen.getByLabelText("Fichier"), { target: { files: [new File(["x"], "p.csv")] } });
    fireEvent.click(screen.getByRole("button", { name: "Vérifier le fichier" }));
    const save = await screen.findByRole("button", { name: "Enregistrer l’import" });
    fireEvent.click(save);
    expect(api.importProgrammes).toHaveBeenCalledTimes(1); // the reason is required
    fireEvent.change(screen.getByLabelText("Motif (obligatoire)"), { target: { value: "Programme corrigé" } });
    fireEvent.click(save);
    expect(await screen.findByText("Import enregistré.")).toBeInTheDocument();
    expect(api.importProgrammes).toHaveBeenLastCalledWith(expect.any(File), true, "Programme corrigé");
  });
});

describe("ProgrammeDetailPage", () => {
  it("shows the figures, the points on the map, the supervisor for the room and filters the points", async () => {
    detailPage();
    expect(await screen.findByRole("heading", { name: PROGRAMME.title })).toBeInTheDocument();
    const kpis = screen.getByLabelText("Chiffres du programme");
    expect(within(kpis).getByText("Sans position").nextSibling).toHaveTextContent("1");
    // Only located points are drawn, in their status colour.
    const map = screen.getByTestId("map");
    expect(map).toHaveTextContent("Plage de la Corniche #188038");
    expect(map).not.toHaveTextContent("Boujaafar");
    const table = screen.getByRole("table", { name: "Points : 2" });
    expect(within(table).getByText("Responsable A")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "+216 70 000 000" })).toHaveAttribute("href", "tel:+216 70 000 000");
    expect(within(table).getByText("Faible")).toBeInTheDocument();
    // The declared total differs from the points: shown, not blocking.
    expect(screen.getByText(/2\s?154 déclarés, 10 d’après les points/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Précision de la position"), { target: { value: "unlocated" } });
    expect(screen.getByRole("table", { name: "Points : 1" })).toHaveTextContent("Plage Boujaafar");
  });

  it("hides the supervisor column from readers outside the operations room", async () => {
    detailPage(fakeProgrammesApi(), {
      sub: "u-cc",
      name: "Mounir Committee",
      realm_access: { roles: ["central_committee"] },
      scope_level: "national",
    });
    const table = await screen.findByRole("table", { name: "Points : 2" });
    expect(within(table).queryByText("Responsable")).not.toBeInTheDocument();
  });

  it("cancels an approved programme only with a reason", async () => {
    const api = detailPage();
    fireEvent.click(await screen.findByRole("button", { name: "Annuler le programme" }));
    const dialog = screen.getByRole("dialog", { name: "Annuler le programme" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Annuler le programme" }));
    expect(api.cancelProgramme).not.toHaveBeenCalled();
    fireEvent.change(within(dialog).getByLabelText("Motif (obligatoire)"), { target: { value: "Saison écourtée" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Annuler le programme" }));
    await waitFor(() => expect(api.cancelProgramme).toHaveBeenCalledWith(PROGRAMME.id, "Saison écourtée"));
    expect(await screen.findByText("Annulé : annulé")).toBeInTheDocument();
  });

  it("adds a point placed by a click on the map", async () => {
    const api = detailPage();
    fireEvent.click(await screen.findByRole("button", { name: "Ajouter un point" }));
    const dialog = screen.getByRole("dialog", { name: "Ajouter un point" });
    fireEvent.change(within(dialog).getByLabelText("Référence du point"), { target: { value: "BEACH-2026-003" } });
    fireEvent.change(within(dialog).getByLabelText("Lieu"), { target: { value: "Plage de Raoued" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "map click" }));
    expect(within(dialog).getByLabelText("Latitude")).toHaveValue(36.765432);
    fireEvent.change(within(dialog).getByLabelText("Motif (obligatoire)"), { target: { value: "Nouvelle plage" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Enregistrer le point" }));
    await waitFor(() =>
      expect(api.addProgrammePoint).toHaveBeenCalledWith(
        PROGRAMME.id,
        expect.objectContaining({
          ref: "BEACH-2026-003",
          place_name: "Plage de Raoued",
          lat: 36.765432,
          lon: 10.123457,
          geo_confidence: "confirmed",
          reason: "Nouvelle plage",
        }),
      ),
    );
  });

  it("lets the regional room follow up its points: status, lifeguards deployed and a note", async () => {
    const api = fakeProgrammesApi();
    api.programme = vi.fn(() => Promise.resolve({ ...DETAIL, programme: { ...PROGRAMME, can_edit: false } }));
    detailPage(api, OPS_MANAGER_CLAIMS);
    const follow = await screen.findAllByRole("button", { name: /^Suivi du jour/ });
    expect(screen.queryByRole("button", { name: "Annuler le programme" })).not.toBeInTheDocument();
    fireEvent.click(follow[0] as HTMLElement);
    const dialog = screen.getByRole("dialog", { name: "Suivi du jour : Plage de la Corniche" });
    fireEvent.change(within(dialog).getByLabelText("Statut"), { target: { value: "closed" } });
    fireEvent.change(within(dialog).getByLabelText("Sauveteurs déployés"), { target: { value: "6" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Enregistrer le suivi" }));
    await waitFor(() =>
      expect(api.updateProgrammePoint).toHaveBeenCalledWith(PROGRAMME.id, POINT_OPEN.id, {
        status: "closed",
        lifeguards_deployed: 6,
        reason: "",
      }),
    );
  });

  it("shows the differences of a version and goes back to an earlier one with a reason", async () => {
    const api = detailPage();
    fireEvent.click(await screen.findByRole("button", { name: "Différences de v3" }));
    expect(await screen.findByText(/Sauveteurs déployés 0 → 2/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Revenir à v1" }));
    const dialog = screen.getByRole("dialog", { name: "Revenir à la version 1" });
    fireEvent.change(within(dialog).getByLabelText("Motif (obligatoire)"), { target: { value: "Erreur de saisie" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Revenir à cette version" }));
    await waitFor(() => expect(api.restoreProgramme).toHaveBeenCalledWith(PROGRAMME.id, 1, "Erreur de saisie"));
  });
});
