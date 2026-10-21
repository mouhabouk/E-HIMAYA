# Threat model (STRIDE)

Phase 10, contract §3. One table per trust boundary. Each threat names its control and the evidence (a test, a
configuration file or a script) that shows the control is in place. "Residual" marks what the code cannot settle
alone and who has to act.

STRIDE: **S**poofing, **T**ampering, **R**epudiation, **I**nformation disclosure, **D**enial of service,
**E**levation of privilege.

Assets, from the most sensitive: SOS reports and their location, media and call recordings, the identity of
reporters and volunteers, the audit log, the alert channel (push, SMS, e-mail to the population), institution files
and certificates, staff accounts.

## Boundaries

```
citizen app ──HTTPS──▶ Caddy ──▶ API ──▶ PostgreSQL (RLS) / SeaweedFS (S3) / Valkey / NATS
dashboard ────HTTPS──▶ Caddy ──▶ API ──▶ AI service, vision service (internal network, bearer tokens)
portal ───────HTTPS──▶ Caddy ──▶ API ◀── tusd, MediaMTX, Asterisk hooks (internal, shared secrets)
everyone ─────OIDC───▶ Keycloak (realms ehimaya-public, ehimaya-staff)
```

## B1. Citizen app ↔ API

| | Threat | Control | Evidence |
|---|---|---|---|
| S | Forged reporter identity | Anonymous device identity bound to a pseudonym keyed with `ANON_PSEUDONYM_SECRET`; signed-in citizens carry a Keycloak token checked against the realm JWKS (issuer, audience, expiry) | `tests/test_data_protection.py`, `tests/test_auth.py` |
| T | Altered report or media in transit | TLS only (HSTS); media checked by magic number after upload and refused when the bytes differ from the declared type | `infra/caddy/Caddyfile`, `tests/test_uploads.py` |
| R | Reporter denies having sent a false SOS | Consent to the charter stored with version and time; every report audited; IP kept only as a rate-limit key | `tests/test_reports.py`, `tests/test_audit.py` |
| I | Location of a reporter or volunteer leaked | Location fields encrypted (AES-256-GCM, column bound as AAD); volunteer position needs explicit consent and the staff map shows it rounded to 0.001° | `tests/test_data_protection.py`, `tests/test_location_consent.py` |
| D | Flood of anonymous reports | Per-IP and per-identity limits, a report budget per window, local counters when Valkey is down | `tests/test_hardening.py`, `tests/test_resilience.py` |
| E | Citizen reads other reports | Row-level security on `reports.*` with the reporter scope; out-of-scope objects answer 404 | `tests/test_rls.py` |

## B2. Dashboard ↔ API (staff)

| | Threat | Control | Evidence |
|---|---|---|---|
| S | Stolen staff password | Staff realm requires TOTP; the API refuses a staff token without `otp` in `amr` (`mfa_required`); production refuses `STAFF_MFA_REQUIRED=false` | `tests/test_auth.py::test_staff_mfa_*`, `infra/keycloak/check_mfa.py` |
| S | Stolen token after sign-out or disablement | Revocation store (`session_revoked`), filled on sign-out, disable and role change; access token lives 5 min | `tests/test_sessions.py`, `tests/test_accounts.py` |
| T | Changing an alert sent to the population | Four eyes: the creator cannot publish; the emergency override is audited and must be acknowledged by another person | `tests/test_four_eyes.py` |
| R | Operator denies an action | Every staff write is audited in a hash chain (`audit.verify_chain()`); the runtime role can only append to `audit` | `tests/test_audit.py`, `app/core/db_roles.py` |
| I | A gouvernorat room reads another room's reports | `authorize` per object plus RLS scope; break-glass reading is time-boxed and audited | `tests/test_access.py`, `tests/test_break_glass.py` |
| I | XSS exfiltrates the token | Strict CSP generated at build time, tokens in `sessionStorage` (cleared with the tab), no inline script | `infra/web/csp.mjs` |
| D | Expensive queries (analytics, scenarios) | Period cap, minimum cell size, hourly quotas | `tests/test_analytics.py` |
| E | Role escalation through the account screen | Only `security_admin`/`sysadmin` manage roles; a role change revokes sessions | `tests/test_accounts.py` |

## B3. Portal ↔ API (institutions)

| | Threat | Control | Evidence |
|---|---|---|---|
| S | Forged certificate shown to an inspector | Certificates signed with Ed25519; public check verifies the signature, the revocation and keys of previous rotations | `tests/test_orgs.py` |
| T | Institution edits a reviewed card | Optimistic version (`version`), review workflow, history audited | `tests/test_orgs.py` |
| I | Member of one institution reads another | Membership checked per request, RLS on `orgs.*` | `tests/test_orgs.py`, `tests/test_rls.py` |
| E | Invitation reused by someone else | Single-use token, bound to the invited e-mail, expiry | `tests/test_orgs.py` |

## B4. API ↔ database and object store

| | Threat | Control | Evidence |
|---|---|---|---|
| T | API compromise rewrites history | Runtime role owns nothing, `audit` is append-only, triggers refuse changes to `evidence.anchor` except the timestamp columns | `app/core/db_roles.py`, `tests/test_evidence.py` |
| T | Media replaced in the bucket | Media hashes sealed hourly into signed Merkle anchors chained to the audit head, optional RFC 3161 timestamp; per-media proof | `tests/test_evidence.py` (tamper detected) |
| I | Backup or disk copy read | Field-level encryption of personal data; WAL and base backups on a separate volume | `app/core/crypto.py`, `infra/backup/` |
| D | Data loss | WAL archived every minute, nightly base backup, restore drill (RPO/RTO measured) | `infra/backup/drill.sh` |

Residual: backups are not encrypted by the backup service itself; the second-site copy (`BACKUP_REMOTE`) must use
an encrypted target. Owner: operations.

## B5. Media hooks (tusd, MediaMTX) and telephony (Asterisk)

| | Threat | Control | Evidence |
|---|---|---|---|
| S | Fake hook call creates media or a stream | Shared secrets (`TUSD_HOOK_SECRET`, `MEDIAMTX_HOOK_TOKEN`) compared in constant time; internal network only | `tests/test_uploads.py`, `tests/test_streams.py` |
| S | Fake inbound SMS | HMAC secret on the SMS gateway callback | `tests/test_telephony.py` |
| I | Live stream watched by an outsider | Viewer tokens with a short TTL, per stream | `tests/test_streams.py` |
| D | Long or numerous streams | Maximum duration, creations per hour | `tests/test_streams.py` |

## B6. AI and vision services

| | Threat | Control | Evidence |
|---|---|---|---|
| S | Fake vision detections injected | Callback token, internal network | `tests/test_streams.py` |
| T | Prompt injection through a report changes its priority | The model only proposes; rules rank the report and an operator decides; outputs are validated against a schema | `tests/test_ai.py` |
| D | AI down blocks intake | Intake never waits for the AI; analysis retried later | `tests/test_resilience.py::test_ai_down` |

## B7. Keycloak

| | Threat | Control | Evidence |
|---|---|---|---|
| S | Password guessing | Brute-force protection on both realms; TOTP on staff | `infra/keycloak/realms/` |
| D | Identity provider down | Anonymous SOS keeps working; staff get `503 identity_provider_unavailable` | `tests/test_resilience.py::test_identity_provider_down` |

Residual: the password policy asks for 8 characters; ASVS L2 asks for 12 (see `asvs-l2.md`, V2.1.1). Owner: the
platform owner decides, then the realm file is changed.

## Review

Review this model at each phase that adds a boundary (a new service, a new hook, a new external provider) and after
any security incident.
