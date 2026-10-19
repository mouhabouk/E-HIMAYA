import { lazy, Suspense } from "react";
import { useServices } from "../context/services";
import { useLanguage } from "../lib/hooks";
import { directionOf } from "../i18n";
import { Loading } from "./Feedback";
import type { MapViewProps } from "./MapView";

/** MapLibre is large: load it only on screens that show a map. */
const LazyMapView = lazy(() => import("./MapView").then((m) => ({ default: m.MapView })));

/** Map with the configured style and the document direction (controls on the inline-end side). */
export function MapPanel(props: Omit<MapViewProps, "styleUrl" | "dir">) {
  const { mapStyleUrl } = useServices();
  const lang = useLanguage();
  return (
    <Suspense fallback={<Loading />}>
      <LazyMapView {...props} styleUrl={mapStyleUrl} dir={directionOf(lang)} />
    </Suspense>
  );
}
