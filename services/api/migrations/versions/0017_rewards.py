"""Rewards (phase 8, docs/api/phase-8-contract.md §3): points ledger, rules, badges, nominations, certificates.

* ``rewards.rule`` — configurable points per reason (FR-A-070), with optional per-category overrides. The four
  defaults (verified +50, helped rescue +500, accurate category ×1.5, volunteer mission +100) are seeded here.
* ``rewards.points_ledger`` — append-only: a trigger refuses every UPDATE except the detachment of a deleted report,
  incident or rule (foreign keys ``ON DELETE SET NULL``, retention). Rows are deleted only with the account (erasure).
  ``dedup_key`` makes every automatic award idempotent.
* ``rewards.pending_award`` — automatic awards queued while their gouvernorat is at operational level ``disaster``.
* ``rewards.badge_award`` — bronze/silver/gold/ambassador (FR-A-071); silver and above wait for a staff decision.
* ``rewards.nomination`` — annual distinctions (FR-C-20); anonymised when the subject's account is erased.
* ``rewards.certificate`` — signed certificate (Ed25519) of a confirmed badge or approved nomination, publicly
  verifiable by code (initials, distinction and date only).
* ``rewards.consumer_cursor`` — position of the rewards consumer in ``events.outbox``.

The runtime role's grants on the new schema come from the grants re-applied after every upgrade (migrations/env.py,
app/core/db_roles.py).

Revision ID: 0017_rewards
Revises: 0016_knowledge
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0017_rewards"
down_revision: str | None = "0016_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
CREATE SCHEMA IF NOT EXISTS rewards;

CREATE TABLE rewards.rule (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reason       text NOT NULL,
    category     text,
    points       integer,
    multiplier   numeric(4, 2),
    enabled      boolean NOT NULL DEFAULT true,
    is_default   boolean NOT NULL DEFAULT false,
    description  jsonb NOT NULL DEFAULT '{}',
    updated_at   timestamptz NOT NULL DEFAULT now(),
    updated_by   text,
    CONSTRAINT ck_rule_reason CHECK (
        reason IN ('report_verified', 'report_helped_rescue', 'accurate_category', 'volunteer_mission')),
    CONSTRAINT ck_rule_value CHECK (
        (reason = 'accurate_category' AND points IS NULL AND multiplier BETWEEN 1 AND 3)
        OR (reason <> 'accurate_category' AND multiplier IS NULL AND points BETWEEN 0 AND 5000)),
    CONSTRAINT ck_rule_default CHECK (NOT is_default OR category IS NULL)
);
CREATE UNIQUE INDEX ux_rule_reason_category ON rewards.rule (reason, COALESCE(category, ''));

INSERT INTO rewards.rule (reason, points, multiplier, is_default, description) VALUES
    ('report_verified', 50, NULL, true,
     '{"ar": "بلاغ موثّق بعد غلق التدخل", "fr": "Signalement vérifié à la clôture de l''intervention"}'),
    ('report_helped_rescue', 500, NULL, true,
     '{"ar": "بلاغ ساهم في إنقاذ (يحدده الأعوان)", "fr": "Signalement ayant aidé un sauvetage (désigné par le personnel)"}'),
    ('accurate_category', NULL, 1.5, true,
     '{"ar": "تصنيف دقيق للبلاغ", "fr": "Catégorie choisie exacte"}'),
    ('volunteer_mission', 100, NULL, true,
     '{"ar": "مهمة تطوع منجزة", "fr": "Mission bénévole accomplie"}');

CREATE TABLE rewards.points_ledger (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    citizen_id       uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    delta            integer NOT NULL,
    reason           text NOT NULL,
    report_id        uuid REFERENCES reports.report(id) ON DELETE SET NULL,
    intervention_id  uuid REFERENCES ops.incident(id) ON DELETE SET NULL,
    rule_id          uuid REFERENCES rewards.rule(id) ON DELETE SET NULL,
    multiplier       numeric(4, 2),
    -- The daily cap reduced this award (delta may then be 0).
    capped           boolean NOT NULL DEFAULT false,
    -- Idempotency of automatic awards: <reason>:<citizen>:<incident|report>:<id>.
    dedup_key        text UNIQUE,
    revokes_id       bigint UNIQUE REFERENCES rewards.points_ledger(id) ON DELETE CASCADE,
    note             text,
    created_by       text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_ledger_reason CHECK (reason IN ('report_verified', 'report_helped_rescue', 'accurate_category',
        'volunteer_mission', 'manual', 'revocation')),
    CONSTRAINT ck_ledger_revocation CHECK ((reason = 'revocation') = (revokes_id IS NOT NULL)),
    CONSTRAINT ck_ledger_manual CHECK (reason NOT IN ('manual', 'revocation') OR created_by IS NOT NULL)
);
CREATE INDEX ix_ledger_citizen ON rewards.points_ledger (citizen_id, created_at DESC, id DESC);
CREATE INDEX ix_ledger_report ON rewards.points_ledger (report_id) WHERE report_id IS NOT NULL;
CREATE INDEX ix_ledger_created ON rewards.points_ledger (created_at);

CREATE FUNCTION rewards.ledger_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- Only the detachment of a deleted report, incident or rule (ON DELETE SET NULL, retention) is allowed.
    IF NEW.id = OLD.id AND NEW.citizen_id = OLD.citizen_id AND NEW.delta = OLD.delta AND NEW.reason = OLD.reason
       AND NEW.multiplier IS NOT DISTINCT FROM OLD.multiplier AND NEW.capped = OLD.capped
       AND NEW.dedup_key IS NOT DISTINCT FROM OLD.dedup_key AND NEW.revokes_id IS NOT DISTINCT FROM OLD.revokes_id
       AND NEW.note IS NOT DISTINCT FROM OLD.note AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
       AND NEW.created_at = OLD.created_at
       AND (NEW.report_id IS NULL OR NEW.report_id = OLD.report_id)
       AND (NEW.intervention_id IS NULL OR NEW.intervention_id = OLD.intervention_id)
       AND (NEW.rule_id IS NULL OR NEW.rule_id = OLD.rule_id) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'rewards.points_ledger is append-only' USING ERRCODE = 'restrict_violation';
END
$$;
CREATE TRIGGER trg_ledger_append_only BEFORE UPDATE ON rewards.points_ledger
    FOR EACH ROW EXECUTE FUNCTION rewards.ledger_append_only();

CREATE TABLE rewards.pending_award (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    citizen_id        uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    reason            text NOT NULL,
    points            integer NOT NULL,
    report_id         uuid REFERENCES reports.report(id) ON DELETE SET NULL,
    intervention_id   uuid REFERENCES ops.incident(id) ON DELETE SET NULL,
    rule_id           uuid REFERENCES rewards.rule(id) ON DELETE SET NULL,
    multiplier        numeric(4, 2),
    dedup_key         text NOT NULL UNIQUE,
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    queued_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_pending_reason CHECK (
        reason IN ('report_verified', 'report_helped_rescue', 'accurate_category', 'volunteer_mission'))
);
CREATE INDEX ix_pending_citizen ON rewards.pending_award (citizen_id);
CREATE INDEX ix_pending_gouvernorat ON rewards.pending_award (gouvernorat_code, id);

CREATE TABLE rewards.badge_award (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    citizen_id        uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    level             text NOT NULL,
    status            text NOT NULL,
    balance_at_award  integer NOT NULL,
    awarded_at        timestamptz NOT NULL DEFAULT now(),
    decided_at        timestamptz,
    decided_by        text,
    reason            text,
    CONSTRAINT ck_badge_level CHECK (level IN ('bronze', 'silver', 'gold', 'ambassador')),
    CONSTRAINT ck_badge_status CHECK (status IN ('pending', 'confirmed', 'rejected', 'revoked')),
    CONSTRAINT ux_badge_citizen_level UNIQUE (citizen_id, level)
);
CREATE INDEX ix_badge_status ON rewards.badge_award (status, awarded_at, id);

CREATE TABLE rewards.nomination (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind              text NOT NULL,
    subject_kind      text NOT NULL,
    -- identity.account user id (citizen, volunteer) or org.organization id; NULL once anonymised.
    subject_id        uuid,
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    year              smallint NOT NULL,
    reason            text,
    evidence          jsonb NOT NULL DEFAULT '{"report_ids": [], "intervention_ids": []}',
    status            text NOT NULL DEFAULT 'proposed',
    proposed_by       text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    decided_by        text,
    decided_at        timestamptz,
    decision_reason   text,
    anonymised_at     timestamptz,
    CONSTRAINT ck_nomination_kind CHECK (
        (kind = 'vigilant_citizen' AND subject_kind = 'citizen')
        OR (kind = 'brave_volunteer' AND subject_kind = 'volunteer')
        OR (kind = 'leading_institution' AND subject_kind = 'org')),
    CONSTRAINT ck_nomination_status CHECK (status IN ('proposed', 'approved', 'rejected')),
    CONSTRAINT ck_nomination_year CHECK (year BETWEEN 2020 AND 2100)
);
CREATE UNIQUE INDEX ux_nomination_subject ON rewards.nomination (kind, subject_id, year)
    WHERE status <> 'rejected' AND subject_id IS NOT NULL;
CREATE INDEX ix_nomination_list ON rewards.nomination (created_at DESC, id DESC);

CREATE TABLE rewards.certificate_counter (
    year  smallint PRIMARY KEY,
    last  integer NOT NULL
);

CREATE TABLE rewards.certificate (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code              text NOT NULL UNIQUE,
    kind              text NOT NULL,
    badge_award_id    uuid UNIQUE REFERENCES rewards.badge_award(id) ON DELETE SET NULL,
    nomination_id     uuid UNIQUE REFERENCES rewards.nomination(id) ON DELETE SET NULL,
    subject_kind      text NOT NULL,
    subject_id        uuid,
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    distinction       text NOT NULL,
    initials          text NOT NULL,
    year              smallint NOT NULL,
    issued_at         timestamptz NOT NULL DEFAULT now(),
    issued_by         text NOT NULL,
    signature         bytea NOT NULL,
    pdf_object_key    text,
    pdf_sha256        text,
    revoked_at        timestamptz,
    revoked_by        text,
    revoked_reason    text,
    CONSTRAINT ck_certificate_kind CHECK (kind IN ('badge', 'nomination')),
    CONSTRAINT ck_certificate_distinction CHECK (
        distinction IN ('gold', 'ambassador', 'vigilant_citizen', 'brave_volunteer', 'leading_institution')),
    CONSTRAINT ck_certificate_code CHECK (code ~ '^EHR-[0-9]{2}-[0-9]{6}-[0-9A-F]{4}$')
);
CREATE INDEX ix_certificate_subject ON rewards.certificate (subject_id) WHERE subject_id IS NOT NULL;
CREATE INDEX ix_certificate_list ON rewards.certificate (issued_at DESC, id DESC);

CREATE TABLE rewards.consumer_cursor (
    name        text PRIMARY KEY,
    last_id     bigint NOT NULL DEFAULT 0,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO rewards.consumer_cursor (name) VALUES ('outbox');
"""


DOWNGRADE = r"""
DROP SCHEMA rewards CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
