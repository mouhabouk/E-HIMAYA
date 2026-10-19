"""Operations: levels, committees, units and resources, assignments, volunteers and call-outs,
notifications and alerts, push devices, outgoing messages, safety tips.

Revision ID: 0007_operations
Revises: 0006_institutions
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

from migrations.sqlutil import run_script

revision: str = "0007_operations"
down_revision: str | None = "0006_institutions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_TIPS = Path(__file__).resolve().parents[2] / "seed" / "safety_tips.json"

UPGRADE = r"""
-- ===================== operational levels (§6.4, FR-C-24) =====================
CREATE TABLE ops.level_state (
    gouvernorat_code  smallint PRIMARY KEY REFERENCES geo.gouvernorat(code),
    level             ops.op_level NOT NULL DEFAULT 'normal',
    since             timestamptz NOT NULL DEFAULT now(),
    reason            text,
    set_by            text,
    set_by_name       text
);
INSERT INTO ops.level_state (gouvernorat_code) SELECT code FROM geo.gouvernorat;

-- ===================== committees (FR-C-15, FR-C-16) =====================
CREATE TABLE ops.directive (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title             text NOT NULL CHECK (char_length(title) BETWEEN 3 AND 150),
    body              text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 5000),
    urgency           text NOT NULL CHECK (urgency IN ('normal', 'urgent')),
    from_level        text NOT NULL CHECK (from_level IN ('central', 'local')),
    gouvernorat_codes smallint[] NOT NULL DEFAULT '{}',   -- empty: the 24 gouvernorats
    issuer_scope      smallint REFERENCES geo.gouvernorat(code),
    issued_by         text NOT NULL,
    issued_by_name    text,
    issued_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_directive_issued ON ops.directive (issued_at DESC, id DESC);
CREATE INDEX ix_directive_targets ON ops.directive USING gin (gouvernorat_codes);

CREATE TABLE ops.directive_ack (
    directive_id      uuid NOT NULL REFERENCES ops.directive(id) ON DELETE CASCADE,
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    acked_by          text NOT NULL,
    acked_by_name     text,
    acked_at          timestamptz NOT NULL DEFAULT now(),
    note              text CHECK (char_length(note) <= 1000),
    PRIMARY KEY (directive_id, gouvernorat_code)
);

-- ===================== units and resources (FR-C-09) =====================
CREATE TABLE ops.unit (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name_ar           text NOT NULL CHECK (char_length(name_ar) BETWEEN 2 AND 150),
    name_fr           text NOT NULL CHECK (char_length(name_fr) BETWEEN 2 AND 150),
    kind              text NOT NULL CHECK (kind IN ('directorate', 'unit', 'advanced_post')),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    location          geography(Point, 4326) NOT NULL,
    phone             text,
    version           integer NOT NULL DEFAULT 1,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_unit_gouvernorat ON ops.unit (gouvernorat_code, name_ar);
CREATE INDEX ix_unit_location ON ops.unit USING gist (location);

CREATE TABLE ops.resource (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id           uuid NOT NULL REFERENCES ops.unit(id),
    kind              text NOT NULL CHECK (kind IN ('fire_engine', 'water_tanker', 'ambulance', 'rescue_vehicle',
                          'heavy_equipment', 'drone', 'large_extinguisher', 'boat', 'command_vehicle', 'other')),
    label             text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 60),
    status            text NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'assigned', 'out_of_service')),
    notes             text CHECK (char_length(notes) <= 500),
    location          geography(Point, 4326),
    version           integer NOT NULL DEFAULT 1,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_resource_label UNIQUE (unit_id, label)
);
CREATE INDEX ix_resource_unit ON ops.resource (unit_id);
CREATE INDEX ix_resource_status ON ops.resource (status, kind);

-- ===================== incident card and evaluation (FR-C-09) =====================
ALTER TABLE ops.incident
    ADD COLUMN title          text CHECK (char_length(title) <= 150),
    ADD COLUMN classification text,
    ADD COLUMN evaluation     jsonb;

-- ===================== volunteers (FR-A-020…023, FR-C-04) =====================
CREATE TABLE identity.volunteer (
    user_id           uuid PRIMARY KEY REFERENCES identity.account(user_id) ON DELETE CASCADE,
    status            text NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'approved', 'rejected', 'suspended', 'withdrawn')),
    skills            text[] NOT NULL CHECK (cardinality(skills) BETWEEN 1 AND 8),
    other_skill       text CHECK (char_length(other_skill) <= 100),
    availability      text NOT NULL CHECK (availability IN ('continuous', 'intermittent')),
    period_from       date NOT NULL,
    period_to         date CHECK (period_to IS NULL OR period_to >= period_from),
    notes             text CHECK (char_length(notes) <= 500),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    submitted_at      timestamptz NOT NULL DEFAULT now(),
    reviewed_at       timestamptz,
    reviewed_by       text,
    review_reason     text,
    -- Readiness (FR-A-022). The live position is kept in Valkey only, never here.
    ready_until       timestamptz,
    version           integer NOT NULL DEFAULT 1,
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_volunteer_status ON identity.volunteer (status, gouvernorat_code);
CREATE INDEX ix_volunteer_skills ON identity.volunteer USING gin (skills);
CREATE INDEX ix_volunteer_ready ON identity.volunteer (ready_until) WHERE ready_until IS NOT NULL;

CREATE TABLE identity.volunteer_review (
    id                bigserial PRIMARY KEY,
    user_id           uuid NOT NULL REFERENCES identity.volunteer(user_id) ON DELETE CASCADE,
    decision          text NOT NULL,
    reason            text,
    actor             text NOT NULL,
    at                timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_volunteer_review_user ON identity.volunteer_review (user_id, at DESC);

-- ===================== call-outs (UC-05) and assignments =====================
CREATE TABLE ops.callout (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id       uuid NOT NULL REFERENCES ops.incident(id),
    skill             text NOT NULL,
    requested         smallint NOT NULL CHECK (requested BETWEEN 1 AND 50),
    radius_km         smallint NOT NULL CHECK (radius_km BETWEEN 1 AND 100),
    message           text CHECK (char_length(message) <= 300),
    status            text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'filled', 'cancelled', 'closed')),
    created_by        text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    closed_at         timestamptz
);
CREATE INDEX ix_callout_incident ON ops.callout (incident_id, created_at DESC);

CREATE TABLE ops.assignment (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id       uuid NOT NULL REFERENCES ops.incident(id),
    kind              text NOT NULL CHECK (kind IN ('resource', 'volunteer')),
    resource_id       uuid REFERENCES ops.resource(id),
    volunteer_id      uuid REFERENCES identity.volunteer(user_id) ON DELETE SET NULL,
    callout_id        uuid REFERENCES ops.callout(id),
    "order"           text CHECK (char_length("order") <= 1000),
    status            text NOT NULL CHECK (status IN ('ordered', 'en_route', 'on_scene', 'released', 'cancelled')),
    created_by        text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    en_route_at       timestamptz,
    on_scene_at       timestamptz,
    released_at       timestamptz,
    cancelled_at      timestamptz,
    CONSTRAINT ck_assignment_target CHECK ((kind = 'resource') = (resource_id IS NOT NULL))
);
CREATE INDEX ix_assignment_incident ON ops.assignment (incident_id, created_at);
-- A resource is engaged on one intervention at a time.
CREATE UNIQUE INDEX ux_assignment_resource_active ON ops.assignment (resource_id)
    WHERE status IN ('ordered', 'en_route', 'on_scene');

CREATE TABLE ops.callout_target (
    callout_id        uuid NOT NULL REFERENCES ops.callout(id) ON DELETE CASCADE,
    volunteer_id      uuid NOT NULL REFERENCES identity.volunteer(user_id) ON DELETE CASCADE,
    distance_m        integer,
    status            text NOT NULL DEFAULT 'sent'
                      CHECK (status IN ('sent', 'accepted', 'declined', 'expired', 'arrived')),
    eta_minutes       smallint,
    sent_at           timestamptz NOT NULL DEFAULT now(),
    responded_at      timestamptz,
    arrived_at        timestamptz,
    assignment_id     uuid REFERENCES ops.assignment(id),
    PRIMARY KEY (callout_id, volunteer_id)
);
CREATE INDEX ix_callout_target_volunteer ON ops.callout_target (volunteer_id, sent_at DESC);
CREATE INDEX ix_callout_target_pending ON ops.callout_target (sent_at) WHERE status = 'sent';

-- ===================== notifications, alerts, devices (FR-A-060, FR-A-061, FR-C-17, FR-C-18) =====================
CREATE SCHEMA IF NOT EXISTS notify;

CREATE TABLE notify.device (
    token             text PRIMARY KEY CHECK (char_length(token) BETWEEN 20 AND 4096),
    user_id           uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    platform          text NOT NULL CHECK (platform IN ('android', 'ios')),
    locale            text NOT NULL DEFAULT 'ar' CHECK (locale IN ('ar', 'fr', 'en')),
    -- Rounded to 0.01° (about 1 km), only to target alerts by current location; replaced at each call.
    location          geography(Point, 4326),
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_device_user ON notify.device (user_id);
CREATE INDEX ix_device_gouvernorat ON notify.device (gouvernorat_code);
CREATE INDEX ix_device_location ON notify.device USING gist (location);

CREATE TABLE notify.message (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind              text NOT NULL CHECK (kind IN ('info', 'alert')),
    status            text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'cancelled', 'expired')),
    title             jsonb NOT NULL,
    body              jsonb NOT NULL,
    channels          text[] NOT NULL,
    -- informational
    topic             text CHECK (topic IN ('activity', 'awareness', 'training', 'world_day', 'other')),
    audience          text CHECK (audience IN ('all', 'volunteers', 'organizations', 'user')),
    user_id           uuid REFERENCES identity.account(user_id) ON DELETE SET NULL,
    -- alert
    severity          text CHECK (severity IN ('high', 'medium', 'low')),
    category          text CHECK (category IN ('weather', 'climate', 'hazard')),
    hazard            text,
    area_polygon      geometry(Polygon, 4326),
    expires_at        timestamptz,
    -- both: target gouvernorats (empty with no polygon: national)
    gouvernorat_codes smallint[] NOT NULL DEFAULT '{}',
    creator_scope     smallint REFERENCES geo.gouvernorat(code),
    created_by        text NOT NULL,
    created_by_name   text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    published_by      text,
    published_by_name text,
    published_at      timestamptz,
    cancelled_at      timestamptz,
    version           integer NOT NULL DEFAULT 1,
    CONSTRAINT ck_message_kind CHECK (
        (kind = 'info' AND topic IS NOT NULL AND audience IS NOT NULL)
        OR (kind = 'alert' AND severity IS NOT NULL AND category IS NOT NULL AND expires_at IS NOT NULL))
);
CREATE INDEX ix_message_register ON notify.message (created_at DESC, id DESC);
CREATE INDEX ix_message_active ON notify.message (expires_at) WHERE kind = 'alert' AND status = 'published';
CREATE INDEX ix_message_published ON notify.message (published_at DESC) WHERE status <> 'draft';
CREATE INDEX ix_message_area ON notify.message USING gist (area_polygon);

-- One fan-out job per message, channel and purpose; resumable from its cursor.
CREATE TABLE notify.dispatch (
    message_id        uuid NOT NULL REFERENCES notify.message(id) ON DELETE CASCADE,
    channel           text NOT NULL CHECK (channel IN ('push', 'sms', 'email')),
    purpose           text NOT NULL CHECK (purpose IN ('publish', 'cancel')),
    status            text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'done', 'skipped', 'failed')),
    cursor            text,
    sent              integer NOT NULL DEFAULT 0,
    failed            integer NOT NULL DEFAULT 0,
    lease_until       timestamptz,
    started_at        timestamptz,
    finished_at       timestamptz,
    error             text,
    PRIMARY KEY (message_id, channel, purpose)
);
CREATE INDEX ix_dispatch_pending ON notify.dispatch (status) WHERE status IN ('pending', 'running');

-- Individual messages (a report status push, a call-out, an e-mail), sent after commit with retries.
CREATE TABLE notify.outbox (
    id                bigserial PRIMARY KEY,
    channel           text NOT NULL CHECK (channel IN ('push', 'email')),
    user_id           uuid REFERENCES identity.account(user_id) ON DELETE CASCADE,
    address           text,
    payload           jsonb NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    next_attempt_at   timestamptz NOT NULL DEFAULT now(),
    attempts          smallint NOT NULL DEFAULT 0,
    sent_at           timestamptz,
    status            text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'skipped', 'failed')),
    last_error        text,
    CONSTRAINT ck_outbox_target CHECK ((channel = 'push') = (user_id IS NOT NULL) AND (channel = 'email') = (address IS NOT NULL))
);
CREATE INDEX ix_outbox_pending ON notify.outbox (next_attempt_at) WHERE status = 'pending';

-- Weekly digest of institution alerts already sent (FR-B-005, FR-B-006).
CREATE TABLE org.digest (
    org_id            uuid PRIMARY KEY REFERENCES org.organization(id) ON DELETE CASCADE,
    fingerprint       text NOT NULL,
    sent_at           timestamptz NOT NULL DEFAULT now()
);

-- ===================== safety tips (FR-A-062, FR-C-19) =====================
CREATE SCHEMA IF NOT EXISTS content;

CREATE TABLE content.safety_tip (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    hazard            text NOT NULL CHECK (hazard IN ('fire', 'flood', 'traffic_accident', 'medical', 'drowning',
                          'landslide', 'chemical_leak', 'heat_wave', 'storm', 'earthquake', 'other')),
    position          integer NOT NULL DEFAULT 0,
    status            text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    content           jsonb NOT NULL,
    version           integer NOT NULL DEFAULT 1,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    updated_by        text,
    published_at      timestamptz
);
CREATE INDEX ix_safety_tip_order ON content.safety_tip (position, hazard);

-- Bumped at each change of the published set, so the app can sync with If-None-Match.
CREATE TABLE content.revision (
    name              text PRIMARY KEY,
    value             bigint NOT NULL DEFAULT 1
);
INSERT INTO content.revision (name, value) VALUES ('safety_tips', 1);
"""

DOWNGRADE = r"""
DROP SCHEMA content CASCADE;
DROP TABLE org.digest;
DROP SCHEMA notify CASCADE;
DROP TABLE ops.callout_target;
DROP TABLE ops.assignment;
DROP TABLE ops.callout;
DROP TABLE identity.volunteer_review;
DROP TABLE identity.volunteer;
ALTER TABLE ops.incident DROP COLUMN title, DROP COLUMN classification, DROP COLUMN evaluation;
DROP TABLE ops.resource;
DROP TABLE ops.unit;
DROP TABLE ops.directive_ack;
DROP TABLE ops.directive;
DROP TABLE ops.level_state;
"""


def upgrade() -> None:
    run_script(UPGRADE)
    # Baseline safety tips (FR-A-062), published so the app has content offline from day one.
    # Their wording must be validated by the Protection Civile before the pilot.
    tips = json.loads(SEED_TIPS.read_text(encoding="utf-8"))
    for position, tip in enumerate(tips):
        op.get_bind().execute(
            sa.text(
                "INSERT INTO content.safety_tip (hazard, position, status, content, updated_by, published_at) "
                "VALUES (:hazard, :position, 'published', CAST(:content AS jsonb), 'system:seed', now())"
            ),
            {"hazard": tip["hazard"], "position": position, "content": json.dumps(tip["content"], ensure_ascii=False)},
        )


def downgrade() -> None:
    run_script(DOWNGRADE)
