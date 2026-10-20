# Phase 9 — handoff (work in progress)

The owner asked on 2026-10-20 to move the project to a new repository
(`202500737studentnaussedusa-max/E-Himaya`). Development was stopped mid-way and everything written so far was
committed on branch `phase-9` as is, **unreviewed and untested as a whole**. The next session continues from here.

Read first: `docs/api/phase-9-contract.md` (binding; §11 work split W1–W4) and `docs/phase-9/review.md`.

## State per worker (from the files on disk when work stopped)

| Worker | Done or started | Not started |
|---|---|---|
| W1 API access, settings, quota, reports | `core/access.py`, `core/security.py`, `core/config.py`, `main.py`, `modules/settings/`, identity quota, `reports/jurisdiction.py`, `reports/geo.py`, `reports/sla.py`, migrations 0018–0020, re-gating in ai/rewards/streams/weather routers, tests `test_settings`, `test_anon_quota`, `test_jurisdiction`, `test_sla` and updates to existing tests | `test_access.py` (was being written); full suite, mypy and migration round trip not yet run |
| W2 API ops, cross-border, access, audit | `ops/scope.py`, `ops/requests.py` and ops changes, `modules/access/`, audit scope, analytics/knowledge/notify/telephony/geo/decision/forecast adjustments (English texts were in progress), migrations 0021–0024, Keycloak staff realm | tests `test_cross_border`, `test_break_glass`, `test_accounts`, `test_audit_scoped`, `tests/scopehelpers.py`; existing test updates; full suite |
| W3 dashboard | `en.json`, language menu, role gates, pages Settings, LateReports, GeoQueue, Accounts, Audit, BreakGlass, ResourceRequests, components for claim/referral, break-glass, incident command, resource requests | CSS tokens (was being added), page tests, lint/typecheck/build run |
| W4 mobile + RLS | mobile quota (error code, blocked state, quota store, quota screen with 198, home card, ARB strings ar/fr/en, sync engine and widget tests in progress); `core/db.py` started | `core/db_roles.py`, `infra/postgres/**`, migration `0025_*`, `test_rls.py`, `test_db_roles.py` |

## Next steps

1. Run each area's checks as CI does (or `scripts/ci-local.sh` from PR #57): API ruff, mypy strict, alembic
   upgrade/downgrade, pytest; dashboard lint, typecheck, tests, build; mobile `flutter analyze` and `flutter test`.
2. Finish the "Not started" column, worker by worker, keeping the §11 file ownership.
3. Map the 20 acceptance criteria (§12) to passing tests, then write `docs/phase-9-report.html` and update
   `docs/versions.md`.

Owner decisions already taken (see the contract): claim delays per severity band editable in national settings
(60/90/120/180 s defaults); central responds and directs, field intervention stays regional; SOS never blocked by
the anonymous quota; quota counters start at 0 at release (no backfill); phase 9 = review, redesign, then build.
