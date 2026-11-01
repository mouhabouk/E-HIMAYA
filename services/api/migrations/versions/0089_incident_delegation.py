"""The délégation of the incidents already open or closed (scenario review, 2026-11-01).

``ops.incident.delegation_id`` existed but was never filled, so the staff app showed no délégation on a mission. The
incidents now take it from their centre on every change; this fills the existing ones the same way: the délégation
whose boundary holds the centre, else that of the incident's first located report.

Revision ID: 0089_incident_delegation
Revises: 0088_phase_d
Create Date: 2026-11-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0089_incident_delegation"
down_revision: str | None = "0088_phase_d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE ops.incident i SET delegation_id = d.id
        FROM geo.delegation d
        WHERE i.delegation_id IS NULL AND i.centroid IS NOT NULL
          AND ST_Contains(d.boundary, i.centroid::geometry)
        """
    )
    op.execute(
        """
        UPDATE ops.incident i SET delegation_id = (
            SELECT r.delegation_id FROM reports.report r
            WHERE r.incident_id = i.id AND r.delegation_id IS NOT NULL
            ORDER BY r.received_at LIMIT 1
        )
        WHERE i.delegation_id IS NULL
        """
    )


def downgrade() -> None:
    """Nothing to undo: the column stays, the values are facts of the boundaries."""
