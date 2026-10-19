# عقد الواجهة البرمجية — المرحلة 5.5 (التحصين)

Phase 5.5 (hardening) additions to the API contract; phases 2–5 stay valid. The live schema is
`GET /openapi.json` (disabled in production). Conventions are unchanged: `snake_case` JSON, errors
`{"detail": "<code>"}`, `429 rate_limited` with `Retry-After`.

Each hardening area has its own section below; workers append theirs.

## Data protection (A5 field encryption, A6 retention and citizen rights)

Tunisian personal data law 2004-63 (Organic Law of 27 July 2004): security of processing, limited
retention, right of access and of erasure. Owner: `services/api/app/modules/privacy`, `app/core/crypto.py`,
migration `0010_data_protection`.

### 1. Citizen rights endpoints

Both accept a registered citizen (`Authorization: Bearer`, realm `ehimaya-public`) **or** an anonymous
device identity (`X-Device-Key`), like the reporting endpoints. Without either: `401 authentication_required`.

#### `GET /api/v1/me/export` — right of access

`200 application/json` (`Cache-Control: no-store`, `Content-Disposition: attachment; filename="ehimaya-export-<date>.json"`),
everything held on the caller, decrypted:

```json
{
  "generated_at": "2026-10-19T10:00:00Z",
  "account": {"user_id": "uuid", "kind": "citizen|organization|anonymous", "status": "active", "created_at": "…"},
  "profile": {
    "first_name": "Amel", "last_name": "Jaziri", "cin": "01234567", "phone": "+21698123456",
    "phone_verified_at": null, "email": "amel@example.tn", "email_verified_at": "…",
    "gouvernorat_code": 61, "delegation_id": 6101, "address": "…",
    "medical": {"blood_group": "O-", "conditions": null, "allergies": "…", "medications": null,
                "emergency_contact_name": null, "emergency_contact_phone": "+21698765432"},
    "locale": "fr", "updated_at": "…"
  },
  "consents": [{"charter_version": "2026-10", "locale": "ar", "platform": "android", "accepted_at": "…"}],
  "reports": [{
    "id": "uuid", "tracking_code": "EH-26-61-0000042", "category": "fire", "status": "closed",
    "text": "…", "lang": "fr", "text_ar": "…",
    "location": {"lat": 34.74, "lon": 10.76, "accuracy_m": 8.0}, "gouvernorat_code": 61,
    "created_at": "…", "received_at": "…", "updated_at": "…",
    "history": [{"status": "received", "at": "…"}],
    "media": [{"id": "uuid", "kind": "audio", "content_type": "audio/mp4", "bytes": 12345, "sha256": "…",
               "duration_s": 12.5, "status": "stored", "created_at": "…",
               "transcript": "…", "translation_ar": "…"}]
  }],
  "volunteer": null,
  "devices": [{"platform": "android", "locale": "ar", "token_suffix": "a1b2c3d4", "gouvernorat_code": 61,
               "has_location": true, "created_at": "…", "updated_at": "…"}],
  "messages": [{"id": "uuid", "kind": "info", "title": {"ar": "…"}, "body": {"ar": "…"}, "published_at": "…"}]
}
```

* `profile` is `null` for anonymous identities and for citizens without a profile; `volunteer` has the shape
  of `GET /api/v1/me/volunteer`; `messages` are the notifications addressed to this account only
  (public alerts are not personal data); staff notes on status changes are not included.
* Media files themselves are not embedded (metadata only); the CIN is given in full (it is the caller's).
* Audited as `user.export` (target `account:<user_id>`). Rate limit: **3 per day per account**, plus 30 per
  day per client address for anonymous identities → `429 rate_limited`.

#### `POST /api/v1/me/delete` — right to erasure

Body `{"confirm": "DELETE"}` (anything else: `422`). Answer `202 {"status": "deleted"}`. Immediately:

* profile row deleted (names, CIN, phone, e-mail, address, medical data); push devices deleted; pending
  personal pushes dropped; institution memberships ended;
* volunteer record (if any) set `withdrawn`, its free text wiped, readiness and live position cleared;
* the account keeps only its random id: Keycloak subject / device pseudonym removed, `deleted_at` set.
  Reports are **kept** for the legal retention period, attached to that identifier-less id (dashboard shows
  no reporter identity), then anonymised by the retention job like every report;
* registered citizens: the Keycloak subject is queued in `identity.erasure_request` — the API holds no
  Keycloak admin credentials, so an administrator disables the account in realm `ehimaya-public` and
  acknowledges it: `python -m app.modules.privacy.cli erasures` (list) / `… erasures --done <id>`;
* audited as `user.delete` (details: kind, reports kept, devices, organisations left).

Errors: `409 last_admin` when the caller is the last administrator of an institution (hand over first, as for
leaving it). Rate limit: 5 per day per account. After erasure the same token or device key resolves to a
**new, empty** account: the app must sign out (registered) or generate a new device key (anonymous) and
clear its local data.

#### Profile: medical data (`PUT/GET /api/v1/me/profile`)

New optional field `medical` (stored encrypted): `blood_group` (`A+ A- B+ B- AB+ AB- O+ O-`),
`conditions` (≤500), `allergies` (≤300), `medications` (≤300), `emergency_contact_name` (≤100),
`emergency_contact_phone` (`+216XXXXXXXX`). In `PUT`: field left out = unchanged, `null` = erased.

### 2. Field-level encryption at rest

AES-256-GCM, format `key version (1 byte) | nonce (12) | ciphertext+tag`, the column name as associated
data (a ciphertext copied into another column does not decrypt). The API encrypts on write and decrypts on
read (SQLAlchemy column types `EncryptedText` / `EncryptedJSON`): API responses, the dashboard and the AI
service (which receives the text from the API) see clear text; the database, its backups and replicas do not.

| data | column | lookup |
|---|---|---|
| CIN | `identity.profile.cin_enc` | `cin_hash` blind index (uniqueness) |
| phone | `identity.profile.phone_enc` | `phone_hash` blind index (volunteer search by full number, SMS de-duplication) |
| address | `identity.profile.address_enc` | — |
| medical data | `identity.profile.medical_enc` (JSON) | — |
| report text, Arabic translation | `reports.report.text_original_enc`, `text_ar_enc` | `search_tokens`: blind index of each normalised word |
| audio/video transcript, its translation | `reports.media.transcript_enc`, `translation_ar_enc` | — |
| volunteer "other skill", notes | `identity.volunteer.other_skill_enc`, `notes_enc` | — |
| AI extraction (includes a summary of the text) | `ai.analysis.extraction_enc` (JSON) | — |
| domain events (report text, volunteer phone…) | `events.outbox.payload = {"sealed": …}`, sealed on the bus too | — |

Stays in clear, by decision:

* **names** (`first_name`, `last_name`): dispatchers search volunteers by partial name; protected by the
  database roles, disk encryption and the audit of every staff view;
* **e-mail**: it is the Keycloak login (already in clear there), the delivery address of the e-mail channel
  and the key of the exact one-user lookup (`ix_profile_email_lower`, migration 0008);
* **report location** (PostGIS point): needed for the gouvernorat scope, the map, grouping and sensitive
  sites; it is precise on purpose (responders go there) and coarsened to 0.01° (~1 km) at anonymisation.
  Push-device positions are already rounded to 0.01° when registered;
* the report **embedding** (needed for similarity grouping), categories, statuses, times, scores;
* institution data (organisation address, contacts, team members): business contacts reviewed by staff;
* staff-written text (status notes, review reasons, audit log), which the audit chain must keep verifiable;
* outgoing e-mail rows (`notify.outbox`, address and body) until purged by retention.

Staff search (`GET /api/v1/staff/reports?q=`) now matches the tracking code (substring, as before) or
**whole words** of the report text and its Arabic translation (case, Latin accents and Arabic
diacritics/letter variants folded) — no longer substrings of the text. Volunteer search (`q`) matches
partial names, or a complete phone number in any usual spelling (`98 123 456`, `+21698123456`, `21698123456`).

**Key rotation.** `FIELD_ENCRYPTION_KEYS="2:<base64>"` adds a key version (the highest becomes active unless
`FIELD_ENCRYPTION_ACTIVE_VERSION` is set); all configured versions stay readable. Then run
`python -m app.modules.privacy.cli reencrypt` (`--dry-run` counts what remains; safe to interrupt and to run
while serving) and retire the old version once it reports 0. `FIELD_ENCRYPTION_KEY` (version 1) stays
configured: it roots the blind indexes, which therefore do not change with rotation.

**Migration 0010** encrypts existing rows in keyset batches with the configured keys (idempotent: only rows
whose encrypted column is empty), computes the blind indexes, seals pending events and drops the clear
columns; the downgrade decrypts everything back.

### 3. Retention (worker role)

Loop `retention` (registered in `WORKER_LOOPS`, runs with `PROCESS_ROLE=worker|all`) every
`RETENTION_INTERVAL_S` (3600). Jobs work in bounded batches under a PostgreSQL advisory lock (safe with
several workers); `RETENTION_ENABLED=false` disables them; `python -m app.modules.privacy.cli retention`
runs them once.

| data | rule | setting (days) | default |
|---|---|---|---|
| domain events already relayed (`events.outbox`) | deleted | `RETENTION_EVENTS_DAYS` | 7 |
| individual pushes/e-mails sent, skipped or failed (`notify.outbox`) | deleted | `RETENTION_NOTIFY_OUTBOX_DAYS` | 30 |
| finished fan-out jobs and their counters (`notify.dispatch`) | deleted | `RETENTION_NOTIFY_DISPATCH_DAYS` | 180 |
| rounded position of a push device not refreshed by the app | set to null | `RETENTION_DEVICE_LOCATION_DAYS` | 30 |
| push device (token) not refreshed by the app | deleted | `RETENTION_DEVICE_DAYS` | 180 |
| closed or rejected report, after its last change | **anonymised**: reporter detached (fixed account `00000000-…`), text, translation, search words, AI summary, embedding, client id and staff notes wiped, media rows and objects deleted, point snapped to 0.01°, accuracy dropped; category, status, gouvernorat/delegation, times, scores, incident and institution kept for statistics; audited `retention.anonymise` | `RETENTION_REPORT_DAYS` | 1826 (5 years) |
| acceptance of a superseded charter version (a newer one was accepted) | deleted | `RETENTION_CONSENT_DAYS` | 1826 |
| anonymous device identity with no report and no device | deleted | `RETENTION_ANON_ACCOUNT_DAYS` | 365 |
| erasure request once the Keycloak account was disabled | deleted | `RETENTION_ERASURE_DAYS` | 30 |
| audit log | kept (append-only, 5 years per architecture §5.3; the runtime role cannot delete it) | — | — |
| volunteers' live position | Valkey only, during readiness (unchanged) | — | — |

Reports that are never closed are not anonymised by this job (they stay in the operators' queues).
