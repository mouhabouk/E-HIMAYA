import { describe, expect, it } from "vitest";
import {
  categoryCounts,
  hexHeight,
  hourlyCounts,
  isOpen,
  openCount,
  opsRoomRestyle,
  readiness,
  reportPoints,
  startOfDay,
} from "./opsRoom";

describe("operations room helpers", () => {
  it("counts the reports of the last 24 hours by hour, current hour last", () => {
    const now = new Date("2026-11-09T21:40:00");
    const at = (s: string) => ({ created_at: new Date(s).toISOString() });
    const counts = hourlyCounts(
      [
        at("2026-11-09T21:05:00"),
        at("2026-11-09T21:39:00"),
        at("2026-11-09T20:59:00"),
        at("2026-11-08T22:00:00"),
        at("2026-11-08T21:59:00"), // 24 hours before the current hour: out
        at("2026-11-09T22:10:00"), // future: out
      ],
      now,
    );
    expect(counts).toHaveLength(24);
    expect(counts[23]).toBe(2);
    expect(counts[22]).toBe(1);
    expect(counts[0]).toBe(1);
    expect(counts.reduce((a, b) => a + b, 0)).toBe(4);
  });

  it("starts the day at local midnight", () => {
    const d = new Date(startOfDay(new Date("2026-11-09T21:40:00")));
    expect([d.getHours(), d.getMinutes(), d.getDate()]).toEqual([0, 0, 9]);
  });

  it("tells open reports from closed ones", () => {
    expect(isOpen("received")).toBe(true);
    expect(isOpen("ongoing")).toBe(true);
    expect(isOpen("closed")).toBe(false);
    expect(isOpen("rejected")).toBe(false);
    expect(openCount({ by_status: { received: 3, in_progress: 2, closed: 9, rejected: 1, ongoing: 1 } })).toBe(6);
  });

  it("orders the day's categories, empty ones left out", () => {
    expect(categoryCounts({ by_category: { fire: 4, medical: 9, flood: 0, sos: 4 } })).toEqual([
      { category: "medical", count: 9 },
      { category: "fire", count: 4 },
      { category: "sos", count: 4 },
    ]);
  });

  it("gives the readiness of the largest fleets", () => {
    const r = readiness({
      by_kind: {
        ambulance: { available: 18, assigned: 3, out_of_service: 2 },
        fire_engine: { available: 9, assigned: 5 },
        drone: { out_of_service: 1 },
        boat: {},
      },
    });
    expect(r).toEqual([
      { kind: "ambulance", available: 18, inService: 21, total: 23 },
      { kind: "fire_engine", available: 9, inService: 14, total: 14 },
      { kind: "drone", available: 0, inService: 0, total: 1 },
    ]);
  });

  it("draws reports as points coloured by category, open ones flagged", () => {
    const fc = reportPoints([
      { id: "a", category: "fire", status: "received", location: { lon: 10.1, lat: 36.8 } },
      { id: "b", category: "medical", status: "closed", location: { lon: 10.2, lat: 36.7 } },
    ]);
    expect(fc.features.map((f) => [f.properties.id, f.properties.open, f.geometry.coordinates])).toEqual([
      ["a", 1, [10.1, 36.8]],
      ["b", 0, [10.2, 36.7]],
    ]);
    expect(fc.features[0]?.properties.colour).toBe("#FF6B6B");
  });

  it("scales hotspot columns to the busiest cell", () => {
    expect(hexHeight(10, 10)).toBe(2500);
    expect(hexHeight(5, 10)).toBe(1250);
    expect(hexHeight(0, 10)).toBe(0);
    expect(hexHeight(3, 0)).toBe(0);
  });

  it("restyles the street map for the dark wall and leaves unknown layers alone", () => {
    expect(opsRoomRestyle({ id: "background", type: "background" })?.paint).toEqual({ "background-color": "#0B1122" });
    expect(opsRoomRestyle({ id: "road-primary-casing", type: "line" })?.paint).toEqual({ "line-color": "#0B1122" });
    expect(opsRoomRestyle({ id: "osm", type: "raster" })?.paint["raster-brightness-max"]).toBe(0.32);
    expect(opsRoomRestyle({ id: "place-city", type: "symbol" })?.paint["text-color"]).toBe("#C7D0E6");
    expect(opsRoomRestyle({ id: "something-else", type: "fill" })).toBeNull();
  });
});
