"""Claim deadlines (phase 9 §2, §4.2): the SLA band of a report and when it becomes late if nobody claims it.

Bands come from the BR-20 priority (``reports.report.priority_score``) and the national settings ``sla.bands``; an SOS
report is always critical; a report without a score yet is ``normal``. The due time is ``received_at`` plus the band's
claim delay (``sla.claim_delay_s``). When the priority changes before a claim (AI rescoring), the band and due time
are recomputed from ``received_at`` but never earlier than ``now + RESCORE_GRACE``.
"""

from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.domain import Category
from app.modules.reports.models import Report
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings

Band = Literal["critical", "high", "normal", "low"]
RESCORE_GRACE = timedelta(seconds=5)


def band_of(priority: int | None, category: str, bands: dict[str, Any]) -> Band:
    if category == Category.SOS.value:
        return "critical"
    if priority is None:
        return "normal"
    if priority >= bands["critical"]:
        return "critical"
    if priority >= bands["high"]:
        return "high"
    if priority >= bands["normal"]:
        return "normal"
    return "low"


def is_critical(report: Report) -> bool:
    return report.sla_band == "critical" or report.category == Category.SOS.value


async def thresholds(session: AsyncSession) -> tuple[dict[str, Any], dict[str, Any]]:
    """Current bands and claim delays."""
    return await settings.get(session, settings_domain.SLA_BANDS), await settings.get(
        session, settings_domain.SLA_CLAIM_DELAY
    )


async def assign(session: AsyncSession, report: Report) -> None:
    """Band and due time of a new report, from its baseline priority."""
    bands, delays = await thresholds(session)
    band = band_of(report.priority_score, report.category, bands)
    report.sla_band = band
    report.sla_due_at = report.received_at + timedelta(seconds=int(delays[band]))


def recompute(report: Report, bands: dict[str, Any], delays: dict[str, Any], now: datetime) -> bool:
    """Follow a priority change of an unclaimed report; True when the band changed."""
    band = band_of(report.priority_score, report.category, bands)
    if band == report.sla_band:
        return False
    report.sla_band = band
    report.sla_due_at = max(report.received_at + timedelta(seconds=int(delays[band])), now + RESCORE_GRACE)
    return True
