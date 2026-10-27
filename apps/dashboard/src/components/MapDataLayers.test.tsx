// covers: phase B1 (docs/phase-b/design.md §2.4): several data layers on the live map at once.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { LayerFeature, MapLayer } from "../lib/layers";
import { fakeApi, fakeAuth, fakeLayersApi, FEATURE_L1A, LAYER_L1A, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { useMapDataLayers, zoomOf } from "./MapDataLayers";

function Harness() {
  const { controls, pois, shapes } = useMapDataLayers([10, 36, 11, 37]);
  return (
    <>
      {controls}
      <ul aria-label="points">
        {pois.map((p) => (
          <li key={p.id}>{`${p.title} | ${(p.details ?? []).join(" ; ")} | ${p.colour ?? ""}`}</li>
        ))}
      </ul>
      <ul aria-label="shapes">
        {shapes.features.map((f) => (
          <li key={String(f.id)}>{`${String(f.properties?.name)} ${String(f.properties?.colour)} ${f.geometry.type}`}</li>
        ))}
      </ul>
    </>
  );
}

const layer = (key: string, fr: string, colour: string): MapLayer =>
  ({
    id: key,
    key,
    name: { ar: fr, fr, en: fr },
    icon: "hospital",
    colour,
    audience: "public",
    source: "",
    licence: "",
    to_verify: false,
    simulated: true,
    staff_only: ["manager"],
    editors_allowed: false,
    enabled: true,
    version: 1,
    data_version: 1,
    feature_count: 1,
    hidden_count: 0,
    updated_by_name: null,
    updated_at: "2026-10-23T09:00:00Z",
    last_import: null,
    can_manage: false,
    can_import: false,
    ...LAYER_L1A,
    audiences: [...LAYER_L1A.audiences],
    scope: [],
    fields: { manager: [...LAYER_L1A.fields.manager] },
    default_on: false,
  });

const feature = (name: string, props: Record<string, string> = {}): LayerFeature => ({
  id: name,
  ref: name,
  name,
  kind: null,
  phone: "+21671578000",
  lat: 36.8,
  lon: 10.18,
  gouvernorat_code: 11,
  delegation_id: null,
  props,
  hidden: false,
  version: 1,
  updated_at: "2026-10-23T09:00:00Z",
  ...FEATURE_L1A,
});

describe("useMapDataLayers", () => {
  it("shows any number of layers at once, each in its colour", async () => {
    sessionStorage.clear();
    const layerFeatures = vi.fn((key: string) =>
      Promise.resolve({
        items: key === "hopitaux" ? [feature("Charles Nicolle", { manager: "Dr C", hours: "24/7" })] : [feature("Abri 1")],
        truncated: false,
      }),
    );
    const api = fakeApi({
      ...fakeLayersApi(),
      layers: vi.fn(() =>
        Promise.resolve({
          items: [layer("hopitaux", "Hôpitaux", "#C62828"), layer("abris", "Abris", "#2E7D32")],
          deleted: [],
          can_manage: false,
          icons: [],
          palette: [],
          limits: { file_bytes: 1, rows: 1 },
        }),
      ),
      layerFeatures,
    });
    renderApp(<Harness />, { api, auth: fakeAuth(OPERATOR_CLAIMS), lang: "fr" });
    fireEvent.click(await screen.findByRole("checkbox", { name: /Hôpitaux/ }));
    // Approximate trial places carry the [SIM] mark in the switcher.
    expect(screen.getAllByTitle("Lieux approximatifs inventés (simulation)")).toHaveLength(2);
    fireEvent.click(screen.getByRole("checkbox", { name: /Abris/ }));
    await waitFor(() => expect(within(screen.getByRole("list", { name: "points" })).getAllByRole("listitem")).toHaveLength(2));
    expect(screen.getByText(/Charles Nicolle \| Téléphone: \+216 71 578 000 ; Responsable: Dr C ; Horaires: 24\/7 \| #C62828/)).toBeInTheDocument();
    expect(screen.getByText(/Abri 1 .* #2E7D32/)).toBeInTheDocument();
    expect(JSON.parse(sessionStorage.getItem("ehimaya.mapDataLayers") ?? "[]")).toEqual(["hopitaux", "abris"]);
    fireEvent.click(screen.getByRole("checkbox", { name: /Hôpitaux/ }));
    await waitFor(() => expect(within(screen.getByRole("list", { name: "points" })).getAllByRole("listitem")).toHaveLength(1));
  });

  it("turns on the layers shown by default and draws their lines and areas", async () => {
    sessionStorage.clear();
    const layerShapes = vi.fn(() =>
      Promise.resolve({
        type: "FeatureCollection" as const,
        features: [
          {
            type: "Feature" as const,
            id: "r1",
            geometry: { type: "LineString" as const, coordinates: [[10.1, 36.8], [10.2, 36.9]] },
            properties: { id: "r1", name: "Oued Medjerda", kind: "river" },
          },
        ],
        truncated: false,
      }),
    );
    const api = fakeApi({
      ...fakeLayersApi(),
      layers: vi.fn(() =>
        Promise.resolve({
          items: [
            { ...layer("oueds", "Oueds", "#1976D2"), default_on: true, geometry: "line" as const },
            layer("abris", "Abris", "#2E7D32"),
          ],
          deleted: [],
          can_manage: false,
          icons: [],
          palette: [],
          limits: { file_bytes: 1, rows: 1 },
        }),
      ),
      layerShapes,
    });
    renderApp(<Harness />, { api, auth: fakeAuth(OPERATOR_CLAIMS), lang: "fr" });
    expect(await screen.findByRole("checkbox", { name: /Oueds/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Abris/ })).not.toBeChecked();
    expect(await screen.findByText("Oued Medjerda #1976D2 LineString")).toBeInTheDocument();
    expect(layerShapes).toHaveBeenCalledWith("oueds", [10, 36, 11, 37], zoomOf([10, 36, 11, 37]), "fr", expect.anything());
    // Unticking stores the choice: the default no longer applies in this tab.
    fireEvent.click(screen.getByRole("checkbox", { name: /Oueds/ }));
    await waitFor(() => expect(screen.queryByText(/Oued Medjerda/)).not.toBeInTheDocument());
    expect(JSON.parse(sessionStorage.getItem("ehimaya.mapDataLayers") ?? "null")).toEqual([]);
  });
});
