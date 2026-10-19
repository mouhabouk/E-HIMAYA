import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makeMessage } from "../test/opsFixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { NotificationsPage } from "./NotificationsPage";

const EDITOR = { sub: "e-1", name: "Rim Editor", realm_access: { roles: ["content_editor"] }, scope_level: "national" };
const MANAGER = { ...OPERATOR_CLAIMS, realm_access: { roles: ["ops_manager"] } };

const PUBLISHED = makeMessage({
  id: "m-2",
  status: "published",
  channels: ["push", "sms"],
  published_by: "Rim Editor",
  published_at: "2026-10-19T08:05:00Z",
  stats: { push: { status: "done", sent: 120, failed: 2 } },
});
const INFO = makeMessage({
  id: "m-3",
  kind: "info",
  severity: null,
  category: null,
  hazard: null,
  topic: "training",
  audience: "volunteers",
  title: { ar: "دورة تكوينية", fr: "", en: "" },
  area: { gouvernorat_codes: [], polygon: null },
});

function setup(claims: Record<string, unknown>, overrides: Parameters<typeof fakeApi>[0] = {}) {
  const api = fakeApi(overrides);
  return renderApp(<NotificationsPage />, { api, auth: fakeAuth(claims), lang: "fr", path: "/notifications" });
}

describe("NotificationsPage", () => {
  it("lists messages with kind, status, target and delivery, falling back to the Arabic title", async () => {
    setup(EDITOR, { messages: vi.fn(() => Promise.resolve({ items: [PUBLISHED, INFO], next_cursor: null })) });
    const table = await screen.findByRole("table", { name: "Registre des notifications et alertes" });
    const alert = within(table).getByRole("row", { name: /Alerte pluies abondantes/ });
    expect(within(alert).getByText("Alerte · Rouge")).toHaveClass("tag--severity-high");
    expect(within(alert).getByText("Publié")).toHaveClass("tag--message-published");
    expect(within(alert).getByText(/Notification : terminé, 120 envoyés, 2 échecs · SMS/)).toBeInTheDocument();
    expect(within(alert).getByRole("link", { name: "Alerte pluies abondantes" })).toHaveAttribute("href", "/notifications/m-2");
    const info = within(table).getByRole("row", { name: /دورة تكوينية/ });
    expect(within(info).getByText("Tout le pays")).toBeInTheDocument();
    expect(within(info).getByText(/Volontaires/)).toBeInTheDocument();
    expect(await within(alert).findByText("Sfax")).toBeInTheDocument();
  });

  it("filters by kind and status and loads more", async () => {
    const messages = vi.fn((filters: { kind?: string; status?: string }, opts: { cursor?: string | null } = {}) =>
      Promise.resolve(
        opts.cursor
          ? { items: [INFO], next_cursor: null }
          : { items: [PUBLISHED], next_cursor: filters.kind ? null : "c-2" },
      ),
    );
    setup(EDITOR, { messages });
    fireEvent.click(await screen.findByRole("button", { name: "Afficher plus" }));
    expect(await screen.findByRole("link", { name: "دورة تكوينية" })).toBeInTheDocument();
    expect(messages).toHaveBeenLastCalledWith({ kind: "", status: "" }, expect.objectContaining({ cursor: "c-2" }));

    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "alert" } });
    fireEvent.change(screen.getByLabelText("Statut"), { target: { value: "published" } });
    await waitFor(() =>
      expect(messages).toHaveBeenLastCalledWith({ kind: "alert", status: "published" }, expect.objectContaining({ cursor: null })),
    );
    await waitFor(() => expect(screen.queryByRole("button", { name: "Afficher plus" })).not.toBeInTheDocument());
  });

  it("shows active alerts and offers only the kinds the role may write", async () => {
    setup(MANAGER, { activeAlerts: vi.fn(() => Promise.resolve([PUBLISHED])) });
    const active = await screen.findByRole("region", { name: "Alertes en cours : 1" });
    expect(within(active).getByText(/jusqu’au/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Nouvelle alerte" })).toHaveAttribute("href", "/notifications/new?kind=alert");
    expect(screen.queryByRole("link", { name: "Nouvelle notification" })).not.toBeInTheDocument();
    expect(await screen.findByText("Aucun message ne correspond aux filtres.")).toBeInTheDocument();
  });
});
