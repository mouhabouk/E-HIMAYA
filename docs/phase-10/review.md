# Phase 10 — Review before hardening

Scope: the "hardening" half of the original phase 9 (requirements §11: performance and penetration testing, DPIA)
plus the audit R1 items left open for it (`docs/audit-r1-closure.html`). The pilot in one gouvernorat is phase 11.
Read-only review of `main` at 8f7d00d; every claim cites `path:line` or a command that was run. API paths are
relative to `services/api/app/`.

---

## 1. The dependency merges since phase 9 were never built

GitHub Actions has not run any job on this repository since it became private (no runner assigned, see PR #61 and
#62). In that time 45 Dependabot pull requests were merged into `main`. Each one was meant to be gated by the full
CI (`.github/dependabot.yml:1-3`). Re-checking them by hand:

| Merge | Change | Finding |
|---|---|---|
| #9, #4, #11, #17 | `python:3.12-slim` → `python:3.15-slim` in api, ai, notify-sim, vision | **Breaks the images.** CI tests on 3.12 (`.github/workflows/ci.yml:55`). For cp315 the locks have no wheel for `brotli` and `pyyaml` (api), `onnxruntime`, `ctranslate2`, `sentencepiece` (ai), `onnxruntime` (vision): checked against every `uv.lock`. The slim image has no compiler, and onnxruntime and ctranslate2 publish no sdist at all, so `uv sync --locked` fails in the `deps` stage. |
| #22 (old repository) | `postgres:17-bookworm` → `postgres:18-bookworm` | **Breaks the database image.** `infra/postgres/Dockerfile:12` then installs `postgresql-17-postgis-3` and `postgresql-17-pgvector` into a PostgreSQL 18 server: `CREATE EXTENSION postgis` fails in `initdb/`. PostgreSQL 18 images also moved `PGDATA` to `/var/lib/postgresql/18/docker` and refuse a volume mounted at `/var/lib/postgresql/data` (`infra/compose.yml:31`). A major upgrade of a live database also needs `pg_upgrade`; it is not a base-image bump. |
| #59, #39 | `node:22-alpine` → `node:26-alpine` (dashboard and portal build stage) | Not tested: CI and `scripts/ci-local.sh` build on Node 22 (`dashboard.yml:34`, `portal.yml:34`). Node 26 is not an LTS line. |
| #56 | Keycloak 26.3 → 26.8 in `infra/compose.yml:162` | CI and ci-local still import the realms into 26.3 (`ci.yml:320`, `scripts/ci-local.sh:28`). **Checked here:** both realms import into 26.8. |
| #21, #24, #20, #18 and the others | TypeScript 7, react-router 8, vite 8.3, web-minor group, uv 0.13.4, Actions majors, seaweedfs, tusd, valkey, nats, ollama, mailpit | Dashboard and portal pass lint, types, unit tests and build on the merged `main` (PR #62). The browser tests needed a fix for react-router 8 transitions (PR #62). The compose services are not exercised without the stack smoke test. |

Dependabot's configuration groups only minor and patch npm and uv updates (`.github/dependabot.yml:13-16,34-36`).
Base images and major versions come one by one, and nothing marks a change of language runtime or database major
as "not a routine bump".

## 2. Security

- **MFA is enforced only by Keycloak, never verified by the API.** The staff realm makes `CONFIGURE_TOTP` a
  default required action (`infra/keycloak/realms/ehimaya-staff-realm.json:107-113`) and the built-in browser flow
  asks for the code only when the user has one configured ("Conditional 2FA"). An administrator who removes a
  user's OTP credential, or an account created without the default action, signs in with a password alone. The API
  accepts any valid staff token (`core/security.py:115-155`): there is no `amr` or `acr` check (grep finds none).
  **Checked here** with Keycloak 26.8: once an AMR mapper and authentication references are configured, the access
  token carries `amr: ["pwd","otp"]`. Without them `amr` is absent.
- **Sessions are not revocable in the API.** Access tokens live 300 s (`…staff-realm.json:29`), and the API keeps no
  deny-list. Disabling an account or resetting its credentials logs it out in Keycloak (`access/keycloak.py:211-219`),
  but tokens already issued keep working until they expire. Refresh tokens are not rotated (`revokeRefreshToken` is
  absent from both realms).
- **Static analysis exists, dependency audit does not.** Ruff runs the bandit rules (`S`) on every Python service
  (`pyproject.toml:45`), eslint runs on the web apps, and Trivy scans the images. `pip-audit` and `npm audit` do not
  run in CI.
- No written threat model (audit I18), no ASVS mapping, no dynamic scan (audit P23).

## 3. Resilience

- **No backup at all.** Nothing in `infra/` archives WAL or takes a base backup (grep `archive_command`,
  `pg_basebackup`, `pgbackrest`, `wal-g`: no hit). The targets RPO < 5 min and RTO < 1 h (requirements NFR-12) and
  the quarterly restore test have no implementation. This is the largest gap of the phase.
- **Failure behaviour is coded but only partly tested.** If Valkey is down, the rate limiter falls back to a local
  in-memory counter and never fails open (`core/ratelimit.py:144-157`). The event outbox survives a NATS outage
  because events are written in the same transaction and published later (`core/events.py`). The SOS intake has
  no test that runs with Valkey and NATS absent.
- Prometheus metrics are exposed behind `METRICS_TOKEN` (`core/metrics.py`, `modules/health/router.py`), but no
  alert rule or scrape configuration ships with the platform (NFR-13).
- The load test exists (`infra/loadtest/RESULTS.md`): about 16 SOS/s on one 4-vCPU machine for the whole stack,
  against a national target of 5000 reports/hour (about 1.4/s, NFR-03). It does not need to be repeated for this
  phase.

## 4. Data protection

- **INPDP declaration (L02):** no record of processing activities and no DPIA in the repository.
- **Certificates (L05):** statuses are draft, submitted, approved, rejected, superseded (`orgs/certificate.py:473-513`).
  There is no revocation, and an approved certificate stays valid until `valid_until` even if it was granted in
  error. The signing key is a single Ed25519 key (`orgs/certificate.py:42-60`) and the signature does not name its
  key, so rotating the key invalidates every certificate already issued. The PDF and the public page do not say that
  the "safety file" is not an official government certificate.
- **Volunteer location (D12):** the position is kept in memory only while the volunteer is ready
  (`volunteers/service.py:201-206`). Staff see a distance to the meter (`ops/interventions.py:448`). The volunteer
  gives no separate consent to sharing their location: the privacy charter is the only consent stored
  (`identity/models.py:105-116`).
- **Evidence (D11):** each media file gets its SHA-256 computed by the server (`reports/models.py:130`) and the
  audit log is hash-chained (`audit/models.py:12-25`). Nothing anchors these hashes outside the database: a database
  administrator could rewrite a media row and rebuild the chain from that point.
- Health data (L03) waits for the owner's decision (collect blood group with separate consent, or stop collecting
  it). Nothing is changed in this phase.

## 5. Quality

- **OpenAPI (I15):** the schema is generated by FastAPI and hidden in production (`main.py`). It is not published in
  the repository, and nothing detects drift between the contracts and the code.
- **ERD (D10):** none. **Traceability (R20):** 106 requirement identifiers in `docs/01-requirements.html`, and 43 of
  them cited somewhere in tests or code (grep `FR-|NFR-|UC-|BR-`).
- **SBOM and licences (V22):** licences are listed by hand in `docs/versions.md`. No SBOM is generated and no licence
  check runs.
- **Accessibility (U21):** the translation keys and RTL direction are tested. No automated accessibility check
  (axe) runs in the browser tests.
- **Four eyes on alerts (E08):** the same person can draft and publish an alert (`notify/service.py:296-377`; only
  the role is checked). When a channel fails to deliver, it is counted in a metric (`notify/delivery.py:91-94`) and
  nobody is told.
