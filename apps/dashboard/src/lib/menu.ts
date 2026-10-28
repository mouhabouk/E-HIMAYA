// How the user wants the main menu (phase UI-3, docs/phase-ui3/design-menu.md §2.2): grouped menus that open on
// hover, or every link at once; at the top of the page or in a side bar on the right or the left. Kept in the
// browser like the theme: there is no account preference store on the server yet (§3).

export const MENU_SHAPES = ["grouped", "flat"] as const;
export type MenuShape = (typeof MENU_SHAPES)[number];

/** Physical sides: "right" stays on the right in Arabic, French and English. */
export const MENU_POSITIONS = ["top", "right", "left"] as const;
export type MenuPosition = (typeof MENU_POSITIONS)[number];

export interface MenuPrefs {
  shape: MenuShape;
  position: MenuPosition;
}

export const DEFAULT_MENU: MenuPrefs = { shape: "grouped", position: "top" };
const STORAGE_KEY = "ehimaya.menu";

export function storedMenu(): MenuPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_MENU;
    const v = JSON.parse(raw) as Partial<MenuPrefs>;
    return {
      shape: MENU_SHAPES.find((s) => s === v.shape) ?? DEFAULT_MENU.shape,
      position: MENU_POSITIONS.find((p) => p === v.position) ?? DEFAULT_MENU.position,
    };
  } catch {
    return DEFAULT_MENU;
  }
}

export function saveMenu(prefs: MenuPrefs): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore: the choice still applies until the page is reloaded */
  }
}
