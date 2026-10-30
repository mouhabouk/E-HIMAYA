# covers: C1-a
"""The medical committee (docs/phase-c/design-medical-axis.md §11): appointed by the system administrator."""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.doctors import service
from app.modules.settings import thresholds
from tests.conftest import TokenFactory, bearer
from tests.test_doctors import GABES, SFAX, approve, registered
from tests.test_operations import Staff

COMMITTEE = "/api/v1/staff/medical-committee"
ME = "/api/v1/me/doctor"
CP = {"kind": "civil_protection", "cp_unit": "Direction régionale", "cp_staff_no": "PC/4521"}


@pytest.fixture(autouse=True)
async def _empty_committee() -> AsyncIterator[None]:
    async def clear() -> None:
        async with get_system_sessionmaker()() as s, s.begin():
            await s.execute(
                text("UPDATE identity.doctor SET committee_since = NULL, committee_until = NULL, committee_by = NULL")
            )

    await clear()
    yield
    await clear()


async def cp_doctor(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, gouvernorat: int = SFAX, **overrides: Any
) -> tuple[str, dict[str, str], str]:
    """An approved Civil Protection doctor: id, app headers and e-mail."""
    email = f"cp{uuid.uuid4().hex[:8]}@example.tn"
    headers = bearer(make_token(roles=["citizen"], email=email, email_verified=True, name="Doctor"))
    doctor_id, _ = await registered(client, staff, headers, gouvernorat_code=gouvernorat, **{**CP, **overrides})
    await approve(client, staff, doctor_id, gouvernorat)
    return doctor_id, headers, email


async def test_sysadmin_appoints_renews_and_revokes(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    admin = staff(["sysadmin"], gouvernorat=None, email="admin@protectioncivile.tn")
    doctor_id, headers, _ = await cp_doctor(client, staff, make_token, gouvernorat=GABES)
    volunteer_id, _ = await registered(client, staff, bearer(make_token(roles=["citizen"], email="v@x.tn")))
    await approve(client, staff, volunteer_id)

    # Only a national system administrator manages the committee.
    for headers_ in (staff(["sysadmin"]), staff(["medical_coordinator"], gouvernorat=None), staff(["ops_manager"])):
        assert (await client.get(COMMITTEE, headers=headers_)).status_code == 403
    workplace = (await client.get(ME, headers=headers)).json()["workplace"]
    candidates = (await client.get(f"{COMMITTEE}/candidates", params={"q": workplace}, headers=admin)).json()
    assert [c["id"] for c in candidates] == [doctor_id]
    everyone = (await client.get(f"{COMMITTEE}/candidates", params={"limit": 100}, headers=admin)).json()
    assert volunteer_id not in {c["id"] for c in everyone}
    assert all("licence_no" not in c and "phone" not in c for c in candidates)

    # A volunteer specialist is never appointed.
    r = await client.put(f"{COMMITTEE}/{volunteer_id}", json={}, headers=admin)
    assert r.status_code == 409 and r.json()["detail"] == "not_civil_protection_doctor"

    r = await client.put(f"{COMMITTEE}/{doctor_id}", json={"months": 6, "reason": "Comité 2027"}, headers=admin)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["max_members"] == thresholds.DEFAULTS["doctors.committee_max"]
    assert [m["id"] for m in out["members"]] == [doctor_id]
    assert out["members"][0]["committee_until"]
    # The doctor sees it in the app; they are no longer a candidate.
    assert (await client.get(ME, headers=headers)).json()["committee_until"]
    assert (await client.get(f"{COMMITTEE}/candidates", params={"q": workplace}, headers=admin)).json() == []

    first_until = out["members"][0]["committee_until"]
    r = await client.put(f"{COMMITTEE}/{doctor_id}", json={"months": 12}, headers=admin)
    assert r.json()["members"][0]["committee_until"] > first_until
    actions = (
        await session.scalars(
            text("SELECT action FROM audit.log WHERE target = :t AND action LIKE 'medical_committee.%' ORDER BY id"),
            {"t": f"doctor:{doctor_id}"},
        )
    ).all()
    assert actions == ["medical_committee.appoint", "medical_committee.renew"]

    assert (await client.post(f"{COMMITTEE}/{doctor_id}/revoke", json={"reason": ""}, headers=admin)).status_code == 422
    r = await client.post(f"{COMMITTEE}/{doctor_id}/revoke", json={"reason": "Fin de mandat"}, headers=admin)
    assert r.status_code == 200 and r.json()["members"] == []
    assert (await client.get(ME, headers=headers)).json()["committee_until"] is None
    r = await client.post(f"{COMMITTEE}/{doctor_id}/revoke", json={"reason": "Encore"}, headers=admin)
    assert r.status_code == 404
    mails = await session.scalar(
        text("SELECT count(*) FROM notify.outbox WHERE payload::text LIKE '%comité médical%'"),
    )
    assert mails and mails >= 3


async def test_no_self_appointment_and_a_seat_limit(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory
) -> None:
    doctor_id, _, email = await cp_doctor(client, staff, make_token)
    # The administrator who is also a Civil Protection doctor cannot open every file to themselves.
    own = staff(["sysadmin"], gouvernorat=None, email=email.upper())
    r = await client.put(f"{COMMITTEE}/{doctor_id}", json={}, headers=own)
    assert r.status_code == 403 and r.json()["detail"] == "self_appointment"

    admin = staff(["sysadmin"], gouvernorat=None, email="admin@protectioncivile.tn")
    most = thresholds.DEFAULTS["doctors.committee_max"]
    seated = [doctor_id] + [(await cp_doctor(client, staff, make_token))[0] for _ in range(most - 1)]
    for d in seated:
        assert (await client.put(f"{COMMITTEE}/{d}", json={}, headers=admin)).status_code == 200
    extra, _, _ = await cp_doctor(client, staff, make_token)
    r = await client.put(f"{COMMITTEE}/{extra}", json={}, headers=admin)
    assert r.status_code == 409 and r.json()["detail"] == "committee_full"
    # Renewing a member does not need a free seat.
    assert (await client.put(f"{COMMITTEE}/{seated[0]}", json={}, headers=admin)).status_code == 200


async def test_membership_ends_with_the_doctor_status(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    admin = staff(["sysadmin"], gouvernorat=None)
    coordinator = staff(["medical_coordinator"], gouvernorat=SFAX)
    suspended, _, _ = await cp_doctor(client, staff, make_token)
    changed, changed_headers, _ = await cp_doctor(client, staff, make_token)
    expired, _, _ = await cp_doctor(client, staff, make_token)
    for d in (suspended, changed, expired):
        assert (await client.put(f"{COMMITTEE}/{d}", json={}, headers=admin)).status_code == 200

    r = await client.post(
        f"/api/v1/staff/doctors/{suspended}/review",
        json={"decision": "suspend", "reason": "Enquête"},
        headers=coordinator,
    )
    assert r.status_code == 200 and r.json()["committee_until"] is None
    # Becoming a volunteer specialist sends the doctor back to review and out of the committee.
    mine = (await client.get(ME, headers=changed_headers)).json()
    body = {k: mine[k] for k in ("specialties", "licence_no", "workplace", "gouvernorat_code")}
    r = await client.put(
        ME,
        json={**body, "kind": "volunteer", "terms_version": "1", "version": mine["version"]},
        headers=changed_headers,
    )
    assert r.status_code == 200 and r.json()["status"] == "pending" and r.json()["committee_until"] is None

    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(
            text(
                "UPDATE identity.doctor SET committee_since = now() - interval '2 days',"
                " committee_until = now() - interval '1 day' WHERE user_id = :id"
            ),
            {"id": expired},
        )
        assert await service.expire_committee(s) >= 1
    assert (await client.get(COMMITTEE, headers=admin)).json()["members"] == []
