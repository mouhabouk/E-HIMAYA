"""Disaster and crisis axes with the command views of the governor and the minister (phase L3,
docs/phase-l/design-l3.md, item 13).

* ``crisis.axis``: one declared disaster or crisis. Regional (one gouvernorat) or national: a national axis is a root
  without gouvernorat with one sub-axis per gouvernorat concerned. Its area on the map, level 1 to 4, the plan in
  force, open or closed with the final figures.
* ``crisis.request``: a regional room asks the commander to declare one; accepted (it opens the axis) or rejected
  with the reason.
* ``crisis.axis_incident``: the interventions attached to an axis (never automatically); detached ones keep the row
  with the reason. ``crisis.dismissal``: suggestions a room turned down, so they are not suggested again.
* ``crisis.shelter``, ``crisis.evacuation``, ``crisis.need``: shelters and their occupancy, evacuation zones and the
  people evacuated, resources the room lacks.
* ``crisis.directive``: a recommendation or a decision of the governor or the minister, signed by the server
  (Ed25519) and never changed afterwards except its execution status; ``crisis.directive_event`` keeps each status.
* ``crisis.sitrep``: situation reports, drafted from the figures and sent by the room with its assessment.
* ``crisis.event``: the axis timeline.

Row-level security: the national staff sees every axis; a regional account (room, governor) sees the axes of its
gouvernorat and the national roots that have a sub-axis there. Who may do what inside that is the API's (roles).

Revision ID: 0056_crisis_axes
Revises: 0055_seasonal_programmes
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0056_crisis_axes"
down_revision: str | None = "0055_seasonal_programmes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEES = "crisis.sees_axis(axis_id)"

UPGRADE = rf"""
CREATE SCHEMA IF NOT EXISTS crisis;

CREATE TABLE crisis.axis (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    number           text NOT NULL UNIQUE,
    name             text NOT NULL CHECK (length(name) BETWEEN 3 AND 200),
    kind             text NOT NULL
                     CHECK (kind IN ('flood', 'forest_fire', 'storm', 'earthquake', 'technological', 'health', 'other')),
    scope            text NOT NULL CHECK (scope IN ('gouvernorat', 'national')),
    parent_id        uuid REFERENCES crisis.axis(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    area             geography(MULTIPOLYGON, 4326),
    level            smallint NOT NULL CHECK (level BETWEEN 1 AND 4),
    plan             text NOT NULL DEFAULT '',
    status           text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    request_id       uuid,
    opened_by        text NOT NULL,
    opened_by_name   text,
    opened_at        timestamptz NOT NULL DEFAULT now(),
    closed_by        text,
    closed_by_name   text,
    closed_at        timestamptz,
    closing          jsonb,
    next_sitrep_at   timestamptz,
    memory_id        uuid,
    version          integer NOT NULL DEFAULT 1,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    -- A national root has no gouvernorat; a regional axis or a sub-axis has one.
    CONSTRAINT ck_axis_scope CHECK (
        (scope = 'national' AND parent_id IS NULL AND gouvernorat_code IS NULL)
        OR (scope = 'gouvernorat' AND gouvernorat_code IS NOT NULL)
    )
);
CREATE INDEX ix_axis_status ON crisis.axis (status, gouvernorat_code);
CREATE INDEX ix_axis_parent ON crisis.axis (parent_id);
CREATE INDEX ix_axis_area ON crisis.axis USING gist (area);
CREATE UNIQUE INDEX uq_axis_sub ON crisis.axis (parent_id, gouvernorat_code) WHERE parent_id IS NOT NULL;

CREATE TABLE crisis.counter (
    year integer PRIMARY KEY,
    last integer NOT NULL
);

-- Gouvernorats an axis concerns: its own, or those of its sub-axes for a national root (owner's rights, so the
-- policies below can ask without recursing into the axis policy).
CREATE FUNCTION crisis.axis_gouvernorats(p_axis uuid) RETURNS smallint[] LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
    SELECT coalesce(array_agg(DISTINCT code), '{{}}') FROM (
        SELECT gouvernorat_code AS code FROM crisis.axis WHERE id = p_axis AND gouvernorat_code IS NOT NULL
        UNION ALL
        SELECT gouvernorat_code FROM crisis.axis WHERE parent_id = p_axis AND gouvernorat_code IS NOT NULL
    ) c $$;

CREATE FUNCTION crisis.sees_axis(p_axis uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT ehimaya.sees_all()
        OR (ehimaya.regional() AND ehimaya.gouvernorat() = ANY(crisis.axis_gouvernorats(p_axis))) $$;

CREATE TABLE crisis.request (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    name             text NOT NULL CHECK (length(name) BETWEEN 3 AND 200),
    kind             text NOT NULL,
    level            smallint NOT NULL CHECK (level BETWEEN 1 AND 4),
    facts            text NOT NULL CHECK (length(facts) >= 10),
    incident_ids     uuid[] NOT NULL DEFAULT '{{}}',
    area             geography(MULTIPOLYGON, 4326),
    status           text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
    created_by       text NOT NULL,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    decided_by       text,
    decided_by_name  text,
    decided_at       timestamptz,
    decision_reason  text,
    axis_id          uuid REFERENCES crisis.axis(id) ON DELETE SET NULL
);
CREATE INDEX ix_request_status ON crisis.request (status, gouvernorat_code);

CREATE TABLE crisis.axis_incident (
    axis_id          uuid NOT NULL REFERENCES crisis.axis(id) ON DELETE CASCADE,
    incident_id      uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    attached_by      text NOT NULL,
    attached_by_name text,
    attached_at      timestamptz NOT NULL DEFAULT now(),
    detached_by      text,
    detached_by_name text,
    detached_at      timestamptz,
    detach_reason    text,
    PRIMARY KEY (axis_id, incident_id)
);
CREATE INDEX ix_axis_incident_incident ON crisis.axis_incident (incident_id) WHERE detached_at IS NULL;

CREATE TABLE crisis.dismissal (
    axis_id      uuid NOT NULL REFERENCES crisis.axis(id) ON DELETE CASCADE,
    incident_id  uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    dismissed_by text NOT NULL,
    dismissed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (axis_id, incident_id)
);

CREATE TABLE crisis.shelter (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    axis_id    uuid NOT NULL REFERENCES crisis.axis(id) ON DELETE CASCADE,
    name       text NOT NULL CHECK (length(name) BETWEEN 2 AND 200),
    location   geography(POINT, 4326),
    capacity   integer NOT NULL CHECK (capacity >= 0),
    occupants  integer NOT NULL DEFAULT 0 CHECK (occupants >= 0),
    updated_by text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_shelter_axis ON crisis.shelter (axis_id);

CREATE TABLE crisis.evacuation (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    axis_id    uuid NOT NULL REFERENCES crisis.axis(id) ON DELETE CASCADE,
    name       text NOT NULL CHECK (length(name) BETWEEN 2 AND 200),
    area       geography(MULTIPOLYGON, 4326),
    evacuated  integer NOT NULL DEFAULT 0 CHECK (evacuated >= 0),
    updated_by text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_evacuation_axis ON crisis.evacuation (axis_id);

CREATE TABLE crisis.need (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    axis_id         uuid NOT NULL REFERENCES crisis.axis(id) ON DELETE CASCADE,
    label           text NOT NULL CHECK (length(label) BETWEEN 2 AND 200),
    quantity        integer NOT NULL CHECK (quantity > 0),
    status          text NOT NULL DEFAULT 'raised' CHECK (status IN ('raised', 'met')),
    created_by      text NOT NULL,
    created_by_name text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    met_at          timestamptz
);
CREATE INDEX ix_need_axis ON crisis.need (axis_id);

CREATE TABLE crisis.directive (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    axis_id        uuid NOT NULL REFERENCES crisis.axis(id) ON DELETE CASCADE,
    number         integer NOT NULL,
    kind           text NOT NULL CHECK (kind IN ('recommendation', 'decision')),
    category       text NOT NULL CHECK (category IN ('evacuation', 'resources', 'closure', 'shelter', 'support',
                                                     'plan', 'public_information', 'other')),
    body           text NOT NULL CHECK (length(body) BETWEEN 5 AND 4000),
    area           geography(MULTIPOLYGON, 4326),
    executor       text NOT NULL CHECK (executor IN ('regional', 'central', 'partner')),
    executor_name  text,
    due_at         timestamptz,
    status         text NOT NULL DEFAULT 'issued'
                   CHECK (status IN ('issued', 'received', 'in_progress', 'done', 'failed')),
    status_reason  text,
    issuer_role    text NOT NULL CHECK (issuer_role IN ('governor', 'minister')),
    issued_by      text NOT NULL,
    issued_by_name text,
    issued_at      timestamptz NOT NULL,
    signature      text,
    key_id         text,
    overridden_by  uuid REFERENCES crisis.directive(id),
    reminded_at    timestamptz,
    overdue_at     timestamptz,
    done_at        timestamptz,
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_directive_number UNIQUE (axis_id, number)
);
CREATE INDEX ix_directive_open ON crisis.directive (status, due_at);

CREATE TABLE crisis.directive_event (
    id           bigserial PRIMARY KEY,
    directive_id uuid NOT NULL REFERENCES crisis.directive(id) ON DELETE CASCADE,
    axis_id      uuid NOT NULL REFERENCES crisis.axis(id) ON DELETE CASCADE,
    status       text NOT NULL,
    reason       text,
    by_actor     text NOT NULL,
    by_name      text,
    at           timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE crisis.sitrep (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    axis_id      uuid NOT NULL REFERENCES crisis.axis(id) ON DELETE CASCADE,
    number       integer NOT NULL,
    figures      jsonb NOT NULL,
    assessment   text NOT NULL DEFAULT '',
    status       text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'sent')),
    created_by   text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    sent_by      text,
    sent_by_name text,
    sent_at      timestamptz,
    CONSTRAINT uq_sitrep_number UNIQUE (axis_id, number)
);

CREATE TABLE crisis.event (
    id         bigserial PRIMARY KEY,
    axis_id    uuid NOT NULL REFERENCES crisis.axis(id) ON DELETE CASCADE,
    at         timestamptz NOT NULL DEFAULT now(),
    actor      text NOT NULL,
    actor_name text,
    kind       text NOT NULL,
    payload    jsonb NOT NULL DEFAULT '{{}}'::jsonb
);
CREATE INDEX ix_crisis_event_axis ON crisis.event (axis_id, at);

ALTER TABLE crisis.axis ENABLE ROW LEVEL SECURITY;
CREATE POLICY axis_all ON crisis.axis USING (crisis.sees_axis(id))
    WITH CHECK (ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()));

ALTER TABLE crisis.counter ENABLE ROW LEVEL SECURITY;
CREATE POLICY counter_all ON crisis.counter USING (ehimaya.sees_all()) WITH CHECK (ehimaya.sees_all());

ALTER TABLE crisis.request ENABLE ROW LEVEL SECURITY;
CREATE POLICY request_all ON crisis.request
    USING (ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()))
    WITH CHECK (ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()));

ALTER TABLE crisis.axis_incident ENABLE ROW LEVEL SECURITY;
CREATE POLICY axis_incident_all ON crisis.axis_incident USING ({_SEES}) WITH CHECK ({_SEES});
ALTER TABLE crisis.dismissal ENABLE ROW LEVEL SECURITY;
CREATE POLICY dismissal_all ON crisis.dismissal USING ({_SEES}) WITH CHECK ({_SEES});
ALTER TABLE crisis.shelter ENABLE ROW LEVEL SECURITY;
CREATE POLICY shelter_all ON crisis.shelter USING ({_SEES}) WITH CHECK ({_SEES});
ALTER TABLE crisis.evacuation ENABLE ROW LEVEL SECURITY;
CREATE POLICY evacuation_all ON crisis.evacuation USING ({_SEES}) WITH CHECK ({_SEES});
ALTER TABLE crisis.need ENABLE ROW LEVEL SECURITY;
CREATE POLICY need_all ON crisis.need USING ({_SEES}) WITH CHECK ({_SEES});
ALTER TABLE crisis.directive ENABLE ROW LEVEL SECURITY;
CREATE POLICY directive_all ON crisis.directive USING ({_SEES}) WITH CHECK ({_SEES});
ALTER TABLE crisis.directive_event ENABLE ROW LEVEL SECURITY;
CREATE POLICY directive_event_all ON crisis.directive_event USING ({_SEES}) WITH CHECK ({_SEES});
ALTER TABLE crisis.sitrep ENABLE ROW LEVEL SECURITY;
CREATE POLICY sitrep_all ON crisis.sitrep USING ({_SEES}) WITH CHECK ({_SEES});
ALTER TABLE crisis.event ENABLE ROW LEVEL SECURITY;
CREATE POLICY event_all ON crisis.event USING ({_SEES}) WITH CHECK ({_SEES});
"""  # noqa: S608 (constant SQL fragments, nothing is interpolated from input)

DOWNGRADE = r"""
DROP SCHEMA crisis CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
