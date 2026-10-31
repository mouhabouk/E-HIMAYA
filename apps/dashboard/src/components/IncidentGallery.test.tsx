// covers: review point 21 (phase D, docs/phase-d/design-d.md §6)
import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { IncidentGallery } from "../lib/phase7Api";
import { fakeApi, renderApp } from "../test/render";
import { IncidentGallerySection } from "./IncidentGallery";

const GALLERY: IncidentGallery = {
  counts: { photo: 2, voice: 1, stream: 1 },
  live_streams: 1,
  items: [
    {
      id: "m-1",
      kind: "photo",
      origin: "citizen",
      at: "2026-10-31T08:00:00Z",
      url: "https://s3.test/m-1.jpg",
      content_type: "image/jpeg",
      duration_s: null,
      label: "EH-26-11-0000001",
      report_id: "r-1",
      stream_id: null,
      transcript: null,
      live: false,
      simulated: false,
    },
    {
      id: "a-1",
      kind: "photo",
      origin: "team",
      at: "2026-10-31T08:05:00Z",
      url: "https://s3.test/a-1.jpg",
      content_type: "image/jpeg",
      duration_s: null,
      label: "Sami",
      report_id: null,
      stream_id: null,
      transcript: null,
      live: false,
      simulated: false,
    },
    {
      id: "a-2",
      kind: "voice",
      origin: "team",
      at: "2026-10-31T08:06:00Z",
      url: "https://s3.test/a-2.m4a",
      content_type: "audio/mp4",
      duration_s: 8,
      label: "Sami",
      report_id: null,
      stream_id: null,
      transcript: "السقف آيل للسقوط",
      live: false,
      simulated: false,
    },
    {
      id: "s-1",
      kind: "stream",
      origin: "team",
      at: "2026-10-31T08:07:00Z",
      url: null,
      content_type: null,
      duration_s: null,
      label: null,
      report_id: null,
      stream_id: "s-1",
      transcript: null,
      live: true,
      simulated: false,
    },
  ],
};

describe("the incident's media gallery", () => {
  it("one summary line, then every medium in time order", async () => {
    const api = fakeApi({
      incidentMedia: vi.fn(() => Promise.resolve(GALLERY)),
    });
    renderApp(<IncidentGallerySection incidentId="i-1" />, { api, lang: "en" });
    expect(await screen.findByTestId("gallery-summary")).toHaveTextContent(
      "Photos: 2 · Voice notes: 1 · Streams: 1 · Live now: 1",
    );
    expect(api.incidentMedia).toHaveBeenCalledWith("i-1", expect.anything());
    expect(
      screen.getAllByRole("img", { name: "Photo of the scene" }),
    ).toHaveLength(2);
    const voice = screen.getByTestId("gallery-a-2");
    expect(within(voice).getByText("السقف آيل للسقوط")).toBeInTheDocument();
    const stream = screen.getByTestId("gallery-s-1");
    expect(
      within(stream).getByRole("link", { name: /Open the stream/ }),
    ).toHaveAttribute("href", "/streams/s-1");
    expect(within(stream).getByText("Live")).toBeInTheDocument();
  });

  it("nothing yet", async () => {
    renderApp(<IncidentGallerySection incidentId="i-1" />, { lang: "en" });
    expect(await screen.findByTestId("gallery-summary")).toHaveTextContent(
      "No media yet.",
    );
  });
});
