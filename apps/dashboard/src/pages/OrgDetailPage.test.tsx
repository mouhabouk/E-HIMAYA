import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { makeOrgDetail, makeReport } from "../test/fixtures";
import { AUDITOR_CLAIMS, fakeApi, fakeAuth, renderApp } from "../test/render";
import { OrgDetailPage } from "./OrgDetailPage";

vi.mock("../components/LazyMap", () => ({ LazyMapView: () => <div data-testid="map" /> }));

const route = "/orgs/:id";
const auditor = () => fakeAuth(AUDITOR_CLAIMS);

function section(name: string | RegExp): HTMLElement {
  return screen.getByRole("region", { name });
}

function currentVersion() {
  const v = makeOrgDetail().documents[0]?.current_version;
  if (!v) throw new Error("fixture without a current version");
  return v;
}

describe("OrgDetailPage", () => {
  it("shows the card, contacts, classification with the provisional note and the completeness checklist", async () => {
    const api = fakeApi({ org: vi.fn(() => Promise.resolve(makeOrgDetail())) });
    renderApp(<OrgDetailPage />, { api, path: "/orgs/o-1", route, lang: "fr" });

    expect(await screen.findByRole("heading", { name: "Société Chimique du Sud", level: 1 })).toBeInTheDocument();
    const card = section("Fiche de l’établissement");
    expect(within(card).getByText("1234567A")).toBeInTheDocument();
    expect(within(card).getByText(/Matricule fiscal/)).toBeInTheDocument();
    expect(within(card).getByText("Fabrication de peintures")).toBeInTheDocument();

    const contacts = section("Contacts");
    expect(within(contacts).getByRole("link", { name: "+21698000000" })).toHaveAttribute("href", "tel:+21698000000");
    expect(within(contacts).getByRole("link", { name: "contact@example.tn" })).toHaveAttribute("href", "mailto:contact@example.tn");

    const cls = section("Classement");
    expect(within(cls).getByText("Établissement industriel")).toBeInTheDocument();
    expect(within(cls).getByRole("note")).toHaveTextContent("Seuils de classement provisoires");
    expect(within(cls).getByText("Dossier incomplet")).toBeInTheDocument();
    const checklist = within(cls).getByRole("list", { name: "Éléments exigés" });
    expect(within(checklist).getAllByRole("listitem")).toHaveLength(6);
    expect(within(checklist).getByText(/Plan de sécurité/).closest("li")).toHaveClass("checklist__missing");
    expect(within(checklist).getByText(/Dossier de sécurité/).closest("li")).toHaveClass("checklist__ok");
  });

  it("shows alerts, the team with training badges, hazmat (UN, class, quantity, SDS), equipment and the map", async () => {
    const api = fakeApi({ org: vi.fn(() => Promise.resolve(makeOrgDetail())) });
    renderApp(<OrgDetailPage />, { api, path: "/orgs/o-1", route, lang: "fr" });
    await screen.findByRole("heading", { level: 1 });

    const alerts = section(/Alertes/);
    expect(within(alerts).getByText("Formation expirée")).toBeInTheDocument();
    // The alert names its subject (team member, equipment).
    expect(within(alerts).getByText(/Karim Ayadi/)).toBeInTheDocument();
    expect(within(alerts).getByText(/Extincteur/)).toBeInTheDocument();

    const team = section(/Équipe de sécurité/);
    const karim = within(team).getByRole("rowheader", { name: "Karim Ayadi" }).closest("tr") as HTMLElement;
    expect(within(karim).getByText("Formation expirée")).toHaveClass("tag--level-bad");
    expect(within(team).getByText("Représentant")).toBeInTheDocument();

    const hazmat = section(/Matières dangereuses/);
    expect(hazmat).toHaveClass("hazard");
    const acetone = within(hazmat).getByRole("rowheader", { name: "Acétone" }).closest("tr") as HTMLElement;
    expect(within(acetone).getByText("UN 1090")).toBeInTheDocument();
    expect(within(acetone).getByText("2,5 t")).toBeInTheDocument();
    expect(within(acetone).getByRole("button", { name: /Obtenir le lien — Fiche de données de sécurité — Acétone/ })).toBeInTheDocument();
    const chlore = within(hazmat).getByRole("rowheader", { name: "Chlore" }).closest("tr") as HTMLElement;
    expect(within(chlore).getByText("absente")).toBeInTheDocument();

    const equipment = section(/Équipements de sécurité/);
    expect(within(equipment).getByText("Maintenance en retard")).toHaveClass("tag--level-bad");

    const map = section("Localisation et repères");
    expect(within(map).getByTestId("map")).toBeInTheDocument();
    expect(within(map).getByRole("list", { name: "Légende" })).toHaveTextContent("Établissement avec matières dangereuses");
    expect(within(map).getByText(/Parking nord/)).toBeInTheDocument();
    expect(within(map).getAllByText("Point d’eau")).toHaveLength(2); // legend + list of features
  });

  it("gets a pre-signed link on demand for documents and certificates, and shows the version history", async () => {
    const api = fakeApi({
      org: vi.fn(() => Promise.resolve(makeOrgDetail())),
      orgDocumentVersions: vi.fn(() =>
        Promise.resolve([
          { ...currentVersion(), version: 3 },
          { ...currentVersion(), version: 2, note: "Première révision" },
        ]),
      ),
    });
    renderApp(<OrgDetailPage />, { api, path: "/orgs/o-1", route, lang: "fr" });
    await screen.findByRole("heading", { level: 1 });

    const docs = section(/Documents/);
    expect(within(docs).getByText(/Version actuelle 3/)).toBeInTheDocument();
    expect(within(docs).getByText("c".repeat(64))).toBeInTheDocument();
    fireEvent.click(within(docs).getByRole("button", { name: "Obtenir le lien — Dossier de sécurité 2026" }));
    await waitFor(() => expect(api.orgDocumentDownload).toHaveBeenCalledWith("o-1", "d-1", 3));
    expect(await within(docs).findByRole("link", { name: /Ouvrir le fichier — Dossier de sécurité 2026/ })).toHaveAttribute(
      "href",
      "https://s3.example/doc?sig=x",
    );

    // History is loaded only when opened.
    expect(api.orgDocumentVersions).not.toHaveBeenCalled();
    const summary = within(docs).getByText("Historique des versions (3)");
    const details = summary.closest("details") as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(await within(docs).findByText("Première révision")).toBeInTheDocument();
    expect(api.orgDocumentVersions).toHaveBeenCalledWith("o-1", "d-1", expect.anything());

    const certs = section(/Certificats de sécurité/);
    expect(within(certs).getByText("EHC-26-61-000123")).toBeInTheDocument();
    expect(within(certs).getByText("Soumis")).toBeInTheDocument();
    expect(within(certs).getByText("e".repeat(64))).toBeInTheDocument();
    fireEvent.click(within(certs).getByRole("button", { name: /Obtenir le lien — PDF EHC-26-61-000123/ }));
    await waitFor(() => expect(api.certificatePdf).toHaveBeenCalledWith("o-1", "c-1"));
  });

  it("lists members and the institution's reports linking to the report detail", async () => {
    const api = fakeApi({
      org: vi.fn(() => Promise.resolve(makeOrgDetail())),
      orgReports: vi.fn(() => Promise.resolve({ items: [makeReport({ id: "r-7", tracking_code: "EH-26-61-0000007" })], next_cursor: null })),
    });
    renderApp(<OrgDetailPage />, { api, path: "/orgs/o-1", route, lang: "fr" });
    await screen.findByRole("heading", { level: 1 });
    expect(within(section(/Membres/)).getByText("Administrateur")).toBeInTheDocument();
    const reports = section("Signalements de l’établissement");
    expect(await within(reports).findByRole("link", { name: "EH-26-61-0000007" })).toHaveAttribute("href", "/reports/r-7");
    expect(api.orgReports).toHaveBeenCalledWith("o-1", expect.objectContaining({ cursor: null }));
  });

  it("is read-only for an operator: no review actions", async () => {
    const api = fakeApi({ org: vi.fn(() => Promise.resolve(makeOrgDetail())) });
    renderApp(<OrgDetailPage />, { api, path: "/orgs/o-1", route, lang: "fr" });
    const review = await screen.findByRole("region", { name: "Validation de l’enregistrement" });
    expect(within(review).getByText(/réservée aux auditeurs/)).toBeInTheDocument();
    expect(within(review).queryByRole("button")).not.toBeInTheDocument();
  });

  it("lets an auditor approve a pending registration after confirmation", async () => {
    const api = fakeApi({
      org: vi.fn(() => Promise.resolve(makeOrgDetail())),
      reviewOrg: vi.fn(() => Promise.resolve(makeOrgDetail({ status: "active" }))),
    });
    renderApp(<OrgDetailPage />, { api, auth: auditor(), path: "/orgs/o-1", route, lang: "fr" });
    const review = await screen.findByRole("region", { name: "Validation de l’enregistrement" });
    // Only the decisions allowed from pending_review.
    expect(await within(review).findByRole("button", { name: "Approuver" })).toBeInTheDocument();
    expect(within(review).getByRole("button", { name: "Rejeter" })).toBeInTheDocument();
    expect(within(review).queryByRole("button", { name: "Suspendre" })).not.toBeInTheDocument();

    fireEvent.click(within(review).getByRole("button", { name: "Approuver" }));
    expect(within(review).getByRole("alert")).toHaveTextContent("Confirmez-vous l’approbation");
    expect(api.reviewOrg).not.toHaveBeenCalled();
    fireEvent.click(within(review).getByRole("button", { name: "Confirmer la décision" }));
    await waitFor(() => expect(api.reviewOrg).toHaveBeenCalledWith("o-1", { decision: "approve", reason: "" }));
    expect(await screen.findByText("Décision enregistrée.")).toBeInTheDocument();
    // The answer replaces the detail: an active institution can now only be suspended.
    expect(await within(review).findByRole("button", { name: "Suspendre" })).toBeInTheDocument();
    expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
  });

  it("shows the kind's fields with who sees them, the readiness, and lets the auditor set the kind on approval (P2a)", async () => {
    const api = fakeApi({
      org: vi.fn(() =>
        Promise.resolve(makeOrgDetail({ kind: "other", kind_review: true, readiness: 67, kind_fields: {} })),
      ),
      reviewOrg: vi.fn(() => Promise.resolve(makeOrgDetail({ status: "active", kind: "health" }))),
    });
    renderApp(<OrgDetailPage />, { api, auth: auditor(), path: "/orgs/o-1", route, lang: "fr" });
    expect(await screen.findByText("Type à revoir")).toBeInTheDocument();
    expect(screen.getByText("Préparation 67%")).toBeInTheDocument();
    const review = screen.getByRole("region", { name: "Validation de l’enregistrement" });
    fireEvent.click(await within(review).findByRole("button", { name: "Approuver" }));
    fireEvent.change(within(review).getByLabelText("Type à l'approbation"), { target: { value: "health" } });
    fireEvent.click(within(review).getByRole("button", { name: "Confirmer la décision" }));
    await waitFor(() =>
      expect(api.reviewOrg).toHaveBeenCalledWith("o-1", { decision: "approve", reason: "", kind: "health" }),
    );
  });

  it("lists the answers to the kind's fields with a visibility badge", async () => {
    const api = fakeApi({
      org: vi.fn(() =>
        Promise.resolve(makeOrgDetail({ kind: "health", kind_fields: { beds: 120, generator: true, reception_phone: "+21671000111" } })),
      ),
    });
    renderApp(<OrgDetailPage />, { api, auth: auditor(), path: "/orgs/o-1", route, lang: "fr" });
    const kind = await screen.findByRole("region", { name: /Propre au type/ });
    expect(within(kind).getByText("Lits")).toBeInTheDocument();
    expect(within(kind).getByText("120")).toBeInTheDocument();
    expect(within(kind).getByText("Oui")).toBeInTheDocument();
    expect(within(kind).getByText("Public")).toBeInTheDocument();
    expect(within(kind).getAllByText("Établissement et Office")).toHaveLength(2);
  });

  it("requires a reason to reject, then sends it", async () => {
    const api = fakeApi({
      org: vi.fn(() => Promise.resolve(makeOrgDetail())),
      reviewOrg: vi.fn(() => Promise.resolve(makeOrgDetail({ status: "rejected", review: { reason: "Identifiant invalide", at: "2026-10-19T10:00:00Z" } }))),
    });
    renderApp(<OrgDetailPage />, { api, auth: auditor(), path: "/orgs/o-1", route, lang: "fr" });
    const review = await screen.findByRole("region", { name: "Validation de l’enregistrement" });
    fireEvent.click(await within(review).findByRole("button", { name: "Rejeter" }));
    fireEvent.click(within(review).getByRole("button", { name: "Confirmer la décision" }));
    expect(within(review).getByText("Le motif est obligatoire pour cette décision.")).toBeInTheDocument();
    expect(within(review).getByLabelText("Motif")).toHaveAttribute("aria-invalid", "true");
    expect(api.reviewOrg).not.toHaveBeenCalled();

    fireEvent.change(within(review).getByLabelText("Motif"), { target: { value: "Identifiant invalide" } });
    fireEvent.click(within(review).getByRole("button", { name: "Confirmer la décision" }));
    await waitFor(() =>
      expect(api.reviewOrg).toHaveBeenCalledWith("o-1", { decision: "reject", reason: "Identifiant invalide" }),
    );
    // A rejected institution shows the reason and offers no decision.
    expect(await within(review).findByText("Identifiant invalide")).toBeInTheDocument();
    expect(within(review).getByText("Aucune décision possible dans cet état.")).toBeInTheDocument();
  });

  it("offers reinstate for a suspended institution and translates a 409 invalid_transition", async () => {
    const api = fakeApi({
      org: vi.fn(() => Promise.resolve(makeOrgDetail({ status: "suspended", review: { reason: "Audit", at: null } }))),
      reviewOrg: vi.fn(() => Promise.reject(new ApiError(409, "invalid_transition"))),
    });
    renderApp(<OrgDetailPage />, { api, auth: auditor(), path: "/orgs/o-1", route, lang: "fr" });
    const review = await screen.findByRole("region", { name: "Validation de l’enregistrement" });
    fireEvent.click(await within(review).findByRole("button", { name: "Réactiver" }));
    fireEvent.click(within(review).getByRole("button", { name: "Confirmer la décision" }));
    expect(await screen.findByText(/Le statut de l’établissement a changé entre-temps/)).toBeInTheDocument();
    expect(screen.queryByText("invalid_transition")).not.toBeInTheDocument();
    // The current state is reloaded (the detail is on screen).
    await waitFor(() => expect(vi.mocked(api.org).mock.calls.length).toBeGreaterThan(1));
  });

  it("shows a translated error for a missing institution", async () => {
    const api = fakeApi({ org: vi.fn(() => Promise.reject(new ApiError(404, "org_not_found"))) });
    renderApp(<OrgDetailPage />, { api, path: "/orgs/x", route, lang: "ar" });
    expect(await screen.findByRole("alert")).toHaveTextContent("المؤسسة غير موجودة");
  });
});
