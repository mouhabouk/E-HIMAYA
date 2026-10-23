# Phase B: the citizen's personal safety, and map data layers. Review and redesign

Status: **approved by Yamen on 2026-10-23** ("I agree with this methodology"), including the four decisions of
section 7. B1 is being developed.

Scope from the roadmap (vision page, step B): additions 5, 7b, 8, 10 and 11. Yamen's request of 2026-10-23 adds
**map data layers loaded from files** (section 2): hospitals first, then any other layer (category-1 institutions,
shelters…), several layers shown at once. "Nearest to me" (10.3) is built on these layers. Every database or code
change follows review → redesign → develop. Reference files: `additions/08-sos-alert-review.md`,
`additions/10-emergency-guide/10-emergency-hub-review.md`, `additions/11-alerts-whatsapp-contact/11-review.md`,
`additions/07b-medical-and-location-legal.md`.

## 1. Review: what exists today

| Area | Today | File |
|---|---|---|
| Map points | fixed kinds only, each from its own table: institutions and their evacuation / water / alarm points (phase 4), Civil Protection units and resources, ready volunteers (phase 5), live streams (phase 6) | `apps/dashboard/src/lib/poiIcons.ts`, `services/api/app/modules/{orgs,ops}` |
| Adding a new kind of place | needs a migration, an endpoint, an icon and a release | — |
| Hospitals, police, pharmacies, shelters | not in the platform | — |
| Spreadsheet import | none for places (`openpyxl` is already a dependency for XLSX exports, phase 8) | `services/api/pyproject.toml` |
| SOS | button → report to the operations room (phase 2); SMS fallback to 198 without internet (FR-A-048) | `features/sos` |
| Emergency contacts, live location, safety check, medical profile | none | — |
| Critical notification channel | exists on Android since phase 5 (`ACCESS_NOTIFICATION_POLICY`) | `core/push` |
| Safety tips | offline, updated from the server (FR-A-062) | `features/tips` |

## 2. Map data layers (new, Yamen 2026-10-23)

### 2.1 Principle

A **layer** is a named set of places loaded from a file: "Hospitals and emergency departments", "Pharmacies",
"Category-1 institutions", "Shelters"… The number of layers is not limited and a new layer needs no code change and no
app release: an administrator creates it in the dashboard, uploads a file, checks the preview and publishes. The map
(dashboard and app) shows one layer or several at once, each with its own icon and colour.

### 2.2 File formats

| Format | Rules |
|---|---|
| **CSV** | UTF-8 (with or without BOM), separator `,` or `;` detected, first row = column names |
| **Excel XLSX** | first sheet, first row = column names (`openpyxl`, already installed) |
| **JSON** | an array of objects with the same keys as the CSV columns |
| **GeoJSON** | a `FeatureCollection` of `Point` features; `properties` hold the other columns |

One file = one layer. Column names are accepted in Arabic, French or English (`الاسم` / `nom` / `name`,
`خط العرض` / `latitude` / `lat`, `الهاتف` / `téléphone` / `phone`…). A downloadable template is offered for each layer.

| Column | Required | Example |
|---|---|---|
| `name` | yes | مستشفى الحبيب بورقيبة |
| `lat`, `lon` | yes (GeoJSON: the geometry) | 34.7406, 10.7603 |
| `id` | recommended: the file's own identifier, lets a later file update the same place instead of duplicating it | HOP-SFX-001 |
| `type` | no: sub-type inside the layer, e.g. hospital / emergency department / clinic | `emergency` |
| `phone`, `phone2` | no | 74 241 511 |
| `address`, `delegation` | no | |
| `manager` | no: name of the person in charge | |
| `hours` | no: "24/7" or "08:00-17:00" | 24/7 |
| `email`, `website` | no | |
| anything else | no: kept as extra information (beds, specialities, capacity…) and shown in the place's card | `beds: 420` |

Checks before anything is saved: coordinates inside Tunisia (the 24 gouvernorat boundaries already in the database;
decimal comma accepted), the gouvernorat and delegation found from the position, phones normalised to `+216`,
duplicates in the file, missing names. Limits: 10 MB and 50,000 rows per file.

### 2.3 Import flow (dashboard)

1. **Layer**: name in ar / fr / en, icon (from a fixed set), colour (from the palette, checked for contrast), audience
   (public: shown in the app; staff: dashboard only), source and licence (e.g. "Ministry of Health 2026",
   "OpenStreetMap, ODbL").
2. **Upload** → **preview** without saving: counts (new, updated, unchanged, removed, rejected), the rejected rows with
   the reason, and the points on a map.
3. **Mode**: *merge* (add and update by `id`, keep the others) or *replace* (the file becomes the whole layer).
4. **Publish** with a reason. Each import is versioned and audited; "undo the last import" restores the previous
   version.
5. **Export** the layer as CSV, XLSX or GeoJSON at any time (the same columns: export, edit, re-import).

A single place can also be added, corrected or hidden by hand from its card.

### 2.4 Display

* **Dashboard**: a layer switcher on every map (live map, incident, analytics) with a tick per layer, any number at
  once; the existing kinds (units, resources, institutions, volunteers, streams) appear in the same switcher. A click
  on a place opens its card (all columns, call, copy coordinates). Many points are grouped into clusters.
* **Mobile, "Nearest to me" (10.3, 10.5)**: the drop-down at the top of the map lists the public layers (Civil
  Protection centres by default), with "several" allowing more than one; the bottom panel shows the three nearest
  with distance, call and route; a "List" button shows the results without a map. The public layers of the user's
  gouvernorat are downloaded in advance, so the list and distances work **without internet** (only the map tiles
  need a connection); the app checks for a newer version once a day.
* Civil Protection centres come from the existing units directory (phase 5), not from a file, so they are always
  in step with operations.

### 2.5 Personal data and security

* The `manager` column and any column marked "staff only" are **never sent to the app**: the public sees the place,
  its phone and hours, not the name of a person. The administrator can change this per column.
* No moving patrols or vehicles in public layers (security; addition 10.3): fixed sites only.
* Who imports: the system administrator (national), and content editors for the layers they are given. Regional
  account administrators may later edit the places of their gouvernorat (to decide).
* Uploaded files are parsed on the server only (no formulas executed, XLSX read in read-only mode, CSV injection
  neutralised on export).

### 2.6 Database (review → redesign → develop)

One migration, schema `geo` (existing):

| Table | Content |
|---|---|
| `geo.layer` | key, name ar/fr/en, icon, colour, audience (public / staff), source, licence, columns (name ar/fr/en, type, public or staff only), current version, enabled, created/updated by and at |
| `geo.layer_feature` | layer, file `id`, name, type, phones, address, gouvernorat and delegation (computed), position (PostGIS point), extra columns (JSON), hidden, import that last changed it |
| `geo.layer_import` | layer, file name, SHA-256, format, mode, counts, rejected rows, reason, who, when, applied / undone |

Indexes: spatial index on the position (nearest and map area queries), unique (layer, file `id`). Row-level
security: public layers readable by everyone, staff layers by staff only.

### 2.7 API

* Staff: `GET/POST/PATCH /api/v1/staff/layers`, `POST /api/v1/staff/layers/{key}/imports` (preview),
  `POST …/imports/{id}/apply`, `POST …/imports/{id}/undo`, `GET …/export?format=csv|xlsx|geojson`,
  `GET …/template`, `PATCH /api/v1/staff/layers/{key}/features/{id}`.
* Public: `GET /api/v1/layers` (public layers, with version), `GET /api/v1/layers/{key}/features?bbox=…` or
  `?near=lat,lon&limit=…`, `GET /api/v1/layers/{key}/package?gouvernorat=…` (offline copy, with `ETag`).

### 2.8 Data while the Office's lists are missing

Proposal: a first load of hospitals, clinics, pharmacies, police and National Guard posts for Tunisia from
**OpenStreetMap** (real public data, ODbL licence, shown with its attribution and marked "to be verified"), through
the same import (a GeoJSON file prepared by a script). The Office's official lists then replace it with *replace*
mode. No simulated places are invented.

## 3. Personal safety (additions 5, 7b, 8, 10, 11)

As reviewed and approved in the addition files; summary of the design:

| Item | Design |
|---|---|
| **Emergency contacts (5)** | contacts and groups chosen from the phone book (contacts permission asked here, first use), stored on the phone. An in-app link to another e-Himaya user only by invitation accepted by both; only the link is stored on the server. |
| **SOS message (5, 11.3)** | default text + last position + battery, 5-second cancel window (can be turned off); channels in order: in-app critical alert to linked contacts, SMS (pre-filled, sent by the user), WhatsApp (pre-filled chat). The report to 198 is unchanged. |
| **Critical alert (8.3, 11.1, 11.2)** | rings through silent / do-not-disturb on Android (existing channel), red full screen, vibration pattern and flash; receiver screen with live location, route, call, SMS, WhatsApp and "report to 198 on their behalf". iPhone needs Apple's Critical Alerts entitlement in the Office's name. |
| **Live location (8.4)** | random, unguessable link, ends automatically (default 1 h), stoppable any time; opens a light web page with the moving point. |
| **Safety check (8.1)** | timer chosen by the user; reminder 10 min before, sound 1 min before; if not cancelled, SOS to trusted contacts only (not to the operations room) with the last position. |
| **Self-test (8.5), recent alerts (8.7), battery guidance (8.6)** | test sound and position without notifying anyone; local history of sent alerts; guidance screen to exempt the app from battery limits. |
| **Medical profile (7b)** | optional fields, separate consent, stored encrypted **on the phone only**; attached to a report only if the user ticks it for that report; fingerprint lock; delete in one tap. |
| **Location history 72 h (7b)** | off by default, visible notification while on; read only by an operator after a missing-person report, with a reason, audited and notified to the user; deleted after 72 h. Needs the legal review first. |
| **Emergency hub (10.1)** | one screen: numbers, first aid, nearest to me (section 2), share my location, my medical profile, my coordinates. |
| **First aid (10.2)** | extends the offline tips with a "first aid" category: "when to call 198 now" first, numbered steps, "what not to do", read aloud, CPR metronome. Content validated by the Office's medical staff. |
| **Contact us (11.4)** | requests with a number and a status (access to information under law 2016-22 with its legal deadlines, non-urgent hazard, question, suggestion, app problem, partnership); one inbox in the dashboard by type and gouvernorat. Banner: "For emergencies call 198". |
| **Account (8.11, 8.12)** | delete my account (required by Google Play; reports kept anonymised), replay the intro from Settings. |

Database for section 3 (detailed in the next revision of this document after the order is decided): contact links
and invitations, live-location shares, contact-us requests and their history, location history (if approved),
medical attachment to a report (encrypted, deleted with the case).

## 4. Simulation

* `[SIM]` stays for the SMS gateway (phase A) and the critical alert on iPhone until Apple's entitlement.
* First-aid content: until the Office's text is validated, the screens show the structure with a visible amber
  `[SIM]` banner "content awaiting medical validation"; nothing is presented as official advice.
* Map layers: no simulated places (section 2.8).

## 5. Proposed order inside phase B

* **B1: map layers, nearest to me, emergency hub, first aid, contact us.** Needs the hospital and centre lists (or
  approval of the OpenStreetMap first load) and the first-aid content.
* **B2: emergency contacts, SOS message, critical alert, live location, safety check, medical profile, location
  history.** Needs the legal review of the medical profile and the location history.

## 6. Tests planned

* API: each format (CSV `,` and `;`, XLSX, JSON, GeoJSON), Arabic / French / English column names, coordinates
  outside Tunisia, decimal comma, duplicates, merge vs replace, undo, export → re-import gives the same layer, staff-only
  columns never in public answers, nearest ordering, offline package `ETag`, permissions, audit.
* Dashboard: layer form, import preview with rejected rows, several layers on one map.
* Mobile: layer drop-down with several layers, offline list and distances, call and route intents.
* Security: CSV injection on export, oversized file, malformed XLSX.

## 7. Decisions (approved by Yamen, 2026-10-23)

1. Phase B is split into **B1 then B2** (section 5).
2. **First load from OpenStreetMap** while waiting for the Office's lists, marked "to be verified" (section 2.8).
3. The `manager` name is **hidden from the public by default** (section 2.5); the administrator may change it per
   column.
4. **Who imports**: the system administrator and content editors (for the layers they are given). Regional
   administrators: later, to decide.
