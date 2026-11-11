// covers: OS2 (docs/phase-os2/design-os2.md §4): the room agent's guide shows the report's eight stages, the
// statuses and the claim deadlines of the national settings.
import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { canReadRoomGuide } from "../lib/roles";
import { makeSettings } from "../test/phase9Fixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { RoomGuidePage } from "./RoomGuidePage";

const agent = { sub: "u-op", name: "عون القاعة", realm_access: { roles: ["operator"] }, gouvernorat_code: "21" };

describe("RoomGuidePage", () => {
  it("is for the rooms and the Office", () => {
    expect(canReadRoomGuide(["operator"])).toBe(true);
    expect(canReadRoomGuide(["content_editor"])).toBe(true);
    expect(canReadRoomGuide(["governor"])).toBe(false);
  });

  it("walks the report's life and reads the deadlines from the national settings", async () => {
    const settings = makeSettings(false).map((s) =>
      s.key === "sla.claim_delay_s" ? { ...s, value: { critical: 45, high: 90, normal: 120, low: 180 } } : s,
    );
    renderApp(<RoomGuidePage />, {
      api: fakeApi({ platformSettings: vi.fn(() => Promise.resolve(settings)) }),
      auth: fakeAuth(agent),
      lang: "ar",
    });
    expect(screen.getByRole("heading", { level: 1, name: "دليل إجراءات عون القاعة" })).toBeInTheDocument();
    const stages = screen.getAllByRole("listitem").filter((li) => li.classList.contains("room-guide__stage"));
    expect(stages).toHaveLength(8);
    expect(within(stages[0] as HTMLElement).getByRole("heading", { name: /الاستقبال/ })).toBeInTheDocument();
    expect(await screen.findByText("القيم من الإعدادات الوطنية الحالية.")).toBeInTheDocument();
    expect(screen.getByText("45 ثانية")).toBeInTheDocument();
    expect(screen.getByText("85 فما فوق")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "إدخال بلاغ جديد" })).toHaveAttribute("href", "/reports/new");
  });
});
