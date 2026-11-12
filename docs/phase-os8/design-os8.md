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
