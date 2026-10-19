# عقد الواجهة البرمجية — المرحلة 3 (طبقة الذكاء الاصطناعي 1)

Phase 3 additions to the API contract of phase 2 (`docs/api/phase-2-contract.md`, still valid). The live
schema is `GET /openapi.json`. Everything the AI produces is a **suggestion** for the operator: no report
is ever rejected, closed or re-categorised automatically (BR-03, BR-06), and grouping is confirmed by an
operator (BR-11).

## 1. Analysis pipeline (architecture §6.1)

```
report created ─► rules at once (priority, credibility, grouping suggestion) ─► report.created event
       └─► queued ─► transcribe audio/video ─► extract (language model) ─► translate fr/en→ar ─► embed
                     ─► rules again ─► report.enriched event
media stored ─► re-queued (new evidence: transcription, credibility)
```

- Every report gets a priority and a credibility **immediately**, computed by transparent rules (category,
  keywords in Arabic, Tunisian Derja, French and English, reporter history, media, location accuracy,
  corroboration). The models refine them when they are available.
- The queue is the table `ai.analysis`. If a model is down the report stays visible and ranked with
  `analysis_state = "pending"`, and is retried with back-off (30 s doubling up to 1 h, 8 attempts), then
  `"failed"` (analysis incomplete). Undecodable media are not retried.
- The most urgent reports (highest priority) are analysed first.
- Without an AI service (`AI_SERVICE_URL` unset), the rules still run; steps show `"disabled"`.

## 2. Staff report fields (list, detail, live events)

`StaffReport` gains:

| field | type | meaning |
|---|---|---|
| `text_ar` | string \| null | Arabic translation of a French or English text (FR-A-045); null for Arabic |
| `priority_score` | 0..100 \| null | BR-20 priority |
| `credibility_score` | 0..100 \| null | BR-06 suggested credibility |
| `analysis_state` | `pending` \| `running` \| `done` \| `failed` \| null | show "بانتظار التحليل / En attente d'analyse" for pending and running |
| `lives_at_risk` | bool \| null | lives component reached 1 (model or keywords) |
| `suggested_category` | category \| null | category read by the language model (may differ from the citizen's) |
| `incident_id` | uuid \| null | incident the report belongs to |
| `has_suggestion` | bool | a grouping suggestion is waiting for the operator |

`GET /api/v1/staff/reports` gains `sort=received|priority` (default `received`; `priority` = highest first,
then newest) and `incident_id=<uuid>`. `q` also searches `text_ar`. Cursors are tied to the sort.

`GET /api/v1/staff/kpis` gains `high_priority` (priority ≥ 70) and `analysis_pending`.

### Detail: `StaffReportDetail.analysis`

```json
{
  "state": "done", "attempts": 1, "language": "fr",
  "steps": {"transcribe": "done", "extract": "done", "translate": "done", "embed": "done"},
  "extraction": {"language": "fr", "category": "fire", "lives_at_risk": true, "people_trapped": true,
                 "injured_count": 2, "deaths_reported": false, "hazards": ["gas"],
                 "keywords": ["incendie"], "summary_ar": "…", "confidence": 0.9},
  "priority": {"score": 79, "components": [
      {"key": "severity", "value": 0.9, "weight": 35, "points": 35.0, "detail": {"category": "fire", "hazards": ["gas"]}},
      {"key": "lives", "value": 1.0, "weight": 25, "points": 27.8, "detail": {"source": "model", "people_trapped": true}},
      {"key": "casualties", "value": 0.4, "weight": 10, "points": 4.4, "detail": {"source": "model", "injured": 2, "deaths": false}},
      {"key": "reporters", "value": 0.3, "weight": 10, "points": 3.3, "detail": {"reporters": 2}},
      {"key": "credibility", "value": 0.8, "weight": 10, "points": 8.9, "detail": {"score": 80}},
      {"key": "sensitive_sites", "value": null, "weight": 5, "points": 0, "detail": {"reason": "no_data_yet"}},
      {"key": "weather", "value": null, "weight": 5, "points": 0, "detail": {"reason": "no_data_yet"}}]},
  "credibility": {"score": 80, "components": [
      {"key": "base", "points": 50, "detail": {}}, {"key": "registered", "points": 15, "detail": {"kind": "citizen"}},
      {"key": "media", "points": 10, "detail": {"count": 1}}, {"key": "precise_location", "points": 5, "detail": {"accuracy_m": 8}}]},
  "suggestion": {"kind": "report", "incident_id": null, "report_id": "…", "tracking_code": "EH-26-61-0000123",
                 "score": 0.82, "distance_m": 150.0, "minutes": 4.0, "similarity": null,
                 "reasons": ["same_category", "within_radius", "within_window"], "matching_reports": 1},
  "transcripts": [{"media_id": "…", "kind": "audio", "text": "…", "language": "ar", "language_probability": 0.93,
                   "duration_s": 41.2, "translation_ar": null, "error": null, "model": "faster-whisper-large-v3"}],
  "models": {"transcribe": "faster-whisper-large-v3", "extract": "qwen3:8b", "translate_fr": "opus-mt-fr-ar", "embed": "e5-base"},
  "updated_at": "…"
}
```

- Priority components: `value` 0..1 (`null` = no data source yet, left out and the other weights
  rescaled), `weight` (settings), `points` (contribution; the points add up to the score).
  `lives.detail.source`: `model`, `keywords` or `category` (SOS/drowning without details).
- Credibility components (points): `base` 50, `registered` +15, `confirmed_false_reports` −15 each
  (max −45), `useful_reports` +5 each (max +15), `media` +10, `precise_location` +5 (≤ 50 m),
  `imprecise_location` −5 (> 1 km), `corroborated` +10 per other reporter (max +20).
- Step values: `done`, `skipped` (nothing to do), `failed` (input refused, not retried),
  `unavailable` (model down, retried), `disabled` (no AI service).
- Suggestion reasons: `same_category`, `sos_nearby`, `within_radius`, `within_window`, `similar_content`.

## 3. Incidents (FR-C-02, BR-10, BR-11)

Grouping rule (BR-10, tunable): same type (an SOS matches any type), closer than the type's radius
(fire 500 m, traffic accident 200 m, flood 2 km, …) and received within 60 min of each other; **or**
semantically close text (cosine ≥ 0.88) within 5 km and 3 h. Reports closed or rejected, and incidents not
open, are not proposed.

`IncidentSummary` = `{id, category, status: open|closed|merged|dissolved, gouvernorat_code,
centroid: {lat, lon} | null, severity (max priority of its reports), report_count, reporter_count,
opened_at, updated_at, closed_at, merged_into}`.

| endpoint | roles | effect |
|---|---|---|
| `GET /api/v1/staff/incidents?status=open&limit=50&cursor=` | read | newest activity first; `status` comma list or `all` |
| `GET /api/v1/staff/incidents/{id}` | read | summary + `reports: [StaffReport]` + `timeline: [{at, kind, actor, payload}]` |
| `POST /api/v1/staff/reports/{id}/incident` `{"action": "accept_suggestion"}` | write | follow the suggestion: join the incident, or create one with the suggested report |
| same with `{"action": "link", "incident_id": "…"}` | write | move the report into a chosen open incident |
| same with `{"action": "new"}` | write | start a new incident with this report |
| `DELETE /api/v1/staff/reports/{id}/incident` | write | split: take the report out (an empty incident becomes `dissolved`) |
| `POST /api/v1/staff/reports/{id}/suggestion/dismiss` | write | the suggestion is not proposed again |
| `POST /api/v1/staff/incidents/{id}/merge` `{"incident_id": "…"}` | write | the other incident's reports move here; it becomes `merged` |

The report endpoints answer `StaffReportDetail`; merge answers the target `IncidentDetail`.
An incident closes by itself when all its reports are closed or rejected, and reopens if one is reopened.
Timeline kinds: `created`, `report_linked` (`payload.via`: suggestion, manual, new), `report_unlinked`,
`merged_from`, `merged_into`, `closed`, `reopened`, `dissolved`. Every action is audited.
Errors: `404 not_found` (out of scope), `409 incident_not_open`, `409 no_suggestion`, `409 not_in_incident`,
`409 suggestion_outdated`, `422 incident_id_required`, `422 same_incident`, `422 invalid_status`.

BR-11 automatic grouping in the "disaster" operational level is not active yet: operational levels are
managed in a later phase (FR-C-24).

## 4. AI settings and status

- `GET /api/v1/staff/ai/settings` (read roles) → `{"priority": {"weights": {severity, lives, casualties,
  reporters, credibility, sensitive_sites, weather}, "category_severity": {<category>: 0..1},
  "suggestion_min_confidence": 0.7}, "grouping": {"window_min": 60, "radius_m": {<category>: m},
  "semantic_min_similarity": 0.88, "semantic_radius_m": 5000, "semantic_window_min": 180}}`
- `PUT /api/v1/staff/ai/settings` same body, roles `central_committee` (national scope) or `sysadmin`;
  `422` when incomplete or out of range, `403 national_scope_required`. Audited with before/after.
  New values apply to reports scored from then on.
- `GET /api/v1/staff/ai/status` (read roles) → `{"configured": false, "capabilities": {}}` or
  `{"configured": true, "capabilities": {"transcribe": {"ready", "model", "detail"}, "translate_fr", "translate_en",
  "embed", "extract"}}` (empty capabilities when the AI service does not answer).

## 5. Live events (`WS /api/v1/staff/live`, same protocol)

- `{"type": "report.enriched", "report": StaffReport}`: scores, translation, suggestion or incident changed.
- `{"type": "incident.updated", "incident": IncidentSummary}`.
Both are filtered by the user's geographic scope like the phase 2 events.

## 6. Internal AI inference service (`services/ai`, never exposed)

Called only by the API with `Authorization: Bearer <AI_SERVICE_TOKEN>`. Stateless: it does not touch the
database and holds no storage credentials (media are read through 30-minute pre-signed links to the
internal object store, the only URL prefix it accepts). All models run locally (NFR-10, NFR-11).

| endpoint | body → answer |
|---|---|
| `POST /v1/transcribe` | `{"url", "language": null}` → `{"text", "language", "language_probability", "duration_s", "segments": [{start, end, text}], "model"}` |
| `POST /v1/translate` | `{"texts": [...], "source": "fr"\|"en"}` → `{"texts": [...arabic], "model"}` |
| `POST /v1/embed` | `{"texts": [...]}` → `{"vectors": [[768 floats]], "dim": 768, "model"}` |
| `POST /v1/extract` | `{"text", "reported_category"}` → extraction (§2) + `"model"` |
| `GET /v1/health` | readiness of each capability |

Errors: `401 invalid_service_token`, `503 model_unavailable` (retry), `422 media_url_not_allowed`,
`422 media_fetch_failed`, `422 media_too_large`, `422 media_undecodable`, `422 audio_too_long`,
`502 invalid_model_output` (not retried).
