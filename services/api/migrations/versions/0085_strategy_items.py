"""The strategies menu (docs/phase-s/design-s.md §2.2).

* ``strategy.item``: an item the system administrator adds to the strategies menu (a national strategy, a programme,
  a reference), with its own page in three languages or a link, open to every staff member or to some roles.

Revision ID: 0085_strategy_items
Revises: 0084_snacr
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0085_strategy_items"
down_revision: str | None = "0084_snacr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
CREATE SCHEMA IF NOT EXISTS strategy;

CREATE TABLE strategy.item (
    key text PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_]{1,39}$'),
    name jsonb NOT NULL,
    summary jsonb NOT NULL DEFAULT '{}',
    body jsonb NOT NULL DEFAULT '{}',
    link text CHECK (link IS NULL OR (length(link) <= 512 AND link ~ '^(/[A-Za-z0-9/_\\-]*|https://\\S{4,})$')),
    icon text NOT NULL,
    tone text NOT NULL,
    roles text[] NOT NULL DEFAULT '{}',
    position integer NOT NULL DEFAULT 100,
    active boolean NOT NULL DEFAULT true,
    updated_by text,
    updated_by_name text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (link IS NOT NULL OR body <> '{}')
);

ALTER TABLE strategy.item ENABLE ROW LEVEL SECURITY;
CREATE POLICY item_read ON strategy.item FOR SELECT USING (ehimaya.scope() IN ('system', 'national', 'gouvernorat'));
CREATE POLICY item_write ON strategy.item FOR ALL USING (ehimaya.sees_all()) WITH CHECK (ehimaya.sees_all());
"""

DOWNGRADE = "DROP SCHEMA strategy CASCADE;"


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
