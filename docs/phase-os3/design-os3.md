# OS3: the fleet and its maintenance, live coverage and repositioning, access profiles

Source: idea OS3 of the open-source study (`/mnt/project-files/advice/open-source-ideas.md`), prototyped in isolation
(`/mnt/project-files/prototypes/coverage/`) and approved by Yamen on 2026-11-11 ("موافق على الإدماج بالمنظومة").
Requests of the same day folded in:

- the vehicles show by scope of competence and the central room sees them all;
- personnel are managed by the personnel department, vehicles by the maintenance directorate, inspections by the
  inspectorate: one set of rights (`قم بتوحيد الصلاحيات`);
- the rooms only set «بالوحدة», «في تعزيز» and «معطبة»; «في مهمة» follows the interventions; «في طور الصيانة» and
  «تم طرحها» come from the maintenance directorate;
- reinforcement is done by the rooms (`التعزيز تقوم به القاعات`);
- a read only or read and write profile the system administrator grants to the inspector general or anyone else.

Migration `0103_fleet`.

## 1. Who does what

| Work | Who | Where |
|---|---|---|
| Vehicle card: administrative number, plate (رقم منجمي), type, specifications, odometer, acquisition date | `maintenance_officer` (regional: own gouvernorat; national: all) | Fleet › Vehicles, `POST/PATCH/DELETE /inventory/vehicles`, also `POST/PUT/DELETE /resources` |
| Into the workshop (workshop, reason, expected exit), out of it (odometer), retirement (decision, date, reason) | `maintenance_officer` | `POST /inventory/vehicles/{id}/maintenance`, `/maintenance/end`, `/retire` |
| Operational state: at the unit, on reinforcement (host unit), broken (fault) | the rooms: `operator`, `ops_manager`, `regional_director` of the owner's or host's gouvernorat; national rooms everywhere | `POST /inventory/vehicles/{id}/state` |
| On a mission | automatic: the dispatch of an intervention | unchanged |
| Agents, transfers | `personnel_officer` | unchanged pages |
| Units (the stations) | `ops_manager` | Resources page |
| Read the fleet | the rooms, the maintenance directorate, the personnel department, the leaders who read the register | Fleet pages, `GET /inventory/vehicles` |

`maintenance_officer` is a new realm role (support family), grantable by a regional account administrator, landing on
`/fleet`. The equipment stock (quantities) moves with the vehicles to the maintenance directorate.

A vehicle in the workshop or retired cannot be moved by a room or by a card edit (409 `vehicle_maintenance`,
`vehicle_retired`). A card edit never changes the state.

## 2. States

| State | Set by | Dispatch | Coverage |
|---|---|---|---|
| `ready` (بالوحدة) | room, or the end of a maintenance | proposed | counts at its unit |
| `assigned` (في مهمة) | dispatch | no | no |
| `reinforcement` (في تعزيز) | room | proposed **from the host unit** | counts at the host |
| `broken` (معطبة) | room, with the fault | no | no |
| `maintenance` (في طور الصيانة) | maintenance directorate | no | no |
| `retired` (تم طرحها) | maintenance directorate | no | leaves the plan; the archive keeps it |

Stored on `ops.resource`: `status` stays the dispatch status, `out_reason` gains `retired`, `stationed_unit_id` and
`stationed_since` hold a reinforcement (cleared by any other state). The card columns: `plate` (unique, `^\d{1,3}
?تونس ?\d{1,4}$`), `odometer_km` (never decreases), `acquired_on` (not in the future), `fault`, `workshop`,
`maint_reason`, `maint_since`, `maint_until`, `retired_on`, `retire_decision`, `retire_reason`.

Every change writes `ops.vehicle_event` (kinds `state`, `reinforce`, `reinforce_end`, `maintenance_start`,
`maintenance_end`, `retire`) with the person, the before and after, and the details (fault, workshop, host, suggested
gain). The owner's and the host's gouvernorats read it.

### Scope of a reinforcement

The host room sees the vehicle while it waits there (row-level security on `stationed_unit_id`), and the name of its
own unit through `ehimaya.hosts_from(unit)` (owner rights, to avoid the policy recursion). The decision support
proposes it from the host's position (`recommendations._candidates`: resource, then host, then unit location).

## 3. Live coverage (`GET /api/v1/staff/coverage?gouvernorat=`)

For each délégation of the gouvernorat (2024 population, label point) and each family of the SNACR plan:

| Family | Vehicle kinds |
|---|---|
| medical | ambulance |
| road | rescue_vehicle |
| fire | fire_engine, water_tanker, large_extinguisher, aerial_ladder |
| rescue | rescue_vehicle, hazmat_vehicle, boat |

- Time = `coverage.turnout_minutes` (2) + road time of `routing.travel` (haversine fallback when the engine is down,
  said on the page). Target = `snacr.target.{family}.{zone}`; zone from `snacr.density.*`.
- **Now:** the ready vehicles where they are (a reinforcement at its host).
- **Plan:** every vehicle not retired at its own unit. A délégation the plan covers and the ready vehicles do not is an
  alert with its population.
- **Suggestions:** greedy moves of one ready vehicle to another unit of the gouvernorat, best net population gain first,
  up to `coverage.suggestions_max` (3) per family. Accepting one sends the vehicle as reinforcement with the gain kept in
  the log.
- The unit-to-délégation grid is cached 10 minutes. A regional caller reads its own gouvernorat (403 otherwise); a
  national caller names one (422 `gouvernorat_required`).

The page `/coverage` (operations menu): KPIs per family against the plan, an SVG map of the délégations (green covered,
red lost, amber out of time even at full fleet) and the units with their ready count, the alerts, the suggestions with
the accept button for the rooms, and the table of délégations.

## 4. Access profiles (`/api/v1/staff/features/profiles`)

`access.feature_profile`: a name, a description and a list of pages, each `read` or `write`. Granting it (`POST
/profiles/{id}/assign`, to an account or a role, optionally one gouvernorat and dates, with a reason) writes the usual
`access.feature_rule` grants, tied by `profile_assignment_id` so they are revoked together:

- `read`: the page and its tabs (GET routes only);
- `write`: also its buttons.

The fixed ceiling holds: what a role may never hold (personal data of the committees, the national scope for a regional
account, the technical keys) is skipped and listed; 422 `profile_grants_nothing` when nothing remains. Built-in
profiles cannot be edited or deleted; a granted one cannot be deleted (409). Three built-in read-only profiles are
seeded: «اطلاع على الوسائل» (fleet), «اطلاع على الأفراد» (personnel), «اطلاع على التفقديات» (inspections).

The panel sits at the top of the Permissions page (system administrator only).

## 5. Catalogue

- New page `fleet` (`/fleet`, group `fleet`), tabs `fleet.maintenance`, `fleet.archive`, `fleet.log`, buttons
  `fleet.edit`, `fleet.maintenance_actions` (act as `maintenance_officer`), `fleet.state` (act as `operator`).
- New page `coverage` (`/coverage`, operations).
- `resources.manage` keeps the units; new button `resources.cards` for the vehicle cards.
- Inventory buttons split: agents and transfers act as `personnel_officer`, the import as `maintenance_officer`.

## 6. Not in this step (backlog)

- OS3-1: the staff app tells the vehicle's crew about a repositioning (push).
- OS3-2: real road times by default (the routing engine in production), measured turnout per unit.
- OS3-3: maintenance cost and fleet availability rate per month.
- OS3-4: coverage across gouvernorat borders for the central room (a neighbour's unit).
