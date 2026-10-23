"""Medical file attached to a report (phase B2, docs/phase-b/design-b2.md §5, addition 7b): stored only when the
reporter ticks it, encrypted, shown only to the staff who may see the reporter, each opening audited, deleted after
the case is closed and on erasure."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.modules.privacy import retention
from tests.conftest import TokenFactory, accept_charter, bearer, device_headers, report_body

Staff = Callable[..., dict[str, str]]
MEDICAL = {
    "sex": "female",
    "birth_date": "1984-03-02",
    "blood_group": "AB-",
    "allergies": "pénicilline",
    "conditions": "diabète de type 1",
    "medications": "insuline",
    "contact_name": "Karim",
    "contact_phone": "+21698765432",
}


async def _report(client: httpx.AsyncClient, headers: dict[str, str], **extra: Any) -> dict[str, Any]:
    await accept_charter(client, headers)
    r = await client.post("/api/v1/reports", json=report_body(category="medical", **extra), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_attached_only_when_ticked_and_encrypted(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff, session: AsyncSession
) -> None:
    citizen = bearer(make_token(roles=["citizen"]))
    without = await _report(client, citizen)
    with_file = await _report(client, citizen, medical=MEDICAL)
    operator = staff(gouvernorat=61)
    plain = (await client.get(f"/api/v1/staff/reports/{without['id']}", headers=operator)).json()
    assert plain["medical_attached"] is False
    detail = (await client.get(f"/api/v1/staff/reports/{with_file['id']}", headers=operator)).json()
    assert detail["medical_attached"] is True
    raw = await session.scalar(
        text("SELECT data_enc FROM reports.medical_attachment WHERE report_id = :i"), {"i": with_file["id"]}
    )
    assert raw is not None and b"insuline" not in bytes(raw) and b"AB-" not in bytes(raw)
    # Nothing at all, or only empty fields: no row.
    empty = await _report(client, citizen, medical={"allergies": None})
    assert (
        await session.scalar(
            text("SELECT count(*) FROM reports.medical_attachment WHERE report_id = :i"), {"i": empty["id"]}
        )
        == 0
    )
    r = await client.post("/api/v1/reports", json=report_body(medical={"blood_group": "Z+"}), headers=device_headers())
    assert r.status_code in (422, 428)


async def test_shown_to_the_handling_room_only_and_audited(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff, session: AsyncSession
) -> None:
    citizen = bearer(make_token(roles=["citizen"]))
    report = await _report(client, citizen, medical=MEDICAL)
    url = f"/api/v1/staff/reports/{report['id']}/medical"
    operator = staff(gouvernorat=61)
    # Like the reporter's identity: not before the operator's room handles (claims) the report.
    assert (await client.get(url, headers=operator)).status_code == 403
    assert (await client.post(f"/api/v1/staff/reports/{report['id']}/claim", headers=operator)).status_code == 200
    r = await client.get(url, headers=operator)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["blood_group"] == "AB-" and data["medications"] == "insuline" and data["birth_date"] == "1984-03-02"
    assert data["contact_phone"] == "+21698765432"
    audited = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'report.medical_view' AND target = :t"),
        {"t": f"report:{report['id']}"},
    )
    assert audited == 1
    # Another gouvernorat does not even learn the report exists.
    assert (await client.get(url, headers=staff(gouvernorat=11))).status_code == 404
    # A report without a file.
    other = await _report(client, citizen)
    await client.post(f"/api/v1/staff/reports/{other['id']}/claim", headers=operator)
    r = await client.get(f"/api/v1/staff/reports/{other['id']}/medical", headers=operator)
    assert r.status_code == 404 and r.json()["detail"] == "no_medical_file"


async def test_deleted_after_closing_and_on_erasure(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    citizen = bearer(make_token(roles=["citizen"]))
    closed = await _report(client, citizen, medical=MEDICAL)
    still_open = await _report(client, citizen, medical=MEDICAL)
    await session.execute(
        text("UPDATE reports.report SET status = 'closed', updated_at = now() - interval '31 days' WHERE id = :i"),
        {"i": closed["id"]},
    )
    await session.commit()
    async with get_system_sessionmaker()() as s, s.begin():
        while await retention.purge_medical_attachments(s, get_settings(), datetime.now(UTC)):
            pass

    async def count(report_id: str) -> int:
        return int(
            await session.scalar(
                text("SELECT count(*) FROM reports.medical_attachment WHERE report_id = :i"), {"i": report_id}
            )
            or 0
        )

    assert await count(closed["id"]) == 0 and await count(still_open["id"]) == 1
    # Erasure: the report stays (legal retention), the medical file goes.
    r = await client.post("/api/v1/me/delete", json={"confirm": "DELETE"}, headers=citizen)
    assert r.status_code == 202, r.text
    assert await count(still_open["id"]) == 0
    assert await session.scalar(text("SELECT count(*) FROM reports.report WHERE id = :i"), {"i": still_open["id"]}) == 1
    assert timedelta(days=30) == timedelta(days=get_settings().retention_medical_days)
