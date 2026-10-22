# Phase 11 — Review before the pilot

Scope: the "pilot launch" half of the original phase 9 (requirements §11: "a trial in one gouvernorat"; NFR-03: "pilot
phase: one gouvernorat"; Q6: "the gouvernorat you choose"; architecture §11: Docker Compose on two servers, one
application server and one GPU server). Phases 9 and 10 are merged (`main` at 10b83a2).

This is a read-only review of `main`. Every claim cites `path:line` or a command that was run. API paths are relative
to `services/api/app/`. Nothing was changed. The redesign comes after the owner's decisions in §8.

The question this review answers: **what stops a real Civil Protection room in one gouvernorat from receiving real
citizens' reports through this system next month?** The answer is in three parts:

* **Code gaps** (§1–§4): changes the team can make.
* **Things only the owner and partners can provide** (§5): contracts, authorisations, validations.
* **What the pilot must measure** (§6).

---

## 1. The system has no notion of "the pilot area"

The platform is national from end to end. That is right for later, but wrong for a pilot in which only one
gouvernorat has a staffed room.

- **Every report in Tunisia is accepted and routed to its gouvernorat's room.** `locate_gouvernorat`
  (`modules/reports/service.py:67-81`) places any point in one of the 24 gouvernorats, and the report is created
  with that code (`service.py:227`).
  - There is no setting that says which gouvernorats are served: grep for `covered`, `service_area`,
    `active_gouvernorat` and `pilot` finds nothing in `app/`.
  - A citizen in a gouvernorat outside the pilot gets a tracking code and "received". Nobody in that gouvernorat is
    on the platform, so the report waits for its claim delay (60 to 180 s by band, `modules/reports/sla.py:1-7`,
    phase 9 contract §2). After that it goes to the central room.
- **The central room becomes the de facto room for 23 gouvernorats.** If central is not staffed during the pilot,
  those reports are lost in silence. Silence is the worst outcome for an emergency report.
- **The citizen is never told that their area is not covered yet.**
  - The app and the portal show no "pilot area" message.
  - The app shows 198 on the emergency numbers screen, around SOS, on the queued-report screen and on the
    anonymous-quota screen (`lib/features/emergency/emergency_numbers.dart`, `sos/sos_widgets.dart`,
    `report/report_queued_screen.dart`, `quota/quota_screen.dart`). None of these depends on where the report is.
  - In the pilot, the honest answer outside the area is "this service is not yet active here, call 198 now". It must
    come before the report is sent, not after.
- **Population alerts, volunteers and institutions are also national.** Alerts are already scoped by area polygon
  (`modules/notify/service.py:216-240`). Volunteer sign-up and institution files are not limited to the pilot
  gouvernorat, so citizens elsewhere can register for something that does not serve them.

**Needed:** a national setting with the list of served gouvernorats (one for the pilot), read by intake, the app,
the portal and sign-up. It must have a defined behaviour for reports from outside the area, which is a decision for
the owner (§8, D2). The redesign has to keep SOS from ever being refused, as decided in phase 9.

## 2. Inside the pilot gouvernorat: data the platform does not have yet

### 2.1 Délégations are listed but have no boundaries

- `geo.delegation.boundary` exists (`modules/geo/models.py:32`, GiST index in
  `migrations/versions/0001_core_schema.py:49`).
- No migration loads it: only gouvernorat boundaries are loaded (`0003_gouvernorat_boundaries.py:1`,
  `seed/geo/tn_gouvernorats.geojson`). `reports.report.delegation_id` is read (`modules/reports/service.py:332`)
  but never written.
- So every report in the pilot carries the gouvernorat and no délégation.
- The requirements give roles a scope of "national, gouvernorat, délégation" (requirements §3, RBAC paragraph). The
  code only knows `gouvernorat` and `national` (`modules/access/schemas.py:56`).
- Inside one gouvernorat, the délégation is how the room thinks: which advanced post, which local unit. Statistics
  per délégation (the analytics minimum cell applies) are also what the pilot report will need.

### 2.2 Units, vehicles and staff have to be typed one by one

- Units and resources can only be created one at a time, through `POST /api/v1/ops/units` and
  `POST /api/v1/ops/resources` (`modules/ops/command_router.py:100,166`).
- There is no import (CSV or other) and no seed for a real gouvernorat.
- A gouvernorat has a regional directorate, several units and advanced posts, and tens of vehicles. Typing them by
  hand before day one is slow and error-prone. Re-typing them after a rehearsal is worse.

### 2.3 A new staff account cannot sign in

- `create_account` (`modules/access/keycloak.py:157-181`) creates the Keycloak user with no password. Its required
  actions are `CONFIGURE_TOTP`, `UPDATE_PASSWORD` and `VERIFY_EMAIL` (`keycloak.py:22`).
- No e-mail is sent: the API never calls `execute-actions-email`, and neither realm has an `smtpServer`
  (`infra/keycloak/realms/*.json`).
- A user with no credential cannot reach the "update password" step. Today the only way in is for an administrator
  to set a temporary password in the Keycloak admin console. That is a manual step outside the audit trail, done
  once per operator.
- The same is true after `reset_credentials` (`keycloak.py:213-221`): the password is kept, but the required action
  `VERIFY_EMAIL` cannot be completed without e-mail.
- The very first national administrator also has to be created by hand in the Keycloak console. No documented
  bootstrap exists (grep for `bootstrap` finds nothing in `app/`).

### 2.4 Reference content written by us, not by the Civil Protection

- **Safety tips:** seeded by migration 0007 with the comment "Their wording must be validated by the Protection
  Civile before the pilot" (`migrations/versions/0007_operations.py:334`).
- **Procedure library:** `docs/procedures/*.ar.md` and `*.fr.md` (fire, flood, drowning, building collapse,
  chemical leak…) feed the incident assistant.
- Neither has a record of validation. These texts reach citizens and operators in an emergency, so they need a
  named validator and a date.

## 3. Deployment for the pilot

### 3.1 The documented deployment is one server; the architecture says two

- `docs/deploy-production.md` describes one host running `compose.yml` + `compose.prod.yml`.
- `infra/compose.gpu.yml:1-3` runs the AI layer with a GPU on the same command line, so on the same host.
- Architecture §11 plans an application server (16 cores, 64 GB) plus a GPU server (24 GB VRAM). No document or
  compose file describes the split:
  - how the API on one host reaches `ai`, `ollama` and `vision` on the other;
  - with which TLS, which token, and which firewall rule.
- In `compose.prod.yml` the AI, assistant and vision URLs stay empty by default (`infra/compose.yml:254`;
  `OLLAMA_URL`, `VISION_SERVICE_URL` in `.env.example`). Without a written procedure, the pilot either runs with no
  AI at all or with a hand-made link nobody reviewed.

### 3.2 The checks that need Docker have never run on a release candidate

- **Not run in phase 10:** image builds, Trivy, Keycloak 26.8 with `check_mfa.py`, and the full stack smoke test
  (phase 10 report, §3 and acceptance criteria 2 and 16). Docker was not available to us.
- **No continuous integration at all:** GitHub Actions does not run on the private repository (phase 10 review §1).
  `docs/self-hosted-runner.md` describes a runner that does not exist yet.
- **Before a pilot:**
  - one full green run of every job on the exact commit that will be deployed;
  - a ZAP scan of the staging stack (`infra/security/zap/run.sh`, not run yet, `docs/security/asvs-l2.md:25`);
  - a restore drill on a real backup of the staging server (`docs/runbooks/backup-restore.md`, quarterly drill).

### 3.3 External services used "as in development"

| Service | Today | For a pilot with real users |
|---|---|---|
| Map tiles | `tile.openstreetmap.org` in the app (`apps/mobile/lib/core/config/app_config.dart:39`) and dashboard (`apps/dashboard/src/lib/mapStyle.ts:10`) | The OSM tile usage policy does not allow an app's production traffic. Needs a tile provider or a self-hosted tile server (`MAP_STYLE_URL`, already supported) |
| Weather | Open-Meteo free API (`.env.example:209-215`) | Free tier is non-commercial; use a key or self-host, as the comment already says |
| Routing | Empty `ROUTING_URL` gives straight-line estimates (`infra/compose.yml:299`) | Enable the `routing` profile with the Tunisia extract |
| Push | FCM | Personal-data transfer outside Tunisia (DPIA R7): needs INPDP authorisation or a local channel |
| SMS | notify-sim unless `SMS_HTTP_URL` is set | Contract with a Tunisian SMS provider (Q3) |

### 3.4 Single points of failure accepted for the pilot

Architecture §11 accepts one database instance with nightly backups and WAL, and one MediaMTX instance, for the
pilot. NFR-02 still says "no single point of failure in the report path".

This is acceptable for a one-gouvernorat pilot if the fallback works:
- the app's offline queue;
- the SMS fallback;
- the emergency numbers.

That has to be written down as a known limit of the pilot and accepted by the owner, not discovered in an incident.

## 4. The citizen app cannot be published as it is

- **Release builds are signed with the debug key** (`apps/mobile/android/app/build.gradle.kts:36-41`). The comment
  says the release pipeline would configure signing "(phase 7)", and it never did. Play Store refuses debug-signed
  builds, and a debug key cannot prove who published the app.
- **A release build without `--dart-define` points at the developer's emulator.**
  - The defaults are `http://10.0.2.2:8000`, `…:1080` and `…:8080` (`app_config.dart:20-30`).
  - Nothing refuses such a build in release mode (`kReleaseMode` is used only for log level,
    `lib/core/logging/log.dart:15`).
  - One forgotten flag ships an app that cannot reach the server.
- **There is no release pipeline** for the app:
  - no workflow builds an AAB or IPA (`.github/workflows/mobile.yml` tests only);
  - no iOS signing or provisioning profile;
  - no store listing, privacy label or data-safety form (these must match the processing register).
- **Keycloak clients still allow only localhost.**
  - The staff dashboard client allows `http://localhost:5173` (`infra/keycloak/realms/ehimaya-staff-realm.json:176-179`).
  - The portal client allows `http://localhost:5174` (`ehimaya-public-realm.json:140-143`).
  - `deploy-production.md` §3 says to change them by hand after import. That is one more manual step that must be on
    the go-live checklist, or scripted.

## 5. Decisions and documents only the owner and partners can provide

These are not code. The pilot cannot start without them, and some of them take weeks.

| # | Item | Source |
|---|---|---|
| L1 | Declaration or authorisation of the processing with the INPDP (law 2004-63), based on `docs/privacy/processing-register.md` and the DPIA | DPIA §5, register |
| L2 | FCM transfer outside Tunisia: INPDP authorisation, or a local push channel | DPIA R7, phase 10 report §2 |
| L3 | Retention of volunteer profiles, institution files and the audit log (then we code the purge jobs) | DPIA R6 |
| L4 | Call recording stays off until authorised (`TELEPHONY_RECORDING_ENABLED=false`) | `docs/deploy-production.md` §9 |
| C1 | Hosting in a Tunisian data centre: two servers, five DNS names, firewall | Q2, architecture §11 |
| C2 | SMS provider contract and sender name | Q3 |
| C3 | Telephony trunk with an operator for the platform number (scenario 1); transfer to 198 stays off | Q5, `docs/telephony.md` |
| C4 | Store accounts (Google Play, Apple) in the operator's name, and the signing key held by the operator | §4 |
| V1 | Civil Protection validation of the safety tips and the procedure library | §2.4 |
| V2 | External penetration test (or at least ZAP plus a review by someone other than us) | phase 10 report §3 |
| D1 | Password length: 8 today, ASVS L2 says 12 with a breached-password check | `docs/security/asvs-l2.md` |

## 6. Nothing defines what a successful pilot is

- The requirements set a pilot scale (NFR-03) but no success criteria, no duration and no exit decision.
- The platform already measures response times, volumes by source, category, hour and status
  (`modules/analytics/schemas.py:55-69`), SLA lateness (phase 9) and notification delivery. Nobody has said which
  of these numbers decide "extend to more gouvernorats" or "stop".
- There is no way to collect the opinion of the users:
  - citizens cannot rate how their report was handled;
  - operators cannot report a problem from inside the dashboard.
- **Proposed** (for the owner to change):
  - a pilot of 8 to 12 weeks after a 2-week rehearsal with simulated reports;
  - weekly figures on time to claim, time to first assignment, share of reports located, SOS delivered within 60 s,
    SMS fallback used, API availability, and false or abusive reports;
  - an end-of-pilot report with a go or no-go for wider rollout.

## 7. Smaller findings

- `docs/phase-9/handoff.md` still says phase 9 is "work in progress, unreviewed and untested". The work was finished
  and merged afterwards: `tests/test_access.py`, `test_rls.py`, `test_db_roles.py` and migration `0025` exist. A new
  reader will be misled; mark the file as superseded.
- The fire and smoke model shipped today (2.0.0) scores AP50 0.26 for smoke and 0.10 for fire on the D-Fire test set
  (measured in this thread). Version 3 is being trained.
  - Detections already raise an alert to a person and never an action (DPIA §2), and there are no real cameras in
    the pilot (requirements §1.3).
  - Detections should stay off or be marked experimental in the pilot dashboard until v3 is evaluated.
- 21 of the 81 requirements still have no named test (`docs/traceability.md`). None of them is about the pilot
  area, which does not exist yet (§1).

## 8. Decisions for the owner before the redesign

| # | Question | Options | Recommendation |
|---|---|---|---|
| D1 | Which gouvernorat? (Q6) | Any of the 24 | Your choice; the délégation boundaries and units of that gouvernorat are needed first |
| D2 | A report from outside the pilot area | (a) refused with "call 198"; (b) accepted and handled by a staffed central room; (c) refused except SOS, which goes to central | (c): the citizen is told before sending, SOS is never refused (phase 9 rule), and central only has to watch SOS |
| D3 | Is the central room staffed during the pilot? | Yes, 24/7 / working hours only / no | Needed for D2 (b) or (c) |
| D4 | Délégation scope for staff (requirements RBAC) | In this phase / later | In this phase, with délégation boundaries; the pilot is where it is tested |
| D5 | AI layer in the pilot | GPU server with assistant and transcription / no AI | Start without AI. Add it after two weeks once the core flow is stable (fewer moving parts on day one) |
| D6 | Vision detections in the pilot | Off / on, marked experimental | Off until v3 is evaluated |
| D7 | Duration and success criteria | §6 proposal / your own | §6 proposal, to adjust with the Civil Protection |

## 9. Proposed redesign (after the decisions)

Code work, to be detailed in `docs/api/phase-11-contract.md` once the decisions above are taken:

1. **Pilot area:**
   - national setting `service.gouvernorats`;
   - intake, app, portal and sign-up behaviour (D2), and an "area not yet served, call 198" screen before sending;
   - tests.
2. **Délégations:**
   - load délégation boundaries (source and licence to be checked, like the ODbL gouvernorat boundaries);
   - set `delegation_id` on reports;
   - délégation scope for staff if D4 says so.
3. **Onboarding:**
   - CSV import of units and resources (dry run, then apply, audited);
   - first-sign-in delivery for staff, either by an e-mail invitation through Keycloak with SMTP configured, or a
     one-time temporary password shown once to the creating administrator and audited;
   - a documented bootstrap for the first national administrator;
   - production redirect URIs set by the deployment, not by hand.
4. **Two-server deployment:** compose files and a guide for the GPU server, a private link with TLS and tokens, and
   firewall rules.
5. **App release:**
   - release signing from the operator's keystore;
   - a release build that refuses development URLs;
   - an AAB/IPA build job;
   - store privacy forms drafted from the processing register.
6. **Pilot measurement:** a pilot dashboard page with the §6 figures, a citizen rating after closure (optional,
   anonymous), and an operator "report a problem" link.
7. **Go-live checklist and rehearsal:**
   - `docs/runbooks/pilot-go-live.md`, covering every manual step from §3–§5;
   - a rehearsal script that replays simulated reports in the pilot gouvernorat, all `[SIM]`-marked and purged
     afterwards.

Not code, tracked in the same checklist: L1–L4, C1–C4, V1–V2, D1 (§5).
