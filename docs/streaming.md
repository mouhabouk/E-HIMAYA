# البث المباشر — دليل التشغيل / Live streaming operator runbook

Phase 6 (docs/api/phase-6-contract.md). This page is for whoever runs the stack: how the pieces fit, which
ports and secrets exist, how to move from the simulated camera to real drones and cameras, and what to check
when something does not work.

## 1. نظرة عامة / How it fits together

```
phone (WHIP) ─────────┐                        ┌─► /internal/mediamtx/auth   (every publish / read / api call)
drone, camera (RTSP,  ├─► MediaMTX 1.21.2 ─────┼─► /internal/mediamtx/hooks  (ready, not_ready, segment_complete)
  RTMP) ──────────────┤    │                   └── /v3 kick ◄── API (staff stop, citizen stop, expiry)
stream-sim [SIM] ─────┘    ├─ fMP4 segments ─► "recordings" volume ─► API worker: SHA-256 → S3 → reports.media
                           ├─ RTSP (user "vision") ─► vision service ─► /internal/vision/detections
                           └─ WHEP / HLS (viewer token, 5 min) ─► dashboard
```

* **MediaMTX decides nothing itself.** Every publish, read and control-API call is a `POST
  /internal/mediamtx/auth` to the API, which answers 200 or 401 (decision table in
  `services/api/app/modules/streams/internal.py`). Denials are logged as `mediamtx.auth_denied` with a reason
  and an opaque client hash, never with a token.
* **Tokens.** A citizen stream gets a 43-character publish token once (only its keyed hash is stored), valid
  for one session: 10 min to start, then at most `STREAM_MAX_DURATION_S`. A drone/camera gets a long-lived
  token at registration (shown once); it may reconnect after a link drop until staff stop it, which retires
  the token. Dashboard viewers get a path-bound token valid 5 min to start a WHEP or HLS session.
* **Recordings.** Every stream is recorded in fMP4 segments of at least 60 s. When a segment is complete,
  MediaMTX's hook queues it (`reports.stream_segment`). The worker reads it, computes its SHA-256, uploads
  it to `recordings/<stream_id>/<n>.mp4`, inserts `reports.media(kind=recording)`, and only then deletes the
  local file. Segments whose hook was lost are found by an orphan scan of the volume every minute, once they
  are older than 10 min.
* **Vision is optional.** Without `VISION_SERVICE_URL`, streams, recordings and uploads work the same:
  streams show `vision_state=disabled` and images are not analysed. When the service is set but down or full
  (429), the API retries with back-off and nothing waits for it.

## 2. التشغيل / Running it

Development (MediaMTX always runs with the stack):

```sh
docker compose --env-file .env -f infra/compose.yml up -d
# simulated camera ("[SIM] SIM camera" in the dashboard):
docker compose --env-file .env -f infra/compose.yml --profile sim up -d
# fire/smoke detector (also set VISION_SERVICE_URL=http://vision:8100 in .env):
docker compose --env-file .env -f infra/compose.yml --profile vision up -d
```

Production: `docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml up -d --build`
(docs/deploy-production.md). The `sim` profile does not exist there, and the API refuses to start when
`STREAM_SIM_TOKEN` is set.

Smoke test: `python3 infra/smoke/smoke_test.py` also creates and stops a citizen stream. When
`STREAM_SIM_TOKEN` is set (environment or `./.env`), it publishes 8 s of test pattern through MediaMTX and
waits for the recording to reach S3.

## 3. المنافذ / Ports

| Port | Protocol | Who | Development | Production |
|------|----------|-----|-------------|------------|
| 8889 | HTTP (WHIP/WHEP signalling) | phones, dashboard | `127.0.0.1:8889` | through Caddy: `https://API_HOST/live/<id>/whip\|whep` |
| 8888 | HTTP (HLS) | dashboard fallback | `127.0.0.1:8888` | through Caddy: `https://API_HOST/live/<id>/index.m3u8` |
| 8189 | UDP (WebRTC media, ICE) | phones, dashboard | `127.0.0.1:8189/udp` | **published** `8189/udp` |
| 8554 | RTSP (TCP only) | drones, cameras, vision (internal) | `127.0.0.1:8554` | **published** `8554` (firewall it) |
| 1935 | RTMP | drones, encoders | `127.0.0.1:1935` | **published** `1935` (firewall it) |
| 9997 | MediaMTX control API | API only | not published | not published |
| 9998 | Prometheus metrics (user `ehimaya-api`) | scraper | not published | not published |

Caddy routes only the media paths: `/live/<uuid>/(whip|whep)[/<session>]` and HLS files `*.m3u8|mp4|mp|ts`
(GET). It never routes MediaMTX's pages, the control API, metrics or anything under `/internal/`. Restrict
8554/1935 in the host firewall to the networks your drones and cameras come from. RTSP and RTMP are not
encrypted, so the token crosses that network in clear: use a VPN, a private APN or a dedicated link for field
units.

## 4. الأسرار / Secrets and settings

| Variable | Where | Notes |
|----------|-------|-------|
| `MEDIAMTX_HOOK_TOKEN` | api + mediamtx | `openssl rand -hex 24`. Sent as `X-Hook-Token` by `infra/mediamtx/hook.sh`. |
| `MEDIAMTX_API_PASSWORD` | api | `openssl rand -hex 24`. User `ehimaya-api`, used for kicks and metrics. |
| `VISION_API_TOKEN` | api + vision | Bearer token of the API's calls to the vision service. |
| `VISION_CALLBACK_TOKEN` | api + vision | `X-Vision-Token` of detection callbacks. |
| `VISION_READ_PASSWORD` | api + vision (`VISION_RTSP_PASSWORD`) | RTSP read password of user `vision`. |
| `STREAM_SIM_TOKEN` | api + stream-sim | **SIMULATION only.** Leave empty in production. |
| `MEDIAMTX_WEBRTC_HOSTS` | mediamtx | ICE address(es) announced to clients. Dev `127.0.0.1`; prod default `API_HOST`. |
| `STREAM_WEBRTC_PUBLIC_URL`, `STREAM_HLS_PUBLIC_URL` | api | Base of `whip_url`, `whep_url`, `hls_url`. Prod: `https://API_HOST`. |
| `STREAM_INGEST_HOST` | api | Host in the RTSP/RTMP URLs given to drones/cameras. Prod default `API_HOST`. |
| `STREAM_MAX_DURATION_S` (900), `STREAM_CREATE_PER_HOUR` (6) | api | Citizen stream limits. |
| `VISION_MIN_CONFIDENCE` (0.45), `VISION_ALERT_CONFIDENCE` (0.6) | api | Floor and confirmation threshold. |
| `RETENTION_STREAM_DAYS` (365) | api | Drone/camera streams without a report, with their recordings. |

With `APP_ENV=production`, the API refuses example or weak values for every secret above, like the earlier
ones.

## 5. من المحاكاة إلى الكاميرات الحقيقية / Switching from simulation to real cameras and drones

The simulator (`infra/stream-sim/stream-sim.sh`, profile `sim`) is marked everywhere. Its log lines start
with `[SIM]`, its streams are labelled `[SIM] …` with `"simulated": true`, and the dashboard shows the amber
"وضع المحاكاة" band. To go live:

1. Stop using the `sim` profile and set `STREAM_SIM_TOKEN=` (empty) in `.env`. Existing `[SIM]` streams stay
   in the history until retention.
2. An ops manager (or sysadmin) registers each drone or camera in the dashboard, or with
   `POST /api/v1/staff/streams {"source": "drone"|"camera", "label": "…", "gouvernorat_code": 11, "lat": …, "lon": …}`.
   The answer carries `publish_url_rtsp`, `publish_url_rtmp` and the `publish_token`, **shown once**. Store
   the token in the device or encoder configuration right away.
3. Configure the device to **push**:
   * RTSP (preferred): `rtsp://<STREAM_INGEST_HOST>:8554/live/<id>`, user any (e.g. `drone`), password = the
     token, transport TCP.
   * RTMP (DJI apps, OBS, most encoders): `rtmp://<STREAM_INGEST_HOST>:1935/live/<id>?token=<token>`.
   * Codecs: H.264 (Baseline/Main) is the safest for WebRTC viewers and the vision service. H.265 records,
     but most browsers cannot play it over WebRTC (they fall back to HLS where supported).
4. Cameras that can only be *pulled* (RTSP server on the camera) need a small relay next to them that pushes
   to MediaMTX, e.g.
   `ffmpeg -rtsp_transport tcp -i rtsp://cam/stream -c copy -f rtsp -rtsp_transport tcp rtsp://drone:<token>@<host>:8554/live/<id>`.
   MediaMTX pull sources are deliberately not used: every path must be backed by a registered stream.
5. Stopping a fixed source in the dashboard disconnects it and retires its token. Register it again to
   issue a new token. A drone whose link drops can simply reconnect with the same token.

Citizens need nothing from operators: the app creates its stream (`POST /api/v1/reports/{id}/streams`) and
publishes with WHIP to `whip_url` using `Authorization: Bearer <publish_token>`.

## 6. الاحتفاظ والخصوصية / Retention and privacy

* A citizen stream follows its report. When the report is anonymised (phase 5.5 retention), the stream's
  location track (`reports.stream_location`) is deleted, its last location is snapped to the anonymisation
  grid, and its account link is replaced like the report's. Its recordings and vision frames are media of the
  report and are deleted with the report's other media (S3 objects and rows).
* Drone/camera/sim streams (no report) are deleted `RETENTION_STREAM_DAYS` after they ended, together with
  their recordings (S3 objects first, then rows; audited `retention.streams`).
* `GET /api/v1/me/export` lists the account's streams with their track and recording ids.
  `DELETE /api/v1/me` ends any active stream and disconnects it. Afterwards the streams follow the reports'
  erasure rules.

## 7. استكشاف الأعطال / Troubleshooting

| Symptom | Check |
|---------|-------|
| Phone gets 401 on WHIP | API log `mediamtx.auth_denied`. The `reason` is one of `not_publishable_<status>` (expired / already used / ended), `protocol_not_allowed` (citizen streams are WHIP-only), `bad_publish_token`, `no_token`. |
| WHIP succeeds but no video; ICE fails | `MEDIAMTX_WEBRTC_HOSTS` must be an address the phone can reach. `8189/udp` must be open on the host and in any cloud firewall. Networks that block UDP need a TURN server (`MTX_WEBRTCICESERVERS2`) or `MTX_WEBRTCLOCALTCPADDRESS=:8189` with that TCP port published. |
| Drone/camera refused | `reason=bad_publish_token` (wrong or retired token), `not_publishable_ended` (stopped by staff: register again), `unknown_stream` (wrong id in the path). RTSP clients first try without credentials, so a single `no_token` before success is normal. |
| Dashboard cannot open a stream | The viewer token lasts 5 min **to start**. `not_readable_<status>` means the stream is no longer pending/live. HLS needs cookies (MediaMTX's cookie check redirect). |
| Stream stays `pending` | The publisher never connected: it expires after 10 min (`end_reason=token_expired`). If it is connected but still pending, the `ready` hook is not reaching the API: look in the MediaMTX log for `hook:` lines and check that `MEDIAMTX_HOOK_TOKEN` is the same in both containers. |
| Recordings missing | `SELECT state, attempts, last_error FROM reports.stream_segment WHERE stream_id = '<id>'`. `pending` with attempts means S3 errors (retried with back-off, failed after 10). `missing` means the file was gone. `failed`/`invalid_path` means the path was outside `/recordings/live/<id>/`. Segments still on the volume are picked up by the orphan scan. |
| Recordings volume filling up | The worker (`PROCESS_ROLE=worker` or `all`) must be running and mount the `recordings` volume. MediaMTX never deletes segments itself. |
| No fire/smoke alerts | `vision_state` of the stream: `disabled` (no `VISION_SERVICE_URL`), `requested` (service unreachable or full, retried), `watching` (OK). An alert needs ≥ `VISION_ALERT_CONFIDENCE` in 3 of the last 5 analysed frames. Alerts per label are throttled for 5 min. |
| stream-sim exits "SHA-256 mismatch" | The clip at `SIM_CLIP_URL` changed: verify it, then update `SIM_CLIP_SHA256`. Without network the simulator falls back to an ffmpeg test pattern. |
| Kick does not disconnect | `MEDIAMTX_API_PASSWORD` must match: the API's control-API calls are themselves authorized through `/internal/mediamtx/auth` (`bad_api_credentials` in the log). |

Useful commands:

```sh
docker compose --env-file .env -f infra/compose.yml logs -f mediamtx           # MediaMTX + hook output
docker compose --env-file .env -f infra/compose.yml logs api | grep -E 'mediamtx\.|streams\.|vision\.'
docker compose --env-file .env -f infra/compose.yml logs stream-sim             # [SIM] lines
```

## 8. مقطع المحاكاة / Simulation clip and licence

Default clip: `people-detection.mp4` from <https://github.com/intel-iot-devkit/sample-videos> (H.264 Baseline
768×432, 12 fps, 49.7 s, 5,482,579 bytes). SHA-256
`18ffe8672d741e3e29c9d891d22c59d453720b086c25b35c88b393d55f92f693`. Licence **CC-BY-4.0**, attribution
"Intel Corporation, sample-videos". The clip is downloaded at run time and not redistributed in this
repository. It shows people walking, not fire, so it exercises the `person` label and the whole pipeline, but
not fire confirmation. To demonstrate fire alerts, point `SIM_CLIP_URL`/`SIM_CLIP_SHA256` at a fire clip whose
licence you have checked (CC0 or CC-BY).

## 9. Limits

* Capacity: 200 concurrent streams nationally (NFR-03) needs MediaMTX on a host with enough uplink. Each
  dashboard viewer is another full-rate copy (WebRTC) and `maxReaders` is 16 per stream. The vision service
  watches at most `VISION_MAX_STREAMS` (default 8 on CPU); the others wait with `vision_state=requested`.
* No TURN server is shipped. Clients behind UDP-blocking networks cannot use WebRTC (see troubleshooting).
* RTSP/RTMP ingest is unencrypted (see §3).
