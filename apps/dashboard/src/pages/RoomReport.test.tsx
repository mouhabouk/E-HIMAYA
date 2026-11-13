// covers: phase N (docs/phase-n/design-n.md §5): a room agent enters a report from a call, the radio or a visit;
// OS2 (docs/phase-os2/design-os2.md §2): the guided call-taking card in the same form.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { canEnterReports } from "../lib/roles";
import { SIM_CALL_CARDS } from "../test/callCardsData";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { intakeLinkFor } from "../components/Softphone";
import type { SoftphoneCall } from "../lib/softphone";
import { parsePoint, RoomReportPage } from "./RoomReportPage";

vi.mock("../components/LazyMap", () => ({
  LazyMapView: (props: { ariaLabel: string; onMapClick?: (lon: number, lat: number) => void; markers: unknown[] }) => (
    <button type="button" aria-label={props.ariaLabel} data-markers={props.markers.length} onClick={() => props.onMapClick?.(10.7357, 36.4513)} />
  ),
}));

const agent = { sub: "u-op", name: "عون القاعة", realm_access: { roles: ["operator"] }, gouvernorat_code: "21" };

describe("RoomReportPage", () => {
  it("is for the rooms and reads typed coordinates inside Tunisia", () => {
    expect(canEnterReports(["operator"])).toBe(true);
    expect(canEnterReports(["local_committee"])).toBe(false);
    expect(parsePoint("36,45", "10.73")).toEqual({ lat: 36.45, lon: 10.73 });
    expect(parsePoint("48.85", "2.35")).toBeNull();
    expect(parsePoint("", "10")).toBeNull();
  });

  it("records a report that came by radio at the point clicked on the map", async () => {
    const enterReport = vi.fn(() => Promise.resolve({ id: "rep-1" }));
    renderApp(<RoomReportPage />, { api: fakeApi({ enterReport } as never), auth: fakeAuth(agent), lang: "ar" });
    fireEvent.click(screen.getByRole("button", { name: "تسجيل البلاغ" }));
    expect(await screen.findByText("حدّد المكان داخل التراب التونسي.")).toBeInTheDocument();
    expect(enterReport).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("radio", { name: "لاسلكي" }));
    fireEvent.click(screen.getByRole("radio", { name: "حريق" }));
    fireEvent.change(screen.getByLabelText("ما قاله المبلّغ"), { target: { value: "دخان كثيف قرب السوق" } });
    fireEvent.click(await screen.findByRole("button", { name: "خريطة لتحديد مكان البلاغ" }));
    expect(screen.getByLabelText("خط العرض")).toHaveValue("36.45130");
    fireEvent.click(screen.getByRole("button", { name: "تسجيل البلاغ" }));
    await waitFor(() => expect(enterReport).toHaveBeenCalled());
    expect(enterReport).toHaveBeenCalledWith({
      category: "fire",
      channel: "radio",
      location: { lat: 36.4513, lon: 10.7357 },
      text: "دخان كثيف قرب السوق",
      received_at: undefined,
      // When the agent opened the form (OS2-3: the time of a radio entry).
      // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment -- an asymmetric matcher
      started_at: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T/),
    });
  });
});

describe("RoomReportPage opened from a softphone call", () => {
  it("links the call to the report and takes the answer as the time received", async () => {
    const answered = Date.parse("2026-11-10T21:05:00Z");
    const href = intakeLinkFor({ apiCallId: "call-7", answeredAt: answered } as SoftphoneCall);
    expect(href).toBe("/reports/new?call=call-7&at=2026-11-10T21%3A05%3A00.000Z");
    const enterReport = vi.fn(() => Promise.resolve({ id: "rep-9" }));
    renderApp(<RoomReportPage />, { api: fakeApi({ enterReport } as never), auth: fakeAuth(agent), lang: "ar", path: href });
    expect(screen.getByRole("status")).toHaveTextContent("تُربط المكالمة بالبلاغ عند الحفظ");
    expect(screen.getByRole("radio", { name: "هاتف" })).toBeChecked();
    fireEvent.click(await screen.findByRole("button", { name: "خريطة لتحديد مكان البلاغ" }));
    fireEvent.click(screen.getByRole("button", { name: "تسجيل البلاغ" }));
    await waitFor(() => expect(enterReport).toHaveBeenCalled());
    expect(enterReport).toHaveBeenCalledWith(
      expect.objectContaining({ channel: "phone", call_id: "call-7", received_at: "2026-11-10T21:05:00.000Z" }),
    );
  });
});

describe("RoomReportPage with the guided call-taking card (OS2)", () => {
  it("asks the card's questions, reads CPR to the caller and sends the answers with the report", async () => {
    const enterReport = vi.fn(() => Promise.resolve({ id: "rep-2" }));
    const callCards = vi.fn(() => Promise.resolve({ cards: SIM_CALL_CARDS }));
    renderApp(<RoomReportPage />, {
      api: fakeApi({ enterReport, callCards } as never),
      auth: fakeAuth(agent),
      lang: "ar",
    });
    fireEvent.click(screen.getByRole("radio", { name: "إسعاف" }));
    const conscious = await screen.findByRole("group", { name: /هل المريض فاقد للوعي/ });
    fireEvent.click(within(conscious).getByRole("radio", { name: "نعم" }));
    const breathing = await screen.findByRole("group", { name: /هل يتنفس تنفسا طبيعيا/ });
    fireEvent.click(within(breathing).getByRole("radio", { name: "لا" }));
    expect(screen.getByText("المستوى: حرج")).toBeInTheDocument();
    expect(screen.getByText(/110 ضغطة في الدقيقة/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "قُرئت على المتصل" }));

    fireEvent.click(await screen.findByRole("button", { name: "خريطة لتحديد مكان البلاغ" }));
    fireEvent.click(screen.getByRole("button", { name: "تسجيل البلاغ" }));
    await waitFor(() => expect(enterReport).toHaveBeenCalled());
    expect(enterReport).toHaveBeenCalledWith(
      expect.objectContaining({
        category: "medical",
        call_card: { card_id: "cc-medical", version: 1, answers: { conscious: "yes", breathing: "no" }, read: ["cpr"] },
      }),
    );
  });

  it("lets the agent enter the report with the free text only", async () => {
    const enterReport = vi.fn(() => Promise.resolve({ id: "rep-3" }));
    const callCards = vi.fn(() => Promise.resolve({ cards: SIM_CALL_CARDS }));
    renderApp(<RoomReportPage />, {
      api: fakeApi({ enterReport, callCards } as never),
      auth: fakeAuth(agent),
      lang: "ar",
    });
    fireEvent.click(screen.getByRole("radio", { name: "حريق" }));
    fireEvent.click(await screen.findByRole("checkbox", { name: "إدخال بلا بطاقة (النص الحر فقط)" }));
    expect(screen.queryByRole("group", { name: /هل/ })).toBeNull();
    fireEvent.click(await screen.findByRole("button", { name: "خريطة لتحديد مكان البلاغ" }));
    fireEvent.click(screen.getByRole("button", { name: "تسجيل البلاغ" }));
    await waitFor(() => expect(enterReport).toHaveBeenCalled());
    expect(enterReport).toHaveBeenCalledWith(expect.objectContaining({ category: "fire", call_card: undefined }));
  });
});
