"""Phase A settings (docs/phase-a/design.md §3): the app release and the extra words of the language filter.

* ``app.release``: latest Android version and build offered to the phones, the oldest build still allowed, release
  notes in ar/fr/en and the download channel (``server`` now, ``play`` once the app is in the store).
* ``moderation.extra_terms``: words the system administrator adds to the built-in list of the respectful-language
  filter (app/modules/moderation).

No new table: two rows in ``platform.setting``. Downgrade deletes them (the defaults in the code apply again).

Revision ID: 0031_phase_a_settings
Revises: 0030_evidence_anchor
Create Date: 2026-10-23
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0031_phase_a_settings"
down_revision: str | None = "0030_evidence_anchor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_script(
        """
        INSERT INTO platform.setting (key, value) VALUES
            ('app.release', '{"latest_version": "0.2.0", "latest_build": 1, "min_build": 1,
              "notes": {"ar": "", "fr": "", "en": ""}, "channel": "server", "download_url": null}'),
            ('moderation.extra_terms', '[]')
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    run_script("DELETE FROM platform.setting WHERE key IN ('app.release', 'moderation.extra_terms');")
