import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Route, Routes, useLocation } from "react-router";
import { Layout } from "../components/Layout";
import { ApiError } from "../lib/api";
import { makeIncidentDetail } from "../test/fixtures";
import {
  makeBadge,
  makeLibraryReport,
  makeMemoryEntry,
  makeNomination,
  makeScenario,
} from "../test/phase8Fixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { AnalyticsPage } from "./AnalyticsPage";
import { EventsLibraryPage, LibraryItemPage } from "./EventsLibraryPage";
import { IncidentDetailPage } from "./IncidentDetailPage";
import { MemoryEntryPage } from "./MemoryEntryPage";
import { ReportsLibraryPage } from "./ReportsLibraryPage";
import { ReportSchedulesPage } from "./ReportSchedulesPage";
import { RewardCertificatesPage, RewardConfirmationsPage, RewardNominationsPage, RewardRulesPage } from "./RewardsPages";
import { ScenarioDetailPage, ScenariosPage } from "./ScenariosPage";

vi.mock("../components/LazyMap", () => ({
  LazyMapView: (props: { ariaLabel: string; hexes?: unknown[] }) => (
    <div data-testid="map" aria-label={props.ariaLabel} data-hexes={props.hexes?.length ?? 0} />
  ),
}));

const NATIONAL_MANAGER = {
  sub: "5f0c8e4a-1b2c-4d3e-8f90-a1b2c3d4e5f6",
  name: "Hedi Manager",
  realm_access: { roles: ["ops_manager"] },
  scope_level: "national",
};
const CENTRAL = { ...NATIONAL_MANAGER, name: "Nadia Central", realm_access: { roles: ["central_committee"] } };
const EDITOR = { sub: "e-1", name: "Rim Editor", realm_access: { roles: ["content_editor"] }, scope_level: "national" };

function Where() {
  const loc = useLocation();
  return <output data-testid="where">{`${loc.pathname}${loc.search}`}</output>;
}

const at = (pattern: string, el: React.ReactNode) => (
  <>
    <Routes>
      <Route path={pattern} element={el} />
      <Route path="*" element={null} />
    </Routes>
    <Where />
  </>
);

describe("AnalyticsPage", () => {
  it("shows KPIs, a trends table with the seasonal band, breakdowns and hexagons, and keeps filters in the URL", async () => {
    const { api } = renderApp(at("/analytics", <AnalyticsPage />), {
      auth: fakeAuth(NATIONAL_MANAGER),
      lang: "fr",
      path: "/analytics?gouvernorat=61&category=fire",
    });
    expect((await screen.findByText("Reçus")).nextElementSibling).toHaveTextContent(/^1\s240$/);
    expect(api.analyticsOverview).toHaveBeenCalledWith(expect.objectContaining({ gouvernorat: 61, category: "fire" }), expect.anything());
    // Response time table: n = 0 shows dashes.
    const rt = screen.getByRole("table", { name: "Délais d’intervention" });
    expect(within(rt).getByRole("rowheader", { name: "Réception → clôture" }).closest("tr")).toHaveTextContent("—");
    // The chart's data table (jsdom cannot draw: the table is shown) lists the band edges.
    const trend = await screen.findByRole("table", { name: "Données : Évolution : Signalements" });
    expect(within(trend).getByRole("columnheader", { name: "Haut de la plage habituelle" })).toBeInTheDocument();
    expect(screen.getByText("Périodes au-dessus de la plage habituelle : 1")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Par canal" })).toHaveTextContent("Application");
    await waitFor(() => expect(screen.getByTestId("map")).toHaveAttribute("data-hexes", "2"));

    fireEvent.click(screen.getByRole("radio", { name: "Mois" }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("interval=month"));
    expect(screen.getByTestId("where")).toHaveTextContent("gouvernorat=61");

    fireEvent.click(screen.getByRole("button", { name: "Exporter (rapport)" }));
    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent("/reports-library?new=1&kind=gouvernorat_summary"),
    );
  });

  it("hides the export for read-only roles and the gouvernorat filter for regional staff", async () => {
    renderApp(at("/analytics", <AnalyticsPage />), { lang: "fr", path: "/analytics" });
    expect(await screen.findByText("Reçus")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Exporter (rapport)" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Gouvernorat" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Simulation « et si »" })).not.toBeInTheDocument();
  });
});

describe("What-if scenarios", () => {
  it("validates the form and sends the run", async () => {
    const { api } = renderApp(at("/analytics/scenarios", <ScenariosPage />), {
      auth: fakeAuth(NATIONAL_MANAGER),
      lang: "fr",
      path: "/analytics/scenarios",
    });
    fireEvent.click(await screen.findByRole("button", { name: "Lancer la simulation" }));
    expect(screen.getByText("Donnez un nom à la simulation.")).toBeInTheDocument();
    expect(api.runScenario).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole("textbox", { name: "Nom" }), { target: { value: "Canicule" } });
    fireEvent.click(await screen.findByRole("checkbox", { name: "Sfax" }));
    fireEvent.change(screen.getByRole("spinbutton", { name: "Fourgon d’incendie" }), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("radio", { name: "Fortes pluies" }));
    fireEvent.click(screen.getByRole("button", { name: "Lancer la simulation" }));
    await waitFor(() =>
      expect(api.runScenario).toHaveBeenCalledWith({
        name: "Canicule",
        gouvernorats: [61],
        category: "fire",
        demand_factor: 1.5,
        unavailable_resources: { fire_engine: 3 },
        horizon_hours: 24,
        weather: "heavy_rain",
      }),
    );
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/analytics/scenarios/sc-1"));
  });

  it("shows the disclaimer, low confidence reasons, overload hours and assumptions", async () => {
    renderApp(at("/analytics/scenarios/:id", <ScenarioDetailPage />), {
      auth: fakeAuth(NATIONAL_MANAGER),
      lang: "fr",
      path: "/analytics/scenarios/sc-1",
    });
    const note = await screen.findByRole("note");
    expect(note).toHaveTextContent("Aide à la planification, pas une prévision.");
    expect(note).toHaveTextContent("Outil de planification fondé sur l’historique.");
    expect(note).toHaveTextContent("Modèle non calibré");
    expect(note).toHaveTextContent("Historique court (40 jours).");
    expect(screen.getByText("Demande supérieure à la capacité aux heures : +4 h, +5 h")).toBeInTheDocument();
    const demand = screen.getByRole("table", { name: "Données : Signalements par heure (bande 10–90 %)" });
    const rows = within(demand).getAllByRole("row");
    expect(rows[5]).toHaveClass("row--highlight");
    expect(rows[1]).not.toHaveClass("row--highlight");
    expect(screen.getByText("Le rythme d’arrivée historique est rejoué.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Créer un rapport de cette simulation" })).toHaveAttribute(
      "href",
      "/reports-library?new=1&kind=scenario&scenario=sc-1&title=Canicule%20Sfax",
    );
  });

  it("says when a run failed", async () => {
    const api = fakeApi({ scenario: vi.fn(() => Promise.resolve(makeScenario({ status: "failed", result: null }))) });
    renderApp(at("/analytics/scenarios/:id", <ScenarioDetailPage />), { api, auth: fakeAuth(NATIONAL_MANAGER), lang: "fr", path: "/analytics/scenarios/sc-1" });
    expect(await screen.findByText("La simulation a échoué.")).toBeInTheDocument();
  });
});

describe("Reports library", () => {
  it("lists reports, opens the prefilled form and sends it", async () => {
    const { api } = renderApp(at("/reports-library", <ReportsLibraryPage />), {
      auth: fakeAuth(NATIONAL_MANAGER),
      lang: "fr",
      path: "/reports-library?new=1&kind=gouvernorat_summary&from=2026-09-01&to=2026-09-30&gouvernorat=61",
    });
    const row = (await screen.findByRole("rowheader", { name: "Synthèse septembre" })).closest("tr") as HTMLElement;
    expect(within(row).getByText("Prêt")).toBeInTheDocument();
    fireEvent.click(within(row).getByRole("button", { name: /Synthèse septembre/ }));
    await waitFor(() => expect(api.libraryReportLink).toHaveBeenCalledWith("rep-1"));

    const form = screen.getByRole("form", { name: "Générer un rapport" });
    expect(within(form).getByRole("combobox", { name: "Type" })).toHaveValue("gouvernorat_summary");
    fireEvent.click(within(form).getByRole("button", { name: "Générer" }));
    expect(within(form).getByText("Indiquez un titre.")).toBeInTheDocument();
    fireEvent.change(within(form).getByRole("textbox", { name: "Titre" }), { target: { value: "Sfax septembre" } });
    fireEvent.click(within(form).getByRole("radio", { name: "Excel (XLSX)" }));
    fireEvent.click(within(form).getByRole("button", { name: "Générer" }));
    await waitFor(() =>
      expect(api.createLibraryReport).toHaveBeenCalledWith({
        kind: "gouvernorat_summary",
        title: "Sfax septembre",
        period_from: "2026-09-01",
        period_to: "2026-09-30",
        gouvernorats: [61],
        filters: {},
        format: "xlsx",
        lang: "fr",
      }),
    );
    await waitFor(() => expect(screen.queryByRole("form", { name: "Générer un rapport" })).not.toBeInTheDocument());
  });

  it("maps API errors (report not ready)", async () => {
    const api = fakeApi({
      libraryReports: vi.fn(() => Promise.resolve({ items: [makeLibraryReport()], next_cursor: null })),
      libraryReportLink: vi.fn(() => Promise.reject(new ApiError(409, "report_not_ready"))),
    });
    renderApp(<ReportsLibraryPage />, { api, lang: "fr", path: "/reports-library" });
    fireEvent.click(await screen.findByRole("button", { name: /Synthèse septembre/ }));
    expect(await screen.findByText("Le rapport n’est pas encore prêt.")).toBeInTheDocument();
  });

  it("creates a weekly schedule", async () => {
    const { api } = renderApp(<ReportSchedulesPage />, { auth: fakeAuth(NATIONAL_MANAGER), lang: "fr", path: "/reports-library/schedules" });
    expect(await screen.findByText("Chaque Lundi à 07:00")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Nouvelle planification" }));
    const form = screen.getByRole("form", { name: "Nouvelle planification" });
    fireEvent.change(within(form).getByRole("textbox", { name: "Titre" }), { target: { value: "Point du lundi" } });
    fireEvent.change(within(form).getByLabelText("Identifiant d’agent (UUID)"), { target: { value: "not-an-id" } });
    fireEvent.click(within(form).getByRole("button", { name: "Ajouter" }));
    expect(within(form).getByText("Identifiant invalide.")).toBeInTheDocument();
    fireEvent.click(within(form).getByRole("button", { name: "Enregistrer" }));
    await waitFor(() =>
      expect(api.createSchedule).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Point du lundi",
          kind: "period_summary",
          cron: { frequency: "weekly", time: "07:00", weekday: 1 },
          recipients: [NATIONAL_MANAGER.sub],
          enabled: true,
        }),
      ),
    );
  });
});

describe("National memory", () => {
  it("renders Markdown safely, side by side, and runs the review workflow", async () => {
    const { api, container } = renderApp(at("/memory/:id", <MemoryEntryPage />), {
      auth: fakeAuth(EDITOR),
      lang: "fr",
      path: "/memory/mem-1",
    });
    expect(await screen.findByRole("heading", { level: 1, name: "Feux de forêt du Kef 2026" })).toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Résumé" });
    expect(within(summary).getByText("événement").tagName).toBe("STRONG");
    expect(within(summary).getByText("الحدث").closest("[lang]")).toHaveAttribute("dir", "rtl");
    expect(container.querySelector("script")).toBeNull();
    expect(within(summary).getByText("<script>alert(1)</script>")).toBeInTheDocument();
    expect(summary.querySelector("a")).toBeNull();
    expect(summary).toHaveTextContent("[lien](javascript:alert(1))");

    fireEvent.click(screen.getByRole("button", { name: "Soumettre à relecture" }));
    await waitFor(() => expect(api.transitionMemoryEntry).toHaveBeenCalledWith("mem-1", { to: "in_review", note: null, version: 3 }));
  });

  it("asks for a note before requesting changes, and edits with the version", async () => {
    const api = fakeApi({
      memoryEntry: vi.fn(() => Promise.resolve(makeMemoryEntry({ status: "in_review", can_review: true, can_edit: false }))),
    });
    renderApp(at("/memory/:id", <MemoryEntryPage />), { api, auth: fakeAuth(NATIONAL_MANAGER), lang: "fr", path: "/memory/mem-1" });
    fireEvent.click(await screen.findByRole("button", { name: "Demander des modifications" }));
    fireEvent.click(screen.getByRole("button", { name: "Demander des modifications" }));
    expect(screen.getByText("Indiquez un motif (3 caractères au moins).")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Modifications demandées" }), { target: { value: "Ajouter les chiffres" } });
    fireEvent.click(screen.getByRole("button", { name: "Demander des modifications" }));
    await waitFor(() =>
      expect(api.transitionMemoryEntry).toHaveBeenCalledWith("mem-1", { to: "draft", note: "Ajouter les chiffres", version: 3 }),
    );
    expect(screen.queryByRole("button", { name: "Modifier" })).not.toBeInTheDocument();
  });

  it("saves edits with the version and reports a conflict", async () => {
    const api = fakeApi({ updateMemoryEntry: vi.fn(() => Promise.reject(new ApiError(409, "version_conflict"))) });
    renderApp(at("/memory/:id", <MemoryEntryPage />), { api, auth: fakeAuth(EDITOR), lang: "fr", path: "/memory/mem-1" });
    fireEvent.click(await screen.findByRole("button", { name: "Modifier" }));
    const editor = screen.getByRole("form", { name: "Éditeur de la fiche" });
    const lessons = within(editor).getByRole("group", { name: "Leçons apprises" });
    fireEvent.change(within(lessons).getByRole("textbox", { name: "Français" }), { target: { value: "## Leçon\n\nPré-positionner" } });
    fireEvent.click(within(lessons).getByRole("button", { name: "Aperçu" }));
    expect(within(lessons).getByRole("heading", { name: "Leçon" })).toBeInTheDocument();
    fireEvent.click(within(editor).getByRole("button", { name: "Enregistrer" }));
    await waitFor(() =>
      expect(api.updateMemoryEntry).toHaveBeenCalledWith(
        "mem-1",
        expect.objectContaining({ version: 3, lessons: { ar: "", fr: "## Leçon\n\nPré-positionner" } }),
      ),
    );
    expect(await screen.findByText(/Quelqu’un a enregistré cette fiche entre-temps/)).toBeInTheDocument();
  });

  it("compares two versions line by line", async () => {
    const entry = (fr: string) => ({ ...makeMemoryEntry(), lessons: { ar: "", fr } });
    const api = fakeApi({
      memoryVersions: vi.fn(() =>
        Promise.resolve([
          { version: 2, status: "draft" as const, created_at: "2026-08-11T10:00:00Z", created_by: null, change: "edited" as const, note: null },
          { version: 3, status: "draft" as const, created_at: "2026-08-12T10:00:00Z", created_by: { id: "x", name: "Amel" }, change: "edited" as const, note: null },
        ]),
      ),
      memoryVersion: vi.fn((_id: string, v: number) =>
        Promise.resolve({
          version: v,
          status: "draft" as const,
          created_at: "2026-08-12T10:00:00Z",
          created_by: null,
          change: "edited" as const,
          note: null,
          entry: entry(v === 2 ? "ligne A\nligne B" : "ligne A\nligne C"),
        }),
      ),
    });
    renderApp(at("/memory/:id", <MemoryEntryPage />), { api, auth: fakeAuth(EDITOR), lang: "fr", path: "/memory/mem-1" });
    const diff = await screen.findByLabelText("Différences : Leçons apprises (fr)");
    expect(within(diff).getByText("ligne B").closest(".diff__line")).toHaveClass("diff__line--del");
    expect(within(diff).getByText("ligne C").closest(".diff__line")).toHaveClass("diff__line--add");
    expect(screen.queryByLabelText("Différences : Résumé (fr)")).not.toBeInTheDocument();
  });

  it("starts a draft from an incident page", async () => {
    const api = fakeApi({ incident: vi.fn(() => Promise.resolve(makeIncidentDetail())) });
    renderApp(at("/incidents/:id", <IncidentDetailPage />), {
      api,
      auth: fakeAuth({ ...OPERATOR_CLAIMS, realm_access: { roles: ["field_commander"] } }),
      lang: "fr",
      path: "/incidents/inc-1",
    });
    fireEvent.click(await screen.findByRole("button", { name: "Démarrer une fiche de mémoire" }));
    await waitFor(() => expect(api.memoryFromIncident).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/memory/mem-new"));
  });

  it("does not offer it to an operator", async () => {
    const api = fakeApi({ incident: vi.fn(() => Promise.resolve(makeIncidentDetail())) });
    renderApp(at("/incidents/:id", <IncidentDetailPage />), { api, lang: "fr", path: "/incidents/inc-1" });
    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Démarrer une fiche de mémoire" })).not.toBeInTheDocument();
  });
});

describe("Events library", () => {
  it("searches with facets, highlights only with <mark>, and uses the calendar", async () => {
    const { api } = renderApp(at("/library", <EventsLibraryPage />), { auth: fakeAuth(EDITOR), lang: "fr", path: "/library?q=feux" });
    const hit = await screen.findByRole("link", { name: "Feux de forêt du Kef 2026" });
    expect(hit).toHaveAttribute("href", "/library/items/memory/mem-1");
    const mark = screen.getByText("feux", { selector: "mark" });
    expect(mark.parentElement).toHaveTextContent("Les feux <b> du Kef");
    expect(screen.getByText(/recherche de secours/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: /Signalement \(4\)/ }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("kinds=report"));
    await waitFor(() => expect(api.librarySearch).toHaveBeenLastCalledWith(expect.objectContaining({ q: "feux", kinds: ["report"] }), expect.anything()));

    fireEvent.click(screen.getByRole("button", { name: "Calendrier" }));
    expect(await screen.findByRole("table", { name: /Éléments par jour/ })).toBeInTheDocument();
  });

  it("shows an item with its linked media", async () => {
    renderApp(at("/library/items/:kind/:id", <LibraryItemPage />), { auth: fakeAuth(EDITOR), lang: "fr", path: "/library/items/transcript/tr-1" });
    expect(await screen.findByRole("heading", { level: 1, name: "Appel 198" })).toBeInTheDocument();
    expect(screen.getByText("Bonjour, il y a un feu près de la route.")).toBeInTheDocument();
    expect(screen.getByLabelText(/Audio/)).toHaveAttribute("src", "https://s3.example/m-9?sig=x");
  });
});

describe("Rewards", () => {
  it("shows the read-only settings, no cash prize, and lets the central committee edit rules", async () => {
    const { api } = renderApp(<RewardRulesPage />, { auth: fakeAuth(CENTRAL), lang: "fr", path: "/rewards" });
    expect(await screen.findByText("200 points")).toBeInTheDocument();
    expect(screen.getByText(/Aucune récompense en argent/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("appeler le 198");
    expect(screen.queryByText(/prix|prize/i, { selector: "input, label" })).not.toBeInTheDocument();
    const value = await screen.findByRole("spinbutton", { name: "Valeur : Catégorie exacte" });
    fireEvent.change(value, { target: { value: "2" } });
    fireEvent.click(within(value.closest("tr") as HTMLElement).getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(api.updateRewardRule).toHaveBeenCalledWith("rule-2", { multiplier: 2 }));
  });

  it("shows rules read-only to an operations manager", async () => {
    renderApp(<RewardRulesPage />, { auth: fakeAuth(NATIONAL_MANAGER), lang: "fr", path: "/rewards" });
    expect(await screen.findByText("×1,5")).toBeInTheDocument();
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
  });

  it("confirms a pending badge and requires a reason to reject", async () => {
    const api = fakeApi({ badgeAwards: vi.fn(() => Promise.resolve({ items: [makeBadge()], next_cursor: null })) });
    renderApp(<RewardConfirmationsPage />, { api, auth: fakeAuth(NATIONAL_MANAGER), lang: "fr", path: "/rewards/confirmations" });
    const row = (await screen.findByRole("rowheader", { name: "Faucon-482" })).closest("tr") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Refuser" }));
    fireEvent.click(within(row).getByRole("button", { name: "Refuser" }));
    expect(api.decideBadge).not.toHaveBeenCalled();
    fireEvent.click(within(row).getByRole("button", { name: "Annuler" }));
    fireEvent.click(within(row).getByRole("button", { name: "Confirmer" }));
    await waitFor(() => expect(api.decideBadge).toHaveBeenCalledWith("b-1", "confirm", undefined));
  });

  it("decides nominations (approval comment optional) and reports the same-reviewer refusal", async () => {
    const api = fakeApi({
      nominations: vi.fn(() => Promise.resolve({ items: [makeNomination()], next_cursor: null })),
      decideNomination: vi.fn(() => Promise.reject(new ApiError(409, "same_reviewer"))),
    });
    renderApp(<RewardNominationsPage />, { api, auth: fakeAuth(NATIONAL_MANAGER), lang: "fr", path: "/rewards/nominations" });
    const card = await screen.findByRole("article", { name: "Citoyen vigilant · 2026" });
    fireEvent.click(within(card).getByRole("button", { name: "Approuver" }));
    fireEvent.click(within(card).getByRole("button", { name: "Approuver" }));
    await waitFor(() => expect(api.decideNomination).toHaveBeenCalledWith("n-1", "approve", ""));
    expect(await within(card).findByText("La personne qui propose ne peut pas décider de sa propre nomination.")).toBeInTheDocument();
  });

  it("opens a certificate PDF through its pre-signed link", async () => {
    const { api } = renderApp(<RewardCertificatesPage />, { auth: fakeAuth(NATIONAL_MANAGER), lang: "fr", path: "/rewards/certificates" });
    fireEvent.click(await screen.findByRole("button", { name: "Obtenir le PDF — RW-2026-0001" }));
    await waitFor(() => expect(api.rewardCertificatePdf).toHaveBeenCalledWith("rc-1"));
    expect(await screen.findByRole("link", { name: "Ouvrir le PDF" })).toHaveAttribute("href", "https://s3.example/rc-1.pdf?sig=x");
  });
});

describe("navigation", () => {
  function nav(claims: Record<string, unknown>) {
    localStorage.setItem("ehimaya.menu", JSON.stringify({ shape: "flat", position: "top" }));
    renderApp(
      <Routes>
        <Route element={<Layout />}>
          <Route path="*" element={null} />
        </Route>
      </Routes>,
      { auth: fakeAuth(claims), lang: "fr", path: "/x" },
    );
    return screen.findByRole("navigation", { name: "Navigation principale" });
  }

  it("shows the phase 8 areas by role", async () => {
    const operator = await nav(OPERATOR_CLAIMS);
    for (const name of ["Analyses", "Rapports", "Mémoire nationale", "Médiathèque des événements", "Récompenses"])
      expect(within(operator).getByRole("link", { name })).toBeInTheDocument();
  });

  it("gives content editors the memory and library only", async () => {
    const editor = await nav(EDITOR);
    expect(within(editor).getByRole("link", { name: "Mémoire nationale" })).toBeInTheDocument();
    expect(within(editor).queryByRole("link", { name: "Analyses" })).not.toBeInTheDocument();
    expect(within(editor).queryByRole("link", { name: "Récompenses" })).not.toBeInTheDocument();
  });
});
