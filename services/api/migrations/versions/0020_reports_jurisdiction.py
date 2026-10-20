"""Report jurisdiction, claim, SLA and escalation (phase 9, docs/api/phase-9-contract.md §4).

* ``reports.report`` gains the location assessment (``geo_state`` trusted/pending/contradictory/verified, candidate
  gouvernorats, reason, who verified it), the claim (``claimed_room`` central | g:<code>, by whom, when), the SLA band
  and due time, and the escalation state (late, central response, referral) with the referral target.
* ``reports.escalation`` — every step of a report's escalation (late, central claim, referral and its answer,
  geographic verification, claim release) with actor, time and reason.
* ``reports.reporter_context`` — the reporter's residence gouvernorat copied at creation (restricted: never used for
  scope, read only by the handling room or under break-glass).

Backfill (§9.4): located reports are ``trusted``; unlocated ones ``pending`` (candidates = gouvernorats within 25 km).
Reports past ``received`` are claimed by their gouvernorat's room (central when unlocated) by the first staff actor of
their history, at their first response. SLA band and due time are computed with the default settings; nothing is
escalated retroactively (``sla.enforced_since``). The reporter context comes from the profile of registered
reporters whose report is not anonymised.

Revision ID: 0020_reports_jurisdiction
Revises: 0019_identity_anon_quota
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0020_reports_jurisdiction"
down_revision: str | None = "0019_identity_anon_quota"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
ALTER TABLE reports.report
    ADD COLUMN geo_state text NOT NULL DEFAULT 'trusted',
    ADD COLUMN geo_candidates smallint[] NOT NULL DEFAULT '{}',
    ADD COLUMN geo_reason text,
    ADD COLUMN geo_verified_by text,
    ADD COLUMN geo_verified_at timestamptz,
    ADD COLUMN claimed_room text,
    ADD COLUMN claimed_by text,
    ADD COLUMN claimed_by_name text,
    ADD COLUMN claimed_at timestamptz,
    ADD COLUMN sla_band text,
    ADD COLUMN sla_due_at timestamptz,
    ADD COLUMN escalation_state text NOT NULL DEFAULT 'none',
    ADD COLUMN escalated_at timestamptz,
    ADD COLUMN referred_to smallint REFERENCES geo.gouvernorat (code),
    ADD CONSTRAINT ck_report_geo_state CHECK (geo_state IN ('trusted', 'pending', 'contradictory', 'verified')),
    ADD CONSTRAINT ck_report_claimed_room CHECK (claimed_room IS NULL OR claimed_room ~ '^(central|g:[0-9]{2})$'),
    ADD CONSTRAINT ck_report_sla_band CHECK (sla_band IS NULL OR sla_band IN ('critical', 'high', 'normal', 'low')),
    ADD CONSTRAINT ck_report_escalation_state CHECK (escalation_state IN (
        'none', 'late', 'central_responding', 'referred', 'referral_accepted', 'referral_refused'));

CREATE INDEX ix_report_sla_due ON reports.report (sla_due_at)
    WHERE claimed_room IS NULL AND status = 'received';
CREATE INDEX ix_report_escalation_state ON reports.report (escalation_state) WHERE escalation_state <> 'none';
CREATE INDEX ix_report_geo_state ON reports.report (geo_state) WHERE geo_state IN ('pending', 'contradictory');

CREATE TABLE reports.escalation (
    id           bigserial PRIMARY KEY,
    report_id    uuid NOT NULL REFERENCES reports.report (id) ON DELETE CASCADE,
    incident_id  uuid,
    kind         text NOT NULL,
    from_room    text,
    to_room      text,
    actor        text NOT NULL,
    actor_name   text,
    at           timestamptz NOT NULL DEFAULT now(),
    reason       text,
    -- What a step produced (e.g. the directive issued with a referral).
    payload      jsonb NOT NULL DEFAULT '{}',
    CONSTRAINT ck_escalation_kind CHECK (kind IN (
        'late', 'central_claim', 'referral', 'referral_accepted', 'referral_refused', 'geo_verified',
        'claim_released'))
);
CREATE INDEX ix_escalation_report ON reports.escalation (report_id, at);

CREATE TABLE reports.reporter_context (
    report_id                  uuid PRIMARY KEY REFERENCES reports.report (id) ON DELETE CASCADE,
    reporter_gouvernorat_code  smallint REFERENCES geo.gouvernorat (code),
    source                     text NOT NULL,
    CONSTRAINT ck_reporter_context_source CHECK (source IN ('profile', 'none'))
);

-- Backfill: location assessment.
UPDATE reports.report r
SET geo_state = 'pending',
    geo_reason = 'outside_boundaries',
    geo_candidates = COALESCE((
        SELECT array_agg(near.code ORDER BY near.distance)
        FROM (
            SELECT g.code, ST_Distance(g.boundary::geography, r.location) AS distance
            FROM geo.gouvernorat g
            WHERE g.boundary IS NOT NULL AND ST_DWithin(g.boundary::geography, r.location, 25000)
            ORDER BY distance
            LIMIT 3
        ) near
    ), '{}')
WHERE r.gouvernorat_code IS NULL;

-- Backfill: claim of the reports already handled.
UPDATE reports.report r
SET claimed_room = CASE WHEN r.gouvernorat_code IS NULL THEN 'central' ELSE 'g:' || lpad(r.gouvernorat_code::text, 2, '0') END,
    claimed_by = (
        SELECT h.actor FROM reports.status_history h
        WHERE h.report_id = r.id AND h.actor <> 'reporter'
        ORDER BY h.at, h.id LIMIT 1
    ),
    claimed_at = COALESCE(r.first_response_at, r.updated_at)
WHERE r.status <> 'received';

-- Backfill: SLA band and due time with the default settings (sos is always critical).
UPDATE reports.report r
SET sla_band = CASE
        WHEN r.category = 'sos' OR r.priority_score >= 85 THEN 'critical'
        WHEN r.priority_score >= 70 THEN 'high'
        WHEN r.priority_score IS NULL OR r.priority_score >= 40 THEN 'normal'
        ELSE 'low'
    END;
UPDATE reports.report r
SET sla_due_at = r.received_at + make_interval(secs => CASE r.sla_band
        WHEN 'critical' THEN 60 WHEN 'high' THEN 90 WHEN 'normal' THEN 120 ELSE 180 END);

-- Backfill: reporter context (restricted), from the profile of registered reporters.
INSERT INTO reports.reporter_context (report_id, reporter_gouvernorat_code, source)
SELECT r.id,
       CASE WHEN p.user_id IS NOT NULL AND a.kind <> 'anonymous' AND r.anonymised_at IS NULL
            THEN p.gouvernorat_code END,
       CASE WHEN p.user_id IS NOT NULL AND a.kind <> 'anonymous' AND r.anonymised_at IS NULL
            THEN 'profile' ELSE 'none' END
FROM reports.report r
JOIN identity.account a ON a.user_id = r.user_id
LEFT JOIN identity.profile p ON p.user_id = r.user_id;
"""

DOWNGRADE = r"""
DROP TABLE IF EXISTS reports.reporter_context;
DROP TABLE IF EXISTS reports.escalation;
DROP INDEX IF EXISTS reports.ix_report_geo_state;
DROP INDEX IF EXISTS reports.ix_report_escalation_state;
DROP INDEX IF EXISTS reports.ix_report_sla_due;
ALTER TABLE reports.report
    DROP CONSTRAINT IF EXISTS ck_report_escalation_state,
    DROP CONSTRAINT IF EXISTS ck_report_sla_band,
    DROP CONSTRAINT IF EXISTS ck_report_claimed_room,
    DROP CONSTRAINT IF EXISTS ck_report_geo_state,
    DROP COLUMN IF EXISTS referred_to,
    DROP COLUMN IF EXISTS escalated_at,
    DROP COLUMN IF EXISTS escalation_state,
    DROP COLUMN IF EXISTS sla_due_at,
    DROP COLUMN IF EXISTS sla_band,
    DROP COLUMN IF EXISTS claimed_at,
    DROP COLUMN IF EXISTS claimed_by_name,
    DROP COLUMN IF EXISTS claimed_by,
    DROP COLUMN IF EXISTS claimed_room,
    DROP COLUMN IF EXISTS geo_verified_at,
    DROP COLUMN IF EXISTS geo_verified_by,
    DROP COLUMN IF EXISTS geo_reason,
    DROP COLUMN IF EXISTS geo_candidates,
    DROP COLUMN IF EXISTS geo_state;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
