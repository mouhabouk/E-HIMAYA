"""Citizen rights and retention of rewards data (phase 8), used by ``app.modules.privacy``.

* Export (``GET /me/export``): balance, ledger, badges, certificates and the nominations naming the person.
* Erasure (``POST /me/delete``): ledger rows, queued awards and badges are deleted; nominations naming the person are
  anonymised (subject, reason and evidence removed; kind, year and decision kept for the yearly statistics); their
  certificates lose the holder link and the PDF (full name), while the public verification keeps showing the
  initials, distinction and date it always showed.
* Retention job ``rewards_ledger``: once a report is anonymised (5 years, architecture §5.3) the ledger and the
  queue lose their link to it, so nothing ties the citizen to that report any more. The points stay.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.storage import get_store
from app.modules.rewards.models import BadgeAward, LedgerEntry, Nomination, PendingAward, RewardCertificate
from app.modules.rewards.service import now_utc

BATCH = 1000


class ExportLedgerEntry(BaseModel):
    delta: int
    reason: str
    report_id: uuid.UUID | None
    intervention_id: uuid.UUID | None
    capped: bool
    note: str | None
    created_at: datetime


class ExportBadge(BaseModel):
    level: str
    status: str
    awarded_at: datetime
    decided_at: datetime | None


class ExportCertificate(BaseModel):
    code: str
    distinction: str
    year: int
    issued_at: datetime
    revoked_at: datetime | None


class ExportNomination(BaseModel):
    kind: str
    year: int
    status: str
    reason: str | None
    created_at: datetime


class ExportRewards(BaseModel):
    balance: int
    pending_points: int
    ledger: list[ExportLedgerEntry]
    badges: list[ExportBadge]
    certificates: list[ExportCertificate]
    nominations: list[ExportNomination]


async def export(session: AsyncSession, user_id: uuid.UUID) -> ExportRewards:
    ledger = list(
        await session.scalars(
            select(LedgerEntry).where(LedgerEntry.citizen_id == user_id).order_by(LedgerEntry.created_at)
        )
    )
    pending = list(await session.scalars(select(PendingAward.points).where(PendingAward.citizen_id == user_id)))
    badges = await session.scalars(
        select(BadgeAward).where(BadgeAward.citizen_id == user_id).order_by(BadgeAward.awarded_at)
    )
    certificates = await session.scalars(
        select(RewardCertificate).where(RewardCertificate.subject_id == user_id).order_by(RewardCertificate.issued_at)
    )
    nominations = await session.scalars(
        select(Nomination).where(Nomination.subject_id == user_id).order_by(Nomination.created_at)
    )
    return ExportRewards(
        balance=sum(e.delta for e in ledger),
        pending_points=sum(pending),
        ledger=[
            ExportLedgerEntry(
                delta=e.delta,
                reason=e.reason,
                report_id=e.report_id,
                intervention_id=e.intervention_id,
                capped=e.capped,
                note=e.note,
                created_at=e.created_at,
            )
            for e in ledger
        ],
        badges=[
            ExportBadge(level=b.level, status=b.status, awarded_at=b.awarded_at, decided_at=b.decided_at)
            for b in badges
        ],
        certificates=[
            ExportCertificate(
                code=c.code, distinction=c.distinction, year=c.year, issued_at=c.issued_at, revoked_at=c.revoked_at
            )
            for c in certificates
        ],
        nominations=[
            ExportNomination(kind=n.kind, year=n.year, status=n.status, reason=n.reason, created_at=n.created_at)
            for n in nominations
        ],
    )


def _count(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


async def forget(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    """Erase the person's rewards data inside the caller's transaction (the caller commits)."""
    now = now_utc()
    keys = [
        k
        for k in await session.scalars(
            select(RewardCertificate.pdf_object_key).where(
                RewardCertificate.subject_id == user_id, RewardCertificate.pdf_object_key.is_not(None)
            )
        )
        if k
    ]
    certificates = await session.execute(
        update(RewardCertificate)
        .where(RewardCertificate.subject_id == user_id)
        .values(subject_id=None, pdf_object_key=None, pdf_sha256=None)
        .execution_options(synchronize_session=False)
    )
    nominations = await session.execute(
        update(Nomination)
        .where(Nomination.subject_id == user_id)
        .values(
            subject_id=None,
            reason=None,
            evidence={"report_ids": [], "intervention_ids": []},
            anonymised_at=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    ledger = await session.execute(delete(LedgerEntry).where(LedgerEntry.citizen_id == user_id))
    await session.execute(delete(PendingAward).where(PendingAward.citizen_id == user_id))
    badges = await session.execute(delete(BadgeAward).where(BadgeAward.citizen_id == user_id))
    # Objects first: if the commit then fails, the erasure is asked again and deleting a missing object is a no-op.
    if keys:
        await get_store().delete(*keys)
    return {
        "rewards_ledger_deleted": _count(ledger),
        "rewards_badges_deleted": _count(badges),
        "rewards_nominations_anonymised": _count(nominations),
        "rewards_certificates_detached": _count(certificates),
    }


async def detach_anonymised(session: AsyncSession, settings: Settings, now: datetime) -> int:
    """Retention job: drop the link from ledger rows and queued awards to reports the retention anonymised."""
    del settings, now
    result = await session.execute(
        text(
            "UPDATE rewards.points_ledger SET report_id = NULL WHERE id IN (SELECT l.id FROM rewards.points_ledger l "
            "JOIN reports.report r ON r.id = l.report_id WHERE r.anonymised_at IS NOT NULL "
            "LIMIT :n FOR UPDATE OF l SKIP LOCKED)"
        ),
        {"n": BATCH},
    )
    pending = await session.execute(
        text(
            "UPDATE rewards.pending_award SET report_id = NULL WHERE id IN (SELECT p.id FROM rewards.pending_award p "
            "JOIN reports.report r ON r.id = p.report_id WHERE r.anonymised_at IS NOT NULL "
            "LIMIT :n FOR UPDATE OF p SKIP LOCKED)"
        ),
        {"n": BATCH},
    )
    return _count(result) + _count(pending)
