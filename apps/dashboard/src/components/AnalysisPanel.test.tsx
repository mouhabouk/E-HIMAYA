import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { makeAnalysis, makeDetail } from "../test/fixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { AnalysisPanel } from "./AnalysisPanel";
import { GroupingSection } from "./GroupingSection";

describe("AnalysisPanel", () => {
  it("explains the priority components, with 'no data yet' and the lives source", () => {
    renderApp(<AnalysisPanel report={makeDetail({ analysis: makeAnalysis() })} />, { lang: "fr" });

    expect(screen.getByRole("note")).toHaveTextContent("la décision appartient toujours à l’opérateur");
    const table = screen.getByRole("table", { name: "Composantes du score de priorité" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(7);

    const lives = within(table).getByRole("rowheader", { name: /Vies en danger/ }).closest("tr") as HTMLElement;
    expect(lives).toHaveTextContent("source : modèle de langue");
    expect(lives).toHaveTextContent("100 %");
    expect(lives).toHaveTextContent("27,8");

    const weather = within(table).getByRole("rowheader", { name: /Météo/ }).closest("tr") as HTMLElement;
    expect(weather).toHaveTextContent("Pas encore de données");
    expect(within(table).getAllByText("Pas encore de données")).toHaveLength(2);
    // The badge shows the band with the score.
    expect(screen.getByTitle("Priorité 79 (haute)")).toBeInTheDocument();
  });

  it("shows signed credibility points, the extraction, transcripts and the discreet footer", () => {
    const report = makeDetail({ category: "flood", analysis: makeAnalysis() });
    renderApp(<AnalysisPanel report={report} />, { lang: "fr" });

    const cred = screen.getByRole("table", { name: "Composantes de la crédibilité, en points" });
    expect(within(cred).getByRole("rowheader", { name: "Signalant inscrit" }).closest("tr")).toHaveTextContent("+15");
    expect(screen.getByText("80 sur 100")).toBeInTheDocument();

    // Suggested "fire" differs from the reported "flood": highlighted.
    expect(screen.getByText("Diffère de la catégorie déclarée")).toBeInTheDocument();
    expect(screen.getByText("Incendie")).toBeInTheDocument();
    expect(screen.getByText("gas")).toBeInTheDocument();
    expect(screen.getByText("حريق في عمارة مع أشخاص عالقين")).toHaveAttribute("lang", "ar");

    expect(screen.getByText("Il y a le feu au deuxième étage")).toBeInTheDocument();
    expect(screen.getByText("هناك حريق في الطابق الثاني")).toBeInTheDocument();
    expect(screen.getByText(/Langue\s*: français/)).toBeInTheDocument();
    expect(screen.getByText("qwen3:8b")).toBeInTheDocument();
    expect(screen.getByText("Extraction: terminé")).toBeInTheDocument();
  });

  it("does not highlight a suggested category equal to the reported one, and shows transcript errors translated", () => {
    const analysis = makeAnalysis({
      transcripts: [
        {
          media_id: "m",
          kind: "video",
          text: null,
          language: null,
          language_probability: null,
          duration_s: null,
          translation_ar: null,
          error: "media_undecodable",
          model: null,
        },
      ],
    });
    renderApp(<AnalysisPanel report={makeDetail({ category: "fire", analysis })} />, { lang: "fr" });
    expect(screen.queryByText("Diffère de la catégorie déclarée")).not.toBeInTheDocument();
    expect(screen.getByText("Transcription impossible : fichier illisible")).toBeInTheDocument();
  });

  it("before any analysis: shows the rule scores and the awaiting chip", () => {
    const report = makeDetail({ analysis: null, analysis_state: "pending", priority_score: 42, credibility_score: null });
    renderApp(<AnalysisPanel report={report} />, { lang: "fr" });
    expect(screen.getByText("En attente d'analyse")).toBeInTheDocument();
    expect(screen.getByText("Ce signalement n’a pas encore été analysé.")).toBeInTheDocument();
    expect(screen.getByTitle("Priorité 42 (moyenne)")).toBeInTheDocument();
  });

  it("renders in Arabic with the translated component labels", () => {
    renderApp(<AnalysisPanel report={makeDetail({ analysis: makeAnalysis() })} />, { lang: "ar" });
    expect(screen.getByRole("heading", { name: "التحليل الآلي" })).toBeInTheDocument();
    expect(screen.getAllByText("لا توجد بيانات بعد")).toHaveLength(2);
    expect(screen.getByText("المصدر: النموذج اللغوي")).toBeInTheDocument();
  });
});

const SUGGESTION = {
  kind: "report" as const,
  incident_id: null,
  report_id: "r-9",
  tracking_code: "EH-26-61-0000123",
  score: 0.82,
  distance_m: 150,
  minutes: 4,
  similarity: null,
  reasons: ["same_category", "within_radius", "within_window"],
  matching_reports: 1,
};

describe("GroupingSection", () => {
  it("shows the suggestion with its reasons and accepts it", async () => {
    const report = makeDetail({ id: "r1", has_suggestion: true, analysis: makeAnalysis({ suggestion: SUGGESTION }) });
    const api = fakeApi({
      linkIncident: vi.fn(() => Promise.resolve({ ...report, has_suggestion: false, incident_id: "i-9" })),
    });
    renderApp(<GroupingSection report={report} />, { api, lang: "fr" });

    // Write actions appear once the signed-in user (and role) is known.
    const accept = await screen.findByRole("button", { name: "Accepter" });
    expect(screen.getByText("EH-26-61-0000123")).toHaveAttribute("href", "/reports/r-9");
    expect(screen.getByText("Même catégorie")).toBeInTheDocument();
    expect(screen.getByText("Dans le rayon")).toBeInTheDocument();
    expect(screen.getByText("82 %")).toBeInTheDocument();
    expect(screen.getByText(/150/)).toBeInTheDocument();

    fireEvent.click(accept);
    await waitFor(() => expect(api.linkIncident).toHaveBeenCalledWith("r1", { action: "accept_suggestion" }));
    expect(await screen.findByText("Mise à jour effectuée.")).toBeInTheDocument();
  });

  it("dismisses a suggestion and shows a translated 409", async () => {
    const report = makeDetail({ id: "r1", has_suggestion: true, analysis: makeAnalysis({ suggestion: SUGGESTION }) });
    const api = fakeApi({ dismissSuggestion: vi.fn(() => Promise.reject(new ApiError(409, "suggestion_outdated"))) });
    renderApp(<GroupingSection report={report} />, { api, lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Ignorer la suggestion" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("La suggestion n’est plus valable");
    expect(api.dismissSuggestion).toHaveBeenCalledWith("r1");
  });

  it("links to the incident and removes the report from it", async () => {
    const report = makeDetail({ id: "r1", incident_id: "i-1" });
    const api = fakeApi({ detachIncident: vi.fn(() => Promise.resolve({ ...report, incident_id: null })) });
    renderApp(<GroupingSection report={report} />, { api, lang: "fr" });
    const remove = await screen.findByRole("button", { name: "Retirer de l’incident" });
    expect(screen.getByRole("link", { name: "Ouvrir l’incident" })).toHaveAttribute("href", "/incidents/i-1");
    expect(screen.queryByRole("button", { name: "Nouvel incident" })).not.toBeInTheDocument();
    fireEvent.click(remove);
    await waitFor(() => expect(api.detachIncident).toHaveBeenCalledWith("r1"));
  });

  it("offers a new incident otherwise", async () => {
    const report = makeDetail({ id: "r1" });
    const api = fakeApi({ linkIncident: vi.fn(() => Promise.resolve({ ...report, incident_id: "i-new" })) });
    renderApp(<GroupingSection report={report} />, { api, lang: "fr" });
    fireEvent.click(await screen.findByRole("button", { name: "Nouvel incident" }));
    await waitFor(() => expect(api.linkIncident).toHaveBeenCalledWith("r1", { action: "new" }));
  });

  it("hides write actions from read-only roles", async () => {
    const report = makeDetail({ id: "r1", has_suggestion: true, analysis: makeAnalysis({ suggestion: SUGGESTION }) });
    const auth = fakeAuth({ ...OPERATOR_CLAIMS, realm_access: { roles: ["central_committee"] }, scope_level: "national" });
    renderApp(<GroupingSection report={report} />, { auth, lang: "fr" });
    expect(await screen.findByText("Votre rôle permet uniquement de consulter le regroupement.")).toBeInTheDocument();
    expect(screen.getByText("Même catégorie")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText("Votre rôle permet uniquement de consulter le regroupement.")).toBeInTheDocument();
  });
});
