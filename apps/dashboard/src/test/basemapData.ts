import type { Basemap, BasemapSettings } from "../lib/basemap";

/** Satellite background data shared by the unit tests and the accessibility run. */

const open = {
  tiles: ["https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg"],
  attribution: "Sentinel-2 cloudless – s2maps.eu by EOX IT Services GmbH",
  max_zoom: 15,
};

export const BASEMAP: Basemap = {
  source: "open",
  satellite: open,
  labels: { tiles: ["https://a.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}.png"], attribution: "© CARTO", max_zoom: 20 },
  open,
};

export const BASEMAP_SETTINGS: BasemapSettings = {
  configured: true,
  provider: "esri",
  url_template: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?token={key}",
  key_hint: "••••9f3a",
  key_header: null,
  attribution: "Esri, Maxar, Earthstar Geographics",
  max_zoom: 19,
  enabled: false,
  last_test_ok: true,
  last_test_at: "2026-10-28T08:10:00Z",
  updated_by_name: "مدير المنظومة",
  updated_at: "2026-10-28T08:09:00Z",
};
