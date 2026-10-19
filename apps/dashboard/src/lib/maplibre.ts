/**
 * MapLibre GL JS entry point for the dashboard. Since v6 MapLibre ships as ES modules only and, under a bundler,
 * needs the URL of its worker: Vite's `?worker&url` emits a self-contained, same-origin worker chunk (no `blob:`
 * worker is needed in the CSP). Every map component imports MapLibre from here so the URL is set once.
 */
import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);

export { maplibregl };
