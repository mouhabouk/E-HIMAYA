# عقد الواجهة البرمجية — المرحلة 6 (البث المباشر والرؤية الحاسوبية)

Phase 6 additions to the API contract (phases 2–5.5 stay valid). The live schema is `GET /openapi.json`;
this file fixes what the dashboard, the mobile app, MediaMTX and the vision service rely on. Conventions
are unchanged: `snake_case` JSON, errors `{"detail": "<code>"}`, `429 rate_limited` with `Retry-After`.

Requirements: FR-A-050..052, FR-C-07, UC-06, NFR-03 (200 concurrent streams nationally), architecture §7.

```
mobile app ── WHIP (WebRTC) ──┐
drone / camera ── RTSP/RTMP ──┼──► MediaMTX ── authHTTPAddress ──► API /internal/mediamtx/auth
stream-sim (SIMULATION) ──────┘        │  └── runOnReady / runOnNotReady / runOnRecordSegmentComplete ──► API /internal/mediamtx/hooks
                                       ├── record fMP4 segments (shared volume) ──► API worker: SHA-256 ──► S3 ──► reports.media(kind=recording)
                                       ├── RTSP (internal, read credentials) ──► vision ──► API /internal/vision/detections
                                       └── WHEP / HLS (viewer token) ──► dashboard multi-screen
```

## 1. Data model (migration `0011_live_streams`, owner: `services/api/app/modules/streams`)

* `reports.live_stream`: `id uuid pk`, `report_id → reports.report` (nullable for staff/drone sources),
  `user_id → identity.account` (nullable for drone/camera), `source text` (`app|drone|camera|sim`),
  `label text` (staff-given name for fixed sources), `path text unique` (= `live/<id>`),
  `publish_token_hash bytea` (HMAC of the token, never the token), `status text`
  (`pending|live|ended|expired|rejected`), `created_at`, `started_at`, `ended_at`, `end_reason text`
  (`publisher_stopped|staff_stopped|max_duration|token_expired|error`), `gouvernorat_code`,
  `last_location geography(Point)`, `last_location_at`, `max_fire_confidence real`, `max_smoke_confidence real`.
* `reports.stream_location`: `id bigserial`, `stream_id`, `at`, `location geography(Point)`, `accuracy_m`.
  Retention follows the report's (phase 5.5 A6).
* `reports.stream_detection`: `id bigserial`, `stream_id` (nullable), `media_id` (nullable, for uploaded
  images), `at`, `label` (`fire|smoke|person`), `confidence real`, `boxes jsonb`
  (`[[x1,y1,x2,y2,conf], …]`, coordinates normalised 0..1), `model text`.
* Recordings reuse `reports.media` with `kind = "recording"`, `stream_id` set, `report_id` = the stream's
  report, `sha256` of the segment, `duration_s`, `status = "stored"`.

## 2. Citizen endpoints (realm `ehimaya-public` bearer **or** `X-Device-Key`, like reporting)

### `POST /api/v1/reports/{report_id}/streams` → `201`
Only the report's owner, only while the report is not `closed|rejected`. One `pending|live` stream per
report (`409 stream_already_active`). Rate limit: 6 per hour per account (`429`).

```json
{"stream_id": "uuid", "path": "live/<uuid>", "whip_url": "https://<host>/live/<uuid>/whip",
 "publish_token": "<opaque, 43 chars>", "expires_at": "…", "max_duration_s": 900,
 "location_interval_s": 10, "simulated": false}
```
The app sends `Authorization: Bearer <publish_token>` on the WHIP request. The token is valid for one
publish session, until `expires_at` (10 min to start) and then for `max_duration_s` after start.

### `POST /api/v1/streams/{stream_id}/location` → `204`
`{"lat": 36.8, "lon": 10.18, "accuracy_m": 12.0}` — owner only, accepted while `pending|live`
(`409 stream_not_active` otherwise). At most 1 per 3 s (extra calls are ignored with `204`).

### `POST /api/v1/streams/{stream_id}/stop` → `200` stream summary
Owner only; idempotent. Kicks the publisher through the MediaMTX API.

### `GET /api/v1/streams/{stream_id}` → `200`
`{"stream_id", "status", "started_at", "ended_at", "end_reason"}` — owner only (the app polls it to show
"stream ended by the operator").

FR-A-051 fallback: when live streaming is not possible (no network quality, old device), the app records a
clip and uploads it through the existing tus upload (`kind = video`), unchanged from phase 2.

## 3. Internal endpoints (not routed by Caddy; network-internal only)

### `POST /internal/mediamtx/auth` (MediaMTX `authHTTPAddress`)
Body from MediaMTX: `{"user","password","token","ip","action","path","protocol","id","query"}`.
`200` allows, `401` denies. Rules:
* `action=publish`: path must be `live/<id>` of a `pending` stream whose token (from `token`, `password`
  or `query token=`) matches and is not expired. Fixed sources (`drone|camera|sim`) use their own token.
* `action=read|playback`: either the internal vision credentials (`user=vision`, `password=$VISION_READ_PASSWORD`),
  or a staff viewer token (§4) for that exact path.
* `action=api|metrics|pprof`: only the internal API user (`user=ehimaya-api`, `$MEDIAMTX_API_PASSWORD`).
* Everything else `401`. Every denial is logged (no token in logs).

### `POST /internal/mediamtx/hooks` (header `X-Hook-Token: $MEDIAMTX_HOOK_TOKEN`)
`{"event": "ready|not_ready|segment_complete", "path": "live/<id>", "source_type": "webRTCSession|rtspSession|rtmpConn|…",
"segment_path": "/recordings/live/<id>/<file>.mp4", "segment_duration_s": 60.0}` → `204`.
* `ready`: stream `live`, `started_at`; emits `stream.started`; asks vision to watch (§5).
* `not_ready`: stream `ended` (`end_reason` default `publisher_stopped`); emits `stream.ended`; vision stops.
* `segment_complete`: the worker hashes the segment (SHA-256), uploads it to S3 under
  `recordings/<stream_id>/<n>.mp4`, inserts `reports.media`, deletes the local file. Idempotent per path.

### `POST /internal/vision/detections` (header `X-Vision-Token: $VISION_CALLBACK_TOKEN`)
`{"stream_id": "uuid", "at": "…", "model": "…", "detections": [{"label": "fire", "confidence": 0.81,
"boxes": [[0.1,0.2,0.4,0.6,0.81]]}], "frame_jpeg_b64": "…|null"}` → `204`.
Detections under `VISION_MIN_CONFIDENCE` (default 0.45) are dropped. A **confirmed** fire or smoke
(≥ `VISION_ALERT_CONFIDENCE`, default 0.6, in 3 of the last 5 analysed frames) raises the report's priority
(phase 3 scoring input `vision_fire`), adds an incident timeline event if linked, stores the frame as
`reports.media(kind=image, analysis.source="vision")`, and pushes `stream.alert` on the live feed. It never
sends a public alert by itself: the final decision stays human (FR-C-11).

## 4. Staff endpoints (realm `ehimaya-staff`; read roles = the report read roles, geographic scope applies)

* `GET /api/v1/staff/streams?status=live|ended|all&gouvernorat=&cursor=` → page of
  `{"id","report_id","tracking_code","source","label","status","started_at","ended_at","duration_s",
  "gouvernorat_code","last_location":{"lat","lon"}|null,"max_fire_confidence","max_smoke_confidence",
  "recordings_count","simulated"}`.
* `GET /api/v1/staff/streams/{id}` → the above plus `"recordings": [{"media_id","sha256","bytes","duration_s","created_at"}]`,
  `"detections": [{"at","label","confidence","boxes"}]` (latest 200), `"track": [{"at","lat","lon"}]`.
* `POST /api/v1/staff/streams/{id}/viewer` → `{"whep_url","hls_url","token","expires_at"}` (token valid 5 min
  to start, path-bound; audited `stream.view`).
* `POST /api/v1/staff/streams/{id}/stop` (roles OPS_MANAGER, FIELD_COMMANDER, operators) → `200`; audited.
* `GET /api/v1/staff/streams/{id}/recordings/{media_id}` → `302` to a short-lived presigned URL (like media),
  audited `stream.recording.download`.
* `POST /api/v1/staff/streams` (OPS_MANAGER, SYSADMIN): register a fixed source (`source=drone|camera`,
  `label`, `gouvernorat_code`) → `{"id","path","publish_url_rtsp","publish_url_rtmp","publish_token"}`.

Live feed (phase 2 §5 WebSocket) new events, scoped like reports:
`stream.started`, `stream.ended`, `stream.location` (throttled 1 per 10 s), `stream.alert`
(`{"stream_id","label","confidence","report_id"}`), `stream.recording` (`{"stream_id","media_id"}`).

## 5. Vision service (`services/vision`, port 8100, internal)

* `GET /healthz`, `GET /v1/model` → `{"name","version","license","labels":["fire","smoke","person"]}`.
* `POST /v1/detect` (multipart `image`) → `{"model","detections":[…]}` — used by the API pipeline for
  uploaded report images (`media.analysis.vision`).
* `PUT /v1/streams/{stream_id}` `{"rtsp_url": "rtsp://mediamtx:8554/live/<id>", "callback_url": "…"}` → `202`
  starts watching (1 frame/s, 2 frames/s while a detection is pending confirmation); `DELETE` stops.
  At most `VISION_MAX_STREAMS` (default 8 on CPU) watched at once; beyond that `429` and the API retries.
* Auth: `Authorization: Bearer $VISION_API_TOKEN` on every call except `/healthz`.

## 6. Simulation (┏━━ SIMULATION banners, `[SIM]` prefix, amber UI band "وضع المحاكاة")
`stream-sim` (compose profile `sim`) publishes a looped sample clip over RTSP to `live/<id>` of a
`source=sim` stream registered at start-up, so the dashboard, recording, hashing and vision paths run end to
end without a phone. Streams with `source=sim` carry `"simulated": true` everywhere.

## Implementation notes

Where the implementation differs from the text above, or fixes something the contract left open:

* **MediaMTX hook names.** MediaMTX 1.21.2 deprecates `runOnReady`/`runOnNotReady`, so
  `infra/mediamtx/mediamtx.yml` uses their replacements `runOnAvailable`/`runOnUnavailable`. The hook body and
  its `event` values (`ready|not_ready|segment_complete`) are unchanged. The hooks are posted by
  `infra/mediamtx/hook.sh` (busybox wget, 5 attempts). Unknown paths answer `204` and are logged.
* **Publish rule.** Beyond "a pending stream with a matching token":
  * a fixed source (`drone|camera|sim`) may publish again after `publisher_stopped|error` (link drops) until
    staff stop it, which retires its token;
  * citizen (`app`) streams may publish only over WebRTC/WHIP (`protocol_not_allowed` otherwise);
  * a citizen token is single-session: its hash is erased when the stream ends.

  `max_duration_s` is enforced by the API's lifecycle loop, which ends the stream (`max_duration`) and kicks
  the publisher, not at authorization time (MediaMTX authorizes a session once).
* **Read rule.** A viewer token opens its path only while the stream is `pending|live`. The token is
  `<unix expiry>.<base64url HMAC>` (opaque to clients), sent as `Authorization: Bearer` (WHEP, HLS) or HLS
  `?token=`. Denials are logged as `mediamtx.auth_denied` with a reason and an opaque client hash.
* **Data model additions** (§1):
  * operational columns on `reports.live_stream`: `expires_at`, `created_by`, `location_event_at`,
    `segment_seq`, `vision_state` (`idle|requested|watching|stopping|disabled`), `vision_attempts`,
    `vision_next_attempt_at`, `vision_frames` (the 5-frame confirmation window), `vision_alerts` (per-label
    cool-down);
  * a `confirmed` flag on `reports.stream_detection`;
  * a new ingest queue `reports.stream_segment` (`segment_path` unique, `seq`, `state
    pending|done|failed|missing`, attempts and back-off), which makes `segment_complete` idempotent per path
    and lets a lost hook be recovered by an orphan scan of the volume;
  * `reports.media.stream_id` references `live_stream` with `ON DELETE CASCADE`.

  The recording key `<n>` is the 1-based segment sequence of the stream.
* **Staff endpoints** (§4):
  * the list takes `limit` (1–200, default 50), and `status` defaults to `live`;
  * `GET /staff/streams/{id}` is audited `stream.detail`, because the track is personal data;
  * registration accepts optional `lat`/`lon` and answers `403 out_of_scope` for a gouvernorat outside a
    regional manager's scope and `422 invalid_gouvernorat`;
  * stop uses the report write roles (operator, ops manager, field commander), and on an already-ended fixed
    source it still retires the token.
* **Live feed payloads are supersets.** Every `stream.*` event carries `gouvernorat_code`, which scope routing
  needs.
  * `stream.started` / `stream.ended`: `{stream_id, gouvernorat_code, stream: <staff list item>}`.
  * `stream.location`: adds `report_id`, `lat`, `lon`, `accuracy_m`, `at`.
  * `stream.alert`: adds `media_id` (the stored frame), `simulated`, `at`.
  * `stream.recording`: adds `report_id`, `sha256`, `duration_s`.
* **Citizen endpoints.**
  * Stream creation is also limited to 30 per hour per client address (on top of 6 per hour per account).
  * Location must fall inside Tunisia's bounding box (`422` otherwise).
  * An expired pending stream does not block a new one.
* **Priority input `vision_fire`** is a bonus component (weight 10, like `op_level`; new key in
  `PRIORITY_COMPONENTS`). Its value is the confidence of the strongest confirmed fire or smoke of the report,
  from a stream or an uploaded image. For an uploaded image, which has no frame series, one detection at or
  above `VISION_ALERT_CONFIDENCE` counts as confirmed. Alerts per label are throttled to one per 5 min per
  stream (`VISION_ALERT_COOLDOWN_S`), but every confirming frame is flagged.
* **Retention and privacy.**
  * When a report is anonymised, its streams' location tracks are deleted, the last location is snapped to
    the anonymisation grid, the account link is detached, and recordings and vision frames go with the
    report's media.
  * Drone/camera/sim streams without a report are deleted `RETENTION_STREAM_DAYS` (365) after they ended,
    with their recordings.
  * `/me/export` includes `streams` (with track and recording ids). `/me/delete` ends and kicks active streams.
* **Simulation endpoints (internal, not in §3).**
  * `POST /internal/sim/streams` and `GET /internal/sim/streams/{id}` use the `X-Sim-Token: $STREAM_SIM_TOKEN`
    header, and answer `404` when the token is unset or `APP_ENV=production`. The API refuses to start in
    production with the token set.
  * Labels are prefixed `[SIM] `. A restarted simulator replaces its active stream of the same label.
  * The default clip is CC-BY-4.0 (Intel `sample-videos`, people walking), pinned by SHA-256. No
    redistributable CC0 fire clip could be verified at build time: see docs/streaming.md §8.
* **Vision service environment.** The API's `VISION_READ_PASSWORD` is passed to the vision service as
  `VISION_RTSP_PASSWORD` (its `VISION_` settings prefix). `POST /v1/detect` is called with the multipart field
  `image`. Callbacks may carry `frame_jpeg_b64` (JPEG, ≤ 2 MB decoded), which is stored only for a confirmed
  alert.
