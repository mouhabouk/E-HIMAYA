// Phase D, review point 9: the order of the menu, a national setting (`menu.order`) the system administrator saves
// from the drag-and-drop editor. Groups and links not named keep their built-in order after the named ones; a link the
// user may not open is never added (the order only sorts what the roles already allow).
import type { NavGroup } from "../components/Navigation";

export const MENU_ORDER_KEY = "menu.order";

export interface MenuOrder {
  groups: string[];
  items: Record<string, string[]>;
}

export const EMPTY_ORDER: MenuOrder = { groups: [], items: {} };

/** The stored value, or the empty order when it is missing or not of the expected shape. */
export function menuOrderOf(value: unknown): MenuOrder {
  if (!value || typeof value !== "object") return EMPTY_ORDER;
  const v = value as Partial<MenuOrder>;
  const groups = Array.isArray(v.groups)
    ? v.groups.filter((g): g is string => typeof g === "string")
    : [];
  const items: Record<string, string[]> = {};
  if (v.items && typeof v.items === "object") {
    for (const [k, paths] of Object.entries(v.items)) {
      if (Array.isArray(paths))
        items[k] = paths.filter((p): p is string => typeof p === "string");
    }
  }
  return { groups, items };
}

function byOrder<T>(
  list: readonly T[],
  keyOf: (x: T) => string,
  order: readonly string[],
): T[] {
  if (order.length === 0) return [...list];
  const rank = new Map(order.map((k, i) => [k, i]));
  return list
    .map((x, i) => ({ x, i, r: rank.get(keyOf(x)) ?? order.length + i }))
    .sort((a, b) => a.r - b.r)
    .map((e) => e.x);
}

/**
 * The menu in the administrator's order. A link named under another group than its own moves there (phase 5: the
 * administrator moves an element from one axis to another); a link named nowhere stays in its built-in group. A group
 * left empty by the moves is dropped.
 */
export function applyMenuOrder(
  groups: readonly NavGroup[],
  order: MenuOrder,
): NavGroup[] {
  const home = new Map<string, string>();
  for (const [key, paths] of Object.entries(order.items)) {
    if (!groups.some((g) => g.key === key)) continue;
    for (const p of paths) if (!home.has(p)) home.set(p, key);
  }
  const all = groups.flatMap((g) => g.items.map((i) => ({ i, from: g.key })));
  const placed = groups.map((g) => ({
    ...g,
    items: all
      .filter(({ i, from }) => (home.get(i.to) ?? from) === g.key)
      .map(({ i }) => i),
  }));
  return byOrder(placed, (g) => g.key, order.groups)
    .map((g) => ({
      ...g,
      items: byOrder(g.items, (i) => i.to, order.items[g.key] ?? []),
    }))
    .filter((g) => g.items.length > 0);
}

/** Moves the link at `path` to the end of group `to` (phase 5: from one axis to another). */
export function movedTo(
  groups: readonly NavGroup[],
  path: string,
  to: string,
): NavGroup[] {
  const item = groups.flatMap((g) => g.items).find((i) => i.to === path);
  if (!item) return [...groups];
  return groups.map((g) => {
    const rest = g.items.filter((i) => i.to !== path);
    return g.key === to ? { ...g, items: [...rest, item] } : { ...g, items: rest };
  });
}

/** Moves the element at `from` to `to` (drag and drop, or the up and down buttons). */
export function moved<T>(list: readonly T[], from: number, to: number): T[] {
  const next = [...list];
  if (from < 0 || from >= next.length || to < 0 || to >= next.length)
    return next;
  const [x] = next.splice(from, 1);
  next.splice(to, 0, x as T);
  return next;
}
