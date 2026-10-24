# covers: C1-b
"""Locked medical files (docs/phase-c/design-medical-axis.md §12): the phone locks the file for the doctors, the server
keeps it without being able to open it, and only those doctors open it, each opening recorded."""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from tests import medical_crypto as mc
from tests.conftest import TokenFactory, accept_charter, bearer, report_body
from tests.test_doctors import GABES, SFAX
from tests.test_medical_committee import cp_doctor
from tests.test_operations import Staff

RECIPIENTS = "/api/v1/medical/recipients"
FILES = "/api/v1/medical/files"
KEY = "/api/v1/me/doctor/key"
SFAX_POINT = {"lat": 34.7406, "lon": 10.7603, "accuracy_m": 8.0}
CARD = {"blood_group": "AB-", "allergies": "pénicilline"}
LOCKED = {"conditions": "diabète de type 1", "medications": "insuline", "other": "pacemaker depuis 2019"}


@pytest.fixture(autouse=True)
async def _empty_committee() -> AsyncIterator[None]:
    async def clear() -> None:
        async with get_system_sessionmaker()() as s, s.begin():
            await s.execute(text("UPDATE identity.doctor SET committee_since = NULL, committee_until = NULL"))

    await clear()
    yield
    await clear()


async def keyed_doctor(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, gouvernorat: int = SFAX, code: str = "482916"
) -> tuple[str, dict[str, str], X25519PrivateKey]:
    doctor_id, headers, _ = await cp_doctor(client, staff, make_token, gouvernorat=gouvernorat)
    private = X25519PrivateKey.generate()
    r = await client.put(
        KEY, json={"public_key": mc.b64(mc.raw_public(private)), "backup": mc.backup(private, code)}, headers=headers
    )
    assert r.status_code == 200 and r.json()["has_key"], r.text
    return doctor_id, headers, private


async def recipients(client: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, dict[str, Any]]:
    r = await client.get(RECIPIENTS, params=SFAX_POINT, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["gouvernorat_codes"] == [SFAX]
    return {x["doctor_id"]: x for x in r.json()["recipients"]}


async def send(client: httpx.AsyncClient, headers: dict[str, str], doctors: list[tuple[str, bytes]]) -> str:
    await accept_charter(client, headers)
    body = report_body(SFAX_POINT, category="medical", medical=CARD, medical_locked=mc.lock(LOCKED, doctors))
    r = await client.post("/api/v1/reports", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def test_the_key_is_kept_locked_and_restored_with_the_code(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory
) -> None:
    pending_headers = bearer(make_token(roles=["citizen"], email=f"p{uuid.uuid4().hex[:6]}@x.tn"))
    from tests.test_doctors import registered

    await registered(client, staff, pending_headers)
    private = X25519PrivateKey.generate()
    body = {"public_key": mc.b64(mc.raw_public(private)), "backup": mc.backup(private, "111111")}
    # Only a verified doctor gets files, so only they set a key.
    assert (await client.put(KEY, json=body, headers=pending_headers)).json()["detail"] == "doctor_not_approved"

    _, headers, private = await keyed_doctor(client, staff, make_token, code="907315")
    saved = (await client.get(KEY, headers=headers)).json()
    assert saved["public_key"] == mc.b64(mc.raw_public(private))
    # A new phone: the code opens the backup; the server never had the key in clear.
    assert mc.raw_public(mc.restore(saved["backup"], "907315")) == mc.raw_public(private)
    for bad in ({**body, "public_key": mc.b64(b"x" * 31)}, {**body, "backup": {**body["backup"], "kdf": "pbkdf2"}}):
        assert (await client.put(KEY, json=bad, headers=headers)).status_code == 422


async def test_only_the_doctors_of_the_place_and_the_committee_open_the_file(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    sfax_id, sfax_headers, sfax_key = await keyed_doctor(client, staff, make_token)
    gabes_id, gabes_headers, gabes_key = await keyed_doctor(client, staff, make_token, gouvernorat=GABES)
    member_id, member_headers, member_key = await keyed_doctor(client, staff, make_token, gouvernorat=GABES)
    admin = staff(["sysadmin"], gouvernorat=None)
    assert (await client.put(f"/api/v1/staff/medical-committee/{member_id}", json={}, headers=admin)).status_code == 200

    citizen = bearer(make_token(roles=["citizen"]))
    found = await recipients(client, citizen)
    assert found[sfax_id]["via"] == "gouvernorat" and found[member_id]["via"] == "committee"
    assert gabes_id not in found
    # The phone also locks it for a doctor of another gouvernorat: the server drops that copy, not the report.
    report_id = await send(
        client,
        citizen,
        [
            (sfax_id, mc.raw_public(sfax_key)),
            (member_id, mc.raw_public(member_key)),
            (gabes_id, mc.raw_public(gabes_key)),
        ],
    )
    stored = await session.scalar(
        text("SELECT ciphertext FROM medical.locked_file WHERE report_id = :r"), {"r": report_id}
    )
    assert stored and b"insuline" not in stored and b"diab" not in stored

    # The operations room reads the emergency card only, and knows the rest is locked for the doctors.
    operator = staff(gouvernorat=SFAX)
    assert (await client.post(f"/api/v1/staff/reports/{report_id}/claim", headers=operator)).status_code == 200
    medical = (await client.get(f"/api/v1/staff/reports/{report_id}/medical", headers=operator)).json()
    assert {k: v for k, v in medical["data"].items() if v} == CARD and medical["locked"] is True

    inbox = (await client.get(FILES, headers=sfax_headers)).json()
    assert [(i["report_id"], i["via"], i["opened_at"]) for i in inbox][:1] == [(report_id, "gouvernorat", None)]
    opened = (await client.post(f"{FILES}/{report_id}/open", json={}, headers=sfax_headers)).json()
    assert mc.open_file(opened, sfax_key) == LOCKED and opened["card"] == CARD
    assert (await client.get(FILES, headers=sfax_headers)).json()[0]["opened_at"]

    assert (await client.post(f"{FILES}/{report_id}/open", json={}, headers=gabes_headers)).status_code == 404
    # A committee member gives a reason; the citizen will see "medical committee", the audit keeps who.
    r = await client.post(f"{FILES}/{report_id}/open", json={}, headers=member_headers)
    assert r.status_code == 422 and r.json()["detail"] == "reason_required"
    r = await client.post(f"{FILES}/{report_id}/open", json={"reason": "Contrôle de qualité"}, headers=member_headers)
    assert mc.open_file(r.json(), member_key) == LOCKED
    openings = (
        await session.execute(
            text("SELECT as_committee, reason FROM medical.file_opening WHERE report_id = :r ORDER BY id"),
            {"r": report_id},
        )
    ).all()
    assert [tuple(o) for o in openings] == [(False, None), (True, "Contrôle de qualité")]
    audited = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'medical.open' AND target = :t"),
        {"t": f"report:{report_id}"},
    )
    assert audited == 2

    # Out of the committee: the committee copies go.
    await client.post(
        f"/api/v1/staff/medical-committee/{member_id}/revoke", json={"reason": "Fin de mandat"}, headers=admin
    )
    assert (
        await client.post(f"{FILES}/{report_id}/open", json={"reason": "x" * 5}, headers=member_headers)
    ).status_code == 404


async def test_a_lost_code_withdrawal_and_retention_drop_the_copies(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    doctor_id, headers, key = await keyed_doctor(client, staff, make_token)
    other_id, other_headers, other_key = await keyed_doctor(client, staff, make_token)
    citizen = bearer(make_token(roles=["citizen"]))
    first = await send(client, citizen, [(doctor_id, mc.raw_public(key)), (other_id, mc.raw_public(other_key))])

    # Forgot the code: a new key; the copies locked for the old one cannot be opened and go.
    new = X25519PrivateKey.generate()
    r = await client.put(
        KEY, json={"public_key": mc.b64(mc.raw_public(new)), "backup": mc.backup(new, "1")}, headers=headers
    )
    assert r.status_code == 200
    assert (await client.get(FILES, headers=headers)).json() == []

    # Withdrawal: the key and the copies go.
    assert (await client.delete("/api/v1/me/doctor", headers=other_headers)).status_code == 204
    keys = await session.scalar(text("SELECT count(*) FROM medical.file_key WHERE report_id = :r"), {"r": first})
    assert keys == 0
    assert (await client.get(KEY, headers=other_headers)).status_code == 404

    # The file goes with the attachment (30 days after closing, or erasure).
    second = await send(client, citizen, [(doctor_id, mc.raw_public(new))])
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(text("DELETE FROM reports.medical_attachment WHERE report_id = :r"), {"r": second})
    left = await session.scalar(text("SELECT count(*) FROM medical.locked_file WHERE report_id = :r"), {"r": second})
    assert left == 0


async def test_old_apps_and_files_without_doctors_still_send_the_report(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff
) -> None:
    citizen = bearer(make_token(roles=["citizen"]))
    await accept_charter(client, citizen)
    # Locked for nobody allowed: the report and its card arrive, no locked part is kept.
    stranger = X25519PrivateKey.generate()
    body = report_body(
        SFAX_POINT, medical=CARD, medical_locked=mc.lock(LOCKED, [(uuid.uuid4(), mc.raw_public(stranger))])
    )
    r = await client.post("/api/v1/reports", json=body, headers=citizen)
    assert r.status_code == 201, r.text
    report_id = r.json()["id"]
    operator = staff(gouvernorat=SFAX)
    assert (await client.post(f"/api/v1/staff/reports/{report_id}/claim", headers=operator)).status_code == 200
    medical = (await client.get(f"/api/v1/staff/reports/{report_id}/medical", headers=operator)).json()
    assert {k: v for k, v in medical["data"].items() if v} == CARD and medical["locked"] is False
    bad = report_body(SFAX_POINT, medical_locked={**mc.lock(LOCKED, [(uuid.uuid4(), b"k" * 32)]), "nonce": "AAAA"})
    assert (await client.post("/api/v1/reports", json=bad, headers=citizen)).status_code == 422
