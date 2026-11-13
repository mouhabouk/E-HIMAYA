/**
 * A map background drawn from the repository's own geodata (gouvernorats, délégations, lakes and lagoons, wadis,
 * railways, forests), since the browser tests reach no tile server: for the pictures of the phase reports.
 */
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import type { Page } from "@playwright/test";
import { E2E_ENV } from "../playwright.config";
import { json } from "./phase7Helpers";

const ROOT = "../..";
const GEO = "http://tiles.e2e.test/geo";

const seed = (name: string) => readFileSync(`${ROOT}/services/api/seed/geo/admin/${name}.geojson.gz`);
const osm = (name: string) => readFileSync(`${ROOT}/data/osm/layers/${name}_enriched.geojson`);
const GEO_FILES: Record<string, () => Buffer> = {
  governorates: () => gunzipSync(seed("governorates")),
  delegations: () => gunzipSync(seed("delegations")),
  water: () => gunzipSync(seed("water")),
  rivers: () => osm("rivers"),
  railways: () => osm("railways"),
  forests: () => osm("forests"),
};

export const GEO_STYLE = {
  version: 8,
  sources: Object.fromEntries(Object.keys(GEO_FILES).map((k) => [k, { type: "geojson", data: `${GEO}/${k}.json` }])),
  layers: [
    { id: "sea", type: "background", paint: { "background-color": "#cfe1ef" } },
    { id: "land", type: "fill", source: "governorates", paint: { "fill-color": "#f6f3ec" } },
    { id: "forests", type: "fill", source: "forests", paint: { "fill-color": "#cfe5c4", "fill-opacity": 0.8 } },
    { id: "water", type: "fill", source: "water", paint: { "fill-color": "#b9d4ea" } },
    { id: "rivers", type: "line", source: "rivers", paint: { "line-color": "#8fb8dc", "line-width": 0.8 } },
    { id: "rail", type: "line", source: "railways", paint: { "line-color": "#9aa0aa", "line-width": 1, "line-dasharray": [3, 2] } },
    { id: "delegations", type: "line", source: "delegations", paint: { "line-color": "#d3cfc4", "line-width": 0.5 } },
    { id: "governorates", type: "line", source: "governorates", paint: { "line-color": "#a7a194", "line-width": 1.2 } },
  ],
};

/** Serves the style and its geodata to the page (call after `baseMock`, whose plain style it replaces). */
export async function routeGeoStyle(page: Page): Promise<void> {
  await page.route(E2E_ENV.VITE_MAP_STYLE_URL, (route) => json(route, GEO_STYLE));
  await page.route(`${GEO}/*.json`, (route) => {
    const name = new URL(route.request().url()).pathname.split("/").pop()?.replace(".json", "") ?? "";
    const file = GEO_FILES[name];
    return file ? route.fulfill({ status: 200, contentType: "application/json", body: file() }) : route.abort();
  });
}
