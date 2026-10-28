import { keepPreviousData, useQueries, useQuery } from "@tanstack/react-query";
import type { FeatureCollection } from "geojson";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import type { BBox } from "../lib/filters";
import { useLanguage } from "../lib/hooks";
import {
  clusterPoints,
  formatPhone,
  isLayerIcon,
  LAYER_ICON_PATHS,
  layerFolders,
  type LayerFeature,
  type LayerGroup,
  type MapLayer,
} from "../lib/layers";
import { layerKeys } from "../lib/layersApi";
import { localized } from "../lib/localized";
import { SimTag } from "./StreamBits";
import { ErrorBox } from "./Feedback";
import { Icon, IconTile, iconOr, toneOr } from "./Icon";
import type { MapPoi } from "./MapView";

const STORE_KEY = "ehimaya.mapDataLayers";
// Phase UI-3b: the folders the user opened, kept in the browser like the menu.
const FOLDERS_KEY = "ehimaya.layerFolders";
// Above this many places of one layer in view, neighbours are grouped (MapLibre draws every marker as an element).
const MAX_SINGLE = 300;

/** The layers ticked in this tab; null until the user changes them (the layers "shown by default" then apply). */
function storedKeys(): string[] | null {
  try {
    const raw = sessionStorage.getItem(STORE_KEY);
    if (raw === null) return null;
    const v: unknown = JSON.parse(raw);
    return Array.isArray(v) ? v.filter((k): k is string => typeof k === "string") : null;
  } catch {
    return null;
  }
}

function storedFolders(): string[] | null {
  try {
    const v: unknown = JSON.parse(localStorage.getItem(FOLDERS_KEY) ?? "null");
    return Array.isArray(v) ? v.filter((k): k is string => typeof k === "string") : null;
  } catch {
    return null;
  }
}

function storeFolders(keys: string[]): void {
  try {
    localStorage.setItem(FOLDERS_KEY, JSON.stringify(keys));
  } catch {
    /* ignore: the choice still applies until the page is reloaded */
  }
}

/** The zoom level that shows this area (the server simplifies the lines and areas for it). */
export function zoomOf(bbox: BBox): number {
  const width = Math.max(bbox[2] - bbox[0], 1e-6);
  return Math.max(0, Math.min(22, Math.round(Math.log2(360 / width) + 1)));
}

function storeKeys(keys: string[]): void {
  try {
    sessionStorage.setItem(STORE_KEY, JSON.stringify(keys));
  } catch {
    /* ignore */
  }
}

export function iconPathOf(icon: string): string {
  return LAYER_ICON_PATHS[isLayerIcon(icon) ? icon : "pin"];
}

/** Coloured square with the layer's icon (legend, layer list). */
export function LayerSwatch({ layer }: { layer: Pick<MapLayer, "icon" | "colour"> }) {
  return (
    <span className="layer-swatch" style={{ background: layer.colour }} aria-hidden="true">
      <svg viewBox="0 0 24 24">
        <path fill="currentColor" fillRule="evenodd" d={iconPathOf(layer.icon)} />
      </svg>
    </span>
  );
}

/**
 * A layer that is not loaded from a file but belongs in a folder (phase R2): the units and resources of the operations,
 * the result of a resources search. Its switch is kept by the page that draws it.
 */
export interface FolderExtra {
  key: string;
  label: string;
  on: boolean;
  onChange: (on: boolean) => void;
  /** Shown under the switch when the layer is on (a count, a legend, a link). */
  note?: ReactNode;
  /** Opens the folder once when the layer arrives (a search sent to the map). */
  reveal?: boolean;
}

/** Phase R2: the folder the operations layers go to, should the caller see no file layer of it. */
export const CIVIL_PROTECTION_GROUP: LayerGroup = {
  key: "civil_protection",
  name: { ar: "موارد الحماية المدنية", fr: "Moyens de la protection civile", en: "Civil protection resources" },
  icon: "localFireDepartment",
  tone: "red",
  position: 0,
  sensitive: false,
  layer_count: 0,
};

/** "Show every layer of the folder": ticked, unticked, or mixed when only some are on. */
function FolderSwitch({
  on,
  total,
  label,
  onChange,
}: {
  on: number;
  total: number;
  label: string;
  onChange: (on: boolean) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const mixed = on > 0 && on < total;
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = mixed;
  }, [mixed]);
  return (
    <input
      ref={ref}
      type="checkbox"
      className="layer-folder__all"
      checked={on === total}
      aria-label={label}
      onChange={() => onChange(on < total)}
    />
  );
}

function LayerFolder({
  group,
  layers,
  shown,
  open,
  onOpen,
  onToggle,
  extras = [],
}: {
  group: LayerGroup;
  layers: MapLayer[];
  shown: readonly string[];
  open: boolean;
  onOpen: (open: boolean) => void;
  onToggle: (keys: string[], on: boolean) => void;
  extras?: readonly FolderExtra[];
}) {
  const { t } = useTranslation();
  const lang = useLanguage();
  const id = useId();
  const name = localized(group.name, lang);
  const on = layers.filter((l) => shown.includes(l.key)).length + extras.filter((x) => x.on).length;
  const total = layers.length + extras.length;
  return (
    <section className="layer-folder" data-open={open || undefined} aria-labelledby={`${id}-name`}>
      <div className="layer-folder__head">
        <FolderSwitch
          on={on}
          total={total}
          label={t("layers.groups.showAll", { group: name })}
          onChange={(next) => {
            if (layers.length > 0) onToggle(layers.map((l) => l.key), next);
            for (const x of extras) if (x.on !== next) x.onChange(next);
          }}
        />
        <button
          type="button"
          className="layer-folder__btn"
          aria-expanded={open}
          aria-controls={`${id}-list`}
          onClick={() => onOpen(!open)}
        >
          <IconTile name={iconOr(group.icon, "layers")} tone={toneOr(group.tone, "slate")} size="sm" />
          <span id={`${id}-name`} className="layer-folder__name">
            {name}
          </span>
          <span className="layer-folder__count">{t("layers.groups.count", { on, total })}</span>
          <Icon name="expandMore" size={18} />
        </button>
      </div>
      <div id={`${id}-list`} className="layer-folder__list" hidden={!open}>
        {extras.map((x) => (
          <div key={x.key} className="layer-folder__extra">
            <label className="checkbox">
              <input type="checkbox" checked={x.on} onChange={(e) => x.onChange(e.target.checked)} />
              <span>{x.label}</span>
            </label>
            {x.on && x.note}
          </div>
        ))}
        {layers.map((layer) => (
          <label key={layer.key} className="checkbox">
            <input
              type="checkbox"
              checked={shown.includes(layer.key)}
              onChange={(e) => onToggle([layer.key], e.target.checked)}
            />
            <LayerSwatch layer={layer} />
            <span dir="auto">{localized(layer.name, lang)}</span>
            {layer.audience === "staff" && <span className="chip">{t("layers.audience.staff")}</span>}
            {layer.simulated && <SimTag label={t("layers.simulated")} />}
          </label>
        ))}
      </div>
    </section>
  );
}

function featurePoi(layer: MapLayer, f: LayerFeature, t: (k: string, o?: Record<string, unknown>) => string): MapPoi {
  const details: string[] = [];
  if (f.phone) details.push(`${t("layers.place.phone")}: ${formatPhone(f.phone)}`);
  for (const [k, v] of Object.entries(f.props)) {
    if (k === "phone2") details.push(`${t("layers.place.phone")}: ${formatPhone(v)}`);
    else details.push(`${t(`layers.columns.${k}`, { defaultValue: k })}: ${v}`);
  }
  if (f.hidden) details.push(t("layers.place.hiddenNote"));
  return {
    id: `${layer.key}:${f.id}`,
    lon: f.lon,
    lat: f.lat,
    kind: "place",
    title: f.name,
    subtitle: [f.kind, layer.simulated ? `[SIM] ${t("layers.simulated")}` : null, layer.to_verify ? t("layers.toVerify") : null]
      .filter(Boolean)
      .join(" · "),
    iconPath: iconPathOf(layer.icon),
    colour: layer.colour,
    details: details.slice(0, 12),
    ...(f.phone ? { call: { number: f.phone } } : {}),
  };
}

/**
 * Map data layers on the live map (phase B1, design §2.4): one tick per layer, any number at once, beside the
 * existing layers; places in the visible area, grouped when there are many. Phase UI-3b: the layers sit in folders
 * (health facilities, civil protection resources…) that open and close, each with a switch for all its layers.
 */
export function useMapDataLayers(bbox: BBox | null, extras: Readonly<Record<string, readonly FolderExtra[]>> = {}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const groupId = useId();
  const [picked, setPicked] = useState<string[] | null>(storedKeys);
  const layersQuery = useQuery({ queryKey: layerKeys.all, queryFn: ({ signal }) => api.layers(signal) });
  const layers = useMemo(() => (layersQuery.data?.items ?? []).filter((l) => l.enabled), [layersQuery.data]);
  const fileFolders = useMemo(() => layerFolders(layersQuery.data?.groups ?? [], layers), [layersQuery.data, layers]);
  // Phase R2: a folder holding only page layers (no file layer the caller sees) still shows, first.
  const folders = useMemo(() => {
    const missing = Object.keys(extras)
      .filter((key) => (extras[key]?.length ?? 0) > 0 && !fileFolders.some((f) => f.group.key === key))
      .map((key) => ({
        group: layersQuery.data?.groups?.find((g) => g.key === key) ?? { ...CIVIL_PROTECTION_GROUP, key },
        layers: [] as MapLayer[],
      }));
    return [...missing, ...fileFolders];
  }, [extras, fileFolders, layersQuery.data]);
  const [openedFolders, setOpenedFolders] = useState<string[] | null>(storedFolders);
  // Phase L1b: until the user ticks a layer, the layers the administrator marked "shown by default" are on.
  const shown = useMemo(() => picked ?? layers.filter((l) => l.default_on).map((l) => l.key), [picked, layers]);
  const active = useMemo(() => layers.filter((l) => shown.includes(l.key)), [layers, shown]);
  const withShapes = useMemo(() => active.filter((l) => l.geometry !== "point"), [active]);
  const zoom = bbox ? zoomOf(bbox) : 0;

  const featureQueries = useQueries({
    queries: active.map((layer) => ({
      queryKey: layerKeys.features(layer.key, bbox),
      enabled: bbox !== null,
      placeholderData: keepPreviousData,
      queryFn: ({ signal }: { signal: AbortSignal }) => api.layerFeatures(layer.key, bbox, signal),
    })),
  });
  const shapeQueries = useQueries({
    queries: withShapes.map((layer) => ({
      queryKey: layerKeys.shapes(layer.key, bbox, zoom, lang),
      enabled: bbox !== null,
      placeholderData: keepPreviousData,
      queryFn: ({ signal }: { signal: AbortSignal }) => api.layerShapes(layer.key, bbox ?? [0, 0, 0, 0], zoom, lang, signal),
    })),
  });

  const shapes = useMemo<FeatureCollection>(
    () => ({
      type: "FeatureCollection",
      features: withShapes.flatMap((layer, i) =>
        (shapeQueries[i]?.data?.features ?? []).map((f) => ({
          type: "Feature" as const,
          id: f.id,
          geometry: f.geometry,
          properties: { ...f.properties, colour: layer.colour, layer: layer.key },
        })),
      ),
    }),
    [withShapes, shapeQueries],
  );

  const pois = useMemo<MapPoi[]>(() => {
    if (!bbox) return [];
    const out: MapPoi[] = [];
    active.forEach((layer, i) => {
      const items = featureQueries[i]?.data?.items ?? [];
      const { singles, clusters } = clusterPoints(items, bbox, MAX_SINGLE);
      for (const f of singles) out.push(featurePoi(layer, f, t));
      for (const c of clusters) {
        out.push({
          id: `${layer.key}:cluster:${c.id}`,
          lon: c.lon,
          lat: c.lat,
          kind: "place_cluster",
          title: t("layers.cluster", { count: c.count, layer: localized(layer.name, lang) }),
          colour: layer.colour,
          count: c.count,
        });
      }
    });
    return out;
  }, [active, featureQueries, bbox, t, lang]);

  const toggle = (keys: string[], on: boolean) => {
    const rest = shown.filter((k) => !keys.includes(k));
    const next = on ? [...rest, ...keys] : rest;
    setPicked(next);
    storeKeys(next);
  };
  // Until the user opens or closes a folder, the folders with a layer on are open (and a lone folder).
  const opened =
    openedFolders ??
    folders
      .filter(
        (f) =>
          folders.length === 1 ||
          f.layers.some((l) => shown.includes(l.key)) ||
          (extras[f.group.key] ?? []).some((x) => x.on),
      )
      .map((f) => f.group.key);
  const revealed = folders
    .filter((f) => (extras[f.group.key] ?? []).some((x) => x.reveal && x.on))
    .map((f) => f.group.key)
    .join(",");
  // Adjusted while rendering (not in an effect): a search sent to the map opens its folder once.
  const [seenRevealed, setSeenRevealed] = useState("");
  if (revealed !== seenRevealed) {
    setSeenRevealed(revealed);
    if (revealed && openedFolders !== null) {
      const missing = revealed.split(",").filter((k) => !openedFolders.includes(k));
      if (missing.length > 0) setOpenedFolders([...openedFolders, ...missing]);
    }
  }
  const openFolder = (key: string, open: boolean) => {
    const next = open ? [...opened.filter((k) => k !== key), key] : opened.filter((k) => k !== key);
    setOpenedFolders(next);
    storeFolders(next);
  };

  const truncated = [
    ...active.filter((_, i) => featureQueries[i]?.data?.truncated),
    ...withShapes.filter((_, i) => shapeQueries[i]?.data?.truncated),
  ];
  const failed = featureQueries.find((q) => q.isError) ?? shapeQueries.find((q) => q.isError);

  const controls =
    folders.length === 0 ? null : (
      <fieldset className="map-data-layers">
        <legend id={`${groupId}-legend`}>{t("layers.mapGroup")}</legend>
        <div className="layer-folders">
          {folders.map(({ group, layers: inFolder }) => (
            <LayerFolder
              key={group.key}
              group={group}
              layers={inFolder}
              shown={shown}
              open={opened.includes(group.key)}
              onOpen={(open) => openFolder(group.key, open)}
              onToggle={toggle}
              extras={extras[group.key]}
            />
          ))}
        </div>
        {truncated.length > 0 && (
          <p className="muted" role="status">
            {t("layers.truncated", {
              names: [...new Set(truncated.map((l) => localized(l.name, lang)))].join(t("common.listSeparator")),
            })}
          </p>
        )}
        {failed && <ErrorBox error={failed.error} onRetry={() => void failed.refetch()} />}
      </fieldset>
    );

  return { controls, pois, shapes, activeLayers: active };
}
