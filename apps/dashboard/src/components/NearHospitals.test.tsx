// covers: phase L1b (design-layers.md §4): the nearest hospitals of an incident on the road, and the one added.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { NearHospital } from "../lib/opsTypes";
import { makeIncidentDetail } from "../test/fixtures";
import { fakeOpsApi } from "../test/opsFixtures";
import { AUDITOR_CLAIMS, fakeApi, fakeAuth, renderApp } from "../test/render";
import { NearHospitals } from "./NearHospitals";

const hospital = (id: string, name: string, extra: Partial<NearHospital> = {}): NearHospital => ({
  id,
  name,
  phone: "+21671578000",
  layer: "hopitaux",
  lat: 36.8,
  lon: 10.18,
  distance_m: 2_000,
  road_m: 3_400,
  road_s: 540,
  engine: "valhalla",
  simulated: false,
  ...extra,
});

describe("NearHospitals", () => {
  it("lists the hospitals by road time and adds one to the incident", async () => {
    const ops = fakeOpsApi();
    ops.incidentHospitals = vi.fn(() =>
      Promise.resolve([hospital("h1", "Charles Nicolle"), hospital("h2", "La Rabta", { road_m: 6_000, road_s: 900, engine: "fallback" })]),
    );
    ops.chooseHospital = vi.fn((_: string, id: string) => Promise.resolve(hospital(id, "Charles Nicolle")));
    const incident = makeIncidentDetail();
    renderApp(<NearHospitals incident={incident} />, { lang: "fr", api: fakeApi(ops) });
    expect(await screen.findByText("Charles Nicolle")).toBeInTheDocument();
    expect(screen.getByText("3,4 km, environ 9 min")).toBeInTheDocument();
    expect(screen.getByText(/6 km, environ 15 min · estimation sans moteur d'itinéraire/)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Ajouter à l'incident" })[0] as HTMLElement);
    await waitFor(() => expect(ops.chooseHospital).toHaveBeenCalledWith(incident.id, "h1"));
    expect(await screen.findByText("Ajouté")).toBeInTheDocument();
  });

  it("offers no button to a reader", async () => {
    const ops = fakeOpsApi();
    ops.incidentHospitals = vi.fn(() => Promise.resolve([hospital("h1", "Charles Nicolle")]));
    renderApp(<NearHospitals incident={makeIncidentDetail()} />, {
      lang: "fr",
      api: fakeApi(ops),
      auth: fakeAuth(AUDITOR_CLAIMS),
    });
    expect(await screen.findByText("Charles Nicolle")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ajouter à l'incident" })).not.toBeInTheDocument();
  });
});
