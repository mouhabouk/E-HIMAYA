import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApi, renderApp } from "../test/render";
import { KPIS } from "../test/fixtures";
import { HomePage, summarize } from "./HomePage";

describe("HomePage (KPIs)", () => {
  it("summarises status counts", () => {
    expect(summarize(KPIS)).toEqual({ total: 12, received: 3, inProgress: 6, closed: 2 });
  });

  it("renders indicators and breakdowns in Arabic with Western digits", async () => {
    const api = fakeApi({ kpis: vi.fn(() => Promise.resolve(KPIS)) });
    renderApp(<HomePage />, { api });

    expect(await screen.findByText("مجموع البلاغات")).toBeInTheDocument();
    const total = screen.getByText("مجموع البلاغات").closest(".kpi");
    expect(total && within(total as HTMLElement).getByText("12")).toBeInTheDocument();
    // 312.5 s → 5 min 13 s, with Latin digits.
    expect(screen.getByText(/5.*13/)).toBeInTheDocument();

    const byStatus = screen.getByRole("table", { name: "التوزيع حسب الحالة" });
    expect(within(byStatus).getByText("قيد المعالجة")).toBeInTheDocument();
    const byGouv = screen.getByRole("table", { name: "التوزيع حسب الولاية" });
    expect(await within(byGouv).findByText("صفاقس")).toBeInTheDocument();
    expect(within(byGouv).getByText("7")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/[٠-٩]/);

    expect(api.kpis).toHaveBeenCalledWith(expect.stringMatching(/^\d{4}-\d{2}-\d{2}T/), expect.anything());
  });

  it("refetches with a new `since` when the period changes", async () => {
    const api = fakeApi({ kpis: vi.fn(() => Promise.resolve(KPIS)) });
    renderApp(<HomePage />, { api, lang: "fr" });
    await screen.findByText("Total des signalements");
    screen.getByLabelText("7 jours").click();
    await vi.waitFor(() => expect(api.kpis).toHaveBeenCalledTimes(2));
    const sinces = vi.mocked(api.kpis).mock.calls.map((c) => Date.parse(c[0]));
    const days = ((sinces[0] ?? 0) - (sinces[1] ?? 0)) / 86_400_000;
    expect(Math.round(days)).toBe(6);
  });

  it("shows a translated error, never the raw code", async () => {
    const { ApiError } = await import("../lib/api");
    const api = fakeApi({ kpis: vi.fn(() => Promise.reject(new ApiError(429, "rate_limited"))) });
    renderApp(<HomePage />, { api, lang: "fr" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Trop de requêtes");
    expect(screen.queryByText("rate_limited")).not.toBeInTheDocument();
  });
});
