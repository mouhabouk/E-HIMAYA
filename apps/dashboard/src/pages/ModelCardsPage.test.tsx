// covers: L5 (docs/phase-l/design-l5.md §4.1 and §4.2, item 9): the model cards with their dated figures, the small
// samples flagged, the thresholds, the committee's decision with its minutes reference (AI-01), the PDF, and the
// drowning model in shadow marked [SIM] and trained on demand.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DROWNING_CARD, fakeModelCardsApi, FIRE_CARD } from "../test/modelCardsFixtures";
import { fakeApi, renderApp } from "../test/render";
import { ModelCardsPage } from "./ModelCardsPage";

describe("ModelCardsPage", () => {
  it("shows each card with its figures, flags the small samples and exports the PDF", async () => {
    const api = fakeModelCardsApi();
    renderApp(<ModelCardsPage />, { api: fakeApi(api), lang: "ar" });
    const fire = (await screen.findByRole("heading", { name: FIRE_CARD.name })).closest("section") as HTMLElement;
    expect(within(fire).getByText("ينتظر اعتماد اللجنة")).toBeInTheDocument();
    const rows = within(fire).getAllByRole("row");
    expect(rows[2]).toHaveTextContent("بعيد");
    expect(rows[2]).toHaveTextContent("عينة صغيرة");
    expect(rows[1]).not.toHaveTextContent("عينة صغيرة");
    expect(within(fire).getByText("أدنى ثقة لاقتراح")).toBeInTheDocument();
    expect(within(fire).getByText("لم تتخذ اللجنة قرارا بعد.")).toBeInTheDocument();
    fireEvent.click(within(fire).getByRole("button", { name: "تصدير PDF" }));
    await waitFor(() => expect(api.modelCardPdf).toHaveBeenCalledWith("fire_smoke", "ar"));
    expect(api.modelCards).toHaveBeenCalledWith("ar", expect.anything());
  });

  it("records the committee's decision only with the minutes reference", async () => {
    const api = fakeModelCardsApi();
    renderApp(<ModelCardsPage />, { api: fakeApi(api), lang: "ar" });
    const fire = (await screen.findByRole("heading", { name: FIRE_CARD.name })).closest("section") as HTMLElement;
    expect(within(fire).getByRole("radio", { name: "اعتماد العتبات كما تظهر" })).toBeChecked();
    fireEvent.click(within(fire).getByRole("button", { name: "سجّل القرار" }));
    expect(await within(fire).findByText("اكتب مرجع المحضر (3 أحرف على الأقل).")).toBeInTheDocument();
    expect(api.decideModel).not.toHaveBeenCalled();
    const reference = within(fire).getByLabelText("مرجع المحضر");
    expect(reference).toBeRequired();
    fireEvent.change(reference, { target: { value: "PV 2026/07" } });
    fireEvent.click(within(fire).getByRole("button", { name: "سجّل القرار" }));
    await waitFor(() =>
      expect(api.decideModel).toHaveBeenCalledWith("fire_smoke", {
        decision: "approved",
        version: FIRE_CARD.version,
        reference: "PV 2026/07",
        note: "",
      }),
    );
  });

  it("marks the drowning model as simulated, in shadow, and trains a new version", async () => {
    const api = fakeModelCardsApi();
    renderApp(<ModelCardsPage />, { api: fakeApi(api), lang: "ar" });
    const card = (await screen.findByRole("heading", { name: DROWNING_CARD.name })).closest("section") as HTMLElement;
    expect(within(card).getByText("في الظل")).toBeInTheDocument();
    expect(within(card).getAllByText("[SIM]").length).toBeGreaterThan(0);
    expect(within(card).getByText("PV 2026/07")).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: "درّب نسخة جديدة" }));
    await waitFor(() => expect(api.trainDrowningModel).toHaveBeenCalled());
  });
});
