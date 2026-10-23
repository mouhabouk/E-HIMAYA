"""Personal safety between citizens (phase B2, docs/phase-b/design-b2.md §4).

* ``safety.invitation`` — a code one registered user gives another to link their accounts (SHA-256 of the code only,
  48 h, single use).
* ``safety.link`` — two accounts linked by an accepted invitation; works both ways, either side removes it.
* ``safety.alert`` / ``safety.alert_recipient`` — an SOS message (or a fired safety check) sent in the app to
  linked contacts: encrypted message and position, battery, delivery and read receipts.
* ``safety.live_share`` — a live location link (SHA-256 of the random token), its last points encrypted.
* ``safety.safety_check`` — a safety check timer fired by the server when the user does not answer "I am fine".

Row-level security: an account reads only its own rows, the alerts it sent or received and the links it is part of.
Staff scopes read nothing here: these are private exchanges between citizens. The system scope (worker, public live
view, retention) reads everything. Settings ``safety.live_max_minutes`` (480) and ``safety.check_max_hours`` (24).
Downgrade drops the schema and the settings.

Revision ID: 0037_personal_safety
Revises: 0036_emergency_guide_more
Create Date: 2026-10-23
"""

# ruff: noqa: S608 (policies are built from the constant SQL fragments below)

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0037_personal_safety"
down_revision: str | None = "0036_emergency_guide_more"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SYSTEM = "ehimaya.scope() = 'system'"


def _mine(column: str) -> str:
    return f"(ehimaya.scope() = 'public' AND CAST({column} AS text) = ehimaya.subject())"


UPGRADE = rf"""
CREATE SCHEMA IF NOT EXISTS safety;

CREATE TABLE safety.invitation (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inviter_id  uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    code_hash   bytea NOT NULL UNIQUE,
    expires_at  timestamptz NOT NULL,
    accepted_by uuid REFERENCES identity.account(user_id) ON DELETE SET NULL,
    accepted_at timestamptz,
    cancelled_at timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_safety_invitation_inviter ON safety.invitation (inviter_id, created_at DESC);

CREATE TABLE safety.link (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_a     uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    user_b     uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_safety_link_order CHECK (user_a < user_b),
    CONSTRAINT uq_safety_link_pair UNIQUE (user_a, user_b)
);
CREATE INDEX ix_safety_link_b ON safety.link (user_b);

CREATE TABLE safety.live_share (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    token_hash  bytea NOT NULL UNIQUE,
    started_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL,
    stopped_at  timestamptz,
    points_enc  bytea,
    battery     smallint,
    updated_at  timestamptz,
    CONSTRAINT ck_safety_live_battery CHECK (battery BETWEEN 0 AND 100)
);
CREATE INDEX ix_safety_live_owner ON safety.live_share (owner_id, started_at DESC);

CREATE TABLE safety.alert (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_uuid   uuid NOT NULL,
    sender_id     uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    kind          text NOT NULL,
    message_enc   bytea NOT NULL,
    position_enc  bytea,
    battery       smallint,
    live_share_id uuid REFERENCES safety.live_share(id) ON DELETE SET NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz NOT NULL,
    CONSTRAINT ck_safety_alert_kind CHECK (kind IN ('sos', 'check')),
    CONSTRAINT ck_safety_alert_battery CHECK (battery BETWEEN 0 AND 100),
    CONSTRAINT uq_safety_alert_client UNIQUE (sender_id, client_uuid)
);

CREATE TABLE safety.alert_recipient (
    alert_id     uuid NOT NULL REFERENCES safety.alert(id) ON DELETE CASCADE,
    recipient_id uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    seen_at      timestamptz,
    PRIMARY KEY (alert_id, recipient_id)
);
CREATE INDEX ix_safety_recipient ON safety.alert_recipient (recipient_id);

CREATE TABLE safety.safety_check (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id     uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    due_at       timestamptz NOT NULL,
    message_enc  bytea NOT NULL,
    position_enc bytea,
    battery      smallint,
    status       text NOT NULL DEFAULT 'active',
    alert_id     uuid REFERENCES safety.alert(id) ON DELETE SET NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    ended_at     timestamptz,
    CONSTRAINT ck_safety_check_status CHECK (status IN ('active', 'ok', 'fired', 'cancelled')),
    CONSTRAINT ck_safety_check_battery CHECK (battery BETWEEN 0 AND 100)
);
-- One active check per account; the worker finds the due ones by this index.
CREATE UNIQUE INDEX uq_safety_check_active ON safety.safety_check (owner_id) WHERE status = 'active';
CREATE INDEX ix_safety_check_due ON safety.safety_check (due_at) WHERE status = 'active';

ALTER TABLE safety.invitation ENABLE ROW LEVEL SECURITY;
CREATE POLICY safety_invitation_all ON safety.invitation USING ({_SYSTEM} OR {_mine("inviter_id")})
    WITH CHECK ({_SYSTEM} OR {_mine("inviter_id")});

ALTER TABLE safety.link ENABLE ROW LEVEL SECURITY;
CREATE POLICY safety_link_all ON safety.link USING ({_SYSTEM} OR {_mine("user_a")} OR {_mine("user_b")})
    WITH CHECK ({_SYSTEM} OR {_mine("user_a")} OR {_mine("user_b")});

ALTER TABLE safety.live_share ENABLE ROW LEVEL SECURITY;
CREATE POLICY safety_live_all ON safety.live_share USING ({_SYSTEM} OR {_mine("owner_id")})
    WITH CHECK ({_SYSTEM} OR {_mine("owner_id")});

-- The recipient reads the alert through its recipient row (its own policy applies inside the EXISTS).
ALTER TABLE safety.alert ENABLE ROW LEVEL SECURITY;
CREATE POLICY safety_alert_select ON safety.alert FOR SELECT USING (
    {_SYSTEM} OR {_mine("sender_id")}
    OR EXISTS (SELECT 1 FROM safety.alert_recipient r WHERE r.alert_id = id AND {_mine("r.recipient_id")}));
CREATE POLICY safety_alert_insert ON safety.alert FOR INSERT WITH CHECK ({_SYSTEM} OR {_mine("sender_id")});
CREATE POLICY safety_alert_delete ON safety.alert FOR DELETE USING ({_SYSTEM} OR {_mine("sender_id")});

-- No reference back to safety.alert (policies referring to each other recurse): the API inserts recipients and reads
-- the sender's read receipts with the system scope, after checking the sender itself.
ALTER TABLE safety.alert_recipient ENABLE ROW LEVEL SECURITY;
CREATE POLICY safety_recipient_select ON safety.alert_recipient FOR SELECT USING ({_SYSTEM} OR {_mine("recipient_id")});
CREATE POLICY safety_recipient_insert ON safety.alert_recipient FOR INSERT WITH CHECK ({_SYSTEM});
CREATE POLICY safety_recipient_update ON safety.alert_recipient FOR UPDATE
    USING ({_SYSTEM} OR {_mine("recipient_id")}) WITH CHECK ({_SYSTEM} OR {_mine("recipient_id")});
CREATE POLICY safety_recipient_delete ON safety.alert_recipient FOR DELETE USING ({_SYSTEM});

ALTER TABLE safety.safety_check ENABLE ROW LEVEL SECURITY;
CREATE POLICY safety_check_all ON safety.safety_check USING ({_SYSTEM} OR {_mine("owner_id")})
    WITH CHECK ({_SYSTEM} OR {_mine("owner_id")});

INSERT INTO platform.setting (key, value) VALUES
    ('safety.live_max_minutes', '480'),
    ('safety.check_max_hours', '24')
ON CONFLICT (key) DO NOTHING;
"""

DOWNGRADE = r"""
DELETE FROM platform.setting WHERE key IN ('safety.live_max_minutes', 'safety.check_max_hours');
DROP TABLE safety.safety_check;
-- This policy reads safety.alert_recipient, so the table cannot go before it.
DROP POLICY safety_alert_select ON safety.alert;
DROP TABLE safety.alert_recipient;
DROP TABLE safety.alert;
DROP TABLE safety.live_share;
DROP TABLE safety.link;
DROP TABLE safety.invitation;
DROP SCHEMA safety;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
