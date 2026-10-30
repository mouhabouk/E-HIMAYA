// covers: FR-M-10 — docs/phase-m/design-m.md §7: a room saves a place by clicking the map, with a kind and a note, and
// finds it in the list with the kind in words.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SavedPlace } from "../lib/places";
import { fakeApi, renderApp } from "../test/render";
import { useSavedPlaces } from "./SavedPlaces";

const DEPOT: SavedPlace = {
  id: "p-1",
  name: "مستودع المحروقات",
  kind: "critical",
  note: "المدخل من طريق قابس",
  lat: 34.74,
  lon: 10.76,
  gouvernorat_code: 61,
  delegation_id: 6114,
  created_by_name: "Salma",
  created_at: "2026-10-30T08:00:00Z",
  updated_by_name: "Salma",
  updated_at: "2026-10-30T08:00:00Z",
};

function Harness() {
  const places = useSavedPlaces();
  return (
    <>
      {places.controls}
      <button type="button" onClick={() => places.onMapClick(10.77, 34.75)}>
        map-click
      </button>
      <p>{places.pois.map((p) => `${p.title}:${p.subtitle ?? ""}`).join("|")}</p>
      {places.popup?.node}
    </>
  );
}

describe("saved places", () => {
  it("lists the places, then saves a new one where the map is clicked", async () => {
    const api = fakeApi({ places: vi.fn(() => Promise.resolve([DEPOT])) });
    renderApp(<Harness />, { api, lang: "ar" });
    expect(await screen.findByText("المدخل من طريق قابس")).toBeInTheDocument();
    expect(screen.getByText("مستودع المحروقات:حرج")).toBeInTheDocument();

    // A map click does nothing until "save a place" is on.
    fireEvent.click(screen.getByRole("button", { name: "map-click" }));
    expect(screen.queryByText("مكان جديد")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "تسجيل مكان" }));
    expect(screen.getByText("انقر على الخريطة في المكان المراد تسجيله.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "map-click" }));
    fireEvent.change(await screen.findByLabelText("الاسم"), { target: { value: "مدرسة" } });
    const important = screen.getAllByLabelText("هام");
    fireEvent.click(important[important.length - 1] as HTMLElement);
    fireEvent.change(screen.getByLabelText("معلومات إضافية"), { target: { value: "مركز إيواء" } });
    fireEvent.click(screen.getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(api.createPlace).toHaveBeenCalled());
    expect(vi.mocked(api.createPlace).mock.calls[0]?.[0]).toEqual({
      name: "مدرسة",
      kind: "important",
      note: "مركز إيواء",
      lon: 10.77,
      lat: 34.75,
    });
  });
});
