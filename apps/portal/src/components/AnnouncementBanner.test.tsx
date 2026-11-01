import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/render";
import { AnnouncementBanner } from "./AnnouncementBanner";

const ROUTE = "GET /api/v1/app/features";

describe("AnnouncementBanner (phase 5)", () => {
  it("shows the administrator's message in the reader's language", async () => {
    renderApp(<AnnouncementBanner />, {
      lang: "fr",
      routes: { [ROUTE]: { body: { hidden: [], announcement: { tone: "warn", ar: "صيانة", fr: "Maintenance ce soir", en: "" } } } },
    });
    const banner = await screen.findByRole("status");
    expect(banner).toHaveTextContent("Maintenance ce soir");
    expect(banner).toHaveClass("alert--warn");
  });

  it("falls back to Arabic, and shows nothing without a message", async () => {
    renderApp(<AnnouncementBanner />, {
      lang: "en",
      routes: { [ROUTE]: { body: { hidden: [], announcement: { tone: "info", ar: "صيانة الليلة", fr: "", en: "" } } } },
    });
    expect(await screen.findByRole("status")).toHaveTextContent("صيانة الليلة");
  });

  it("shows nothing when there is no message", async () => {
    const { calls } = renderApp(<AnnouncementBanner />, { routes: { [ROUTE]: { body: { hidden: [], announcement: null } } } });
    await waitFor(() => expect(calls(ROUTE)).toHaveLength(1));
    expect(screen.queryByRole("status")).toBeNull();
  });
});
