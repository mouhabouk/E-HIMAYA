import { keepPreviousData, useQueries, useQuery } from "@tanstack/react-query";
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

function storedKeys(): string[] {
  try {
    const raw = sessionStorage.getItem(STORE_KEY);
    const v: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(v) ? v.filter((k): k is string => typeof k === "string") : [];
  } catch {
    return [];
  }
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
  const [shown, setShown] = useState<string[]>(storedKeys);
  const layersQuery = useQuery({ queryKey: layerKeys.all, queryFn: ({ signal }) => api.layers(signal) });
  const layers = useMemo(() => (layersQuery.data?.items ?? []).filter((l) => l.enabled), [layersQuery.data]);
  const active = useMemo(() => layers.filter((l) => shown.includes(l.key)), [layers, shown]);

  const featureQueries = useQueries({
    queries: active.map((layer) => ({
      queryKey: layerKeys.features(layer.key, bbox),
      enabled: bbox !== null,
      placeholderData: keepPreviousData,
      queryFn: ({ signal }: { signal: AbortSignal }) => api.layerFeatures(layer.key, bbox, signal),
    })),
  });

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
    setShown(next);
    storeKeys(next);
  };

  const truncated = active.filter((_, i) => featureQueries[i]?.data?.truncated);
  const failed = featureQueries.find((q) => q.isError);

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
            {t("layers.truncated", { names: truncated.map((l) => localized(l.name, lang)).join(t("common.listSeparator")) })}
          </p>
        )}
        {failed && <ErrorBox error={failed.error} onRetry={() => void failed.refetch()} />}
      </fieldset>
    );

  return { controls, pois, activeLayers: active };
}
