/**
 * Map data layers loaded from files (phase B1, docs/phase-b/design.md §2): types of
 * `/api/v1/staff/layers`, the icons the dashboard and the app both draw, the form checks (mirroring
 * `services/api/app/modules/layers/schemas.py`) and the grouping of many places into clusters.
 */

import type { Geometry as GeoJsonGeometry } from "geojson";
import type { BBox } from "./filters";

export const LAYER_ICONS = [
  "hospital",
  "clinic",
  "pharmacy",
  "police",
  "guard",
  "civil_protection",
  "shelter",
  "school",
  "factory",
  "water",
  "fuel",
  "pin",
] as const;
export type LayerIcon = (typeof LAYER_ICONS)[number];

/** 24×24 paths, drawn in white on the layer's colour (our own shapes, no third-party icon set). */
export const LAYER_ICON_PATHS: Record<LayerIcon, string> = {
  // Building with a cross.
  hospital: "M4 3h16v18H4V3zm6 3v3H7v4h3v3h4v-3h3V9h-3V6h-4z",
  // House with a cross.
  clinic: "M12 3 3 9v12h18V9l-9-6zm-2 8V9h4v2h2v4h-2v2h-4v-2H8v-4h2z",
  // Plain cross.
  pharmacy: "M9 2h6v7h7v6h-7v7H9v-7H2V9h7V2z",
  // Shield with a star.
  police:
    "M12 2 4 5v6c0 5 3.4 9.7 8 11 4.6-1.3 8-6 8-11V5l-8-3zm0 5 1.5 3 3.5.5-2.5 2.4.6 3.4L12 14.6l-3.1 1.7.6-3.4L7 10.5l3.5-.5L12 7z",
  // Round badge with a star.
  guard: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 4 1.8 3.7 4 .6-2.9 2.8.7 4L12 15.2l-3.6 1.9.7-4-2.9-2.8 4-.6L12 6z",
  // Shield with a cross (same shape as the units of phase 5).
  civil_protection: "M12 2 4 5v6c0 5 3.4 9.7 8 11 4.6-1.3 8-6 8-11V5l-8-3zm-1 5h2v4h4v2h-4v4h-2v-4H7v-2h4V7z",
  // Tent.
  shelter: "M12 3 2 21h7l3-6 3 6h7L12 3z",
  // Mortarboard.
  school: "M12 3 1 9l11 6 9-4.9V17h2V9L12 3zM5 13.2V17l7 4 7-4v-3.8L12 17l-7-3.8z",
  // Saw-tooth roof.
  factory: "M2 21V9l6 4V9l6 4V3h4v18H2z",
  // Drop.
  water: "M12 2s7 8 7 13a7 7 0 0 1-14 0c0-5 7-13 7-13z",
  // Pump.
  fuel: "M4 3h10v18H4V3zm2 2v5h6V5H6zm9.5 2.5 1.4-1.4L20 9.2V18a2 2 0 0 1-4 0v-3h-1v-2h3v5h.5V10l-3-2.5z",
  // Map pin.
  pin: "M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 4.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z",
};

export function isLayerIcon(v: unknown): v is LayerIcon {
  return typeof v === "string" && (LAYER_ICONS as readonly string[]).includes(v);
}

export type Lang = "ar" | "fr" | "en";
export type Names = Record<Lang, string>;
export type Audience = "public" | "staff";
export type ImportMode = "merge" | "replace";
export type Change = "new" | "updated" | "unchanged" | "removed";

// Phase L1a (docs/phase-l/design-layers.md §3): the layer's state, who sees it and the quality of its names.
export type LayerStatus = "draft" | "published" | "paused";
export const LAYER_STATUSES: readonly LayerStatus[] = ["draft", "published", "paused"];
/** Five audiences instead of the staff roles (services/api/app/modules/layers/access.py). */
export type Group = "citizen" | "room" | "field" | "command" | "support";
export const GROUPS: readonly Group[] = ["citizen", "room", "field", "command", "support"];
export const STAFF_GROUPS: readonly Group[] = ["room", "field", "command", "support"];
/** Columns of a place card that the administrator gives to some audiences only (besides the file's own columns). */
export const CARD_FIELDS = ["phone", "address", "manager", "hours", "email", "website"] as const;
export type Confidence = "confirmed" | "high" | "medium" | "low" | "review";
export const CONFIDENCES: readonly Confidence[] = ["confirmed", "high", "medium", "low", "review"];
export type NameStatus = "official" | "suggested" | "accepted" | "rejected";
export type Geometry = "point" | "line" | "area" | "mixed";
/** Reasons offered as chips when deleting (design §3.10); "other" asks for the reason in words. */
export const DELETE_REASONS = ["duplicate", "invalid", "replaced", "other"] as const;

export interface MapLayer {
  id: string;
  key: string;
  name: Names;
  icon: string;
  colour: string;
  audience: Audience;
  source: string;
  licence: string;
  to_verify: boolean;
  /** Approximate, invented places for trials, shown with the amber [SIM] mark (migration 0035). */
  simulated: boolean;
  staff_only: string[];
  editors_allowed: boolean;
  enabled: boolean;
  version: number;
  data_version: number;
  feature_count: number;
  hidden_count: number;
  updated_by_name: string | null;
  updated_at: string;
  last_import: { id: string; status: string; at: string; by: string | null } | null;
  can_manage: boolean;
  /** Load a file, apply or undo an import: the managers alone (phase N). */
  can_import: boolean;
  /** Correct the places by hand: managers, and content editors on the layers opened to them (phase N). */
  can_edit: boolean;
  status: LayerStatus;
  audiences: Group[];
  /** Gouvernorat codes whose regional staff see it; empty: national. */
  scope: number[];
  default_on: boolean;
  /** The minister alone (and the administrator); every read of its places is audited. */
  sensitive: boolean;
  /** Column → audiences that see it; a column not listed is seen by every audience of the layer. */
  fields: Record<string, Group[]>;
  actions: { call: boolean; directions: boolean };
  geometry: Geometry;
  quality: { suggested: number; duplicates: number; deleted: number };
  deleted_at: string | null;
  delete_reason: string | null;
  purge_at: string | null;
  /** Phase UI-3b: the folder of the layer panel it shows in (its own, or the one its key suggests). */
  group?: string;
}

/** A folder of the map's layer panel (phase UI-3b): grants nothing, each layer keeps who sees it. */
export interface LayerGroup {
  key: string;
  name: Names;
  /** A dashboard icon (Icon.tsx) and a category colour. */
  icon: string;
  tone: string;
  position: number;
  /** Holds the sensitive layers alone; listed only to their readers. */
  sensitive: boolean;
  layer_count: number;
}

export interface LayerGroupBody {
  key: string;
  name: Names;
  icon: string;
  tone: string;
  position?: number;
}

export const OTHER_GROUP = "other";
const FALLBACK_OTHER: LayerGroup = {
  key: OTHER_GROUP,
  name: { ar: "طبقات أخرى", fr: "Autres couches", en: "Other layers" },
  icon: "layers",
  tone: "slate",
  position: 999,
  sensitive: false,
  layer_count: 0,
};

/** The layers in each folder of the panel, in the groups' order; a layer whose group is unknown goes to "other". */
export function layerFolders<T extends Pick<MapLayer, "key" | "group">>(
  groups: readonly LayerGroup[],
  layers: readonly T[],
): { group: LayerGroup; layers: T[] }[] {
  const known = new Set(groups.map((g) => g.key));
  const folderOf = (l: T) => (l.group && known.has(l.group) ? l.group : OTHER_GROUP);
  const all = known.has(OTHER_GROUP) ? groups : [...groups, FALLBACK_OTHER];
  return all
    .map((group) => ({ group, layers: layers.filter((l) => folderOf(l) === group.key) }))
    .filter((f) => f.layers.length > 0);
}

/** The lines and areas of a layer in a map area (phase L1b), simplified for the zoom. */
export interface LayerShapes {
  type: "FeatureCollection";
  features: { type: "Feature"; id: string; geometry: GeoJsonGeometry; properties: { id: string; name: string; kind: string | null } }[];
  truncated: boolean;
}

export interface MapLayers {
  /** Phase UI-3b: the folders holding a layer the caller sees (all of them for the administrator), in order. */
  groups?: LayerGroup[];
  items: MapLayer[];
  /** Layers deleted less than 30 days ago (administrator only): restorable. */
  deleted: MapLayer[];
  /** The caller may create layers and change their settings (system administrator, national scope). */
  can_manage: boolean;
  icons: string[];
  palette: string[];
  limits: { file_bytes: number; rows: number };
}

export interface RowProblem {
  line: number;
  reason: string;
  name?: string | null;
}

export interface RowWarning {
  line: number;
  column: string;
  reason: string;
}

export interface LayerImport {
  id: string;
  file_name: string;
  format: string;
  mode: ImportMode;
  status: "preview" | "applied" | "undone" | "discarded";
  counts: Partial<Record<Change | "rejected" | "warnings" | "rows", number>>;
  rejected: RowProblem[];
  warnings: RowWarning[];
  reason: string | null;
  created_by_name: string | null;
  created_at: string;
  applied_at: string | null;
  undone_at: string | null;
  expired: boolean;
  can_apply: boolean;
  can_undo: boolean;
}

export interface PreviewPoint {
  ref: string;
  name: string;
  lat: number;
  lon: number;
  change: Change;
}

export interface LayerImportDetail extends LayerImport {
  points: PreviewPoint[];
}

export interface LayerFeature {
  id: string;
  ref: string;
  name: string;
  kind: string | null;
  phone: string | null;
  lat: number;
  lon: number;
  gouvernorat_code: number | null;
  delegation_id: number | null;
  props: Record<string, string>;
  hidden: boolean;
  version: number;
  updated_at: string;
  geometry: Exclude<Geometry, "mixed">;
  name_status: NameStatus;
  suggested_name: string | null;
  name_confidence: Confidence | null;
  name_source: string | null;
  source_url: string | null;
  snapshot_at: string | null;
  possible_duplicate: boolean;
  deleted_at: string | null;
  delete_reason: string | null;
}

export interface LayerFeatures {
  items: LayerFeature[];
  truncated: boolean;
}

export interface LayerBody {
  key: string;
  name: Names;
  icon: string;
  colour: string;
  audience: Audience;
  source: string;
  licence: string;
  to_verify: boolean;
  simulated: boolean;
  staff_only: string[];
  editors_allowed: boolean;
  reason: string;
}

export interface LayerAccess {
  status: LayerStatus;
  audiences: Group[];
  scope: number[];
  default_on: boolean;
  sensitive: boolean;
  fields: Record<string, Group[]>;
  actions: { call: boolean; directions: boolean };
}

export type LayerPatch = Partial<Omit<LayerBody, "key" | "reason">> &
  Partial<LayerAccess> & {
  enabled?: boolean;
  /** Phase UI-3b: null puts it back in the folder its key suggests. */
  group_key?: string | null;
  version: number;
  reason: string;
};

export interface FeaturePatch {
  version: number;
  reason: string;
  name?: string;
  kind?: string | null;
  phone?: string | null;
  hidden?: boolean;
}

export interface FeatureBody {
  name: string;
  kind?: string | null;
  phone?: string | null;
  lat: number;
  lon: number;
  reason: string;
}

// ---------------------------------------------------------------- checks

export const KEY_PATTERN = /^[a-z][a-z0-9_]{1,39}$/;
export const NAME_MAX = 100;
export const SOURCE_MAX = 200;
/** Rough box around Tunisia (the API then checks the gouvernorat boundaries). */
export const LAT_RANGE = [30, 37.6] as const;
export const LON_RANGE = [7.4, 11.7] as const;

/** A key proposed from the French name: "Hôpitaux et urgences" → "hopitaux_et_urgences". */
export function keyFrom(name: string): string {
  const slug = name
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
  return /^[a-z]/.test(slug) ? slug : slug ? `l_${slug}`.slice(0, 40) : "";
}

export type LayerError = "key" | "name" | "icon" | "colour" | "source";

export function validateLayer(b: Omit<LayerBody, "reason">, palette: readonly string[]): LayerError | null {
  if (!KEY_PATTERN.test(b.key)) return "key";
  if ((["ar", "fr", "en"] as const).some((l) => b.name[l].trim() === "" || b.name[l].length > NAME_MAX)) return "name";
  if (!isLayerIcon(b.icon)) return "icon";
  if (!palette.includes(b.colour.toUpperCase())) return "colour";
  if (b.source.length > SOURCE_MAX || b.licence.length > SOURCE_MAX) return "source";
  return null;
}

/** "+216 XX XXX XXX" from "+216XXXXXXXX"; short service numbers (198) unchanged. */
export function formatPhone(phone: string): string {
  const m = /^\+216(\d{2})(\d{3})(\d{3})$/.exec(phone);
  return m ? `+216 ${m[1]} ${m[2]} ${m[3]}` : phone;
}

export function inTunisiaBox(lat: number, lon: number): boolean {
  return lat >= LAT_RANGE[0] && lat <= LAT_RANGE[1] && lon >= LON_RANGE[0] && lon <= LON_RANGE[1];
}

// ---------------------------------------------------------------- clusters

export interface Cluster {
  lat: number;
  lon: number;
  count: number;
  /** Stable while the view does not move: the grid cell. */
  id: string;
}

/**
 * Up to `max` points are drawn one by one; beyond, the visible area is cut into `cells`×`cells` squares and the
 * squares holding several points become one cluster (centred on their points) with the count.
 */
export function clusterPoints<T extends { lat: number; lon: number }>(
  points: readonly T[],
  bbox: BBox,
  max = 300,
  cells = 12,
): { singles: T[]; clusters: Cluster[] } {
  if (points.length <= max) return { singles: [...points], clusters: [] };
  const [w, s, e, n] = bbox;
  const dx = (e - w) / cells || 1;
  const dy = (n - s) / cells || 1;
  const groups = new Map<string, T[]>();
  for (const p of points) {
    const cx = Math.min(cells - 1, Math.max(0, Math.floor((p.lon - w) / dx)));
    const cy = Math.min(cells - 1, Math.max(0, Math.floor((p.lat - s) / dy)));
    const id = `${cx}:${cy}`;
    const group = groups.get(id);
    if (group) group.push(p);
    else groups.set(id, [p]);
  }
  const singles: T[] = [];
  const clusters: Cluster[] = [];
  for (const [id, group] of groups) {
    if (group.length === 1) {
      singles.push(group[0] as T);
      continue;
    }
    const lat = group.reduce((sum, p) => sum + p.lat, 0) / group.length;
    const lon = group.reduce((sum, p) => sum + p.lon, 0) / group.length;
    clusters.push({ id, lat, lon, count: group.length });
  }
  return { singles, clusters };
}

export interface LayerRevision {
  number: number;
  action: string;
  reason: string | null;
  created_by_name: string | null;
  created_at: string;
  /** The settings this revision changed from the one before. */
  changes: string[];
}

export interface ReviewQueue {
  items: LayerFeature[];
  /** Suggested names by confidence, and "duplicates". */
  counts: Record<string, number>;
  total: number;
}

export type ReviewAction = "accept" | "edit" | "reject" | "keep" | "merge";

export interface ReviewBody {
  items?: { id: string; action: ReviewAction; name?: string; into?: string }[];
  accept_confidence?: Confidence[];
  reason: string;
}

export interface ReviewResult {
  accepted: number;
  edited: number;
  rejected: number;
  kept: number;
  merged: number;
}

/** The reason sent for a delete: the chip's words, or what the administrator typed for "other". */
export function deleteReason(chip: (typeof DELETE_REASONS)[number] | null, words: string, label: (k: string) => string) {
  if (chip === null) return "";
  return chip === "other" ? words.trim() : [label(chip), words.trim()].filter(Boolean).join(" — ");
}
