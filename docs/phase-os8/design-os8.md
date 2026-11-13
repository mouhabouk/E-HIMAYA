# OS8: address warnings

Source: idea OS8 of the open-source study (`/mnt/project-files/advice/open-source-ideas.md` §3), prototyped in isolation
(`/mnt/project-files/prototypes/address-warnings/`) and approved by Yamen on 2026-11-12 ("خذ نسخة من المنظومة قبل تنفيذ
الفكرة للرجوع لها متى شئت ثم نفذ الفكرة"). The version before this work is kept on the branch
`backup/pre-address-warnings-2026-11-12` and in the bundle `backups/repo/e-himaya-pre-address-warnings-2026-11-12.bundle`
of the project files.

## 1. What changes and what stays

- New: a register of dangerous addresses (marks) per gouvernorat, the warnings of an incident in its file, the team
  leader's warnings on the phone, and the citizen's consent from the medical file.
- Unchanged: the report, its priority and deadline band, the dispatch. A warning informs; it decides nothing.

## 2. The mark

A mark is a point, an address, a description and a category. It shows for every incident inside the category's circle.

| Category | Circle | Review | Critical with |
|---|---|---|---|
| gas, chem | 150 m, 250 m | 12 months | fire, chemical leak |
| fuel | 200 m | 12 months | fire |
| batt | 100 m | 12 months | fire, flood |
| coll (unsafe building) | 80 m | 6 months | fire, landslide, flood, SOS |
| acc (hard to reach) | 120 m | 12 months | fire |
| dog | 80 m | 6 months | — |
| occ (many people, with hours) | 150 m | 12 months | fire, chemical leak |
| mob, oxy, deaf (personal) | 60 m | 12 months | fire (and flood for mob, deaf) |

The central room (national ops_manager) sets the circle, the review period, whether the team sees the category, and the
critical kinds (`PUT /api/v1/staff/address-warnings/categories/{key}`, audited).

Statuses: `pending` (proposed by a team or imported from the institutions' hazardous materials), `active`, `archived`
(with a reason), `rejected`, `withdrawn` (a personal need withdrawn). A mark past its review date stays shown with
«مراجعة متأخرة» until the room confirms it (`confirm` moves the date by the category's period).

## 3. The warnings of an incident

`GET /api/v1/staff/address-warnings/incidents/{id}`: the active marks whose circle holds the incident's point, read
across gouvernorats once the caller's scope on the incident is checked. Order: in hours before off hours, critical with
the incident's kind first, then the nearest. A mark with hours (a nursery) outside them is shown greyed and never critical.

The room marks them read (one or all, `…/ack`); the read is kept under the incident with who and when. The team's
reading arrives in the same row.

## 4. Personal marks (consent)

- Only the owner creates them, from the citizen app (medical file → «تنبيه فرق الإنقاذ عند عنواني»), registered
  accounts only (403 `registration_required` for a guest). One mark per need, at the owner's address.
- Never listed in the register (only counted). The warning carries the need and the address, never a name.
- The name and phone are shown on request, for one incident, with a reason (`…/reveal/{marker_id}`). The request is
  kept (`aw.reveal`) and the owner sees when and why, not who.
- Renewed each year by saving again; withdrawn at once by the owner (`DELETE /api/v1/me/address-warnings`).

## 5. The team leader's phone

The mission screen shows «تحذيرات العنوان» under the mission card: red when a critical one is unread, amber when one is
unread, green when read. The screen lists them, «قرأت التحذيرات» (`POST /api/v1/crew/missions/{id}/address-warnings/ack`),
and «اقترح علامة»: a category, what was seen and the phone's position; the mark is pending until the room approves it.
The team sees only categories marked for the team and marks the room made visible to the team. Button
`field_missions.address_warnings`.

## 6. Rights

| Action | Who | Button |
|---|---|---|
| Read the register, an incident's warnings, the reveals | the operations read roles | page `address_warnings` |
| Add, edit, approve, reject, archive, confirm, import | operator, ops_manager (own gouvernorat; the central room every one) | `address_warnings.edit` |
| Mark read | operator, ops_manager | `address_warnings.ack` |
| Reveal a personal mark's owner | operator, ops_manager | `address_warnings.reveal` |
| Category settings | national ops_manager | `address_warnings.settings` |

## 7. Data

Migration `0103_address_warnings`: schema `aw` with `category` (11 seeded), `marker` (PostGIS point, row-level security
by gouvernorat, the owner's own rows for the citizen, change journal attached), `ack` and `reveal` (append-only logs,
left out of the change journal like the other streams).

## 8. Follow-up OS8-1: the layer on the interactive map

Approved by Yamen on 2026-11-13 from the isolated mockup (`/mnt/project-files/prototypes/address-warnings-followups/`);
the version before it is kept on `backup/pre-os8-followups-2026-11-13`.

- The map page (`/map`) has a switch «تحذيرات العناوين» for those who read the register (`canReadAddressWarnings`),
  remembered for the tab like the other layers (`components/AddressWarningsLayer.tsx`). It reads the same register
  (`GET …/markers`, row-level security by gouvernorat): the active room and team marks, in the category's icon and colour,
  a red ring past their review date, a popup with the description, the circle, the review date and the source.
- Over a whole gouvernorat (zoom below 12) the marks are grouped by cells of the visible area: the count, the colour of
  the heaviest mark (past review, then hazards, then buildings). Closer, one by one.
- Group chips: all, hazardous materials, buildings and access, people and animals, past review.
- Personal marks are never on the layer, not even per area: only their total count in the line under the switch. They
  stay in the file of a nearby incident, without a name, as in §4.
- Yamen's rule of 2026-11-13 (every map datum also a layer of the official interactive map) is met; the thread that
  unifies the map layers moves this switch into its «الإنذار والتحذيرات» folder once its registry lands.

## 9. Follow-up OS8-2: the owner told when a room reads their name

- The reveal (§4) queues at once, in the same transaction, a content-free push `address_warning_viewed` with the
  reveal's id only (contract A8): «اطّلعت فرق الحماية على اسمك · بسبب بلاغ قريب من عنوانك». The app fetches when and
  why behind the login and opens the consent screen.
- An account with no phone registered for pushes gets one SMS with a fixed text (no name, address nor reason) to the
  profile's number; with neither, nothing is sent. How the owner was told is kept on the reveal (`notified_via`: push,
  sms, none) and shown in the reveals log of the room.
- The owner may object: «لا علم لي بأي بلاغ عندي» (`POST /api/v1/me/address-warnings/reveals/{id}/dispute`, optional
  note, once). The objection is kept on the reveal, audited (`address_warnings.reveal_disputed`), shown red in the
  reveals log with the note, and counted in the reminders of the room (the central room: every one).

## 10. Follow-up OS8-3: the review reminder

- `GET /api/v1/staff/address-warnings/reminders`: the active marks of the scope past their review date, or within 30 days
  of it, the oldest first, with their days and level: `soon`, `room` (past), `manager` (7 days or more past),
  `central` (30 days or more past). Personal marks are left out: their owner renews the consent each year in the app.
- The tab «تذكير المراجعة» of the page lists them (red past, amber soon) with: confirm (the category's period), edit in
  the register, archive with a reason, ask a field check (`POST …/markers/{id}/check`: who and when, kept on the mark
  until a confirm or an archive). Nothing is archived automatically.
- Worker loop `address-warning-reminders`: from 08:00 Tunis time, once a day per gouvernorat with marks past or near their
  date (`aw.reminder_day`, safe across processes), the live event `address_warnings.review_reminder` (late, soon, raised
  to the manager, raised to the central room) to the rooms of the gouvernorat and the national room. The dashboard
  shows it as a toast that opens the tab.
- The hour and the delays are constants in this version (08:00, 30, 7 and 30 days); making them settings is OS8-6.

