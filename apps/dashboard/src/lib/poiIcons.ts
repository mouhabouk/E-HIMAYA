/** Map points of interest of the institutions layer (phase 4 §5, §9): kinds and 24×24 icon paths. */

export const POI_KINDS = ["org", "org_hazmat", "evacuation_point", "water_point", "alarm"] as const;
export type PoiKind = (typeof POI_KINDS)[number];

export const POI_ICON_PATHS: Record<PoiKind, string> = {
  // Building.
  org: "M4 21V5l8-3 8 3v16h-6v-5h-4v5H4zm4-12h2V7H8v2zm6 0h2V7h-2v2zm-6 4h2v-2H8v2zm6 0h2v-2h-2v2z",
  // Warning triangle (hazardous materials).
  org_hazmat: "M12 2 1 21h22L12 2zm-1 7h2v6h-2V9zm0 8h2v2h-2v-2z",
  // Person at an assembly point.
  evacuation_point: "M12 2a2 2 0 1 1 0 4 2 2 0 0 1 0-4zM9 8h6l-1 6h-1v8h-2v-8h-1L9 8z",
  // Water drop.
  water_point: "M12 2s7 8 7 13a7 7 0 0 1-14 0c0-5 7-13 7-13z",
  // Bell.
  alarm: "M12 22a2 2 0 0 0 2-2h-4a2 2 0 0 0 2 2zm6-6v-5a6 6 0 0 0-5-5.9V4h-2v1.1A6 6 0 0 0 6 11v5l-2 2v1h16v-1l-2-2z",
};

export function isPoiKind(v: unknown): v is PoiKind {
  return typeof v === "string" && (POI_KINDS as readonly string[]).includes(v);
}
