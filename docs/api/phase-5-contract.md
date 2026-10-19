# عقد الواجهة البرمجية — المرحلة 5 (العمليات والمتطوعون والتنبيهات)

Phase 5 additions to the API contract (phases 2–4 stay valid). The live schema is `GET /openapi.json`;
this file fixes what the dashboard (`apps/dashboard`), the mobile app (`apps/mobile`) and the portal rely
on. Conventions are unchanged: `snake_case` JSON, errors `{"detail": "<code>"}` with stable machine codes
that clients translate, opaque cursors, optimistic locking with `version` (`409 version_conflict`).

Requirements covered: FR-A-020…023 (volunteers), FR-A-060…062 (notifications, alerts, safety tips),
FR-C-04 (volunteer network), FR-C-06 and FR-C-10 (resources, volunteers and alerts layers), FR-C-09
(operations), FR-C-15 and FR-C-16 (committees), FR-C-17 (notifications), FR-C-18 (alerts), FR-C-19
(safety tips), the operational levels of §6.4 and the level switch of FR-C-24, BR-11 (automatic grouping
at disaster level), UC-01 step 6 (status pushes), UC-04 and UC-05.

Out of this phase (unchanged plan): alert-rules builder and IoT (phase 7, with MQTT), weather layer and
AI recommendations of forces (phase 7), periodic scheduled reports and rewards (phase 8), delegation of
powers inside Keycloak (accounts and roles stay administered in Keycloak).

## 0. Roles

| action | roles (realm `ehimaya-staff`, limited to the token's gouvernorat unless national) |
|---|---|
| read operations, resources, volunteers, alerts, levels | `operator`, `ops_manager`, `field_commander`, `local_committee`, `central_committee` |
| assign resources, update assignments, call volunteers out, timeline notes | `operator`, `ops_manager`, `field_commander` |
| close and evaluate an incident | `ops_manager`, `field_commander` |
| manage units and resources | `ops_manager`, `sysadmin` |
| review volunteers | `ops_manager`, `local_committee`, `central_committee` |
| draft an alert | `ops_manager`, `content_editor`, `local_committee`, `central_committee` |
| publish or cancel an alert (UC-04: «مصادقة المحرر أو اللجنة») | `content_editor`, `local_committee`, `central_committee` |
| draft, publish, cancel an informational notification | `content_editor`, `local_committee`, `central_committee` |
| safety tips | `content_editor` |
| set the operational level | `local_committee` (own gouvernorat, `normal` ↔ `crisis`), `central_committee` (any) |
| issue directives | `central_committee` (to any gouvernorat), `local_committee` (to its own) |
| acknowledge directives | `local_committee` of the target gouvernorat |

`content_editor` and `sysadmin` read the pages they manage but not reports. A staff member with a
gouvernorat scope cannot read or act outside it (`404` for objects, `403 out_of_scope` for targets).

## 1. Operational levels (§6.4, FR-C-24)

One level per gouvernorat: `normal` (default) | `crisis` | `disaster`.

- `GET /api/v1/staff/levels` (every staff role) → `[{"gouvernorat_code", "level", "since", "reason",
  "set_by"}]` for the 24 gouvernorats. `set_by` is the display name of who set it.
- `POST /api/v1/staff/levels` body `{"gouvernorat_codes": [11, 12], "level": "crisis", "reason": "…"}`
  (reason 5–500 characters) → the updated rows. `local_committee`: only its own gouvernorat and only
  `normal`/`crisis`; a gouvernorat at `disaster` can only be lowered by `central_committee`
  (`403 level_not_allowed`). Audited (`oplevel.change`); event `oplevel.changed`.

Effects (read by every module, applied on the change):

| level | effect |
|---|---|
| `crisis` | the priority component `op_level` (value 0.7) raises reports of the gouvernorat; open incidents carry the level; the dashboard shows the crisis banner |
| `disaster` | `op_level` value 1.0; AI grouping suggestions are applied automatically (BR-11, actor `system:auto_grouping`, timeline `via: "auto"`); informational notifications are suspended (`409 suspended_by_level`) — alerts are not |

`op_level` is a bonus component like `sensitive_sites`: weight 10 by default in the AI settings, absent
at `normal` (`detail.reason = "normal_level"`), never lowers a score (`detail.counted = false`). Open
reports of the last 48 hours in the gouvernorats concerned are re-scored when the level changes.

## 2. Committees (FR-C-15, FR-C-16)

### Directives
`Directive` = `{"id", "title", "body", "urgency": "normal" | "urgent", "from_level": "central" | "local",
"issued_by", "issued_at", "gouvernorat_codes": [..] (empty = all 24), "acks": [{"gouvernorat_code",
"acked_by", "acked_at", "note"}], "pending_acks": [codes]}`.

- `GET /api/v1/staff/directives?pending=true&limit&cursor` → newest first; a local scope sees the
  directives addressed to its gouvernorat and its own.
- `POST /api/v1/staff/directives` body `{"title" (3–150), "body" (1–5000), "urgency",
  "gouvernorat_codes"}` → `201 Directive`. Event `directive.issued`.
- `POST /api/v1/staff/directives/{id}/ack` body `{"note": "…" | null}` (`local_committee` of a target
  gouvernorat, once: `409 already_acknowledged`) → `Directive`.

### Performance (local and national monitoring)
`GET /api/v1/staff/committee/performance?since=ISO` (committees, `ops_manager`; default last 30 days) →
`{"since", "rows": [{"gouvernorat_code", "level", "reports", "closed", "rejected",
"avg_first_response_s", "avg_resolution_s", "open_incidents", "active_assignments",
"volunteers_approved", "volunteers_ready", "alerts_active"}], "national": {same totals}}` in scope.

## 3. Units and resources (FR-C-09, FR-C-10)

`Unit` = `{"id", "name_ar", "name_fr", "kind": "directorate" | "unit" | "advanced_post", "gouvernorat_code",
"location": {"lat", "lon"}, "phone", "version"}`.

`Resource` = `{"id", "unit_id", "unit_name", "kind", "label", "status": "available" | "assigned" |
"out_of_service", "notes", "location": {"lat","lon"} | null, "gouvernorat_code", "assignment": {"id",
"incident_id", "status"} | null, "version", "updated_at"}` with `kind` ∈ `fire_engine`, `water_tanker`,
`ambulance`, `rescue_vehicle`, `heavy_equipment`, `drone`, `large_extinguisher`, `boat`,
`command_vehicle`, `other`. `label` (call sign) is unique per unit.

- `GET /api/v1/staff/units` / `POST` / `PUT /{id}` / `DELETE /{id}` (`409 unit_in_use` while it has resources).
- `GET /api/v1/staff/resources?status=&kind=&unit_id=&gouvernorat_code=&limit&cursor`, `POST`,
  `PUT /{id}` (status may be set to `available` or `out_of_service` only when not assigned:
  `409 resource_busy`), `DELETE /{id}` (`409 resource_busy`).
- `GET /api/v1/staff/resources/summary` → `{"by_kind": {kind: {"available", "assigned", "out_of_service"}}}` in scope.
- `GET /api/v1/staff/resources/map?bbox=` → GeoJSON of units (`layer: "unit"`) and resources
  (`layer: "resource"`, at their location or their unit's).

## 4. Interventions (FR-C-09)

### Incident card
`IncidentSummary` gains `"title"`, `"classification"`, `"op_level"`, `"assignments_active"`,
`"callouts_open"`; `IncidentDetail` gains `"assignments": [Assignment]`, `"callouts": [Callout]` and
`"evaluation": Evaluation | null`.

- `PATCH /api/v1/staff/incidents/{id}` body `{"title" (≤150) | null, "classification" | null}` (writers).
  `classification` vocabulary per category: fire → `forest_fire`, `residential_fire`, `industrial_fire`,
  `vehicle_fire`; flood → `river_flood`, `urban_flood`, `flash_flood`; traffic_accident →
  `road_accident`, `chemical_road_accident`, `rail_accident`; drowning → `beach`, `dam_or_lake`, `well`;
  landslide → `landslide`, `rockfall`, `building_collapse`; chemical_leak → `industrial_leak`,
  `transport_leak`, `gas_leak`; medical → `cardiac`, `trauma`, `mass_casualty`; any category → `other`
  (`422 invalid_classification`).
- `POST /api/v1/staff/incidents/{id}/notes` body `{"text" (1–2000)}` → `TimelineEntry` (`kind: "note"`).

### Assignments (أوامر التكليف)
`Assignment` = `{"id", "incident_id", "kind": "resource" | "volunteer", "resource": {"id", "label",
"kind", "unit_name"} | null, "volunteer": {"id", "full_name", "phone", "skills"} | null, "order",
"status", "created_by", "created_at", "en_route_at", "on_scene_at", "released_at", "cancelled_at"}`.

Status flow: `ordered` → `en_route` → `on_scene` → `released`; `ordered`/`en_route` → `cancelled`
(`409 invalid_transition`). A resource is `assigned` while one of its assignments is active and
`available` again when it is released or cancelled.

- `POST /api/v1/staff/incidents/{id}/assignments` body `{"resource_id", "order" (≤1000)}` → `201
  Assignment`. The incident must be `open` (`409 incident_not_open`) and the resource `available`
  (`409 resource_busy`) and in scope. Volunteer assignments are created only by a call-out acceptance (§5).
- `POST /api/v1/staff/assignments/{id}/status` body `{"status", "note"}` → `Assignment`.

Automatic tracking-code updates for reporters (FR-C-09, UC-01): when the first assignment of an incident
is created, its reports still `received` move to `in_progress`; when an assignment reaches `on_scene`,
reports `in_progress` move to `intervened`. Actor `system:operations`; usual history, audit and push.

### Close and evaluate
`POST /api/v1/staff/incidents/{id}/close` (`ops_manager`, `field_commander`) body
`{"outcome": "resolved" | "false_alarm" | "transferred", "summary" (10–5000), "casualties": {"rescued",
"injured", "deceased", "evacuated"} (integers ≥ 0, default 0), "lessons": "…" | null}` → `IncidentDetail`.
Requires no active assignment (`409 assignments_active`). Open call-outs are closed. Reports not yet
final move to `closed` (through `in_progress` when needed). `Evaluation` = the body + `closed_by`,
`closed_at`.

## 5. Volunteers (FR-A-020…023, FR-C-04)

Skills: `first_aid`, `diving`, `heavy_vehicles`, `firefighting`, `search_rescue`, `logistics`,
`medical`, `other` (with `other_skill` text). Availability (مباشر أو منقطع): `continuous` | `intermittent`.
Statuses: `pending` → `approved` | `rejected`; `approved` → `suspended` → `approved`; any → `withdrawn`
(by the volunteer). Changing skills while `approved` sends the application back to `pending`.

### App (realm `ehimaya-public`, registered citizens only: anonymous `403 registration_required`)
`Volunteer` = `{"status", "skills", "other_skill", "availability", "period_from", "period_to" | null,
"notes", "review_reason", "submitted_at", "reviewed_at", "ready", "ready_until", "version"}`.

- `GET /api/v1/me/volunteer` → `Volunteer` or `404 not_volunteer`.
- `PUT /api/v1/me/volunteer` body `{"skills" (1–8), "other_skill", "availability", "period_from",
  "period_to", "notes" (≤500), "version"}` → `Volunteer`. Needs a profile with phone and gouvernorat
  (`409 profile_incomplete`); `period_to` ≥ `period_from` and ≤ 2 years ahead (`422 invalid_period`).
  A `rejected` or `withdrawn` application is resubmitted by the same call.
- `DELETE /api/v1/me/volunteer` → `204` (withdrawn; readiness and location cleared).
- `POST /api/v1/me/volunteer/readiness` body `{"ready": true, "lat", "lon", "accuracy_m", "hours"
  (1–24, default 8)}` or `{"ready": false}` → `Volunteer`. Ready needs `approved`
  (`409 volunteer_not_approved`) and today within the period (`409 outside_period`).
- `PUT /api/v1/me/volunteer/location` body `{"lat", "lon", "accuracy_m"}` → `204` while ready
  (`409 not_ready`); at most one update per 20 s.

Location privacy (§8 of the requirements): the live position lives in Valkey only while the volunteer is
ready, with an expiry equal to `ready_until`; it is never written to PostgreSQL nor archived, and is
deleted when readiness ends. The e-mail confirming approval or rejection (FR-A-021) goes to the
account's e-mail.

### Call-outs (UC-05, FR-A-023)
`Callout` = `{"id", "incident_id", "skill", "requested", "radius_km", "message", "status": "open" |
"filled" | "cancelled" | "closed", "created_by", "created_at", "accepted", "targets": [{"volunteer_id",
"full_name", "phone", "distance_m", "status": "sent" | "accepted" | "declined" | "expired" | "arrived",
"eta_minutes", "responded_at", "arrived_at", "position": {"lat","lon","at"} | null}]}`. `position` is
given for accepted volunteers while they are ready.

- `GET /api/v1/staff/incidents/{id}/volunteer-suggestions?skill=&radius_km=30&limit=20` → ready,
  approved volunteers in period, in scope, with the skill, nearest first: `[{"volunteer_id",
  "full_name", "phone", "skills", "distance_m", "busy"}]` (`busy`: already accepted another open call-out).
- `POST /api/v1/staff/incidents/{id}/callouts` body `{"skill", "requested" (1–50), "radius_km" (1–100),
  "message" (≤300), "volunteer_ids": [..] | null}` → `201 Callout`. Without `volunteer_ids` the nearest
  `requested × 2` (max 100) suggestions that are not busy are called. No candidate → `409 no_volunteer_available`.
- `GET /api/v1/staff/callouts/{id}`, `POST /api/v1/staff/callouts/{id}/cancel`,
  `POST /api/v1/staff/callouts/{id}/targets/{volunteer_id}/arrived`.
- App: `GET /api/v1/me/callouts?active=true` → `[{"id", "incident_category", "message", "distance_m",
  "location": {"lat","lon"}, "status", "my_status", "eta_minutes", "created_at"}]`;
  `POST /api/v1/me/callouts/{id}/respond` body `{"response": "accept" | "decline", "eta_minutes"
  (1–600, required to accept)}`; `POST /api/v1/me/callouts/{id}/arrived`.
  Accepting a `filled`, `cancelled` or `closed` call-out → `409 callout_closed`. An acceptance creates a
  volunteer `Assignment` (`en_route`); arrival moves it to `on_scene`. When the number of acceptances
  reaches `requested` the call-out becomes `filled` and the remaining `sent` targets `expired`. Targets
  without an answer after 30 minutes become `expired`.

### Staff
- `GET /api/v1/staff/volunteers?status=&skill=&gouvernorat_code=&ready=&q=&limit&cursor` →
  `{"items": [{"id", "full_name", "phone", "gouvernorat_code", "skills", "availability", "period_from",
  "period_to", "status", "ready", "ready_until", "submitted_at"}], "next_cursor"}` (pending first, then name).
- `GET /api/v1/staff/volunteers/{id}` → item + `email`, `other_skill`, `notes`, `review_reason`,
  `reviews`, `callouts` (last 20). Audited (`volunteer.view`).
- `POST /api/v1/staff/volunteers/{id}/review` body `{"decision": "approve" | "reject" | "suspend" |
  "reinstate", "reason"}` (`reason` required for reject and suspend) → detail. Sends the e-mail.
- `GET /api/v1/staff/volunteers/map?bbox=&skill=` → GeoJSON points of ready volunteers in scope with
  `{"id", "full_name", "phone", "skills", "ready_until"}` (layer «متطوعون حسب الاختصاص» and readiness heat map).

## 6. Push devices

- `PUT /api/v1/devices` (reporter identity as for reports: bearer of the public realm, or `X-Device-Key`)
  body `{"token" (FCM registration token), "platform": "android" | "ios", "locale", "lat", "lon",
  "location_alerts": true}` → `204`. The position is rounded to 0.01° (about 1 km), used only to target
  alerts by current location (FR-A-061), and replaced at each call. `location_alerts: false` clears it.
- `DELETE /api/v1/devices/{token}` → `204`.

Push payloads carry no personal data: `{"type": "alert" | "info" | "alert_cancelled" | "callout" |
"report_status", "id", …}` plus a localized title and body. Alerts use the Android channel
`ehimaya_alerts` and the iOS sound `alert.caf` with `interruption-level: time-sensitive`. A report
status change pushes `{"type": "report_status", "tracking_code", "status"}` to the reporter's devices.

## 7. Notifications and alerts (FR-A-060, FR-A-061, FR-C-17, FR-C-18)

`Message` = `{"id", "kind": "info" | "alert", "status": "draft" | "published" | "cancelled" | "expired",
"title": {"ar", "fr", "en"}, "body": {"ar", "fr", "en"}, "channels": ["push", "sms", "email"],
"created_by", "created_at", "published_by", "published_at", "cancelled_at", "version", "stats":
{"push": {"status", "sent", "failed"}, "sms": …, "email": …}}` (Arabic required; French and English fall
back to Arabic when empty; title ≤ 120, body ≤ 1000; SMS uses the title and the first 300 characters).

Informational (`kind: "info"`) adds `{"topic": "activity" | "awareness" | "training" | "world_day" |
"other", "audience": "all" | "volunteers" | "organizations" | "user", "gouvernorat_codes": [..],
"user_id": "…" | null}`; empty `gouvernorat_codes` = national.

Alert (`kind: "alert"`) adds `{"severity": "high" | "medium" | "low", "category": "weather" | "climate" |
"hazard", "hazard": "heavy_rain" | "flood" | "storm" | "wind" | "heat_wave" | "cold_wave" | "sea" |
"forest_fire" | "chemical" | "other", "area": {"gouvernorat_codes": [..]} | {"polygon": GeoJSON
Polygon}, "expires_at"}`. Polygon: one ring, 4–500 points, inside Tunisia (`422 invalid_area`);
`expires_at` within 7 days (`422 invalid_expiry`).

Staff (`/api/v1/staff/notifications`):
- `GET ?kind=&status=&limit&cursor` (register, newest first, in scope), `GET /{id}`.
- `POST` (draft) → `201 Message`; `PUT /{id}` (draft only, `version`; `409 not_draft`); `DELETE /{id}` (draft only).
- `GET /{id}/audience` → `{"push", "sms", "email"}` estimated recipients.
- `POST /{id}/publish` → `Message`. Alerts emit `alert.issued`. Local scope can only target its
  gouvernorat (`403 out_of_scope`; a polygon must lie in it, 5 km tolerance).
- `POST /{id}/cancel` → `Message` (published only). Cancelling an alert pushes `alert_cancelled`.
- `GET /api/v1/staff/alerts/active` → active alerts in scope (map layer).

Recipients: push → devices targeted by gouvernorat (profile or device position), polygon (device
position, else profile gouvernorat intersecting it), audience or user; SMS → verified phones of
registered profiles in the area; e-mail → registered profiles in the area. Channels without a
configured provider are recorded `skipped`. Delivery runs in the background in batches; `stats` updates
live (`notification.updated`).

Public:
- `GET /api/v1/alerts/active?lat=&lon=&gouvernorat_code=` (no sign-in, cached 60 s) → active alerts
  covering the point or gouvernorat (all active alerts without parameters): `[{"id", "severity",
  "category", "hazard", "title", "body", "area": {"gouvernorat_codes"} | {"polygon"}, "published_at",
  "expires_at"}]`.
- `GET /api/v1/notifications?limit&cursor` (reporter identity) → the caller's inbox: informational
  messages targeted to them and alerts of the last 30 days for their gouvernorat or device position,
  newest first, `{"items": [{"id", "kind", "topic" | "severity", "title", "body", "published_at",
  "expires_at", "active"}], "next_cursor"}`.

## 8. Safety tips (FR-A-062, FR-C-19)

`SafetyTip` = `{"id", "hazard", "position", "status": "draft" | "published", "content": {"ar": {"title",
"do": [..], "dont": [..]}, "fr": {…}, "en": {…}}, "version", "updated_at", "published_at"}` with
`hazard` ∈ `fire`, `flood`, `traffic_accident`, `medical`, `drowning`, `landslide`, `chemical_leak`,
`heat_wave`, `storm`, `earthquake`, `other`; up to 15 items of ≤ 300 characters in each list.

- Staff (`content_editor`): `GET /api/v1/staff/safety-tips`, `POST`, `PUT /{id}`, `DELETE /{id}`,
  `POST /{id}/publish` (all three languages complete: `409 translation_missing`), `POST /{id}/unpublish`.
- Public: `GET /api/v1/safety-tips` → `{"revision", "items": [published SafetyTip without status]}`
  with `ETag` (`If-None-Match` → `304`). The app stores the last copy for offline use and ships a
  bundled copy for the first launch. Seeded tips must be validated by the Protection Civile.

## 9. E-mail

Sent through SMTP (`SMTP_*` settings; Mailpit in development): volunteer decision (FR-A-021),
institution invitations (phase 4 links are now also e-mailed), weekly digest to institution admins of
expired safety trainings and overdue maintenance (FR-B-005, FR-B-006), and informational or alert
messages with the `email` channel.

## 10. Live events (WS `/api/v1/staff/live`, filtered by scope)
`oplevel.changed` `{"level": LevelRow}`, `directive.issued` `{"directive"}`, `assignment.updated`
`{"assignment", "gouvernorat_code"}`, `callout.updated` `{"callout", "gouvernorat_code"}`,
`resource.updated` `{"resource"}`, `volunteer.updated` `{"volunteer": item}`, `notification.updated`
`{"message"}`; `incident.updated` carries the new summary fields.

## 11. Error codes added in this phase
`level_not_allowed`, `out_of_scope`, `already_acknowledged`, `unit_in_use`, `resource_busy`,
`incident_not_open`, `invalid_classification`, `assignments_active`, `registration_required`,
`not_volunteer`, `profile_incomplete`, `invalid_period`, `volunteer_not_approved`, `outside_period`,
`not_ready`, `callout_closed`, `no_volunteer_available`, `invalid_area`, `invalid_expiry`, `not_draft`,
`suspended_by_level`, `translation_missing`, `invalid_transition`, `reason_required`, `version_conflict`,
`not_found`.
