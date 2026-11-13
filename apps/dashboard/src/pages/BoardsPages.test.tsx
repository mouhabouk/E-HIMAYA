// covers: the four boards of the menu of 20 systems (Yamen 2026-11-13) and the resources tabs.
import { screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { ResourcesTabs } from "../components/ResourcesTabs";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { AdminBoardPage, CitizensPage, ForecastPage, VisionPage } from "./BoardsPages";

describe("boards", () => {
  it("shows the detections with their estimated danger", async () => {
    const api = fakeApi({
      visionOverview: vi.fn(() =>
        Promise.resolve({
          hours: 24,
          counts: { fire: 2, smoke: 1, person: 0 },
          confirmed: 1,
          danger: { high: 1, medium: 1, low: 1 },
          watching: 3,
          alert_confidence: 0.6,
          items: [
            {
              at: "2026-11-13T01:00:00Z",
              label: "fire",
              confidence: 0.91,
              confirmed: true,
              danger: "high" as const,
              origin: "drone",
              stream_id: "s1",
              stream_label: "Drone 4",
              report_id: "r1",
              gouvernorat_code: 61,
              model: "yolo",
            },
          ],
        }),
      ),
    });
    renderApp(<VisionPage />, { lang: "en", api });
    expect(await screen.findByRole("heading", { name: "Image and video analysis centre" })).toBeInTheDocument();
    const kpis = await screen.findByLabelText("Detection figures");
    expect(within(kpis).getByText("Streams under watch").nextSibling).toHaveTextContent("3");
    const table = screen.getByRole("table", { name: "Latest detections" });
    expect(within(table).getByText("High danger")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "Open" })).toHaveAttribute("href", "/reports/r1");
  });

  it("marks a simulated forecast with the [SIM] band", async () => {
    const api = fakeApi({
      forecastOverview: vi.fn(() =>
        Promise.resolve({
          hours: 48,
          from: "2026-11-13T00:00:00Z",
          simulated: true,
          gouvernorats: [
            {
              gouvernorat_code: 61,
              fwi: 42.3,
              fire_danger: "very_high",
              fire_at: "2026-11-13T13:00:00Z",
              rain: "watch",
              rain_24h_mm: 12,
              gust_kmh: 70,
            },
          ],
          runs: [],
        }),
      ),
    });
    renderApp(<ForecastPage />, { lang: "en", api });
    expect(await screen.findByRole("note")).toHaveTextContent("Simulated weather data");
    expect(screen.getByRole("table", { name: "Forecast per gouvernorat" })).toHaveTextContent("42.3");
    expect(screen.getByText("No forecast run yet.")).toBeInTheDocument();
  });

  it("sums the citizens per gouvernorat without any identity", async () => {
    const api = fakeApi({
      citizensOverview: vi.fn(() =>
        Promise.resolve({
          days: 90,
          national: {},
          gouvernorats: [
            { gouvernorat_code: 61, reporters: 4, reports: 9, rejected: 2, kept: 5, volunteers: 1 },
            { gouvernorat_code: 11, reporters: 1, reports: 1, rejected: 0, kept: 1, volunteers: 3 },
          ],
        }),
      ),
    });
    renderApp(<CitizensPage />, { lang: "en", api });
    const kpis = await screen.findByLabelText("Citizen figures");
    expect(within(kpis).getByText("Reports").nextSibling).toHaveTextContent("10");
    expect(within(kpis).getByText("Approved volunteers").nextSibling).toHaveTextContent("4");
    // A regional caller gets no national figures.
    expect(within(kpis).queryByText("Citizen accounts")).not.toBeInTheDocument();
  });

  it("shows the services, the subsystem rules and the latest changes to the administrator", async () => {
    const api = fakeApi({
      adminBoardOverview: vi.fn(() =>
        Promise.resolve({
          services: {
            database: "ok" as const,
            ai: "not_configured" as const,
            vision: "unreachable" as const,
            telephony: "ok" as const,
            notifications: "simulated" as const,
          },
          accounts_week: { citizen: 3, staff: 1 },
          rules: { grants: 2, hidden: 1, assignments: 1 },
          systems: [
            {
              key: "partners",
              number: 11,
              effect: "suspend",
              target_kind: "everyone",
              target: null,
              message: { ar: "صيانة", fr: "Maintenance", en: "Maintenance" },
              ends_at: null,
            },
          ],
          recent: [{ at: "2026-11-13T01:00:00Z", action: "features.rule.create", target: "system.partners", reason: "maintenance" }],
        }),
      ),
    });
    renderApp(<AdminBoardPage />, { lang: "en", api });
    const services = await screen.findByLabelText("Services");
    expect(within(services).getByText("Image analysis").nextSibling).toHaveTextContent("Unreachable");
    expect(screen.getByText(/11\. partners · Everyone · «Maintenance»/)).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Latest changes" })).toHaveTextContent("features.rule.create");
  });
});

describe("ResourcesTabs", () => {
  const tabs = (
    <Routes>
      <Route path="/resources" element={<ResourcesTabs tab="resources"><p>units</p></ResourcesTabs>} />
      <Route path="/inventory" element={<ResourcesTabs tab="inventory"><p>register</p></ResourcesTabs>} />
    </Routes>
  );

  it("joins the resources and their register in one page with two tabs", async () => {
    renderApp(tabs, { lang: "en", path: "/resources" });
    const nav = await screen.findByRole("navigation", { name: "Resources" });
    expect(within(nav).getByRole("link", { name: "Units and resources" })).toHaveClass("tabs__tab--active");
    expect(within(nav).getByRole("link", { name: "Inventory" })).toHaveAttribute("href", "/inventory");
    expect(screen.getByText("units")).toBeInTheDocument();
  });

  it("opens the register for a governor, who sees the counts only", async () => {
    const auth = fakeAuth({ sub: "g", name: "Gov", realm_access: { roles: ["governor"] }, gouvernorat_code: "61" });
    renderApp(tabs, { lang: "en", path: "/resources", auth });
    expect(await screen.findByText("register")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Resources" })).not.toBeInTheDocument();
  });
});
