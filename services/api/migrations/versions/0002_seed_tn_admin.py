"""Seed the Tunisian administrative reference: 24 gouvernorats and their délégations.

Source: services/api/seed/*.csv (see seed/README.md for provenance).

Revision ID: 0002_seed_tn_admin
Revises: 0001_core_schema
Create Date: 2026-10-19
"""

import csv
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_tn_admin"
down_revision: str | None = "0001_core_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


def _read(name: str) -> list[dict[str, str]]:
    with (SEED_DIR / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def upgrade() -> None:
    gouvernorats = [
        {"code": int(r["code"]), "iso_code": r["iso_code"], "name_ar": r["name_ar"], "name_fr": r["name_fr"]}
        for r in _read("gouvernorats.csv")
    ]
    op.get_bind().execute(
        sa.text(
            "INSERT INTO geo.gouvernorat (code, iso_code, name_ar, name_fr) "
            "VALUES (:code, :iso_code, :name_ar, :name_fr)"
        ),
        gouvernorats,
    )

    counters: dict[int, int] = {}
    delegations = []
    for r in _read("delegations.csv"):
        gov = int(r["gouvernorat_code"])
        counters[gov] = counters.get(gov, 0) + 1
        seq = counters[gov]
        delegations.append(
            {
                "id": gov * 100 + seq,
                "code": f"TN-{gov}-{seq:02d}",
                "gouvernorat_code": gov,
                "name_ar": r["name_ar"],
                "name_fr": r["name_fr"],
            }
        )
    op.get_bind().execute(
        sa.text(
            "INSERT INTO geo.delegation (id, code, gouvernorat_code, name_ar, name_fr) "
            "VALUES (:id, :code, :gouvernorat_code, :name_ar, :name_fr)"
        ),
        delegations,
    )


def downgrade() -> None:
    op.execute("DELETE FROM geo.delegation")
    op.execute("DELETE FROM geo.gouvernorat")
