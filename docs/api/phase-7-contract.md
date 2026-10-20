# عقد الواجهة البرمجية — المرحلة 7 (الطقس والتنبؤ ودعم القرار والاتصالات)

Phase 7 additions (phases 2–6 stay valid). Conventions unchanged: `snake_case` JSON, errors `{"detail": "<code>"}`,
`429 rate_limited` with `Retry-After`, staff scope by gouvernorat, every staff write audited.

Requirements: FR-A-034, FR-A-048, FR-C-08, FR-C-10 (weather layer), FR-C-11, FR-C-13 (suggested responders),
FR-C-14, BR-20 (weather component), UC "weather threshold → suggested alert", architecture §6 (models), §8 (telephony),
ADR-10, retention: call recordings 2 years.

Golden rule for every recommendation in this phase: it is shown **with its justification and inputs**, and **a human
decides**. Nothing here sends a public alert, dispatches a resource or transfers a call on its own.

Owners and migration numbers (to avoid collisions while three API modules are built in parallel):
`modules/weather` + `modules/forecast` → `0012_weather`; `modules/decision` → `0013_decision`;
`modules/telephony` → `0014_telephony` (each `down_revision` is the previous one).

## 1. Weather layer (`modules/weather`)

Source: Open-Meteo forecast API (`api.open-meteo.com`, data CC-BY 4.0, attribution shown in the UI), base URL
configurable (`WEATHER_API_URL`) so a self-hosted Open-Meteo or a national (INM) feed can replace it. A worker loop
refreshes a grid of points covering Tunisia (≈ 0.25°, about 300 points, batched requests) every 30 min, stores the
latest snapshot and hourly forecast (next 48 h) in `weather.grid_point` / `weather.observation`, and never blocks the
report path. Without network (`WEATHER_PROVIDER=sim`) a deterministic simulator feeds the same tables
(┏━━ SIMULATION banners, `[SIM]`, `"simulated": true` in responses).

Derived indices per point and hour: wind (speed km/h, gusts, direction °), temperature °C, relative humidity %,
precipitation mm/h and 24 h total, **fire danger** (Canadian FWI system computed in-house from noon values, with the
class `low|moderate|high|very_high|extreme`), **heavy-rain level** (`none|watch|warning` from mm/h and mm/24 h).

* `GET /api/v1/weather?lat=&lon=` (public, cached 10 min, rate-limited): current values + next 12 h hourly + active
  weather alerts covering the point (from `notify`, category `weather`) + `attribution`.
* `GET /api/v1/staff/weather/grid?bbox=&hour=` → GeoJSON FeatureCollection of points with all fields (map layer).
* `GET /api/v1/staff/weather/at?lat=&lon=` → the point detail with 48 h forecast.
* Threshold rules (configurable per gouvernorat in `weather.rule`): `fire_danger ≥ very_high`, `wind_gust ≥ 70`,
  `rain_24h ≥ 50`, `rain_1h ≥ 20` … → a **suggested alert** row (`weather.alert_suggestion`: gouvernorats, category
  `weather`, severity, prefilled ar/fr/en text, evidence values, valid_until) shown to editors and committees.
  `GET /api/v1/staff/weather/suggestions`, `POST …/{id}/accept` (opens the phase 5 alert form prefilled; the alert is
  sent only by the existing alert endpoint after human review), `POST …/{id}/dismiss` (reason). Live feed event
  `weather.suggestion`.
* Priority scoring (BR-20): the `weather` component now uses the report's nearest point (fire reports: fire danger;
  flood reports: rain level; others: wind) instead of `no_data_yet`.

## 2. Spread forecast (`modules/forecast`)

* Fire: `POST /api/v1/staff/incidents/{id}/forecast/fire` `{"ignition": {"lat","lon"} | null (incident centroid),
  "fuel_model": "grass|shrub|timber_litter|mixed" (default by land cover or "mixed"), "horizons_min": [30,60,120]}`
  → `{"forecast_id","model":"rothermel-elliptical-v1","inputs":{wind,rh,temp,slope_pct,fuel,…},
  "polygons":[{"minutes":30,"geojson":…,"area_ha":…}],"rate_of_spread_m_min":…,"assumptions":[…],"generated_at"}`.
  Rothermel surface rate of spread (Anderson fuel parameters) with wind and slope, Anderson length-to-breadth ellipse
  oriented downwind; slope from a terrain model (Copernicus GLO-90 or SRTM tiles for Tunisia, licence checked; slope
  0 with an explicit assumption when absent). Stored in `forecast.run`, shown on the map, refreshable.
* Flood: `POST /api/v1/staff/incidents/{id}/forecast/flood` → rainfall-driven advisory: accumulated rain (observed +
  next 6/12/24 h) over the incident's area, terrain low points and drainage direction from the terrain model, and a
  risk polygon with a level and its assumptions. It is an advisory, not a hydraulic model, and says so.
* Every run is audited and carries `"disclaimer"` text (ar/fr) that the operator sees.

## 3. Decision support (`modules/decision`)

* `GET /api/v1/staff/incidents/{id}/recommendations` → `{"generated_at","items":[…]}` where each item is
  `{"kind":"resources|volunteers|route|escalation|alert|responders","title":{ar,fr},"rationale":{ar,fr},
  "inputs":{…},"confidence":"low|medium|high","actions":[{"type":"open_assignment|open_alert_form|call|show_route",…}]}`.
  Built from rules over existing data (category, priority, reporters count, people detected, fire danger, spread
  forecast area, available resources and volunteers by distance/skill, op level, sensitive sites), never auto-applied.
* Routing: `GET /api/v1/staff/route?from=lat,lon&to=lat,lon&profile=car|truck` → `{"distance_m","duration_s",
  "geometry":GeoJSON LineString,"engine":"osrm|valhalla","simulated":bool}` through a self-hosted routing engine on
  OpenStreetMap Tunisia (ODbL, attribution shown); straight-line estimate with `"engine":"fallback"` when the engine is
  down. Used for "best vehicle route" and to rank resources by travel time.
* Responders directory suggestion (FR-C-13): `GET /api/v1/staff/incidents/{id}/responders` → officials to involve by
  incident type and gouvernorat from the existing directory (phase 5), with the reason.
* Assistant: `POST /api/v1/staff/incidents/{id}/assistant` `{"question": "…", "lang":"ar|fr"}` → `{"answer",
  "sources":[{"kind":"procedure|incident|report","id","title","excerpt"}],"model"}`. Local LLM (Ollama, phase 3) with
  retrieval over a procedures library (`docs/procedures/*.md`, ar/fr, seeded with civil-protection guidance written
  for the project, sources cited) and similar past incidents (pgvector). Answers only from sources, says when it does
  not know, rate-limited, audited (question and answer stored with the incident timeline). 503 `assistant_unavailable`
  when the model is not installed.

## 4. Telephony (`services/telephony` + `modules/telephony`) — scenarios 1 and 2 (ADR-10)

* Asterisk 22 LTS (built from source or an official distribution package, pinned, non-root, minimal modules) with
  PJSIP: extension **8000** (public entry, from a SIP trunk DID in production or a WebRTC caller in the app later)
  → queue `operators`; operators are PJSIP WebRTC endpoints (WSS + DTLS-SRTP) registered by the dashboard softphone.
  MixMonitor records every queued call to a shared volume; Stasis/ARI app `ehimaya` drives call control.
* API ↔ Asterisk over ARI (HTTP + WebSocket events, credentials in settings): call lifecycle into
  `telephony.call` (`id, direction, caller_number (encrypted + blind index), started_at, answered_at, ended_at,
  operator_user_id, queue, status, report_id, incident_id, tracking_code, recording_media_id, transferred_to,
  end_reason`), recording ingestion like phase 6 segments (SHA-256 → S3 → `reports.media kind=call_recording`),
  retention 2 years then deletion.
* Staff endpoints:
  `POST /api/v1/staff/telephony/credentials` → short-lived SIP credentials for the operator's WebRTC endpoint
  `{"ws_url","sip_uri","username","password","expires_at","ice_servers"}`;
  `GET /api/v1/staff/calls?status=&cursor=`; `GET /api/v1/staff/calls/{id}`;
  `POST /api/v1/staff/calls/{id}/link` `{"report_id"|"tracking_code"|"incident_id"}`;
  `POST /api/v1/staff/calls/{id}/transfer-198` → scenario 2 blind transfer through the trunk via ARI; returns
  `409 transfer_disabled` unless `TELEPHONY_TRANSFER_198_ENABLED=true` and a trunk is configured (scenario 1 stays the
  default: the operator calls 198 from their own phone);
  `POST /api/v1/staff/calls/dial` `{"number"|"report_id"|"volunteer_id"}` → outbound call from the operator's softphone
  (FR-C-10 "contact from the map"), numbers limited to Tunisian formats, audited;
  conferences: `POST /api/v1/staff/incidents/{id}/conference` → a crisis room bridge `{"room","join_uri"}`, list and
  end. Recording download like stream recordings (302 presigned, audited).
* Live feed events: `call.ringing`, `call.answered`, `call.ended`, `call.recording` (scoped; caller number masked
  except last 2 digits for roles without call access).
* Simulation: a `call-sim` service (profile `sim`) places scripted SIP calls to 8000 with an audio prompt so the queue,
  softphone, recording and linking run end to end (┏━━ SIMULATION banners, `[SIM]`).

## 5. Mobile

* FR-A-034: weather card on home (current + next hours at the user's position, active weather alerts highlighted,
  Open-Meteo attribution), cached for offline display with its time, refreshed under the phase 5.5 battery rules.
* FR-A-048: with no internet at all, the report flow offers (a) an SMS to the platform number
  (`SMS_REPORT_NUMBER`, dart-define) with a compact machine-readable body `EH1 <category> <lat>,<lon> <acc>m <client_uuid8>`
  opened in the SMS app for the user to send, and (b) a call to 198 (scenario 0). The API accepts such SMS through the
  SMS gateway webhook `POST /internal/sms/inbound` (signed) and creates a report with `source=sms` (dedup by
  client_uuid prefix when the app later syncs).

## Implementation notes

### Mobile (§5) — what the app reads and sends

* `GET /api/v1/weather?lat=&lon=` — the app sends its coarse position rounded to 2 decimals (≈ 1 km) and reads
  this shape (snake_case; the parser also accepts the aliases in brackets, unknown fields are ignored, every
  field except `current` is optional):
  `{"location":{"lat","lon"}, "updated_at" [generated_at|observed_at], "current":{HOUR}, "hourly":[{HOUR},…],
  "alerts":[<same item as GET /api/v1/alerts/active>], "attribution":{"text","url","licence"} | "<text>",
  "simulated":bool}` with
  `HOUR = {"time", "temperature_c" [temperature], "wind_speed_kmh" [wind_kmh], "wind_gust_kmh" [wind_gusts_kmh],
  "wind_direction_deg" [wind_dir_deg], "relative_humidity_pct" [humidity_pct], "precipitation_mm_h"
  [precipitation_mm|rain_1h_mm], "precipitation_24h_mm" [rain_24h_mm], "fire_danger": "low|moderate|high|very_high|extreme"
  | {"class","fwi"}, "heavy_rain" [rain_level]: "none|watch|warning" | {"level"}, "weather_code" (WMO, optional)}`.
  Without `attribution` the app shows "Open-Meteo.com (CC BY 4.0)". Alerts listed there open the existing alert
  detail screen (`/alerts/{id}`).
* Weather refresh on the phone: at most every 30 min in the foreground (60 min in battery saver, back-off to 2 h
  after failures), never in the background or offline; the last answer is cached on the phone (with the time it was
  fetched) and shown offline for up to 24 h, hours already past are dropped.
* FR-A-048 SMS body, exactly: `EH1 <category wire> <lat>,<lon> <acc>m <id8>` — ASCII only, single spaces;
  `lat`/`lon` with 5 decimals and `.` as separator (no locale formatting); `acc` = horizontal accuracy in whole metres
  rounded up, clamped to 1…99999, **`0m` means unknown accuracy**; `id8` = the first 8 lowercase hex digits of the
  report's `client_uuid` (its first UUID group). Example: `EH1 fire 36.80650,10.18150 12m 3f2a9c1d`. The SMS is only
  offered when no network interface is up at all; the report stays in the encrypted queue and is synced with the same
  `client_uuid` later, so the server must merge the SMS report with the synced one by that 8-hex prefix (plus
  category and a time window, since 32 bits can collide).

### Decision support (§3) — as implemented

* Routing engine: Valhalla 3.9.1 (`"engine":"valhalla"`). Route responses add `profile`, `attribution`, and, for
  `"engine":"fallback"`, `fallback_reason` (`not_configured|engine_unavailable|no_route`) and `assumptions`. A
  point outside Tunisia → `422 out_of_coverage`; a malformed point → `422 invalid_point`.
* The recommendations response adds `incident_id`, `simulated` (weather or forecast inputs simulated) and a bilingual
  `notice`; actions carry `label` and their target fields (`resource_id`, `prefill`, `number`, `volunteer_id`,
  `from`/`to`/`profile`).
* Responders: no officials table exists from phase 5, so the suggestion is drawn from directorate and nearby units,
  the regional committee, registered institutions and public agency numbers; each entry has `kind`
  (`unit|committee|agency|institution`) and `name_fr`.
* The assistant response adds `supported` (false = the fixed refusal) and `notice`; sources add `references` (the
  public documents a procedure cites). The assistant is open to the staff read roles within their scope.
  Details: `docs/decision-support.md`.

### Dashboard (§1–§4) — what the dashboard reads and sends

Assumptions where the contract is open; the dashboard parses leniently (unknown fields ignored).

* Weather grid: `hour` is an offset in hours from now, `0`–`47`; `bbox` is `minLon,minLat,maxLon,maxLat` (5 decimals).
  Point fields are read under the §1 names and the Open-Meteo aliases (`wind_speed_10m`, `wind_direction_10m`,
  `wind_gusts_10m`, `precipitation`, `relative_humidity_2m`, `temperature_2m`); `fire_danger` ∈
  `low|moderate|high|very_high|extreme`, `rain_level` ∈ `none|watch|warning`. The collection may carry
  `simulated` and `attribution` (`{"text","url","licence"}`, default Open-Meteo.com / CC BY 4.0). Point popup:
  `GET /api/v1/staff/weather/at?lat=&lon=` → `{"lat","lon","current":{…},"hourly":[{"time",…}],"alerts":[…],
  "attribution","simulated"}` (the staff twin of the public `GET /api/v1/weather`).
* Suggestions: the list may be an array or a page `{"items":[…]}`; `evidence` an array of `{"metric","value","unit",
  "threshold","gouvernorat_code","lat","lon","at"}` or a flat object of metric → value. Dismiss sends
  `{"reason"}` (≥ 3 characters). Accept then opens the phase 5 alert form with a prefill built in the browser
  (title, body, severity, gouvernorats, expiry = `valid_until`); the alert is only sent from that form.
  Live event: `{"type":"weather.suggestion","suggestion_id","suggestion"?}`. Error `409 suggestion_not_pending`.
* Forecast runs are shown from the POST response only (not reloaded after a page reload). Assistant sources link
  to a procedure only when they carry `url`, to an incident when they carry `incident_id`.
* Telephony: `POST /telephony/credentials` → `{"ws_url","sip_uri","username","password","expires_at",
  "ice_servers"?,"display_name"?,"transfer_198_enabled"?,"simulated"?}`; renewed at
  `expires_at − max(60 s, 20 % of the lifetime)`, retried every 15 s. `transfer_198_enabled` (default false) decides
  between the "Transfer to 198" button and the scenario 1 instruction. Asterisk should add the SIP headers
  `X-EHimaya-Call-Id: <calls.id>` (and optionally `X-EHimaya-Queue`) to the INVITE it sends the operator; without
  them the softphone pairs the INVITE with the latest `call.ringing` event. A dial-out (`POST /calls/dial` →
  `{"id"}`) rings the operator's own endpoint first; the softphone answers that leg itself within 30 s.
  Live events: `{"type":"call.ringing|call.answered|call.ended|call.recording","call_id","call"?,"queue"?:
  {"name","waiting"},"media_id"?}`. Recording: `GET /calls/{id}/recording` (302 or `{"url"}`). Conferences:
  `GET /incidents/{id}/conference` (list), `POST` (start, `{"room","join_uri"}`), `DELETE
  /incidents/{id}/conference/{room}` (end); the softphone joins by dialling `join_uri`. The calls log filters by
  `status` on the server; direction, linked/unlinked and text search are applied in the browser.
* Roles in the dashboard: softphone = operator, ops_manager, field_commander; conference join adds the national and
  regional committees; suggestion queue = the phase 5 notification roles (accept only for alert drafters); calls
  log = the staff read roles.
* Deployment: the dashboard image takes `CSP_TELEPHONY_SRC` (SIP WebSocket origin, e.g. `wss://sip.example.tn`) for
  `connect-src`, and emits `Permissions-Policy: microphone=(self)` (`CSP_MICROPHONE=self`, `infra/web/csp.mjs`).
