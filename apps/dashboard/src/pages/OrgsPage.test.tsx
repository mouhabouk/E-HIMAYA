import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Gate } from "../App";
import { Layout } from "../components/Layout";
import { DEFAULT_ORG_FILTERS } from "../lib/orgs";
import { hasReadAccess } from "../lib/roles";
import { makeStaffOrg } from "../test/fixtures";
import { AUDITOR_CLAIMS, fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { OrgsPage } from "./OrgsPage";

const ORGS = [
  makeStaffOrg(),
  makeStaffOrg({
    id: "o-2",
    name: "Hôtel La Corniche",
    kind: "tourism",
    status: "pending_review",
    identifier_type: "rne",
    identifier: "7654321B",
    capacity: 900,
    classification: { family: "erp", category: 2 },
    hazmat_count: 0,
    alerts_count: 0,
    certificate_status: "none",
    certificate_valid_until: null,
  }),
];

function rowOf(name: string): HTMLElement {
  return screen.getByRole("link", { name: new RegExp(name) }).closest("tr") as HTMLElement;
}

describe("OrgsPage", () => {
  it("lists institutions with kind, status, capacity, classification, hazmat, alerts and certificate", async () => {
    const api = fakeApi({ orgs: vi.fn(() => Promise.resolve({ items: ORGS, next_cursor: null })) });
    renderApp(<OrgsPage />, { api, lang: "fr", path: "/orgs" });
    await screen.findByRole("table", { name: /Liste des établissements/ });

    const a = rowOf("Société Chimique du Sud");
    expect(within(a).getByRole("link")).toHaveAttribute("href", "/orgs/o-1");
    expect(within(a).getByText("1234567A")).toBeInTheDocument();
    expect(within(a).getByText("Industrielle")).toBeInTheDocument();
    expect(within(a).getByText("Active")).toBeInTheDocument();
    expect(within(a).getByText("420")).toBeInTheDocument();
    expect(within(a).getByText("Établissement industriel")).toBeInTheDocument();
    expect(within(a).getByText("Matières dangereuses : 2")).toBeInTheDocument();
    expect(within(a).getByText("Approuvé")).toBeInTheDocument();
    expect(within(a).getByText(/valable jusqu’au/)).toBeInTheDocument();
    expect(await within(a).findByText("Sfax")).toBeInTheDocument();

    const b = rowOf("Hôtel La Corniche");
    expect(within(b).getByText("En attente de validation")).toBeInTheDocument();
    expect(within(b).getByText("Établissement recevant du public · catégorie 2")).toBeInTheDocument();
    expect(within(b).getByText("Aucun", { selector: ".tag" })).toBeInTheDocument();
    expect(api.orgs).toHaveBeenCalledWith(DEFAULT_ORG_FILTERS, expect.objectContaining({ cursor: null }));
  });

  it("reads filters from the URL (KPI links) and sends them; changes update the query", async () => {
    const api = fakeApi();
    renderApp(<OrgsPage />, { api, lang: "fr", path: "/orgs?status=pending_review&has_hazmat=true" });
    expect(await screen.findByText("Aucun établissement ne correspond aux filtres.")).toBeInTheDocument();
    expect(api.orgs).toHaveBeenLastCalledWith(
      { ...DEFAULT_ORG_FILTERS, status: "pending_review", hasHazmat: true },
      expect.anything(),
    );
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "education" } });
    await waitFor(() =>
      expect(api.orgs).toHaveBeenLastCalledWith(expect.objectContaining({ kind: "education" }), expect.anything()),
    );
    fireEvent.change(screen.getByLabelText("Certificat de sécurité"), { target: { value: "expired" } });
    await waitFor(() =>
      expect(api.orgs).toHaveBeenLastCalledWith(expect.objectContaining({ certificate: "expired" }), expect.anything()),
    );
    fireEvent.change(screen.getByLabelText("Recherche"), { target: { value: "Corniche" } });
    await waitFor(() =>
      expect(api.orgs).toHaveBeenLastCalledWith(expect.objectContaining({ q: "Corniche" }), expect.anything()),
    );
    fireEvent.click(screen.getByRole("button", { name: "Réinitialiser" }));
    await waitFor(() => expect(api.orgs).toHaveBeenLastCalledWith(DEFAULT_ORG_FILTERS, expect.anything()));
  });

  it("offers the gouvernorat filter to national users only and never sends another scope", async () => {
    const api = fakeApi();
    const { unmount } = renderApp(<OrgsPage />, { api, lang: "fr", path: "/orgs?gouvernorat_code=11" });
    await screen.findByText("Aucun établissement ne correspond aux filtres.");
    expect(screen.queryByLabelText("Gouvernorat")).not.toBeInTheDocument();
    expect(api.orgs).toHaveBeenLastCalledWith(expect.objectContaining({ gouvernorat: null }), expect.anything());
    unmount();

    const national = fakeAuth({ ...OPERATOR_CLAIMS, realm_access: { roles: ["central_committee"] }, scope_level: "national" });
    const api2 = fakeApi();
    renderApp(<OrgsPage />, { api: api2, auth: national, lang: "fr", path: "/orgs?gouvernorat_code=11" });
    expect(await screen.findByLabelText("Gouvernorat")).toBeInTheDocument();
    expect(api2.orgs).toHaveBeenLastCalledWith(expect.objectContaining({ gouvernorat: 11 }), expect.anything());
  });

  it("lists the upcoming public events of institutions (P2b)", async () => {
    const api = fakeApi({
      orgs: vi.fn(() => Promise.resolve({ items: ORGS, next_cursor: null })),
      orgEvents: vi.fn(() =>
        Promise.resolve([
          {
            id: "a-7",
            kind: "event" as const,
            title: "Festival de la corniche",
            starts_on: "2026-11-02",
            ends_on: "2026-11-04",
            participants: 5000,
            notes: null,
            created_by: "Amel",
            created_at: "2026-10-20T10:00:00Z",
            org_id: "o-2",
            org_name: "Hôtel La Corniche",
            org_kind: "tourism" as const,
            gouvernorat_code: 61,
          },
        ]),
      ),
    });
    renderApp(<OrgsPage />, { api, auth: fakeAuth(OPERATOR_CLAIMS), lang: "fr", path: "/orgs" });
    const events = await screen.findByRole("region", { name: "Événements publics à venir" });
    expect(await within(events).findByText("Festival de la corniche")).toBeInTheDocument();
    expect(within(events).getByRole("link", { name: "Hôtel La Corniche" })).toHaveAttribute("href", "/orgs/o-2");
    expect(within(events).getByText(/Tourisme/)).toBeInTheDocument();
    expect(api.orgEvents).toHaveBeenCalledWith(10, expect.anything());
  });

  it("loads more with the cursor", async () => {
    const api = fakeApi({
      orgs: vi
        .fn()
        .mockResolvedValueOnce({ items: [ORGS[0]], next_cursor: "c2" })
        .mockResolvedValueOnce({ items: [ORGS[1]], next_cursor: null }),
    });
    renderApp(<OrgsPage />, { api, lang: "fr", path: "/orgs" });
    fireEvent.click(await screen.findByRole("button", { name: "Charger plus" }));
    expect(await screen.findByRole("link", { name: /Hôtel La Corniche/ })).toBeInTheDocument();
    expect(api.orgs).toHaveBeenLastCalledWith(expect.anything(), expect.objectContaining({ cursor: "c2" }));
  });

  it("renders in Arabic with an unambiguous title", async () => {
    const api = fakeApi({ orgs: vi.fn(() => Promise.resolve({ items: ORGS, next_cursor: null })) });
    renderApp(<OrgsPage />, { api, lang: "ar", path: "/orgs" });
    expect(await screen.findByRole("heading", { name: "المؤسسات" })).toBeInTheDocument();
    expect(screen.getAllByText("صناعية").length).toBeGreaterThan(0);
    expect(screen.getByText("بانتظار المراجعة", { selector: ".chip" })).toBeInTheDocument();
  });
});

describe("navigation and gates by role", () => {
  it("shows reports and institutions to an operator", async () => {
    renderApp(<Layout />, { lang: "fr" });
    const nav = await screen.findByRole("navigation", { name: "Navigation principale" });
    for (const name of ["Indicateurs", "Signalements", "Incidents", "Carte en direct", "Établissements", "Certificats à examiner"]) {
      expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
    }
  });

  it("shows only the institution screens to an institutions auditor", async () => {
    renderApp(<Layout />, { auth: fakeAuth(AUDITOR_CLAIMS), lang: "fr" });
    const nav = await screen.findByRole("navigation", { name: "Navigation principale" });
    expect(within(nav).getAllByRole("link").map((l) => l.textContent)).toEqual([
      "Établissements",
      "Certificats à examiner",
    ]);
    expect(screen.getByText("Auditeur des établissements")).toBeInTheDocument();
  });

  it("refuses report screens to an institutions auditor", async () => {
    renderApp(
      <Gate allow={hasReadAccess}>
        <p>reports</p>
      </Gate>,
      { auth: fakeAuth(AUDITOR_CLAIMS), lang: "fr" },
    );
    expect(await screen.findByRole("heading", { name: "Accès refusé" })).toBeInTheDocument();
    expect(screen.queryByText("reports")).not.toBeInTheDocument();
  });
});
