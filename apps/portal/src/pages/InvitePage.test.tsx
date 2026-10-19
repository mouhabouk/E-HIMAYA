import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp, type RenderOptions } from "../test/render";
import { InvitePage } from "./InvitePage";

const PREVIEW = { org_name: "Société X", role: "editor", email: "amira@x.tn", expires_at: "2026-10-26T10:00:00Z" };

function setup(routes: RenderOptions["routes"]) {
  return renderApp(<InvitePage />, {
    path: "/invite/tok",
    route: "/invite/:token",
    lang: "en",
    routes,
  });
}

describe("InvitePage (§2)", () => {
  it("shows the invitation and accepts it", async () => {
    const { calls } = setup({
      "GET /api/v1/invitations/tok": { body: PREVIEW },
      "POST /api/v1/invitations/tok/accept": { body: { org_id: "o-1", role: "editor" } },
    });
    expect(await screen.findByText("You are invited to join Société X as Editor.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Accept the invitation" }));
    await waitFor(() => expect(calls("POST /api/v1/invitations/tok/accept")).toHaveLength(1));
  });

  it("warns before accepting when signed in with another e-mail, and maps 403 mismatch", async () => {
    setup({
      "GET /api/v1/invitations/tok": { body: { ...PREVIEW, email: "other@x.tn" } },
      "POST /api/v1/invitations/tok/accept": { status: 403, body: { detail: "invitation_email_mismatch" } },
    });
    expect(await screen.findByText(/but the invitation is for other@x.tn/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Accept the invitation" }));
    expect(await screen.findByText("This invitation was sent to another e-mail address. Sign in with the invited address.")).toBeInTheDocument();
  });

  it("maps expired and unknown invitations", async () => {
    setup({ "GET /api/v1/invitations/tok": { status: 410, body: { detail: "invitation_expired" } } });
    expect(await screen.findByText("This invitation has expired. Ask the administrator for a new one.")).toBeInTheDocument();
  });

  it("maps a used or revoked invitation", async () => {
    setup({ "GET /api/v1/invitations/tok": { status: 404, body: { detail: "invitation_not_found" } } });
    expect(await screen.findByText("This invitation does not exist, was already used or was revoked.")).toBeInTheDocument();
  });
});
