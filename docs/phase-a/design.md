# Phase A: the citizen's first experience. Review and redesign

Scope approved by Yamen on 2026-10-23 (vision page, roadmap step A): additions 1, 2/7, 3, 4, 6 and 9, plus the four
cross-cutting rules. Institutions (6b, 12, 13), personal safety (5, 7b, 8, 10, 11) and the staff app (14, 15) are
later phases. Every database or code change below follows review → redesign → develop.

## 1. Review: what exists today

| Area | Today | File |
|---|---|---|
| First launch | charter (6 sections, version `2026-10`) → role (citizen / institution) → citizen mode (anonymous, or Keycloak page in the browser) → profile | `core/routing/app_router.dart` |
| Sign-in | Authorization Code + PKCE in the system browser, Keycloak default theme, username/email + password | `core/auth/oidc_client.dart` |
| Language | ar / fr / en, chosen only in Settings | `core/settings/settings_controller.dart` |
| Theme | Material 3 seeded from red `#B3261E`; light / dark / system in Settings | `core/ui/theme.dart` |
| Home | big SOS, Live button, list of actions (report, emergency numbers, track, tips, volunteer, rewards, institution), weather | `features/home/home_screen.dart` |
| Emergency numbers | 198, 190, 197, 193, constant, offline | `features/emergency/emergency_numbers.dart` |
| Permissions | asked at first use (location when reporting, notifications at start) | various |
| Updates | none: the app never learns that a newer version exists | — |
| Server | charter version must equal `CHARTER_VERSION`; profile holds an encrypted phone with `phone_verified_at`; SMS provider abstraction (HTTP gateway, `[SIM]` notify-sim in development); typed national settings editable in the dashboard | `services/api/app/modules/{identity,notify,settings}` |
| Moderation | none | — |

## 2. Redesign

### 2.1 First-launch flow (mobile)

`language → intro (5 cards) → terms (10 sections, version 2026-11) → permissions → sign-in → home`

* The language bar (ع · FR · EN) sits in the app bar of **every** screen (rule 1), including the four screens above.
* The emergency numbers stay reachable from every screen, before any account (unchanged guard rule).
* The charter becomes the terms of use of addition 7 (ten numbered sections, ar/fr/en). `CHARTER_VERSION` moves
  from `2026-10` to `2026-11`, so every existing user accepts the new text once. The accept button is enabled once
  the text has been scrolled to the end and the box is ticked. Settings → Terms of use shows the text, the version
  and the acceptance date.
* Permissions screen: four cards (location, notifications, SMS, contacts), each saying why and what happens
  without it. Location is requested here; notifications too. SMS needs no permission (the app opens a pre-filled
  message), contacts are requested when the user first adds an emergency contact (phase B).
* Location on every use (addition 4): a status strip on the home screen, green when location works, amber with a
  "Turn on" button when the service is off or permission is denied. SOS and the emergency numbers are never blocked.

### 2.2 Sign-in with phone number and SMS code (addition 6)

* Native screen: logo, Tunisian flag with a fixed `+216`, 8-digit field (mobile prefixes 2, 3, 4, 5, 9 checked
  before sending), "Send code", then a 6-digit code field with a 60 s resend timer. "Continue as guest" keeps the
  anonymous mode. "Institution account" keeps today's browser sign-in for institutions (account type choice is
  phase C). A light/dark switch and the language bar are on the screen.
* Keycloak stays the only token issuer. A new provider `ehimaya-phone-otp` (Java, Keycloak SPI) is bound to the
  **direct grant** flow of client `ehimaya-mobile` only:
  1. `grant_type=password`, `phone=+216XXXXXXXX`, no `otp` → the authenticator stores a salted SHA-256 of a random
     6-digit code with its expiry (5 min) and tries left (3) in Keycloak's single-use store (shared by the cluster,
     expires on its own; keys `ehimaya-otp:*`), asks the API to send the SMS, and answers
     `400 {"error":"otp_sent", "expires_in", "resend_after", "sms_simulated"}`. **No account is created at this
     step**, so a mistyped or someone else's number leaves nothing behind.
  2. Same request with `otp=123456` → code checked in constant time and removed; only then is the user found or
     created (username = the phone digits, attributes `phone_number` and `phone_number_verified=true`) and the tokens
     issued (access, refresh, id) as for any login. A wrong code answers `401 invalid_grant` with `tries_left`.
  * Implemented and verified (2026-10-23): the change from user attributes to the single-use store was made during
    development after review, to avoid creating accounts for numbers that never confirm.
  * Limits: one code per 60 s per phone, 5 codes per hour per phone, 3 tries per code; Keycloak brute-force
    protection stays on.
* The SMS leaves through the API: `POST /internal/auth/otp-sms`, HMAC-signed like `/internal/sms/inbound`
  (`X-Timestamp`, `X-Signature`, secret `OTP_SMS_SECRET`), body `{phone, code, locale}`. The API renders the text in
  the user's language and sends it with the existing SMS provider. In development the provider is the
  `[SIM]` notify-sim gateway, which shows the message in its inbox; production refuses to boot with a simulator.
* Token claims `phone_number` and `phone_number_verified` map to the profile: the profile form shows the verified
  number, and when the saved phone equals it `phone_verified_at` is filled (the phone stays encrypted with its hash).
* Public realm theme `ehimaya` for the remaining Keycloak pages (logo, colours, ar/fr/en).

### 2.3 Home screen (addition 9)

Top bar: logo, title, language bar, light/dark switch, notifications. Location strip. Hero: the existing SOS button
and a large "Report an incident" card. Emergency numbers as four square buttons with an icon and the number
(198 Civil Protection highlighted with the logo, 190 SAMU, 197 Police, 193 National Guard: kept as in the app,
Yamen 2026-10-23); a tap opens the dialler with the number, never an automatic call. Shortcuts grid (my reports,
track, live, tips, alerts, volunteer, rewards, institution, as today). Weather card. A fixed bar "Call 198 /
SOS message" above the navigation bar.

### 2.4 Update notice and in-place upgrade (addition 3)

* `GET /v1/app/version?platform=android&build=N` (public, cached 10 min) answers the latest version, the minimum
  supported build, release notes in ar/fr/en and the download channel: `server` (stage 1, a URL on our server) or
  `play` (stage 2, the store listing).
* Values come from a new national setting `app.release`, edited by the system administrator in the dashboard.
* The app checks at start and once a day: below the latest build it shows "What's new" with "Update" and "Later";
  below the minimum build the sheet cannot be dismissed (SOS and emergency numbers stay reachable).
* Data survives the upgrade because the package name and signing key stay the same and the local database migrates
  forward (drift `schemaVersion`). The signing and release guide is part of this phase's report.

### 2.5 Branding and themes (addition 1, addition 6)

* Logo of the Office in the app (launcher icon, intro, sign-in, home), the portal and the dashboard headers and the
  Keycloak theme.
* Default palette taken from the logo (navy, orange, green, red); other colour themes in Settings: red, blue, green.
  Light / dark / system on the screen and in Settings. Contrast checked (WCAG AA).

### 2.6 Cross-cutting rules

1. Language bar on every screen: one widget `LanguageBar` in every app bar (mobile), the existing menus in portal and
   dashboard stay.
2. Required fields: `RequiredLabel` (label + red asterisk + screen-reader "required") and a "* required" note at the
   top of each form. Mobile forms in this phase; the portal and dashboard forms too.
3. Accessibility: semantics on every new widget, 48 dp targets, text scale up to 200 % covered by widget tests,
   no meaning by colour alone.
4. No advertising and respectful language:
   * a test fails the build if an advertising or tracking SDK appears in `pubspec.lock`, `package-lock.json` or
     `uv.lock`; the terms say so;
   * module `moderation` in the API: normalised matching (Arabic diacritics and letter variants, Latin-script
     Tunisian, French, English, repeated letters, separators) against a built-in list plus terms added by the system
     administrator (setting `moderation.extra_terms`); used on profile names and other non-emergency free text, answer
     `422 offensive_text`; **never** on reports, SOS or report descriptions.

## 3. Database changes

No new table. One Alembic migration (`0031_phase_a_settings`) seeds two national settings:

| Key | Type | Default | Who changes it |
|---|---|---|---|
| `app.release` | object: `latest_version`, `latest_build`, `min_build`, `notes` {ar, fr, en}, `channel` (`server`/`play`), `download_url` | build 1, min build 1, empty notes, `server` | sysadmin |
| `moderation.extra_terms` | list of strings (≤ 500, each ≤ 64 chars) | `[]` | sysadmin |

`CHARTER_VERSION` becomes `2026-11` (configuration, no schema change). Keycloak keeps its own state: the code
hash, expiry and tries live in its single-use store (not in the database, not in user attributes) and are removed
once used or expired.

## 4. Simulation

Kept apart from the main code and marked `[SIM]` (amber banner in apps, `SIMULATION` comment header in code):
* SMS codes in development go to `notify-sim`; its inbox shows them. The mobile app shows an amber `[SIM]` strip on
  the code screen when the API reports a simulated SMS provider (`GET /v1/app/version` → `sms_simulated: true`,
  never true in production).
* No other simulation is needed for this phase.

## 5. Tests planned

* Java (JUnit): code generation, hashing, expiry, tries, rate limits, phone validation.
* API (pytest): `/v1/app/version`, `/internal/auth/otp-sms` (signature, rate limit, provider call), moderation
  normaliser and matcher, settings validation, charter version, phone claims to profile.
* Mobile (flutter test): flow guard order, language bar presence on every screen, terms scroll-to-accept, permission
  cards, phone validation and OTP screen, home emergency grid and dialler intent, update sheet (optional and
  mandatory), text scale 200 %, required asterisks.
* Integration: real Keycloak 26.8 with the provider jar (Docker), full phone sign-in against the API with notify-sim.
