import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Handler } from "../test/fetch";
import { makeOrg } from "../test/fixtures";
import { renderApp } from "../test/render";
import { RegisterOrgPage } from "./RegisterOrgPage";

vi.mock("../components/LazyMap", () => ({ MapPanel: () => <div data-testid="map" /> }));

const type = (label: RegExp | string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const next = () => fireEvent.click(screen.getByRole("button", { name: "Next" }));

async function fillAll() {
  await screen.findByRole("heading", { name: /Step 1 of 5/ });
  type(/^Institution name/, "Société X");
  type(/^Identifier/, " 1234567a ");
  next();
  await screen.findByRole("heading", { name: /Step 2 of 5/ });
  type(/^Capacity/, "420");
  type(/^Address/, "Route de Gabès km 4");
  next();
  await screen.findByRole("heading", { name: /Step 3 of 5/ });
  type("Latitude", "34.7");
  type("Longitude", "10.72");
  next();
  await screen.findByRole("heading", { name: /Step 4 of 5/ });
  type(/^Manager — full name/, "Karim Trabelsi");
  type(/^Manager — phone/, "20 123 456");
  next();
  await screen.findByRole("heading", { name: /Step 5 of 5/ });
}

function setup(reply: Handler) {
  return renderApp(<RegisterOrgPage />, { lang: "en", routes: { "POST /api/v1/orgs": reply } });
}

describe("RegisterOrgPage (FR-B-001)", () => {
  it("phase A, rule 2: a note explains the red asterisk of required fields", async () => {
    setup({ status: 201, body: makeOrg() });
    await screen.findByRole("heading", { name: /Step 1 of 5/ });
    expect(screen.getByText("Fields marked * are required.")).toBeInTheDocument();
    const name = screen.getByLabelText(/^Institution name/);
    expect(name).toBeRequired();
    const mark = document.querySelector(`label[for="${name.id}"] .required-mark`);
    expect(mark).toHaveAttribute("aria-hidden", "true");
  });

  it("walks through the wizard, posts the normalised card and shows the pending review screen", async () => {
    const { calls } = setup({ status: 201, body: makeOrg({ status: "pending_review" }) });
    await fillAll();
    expect(screen.getByText("1234567A")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Send the registration" }));
    expect(await screen.findByRole("heading", { name: "Registration sent" })).toBeInTheDocument();
    expect(screen.getByText("Pending review")).toBeInTheDocument();
    expect(await screen.findByText("Sfax")).toBeInTheDocument();
    const [post] = calls("POST /api/v1/orgs");
    expect(post?.body).toMatchObject({
      name: "Société X",
      kind: "industrial",
      identifier_type: "mf",
      identifier: "1234567A",
      capacity: 420,
      floors: null,
      receives_public: false,
      location: { lat: 34.7, lon: 10.72 },
      manager: { full_name: "Karim Trabelsi", phone: "+21620123456", email: null },
      contact_phone: null,
    });
  });

  it("validates each step on the client before moving on", async () => {
    const { calls } = setup({ status: 201, body: makeOrg() });
    await screen.findByRole("heading", { name: /Step 1 of 5/ });
    type(/^Institution name/, "X");
    type(/^Identifier/, "12345A");
    next();
    expect(await screen.findByText(/Invalid tax identifier/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Step 1 of 5/ })).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("National business register (RNE)"));
    type(/^Identifier/, "1234567A/A/M/000");
    next();
    expect(await screen.findByText(/Invalid RNE identifier/)).toBeInTheDocument();
    expect(calls("POST /api/v1/orgs")).toHaveLength(0);
  });

  it("puts a server error on its field and goes back to its step", async () => {
    setup({ status: 409, body: { detail: "identifier_already_registered" } });
    await fillAll();
    fireEvent.click(screen.getByRole("button", { name: "Send the registration" }));
    expect(await screen.findByRole("heading", { name: /Step 1 of 5/ })).toBeInTheDocument();
    expect(screen.getByText("An institution with this identifier is already registered.")).toBeInTheDocument();
    expect(screen.getByLabelText(/^Identifier/)).toHaveAttribute("aria-invalid", "true");
  });

  it("maps a FastAPI 422 on the location to the location step", async () => {
    setup({ status: 422, body: { detail: [{ loc: ["body", "location", "lat"], msg: "out of range" }] } });
    await fillAll();
    fireEvent.click(screen.getByRole("button", { name: "Send the registration" }));
    expect(await screen.findByRole("heading", { name: /Step 3 of 5/ })).toBeInTheDocument();
    expect(screen.getByText("The location must be in Tunisia.")).toBeInTheDocument();
  });

  it("shows account-level errors on the review step, translated", async () => {
    setup({ status: 403, body: { detail: "email_not_verified" } });
    await fillAll();
    fireEvent.click(screen.getByRole("button", { name: "Send the registration" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Verify your e-mail address/));
    expect(screen.queryByText("email_not_verified")).not.toBeInTheDocument();
  });
});
