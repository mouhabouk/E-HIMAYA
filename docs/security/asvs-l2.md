# OWASP ASVS 4.0.3, level 2

Phase 10, contract §3. Chapter by chapter, with the verdict for the platform (API, dashboard, portal, citizen app)
and the evidence. **met**: in place and shown by a test or a file. **partial**: in place for part of the chapter,
the gap and its owner are named. **n/a**: the chapter does not apply.

This is a self-assessment by the development team, not an audit. An external penetration test before the
national launch is still needed (owner: Civil Protection IT security).

| Chapter | Verdict | Evidence and notes |
|---|---|---|
| V1 Architecture | met | `docs/02-architecture.html`, `docs/security/threat-model.md`; components separated by network (internal services not exposed), one owner role for migrations and a runtime role without DDL (`app/core/db_roles.py`) |
| V2 Authentication | partial | Keycloak, Authorization Code + PKCE, TOTP for staff proven in the token (`test_auth.py::test_staff_mfa_*`, `infra/keycloak/check_mfa.py`), brute-force protection. **Gap V2.1.1**: the password policy asks for 8 characters, L2 asks for 12; **V2.1.7**: no breached-password check. Owner: platform owner (realm policy). |
| V3 Session management | met | Short access tokens (5 min), refresh with idle timeout (15 min staff, 30 min citizens), server-side revocation on sign-out, disable and role change (`test_sessions.py`, `test_accounts.py`); tokens in `sessionStorage` for the web apps |
| V4 Access control | met | Deny by default, `authorize` per object with scope, 404 for out-of-scope objects, RLS as second layer, audited break-glass reading (`test_access.py`, `test_rls.py`, `test_break_glass.py`) |
| V5 Validation, sanitisation, encoding | met | Pydantic schemas on every input, bound SQL parameters only, uploads checked by magic number (`test_uploads.py`), React escaping, AI output validated against a schema |
| V6 Stored cryptography | met | AES-256-GCM per field with key versions and rotation (`app/core/crypto.py`, `test_data_protection.py`), Ed25519 for certificates and evidence anchors, keyed hashes for lookups; weak or example secrets refused in production (`app/core/secrets_policy.py`, `test_production_settings.py`) |
| V7 Errors and logging | met | Errors `{"detail": code}` without stack traces; structured logs without personal data; hash-chained audit log (`test_audit.py`); 5xx counted and alerted (`infra/monitoring/alerts.yml`) |
| V8 Data protection | met | Retention and anonymisation jobs (`app/modules/privacy/retention.py`), erasure requests, consent per purpose (`test_location_consent.py`), `Cache-Control: no-store` on every API answer unless an endpoint sets its own caching (`tests/test_health.py`) |
| V9 Communications | met | TLS at Caddy with HSTS; internal services on a private network. Hops between containers are plain HTTP inside that private network, which is accepted for a single-host deployment; a multi-host deployment needs mTLS or a private link (owner: operations) |
| V10 Malicious code | met | Dependencies pinned with lock files, audited (`scripts/dep_audit.py`, `.github/audit-allowlist.yml`), licences checked (`scripts/licences.py`), images pinned by version |
| V11 Business logic | met | Rate limits and budgets on anonymous intake (`test_anon_quota.py`, `test_hardening.py`), four eyes on population alerts (`test_four_eyes.py`), state machines for reports and certificates |
| V12 Files and resources | met | tus uploads with size and count limits per kind, type verified after upload, served from a separate host with a sandbox CSP (`infra/caddy/Caddyfile`), no user-controlled paths |
| V13 API and web services | met | OpenAPI exported and checked for drift (`docs/api/openapi.json`), CORS allow list, hooks authenticated by shared secrets compared in constant time |
| V14 Configuration | partial | Security headers (CSP, HSTS, frame-ancestors, Permissions-Policy), production start-up checks. **Gap**: the ZAP scan (`infra/security/zap/run.sh`) is run by hand before a release and has not yet been run against a full staging stack. Owner: release manager. |

## Open items

| Item | Owner | When |
|---|---|---|
| Password length 12 and breached-password check (Keycloak policy) | Platform owner | Before the national launch |
| First ZAP API scan on staging, report in `docs/security/` | Release manager | Before the first release |
| External penetration test | Civil Protection IT security | Before the national launch |
| Encrypted target for the second-site backup copy | Operations | When `BACKUP_REMOTE` is configured |
