// covers: phase B1 (docs/phase-b/design.md §2bis): emergency hub topics and items, Yamen's request of 2026-10-23.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Guide, GuideItem, ItemText } from "../lib/guide";
import { linesOf, validateItem } from "../lib/guide";
import { fakeApi, fakeAuth, fakeGuideApi, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { EmergencyGuidePage } from "./EmergencyGuidePage";

const EDITOR = { ...OPERATOR_CLAIMS, realm_access: { roles: ["content_editor"] }, scope_level: "national" };
const txt = (title: string): ItemText => ({ title, call: [], steps: ["Appuyez sur la plaie"], dont: [] });

const ITEM: GuideItem = {
  id: "i1",
  topic_id: "t1",
  position: 0,
  content: { ar: txt("نزيف حاد"), fr: txt("Saignement abondant"), en: txt("Severe bleeding") },
  call_198: true,
  hidden: false,
  validated: false,
  validated_by: null,
  validated_at: null,
  version: 1,
  updated_at: "2026-10-23T09:00:00Z",
};

const GUIDE: Guide = {
  revision: 3,
  icons: ["drop", "fire"],
  palette: ["#C62828", "#2E7D32"],
  topics: [
    {
      id: "t1",
      key: "bleeding",
      title: { ar: "النزيف", fr: "Saignements", en: "Bleeding" },
      icon: "drop",
      colour: "#C62828",
      position: 0,
      hidden: false,
      version: 1,
      updated_at: "2026-10-23T09:00:00Z",
      items: [ITEM],
    },
    {
      id: "t2",
      key: "fire",
      title: { ar: "الحرائق", fr: "Incendies", en: "Fires" },
      icon: "fire",
      colour: "#2E7D32",
      position: 10,
      hidden: false,
      version: 1,
      updated_at: "2026-10-23T09:00:00Z",
      items: [],
    },
  ],
};

function setup(overrides: Partial<ReturnType<typeof fakeGuideApi>> = {}) {
  const api = fakeApi({ ...fakeGuideApi(), guide: vi.fn(() => Promise.resolve(GUIDE)), ...overrides });
  renderApp(<EmergencyGuidePage />, { api, auth: fakeAuth(EDITOR), lang: "fr" });
  return api;
}

describe("guide helpers", () => {
  it("splits lines and checks every language", () => {
    expect(linesOf(" a \n\n b\n")).toEqual(["a", "b"]);
    expect(validateItem(ITEM.content)).toBeNull();
    expect(validateItem({ ...ITEM.content, en: { ...txt(""), title: "" } })).toEqual({ lang: "en", error: "title" });
    expect(validateItem({ ...ITEM.content, ar: { ...txt("x"), steps: [] } })).toEqual({ lang: "ar", error: "steps" });
  });
});

describe("EmergencyGuidePage", () => {
  it("lists topics with their items and shows the [SIM] state of unvalidated items", async () => {
    setup();
    const topic = await screen.findByRole("region", { name: "Saignements" });
    expect(within(topic).getByText("Saignement abondant")).toBeInTheDocument();
    expect(within(topic).getByText("[SIM] En attente de validation médicale")).toBeInTheDocument();
    expect(within(topic).getByRole("button", { name: "Monter « Saignements »" })).toBeDisabled();
    expect(screen.getByRole("region", { name: "Incendies" })).toBeInTheDocument();
  });

  it("adds an item to a topic in three languages", async () => {
    const createItem = vi.fn(() => Promise.resolve(GUIDE));
    setup({ createItem });
    const topic = await screen.findByRole("region", { name: "Incendies" });
    fireEvent.click(within(topic).getByRole("button", { name: "Ajouter une fiche" }));
    const titles = within(topic).getAllByLabelText("Titre");
    const steps = within(topic).getAllByLabelText("Étapes, dans l’ordre");
    ["حريق غابة", "Feu de forêt", "Forest fire"].forEach((v, i) => fireEvent.change(titles[i] as HTMLElement, { target: { value: v } }));
    steps.forEach((el) => fireEvent.change(el, { target: { value: "Éloignez-vous\nAppelez le 198" } }));
    fireEvent.click(within(topic).getByLabelText("Afficher le bouton « Appeler le 198 » sur cette fiche"));
    fireEvent.change(within(topic).getByLabelText("Motif de la modification"), { target: { value: "Saison des feux" } });
    fireEvent.click(within(topic).getByRole("button", { name: "Ajouter la fiche" }));
    await waitFor(() => expect(createItem).toHaveBeenCalledTimes(1));
    expect(createItem).toHaveBeenCalledWith("t2", {
      call_198: true,
      reason: "Saison des feux",
      content: {
        ar: { title: "حريق غابة", call: [], steps: ["Éloignez-vous", "Appelez le 198"], dont: [] },
        fr: { title: "Feu de forêt", call: [], steps: ["Éloignez-vous", "Appelez le 198"], dont: [] },
        en: { title: "Forest fire", call: [], steps: ["Éloignez-vous", "Appelez le 198"], dont: [] },
      },
    });
  });

  it("hides an item with a reason, moves a topic, records a validation", async () => {
    const updateItem = vi.fn(() => Promise.resolve(GUIDE));
    const moveTopic = vi.fn(() => Promise.resolve(GUIDE));
    const validateItemCall = vi.fn(() => Promise.resolve(GUIDE));
    setup({ updateItem, moveTopic, validateItem: validateItemCall });
    const topic = await screen.findByRole("region", { name: "Saignements" });
    const item = within(topic).getByText("Saignement abondant").closest("li");
    if (!item) throw new Error("no item");
    fireEvent.click(within(item).getByRole("button", { name: "Masquer" }));
    fireEvent.change(within(item).getByLabelText("Motif de la modification"), { target: { value: "À revoir" } });
    fireEvent.click(within(item).getByRole("button", { name: "Masquer" }));
    await waitFor(() => expect(updateItem).toHaveBeenCalledWith("i1", { version: 1, reason: "À revoir", hidden: true }));

    fireEvent.click(within(item).getByRole("button", { name: "Enregistrer la validation médicale" }));
    fireEvent.change(within(item).getAllByLabelText("Motif de la modification").at(-1) as HTMLElement, {
      target: { value: "Validé par Dr Ben Salah" },
    });
    fireEvent.click(within(item).getByRole("button", { name: "Confirmer la validation" }));
    await waitFor(() => expect(validateItemCall).toHaveBeenCalledWith("i1", 1, "Validé par Dr Ben Salah"));

    fireEvent.click(screen.getByRole("button", { name: "Descendre « Saignements »" }));
    await waitFor(() => expect(moveTopic).toHaveBeenCalledWith("t1", "down"));
  });
});
