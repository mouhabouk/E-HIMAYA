/**
 * The repository map of the «تطوير النظام» menu (Yamen, 2026-11-09; docs/dev/repo-map.md): pages, mobile features,
 * API modules, services and infrastructure, and the imports, HTTP calls and settings that tie them. The layout is a
 * small force simulation computed once in the browser (no drawing library).
 */
import type { ApiClient } from "./api";
import type { Tone } from "../components/Icon";

export type MapGroup = "api" | "dashboard" | "portal" | "mobile" | "service" | "infra" | "external";
export type LinkKind = "import" | "http" | "calls";

export interface MapNode {
  id: string;
  label: string;
  group: MapGroup;
  files: number;
  loc: number;
  deg: number;
}

export interface MapEdge {
  s: string;
  t: string;
  k: LinkKind;
  w: number;
  via: string[];
}

export interface RepoMap {
  nodes: MapNode[];
  edges: MapEdge[];
  routes: number;
  generated_at: string;
}

export const MAP_GROUPS: MapGroup[] = ["dashboard", "portal", "mobile", "api", "service", "infra", "external"];
export const LINK_KINDS: LinkKind[] = ["http", "import", "calls"];
export const GROUP_TONE: Record<MapGroup, Tone> = {
  dashboard: "purple",
  portal: "teal",
  mobile: "green",
  api: "navy",
  service: "orange",
  infra: "slate",
  external: "amber",
};

export function repoMapApi(api: ApiClient) {
  return {
    repoMap: (signal?: AbortSignal) => api.request<RepoMap>("/api/v1/admin/dev/repo-map", { signal }),
  };
}

export const repoMapKeys = { map: ["dev", "repo-map"] as const };

/** The «تطوير النظام» menu: the national system administrator. */
export function canUseDevTools(who: { roles: readonly string[]; national: boolean }): boolean {
  return who.national && who.roles.includes("sysadmin");
}

export interface Placed {
  x: number;
  y: number;
  r: number;
}

/** Node radius from its lines of code (an area that grows with the code). */
export function radius(n: Pick<MapNode, "loc">): number {
  return 4 + Math.sqrt(Math.max(n.loc, 0)) / 9;
}

// Where each group gathers: front ends on one side, the API in the middle, what it calls on the other side.
const ANCHORS: Record<MapGroup, [number, number]> = {
  dashboard: [-520, -120],
  portal: [-420, 330],
  mobile: [-80, 420],
  api: [80, -40],
  service: [520, 260],
  infra: [560, -200],
  external: [620, 120],
};

/**
 * Positions of the nodes: repulsion between all nodes, springs along the links, a pull toward the group's anchor,
 * and no overlap. Deterministic (the start positions come from the order of the nodes), so the map is the same on
 * every visit.
 */
export function layout(nodes: MapNode[], edges: MapEdge[], ticks = 260): Map<string, Placed> {
  interface Body {
    id: string;
    x: number;
    y: number;
    vx: number;
    vy: number;
    r: number;
    ax: number;
    ay: number;
  }
  const bodies: Body[] = nodes.map((node, i) => {
    const [ax, ay] = ANCHORS[node.group];
    const a = i * 2.399963; // golden angle: an even spread around the anchor
    const d = 12 * Math.sqrt(i % 60);
    return { id: node.id, x: ax + d * Math.cos(a), y: ay + d * Math.sin(a), vx: 0, vy: 0, r: radius(node), ax, ay };
  });
  const byId = new Map(bodies.map((b) => [b.id, b]));
  const links: [Body, Body, LinkKind][] = [];
  for (const e of edges) {
    const a = byId.get(e.s);
    const b = byId.get(e.t);
    if (a && b) links.push([a, b, e.k]);
  }
  for (let tick = 0; tick < ticks; tick += 1) {
    const alpha = 1 - tick / ticks;
    bodies.forEach((p, i) => {
      for (const q of bodies.slice(i + 1)) {
        let dx = q.x - p.x;
        let dy = q.y - p.y;
        let d2 = dx * dx + dy * dy;
        if (d2 < 0.01) {
          dx = 0.1 * ((i % 7) - 3);
          dy = 0.1;
          d2 = dx * dx + dy * dy;
        }
        const d = Math.sqrt(d2);
        let f = Math.min((260 * alpha) / d2, 0.5);
        const min = p.r + q.r + 4;
        if (d < min) f += (min - d) / d / 2;
        p.vx -= dx * f;
        p.vy -= dy * f;
        q.vx += dx * f;
        q.vy += dy * f;
      }
    });
    for (const [a, b, k] of links) {
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const rest = k === "import" ? 70 : 140;
      const f = ((d - rest) / d) * 0.008 * alpha;
      a.vx += dx * f;
      a.vy += dy * f;
      b.vx -= dx * f;
      b.vy -= dy * f;
    }
    for (const b of bodies) {
      b.vx += (b.ax - b.x) * 0.03;
      b.vy += (b.ay - b.y) * 0.03;
      b.x += b.vx;
      b.y += b.vy;
      b.vx *= 0.55;
      b.vy *= 0.55;
    }
  }
  return new Map(bodies.map((b) => [b.id, { x: b.x, y: b.y, r: b.r }]));
}

/** The pan and zoom that show every placed node in a width × height view centred on 0, 0. */
export function fit(placed: Map<string, Placed>, width: number, height: number): { x: number; y: number; k: number } {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of placed.values()) {
    minX = Math.min(minX, p.x - p.r);
    minY = Math.min(minY, p.y - p.r);
    maxX = Math.max(maxX, p.x + p.r);
    maxY = Math.max(maxY, p.y + p.r + 14);
  }
  if (!Number.isFinite(minX)) return { x: 0, y: 0, k: 1 };
  const k = Math.min(width / (maxX - minX + 60), height / (maxY - minY + 60), 2);
  return { x: (-(minX + maxX) / 2) * k, y: (-(minY + maxY) / 2) * k, k };
}
