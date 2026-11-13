// covers: OS2-3 and OS2-4 (docs/phase-os2b/design-os2b.md): the statistics of the call-taking cards and the review
// of the nine [SIM] cards (the Office hands a draft over, the doctor validates or sends back, the manager approves).
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  minutes,
  percent,
  questionChanges,
  statsCsv,
  stepChanges,
  type CallCard,
  type CardStats,
  type ReviewItem,
} from "../lib/callCards";
import { CallCardsPage } from "../pages/CallCardsPage";
import { SIM_CALL_CARDS } from "../test/callCardsData";
import { fakeApi, fakeAuth, renderApp } from "../test/render";

const person = (roles: string[], gouvernorat_code?: string) => ({
  sub: "u-1",
  name: "مكتب البطاقات",
  realm_access: { roles },
  ...(gouvernorat_code ? { gouvernorat_code } : {}),
});

const medical = SIM_CALL_CARDS.find((c) => c.category === "medical") as CallCard;
const fire = SIM_CALL_CARDS.find((c) => c.category === "fire") as CallCard;
const changed = structuredClone(medical.content);
const breathing = changed.questions.find((q) => q.id === "breathing");
if (breathing) breathing.help = "ضع يدك على صدره";
changed.questions.push({ id: "faint", text: "هل فقد الوعي ثم استعاده؟", help: null, key: true, when: null, effects: {} });
const draft: CallCard = {
  ...medical,
  id: "cc-medical-2",
  version: 2,
  status: "draft",
  sim: false,
  content: changed,
  submitted_at: "2026-11-13T08:00:00Z",
  submitted_by_name: "مكتب الوقاية",
  notes: { faint: "حالات إغماء كثيرة", _card: "مراجعة أولى" },
  updated_at: "2026-11-13T08:00:00Z",
};

const item = (over: Partial<ReviewItem>): ReviewItem => ({
  category: "fire",
  title: fire.content.title,
  stage: "not_started",
  medical: false,
  approved: fire,
  draft: null,
  office: null,
  doctor: null,
  ...over,
});

const review = {
  items: [
    item({}),
    item({
      category: "medical",
      title: medical.content.title,
      stage: "doctor",
      medical: true,
      approved: medical,
      draft,
      office: "مكتب الوقاية",
      doctor: "الطبيب المنسق",
    }),
  ],
  done: 0,
  total: 2,
};

const figures = {
  entered: 10,
  with_card: 7,
  median_with_s: 125,
  median_without_s: 160,
  p90_s: 240,
  field_checked: 5,
  field_confirmed: 4,
};
const stats: CardStats = {
  days: 30,
  since: "2026-10-14T00:00:00Z",
  room: null,
  total: figures,
  national: figures,
  rooms: [{ room: "g:21", ...figures }],
  cards: [
    {
      category: "medical",
      title: medical.content.title,
      used: 7,
      median_s: 125,
      key_unknown: 3,
      key_answered: 10,
      field_checked: 5,
      checks: { confirmed: 4, nature_differs: 1, lives_not_on_card: 0, injured_not_on_card: 0, band_below_toll: 0 },
      questions: [
        { id: "breathing", text: "هل يتنفس تنفسا طبيعيا؟", key: true, yes: 4, no: 2, unknown: 4, field_changed: 1, field_answered: 2 },
      ],
      read: { cpr: 2 },
      instruction_titles: { cpr: "الإنعاش القلبي بالهاتف" },
    },
  ],
};

describe("call-taking cards: statistics and review", () => {
  it("compares a draft with the approved version and formats the figures", () => {
    const changes = questionChanges(medical.content, changed);
    expect(changes.map((c) => [c.kind, c.question.id])).toEqual([
      ["changed", "breathing"],
      ["added", "faint"],
    ]);
    expect(stepChanges(["أ", "ب"], ["أ", "ج"])).toEqual([
      { text: "أ", mark: "same" },
      { text: "ج", mark: "added" },
      { text: "ب", mark: "removed" },
    ]);
    expect(minutes(125)).toBe("2:05");
    expect(minutes(null)).toBe("—");
    expect(percent(1, 0)).toBeNull();
    const csv = statsCsv(stats, (r) => (r === "g:21" ? "نابل, الجهوية" : r));
    expect(csv.split("\n")[1]).toBe('"نابل, الجهوية",10,7,125,160,240,5,4');
  });

  it("shows card use and call time per room, and a card's questions", async () => {
    const cardStats = vi.fn(() => Promise.resolve(stats));
    renderApp(<CallCardsPage />, {
      api: fakeApi({ callCards: vi.fn(() => Promise.resolve({ cards: SIM_CALL_CARDS })), cardStats }),
      auth: fakeAuth(person(["ops_manager"])),
      lang: "ar",
    });
    fireEvent.click(await screen.findByRole("tab", { name: "الإحصاء" }));
    expect((await screen.findAllByText("70%")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("2:05").length).toBeGreaterThan(0);
    expect(cardStats).toHaveBeenCalledWith(30, ["phone", "radio", "in_person", "other"], null, expect.anything());
    fireEvent.click(screen.getByRole("button", { name: "لاسلكي" }));
    await waitFor(() =>
      expect(cardStats).toHaveBeenLastCalledWith(30, ["phone", "in_person", "other"], null, expect.anything()),
    );
    fireEvent.click(await screen.findByRole("button", { name: /إسعاف/ }));
    expect(await screen.findByText(/لا يعرف 40%/)).toBeInTheDocument();
  });

  it("lets the doctor validate a handed-over medical draft or send it back with a note", async () => {
    const validateCardMedical = vi.fn(() => Promise.resolve(draft));
    const returnCard = vi.fn(() => Promise.resolve(draft));
    renderApp(<CallCardsPage />, {
      api: fakeApi({
        callCards: vi.fn(() => Promise.resolve({ cards: SIM_CALL_CARDS })),
        cardReview: vi.fn(() => Promise.resolve(review)),
        cardStats: vi.fn(() => Promise.resolve(stats)),
        validateCardMedical,
        returnCard,
      }),
      auth: fakeAuth(person(["medical_coordinator"])),
      lang: "ar",
    });
    fireEvent.click(await screen.findByRole("tab", { name: "مراجعة البطاقات التجريبية" }));
    const detail = await screen.findByRole("region", { name: medical.content.title });
    expect(within(detail).getByText("هل فقد الوعي ثم استعاده؟")).toBeInTheDocument();
    expect(within(detail).getByText("ملاحظة المكتب: حالات إغماء كثيرة")).toBeInTheDocument();
    await waitFor(() => expect(within(detail).getByText("لا يعرف 40%")).toBeInTheDocument());
    // The doctor does not approve; the Office's own buttons are not offered.
    expect(within(detail).queryByRole("button", { name: "اعتماد" })).toBeNull();
    fireEvent.click(within(detail).getByRole("button", { name: "إرجاع إلى المكتب بملاحظة" }));
    fireEvent.change(within(detail).getByLabelText("السبب"), { target: { value: "راجعوا وضعية الأمان" } });
    fireEvent.click(within(detail).getAllByRole("button", { name: "إرجاع إلى المكتب بملاحظة" })[0] as HTMLElement);
    await waitFor(() => expect(returnCard).toHaveBeenCalledWith("cc-medical-2", "راجعوا وضعية الأمان", draft.updated_at));
  });

  it("lets the Office confirm the [SIM] text unchanged", async () => {
    const confirmCard = vi.fn(() => Promise.resolve(draft));
    renderApp(<CallCardsPage />, {
      api: fakeApi({
        callCards: vi.fn(() => Promise.resolve({ cards: SIM_CALL_CARDS })),
        cardReview: vi.fn(() => Promise.resolve({ ...review, items: [item({})] })),
        confirmCard,
      }),
      auth: fakeAuth(person(["content_editor"])),
      lang: "ar",
    });
    fireEvent.click(await screen.findByRole("tab", { name: "مراجعة البطاقات التجريبية" }));
    fireEvent.click(await screen.findByRole("button", { name: /حريق/ }));
    const detail = await screen.findByRole("region", { name: fire.content.title });
    fireEvent.click(within(detail).getByRole("button", { name: "تأكيد النص دون تغيير" }));
    fireEvent.change(within(detail).getByLabelText("السبب"), { target: { value: "النص مطابق" } });
    fireEvent.click(within(detail).getAllByRole("button", { name: "تأكيد النص دون تغيير" })[0] as HTMLElement);
    await waitFor(() => expect(confirmCard).toHaveBeenCalledWith("fire", "النص مطابق"));
  });
});
