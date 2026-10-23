// covers: phase B2 (docs/phase-b/design-b2.md): the public live location page.
import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeAuth, renderApp } from "../test/render";
import { LivePage, liveToken } from "./LivePage";

vi.mock("../components/LazyMap", () => ({ MapPanel: () => <div data-testid="map" /> }));

const KEY = "POST /api/v1/live/view";
const TOKEN = "tok_ABCDEFGHIJKLMNOPQRSTUVWX";
const ACTIVE = {
  active: true,
  points: [
    { lat: 34.7398, lon: 10.76, accuracy_m: 30, at: "2026-10-23T09:00:00Z" },
    { lat: 34.74012, lon: 10.76123, accuracy_m: 12.2, at: "2026-10-23T09:05:00Z" },
  ],
  battery: 41,
  updated_at: "2026-10-23T09:05:00Z",
  expires_at: "2026-10-23T17:00:00Z",
  stopped_at: null,
};

describe("LivePage (public, phase B2)", () => {
  it("reads the token from the fragment only", () => {
    expect(liveToken(`#${TOKEN}`)).toBe(TOKEN);
    expect(liveToken("")).toBeNull();
    expect(liveToken("#short")).toBeNull();
    expect(liveToken("#a b<script>")).toBeNull();
  });

  it("shows the last position without signing in, the token in the body", async () => {
    const { calls } = renderApp(<LivePage />, {
      auth: fakeAuth(null),
      path: `/live#${TOKEN}`,
      route: "/live",
      lang: "en",
      routes: { [KEY]: { body: ACTIVE } },
    });
    expect(await screen.findByRole("heading", { name: "Location shared now" })).toBeInTheDocument();
    expect(screen.getByText("Phone battery: 41%")).toBeInTheDocument();
    expect(screen.getByText("34.74012, 10.76123")).toBeInTheDocument();
    expect(screen.getByText("± 13 m")).toBeInTheDocument();
    expect(screen.getByTestId("map")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Call 198" })).toHaveAttribute("href", "tel:198");
    const [call] = calls(KEY);
    expect(call?.body).toEqual({ token: TOKEN });
    expect(call?.url.search).toBe("");
  });

  it("says when the person stopped sharing", async () => {
    renderApp(<LivePage />, {
      path: `/live#${TOKEN}`,
      route: "/live",
      lang: "fr",
      routes: { [KEY]: { body: { ...ACTIVE, active: false, stopped_at: "2026-10-23T10:00:00Z" } } },
    });
    expect(await screen.findByRole("heading", { name: "Le partage est terminé" })).toBeInTheDocument();
    expect(screen.getByText(/La personne a arrêté le partage le/)).toBeInTheDocument();
  });

  it("explains an unknown link and an incomplete one", async () => {
    renderApp(<LivePage />, {
      path: `/live#${TOKEN}`,
      route: "/live",
      lang: "ar",
      routes: { [KEY]: { status: 404, body: { detail: "not_found" } } },
    });
    expect(await screen.findByRole("heading", { name: "الرابط غير موجود" })).toBeInTheDocument();
  });

  it("asks for a complete link when the fragment is missing", () => {
    const { calls } = renderApp(<LivePage />, { path: "/live", route: "/live", lang: "en" });
    expect(screen.getByRole("heading", { name: "Incomplete link" })).toBeInTheDocument();
    expect(calls(KEY)).toHaveLength(0);
  });
});
