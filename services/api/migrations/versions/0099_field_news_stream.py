"""News from the field: an agent streams from the staff app without a mission (Yamen, 2026-11-09).

``reports.live_stream.news``: a stream of the source ``crew`` opened from the home of the staff app, with no
mission nor incident. The room sees it on the wall as «news from the field». One active news stream per agent.

Revision ID: 0099_field_news_stream
Revises: 0098_sql_console
Create Date: 2026-11-09
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0099_field_news_stream"
down_revision: str | None = "0098_sql_console"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE reports.live_stream
    ADD COLUMN news boolean NOT NULL DEFAULT false,
    DROP CONSTRAINT ck_live_stream_crew,
    ADD CONSTRAINT ck_live_stream_crew CHECK (
        source <> 'crew' OR (created_by IS NOT NULL AND (news OR assignment_id IS NOT NULL))
    ),
    ADD CONSTRAINT ck_live_stream_news CHECK (NOT news OR (source = 'crew' AND assignment_id IS NULL));
CREATE UNIQUE INDEX ux_live_stream_news_active ON reports.live_stream (created_by)
    WHERE news AND status IN ('pending', 'live');
"""

DOWNGRADE = """
DROP INDEX reports.ux_live_stream_news_active;
DELETE FROM reports.live_stream WHERE news;
ALTER TABLE reports.live_stream
    DROP CONSTRAINT ck_live_stream_news,
    DROP CONSTRAINT ck_live_stream_crew,
    ADD CONSTRAINT ck_live_stream_crew CHECK (source <> 'crew' OR (assignment_id IS NOT NULL AND created_by IS NOT NULL)),
    DROP COLUMN news;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
