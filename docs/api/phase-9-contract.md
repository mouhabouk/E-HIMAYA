# عقد الواجهة البرمجية — المرحلة 9 (غرف العمليات المركزية والجهوية، حصة البلاغات المجهولة، الإنجليزية)

Phase 9 additions and changes (phases 2–8 stay valid except where §10 "Changes to earlier contracts" says otherwise).
Conventions unchanged: `snake_case` JSON, errors `{"detail": "<code>"}`, `429 rate_limited` with `Retry-After`,
cursor pagination `?cursor=&limit=` → `{"items","next_cursor"}`, every staff write audited, RTL for Arabic.
Dashboard becomes **ar/fr/en**; mobile and portal stay ar/fr/en.

Source: owner change request opening phase 9 (A anonymous quota, B English dashboard, C central vs regional rooms)
and the review `docs/phase-9/review.md` (cited below as "review §n"). Law 63-2004 (personal data) applies to §3.

Golden rules for this phase:
* **Scope is decided by the API, then again by the database.** Every staff read and write goes through one policy
  function (`core/access.py`); PostgreSQL row-level security is the second layer. The UI only hides what the API
  already refuses. Out-of-scope objects answer `404 not_found` (existence not disclosed); in-scope but forbidden
  actions answer `403 <code>`.
* **Jurisdiction follows the trusted incident location, never the reporter.** The reporter's gouvernorat is kept
  in a restricted record and never decides who handles a report.
* **One event, one incident file.** A cross-border event has one incident with one lead gouvernorat and
  participating gouvernorats; nothing creates a competing incident silently.
* **Central directs, regions intervene.** The central room may take over the answer to a late report and instruct
  a region; dispatching units, resources and volunteers stays with the region that owns them.
* **Emergency is never blocked.** 198 is always one tap away in the app; an SOS report is never refused for quota
  reasons; critical reports are never delayed by geographic verification.
* **Codes are fixed, words are translated.** Status, category, level, role and error codes never change with the
  language; the UI translates them. The citizen's original text is never replaced by a machine translation.
* **Nothing goes out for real.** Real alert sending and government integrations stay disabled (§7.4).

Owners and migration numbers (four workers build in parallel; each `down_revision` is the previous number):

| Migration | Owner | Content |
|---|---|---|
| `0018_platform_settings` | W1 | `platform.setting` + seeds (§2) |
| `0019_identity_anon_quota` | W1 | anonymous counter on `identity.account` (§3) |
| `0020_reports_jurisdiction` | W1 | claim, SLA, escalation, geo state, `reports.escalation`, `reports.reporter_context` (§4) |
| `0021_ops_multi_gouvernorat` | W2 | lead/participants, command level, resource requests (§5) |
| `0022_access_break_glass` | W2 | schema `access`: break-glass grants, account-admin log (§6) |
| `0023_audit_scope` | W2 | `audit.log.gouvernorats` generated column (§7.2) |
| `0024_i18n_english` | W2 | `en` in analytics language checks, `geo.gouvernorat.name_en` (§8) |
| `0025_rls_policies` | W4 | row-level security, last (§9) |

W1 = API access, settings, identity quota, reports jurisdiction/claim/SLA/geo. W2 = API ops multi-gouvernorat,
resource requests, live/analytics/knowledge/telephony adjustments, audit scope, break-glass, account-admin proxy,
Keycloak realm export. W3 = dashboard. W4 = mobile + RLS. File ownership in §11.

---

## 1. Access model (`core/security.py`, `core/access.py`) — owner W1

### 1.1 Roles and functions

Staff realm roles (W2 adds the three new ones to `infra/keycloak/realms/ehimaya-staff-realm.json`; W1 adds them to
`Role` and `REALM_ROLES` in `core/security.py`):

| Function | Roles |
|---|---|
| `command` | `central_committee` (committee chair, national), `local_committee` (regional committee’s committee), `field_commander` |
| `operations` | `operator`, `ops_manager` |
| `technical` | `sysadmin`, **`security_admin`**, **`ai_admin`**, **`regional_account_admin`** |
| `support` (unchanged) | `content_editor`, `org_auditor` |

`Principal` gains read-only properties: `functions: frozenset[str]` (derived from roles, never from a claim),
`room: "central" | "regional"` (`central` = `is_national`). Scope claims are unchanged (`scope_level`,
`gouvernorat_code`, review §1). A token carrying roles of two families is allowed (e.g. operator + content_editor);
technical roles never grant operational rights.

### 1.2 Policy function

```python
# core/access.py (W1)
class Action(StrEnum): ...            # values listed in the matrix below
@dataclass(frozen=True) class Ctx:     # what is being touched
    lead: int | None                   # report.gouvernorat_code or incident lead; None = unverified/central
    participants: frozenset[int]       # incident participating gouvernorats (empty for a lone report)
    candidates: frozenset[int]         # geo candidates of a pending report (§4.2)
    claimed_room: str | None           # "central" | "g:<code>" | None
    critical: bool                     # SLA band critical or category sos
    command_level: str = "regional"    # incident command level (§5.3)
    late: bool = False                 # escalation_state != none
async def authorize(session, principal, action, ctx) -> Decision   # Decision.allow | .not_found | .forbidden(code)
def require(decision) -> None          # raises 404 not_found / 403 <code>
async def visible_gouvernorats(session, principal) -> frozenset[int] | None   # None = national
```

`authorize` adds active break-glass grants (W2, `modules/access/grants.py: async def active_grants(session, subject)
-> list[Grant]`; W1 calls it, W2 implements it; until it exists W1 uses a stub returning `[]`).

"In scope" for a regional principal with gouvernorat `g`: `g == lead` or `g in participants` or
(`g in candidates` and `critical`) or an active grant covers the object. National principals: always in scope.

Action matrix (R = regional room of the object, N = national/central room, ✗ = refused `403 action_not_allowed`):

| Action | operator | ops_manager | field_commander | local_committee | central_committee | technical |
|---|---|---|---|---|---|---|
| `report.read`, `incident.read` | R, N | R, N | R, N | R, N | N | ✗ |
| `report.read_sensitive` (§1.3) | handling room | handling room | ✗ | ✗ | ✗ | ✗ (break-glass only) |
| `report.claim`, `report.status`, `report.link` | R; N only if late, geo-pending or central command level | same | ✗ | ✗ | ✗ | ✗ |
| `report.refer`, `report.geo_verify` | N | N | ✗ | ✗ | N | ✗ |
| `report.referral_decide` | R (target) | R (target) | ✗ | R (target) | ✗ | ✗ |
| `incident.card`, `incident.note` | R lead/participant, N | same | same | ✗ | N | ✗ |
| `incident.assign`, `incident.callout`, `assignment.status` | R, own resources only | same | same | ✗ | ✗ | ✗ |
| `incident.close` | ✗ | R lead | R lead | ✗ | ✗ | ✗ |
| `incident.participants`, `incident.merge` | ✗ | R lead (participants), N | ✗ | R lead (participants) | N | ✗ |
| `incident.lead_transfer`, `incident.command_level` | ✗ | N | ✗ | ✗ | N | ✗ |
| `resource_request.create` | R lead/participant, N | same | same | same | N | ✗ |
| `resource_request.decide` | ✗ | owning R | ✗ | owning R | N when incident `command_level = central` | ✗ |
| `directive.issue` | ✗ | N (late-report directive only, §4.4) | ✗ | R (own) | N | ✗ |
| `settings.write` (§2) | ✗ | ✗ | ✗ | ✗ | N | N per key (`ai_admin`, `security_admin`) |
| `breakglass.request` | R, N | R, N | R, N | R, N | N | ✗ |
| `breakglass.review`, `audit.read_raw` | ✗ | ✗ | ✗ | ✗ | ✗ | `security_admin` N |
| `audit.read_scoped` | ✗ | R | ✗ | R | ✗ | `security_admin` R |
| `account.manage` | ✗ | ✗ | ✗ | ✗ | ✗ | `regional_account_admin` (own gouvernorat; N = all) |
| `units.write`, `resources.write` | ✗ | R own gouvernorat | ✗ | ✗ | ✗ | ✗ (**sysadmin removed**) |

Existing role lists (`READ_ROLES`, `WRITE_ROLES`, …) stay as coarse first gates in the routers; `authorize` is called
after loading the object, before any change.

### 1.3 Sensitive data

Sensitive = reporter `first_name`, `last_name`, `phone`, and the whole `reporter_context` (§4.1). They are returned
only when `report.read_sensitive` is allowed: the caller has the `operations` function **and** the caller's room is
the handling room — `claimed_room` of the report, or the lead room of its incident when the caller's room has an
active assignment or claimed report in that incident. Otherwise the API returns
`"reporter": {"kind", "masked": true, "first_name": null, "last_name": null, "phone": "+216••••••12"}` (last two
digits) and `"reporter_context": null`. Field commanders reach the citizen through `POST /staff/calls/dial`
`{"report_id"}` (phase 7), which dials without revealing the number. An active break-glass grant on the report or its
gouvernorat reveals the fields; each reveal is audited `report.view_sensitive` with the grant id.

**Tests required** (`tests/test_access.py`, W1): matrix rows above as parametrised cases; technical roles get no
report/incident data; masked reporter for committees, field commanders, other rooms; unmasked for the claiming room;
reveal with a grant is audited; `functions`/`room` derivation.

---

## 2. National settings (`modules/settings`, new) — owner W1, migration `0018_platform_settings`

`platform.setting(key text PK, value jsonb NOT NULL, version int NOT NULL DEFAULT 1, updated_by text,
updated_at timestamptz)`. Seeds:

| Key | Default | Editable by (national scope required) |
|---|---|---|
| `sla.bands` | `{"critical": 85, "high": 70, "normal": 40}` (lower bounds of `reports.report.priority_score`, 0–100; below `normal` = `low`) | `central_committee` |
| `sla.claim_delay_s` | `{"critical": 60, "high": 90, "normal": 120, "low": 180}` (each 15–3600, critical ≤ high ≤ normal ≤ low) | `central_committee` |
| `sla.enforced_since` | migration timestamp (no retro-escalation) | read-only |
| `anonymous.report_quota` | `5` (1–100) | `central_committee`, `security_admin` |
| `geo.max_trusted_accuracy_m` | `1000` (50–20000) | `central_committee` |
| `notify.real_send_enabled` | `false` | **not editable in phase 9** (`403 requires_formal_approval`) |

Bands use the existing BR-20 priority (`reports.report.priority_score`, phase 3); an SOS report, or a report with no
score yet and category `sos`, is `critical`; no score otherwise = `normal`. The dashboard's existing
high/medium/low display (`lib/priority.ts`, ≥70/≥40) gains `critical` (≥ `sla.bands.critical`) and renames
`medium` → `normal` in labels only.

Routes:
* `GET /api/v1/staff/settings` (any staff) → `{"items":[{"key","value","version","updated_by_name","updated_at",
  "editable": bool}]}`.
* `PUT /api/v1/staff/settings/{key}` `{"value", "version", "reason"}` (reason 5–500 chars) → the item.
  `403 national_scope_required`, `403 action_not_allowed`, `409 version_conflict`, `422 invalid_setting`,
  `404 not_found`. Audited `settings.update` with `before`/`after`. Emits `settings.changed {"key"}`.
* `services/settings.get(session, key)` with a 10 s in-process cache, invalidated on `settings.changed`.
* AI settings (`/staff/ai/settings`, phase 3) stay in `ai.settings`; `PUT` roles become `central_committee`,
  `ai_admin` (national), sysadmin removed. Reward rules: `central_committee` only (sysadmin removed).

**Tests required** (`tests/test_settings.py`): defaults present; regional and technical-without-domain refused;
version conflict; band ordering validation; audit before/after; `notify.real_send_enabled` not writable.

---

## 3. Anonymous report quota (`modules/identity`, `modules/reports`) — owner W1, migration `0019_identity_anon_quota`

Schema: `identity.account.anon_reports_accepted int NOT NULL DEFAULT 0`, `anon_quota_reached_at timestamptz`.
No backfill: every existing installation starts at 0 when phase 9 is deployed, so no device is blocked by reports
made before the rule existed (owner rule: per installation, 5 accepted reports, counted from the release).

Rules (`POST /api/v1/reports`):
1. Order: idempotent replay lookup **first** (a replay of a known `client_uuid` returns `200` and consumes neither
   the quota nor the per-account/per-IP windows) → abuse checks (phase 2.5, unchanged) → consent → quota → insert.
2. For `kind = anonymous` and category ≠ `sos`: in the insert transaction,
   `UPDATE identity.account SET anon_reports_accepted = anon_reports_accepted + 1 WHERE user_id = :u AND
   anon_reports_accepted < :quota RETURNING anon_reports_accepted`; no row → `403 anon_quota_exhausted`, nothing
   stored. The increment rolls back with the insert (concurrent duplicate `client_uuid` → no double count).
3. Category `sos` beyond the quota: accepted, `needs_verification = true`, `verification_reason =
   "anonymous_quota"` (priority lowered like `anonymous_budget`, phase 2.5), counter still incremented.
4. SMS-adopted reports (phase 7) do not count. Registered citizens and institutions have no quota.
5. Every response for an anonymous caller carries `X-Anon-Quota-Limit` and `X-Anon-Quota-Remaining` (0 when
   exhausted, also on the 403); CORS exposes both headers.
6. `GET /api/v1/reports/quota` (anonymous or citizen) → `{"limit": 5, "used": 3, "remaining": 2}` for anonymous,
   `{"limit": null, "used": null, "remaining": null}` for registered accounts.

Law 63-2004 record (added to `docs/` privacy register by W1): purpose = limit anonymous abuse and invite
registration; data = existing HMAC pseudonym (`core/crypto.py`) + one counter, no IP, no device identifier in
clear; retention = with the anonymous account (existing purge rules, phase 5.5) and anonymised with it; protection =
pseudonym secret in the secrets store, counter readable only by the API (not exposed to staff). The counter is part
of `GET /me/export` for the device. The privacy charter text update is an owner/legal decision outside this contract
(no forced charter version bump in phase 9).

**Tests required** (`tests/test_anon_quota.py`, W1): 5 accepted then `403 anon_quota_exhausted`; replay of the 5th
returns 200 and keeps remaining = 0 without error; concurrent identical replays count once; SOS 6th accepted and
flagged `anonymous_quota`; registered user unaffected; quota from settings (change to 3 applies at once);
headers present; existing accounts start at 0 after the migration; replay does not consume the per-IP window (update of
`test_hardening.py`).

---

## 4. Report jurisdiction, claim, SLA and escalation (`modules/reports`) — owner W1, migration `0020_reports_jurisdiction`

### 4.1 Schema (`reports.report` new columns)

`geo_state text NOT NULL DEFAULT 'trusted' CHECK IN ('trusted','pending','contradictory','verified')`,
`geo_candidates smallint[] NOT NULL DEFAULT '{}'`, `geo_reason text`, `geo_verified_by text`, `geo_verified_at`,
`claimed_room text` (`central` | `g:<code>`), `claimed_by text`, `claimed_by_name text`, `claimed_at`,
`sla_band text`, `sla_due_at timestamptz`, `escalation_state text NOT NULL DEFAULT 'none' CHECK IN ('none','late',
'central_responding','referred','referral_accepted','referral_refused')`, `escalated_at`, `referred_to smallint`.
Indexes: `(sla_due_at) WHERE claimed_room IS NULL AND status = 'received'`, `(escalation_state) WHERE
escalation_state <> 'none'`, `(geo_state) WHERE geo_state IN ('pending','contradictory')`.

`reports.escalation(id bigserial, report_id uuid FK CASCADE, incident_id uuid NULL, kind text CHECK IN ('late',
'central_claim','referral','referral_accepted','referral_refused','geo_verified','claim_released'), from_room text,
to_room text, actor text, actor_name text, at timestamptz DEFAULT now(), reason text)`.

`reports.reporter_context(report_id uuid PK FK CASCADE, reporter_gouvernorat_code smallint NULL, source text CHECK
IN ('profile','none'))` — copied from `identity.profile.gouvernorat_code` at creation for citizens/institutions,
`none` for anonymous. Restricted: read only through §1.3; RLS (§9); never used for scope.

### 4.2 Location assessment (replaces the direct use of `locate_gouvernorat`)

`reports/geo.py: async def assess(session, lat, lon, accuracy_m, source) -> Assessment(state, gouvernorat_code,
candidates, reason)`:
* `trusted`: the point is inside gouvernorat G **and** the accuracy circle (radius `accuracy_m`) intersects no other
  gouvernorat **and** `accuracy_m ≤ geo.max_trusted_accuracy_m`; `accuracy_m = null` counts as trusted only for
  `source = portal` (point picked on a map). → `gouvernorat_code = G`.
* `contradictory`: inside G but the accuracy circle crosses into H (candidates `[G, H, …]`), reason
  `accuracy_crosses_border`.
* `pending`: offshore/outside (candidates = nearest within 25 km, phase 2 rule), accuracy above the threshold, or
  app report without accuracy; reasons `outside_boundaries`, `low_accuracy`, `accuracy_missing`.
* `pending`/`contradictory` → `gouvernorat_code = NULL` (no automatic final assignment). The tracking code keeps
  the phase 2 format (`00` when outside, else the point's gouvernorat) — unchanged, not a jurisdiction.

Report creation sets `sla_band`, `sla_due_at = received_at + claim_delay_s[band]` from the baseline priority;
when the priority changes before a claim (AI pipeline rescore), band and due time are recomputed from `received_at`
(never earlier than now + 5 s).

### 4.3 Claim

* `POST /api/v1/staff/reports/{id}/claim` `{}` → `StaffReportDetail`. Allowed per §1.2 (regional room of
  `gouvernorat_code`; a candidate room for a critical geo-pending report; central only when late, geo-pending or
  the incident is at central command level). Same room again → 200 (idempotent). Other room holds it →
  `409 already_claimed` with `{"detail","claimed_room","claimed_by_name"}`. Audited `report.claim`; event
  `report.claimed`.
* A status change (`POST /staff/reports/{id}/status`, phase 2) on an unclaimed report claims it implicitly for the
  caller's room when the caller may claim; otherwise `409 claim_required`. A report claimed by another room →
  `409 already_claimed`.
* `DELETE /api/v1/staff/reports/{id}/claim` `{"reason"}` (ops_manager of the claiming room, or national) → releases;
  escalation row `claim_released`; the SLA clock does not restart.
* `first_response_at` and the KPI `avg_first_response_s` keep their phase 2 meaning; `claimed_at` is new.

### 4.4 SLA, late list and central response

* Worker loop `sla-escalation` (W1; `WORKER_LOOPS` gains it; every 5 s, `FOR UPDATE SKIP LOCKED`, batch 200):
  reports with `status = 'received'`, `claimed_room IS NULL`, `escalation_state = 'none'`, `sla_due_at <= now()`,
  `received_at >= sla.enforced_since` → `escalation_state = 'late'`, `escalated_at`, escalation row `late`
  (actor `system:sla`), timeline entry on the incident when linked (§5.5), event `report.late`.
* `GET /api/v1/staff/reports/late?cursor=&limit=&gouvernorat=` (national read roles) → `StaffReportPage` of reports
  with `escalation_state IN ('late','central_responding','referred','referral_refused')`, oldest `sla_due_at` first.
  Regional rooms see their own late reports in the normal list (`late: true` in `StaffReport`).
* Central response: a national operator/ops_manager claims a late report (`claimed_room = central`,
  `escalation_state = central_responding`, row `central_claim`) and may then change its status (e.g. `in_progress`,
  which notifies the citizen as in phase 2), link it to an incident and add notes. Central **cannot** create
  assignments, call-outs or dispatch on regional resources (`403 field_action_regional_only`, §5); it may request
  resources (§5.4).
* `POST /api/v1/staff/reports/{id}/refer` `{"to_gouvernorat_code", "reason", "directive": {"title","body",
  "urgency"} | null}` (national ops_manager/operator/central_committee) → `escalation_state = referred`,
  `referred_to`, row `referral`; when `directive` is given, a phase 5 directive is issued to that gouvernorat
  (`issuer_scope = NULL`) and its id stored in the escalation reason payload. `409 referral_pending` if one is open.
* `POST /api/v1/staff/reports/{id}/referral/accept` `{"note"}` / `…/referral/refuse` `{"reason"}` (target room,
  §1.2) → `referral_accepted` (claim moves to `g:<code>`) or `referral_refused` (stays on the late list, central
  must act). `409 referral_not_pending`. Every step: escalation row with actor, time, reason; audited; event
  `report.escalation`.

### 4.5 Geo-verification queue

* `GET /api/v1/staff/reports/geo-queue?cursor=&limit=` (national read roles) → open reports (not closed/rejected)
  with `geo_state IN ('pending','contradictory')`, critical first, then `received_at`.
* `POST /api/v1/staff/reports/{id}/geo-verify` `{"gouvernorat_code", "reason"}` (national operations/command) →
  `geo_state = verified`, `gouvernorat_code` set, row `geo_verified`; when a candidate room had already claimed it
  and the verified code differs, a `referral` to the verified room is recorded automatically (actor = verifier).
  `409 geo_not_pending`, `422 invalid_gouvernorat`.
* Critical reports in the queue are pushed live to their candidate rooms too (read + claim, §1.2) so they are not
  delayed; non-critical ones are national-only until verified.

### 4.6 Responses

`StaffReport` gains `geo_state`, `geo_candidates`, `claimed_room`, `claimed_by_name`, `claimed_at`, `sla_band`,
`sla_due_at`, `escalation_state`, `late` (bool). `StaffReportDetail` gains `escalations: [{"kind","from_room",
"to_room","actor_name","at","reason"}]`, `reporter_context: {"reporter_gouvernorat_code","source"} | null`, and the
masked `reporter` of §1.3. `GET /staff/reports` gains filters `geo_state=`, `escalation_state=`, `claimed=true|false`,
`sla_band=`. Report reads use the §1.2 scope (lead, participants of its incident, critical candidates, grants).

Errors: `409 claim_required`, `409 already_claimed`, `403 not_claimable`, `409 referral_pending`,
`409 referral_not_pending`, `409 geo_not_pending`, `422 invalid_gouvernorat`, `403 field_action_regional_only`.

Events (outbox, W1 emits, W2 routes in `live.py`): `report.claimed`, `report.late`, `report.escalation`
(refer/accept/refuse/release/geo_verified), plus `report.created`/`report.status_changed` payloads gain the §4.6
fields and `"gouvernorat_codes"` (lead + incident participants + critical candidates).

**Tests required** (`tests/test_jurisdiction.py`, `tests/test_sla.py`, W1): assessment cases (inside, crossing
circle, offshore, low accuracy, missing accuracy app vs portal); NULL gouvernorat for pending; reporter in Sfax
reporting a point in Gabès → Gabès handles, `reporter_context` = Sfax, Sfax room 404; claim idempotent / conflict /
implicit on status; worker marks late at 60 s for critical and 180 s for low (frozen clock), not before, not for
claimed or pre-`enforced_since` reports; delay change in settings applies to new reports; central claim allowed only
when late; central assignment refused; refer → accept/refuse; geo-verify with automatic referral; critical pending
visible to candidates only; all steps listed in `escalations` with actor/time/reason.

---

## 5. Incidents across gouvernorats (`modules/ops`) — owner W2, migration `0021_ops_multi_gouvernorat`

### 5.1 Schema

* `ops.incident.gouvernorat_code` **now means the lead gouvernorat** and is no longer recomputed from member reports
  (the majority rule of phase 3 is removed). New columns: `lead_set_by text`, `lead_set_at`, `command_level text NOT
  NULL DEFAULT 'regional' CHECK IN ('regional','central')`, `command_level_reason text`, `command_level_manual bool
  NOT NULL DEFAULT false`.
* `ops.incident_gouvernorat(incident_id FK CASCADE, gouvernorat_code FK, role text CHECK IN ('lead',
  'participating'), added_at, added_by, reason, PRIMARY KEY (incident_id, gouvernorat_code))`; exactly one `lead`
  row per incident with a lead (partial unique index), kept in sync with `incident.gouvernorat_code`.
* `ops.resource_request(id uuid PK, incident_id FK, from_room text, to_gouvernorat_code smallint, resource_id uuid
  NULL, resource_kind text NULL, quantity smallint DEFAULT 1, reason text, status text CHECK IN ('pending',
  'approved','refused','cancelled'), requested_by, requested_by_name, requested_at, decided_by, decided_by_name,
  decided_at, decision_note)`; `ops.assignment.request_id uuid NULL FK`.

### 5.2 Lead and participants

* Incident creation (`action: new`): lead = the report's `gouvernorat_code`; a report with `geo_state` pending or
  contradictory may only be grouped by national staff (lead NULL until verified, `command_level = central`).
* Linking a report of gouvernorat H into an incident led by G (manual link, suggestion accepted, or automatic
  disaster grouping) adds H as `participating` (timeline `participant_added`, reason `report_linked`). A regional
  operator of H may link into G's incident when it is returned by `GET /api/v1/staff/reports/{id}/nearby-incidents`
  (open incidents of a compatible category within the AI grouping radius/window of the report, any gouvernorat;
  summary only: id, category, lead, participants, centroid, severity, opened_at, report_count — no reporter data) or
  is the AI suggestion. This replaces the phase 3 `404` on cross-border suggestions.
* `POST /api/v1/staff/incidents/{id}/participants` `{"gouvernorat_code","reason"}`; `DELETE …/participants/{code}`
  `{"reason"}` (refused `409 participant_active` while that gouvernorat has active assignments or member reports).
* `POST /api/v1/staff/incidents/{id}/lead` `{"gouvernorat_code","reason"}` (national ops_manager/central_committee)
  → the old lead becomes participating. `422 invalid_gouvernorat`.
* Duplicate guard: `action: new` returns `409 possible_duplicate` `{"detail","incident_ids":[…]}` when an open
  incident of a compatible category exists within the grouping radius/window in any gouvernorat, unless the body
  carries `"override_reason"` (5–500 chars, audited, timeline `duplicate_override`).
* Merge across leads: national only (`403 action_not_allowed` otherwise); the source's lead and participants become
  participants of the target.

### 5.3 Command level

Automatic (on every refresh): `central` when severity ≥ `sla.bands.critical`, or the incident has ≥ 1 participating
gouvernorat, or the lead's operational level is `crisis`/`disaster`; else `regional`; not changed while
`command_level_manual`. `POST /api/v1/staff/incidents/{id}/command-level` `{"level","reason"}` (national
ops_manager/central_committee) sets it manually; `{"level": null, …}` returns to automatic. Timeline
`command_level_changed`. Effect: §1.2 (central may claim member reports and decide resource requests).

### 5.4 Resources across gouvernorats

* `POST /api/v1/staff/incidents/{id}/assignments` (phase 5): the resource's unit must be in the caller's own
  gouvernorat and that gouvernorat must be lead or participating; national callers → `403
  field_action_regional_only`; a resource of another gouvernorat → `403 resource_not_owned` (use a request).
  Call-outs: volunteers of the caller's own gouvernorat only (unchanged), national → `403 field_action_regional_only`.
* `POST /api/v1/staff/incidents/{id}/resource-requests` `{"to_gouvernorat_code","resource_id"|null,
  "resource_kind"|null,"quantity","reason"}` → `201` request; `GET /api/v1/staff/resource-requests?status=&
  direction=incoming|outgoing&cursor=`; `GET …/{id}`.
* `POST /api/v1/staff/resource-requests/{id}/approve` `{"resource_ids":[…],"note"}` (owning region ops_manager or
  local_committee; or national central_committee when the incident's `command_level = central`) → creates one
  assignment per resource (`status = ordered`, `request_id`), adds the owning gouvernorat as participating.
  `409 request_not_pending`, `409 resource_busy`, `403 resource_not_owned`.
* `POST …/{id}/refuse` `{"reason"}`; `POST …/{id}/cancel` (requester). Every step: timeline entry (actor, time,
  reason), audit, event `resource_request.updated`. Assignment status changes stay with the owning region.

### 5.5 Timeline

Public helper `ops.service.add_timeline(session, incident_id, kind, actor, actor_name=None, **payload)` (W2) used by
W1 for report escalations. New kinds: `participant_added`, `participant_removed`, `lead_transferred`,
`command_level_changed`, `duplicate_override`, `resource_requested`, `resource_request_approved`,
`resource_request_refused`, `resource_request_cancelled`, `report_late`, `report_central_claim`, `report_referred`,
`report_referral_accepted`, `report_referral_refused`, `report_geo_verified`. Every entry has `actor`, `at`,
`payload.reason` when a reason exists. `IncidentSummary` gains `lead_gouvernorat_code` (= `gouvernorat_code`),
`participating_gouvernorats`, `command_level`; `IncidentDetail` gains `resource_requests`.

### 5.6 Live, analytics, knowledge, telephony (W2)

* `reports/live.py` (owned by W2): every report/incident/assignment/callout/resource-request event carries
  `gouvernorat_codes`; routing uses "national or own code in `gouvernorat_codes`" (empty = national only);
  `report.late` → national + the report's room; `report.escalation` → national + from/to rooms;
  `settings.changed` → all staff; `breakglass.*` → security admins + the requester. Unlocated **ringing** calls stay
  in the shared queue; once ended, an unlocated call is national-only (and the operator who took it).
* Analytics (phase 8): incidents are attributed to their lead; a regional query includes incidents where the region
  participates (`"participating": true` breakdown); reports stay attributed to `gouvernorat_code`, unverified ones
  under `"unverified"` (national only). Leaderboard `scope=national` requires national scope.
* Knowledge: incident documents and memory pre-fill use lead + participants as `gouvernorats`.
* Committee performance: incidents by lead; participations counted separately.
* Notifications (phase 5) scope leaks closed (W2 owns `modules/notify`): `audience = user` requires the target's
  profile gouvernorat in scope (national: any); `POST /staff/users/lookup` returns `404 not_found` for out-of-scope
  accounts; polygon messages are visible to editors whose gouvernorat the polygon intersects (not all editors).

**Tests required** (W2: `tests/test_cross_border.py`, updates to `test_incidents.py`, `test_operations.py`,
`test_live.py`, `test_analytics.py`, `test_notifications.py`, `test_telephony.py`, `test_knowledge.py`): border fire
Kasserine/Sidi Bouzid → one incident, lead Kasserine, Sidi Bouzid participating, both rooms read it; second "new"
from Sidi Bouzid → `409 possible_duplicate`; lead never flips when the other side has more reports; national
assignment refused; request → approve creates assignment and participation; refuse recorded; central command
approves when central level; live payload codes; analytics participating breakdown; notify user-audience and lookup
out of scope refused.

---

## 6. Break-glass and regional account administration (`modules/access`, new) — owner W2, migration `0022_access_break_glass`

### 6.1 Break-glass

`access.break_glass_grant(id uuid PK, subject text, subject_name text, target_kind text CHECK IN ('report',
'incident','gouvernorat'), target_id uuid NULL, gouvernorat_code smallint NULL, justification text CHECK
(char_length BETWEEN 20 AND 1000), granted_at, expires_at, revoked_at, revoked_by, reviewed_by, reviewed_at,
review_outcome text CHECK IN ('justified','unjustified') NULL, review_note)`.

* `POST /api/v1/staff/break-glass` `{"target_kind","target_id"|null,"gouvernorat_code"|null,"justification",
  "duration_min"}` (15–240, default 60; roles §1.2) → `201` grant, active at once. Read-only: the grant extends
  `report.read`, `incident.read` and `report.read_sensitive` on its target; it never allows writes or commands.
  `422 breakglass_justification_required`, `422 invalid_target`. Audited `breakglass.grant`; event
  `breakglass.granted`.
* `GET /api/v1/staff/break-glass?status=active|expired|pending_review|reviewed&cursor=` (security_admin national: all;
  others: their own). `POST …/{id}/revoke` (holder or security_admin). `POST …/{id}/review`
  `{"outcome","note"}` (security_admin national, not the holder: `403 breakglass_self_review`; `409 already_reviewed`).
* Worker loop `breakglass` (W2): expires grants (`expires_at`), emits `breakglass.review_overdue` for grants
  unreviewed 72 h after expiry.
* Every request made under a grant is audited with `details.grant_id`.

### 6.2 Regional account administration (Keycloak admin proxy)

Settings (W1 adds to `core/config.py`, W2 uses): `KEYCLOAK_ADMIN_URL`, `KEYCLOAK_ADMIN_CLIENT_ID`,
`KEYCLOAK_ADMIN_CLIENT_SECRET` (secret), realm `ehimaya-staff`. W2 adds a confidential client
`ehimaya-account-admin` with a service account holding `realm-management: manage-users, view-users` to the realm
export (secret from env), plus the three new roles and locale `en`.

* `GET /api/v1/staff/accounts?gouvernorat=&role=&q=&cursor=` → `{"items":[{"id","username","email",
  "first_name","last_name","enabled","roles","scope_level","gouvernorat_code","mfa_configured"}]}`.
* `POST /api/v1/staff/accounts` `{"username","email","first_name","last_name","roles":[…],
  "scope_level":"gouvernorat"|"national","gouvernorat_code"|null}` → `201`; required actions `CONFIGURE_TOTP`,
  `UPDATE_PASSWORD`, `VERIFY_EMAIL`.
* `PATCH /api/v1/staff/accounts/{id}` `{"roles"?, "enabled"?}`; `POST …/{id}/reset-credentials`.
* Rules: `regional_account_admin` with gouvernorat g sees and edits only accounts with `gouvernorat_code = g`
  (others `404 not_found`); `scope_level`/`gouvernorat_code` forced to g (`403 out_of_scope` for anything else);
  grantable roles: operator, ops_manager, field_commander, local_committee, content_editor (others `403
  role_not_grantable`). A national `regional_account_admin` may manage all gouvernorats and also grant
  central_committee and org_auditor; technical roles only by `security_admin` (national). Nobody edits their own
  account (`403 self_edit`). Audited `account.create|update|reset` in `access.account_admin_log` and the audit log
  with `gouvernorats = [g]`. Keycloak errors → `502 identity_provider_error`, conflicts → `409 username_taken`.

**Tests required** (W2: `tests/test_break_glass.py`, `tests/test_accounts.py` with a fake admin client): grant
lifecycle, read reveal, write still refused, expiry, self-review refused; regional admin cannot list/create/patch an
account of another gouvernorat even by editing `gouvernorat_code` in the body or the id in the path (IDOR); role
grant limits; national admin limits.

---

## 7. Audit and alerting (`modules/audit`, `modules/notify`) — owner W2

### 7.1 Recording

`audit.record(session, *, actor, action, target=None, reason=None, details=None, gouvernorats: list[int] | None =
None)` — new keyword (W2 changes the signature first; W1 and W2 pass it on report/incident/settings actions).
Stored as `details["gouvernorats"]` (inside the hash chain). Omitted = national-only entry.

### 7.2 Schema (`0023_audit_scope`)

Immutable SQL function `audit.scope_of(jsonb) RETURNS smallint[]` and `ALTER TABLE audit.log ADD COLUMN
gouvernorats smallint[] GENERATED ALWAYS AS (audit.scope_of(details)) STORED` + GIN index. `audit.entry_hash`,
the chain trigger and the append-only triggers are not modified; `verify_chain` keeps passing on old rows.

### 7.3 Reading

* `GET /api/v1/admin/audit` (raw, phase 1): roles become `security_admin` national (sysadmin removed);
  `GET /api/v1/admin/audit/verify`: `security_admin`, `sysadmin`.
* `GET /api/v1/staff/audit?action=&from=&to=&cursor=` (`audit.read_scoped`, §1.2) → own-gouvernorat entries only
  (`gouvernorats` contains the caller's code), redacted: `actor` replaced by `actor_name` (or `"system"`),
  `details` reduced to the whitelist `{action-specific ids, from, to, status, outcome, kind}`, `reason` kept only for
  escalation/referral/break-glass/settings actions; no `hash`. Reading is audited `audit.read_scoped`.

### 7.4 Real sending stays off

No provider is enabled by this phase. `notify.real_send_enabled` (§2) is read by the notify delivery loop together
with the existing provider configuration: when `false`, alert dispatches go only to the simulation/in-app channels
as today. Government integrations: none added. Production settings check refuses `NOTIFY_REAL_SEND=true` without
`NOTIFY_REAL_SEND_APPROVAL_REF` (W1 adds both settings).

**Tests required** (W2, `tests/test_audit.py` update + `tests/test_audit_scoped.py`): chain intact after migration;
scoped view shows own gouvernorat only, redacted; operator refused; sysadmin refused raw list; real send flag not
writable.

---

## 8. English (`apps/dashboard`, API labels) — W3 (dashboard), W2 (API), migration `0024_i18n_english`

* Dashboard: `src/i18n/en.json` with the same 2,249 keys; `LANGUAGES = ["ar","fr","en"]`; language menu with three
  entries (replaces the ar↔fr toggle); `INTL_LOCALE.en = "en-GB-u-nu-latn"`; every `lang === "ar" ? … : …` and
  `{ar,fr}` helper (`lib/localized.ts`, `lib/forecast.ts`, `lib/hooks.ts`, review §7 list) becomes a lookup with
  fallback `en → fr → ar` for API text pairs; codes translated through i18n keys only.
* Original texts: the report list/detail keep showing `text` (original) first and `text_ar` labelled as a machine
  translation; no English machine translation is requested or shown.
* API (W2): `ReportLang = Literal["ar","fr","en"]` for analytics documents and schedules; all analytics label
  tables become `{ar,fr,en}`; PDF `lang="en" dir="ltr"`, XLSX left-to-right; gouvernorat names from
  `geo.gouvernorat.name_en` (seeded = French names without diacritics where usual, e.g. "Gabes", "Beja"); decision,
  forecast and scenario fixed labels gain `en`; free texts without `en` fall back to `fr`.
  Migration: `ck_schedule_lang`, `ck_report_lang` (analytics) accept `en`; `geo.gouvernorat.name_en` NOT NULL after
  seed. `GET /api/v1/geo/gouvernorats?lang=en` uses it.
* Exports follow the user: the dashboard sends the current UI language as default `lang` for new library documents
  and schedules; the document keeps its language.
* Keycloak staff realm `supportedLocales` gains `en` (W2).

**Tests required**: dashboard `i18n.test.ts` key parity and placeholders across ar/fr/en, direction (`en` = ltr),
contract coverage of all new codes (W3); API document generation in `en` (W2).

---

## 9. Row-level security and backfill — owner W4 (RLS), W1/W2 (backfills in their migrations)

### 9.1 Session scope (W4: `core/db.py`)

* GUCs set **per transaction** by an `after_begin` listener: `SELECT set_config('ehimaya.scope', :scope, true),
  set_config('ehimaya.gouvernorat', :g, true), set_config('ehimaya.subject', :sub, true)`.
* Values come from a contextvar `core.access.db_scope` (W1 sets it in `get_principal`/`require_roles` for staff:
  `national` or `gouvernorat`; in `get_reporter` for reporters: `public` + user id). W4 reads it.
* Unset contextvar in an HTTP request → `none` → policies return no rows (fail closed).
* `core/db.py` gains `get_system_sessionmaker()` (scope `system`); W1 changes `main.py` to start every worker loop
  with it; CLIs (`*/cli.py`) and internal hook routers (`streams/internal.py`, `telephony/internal.py`) use
  `system` explicitly; public `/reports/track` uses a `system` session for its single lookup (W1).

### 9.2 Policies (`0025_rls_policies`)

Function `ehimaya.can_see(lead smallint, incident uuid) RETURNS bool STABLE` = scope `system`/`national`, or scope
`gouvernorat` and (lead = GUC, or the GUC gouvernorat participates in `incident`, or an unexpired break-glass grant
of `ehimaya.subject` covers it). Policies (`ENABLE` + `FORCE` is **not** used; the owner role keeps migrating):
* `reports.report`: SELECT/UPDATE `can_see(gouvernorat_code, incident_id)` or critical candidate rule or (scope
  `public` and `user_id = subject`); INSERT for `public`/`system`/staff.
* `reports.media`, `reports.status_history`, `reports.escalation`: via their report.
* `reports.reporter_context`: SELECT only `system` or staff scopes passing `can_see` (the sensitive-field rule stays
  in the API; the DB only blocks other gouvernorats).
* `ops.incident`, `ops.timeline_event`, `ops.assignment`, `ops.callout`, `ops.resource_request`: via the incident
  (resource requests also visible to `to_gouvernorat_code`).
* `ops.unit`, `ops.resource`: own gouvernorat (+ national/system); SELECT also for resources assigned to an incident
  the caller can see.
* `telephony.call`, `reports.live_stream`: their `gouvernorat_code` (NULL: national/system, and ringing calls).
* `audit.log`: SELECT `system`/`national` or `gouvernorat = ANY(gouvernorats)`; INSERT unrestricted (append).
* `access.break_glass_grant`: subject's own rows, national security admins via `national`.
Grants re-applied by `core/db_roles.py` after migration (unchanged mechanism). Runtime role stays `NOBYPASSRLS`.

### 9.3 Rollout

1. W1/W2/W3 code merged first (API enforces scope); 2. `0025` applied last; 3. `RLS_ENFORCED` is not a flag —
the downgrade of `0025` (`DISABLE ROW LEVEL SECURITY`) is the rollback. A staging run with every worker loop and
the smoke test (`infra/smoke`) must pass before production.

### 9.4 Backfill of existing data

* `0020`: `geo_state = 'trusted'` where `gouvernorat_code IS NOT NULL`, else `'pending'` (candidates = nearest
  within 25 km); closed/rejected NULL reports keep `'pending'` but the queue only lists open statuses. Reports past `received`: `claimed_room = 'g:<gouvernorat_code>'` (or `central` when NULL),
  `claimed_by` = first non-reporter actor of `status_history`, `claimed_at = first_response_at`. `sla_band` and
  `sla_due_at` computed; `escalation_state = 'none'`; no retro-escalation (`sla.enforced_since`).
  `reporter_context` from `identity.profile` for non-anonymised, non-anonymous reports; `none` otherwise.
* `0021`: `incident_gouvernorat` lead row from `gouvernorat_code`; participating rows from distinct member report
  gouvernorats ≠ lead; `command_level` computed by §5.3; incidents with NULL `gouvernorat_code` keep lead NULL,
  `command_level = central` (national only).
* `0019`: counters from existing anonymous reports (§3). `0023`: old audit rows national-only.

**Tests required** (W4: `tests/test_rls.py`, `test_db_roles.py` update): with the runtime role and scope
`gouvernorat=31`, raw SQL on each table returns only allowed rows; unset scope returns nothing; `system` sees all;
participant and break-glass visibility; INSERT into `audit.log` still works and UPDATE still fails; worker loops run
under `system`; migration upgrade/downgrade round trip with backfill assertions.

---

## 10. Changes to earlier contracts

| Contract | Old rule | New rule |
|---|---|---|
| Phase 2.5 (A1) | A report is never refused for abuse-control reasons (only 429 windows) | **Exception**: anonymous non-SOS reports beyond `anonymous.report_quota` → `403 anon_quota_exhausted`; SOS accepted and flagged |
| Phase 2.5 | Rate-limit windows checked before the replay lookup | Replays of a known `client_uuid` consume nothing |
| Phase 2 | Staff read a report iff its `gouvernorat_code` is in scope | §1.2 scope (lead, incident participants, critical candidates, grants); NULL = national only |
| Phase 2 | `gouvernorat_code` = point-in-polygon or nearest within 25 km | Only when the location is trusted (§4.2); otherwise NULL + geo-verification queue |
| Phase 2 | Report detail returns reporter name/phone to every read role | Masked except handling operations room or break-glass (§1.3) |
| Phase 2 | Any write role in scope may change a report status | Requires a claim by the caller's room (implicit claim when allowed) |
| Phase 3 | AI suggestion to an incident outside scope → 404 | Linking adds the caller's gouvernorat as participant |
| Phase 3 | Disaster-level auto-grouping attaches without scope | Still automatic, adds participants, timeline `participant_added` |
| Phase 3 | AI settings `PUT`: central_committee or sysadmin (national) | central_committee or `ai_admin` (national) |
| Phase 5 | Incident `gouvernorat_code` = majority of member reports | Fixed lead; changed only by `POST …/lead` |
| Phase 5 | Merge needs both incidents in the caller's scope; one gouvernorat remains | Cross-lead merge national only; others become participants |
| Phase 5 | National staff may assign any resource | National cannot dispatch (`field_action_regional_only`); requests + approval |
| Phase 5 | Units/resources CRUD: ops_manager, sysadmin | ops_manager of the unit's gouvernorat (national ops_manager: all); sysadmin removed |
| Phase 5 | Committees read-only on incidents | Command family decides participants, lead (national), command level, resource requests |
| Phase 5 | Notify user-audience messages and user lookup not scoped | Scoped by the target's profile gouvernorat (§5.6) |
| Phase 5 | Polygon notifications broadcast to every editor | Only editors whose gouvernorat intersects |
| Phase 6 | Stream source registration: ops_manager, sysadmin | ops_manager only |
| Phase 7 | Unlocated calls visible to every operator | Ringing: shared queue; ended: national + taker |
| Phase 8 | Reward rules write: central_committee or sysadmin | central_committee only |
| Phase 8 | Leaderboard `scope=national` (enforcement missing in code) | National scope required (`403 out_of_scope`) |
| Phase 8 | Analytics/library languages ar/fr | ar/fr/en; default = user's UI language |
| Phase 8 | Incidents counted by their single gouvernorat | By lead, with participating breakdown |
| Phase 1 | Audit list: sysadmin | `security_admin` (raw); scoped redacted view for regional managers |
| Phase 1 | Staff roles: 8 | 11 (security_admin, ai_admin, regional_account_admin) |

---

## 11. Work split and file ownership

No two workers edit the same file; when a worker needs a change in another worker's file it asks the owner.

| Worker | Owns (create/edit) |
|---|---|
| **W1** API access/settings/quota/reports | `core/security.py`, `core/access.py` (new), `core/config.py`, `app/main.py`; `modules/settings/**` (new); `modules/identity/**`; `modules/reports/**` **except `live.py`**; `modules/ai/router.py`; `modules/rewards/staff_router.py`, `modules/streams/staff_router.py`, `modules/weather/staff_router.py` (re-gating only); `migrations/versions/0018_*`, `0019_*`, `0020_*`; tests `conftest.py`, `test_access.py`, `test_settings.py`, `test_anon_quota.py`, `test_jurisdiction.py`, `test_sla.py`, updates to `test_auth.py`, `test_staff.py`, `test_reports.py`, `test_hardening.py`, `test_ai.py`, `test_rewards.py`, `test_streams.py`, `test_weather.py`; privacy register note for §3 |
| **W2** API ops/access/audit/live | `modules/ops/**`, `modules/reports/live.py`, `modules/analytics/**`, `modules/knowledge/**`, `modules/audit/**`, `modules/notify/**`, `modules/telephony/service.py`, `modules/decision/domain.py`, `modules/forecast/service.py`, `modules/geo/**`, `modules/access/**` (new: grants, break-glass, accounts); `infra/keycloak/realms/*.json`; `migrations/versions/0021_*`–`0024_*`; tests `test_cross_border.py`, `test_break_glass.py`, `test_accounts.py`, `test_audit_scoped.py`, updates to `test_incidents.py`, `test_operations.py`, `test_live.py`, `test_analytics.py`, `test_audit.py`, `test_knowledge.py`, `test_notifications.py`, `test_telephony.py`, `test_decision.py`, `test_forecast.py`, `test_geo.py`; helper `tests/scopehelpers.py` |
| **W3** dashboard | `apps/dashboard/**` |
| **W4** mobile + RLS | `apps/mobile/**`; `core/db.py`, `core/db_roles.py`; `infra/postgres/**`; `migrations/versions/0025_*`; tests `test_rls.py`, `test_db_roles.py` |

Cross-worker interfaces (frozen by this contract): `core.access.authorize/Ctx/Action/db_scope` (W1) ·
`modules.access.grants.active_grants` (W2) · `ops.service.add_timeline`, `ops.service.incident_gouvernorats(session,
incident_id) -> (lead, frozenset)` (W2) · `audit.record(..., gouvernorats=)` (W2) · `settings.get` (W1) ·
`db.get_system_sessionmaker` (W4) · routers `app.modules.settings.router.router`, `app.modules.access.router.router`,
`app.modules.access.accounts.router` registered by W1 in `main.py`; worker loops `sla-escalation` (W1) and
`breakglass` (W2, function `modules.access.worker.breakglass_forever`) registered by W1.

Dashboard (W3) scope: language menu + `en.json`; settings page `/settings` (SLA delays per band, bands, anonymous
quota, geo accuracy; editable only when `editable`); late list `/reports/late` with countdown; claim / release
buttons and "claimed by" badge; referral dialog and accept/refuse in the regional room; geo-verification queue
`/reports/geo-queue` with candidate map; masked reporter rendering and break-glass dialog (justification, duration)
with an active-grant banner; incident lead/participants panel, command level, nearby-incidents duplicate warning,
resource requests (incoming/outgoing); accounts page `/accounts` (regional admin); scoped audit view `/audit`;
security admin break-glass review page; tests per page (`*.test.tsx`).

Mobile (W4): `ApiErrorCode.anonQuotaExhausted('anon_quota_exhausted')`; sync engine maps it to `ReportState.blocked`
(kept, resent after registration like `anon_blocked`); store `X-Anon-Quota-Remaining` after each accepted report;
quota card on home and report screen ("N of 5 left"); quota screen with explanation, "create an account" and a
**call 198** button; before queuing a non-SOS anonymous report with remaining = 0 the app shows the quota screen
and keeps the draft (state `blocked`); SOS is never gated client-side; `GET /reports/quota` on start when online;
strings ar/fr/en. Tests: `sync_engine_test.dart` (403 → blocked, resent after login), quota widget tests, SOS path.

---

## 12. Acceptance

| # | Criterion | Test(s) |
|---|---|---|
| 1 | Anonymous quota: 5 accepted, then registration required; replays not counted | `test_anon_quota.py::test_five_then_refused`, `::test_replay_not_counted`, `::test_concurrent_replay_counts_once` |
| 2 | 198 always available | mobile `quota_screen_test.dart::shows_call_198`, `rewards`/`sms_fallback` tests unchanged; `test_anon_quota.py::test_sos_beyond_quota_accepted_flagged` |
| 3 | Draft kept when quota reached | `sync_engine_test.dart::quota_exhausted_keeps_report_blocked_and_resends_after_login` |
| 4 | Dashboard in 3 languages | `i18n.test.ts` parity ar/fr/en, `Layout.test.tsx::language_menu`, API `test_analytics.py::test_document_in_english` |
| 5 | Scope per account | `test_access.py` matrix; `test_auth.py` scope claims |
| 6 | Jurisdiction = incident location | `test_jurisdiction.py::test_reporter_elsewhere_location_decides` |
| 7 | Geo-verification queue | `test_jurisdiction.py::test_pending_goes_to_queue`, `::test_geo_verify_refers`, `::test_critical_pending_visible_to_candidates` |
| 8 | Central sees all without unnecessary sensitive data | `test_access.py::test_national_reads_all_masked_reporter`, `test_audit_scoped.py` |
| 9 | Regional limits | `test_access.py::test_regional_404_other_gouvernorat` (reports, incidents, units, resources, calls, streams, volunteers, orgs, rewards) |
| 10 | Late escalation | `test_sla.py::test_late_after_band_delay`, `::test_settings_delay_applies`, `::test_central_claim_only_when_late` |
| 11 | Cross-border single incident, one lead | `test_cross_border.py::test_one_incident_one_lead`, `::test_possible_duplicate`, `::test_lead_does_not_flip` |
| 12 | Escalation timeline (actor, time, reason) | `test_sla.py::test_escalations_listed`, `test_cross_border.py::test_timeline_entries_have_actor_reason` |
| 13 | Read / edit / command separation | `test_access.py::test_technical_roles_no_ops`, `::test_committee_cannot_triage`, `test_cross_border.py::test_national_cannot_dispatch` |
| 14 | National settings central-only | `test_settings.py::test_regional_refused`, `test_ai.py` (ai_admin), `test_rewards.py` (rules) |
| 15 | Regional account admin own gouvernorat only | `test_accounts.py::test_idor_path_and_body`, `::test_role_grant_limits` |
| 16 | Sensitive data protection | `test_access.py::test_reporter_masked_unless_handling_room`, `test_break_glass.py::test_reveal_audited` |
| 17 | Scoped reports (analytics/library) | `test_analytics.py::test_overview_scope_filtering`, `::test_participating_breakdown`, `::test_leaderboard_national_refused` |
| 18 | Restricted operations refused | `test_cross_border.py::test_resource_not_owned`, `test_settings.py`, `test_audit.py::test_sysadmin_refused_raw` |
| 19 | Scope in API and DB, IDOR tests | `test_access.py::test_idor_*` (ids of other gouvernorats on every staff route, list param tampering), `test_rls.py` |
| 20 | Reporter location vs incident location | `test_jurisdiction.py::test_reporter_context_restricted`, `test_rls.py::test_reporter_context_other_gouvernorat` |

IDOR suite rule (W1 `test_access.py`, W2 adds its routes in `test_cross_border.py`): for every staff route taking an
id or a gouvernorat parameter, a regional token of another gouvernorat gets `404` (ids) or an empty/`403` result
(filters) and the database row is unchanged afterwards.
