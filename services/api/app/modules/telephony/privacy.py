"""Citizen rights over telephony data (phase 7), used by ``app.modules.privacy.router``.

Calls and SMS are tied to a person only through a phone number. A citizen is matched by the phone number they
verified (an unverified number proves nothing), and by the SMS that created their own reports.

* Export: the calls from or to that number and the SMS received from it (no recording: available on request to
  the authority, like stream recordings).
* Erasure: the number is removed from the calls and SMS (encrypted value and blind index). Calls, recordings and
  reports stay for their legal retention period without any link to the person.

Calls are staff data under row-level security; both steps reach the person's own calls with the system scope (the
match on their verified number being the check).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import ColumnElement, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system
from app.modules.identity.models import Profile
from app.modules.reports.models import Report
from app.modules.telephony.domain import caller_index, normalize_caller
from app.modules.telephony.models import Call, SmsInbound
from app.modules.telephony.sms import sender_hash


class ExportCall(BaseModel):
    id: uuid.UUID
    direction: str
    started_at: datetime
    answered_at: datetime | None
    ended_at: datetime | None
    status: str
    report_id: uuid.UUID | None
    recorded: bool


class ExportSms(BaseModel):
    received_at: datetime
    category: str | None
    outcome: str
    report_id: uuid.UUID | None


def _verified_number(profile: Profile | None) -> str | None:
    if profile is None or profile.phone_verified_at is None or not profile.phone:
        return None
    return normalize_caller(profile.phone)


def _sms_filter(user_id: uuid.UUID, number: str | None) -> ColumnElement[bool]:
    own_reports = SmsInbound.report_id.in_(select(Report.id).where(Report.user_id == user_id))
    return or_(own_reports, SmsInbound.sender_hash == sender_hash(number)) if number else own_reports


async def export(session: AsyncSession, user_id: uuid.UUID) -> tuple[list[ExportCall], list[ExportSms]]:
    number = _verified_number(await session.get(Profile, user_id))
    calls: list[ExportCall] = []
    if number is not None:
        async with as_system(session):
            rows = (
                await session.scalars(
                    select(Call).where(Call.caller_hash == caller_index(number)).order_by(Call.started_at)
                )
            ).all()
        calls = [
            ExportCall(
                id=c.id,
                direction=c.direction,
                started_at=c.started_at,
                answered_at=c.answered_at,
                ended_at=c.ended_at,
                status=c.status,
                report_id=c.report_id,
                recorded=c.recording_media_id is not None,
            )
            for c in rows
        ]
    sms = await session.scalars(select(SmsInbound).where(_sms_filter(user_id, number)).order_by(SmsInbound.received_at))
    messages = [
        ExportSms(received_at=s.received_at, category=s.category, outcome=s.outcome, report_id=s.report_id) for s in sms
    ]
    return calls, messages


async def forget(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    """Detach the person's number from calls and SMS. Call before the profile is deleted."""
    number = _verified_number(await session.get(Profile, user_id))
    calls = 0
    if number is not None:
        async with as_system(session):
            result = await session.execute(
                update(Call)
                .where(Call.caller_hash == caller_index(number))
                .values(caller_number=None, caller_hash=None)
                .execution_options(synchronize_session=False)
            )
        calls = int(result.rowcount or 0)  # type: ignore[attr-defined]
    result = await session.execute(
        update(SmsInbound)
        .where(_sms_filter(user_id, number))
        .values(sender_number=None, sender_hash=None)
        .execution_options(synchronize_session=False)
    )
    return {"calls_detached": calls, "sms_detached": int(result.rowcount or 0)}  # type: ignore[attr-defined]
