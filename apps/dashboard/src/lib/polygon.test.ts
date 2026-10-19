import { describe, expect, it } from "vitest";
import {
  addVertex,
  fromPolygon,
  MAX_VERTICES,
  selfIntersects,
  toPolygon,
  undoVertex,
  validateVertices,
  verticesBounds,
  type Vertex,
} from "./polygon";

const SQUARE: Vertex[] = [
  [10.7, 34.7],
  [10.82, 34.7],
  [10.82, 34.8],
  [10.7, 34.8],
];

describe("alert area polygon", () => {
  it("adds rounded vertices, ignores an immediate duplicate and undoes the last one", () => {
    let v = addVertex([], 10.123456789, 34.987654321);
    expect(v).toEqual([[10.123457, 34.987654]]);
    v = addVertex(v, 10.123457, 34.987654);
    expect(v).toHaveLength(1);
    v = addVertex(v, 10.2, 34.9);
    expect(undoVertex(v)).toEqual([[10.123457, 34.987654]]);
  });

  it("stops at the server's limit", () => {
    const full = Array.from({ length: MAX_VERTICES }, (_, i) => [10 + i / 1000, 34] as Vertex);
    expect(addVertex(full, 11, 35)).toHaveLength(MAX_VERTICES);
  });

  it("validates count, bounds and self-intersection", () => {
    expect(validateVertices(SQUARE.slice(0, 2))).toBe("too_few");
    expect(validateVertices(SQUARE)).toBeNull();
    expect(validateVertices([...SQUARE.slice(0, 3), [2.35, 48.85]])).toBe("outside");
    const bowtie: Vertex[] = [
      [10.7, 34.7],
      [10.82, 34.8],
      [10.82, 34.7],
      [10.7, 34.8],
    ];
    expect(selfIntersects(bowtie)).toBe(true);
    expect(validateVertices(bowtie)).toBe("self_intersecting");
    expect(selfIntersects(SQUARE)).toBe(false);
  });

  it("closes the ring for GeoJSON and reopens it when editing", () => {
    const polygon = toPolygon(SQUARE);
    expect(polygon.type).toBe("Polygon");
    expect(polygon.coordinates[0]).toHaveLength(5);
    expect(polygon.coordinates[0]?.[4]).toEqual([10.7, 34.7]);
    expect(fromPolygon(polygon)).toEqual(SQUARE);
    expect(fromPolygon(null)).toEqual([]);
  });

  it("computes padded bounds", () => {
    expect(verticesBounds([])).toBeNull();
    const b = verticesBounds(SQUARE) ?? [0, 0, 0, 0];
    expect(b[0]).toBeCloseTo(10.68);
    expect(b[3]).toBeCloseTo(34.82);
  });
});
