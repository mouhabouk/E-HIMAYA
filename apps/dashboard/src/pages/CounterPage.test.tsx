import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CertificateStamp, CounterView } from "../lib/types";
import { makeCertificate } from "../test/fixtures";
import { AUDITOR_CLAIMS, fakeApi, fakeAuth, renderApp } from "../test/render";
import { CounterPage, counterCode, photoProblem, STAMP_PHOTO_MAX_BYTES } from "./CounterPage";

const STAMP: CertificateStamp = {
  id: "s-1",
  place: "Direction régionale de Sfax",
  gouvernorat_code: 61,
  stamped_on: "2026-10-20",
  note: null,
  stamped_by_name: "Leila Auditor",
  recorded_at: "2026-10-20T09:00:00Z",
  has_photo: true,
  changes: [],
};

function view(overrides: Partial<CounterView> = {}): CounterView {
  return {
    certificate: makeCertificate({
      status: "approved",
      reviewed_at: "2026-10-03T08:00:00Z",
      valid_until: "2027-10-03",
      needs_update: true,
      changes: [
        { section: "building", field: "capacity", certified: 300, current: 420 },
        { section: "hazmat", field: "items", certified: [], current: ["Chlore (UN 1017): 200 kg"] },
      ],
      stamps: [STAMP],
    }),
    valid: true,
    reasons: [],
    signature_valid: true,
    can_stamp: true,
    org_id: "o-1",
    org_name: "Société Chimique du Sud",
    org_kind: "industrial",
    org_status: "active",
    org_address: "Route de Gabès km 4",
    gouvernorat_code: 61,
    ...overrides,
  };
}

function setup(overrides: Parameters<typeof fakeApi>[0] = {}) {
  const api = fakeApi({ certificateLookup: vi.fn(() => Promise.resolve(view())), ...overrides });
  return renderApp(<CounterPage />, { api, auth: fakeAuth(AUDITOR_CLAIMS), lang: "fr", path: "/orgs/certificates/counter" });
}

function lookUp(text: string) {
  fireEvent.change(screen.getByLabelText("Code du certificat ou lien de vérification"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Vérifier" }));
}

describe("counterCode / photoProblem", () => {
  it("takes the code from a typed code or a whole verification link", () => {
    expect(counterCode(" ehc-26-61-000123 ")).toBe("EHC-26-61-000123");
    expect(counterCode("https://portail.example/verify/EHC-26-61-000123?x=1")).toBe("EHC-26-61-000123");
    expect(counterCode("EHC-26-61")).toBeNull();
  });

  it("accepts a JPEG or PNG of 5 MB at most", () => {
    expect(photoProblem(null)).toBeNull();
    expect(photoProblem(new File(["x"], "a.jpg", { type: "image/jpeg" }))).toBeNull();
    expect(photoProblem(new File(["x"], "a.gif", { type: "image/gif" }))).toBe("type");
    const big = new File(["x"], "a.png", { type: "image/png" });
    Object.defineProperty(big, "size", { value: STAMP_PHOTO_MAX_BYTES + 1 });
    expect(photoProblem(big)).toBe("size");
  });
});

describe("CounterPage", () => {
  it("refuses a text without a certificate code before asking the server", () => {
    const { api } = setup();
    lookUp("bonjour");
    expect(screen.getByText(/Code invalide/)).toBeInTheDocument();
    expect(api.certificateLookup).not.toHaveBeenCalled();
  });

  it("reads a verification link, shows validity, the comparison and the stamps", async () => {
    const { api } = setup();
    lookUp("https://portail.example/verify/EHC-26-61-000123");
    await waitFor(() => expect(api.certificateLookup).toHaveBeenCalledWith("EHC-26-61-000123", expect.anything()));
    expect(await screen.findByText("Certificat valide")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Société Chimique du Sud" })).toHaveAttribute("href", "/orgs/o-1");
    expect(screen.getByText("Conforme")).toBeInTheDocument();

    expect(screen.getByText("À mettre à jour (écarts : 2)")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Écarts entre l’approuvé et l’état actuel" });
    const capacity = within(table).getByRole("row", { name: /Capacité/ });
    expect(capacity).toHaveTextContent("300");
    expect(capacity).toHaveTextContent("420");
    expect(within(table).getByRole("row", { name: /Matières dangereuses/ })).toHaveTextContent("Chlore (UN 1017): 200 kg");

    const stamps = screen.getByRole("region", { name: "Cachets dans les directions régionales" });
    expect(within(stamps).getByText("Direction régionale de Sfax")).toBeInTheDocument();
    expect(within(stamps).getByText(/Agent : Leila Auditor/)).toBeInTheDocument();
  });

  it("explains why a certificate is not valid and offers no stamp", async () => {
    setup({
      certificateLookup: vi.fn(() =>
        Promise.resolve(view({ valid: false, reasons: ["revoked", "expired"], can_stamp: false })),
      ),
    });
    lookUp("EHC-26-61-000123");
    expect(await screen.findByText("Certificat non valide")).toBeInTheDocument();
    expect(screen.getByText("Révoqué")).toBeInTheDocument();
    expect(screen.getByText("Expiré")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrer le cachet" })).not.toBeInTheDocument();
  });

  it("records the stamp with the place of the agent's gouvernorat, then sends the photo", async () => {
    const { api } = setup({
      addStamp: vi.fn(() => Promise.resolve({ ...STAMP, id: "s-2", has_photo: false })),
      putStampPhoto: vi.fn(() => Promise.resolve({ ...STAMP, id: "s-2" })),
    });
    lookUp("EHC-26-61-000123");
    const form = await screen.findByRole("form", { name: "Enregistrer le cachet manuel" });
    await waitFor(() =>
      expect(within(form).getByLabelText("Lieu")).toHaveValue("Direction régionale de la protection civile de Sfax"),
    );
    fireEvent.change(within(form).getByLabelText("Remarque"), { target: { value: "Présenté sur papier" } });
    const photo = new File(["jpeg"], "cachet.jpg", { type: "image/jpeg" });
    fireEvent.change(within(form).getByLabelText(/Photo du papier cacheté/), { target: { files: [photo] } });
    fireEvent.click(within(form).getByRole("button", { name: "Enregistrer le cachet" }));

    await waitFor(() =>
      expect(api.addStamp).toHaveBeenCalledWith("c-1", {
        place: "Direction régionale de la protection civile de Sfax",
        stamped_on: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/) as string,
        note: "Présenté sur papier",
      }),
    );
    await waitFor(() => expect(api.putStampPhoto).toHaveBeenCalledWith("c-1", "s-2", photo));
    expect(await screen.findByText("Cachet du certificat EHC-26-61-000123 enregistré.")).toBeInTheDocument();
  });

  it("refuses an empty place and a photo of the wrong type before sending", async () => {
    const { api } = setup();
    lookUp("EHC-26-61-000123");
    const form = await screen.findByRole("form", { name: "Enregistrer le cachet manuel" });
    fireEvent.change(within(form).getByLabelText("Lieu"), { target: { value: "  " } });
    fireEvent.change(within(form).getByLabelText(/Photo du papier cacheté/), {
      target: { files: [new File(["gif"], "a.gif", { type: "image/gif" })] },
    });
    fireEvent.click(within(form).getByRole("button", { name: "Enregistrer le cachet" }));
    expect(within(form).getByText("Le lieu du cachet est requis.")).toBeInTheDocument();
    expect(within(form).getByText("Type de fichier non accepté.")).toBeInTheDocument();
    expect(api.addStamp).not.toHaveBeenCalled();
  });
});
