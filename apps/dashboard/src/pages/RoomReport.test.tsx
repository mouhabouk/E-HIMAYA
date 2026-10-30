// covers: phase N (docs/phase-n/design-n.md §5): a room agent enters a report from a call, the radio or a visit.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { canEnterReports } from "../lib/roles";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
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
    fireEvent.change(screen.getByLabelText("النوع"), { target: { value: "fire" } });
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
    });
  });
});
