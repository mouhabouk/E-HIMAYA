# Record of processing activities

Phase 10, contract §7. Law 2004-63 on the protection of personal data (Tunisia) and the declarations to the INPDP.
**Draft for the platform owner and a lawyer**: the legal bases below are the development team's reading and must be
confirmed before the declarations are filed.

Controller: Office national de la Protection civile (ONPC). Processor for hosting: to be named in the hosting
contract. Contact for the people concerned: the data protection contact named by the ONPC (to be filled in).

Retention durations are the defaults coded in `services/api/app/modules/privacy/retention.py` and
`app/modules/telephony/retention.py` (settings `RETENTION_*`); a shorter duration can be set per deployment, a
longer one needs a new legal analysis.

| # | Purpose | Legal basis (to confirm) | People | Data | Recipients | Retention |
|---|---|---|---|---|---|---|
| 1 | Receive and handle emergency reports (SOS, fire, flood…) | Public interest mission of the Civil Protection; vital interest | Reporters (anonymous device or signed-in citizen), people named in a report | Category, text, location (encrypted), media, device pseudonym, phone number when given, IP as a rate-limit key only | Operators of the room in charge, then the incident commanders; never published | Closed or rejected report: 5 years, then anonymised (text and media deleted, location rounded to 0.01°) |
| 2 | Emergency calls and SMS | Same as 1 | Callers, SMS senders | Number, time, duration, recording (when enabled), SMS text | Operators | 2 years (legal maximum coded as an upper bound) |
| 3 | Live streams from the scene (citizen, drone, camera) | Same as 1 | Publisher, people filmed | Video, track, frames analysed by the vision service | Operators, commanders | With the report (5 years, then deleted); streams without a report: 365 days |
| 4 | Volunteers: readiness, call-outs | Consent of the volunteer (registration, then a separate consent to share the position) | Volunteers | Identity, skills, availability, position while ready (only with the location consent) | Operators of the gouvernorat; the map shows the position rounded to 0.001° | Position: dropped on withdrawal of the consent or when readiness ends; profile: while registered (no purge job yet, see the DPIA) |
| 5 | Alerts to the population (push, SMS, e-mail) | Public interest mission | App users, subscribers | Device token, rounded position of the device, language | Push provider (FCM), SMS gateway, mail server | Device: 180 days without refresh; device position: 30 days; sent messages: 30 days; fan-out jobs: 180 days |
| 6 | Institutions: registration, safety registers, certificates | Legal obligation of the institution (safety rules) and public interest mission | Managers, safety team members, members of the portal | Names, roles, phone, e-mail, training records, documents | Civil Protection reviewers; the public sees only the certificate check (name of the institution, status) | While the institution is registered (no purge job yet, see the DPIA) |
| 7 | Rewards and badges of citizens | Consent (participation is optional) | Citizens who opt in | Points ledger linked to reports | The citizen only | The link to a report is cut when the report is anonymised |
| 8 | Consent records | Legal obligation (proof of consent) | All users who accepted the charter or a purpose | Version, time, locale, platform | None | 5 years after the version is superseded |
| 9 | Staff accounts and audit | Legal obligation (accountability), security | Staff | Identity, roles, room, sign-ins, every write action | Security administrators, auditors | Audit log: kept (append-only, hash-chained); a retention for it must be decided |
| 10 | Erasure requests | Legal obligation (rights of the people) | Citizens who ask | Account reference, dates | Security administrators | 30 days after the identity-provider account is disabled |
| 11 | Anonymous device identities | Same as 1 | App users without an account | Pseudonym, creation date | None | 365 days without a report or a device |

## Transfers outside Tunisia

* Push notifications go through Firebase Cloud Messaging (Google). Only the device token and the alert text leave
  the country. A transfer authorisation (INPDP) or a local alternative must be decided by the owner.
* Weather data is fetched from an external provider; no personal data is sent (grid points only).
* The AI and vision models run on the platform's own servers; no report content leaves the platform.

## Security measures

See `docs/security/threat-model.md` and `docs/security/asvs-l2.md`: field encryption, row-level security, audit
chain, MFA for staff, backups with a tested restore, evidence anchoring.
