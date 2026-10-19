"""Institutions: card, members and invitations, safety team, registers, documents, digital certificates.

Revision ID: 0006_institutions
Revises: 0005_ai_layer
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0006_institutions"
down_revision: str | None = "0005_ai_layer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
CREATE SCHEMA IF NOT EXISTS org;

-- ===================== institution card (FR-B-001, FR-B-002) =====================
CREATE TABLE org.organization (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status            text NOT NULL DEFAULT 'pending_review'
                      CHECK (status IN ('pending_review', 'active', 'rejected', 'suspended')),
    version           integer NOT NULL DEFAULT 1,          -- optimistic concurrency of the card
    name              text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 200),
    kind              text NOT NULL
                      CHECK (kind IN ('industrial', 'educational', 'hotel', 'government', 'private', 'other')),
    identifier_type   text NOT NULL CHECK (identifier_type IN ('mf', 'rne')),
    identifier        text NOT NULL UNIQUE,
    activity_sector   text,
    activity_type     text,
    capacity          integer CHECK (capacity BETWEEN 0 AND 1000000),
    floors            smallint CHECK (floors BETWEEN 0 AND 300),
    height_m          real CHECK (height_m BETWEEN 0 AND 1000),
    receives_public   boolean NOT NULL DEFAULT false,
    address           text,
    location          geography(Point, 4326) NOT NULL,
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    delegation_id     integer REFERENCES geo.delegation(id),
    manager           jsonb NOT NULL DEFAULT '{}'::jsonb,  -- {full_name, phone, email}
    contact_email     text,
    contact_phone     text,
    review_reason     text,
    reviewed_by       text,
    reviewed_at       timestamptz,
    created_by        uuid NOT NULL REFERENCES identity.account(user_id),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_org_location ON org.organization USING gist (location);
CREATE INDEX ix_org_scope ON org.organization (gouvernorat_code, status);
CREATE INDEX ix_org_name ON org.organization (lower(name), id);
CREATE INDEX ix_org_created_by ON org.organization (created_by);

-- Members of the institution's account (FR-B-009). Authorization source of truth, not Keycloak roles.
CREATE TABLE org.member (
    org_id        uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    user_id       uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    role          text NOT NULL CHECK (role IN ('admin', 'editor', 'member')),
    display_name  text,
    email         text,
    joined_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, user_id)
);
CREATE INDEX ix_member_user ON org.member (user_id);

CREATE TABLE org.invitation (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    email        text NOT NULL,
    role         text NOT NULL CHECK (role IN ('admin', 'editor', 'member')),
    token_hash   bytea NOT NULL UNIQUE,                 -- SHA-256 of the one-time token
    expires_at   timestamptz NOT NULL,
    created_by   uuid NOT NULL REFERENCES identity.account(user_id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    accepted_by  uuid REFERENCES identity.account(user_id),
    accepted_at  timestamptz,
    revoked_at   timestamptz
);
CREATE INDEX ix_invitation_pending ON org.invitation (org_id) WHERE accepted_at IS NULL AND revoked_at IS NULL;

-- ===================== safety team (FR-B-005) =====================
CREATE TABLE org.team_member (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id                 uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    full_name              text NOT NULL CHECK (char_length(full_name) BETWEEN 2 AND 120),
    team_role              text NOT NULL CHECK (team_role IN ('representative', 'member')),
    position               text,
    phone                  text,
    email                  text,
    last_training_on       date,
    training_valid_months  smallint NOT NULL DEFAULT 24 CHECK (training_valid_months BETWEEN 1 AND 120),
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_team_org ON org.team_member (org_id);
CREATE UNIQUE INDEX ux_team_representative ON org.team_member (org_id) WHERE team_role = 'representative';

-- ===================== documents with versions (FR-B-004) =====================
CREATE TABLE org.document (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('safety_file', 'safety_plan', 'sds', 'other')),
    title       text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_document_org ON org.document (org_id);

CREATE TABLE org.document_version (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       uuid NOT NULL REFERENCES org.document(id) ON DELETE CASCADE,
    version           integer NOT NULL CHECK (version >= 1),
    upload_id         text UNIQUE,
    object_key        text NOT NULL UNIQUE,
    filename          text,
    content_type      text NOT NULL,
    bytes             bigint,
    sha256            char(64) NOT NULL,
    note              text,
    status            text NOT NULL DEFAULT 'uploading'
                      CHECK (status IN ('uploading', 'verifying', 'stored', 'rejected')),
    uploaded_by       uuid REFERENCES identity.account(user_id),
    uploaded_by_name  text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    stored_at         timestamptz,
    UNIQUE (document_id, version)
);
CREATE INDEX ix_document_version_verifying ON org.document_version (created_at) WHERE status = 'verifying';

-- ===================== registers (FR-B-006, FR-B-007) =====================
CREATE TABLE org.hazmat (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id            uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    name              text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
    un_number         text CHECK (un_number ~ '^[0-9]{4}$'),
    hazard_class      text CHECK (char_length(hazard_class) <= 8),
    quantity          numeric(14, 3) NOT NULL CHECK (quantity >= 0),
    unit              text NOT NULL CHECK (unit IN ('kg', 't', 'l', 'm3')),
    storage_location  text,
    sds_document_id   uuid REFERENCES org.document(id),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_hazmat_org ON org.hazmat (org_id);

CREATE TABLE org.equipment (
    id                           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id                       uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    kind                         text NOT NULL CHECK (kind IN ('extinguisher', 'fire_hose_reel', 'sprinkler',
                                     'smoke_detector', 'alarm_panel', 'emergency_lighting', 'fire_door', 'other')),
    count                        integer NOT NULL CHECK (count BETWEEN 0 AND 100000),
    location                     text,
    last_maintenance_on          date,
    maintenance_interval_months  smallint NOT NULL DEFAULT 12 CHECK (maintenance_interval_months BETWEEN 1 AND 120),
    created_at                   timestamptz NOT NULL DEFAULT now(),
    updated_at                   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_equipment_org ON org.equipment (org_id);

CREATE TABLE org.map_feature (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('evacuation_point', 'water_point', 'alarm')),
    label       text CHECK (char_length(label) <= 120),
    location    geography(Point, 4326) NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_feature_org ON org.map_feature (org_id);

-- ===================== digital safety certificates (FR-B-008) =====================
CREATE TABLE org.certificate_counter (
    year  smallint PRIMARY KEY,
    last  integer NOT NULL
);

CREATE TABLE org.certificate (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    code            text NOT NULL UNIQUE,
    status          text NOT NULL CHECK (status IN ('draft', 'submitted', 'approved', 'rejected')),
    snapshot        jsonb NOT NULL,                     -- the certified content, frozen at generation
    fingerprint     char(64) NOT NULL,                  -- SHA-256 of the canonical snapshot
    signature       bytea,                              -- Ed25519, set on approval
    pdf_object_key  text NOT NULL,
    pdf_sha256      char(64) NOT NULL,
    created_by      uuid NOT NULL REFERENCES identity.account(user_id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    submitted_by    uuid REFERENCES identity.account(user_id),
    submitted_at    timestamptz,
    reviewed_by     text,
    reviewed_at     timestamptz,
    review_reason   text,
    valid_until     date,
    superseded_by   uuid REFERENCES org.certificate(id)
);
CREATE UNIQUE INDEX ux_certificate_draft ON org.certificate (org_id) WHERE status = 'draft';
CREATE INDEX ix_certificate_org ON org.certificate (org_id, created_at DESC);
CREATE INDEX ix_certificate_queue ON org.certificate (submitted_at, id) WHERE status = 'submitted';

-- ===================== reports made on behalf of an institution (FR-A-080, FR-B-011) =====================
ALTER TABLE reports.report ADD COLUMN organization_id uuid REFERENCES org.organization(id);
CREATE INDEX ix_report_org ON reports.report (organization_id, received_at DESC, id DESC)
    WHERE organization_id IS NOT NULL;
"""

DOWNGRADE = r"""
DROP INDEX reports.ix_report_org;
ALTER TABLE reports.report DROP COLUMN organization_id;
DROP SCHEMA org CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
