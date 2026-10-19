# عقد الواجهة البرمجية — المرحلة 2 (مسار البلاغ الأساسي)

Phase 2 API contract shared by the backend (`services/api`), the mobile app (`apps/mobile`) and the
dashboard (`apps/dashboard`). The live, authoritative schema is the API's OpenAPI document
(`GET /openapi.json`); this file fixes the decisions the three clients depend on.

All paths are under the API base URL (dev: `http://localhost:8000`). JSON bodies use `snake_case`.
Errors use FastAPI's shape `{"detail": "<machine_code or message>"}`; the machine codes listed below
are stable and must be mapped to translated messages on the clients (never shown raw).

## 1. Identities

| Caller | How it authenticates | Account |
|---|---|---|
| Citizen / volunteer (registered) | `Authorization: Bearer <access token>` from realm `ehimaya-public`, client `ehimaya-mobile` (Authorization Code + PKCE, redirect `tn.ehimaya.app:/oauth2redirect`) | created on first call (just-in-time), `kind=citizen` |
| Anonymous citizen | `X-Device-Key: <base64url, 32 random bytes>` generated once at install and kept in the platform secure storage. Never sent together with a Bearer token. | the server derives `pseudonym = HMAC-SHA256(server secret, device key)`; `kind=anonymous`. No IP address is stored for these requests (BR-01, BR-02). |
| Staff | `Authorization: Bearer <access token>` from realm `ehimaya-staff`, client `ehimaya-dashboard` (Authorization Code + PKCE, TOTP enforced by Keycloak, redirect `http://localhost:5173/*`) | none (staff are not reporters) |

Keycloak (dev): `http://localhost:8080/realms/<realm>`; registration page for citizens: authorization
request with `prompt=create`.

Error codes: `authentication_required` (401), `invalid_device_key` (400), `anon_blocked` (403: the
anonymous pseudonym is quarantined after confirmed false reports; the app must offer registration),
`account_suspended` (403), `consent_required` (428), `rate_limited` (429, with `Retry-After`).

### Profile of a registered citizen (FR-A-005)
- `GET /api/v1/me/profile` → `{"first_name", "last_name", "cin_last4", "phone", "email", "gouvernorat_code", "delegation_id", "address", "locale"}` (fields null until filled).
- `PUT /api/v1/me/profile` body `{"first_name", "last_name", "cin": "8 digits", "phone": "+216XXXXXXXX", "gouvernorat_code", "delegation_id", "address", "locale"}` → same as GET.
  The CIN is stored encrypted (AES-256-GCM) with a keyed hash for uniqueness (`409 cin_already_registered`);
  the délégation must belong to the gouvernorat (`422 delegation_mismatch`). Email comes from Keycloak.

## 2. Charter consent (FR-A-001)

- `GET /api/v1/charter` → `{"version": "2026-10"}`: the version the server currently requires.
  The charter text itself ships in the clients' translation files, keyed by version.
- `POST /api/v1/consents` (citizen or anonymous) body `{"charter_version": "2026-10", "locale": "ar|fr|en", "platform": "android|ios|web"}` → `201 {"charter_version", "accepted_at"}`.
  Any other version → `422 unknown_charter_version`.
- Report creation answers `428 consent_required` until the caller has accepted the current version.

## 3. Reports

### Categories (FR-A-040)
`sos`, `fire`, `flood`, `traffic_accident`, `drowning`, `landslide`, `chemical_leak`, `medical`, `other`.
`sos` is what the one-touch SOS button sends (location only, no form).
`GET /api/v1/reports/categories?lang=ar|fr|en` → `[{"code": "fire", "label": "حريق"}]`.

### Status lifecycle (FR-A-032)
`received` → `in_progress` → `intervened` / `ongoing` → `closed`; `rejected` from `received` or `in_progress`.

| from | allowed next |
|---|---|
| received | in_progress, rejected |
| in_progress | intervened, ongoing, closed, rejected |
| intervened | ongoing, closed |
| ongoing | intervened, closed |
| closed, rejected | (final) |

Labels: ar مستلم / قيد المعالجة / تم التدخل / التدخل متواصل / أُغلق التدخل / مرفوض;
fr Reçu / En cours de traitement / Intervention effectuée / Intervention en cours / Intervention clôturée / Rejeté;
en Received / Being processed / Intervened / Intervention ongoing / Closed / Rejected.

### Tracking code (FR-A-046)
Format `EH-<yy>-<gouvernorat code>-<7 digits>`, e.g. `EH-26-61-0004821` (`00` when the location is
outside the 24 gouvernorats). While offline the app shows a local temporary code `TMP-<6 chars>` and
replaces it with the server code once the report is synced.

### Create — `POST /api/v1/reports` (citizen or anonymous)
```json
{
  "client_uuid": "6f1c…",            // generated on the device; idempotency key
  "category": "fire",
  "text": "…",                        // optional, ≤ 4000 chars
  "lang": "ar",                       // optional: ar | fr | en (language of text)
  "location": {"lat": 34.74, "lon": 10.76, "accuracy_m": 12.5},
  "created_at": "2026-10-19T10:15:00Z" // device time; may be in the past when sent offline
}
```
→ `201` (new) or `200` (same `client_uuid` already received from the same caller) with a `Report`:
```json
{
  "id": "uuid", "tracking_code": "EH-26-61-0004821", "client_uuid": "uuid",
  "category": "fire", "status": "received", "text": "…", "lang": "ar",
  "location": {"lat": 34.74, "lon": 10.76, "accuracy_m": 12.5},
  "gouvernorat_code": 61, "created_at": "…", "received_at": "…", "updated_at": "…",
  "media": [{"id": "uuid", "kind": "image", "bytes": 123456, "sha256": "…", "status": "stored"}]
}
```
The gouvernorat is computed by the server from the point (PostGIS). `409 client_uuid_conflict` if the
same `client_uuid` was used by another caller. Location must fall in a bounding box around Tunisia
(lat 30.0–37.6, lon 7.4–11.7) → otherwise `422`.

### My reports — `GET /api/v1/reports/mine?limit=50&before=<received_at ISO>`
→ `{"items": [Report], "next_before": "…" | null}` newest first.

### Public tracking — `GET /api/v1/reports/track/{tracking_code}` (no auth, rate limited)
→ `{"tracking_code", "status", "received_at", "updated_at", "history": [{"status", "at"}]}`.
Nothing else (no category, text or location). `404 not_found`.

## 4. Media upload — tus 1.0 (FR-A-041, FR-A-047, NFR-07)

Resumable uploads go to the tus server at `POST /api/v1/uploads/` (dev: tusd on
`http://localhost:1080/api/v1/uploads/`). Send the same identity headers as the API
(`Authorization` or `X-Device-Key`); tusd forwards them to the API, which authorizes each upload.

`Upload-Metadata` (tus base64 pairs) must contain:
- `report_id` — the report's server `id` (create the report first, then upload its media)
- `kind` — `image` | `video` | `audio`
- `sha256` — lowercase hex SHA-256 of the whole file, computed on the device
- `filetype` — MIME type (`image/jpeg`, `image/png`, `image/heic`, `video/mp4`, `audio/mp4`, `audio/aac`, `audio/mpeg`, `audio/ogg`, `audio/wav`)
- `filename` — optional

Limits: image ≤ 20 MB, video ≤ 300 MB, audio ≤ 30 MB (and ≤ 5 minutes, enforced by the app);
at most 10 files per report; uploads accepted until 24 h after the report was received.
Use the `creation` extension, then `PATCH` in chunks (recommended 1 MB on mobile networks) and
`HEAD` to resume from `Upload-Offset` after a disconnect.

When the upload completes the server recomputes SHA-256 over the stored object. If it differs from
the declared value the media is marked `rejected` and the object deleted. Media `status`:
`uploading` → `verifying` → `stored` | `rejected` (rejected media are hidden from lists).
The original is never modified (derived copies come later). Downloads through tusd are disabled;
staff read media through short-lived pre-signed links only.

A refused upload creation answers with the HTTP status below and a body `{"detail": "<code>"}`:
`401 authentication_required`, `403 anon_blocked`, `404 report_not_found`, `400 invalid_sha256`,
`400 invalid_report_id`, `400 upload_length_required` (deferred length is not accepted),
`400 concatenation_not_supported`, `413 media_too_large`, `415 unsupported_media_type`,
`409 too_many_media`, `409 upload_window_closed`.

## 5. Staff (dashboard) — realm `ehimaya-staff`

Read roles: `operator`, `ops_manager`, `field_commander`, `local_committee`, `central_committee`.
Status changes: `operator`, `ops_manager`, `field_commander`.
Every result is restricted to the token's geographic scope (`gouvernorat_code` claim, or national).

- `GET /api/v1/staff/kpis?since=<ISO, default now-24h>` →
  `{"since", "total", "by_status": {"received": 3, …}, "by_category": {"fire": 2, …},
    "by_gouvernorat": [{"code": 61, "count": 4}], "avg_first_response_s": 312.5 | null}`
- `GET /api/v1/staff/reports?status=&category=&gouvernorat_code=&since=&until=&bbox=minLon,minLat,maxLon,maxLat&q=&limit=50&cursor=`
  → `{"items": [StaffReport], "next_cursor": "…" | null}` newest first. `status` and `category`
  accept comma-separated lists; `q` searches the tracking code and the text.
- `GET /api/v1/staff/reports/{id}` → `StaffReportDetail` = `StaffReport` + `history`
  (`[{"status", "at", "actor", "note"}]`) + `allowed_transitions` (statuses reachable from the current one) +
  `media[].url` (pre-signed, 10 minutes, only when `status` is `stored`) + `reporter` (`{"kind": "citizen", "first_name", "last_name", "phone"}`
  or `{"kind": "anonymous"}`). Opening a detail is written to the audit log.
- `POST /api/v1/staff/reports/{id}/status` body `{"status": "in_progress", "note": "optional"}` →
  `StaffReportDetail`. Invalid transition → `409 invalid_transition`.

`StaffReport` = `Report` fields + `reporter_kind` (`citizen` | `anonymous`) + `media_count` +
`gouvernorat_code` + `delegation_id` (null for now).

### Live updates — `WS /api/v1/staff/live`
1. Client connects and sends, within 10 s: `{"type": "auth", "token": "<staff access token>"}`.
2. Server answers `{"type": "ready"}` (or closes with code 4401 / 4403).
3. Server pushes, filtered by the user's scope:
   - `{"type": "report.created", "report": StaffReport}`
   - `{"type": "report.status_changed", "report": StaffReport}`
   - `{"type": "media.stored", "report_id": "uuid", "media": {…}}`
4. The client re-sends `{"type": "auth", "token": …}` after each token refresh; the server closes the
   socket with 4401 when the token expires without refresh. Clients reconnect with back-off.

## 6. Emergency numbers (FR-A-033, BR-30, scenario 0)
198 الحماية المدنية · 190 الإسعاف الطبي الاستعجالي (SAMU) · 197 شرطة النجدة · 193 الحرس الوطني.
The app dials these with the phone's native dialer (`tel:` URI) directly over the SIM. No API call,
works offline, never routed through the platform.
