"""The record of a mission and the SNACR indicators drawn from it (docs/phase-s/design-s2.md).

* ``ops.assignment``: when the team left the scene, reached the hospital and came back to its unit, how many agents
  it had, what it used (water, foam, powder...) and who gave each time (the app, a text message or the room). The
  times follow one another, and the return comes after the departure. The check is not run on older rows.
* ``ops.crew_event``: two new kinds, a step of the mission (``milestone``) and the crew and resources (``record``).
* ``snacr.intervention``: the same times and the crew, for the archive and for a year drawn from the records
  (``snacr.dataset.source = 'live'``).

Revision ID: 0086_mission_record
Revises: 0085_strategy_items
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0086_mission_record"
down_revision: str | None = "0085_strategy_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "'ack', 'status', 'first_report', 'casualties', 'transport', 'alert', 'attachment', 'detailed_report'"

UPGRADE = f"""
ALTER TABLE ops.assignment
    ADD COLUMN left_scene_at timestamptz,
    ADD COLUMN at_hospital_at timestamptz,
    ADD COLUMN available_at timestamptz,
    ADD COLUMN back_at_unit_at timestamptz,
    ADD COLUMN crew_count smallint CHECK (crew_count BETWEEN 1 AND 60),
    ADD COLUMN consumables jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(consumables) = 'object'),
    ADD COLUMN time_sources jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(time_sources) = 'object');
ALTER TABLE ops.assignment ADD CONSTRAINT ck_assignment_times_order CHECK (
    (on_scene_at IS NULL OR en_route_at IS NULL OR on_scene_at >= en_route_at)
    AND (left_scene_at IS NULL OR (on_scene_at IS NOT NULL AND left_scene_at >= on_scene_at))
    AND (at_hospital_at IS NULL OR (left_scene_at IS NOT NULL AND at_hospital_at >= left_scene_at))
    AND (available_at IS NULL OR (left_scene_at IS NOT NULL AND available_at >= coalesce(at_hospital_at, left_scene_at)))
    AND (back_at_unit_at IS NULL OR (en_route_at IS NOT NULL AND back_at_unit_at > en_route_at
        AND back_at_unit_at >= coalesce(available_at, at_hospital_at, left_scene_at, on_scene_at, en_route_at)))
) NOT VALID;

ALTER TABLE ops.crew_event DROP CONSTRAINT crew_event_kind_check;
ALTER TABLE ops.crew_event ADD CONSTRAINT crew_event_kind_check CHECK (kind IN ({KINDS}, 'milestone', 'record'));

ALTER TABLE snacr.intervention
    ADD COLUMN left_at timestamptz,
    ADD COLUMN hospital_at timestamptz,
    ADD COLUMN returned_at timestamptz,
    ADD COLUMN crew_count smallint CHECK (crew_count BETWEEN 1 AND 500);
ALTER TABLE snacr.dataset DROP CONSTRAINT dataset_source_check;
ALTER TABLE snacr.dataset ADD CONSTRAINT dataset_source_check CHECK (source IN ('office', 'simulated', 'live'));
"""

DOWNGRADE = f"""
DELETE FROM snacr.dataset WHERE source = 'live';
ALTER TABLE snacr.dataset DROP CONSTRAINT dataset_source_check;
ALTER TABLE snacr.dataset ADD CONSTRAINT dataset_source_check CHECK (source IN ('office', 'simulated'));
ALTER TABLE snacr.intervention DROP COLUMN left_at, DROP COLUMN hospital_at, DROP COLUMN returned_at,
    DROP COLUMN crew_count;

DELETE FROM ops.crew_event WHERE kind IN ('milestone', 'record');
ALTER TABLE ops.crew_event DROP CONSTRAINT crew_event_kind_check;
ALTER TABLE ops.crew_event ADD CONSTRAINT crew_event_kind_check CHECK (kind IN ({KINDS}));

ALTER TABLE ops.assignment DROP CONSTRAINT ck_assignment_times_order;
ALTER TABLE ops.assignment DROP COLUMN left_scene_at, DROP COLUMN at_hospital_at, DROP COLUMN available_at,
    DROP COLUMN back_at_unit_at, DROP COLUMN crew_count, DROP COLUMN consumables, DROP COLUMN time_sources;
"""  # noqa: S608 (constant SQL, nothing is interpolated from input)


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
