// covers: phase P5b (docs/phase-p5/design-simple.md §2.2): ratings of the mobile app in the national settings, for the
// system administrator and the content editor only.
import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { canReadAppFeedback, starShares, type AppFeedbackSummary } from "../lib/appFeedback";
import { SettingsPage } from "../pages/SettingsPage";
import { makeSettings } from "../test/phase9Fixtures";
import { fakeApi, fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";

const SUMMARY: AppFeedbackSummary = {
  days: 90,
  count: 3,
  average: 3.67,
  by_stars: { "1": 0, "2": 1, "3": 0, "4": 1, "5": 1 },
  by_build: [
    { build: 16, version: "0.17.0", count: 2, average: 4.5 },
    { build: 15, version: "0.16.0", count: 1, average: 2 },
  ],
  remarks: [
    { stars: 2, remark: "Lente à ouvrir la carte", platform: "android", version: "0.16.0", locale: "fr", created_at: "2026-10-26T09:00:00Z" },
  ],
};

function claims(role: string) {
  return { ...OPERATOR_CLAIMS, realm_access: { roles: [role] }, scope_level: "national" };
}

function setup(role: string) {
  const appFeedback = vi.fn((days: number) => Promise.resolve({ ...SUMMARY, days }));
  const api = fakeApi({ platformSettings: vi.fn(() => Promise.resolve(makeSettings(true))), appFeedback });
  renderApp(<SettingsPage />, { api, auth: fakeAuth(claims(role)), lang: "fr" });
  return appFeedback;
}

describe("app rating", () => {
  it("shows the average, the stars, the builds and the remarks", async () => {
    const appFeedback = setup("sysadmin");
    const card = await screen.findByTestId("app-feedback");
    const scope = within(card);
    expect(await scope.findByText("Lente à ouvrir la carte")).toBeTruthy();
    expect(scope.getByText(/3,67\s*\/\s*5/)).toBeTruthy();
    expect(scope.getByText("5 ★ (33%)")).toBeTruthy();
    expect(scope.getByText("0.17.0")).toBeTruthy();
    expect(appFeedback).toHaveBeenCalledWith(90, expect.anything());

    fireEvent.change(scope.getByLabelText("Période"), { target: { value: "30" } });
    await vi.waitFor(() => expect(appFeedback).toHaveBeenCalledWith(30, expect.anything()));
  });

  it("is shown to the content editor", async () => {
    setup("content_editor");
    expect(await screen.findByTestId("app-feedback")).toBeTruthy();
  });

  it("is not shown without the role", async () => {
    const appFeedback = setup("security_admin");
    await screen.findAllByRole("heading");
    expect(screen.queryByTestId("app-feedback")).toBeNull();
    expect(appFeedback).not.toHaveBeenCalled();
  });

  it("computes the share of each star", () => {
    expect(starShares(SUMMARY)).toEqual({ 1: 0, 2: 33, 3: 0, 4: 33, 5: 33 });
    expect(starShares({ count: 0, by_stars: {} })).toEqual({ 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 });
    expect(canReadAppFeedback(["operator"])).toBe(false);
    expect(canReadAppFeedback(["sysadmin"])).toBe(true);
  });
});
