import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { MapPoi, MapPolygon } from "../components/MapView";
import { iconPathOf } from "../components/MapDataLayers";
import { useServices } from "../context/services";
import { crisisKeys, DRAWN_GROUPS, EXPOSURE_CORE, EXPOSURE_GROUPS, EXPOSURE_RING, type Exposure, type ExposureGroupKey } from "./crisis";

/**
 * OS14: the people and places exposed on the area of a crisis axis, drawn on a map. The estimate is computed and
 * kept by the axis (tab «المعرّضون للخطر»); the maps only read it: the axis map, and the optional layer
 * «المعرّضون للخطر» of the interactive map (/map), which reads the latest estimate of every open axis the user sees.
 */

const GROUP_ICON: Record<ExposureGroupKey, string> = {
  health: "hospital",
  elderly: "shelter",
  education: "school",
  hazardous: "fuel",
  transport: "pin",
  gathering: "pin",
};

export function exposureRingPolygons(e: Exposure): MapPolygon[] {
  if (!e.ring) return [];
  const polygons = e.ring.type === "Polygon" ? [e.ring.coordinates] : e.ring.coordinates;
  return polygons.map((rings, n) => ({
    id: `exposure-${e.axis_id}-${n}`,
    coordinates: rings as [number, number][][],
    tone: "medium",
    colour: EXPOSURE_RING,
    outline: "dashed",
  }));
}

export function useExposurePois(): (e: Exposure) => MapPoi[] {
  const { t } = useTranslation();
  return (e: Exposure) =>
    EXPOSURE_GROUPS.filter((g) => DRAWN_GROUPS.includes(g)).flatMap((g) =>
      e.groups[g].items.map((p, n) => ({
        id: `exposure-${e.axis_id}-${g}-${n}`,
        lon: p.lon,
        lat: p.lat,
        kind: "place" as const,
        title: p.name,
        subtitle: [t(`crisis.exposure.group.${g}`), t(`crisis.exposure.zone.${p.zone}`), e.axis_number].join(" · "),
        iconPath: iconPathOf(GROUP_ICON[g]),
        colour: p.zone === "core" ? EXPOSURE_CORE : EXPOSURE_RING,
        href: `/axes/${e.axis_id}?tab=exposure`,
      })),
    );
}

/** The optional layer of the interactive map: rings and sensitive places of every open axis's latest estimate. */
export function useExposureLayer(enabled: boolean): { pois: MapPoi[]; polygons: MapPolygon[]; items: Exposure[]; isError: boolean } {
  const { api } = useServices();
  const toPois = useExposurePois();
  const q = useQuery({
    queryKey: crisisKeys.exposureMap,
    enabled,
    queryFn: ({ signal }) => api.crisisExposureMap(signal),
    refetchInterval: 60_000,
  });
  return useMemo(() => {
    const items = enabled ? (q.data ?? []) : [];
    return {
      items,
      pois: items.flatMap(toPois),
      polygons: items.flatMap(exposureRingPolygons),
      isError: q.isError,
    };
    // toPois changes with the language only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, q.data, q.isError]);
}
