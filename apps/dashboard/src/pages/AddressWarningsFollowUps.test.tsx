// covers: OS8-2 and OS8-3 (design-os8.md §9, §10): the review reminder of the register, the owner told of a reveal
// and their objection in the reveals log.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AwCategory, AwMarker } from "../lib/addressWarnings";
import { fakeApi, renderApp } from "../test/render";
import { AddressWarningsPage } from "./AddressWarningsPage";

const dog: AwCategory = {
  key: "dog",
  name: "حيوان خطر",
  icon: "paw",
  colour: "slate",
  personal: false,
  radius_m: 80,
  review_months: 6,
  team: true,
  critical_with: [],
  examples: [],
  updated_by_name: null,
};

const mark = (id: string, extra: Partial<AwMarker> = {}): AwMarker => ({
  id,
  category: "dog",
  gouvernorat_code: 61,
  location: { lat: 34.95, lon: 10.4 },
  address: `نهج ابن خلدون ${id}`,
  description: `كلب حراسة ${id}`,
  source: "report",
  source_ref: null,
  org_id: null,
  incident_id: null,
  team_visible: true,
  hours: null,
  review_on: "2026-09-15",
  review_due: true,
  status: "active",
  created_at: "2026-01-01T08:00:00Z",
  created_by_name: null,
  decided_at: null,
  decided_by_name: null,
  decision_reason: null,
  confirmed_at: null,
  ...extra,
});

function setup() {
  const api = fakeApi({
    awCategories: vi.fn(() => Promise.resolve([dog])),
    awReminders: vi.fn(() =>
      Promise.resolve({
        late: [
          { marker: mark("a"), days: 59, level: "central" as const },
          { marker: mark("b"), days: 2, level: "room" as const },
        ],
        soon: [{ marker: mark("c", { review_due: false, review_on: "2026-12-01" }), days: -18, level: "soon" as const }],
        disputes: 1,
        settings: { hour: 8, ahead_days: 30, manager_days: 7, central_days: 30 },
      }),
    ),
    awDecide: vi.fn((id: string) => Promise.resolve(mark(id, { review_due: false }))),
    awRequestCheck: vi.fn((id: string) => Promise.resolve(mark(id))),
    awReveals: vi.fn(() =>
      Promise.resolve([
        {
          id: 7,
          at: "2026-11-13T07:41:00Z",
          by_name: "رئيس القاعة",
          category: "dog",
          address: "نهج",
          incident_id: null,
          reason: "للاتصال",
          notified_via: "push" as const,
          disputed_at: "2026-11-13T08:00:00Z",
          dispute_note: "لا أحد اتصل بي",
        },
      ]),
    ),
  });
  return { ...renderApp(<AddressWarningsPage />, { api, path: "/address-warnings?tab=reminders" }), api };
}

describe("AddressWarningsPage follow-ups", () => {
  it("lists the marks past or near their review date with their level", async () => {
    const { api } = setup();
    expect(await screen.findByText("تجاوزت تاريخ المراجعة (2)")).toBeInTheDocument();
    expect(screen.getByText("متأخرة 59 يوما")).toBeInTheDocument();
    expect(screen.getByText("رُفع إلى القاعة المركزية")).toBeInTheDocument();
    expect(screen.getByText("تحلّ بعد 18 يوما")).toBeInTheDocument();
    expect(screen.getByText("اعتراضات أصحاب العلامات الشخصية: 1")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "اطلب تحققا من فريق" })[1] as HTMLElement);
    await waitFor(() => expect(api.awRequestCheck).toHaveBeenCalledWith("b"));
    fireEvent.click(screen.getAllByRole("button", { name: "أكّد (6 شهرا)" })[0] as HTMLElement);
    await waitFor(() => expect(api.awDecide).toHaveBeenCalledWith("a", "confirm", undefined));
  });

  it("shows how the owner was told and their objection", async () => {
    setup();
    fireEvent.click(await screen.findByRole("button", { name: "سجل الاطلاع على المعطيات الشخصية" }));
    expect(await screen.findByText("أُشعر في التطبيق")).toBeInTheDocument();
    expect(screen.getByText(/اعترض صاحبها/)).toBeInTheDocument();
    expect(screen.getByText("لا أحد اتصل بي")).toBeInTheDocument();
  });
});
