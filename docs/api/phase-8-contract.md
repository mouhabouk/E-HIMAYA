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
