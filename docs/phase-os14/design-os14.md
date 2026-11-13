# OS14: people and places exposed on the area of a crisis axis

Source: idea OS14 of the open-source study (estimate the people, schools, hospitals, elderly homes and roads inside the
footprint of a hazard, shown in the decision window and the crisis axis; InaSAFE as an idea). Prototyped in isolation
(`/mnt/project-files/additions/18-exposure/`), then built integrated at Yamen's request of 2026-11-13: «تحقيق مبدأ
التكامل وإدماج العناصر بينها وتفادي التكرار لأن محور الأزمة ونافذة القرار موجودة». Decision card: «موافق، نفّذ مدمجا».
Then: «اجعلها طبقة إظافية على الخريطة التفاعلية … حسب الاختيار كشف أو سحب». The version before this work is kept on the
branch `backup/pre-os14-2026-11-13`.

## 1. What changes and what stays

- No new page and no new menu entry: the planned `/exposure` entry of system 4 is removed from `menu.json`.
- The footprint is the axis area that already exists (the union over the axis and its sub-axes), so no hazard is drawn
  twice. The flood area, the spread of a fire and the circle of a gas leak are all drawn as the axis area.
- New: the tab «المعرّضون للخطر» of the axis, its own layer on the axis map, one line per open axis in the decision
  window, and the optional layer «المعرّضون للخطر» of the interactive map (`/map`), off by default.
- No migration: each estimate is an event of the axis timeline (`crisis.event`, kind `exposure`).

## 2. The band

A band around the area is chosen in the tab: none, 0.5, 1, 2 or 5 km. The default follows the kind of the axis
(flood 1 km, forest fire 1 km, technological 2 km, storm, earthquake and health none, other 0.5 km). The last band
chosen is kept for the next computation. "Zone" is the area itself, "band" is the ring around it.

## 3. The estimate

| Figure | How |
|---|---|
| People | For each delegation crossed (INS RGPH 2024 population): its share of the area, and its share of the places of daily life (schools, worship, pharmacies, supermarkets, bus stops), pulled towards the area share by a prior of 10 places. The two give a range; the middle is shown, rounded. Also the people in the zone alone. |
| Places | Map layer features (OpenStreetMap layers and those the rooms loaded) in the zone or the band, by group: health, elderly homes, education, hazardous sites (domino effect), transport, hotels and gathering places. The same place loaded twice (same name within 300 m) counts once. |
| Lines | Railways and roads (when a roads layer is loaded) crossing the footprint: their length inside, and "cut" when they cross the zone itself. Stubs under 50 m are left out. |
| Sources | The census, the layers used and whether each is still "to verify". |

It is a planning figure, not a census: it does not know who is at home now.

## 4. Who

| Action | Who |
|---|---|
| Read the estimate (tab, window line, map layer) | everyone who reads the axis; the author's name only for the rooms |
| Compute or recompute | the rooms that manage the axis, while it is open (`axes.exposure` button) |

When the axis area changes, an existing estimate is recomputed with the same band, so the window and the map never show
figures of an old area. The timeline keeps the brief figures of each estimate.

## 5. API

- `GET /api/v1/staff/crisis/axes/{id}/exposure`: the latest estimate, the default band, the bands, `can_compute`,
  `has_area`.
- `POST /api/v1/staff/crisis/axes/{id}/exposure` `{ring_m}`: compute; `409 axis_no_area` without an area, `422` for a
  band not in the list.
- `GET /api/v1/staff/crisis/exposure/map`: the latest estimate of every open top axis the user sees (map layer).
- `GET /api/v1/staff/window/now`: each axis carries `exposure` (brief figures) when estimated.
- Audit: `crisis.exposure_estimated` with the brief figures.

## 6. Also fixed

- An area added to the interactive map while its markers were loading was never drawn (the map style was then "not
  loaded" and the "load" event had already passed). The map now remembers that its style loaded once.
