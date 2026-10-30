"""Runtime configuration, read from environment variables (see .env.example)."""

import base64
import binascii
import ipaddress
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.secrets_policy import production_problems


class Settings(BaseSettings):
    # hide_input_in_errors: a start-up error must never print the secrets it was given.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    # production: no /docs, /redoc or /openapi.json, and start-up refuses weak or example secrets
    # (app/core/secrets_policy.py). development (default): local stacks and tests.
    app_env: Literal["development", "production"] = "development"
    # Environment strip shown at the top of the app, the dashboard and the portal (backlog G3), so test data is never
    # taken for real. auto = "development" when APP_ENV=development, no strip in production. pilot and training keep
    # the strip on a production stack that holds test data (field pilot, tabletop exercise).
    environment_banner: Literal["auto", "development", "pilot", "training", "off"] = "auto"
    database_url: str = Field(description="postgresql+asyncpg://user:pass@host:5432/db")
    valkey_url: str | None = None
    nats_url: str | None = None

    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: SecretStr | None = None
    s3_bucket_media: str = "ehimaya-media"
    # Endpoint used in pre-signed URLs handed to browsers (defaults to s3_endpoint_url).
    s3_public_endpoint_url: str | None = None
    s3_region: str = "us-east-1"

    # Comma-separated list of accepted token issuers (public realm, staff realm).
    oidc_issuers: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Optional internal base URL used to fetch JWKS when the public issuer host is not reachable
    # from inside the cluster (e.g. issuer http://localhost:8080, internal http://keycloak:8080).
    oidc_jwks_base_url: str | None = None
    oidc_audience: str = "ehimaya-api"
    # A staff-realm token must prove a second factor in its ``amr`` claim (otp, hwk or mfa), phase 10 §1.1.
    # Turn off only for a staff realm whose flow does not set authentication references yet.
    staff_mfa_required: bool = True

    anon_pseudonym_secret: SecretStr = Field(min_length=32)
    # AES-256-GCM key for field-level encryption (personal data at rest): base64 of 32 random bytes. It is key
    # version 1 and the root of the blind indexes (CIN, phone, report search words), so it stays configured
    # after a rotation.
    field_encryption_key: SecretStr
    # Key rotation: further key versions "2:<base64>,3:<base64>" (2..255). New values are encrypted with the
    # active version (default: the highest configured); every listed version stays readable. After adding a
    # version run `python -m app.modules.privacy.cli reencrypt`, then retire the old one.
    field_encryption_keys: SecretStr | None = None
    field_encryption_active_version: int | None = Field(default=None, ge=1, le=255)
    # Version of the privacy charter every reporter must have accepted (FR-A-001).
    charter_version: str = "2026-11"
    # Shared secret tusd sends in the Authorization header of its hook calls (HTTP Basic, user "tusd", or
    # "Bearer <secret>"); the hook endpoint is disabled when unset.
    tusd_hook_secret: SecretStr | None = Field(default=None, min_length=24)
    # Background loops (outbox relay, media verification). Disabled in tests, which drive them directly.
    background_workers: bool = True
    # api: serve HTTP only, no background loop; worker: run the background loops and serve only /health and
    # /metrics (no SOS traffic); all: both (single-container development).
    process_role: Literal["api", "worker", "all"] = "all"
    # Bearer token of the Prometheus scraper; /metrics answers 404 while unset.
    metrics_token: SecretStr | None = Field(default=None, min_length=24)

    # Abuse controls (A1). Per-client-IP limits apply to anonymous device identities only (registered
    # citizens are limited per account); windows in seconds. Beyond the global anonymous budget, reports
    # are still accepted but flagged "needs verification" with a lowered priority.
    anon_identity_per_ip: int = Field(default=60, ge=1)
    anon_identity_window_s: int = Field(default=3600, ge=1)
    anon_report_per_ip: int = Field(default=60, ge=1)
    anon_report_window_s: int = Field(default=600, ge=1)
    anon_consent_per_ip: int = Field(default=60, ge=1)
    anon_device_per_ip: int = Field(default=120, ge=1)
    anon_report_budget: int = Field(default=300, ge=1)
    anon_report_budget_window_s: int = Field(default=600, ge=1)

    # Internal AI inference service (services/ai). Without it, reports are scored and grouped by rules only.
    ai_service_url: str | None = None
    ai_service_token: SecretStr | None = Field(default=None, min_length=24)
    # Long audio on a CPU-only server can take minutes to transcribe.
    ai_request_timeout_s: float = 900.0
    ai_concurrency: int = Field(default=2, ge=1, le=32)
    # Retries with back-off when a model is unavailable, then the analysis is marked failed.
    ai_max_attempts: int = Field(default=8, ge=1, le=50)

    # Institutions portal (FR-B-*): base of invitation links and of the certificate verification page.
    portal_public_url: str = "http://localhost:5174"
    # Ed25519 private key (base64 of the 32-byte seed) signing approved safety certificates (FR-B-008).
    # Without it certificates can be generated and submitted but not approved.
    certificate_signing_key: SecretStr | None = None
    # Key rotation (phase 10 §4.1): comma-separated base64 raw public keys of earlier signing keys. Certificates they
    # signed stay verifiable; nothing new is signed with them.
    certificate_previous_public_keys: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Evidence anchoring (phase 10 §4.3): Ed25519 key (base64 seed) signing the hourly anchors. Unset: the
    # certificate key signs them (with a warning); neither: anchors are sealed unsigned.
    evidence_signing_key: SecretStr | None = None
    # Optional RFC 3161 time-stamping authority asked to time-stamp each anchor hash. Its failures never block sealing.
    tsa_url: str | None = None
    tsa_timeout_s: float = Field(default=10.0, gt=0, le=60)

    # Notification channels (phase 5). Each one is optional: without its settings the channel is recorded
    # as "skipped" and the other channels still go out.
    # Firebase Cloud Messaging (Android, and iOS through APNs): the service-account JSON, base64-encoded.
    fcm_service_account: SecretStr | None = None
    # ┏━━ SIMULATION ━━ in development compose these two point at services/notify-sim (emulated FCM HTTP v1 + OAuth)
    # ┃ PRODUCTION: set FCM_SERVICE_ACCOUNT=<base64 of the key from Firebase console > Project settings > Service
    # ┃   accounts > Generate new private key>, FCM_API_URL=https://fcm.googleapis.com (the default here).
    # ┃   FCM_SERVICE_ACCOUNT wins over FCM_SERVICE_ACCOUNT_FILE; the defaults below are the production ones.
    # ┗━━━━━━━━━━━━━━━━
    # Path of the service-account JSON file, used when FCM_SERVICE_ACCOUNT is unset.
    fcm_service_account_file: Path | None = None
    # Base URL of the FCM HTTP v1 API.
    fcm_api_url: str = "https://fcm.googleapis.com"
    # SMS gateway of a Tunisian operator or aggregator: JSON POST {"to", "text", "sender"} with a bearer token.
    sms_http_url: str | None = None
    sms_http_token: SecretStr | None = None
    sms_sender: str = "E-HIMAYA"
    # Outgoing e-mail (Mailpit in development).
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "e-Himaya <no-reply@ehimaya.tn>"
    smtp_starttls: bool = True

    # Retention and anonymisation (law 2004-63, architecture §5.3), run by the worker role. Durations in days.
    retention_enabled: bool = True
    retention_interval_s: int = Field(default=3600, ge=60)
    # Domain events already relayed to the bus (the bus itself keeps 7 days).
    retention_events_days: int = Field(default=7, ge=1)
    # Individual pushes and e-mails once sent, skipped or failed.
    retention_notify_outbox_days: int = Field(default=30, ge=1)
    # Finished fan-out jobs of notifications and alerts (their delivery counters).
    retention_notify_dispatch_days: int = Field(default=180, ge=1)
    # Push devices not refreshed by the app for this long are forgotten; their rounded position earlier.
    retention_device_days: int = Field(default=180, ge=1)
    retention_device_location_days: int = Field(default=30, ge=1)
    # Positions of the vehicles from the team leaders' phones during their missions (phase P4d).
    retention_crew_position_days: int = Field(default=30, ge=1)
    # Closed or rejected reports are anonymised this long after their last change (5 years).
    retention_report_days: int = Field(default=1826, ge=1)
    # A medical file attached to a report (phase B2, addition 7b) is deleted this long after the report is closed.
    retention_medical_days: int = Field(default=30, ge=1)
    # Acceptances of a superseded charter, kept as proof while reports made under them are kept.
    retention_consent_days: int = Field(default=1826, ge=1)
    # Anonymous device identities that never reported and have no push device.
    retention_anon_account_days: int = Field(default=365, ge=1)
    # Erasure requests once the identity-provider account was disabled.
    retention_erasure_days: int = Field(default=30, ge=1)
    # Map layers and places deleted by the administrator (phase L1a): restorable for this long, then erased.
    retention_layer_deleted_days: int = Field(default=30, ge=1)
    # Anonymous "I am at this beach" rows (phase L1b): kept this many hours, only counts are ever read.
    retention_coastal_presence_hours: int = Field(default=24, ge=1)

    # Live streaming (phase 6, docs/streaming.md). MediaMTX authenticates every publisher and reader through
    # POST /internal/mediamtx/auth and reports the stream life cycle to POST /internal/mediamtx/hooks.
    # Public base of the WebRTC endpoints (WHIP for the app, WHEP for the dashboard): <base>/live/<id>/whip.
    stream_webrtc_public_url: str = "http://localhost:8889"
    # Public base of the HLS endpoints (dashboard fallback): <base>/live/<id>/index.m3u8.
    stream_hls_public_url: str = "http://localhost:8888"
    # Host name and ports fixed sources (drones, cameras) publish to over RTSP or RTMP.
    stream_ingest_host: str = "localhost"
    stream_rtsp_port: int = Field(default=8554, ge=1, le=65535)
    stream_rtmp_port: int = Field(default=1935, ge=1, le=65535)
    # Internal RTSP base the vision service reads streams from (with its own read credentials).
    stream_internal_rtsp_url: str = "rtsp://mediamtx:8554"
    # MediaMTX control API (kicking publishers). Unset: a stopped stream ends at its next reconnection only.
    mediamtx_api_url: str | None = None
    mediamtx_api_user: str = "ehimaya-api"
    mediamtx_api_password: SecretStr | None = Field(default=None, min_length=24)
    # Shared secret MediaMTX's hook script sends in X-Hook-Token; the hook endpoint answers 404 while unset.
    mediamtx_hook_token: SecretStr | None = Field(default=None, min_length=24)
    # Directory MediaMTX records fMP4 segments into (volume shared with the api and worker containers).
    stream_recordings_dir: Path = Path("/recordings")
    # A citizen's publish token must be used within this time; a stream then lasts at most stream_max_duration_s.
    stream_start_window_s: int = Field(default=600, ge=60, le=3600)
    stream_max_duration_s: int = Field(default=900, ge=60, le=7200)
    # Interval the app sends its position at while streaming (the API ignores calls closer than 3 s).
    stream_location_interval_s: int = Field(default=10, ge=3, le=300)
    # A staff viewer token must be used within this time (WHEP/HLS session start).
    stream_viewer_token_ttl_s: int = Field(default=300, ge=30, le=3600)
    # New live streams per citizen account per hour.
    stream_create_per_hour: int = Field(default=6, ge=1)
    # Segments no hook announced (MediaMTX restarted, API down) are picked up once untouched for this long.
    stream_segment_orphan_after_s: int = Field(default=600, ge=120)
    # ┏━━ SIMULATION ━━ token of the stream-sim service (compose profile "sim"), which registers a source=sim stream
    # ┃   through POST /internal/sim/streams and publishes a looped sample clip.
    # ┃ PRODUCTION: leave STREAM_SIM_TOKEN empty (APP_ENV=production refuses it); register real drones and cameras
    # ┃   with POST /api/v1/staff/streams (docs/streaming.md).
    # ┗━━━━━━━━━━━━━━━━
    stream_sim_token: SecretStr | None = Field(default=None, min_length=24)

    # Sensors of the local network (L5b, docs/phase-l/design-l5.md §3.0): the gateway beside MediaMTX relays their
    # signed readings to POST /internal/sensors/readings with this token (X-Gateway-Token); 404 while unset.
    sensor_gateway_token: SecretStr | None = Field(default=None, min_length=24)
    # Addresses the gateway may call from: the local network only, never the internet.
    sensor_gateway_networks: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "::1/128"]
    )

    # Vision service (services/vision, fire/smoke/person detector). Unset: streams and images are not analysed.
    vision_service_url: str | None = None
    # Bearer token the API presents to the vision service.
    vision_api_token: SecretStr | None = Field(default=None, min_length=24)
    # Token the vision service presents on POST /internal/vision/detections (X-Vision-Token); 404 while unset.
    vision_callback_token: SecretStr | None = Field(default=None, min_length=24)
    # Address of the detections callback as reached from the vision service.
    vision_callback_url: str = "http://api:8000/internal/vision/detections"
    # MediaMTX read password of the internal "vision" user (RTSP reads of every live path).
    vision_read_password: SecretStr | None = Field(default=None, min_length=24)
    # Detections below the first threshold are dropped; a fire or smoke at or above the second in 3 of the last
    # 5 analysed frames is confirmed (raises the priority, alerts the operators; never a public alert).
    vision_min_confidence: float = Field(default=0.45, ge=0, le=1)
    vision_alert_confidence: float = Field(default=0.6, ge=0, le=1)
    # A label confirmed on a stream is announced again only after this pause.
    vision_alert_cooldown_s: int = Field(default=300, ge=10)
    vision_request_timeout_s: float = Field(default=10.0, gt=0, le=120)
    # Retries with back-off when the vision service is unavailable, then an uploaded image stays unanalysed.
    vision_max_attempts: int = Field(default=8, ge=1, le=50)
    # Streams without a report (drones, cameras, simulation): recordings, track and detections kept this long
    # after the stream ended. Streams of a report follow the report (anonymised with it).
    retention_stream_days: int = Field(default=365, ge=1)

    # Telephony (phase 7, docs/telephony.md): Asterisk driven over ARI (HTTP + WebSocket events in the worker role).
    # Unset TELEPHONY_ARI_URL: the call endpoints answer 503 telephony_unavailable and no loop connects; SMS reports
    # (POST /internal/sms/inbound) work without it.
    telephony_ari_url: str | None = None
    telephony_ari_user: str = "ehimaya-api"
    telephony_ari_password: SecretStr | None = Field(default=None, min_length=16)
    telephony_ari_app: str = "ehimaya"
    # Handed to the dashboard softphone with its credentials: SIP over WebSocket URL (production:
    # wss://<API_HOST>/telephony/ws through Caddy), SIP domain of the URIs, ICE servers (comma-separated URLs).
    telephony_ws_public_url: str = "ws://localhost:8088/ws"
    telephony_sip_domain: str = "ehimaya.local"
    telephony_ice_servers: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Lifetime of an operator's SIP credentials; the softphone asks for new ones before they expire.
    telephony_credential_ttl_s: int = Field(default=14400, ge=300, le=86400)
    # Directory Asterisk's MixMonitor writes call recordings into (volume shared with the worker).
    telephony_recordings_dir: Path = Path("/telephony-recordings")
    # A SIP trunk is configured on the Asterisk side (TELEPHONY_TRUNK_HOST): outbound calls to the PSTN possible.
    telephony_trunk_enabled: bool = False
    # Scenario 2 (ADR-10): blind transfer to 198 through the trunk. Off by default (scenario 1: the operator calls 198).
    telephony_transfer_198_enabled: bool = False
    # Outbound calls per staff member per hour (contact from the map, invitations to a crisis room).
    telephony_dial_per_hour: int = Field(default=60, ge=1)
    # Calls are recorded (after the recorded-call notice) only when true; must match TELEPHONY_RECORDING_ENABLED of the
    # telephony container. Production: only once the processing is declared to the INPDP (legal point L04).
    telephony_recording_enabled: bool = True
    # Call records (metadata) and their recordings are deleted this long after the call ended: at most 2 years (L04).
    retention_call_days: int = Field(default=730, ge=1, le=730)
    # ┏━━ SIMULATION ━━ token of the smoke test / call-sim checks on GET /internal/sim/calls (calls with source=sim).
    # ┃ PRODUCTION: leave TELEPHONY_SIM_TOKEN empty (APP_ENV=production refuses it); the endpoint then answers 404.
    # ┗━━━━━━━━━━━━━━━━
    telephony_sim_token: SecretStr | None = Field(default=None, min_length=24)
    # SMS reports (FR-A-048): HMAC-SHA256 key shared with the SMS gateway that signs POST /internal/sms/inbound
    # (X-Signature: sha256=<hex> of "<X-Timestamp>.<body>"). Unset: the endpoint answers 404.
    sms_inbound_secret: SecretStr | None = Field(default=None, min_length=24)
    # Window in which an SMS report and the same report synced later by the app are merged (same 8-hex prefix,
    # category and sender), and in which a repeated SMS returns the existing report.
    sms_dedup_window_h: int = Field(default=48, ge=1, le=168)
    # Phase A sign-in by phone (docs/phase-a/design.md §2.2): HMAC-SHA256 key shared with the Keycloak provider
    # ehimaya-phone-otp, which signs POST /internal/auth/otp-sms like the SMS gateway does. Unset: 404.
    otp_sms_secret: SecretStr | None = Field(default=None, min_length=24)

    # Decision support (phase 7, docs/decision-support.md). Self-hosted routing engine (Valhalla on OpenStreetMap
    # Tunisia, compose profile "routing"). Unset or down: straight-line estimate answered with "engine": "fallback".
    routing_url: str | None = None
    routing_timeout_s: float = Field(default=5.0, gt=0, le=60)
    # Ollama server of the incident assistant (the local model of the AI layer, compose profile "ai"). Unset or model
    # not pulled: the assistant answers 503 assistant_unavailable; recommendations and routing still work.
    ollama_url: str | None = None
    assistant_model: str = "qwen3:4b"
    assistant_timeout_s: float = Field(default=120.0, gt=0, le=600)
    assistant_num_ctx: int = Field(default=8192, ge=2048, le=131072)
    # Assistant questions per staff member per hour.
    assistant_per_hour: int = Field(default=30, ge=1)
    # Procedures library (docs/procedures/*.ar.md, *.fr.md) indexed by the worker. Unset: the repository's
    # docs/procedures when present (development, tests); compose mounts it at /app/procedures.
    procedures_dir: Path | None = None

    # Weather layer and spread forecasts (phase 7, docs/weather-forecast.md).
    # ┏━━ SIMULATION ━━ WEATHER_PROVIDER=sim: a deterministic weather simulator feeds the grid (no network); it is the
    # ┃   default when APP_ENV=development (local stacks, CI, tests), so tests never call Open-Meteo.
    # ┃ PRODUCTION: WEATHER_PROVIDER=open-meteo (the default when APP_ENV=production, which refuses "sim"), and
    # ┃   WEATHER_API_URL=https://api.open-meteo.com, https://customer-api.open-meteo.com with WEATHER_API_KEY, a
    # ┃   self-hosted Open-Meteo or an INM feed exposing the same /v1/forecast interface.
    # ┗━━━━━━━━━━━━━━━━
    weather_provider: Literal["open-meteo", "sim"] | None = None
    weather_api_url: str = "https://api.open-meteo.com"
    # Commercial Open-Meteo API key (customer-api.open-meteo.com); unset for the free tier or a self-hosted server.
    weather_api_key: SecretStr | None = None
    # The worker refreshes the grid every interval; a point is fetched again only when its data is older than
    # weather_fetch_min_age_s, at most weather_max_points_per_cycle points per cycle (free tier: < 10 000 calls a day).
    weather_refresh_interval_s: int = Field(default=1800, ge=60)
    weather_fetch_min_age_s: int = Field(default=3600, ge=60)
    weather_max_points_per_cycle: int = Field(default=160, ge=1, le=5000)
    weather_batch_size: int = Field(default=50, ge=1, le=100)
    weather_request_timeout_s: float = Field(default=20.0, gt=0, le=120)
    # Days of past weather requested once for a new point, to spin up the fire weather moisture codes.
    weather_spinup_days: int = Field(default=30, ge=1, le=92)
    # Spacing of the grid laid over Tunisia on first start (degrees).
    weather_grid_step_deg: float = Field(default=0.25, ge=0.05, le=1.0)
    # A position farther than this from every grid point has no weather (km).
    weather_max_distance_km: float = Field(default=40.0, gt=0, le=200)
    # Coastal safety (phase L1b, docs/phase-l/design-l1b-coastal.md): the marine weather (waves, sea temperature,
    # current) of every beach of the beaches layer, from the Open-Meteo Marine API (or the same interface from INM),
    # and the daily drowning risk. The provider follows WEATHER_PROVIDER: the simulator ([SIM]) in development.
    marine_api_url: str = "https://marine-api.open-meteo.com"
    coastal_layer_key: str = "osm_beaches"
    coastal_refresh_interval_s: int = Field(default=3600, ge=60)
    coastal_max_beaches_per_cycle: int = Field(default=300, ge=1, le=5000)
    # Self-learning (docs/learning.md): seconds between two looks at the training queue and the schedule.
    learning_interval_s: int = Field(default=300, ge=30)
    # Terrain model (Copernicus DEM GLO-90) installed by the one-shot "terrain" job; absent: slope 0, stated.
    terrain_dir: Path = Path("/terrain")
    # Open satellite background and hybrid place names of the maps (docs/offline-maps.md). Unset: the public sources of
    # app/modules/basemap/domain.py (Sentinel-2 cloudless by EOX, CARTO place names). On a network without internet, the
    # Office's own map server (profile "maps"): BASEMAP_OPEN_TILES=https://API_HOST/maps/data/satellite/{z}/{x}/{y}.jpg
    # and BASEMAP_LABEL_TILES=https://API_HOST/maps/styles/ehimaya-labels/{z}/{x}/{y}.png (space-separated for several).
    basemap_open_tiles: str | None = None
    basemap_open_attribution: str | None = None
    basemap_open_max_zoom: int | None = Field(default=None, ge=1, le=22)
    basemap_label_tiles: str | None = None
    basemap_label_attribution: str | None = None
    basemap_label_max_zoom: int | None = Field(default=None, ge=1, le=22)

    # Analytics and reports (phase 8, docs/api/phase-8-contract.md §1). k-anonymity floor of exported documents: a
    # count below it is printed "<N" (never the exact value) in PDF and XLSX exports.
    analytics_min_cell: int = Field(default=5, ge=2, le=100)
    # Monte Carlo runs of a what-if scenario (at least 200, FR-C-12).
    analytics_scenario_runs: int = Field(default=200, ge=200, le=5000)
    # Worker loop "analytics": due scheduled reports and the generation queue are checked at this interval.
    analytics_interval_s: int = Field(default=60, ge=5, le=3600)
    # Longest period an overview, a trend or a document may cover.
    analytics_max_period_days: int = Field(default=1830, ge=31, le=7400)
    # Scenario runs per staff member per hour (each one replays hundreds of simulated days).
    analytics_scenarios_per_hour: int = Field(default=20, ge=1)

    # Rewards (phase 8, docs/api/phase-8-contract.md §3). Points per citizen and day (Africa/Tunis) from automatic
    # awards; rescues designated by staff and manual adjustments are not counted (safety rule T25).
    rewards_daily_cap: int = Field(default=200, ge=0, le=100_000)
    # Badge thresholds in points (FR-A-071); bronze shows at once, the others after a staff confirmation.
    rewards_badge_bronze: int = Field(default=100, ge=1)
    rewards_badge_silver: int = Field(default=500, ge=1)
    rewards_badge_gold: int = Field(default=2000, ge=1)
    rewards_badge_ambassador: int = Field(default=10000, ge=1)
    # Worker loop "rewards": outbox events and awards queued at level disaster are processed at this interval.
    rewards_interval_s: float = Field(default=5.0, ge=0.5, le=3600)
    # Public base of the API (QR of reward certificates → <base>/api/v1/rewards/certificates/<code>).
    # Production (compose.prod.yml): https://API_HOST.
    api_public_url: str = "http://localhost:8000"

    # Knowledge (phase 8, docs/api/phase-8-contract.md §2): events library search. OpenSearch 2 (security plugin on,
    # HTTPS with the installation's own CA, infra/opensearch) when SEARCH_BACKEND=opensearch and OPENSEARCH_URL is set;
    # otherwise, and whenever OpenSearch does not answer, PostgreSQL full-text search + pg_trgm (same response shape,
    # "backend": "postgres"). The worker loop "knowledge" keeps both indexes in line with the platform's data.
    search_backend: Literal["opensearch", "postgres"] = "opensearch"
    opensearch_url: str | None = None
    opensearch_user: str = "ehimaya"
    opensearch_password: SecretStr | None = Field(default=None, min_length=16)
    # CA certificate of the node (generated on first start into the opensearch-ca volume); unset: system CAs.
    opensearch_ca_file: Path | None = None
    # Indices are "<prefix>-<kind>-v<n>" behind the aliases "<prefix>-<kind>" and "<prefix>-library".
    opensearch_index_prefix: str = Field(default="ehimaya", pattern=r"^[a-z][a-z0-9-]{0,30}$")
    opensearch_timeout_s: float = Field(default=5.0, gt=0, le=60)
    # Library searches per staff member per minute.
    library_search_per_minute: int = Field(default=60, ge=1)

    # Central and regional rooms (phase 9, docs/api/phase-9-contract.md). Worker loop "sla-escalation": seconds
    # between passes marking unclaimed reports late (§4.4); delays and bands are national settings (/staff/settings).
    sla_interval_s: float = Field(default=5.0, ge=0.5, le=3600)
    # Regional account administration (§6.2): confidential client of the staff realm with a service account holding
    # realm-management manage-users/view-users. Unset URL = the accounts endpoints answer 502 identity_provider_error.
    keycloak_admin_url: str | None = None
    keycloak_admin_client_id: str = "ehimaya-account-admin"
    keycloak_admin_client_secret: SecretStr | None = Field(default=None, min_length=16)
    keycloak_staff_realm: str = "ehimaya-staff"
    # Real alert sending stays off (§7.4): enabling it needs the reference of the formal approval.
    notify_real_send: bool = False
    notify_real_send_approval_ref: str | None = Field(default=None, max_length=200)

    api_cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    api_log_level: str = "INFO"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    @field_validator("basemap_open_tiles", "basemap_label_tiles")
    @classmethod
    def _tile_templates(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        if not value:
            return None
        for template in value.split():
            placeholders = all(p in template for p in ("{z}", "{x}", "{y}"))
            if not template.startswith(("https://", "http://")) or not placeholders:
                raise ValueError("a tile address is an http(s) URL with {z}, {x} and {y}")
        return value

    @field_validator("field_encryption_key")
    @classmethod
    def _check_key(cls, value: SecretStr) -> SecretStr:
        # Fail at start-up rather than on the first encrypted write.
        try:
            raw = base64.b64decode(value.get_secret_value(), validate=True)
        except binascii.Error as exc:
            raise ValueError("FIELD_ENCRYPTION_KEY must be base64 (openssl rand -base64 32)") from exc
        if len(raw) != 32:
            raise ValueError("FIELD_ENCRYPTION_KEY must decode to 32 bytes (openssl rand -base64 32)")
        return value

    @field_validator("field_encryption_keys")
    @classmethod
    def _check_keyring(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        parse_keyring(value.get_secret_value())
        return value

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.app_env == "production":
            problems = production_problems(self)
            if self.stream_sim_token is not None:
                # SIMULATION: the stream simulator never runs in production.
                problems.append("STREAM_SIM_TOKEN must be empty (simulation only)")
            if self.weather_provider == "sim":
                # SIMULATION: simulated weather never feeds production decisions.
                problems.append("WEATHER_PROVIDER must not be sim (simulation only)")
            if self.telephony_sim_token is not None:
                # SIMULATION: the call simulator checks never run in production.
                problems.append("TELEPHONY_SIM_TOKEN must be empty (simulation only)")
            if not self.staff_mfa_required:
                # Phase 10 §1.1: staff accounts always prove a second factor in production.
                problems.append("STAFF_MFA_REQUIRED must be true")
            if self.notify_real_send and not (self.notify_real_send_approval_ref or "").strip():
                # Real alert sending needs a formal approval (phase 9 §7.4).
                problems.append("NOTIFY_REAL_SEND=true requires NOTIFY_REAL_SEND_APPROVAL_REF")
            if problems:
                raise ValueError("APP_ENV=production refuses weak or example secrets: " + "; ".join(problems))
        return self

    @model_validator(mode="after")
    def _check_active_version(self) -> "Settings":
        if self.field_encryption_active_version is not None:
            extra = parse_keyring(self.field_encryption_keys.get_secret_value()) if self.field_encryption_keys else {}
            if self.field_encryption_active_version not in {1, *extra}:
                raise ValueError("FIELD_ENCRYPTION_ACTIVE_VERSION names a key version that is not configured")
        return self

    @field_validator("certificate_signing_key", "evidence_signing_key")
    @classmethod
    def _check_signing_key(cls, value: SecretStr | None, info: ValidationInfo) -> SecretStr | None:
        if value is None:
            return None
        name = (info.field_name or "").upper()
        try:
            raw = base64.b64decode(value.get_secret_value(), validate=True)
        except binascii.Error as exc:
            raise ValueError(f"{name} must be base64 (openssl rand -base64 32)") from exc
        if len(raw) != 32:
            raise ValueError(f"{name} must decode to 32 bytes (openssl rand -base64 32)")
        return value

    @field_validator(
        "basemap_open_attribution",
        "basemap_open_max_zoom",
        "basemap_label_attribution",
        "basemap_label_max_zoom",
        "ai_service_url",
        "ai_service_token",
        "metrics_token",
        "tusd_hook_secret",
        "certificate_signing_key",
        "evidence_signing_key",
        "tsa_url",
        "field_encryption_keys",
        "field_encryption_active_version",
        "fcm_service_account",
        "fcm_service_account_file",
        "sms_http_url",
        "sms_http_token",
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "mediamtx_api_url",
        "mediamtx_api_password",
        "mediamtx_hook_token",
        "stream_sim_token",
        "vision_service_url",
        "vision_api_token",
        "vision_callback_token",
        "vision_read_password",
        "sensor_gateway_token",
        "telephony_ari_url",
        "telephony_ari_password",
        "telephony_sim_token",
        "sms_inbound_secret",
        "otp_sms_secret",
        "routing_url",
        "ollama_url",
        "procedures_dir",
        "weather_provider",
        "weather_api_key",
        "opensearch_url",
        "opensearch_password",
        "opensearch_ca_file",
        "keycloak_admin_url",
        "keycloak_admin_client_secret",
        "notify_real_send_approval_ref",
        mode="before",
    )
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        # Compose passes "" when the optional AI profile is not configured.
        return None if value == "" else value

    @field_validator("telephony_recording_enabled", mode="before")
    @classmethod
    def _recording_default(cls, value: object, info: ValidationInfo) -> object:
        # Empty in .env = the environment's default: recorded in development, not in production (INPDP, L04).
        if value == "" or value is None:
            return info.data.get("app_env") != "production"
        return value

    @field_validator("fcm_api_url", mode="before")
    @classmethod
    def _default_fcm_api_url(cls, value: object) -> object:
        # Compose passes "" when the variable is not set in .env.
        return "https://fcm.googleapis.com" if value == "" or value is None else value

    @field_validator(
        "portal_public_url",
        "api_public_url",
        "fcm_api_url",
        "stream_webrtc_public_url",
        "stream_hls_public_url",
        "stream_internal_rtsp_url",
        "mediamtx_api_url",
        "vision_service_url",
        "routing_url",
        "ollama_url",
        "telephony_ari_url",
        "telephony_ws_public_url",
        "weather_api_url",
        "marine_api_url",
        "opensearch_url",
        "keycloak_admin_url",
    )
    @classmethod
    def _strip_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else value

    @model_validator(mode="after")
    def _check_badge_thresholds(self) -> "Settings":
        levels = (
            self.rewards_badge_bronze,
            self.rewards_badge_silver,
            self.rewards_badge_gold,
            self.rewards_badge_ambassador,
        )
        if list(levels) != sorted(set(levels)):
            raise ValueError("REWARDS_BADGE_* thresholds must increase from bronze to ambassador")
        return self

    @model_validator(mode="after")
    def _check_vision_thresholds(self) -> "Settings":
        if self.vision_alert_confidence < self.vision_min_confidence:
            raise ValueError("VISION_ALERT_CONFIDENCE must be at least VISION_MIN_CONFIDENCE")
        return self

    @field_validator("sensor_gateway_networks", mode="before")
    @classmethod
    def _split_networks(cls, value: object) -> object:
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            for item in value:
                ipaddress.ip_network(item, strict=False)  # ValueError on anything that is not a network
        return value

    @field_validator("oidc_issuers", "api_cors_origins", "telephony_ice_servers", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]
        return value

    @field_validator("certificate_previous_public_keys", mode="before")
    @classmethod
    def _split_keys(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def search_engine(self) -> Literal["opensearch", "postgres"]:
        """The configured library search backend (PostgreSQL when OpenSearch is disabled or not configured)."""
        if self.search_backend == "opensearch" and self.opensearch_url and self.opensearch_password is not None:
            return "opensearch"
        return "postgres"

    @property
    def weather_source(self) -> Literal["open-meteo", "sim"]:
        """WEATHER_PROVIDER, defaulting to the simulator in development and to Open-Meteo in production."""
        if self.weather_provider is not None:
            return self.weather_provider
        return "open-meteo" if self.app_env == "production" else "sim"


def parse_keyring(value: str) -> dict[int, bytes]:
    """``"2:<base64>,3:<base64>"`` → {2: key, 3: key}; version 1 is FIELD_ENCRYPTION_KEY."""
    keys: dict[int, bytes] = {}
    for item in (part.strip() for part in value.split(",")):
        if not item:
            continue
        version_text, sep, encoded = item.partition(":")
        if not sep or not version_text.strip().isdigit():
            raise ValueError("FIELD_ENCRYPTION_KEYS entries are <version>:<base64 key>")
        version = int(version_text)
        if not 2 <= version <= 255 or version in keys:
            raise ValueError("FIELD_ENCRYPTION_KEYS versions are distinct numbers from 2 to 255")
        try:
            raw = base64.b64decode(encoded.strip(), validate=True)
        except binascii.Error as exc:
            raise ValueError("FIELD_ENCRYPTION_KEYS keys must be base64 (openssl rand -base64 32)") from exc
        if len(raw) != 32:
            raise ValueError("FIELD_ENCRYPTION_KEYS keys must decode to 32 bytes (openssl rand -base64 32)")
        keys[version] = raw
    return keys


@lru_cache
def get_settings() -> Settings:
    return Settings()
