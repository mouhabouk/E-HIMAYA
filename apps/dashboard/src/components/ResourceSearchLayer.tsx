// covers: phase R2 (docs/phase-r/design-resources.md §2.4): a resources search sent from the register to the map. It is
// a layer of the «موارد الحماية المدنية» folder (not one more switch in a flat list): each gouvernorat coloured by its
// count with the count written on it, and the units with their counts once the map is close enough.
import { useQuery } from "@tanstack/react-query";
import type { Feature } from "geojson";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";
import { useServices } from "../context/services";
import type { BBox } from "../lib/filters";
import { useFormat, useLanguage } from "../lib/hooks";
import {
  COUNT_COLOURS,
  countClass,
  inventoryKeys,
  parseSearch,
  type Category,
  type SearchQuery,
} from "../lib/inventory";
import { categoryName } from "./InventoryForms";
import { ErrorBox } from "./Feedback";
import { zoomOf, type FolderExtra } from "./MapDataLayers";
import type { MapPoi } from "./MapView";

export const SEARCH_PARAM = "resources";
// From this zoom on (about one gouvernorat on screen) the units replace the gouvernorat counts.
const UNIT_ZOOM = 8;
const BUBBLE = "#00695A";

/** "Fire truck · capacity 2 000 L or more · 4x4": the search in words, for the folder and the result card. */
export function describeSearch(
  q: SearchQuery,
  category: Category | undefined,
  lang: "ar" | "fr" | "en",
  t: (key: string, options?: Record<string, unknown>) => string,
  number: (n: number) => string,
): string {
  const parts = [category ? categoryName(category, lang) : t(`inventory.tabs.${q.what}`)];
  for (const [key, condition] of Object.entries(q.specs)) {
    const def = category?.specs.find((d) => d.key === key);
    const name = def ? def.name[lang] || def.name.ar : key;
    if (typeof condition === "boolean") {
      parts.push(name);
      continue;
    }
    const [low, high] = condition;
    // "2 000 L" kept in one piece inside Arabic text (first-strong isolate).
    const unit = def?.unit ? ` ${def.unit}` : "";
    const iso = (n: number, u = "") => `\u2068${number(n)}${u}\u2069`;
    if (low !== null && high !== null) {
      parts.push(t("map.resourceSearch.between", { spec: name, low: iso(low), high: iso(high, unit) }));
    } else if (low !== null) parts.push(t("map.resourceSearch.atLeast", { spec: name, value: iso(low, unit) }));
    else if (high !== null) parts.push(t("map.resourceSearch.atMost", { spec: name, value: iso(high, unit) }));
  }
  if (q.min_level !== null) parts.push(t("map.resourceSearch.level", { level: number(q.min_level) }));
  if (q.valid_cert) parts.push(t("inventory.search.validCert"));
  if (q.ready_only) parts.push(t(`inventory.search.readyOnly.${q.what}`));
  return parts.join(" · ");
}

export function useResourceSearchLayer(bbox: BBox | null) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const [params, setParams] = useSearchParams();
  const raw = params.get(SEARCH_PARAM);
  const search = useMemo(() => parseSearch(raw), [raw]);
  const [on, setOn] = useState(true);
  const visible = search !== null && on;

  const result = useQuery({
    queryKey: search ? inventoryKeys.search(search) : ["inventory", "search", "none"],
    enabled: search !== null,
    queryFn: ({ signal }) => {
      if (!search) throw new Error("no search");
      return api.searchInventory(search, signal);
    },
  });
  const outlines = useQuery({
    queryKey: inventoryKeys.boundaries,
    enabled: search !== null,
    staleTime: Infinity,
    queryFn: ({ signal }) => api.inventoryBoundaries(signal),
  });
  const catalogue = useQuery({
    queryKey: inventoryKeys.catalogue,
    enabled: search !== null,
    queryFn: ({ signal }) => api.inventoryCatalogue(signal),
  });
  const category = catalogue.data?.items.find((c) => c.key === search?.category);
  const label = search ? describeSearch(search, category, lang, t, (n) => fmt.number(n)) : "";
  const readyLabel = search ? t(`inventory.search.ready.${search.what}`) : "";

  const gouvernorats = useMemo(() => result.data?.gouvernorats ?? [], [result.data]);
  const max = Math.max(0, ...gouvernorats.map((g) => g.total));

  const shapes = useMemo<Feature[]>(() => {
    if (!visible) return [];
    const counts = new Map(gouvernorats.map((g) => [g.code, g.total]));
    return (outlines.data?.features ?? [])
      .filter((f) => counts.has(Number(f.id)))
      .map((f) => ({
        type: "Feature" as const,
        id: `resources-${String(f.id)}`,
        geometry: f.geometry,
        properties: {
          colour: COUNT_COLOURS[countClass(counts.get(Number(f.id)) ?? 0, max)],
          opacity: 0.45,
          layer: "resources-search",
        },
      }));
  }, [visible, gouvernorats, outlines.data, max]);

  const zoom = bbox ? zoomOf(bbox) : 0;
  const pois = useMemo<MapPoi[]>(() => {
    if (!visible) return [];
    const out: MapPoi[] = [];
    for (const g of gouvernorats) {
      if (g.total === 0) continue;
      const name = lang === "ar" ? g.name_ar : lang === "fr" ? g.name_fr : g.name_en;
      if (zoom < UNIT_ZOOM) {
        if (g.lat === null || g.lon === null) continue;
        out.push({
          id: `resources-g-${g.code}`,
          lat: g.lat,
          lon: g.lon,
          kind: "place_cluster",
          colour: BUBBLE,
          count: g.total,
          title: t("map.resourceSearch.place", { name, total: fmt.number(g.total) }),
          details: [
            t("inventory.search.readyCount", { label: readyLabel, ready: fmt.number(g.ready) }),
            t("inventory.search.unitsOf", { count: fmt.number(g.units.length) }),
          ],
        });
        continue;
      }
      for (const u of g.units) {
        if (u.lat === null || u.lon === null) continue;
        out.push({
          id: `resources-u-${u.id}`,
          lat: u.lat,
          lon: u.lon,
          kind: "place_cluster",
          colour: BUBBLE,
          count: u.total,
          title: t("map.resourceSearch.place", {
            name: lang === "ar" ? u.name_ar : u.name_fr || u.name_ar,
            total: fmt.number(u.total),
          }),
          details: [t("inventory.search.readyCount", { label: readyLabel, ready: fmt.number(u.ready) }), name],
        });
      }
    }
    return out;
  }, [visible, gouvernorats, zoom, lang, t, fmt, readyLabel]);

  const clear = () => {
    const next = new URLSearchParams(params);
    next.delete(SEARCH_PARAM);
    setParams(next, { replace: true });
  };

  const found = gouvernorats.filter((g) => g.total > 0).length;
  // The counts each colour stands for (classes of a quarter of the largest count; empty classes left out).
  const legend = COUNT_COLOURS.map((colour, i) => ({
    colour,
    low: i === 0 ? 0 : Math.floor(((i - 1) * max) / 4) + 1,
    high: i === 0 ? 0 : Math.floor((i * max) / 4),
  })).filter((c) => c.low <= c.high);
  const note = (
    <div className="resource-search">
      {result.isError && <ErrorBox error={result.error} onRetry={() => void result.refetch()} />}
      {result.data && (
        <p role="status">
          {t("inventory.search.total", { total: fmt.number(result.data.total) })}
          {" · "}
          {t("inventory.search.readyCount", { label: readyLabel, ready: fmt.number(result.data.ready) })}
          {" · "}
          {t("inventory.search.inGouvernorats", { count: fmt.number(found) })}
        </p>
      )}
      <ul className="resource-search__legend" aria-label={t("map.resourceSearch.legend")}>
        {legend.map(({ colour, low, high }) => (
          <li key={colour}>
            <span className="resource-search__swatch" style={{ background: colour }} aria-hidden="true" />
            {low === 0
              ? t("map.resourceSearch.none")
              : low === high
                ? fmt.number(low)
                : t("map.resourceSearch.range", { low: fmt.number(low), high: fmt.number(high) })}
          </li>
        ))}
      </ul>
      <p className="muted">{t(zoom < UNIT_ZOOM ? "map.resourceSearch.zoomHint" : "map.resourceSearch.unitsHint")}</p>
      <div className="actions">
        <Link className="btn btn--small" to="/inventory">
          {t("map.resourceSearch.edit")}
        </Link>
        <button type="button" className="btn btn--small" onClick={clear}>
          {t("map.resourceSearch.clear")}
        </button>
      </div>
    </div>
  );

  const extra: FolderExtra | null = search
    ? { key: "resources-search", label: t("map.resourceSearch.layer", { search: label }), on, onChange: setOn, note, reveal: true }
    : null;
  return { extra, pois, shapes };
}
