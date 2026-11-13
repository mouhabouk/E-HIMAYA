# ML: every map datum is a layer of the interactive map

Request (Yamen, 2026-11-13): any data drawn on any map of the system is also an optional layer of the interactive map
(`/map`), without removing it from its source screen. No duplication: the information can be reached from more than
one place. Standing rule in `CLAUDE.md` ("integration first"). Approved mockup:
`additions/19-map-layers/` in the project files; full delegation to implement given the same day.

## Inventory

19 screens of the dashboard draw a map. Twelve draw data that can be a layer; seven show a single record (report,
intervention, geocoding queue, room report, institution, alert area drawing, délégation picker) whose record is
already in a layer.

| Folder (panel of `/map`) | Layer | Source screen (kept) | Request reused | Gate |
|---|---|---|---|---|
| البلاغات والتدخّلات `ops_reports` | Open interventions (new) | `/incidents` | `api.incidents` | map readers |
| | Hotspots, 7 days, 1 km (new) | `/analytics`, ops room | `api.analyticsHotspots` (same cache key) | `canReadAnalytics` |
| الإنذار والتحذيرات `warnings` | Active alerts (moved) | `/notifications` | `api.activeAlerts` | map readers |
| | Address warnings (moved, OS8-1 hook) | `/address-warnings` | `api.awMarkers` | `canReadAddressWarnings` |
| الأزمات والمحاور `crisis` | Open axes: areas, shelters, evacuation zones (new) | `/disasters` | `api.crisisAxes` + `api.disasterMap` | `canOpenDisasters` |
| | People and places exposed (moved, OS14 hook) | `/disasters`, axis tab | `api.crisisExposureMap` | `canOpenDisasters` |
| موارد الحماية المدنية `civil_protection` | Units and resources, register search (kept) | `/resources` | `api.resourcesMap` | `canReadResources` |
| | Ready volunteers (moved) | `/volunteers` | `api.volunteersMap` | map readers |
| الرصد والاستشعار `monitoring` | Sensors, towers, drones (moved) | their pages | `api.sensors`, `api.towers`, `api.drones` | their gates |
| | Live streams and cameras (new) | `/streams/wall` | `api.streams` (live) | map readers |
| | Weather (moved) | the map itself | weather grid | map readers |
| الوقاية والمؤسسات `prevention` | Institutions (moved) | `/orgs` | `api.orgsMap` | `canReadOrgs` |
| المواسم والسواحل `seasons` | Beaches and risk flags (new) | `/coastal` | `api.coastalOverview` | `canOpenCoastal` |

Prevention programmes were already a file layer (`programme.layer_key`). Not done here because they need the
administrative fill the map already uses for boundaries: the SNACR choropleth and the level of the gouvernorats of the
command screen (the axis areas carry the level). Data with coordinates that no map draws yet (inspection sites, last
vehicle positions, PAR teams, OS3 coverage) are proposed for later.

## Rules

- A layer reads the very request of its source screen, with the same permissions; the server scopes by gouvernorat
  (row level security). Nothing is copied or entered twice; changes are made at the source.
- A layer shows in the panel only to the roles that can read its source.
- Address warnings: personal marks are a total count only (no point, no count per délégation), as approved in OS8-1.
- Each layer carries a link "المصدر: …" to its source screen; each source screen has «اعرضها على الخريطة التفاعلية»,
  which opens `/map?layers=<id>` with the layer on and its folder open.
- The switches above the map moved into the folders; the row keeps the legend and the basemap.
- The folders show before the administrator creates them (`SYSTEM_GROUPS` in `MapDataLayers.tsx`); a folder created
  with the same key in the layers page takes over its name, icon, colour and place.

## Code

- `apps/dashboard/src/components/SystemLayers.tsx`: one hook per new layer, `layersFromUrl`, `MAP_LAYER_IDS`.
- `apps/dashboard/src/components/MapLayerLink.tsx`: the button of the source screens (12 screens).
- `apps/dashboard/src/components/MapDataLayers.tsx`: `SYSTEM_GROUPS`, `FolderExtra.source`.
- `apps/dashboard/src/pages/MapPage.tsx`: the folders, `?layers=`.
- Tests: `e2e/phase-ml.spec.ts`; the map specs open the folder before ticking a layer.
- No API change, no migration, no new package or setting.
