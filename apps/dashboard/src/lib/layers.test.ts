// covers: phase B1 (docs/phase-b/design.md §2): layer form checks, phone display, clusters.
import { describe, expect, it } from "vitest";
import { clusterPoints, formatPhone, inTunisiaBox, isLayerIcon, keyFrom, LAYER_ICON_PATHS, LAYER_ICONS, validateLayer } from "./layers";

const PALETTE = ["#C62828", "#2E7D32"];
const BASE = {
  key: "hopitaux",
  name: { ar: "المستشفيات", fr: "Hôpitaux", en: "Hospitals" },
  icon: "hospital",
  colour: "#c62828",
  audience: "public" as const,
  source: "OpenStreetMap",
  licence: "ODbL",
  to_verify: true,
  simulated: false,
  staff_only: ["manager"],
  editors_allowed: false,
};

describe("layers", () => {
  it("proposes a key from the French name", () => {
    expect(keyFrom("Hôpitaux et urgences")).toBe("hopitaux_et_urgences");
    expect(keyFrom("1er secours")).toBe("l_1er_secours");
    expect(keyFrom("مستشفيات")).toBe("");
  });

  it("checks the layer form like the API", () => {
    expect(validateLayer(BASE, PALETTE)).toBeNull();
    expect(validateLayer({ ...BASE, key: "Hôpitaux" }, PALETTE)).toBe("key");
    expect(validateLayer({ ...BASE, name: { ...BASE.name, en: " " } }, PALETTE)).toBe("name");
    expect(validateLayer({ ...BASE, icon: "rocket" }, PALETTE)).toBe("icon");
    expect(validateLayer({ ...BASE, colour: "#FFB300" }, PALETTE)).toBe("colour");
    expect(validateLayer({ ...BASE, source: "x".repeat(201) }, PALETTE)).toBe("source");
  });

  it("has a path for every icon", () => {
    for (const icon of LAYER_ICONS) expect(LAYER_ICON_PATHS[icon]).toMatch(/^M/);
    expect(isLayerIcon("hospital")).toBe(true);
    expect(isLayerIcon("x")).toBe(false);
  });

  it("formats Tunisian numbers and keeps short ones", () => {
    expect(formatPhone("+21674241511")).toBe("+216 74 241 511");
    expect(formatPhone("198")).toBe("198");
    expect(inTunisiaBox(36.8, 10.18)).toBe(true);
    expect(inTunisiaBox(48.85, 2.35)).toBe(false);
  });

  it("groups many places into clusters, keeps lone ones", () => {
    const few = [{ lat: 36.8, lon: 10.1 }];
    expect(clusterPoints(few, [10, 36, 11, 37])).toEqual({ singles: few, clusters: [] });
    const many = [
      ...Array.from({ length: 5 }, () => ({ lat: 36.01, lon: 10.01 })),
      { lat: 36.95, lon: 10.95 },
    ];
    const { singles, clusters } = clusterPoints(many, [10, 36, 11, 37], 3, 10);
    expect(singles).toEqual([{ lat: 36.95, lon: 10.95 }]);
    expect(clusters).toHaveLength(1);
    expect(clusters[0]).toMatchObject({ count: 5, lat: 36.01, lon: 10.01 });
  });
});
