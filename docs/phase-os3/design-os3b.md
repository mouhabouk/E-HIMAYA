# OS3, follow-ups: the crews, the turnout, the cost of maintenance and the neighbouring units

Yamen, 2026-11-13: «إليك التفويض الكلي بدون بيئة معزولة ولكن خذ نسخة احتياطية ونفذ، وكقاعدة أساسية أي خريطة في المنظومة
يجب أن تكون لها نظير ويمكن كشفها أو حجبها». Prototype: `prototypes/coverage-followups/` in the project files. Backup:
`backups/os3-followups-2026-11-13/`. Every item joins an existing screen (integration first, Yamen 2026-11-13): no new
page in the menu.

## 1. OS3-1: the repositioning order reaches the crew

* A room's decision that sends a vehicle to another unit as reinforcement, or ends a reinforcement (back to its own
  unit), writes an order in `ops.reposition_order` (migration 0109) and queues a content-free push (`type:
  reposition`, `order_id` only) to the phone of the leader holding the vehicle on shift. The staff app fetches the
  order from `GET /api/v1/crew/repositions` and shows it above the missions.
* The leader taps «اطّلعت», «انطلقنا», «وصلنا»: `POST /api/v1/crew/repositions/{id}/{seen|departed|arrived}`. Each
  step is set once; a later step fills the earlier ones; a phone that was offline keeps its own time up to 12 hours.
  The crew's agents see the card without the buttons (`field_missions.reposition`).
* The rooms follow the steps on the coverage page («أوامر التمركز»): who sent it, who saw it, when the crew left and
  arrived. An order nobody opened after `coverage.order_ack_minutes` (2 by default) turns red: «اتصل بالفريق». An
  order with no crew on shift says it reached no phone.
* A newer order, a breakdown, the workshop or the decommissioning closes the open order (`close_reason`).
* Read by the rooms of the vehicle's gouvernorat and of the other end of the move (RLS like `ops.vehicle_event`).
* Not done: an SMS to the leader when the order stays unread (no outbound SMS to crews yet), backlog OS3-5.

## 2. OS3-2: road times and the measured turnout

* Production sets `ROUTING_URL=http://routing:8002` by default; the engine runs with the profile `routing`. Without it
  every time is the straight-line estimate and the page says so.
* The turnout of each unit is measured on its missions: from the assignment in the room to «في الطريق», median and 9 in
  10, over `coverage.turnout_days` (90), from `coverage.turnout_min_missions` (20) missions; a unit with fewer missions
  keeps `coverage.turnout_minutes`. `coverage.turnout_measured = 0` goes back to one turnout for every unit. The table
  «زمن الخروج لكل وحدة» on the coverage page shows it.

## 3. OS3-3: the cost of maintenance and the monthly readiness

* At the exit of the workshop the maintenance department may enter the kind (repair, periodic, accident), parts,
  labour and outside workshop in dinars (three decimals) and the invoice number; later, when the invoice arrives, from
  the fleet log (`POST /inventory/vehicle-events/{id}/cost`).
* The tab «التقرير الشهري» of the fleet (`GET /inventory/fleet-report`): readiness = vehicle-days neither broken nor in
  the workshop over vehicle-days in the fleet, from the vehicle's log, per gouvernorat and month (Tunisia's time); the
  cost of the stays that ended in the month; workshop entries, decommissionings; the last six months; the five
  costliest vehicles; CSV export and print. Red under `fleet.readiness_red` (80 %), amber under
  `fleet.readiness_amber` (85 %).

## 4. OS3-4: coverage across gouvernorat borders (central room)

* The central room ticks «احتساب وحدات الولايات المجاورة»: the units of other gouvernorats within
  `coverage.neighbour_m` (40 km) of the gouvernorat's délégations count, marked purple; each family shows the coverage
  with the gouvernorat's own units alone too. A suggestion may move a vehicle of a neighbouring gouvernorat
  («تعزيز بين ولايتين، بقرار القاعة المركزية»), sent directly by the central room as before.
* Regional rooms keep their own units only (403 `national_only`). Not done: the owner room's acceptance (OS3-6) and a
  hint for the regional room (OS3-7).

## 5. The official map

Three optional layers in «التغطية والأسطول» on `/map`, each following the rights of its page, each shown or hidden by
its switch (kept for the tab): the live coverage (délégations by state, units, the neighbours for the central room,
with the family and the gouvernorat), the orders on their way (the line from the unit to the host unit, red when
unread), and the readiness per gouvernorat. A click opens `/coverage` or `/fleet/report`. The data stays on its pages.

## 6. Tests

`services/api/tests/test_coverage_followups.py` (5), `apps/dashboard/src/pages/FleetPage.test.tsx` (3 new),
`apps/mobile/test/staff/staff_app_test.dart` (1 new), `apps/dashboard/e2e/phase-os3b.spec.ts` (3, screenshots
`os3b-*.png` in this folder).
