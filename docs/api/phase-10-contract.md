# API contract — phase 10 (hardening)

Phase 10 additions and changes. Phases 2–9 stay valid except where this document says otherwise. The conventions
are unchanged: `snake_case` JSON, errors `{"detail": "<code>"}`, cursor pagination, every staff write audited.
The source is the review `docs/phase-10/review.md` (cited as "review §n").

Golden rules for this phase:
* **The API verifies, it does not trust.** A staff token proves MFA (`amr`) or it is refused, and a revoked
  session stops at the next request, not when the token expires.
* **Nothing is lost silently.** WAL is archived every minute, a base backup is taken every night, and a restore
  drill proves both. A failed alert delivery reaches a person.
* **Evidence is anchored outside the database.** Media hashes and the audit chain head are sealed periodically,
  signed, and can be timestamped by an external authority.
* **What CI cannot run on a private repository runs in `scripts/ci-local.sh`.** Every new check is wired in both
  places.

Migrations (each `down_revision` is the previous number):

| Migration | Content |
|---|---|
| `0026_access_sign_out` | account log action `account.sign_out` (§1.2) |
| `0027_orgs_certificate_revocation` | certificate `revoked` state, `key_id` (§4.1) |
| `0028_notify_four_eyes` | alert reviewer and emergency override (§5.1) |
| `0029_identity_consent_purpose` | consent purpose (§4.2) |
| `0030_evidence_anchor` | schema `evidence`, anchors (§4.3) + RLS |

---

## 0. Repairs of the untested dependency merges (review §1)

* Python services go back to the base image that CI tests: `python:3.12-slim` (api, ai, vision, notify-sim), with
  the digest that was pinned before the merges. Moving to a newer Python is a deliberate change, made together with
  the CI matrix and the locks.
* `infra/postgres` goes back to `postgres:17-bookworm`, which matches the PostGIS and pgvector packages for 17 and
  the volume layout. A move to PostgreSQL 18 needs `pg_upgrade` and its own runbook.
* The dashboard and portal images go back to `node:22-alpine`, the version CI builds with.
* Keycloak 26.8 stays (both realms import, see §1.1), and CI and ci-local move to the same 26.8 digest.
* `.github/dependabot.yml` ignores semver-major updates of the `python`, `postgres`, `node` and `keycloak` images.
  It also ignores semver-minor updates of the `python` image, because 3.12 → 3.15 is a "minor" bump in semver
  terms. Those updates become planned work, not routine pull requests.

## 1. Authentication

### 1.1 MFA proven in the token

Keycloak, staff realm (`infra/keycloak/realms/ehimaya-staff-realm.json`):
* New top-level flow `ehimaya browser`, bound as `browserFlow`:
  * cookie (ALTERNATIVE);
  * `forms` sub-flow (ALTERNATIVE) containing the username/password form (REQUIRED, reference `pwd`) and the OTP form
    (REQUIRED, reference `otp`).
  The OTP form is unconditional. A user without an OTP credential is sent to `CONFIGURE_TOTP`.
* The `ehimaya-dashboard` client gets the `oidc-amr-mapper` (access and ID token).
* Refresh tokens are rotated (`revokeRefreshToken: true`, `refreshTokenMaxReuse: 0`) in both realms.

API (`core/security.py`):
* Setting `STAFF_MFA_REQUIRED` (default `true`). A staff-realm token whose `amr` does not contain one of `otp`,
  `hwk` or `mfa` is refused with **`401 mfa_required`** (`WWW-Authenticate: Bearer error="insufficient_user_authentication"`).
* Public-realm tokens are not affected.

Dashboard: on `401 mfa_required` it calls `signinRedirect({ prompt: "login" })` once per tab and otherwise shows
`errors.mfa_required`; on `401 session_revoked` it forgets the session and goes back to the login page. Only the first sign-in after enrolment needs this: the token issued during the enrolment
carries `amr: ["pwd"]`, which was checked with Keycloak 26.8.

CI and ci-local: `infra/keycloak/check_mfa.py` imports the realms into Keycloak 26.8, creates a staff user, signs in
through the browser flow (password, OTP enrolment, then a second sign-in with OTP), and asserts:
* the first token has no `otp` in `amr`;
* the second token has `amr ⊇ {pwd, otp}`.

### 1.2 Session revocation

* `core/sessions.py`: `revoke(subject, at=now)` stores a "not before" time per subject in Valkey
  (`auth:nbf:<sub>`, TTL 1 day, which is longer than any access token). It falls back to process memory when no
  Valkey is configured (tests, single process).
* `get_optional_principal` refuses a token whose `iat` is earlier than that time with **`401 session_revoked`**.
* If Valkey cannot be reached, the check is skipped, `ehimaya_session_check_degraded_total` is incremented and a
  warning is logged. Refusing every staff request during a Valkey outage would stop the emergency room. Access
  tokens live 5 minutes, which bounds the exposure.
* Revocation is triggered by:
  * the account administration proxy (phase 9), when it disables an account, changes its roles or resets its
    credentials;
  * `POST /api/v1/staff/accounts/{id}/sign-out` (security_admin; regional_account_admin within its gouvernorat,
    with the same scope rules as the other account actions), which also calls Keycloak `logout`. It answers `204`
    and audits `account.sign_out`.
  * `POST /api/v1/me/sign-out-everywhere` (any signed-in principal, either realm), which answers `204`.

## 2. Resilience

### 2.1 Backups (NFR-12: RPO < 5 min, RTO < 1 h)

* PostgreSQL archives WAL continuously: `archive_mode=on`,
  `archive_command='/usr/local/bin/ehimaya-archive-wal %p %f'`, `archive_timeout=60`. The script copies the segment
  atomically into `/archive/wal` (a separate volume) and never overwrites an existing segment with different bytes.
* Service `backup` (production compose): one `pg_basebackup` (tar, compressed, with a manifest) each night into
  `/archive/base/<date>`. It keeps 7 daily backups and the WAL needed by the oldest one. A copy to a second site goes
  through `BACKUP_REMOTE` (an rclone or S3 target, documented, off by default).
* `infra/backup/restore.sh <base> [--target-time …]` restores into an empty data directory with
  `restore_command` and `recovery_target_time`.
* `infra/backup/drill.sh` is the restore drill:
  1. start a throwaway cluster with archiving on;
  2. migrate it and write rows;
  3. take a base backup and write more rows;
  4. write a marker and wait for its segment to be archived;
  5. restore into a second cluster at a target time;
  6. assert that every row written before the target is present and none written after it, and that
     `audit.verify_chain()` is intact;
  7. print the elapsed restore time (RTO) and the archive lag (RPO).
  It runs in CI (job "Backup · restore drill") and in ci-local, and the docs ask for it once a quarter on the real
  backups (`docs/runbooks/backup-restore.md`).

### 2.2 Failure behaviour (NFR-02)

Tests `tests/test_resilience.py` cover the paths an SOS takes when a dependency is down:
* Valkey unreachable → `POST /reports` (SOS) answers 201 and the rate limit still applies (local counters);
* NATS absent → the report is accepted and its event stays in `events.outbox` until a publisher drains it;
* the AI service is down → the report is accepted and enrichment is retried;
* the identity provider's JWKS is unreachable → anonymous SOS still works and staff get `503
  identity_provider_unavailable`, never 500.

### 2.3 Monitoring (NFR-13)

`infra/monitoring/` contains:
* `prometheus.yml`, which scrapes the API, worker, MediaMTX and Keycloak management endpoints;
* `alerts.yml`, with rules for:
  * report intake errors and latency (p95 > 2 s, NFR-01);
  * outbox backlog;
  * notification failures;
  * WAL archive lag > 5 min and last base backup > 26 h (both read from a textfile written by the backup service);
  * rate limiter degraded;
  * session check degraded;
  * instance down;
* `alertmanager.yml`, which sends to e-mail by default.
The compose profile `monitoring` (production file) starts Prometheus and Alertmanager on the internal network
only. CI validates the rules with `promtool check rules` and unit-tests them with `promtool test rules`.

## 3. Security assurance

* `docs/security/threat-model.md`: STRIDE per trust boundary (citizen app ↔ API, dashboard ↔ API, API ↔ DB,
  media hooks, telephony, AI and vision, Keycloak), each threat with its control and the evidence (test or file).
* `docs/security/asvs-l2.md`: OWASP ASVS 4.0.3 level 2, chapter by chapter, marked "met", "partial" or "n/a", with
  evidence. A partial item names who must act.
* Dependency audit in CI and ci-local:
  * `pip-audit` on each Python lock (exported with `uv export --frozen`);
  * `npm audit --omit=dev --audit-level=high` on the dashboard and portal.
  A finding fails the job, unless it is listed with a reason and an expiry date in `.github/audit-allowlist.yml`.
* DAST: `infra/security/zap/run.sh` runs the ZAP API scan (pinned image) against a running stack with the exported
  OpenAPI document (§6.1) and a staff token. It is run by hand before a release, and its report goes in
  `docs/security/`.

## 4. Data protection

### 4.1 Certificate revocation and key rotation (L05)

* Status `revoked`, reachable only from `approved`, via `POST /api/v1/staff/certificates/{id}/revoke`
  `{"reason": "…"}`:
  * only `org_auditor` may revoke, within its scope;
  * a reason is required, otherwise `422 reason_required`;
  * a certificate that is not approved answers `409 invalid_transition`;
  * a certificate already revoked answers `409 already_revoked`.
  New columns `revoked_at`, `revoked_by`, `revoke_reason`. It emits `certificate.updated` and is audited as
  `certificate.revoke`.
* The public verification (`GET /api/v1/public/certificates/{code}`) answers `valid: false, revoked: true,
  revoked_at` and never shows the reason.
* `key_id` = the first 16 hex characters of the SHA-256 of the raw public key, stored at approval.
  `CERTIFICATE_PREVIOUS_PUBLIC_KEYS` (comma-separated base64 raw public keys) keeps old keys valid for
  verification only. A certificate whose `key_id` is unknown is not valid.
* The certificate (HTML/PDF) and the public page say, in ar/fr/en, that the file is a self-assessment recorded on
  the e-Himaya platform and reviewed by its auditors, and not an official certificate of the civil protection or of
  another administration.

### 4.2 Volunteer location (D12)

* `identity.consent` gains `purpose` (`charter` | `volunteer_location`, default `charter`).
* `POST /api/v1/me/consents` `{"purpose": "volunteer_location", "version": "1"}` records it (idempotent) and
  answers `204`. `DELETE /api/v1/me/consents/volunteer_location` withdraws it: the stored position is dropped
  immediately and readiness ends.
* `POST /api/v1/me/volunteer/readiness` with `ready: true`, and `PUT /api/v1/me/volunteer/location`, answer
  **`409 location_consent_required`** while no consent is in force. The consent row keeps `withdrawn_at` when
  withdrawn, so the privacy export shows both. The volunteer's own view (`GET /api/v1/me/volunteer`) gains
  `location_consent: bool`.
* What staff see: `distance_m` in suggestions is rounded to 100 m (to 50 m under 500 m), and the volunteer map
  (`GET /api/v1/staff/volunteers/map`) shows positions rounded to 3 decimals (about 100 m). The raw position is
  never returned to staff. The exact distance is still used to rank the candidates.
* Mobile: before a volunteer first becomes ready, a dialog explains what is shared, with whom and for how long, and
  records the consent. Withdrawing it is a switch in the volunteer settings.

### 4.3 Evidence anchoring (D11)

* Schema `evidence` (migration `0030_evidence_anchor`):
  * `evidence.anchor`: `id, seq, from_at, to_at, media_count, media_root, audit_seq, audit_hash, prev_anchor_hash,
    anchor_hash, signature (Ed25519, base64), key_id, tsa_url, tsa_token (bytea, as received), tsa_error,
    created_at`.
  * `evidence.leaf`: `anchor_id, idx, media_id (unique), sha256`. The leaves are kept when a media row is erased, so
    an earlier proof stays checkable.
  * A trigger refuses every change to both tables except filling in `tsa_token`/`tsa_error`, and every deletion.
* The worker loop `evidence` seals an anchor every hour, and once more when the worker stops. An anchor covers the
  stored media not anchored yet (ordered by `created_at, id`, at most 10,000 per anchor) and the current head of the
  audit chain (`audit_seq`, `audit_hash`). Nothing new (no media, same audit head) means no anchor. One sealer at a
  time (advisory lock).
* Method, so that a third party can recompute everything with any SHA-256 tool:
  * leaf = `sha256(0x00 || media_id (16 bytes) || sha256 (32 bytes))`;
  * node = `sha256(0x01 || left || right)`; on a level with an odd count the last node goes up unchanged;
  * `anchor_hash` = `sha256` of the line
    `e-himaya-anchor-v1|seq|from_at|to_at|media_count|media_root|audit_seq|audit_hash|prev_anchor_hash`
    (UTC ISO 8601 timestamps with microseconds, empty fields for nulls);
  * the signature is Ed25519 over the ASCII of `anchor_hash`, by `EVIDENCE_SIGNING_KEY` (falls back to
    `CERTIFICATE_SIGNING_KEY` with a warning; with neither, anchors are sealed unsigned and the check lists them).
    `key_id` is computed like the certificates' one.
* If `TSA_URL` is set, an RFC 3161 request is sent with `anchor_hash` as the SHA-256 message imprint, and the
  response is stored as received (`openssl ts -verify -digest <anchor_hash>`). TSA errors are recorded in
  `tsa_error` and never block sealing; the next run retries.
* `GET /api/v1/staff/evidence/anchors?limit=&before_seq=` (security_admin, sysadmin) lists the anchors, newest first.
* `GET /api/v1/staff/media/{id}/proof` (staff who may read the report or the live stream's report; `404` otherwise)
  returns the leaf, the Merkle path (`[{side, hash}]`), the anchor, its canonical line, the public key and the method.
  `409 not_anchored_yet` before the next sealing.
* `python -m app.modules.evidence verify` re-checks the whole chain (sequence, chaining, hash, signature, Merkle root,
  the audit entry it names, and media rows whose hash changed since) and exits 1 on any problem;
  `python -m app.modules.evidence seal` seals at once.
* RLS: every staff scope reads, only the system scope writes.

## 5. Alerts

### 5.1 Four eyes (E08)

* `alert` messages: the publisher must differ from the creator and from the last editor (`updated_by`, new). If not,
  the API answers `403 second_reviewer_required`.
* Emergency override: `POST …/publish` with `{"emergency_reason": "…"}` (at least 10 characters) lets the same
  person publish. The message records `emergency_reason` and `single_reviewer: true`, the audit entry is
  `alert.publish_single`, and an `alert.review_needed` live event lists it for a second person to acknowledge
  after the fact: `POST …/acknowledge` by another publisher, which stores `reviewed_by` and `reviewed_at`.
* Info messages are unchanged.
* Setting `alerts.four_eyes` (`platform.setting`, default `true`, national security admin) can turn the rule off.

### 5.2 Delivery failure

When an alert's dispatch finishes with failures of 10 % or more, or with the channel skipped as `not_configured`:
* a live event `alert.delivery_degraded` goes to the message's publishers' scope;
* it is audited (`alert.delivery_degraded`);
* the dashboard shows a persistent toast with the channel, sent/failed counts and a link to the message.

## 6. Quality

### 6.1 OpenAPI

* `python -m app.openapi` writes `docs/api/openapi.json`, sorted, with `info.version` = `API_VERSION`.
* CI and ci-local fail if the committed file differs ("API · OpenAPI drift").
* Version policy (in `docs/api/README.md`): `/api/v1` changes only additively. A breaking change needs `/api/v2` and
  six months of overlap.

### 6.2 ERD

`python -m app.erd` writes `docs/erd.md`: one Mermaid `erDiagram` per schema, with the foreign keys. It is checked
for drift like the OpenAPI document.

### 6.3 Traceability (R20)

`scripts/traceability.py` reads the requirement identifiers from `docs/01-requirements.html` and the references in
the tests (`# covers: FR-…` comments and docstrings, plus identifiers already cited). It writes
`docs/traceability.md`: requirement → test files, and the list of requirements without a test. CI only checks that
the file is current. The gaps are listed, not hidden.

### 6.4 SBOM and licences (V22)

* CI job "Supply chain · SBOM and licences" writes CycloneDX SBOMs: `cyclonedx-py` per Python lock and
  `@cyclonedx/cyclonedx-npm` per web app. They are uploaded as artifacts, not committed.
* `scripts/licences.py` checks the licences against an allow list: MIT, BSD-2/3, Apache-2.0, ISC, MPL-2.0,
  PSF/Python-2.0, Unlicense, 0BSD, CC0-1.0, LGPL (dynamic linking only), plus the exceptions already recorded in
  `docs/versions.md` (e.g. AGPL tools outside the product). A copyleft or unknown licence fails the job.

### 6.5 Accessibility (U21)

The dashboard and portal browser tests run axe-core (`@axe-core/playwright`, WCAG 2.2 A/AA tags) on the main
screens. A violation of impact `serious` or `critical` fails the test, and the violations found are fixed in this
phase.

## 7. Documents (no code)

* `docs/privacy/dpia.md`: DPIA (purpose, necessity, risks, measures, residual risk). It is a draft for the owner and
  a lawyer.
* `docs/privacy/processing-register.md`: record of processing activities per purpose (Law 63-2004, INPDP), with
  legal basis, data, recipients and retention as coded in `privacy/retention.py`.
* `docs/runbooks/incident-response.md`: severity levels, roles, the first hour, notification of INPDP and of the
  people concerned, the post-mortem.
* `docs/runbooks/backup-restore.md`: daily checks, the quarterly drill, restoring after a loss.

The runbooks live in `docs/runbooks/`, not `docs/procedures/`: that folder is the library of field procedures read
by the knowledge module, whose parser accepts only procedure files.

## 8. Acceptance

| # | Criterion | Test |
|---|---|---|
| 1 | Staff token without `otp` in `amr` → 401 `mfa_required`; citizen token unaffected | `test_auth.py::test_staff_mfa_*` |
| 2 | Real Keycloak 26.8: second sign-in carries `amr ⊇ {pwd, otp}` | `infra/keycloak/check_mfa.py` (CI, ci-local) |
| 3 | Revoked subject → 401 `session_revoked`; a token issued afterwards works | `test_sessions.py` |
| 4 | Disabling an account or changing its roles revokes its sessions | `test_accounts.py` |
| 5 | Restore drill: PITR keeps exactly the rows before the target and the audit chain is intact | `infra/backup/drill.sh` |
| 6 | SOS accepted with Valkey, NATS and AI down | `test_resilience.py` |
| 7 | Alert rules valid and unit-tested | `promtool check/test rules` |
| 8 | Revoked certificate → public `valid: false, revoked: true`; old key still verifies after rotation | `test_orgs.py` |
| 9 | Location without consent → 409; withdrawal drops the position; distance rounded | `test_location_consent.py` |
| 10 | Anchors chain, verify, and give a media proof; a tampered media hash is detected | `test_evidence.py` |
| 11 | Alert published by its creator → 403; emergency override audited and acknowledged by another person | `test_four_eyes.py` |
| 12 | Failed alert delivery raises `alert.delivery_degraded` | `test_four_eyes.py` |
| 13 | OpenAPI and ERD up to date | drift steps |
| 14 | No serious/critical axe violation on the main screens | dashboard and portal e2e |
| 15 | pip-audit and npm audit clean (or allow-listed with an expiry) | supply-chain job |
| 16 | The four images build again on the tested runtimes | image jobs, ci-local |
