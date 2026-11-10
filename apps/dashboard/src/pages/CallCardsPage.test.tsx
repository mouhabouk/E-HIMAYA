// covers: OS2 (docs/phase-os2/design-os2.md §3): the Office writes a new version of a card, the doctor validates a
// medical one, the head of operations approves it; a gouvernorat's room reads the cards and tries them only.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CallCard } from "../lib/callCards";
import { callCardRights } from "../lib/roles";
import { SIM_CALL_CARDS } from "../test/callCardsData";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { CallCardsPage } from "./CallCardsPage";

const person = (roles: string[], gouvernorat_code?: string) => ({
  sub: "u-1",
  name: "مكتب البطاقات",
  realm_access: { roles },
  ...(gouvernorat_code ? { gouvernorat_code } : {}),
});

const medical = SIM_CALL_CARDS.find((c) => c.category === "medical") as CallCard;
const draft: CallCard = {
  ...medical,
  id: "cc-medical-2",
  version: 2,
  status: "draft",
  sim: false,
  medical_validated_at: null,
  medical_validated_by: null,
  medical_reason: null,
  approved_at: null,
  approved_by: null,
  approval_reason: null,
  updated_at: "2026-11-10T09:00:00Z",
};

describe("CallCardsPage", () => {
  it("gives the actions to the national Office only", () => {
    expect(callCardRights({ roles: ["content_editor"], gouvernoratCode: null })).toEqual({
      edit: true,
      validate: true,
      approve: false,
    });
    expect(callCardRights({ roles: ["ops_manager"], gouvernoratCode: 21 })).toEqual({
      edit: false,
      validate: false,
      approve: false,
    });
  });

  it("lists the nine simulated cards and writes a new version with a reason", async () => {
    const createCardDraft = vi.fn(() => Promise.resolve(draft));
    const api = fakeApi({ callCards: vi.fn(() => Promise.resolve({ cards: SIM_CALL_CARDS })), createCardDraft });
    renderApp(<CallCardsPage />, { api, auth: fakeAuth(person(["content_editor"])), lang: "ar" });
    const table = await screen.findByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(10);
    fireEvent.click(screen.getByRole("button", { name: "نسخة جديدة" }));
    fireEvent.change(screen.getByLabelText("عنوان البطاقة"), { target: { value: "إسعاف: مريض أو مصاب" } });
    fireEvent.click(screen.getByRole("button", { name: "حفظ المسودة" }));
    fireEvent.change(screen.getByLabelText("السبب"), { target: { value: "توضيح العنوان" } });
    fireEvent.click(screen.getByRole("button", { name: "حفظ المسودة" }));
    await waitFor(() => expect(createCardDraft).toHaveBeenCalled());
    expect(createCardDraft).toHaveBeenCalledWith(
      "medical",
      expect.objectContaining({ title: "إسعاف: مريض أو مصاب" }),
      "توضيح العنوان",
    );
  });

  it("asks the medical validation of a medical draft before the head of operations approves it", async () => {
    const approveCard = vi.fn(() => Promise.resolve(draft));
    const cards = vi.fn(() => Promise.resolve({ cards: [...SIM_CALL_CARDS, draft] }));
    renderApp(<CallCardsPage />, {
      api: fakeApi({ callCards: cards, approveCard }),
      auth: fakeAuth(person(["ops_manager"])),
      lang: "ar",
    });
    expect(await screen.findByText("تنتظر التصديق الطبي قبل الاعتماد.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "تصديق طبي" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "اعتماد" }));
    fireEvent.change(screen.getByLabelText("السبب"), { target: { value: "راجعه الطبيب" } });
    fireEvent.click(screen.getByRole("button", { name: "اعتماد" }));
    await waitFor(() => expect(approveCard).toHaveBeenCalledWith("cc-medical-2", "راجعه الطبيب", draft.updated_at));
  });

  it("lets a gouvernorat's room try a card without changing it", async () => {
    renderApp(<CallCardsPage />, {
      api: fakeApi({ callCards: vi.fn(() => Promise.resolve({ cards: SIM_CALL_CARDS })) }),
      auth: fakeAuth(person(["operator"], "21")),
      lang: "ar",
    });
    const q = await screen.findByRole("group", { name: /هل يوجد نزيف قوي/ });
    expect(screen.queryByRole("button", { name: "نسخة جديدة" })).toBeNull();
    fireEvent.click(within(q).getByRole("radio", { name: "نعم" }));
    expect(screen.getByText("المستوى: حرج")).toBeInTheDocument();
  });
});
