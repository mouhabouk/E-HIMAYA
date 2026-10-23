"""Map data layers: the "simulated" mark (phase B1, Yamen 2026-10-23: approximate data while the lists are missing).

``geo.layer.simulated``: the layer holds approximate, invented places for trials and demonstrations, never real ones.
The dashboard and the app show it with the amber ``[SIM]`` mark; a simulated layer can be made public only for a
trial. Default false: every existing layer keeps its meaning. Downgrade drops the column.

Revision ID: 0035_layer_simulated
Revises: 0034_contact_requests
Create Date: 2026-10-23
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0035_layer_simulated"
down_revision: str | None = "0034_contact_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
ALTER TABLE geo.layer ADD COLUMN simulated boolean NOT NULL DEFAULT false;
"""

DOWNGRADE = r"""
ALTER TABLE geo.layer DROP COLUMN simulated;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
