# Phase 9 — Review of the current schema and code

Scope: change request A (anonymous quota), B (English dashboard), C (central vs regional rooms, RBAC+ABAC, RLS,
escalation). Branch `phase-9` cut from `origin/main`. Read-only review; every claim cites `path:line`.
API paths are relative to `services/api/app/` unless stated. "(inferred)" marks conclusions not read directly in code.

---

## 1. Principal and scope model

**Token → Principal.** `core/security.py:63-81` — `Principal(subject, realm, roles, gouvernorat_code, claims)`.
`is_national` = staff realm and `gouvernorat_code is None` (`:76-78`); `can_access_gouvernorat(code)` = national or
equal code (`:80-81`). Scope is a single integer: no list of gouvernorats, no function, no room, no assignment.

**How scope is read.** `core/security.py:143-149`: for the staff realm, `scope_level == "national"` → national;
otherwise the `gouvernorat_code` claim is required (missing → `403 staff_scope_missing`). Public-realm tokens never
carry a scope. Roles are filtered per realm (`:139-141`, `REALM_ROLES` `:46-60`).

**Keycloak.** `infra/keycloak/realms/ehimaya-staff-realm.json`: realm roles at `:50-80` (operator, ops_manager,
field_commander, local_committee, central_committee, org_auditor, content_editor, sysadmin); user-attribute mappers
`attr-gouvernorat_code` (`:156-161`) and `attr-scope_level` (`:170-175`) on the `ehimaya-dashboard` client; user
profile restricts `gouvernorat_code` to the 24 codes and `scope_level` to `national|gouvernorat`, both admin-edit
only (`:193`). Locales `ar, fr` only (`:23-27`). Access token 300 s (`:28`). No groups, no fine-grained admin
permissions, no API endpoint that creates staff accounts (grep for `admin/realms` finds nothing) → accounts are
created in the Keycloak console by whoever holds realm-admin. The dashboard re-derives scope from the same claims
(`apps/dashboard/src/auth/identity.ts:40-46`).

**Role and scope are independent**: any role can be national or regional. `ops/levels.py:56-62` and
`ops/committee.py:107-114` explicitly handle "central_committee with a regional scope".

| Role (family today) | What it can do today (main gates) |
|---|---|
| operator | read reports/incidents (`reports/staff_router.py:28`), write: status, link/merge, card, assignments, callouts, stream stop (`:29`, `ops/router.py:23`, `streams/staff_router.py:30`); calls (`telephony/domain.py:53`) |
| ops_manager | operator rights + close incidents (`ops/router.py:24`), units/resources CRUD (`ops/command_router.py:24`), alert drafts (`notify/service.py:37`), weather rules (`weather/staff_router.py:29`), reward management (`rewards/staff_router.py:45`), volunteer review (`volunteers/staff_router.py:18`), stream source registration (`streams/staff_router.py:28`) |
| field_commander | operator rights + close incidents (`ops/router.py:24`), calls |
| local_committee | read; set own level except leaving disaster (`ops/levels.py:58-67`); directives to own gouvernorat + ack (`ops/command_router.py:21,23`); publish info/alerts (`notify/service.py:36-38`); rewards, volunteers review, analytics planner |
| central_committee | read; any level and directives when national (`ops/levels.py:56`, `ops/committee.py:107`); AI settings and reward rules when national (`ai/router.py:20,33`, `rewards/staff_router.py:46,110`) |
| org_auditor | institutions read/review only (`orgs/staff_router.py:25-27`) |
| content_editor | safety tips (`content/router.py:23`), notification drafts/publish of info (`notify/service.py:36`), weather editor (`weather/staff_router.py:28`) |
| sysadmin | audit log read/verify (`audit/router.py:16`); **also** units/resources CRUD (`ops/command_router.py:24-25`), stream registration (`streams/staff_router.py:28`), AI settings (`ai/router.py:20`), reward rules (`rewards/staff_router.py:46`), weather read (`weather/staff_router.py:30`) |

Gaps vs CR-C: no `security_admin`, `ai_admin`, `regional_account_admin` roles; sysadmin mixes technical and
operational writes; no "function", "assignment", "sensitivity" or break-glass attribute anywhere in `Principal`.

---

## 2. Staff endpoints

Legend: **R** read, **W** write, **C** command (acts on field/people). "scope" = how gouvernorat is enforced.
Every listed scope check is server-side unless flagged.

| Module · route (prefix `/api/v1/staff` unless noted) | Roles | Scope enforcement | Kind |
|---|---|---|---|
| reports · `GET /kpis` (`reports/staff_router.py:57`) | READ_ROLES | `scope_filter` on report gouvernorat (`reports/service.py:317-321,472`) | R |
| reports · `GET /reports` (`:62-92`) | READ_ROLES | `scope_filter` AND optional `gouvernorat_code` param (`reports/service.py:380,385-386`) → foreign code returns empty, no IDOR | R |
| reports · `GET /reports/{id}` (`:166-172`) | READ_ROLES | `in_scope(report.gouvernorat_code)`, 404 (`:98`); returns reporter name+phone to every read role (`:112-121`) | R (PII) |
| reports · `POST /reports/{id}/status` (`:175-199`) | WRITE_ROLES | `in_scope` (`:180`); no claim/assignment check | W/C |
| ops · `GET /incidents`, `GET /incidents/{id}` (`ops/router.py:36-63`) | READ_ROLES | `Incident.gouvernorat_code` (`ops/service.py:37-44,140-147`) | R |
| ops · `POST/DELETE /reports/{id}/incident`, `.../suggestion/dismiss` (`ops/router.py:66-107`) | WRITE_ROLES | report in scope (`:29-33`); target incident in scope (`ops/service.py:195,216,223`) | W |
| ops · `POST /incidents/{id}/merge` (`:110-127`) | WRITE_ROLES | both incidents in caller scope (`:116`) | W |
| ops · `PATCH /incidents/{id}`, `POST .../notes` (`:133-159`) | WRITE_ROLES | incident in scope; notes not audited (`:153-159`) | W |
| ops · `POST /incidents/{id}/assignments` (`:162-178`) | WRITE_ROLES | incident in scope + resource's unit in scope (`ops/interventions.py:271`, `ops/resources.py:221-230`) | C |
| ops · `POST /assignments/{id}/status` (`:181-195`) | WRITE_ROLES | via incident (`ops/interventions.py:334`) | C |
| ops · `POST /incidents/{id}/close` (`:198-213`) | ops_manager, field_commander | incident in scope | C |
| ops · volunteer suggestions, callouts, cancel, arrived (`:216-272`) | READ (suggest) / WRITE | incident in scope; volunteers limited to caller's gouvernorat (`ops/interventions.py:402`); `arrived` not audited (`:264-272`) | C |
| command · `GET /levels` (`ops/command_router.py:38`) | any staff | none (national picture by design) | R |
| command · `POST /levels` (`:43`) | committees | `_check_allowed` (`ops/levels.py:55-67`) | C |
| command · directives list/issue/ack, performance (`:54-87`) | committees (+ops_manager read) | `ops/committee.py:31-40,102-114,144-147,236` | C/R |
| command · units CRUD (`:93-123`) | Logistics = ops_manager, **sysadmin** | `_check_gouvernorat` on body (`ops/resources.py:37-39,96`), `get_unit` (`:80-84`) | W |
| command · resources list/summary/map/CRUD (`:130-201`) | LogisticsReader incl. **sysadmin** / Logistics | `unit_scope` AND optional `gouvernorat_code` (`ops/resources.py:194,201-202`) | R/W |
| decision · route, recommendations, responders, assistant (`decision/router.py:52-77`) | READ_ROLES | incident in scope (`:60,68,77`); assistant is a POST by read roles | R (LLM) |
| forecast · `POST .../forecast/fire|flood`, list (`forecast/router.py:33-80`) | READ_ROLES | incident in scope; read roles trigger computation | R/compute |
| telephony · calls list/get/dial/link/transfer/recording, conferences (`telephony/staff_router.py:52-348`) | READ / CALL_ROLES | `scope_filter`: own gouvernorat **or unlocated calls** **or** calls I took (`telephony/service.py:109-119`) | R/C |
| streams · list/get/viewer/stop/recordings/register (`streams/staff_router.py:54-147`) | READ / WRITE / ops_manager+**sysadmin** | `scope_filter` (`streams/service.py:114-121`); register checks body code (`:64-65`) | R/C |
| volunteers · list/map/get/review (`volunteers/staff_router.py:34-78`) | READ / reviewers | `scope_filter` AND param (`volunteers/service.py:211-212,249-250`), `get_in_scope` (`:288-292`) | R/W |
| orgs · list/map/detail/docs/reports/review, certificates (`orgs/staff_router.py:64-216`) | READ+org_auditor / org_auditor | `staff_scope` / `in_scope` (`orgs/service.py:908-916`, `orgs/certificate.py:582`) | R/W |
| notify · notifications CRUD/publish/cancel/audience (`notify/staff_router.py:44-147`) | editors | read: `_visible` (`notify/service.py:205-219`); write: `check_scope` (`:95-113`) — **`audience == "user"` skips the check** (`:110-111`) | C (alerts) |
| notify · `POST /users/lookup` (`notify/staff_router.py:67-88`) | INFO_ROLES | **none**: resolves any e-mail nationwide (audited, rate-limited) | R (PII) |
| weather · grid/at/suggestions/accept/dismiss/rules (`weather/staff_router.py:54-215`) | readers incl. sysadmin / editors | accept national-only (`:143`); rules national needs national central/ops_manager (`:210-215`) | R/W |
| ai · `GET/PUT /ai/settings`, status (`ai/router.py:24-50`) | READ / central_committee+**sysadmin** | PUT requires national (`:33-34`) | W (national) |
| rewards · settings/rules (`rewards/staff_router.py:75-195`) | readers+sysadmin / central+**sysadmin** | `_national` (`:110-111`) | W (national) |
| rewards · citizens/badges/nominations/certificates/rescue (`:265-915`) | READ / MANAGE | `_in_scope` on **residence** `Profile.gouvernorat_code` (`:59-64,277`); rescue via incident (`:917`) | R/W |
| rewards · `GET /leaderboard?scope=national` (`:950-975`) | READ_ROLES | **no check for `scope=national`** (pseudonymised) | R |
| analytics · overview/trends/hotspots/scenarios/notifications (`analytics/router.py:35-210`) | READ / PLANNER | `resolve_scope` → 403 `out_of_scope` (`analytics/service.py:37-49`) | R |
| analytics · reports library/schedules (`analytics/library.py:101-404`) | READ / PLANNER / SCHEDULE | `_visible` on `gouvernorats[]` (`:40-44`), incident target single code (`:75-81`) | R/W |
| knowledge · memory/library (`knowledge/router.py:70-203`) | LIBRARY / AUTHOR | `covers` (`knowledge/domain.py:81-86`), incident in scope (`knowledge/memory.py:576`) | R/W |
| content · safety tips (`content/router.py:80-162`) | content_editor | national content, no scope | W |
| audit · `GET /api/v1/admin/audit`, `/verify` (`audit/router.py:37-67`) | sysadmin | **none** (all rows, any scope) | R |
| live · WS `/api/v1/staff/live` (`reports/live.py:209`) | any staff with a role | per-event `_route` (`:130-171`) | R |

**Flags.**
1. *Parameter filters are AND-ed with the token scope* in reports, resources, volunteers, orgs lists — no IDOR,
   but behaviour differs (empty page) from analytics/rewards (403). No endpoint filters by gouvernorat only in the UI;
   the UI hides the selector for regional users (`apps/dashboard/src/pages/useEffectiveFilters.ts:6-12`).
2. *Scope leaks to fix*: notify user-audience messages + `users/lookup` (regional editor can message any citizen);
   unlocated calls shared with every gouvernorat (`telephony/service.py:117`, `reports/live.py:123-127`); polygon
   notifications broadcast to every editor (`reports/live.py:168-169`); national leaderboard; audit log unscoped.
3. *Read roles issuing actions*: forecasts and the incident assistant are POSTs open to READ_ROLES incl. committees
   (`forecast/router.py:33,56`, `decision/router.py:76`) — compute, not field commands. Committees cannot change
   reports or assign (WRITE_ROLES excludes them, `reports/staff_router.py:29`) — the CR's "command" family therefore
   has *fewer* write rights than operations today.
4. *Family mixing*: sysadmin writes units/resources/streams/AI/reward rules (see table) — violates the separation of
   technical admin from operations/command.
5. *No claim gate*: any WRITE role in scope may change any report status (`reports/staff_router.py:175-185`).
6. *Sensitivity*: reporter identity is returned to every read role incl. committees (`reports/staff_router.py:112-121`),
   only audited (`:170`).

---

## 3. Data model

**Reports** (`modules/reports/models.py:30-67`): one `gouvernorat_code` (`:52`) + `delegation_id`, `location`
geography point always present (`:50`), `location_accuracy_m` optional (`:51`), `priority_score` (`:54`),
`first_response_at` (`:62`), `needs_verification`/`verification_reason` (`:64-65`), `incident_id` (`:38`).
Reporter = `user_id` → `identity.account` (`:37`); reporter gouvernorat exists only as the citizen's residence
`identity.profile.gouvernorat_code` (`identity/models.py:93`), never copied on the report; anonymous accounts have none.
No claim, deadline, escalation or geo-verification fields.

**Incidents** (`ops/models.py:20-43`): single nullable `gouvernorat_code` (`:29`), `op_level` (`:31-34`),
`severity` (`:26`), `merged_into` (`:38`). `refresh()` **recomputes `gouvernorat_code` as the majority gouvernorat of
member reports** on every link/unlink/merge (`ops/service.py:110-111`) → ownership can flip silently and the original
room loses access (404) to its own incident. AI grouping candidates are purely spatial (`ai/grouping.py:32,61-79`)
so suggestions cross borders; a regional operator accepting one gets 404 (`ops/service.py:216,223`); at disaster level
`auto_group` attaches with `principal=None`, no scope check (`ops/service.py:331-342`). Merge needs both incidents
in the caller's scope (`ops/router.py:116`) → only national staff can merge across a border; afterwards a single
gouvernorat remains. There is therefore no lead/participating model and no guard against two competing incidents on
each side of a border (inferred from the absence of any cross-scope duplicate check in `ops/service.py:150-228`).
Timeline: `ops.timeline_event(incident_id, at, actor, kind, payload)` (`ops/models.py:46-57`) — fit for
escalation/referral entries; it is mutable by the runtime role (only `audit` is append-only, `core/db_roles.py:76,98`).

**Units/resources/assignments** (`ops/models.py:111-186`): unit owns `gouvernorat_code` (`:121`); resource inherits
via `unit_id` (`:136`); assignment has no gouvernorat and no requesting/lending side (`:165-186`).
**Levels** per gouvernorat (`ops/models.py:67-78`). **Directives** carry `gouvernorat_codes[]` + `issuer_scope`
(`:81-95`) — the only existing central→regional instruction channel.
**Notifications**: `gouvernorat_codes[]`, `creator_scope`, polygon (`notify/models.py:55-56`). **Volunteers**:
residence gouvernorat (`volunteers/models.py:29`). **Orgs** (`orgs/models.py:56`), **streams** (`streams/models.py:34`),
**calls/conferences** (`telephony/models.py:44,69,88`), **rewards** nomination/certificate/pending award
(`rewards/models.py:104,133,162`), **analytics** `gouvernorats[]` + `creator_scope` (`analytics/models.py:28-93`),
**knowledge** `gouvernorats[]` (`knowledge/models.py:44,113`).

**Audit** (`audit/models.py:11-26`; trigger `migrations/versions/0001_core_schema.py:170-235`): hash chain over
`seq, prev_hash, at, actor, action, target, reason, details` (`:186-214`), UPDATE/DELETE/TRUNCATE refused by trigger
(`:216-224`), runtime role has SELECT/INSERT only (`core/db_roles.py:76,98`). Tamper-evident against the app role;
not against the owner role (inferred: owner can drop triggers). No gouvernorat column; scope must be derived from
`target`/`details`.

**Settings stores today**: `ai.settings` singleton JSONB row (`ai/models.py:42-49`, `ai/settings.py:111-130`);
`rewards.rule` rows (`rewards/models.py:33`); weather rules (`weather/staff_router.py:200-215`); everything else is
env (`core/config.py`, e.g. anonymous limits `:67-74`).

**New columns/tables needed**

| Need | Where |
|---|---|
| lead + participating gouvernorats | `ops.incident.lead_gouvernorat_code` (replace majority recompute) + `ops.incident_gouvernorat(incident_id, gouvernorat_code, role, added_at, added_by, reason)`; `command_level` (regional/central) on `ops.incident` |
| report claim | `reports.report.claimed_by`, `claimed_at`, `claimed_scope` |
| SLA / escalation | `reports.report.sla_due_at`, `escalation_state` (none/late/central_responding/referred), `escalated_at`; history in `ops.escalation` or `reports.escalation(report_id, kind, from_scope, to_scope, actor, at, reason)` mirrored to the timeline |
| geo-verification queue | `reports.report.geo_state` (trusted/pending/contradictory/verified), `geo_reason`, `geo_verified_by/at`; `gouvernorat_code` stays NULL until trusted |
| reporter gouvernorat (restricted) | separate table `reports.reporter_context(report_id PK, reporter_gouvernorat_code, source)` with its own grants/RLS |
| cross-gouvernorat assignment | `ops.resource_request(id, incident_id, resource_id/kind, from_gouvernorat, to_gouvernorat, status, requested_by/at, decided_by/at, reason)`; `ops.assignment.request_id` |
| break-glass | `access.break_glass_grant(id, subject, target_kind, target_id/gouvernorat, justification, granted_at, expires_at, reviewed_by, reviewed_at, review_outcome)` |
| anonymous counters | `identity.account.anon_reports_accepted int`, `anon_quota_reached_at` (or `identity.anon_quota(user_id PK, accepted, updated_at)`) |
| SLA + quota settings | national settings table (§6) |

---

## 4. Report creation, location, anonymity

**Gouvernorat assignment.** `reports/service.py:189` calls `locate_gouvernorat` (`:64-78`): point-in-polygon, else
nearest boundary within `NEAREST_GOUVERNORAT_MAX_M = 25 km` (`reports/domain.py:61`), else `None`. Accuracy is
validated (`reports/schemas.py:14`, 0–100 km, optional) and stored (`service.py:201`) but **never used**: a 5 km
accuracy circle straddling a border is assigned by its centre. Location is mandatory (`schemas.py:28`), so "no
location" today only exists for calls/SMS. `gouvernorat_code = NULL` → tracking code `EH-yy-00-…` (`service.py:88`)
and visible to national staff only (`service.py:324-327`, `reports/live.py:61-64`) — a de-facto central queue with no
state, no SLA and no hand-over. No contradiction check (GPS vs text place names vs profile).

**Idempotent create.** Replay by `client_uuid` returns the stored row before any insert (`service.py:167-171`);
concurrent duplicate caught on the unique index (`:213-221`); SMS-adopted reports return `created=False`
(`:176-181`); router turns replays into `200` (`reports/router.py:55-56`). **But** abuse checks run *before* the
idempotency lookup (`reports/router.py:49-50`), so a replay consumes the per-account/per-IP windows. The quota must be
incremented inside `create_report` after the successful flush (`service.py:213-214`), in the same transaction.

**Anonymous controls today.** Per account 20/10 min (`reports/router.py:24,76`); per IP for anonymous
(`:77-80`, `core/config.py:69-70`); global anonymous budget → accept and flag `anonymous_budget` (`router.py:81-84`,
`config.py:73-74`); never refuse except 429 (principle A1, `service.py:165-166`, `router.py:44-47`). New anonymous
identities per IP 60/h (`identity/service.py:88-91`, `config.py:67-68`). Pseudonym = HMAC-SHA256(secret, device key)
(`core/crypto.py:90-93`) stored unique in `identity.account.anon_pseudonym` (`identity/models.py:56`). Quarantine →
`403 anon_blocked` (`identity/service.py:98-101`). Retention: anonymous accounts with no report/device purged after
365 days (`config.py:133`, `privacy/retention.py:19,221`); closed reports detached after 5 years (`retention.py:14,112-154`)
— counting `reports.report` rows per user would therefore drift; a stored counter is required.

**Per-installation identity is resettable.** The key is 32 random bytes per install (`apps/mobile/lib/core/identity/device_key.dart:8-10,24-30`)
and is deleted on account deletion (`:34-37`, `features/privacy/account_deletion.dart:58`); a reinstall or data wipe
mints a new pseudonym with a fresh quota, bounded only by the 60/h per-IP identity limit. The CR accepts
"installation" as the unit; the design must state this limit.

**Mobile flow.** SOS is an ordinary queued report (`features/sos/sos_service.dart:50-52`), sent first
(`core/sync/sync_engine.dart:102-106`). Errors map in `_recordReportFailure` (`sync_engine.dart:178-205`):
`anon_blocked` → state `blocked`, retried after registration (`:186-188`, `:110`, `core/db/app_database.dart:22-23`);
any other unknown 4xx → `failed`, never retried (`:196-198`). A new `anon_quota_exhausted` code must be added to
`core/http/api_error.dart:7` and mapped to `blocked` (plus a dedicated message next to `anonBlockedBody` in
`features/report/report_queued_screen.dart:132-139`); otherwise the 6th report is silently lost. 198 dialing is
local and independent (`features/emergency/emergency_numbers.dart:34`, `features/report/sms_fallback.dart:153`).

---

## 5. Live updates, analytics and search

Live routing (`reports/live.py:130-171`) uses a **single** gouvernorat per event: reports by
`report.gouvernorat_code` (`:132-133`), incidents by `incident.gouvernorat_code` (`:134-135`), assignments/callouts
by the incident's code passed by the emitter (`ops/interventions.py:215-226`). Report-scoped staff queries use the
report's gouvernorat (`reports/service.py:317-321`); incident queries use the incident's (`ops/service.py:43-44`).
`get_incident` lists member reports through `staff_list` with the caller's report scope (`ops/router.py:54-55`).

When an incident spans two gouvernorats, today: (a) its owner flips with the report majority; (b) the other room sees
its own member reports but not the incident (404) nor its assignments/timeline; (c) the owner sees the incident but
not the other side's reports in the incident detail (filtered by report scope); (d) live `incident.updated` reaches
one gouvernorat only; (e) analytics count reports by report gouvernorat (`analytics/service.py:86,131`) and
incidents by single code (`analytics/documents.py:200`, `analytics/library.py:75-81`); committee performance does the
same (`ops/committee.py:176-190`); knowledge indexes one code (`knowledge/memory.py:706`). Scope must become
"report gouvernorat OR participating gouvernorat of its incident" for staff reads, and live payloads must carry
`gouvernorat_codes[]` evaluated with `_among`-style logic (`reports/live.py:103-111`).

---

## 6. Settings

National-only settings already follow one pattern: dedicated row/table + national check + audit with before/after
(`ai/router.py:29-41`; `rewards/staff_router.py:110-111,123`). Dashboard page `settings/ai`
(`apps/dashboard/src/App.tsx:143`, `pages/AiSettingsPage.tsx`, client validation `lib/aiSettings.ts:4-5`).
Anonymous limits live in env (`core/config.py:67-74`) and cannot be edited at runtime.

Recommendation: one `platform.setting(key PK, value JSONB, version, updated_by, updated_at)` table (or schema
`ops.settings` singleton like `ai.settings`) holding `sla.claim_delay_s` per severity band and
`anonymous.report_quota`; a new national-only editor role (see §10); `PUT` audited with before/after; cached with a
short TTL (inferred: the SLA worker reads it every loop). Keep the env value as bootstrap default.

---

## 7. Dashboard i18n

- `apps/dashboard/src/i18n/index.ts:6` `LANGUAGES = ["ar","fr"]`; `directionOf` returns rtl only for ar (`:15-17`) —
  works for en; `applyDocumentLanguage` picks title with a two-way ternary (`:22`); resources registered for ar/fr
  only (`:49`); `fallbackLng: false` (`:51`) → missing en keys render the key.
- Keys: `ar.json` / `fr.json` 2,249 leaf keys each (2,807 lines).
- Hardcoded two-language assumptions: language toggle flips ar↔fr (`components/Layout.tsx:27-40`);
  `lib/localized.ts:6` and `lib/forecast.ts:72` map any non-fr language to **Arabic** for API `{ar,fr}` pairs;
  `lib/hooks.ts:36`, `pages/ResourcesPage.tsx:34-35`, `pages/MapPage.tsx:294,422`, `components/WeatherLayer.tsx:301`,
  `pages/WeatherSuggestionsPage.tsx:171-172`, `pages/NotificationsPage.tsx:15` (ternaries on `lang === "ar"`);
  `pages/EventsLibraryPage.tsx:243,257,263` (own Intl locale); `components/Phase8Bits.tsx:38`;
  `components/OperationsPanel.tsx:841`; `lib/orgs.ts:96`; `lib/format.ts:4` `INTL_LOCALE` keyed by Language (needs en);
  document language pickers `pages/ReportsLibraryPage.tsx:229`, `pages/ReportSchedulesPage.tsx:283`;
  `pages/MemoryEntryPage.tsx:27` (memory content is ar/fr by design).
- Original text: list and detail show `text` first and `text_ar` as a labelled translation
  (`pages/ReportsPage.tsx:57-59`, `pages/ReportDetailPage.tsx:340-344`, `components/AnalysisPanel.tsx:277-281`) —
  already compliant; English must not add a machine "text_en".
- API side producing ar/fr only: analytics `ReportLang = Literal["ar","fr"]` (`analytics/domain.py:33`), label tables
  (`:46-98`), `_l(ar, fr)` (`analytics/documents.py:57-58`), direction/brand (`:513-514,539-564`), DB checks
  `ck_schedule_lang`/`ck_report_lang` (`migrations/versions/0015_analytics.py:81,117`); gouvernorat names
  `name_ar/name_fr` only (`geo/models.py:14-15`, `analytics/service.py:397-399`); decision/forecast/scenario texts
  (`decision/domain.py` 73 `"fr":` pairs, `decision/schemas.py:95`, `forecast/service.py`, `analytics/scenario.py`).
  Report/notify/rewards/content already accept `en` (`reports/domain.py:6`, `notify/templates.py:9`,
  `rewards/domain.py:15`). Keycloak staff login locales ar/fr (`ehimaya-staff-realm.json:23-27`).
- Tests enumerating languages: `src/i18n/i18n.test.ts:71-102` (ar/fr key parity, placeholders, contract coverage),
  `:228-253` (direction/persistence); `pages/Phase8Pages.test.tsx`, `pages/SafetyTipsPage.test.tsx` (changeLanguage).

---

## 8. RLS feasibility

- One engine, one runtime role for API and workers (`core/db.py:28-50`; `infra/compose.prod.yml:34` shared
  `DATABASE_URL`). The runtime role owns nothing and is `NOBYPASSRLS` (`infra/postgres/ehimaya-roles.sh:35`,
  `core/db_roles.py:59-69`) → RLS policies would apply to it; migrations run as owner and are unaffected.
- `get_session` yields a plain session with no principal (`core/db.py:48-50`). Requests commit several times
  (`identity/service.py:103` then `reports/service.py:233`; `reports/staff_router.py:171`), so a per-request
  `SET LOCAL` is lost after the first commit. Feasible pattern (inferred): a principal-aware session dependency that
  stores the scope in a contextvar and an `after_begin` event issuing
  `SELECT set_config('ehimaya.scope', :s, true), set_config('ehimaya.subject', :u, true)` on every transaction —
  transaction-local, therefore safe with the asyncpg pool (no PgBouncer in compose).
- Bypass needed: 16 worker loops open sessions directly (`main.py:85-102,107-108`, e.g. `core/events.py:161-163`),
  plus public reporter paths (create, mine, track) and internal hooks (`main.py:195,203`). They need an explicit
  `system`/`public` scope value; policies must fail closed when the GUC is unset. Alternative: a second
  `BYPASSRLS` worker role with its own URL (`PROCESS_ROLE=worker`, `infra/compose.prod.yml:168-174`) — but dev runs
  `all` in one process (`infra/compose.yml:212`).
- Start with staff-read tables: `reports.report`, `reports.media`, `reports.status_history`, `ops.incident`,
  `ops.timeline_event`, `ops.assignment`, `ops.unit`, `ops.resource`, `telephony.call`, `reports.live_stream`,
  restricted `reports.reporter_context`, `audit.log` (SELECT policy only).

---

## 9. Tests that encode current behaviour

API (`services/api/tests/`): `test_auth.py:31-49` (scope claims); `test_staff.py:31` (report scope by report
gouvernorat); `test_incidents.py:27-75` (cross-report grouping), `:123` (merge), `:182` (incident scope);
`test_live.py:46-73` (single-code routing); `test_reports.py:36,66` (gouvernorat/offshore assignment), `:84,94`
(idempotency), `:123` (anonymous reporting); `test_hardening.py:66-197` (per-IP limits, budget and degraded limiter accepted+flagged —
the "never refuse" rule changes); `test_operations.py:70,147,224` (levels, directives, units/resources scope incl.
sysadmin); `test_ai.py:236` (AI settings editors incl. sysadmin); `test_audit.py:40-50` (sysadmin-only audit);
`test_analytics.py:282,638` and the ar/fr label assertions (`:166,468-474,551`); `test_rewards.py:499`
(nomination scope); `test_db_roles.py:57-123` (role privileges — must also cover RLS); fixture `conftest.py:182-184`
(staff token = one gouvernorat or national). Dashboard: `i18n.test.ts`, `Phase8Pages.test.tsx`,
`SafetyTipsPage.test.tsx`, `test/render.tsx:82-102` (ar default, name_ar/name_fr fixtures). Mobile: `apps/mobile/test/core/sync_engine_test.dart`
(error-state mapping incl. `anon_blocked`), `apps/mobile/test/core/device_key_test.dart`.

---

## 10. Design inputs

Decisions the design must make (recommended option in one line each):

1. **Scope representation** — keep `scope_level` + `gouvernorat_code` claims; add a `function` claim (command /
   operations / technical) derived from roles, not a free attribute.
2. **New roles** — add `security_admin`, `ai_admin`, `regional_account_admin`; remove sysadmin from operational and
   national-setting gates (`ops/command_router.py:24-25`, `streams/staff_router.py:28`, `ai/router.py:20`,
   `rewards/staff_router.py:46`).
3. **Command family rights** — committees and field commander get incident command actions (lead/participants,
   escalation decisions, cross-gouvernorat approvals), not report triage.
4. **Policy engine** — one `core/access.py` with `can(principal, action, resource)` evaluating role, scope, function,
   incident level, assignment, sensitivity; every router calls it; 404 for out-of-scope reads.
5. **Incident jurisdiction** — `lead_gouvernorat_code` fixed at creation (trusted location), changed only by an
   audited transfer; drop the majority recompute (`ops/service.py:110-111`).
6. **Participating gouvernorats** — join table; a participant reads the whole incident and writes only its own
   assignments/notes.
7. **Duplicate prevention** — grouping suggestions across borders allowed; accepting one adds the caller's
   gouvernorat as participant instead of 404; a cross-border "new" incident within the grouping radius of an open one
   requires explicit override with reason.
8. **Central command level** — `command_level` set automatically from severity ≥ threshold or ≥ 2 gouvernorats or a
   level ≥ crisis; manual override by central command only.
9. **Report claim** — explicit `POST /reports/{id}/claim` (idempotent, regional room of the lead gouvernorat);
   status changes require a claim by the caller's room; `first_response_at` stays as KPI.
10. **SLA engine** — `sla_due_at` computed at creation from severity band; a new worker loop `sla-escalation`
    (SKIP LOCKED) marks late reports and emits `report.late`; defaults 60/90/120 s per band from settings.
11. **Late list behaviour** — central may respond to the citizen and issue a directive to the region; assignments of
    regional resources remain regional-only (central request → regional approval).
12. **Geo-verification** — trusted iff point-in-polygon and (accuracy ≤ X m or accuracy circle within one
    gouvernorat); otherwise `geo_state=pending`, `gouvernorat_code` NULL, central queue; critical reports also
    pushed provisionally to the candidate gouvernorat(s) read-only.
13. **Reporter gouvernorat** — copy residence/profile code into restricted `reports.reporter_context`; readable via
    break-glass or central security role only.
14. **Cross-gouvernorat resources** — `ops.resource_request` with approve/refuse by the owning region (or central
    command at central level); assignment created only on approval.
15. **Break-glass** — time-boxed grant (≤ 4 h), mandatory justification, audited, mandatory review by
    `security_admin`; principal scope extended in the policy engine, never in Keycloak.
16. **Regional audit view** — store `gouvernorat_code` in `details` (hashed) and add a STORED generated column + index;
    redaction (actor names, PII targets) in the API view; national raw view for security_admin.
17. **Regional account admin** — Keycloak fine-grained admin permissions with one group per gouvernorat, or an API
    proxy to the Keycloak admin API enforcing own-gouvernorat; recommend the API proxy (testable IDOR, audited).
18. **RLS** — GUC per transaction via `after_begin`; fail closed; `system` scope for workers; policies only on
    staff-read tables in phase 9.
19. **Settings store** — new national `platform.setting` table + `/staff/settings` page next to `settings/ai`,
    editable by a national settings role only.
20. **Anonymous quota counter** — `identity.account.anon_reports_accepted`, incremented atomically
    (`UPDATE … WHERE accepted < :limit RETURNING`) in the create transaction, only when `created=True`.
21. **6th report and SOS** — `403 anon_quota_exhausted` + registration prompt + 198 button; recommend SOS beyond quota
    accepted and flagged `needs_verification` (keeps A1 for life-threatening cases) — needs owner sign-off.
22. **Quota retention/purpose (law 63-2004)** — counter lives with the pseudonym, purged with the anonymous account
    (365 d), documented in the processing register and the privacy charter version bump.
23. **Mobile handling** — map the new code to `blocked` (`sync_engine.dart:186`), show remaining quota from a header
    (`X-Anon-Quota-Remaining`) on each accepted report.
24. **English** — add `en.json`, a three-way language menu, `en` in API `ReportLang`, `{ar,fr,en}` label pairs,
    `geo.gouvernorat.name_en` (fallback fr), Keycloak staff locale `en`; codes stay untranslated in the API.
25. **Export language** — default `lang` of library/schedule requests = user's UI language; stored per document.
26. **Real alert/government integration** — keep provider flags off; add an explicit `notify.real_send_enabled`
    national setting defaulting false, refused in production checks without approval reference.

Proposed migrations (revision ids follow `0017_rewards` style):

| Rev | Module | Content |
|---|---|---|
| `0018_platform_settings` | core/settings | `platform.setting` table, seed SLA bands and anonymous quota |
| `0019_identity_anon_quota` | identity | `account.anon_reports_accepted`, `anon_quota_reached_at` |
| `0020_reports_jurisdiction` | reports | claim, SLA, escalation, geo-verification columns; `reporter_context`; `report_escalation` |
| `0021_ops_multi_gouvernorat` | ops | `incident.lead_gouvernorat_code` (backfill from `gouvernorat_code`), `command_level`, `incident_gouvernorat`, `resource_request`, `assignment.request_id` |
| `0022_access_break_glass` | access (new schema) | `break_glass_grant`; regional account-admin request log |
| `0023_audit_scope` | audit | generated `gouvernorat_code` column from `details` + index (chain function untouched) |
| `0024_i18n_english` | analytics/geo | `ck_*_lang` add `en`; `geo.gouvernorat.name_en` |
| `0025_rls_policies` | reports/ops/telephony/streams/audit | enable RLS + policies on staff-read tables; grants for restricted tables |
