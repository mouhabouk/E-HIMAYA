import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { toHex } from "../lib/sha256";
import { makePublicCertificate } from "../test/fixtures";
import { fakeAuth, renderApp } from "../test/render";
import { VerifyPage } from "./VerifyPage";

const route = "/verify/:code";
const path = "/verify/EHC-26-61-000123";
const KEY = "GET /api/v1/public/certificates/EHC-26-61-000123";

async function sha(text: string) {
  return toHex(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text))));
}

describe("VerifyPage (public, §7)", () => {
  it("shows a valid certificate without signing in and without a token", async () => {
    const { calls } = renderApp(<VerifyPage />, {
      auth: fakeAuth(null),
      path,
      route,
      lang: "en",
      routes: { [KEY]: { body: makePublicCertificate() } },
    });
    expect(await screen.findByRole("heading", { name: "Valid certificate" })).toBeInTheDocument();
    expect(screen.getByText("Société X", { selector: "dd" })).toBeInTheDocument();
    expect(await screen.findByText("Sfax")).toBeInTheDocument();
    expect(screen.getByText("Valid (signed by the platform)")).toBeInTheDocument();
    expect(calls(KEY)).toHaveLength(1);
  });

  it("explains why a certificate is not valid", async () => {
    renderApp(<VerifyPage />, {
      path,
      route,
      lang: "fr",
      routes: { [KEY]: { body: makePublicCertificate({ valid: false, superseded: true, valid_until: "2020-01-01" }) } },
    });
    expect(await screen.findByRole("heading", { name: "Certificat non valide" })).toBeInTheDocument();
    expect(screen.getByText("un certificat plus récent l’a remplacé ;")).toBeInTheDocument();
    expect(screen.getByText("sa validité a expiré ;")).toBeInTheDocument();
  });

  it("says a revoked certificate is not valid, and what the certificate is", async () => {
    renderApp(<VerifyPage />, {
      path,
      route,
      lang: "en",
      routes: {
        [KEY]: {
          body: makePublicCertificate({ status: "revoked", valid: false, revoked: true, revoked_at: "2026-10-20T09:00:00Z" }),
        },
      },
    });
    expect(await screen.findByRole("heading", { name: "Certificate not valid" })).toBeInTheDocument();
    expect(screen.getByText("it was revoked by the platform auditors after its approval;")).toBeInTheDocument();
    expect(screen.getByText(/^Revoked on /)).toBeInTheDocument();
    expect(screen.getByText(/It is not an official certificate of the National Office of Civil Protection/)).toBeInTheDocument();
  });

  it("shows the suspended institution reason", async () => {
    renderApp(<VerifyPage />, { path, route, lang: "en", routes: { [KEY]: { body: makePublicCertificate({ valid: false }) } } });
    expect(await screen.findByText("the institution is suspended;")).toBeInTheDocument();
  });

  it("says when no certificate has this code (404), never the raw code", async () => {
    renderApp(<VerifyPage />, { path, route, lang: "ar", routes: { [KEY]: { status: 404, body: { detail: "not_found" } } } });
    expect(await screen.findByRole("heading", { name: "شهادة غير معروفة" })).toBeInTheDocument();
    expect(screen.queryByText("not_found")).not.toBeInTheDocument();
  });

  it("compares a dropped PDF locally: match", async () => {
    const content = "%PDF-1.7 certificate";
    const { fetch } = renderApp(<VerifyPage />, {
      path,
      route,
      lang: "en",
      routes: { [KEY]: { body: makePublicCertificate({ pdf_sha256: (await sha(content)).toUpperCase() }) } },
    });
    const input = await screen.findByLabelText("PDF file to compare");
    const before = fetch.mock.calls.length;
    fireEvent.change(input, { target: { files: [new File([content], "cert.pdf", { type: "application/pdf" })] } });
    expect(await screen.findByText("The file matches")).toBeInTheDocument();
    // The file never leaves the browser: hashing makes no request.
    expect(fetch.mock.calls.length).toBe(before);
  });

  it("compares a dropped PDF locally: mismatch (drag and drop)", async () => {
    renderApp(<VerifyPage />, { path, route, lang: "en", routes: { [KEY]: { body: makePublicCertificate({ pdf_sha256: "0".repeat(64) }) } } });
    const zone = await screen.findByTestId("file-drop");
    const file = new File(["tampered"], "cert.pdf", { type: "application/pdf" });
    fireEvent.drop(zone, { dataTransfer: { files: [file] } });
    expect(await screen.findByText("The file does not match")).toBeInTheDocument();
    expect(screen.getByText(await sha("tampered"))).toBeInTheDocument();
  });
});
