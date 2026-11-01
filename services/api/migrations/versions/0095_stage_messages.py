"""A spoken word at every step of the mission (Yamen, 2026-11-01): a text of the scene keeps the step the mission had
reached (from «غادرت الوحدة» to the return) and whether it was spoken, transcribed and corrected.

Revision ID: 0095_stage_messages
Revises: 0094_camera_bridge
Create Date: 2026-11-01
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0095_stage_messages"
down_revision: str | None = "0094_camera_bridge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE ops.field_attachment ADD COLUMN stage text
    CONSTRAINT ck_field_attachment_stage
    CHECK (stage IN ('en_route', 'on_scene', 'left_scene', 'at_hospital', 'available', 'back_at_unit'));
ALTER TABLE ops.field_attachment ADD COLUMN spoken boolean NOT NULL DEFAULT false;
"""

DOWNGRADE = """
ALTER TABLE ops.field_attachment DROP COLUMN spoken;
ALTER TABLE ops.field_attachment DROP COLUMN stage;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
