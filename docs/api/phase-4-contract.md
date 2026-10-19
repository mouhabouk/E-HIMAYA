# عقد الواجهة البرمجية — المرحلة 4 (المؤسسات)

Phase 4 additions to the API contract (phases 2 and 3 stay valid). The live schema is `GET /openapi.json`;
this file fixes what the portal (`apps/portal`), the dashboard (`apps/dashboard`) and the mobile app
(`apps/mobile`) rely on. Conventions are unchanged: `snake_case` JSON, errors `{"detail": "<code>"}` with
stable machine codes that clients translate (never shown raw), cursors are opaque strings.

Requirements covered: FR-B-001…FR-B-009, FR-B-011, FR-A-080, FR-A-081, FR-C-05 (and the institutions
layer of FR-C-10). FR-B-010 (IoT sensors) comes with the alert-rules engine (MQTT) in phase 7;
notifications (push, e-mail, SMS) come in phase 5 — this phase computes the alerts they will send.

## 0. Identities and roles

- Portal and app users sign in to realm `ehimaya-public` (portal client `ehimaya-portal`, Authorization
  Code + PKCE, redirect `http://localhost:5174/*`; app client `ehimaya-mobile` as before). Registration:
  authorization request with `prompt=create`. Keycloak verifies the user's e-mail.
- **Membership of an institution is stored by the API, not in Keycloak**: the realm roles `org_admin`
  and `org_member` are not used for authorization. One account can belong to several institutions.
- Institution roles (FR-B-009):

| role | can |
|---|---|
| `admin` | everything below + edit members and invitations, submit the certificate, delete documents |
| `editor` | edit the card, safety team, hazardous materials, equipment, map features; upload documents; generate a draft certificate |
| `member` | read everything of the institution; report on its behalf; follow its reports |

  The account that registers an institution becomes its first `admin`. The last admin cannot leave or
  be demoted (`409 last_admin`).
- Staff (realm `ehimaya-staff`): read roles for institutions are `operator`, `ops_manager`,
  `field_commander`, `local_committee`, `central_committee`, `org_auditor`, restricted to the token's
  gouvernorat scope as for reports. **Reviews** (registration and certificates) are `org_auditor` only.

Common errors: `authentication_required` (401), `realm_not_allowed` (403: staff token on a portal
endpoint or the reverse), `org_not_found` (404: also when the caller is not a member — existence is not
disclosed), `org_role_required` (403: member without the needed role), `org_not_active` (409: action
that needs an approved institution), `version_conflict` (409: stale `version`, reload and retry),
`consent_required` (428, same charter as citizens, needed before the first report).

## 1. Institution (FR-B-001, FR-B-002, FR-B-003)

### Statuses
`pending_review` → `active` | `rejected`; `active` → `suspended` → `active`. While `pending_review` or
`rejected` the institution can be edited (to fix and resubmit) but cannot report on its behalf, invite
members or submit a certificate (`409 org_not_active`). `POST …/resubmit` moves `rejected` back to
`pending_review`.

### Kinds (`kind`, الصبغة)
`industrial`, `educational`, `hotel`, `government`, `private`, `other`.
Labels: ar صناعية / تعليمية / نزل / حكومية / خاصة / أخرى; fr Industrielle / Éducative / Hôtel /
Administration publique / Privée / Autre; en Industrial / Educational / Hotel / Government / Private / Other.

### Identifier (FR-B-001)
`identifier_type`: `mf` (المعرف الجبائي / matricule fiscal) or `rne` (السجل الوطني للمؤسسات).
- `mf`: 7 digits + a control letter, optionally followed by `/<letter>/<letter>/<3 digits>`
  (e.g. `1234567A` or `1234567A/A/M/000`); stored upper-case without spaces.
- `rne`: 7 digits + a letter (the unique identifier of the national business register).
Unique across institutions (`409 identifier_already_registered`); format errors `422 invalid_identifier`.

### `Organization` (as returned to members)
```json
{
  "id": "uuid", "status": "active", "version": 7,
  "name": "Société X", "kind": "industrial",
  "identifier_type": "mf", "identifier": "1234567A",
  "activity_sector": "Chimie", "activity_type": "Fabrication de peintures",
  "capacity": 420,                       // maximum number of people present (الطاقة الاستيعابية)
  "floors": 3, "height_m": 12.5, "receives_public": false,
  "address": "Route de Gabès km 4", "location": {"lat": 34.70, "lon": 10.72},
  "gouvernorat_code": 61, "delegation_id": null,
  "manager": {"full_name": "…", "phone": "+216…", "email": "…"},   // المسؤول
  "contact_email": "contact@x.tn", "contact_phone": "+216…",
  "classification": {                    // computed, see below
    "family": "industrial", "category": 3, "high_rise": false,
    "required": ["safety_file", "safety_plan", "safety_team", "training", "hazmat_sds", "equipment"],
    "provisional": true
  },
  "completeness": {"ok": false, "missing": ["safety_plan", "hazmat_sds"]},
  "alerts": [{"kind": "training_expired", "ref": "uuid", "since": "2026-09-01"},
             {"kind": "maintenance_overdue", "ref": "uuid", "since": "2026-08-15"}],
  "my_role": "admin",
  "review": {"reason": null, "at": null},  // last registration decision (reason shown when rejected/suspended)
  "created_at": "…", "updated_at": "…"
}
```
Phones are `+216` followed by 8 digits (`422 invalid_phone`). The location must be in Tunisia (same box
as reports, `422`); the gouvernorat is computed from the point.

### Classification (FR-B-003)
Computed by the server from the card and the registers, never typed by the user:
- `family`: `high_rise` when `height_m > 28`; else `industrial` when `kind = industrial` or hazardous
  materials are registered; else `erp` (établissement recevant du public) when `receives_public`;
  else `workplace`.
- `category` (only for `erp`): 1 when capacity > 1500, 2 for 701–1500, 3 for 301–700, 4 for 51–300,
  5 for ≤ 50. `null` for the other families.
- `required` items and `completeness.missing` use these codes: `safety_file` (a stored safety file),
  `safety_plan` (a stored safety plan), `safety_team` (a representative and at least one member),
  `training` (every team member has a training date and none is expired), `hazmat_sds` (a safety data sheet for every
  hazardous material), `equipment` (at least one equipment item, none overdue), `evacuation_points`
  (at least one). Required sets: every family needs `safety_file`, `safety_team`, `equipment`;
  `erp` categories 1–3, `high_rise` and `industrial` also need `safety_plan`, `training`,
  `evacuation_points`; `industrial` with hazardous materials needs `hazmat_sds`.
- `provisional: true` — the thresholds are a working model and **must be validated against the
  official text** (مجلة السلامة والوقاية من أخطار الحريق والانفجار والفزع بالبنايات) with the
  Protection Civile before production. They live in one server module so they can be corrected
  without client changes.

### Endpoints (portal and app, realm `ehimaya-public`)
- `POST /api/v1/orgs` body = the editable card fields (`name`, `kind`, `identifier_type`, `identifier`,
  `activity_sector`, `activity_type`, `capacity`, `floors`, `height_m`, `receives_public`, `address`,
  `location`, `manager`, `contact_email`, `contact_phone`) → `201 Organization` (`pending_review`,
  caller = `admin`). Requires the caller's Keycloak e-mail to be verified (`403 email_not_verified`).
  Limit: 5 institutions created per account (`409 too_many_orgs`).
- `GET /api/v1/orgs/mine` → `[{"id", "name", "kind", "status", "my_role", "alerts_count"}]`.
- `GET /api/v1/orgs/{id}` → `Organization`.
- `PUT /api/v1/orgs/{id}` (editor) body = card fields + `"version"` → `Organization`. Changing
  `identifier` or `name` of an `active` institution sends it back to `pending_review`.
- `POST /api/v1/orgs/{id}/resubmit` (admin; only from `rejected`) → `Organization`.

## 2. Members and invitations (FR-B-009)
- `GET /api/v1/orgs/{id}/members` → `[{"user_id", "display_name", "email", "role", "joined_at"}]`
  (`display_name`/`email` from the member's token claims at their last call).
- `PUT /api/v1/orgs/{id}/members/{user_id}` (admin) body `{"role": "editor"}` → member.
- `DELETE /api/v1/orgs/{id}/members/{user_id}` (admin, or the member themselves to leave) → `204`.
- `POST /api/v1/orgs/{id}/invitations` (admin, `active` only) body `{"email": "…", "role": "member"}` →
  `201 {"id", "email", "role", "expires_at", "token": "…", "accept_url": "http://localhost:5174/invite/<token>"}`.
  The token is shown **once** (only its hash is stored); valid 7 days. The admin shares the link (e-mail
  sending arrives with notifications in phase 5). At most 20 pending invitations (`409 too_many_invitations`).
- `GET /api/v1/orgs/{id}/invitations` (admin) → pending ones, without token.
- `DELETE /api/v1/orgs/{id}/invitations/{invitation_id}` (admin) → `204`.
- `GET /api/v1/invitations/{token}` (signed-in) → `{"org_name", "role", "email", "expires_at"}`.
- `POST /api/v1/invitations/{token}/accept` (signed-in) → `{"org_id", "role"}`. The caller's verified
  e-mail must equal the invited e-mail (case-insensitive) → else `403 invitation_email_mismatch`;
  `404 invitation_not_found` (unknown, used, revoked) and `410 invitation_expired`.

## 3. Safety team (FR-B-005)
`TeamMember`:
```json
{"id": "uuid", "full_name": "…", "team_role": "representative", "position": "Responsable HSE",
 "phone": "+216…", "email": "…", "last_training_on": "2025-03-10", "training_valid_months": 24,
 "training_status": "valid", "training_expires_on": "2027-03-10"}
```
`team_role`: `representative` (الممثل) | `member` (عضو). `training_status`: `valid`, `expiring`
(expires within 60 days), `expired`, `unknown` (no training date). At most one representative
(`409 representative_exists`). `training_valid_months` 1–120, default 24.
- `GET /api/v1/orgs/{id}/team` → `[TeamMember]`
- `POST /api/v1/orgs/{id}/team` (editor) → `201 TeamMember`; `PUT …/team/{member_id}`; `DELETE …/team/{member_id}` → `204`.

## 4. Hazardous materials and equipment (FR-B-006)
`Hazmat`:
```json
{"id": "uuid", "name": "Acétone", "un_number": "1090", "hazard_class": "3",
 "quantity": 2.5, "unit": "t", "storage_location": "Dépôt B", "sds_document_id": "uuid" | null}
```
`un_number`: 4 digits or null (`422 invalid_un_number`). `hazard_class`: ADR class text such as `"3"` or
`"2.1"` (optional, ≤ 8 chars). `unit`: `kg`, `t`, `l`, `m3`. `sds_document_id` must be a document of kind
`sds` of the same institution (`422 invalid_document`).
- `GET|POST /api/v1/orgs/{id}/hazmat`, `PUT|DELETE /api/v1/orgs/{id}/hazmat/{item_id}` (write: editor).

`Equipment`:
```json
{"id": "uuid", "kind": "extinguisher", "count": 24, "location": "Tous niveaux",
 "last_maintenance_on": "2026-02-01", "maintenance_interval_months": 12,
 "maintenance_status": "ok", "next_maintenance_on": "2027-02-01"}
```
`kind`: `extinguisher`, `fire_hose_reel`, `sprinkler`, `smoke_detector`, `alarm_panel`,
`emergency_lighting`, `fire_door`, `other`. `maintenance_status`: `ok`, `due_soon` (within 30 days),
`overdue`, `unknown`.
- `GET|POST /api/v1/orgs/{id}/equipment`, `PUT|DELETE /api/v1/orgs/{id}/equipment/{item_id}`.

## 5. Map features (FR-B-007)
`MapFeature`: `{"id", "kind", "label", "location": {"lat", "lon"}}`, `kind`: `evacuation_point`
(نقطة إخلاء وتجمّع), `water_point` (مأخذ مياه), `alarm` (جهاز إنذار). Must be within 2 km of the
institution's location (`422 feature_too_far`). At most 200 per institution.
- `GET|POST /api/v1/orgs/{id}/features`, `PUT|DELETE /api/v1/orgs/{id}/features/{feature_id}`.

## 6. Documents and versions (FR-B-004)
`Document`:
```json
{"id": "uuid", "kind": "safety_file", "title": "Dossier de sécurité 2026",
 "current_version": {"version": 3, "filename": "dossier.pdf", "content_type": "application/pdf",
                     "bytes": 1832211, "sha256": "…", "status": "stored", "uploaded_at": "…",
                     "uploaded_by": "display name", "note": "Mise à jour après audit"},
 "versions_count": 3}
```
`kind`: `safety_file` (ملف السلامة, PDF), `safety_plan` (مخطط السلامة, PDF or CAD), `sds` (بطاقة بيانات
السلامة, PDF), `other` (PDF). Allowed types: `application/pdf` (all kinds); for `safety_plan` also
`image/vnd.dwg` (`.dwg`) and `image/vnd.dxf` (`.dxf`). Size ≤ 50 MB (CAD ≤ 100 MB).
- `GET /api/v1/orgs/{id}/documents` → `[Document]` (only versions `stored` count as current).
- `POST /api/v1/orgs/{id}/documents` (editor) body `{"kind", "title"}` → `201 Document` (no version yet).
- `PUT /api/v1/orgs/{id}/documents/{doc_id}` (editor) body `{"title"}`; `DELETE` (admin) → `204`
  (refused with `409 document_in_use` while referenced by a hazardous material).
- `GET /api/v1/orgs/{id}/documents/{doc_id}/versions` → `[DocumentVersion]` newest first (history is
  never deleted; a new upload adds a version).
- `GET /api/v1/orgs/{id}/documents/{doc_id}/versions/{version}/download` → `{"url"}` pre-signed, 10 min.

**Upload** = tus, same server and rules as report media (`POST /api/v1/uploads/`, `Authorization`
header forwarded). `Upload-Metadata`: `target=org_document`, `document_id`, `sha256`, `filetype` (one of
the types above), `filename` (kept: it is the institution's file name, shown in the history), `note`
(optional, ≤ 200 chars, else `400 invalid_note`). The server recomputes SHA-256 after upload (`uploading` → `verifying` →
`stored` | `rejected`). Errors: those of §4 of phase 2 plus `404 document_not_found`,
`403 org_role_required`, `415 unsupported_media_type`, `413 document_too_large`.

## 7. Digital safety certificate (FR-B-008)

### Statuses
`draft` → `submitted` → `approved` | `rejected`. An approved certificate stays valid until
`valid_until`; a newer approved certificate supersedes it (`superseded: true`).

`Certificate`:
```json
{"id": "uuid", "code": "EHC-26-61-000123", "status": "submitted", "superseded": false,
 "created_at": "…", "submitted_at": "…", "reviewed_at": null, "review_reason": null,
 "valid_until": null, "fingerprint": "sha256 hex of the certificate content",
 "pdf_sha256": "sha256 hex of the PDF file", "verify_url": "http://localhost:5174/verify/EHC-26-61-000123"}
```

- `POST /api/v1/orgs/{id}/certificate` (editor) → `201 Certificate` (`draft`): snapshots the card,
  classification, team, registers, features and the current document versions (with their SHA-256),
  and renders the PDF (Arabic and French, a QR code to `verify_url`, the fingerprint, the word
  «مسودة / BROUILLON» across draft pages). Replaces any previous draft.
- `GET /api/v1/orgs/{id}/certificates` → `[Certificate]` newest first.
- `GET /api/v1/orgs/{id}/certificates/{cert_id}/pdf` → `{"url"}` pre-signed, 10 min.
- `POST /api/v1/orgs/{id}/certificates/{cert_id}/submit` (admin; `active` institution; draft only;
  `completeness.ok` must be true at submission else `409 incomplete` with `{"detail": "incomplete"}` and
  the client shows `completeness.missing`) → `Certificate` (`submitted`).
  If the registers were completed after the draft was generated, the draft still certifies the incomplete
  state: `409 certificate_outdated`, generate a new draft.
- On approval the server re-renders the PDF without the draft mark, with the approval date, validity
  and the server signature: Ed25519 over the UTF-8 text `<code>|<fingerprint>|<valid_until>` (ISO date).
  The fingerprint itself does not change. Without a configured signing key approval answers
  `503 signing_key_missing` (rejection still works).
- `GET /api/v1/public/certificate-key` (no sign-in) → `{"algorithm": "Ed25519", "public_key": "<base64 of
  the raw 32 bytes>" | null, "signed_message": "<code>|<fingerprint>|<valid_until ISO date>, UTF-8"}`, so
  anyone can check a signature independently.

### Public verification (no sign-in, rate limited)
`GET /api/v1/public/certificates/{code}` →
```json
{"code": "EHC-26-61-000123", "status": "approved", "valid": true, "superseded": false,
 "org_name": "Société X", "org_kind": "industrial", "gouvernorat_code": 61,
 "classification": {"family": "industrial", "category": null},
 "issued_at": "…", "valid_until": "2027-10-19", "fingerprint": "…", "pdf_sha256": "…",
 "signature_valid": true}
```
`valid` = approved, not superseded, not expired and the institution is `active`. Drafts and unknown
codes → `404 not_found` (drafts are never public). The portal page `/verify/:code` shows this and lets
the visitor drop their PDF copy: the browser computes its SHA-256 and compares it with `pdf_sha256`
(the file never leaves the browser).

## 8. Reporting on behalf of an institution (FR-A-080, FR-B-011)
- `POST /api/v1/reports` accepts an optional `"organization_id"`: the caller must be a member (any role)
  of an `active` institution (`404 org_not_found` / `409 org_not_active`). The report is then attached
  to the institution, and operators see its card (see §9). An institution never reports anonymously.
  Reports made from the portal set `"source": "portal"` automatically (`app` otherwise).
- `Report` gains `"organization": {"id", "name"} | null`.
- `GET /api/v1/orgs/{id}/reports?limit=50&cursor=` (any member) →
  `{"items": [{"id", "tracking_code", "category", "status", "text", "received_at", "updated_at",
  "reporter_display_name"}], "next_cursor"}` newest first.
- App (FR-A-081): `GET /api/v1/orgs/mine` then `GET /api/v1/orgs/{id}/summary` →
  `{"id", "name", "kind", "status", "capacity", "address", "location", "classification",
   "team": [{"full_name", "team_role", "phone", "training_status"}],
   "hazmat_count", "hazmat": [{"name", "un_number", "quantity", "unit"}], "alerts_count"}`.

## 9. Staff (dashboard, FR-C-05)
- `GET /api/v1/staff/orgs?status=&kind=&gouvernorat_code=&q=&has_hazmat=true|false&certificate=none|draft|submitted|approved|rejected|expired&limit=50&cursor=`
  → `{"items": [StaffOrg], "next_cursor"}` sorted by name. `StaffOrg` = `{"id", "name", "kind",
  "status", "identifier_type", "identifier", "gouvernorat_code", "capacity", "location", "classification",
  "hazmat_count", "alerts_count", "certificate_status", "certificate_valid_until", "created_at"}`.
  `certificate_status` is the latest certificate's status, or `expired`, or `none`.
- `GET /api/v1/staff/orgs/{id}` → `StaffOrgDetail` = `Organization` (without `my_role`) + `team` +
  `hazmat` + `equipment` + `features` + `documents` + `members` (`[{"display_name", "email", "role"}]`) +
  `certificates`. Opening it is written to the audit log.
- `GET /api/v1/staff/orgs/{id}/documents/{doc_id}/versions` → `[DocumentVersion]` newest first.
- `GET /api/v1/staff/orgs/{id}/documents/{doc_id}/versions/{version}/download` and
  `GET /api/v1/staff/orgs/{id}/certificates/{cert_id}/pdf` → `{"url"}`.
- `GET /api/v1/staff/orgs/{id}/reports?limit&cursor` → `{"items": [StaffReport], "next_cursor"}`.
- `GET /api/v1/staff/orgs/map?bbox=minLon,minLat,maxLon,maxLat` → GeoJSON `FeatureCollection` of
  `active` institutions in scope: points with properties `{"id", "name", "kind", "capacity",
  "hazmat_count", "category", "family"}` (map layer «المؤسسات», FR-C-10).
- `POST /api/v1/staff/orgs/{id}/review` (`org_auditor`) body `{"decision": "approve" | "reject" | "suspend" | "reinstate", "reason": "…"}`
  → `StaffOrgDetail`. `reason` required for `reject` and `suspend` (`422 reason_required`). Allowed:
  approve/reject from `pending_review`, suspend from `active`, reinstate from `suspended`
  (`409 invalid_transition`).
- `GET /api/v1/staff/certificates?status=submitted&limit&cursor` → `{"items": [{"id", "code",
  "status", "org_id", "org_name", "gouvernorat_code", "submitted_at", "completeness"}], "next_cursor"}`
  oldest submission first (review queue).
- `POST /api/v1/staff/certificates/{cert_id}/review` (`org_auditor`) body
  `{"decision": "approve" | "reject", "reason": "…", "valid_until": "2027-10-19"}` → `Certificate`.
  `valid_until` required for approve (between tomorrow and 5 years, `422 invalid_valid_until`);
  `reason` required for reject.
- `StaffReport` and `StaffReportDetail` gain `"organization": {"id", "name", "kind"} | null`; the
  detail also gains `"organization_card"` (for responders): `{"id", "name", "kind", "capacity",
  "address", "location", "classification", "representative": {"full_name", "phone"} | null,
  "hazmat": [Hazmat without ids], "features": [MapFeature]}`.
- `GET /api/v1/staff/kpis` gains `orgs_pending_review` and `certificates_submitted` (in scope). It stays
  limited to the report read roles: an `org_auditor` alone gets `403` and uses the institutions pages.

### Live events (WS `/api/v1/staff/live`, filtered by scope)
- `{"type": "org.updated", "org": StaffOrg}` — registration, review, card change.
- `{"type": "certificate.updated", "certificate": {"id", "code", "status", "org_id", "org_name", "gouvernorat_code"}}`.

## 10. Priority: sensitive sites (BR-20)
The `sensitive_sites` priority component (shown "no data" in phase 3) now uses the institutions: a
report within 300 m of an `active` institution gets `value` = 1.0 if it stores hazardous materials,
0.8 for `high_rise` or `erp` category 1–2, 0.6 for other `erp`/`educational`, 0.4 otherwise (the most
sensitive institution in the radius wins, then the nearest); `detail` = `{"org_id", "name", "distance_m",
"reason": "hazmat|high_rise|large_public|public|nearby"}`. With no institution in the radius the value
stays `null` (`detail.reason = "no_site_nearby"`) and the component is left out, as before.
The component can only **raise** a priority: when counting it would lower the score (a low-sensitivity
site next to a grave emergency) it gets 0 points and `detail.counted = false`. Its weight is in the AI
settings (default 5, unchanged).

The credibility score gains a component `organization` (+10, `detail = {"org_id"}`) for reports made on
behalf of an institution.

## 11. Error codes added in this phase
`realm_not_allowed`, `org_not_found`, `org_role_required`, `org_not_active`, `version_conflict`,
`email_not_verified`, `too_many_orgs`, `identifier_already_registered`, `invalid_identifier`,
`invalid_phone`, `last_admin`, `too_many_invitations`, `invitation_not_found`, `invitation_expired`,
`invitation_email_mismatch`, `representative_exists`, `invalid_un_number`, `invalid_document`,
`feature_too_far`, `too_many_features`, `document_not_found`, `document_in_use`, `document_too_large`,
`incomplete`, `certificate_outdated`, `signing_key_missing`, `invalid_valid_until`, `reason_required`,
`invalid_transition`, `invalid_note`, `not_found`.
