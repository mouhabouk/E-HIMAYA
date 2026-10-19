<!--
┏━━ SIMULATION ━━ notify-sim: development emulator of Firebase Cloud Messaging HTTP v1 (OAuth) and the SMS gateway
┃ PRODUCTION: follow "Switching to production" below: real FCM_SERVICE_ACCOUNT, FCM_API_URL, SMS_HTTP_URL,
┃   SMS_HTTP_TOKEN in .env, then remove the notify-sim service and the notifysim volume from infra/compose.yml.
┗━━━━━━━━━━━━━━━━
-->
# notify-sim: channels simulator (development and tests only)

> **SIMULATION.** Nothing that goes through notify-sim reaches a real phone. It is never deployed to production.

`services/notify-sim` stands in for the two external delivery channels of phase 5, so the whole notification
path (outbox → API providers → channel → phone) can be exercised on a laptop and in CI without Google or an
operator account:

| Emulates | Endpoint | Used by |
|---|---|---|
| Google OAuth 2.0 token endpoint (JWT-bearer grant of a service account) | `POST /oauth2/token` | `FcmPush` |
| Firebase Cloud Messaging HTTP v1 | `POST /v1/projects/{project}/messages:send` | `FcmPush` |
| HTTP SMS gateway of a Tunisian operator/aggregator | `POST /sms/send` | `HttpSms` |
| Inspection (tests, inbox page, mobile simulated push) | `GET`/`DELETE /api/messages`, `GET /healthz`, `GET /` | developers, tests, mobile app |

The API runs **its real provider code** against it: the only difference with production is the configuration.
E-mail is not part of it (Mailpit already catches e-mail at http://localhost:8025).

## Running it

It starts with the development stack (`docker compose --env-file .env -f infra/compose.yml up -d --build`) on
http://localhost:8090. The API waits for it to be healthy and is wired to it by default:

| API variable | Default in compose (simulator) |
|---|---|
| `FCM_SERVICE_ACCOUNT_FILE` | `/run/notify-sim/fcm-service-account.json` (volume `notifysim`, read-only) |
| `FCM_API_URL` | `http://notify-sim:8090` |
| `SMS_HTTP_URL` | `http://notify-sim:8090/sms/send` |
| `SMS_HTTP_TOKEN` | `sim-sms-token` |

Outside compose: `cd services/notify-sim && uv sync && SIM_DATA_DIR=./data SIM_PUBLIC_URL=http://localhost:8090
uv run uvicorn --factory app.main:create_app --port 8090`, then point the API at `./data/fcm-service-account.json`
and `http://localhost:8090`.

Simulator settings (`SIM_` prefix): `SIM_DATA_DIR` (default `/data`), `SIM_FCM_PROJECT` (`ehimaya-sim`),
`SIM_PUBLIC_URL` (`http://notify-sim:8090`, becomes the `token_uri` of the service account), `SIM_SMS_TOKEN`
(`sim-sms-token`; compose passes `SMS_HTTP_TOKEN`), `SIM_SMS_FAIL_NUMBERS` (compose default `+21698000000`).

## Behaviour

**Service account.** On first start it generates an RSA-2048 key and writes `SIM_DATA_DIR/fcm-service-account.json`
in the exact shape of a Google service account (`client_email notify@ehimaya-sim.iam.gserviceaccount.com`). The key
is kept across restarts; project id and `token_uri` follow the current settings. The file is mode 0600, owned by
uid 10001 (the API image runs as the same uid).

**OAuth.** The assertion must be RS256-signed with that key, `iss` = `client_email`, `aud` = `token_uri`, `scope`
containing `https://www.googleapis.com/auth/firebase.messaging`, `exp` in the future and `exp - iat ≤ 3600`.
Answer: `{"access_token": "sim-at-…", "expires_in": 3600, "token_type": "Bearer"}`, otherwise
400 `{"error": "invalid_grant", "error_description": …}`.

**FCM send.** 401 `UNAUTHENTICATED` without a valid access token, 404 `NOT_FOUND` for another project, 400
`INVALID_ARGUMENT` (with a `fieldViolations` entry) when the message is not what FCM accepts: not exactly one of
`token`/`topic`/`condition`, unknown fields, non-string `data` values or reserved `data` keys (`from`, `google*`,
`gcm*`…), `android.priority` other than `normal`/`high`, non-string `apns.headers`. A token starting with
`sim-unregistered` gets FCM's 404 `UNREGISTERED`, which the API turns into `unregistered=True` (device deleted).
`validate_only: true` is checked but not stored.

**SMS.** Bearer token required (401 `unauthorized`). `to` must match `^\+216[2-9][0-9]{7}$` (400 `invalid_number`),
`text` non-empty and at most 1000 characters (400 `invalid_text`), `sender` 1–11 characters (400 `invalid_sender`).
Numbers in `SIM_SMS_FAIL_NUMBERS` get 503 `operator_unavailable`. Success:
`{"id", "segments", "encoding"}` with GSM-7 (160 characters, then 153 per part; `€[]{}^~|\` count twice) or UCS-2
for anything else, e.g. Arabic (70, then 67 per part).

**Inspection.** `GET /api/messages?channel=push|sms&token=&to=&after=&limit=` (limit 1–200, default 50) returns
`{"items": [...], "last_seq"}`, oldest first, only `seq > after`. Pass `last_seq` back as `after` to poll: it is the
last item of a full page, otherwise the newest sequence number. `seq` starts from the start-up time in milliseconds,
so it keeps increasing across restarts and `DELETE /api/messages` (204). The last 1000 messages are kept in memory.

## Inbox

Open http://localhost:8090. Every push and SMS received, newest first, refreshed every 3 seconds; filter by
channel, clear everything, switch the labels between Arabic (RTL) and French (LTR). Message texts are shown with
their own direction (`dir="auto"`). Alerts (`ehimaya_alerts`) have a red edge. The amber striped band
"وضع المحاكاة · Mode simulation — not real deliveries" is always visible. The page is a single self-contained file
(no external assets) served with a strict Content-Security-Policy.

## Testing tips

- Push to a device that has gone: register the token `sim-unregistered-<anything>`.
- SMS operator outage: send to `+21698000000` (or any number listed in `SIM_SMS_FAIL_NUMBERS`).
- Mobile app without Firebase: build with `--dart-define=PUSH_SIMULATOR_URL=http://10.0.2.2:8090` (Android
  emulator); the app registers a `sim-<uuid>` token and polls `/api/messages?channel=push&token=…`.
- Tests: `services/notify-sim/tests` cover the simulator itself; `services/api/tests/test_notify_sim.py` runs the
  API's `FcmPush` and `HttpSms` against the simulator in-process (`httpx.ASGITransport`, no network).

## Switching to production

Each step matches a `┏━━ SIMULATION ━━` banner in the code.

1. **Firebase key**: Firebase console > Project settings > Service accounts > Generate new private key. In `.env`:
   `FCM_SERVICE_ACCOUNT=$(base64 -w0 key.json)` (it wins over `FCM_SERVICE_ACCOUNT_FILE`). Keep the JSON file out of
   the repository.
2. **FCM endpoint**: `FCM_API_URL=https://fcm.googleapis.com` in `.env`. Mandatory: left empty, compose sends
   pushes to the simulator.
3. **SMS**: `SMS_HTTP_URL` and `SMS_HTTP_TOKEN` from the SMS provider contract, `SMS_SENDER` set to the registered
   sender name.
4. **Compose** (`infra/compose.yml`): delete the `notify-sim` service, the `notifysim:/run/notify-sim:ro` volume
   line and the `notify-sim` `depends_on` entry of `api`, and the `notifysim` volume. Remove `SIM_SMS_FAIL_NUMBERS`
   from `.env`.
5. **Smoke test**: run `NOTIFY_SIM_URL= python3 infra/smoke/smoke_test.py` (skips the simulator check).
6. **Mobile**: build without `PUSH_SIMULATOR_URL` and with the real Firebase configuration of the app.
7. **Check**: send a test notification from the dashboard and confirm the push on a real device and the SMS
   delivery report at the provider; nothing should appear at http://localhost:8090 any more.
