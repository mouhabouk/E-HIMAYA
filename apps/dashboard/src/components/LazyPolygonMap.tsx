import { lazy } from "react";

/** MapLibre is large: the area drawing map is loaded only when an alert area is drawn or shown. */
export const LazyPolygonDrawMap = lazy(() =>
  import("./PolygonDrawMap").then((m) => ({ default: m.PolygonDrawMap })),
);
