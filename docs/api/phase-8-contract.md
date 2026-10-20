# عقد الواجهة البرمجية — المرحلة 8 (المعرفة والتحليلات)

Phase 8 additions (phases 2–7 stay valid). Conventions unchanged: `snake_case` JSON, errors `{"detail": "<code>"}`,
`429 rate_limited` with `Retry-After`, staff scope by gouvernorat (national roles see all), every staff write audited,
cursor pagination `?cursor=&limit=` → `{"items","next_cursor"}`, dashboard ar/fr, mobile ar/fr/en, RTL.

Requirements: FR-C-01 (trends), FR-C-12, FR-C-20, FR-C-21, FR-C-22, FR-C-23, FR-A-070, FR-A-071, FR-A-072,
architecture §5 (rewards, reports and knowledge modules), §6 (RAG over the national memory), operational levels
(rewards paused at level `disaster`), OpenSearch 2 for Arabic full-text search (architecture table, phase 8).

Golden rules for this phase:
* **Aggregates never leak people.** Analytics and exports carry counts, durations and areas, never names, phone
  numbers or exact citizen positions; any cell under 5 reports is shown as `<5` in exports shared outside the
  national level (k-anonymity floor, configurable `ANALYTICS_MIN_CELL`).
* **Humans award.** Points follow configured rules automatically, but badges above bronze, nominations and
  certificates are confirmed by a staff member, audited, and can be revoked with a reason.
* **Search respects scope.** Every search hit is filtered by the caller's role and gouvernorat *before* it is
  returned; the index never decides access on its own.

Owners and migration numbers (three API modules are built in parallel):
`modules/analytics` → `0015_analytics`; `modules/knowledge` → `0016_knowledge`; `modules/rewards` → `0017_rewards`
(each `down_revision` is the previous one). New role scopes go in the Keycloak realm export by the module that needs
them; the dashboard and mobile workers own their apps.

## 1. Analytics and reports (`modules/analytics`) — FR-C-01, FR-C-12, FR-C-21

* `GET /api/v1/staff/analytics/overview?from=&to=&gouvernorat=&category=` → totals (received, verified, in progress,
  closed, rejected), mean and p90 response time (received → first assignment → on scene → closed), breakdown by
  category, gouvernorat, status, source (`app|sms|call|portal`) and hour of day / day of week.
* `GET /api/v1/staff/analytics/trends?metric=reports|response_time|interventions&interval=day|week|month&…` →
  time series with the same period last year when available and a simple seasonal baseline
  (`expected`, `low`, `high` from the same weeks of previous years; `null` when history is too short).
* `GET /api/v1/staff/analytics/hotspots?…` → GeoJSON hexagon grid (H3-like hexes computed in PostGIS,
  `ST_HexagonGrid`) with counts, never single points.
* What-if simulation (FR-C-12): `POST /api/v1/staff/analytics/scenarios` `{"name","gouvernorats":[…],
  "category":…, "demand_factor": 1.0–10.0, "unavailable_resources": [ids] | {"kind": n}, "horizon_hours": 6–72,
  "weather": "as_forecast|fire_danger_extreme|heavy_rain"}` → a run that replays the historical arrival rate for that
  category, place and season, scaled by the factor (and by the phase 7 weather/fire-danger relation when chosen),
  against the resources left, with a deterministic seeded queue simulation (Monte Carlo, ≥ 200 runs, seed stored).
  Result: expected reports per hour, expected waiting time and resource utilisation with 10/50/90 percentiles, the
  hours where demand exceeds capacity, and `assumptions` (ar/fr). `GET …/scenarios`, `GET …/scenarios/{id}`.
  It is a planning aid built on history and says so in its disclaimer.
* Reports repository (FR-C-21), `analytics.report`: `id, kind (incident_summary|period_summary|gouvernorat_summary|
  scenario|after_action), title, period_from, period_to, gouvernorats, filters, format (pdf|xlsx), status
  (queued|ready|failed), media_id, sha256, created_by, schedule_id, created_at`. PDF via WeasyPrint (already pinned)
  with an RTL Arabic template and French twin, XLSX via openpyxl (new pinned dependency), both with a cover page,
  the filters used and the `ANALYTICS_MIN_CELL` rule. Generation runs in a worker loop (`WORKER_LOOPS` gains
  `analytics`), the file goes to S3 like other media, download is a 302 presigned URL, audited.
  `POST /api/v1/staff/reports-library` (create), `GET …?q=&kind=&from=&to=&gouvernorat=&cursor=` (search and filter;
  title and filters, full-text through the knowledge search when available), `GET …/{id}`, `GET …/{id}/download`.
* Scheduled reports, `analytics.schedule`: `kind, filters, format, cron (daily|weekly|monthly at a time, Africa/Tunis),
  recipients (staff user ids only), enabled`. CRUD under `/api/v1/staff/report-schedules`; on each run the report is
  generated and recipients get an in-app notification (existing phase 5 notify, no email in this phase).

## 2. National memory and events library (`modules/knowledge`) — FR-C-22, FR-C-23

* National memory, `knowledge.memory_entry`: `id, title {ar,fr}, event_type, started_at, ended_at, gouvernorats,
  geometry (optional area), incident_ids, summary, strengths, weaknesses, lessons, recommendations (each {ar,fr} text,
  Markdown), sources (list of {title, url | media_id}), access (national|gouvernorat|committee), status
  (draft|in_review|published|archived), author, reviewers, version` with full version history
  (`knowledge.memory_entry_version`). Workflow: draft → in_review (a second staff member reviews) → published;
  every transition audited. `POST /api/v1/staff/memory/from-incident/{id}` pre-fills a draft (timeline, figures,
  resources used, response times) for the after-action review; nothing is published automatically.
  CRUD and transitions under `/api/v1/staff/memory`. Published entries also become a source for the phase 7
  assistant (`sources.kind = "memory"`), next to procedures and past incidents.
* Events library: one search over memory entries, reports-library documents, incident timelines, report texts
  (already translated to ar), call and video transcripts when present (`reports.media` with a transcript), and
  procedures. Index: OpenSearch 2 (pinned 2.19.x, single node, security plugin on, Arabic + French analyzers,
  index per kind with an alias) fed by an outbox consumer (`WORKER_LOOPS` gains `knowledge`) and a backfill command;
  semantic part: pgvector embeddings from the existing AI `embed` endpoint, merged with the text score
  (reciprocal rank fusion). When OpenSearch is down or disabled (`SEARCH_BACKEND=postgres`) the API falls back to
  PostgreSQL full-text search (`simple` config + `pg_trgm` for Arabic) with the same response shape and
  `"backend": "postgres"`.
  `GET /api/v1/staff/library/search?q=&kinds=&from=&to=&gouvernorat=&category=&cursor=` →
  `{"items":[{"kind","id","title","excerpt" (highlighted, `<mark>` only),"date","gouvernorat","category",
  "incident_id","score"}],"facets":{"kind","year","gouvernorat","category"},"backend","next_cursor"}`.
  `GET /api/v1/staff/library/calendar?year=&month=&…` → counts per day; `GET /api/v1/staff/library/tree?by=
  period|type|gouvernorat` → nested counts for the tree view; `GET /api/v1/staff/library/items/{kind}/{id}` →
  the item with its linked media (playable through existing presigned URLs, audited).

## 3. Rewards (`modules/rewards`) — FR-A-070, FR-A-071, FR-A-072, FR-C-20

* Ledger, `rewards.points_ledger`: `id, citizen_id, delta, reason (report_verified|report_helped_rescue|
  accurate_category|volunteer_mission|manual|revocation), report_id, intervention_id, rule_id, multiplier,
  created_by (null for automatic), created_at` — append-only; the balance is the sum. Rules,
  `rewards.rule` (configurable from the dashboard, audited): defaults verified +50, helped rescue +500 (set by staff on
  the intervention), accurate category ×1.5 (the citizen's chosen category equals the verified one), volunteer
  mission completed +100. Events come from the existing outbox (`report.verified`, `intervention.closed`, …),
  idempotent per (reason, report_id/intervention_id). **No points for anonymous reports**, none for rejected or
  false reports; points are paused at operational level `disaster` (queued and applied when the level drops, as the
  architecture states).
* Badges, `rewards.badge_award`: bronze 100, silver 500, gold 2000 (automatic on threshold, bronze immediate,
  silver/gold confirmed by staff before they show), ambassador 10000 (staff confirmation required). Thresholds are
  settings.
* Nominations (FR-C-20), `rewards.nomination`: `kind (vigilant_citizen|brave_volunteer|leading_institution),
  subject (citizen|volunteer|org id), year, reason, evidence (report/intervention ids), status (proposed|approved|
  rejected), decided_by`. Approved nominations and confirmed gold/ambassador badges can produce a **certificate PDF**
  (WeasyPrint, ar/fr, QR to a public verify URL `GET /api/v1/rewards/certificates/{code}` that shows only the name
  initials, the distinction and the date) like the phase 4 safety certificate.
* Citizen: `GET /api/v1/me/rewards` → `{"balance","badges":[…],"next_badge":{…,"missing_points"},"history":[…],
  "certificates":[…],"paused":bool}`; `GET /api/v1/me/rewards/certificates/{id}` (PDF).
* Staff: `GET /api/v1/staff/rewards/citizens?…` (pseudonymous list, contact only for roles that already have it),
  manual adjust with reason, badge confirmation, rules CRUD, nominations CRUD, `GET …/rewards/leaderboard?scope=
  gouvernorat|national&period=year` (pseudonyms only).
* Privacy: deleting an account (phase 5.5 rights) deletes its ledger rows and anonymises nominations; the ledger
  follows the citizen data retention rules.
* Safety (R1 audit finding T25): rewards must never encourage repeated reporting or putting oneself in danger.
  Points come only from **verified usefulness**, never from the number of reports sent, the number of photos/videos,
  streaming, or being on scene; a daily cap per citizen (`REWARDS_DAILY_CAP`, default 200 points, rescue awards
  excluded) and duplicates of an already verified incident earn nothing beyond the first verified reporter
  (later reporters of the same incident get the verified bonus only once per incident, not per report).
  **No cash rewards in this release**: the "annual financial prizes" of FR-A-072 are shown as "subject to a decision
  of the competent authority" and nothing in the code pays or promises money. The rewards screen carries a fixed
  safety notice (ar/fr/en): "never put yourself in danger to report; call 198".

## 4. Dashboard (ar/fr)

* Analytics page: KPI cards, trends chart with the seasonal band, breakdown charts, hex map layer, filters shared
  in the URL; "export" opens the report form prefilled.
* What-if page: form, run, percentile bands chart, overload hours highlighted, assumptions and disclaimer visible.
* Reports library: search, filters, status, download; schedules management.
* National memory: list, editor (Markdown ar/fr side by side), review workflow, version diff, "start from incident"
  button on the incident page.
* Events library: search box with facets, calendar view, tree view, item view with linked media.
* Rewards: rules, pending confirmations, nominations, certificates, leaderboard.
* Charts use one chart library already in the dashboard if any, otherwise a pinned, MIT/Apache one; every chart has
  a data table alternative (accessibility).

## 5. Mobile (ar/fr/en)

* Rewards screen (FR-A-072): balance, current and next badge with progress, history, certificates (open PDF),
  "paused" notice at disaster level; anonymous users see an explanation that anonymous reports earn no points.
* After a report is verified, the existing tracking screen shows the points it earned.

## Implementation notes

### Rewards (`modules/rewards`, migration `0017_rewards`)

* **Events.** There is no `report.verified` / `intervention.closed` event in the code base; the consumer (worker loop
  `rewards`, own cursor `rewards.consumer_cursor` over `events.outbox`, holes in the ids waited for 60 s) uses the
  existing ones: `report.status_changed` with status `closed` → `report_verified` (+ `accurate_category`),
  `assignment.updated` (volunteer, `released` after `on_scene`) → `volunteer_mission`, `oplevel.changed` → queued
  awards re-examined (also every loop pass). No event emission was added. Events name what changed; awards are
  decided from the current rows and are idempotent (`dedup_key` unique in the ledger and in `rewards.pending_award`).
* **"Verified"** = report closed (never received/in progress/rejected) and its incident not closed as `false_alarm`.
  Once per citizen per incident (`report_verified:<citizen>:incident:<id>`; per report when it has no incident).
  `accurate_category` = report category equals the incident's category (not `other`); booked as its own row:
  delta = verified points × (multiplier − 1), `multiplier` = 1.5. Only accounts of kind `citizen`, active and not
  erased earn: anonymous devices **and institution accounts** get nothing.
* **Helped rescue** is set by staff with `POST /api/v1/staff/rewards/interventions/{incident_id}/rescue`
  `{"report_ids":[…],"note"}` (roles operator/ops_manager/field_commander, incident in scope, closed and evaluated,
  not false alarm: `409 incident_not_evaluated|false_alarm`), once per citizen per incident; outside the daily cap.
* **Daily cap** `REWARDS_DAILY_CAP` (200, Africa/Tunis day) on `report_verified`, `accurate_category`,
  `volunteer_mission`; an award beyond it is booked with the remaining points (possibly 0) and `capped: true`.
* **Pause**: an award whose report/incident gouvernorat is at level `disaster` goes to `rewards.pending_award`
  (rule values frozen at that time) and is applied (cap computed on the day of application) once the level drops.
  `/me/rewards.paused` = the citizen has queued points or their profile gouvernorat is at `disaster`.
* **Ledger** append-only by trigger (only detaching a deleted/anonymised report, incident or rule is allowed).
  Corrections: `manual` (±5000, reason) and `revocation` (`POST /staff/rewards/ledger/{id}/revoke`, once).
* **Badges**: thresholds `REWARDS_BADGE_*` (must increase). One row per citizen and level; bronze `confirmed` at once,
  others `pending` until `confirm`/`reject`; `revoke` also revokes the badge's certificate. Badges are not withdrawn
  automatically when the balance drops.
* **Nominations**: `subject_kind` must match the kind (422 `invalid_subject`), subject must exist and be in the
  caller's scope (`404 subject_not_found`), evidence ids must exist (`422 invalid_evidence`), one non-rejected
  nomination per kind/subject/year (`409 duplicate_nomination`), the proposer cannot decide (`409 same_reviewer`).
* **Certificates**: code `EHR-<yy>-<6 digits>-<4 random hex>`, signed Ed25519 with `CERTIFICATE_SIGNING_KEY`
  (`503 signing_key_missing`) over `code|distinction|initials|issued date`; QR → `API_PUBLIC_URL` (new setting,
  production `https://API_HOST`) + `/api/v1/rewards/certificates/{code}`, which returns exactly
  `{code, valid, initials, distinction, distinction_label, date}` (rate-limited 60/min per address). PDF downloads
  (`/me/rewards/certificates/{id}`, `/staff/rewards/certificates/{id}/pdf`) are **302 redirects to a presigned URL**
  (audited), or `200 {"url"}` with `Accept: application/json`, like the analytics downloads.
* **Roles**: read = reports read roles (operator, ops_manager, field_commander, local/central committee); decisions
  (adjust, revoke, badges, nominations, certificates) = ops_manager, local_committee, central_committee; rules write =
  central_committee or sysadmin with national scope (`403 national_scope_required`); sysadmin may read rules/settings.
  Rules: four seeded defaults (cannot be deleted, `409 default_rule`) plus per-category overrides
  (`409 rule_exists`). Contact data in `/staff/rewards/citizens[/{id}]` only with `with_contact=true` (audited).
  Leaderboard: `scope=national` needs national staff; `scope=gouvernorat` defaults to the caller's gouvernorat.
* **Privacy**: `/me/export` gains `rewards`; `/me/delete` deletes ledger, queued awards and badges, anonymises
  nominations (subject, reason, evidence), detaches certificates and deletes their PDF (the public verification keeps
  initials/distinction/date). Retention job `rewards_ledger` detaches ledger rows from reports once anonymised.
* **No cash**: `prizes_notice` and `safety_notice` (ar/fr/en) are returned by `/me/rewards`; nothing pays money.
* Not done: no push notification when points are earned; the consumer misses events if stopped longer than
  `RETENTION_EVENTS_DAYS` (manual adjustment then).

### Mobile (`apps/mobile`, FR-A-072)

* **Screen** `/rewards` ("My rewards"), reached from a home card and from Settings (identity section) for citizens
  (anonymous included). Shows balance, current badge (`current_badge`, else highest listed badge), next badge with
  a progress bar (`balance / threshold`) and `missing_points`, history (first 50 from `/me/rewards`, then
  "show more" via `/me/rewards/history?cursor=`), certificates, the "points paused" card when `paused` (with
  `pending_points`), `daily_cap`, and a generic "how to earn" text (no amounts: rules are configurable).
* **Safety / no cash**: the safety notice ("never put yourself in danger…, call 198", with a call button) and the
  prizes notice ("subject to a decision of the competent authority") are **fixed app strings in ar/fr/en**, always
  shown (also offline and to anonymous users); the server's `safety_notice` / `prizes_notice` are not displayed.
* **Anonymous**: the app does not call `/me/rewards` for an anonymous device (or an institution account); it shows
  the explanation and a "create an account" button. A `200 {"anonymous": true}` answer is rendered the same way.
* **Certificates**: `GET /me/rewards/certificates/{id}` is requested without following redirects; the `Location`
  (presigned URL) is then fetched **without any identity header**; an inline `200` PDF is accepted too. The file
  is written to the app cache folder (`certificates/`) and opened with `open_filex 4.7.0` (BSD-3, new dependency;
  its `READ_EXTERNAL_STORAGE`/`READ_MEDIA_*` permissions are removed from the merged Android manifest).
* **Offline**: the last summary is kept in the secure store (`rewards_cache_v1`), tied to the account and deleted
  on logout / account deletion; shown with "offline: copy saved on <date>" when the phone is offline or the API
  is unreachable.
* **Tracking screen**: for a signed-in citizen, the points a report earned are the sum of `history[]` rows whose
  `tracking_code` equals the tracked code (the public track answer is unchanged). Limitation: only the 50 latest
  history rows are searched; points appear a few seconds after the report is closed.
* Not verified here: `flutter build apk --debug` (no Android SDK in this environment), so the `open_filex`
  manifest merge is unbuilt; format, analyze and the full `flutter test` suite pass locally.

### §1 Analytics and reports (`modules/analytics`, migration `0015_analytics`)

* **Shapes** (as agreed with the dashboard): overview `{from,to,gouvernorats,category,totals,response_time:{to_assignment,
  to_on_scene,to_closed:{mean_s,p90_s,n}},by_category|by_gouvernorat|by_status|by_source|by_hour|by_weekday:[{key,count}],
  min_cell}`; "verified" = reached in_progress/intervened/ongoing/closed; hours and ISO weekdays in Africa/Tunis.
  Trends `{metric,interval,unit,points:[{period_start,value,last_year,expected,low,high}],baseline_available,
  history_years}`: the band is mean ± 1.96 sd of the same period (same weekday 52 weeks back, same month) of up to 5
  previous years, shown only from 2 years that already had data. `response_time` = mean seconds to first assignment;
  `interventions` = resources ordered (cancelled excluded). Hotspots: `ST_HexagonGrid` in EPSG:3857, `size_km` 1–50
  (default 5, corrected for latitude), properties `{id:"i:j",count}`, `cell_size_m`.
* **Scope**: a regional caller is limited to their gouvernorat (403 `out_of_scope` for another); documents and
  scenarios with `gouvernorats: []` are national and visible to national roles only. Roles: read = operator,
  ops_manager, field_commander, local/central committee; scenarios and documents = the same minus operator;
  schedules = ops_manager and committees. No new Keycloak role.
* **What-if** (FR-C-12, audit finding T26): computed synchronously on POST (status `done`), seeded `random.Random`,
  `ANALYTICS_SCENARIO_RUNS` (default 200) runs, optional `seed` in the body. History = same season (±45 days) of the
  last 3 years; days without any report nationwide are treated as data gaps (`gap_days`) and excluded. Result carries
  `provenance` (history window, events, incidents, days covered, gap days, service-time source and sample size,
  weather factor and its source), `calibration: "uncalibrated"` with `calibration_note` {ar,fr}, `confidence:
  "low"|"normal"` with `confidence_reasons` [{ar,fr}] (low when < 30 events, < 30 covered days or default service
  times), `assumptions` [{ar,fr}] and `disclaimer` {ar,fr}. Rounding: demand 1 decimal, waits whole minutes,
  utilisation 2 decimals, service time to 5 min. Weather factors are measured from phase 7 past observations when
  history allows, otherwise stated defaults (fire ×2.5 under very high/extreme danger; flood ×3, landslide ×2,
  traffic ×1.3, drowning ×1.2 under heavy-rain watch/warning). Errors: `no_capacity`, `unknown_resource`,
  `demand_too_large`, `unknown_gouvernorat`; 20 runs/hour/person (`ANALYTICS_SCENARIOS_PER_HOUR`).
* **Reports repository**: extra fields `lang` (ar = RTL Arabic template, fr = French twin; one language per file),
  `error`, `bytes`, `ready_at`; status also `running`. Filters `{category?, incident_id?, scenario_id?}` (incident kinds
  and scenario take the gouvernorat of their target). The file is a `reports.media` row of new kind `analytics_report`
  (`ck_media_kind` extended). Download: 302 by default, `Accept: application/json` → `{"url"}` (5 min URL); 409
  `report_not_ready`. The k-floor is applied to **every** export (stricter than "outside the national level", since a
  national document can be forwarded); durations computed on fewer than `ANALYTICS_MIN_CELL` reports are left blank;
  after-action documents carry counts only, never the free-text summary or lessons. `q` = title/filters ILIKE, OR'ed
  with `knowledge.search.search_ids(..., kinds=["report_doc"])` when it answers (`search_backend` in the page).
* **Schedules**: `cron` is an object `{frequency, time "HH:MM", weekday (weekly), day 1–28 (monthly)}` in
  Africa/Tunis; kinds `period_summary|gouvernorat_summary`; covered period = previous day / previous 7 days / previous
  calendar month. CRUD = POST, GET, GET /{id}, PATCH, DELETE.
* **Deviation — in-app notification**: phase 5 notify only addresses citizen accounts (`identity.account`), so staff
  recipients get rows in `analytics.notification` (`GET /api/v1/staff/analytics/notifications` → `{items, next_cursor,
  unread}`, `POST …/{id}/read`) plus the live WebSocket event `analytics.report_ready` / `analytics.report_failed`
  (route added in `reports/live.py`, delivered only to the creator and recipients). Marking read is not audited.
* Worker loop `analytics` (`ANALYTICS_INTERVAL_S`, default 60 s): due schedules, then the queue (SKIP LOCKED, 10 min
  lease, 3 attempts; a missing incident/scenario fails at once). New settings: `ANALYTICS_MIN_CELL` (5),
  `ANALYTICS_SCENARIO_RUNS`, `ANALYTICS_INTERVAL_S`, `ANALYTICS_MAX_PERIOD_DAYS` (1830), `ANALYTICS_SCENARIOS_PER_HOUR`.

### §4 Dashboard (`apps/dashboard`)

* **Routes** (lazy-loaded, role-gated like the existing pages; nav links appear only for allowed roles):
  `/analytics` (+ `/analytics/scenarios`, `/analytics/scenarios/:id`), `/reports-library` (+ `/schedules`),
  `/memory`, `/memory/new`, `/memory/:id`, `/library`, `/library/items/:kind/:id`, `/rewards` (+ `/confirmations`,
  `/nominations`, `/certificates`, `/leaderboard`). Gates mirror the API: reports/scenarios = ops_manager,
  field_commander, committees; schedules = ops_manager, committees; memory review = ops_manager, committees (the author
  never sees a review action on their own entry); reward rule edits = central_committee/sysadmin at national scope.
  The incident page has a "start from incident" button (POST `/memory/from-incident/{id}`).
* **Charts**: uPlot 1.6.32 on canvas (lazy chunk ~24 kB gzip), `aria-hidden` and `dir="ltr"` inside RTL pages; every
  chart has a text summary, a legend and a toggle to a full data table (seasonal band and highlight columns included).
  Hex layer = an extra MapLibre GeoJSON source on the existing map, quantile 5-class colours with a legend.
  Filters live in the URL; "export" opens the report form prefilled from the same query string.
* **Markdown**: markdown-it with `html: false` and images off, then DOMPurify (allowlist; links http(s)/mailto only,
  forced `rel="noopener noreferrer nofollow"`). ar and fr edited side by side with live preview; `version` sent with
  PATCH, 409 `version_conflict` shown as "reload". Version diff is a client-side line diff of two `/versions/{v}`.
* **Downloads** (reports, certificate PDF) always use `Accept: application/json` → `{"url"}` and open the presigned
  link, so the CSP keeps no new origin (`connect-src` unchanged).
* **Rewards safety**: no cash/prize configuration anywhere; `GET /rewards/settings` (daily cap, thresholds, paused
  gouvernorats) shown read-only with a "no money prizes" notice.
* **Not in the UI (open)**: the rescue flag (`POST /staff/rewards/interventions/{incident_id}/rescue`) and citizen
  points adjustment; the live `analytics.report_ready`/`report_failed` events are not wired (the reports page polls
  every 5 s while a report is queued/running and lists unread notifications). Schedule recipients are entered as
  staff UUIDs (no staff-directory endpoint), with an "add me" shortcut.

### §2 National memory and events library (`modules/knowledge`, migration `0016_knowledge`)

* **Tables**: `knowledge.memory_entry`, `knowledge.memory_entry_version` (one full snapshot per saved change and per
  transition), `knowledge.search_doc` (one row per library item: the PostgreSQL index and the authority for every
  scope check; surrogate `id` identity key + unique `(kind, ref_id)`, required by key rotation), `knowledge.index_state`
  (outbox cursor, sweep watermarks). The migration creates `pg_trgm` (trusted extension) and drops it on downgrade.
* **Memory workflow**: a single `POST /staff/memory/{id}/transition {to, note?, version}` instead of one route per
  transition: draft → in_review (authors), in_review → published (reviewers: ops_manager, local/central committee;
  never the author nor the last editor: 403 `self_review_forbidden`), in_review → draft (`note` required: changes
  requested), draft|published → archived (`note` required), archived → draft. Authors: ops_manager, field_commander,
  local/central committee, content_editor. `version` is an optimistic lock (409 `version_conflict`). Editing a
  published entry turns it into a draft; readers keep seeing `published_version` until the next publication. Other
  codes: `entry_in_review`, `entry_archived`, `entry_published_once` (delete), `invalid_transition`, `note_required`,
  `out_of_scope`, `insufficient_role`. Every write is audited (`memory.<change>`, `library.item_view`) and emits
  `memory.updated`. `from-incident` pre-fills a draft (`access: gouvernorat`), never publishes.
* **Access**: `national` → every library role; `gouvernorat` → national roles and the entry's gouvernorats;
  `committee` → the national central committee, and committee members of one of the entry's gouvernorats. Operational kinds
  (incident, report, transcript, report_doc) only reach roles that read incidents; content editors see memory and
  procedures. Scope is applied in the query (SQL `WHERE` or OpenSearch `filter`) and every OpenSearch hit is checked
  again against `search_doc` before it is returned; the item endpoint answers 404 outside scope.
* **Search**: OpenSearch indices `<prefix>-<kind>-v1` behind the aliases `<prefix>-<kind>` and `<prefix>-library`
  (`backfill --rebuild` fills `-v1-r<time>` indices and moves the aliases at the end). Analyzers: folded (Arabic
  normalisation, diacritics, alef/ya/ta marbuta, French elision/ASCII folding), Arabic (stemmer) and French
  (light stemmer). Semantic part: e5 vectors (768) in `search_doc.embedding`, HNSW cosine, kept when similarity ≥ 0.8;
  merged with the text ranking by RRF (k = 60, ≤ 300 candidates each). Highlights are produced with private sentinels
  and the text is HTML-escaped before they become `<mark>`, so `<mark>` is the only markup ever returned. Facets are
  computed over the candidate set (≤ 300) for a query and by SQL aggregates when browsing (empty `q`).
  `score` is the fused RRF score. `library_search_per_minute` (default 60) per staff member.
* **PostgreSQL fallback**: `"backend": "postgres"` when `SEARCH_BACKEND=postgres`, when OpenSearch is not configured
  (no URL or password), while its CA file is not written yet, and per request when it fails (the error is logged).
  Texts encrypted at their source (report texts, transcripts) stay encrypted in `search_doc` and are matched through
  blind-index tokens: whole words only (no prefix, no trigram; excerpts are cut from the decrypted text); all other
  kinds use the `simple` tsvector with prefix matching plus `pg_trgm` similarity.
* **Dates**: memory = `started_at`, report_doc = `period_from`, incident = creation, report/transcript = creation;
  procedures are dateless (excluded by `from`/`to` filters and the calendar).
* **Indexer**: worker loop `knowledge` reads `events.outbox` with a cursor that waits 60 s for gaps (transactions that
  commit late), refreshes the affected rows, sweeps sources changed without an event, embeds rows through the AI
  service when it is configured and pushes dirty rows to OpenSearch (tombstones deleted after the push).
  `python -m app.modules.knowledge.cli backfill [--kinds …] [--rebuild]` and `… status`. Other modules can call
  `knowledge.search.search_ids(session, principal, q, kinds)` (never raises; used by analytics).
* **Assistant**: up to 2 published memory entries matching the incident (category, gouvernorat, text) are added as
  `sources[].kind = "memory"` (decision `Source.kind` gained `"memory"`; the dashboard should label it).
* **Infra**: `opensearchproject/opensearch:2.19.6` pinned by digest, compose profile `search` in development (always on
  in production), no published port; `infra/opensearch/ehimaya-entrypoint.sh` creates the installation's CA and
  certificates on first start, writes the security configuration (users `admin` and the API's user, restricted to
  `<prefix>-*`) and re-applies it with `securityadmin` when a password changes; it refuses missing, short, default
  or example passwords. **OpenSearch holds report texts and transcripts in clear** (they are encrypted in PostgreSQL):
  its volumes are as confidential as the database. CI runs `tests/test_knowledge.py` a second time against a real
  node (`api` job). Disk watermarks: OpenSearch stops writing above 95 % disk (the CI step turns them off).
