// covers: the Office's reference lists (migration 0091, Yamen 2026-11-01): read by every staff member, kept by the
// central room (add, retire), the crop units shown.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RefItem } from "../lib/references";
import { fakeApi, REFERENCES, renderApp } from "../test/render";
import { ReferencesPage } from "./ReferencesPage";

describe("ReferencesPage", () => {
  it("lists the lists and their items, read only for a reader", async () => {
    renderApp(<ReferencesPage />, { lang: "fr" });
    const nav = await screen.findByRole("navigation", { name: "Listes" });
    fireEvent.click(within(nav).getByRole("button", { name: /Pertes agricoles/ }));
    const table = screen.getByRole("table", { name: "Pertes agricoles" });
    expect(within(table).getByText("قرط")).toBeInTheDocument();
    expect(within(table).getByText("botte")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ajouter" })).not.toBeInTheDocument();
  });

  it("lets the central room add and retire an item", async () => {
    const item = REFERENCES.lists[0]?.items[0] as RefItem;
    const addReference = vi.fn(() => Promise.resolve(item));
    const changeReference = vi.fn(() => Promise.resolve(item));
    const api = fakeApi({
      references: vi.fn(() => Promise.resolve({ ...REFERENCES, can_manage: true })),
      addReference,
      changeReference,
    });
    renderApp(<ReferencesPage />, { api, lang: "fr" });
    fireEvent.change(await screen.findByLabelText("Nouvel élément"), { target: { value: "غابة صنوبر" } });
    fireEvent.change(screen.getByLabelText("Code"), { target: { value: "7" } });
    fireEvent.click(screen.getByRole("button", { name: "Ajouter" }));
    await waitFor(() => expect(addReference).toHaveBeenCalledWith("forest_place", { label_ar: "غابة صنوبر", code: "7" }));
    fireEvent.click(screen.getByRole("button", { name: "Retirer" }));
    await waitFor(() => expect(changeReference).toHaveBeenCalledWith("f1", { active: false }));
  });
});
