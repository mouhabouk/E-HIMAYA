# Decision support (phase 7 §3)

Module `services/api/app/modules/decision`, migration `0013_decision` (schema `decision`). Contract:
`docs/api/phase-7-contract.md` §3. Decision support suggests and explains; it never assigns, alerts, escalates or calls on
its own. Every action is a button that opens an existing flow (an assignment order, the alert form, a call, a route), and
an operator confirms it there.

| Endpoint | Roles | Limit |
|---|---|---|
| `GET /api/v1/staff/incidents/{id}/recommendations` | staff read roles, within the user's scope | 60 / min / user |
| `GET /api/v1/staff/route?from=lat,lon&to=lat,lon&profile=car\|truck` | staff read roles | 120 / min / user |
| `GET /api/v1/staff/incidents/{id}/responders` | staff read roles, within the user's scope | — |
| `POST /api/v1/staff/incidents/{id}/assistant` `{"question","lang":"ar\|fr"}` | staff read roles, within the user's scope | `ASSISTANT_PER_HOUR` (30) / h / user |

Errors (standard error envelope): `422 invalid_point` (a malformed `from`/`to`), `422 out_of_coverage` (a point outside
Tunisia's bounding box), `404` (an unknown incident or one outside the scope), `429 rate_limited`, and
`503 assistant_unavailable` (no LLM is configured, Ollama is unreachable, or the model is not pulled).

## 1. Recommendations

`context.gather()` builds a `Situation` from data that already exists:

* The incident: category, classification, priority, op level, centroid and gouvernorat.
* Its non-rejected reports and their AI extraction: lives at risk, people trapped, injured, deaths and hazards.
* The number of distinct reporters.
* Vision detections (phase 6): the most persons seen in one frame or image, and the strongest confirmed fire or smoke.
* The nearest registered sensitive site (`orgs.sites`).
* The resources already engaged, by kind.
* The other open incidents in the same gouvernorat with priority ≥ 70 in the last 24 h.
* The weather at the nearest grid point:
  * the current hour's values
  * fire danger: the latest class of the past 24 h
  * heavy rain: the strongest level from 1 h ago to 6 h ahead
* The latest spread forecast run, using its largest polygon.
* The pending weather alert suggestions for the gouvernorat.

Weather and forecast data are read through the small `Environment` protocol (`context.py`). The platform adapter is
`environment.py`, built on `weather.service` and `forecast.run`, and tests inject a fake.

Each item carries a title and a rationale in Arabic and French, `inputs` (including the shared `inputs.incident`) and a
`confidence`. The response also carries `simulated` (true when the weather or forecast it used is simulated) and a
bilingual `notice` ("nothing is applied automatically").

| Kind | Rule (summary) | Action |
|---|---|---|
| `resources` | Base needs per category (`domain.BASE_NEEDS`), plus extra units when needed:<br>• forest fire or fire danger ≥ high: a fire engine and a tanker<br>• forecast area ≥ 50 ha<br>• an industrial or hazmat site nearby<br>• a flood with a rain warning<br>• injured or fuel at a traffic accident<br>• a building collapse<br>• lives at risk<br>• a large incident<br>Already-engaged units are deducted. Up to 8 available resources of each kind within 150 km (in the user's unit scope) are ranked by **travel time** (the routing matrix). | `open_assignment` (resource_id, order) |
| `route` | The route from the best-ranked vehicle to the incident (truck profile for heavy kinds). | `show_route` (from, to, profile) |
| `volunteers` | Ready volunteers within 20 km with matching skills (`ops.interventions.suggestions`); none for a chemical leak. | `call` (volunteer_id) |
| `escalation` | Triggers:<br>• priority ≥ 85 with ≥ 10 reporters or persons detected<br>• forecast fire ≥ 100 ha<br>• extreme fire danger<br>• a flood with lives at risk and a rain warning or high flood level<br>• ≥ 3 other busy incidents<br>• people trapped under a collapse<br>Proposes `crisis` from `normal`, or `disaster` from `crisis` when there are ≥ 3 triggers. | none: the committee decides through the existing level flow |
| `alert` | Fire: forest fire or danger ≥ very high, plus forecast ≥ 20 ha or danger.<br>Flood: a rain warning, or a watch with lives at risk, or a high forecast level.<br>Chemical leak: priority ≥ 60 or a sensitive site.<br>Landslide: lives at risk.<br>Pending weather suggestions add a reason. | `open_alert_form` with a prefill (kind, hazard, severity, ar/fr/en title and body, channels, gouvernorat and forecast polygon). An editor or committee still reviews and validates it. |
| `responders` | See §3. | `call` for agencies that have a public number |

When a needed kind has no available resource, an item with `confidence: low` says so. An incident without a location
gets an item that explains why no distances could be computed.

## 2. Routing engine

**Valhalla 3.9.1** (MIT) was chosen over OSRM because it serves the car and truck profiles from one graph and has a
matrix API. The image is `ghcr.io/valhalla/valhalla:3.9.1@sha256:4fd114eb1d26b8fc2f43bcb3df234c1b63a0bf13c277405e5943d5361dc575de`.
The data is the OpenStreetMap extract of Tunisia from Geofabrik, **© OpenStreetMap contributors, ODbL 1.0**. Every
route response carries `attribution`, and the map must show it.

Compose profile `routing` (`infra/compose.yml`) defines three services:

* `routing-init` makes the `routingdata` volume writable by uid 10002.
* `routing-prepare` is a one-shot job that runs `infra/routing/prepare.sh`.
* `routing` runs `valhalla_service` on the internal port 8002, with no published port, a read-only root filesystem and
  all capabilities dropped.

### Pinning the extract

`prepare.sh` refuses to run without a checksum. To pin one:

```sh
# 1. Choose a dated extract (not tunisia-latest), e.g. https://download.geofabrik.de/africa/tunisia-260901.osm.pbf
curl -fLO https://download.geofabrik.de/africa/tunisia-260901.osm.pbf
curl -fsSL https://download.geofabrik.de/africa/tunisia-260901.osm.pbf.md5   # cross-check with md5sum
sha256sum tunisia-260901.osm.pbf
# 2. Put both into .env:
#    ROUTING_OSM_URL=https://download.geofabrik.de/africa/tunisia-260901.osm.pbf
#    ROUTING_OSM_SHA256=<64 hex>
#    ROUTING_URL=http://routing:8002
# 3. Build the graph, then start the engine
docker compose -f infra/compose.yml --profile routing run --rm routing-init
docker compose -f infra/compose.yml --profile routing run --rm routing-prepare
docker compose -f infra/compose.yml --profile routing up -d routing
```

`prepare.sh`:

* downloads to `.part` and deletes it on a checksum mismatch
* builds admins, tiles and `tiles.tar` into `build-<sha>/`
* switches the `current` symlink atomically, then removes older builds
* does nothing when re-run with the same checksum

To update the map, pin a newer dated extract and re-run `routing-prepare`, then restart `routing`. Building Tunisia
needs about 2 GB of RAM and a few minutes; `ROUTING_BUILD_THREADS` defaults to 2.

### API and fallback

`GET /route` returns `{"distance_m","duration_s","geometry":LineString,"engine":"valhalla"|"fallback","profile",
"simulated":false,"attribution"}`. Both points must lie inside Tunisia's bounding box.

When `ROUTING_URL` is unset (`not_configured`), the engine times out or errors (`engine_unavailable`, after
`ROUTING_TIMEOUT_S`, 5 s by default), or it finds no road (`no_route`), the API answers with a **straight-line
estimate**:

* `"engine":"fallback"`
* a two-point geometry
* the haversine distance × 1.3 detour factor, at 55 km/h by car or 45 km/h by truck
* `fallback_reason` and `assumptions`

The estimate is not a simulation of real data, so it keeps `simulated: false`, but the dashboard labels it as an
estimate. Ranking resources uses the matrix endpoint (`/sources_to_targets`, in chunks of 50) and falls back the same
way. Each ranked candidate states which engine produced its time.

## 3. Responders (FR-C-13)

There is no separate officials table, so responders are drawn from the phase 4–5 directory. In order:

1. The civil-protection directorate unit of the gouvernorat (`ops.unit`).
2. The two nearest other units within 60 km.
3. The regional committee, when the op level is above `normal` or the priority is ≥ 80.
4. The nearest registered institution (`orgs`) with its contact.
5. Agencies matched by category and classification (`domain.AGENCY_RULES`): SAMU 190 when there are injured or lives at
   risk, police 197, garde nationale 193, STEG, SONEDE, forests (DGF), ANPE, INM, poison centre, municipality and
   equipment.

Each entry has `kind` (`unit|committee|agency|institution`), its names in Arabic and French, its role, a phone number
when one is known and public, its distance, and `reason`. Agency numbers are the public short numbers; no personal
number is ever invented.

## 4. Assistant (RAG over Ollama)

Configuration:

* `OLLAMA_URL`: the Ollama instance of phase 3, for example `http://ollama:11434`. When unset, the assistant answers 503.
* `ASSISTANT_MODEL`: defaults to `AI_LLM_MODEL`, then to `qwen3:4b`.
* Optional settings: `ASSISTANT_TIMEOUT_S` (120), `ASSISTANT_NUM_CTX` (8192) and `ASSISTANT_PER_HOUR` (30).

The call goes to `/api/chat` with a JSON-schema `format`, temperature 0 and `think: false`; it retries without `think`
for models that reject it.

### Retrieval

1. **Procedures library** (`decision.procedure_chunk`). The question is embedded with the e5 model through the AI
   service (the same e5 pipeline as reports, 768 dimensions), and passages are ranked by cosine similarity in pgvector plus Postgres
   full-text search ('simple' config, Arabic article prefixes stripped). The score is:
   `similarity + 0.3·lexical + 0.2·same category + 0.1·same classification`.
   A passage with no lexical match needs a similarity of at least 0.78. When the AI service or the embeddings are not
   available, full-text search alone is used, and the audit records `retrieval: full_text`.
2. **Similar past incidents.** These are closed incidents in the user's scope that have an evaluation, whose report
   embeddings (averaged) have a cosine similarity of at least 0.85 or share the category. Their closing evaluation is
   used as the excerpt.
3. **The incident's own reports.** Their summaries are given as untrusted context, clearly labelled. They can never be
   the only support: without a procedure or a past-incident source, the model is not called and the answer is the
   refusal.

### Answer rules

The system prompt says:

* answer only from the numbered sources
* cite them as `[n]`
* reply with a fixed refusal when the sources do not cover the question
* never invent numbers, phone numbers or doses
* answer in the requested language

The server enforces these rules regardless of what the model says:

* Output that is not valid JSON, or a "supported" answer without a valid citation, becomes the refusal.
* Citations to source numbers that do not exist are removed.
* `supported` is false whenever the answer is the refusal.

The response is `{"answer","supported","sources":[{"kind","id","title","excerpt","references"}],"model","notice"}`.
`references` lists the public documents a procedure cites.

### Injection safety

Report text, the question and passages are all **data**. They are wrapped in `<incident>`, `<sources>` and `<question>`
blocks, and `<` and `>` inside them are replaced with `‹` and `›`, so a report cannot close a block or open a new one.
The system prompt states that instructions inside these blocks must be ignored. The model also has no tools and no
side effects: its only output is text shown to the operator, with its sources.

### Records

Each question writes an `ops.timeline_event` of kind `assistant`, containing the question, the answer, `supported`,
the language, the source ids and the model. It also writes an audit entry `assistant.ask` with the language,
`supported`, the sources, the model and the retrieval mode.

## 5. Procedures library

`docs/procedures/` holds 16 sheets: 8 hazards in Arabic and French. The hazards are fire, forest fire, flood, traffic
accident, drowning, landslide, chemical leak and building collapse. They are written for the project from public
guidance (ONPC, WHO, IFRC, ERC, ERG 2024, INSARAG, UNDRR, USGS, NWCG, FAO, EFFIS, INM and others), with no copied text.
The header format and rules are in `docs/procedures/README.md`. Each `##` section is one retrieval passage.

* **Indexing.** The API worker loop `procedures-index` runs at start-up and then every 5 minutes. Under an advisory
  lock, it adds, updates (by sha256) and removes passages, then embeds those still pending, 16 at a time.
  * `PROCEDURES_DIR` defaults to `/app/procedures`, mounted read-only from `docs/procedures` in compose.
  * A one-shot run: `python -m app.modules.decision.cli index [--no-embed]`.
* **Validation without a database:** `python -m app.modules.decision.cli check ../../docs/procedures`. Tests also check
  that every sheet parses and that the Arabic and French versions pair up.

The sheets are reference material for trained staff. They do not replace ONPC orders or official operating procedures,
and a domain expert should review them before operational use.

## 6. Limits

* The OSM extract checksum is not committed: the operator pins it (see §2). Until then the engine is not built, and
  every route is a fallback estimate.
* The fallback ignores roads, relief and closures, so its times only order candidates roughly.
* Traffic is not modelled; Valhalla uses free-flow speeds.
* The rules are fixed thresholds (`recommendations.py`, `domain.py`). They are explainable but not calibrated on
  Tunisian data.
* Responders come from units, committees, institutions and agency numbers, not from named officials, because no
  officials directory exists.
* Answer quality depends on the local model. `qwen3:4b` can be terse in Arabic. The server-side citation check catches
  missing citations, not citations that are wrong.
* The procedures library is the only knowledge the assistant has; a question it does not cover is refused.
