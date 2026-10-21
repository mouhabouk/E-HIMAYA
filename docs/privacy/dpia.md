# Data protection impact assessment (DPIA)

Phase 10, contract §7. **Draft for the platform owner and a lawyer.** It follows the usual structure (description,
necessity, risks, measures, residual risk). Law 2004-63 and the INPDP's procedures decide the final form.

## 1. Description

e-Himaya receives emergency reports from citizens (app, web, telephone, SMS), dispatches the Civil Protection,
mobilises volunteers, alerts the population and keeps the safety files of institutions. The processing activities
are listed in `processing-register.md`.

Why a DPIA is needed:
* location data of reporters and volunteers, sometimes in real time;
* images, video and call recordings of people in distress, possibly of minors or injured people;
* large scale (national), and people who cannot refuse in an emergency;
* automated analysis (AI ranking, vision detections) that influences the order in which reports are handled.

## 2. Necessity and proportionality

| Principle | How it is met |
|---|---|
| Purpose limitation | Reports are used for the response and for statistics after anonymisation only; no marketing, no profiling |
| Minimisation | Anonymous reporting is possible; IP addresses are not stored with reports; the staff map shows volunteers rounded to about 100 m; anonymised reports keep a 1 km grid |
| Accuracy | Reporters can complete their report; operators qualify it; AI suggestions are marked as suggestions |
| Storage limitation | Retention jobs coded per data type (register, last column) and run every hour |
| Rights | Access to one's own reports in the app; account deletion request (`POST /api/v1/me/delete`); consent withdrawal for the volunteer location; rewards are opt-in |
| Human decision | The AI only proposes a priority; rules rank the report and an operator decides; vision detections raise an alert to a person, never an action |

## 3. Risks

Likelihood and severity on a 1–4 scale, before the measures.

| # | Risk for the people | Source | L | S |
|---|---|---|---|---|
| R1 | Location of a reporter or volunteer disclosed (stalking, retaliation) | Data breach, staff curiosity, over-wide access | 2 | 4 |
| R2 | Images or recordings of victims leaked | Breach, export by staff | 2 | 4 |
| R3 | A false or manipulated alert reaches the population | Compromised staff account, mistake | 2 | 4 |
| R4 | A report is lost or delayed | Outage, overload, AI error ranking it low | 2 | 4 |
| R5 | A person is identified from anonymised statistics | Small cells, re-identification | 2 | 2 |
| R6 | Data kept longer than needed | Missing purge jobs | 3 | 2 |
| R7 | Transfer of device tokens outside Tunisia without authorisation | FCM | 4 | 1 |

## 4. Measures

| Risk | Measures (evidence in `docs/security/threat-model.md`) |
|---|---|
| R1 | Field encryption of locations; RLS and per-object authorisation by room; break-glass reading time-boxed and audited; volunteer position only with consent, rounded on the map, dropped on withdrawal |
| R2 | Media served through short-lived signed links from a sandboxed host; every access audited; evidence anchoring proves integrity without copying the media |
| R3 | MFA proven in the token; four eyes on population alerts; emergency override audited and acknowledged by another person; delivery failures reach a person |
| R4 | Intake does not depend on Valkey, NATS, the AI or Keycloak; outbox; backups with WAL every minute and a tested restore (RPO, RTO measured); monitoring with alerts; SLA timers on reports |
| R5 | Minimum cell size in analytics (`ANALYTICS_MIN_CELL`); 1 km grid after anonymisation |
| R6 | Retention jobs for reports, streams, calls, devices, consents, accounts. **Open**: no purge job yet for volunteer profiles, institution files and the audit log |
| R7 | Only the token and the alert text are sent; the owner must obtain the authorisation or choose a local channel |

## 5. Residual risk

| Risk | After the measures | Decision needed |
|---|---|---|
| R1, R2 | Low (L1, S4) | None beyond the external penetration test before launch |
| R3 | Low (L1, S4) | None |
| R4 | Low (L1, S4) | Run the restore drill each quarter on the real backups (`docs/runbooks/backup-restore.md`) |
| R5 | Low (L1, S2) | None |
| R6 | Medium (L3, S2) | Owner and lawyer set the retention of volunteer profiles, institution files and the audit log; the team then codes the jobs |
| R7 | Medium (L4, S1) | Owner decides: INPDP authorisation for FCM or a local push channel |

Opinion of the data protection contact and decision of the controller: to be added.
