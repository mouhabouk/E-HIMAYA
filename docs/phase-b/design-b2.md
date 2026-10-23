# Phase B2: personal safety. Review and redesign

Status: B2 started on Yamen's go-ahead of 2026-10-23 ("yes, continue B2 with full professionalism"). It details
section 3 of `design.md`, which Yamen approved, together with additions 5, 7b, 8 and 11. One point is still open for
Yamen (section 9). Every database change follows review, then redesign, then development.

## 1. Review: what exists today

| Area | Today | File |
|---|---|---|
| SOS | The button sends an `sos` report to the operations room. It needs two taps, or a long press. Without network it falls back to an SMS to the platform or a call to 198. | `features/sos`, `features/report/sms_fallback.dart` |
| Personal emergency contacts | None. | |
| Pushes to one account | `notify.outbox` sends a content-free push to the account's devices with retries; the app then fetches the content. It cannot use the critical channel. | `notify/outbox.py`, `notify/delivery.py` |
| Critical channel (rings through silent mode) | Android opt-in exists since phase 5, but only public alerts use it. | `core/push/push_notifications.dart` |
| Alert delivery check, battery guidance (8.6) | A settings screen lists what blocks alerts (notifications, Do Not Disturb, full screen, battery). | `features/settings/alert_check.dart` |
| Positions | Foreground only. The position stream works only while the screen is open, and there is no foreground service. | `core/location/location_service.dart` |
| Medical data | **Mismatch with addition 7b.** `identity.profile.medical_enc` is an encrypted server column, accepted by `PUT /me/profile`. No screen fills it and no staff screen shows it. Addition 7b says the medical file lives on the phone only. | `identity/router.py` |
| Local database | SQLCipher, schema version 1, with no migration step yet. It holds only the report queue and media. | `core/db/app_database.dart` |
| Account deletion (8.11), contact us and bug report (8.9) | Done in phases A and B1. | `features/privacy`, `features/contact` |
| Native bridge | Battery level, Do Not Disturb, battery optimisation and channel settings. There is no contact picker and no app shortcuts. | `MainActivity.kt`, `core/platform/device_services.dart` |

## 2. What B2 delivers

| # | Feature | Where the data lives |
|---|---|---|
| 5 | **Emergency contacts and groups**: up to 10 contacts, chosen with the system contact picker (no contacts permission, no address-book upload), in named groups. | Phone only (encrypted local database). |
| 5, 11.3 | **SOS message**: editable template plus position link, accuracy, time and battery, with a 5-second cancel window that can be turned off. Channels, in order: in-app alert to linked contacts, then SMS, then WhatsApp. | Template and history on the phone. In-app alert on the server (section 4). |
| 8.3, 11.1, 11.2 | **Linked contacts and critical alert**: two e-Himaya users are linked by an invitation code that the other person accepts. The alert rings through silent mode on Android. The receiver's screen shows the message, position, battery, live tracking, route, call, SMS, WhatsApp and "report to 198 on their behalf". | Only the link and the alert are on the server. |
| 8.4 | **Live location**: a random link that ends by itself (default 1 h, from 15 min to 8 h) and can be stopped at any time. It opens a light page in the portal with the moving point. | Server: the last points of the share, encrypted, deleted 24 h after the end. |
| 8.1 | **Safety check**: the user sets a time. Reminders come 10 min and 1 min before. If the user has not pressed "I am fine" by then, the **server** sends the alert to the linked contacts with the last position, even if the phone is off. It does not alert the operations room. | Server: the timer and its last position, deleted 7 days after it ends. |
| 8.5 | **Self-test**: the alarm sound on the critical channel, the position on the map, network, permissions and battery. Nothing is sent to anyone. | Phone. |
| 8.7 | **Recent alerts**: time, channels and recipients of each SOS message or safety check. | Phone only. |
| 8.2 | **App shortcuts** on a long press of the icon: "Call 198", "SOS message" and "Quick report". | Phone. |
| 7b | **Medical file**: optional fields, its own consent, and an optional fingerprint lock. It can be deleted in one tap. It is **attached to a report only when the user ticks the box for that report**, shared as a QR code or text, or shown in the hub. | Phone only. When attached: `reports.medical_attachment`, encrypted, deleted 30 days after the report closes. |
| 7b | **Location history, 72 h**: off by default, with a visible notification while on. An operator may read it only after a missing-person report, with a reason; each access is audited and the user is notified. | Server, encrypted, deleted after 72 h. **Platform switch off until the legal decision (section 9).** |

Kept for later (proposals): a home-screen widget (8.2: needs a native widget), a choice of alarm sound (8.8: needs
recorded sounds), the Play rating (8.10: Play build only), and sending the SMS without a tap (addition 5: needs the
`server` build flavour of addition 3 and `SEND_SMS`). Today the SMS app opens pre-filled with every recipient and the
user presses Send.

## 3. Phone: local database (schema 1 → 2)

The first drift migration step, with a test that opens a version-1 file and checks that its queued reports survive.

| Table | Content |
|---|---|
| `emergency_contacts` | id, display name, phone (`+216…` or international), group ids, position, linked account link id (null if not linked), created/updated |
| `contact_groups` | id, name, position |
| `alert_history` | id, kind (`sos_message` / `safety_check` / `test`), time, channels used, recipients count, server alert id, status |
| `medical_profile` | one row: sex, birth date, blood group, treatment card number, allergies, chronic conditions, regular medicines, other (pregnancy, device, disability), nearest contact id, consent version and date, lock on/off, updated |

The SOS template and the cancel-window switch are kept in preferences. No table is sent to the server, except the
medical file when the user attaches it to a report.

## 4. Server: database (migration 0037, schema `safety`)

| Table | Content |
|---|---|
| `safety.invitation` | id, inviter, SHA-256 of the code (never the code itself), expires (48 h), accepted by and when, cancelled |
| `safety.link` | id, user A, user B (ordered pair, unique), created. A link works both ways. Either side removes it for both. |
| `safety.alert` | id, client uuid (idempotent), sender, kind (`sos` / `check`), message (encrypted), position and accuracy (encrypted), battery, live share id, created, expires (24 h) |
| `safety.alert_recipient` | alert, recipient account, delivered, seen |
| `safety.live_share` | id, owner, SHA-256 of the token, started, expires, stopped, last points (encrypted, at most 120), updated |
| `safety.check` | id, owner, due at, message (encrypted), last position (encrypted), status (`active` / `ok` / `fired` / `cancelled`), alert id, created |

Rules:

- Row-level security reads by owner and by the subject:
  - an account sees its own invitations, links, shares and checks, plus the alerts it sent or received;
  - staff scopes see **nothing** in `safety` (it is private, between citizens);
  - the system scope is used only by the worker and by the public live-share view.
- Only registered accounts can link. A guest has no stable identity to notify.
- Limits:
  - 5 open invitations per account;
  - 10 code tries per hour;
  - 20 links per account;
  - 10 alerts per hour;
  - one active safety check per account.
- Retention jobs:
  - alerts are deleted 7 days after they are sent;
  - live shares are deleted 24 h after they end;
  - checks are deleted 7 days after they end;
  - unused invitations are deleted 7 days after they expire.
- Account deletion removes the account's links, shares, checks and alerts (cascade).
- Settings:
  - `safety.live_max_minutes` (480);
  - `safety.check_max_hours` (24).

## 5. Server: medical file attached to a report (migration 0038)

- `reports.medical_attachment`: the report, the data (encrypted JSON with the 7b fields), and when it was attached. It
  is visible only to staff who can see the report, by the same row-level security as the report.
- `POST /api/v1/reports` accepts an optional `medical` object. The queue keeps it encrypted on the phone until the
  report is sent.
- `GET /api/v1/staff/reports/{id}/medical` returns it. **Each opening is audited** (`report.medical_view`). The
  incident screen shows only "Medical file attached" and a button to open it.
- Deleted 30 days after the report is closed (`retention.medical_days`), when the report is anonymised, and when the
  account is erased.
- `identity.profile.medical_enc` is **retired** to match 7b. `PUT /me/profile` no longer stores it (sending it gives
  `410 medical_moved_to_phone`). A user who already has one can still read it in "my data" or erase it by sending
  `medical: null`. A later migration drops the column once no row holds data. No data is deleted without its owner's
  action.

## 6. Server: location history (migration 0039)

- `safety.location_point`: owner, time, position (encrypted), accuracy. Consent is the `location_history` purpose in
  `identity.consent`, with the version of the 7b text.
- `PUT /api/v1/safety/history` turns it on (hours ≤ 72) or off. Turning it off deletes every point at once.
  `POST /api/v1/safety/history/points` adds points in batches.
- Staff: `POST /api/v1/staff/safety/history/search` takes the person's phone, a missing-person report the operator
  can see, and a reason. It returns the points of the last 72 h. It is audited, and the person gets a push and an
  inbox message ("your location history was consulted by Civil Protection for report …").
- Allowed roles: operations manager and dispatcher, in the report's scope.
- **The platform setting `safety.location_history` is `off` by default.** The API refuses with
  `403 feature_off` and the app hides the switch until a system administrator turns it on after the legal review.

## 7. API (all under `/api/v1`)

| Endpoint | Use |
|---|---|
| `POST /safety/invitations` | Creates a code `XXXX-XXXX` (Crockford base 32, 48 h). The phone shares it by SMS or WhatsApp. |
| `GET /safety/invitations/{code}` | Preview: the inviter's first name and the last 2 digits of their phone. |
| `POST /safety/invitations/{code}/accept` | Creates the link. Both sides get a push. |
| `GET /safety/links`, `DELETE /safety/links/{id}` | Lists links as id, first name and phone of the other party (which both accept by linking), and removes a link. |
| `POST /safety/alerts` | Sends an SOS or test alert to all linked contacts or to chosen ones. Critical push. Idempotent by `client_uuid`. |
| `GET /safety/alerts/{id}`, `POST /safety/alerts/{id}/seen` | The receiver's screen and the read receipt. The sender sees "seen by n". |
| `POST /safety/live`, `PUT /safety/live/{id}`, `POST /safety/live/{id}/stop` | Live location share: start, position and battery, and stop. |
| `GET /safety/live/{id}` | A linked receiver follows a share attached to an alert. |
| `POST /live/view` (public, token in the body) | The portal page reads the share without an account. The token is sent in the body so it never appears in access logs. 30 requests per minute per address. |
| `POST /safety/checks`, `POST /safety/checks/{id}/ok`, `POST /safety/checks/{id}/extend`, `PUT /safety/checks/{id}/position` | The safety check. |

A worker in the existing delivery loop fires due safety checks and purges expired rows.

## 8. Screens

- **App:**
  - a "Personal safety" section in Settings and in the emergency hub: emergency contacts and groups, SOS message, linked
    contacts (invite, enter a code), live location, safety check, self-test, recent alerts, medical file (with its
    consent), and location history (shown only when switched on);
  - an "SOS message" button beside "Call 198" on the home screen;
  - the receiver's full-screen alert;
  - in the report form, the box "Attach my medical file to this report", unticked by default.
- **Dashboard:**
  - "Medical file attached" with its audited opening in the incident detail;
  - the location-history search page (hidden while the feature is off);
  - the two new settings.
- **Portal:** `/live#<token>` shows the map with the moving point, its accuracy, the last update, the end time, and
  "for an emergency call 198". No name is shown.

## 9. Decision for Yamen

**Location history (72 h):** I recommend building it now with the platform switch off. The system administrator turns
it on only after the Office's legal service approves the 7b text, and after the processing is declared to the national
personal data authority (INPDP). The other choice is to postpone it entirely.

## 10. Simulation

- iPhone: ringing through silent mode needs Apple's Critical Alerts entitlement in the Office's name. Until then the
  alert uses the "time sensitive" level, and the screen shows the amber `[SIM]` note.
- Without Firebase (test builds), pushes go through the existing simulated push. The `[SIM]` banner is already shown.
- No invented contacts or positions are shipped. The tests build their own.

## 11. Tests planned

- **API:**
  - invitations: expiry, single use, tries limit, own code;
  - links both ways, and removal;
  - alert to chosen recipients only, idempotency, rate limit;
  - receiver access only;
  - a critical push is queued;
  - live share: expiry, stop, public view by token, wrong token, no name;
  - safety check: fires once at the due time, "I am fine" cancels, extend;
  - row-level security: staff cannot read `safety`;
  - retention;
  - medical attachment: stored encrypted, audited view, outside scope refused, deleted after closing;
  - profile medical refused;
  - location history: feature off, consent, 72 h purge, staff search audited and notified.
- **App:**
  - local migration 1 → 2;
  - contacts and groups;
  - SOS message text, recipients, SMS and WhatsApp links, cancel window;
  - invitation flow;
  - receiver screen;
  - live share timer;
  - safety check reminders;
  - medical file consent, lock and delete;
  - attachment to a report.
- **Dashboard:** the attached medical file and its audit, the history search, the settings.
- **Portal:** the live page (active, ended, wrong token).
