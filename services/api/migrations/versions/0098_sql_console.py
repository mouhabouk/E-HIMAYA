"""The SQL window's history (Yamen, 2026-11-09; docs/sql/console.md).

``platform.sql_query`` keeps every query a system administrator ran in the SQL window: the text, the connection, the
outcome of the last run (rows, duration or error) and how many times it ran. The same text on the same connection is
one entry whose counter rises. Each administrator sees, renames, edits, pins and deletes their own entries only.
This is a working notebook: the audit log keeps every run with its text whatever happens to the history.

Revision ID: 0098_sql_console
Revises: 0097_change_journal
Create Date: 2026-11-09
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0098_sql_console"
down_revision: str | None = "0097_change_journal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
CREATE TABLE platform.sql_query (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner        text NOT NULL,
    owner_name   text,
    connection   text NOT NULL CHECK (char_length(connection) BETWEEN 1 AND 32),
    sql          text NOT NULL CHECK (char_length(sql) BETWEEN 1 AND 20000),
    title        text CHECK (char_length(title) BETWEEN 1 AND 120),
    pinned       boolean NOT NULL DEFAULT false,
    status       text NOT NULL CHECK (status IN ('ok', 'error')),
    command      text CHECK (char_length(command) <= 20),
    rows         integer CHECK (rows >= 0),
    truncated    boolean NOT NULL DEFAULT false,
    duration_ms  integer CHECK (duration_ms >= 0),
    error        text CHECK (char_length(error) <= 2000),
    run_count    integer NOT NULL DEFAULT 1 CHECK (run_count >= 1),
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_run_at  timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_sql_query_text ON platform.sql_query (owner, connection, md5(sql));
CREATE INDEX ix_sql_query_owner_recent ON platform.sql_query (owner, pinned DESC, last_run_at DESC);
COMMENT ON TABLE platform.sql_query IS 'سجل استعلامات نافذة SQL لكل مدير نظام: النص، الاتصال، نتيجة آخر تشغيل، عدد مرات التشغيل.';
"""

DOWNGRADE = """
DROP TABLE platform.sql_query;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
