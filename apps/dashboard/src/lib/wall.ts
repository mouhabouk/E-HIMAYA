/**
 * The multi-screen wall (phase 6): 1, 4 or 9 tiles. An operator can pin a stream to a tile; the other tiles show the
 * remaining live streams, those with the strongest fire or smoke first. The layout and the pins are a per-browser
 * convenience (localStorage), never shared.
 */
import type { StaffStream } from "./streamTypes";

export const WALL_LAYOUTS = [1, 4, 9] as const;
export type WallLayout = (typeof WALL_LAYOUTS)[number];

export interface WallState {
  layout: WallLayout;
  /** One entry per tile (up to 9): the pinned stream id, or null for "next live stream". */
  pinned: (string | null)[];
}

export interface WallTile {
  slot: number;
  streamId: string | null;
  pinned: boolean;
}

const STORAGE_KEY = "ehimaya.streamWall";
export const DEFAULT_WALL: WallState = { layout: 4, pinned: [] };

export function isWallLayout(v: unknown): v is WallLayout {
  return v === 1 || v === 4 || v === 9;
}

export function loadWall(): WallState {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_WALL;
    const parsed = JSON.parse(raw) as Partial<WallState>;
    const layout = isWallLayout(parsed.layout) ? parsed.layout : DEFAULT_WALL.layout;
    const pinned = Array.isArray(parsed.pinned)
      ? parsed.pinned.slice(0, 9).map((p) => (typeof p === "string" && p ? p : null))
      : [];
    return { layout, pinned };
  } catch {
    return DEFAULT_WALL;
  }
}

export function saveWall(state: WallState): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* storage unavailable: the wall resets on reload */
  }
}

/** Strongest fire/smoke first, then the most recently started. */
export function byDanger(a: StaffStream, b: StaffStream): number {
  const da = Math.max(a.max_fire_confidence ?? 0, a.max_smoke_confidence ?? 0);
  const db = Math.max(b.max_fire_confidence ?? 0, b.max_smoke_confidence ?? 0);
  if (da !== db) return db - da;
  return Date.parse(b.started_at ?? "") - Date.parse(a.started_at ?? "") || 0;
}

/** Tiles of the wall: pinned streams where they were pinned, the other live streams in the free tiles. */
export function arrangeWall(state: WallState, live: readonly StaffStream[]): WallTile[] {
  const count = state.layout;
  const pinned = state.pinned.slice(0, count);
  const taken = new Set(pinned.filter((p): p is string => p !== null));
  const queue = live.filter((s) => s.status === "live" && !taken.has(s.id)).sort(byDanger);
  const tiles: WallTile[] = [];
  for (let slot = 0; slot < count; slot += 1) {
    const id = pinned[slot] ?? null;
    if (id) tiles.push({ slot, streamId: id, pinned: true });
    else tiles.push({ slot, streamId: queue.shift()?.id ?? null, pinned: false });
  }
  return tiles;
}

/** Pin `id` to `slot` (removing it from another tile), or unpin the tile with `id = null`. */
export function pinStream(state: WallState, slot: number, id: string | null): WallState {
  const pinned = Array.from({ length: 9 }, (_, i) => state.pinned[i] ?? null).map((p) => (p === id ? null : p));
  pinned[slot] = id;
  return { ...state, pinned: trimNulls(pinned) };
}

/** "Show on the wall" from a list: the first free tile of the current layout, else the last one. */
export function pinToFreeTile(state: WallState, id: string): WallState {
  if (state.pinned.slice(0, state.layout).includes(id)) return state;
  let slot = -1;
  for (let i = 0; i < state.layout; i += 1) {
    if (!state.pinned[i]) {
      slot = i;
      break;
    }
  }
  return pinStream(state, slot === -1 ? state.layout - 1 : slot, id);
}

function trimNulls(list: (string | null)[]): (string | null)[] {
  let end = list.length;
  while (end > 0 && list[end - 1] === null) end -= 1;
  return list.slice(0, end);
}
