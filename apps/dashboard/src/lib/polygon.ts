/**
 * Alert areas drawn on the map (contract §7): one ring of 4–500 positions inside Tunisia, closed.
 * The editor keeps the open list of vertices; the ring is closed only when it is sent.
 */
import type { Polygon } from "./opsTypes";

export type Vertex = [lon: number, lat: number];

/** Distinct vertices: at least 3 (4 positions once closed), at most 500 (the server's limit before closing). */
export const MIN_VERTICES = 3;
export const MAX_VERTICES = 500;
/** The contract's accepted area (same bounds as the API's LAT_/LON_ limits). */
export const AREA_BOUNDS = { minLon: 7.4, maxLon: 11.7, minLat: 30.0, maxLat: 37.6 } as const;

export type PolygonError = "too_few" | "too_many" | "outside" | "self_intersecting";

const round = (n: number) => Math.round(n * 1e6) / 1e6;

export function addVertex(vertices: readonly Vertex[], lon: number, lat: number): Vertex[] {
  if (vertices.length >= MAX_VERTICES) return [...vertices];
  const v: Vertex = [round(lon), round(lat)];
  const last = vertices.at(-1);
  if (last && last[0] === v[0] && last[1] === v[1]) return [...vertices];
  return [...vertices, v];
}

export function undoVertex(vertices: readonly Vertex[]): Vertex[] {
  return vertices.slice(0, -1);
}

function inside([lon, lat]: Vertex): boolean {
  return lon >= AREA_BOUNDS.minLon && lon <= AREA_BOUNDS.maxLon && lat >= AREA_BOUNDS.minLat && lat <= AREA_BOUNDS.maxLat;
}

function orientation(a: Vertex, b: Vertex, c: Vertex): number {
  const v = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1]);
  return Math.abs(v) < 1e-12 ? 0 : v > 0 ? 1 : 2;
}

function segmentsCross(p1: Vertex, p2: Vertex, q1: Vertex, q2: Vertex): boolean {
  const o1 = orientation(p1, p2, q1);
  const o2 = orientation(p1, p2, q2);
  const o3 = orientation(q1, q2, p1);
  const o4 = orientation(q1, q2, p2);
  return o1 !== o2 && o3 !== o4 && o1 !== 0 && o2 !== 0 && o3 !== 0 && o4 !== 0;
}

/** True when two non-adjacent edges of the closed ring cross (PostGIS would reject it as invalid). */
export function selfIntersects(vertices: readonly Vertex[]): boolean {
  const n = vertices.length;
  if (n < 4) return false;
  const edge = (i: number): [Vertex, Vertex] => [vertices[i] as Vertex, vertices[(i + 1) % n] as Vertex];
  for (let i = 0; i < n; i += 1) {
    for (let j = i + 1; j < n; j += 1) {
      if (j === i + 1 || (i === 0 && j === n - 1)) continue;
      const [a, b] = edge(i);
      const [c, d] = edge(j);
      if (segmentsCross(a, b, c, d)) return true;
    }
  }
  return false;
}

export function validateVertices(vertices: readonly Vertex[]): PolygonError | null {
  if (vertices.length < MIN_VERTICES) return "too_few";
  if (vertices.length > MAX_VERTICES) return "too_many";
  if (!vertices.every(inside)) return "outside";
  if (selfIntersects(vertices)) return "self_intersecting";
  return null;
}

/** GeoJSON Polygon with the ring closed (first position repeated at the end). */
export function toPolygon(vertices: readonly Vertex[]): Polygon {
  const ring: [number, number][] = vertices.map(([lon, lat]) => [lon, lat]);
  const first = ring[0];
  if (first) ring.push([first[0], first[1]]);
  return { type: "Polygon", coordinates: [ring] };
}

/** Vertices of a stored polygon (the closing position dropped). */
export function fromPolygon(polygon: Polygon | null | undefined): Vertex[] {
  const ring = polygon?.coordinates[0] ?? [];
  const vertices = ring.map(([lon, lat]) => [lon, lat] as Vertex);
  const first = vertices[0];
  const last = vertices.at(-1);
  if (vertices.length > 1 && first && last && first[0] === last[0] && first[1] === last[1]) vertices.pop();
  return vertices;
}

/** Bounding box [west, south, east, north] of the vertices, with a small margin; null when empty. */
export function verticesBounds(vertices: readonly Vertex[]): [number, number, number, number] | null {
  if (vertices.length === 0) return null;
  const lons = vertices.map((v) => v[0]);
  const lats = vertices.map((v) => v[1]);
  const pad = 0.02;
  return [Math.min(...lons) - pad, Math.min(...lats) - pad, Math.max(...lons) + pad, Math.max(...lats) + pad];
}
