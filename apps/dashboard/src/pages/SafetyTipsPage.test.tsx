import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import type { SafetyTip, SafetyTipBody } from "../lib/opsTypes";
import { makeTip } from "../test/opsFixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { allComplete, cleanContent, SafetyTipsPage } from "./SafetyTipsPage";

const EDITOR = { ...OPERATOR_CLAIMS, name: "Rim Editor", realm_access: { roles: ["content_editor"] }, scope_level: "national" };

function setup(tips: SafetyTip[], overrides: Parameters<typeof fakeApi>[0] = {}) {
  const api = fakeApi({ tips: vi.fn(() => Promise.resolve(tips)), ...overrides });
  return renderApp(<SafetyTipsPage />, { api, auth: fakeAuth(EDITOR), lang: "fr", path: "/safety-tips" });
}

describe("safety tip helpers", () => {
  it("trims, drops empty items and checks the three languages", () => {
    const content = cleanContent({
      ar: { title: " عنوان ", do: [" افعل ", "  "], dont: [] },
      fr: { title: "Titre", do: [], dont: ["Ne pas"] },
      en: { title: "", do: ["Do"], dont: [] },
    });
    expect(content.ar).toEqual({ title: "عنوان", do: ["افعل"], dont: [] });
    expect(allComplete(content)).toBe(false);
    expect(allComplete({ ...content, en: { title: "Title", do: ["Do"], dont: [] } })).toBe(true);
  });
});

describe("SafetyTipsPage", () => {
  it("lists tips by position with status and per-language completeness", async () => {
    setup([
      makeTip({ id: "t-2", hazard: "flood", position: 20, status: "draft", content: { ...makeTip().content, en: { title: "", do: [], dont: [] } } }),
      makeTip(),
    ]);
    const table = await screen.findByRole("table", { name: "Conseils de sécurité" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(within(rows[0] as HTMLElement).getByText("Incendies")).toBeInTheDocument();
    expect(within(rows[0] as HTMLElement).getByText("Publié")).toBeInTheDocument();
    const flood = rows[1] as HTMLElement;
    expect(within(flood).getByText("Brouillon")).toBeInTheDocument();
    expect(within(flood).getByText(/EN ✗/)).toBeInTheDocument();
  });

  it("creates a draft, blocks publishing until complete, previews in RTL and publishes", async () => {
    const created = makeTip({ id: "t-9", hazard: "storm", status: "draft", position: 20 });
    const createTip = vi.fn(() => Promise.resolve(created));
    const publishTip = vi.fn(() => Promise.resolve({ ...created, status: "published" as const, version: 2 }));
    setup([makeTip()], { createTip, publishTip });
    await screen.findByRole("table", { name: "Conseils de sécurité" });
    // The next position follows the last tip (10 → 20).
    fireEvent.click(screen.getByRole("button", { name: "Nouveau conseil" }));
    const editor = screen.getByRole("region", { name: "Nouveau conseil" });

    fireEvent.change(within(editor).getByLabelText("Risque"), { target: { value: "storm" } });
    fireEvent.change(within(editor).getByLabelText("Titre"), { target: { value: "العواصف" } });
    fireEvent.click(within(editor).getByRole("button", { name: "Ajouter à « À faire »" }));
    fireEvent.change(within(editor).getByLabelText("À faire, élément 1"), { target: { value: "ابق في الداخل" } });
    const preview = within(editor).getByRole("region", { name: "Aperçu (العربية)" });
    expect(within(preview).getByRole("heading", { name: "العواصف" }).closest("[dir]")).toHaveAttribute("dir", "rtl");
    expect(within(preview).getByText("✓ ابق في الداخل")).toBeInTheDocument();
    expect(within(editor).getByText(/La publication exige/)).toBeInTheDocument();

    fireEvent.click(within(editor).getByRole("button", { name: "Enregistrer" }));
    await waitFor(() =>
      expect(createTip).toHaveBeenCalledWith({
        hazard: "storm",
        position: 20,
        content: {
          ar: { title: "العواصف", do: ["ابق في الداخل"], dont: [] },
          fr: { title: "", do: [], dont: [] },
          en: { title: "", do: [], dont: [] },
        },
      }),
    );
    // The saved tip is complete (from the server): publishing is now possible.
    const publish = await within(editor).findByRole("button", { name: "Publier" });
    expect(publish).toBeEnabled();
    fireEvent.click(publish);
    await waitFor(() => expect(publishTip).toHaveBeenCalledWith("t-9"));
    expect(await within(editor).findByText(/Conseil publié/)).toBeInTheDocument();
    expect(within(editor).getByRole("button", { name: "Dépublier" })).toBeInTheDocument();
  });

  it("edits a language tab, reorders items and shows the server's translation_missing refusal", async () => {
    const tip = makeTip({
      content: { ...makeTip().content, fr: { title: "Incendie", do: ["Appelez le 198", "Sortez"], dont: [] } },
    });
    const updateTip = vi.fn(() => Promise.reject(new ApiError(409, "translation_missing", "translation_missing")));
    setup([tip], { updateTip });
    fireEvent.click(await screen.findByRole("button", { name: "Modifier : Incendie" }));
    const editor = screen.getByRole("region", { name: "Modifier le conseil" });
    fireEvent.click(within(editor).getByRole("tab", { name: /Français/ }));
    expect(within(editor).getByRole("tab", { name: /Français/ })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(within(editor).getByRole("button", { name: "Descendre l’élément 1" }));
    expect(within(editor).getByLabelText("À faire, élément 1")).toHaveValue("Sortez");
    expect(within(editor).getByRole("region", { name: "Aperçu (Français)" }).querySelector("[dir]")).toHaveAttribute(
      "dir",
      "ltr",
    );
    fireEvent.click(within(editor).getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(updateTip).toHaveBeenCalledTimes(1));
    const [id, body] = vi.mocked(updateTip).mock.calls[0] as unknown as [string, SafetyTipBody];
    expect(id).toBe("t-1");
    expect(body.version).toBe(1);
    expect(body.content.fr).toEqual({ title: "Incendie", do: ["Sortez", "Appelez le 198"], dont: [] });
    expect(await within(editor).findByText(/Traduction incomplète/)).toBeInTheDocument();
  });

  it("deletes a tip after confirmation", async () => {
    const deleteTip = vi.fn(() => Promise.resolve(undefined));
    setup([makeTip()], { deleteTip });
    fireEvent.click(await screen.findByRole("button", { name: "Modifier : Incendie" }));
    const editor = screen.getByRole("region", { name: "Modifier le conseil" });
    fireEvent.click(within(editor).getByRole("button", { name: "Supprimer" }));
    expect(within(editor).getByRole("alert")).toHaveTextContent("le supprimer le retire des applications");
    fireEvent.click(within(editor).getByRole("button", { name: "Confirmer la suppression" }));
    await waitFor(() => expect(deleteTip).toHaveBeenCalledWith("t-1"));
    expect(await screen.findByText("Conseil supprimé.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Modifier le conseil" })).not.toBeInTheDocument();
  });
});
