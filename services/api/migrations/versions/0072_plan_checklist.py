"""The task list read from an intervention plan (L5, docs/phase-l/design-l5.md §2.3, AI2).

The local language model reads the plan's PDF and suggests tasks (action, who, with what, page of the plan); the room
manager accepts, edits or deletes each one, adds the ones it missed, and approves the list, which is then followed
task by task on the crisis axis or in the dry run it belongs to.

* ``crisis.checklist``: the list of an axis or of a dry run (one each), the plan it was read from, and the state of
  the reading: queued, reading, review (suggestions waiting), approved, failed.
* ``crisis.checklist_task``: one task, its origin (the model or a person), what the reviewer did with it, the passage
  of the plan it rests on and whether that passage was found on its page, and how far it is followed.

A dry run's list is read and written through the system scope by the drill routes after their own checks, like every
row of a dry run (migration 0066); an axis's list follows the axis's own visibility.

Revision ID: 0072_plan_checklist
Revises: 0071_drones
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0072_plan_checklist"
down_revision: str | None = "0071_drones"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LIST = "ehimaya.scope() = 'system' OR (axis_id IS NOT NULL AND crisis.sees_axis(axis_id))"
_TASK = "EXISTS (SELECT 1 FROM crisis.checklist c WHERE c.id = checklist_id)"

UPGRADE = f"""
CREATE TABLE crisis.checklist (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    axis_id           uuid UNIQUE REFERENCES crisis.axis(id) ON DELETE CASCADE,
    exercise_id       uuid UNIQUE REFERENCES drill.exercise(id) ON DELETE CASCADE,
    document_id       uuid NOT NULL REFERENCES register.document(id),
    file_sha256       text NOT NULL,
    state             text NOT NULL DEFAULT 'queued'
                      CHECK (state IN ('queued', 'reading', 'review', 'approved', 'failed')),
    error             text CHECK (char_length(error) <= 60),
    attempts          smallint NOT NULL DEFAULT 0,
    next_attempt_at   timestamptz NOT NULL DEFAULT now(),
    lease_until       timestamptz,
    model             text,
    pages             smallint,
    pages_read        smallint,
    requested_by      text NOT NULL,
    requested_by_name text,
    requested_at      timestamptz NOT NULL DEFAULT now(),
    read_at           timestamptz,
    approved_by       text,
    approved_by_name  text,
    approved_at       timestamptz,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    version           integer NOT NULL DEFAULT 1,
    CONSTRAINT ck_checklist_owner CHECK ((axis_id IS NULL) <> (exercise_id IS NULL))
);
CREATE INDEX ix_checklist_queue ON crisis.checklist (next_attempt_at) WHERE state IN ('queued', 'reading');

CREATE TABLE crisis.checklist_task (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    checklist_id     uuid NOT NULL REFERENCES crisis.checklist(id) ON DELETE CASCADE,
    position         smallint NOT NULL,
    action           text NOT NULL CHECK (char_length(action) BETWEEN 3 AND 400),
    owner            text NOT NULL DEFAULT '' CHECK (char_length(owner) <= 160),
    resource         text NOT NULL DEFAULT '' CHECK (char_length(resource) <= 160),
    page             smallint CHECK (page BETWEEN 1 AND 2000),
    quote            text NOT NULL DEFAULT '' CHECK (char_length(quote) <= 300),
    -- The quoted passage was found on that page of the plan (False: the reviewer checks it against the plan).
    quote_found      boolean,
    origin           text NOT NULL CHECK (origin IN ('ai', 'manual')),
    review           text NOT NULL CHECK (review IN ('suggested', 'accepted', 'edited', 'deleted', 'added')),
    -- What the model suggested, kept when the reviewer edits it (how often the model is corrected, item 9).
    suggested        jsonb,
    status           text NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'doing', 'done', 'not_applicable')),
    note             text NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
    status_by_name   text,
    status_at        timestamptz,
    reviewed_by_name text,
    reviewed_at      timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_checklist_task_position UNIQUE (checklist_id, position) DEFERRABLE INITIALLY DEFERRED
);

ALTER TABLE crisis.checklist ENABLE ROW LEVEL SECURITY;
CREATE POLICY checklist_all ON crisis.checklist USING ({_LIST}) WITH CHECK ({_LIST});
ALTER TABLE crisis.checklist_task ENABLE ROW LEVEL SECURITY;
CREATE POLICY checklist_task_all ON crisis.checklist_task USING ({_TASK}) WITH CHECK ({_TASK});
"""

DOWNGRADE = """
DROP TABLE crisis.checklist_task;
DROP TABLE crisis.checklist;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
