# covers: C1-c
"""Referrals and locked opinions (docs/phase-c/design-medical-axis.md §13): a doctor holding a file sends it to
specialists from their phone, the specialist's opinion is locked for the file's group, a new committee member gets the
keys from a member's phone, and the reporter sees who saw their file, by role only. The server opens nothing."""

import base64
import json
import os
import uuid
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests import medical_crypto as mc
from tests.conftest import TokenFactory, bearer
from tests.test_doctors import GABES, SFAX, approve, registered
from tests.test_locked_medical import FILES, KEY, LOCKED, _empty_committee, keyed_doctor, send
from tests.test_operations import Staff

__all__ = ["_empty_committee"]  # the committee is emptied around each test, as in test_locked_medical

COMMITTEE = "/api/v1/staff/medical-committee"
OPENINGS = "/api/v1/me/medical/openings"
OPINION = "Échographie cardiaque recommandée sous 48 h ; pas de contre-indication au transport."


async def specialist(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, *, key: bool = True
) -> tuple[str, dict[str, str], X25519PrivateKey]:
    """An approved volunteer doctor (cardiology) with a key set on their phone."""
    headers = bearer(make_token(roles=["citizen"], email=f"s{uuid.uuid4().hex[:8]}@example.tn", email_verified=True))
    doctor_id, _ = await registered(client, staff, headers, specialties=["cardiology"])
    await approve(client, staff, doctor_id)
    private = X25519PrivateKey.generate()
    if key:
        body = {"public_key": mc.b64(mc.raw_public(private)), "backup": mc.backup(private, "246810")}
        assert (await client.put(KEY, json=body, headers=headers)).status_code == 200
    return doctor_id, headers, private


async def dek(
    client: httpx.AsyncClient, headers: dict[str, str], report_id: str, private: X25519PrivateKey, **body: Any
) -> bytes:
    r = await client.post(f"{FILES}/{report_id}/open", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return mc.dek_of(r.json(), private)


def refer_body(key: bytes, doctors: list[tuple[str, X25519PrivateKey]], reason: str = "Avis cardiologique") -> Any:
    return {"reason": reason, "keys": mc.wrap(key, [(d, mc.raw_public(p)) for d, p in doctors])}


def opinion_body(readers: list[dict[str, Any]], words: str = OPINION) -> dict[str, Any]:
    key, nonce = AESGCM.generate_key(bit_length=256), os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, json.dumps({"text": words}).encode(), None)
    keys = mc.wrap(key, [(r["doctor_id"], base64.b64decode(r["public_key"])) for r in readers])
    return {"nonce": mc.b64(nonce), "ciphertext": mc.b64(ciphertext), "keys": keys}


async def test_referral_opinion_and_what_the_reporter_sees(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    sfax_id, sfax_headers, sfax_key = await keyed_doctor(client, staff, make_token)
    heart_id, heart_headers, heart_key = await specialist(client, staff, make_token)
    keyless_id, _, keyless_key = await specialist(client, staff, make_token, key=False)
    citizen = bearer(make_token(roles=["citizen"]))
    report_id = await send(client, citizen, [(sfax_id, mc.raw_public(sfax_key))])

    # The directory gives the key to lock the file for, and none for a doctor who has not set one yet.
    found = {
        d["id"]: d
        for d in (
            await client.get("/api/v1/doctors/directory", params={"specialty": "cardiology"}, headers=sfax_headers)
        ).json()
    }
    assert found[heart_id]["public_key"] == mc.b64(mc.raw_public(heart_key)) and found[keyless_id]["public_key"] is None

    key = await dek(client, sfax_headers, report_id, sfax_key)
    referrals = f"{FILES}/{report_id}/referrals"
    r = await client.post(referrals, json=refer_body(key, [(keyless_id, keyless_key)]), headers=sfax_headers)
    assert r.status_code == 422 and r.json()["detail"] == "invalid_recipient"
    r = await client.post(referrals, json=refer_body(key, [(heart_id, heart_key)]), headers=sfax_headers)
    assert r.status_code == 204, r.text
    r = await client.post(referrals, json=refer_body(key, [(heart_id, heart_key)]), headers=sfax_headers)
    assert r.status_code == 409 and r.json()["detail"] == "already_holds_file"
    # The specialist is told without any content, and the referral is audited with its reason.
    pushes = (
        await session.execute(
            text("SELECT payload FROM notify.outbox WHERE user_id = :u AND payload->>'type' = 'medical_referral'"),
            {"u": heart_id},
        )
    ).scalars()
    assert [p["data"] for p in pushes] == [{"report_id": report_id, "redacted": "1"}]
    audited = await session.scalar(
        text("SELECT reason FROM audit.log WHERE action = 'medical.refer' AND target = :t"),
        {"t": f"report:{report_id}"},
    )
    assert audited == "Avis cardiologique"

    inbox = (await client.get(FILES, headers=heart_headers)).json()
    assert [(i["report_id"], i["via"]) for i in inbox] == [(report_id, "referral")]
    opened = (await client.post(f"{FILES}/{report_id}/open", json={}, headers=heart_headers)).json()
    assert mc.open_file(opened, heart_key) == LOCKED
    # A specialist does not refer the file on, nor sees who else it went to.
    other_id, other_headers, other_key = await specialist(client, staff, make_token)
    heart_dek = mc.dek_of(opened, heart_key)
    r = await client.post(referrals, json=refer_body(heart_dek, [(other_id, other_key)]), headers=heart_headers)
    assert r.status_code == 403 and r.json()["detail"] == "referral_not_allowed"
    assert (await client.get(referrals, headers=heart_headers)).status_code == 403

    # The opinion: locked for the group holding the file, the referring doctor and the author; nobody else.
    readers = (await client.get(f"{FILES}/{report_id}/opinion-recipients", headers=heart_headers)).json()
    assert {(r["doctor_id"], r["role"]) for r in readers} == {(sfax_id, "referrer"), (heart_id, "author")}
    assert (await client.get(f"{FILES}/{report_id}/opinion-recipients", headers=sfax_headers)).status_code == 403
    stranger = {"doctor_id": other_id, "public_key": mc.b64(mc.raw_public(other_key))}
    r = await client.post(
        f"{FILES}/{report_id}/opinions", json=opinion_body([*readers, stranger]), headers=heart_headers
    )
    assert r.status_code == 409 and r.json()["detail"] == "recipients_changed"
    r = await client.post(f"{FILES}/{report_id}/opinions", json=opinion_body(readers), headers=heart_headers)
    assert r.status_code == 201, r.text
    stored = await session.scalar(text("SELECT ciphertext FROM medical.opinion WHERE id = :i"), {"i": r.json()["id"]})
    assert stored and b"chographie" not in stored

    seen = (await client.get(f"{FILES}/{report_id}/opinions", headers=sfax_headers)).json()
    assert [(o["specialty"], o["mine"], mc.open_file(o, sfax_key)["text"]) for o in seen] == [
        ("cardiology", False, OPINION)
    ]
    assert (await client.get(f"{FILES}/{report_id}/opinions", headers=heart_headers)).json()[0]["mine"] is True
    # A second specialist on the same file does not read the first one's opinion.
    r = await client.post(referrals, json=refer_body(key, [(other_id, other_key)]), headers=sfax_headers)
    assert r.status_code == 204
    assert (await client.get(f"{FILES}/{report_id}/opinions", headers=other_headers)).json() == []
    listed = (await client.get(referrals, headers=sfax_headers)).json()
    assert [(x["doctor_id"], x["mine"]) for x in listed] == [(heart_id, True), (other_id, True)]

    # At most five referrals for one file.
    more = [await specialist(client, staff, make_token) for _ in range(4)]
    r = await client.post(referrals, json=refer_body(key, [(d, p) for d, _, p in more]), headers=sfax_headers)
    assert r.status_code == 409 and r.json()["detail"] == "too_many_referrals"
    r = await client.post(referrals, json=refer_body(key, [(d, p) for d, _, p in more[:3]]), headers=sfax_headers)
    assert r.status_code == 204

    # The operations room's medical coordinator sees counts, never content.
    operator = staff(gouvernorat=SFAX)
    assert (await client.post(f"/api/v1/staff/reports/{report_id}/claim", headers=operator)).status_code == 200
    medical = (await client.get(f"/api/v1/staff/reports/{report_id}/medical", headers=operator)).json()
    assert (medical["referrals"], medical["opinions"]) == (5, 1)

    # The reporter sees every opening and referral by role: never a name.
    seen_by = (await client.get(OPENINGS, params={"report_id": report_id}, headers=citizen)).json()
    lines = {(o["kind"], o["role"], o["gouvernorat_code"], tuple(o["specialties"])) for o in seen_by}
    assert ("open", "civil_protection", SFAX, ()) in lines
    assert ("open", "specialist", None, ("cardiology",)) in lines
    assert ("referral", "specialist", None, ("cardiology",)) in lines
    assert len([o for o in seen_by if o["kind"] == "referral"]) == 5
    assert all(set(o) == set(seen_by[0]) and "full_name" not in o for o in seen_by)
    assert (await client.get(OPENINGS, headers=bearer(make_token(roles=["citizen"])))).json() == []


async def test_a_new_committee_member_gets_the_keys_from_a_member(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    admin = staff(["sysadmin"], gouvernorat=None)
    sfax_id, sfax_headers, sfax_key = await keyed_doctor(client, staff, make_token)
    first_id, first_headers, first_key = await keyed_doctor(client, staff, make_token, gouvernorat=GABES)
    assert (await client.put(f"{COMMITTEE}/{first_id}", json={}, headers=admin)).status_code == 200
    citizen = bearer(make_token(roles=["citizen"]))
    report_id = await send(client, citizen, [(sfax_id, mc.raw_public(sfax_key)), (first_id, mc.raw_public(first_key))])
    heart_id, heart_headers, heart_key = await specialist(client, staff, make_token)
    key = await dek(client, sfax_headers, report_id, sfax_key)
    referrals = f"{FILES}/{report_id}/referrals"
    assert (
        await client.post(referrals, json=refer_body(key, [(heart_id, heart_key)]), headers=sfax_headers)
    ).status_code == 204
    readers = (await client.get(f"{FILES}/{report_id}/opinion-recipients", headers=heart_headers)).json()
    assert {r["role"] for r in readers} == {"referrer", "committee", "author"}
    r = await client.post(f"{FILES}/{report_id}/opinions", json=opinion_body(readers), headers=heart_headers)
    opinion_id = r.json()["id"]

    # Appointed afterwards: the files and opinions locked before are waiting for a member's phone.
    new_id, new_headers, new_key = await keyed_doctor(client, staff, make_token, gouvernorat=GABES)
    assert (await client.put(f"{COMMITTEE}/{new_id}", json={}, headers=admin)).status_code == 200
    pending = (await client.get("/api/v1/medical/committee/pending", headers=first_headers)).json()
    assert [(p["doctor_id"], p["files"], p["opinions"]) for p in pending] == [
        (new_id, [report_id], [{"id": opinion_id, "report_id": report_id}])
    ]
    assert (await client.get("/api/v1/medical/committee/pending", headers=sfax_headers)).status_code == 403

    key = await dek(client, first_headers, report_id, first_key, reason="Copie pour le nouveau membre")
    share = {"reason": "Nouveau membre", "keys": mc.wrap(key, [(new_id, mc.raw_public(new_key))])}
    r = await client.post(f"{FILES}/{report_id}/keys", json=share, headers=sfax_headers)
    assert r.status_code == 403 and r.json()["detail"] == "not_committee_member"
    bad = {"reason": "Nouveau membre", "keys": mc.wrap(key, [(heart_id, mc.raw_public(heart_key))])}
    r = await client.post(f"{FILES}/{report_id}/keys", json=bad, headers=first_headers)
    assert r.status_code == 422 and r.json()["detail"] == "invalid_recipient"
    assert (await client.post(f"{FILES}/{report_id}/keys", json=share, headers=first_headers)).status_code == 204
    assert (await client.post(f"{FILES}/{report_id}/keys", json=share, headers=first_headers)).status_code == 409

    first_copy = (await client.get(f"{FILES}/{report_id}/opinions", headers=first_headers)).json()[0]
    opinion_key = mc.dek_of(first_copy, first_key)
    share = {"reason": "Nouveau membre", "keys": mc.wrap(opinion_key, [(new_id, mc.raw_public(new_key))])}
    assert (
        await client.post(f"/api/v1/medical/opinions/{opinion_id}/keys", json=share, headers=first_headers)
    ).status_code == 204
    assert (await client.get("/api/v1/medical/committee/pending", headers=first_headers)).json() == []

    r = await client.post(f"{FILES}/{report_id}/open", json={"reason": "Suivi du dossier"}, headers=new_headers)
    assert mc.open_file(r.json(), new_key) == LOCKED
    mine = (await client.get(f"{FILES}/{report_id}/opinions", headers=new_headers)).json()
    assert mc.open_file(mine[0], new_key)["text"] == OPINION
    shared = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'medical.share' AND target = :t"),
        {"t": f"report:{report_id}"},
    )
    assert shared == 2
    # The reporter sees "the medical committee", without a name or a gouvernorat.
    seen_by = (await client.get(OPENINGS, headers=citizen)).json()
    assert {(o["role"], o["gouvernorat_code"]) for o in seen_by if o["role"] == "committee"} == {("committee", None)}

    # Out of the committee: their copies of the file and of its opinions go.
    r = await client.post(f"{COMMITTEE}/{new_id}/revoke", json={"reason": "Fin de mandat"}, headers=admin)
    assert r.status_code == 200
    left = await session.scalar(text("SELECT count(*) FROM medical.opinion_key WHERE doctor_id = :d"), {"d": new_id})
    assert left == 0
    # A withdrawn specialist loses their copies; the opinion stays for its readers.
    assert (await client.delete("/api/v1/me/doctor", headers=heart_headers)).status_code == 204
    assert (await client.get(f"{FILES}/{report_id}/opinions", headers=heart_headers)).status_code == 409
    assert len((await client.get(f"{FILES}/{report_id}/opinions", headers=sfax_headers)).json()) == 1
