import { keepPreviousData, useQueries, useQuery } from "@tanstack/react-query";
import type { FeatureCollection } from "geojson";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import type { BBox } from "../lib/filters";
import { useLanguage } from "../lib/hooks";
import {
  clusterPoints,
  formatPhone,
  isLayerIcon,
  LAYER_ICON_PATHS,
  type LayerFeature,
  type MapLayer,
} from "../lib/layers";
import { layerKeys } from "../lib/layersApi";
import { localized } from "../lib/localized";
import { SimTag } from "./StreamBits";
import { ErrorBox } from "./Feedback";
import type { MapPoi } from "./MapView";

const STORE_KEY = "ehimaya.mapDataLayers";
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
 * existing layers; places in the visible area, grouped when there are many.
 */
export function useMapDataLayers(bbox: BBox | null) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const groupId = useId();
  const [picked, setPicked] = useState<string[] | null>(storedKeys);
  const layersQuery = useQuery({ queryKey: layerKeys.all, queryFn: ({ signal }) => api.layers(signal) });
  const layers = useMemo(() => (layersQuery.data?.items ?? []).filter((l) => l.enabled), [layersQuery.data]);
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

  const toggle = (key: string, on: boolean) => {
    const next = on ? [...shown.filter((k) => k !== key), key] : shown.filter((k) => k !== key);
    setPicked(next);
    storeKeys(next);
  };

  const truncated = [
    ...active.filter((_, i) => featureQueries[i]?.data?.truncated),
    ...withShapes.filter((_, i) => shapeQueries[i]?.data?.truncated),
  ];
  const failed = featureQueries.find((q) => q.isError) ?? shapeQueries.find((q) => q.isError);

  const controls =
    layers.length === 0 ? null : (
      <fieldset className="map-data-layers">
        <legend id={`${groupId}-legend`}>{t("layers.mapGroup")}</legend>
        {layers.map((layer) => (
          <label key={layer.key} className="checkbox">
            <input
              type="checkbox"
              checked={shown.includes(layer.key)}
              onChange={(e) => toggle(layer.key, e.target.checked)}
            />
            <LayerSwatch layer={layer} />
            <span dir="auto">{localized(layer.name, lang)}</span>
            {layer.audience === "staff" && <span className="chip">{t("layers.audience.staff")}</span>}
            {layer.simulated && <SimTag label={t("layers.simulated")} />}
          </label>
        ))}
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
