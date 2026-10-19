import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { validUntilBounds } from "../lib/orgs";
import { makeCertificate, makeQueueCertificate } from "../test/fixtures";
import { AUDITOR_CLAIMS, fakeApi, fakeAuth, renderApp } from "../test/render";
import { CertificatesPage } from "./CertificatesPage";

const QUEUE = [
  makeQueueCertificate(),
  makeQueueCertificate({
    id: "c-2",
    code: "EHC-26-11-000200",
    org_id: "o-2",
    org_name: "Hôtel La Corniche",
    gouvernorat_code: 11,
    submitted_at: "2026-10-05T08:00:00Z",
    completeness: { ok: false, missing: ["safety_plan", "evacuation_points"] },
  }),
];

function setup(overrides: Parameters<typeof fakeApi>[0] = {}, claims: Record<string, unknown> = AUDITOR_CLAIMS) {
  const api = fakeApi({ certificates: vi.fn(() => Promise.resolve({ items: QUEUE, next_cursor: null })), ...overrides });
  return renderApp(<CertificatesPage />, { api, auth: fakeAuth(claims), lang: "fr", path: "/orgs/certificates" });
}

async function item(code: string): Promise<HTMLElement> {
  return (await screen.findByText(code)).closest("li") as HTMLElement;
}

describe("CertificatesPage (review queue)", () => {
  it("lists submitted certificates oldest first with completeness, institution link and PDF link", async () => {
    const { api } = setup();
    const list = await screen.findByRole("list", { name: /Certificats en attente d’examen/ });
    const items = within(list).getAllByRole("listitem");
    expect(items.map((li) => within(li).getByText(/^EHC-/).textContent)).toEqual(["EHC-26-61-000123", "EHC-26-11-000200"]);
    expect(api.certificates).toHaveBeenCalledWith(expect.objectContaining({ status: "submitted", cursor: null }));

    const first = items[0] as HTMLElement;
    expect(within(first).getByText("Dossier complet")).toBeInTheDocument();
    expect(within(first).getByRole("link", { name: "Société Chimique du Sud" })).toHaveAttribute("href", "/orgs/o-1");
    const second = items[1] as HTMLElement;
    expect(within(second).getByText("Manquant : Plan de sécurité, Au moins un point d’évacuation et de rassemblement")).toBeInTheDocument();

    fireEvent.click(within(first).getByRole("button", { name: /Obtenir le lien — PDF EHC-26-61-000123/ }));
    await waitFor(() => expect(api.certificatePdf).toHaveBeenCalledWith("o-1", "c-1"));
    expect(await within(first).findByRole("link", { name: /Ouvrir le fichier/ })).toHaveAttribute(
      "href",
      "https://s3.example/cert.pdf?sig=x",
    );
  });

  it("approves with a validity date (default one year), after confirmation", async () => {
    const { api } = setup({ reviewCertificate: vi.fn(() => Promise.resolve(makeCertificate())) });
    const bounds = validUntilBounds();
    const li = await item("EHC-26-61-000123");
    fireEvent.click(within(li).getByRole("button", { name: "Approuver" }));
    const date = within(li).getByLabelText("Valable jusqu’au");
    expect(date).toHaveValue(bounds.default);
    expect(date).toHaveAttribute("min", bounds.min);
    expect(date).toHaveAttribute("max", bounds.max);

    // The form's own submit button (the first "Approuver" chooses the decision).
    fireEvent.submit(date.closest("form") as HTMLFormElement);
    expect(within(li).getByRole("alert")).toHaveTextContent("Confirmez-vous l’approbation du certificat EHC-26-61-000123");
    expect(api.reviewCertificate).not.toHaveBeenCalled();
    fireEvent.click(within(li).getByRole("button", { name: "Confirmer" }));
    await waitFor(() =>
      expect(api.reviewCertificate).toHaveBeenCalledWith("c-1", { decision: "approve", valid_until: bounds.default }),
    );
    expect(await screen.findByText("Certificat EHC-26-61-000123 approuvé.")).toBeInTheDocument();
    // It leaves the queue.
    expect(screen.queryByText("EHC-26-61-000123")).not.toBeInTheDocument();
  });

  it("refuses a validity date out of range before sending", async () => {
    const { api } = setup();
    const li = await item("EHC-26-61-000123");
    fireEvent.click(within(li).getByRole("button", { name: "Approuver" }));
    const date = within(li).getByLabelText("Valable jusqu’au");
    fireEvent.change(date, { target: { value: validUntilBounds().min.replace(/^\d{4}/, (y) => String(Number(y) - 1)) } });
    const form = date.closest("form") as HTMLFormElement;
    fireEvent.submit(form);
    expect(within(li).getByText("La date doit être comprise entre demain et dans cinq ans.")).toBeInTheDocument();
    expect(date).toHaveAttribute("aria-invalid", "true");
    fireEvent.change(date, { target: { value: "" } });
    fireEvent.submit(form);
    expect(within(li).getByText("Choisissez la date de fin de validité.")).toBeInTheDocument();
    expect(api.reviewCertificate).not.toHaveBeenCalled();
  });

  it("requires a reason to reject, then rejects after confirmation", async () => {
    const { api } = setup({ reviewCertificate: vi.fn(() => Promise.resolve(makeCertificate())) });
    const li = await item("EHC-26-11-000200");
    fireEvent.click(within(li).getByRole("button", { name: "Rejeter" }));
    const form = within(li).getByLabelText("Motif du rejet").closest("form") as HTMLFormElement;
    fireEvent.submit(form);
    expect(within(li).getByText("Le motif du rejet est obligatoire.")).toBeInTheDocument();
    fireEvent.change(within(li).getByLabelText("Motif du rejet"), { target: { value: "Plan manquant" } });
    fireEvent.submit(form);
    expect(within(li).getByRole("alert")).toHaveTextContent("Confirmez-vous le rejet du certificat EHC-26-11-000200");
    fireEvent.click(within(li).getByRole("button", { name: "Confirmer" }));
    await waitFor(() =>
      expect(api.reviewCertificate).toHaveBeenCalledWith("c-2", { decision: "reject", reason: "Plan manquant" }),
    );
    expect(await screen.findByText("Certificat EHC-26-11-000200 rejeté.")).toBeInTheDocument();
  });

  it("translates server refusals, never showing raw codes", async () => {
    const review = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(422, "invalid_valid_until"))
      .mockRejectedValueOnce(new ApiError(403, "insufficient_role"));
    setup({ reviewCertificate: review });
    const li = await item("EHC-26-61-000123");
    fireEvent.click(within(li).getByRole("button", { name: "Approuver" }));
    const form = within(li).getByLabelText("Valable jusqu’au").closest("form") as HTMLFormElement;
    fireEvent.submit(form);
    fireEvent.submit(form);
    expect(await within(li).findByText(/doit être comprise entre demain et dans cinq ans/, { selector: ".alert" })).toBeInTheDocument();
    fireEvent.submit(form);
    fireEvent.submit(form);
    expect(await within(li).findByText("Votre rôle ne permet pas cette action.")).toBeInTheDocument();
    expect(screen.queryByText(/insufficient_role|invalid_valid_until/)).not.toBeInTheDocument();
  });

  it("explains a missing signing key (503 signing_key_missing)", async () => {
    setup({ reviewCertificate: vi.fn().mockRejectedValue(new ApiError(503, "signing_key_missing")) });
    const li = await item("EHC-26-61-000123");
    fireEvent.click(within(li).getByRole("button", { name: "Approuver" }));
    const form = within(li).getByLabelText("Valable jusqu’au").closest("form") as HTMLFormElement;
    fireEvent.submit(form);
    fireEvent.submit(form);
    expect(await within(li).findByText(/La clé de signature des certificats n’est pas configurée/)).toBeInTheDocument();
    expect(screen.queryByText(/signing_key_missing/)).not.toBeInTheDocument();
  });

  it("lists decided certificates by status, without review actions", async () => {
    const certificates = vi.fn((opts?: { status?: string }) =>
      Promise.resolve({
        items: opts?.status === "approved" ? [makeQueueCertificate({ id: "c-9", code: "EHC-26-61-000099", status: "approved" })] : QUEUE,
        next_cursor: null,
      }),
    );
    setup({ certificates });
    await item("EHC-26-61-000123");
    fireEvent.change(screen.getByLabelText("Statut"), { target: { value: "approved" } });
    const li = await item("EHC-26-61-000099");
    expect(certificates).toHaveBeenLastCalledWith(expect.objectContaining({ status: "approved" }));
    expect(within(li).getByText("Approuvé")).toBeInTheDocument();
    expect(within(li).queryByRole("button", { name: "Approuver" })).not.toBeInTheDocument();
  });

  it("is read-only for other roles", async () => {
    setup({}, { sub: "u", realm_access: { roles: ["operator"] }, gouvernorat_code: "61" });
    await item("EHC-26-61-000123");
    expect(screen.getByText(/L’examen est réservé aux auditeurs/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approuver" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Rejeter" })).not.toBeInTheDocument();
    // The PDF stays available.
    expect(screen.getAllByRole("button", { name: /Obtenir le lien/ })).toHaveLength(2);
  });
});
