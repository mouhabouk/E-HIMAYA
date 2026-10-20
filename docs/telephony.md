# الهاتف والرسائل القصيرة — دليل التشغيل / Telephony and SMS operator runbook

Phase 7 (docs/api/phase-7-contract.md §4 and the SMS part of §5, ADR-10). This page is for whoever runs the stack:
how calls flow, the four scenarios and what each one needs legally, ports and secrets, how to connect a Tunisian
operator's SIP trunk, how to enable scenario 2, the SMS gateway webhook, and what to check when something fails.

## 1. نظرة عامة / How it fits together

```
citizen phone ── PSTN ── operator SBC ── SIP trunk ──┐                 ┌─► ARI WebSocket (events) ─► API worker
call-sim [SIM] ── SIP (dev only) ────────────────────┼─► Asterisk 22 ──┤        └─ calls, live feed call.*
                                                     │   8000:          └◄─ ARI HTTP (API): operator endpoints,
dashboard softphone ── WSS (Caddy /telephony/ws) ────┘   notice → record      transfer, conferences, outbound
                                                         → queue
                     MixMonitor WAV ─► "telrecordings" volume ─► API worker: SHA-256 → S3 → reports.media
SMS gateway ── POST /internal/sms/inbound (HMAC) ─► API ─► report source=sms (dedup) ─► acknowledgement SMS
```

* **The emergency path never waits for the API.** A call to 8000 is answered, hears the recorded-call notice
  (Arabic, then French), is recorded (when enabled) and queued, all in the dialplan
  (`services/telephony/config/extensions.conf`). The API learns about it from ARI events (`EhimayaCall` user events
  and `ChannelDestroyed`) over one WebSocket held by one worker process (PostgreSQL advisory lock). If the API is
  down, calls are still queued, answered and recorded; on reconnection the API ends the calls whose channel vanished
  and recordings nobody announced become `untracked` calls (orphan scan every minute).
* **Operators** get short-lived SIP credentials (`POST /api/v1/staff/telephony/credentials`, 4 h, rotated on every
  request) for a WebRTC endpoint `op-<12 hex>` pushed into Asterisk over ARI (memory sorcery, nothing on disk); the
  same request puts the endpoint in the `operators` queue. Expired endpoints leave the queue and Asterisk (worker loop
  `telephony-endpoints`). The queue rings every free operator (`ringall`); each INVITE carries
  `X-EHimaya-Call-Id: <calls.id>` and `X-EHimaya-Queue: operators`.
* **Records.** `telephony.call`: caller number encrypted (`caller_number_enc`) with a blind index for exact lookups,
  times, operator, status, linked report/incident, recording. Staff without call access (local and central committees)
  see numbers masked except the last 2 digits, in the API and in the live feed.
* **Recordings** (`calls/<call_id>.wav` in S3, `reports.media kind=call_recording`) are downloaded through a 5-minute
  presigned link, audited (`call.recording.download`), by operators, ops managers and field commanders only.

## 2. Scenarios (ADR-10) and their legal conditions

| # | What happens | Built | Condition |
|---|---|---|---|
| 0 | The app's emergency numbers (198, 190, 197, 193) **always** open the phone's own dialer (`tel:198`): an ordinary call over the SIM and the operator network, never through the platform, never recorded. | Mobile app, phase 2 | None. Works without internet or servers. |
| 1 | The platform's number (8000 behind the trunk, or the dashboard softphone) reaches an e-Himaya operator; when the Civil Protection must act, **the operator calls 198 from their own phone** and relays. | This phase (default) | No agreement needed for routing; recording needs the INPDP declaration (§3). |
| 2 | Same as 1, plus a **"Transfer to 198" button**: blind transfer of the caller through the SIP trunk (`POST /api/v1/staff/calls/{id}/transfer-198`). | Code ready, **off** (`TELEPHONY_TRANSFER_198_ENABLED=false`) | **A signed agreement with the operator (and the Civil Protection) and a regulatory review (INTT).** Never enable it without both. |
| 3 | 198 itself routed to the state's centre with only metadata recorded by the platform. | Not built | **An agreement with the state** and regulatory review. |

Scenario 0 is not a fallback the platform controls: it is the rule for every emergency number in the app, so a
citizen reaches help even when the platform, the internet or this server is down. Nothing in this phase changes it.

## 3. Recording, notice and retention (legal point L04)

* Every call to 8000 first hears a **recorded-call notice, in Arabic then French**; recording (MixMonitor) starts only
  after it, then the call is queued. For outbound calls the called party hears the notice once they answer and the
  recording starts after it. The CI job `telephony` checks the order in the rendered dialplan.
* `TELEPHONY_RECORDING_ENABLED` (same value for the `api`/`worker` and `telephony` services): `false` removes
  MixMonitor entirely (calls get `recording_state=none`). Default: **true in development, false in production**
  (`compose.prod.yml`; an empty value in `.env` means the environment's default). Set it to true in production **only
  once the processing has been declared to the INPDP** (Instance nationale de protection des données personnelles,
  law 2004-63) and the notice text validated by the legal adviser. The notice itself plays in both cases.
* **Replacing the generated notice** (espeak-ng text-to-speech, generated at build time) with professional
  recordings: record both texts, convert to 8 kHz mono 16-bit PCM WAV
  (`sox in.wav -r 8000 -c 1 -b 16 notice-ar.wav`), and mount them read-only over the generated files:

  ```yaml
  # infra/compose.prod.yml, service telephony
  volumes:
    - ./telephony/sounds/notice-ar.wav:/var/lib/asterisk/sounds/ehimaya/notice-ar.wav:ro
    - ./telephony/sounds/notice-fr.wav:/var/lib/asterisk/sounds/ehimaya/notice-fr.wav:ro
  ```

  An optional `welcome.wav` in the same folder is played after the notice when present.
* **Retention:** call metadata and recordings are deleted 2 years after the call (`RETENTION_CALL_DAYS`, default 730,
  refused above 730), inbound SMS records and retired operator endpoints too (privacy retention jobs `calls`,
  `sms_inbound`, `operator_endpoints`).
* **Citizen rights:** `GET /api/v1/me/export` lists the calls from/to the citizen's **verified** phone and the
  emergency SMS they sent; `POST /api/v1/me/delete` removes the number from those calls and SMS (calls and recordings
  stay, without the link to the person, until their retention ends).

## 4. Ports and firewall

| Port | Who | Production |
|---|---|---|
| 443/tcp `wss://API_HOST/telephony/ws` | dashboard softphones (through Caddy; only this path of Asterisk is routed) | open |
| 5060/udp, 5060/tcp, 5061/tcp (TLS) | the operator's SBC (SIP trunk) | **restrict to the operator's SBC addresses** in the host firewall; SIP scanners hit 5060 within minutes |
| `TELEPHONY_RTP_START`–`TELEPHONY_RTP_END`/udp (default 10000–10099, ~50 simultaneous calls) | trunk media and softphone media (DTLS-SRTP) | open (UDP) |
| 8088/tcp (ARI + WebSocket) | the API only | never published (`127.0.0.1` in development, internal network in production) |

`TELEPHONY_EXTERNAL_HOST` is the address Asterisk announces in SDP and ICE (public IP or a name resolving to it;
production default `API_HOST`). Behind NAT, forward the SIP and RTP ports 1:1. Softphones outside the server's
network may need a TURN server (`TELEPHONY_ICE_SERVERS=turn:turn.example.tn:3478?transport=udp,...`).

## 5. Secrets and settings

| Setting | Where | Notes |
|---|---|---|
| `TELEPHONY_ARI_PASSWORD` | api, worker, telephony | `openssl rand -hex 24`; Asterisk refuses to start without it (≥ 16 characters) |
| `TELEPHONY_TRUNK_*` | telephony | §6 |
| `TELEPHONY_TRUNK_ENABLED` | api, worker | `true` once the trunk works: outbound calls and invitations go through it |
| `TELEPHONY_TRANSFER_198_ENABLED` | api, worker, telephony | scenario 2, §7 |
| `TELEPHONY_RECORDING_ENABLED` | api, worker, telephony | §3 |
| `SMS_INBOUND_SECRET` | api | §8 |
| `TELEPHONY_SIM_PASSWORD`, `TELEPHONY_SIM_TOKEN` | development only | empty in production (the API refuses the token there) |

## 6. Connecting an operator's SIP trunk (Tunisie Telecom, Ooredoo, Orange Tunisie)

All three offer SIP trunks to businesses ("SIP Trunk" / "Trunk SIP" offers of their enterprise divisions). Ask the
operator for, and write into `.env`:

| Ask the operator | Setting |
|---|---|
| SBC address and port, transport (UDP, TCP or TLS) | `TELEPHONY_TRUNK_HOST`, `TELEPHONY_TRUNK_PORT`, `TELEPHONY_TRUNK_TRANSPORT` |
| Authentication: by IP only, or digest username/password (with or without REGISTER) | `TELEPHONY_TRUNK_USERNAME`, `TELEPHONY_TRUNK_PASSWORD`, `TELEPHONY_TRUNK_REGISTER=true` when they require registration |
| SIP domain/realm if different from the SBC address; the source addresses their calls come from | `TELEPHONY_TRUNK_DOMAIN`, `TELEPHONY_TRUNK_MATCH` (comma-separated IPs/CIDRs) |
| Number format they expect on outbound calls: `+216XXXXXXXX`, `00216XXXXXXXX` or the 8 national digits | `TELEPHONY_TRUNK_NUMBER_FORMAT=e164`, `00` or `national` |
| The DID(s) assigned to the platform and the presented number allowed on outbound calls | `TELEPHONY_TRUNK_CALLER_ID` |
| Codecs (G.711 A-law is the norm in Tunisia) and SRTP | `TELEPHONY_TRUNK_CODECS=alaw,ulaw`, `TELEPHONY_TRUNK_MEDIA_ENCRYPTION=sdes` if they offer SRTP |
| The number to dial for 198 through the trunk (scenario 2 only) | `TELEPHONY_TRUNK_198_NUMBER` |

Every DID arriving from the trunk goes to 8000 (`[ehimaya-trunk-in]`). For SIP over TLS, put the certificate chain and key as
`tls.crt` and `tls.key` in `infra/telephony/certs/` (readable by uid 10001) and uncomment the certificate volume of the `telephony` service: the TLS
transport (5061) is rendered only when both files exist. Then:

```bash
docker compose --env-file .env -f infra/compose.yml -f infra/compose.prod.yml up -d telephony
docker compose ... exec telephony asterisk -C /run/asterisk/etc/asterisk.conf -rx "pjsip show registrations"  # when REGISTER
docker compose ... exec telephony asterisk -C /run/asterisk/etc/asterisk.conf -rx "pjsip show endpoint trunk"
```

Test with a call from a mobile phone to the DID: it must hear the notice and ring the logged-in softphones; then set
`TELEPHONY_TRUNK_ENABLED=true` for the API and test an outbound call from the dashboard (Tunisian numbers only; the API
refuses others with `422 invalid_number`, and short codes such as 198 are never dialled from the dashboard).

## 7. Enabling scenario 2 (transfer to 198)

Only after **(1) the signed agreement with the operator and the Civil Protection** and **(2) the regulatory review**:

1. Agree with the operator on the number or route that reaches the 198 centre through the trunk
   (`TELEPHONY_TRUNK_198_NUMBER`) and test it with them outside production.
2. Set `TELEPHONY_TRANSFER_198_ENABLED=true` for the api, worker **and** telephony services (the dialplan checks it
   again), with a working trunk (`TELEPHONY_TRUNK_HOST` and `TELEPHONY_TRUNK_ENABLED=true`).
3. Restart; the credentials response now says `transfer_198_enabled: true` and the dashboard shows the button. Each
   transfer is audited (`call.transfer_198`). If the trunk refuses it, the caller goes back to the queue and the
   operator sees the call ringing again.

## 8. SMS reports (FR-A-048)

With no data connection the app prepares an SMS `EH1 <category> <lat>,<lon> <acc>m <uuid8>` (accuracy in whole metres,
rounded up, `0m` = unknown; `uuid8` = the first 8 hex digits of the report's `client_uuid`). The operator's SMS gateway
posts every received SMS to `POST https://API_HOST/internal/sms/inbound` (the only `/internal` path Caddy routes):

```
X-Timestamp: <unix seconds>
X-Signature: sha256=<hex HMAC-SHA256(SMS_INBOUND_SECRET, "<X-Timestamp>.<raw body>")>
{"message_id":"…","from":"+216XXXXXXXX","to":"…","text":"EH1 fire 36.80650,10.18150 12m 3f2a9c1d","received_at":"…"}
```

Signatures older than 5 minutes are refused (401). The answer is always 200 for a validly signed message: `created`
(a report `source=sms`, the sender receives its tracking code by SMS), `duplicate` (gateway retry, the same SMS again,
or the app already synced it) or `ignored` with a reason (`unparseable`, `rate_limited` after 10 SMS per sender per
hour, …). **Deduplication never relies on the 8-hex prefix alone**: an SMS and an app report are the same report only
with the same prefix AND category, within `SMS_DEDUP_WINDOW_H` (48 h), AND the same sender when it is a citizen with a
verified phone (otherwise within 5 km). When the SMS arrives first, the app's later sync adopts that report (one
report, one tracking code). No message text is stored, only keyed hashes, the prefix, the category and the sender's
number encrypted (for call-backs).

## 9. Simulation (development)

`docker compose --env-file .env -f infra/compose.yml --profile sim up -d` starts `call-sim`, a second Asterisk that
calls 8000 every `CALL_SIM_INTERVAL_S` seconds (source `sim`, caller `+21620001xxx`) and plays a generated prompt for
`CALL_SIM_TALK_S` seconds; it also answers the dashboard's outbound calls and invitations while there is no trunk.
Log in to the dashboard as an operator, open the softphone and answer. A call by hand:

```bash
docker compose --env-file .env -f infra/compose.yml exec telephony \
  asterisk -C /run/asterisk/etc/asterisk.conf -rx "channel originate Local/8000@ehimaya-sim-in application Wait 30"
```

## 10. Troubleshooting

| Symptom | Check |
|---|---|
| Calls endpoints answer 503 `telephony_unavailable` | `TELEPHONY_ARI_URL`/`TELEPHONY_ARI_PASSWORD` of the api; `docker compose logs telephony`; worker log `telephony.ari_disconnected` |
| No call appears in the dashboard | worker log `telephony.ari_connected`; `asterisk -rx "queue show operators"` |
| Softphone does not register | browser console; `asterisk -rx "pjsip show endpoint op-…"` (expired credentials are removed); the dashboard CSP needs `CSP_TELEPHONY_SRC=wss://API_HOST` |
| One-way or no audio | `TELEPHONY_EXTERNAL_HOST`, RTP range open in UDP, a TURN server for remote operators |
| Recording `missing` | `TELEPHONY_RECORDING_ENABLED`, the `telrecordings` volume mounted in both telephony and worker (owner 10001) |
| Calls refused by the trunk | `asterisk -rx "pjsip set logger on"` (SIP traces in the container log; contains numbers: personal data) |

Versions: Asterisk 22.11.0 LTS (GPL-2.0, built from the official release tarball pinned by SHA-256, with the bundled
pjproject 2.17), base image `ubuntu:26.04` pinned by digest. Asterisk runs as a separate process the API talks to over
HTTP/WebSocket only (no GPL code linked into the API). Updates: new 22.x tarball + SHA-256 in
`services/telephony/Dockerfile`, then the CI job `telephony` and the Trivy scan.
