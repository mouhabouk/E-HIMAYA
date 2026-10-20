"""English (phase 9, docs/api/phase-9-contract.md §8).

* ``geo.gouvernorat.name_en`` — English names (the French transliteration without diacritics, as usual in English:
  "Beja", "Gabes"), seeded here, then ``NOT NULL``. ``GET /api/v1/geo/gouvernorats?lang=en`` uses it.
* ``analytics.schedule`` and ``analytics.report``: ``lang`` also accepts ``en``.

Downgrade: English documents and schedules have no Arabic or French equivalent; they are switched to French (the
fallback of every English label) before the checks are narrowed again.

Revision ID: 0024_i18n_english
Revises: 0023_audit_scope
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0024_i18n_english"
down_revision: str | None = "0023_audit_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
ALTER TABLE geo.gouvernorat ADD COLUMN name_en text;
UPDATE geo.gouvernorat g SET name_en = v.name_en FROM (VALUES
    (11, 'Tunis'), (12, 'Ariana'), (13, 'Ben Arous'), (14, 'Manouba'),
    (21, 'Nabeul'), (22, 'Zaghouan'), (23, 'Bizerte'),
    (31, 'Beja'), (32, 'Jendouba'), (33, 'Kef'), (34, 'Siliana'),
    (41, 'Kairouan'), (42, 'Kasserine'), (43, 'Sidi Bouzid'),
    (51, 'Sousse'), (52, 'Monastir'), (53, 'Mahdia'),
    (61, 'Sfax'),
    (71, 'Gafsa'), (72, 'Tozeur'), (73, 'Kebili'),
    (81, 'Gabes'), (82, 'Medenine'), (83, 'Tataouine')
) AS v(code, name_en) WHERE g.code = v.code;
-- Any gouvernorat added outside the reference seed falls back to its French name.
UPDATE geo.gouvernorat SET name_en = name_fr WHERE name_en IS NULL;
ALTER TABLE geo.gouvernorat ALTER COLUMN name_en SET NOT NULL;

ALTER TABLE analytics.schedule DROP CONSTRAINT ck_schedule_lang;
ALTER TABLE analytics.schedule ADD CONSTRAINT ck_schedule_lang CHECK (lang IN ('ar', 'fr', 'en'));
ALTER TABLE analytics.report DROP CONSTRAINT ck_report_lang;
ALTER TABLE analytics.report ADD CONSTRAINT ck_report_lang CHECK (lang IN ('ar', 'fr', 'en'));
"""


DOWNGRADE = r"""
UPDATE analytics.report SET lang = 'fr' WHERE lang = 'en';
UPDATE analytics.schedule SET lang = 'fr' WHERE lang = 'en';
ALTER TABLE analytics.report DROP CONSTRAINT ck_report_lang;
ALTER TABLE analytics.report ADD CONSTRAINT ck_report_lang CHECK (lang IN ('ar', 'fr'));
ALTER TABLE analytics.schedule DROP CONSTRAINT ck_schedule_lang;
ALTER TABLE analytics.schedule ADD CONSTRAINT ck_schedule_lang CHECK (lang IN ('ar', 'fr'));
ALTER TABLE geo.gouvernorat DROP COLUMN name_en;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
