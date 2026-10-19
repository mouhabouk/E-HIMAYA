import { lazy } from "react";

/** MapLibre is large: load it only on screens that show a map. */
export const LazyMapView = lazy(() => import("./MapView").then((m) => ({ default: m.MapView })));
