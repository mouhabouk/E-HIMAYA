# Weather layer and spread forecasts (phase 7 §1–§2)

Modules `services/api/app/modules/weather` and `services/api/app/modules/forecast`, migration `0012_weather` (schemas
`weather` and `forecast`). Contract: `docs/api/phase-7-contract.md` §1–§2. Every number here is an aid to a human
decision: a weather threshold produces a *suggested* alert that an editor reviews, and a forecast is a drawing with its
inputs, assumptions and a disclaimer. Nothing is sent or dispatched on its own.

| Endpoint | Roles | Limit |
|---|---|---|
| `GET /api/v1/weather?lat=&lon=` | public | 60 / min / client; `Cache-Control: public, max-age=60` |
| `GET /api/v1/staff/weather/grid?bbox=&hour=` | any staff role | — |
| `GET /api/v1/staff/weather/at?lat=&lon=` | any staff role | — |
| `GET /api/v1/staff/weather/suggestions?status=` | content editor, ops manager, committees (scope) | — |
| `POST /api/v1/staff/weather/suggestions/{id}/accept` · `/dismiss` `{"reason"}` | same | — |
| `GET` · `PUT /api/v1/staff/weather/rules` | read: staff; write: ops manager, committees | — |
| `POST /api/v1/staff/incidents/{id}/forecast/fire` · `/forecast/flood` | staff read roles, incident scope | 30 / 10 min / user |
| `GET /api/v1/staff/incidents/{id}/forecasts` | staff read roles, incident scope | — |

Errors: `422 invalid_bbox`, `404 no_weather_data` (no fetched grid point within `WEATHER_MAX_DISTANCE_KM`),
`503 weather_unavailable` (public card or forecast without weather data), `409 incident_without_location`,
`409 suggestion_not_pending`, `422 duplicate_metric|invalid_threshold|national_rules_incomplete`, `403 out_of_scope`,
`404` for an incident or suggestion outside the user's scope.

## 1. Sources and licences

| What | Source | Licence | How it is used |
|---|---|---|---|
| Hourly weather | [Open-Meteo](https://open-meteo.com) forecast API (`/v1/forecast`) | Data: **CC BY 4.0**, attribution "Weather data by Open-Meteo.com". The free endpoint is for **non-commercial** use only (10,000 calls/day, 5,000/h, 600/min). | HTTP client only, no code linked. Attribution in every API response and in the apps. |
| Open-Meteo server (option) | `open-meteo/open-meteo` | **AGPL-3.0** | Only as a separate self-hosted service reached over HTTP (`WEATHER_API_URL`); never linked into our services. |
| Terrain | [Copernicus DEM GLO-90](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) (`COP-DEM_GLO-90-DGED`), AWS Open Data copy `s3://copernicus-dem-90m` | "Licence for COP-DEM-GLO-90-F Global 90m Full, Free & Open": free of charge, worldwide, reproduction, distribution and adaptation allowed, with the notice below | Converted once into a volume; never committed. |
| FWI, Rothermel, ellipse | Published equations (references in §3–§4) | — | Implemented in-house in Python (standard library only); no third-party code copied. |

GLO-90 notice, carried in every forecast that used the terrain (`attribution`): "produced using Copernicus
WorldDEM-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the
European Union and ESA; all rights reserved".

No new Python dependency and no new container image: the weather client uses `httpx` (already locked), the terrain
installer runs in the API image.

## 2. Weather layer

### Grid and refresh

`ensure_grid` lays a 0.25° grid over Tunisia on first start: every node within ≈ 10 km of a gouvernorat boundary,
plus one point inside any gouvernorat too small to hold a node (Tunis) — **285 points, all 24 gouvernorats**. Each
point carries its gouvernorat (the nearest boundary).

The worker loop `weather-grid` runs every `WEATHER_REFRESH_INTERVAL_S` (1800 s). A cycle claims at most
`WEATHER_MAX_POINTS_PER_CYCLE` (160) points whose `next_fetch_at` is due (`FOR UPDATE SKIP LOCKED`, 15-min lease, so
several workers never fetch the same point), fetches them in batches of `WEATHER_BATCH_SIZE` (50) coordinates per
request, stores the hourly series (yesterday + 3 days ahead) and sets `next_fetch_at` one hour
(`WEATHER_FETCH_MIN_AGE_S`) later. A failed batch backs off (5 min doubling, at most 6 h) without blocking the rest;
the report path never waits on the weather.

Request volume against Open-Meteo, with 7 hourly variables (weight 1 per location for ≤ 14 days):

* steady state: 285 points × 24 refreshes = **≈ 6,840 calls/day**, ≈ 285/h, ≤ 160 per 30-min cycle (in 4 requests);
* first start: one spin-up of `WEATHER_SPINUP_DAYS` (30) past days per point so the FWI codes start from a month of
  weather, ≈ 2.4 calls per point = ≈ 680 calls once.

This fits the free tier's limits, but the free tier is non-commercial: see §6 for the operational options.

The client sends `timezone=GMT`, `timeformat=unixtime`, `wind_speed_unit=kmh`, 20 s timeout, 3 attempts with back-off;
`429` stops the cycle (`WeatherRateLimited`) and the points are retried later. A self-hosted or commercial endpoint
takes the same parameters (`apikey` is added when `WEATHER_API_KEY` is set).

### Simulator

┏━━ SIMULATION ━━ `WEATHER_PROVIDER` empty → `sim` in development and CI, `open-meteo` with `APP_ENV=production`
(which refuses `sim`). The simulator (`provider.simulated_hour`) is deterministic in (lat, lon, hour): a diurnal
cycle, a north–south gradient, a sirocco day every 5 days (hot, dry, windy: high fire danger) and a storm day every
7 days (heavy rain, gusts), so suggestions and forecasts can be demonstrated offline. Simulated rows are flagged
`simulated`, every response carries `"simulated": true` and the attribution "[SIM] Simulated weather…", and logs use
`[SIM]`. ┗━━

### Derived indices

* **Fire danger** — Canadian FWI System (§3) from the noon values of each day (11:00 UTC = noon local standard time),
  carried day to day in `weather.grid_point.codes`; every hour of a day shows that day's indices. Classes on the FWI,
  with the EFFIS thresholds used for the Mediterranean: `low` < 5.2 ≤ `moderate` < 11.2 ≤ `high` < 21.3 ≤
  `very_high` < 38.0 ≤ `extreme`.
* **Heavy rain** — `warning` when the hour's rain ≥ 20 mm or the last 24 h ≥ 50 mm, `watch` from half of that
  (10 mm/h, 30 mm/24 h), else `none`.

### Suggested alerts

After each refresh the rules (`weather.rule`, national defaults overridable per gouvernorat) are checked on the next
24 h: `fire_danger ≥ very_high`, `wind_gust ≥ 70 km/h`, `rain_24h ≥ 50 mm` (severity medium), `rain_1h ≥ 20 mm`
(high). Exceedances are grouped by metric and severity into one suggestion listing the gouvernorats, with prefilled
ar/fr/en texts (local times, the 198 number), the evidence (`max_value`, peak time and point, per-gouvernorat values,
thresholds, rule ids) and a validity window; a gouvernorat already covered by an active suggestion of the same metric
is not suggested again. Each suggestion emits the live event `weather.suggestion` (to editors in scope).

**Accept** marks it accepted, audits it and returns the phase 5 alert form prefilled (`alert_form`, a valid
`MessageIn`, limited to the editor's own gouvernorat for a local editor). Nothing is created or sent: the editor
reviews the form and publishes through the existing alert endpoints. **Dismiss** needs a reason (3–500 characters).
Pending suggestions expire at `valid_until`.

### Priority (BR-20)

The `weather` component of the priority score reads the report's nearest fetched grid point at the current hour:
fire reports → fire danger class (low 0 … extreme 1); flood reports → heavy-rain level of the next 6 h (none 0,
watch 0.5, warning 1); other reports → strongest gust of the next 3 h (40 km/h → 0, 100 km/h → 1). It is a bonus
component: it can raise a priority, never lower it. Without data it reports `no_weather_data`.

## 3. Fire Weather Index System

Van Wagner (1987), *Development and structure of the Canadian Forest Fire Weather Index System*, CFS Forestry
Technical Report 35 (equation numbers in `fwi.py`), with the numerically safer forms of Eqs. 12, 15 and 21 from Wang,
Anderson and Suddaby (2015), *Updated source code for calculating fire danger indices in the Canadian FWI System*,
NOR-X-424.

* FFMC: Eqs. 1–10; the moisture/FFMC constant is 147.2 (Van Wagner 1987). With it, **all 49 days of Table 7 of
  Wang et al. (2015)** — FFMC, DMC, DC, ISI, BUI and FWI — are reproduced to the published decimal
  (`tests/test_weather.py::test_fwi_reproduces_the_published_reference_table`); the later constant 147.27723 is off by 0.1 on some days.
* DMC: Eqs. 11–16 with the 46° N day-length factors (Tunisia lies at 30–37.5° N; the 20° N factors of Lawson and
  Armitage 2008 apply below 30° N). DC: Eqs. 18–23 with the northern-hemisphere factors.
* ISI, BUI, FWI: Eqs. 24–30.
* Start-up: FFMC 85, DMC 6, DC 15, then a 30-day spin-up from the past weather (§2).

## 4. Fire spread (`rothermel-elliptical-v1`)

### Rate of spread

Rothermel (1972), *A mathematical model for predicting fire spread in wildland fuels*, INT-115, for a
heterogeneous fuel bed (dead and live categories, size classes weighted by surface area, Albini 1976 for the live
moisture of extinction), with:

* the 13 fuel models of Anderson (1982), *Aids to determining fuel models*, INT-122, as tabulated by Andrews (2018,
  RMRS-GTR-371, table 8a);
* wind and slope effects added as vectors (Rothermel 1983, INT-143), which gives the heading and the effective wind;
* the wind limit of Andrews, Cruz and Rothermel (2013): U ≤ 96.8 · I_R^(1/3) ft/min (flagged in the assumptions);
* fireline intensity (Byram) with residence time 384/σ min, and flame length 0.0775 · I^0.46 (m, kW/m).

Validation (`tests/test_forecast.py`): characteristic SAV and relative packing ratio match table 8a of Andrews
(2018) for all 13 models; rates of spread against Anderson's (1982) table (8 % dead, 100 % live, 5 mi/h midflame,
flat):

| Model | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Anderson 1982 (ch/h) | 78 | 35 | 104 | 75 | 18 | 32 | 20 | 1.6 | 7.5 | 7.9 | 6 | 13 | 13.5 |
| This model (ch/h) | 81.1 | 32.5 | 102 | 71.4 | 14.5 | 29.6 | 26.1 | 1.8 | 7.6 | 7.9 | 5.6 | 11.9 | 14.2 |

All within 12 % except model 5 (−19 %), model 7 (+30 %) and model 8 (a rounded small value). Anderson's 1982 table
predates today's live-fuel handling (current BehavePlus results differ from it in the same direction for the
live-fuel models 5 and 7); models 5 and 7 are not used for Tunisia (below).

### Fuels

No land-cover layer is loaded yet, so the operator chooses the fuel (default `mixed`, stated as an assumption):

| `fuel_model` | Anderson model | Typical in Tunisia |
|---|---|---|
| `grass` | 1 short grass | cereal stubble, dry grassland |
| `shrub` | 4 chaparral | maquis, garrigue |
| `timber_litter` | 9 long-needle/hardwood litter, sheltered (wind factor 0.15) | Aleppo pine, cork oak stands |
| `mixed` | 2 timber with grass understory | open woodland with grass and shrubs |

### Inputs and assumptions

* Weather: the nearest grid point's current hour. 10 m wind → 20 ft wind ÷ 1.15, then the model's unsheltered wind
  adjustment factor (Andrews 2012, RMRS-GTR-266) to midflame. Fire spreads towards (wind direction + 180°).
* Dead fuel moisture from the day's FFMC (Van Wagner's FFMC→moisture inverse), +1 % and +2 % for the 10 h and 100 h
  classes; 8 % when no FFMC exists. Live moisture 80 % June–September, 120 % otherwise.
* Slope and upslope direction at the ignition point from the terrain model (Horn 1981, 3 × 3 cells, 90 m); slope 0
  and the assumption `no_terrain` when the model is not installed.
* Conditions uniform over the area and the horizon; no suppression, no fuel breaks.

### Shape

An ellipse per horizon (5–720 min, up to 6, default 30/60/120): length-to-breadth of Anderson (1983, INT-305)
`L/B = 0.936 e^(0.2566 U) + 0.461 e^(−0.1548 U) − 0.397` (U effective midflame wind in mi/h), capped at 8 as in
FARSITE; the ignition point is the rear focus, the head at ROS × t, the back at the backing rate × t. Each polygon is a
GeoJSON ring (48 vertices) with its area, head and back distances. The run (inputs, result, assumptions) is stored in
`forecast.run` and audited (`forecast.fire`).

## 5. Flood advisory (`rain-terrain-advisory-v1`)

Clearly labelled an **advisory, not a hydraulic model** (`"advisory": true` and the disclaimer).

* Rain at the nearest grid point: observed last 24 h, next 6/12/24 h, strongest hour.
* Level: `high` when observed + next 24 h ≥ 100 mm or an hour ≥ 30 mm; `moderate` ≥ 50 mm or ≥ 20 mm/h; `low` ≥ 20 mm
  or ≥ 10 mm/h; else `minimal`.
* Terrain (when installed): a 21 × 21 sample over the incident's area (its polygon's extent, else a 3 km circle);
  the least-squares plane gives the drainage direction and mean slope, local minima are the low points, and the
  lowest 20 % of the area (its convex hull) is the risk polygon. Without terrain the risk polygon is the whole area.
* Not modelled: river flow, drainage networks, dams, soil saturation. GLO-90 is a surface model (buildings, trees) at
  90 m, too coarse for streets.

## 6. Switching the weather source

| Option | Settings | Notes |
|---|---|---|
| Free Open-Meteo (default production) | `WEATHER_PROVIDER=open-meteo` | Non-commercial use only. |
| Open-Meteo commercial API | `WEATHER_API_URL=https://customer-api.open-meteo.com`, `WEATHER_API_KEY=<key>` | Same parameters, `apikey` sent. |
| Self-hosted Open-Meteo | `WEATHER_API_URL=http://<host>:8080` | Run the AGPL server as its own service (e.g. its Docker image with the ICON/ECMWF/Météo-France datasets for North Africa); it is only called over HTTP. |
| INM (Institut National de la Météorologie) | a new provider class | INM has no public API; with an agreement, implement `WeatherProvider.fetch()` in `weather/provider.py` (returns hourly `Series` per point) and select it in `get_provider()`. Indices, rules and forecasts are unchanged. |

## 7. Terrain model

```sh
docker compose -f infra/compose.yml --profile terrain run --rm terrain        # once per installation
# offline: put the 40 Copernicus_DSM_COG_30_*_DEM.tif files in a directory mounted into the container and add
#   --tiles /that/dir  (the same SHA-256 pins apply)
```

`app.modules.forecast.terrain_fetch` downloads the 40 one-degree tiles covering 30–38° N, 7–12° E (~150 MB) from
`https://copernicus-dem-90m.s3.amazonaws.com`, checks each against its pinned SHA-256 (`TILES`; any mismatch stops the
installation), decodes the Cloud Optimized GeoTIFFs with the standard library (deflate, floating-point predictor,
PixelIsPoint tie points) and writes `tunisia-glo90.i16` (int16 metres, 9600 × 6000 cells, 115 MB) and
`tunisia-glo90.json` (grid, raster SHA-256, licence, attribution) into the `terrain` volume. A re-run skips an
installed model (`--force` rebuilds). The API memory-maps the raster read-only at `TERRAIN_DIR` (`/terrain`); when the
volume is empty everything works with flat terrain and the explicit assumption. The production overlay must mount the
same volume into the api container (`terrain:/terrain:ro`).

## 8. Limits

* Grid resolution 0.25° (≈ 25 km): local winds (valleys, sea breeze) and convective rain are smoothed; a point
  more than 40 km from any fetched node gets no weather.
* The FWI System was calibrated on Canadian pine stands; EFFIS classes are the usual Mediterranean adaptation,
  not a Tunisian calibration.
* Fire spread is a surface fire, homogeneous fuel and constant weather model: no crown fire, spotting, terrain
  channelling, fuel breaks or suppression. It is meant for the first hours, and is not accurate beyond that.
* No land-cover layer: the fuel is the operator's choice.
* The flood advisory has no hydrology (§5).
* Weather alerts are only ever *suggested*; publication stays with the editors (phase 5 flow).
