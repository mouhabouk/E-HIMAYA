import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import {
  AW_GROUPS,
  AW_MAP_COLOURS,
  AW_MAP_ICONS,
  AW_MAP_WARNING,
  awKeys,
  type AwCategory,
  type AwMarker,
} from "../lib/addressWarnings";
import type { BBox } from "../lib/filters";
import { useFormat } from "../lib/hooks";
import type { MapPoi } from "./MapView";
import { zoomOf } from "./MapDataLayers";

export type AwGroup = "all" | keyof typeof AW_GROUPS | "late";
const GROUPS: AwGroup[] = ["all", "haz", "bld", "ppl", "late"];
/** Below this zoom the marks are grouped by cells of the visible area (the gouvernorat's view). */
const GROUP_BELOW_ZOOM = 12;
const CELLS = 10;

function inGroup(m: AwMarker, group: AwGroup): boolean {
  if (group === "all") return true;
  if (group === "late") return m.review_due;
  return AW_GROUPS[group].includes(m.category);
}

/** Highest first: a mark past its review date, then the hazards, the buildings, the rest. */
function weight(m: AwMarker): number {
  if (m.review_due) return 4;
  if (AW_GROUPS.haz.includes(m.category)) return 3;
  if (AW_GROUPS.bld.includes(m.category)) return 2;
  return 1;
}

/**
 * OS8-1 (docs/phase-os8/design-os8.md §8): the address warnings on the room's map. The active marks of the room's
 * register (the central room: every one), filtered by group; grouped by cells with their count when the map shows a
 * whole gouvernorat, one by one closer. Personal marks are never on the layer: only their count, beside the switch;
 * they stay in the file of a nearby incident, without a name.
 */
export function useAddressWarningsLayer(bbox: BBox | null, enabled: boolean) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const [group, setGroup] = useState<AwGroup>("all");
  const marks = useQuery({
    queryKey: awKeys.markers(""),
    enabled,
    queryFn: ({ signal }) => api.awMarkers("", signal),
  });
  const cats = useQuery({ queryKey: awKeys.categories, enabled, queryFn: ({ signal }) => api.awCategories(signal) });
  const byKey = useMemo(() => new Map<string, AwCategory>((cats.data ?? []).map((c) => [c.key, c])), [cats.data]);
  const active = useMemo(() => (marks.data?.items ?? []).filter((m) => m.status === "active"), [marks.data]);
  const shown = useMemo(() => active.filter((m) => inGroup(m, group)), [active, group]);

  const pois = useMemo<MapPoi[]>(() => {
    if (!enabled || !bbox) return [];
    const inside = shown.filter(
      (m) => m.location.lon >= bbox[0] && m.location.lon <= bbox[2] && m.location.lat >= bbox[1] && m.location.lat <= bbox[3],
    );
    const point = (m: AwMarker): MapPoi => {
      const c = byKey.get(m.category);
      return {
        id: `aw-${m.id}`,
        lon: m.location.lon,
        lat: m.location.lat,
        kind: m.review_due ? "aw_due" : "aw",
        title: c?.name ?? t("addressWarnings.layer.mark"),
        subtitle: [m.address, m.review_due ? t("addressWarnings.status.review_due") : null].filter(Boolean).join(" · "),
        iconPath: (c && AW_MAP_ICONS[c.icon]) || AW_MAP_WARNING,
        colour: (c && AW_MAP_COLOURS[c.colour]) || AW_MAP_COLOURS.amber,
        href: "/address-warnings",
        details: [
          m.description,
          `${t("addressWarnings.layer.circle")}: ${fmt.number(c?.radius_m ?? 0)} ${t("addressWarnings.layer.metres")}`,
          `${t("addressWarnings.col.review")}: ${fmt.date(m.review_on)}`,
          `${t("addressWarnings.col.source")}: ${t(`addressWarnings.source.${m.source}`)}${m.source_ref ? ` · ${m.source_ref}` : ""}`,
        ],
      };
    };
    if (zoomOf(bbox) >= GROUP_BELOW_ZOOM) return inside.map(point);
    // The gouvernorat's view: one point per cell of the visible area, its count, the colour of its heaviest mark.
    const w = (bbox[2] - bbox[0]) / CELLS || 1;
    const h = (bbox[3] - bbox[1]) / CELLS || 1;
    const cells = new Map<string, AwMarker[]>();
    for (const m of inside) {
      const key = `${Math.floor((m.location.lon - bbox[0]) / w)}:${Math.floor((m.location.lat - bbox[1]) / h)}`;
      cells.set(key, [...(cells.get(key) ?? []), m]);
    }
    return [...cells.entries()].map(([key, list]) => {
      if (list.length === 1) return point(list[0] as AwMarker);
      const top = list.reduce((a, b) => (weight(b) > weight(a) ? b : a));
      const due = list.filter((m) => m.review_due).length;
      const c = byKey.get(top.category);
      return {
        id: `aw-cell-${key}`,
        lon: list.reduce((s, m) => s + m.location.lon, 0) / list.length,
        lat: list.reduce((s, m) => s + m.location.lat, 0) / list.length,
        kind: "aw_cluster",
        title: t("addressWarnings.layer.cluster", { n: fmt.number(list.length) }),
        subtitle: due ? t("addressWarnings.layer.clusterDue", { n: fmt.number(due) }) : undefined,
        colour: top.review_due ? "#B3121A" : (c && AW_MAP_COLOURS[c.colour]) || AW_MAP_COLOURS.amber,
        count: list.length,
        details: [...new Set(list.map((m) => byKey.get(m.category)?.name ?? m.category))].slice(0, 6),
      };
    });
  }, [enabled, bbox, shown, byKey, t, fmt]);

  const due = active.filter((m) => m.review_due).length;
  const controls = enabled ? (
    <div className="aw-layer" role="group" aria-label={t("addressWarnings.layer.groups")}>
      {GROUPS.map((g) => (
        <button key={g} type="button" className="btn btn--small" aria-pressed={group === g} onClick={() => setGroup(g)}>
          {t(`addressWarnings.layer.group.${g}`)}
          {g === "late" && due > 0 && <span className="aw-layer__count">{fmt.number(due)}</span>}
        </button>
      ))}
      <span className="muted" role="status" aria-live="polite">
        {marks.isFetching
          ? t("common.loading")
          : t("addressWarnings.layer.count", { n: fmt.number(shown.length) })}
        {marks.data && marks.data.counts.personal > 0 && (
          <> · {t("addressWarnings.layer.personal", { n: fmt.number(marks.data.counts.personal) })}</>
        )}
      </span>
    </div>
  ) : null;
  return { pois, controls };
}
