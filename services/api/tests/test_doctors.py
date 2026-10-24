# covers: C1-a
"""Phase C1-a (docs/phase-c/design-medical-axis.md §2): doctors register from the app and are checked by staff."""

import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TokenFactory, bearer
from tests.test_operations import Staff, with_profile

ME = "/api/v1/me/doctor"
STAFF = "/api/v1/staff/doctors"
DIRECTORY = "/api/v1/doctors/directory"
SFAX, GABES = 61, 81


@pytest.fixture
def citizen(make_token: TokenFactory) -> Callable[[], dict[str, str]]:
    def _make() -> dict[str, str]:
        email = f"d{uuid.uuid4().hex[:8]}@example.tn"
        return bearer(make_token(roles=["citizen"], email=email, email_verified=True, name="Doctor"))

    return _make


def application(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "volunteer",
        "specialties": ["cardiology", "internal_medicine"],
        "licence_no": "TN-12345",
        "workplace": f"Clinique {uuid.uuid4().hex[:10]}",
        "gouvernorat_code": SFAX,
        "terms_version": "1",
    }
    body.update(overrides)
    return body


async def registered(
    client: httpx.AsyncClient, staff: Staff, headers: dict[str, str], **overrides: Any
) -> tuple[str, dict[str, Any]]:
    """Registers a doctor and returns their id (found by the unique workplace) and the body sent."""
    await with_profile(client, headers)
    body = application(**overrides)
    r = await client.put(ME, json=body, headers=headers)
    assert r.status_code == 200, r.text
    reviewer = staff(["medical_coordinator"], gouvernorat=body["gouvernorat_code"])
    items = (await client.get(STAFF, params={"q": body["workplace"]}, headers=reviewer)).json()["items"]
    assert len(items) == 1, items
    return items[0]["id"], body


async def approve(client: httpx.AsyncClient, staff: Staff, doctor_id: str, gouvernorat: int = SFAX) -> None:
    reviewer = staff(["medical_coordinator"], gouvernorat=gouvernorat)
    r = await client.post(f"{STAFF}/{doctor_id}/review", json={"decision": "approve"}, headers=reviewer)
    assert r.status_code == 200 and r.json()["status"] == "approved", r.text


async def test_registration_needs_a_complete_profile_and_valid_details(
    client: httpx.AsyncClient, citizen: Callable[[], dict[str, str]]
) -> None:
    headers = citizen()
    assert (await client.get(ME, headers=headers)).json()["detail"] == "not_doctor"
    assert (await client.put(ME, json=application(), headers=headers)).json()["detail"] == "profile_incomplete"
    await with_profile(client, headers)
    for body, error in (
        (application(terms_version="0"), "unknown_terms_version"),
        (application(kind="civil_protection"), "cp_details_required"),
        (application(gouvernorat_code=19), "invalid_gouvernorat"),
    ):
        r = await client.put(ME, json=body, headers=headers)
        assert r.status_code == 422 and r.json()["detail"] == error, r.text
    for body in (application(specialties=[]), application(specialties=["magic"]), application(licence_no="12 <3>")):
        assert (await client.put(ME, json=body, headers=headers)).status_code == 422
    # Anonymous devices cannot register.
    r = await client.put(ME, json=application(), headers={"X-Device-Id": str(uuid.uuid4())})
    assert r.status_code in (401, 403)


async def test_civil_protection_doctor_is_reviewed_in_their_gouvernorat(
    client: httpx.AsyncClient, staff: Staff, citizen: Callable[[], dict[str, str]], session: AsyncSession
) -> None:
    headers = citizen()
    doctor_id, _ = await registered(
        client,
        staff,
        headers,
        kind="civil_protection",
        cp_unit="Direction régionale de Sfax",
        cp_staff_no="PC/4521",
        specialties=["emergency_medicine"],
    )
    mine = (await client.get(ME, headers=headers)).json()
    assert mine["status"] == "pending" and mine["cp_staff_no"] == "PC/4521" and not mine["available"]

    # Another gouvernorat's coordinator does not see them; an operator has no access at all.
    elsewhere = staff(["medical_coordinator"], gouvernorat=GABES)
    assert (await client.get(f"{STAFF}/{doctor_id}", headers=elsewhere)).status_code == 404
    assert (await client.get(STAFF, headers=staff(["operator"]))).status_code == 403
    coordinator = staff(["medical_coordinator"], gouvernorat=SFAX)
    pending = (await client.get(STAFF, params={"status": "pending"}, headers=coordinator)).json()["items"]
    assert pending and all(i["status"] == "pending" for i in pending)
    assert "licence_no" not in pending[0] and "phone" not in pending[0]

    detail = (await client.get(f"{STAFF}/{doctor_id}", headers=coordinator)).json()
    assert detail["licence_no"] == "TN-12345" and detail["cp_staff_no"] == "PC/4521" and detail["phone"]
    viewed = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'doctor.view' AND target = :t"),
        {"t": f"doctor:{doctor_id}"},
    )
    assert viewed == 1

    r = await client.post(f"{STAFF}/{doctor_id}/review", json={"decision": "reject"}, headers=coordinator)
    assert r.json()["detail"] == "reason_required"
    r = await client.post(
        f"{STAFF}/{doctor_id}/review", json={"decision": "suspend", "reason": "x"}, headers=coordinator
    )
    assert r.json()["detail"] == "invalid_transition"
    await approve(client, staff, doctor_id)
    detail = (await client.get(f"{STAFF}/{doctor_id}", headers=coordinator)).json()
    assert [r["decision"] for r in detail["reviews"]] == ["approve"]
    mail = await session.scalar(
        text("SELECT count(*) FROM notify.outbox WHERE channel = 'email' AND payload->>'text' LIKE :p"),
        {"p": "%statut de médecin%"},
    )
    assert mail and mail >= 1
    reviewed = await session.scalar(
        text("SELECT details->>'to' FROM audit.log WHERE action = 'doctor.review' AND target = :t"),
        {"t": f"doctor:{doctor_id}"},
    )
    assert reviewed == "approved"


async def test_checked_details_changed_means_a_new_review(
    client: httpx.AsyncClient, staff: Staff, citizen: Callable[[], dict[str, str]]
) -> None:
    headers = citizen()
    doctor_id, body = await registered(client, staff, headers)
    await approve(client, staff, doctor_id)
    version = (await client.get(ME, headers=headers)).json()["version"]
    # The workplace's wording is not checked: still approved.
    r = await client.put(
        ME, json={**body, "workplace": body["workplace"] + " Nord", "version": version}, headers=headers
    )
    assert r.json()["status"] == "approved", r.text
    stale = {**body, "licence_no": "TN-99999", "version": version}
    assert (await client.put(ME, json=stale, headers=headers)).json()["detail"] == "version_conflict"
    r = await client.put(ME, json={**stale, "version": r.json()["version"]}, headers=headers)
    assert r.json()["status"] == "pending" and not r.json()["available"], r.text


async def test_availability_and_referral_directory(
    client: httpx.AsyncClient, staff: Staff, citizen: Callable[[], dict[str, str]]
) -> None:
    cardio = citizen()
    cardio_id, _ = await registered(client, staff, cardio, specialties=["cardiology"])
    r = await client.post(f"{ME}/availability", json={"available": True}, headers=cardio)
    assert r.json()["detail"] == "doctor_not_approved"
    # Not a doctor, or not approved yet: no access to the list.
    assert (await client.get(DIRECTORY, headers=citizen())).status_code == 404
    assert (await client.get(DIRECTORY, headers=cardio)).json()["detail"] == "doctor_not_approved"

    await approve(client, staff, cardio_id)
    gabes = citizen()
    gabes_id, _ = await registered(client, staff, gabes, specialties=["cardiology"], gouvernorat_code=GABES)
    await approve(client, staff, gabes_id, GABES)
    r = await client.post(f"{ME}/availability", json={"available": True, "hours": 2}, headers=gabes)
    assert r.status_code == 200 and r.json()["available"] and r.json()["available_until"], r.text

    listed = (await client.get(DIRECTORY, params={"specialty": "cardiology"}, headers=cardio)).json()
    ids = [d["id"] for d in listed]
    assert cardio_id in ids and gabes_id in ids
    # The available doctor comes first, wherever they work; no phone, no registration number.
    assert ids.index(gabes_id) < ids.index(cardio_id)
    assert listed[0]["available"] and set(listed[0]) == {
        "id",
        "full_name",
        "kind",
        "specialties",
        "workplace",
        "gouvernorat_code",
        "available",
    }
    only_gabes = (await client.get(DIRECTORY, params={"gouvernorat_code": GABES}, headers=cardio)).json()
    assert {d["gouvernorat_code"] for d in only_gabes} == {GABES}
    assert (await client.get(DIRECTORY, params={"specialty": "magic"}, headers=cardio)).status_code == 422

    r = await client.post(f"{ME}/availability", json={"available": False}, headers=gabes)
    assert not r.json()["available"]
    # Suspended: off the list at once.
    coordinator = staff(["medical_coordinator"], gouvernorat=GABES)
    body = {"decision": "suspend", "reason": "Registration expired"}
    assert (await client.post(f"{STAFF}/{gabes_id}/review", json=body, headers=coordinator)).status_code == 200
    ids = [d["id"] for d in (await client.get(DIRECTORY, headers=cardio)).json()]
    assert gabes_id not in ids


async def test_withdrawal_and_erasure_drop_the_numbers(
    client: httpx.AsyncClient, staff: Staff, citizen: Callable[[], dict[str, str]], session: AsyncSession
) -> None:
    headers = citizen()
    doctor_id, body = await registered(client, staff, headers)
    exported = (await client.get("/api/v1/me/export", headers=headers)).json()
    assert exported["doctor"]["licence_no"] == "TN-12345"
    assert (await client.delete(ME, headers=headers)).status_code == 204
    mine = (await client.get(ME, headers=headers)).json()
    assert mine["status"] == "withdrawn" and mine["licence_no"] is None
    # Registering again starts a new review.
    r = await client.put(ME, json={**body, "version": mine["version"]}, headers=headers)
    assert r.json()["status"] == "pending", r.text

    r = await client.post("/api/v1/me/delete", json={"confirm": "DELETE"}, headers=headers)
    assert r.status_code == 202, r.text
    row = (
        await session.execute(
            text("SELECT status, licence_no_enc, workplace FROM identity.doctor WHERE user_id = :i"),
            {"i": uuid.UUID(doctor_id)},
        )
    ).one()
    assert row == ("withdrawn", None, "--")
