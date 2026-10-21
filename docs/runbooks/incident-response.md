# Incident response

Phase 10, contract §7. For outages and for security or personal-data incidents of the platform. It does not replace
the Civil Protection's operational procedures for the emergencies themselves (`docs/procedures/`).

## Severity

| Level | Meaning | Examples | Response |
|---|---|---|---|
| 1 | Citizens cannot reach help through the platform, or personal data is leaking now | `ApiDown`, `ReportIntakeErrors` on all instances; staff account used by an attacker; database exposed | At once, day and night; incident lead named within 15 minutes |
| 2 | Degraded, help still reaches people | `ReportIntakeSlow`, `OutboxBacklog`, `NotificationFailures`, `WalArchiveLag`, `BaseBackupMissing`, a failed restore drill; a suspected breach not confirmed | Within 1 hour in working hours, 4 hours otherwise |
| 3 | No effect on the response | `RateLimiterDegraded`, `SessionCheckDegraded` alone; a dependency audit finding | Next working day |

When in doubt, choose the higher level; lowering it later costs nothing.

## Roles

* **Incident lead**: decides, keeps the timeline, names the others. By default the on-call engineer; the head of IT
  for level 1.
* **Operations liaison**: tells the central room what works and what does not, and switches the rooms to the
  fallback (telephone 198, radio) when intake is down.
* **Communications**: the only person who speaks outside (public, press, INPDP), with the controller's approval.
* **Scribe**: notes every action with its time, in the incident record.

## The first hour

1. **Acknowledge** the alert in Alertmanager and open an incident record (time, alert, who).
2. **Protect people first**: if reports cannot be received, the operations liaison tells the rooms to rely on the
   telephone lines. The citizen app keeps reports offline and offers the SMS fallback and the emergency numbers.
3. **Look**: `docker compose -f infra/compose.prod.yml ps`, logs of `api`, `worker`, `postgres`, `caddy`; Prometheus
   for the failing rule; `/health/ready` for the dependencies.
4. **Contain**, depending on the case:
   * compromised staff account: disable it in the dashboard (accounts screen); this revokes its sessions at the next
     request. Rotate the secrets it could reach;
   * leaked secret: rotate it (`.env`, then restart the service); for the field encryption key, add a new version and
     run `python -m app.modules.privacy.cli reencrypt`; for the certificate or evidence key, rotate and keep the old
     public key in `CERTIFICATE_PREVIOUS_PUBLIC_KEYS`;
   * suspected tampering: `SELECT audit.verify_chain();` and `python -m app.modules.evidence verify`; do not
     change anything before copying the data aside;
   * data lost or corrupted: `backup-restore.md`.
5. **Keep evidence**: copy logs, the audit rows of the period, and the affected objects before any clean-up.
6. **Update** the central room every 30 minutes until the service is back.

## Personal data breach

A breach is any loss of confidentiality, integrity or availability of personal data (reports, locations, media,
identities).

1. The incident lead informs the controller (ONPC) and the data protection contact **at once**.
2. Assess: which data, how many people, whether it was encrypted (fields encrypted with AES-256-GCM are not readable
   without the key), the likely consequences.
3. Notify the INPDP **without delay** in the form and time the law and the INPDP require (the lawyer confirms the
   current rule; record the time of notification).
4. Inform the people concerned when the breach is likely to put them at risk (location of a reporter or volunteer,
   images of a victim): through the app, by SMS or by e-mail, in Arabic and French, saying what happened, what was
   done and whom to contact.
5. Record the breach in the breach register, even when no notification is needed, with the reason.

## Closing

* The service is back and stable for one hour, and the alerts have cleared.
* Write the post-mortem within 5 working days, without blame: timeline, cause, what worked, what did not, and
  actions with an owner and a date. Actions that change code go through review → redesign → develop.
* Review the threat model (`docs/security/threat-model.md`) when the incident shows a threat it missed.
