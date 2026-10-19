import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import type { Message, MessageBody } from "../lib/opsTypes";
import type { Vertex } from "../lib/polygon";
import { makeMessage } from "../test/opsFixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { NotificationEditorPage } from "./NotificationEditorPage";

// MapLibre does not run in jsdom: a stand-in map adds the corners of a square, one per click.
const SQUARE: Vertex[] = [
  [10.1, 34.1],
  [10.3, 34.1],
  [10.3, 34.3],
  [10.1, 34.3],
];
vi.mock("../components/LazyPolygonMap", () => ({
  LazyPolygonDrawMap: ({
    vertices,
    onAddVertex,
    ariaLabel,
  }: {
    vertices: readonly Vertex[];
    onAddVertex?: (lon: number, lat: number) => void;
    ariaLabel: string;
  }) => (
    <div role="img" aria-label={ariaLabel}>
      {onAddVertex && (
        <button
          type="button"
          onClick={() => {
            const [lon, lat] = SQUARE[vertices.length % SQUARE.length] ?? [0, 0];
            onAddVertex(lon, lat);
          }}
        >
          fake-click
        </button>
      )}
    </div>
  ),
}));

const EDITOR = { sub: "e-1", name: "Rim Editor", realm_access: { roles: ["content_editor"] }, scope_level: "national" };
const MANAGER = { ...OPERATOR_CLAIMS, realm_access: { roles: ["ops_manager"] } };

function setup(path: string, claims: Record<string, unknown> = EDITOR, overrides: Parameters<typeof fakeApi>[0] = {}) {
  const api = fakeApi(overrides);
  return renderApp(
    <Routes>
      <Route path="/notifications" element={<p>Registre</p>} />
      <Route path="/notifications/new" element={<NotificationEditorPage />} />
      <Route path="/notifications/:id" element={<NotificationEditorPage />} />
    </Routes>,
    { api, auth: fakeAuth(claims), lang: "fr", path },
  );
}

const lastBody = (fn: unknown) => {
  const calls = vi.mocked(fn as (...a: unknown[]) => unknown).mock.calls;
  return calls[calls.length - 1]?.at(-1) as MessageBody;
};

describe("NotificationEditorPage", () => {
  it("refuses an incomplete alert with field errors", async () => {
    const createMessage = vi.fn();
    setup("/notifications/new?kind=alert", EDITOR, { createMessage });
    fireEvent.click(await screen.findByRole("button", { name: "Enregistrer le brouillon" }));
    expect(await screen.findByText("Corrigez les champs signalés.")).toBeInTheDocument();
    expect(screen.getByText("Le titre en arabe est obligatoire.")).toBeInTheDocument();
    expect(screen.getByText("Choisissez un niveau de vigilance.")).toBeInTheDocument();
    expect(screen.getByLabelText("Titre (arabe)")).toHaveAttribute("aria-invalid", "true");
    expect(createMessage).not.toHaveBeenCalled();
  });

  it("drafts an alert over a drawn area, then shows the saved draft with its audience", async () => {
    const created = makeMessage({ id: "m-9", area: { gouvernorat_codes: [], polygon: { type: "Polygon", coordinates: [[...SQUARE, SQUARE[0] ?? [0, 0]]] } } });
    const createMessage = vi.fn(() => Promise.resolve(created));
    const message = vi.fn(() => Promise.resolve(created));
    const messageAudience = vi.fn(() => Promise.resolve({ push: 12, sms: 3, email: 4 }));
    setup("/notifications/new?kind=alert", EDITOR, { createMessage, message, messageAudience });

    expect(await screen.findByRole("heading", { name: "Nouvelle alerte" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Titre (arabe)"), { target: { value: "تنبيه أمطار" } });
    fireEvent.change(screen.getByLabelText("Texte (arabe)"), { target: { value: "تجنبوا الأودية" } });
    fireEvent.change(screen.getByLabelText("Niveau de vigilance"), { target: { value: "high" } });
    fireEvent.change(screen.getByLabelText("Catégorie"), { target: { value: "weather" } });
    fireEvent.change(screen.getByLabelText("Phénomène"), { target: { value: "heavy_rain" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "SMS" }));
    expect(screen.getByText("تنبيه أمطار: تجنبوا الأودية")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: "Zone dessinée" }));
    const draw = await screen.findByRole("button", { name: "fake-click" });
    fireEvent.click(draw);
    fireEvent.click(draw);
    // Two points are not an area yet.
    expect(screen.getByRole("button", { name: "Terminer la zone" })).toBeDisabled();
    fireEvent.click(draw);
    fireEvent.click(draw);
    expect(screen.getByText(/Sommets : 4/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Annuler le dernier point" }));
    fireEvent.click(draw);
    fireEvent.click(screen.getByRole("button", { name: "Terminer la zone" }));
    expect(screen.queryByRole("button", { name: "fake-click" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer le brouillon" }));
    await waitFor(() => expect(createMessage).toHaveBeenCalledTimes(1));
    const body = lastBody(createMessage);
    expect(body).toMatchObject({ kind: "alert", severity: "high", category: "weather", hazard: "heavy_rain", channels: ["push", "sms"] });
    expect(body.area.gouvernorat_codes).toEqual([]);
    expect(body.area.polygon?.coordinates[0]).toEqual([...SQUARE, SQUARE[0]]);

    // The page moves to the saved draft, whose audience is estimated.
    await waitFor(() => expect(message).toHaveBeenCalledWith("m-9", expect.anything()));
    expect(await screen.findByText(/Notification : 12 appareils · SMS : 3 numéros · E-mail : 4 adresses/)).toBeInTheDocument();
  });

  it("publishes a saved draft after a confirmation that states the estimate", async () => {
    const draft = makeMessage();
    const publishMessage = vi.fn(() =>
      Promise.resolve({ ...draft, status: "published" as const, version: 2, published_at: draft.created_at }),
    );
    setup("/notifications/m-1", EDITOR, {
      message: vi.fn(() => Promise.resolve(draft)),
      messageAudience: vi.fn(() => Promise.resolve({ push: 12, sms: 3, email: 4 })),
      publishMessage,
    });
    const publish = await screen.findByRole("button", { name: "Publier l’alerte" });
    await waitFor(() => expect(publish).toBeEnabled());
    fireEvent.click(publish);
    const confirm = screen.getByRole("alert");
    expect(confirm).toHaveTextContent("environ 12 appareils (notification), 3 numéros (SMS) et 4 adresses (e-mail)");
    expect(publishMessage).not.toHaveBeenCalled();
    fireEvent.click(within(confirm).getByRole("button", { name: "Confirmer la publication" }));
    await waitFor(() => expect(publishMessage).toHaveBeenCalledWith("m-1"));
    // The published message is no longer editable: the delivery view replaces the composer.
    expect(await screen.findByRole("heading", { name: "Distribution par canal" })).toBeInTheDocument();
  });

  it("asks to save before publishing an edited draft and reports a version conflict", async () => {
    const updateMessage = vi.fn(() => Promise.reject(new ApiError(409, "version_conflict", "version_conflict")));
    setup("/notifications/m-1", EDITOR, { message: vi.fn(() => Promise.resolve(makeMessage())), updateMessage });
    const title = await screen.findByLabelText("Titre (français)");
    fireEvent.change(title, { target: { value: "Alerte orages" } });
    expect(screen.getByRole("button", { name: "Publier l’alerte" })).toBeDisabled();
    expect(screen.getByText(/Enregistrez les modifications avant de publier/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer le brouillon" }));
    await waitFor(() => expect(updateMessage).toHaveBeenCalledTimes(1));
    const [id] = vi.mocked(updateMessage).mock.calls[0] as unknown as [string];
    expect(id).toBe("m-1");
    expect(lastBody(updateMessage)).toMatchObject({ version: 1, title: { fr: "Alerte orages" } });
    expect(await screen.findByText("Les données ont changé entre-temps. Rechargez puis réessayez.")).toBeInTheDocument();
  });

  it("deletes a draft after confirmation", async () => {
    const deleteMessage = vi.fn(() => Promise.resolve(undefined));
    setup("/notifications/m-1", EDITOR, { message: vi.fn(() => Promise.resolve(makeMessage())), deleteMessage });
    fireEvent.click(await screen.findByRole("button", { name: "Supprimer le brouillon" }));
    fireEvent.click(within(screen.getByRole("alert")).getByRole("button", { name: "Confirmer la suppression" }));
    await waitFor(() => expect(deleteMessage).toHaveBeenCalledWith("m-1"));
    expect(await screen.findByText("Registre")).toBeInTheDocument();
  });

  it("lets an operations manager draft an alert for its gouvernorat but not publish it nor write an information", async () => {
    setup("/notifications/m-1", MANAGER, { message: vi.fn(() => Promise.resolve(makeMessage())) });
    expect(await screen.findByRole("button", { name: "Enregistrer le brouillon" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Publier l’alerte" })).not.toBeInTheDocument();
    expect(screen.getByText(/La publication est réservée/)).toBeInTheDocument();
    expect(await screen.findByText("Cible : gouvernorat de Sfax")).toBeInTheDocument();
  });

  it("refuses a new information to an operations manager", async () => {
    setup("/notifications/new?kind=info", MANAGER);
    expect(await screen.findByText("Votre rôle ne permet pas cette action.")).toBeInTheDocument();
  });

  it("composes an information for one user", async () => {
    const createMessage = vi.fn(() => Promise.resolve(makeMessage({ id: "m-5", kind: "info" })));
    setup("/notifications/new?kind=info", EDITOR, { createMessage, message: vi.fn(() => new Promise<Message>(() => undefined)) });
    fireEvent.change(await screen.findByLabelText("Titre (arabe)"), { target: { value: "دورة تكوينية" } });
    fireEvent.change(screen.getByLabelText("Texte (arabe)"), { target: { value: "التسجيل مفتوح" } });
    fireEvent.change(screen.getByLabelText("Thème"), { target: { value: "training" } });
    fireEvent.change(screen.getByLabelText("Public"), { target: { value: "user" } });
    // A message to one user has no area.
    expect(screen.queryByText("Gouvernorats ciblés")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Identifiant de l’utilisateur"), { target: { value: "nope" } });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer le brouillon" }));
    expect(await screen.findByText("Identifiant invalide (UUID attendu).")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Identifiant de l’utilisateur"), {
      target: { value: "1b4e28ba-2fa1-11d2-883f-0016d3cca427" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer le brouillon" }));
    await waitFor(() => expect(createMessage).toHaveBeenCalledTimes(1));
    expect(lastBody(createMessage)).toMatchObject({
      kind: "info",
      topic: "training",
      audience: "user",
      user_id: "1b4e28ba-2fa1-11d2-883f-0016d3cca427",
      area: { gouvernorat_codes: [] },
    });
  });

  it("shows a published alert's delivery per channel and cancels it after confirmation", async () => {
    const published = makeMessage({
      status: "published",
      channels: ["push", "sms"],
      published_by: "Rim Editor",
      published_at: "2026-10-19T08:05:00Z",
      stats: { push: { status: "done", sent: 120, failed: 2 }, sms: { status: "running", sent: 40, failed: 0 } },
    });
    const cancelMessage = vi.fn(() => Promise.resolve({ ...published, status: "cancelled" as const, cancelled_at: "2026-10-19T09:00:00Z" }));
    setup("/notifications/m-1", EDITOR, { message: vi.fn(() => Promise.resolve(published)), cancelMessage });
    const table = await screen.findByRole("table", { name: "Distribution par canal" });
    const sms = within(table).getByRole("row", { name: /SMS/ });
    expect(within(sms).getByText("en cours")).toBeInTheDocument();
    expect(within(sms).getByText("40")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrer le brouillon" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Annuler l’alerte" }));
    expect(cancelMessage).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirmer l’annulation" }));
    await waitFor(() => expect(cancelMessage).toHaveBeenCalledWith("m-1"));
    expect(await screen.findByText("Annulé")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Annuler l’alerte" })).not.toBeInTheDocument();
  });
});
