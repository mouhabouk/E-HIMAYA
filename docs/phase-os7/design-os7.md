# OS7: crew accountability in danger zones (PAR)

**Request (Yamen, 2026-11-12):** OS7 was not part of the system. The screens were shown first (isolated mockup,
project files `additions/17-par-module/`), changed several times at Yamen's request, then approved («إليك التفويض
لتنفيذ هذا الخيط»). It was first planned as a module that a script adds and removes; Yamen then asked for it to be
built into the system instead («لا تجعل تفعيل مكونات هذه الفكرة عبر Script بل نفذه»): it is always on.

## 1. What it does

A team leader (`team_leader`) whose vehicle is assigned to an incident starts the check before going into a danger
zone. From then on:

* **The timer.** Every interval (hot zone 10 min, warm zone 15 min by default) the leader confirms with one press that
  the whole team is present («الكل حاضر الآن»). One minute before, the phone shows that the check is due; past the
  time, a grace period (60 s by default), then a red alarm for the operations commander and the room, logged once.
* **A member out for a while** («خرج مؤقتا»), with a reason: air refill, water or fuel, care, rest, other task. He is not
  asked for at the checks until he is back («عاد»), and the room sees it. The leader himself stays.
* **A missing resource** («مورد مفقود»): radio, breathing apparatus, thermal camera, torch, or any resource the leader
  adds («إضافة مورد أو تجهيز»), with who had it and its last known place. The room sends a replacement and marks it
  recovered.
* **The word from the scene** («ردّ الخبر»): under control, being brought under control or not under control, a request
  for reinforcement, and a text typed, or spoken and transcribed by the platform then corrected before sending. The
  board shows when a transcribed text was corrected.
* **The exit** («خرجنا»): the leader ticks every member; the timer stops only when everyone is out.
* **The end** («إنهاء التفقّد»): once every team is out and every resource recovered, the commander or the room ends
  the check; it closes by itself when the intervention is closed. Nothing is deleted: the check, its word from the
  scene and its log stay with the intervention, off the live follow-up (tab «الأرشيف»).

The operations commander and the room (operator, ops manager, field commander) also:

* set the intervals of their gouvernorat (hot 5/10/15 min, warm 10/15/20 min, grace 30–180 s) and the events that call
  for an immediate check (stored, see §6);
* set **the time of the next check** for one team or all, with a small hour and minute picker: no typing, the past
  and more than 12 hours ahead are blocked, quick +5/+10/+15/+30 min; after that check the usual interval resumes;
* **pause the check** with a mandatory reason (danger over, defensive outside, operations stopped, communication
  failure, other with a text) and resume it; the timer goes on from where it stopped;
* call an immediate general check with its reason, call a team by radio, record a confirmation or an exit taken by
  radio.

## 2. Where it lives

* **Team leader:** inside the existing staff app (ء-حماية الأعوان), a card on the mission screen that opens the check
  screen. Not a new app and not the inspector app.
* **Commander and rooms:** the dashboard page `/par` (menu «العمليات اليومية» › «تفقّد الأعوان»), for the read roles
  of operations.

## 3. In the system

The migration `0107_par` of the main chain creates the schema `par`; the routes are always mounted, the pages `par` and
`field_par` are in the permissions catalogue, and the models are in `app.modules.models` (OpenAPI and ERD regenerated).
No setting and no script.

## 4. Data (schema `par`, migration `0107_par`)

`setting` (per gouvernorat), `team` (one assignment inside a zone: members, those out and why, last confirmation,
set time, pause and reason, alarm, exit headcount), `missing`, `sitrep`, `event` (the log), `closure`. Row-level
security on every table: the incident's gouvernorat, like the rest of operations.

## 5. API

| Route | Who |
|---|---|
| `GET /staff/par/incidents?closed=`, `GET /staff/par/incidents/{id}` | read roles of operations |
| `GET/PUT /staff/par/settings` | read roles / write roles, own gouvernorat |
| `POST /staff/par/incidents/{id}/next`, `next/clear`, `pause`, `resume`, `check-all` | write roles (button `par.timing`) |
| `POST /staff/par/incidents/{id}/teams/{team_id}/{radio,confirm,out}`, `missing/{id}/{replacement,recovered}` | write roles (`par.teams`) |
| `POST /staff/par/incidents/{id}/close` | write roles (`par.close`) |
| `GET /crew/missions/{a}/par`, `POST …/par/{enter,confirm,away,back,exit}` | the leader of the vehicle on shift (`field_par.check`) |
| `POST …/par/{missing,sitrep}` | same (`field_par.report`) |

Refusals: `time_passed`, `time_too_far`, `reason_detail_required`, `paused`, `already_inside`, `not_inside`,
`leader_stays`, `headcount_incomplete`, `teams_inside`, `missing_open`, `par_closed`.

## 6. Not in this step (backlog OS7-1 to OS7-3)

* The automatic general check on events (collapse, defensive, evacuation, severity): the choice is saved, the check is
  called by the button for now.
* A push notification, vibration and sound on the leader's phone when the check is due while the app is closed, and
  the SMS confirmation without network.
* The rapid intervention team (RIT) suggestion after 3 minutes without an answer, and the position of a missing
  resource from the phone's location.

## 7. Tests

* `services/api/tests/test_par.py`: the catalogue (20 routes, each under its page or button); entering,
  the crew, away and back, the alarm logged once, the set time and the past refused, the pause with its reason, the
  missing radio, the dictated and corrected word, the headcount, the end and the archive, the settings and the scope,
  the automatic end with the intervention.
* CI: `0107_par` goes up and down with the main chain.
* Dashboard: `src/pages/ParPage.test.tsx`, `e2e/phase-os7.spec.ts` (the screenshots of this folder).
* Phone: `test/staff/field_flow_test.dart` (enter, away, back, missing, headcount).
