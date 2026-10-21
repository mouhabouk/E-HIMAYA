"""Institutions (phase 4): card, membership, registers, documents, certificate, staff hub, reporting."""

import base64
import hashlib
import os
import random
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.modules.orgs import documents
from tests.conftest import (
    HOOK_AUTH,
    STAFF_ISS,
    FakeStore,
    TokenFactory,
    accept_charter,
    bearer,
    outbox_events,
    report_body,
)

HOOK = "/internal/tusd/hooks"
SFAX = {"lat": 34.7406, "lon": 10.7603}
TUNIS = {"lat": 36.8065, "lon": 10.1815}
Staff = Callable[..., dict[str, str]]
User = Callable[..., dict[str, str]]


@pytest.fixture
def user(make_token: TokenFactory) -> User:
    def _user(email: str | None = None, verified: bool = True, **claims: Any) -> dict[str, str]:
        email = email or f"u{uuid.uuid4().hex[:10]}@example.tn"
        token = make_token(
            roles=["citizen"], email=email, email_verified=verified, name=f"User {email.split('@')[0]}", **claims
        )
        return bearer(token)

    return _user


@pytest.fixture
def signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "certificate_signing_key", SecretStr(base64.b64encode(os.urandom(32)).decode()))


def identifier() -> str:
    return f"{random.randint(0, 9_999_999):07d}{random.choice('ABCDEFGHJKLMNPQRSTVWXYZ')}"


def card(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Société des Peintures du Sud",
        "kind": "private",
        "identifier_type": "mf",
        "identifier": identifier().lower(),
        "activity_sector": "Commerce",
        "capacity": 40,
        "floors": 2,
        "height_m": 8.0,
        "receives_public": False,
        "address": "Route de Gabès km 4",
        "location": SFAX,
        "manager": {"full_name": "Mohamed Ali", "phone": "98 123 456", "email": "manager@example.tn"},
        "contact_email": "Contact@Example.tn",
        "contact_phone": "0021674000000",
    }
    body.update(overrides)
    return body


async def register(client: httpx.AsyncClient, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    r = await client.post("/api/v1/orgs", json=card(**overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def approve(client: httpx.AsyncClient, staff: Staff, org_id: str) -> None:
    r = await client.post(
        f"/api/v1/staff/orgs/{org_id}/review", json={"decision": "approve"}, headers=staff(["org_auditor"])
    )
    assert r.status_code == 200, r.text


async def active_org(client: httpx.AsyncClient, staff: Staff, headers: dict[str, str], **overrides: Any) -> str:
    org = await register(client, headers, **overrides)
    await approve(client, staff, org["id"])
    return str(org["id"])


async def add_member(
    client: httpx.AsyncClient, admin: dict[str, str], org_id: str, user: User, role: str
) -> dict[str, str]:
    email = f"m{uuid.uuid4().hex[:10]}@example.tn"
    created = (
        await client.post(f"/api/v1/orgs/{org_id}/invitations", json={"email": email, "role": role}, headers=admin)
    ).json()
    headers = user(email)
    r = await client.post(f"/api/v1/invitations/{created['token']}/accept", headers=headers)
    assert r.status_code == 200, r.text
    return headers


def _hook(kind: str, headers: dict[str, str], upload: dict[str, Any]) -> dict[str, Any]:
    return {
        "Type": kind,
        "Event": {"Upload": upload, "HTTPRequest": {"Header": {k: [v] for k, v in headers.items()}}},
    }


def _upload(document_id: str, data: bytes, **meta: str) -> dict[str, Any]:
    metadata = {
        "target": "org_document",
        "document_id": document_id,
        "filetype": "application/pdf",
        "sha256": hashlib.sha256(data).hexdigest(),
        "filename": "C:\\Users\\hse\\dossier sécurité.pdf",
        "note": "Mise à jour après audit",
        **meta,
    }
    return {"ID": "", "Size": len(data), "SizeIsDeferred": False, "Offset": 0, "MetaData": metadata}


async def upload_document(
    client: httpx.AsyncClient, headers: dict[str, str], store: FakeStore, document_id: str, data: bytes | None = None
) -> dict[str, Any]:
    data = data or b"%PDF-1.7 " + os.urandom(2048)
    answer = (
        await client.post(HOOK, headers=HOOK_AUTH, json=_hook("pre-create", headers, _upload(document_id, data)))
    ).json()
    assert "RejectUpload" not in answer, answer
    upload_id = answer["ChangeFileInfo"]["ID"]
    key = f"uploads/{upload_id}"
    store.objects[key] = data
    finished = {**_upload(document_id, data), "ID": f"{upload_id}+mp", "Storage": {"Key": key}}
    assert (await client.post(HOOK, headers=HOOK_AUTH, json=_hook("post-finish", headers, finished))).status_code == 200
    assert await documents.verify_one(get_system_sessionmaker(), store) is True
    return answer  # type: ignore[no-any-return]


async def complete(client: httpx.AsyncClient, headers: dict[str, str], store: FakeStore, org_id: str) -> None:
    """Fill what a small workplace needs: safety file, safety team with training, maintained equipment."""
    base = f"/api/v1/orgs/{org_id}"
    doc = (
        await client.post(f"{base}/documents", json={"kind": "safety_file", "title": "Dossier"}, headers=headers)
    ).json()
    await upload_document(client, headers, store, doc["id"])
    today = date.today().isoformat()
    for person in (
        {"full_name": "Sami Ben Salah", "team_role": "representative", "phone": "22333444", "last_training_on": today},
        {"full_name": "Amel Trabelsi", "team_role": "member", "last_training_on": today},
    ):
        assert (await client.post(f"{base}/team", json=person, headers=headers)).status_code == 201
    equipment = {"kind": "extinguisher", "count": 12, "last_maintenance_on": today}
    assert (await client.post(f"{base}/equipment", json=equipment, headers=headers)).status_code == 201


# ---------------------------------------------------------------- card and membership


async def test_staff_token_is_refused(client: httpx.AsyncClient, staff: Staff) -> None:
    r = await client.get("/api/v1/orgs/mine", headers=staff())
    assert r.status_code == 403 and r.json()["detail"] == "realm_not_allowed"


async def test_registration_needs_a_verified_email(client: httpx.AsyncClient, user: User) -> None:
    r = await client.post("/api/v1/orgs", json=card(), headers=user(verified=False))
    assert r.status_code == 403 and r.json()["detail"] == "email_not_verified"


async def test_register_and_read(client: httpx.AsyncClient, user: User) -> None:
    admin = user()
    org = await register(client, admin)
    assert org["status"] == "pending_review" and org["my_role"] == "admin" and org["version"] == 1
    assert org["identifier"] == org["identifier"].upper() and org["gouvernorat_code"] == 61
    assert org["manager"]["phone"] == "+21698123456" and org["contact_phone"] == "+21674000000"
    assert org["contact_email"] == "contact@example.tn"
    assert org["classification"] == {
        "family": "workplace",
        "category": None,
        "high_rise": False,
        "required": ["safety_file", "safety_team", "equipment"],
        "provisional": True,
    }
    assert org["completeness"] == {"ok": False, "missing": ["safety_file", "safety_team", "equipment"]}
    mine = (await client.get("/api/v1/orgs/mine", headers=admin)).json()
    assert mine == [
        {
            "id": org["id"],
            "name": org["name"],
            "kind": "private",
            "status": "pending_review",
            "my_role": "admin",
            "alerts_count": 0,
        }
    ]
    assert (await client.get(f"/api/v1/orgs/{org['id']}", headers=admin)).json()["id"] == org["id"]


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"identifier": "123456A"}, "invalid_identifier"),
        ({"identifier_type": "rne", "identifier": "1234567A/A/M/000"}, "invalid_identifier"),
        ({"contact_phone": "+33612345678"}, "invalid_phone"),
    ],
)
async def test_card_validation(client: httpx.AsyncClient, user: User, overrides: dict[str, Any], code: str) -> None:
    r = await client.post("/api/v1/orgs", json=card(**overrides), headers=user())
    assert r.status_code == 422 and r.json()["detail"] == code


async def test_identifier_is_unique(client: httpx.AsyncClient, user: User) -> None:
    value = identifier()
    await register(client, user(), identifier=value)
    r = await client.post("/api/v1/orgs", json=card(identifier=f" {value.lower()} "), headers=user())
    assert r.status_code == 409 and r.json()["detail"] == "identifier_already_registered"


async def test_classification_follows_the_card(client: httpx.AsyncClient, user: User) -> None:
    high = await register(client, user(), height_m=31.0)
    assert high["classification"]["family"] == "high_rise"
    assert "evacuation_points" in high["classification"]["required"]
    erp = await register(client, user(), receives_public=True, capacity=900, kind="hotel")
    assert (erp["classification"]["family"], erp["classification"]["category"]) == ("erp", 2)
    small = await register(client, user(), receives_public=True, capacity=50, kind="educational")
    assert small["classification"]["category"] == 5 and "training" not in small["classification"]["required"]


async def test_non_members_do_not_see_the_institution(client: httpx.AsyncClient, user: User) -> None:
    org = await register(client, user())
    r = await client.get(f"/api/v1/orgs/{org['id']}", headers=user())
    assert r.status_code == 404 and r.json()["detail"] == "org_not_found"


async def test_update_checks_version_and_sends_back_to_review(
    client: httpx.AsyncClient, user: User, staff: Staff
) -> None:
    admin = user()
    org_id = await active_org(client, staff, admin)
    current = (await client.get(f"/api/v1/orgs/{org_id}", headers=admin)).json()
    body = card(identifier=current["identifier"], capacity=55, version=current["version"])
    updated = (await client.put(f"/api/v1/orgs/{org_id}", json=body, headers=admin)).json()
    assert updated["status"] == "active" and updated["version"] == current["version"] + 1
    stale = await client.put(f"/api/v1/orgs/{org_id}", json=body, headers=admin)
    assert stale.status_code == 409 and stale.json()["detail"] == "version_conflict"
    renamed = card(identifier=current["identifier"], name="Nouveau nom", version=updated["version"])
    again = (await client.put(f"/api/v1/orgs/{org_id}", json=renamed, headers=admin)).json()
    assert again["status"] == "pending_review"


async def test_rejected_institution_can_resubmit(client: httpx.AsyncClient, user: User, staff: Staff) -> None:
    admin = user()
    org = await register(client, admin)
    auditor = staff(["org_auditor"])
    url = f"/api/v1/staff/orgs/{org['id']}/review"
    missing = await client.post(url, json={"decision": "reject"}, headers=auditor)
    assert missing.status_code == 422 and missing.json()["detail"] == "reason_required"
    rejected = await client.post(url, json={"decision": "reject", "reason": "Identifiant illisible"}, headers=auditor)
    assert rejected.json()["status"] == "rejected" and rejected.json()["review"]["reason"] == "Identifiant illisible"
    wrong = await client.post(url, json={"decision": "suspend", "reason": "x"}, headers=auditor)
    assert wrong.status_code == 409 and wrong.json()["detail"] == "invalid_transition"
    again = (await client.post(f"/api/v1/orgs/{org['id']}/resubmit", headers=admin)).json()
    assert again["status"] == "pending_review"


async def test_roles_and_invitations(client: httpx.AsyncClient, user: User, staff: Staff) -> None:
    admin = user()
    org = await register(client, admin)
    base = f"/api/v1/orgs/{org['id']}"
    pending = await client.post(f"{base}/invitations", json={"email": "x@example.tn"}, headers=admin)
    assert pending.status_code == 409 and pending.json()["detail"] == "org_not_active"
    await approve(client, staff, org["id"])

    created = (
        await client.post(f"{base}/invitations", json={"email": "Editor@Example.tn", "role": "editor"}, headers=admin)
    ).json()
    assert created["accept_url"].endswith(f"/invite/{created['token']}") and created["email"] == "editor@example.tn"
    listed = (await client.get(f"{base}/invitations", headers=admin)).json()
    assert [i["id"] for i in listed] == [created["id"]] and "token" not in listed[0]

    stranger = user()
    preview = (await client.get(f"/api/v1/invitations/{created['token']}", headers=stranger)).json()
    assert preview["org_name"] == org["name"] and preview["role"] == "editor"
    mismatch = await client.post(f"/api/v1/invitations/{created['token']}/accept", headers=stranger)
    assert mismatch.status_code == 403 and mismatch.json()["detail"] == "invitation_email_mismatch"
    editor = user("editor@example.tn")
    accepted = (await client.post(f"/api/v1/invitations/{created['token']}/accept", headers=editor)).json()
    assert accepted == {"org_id": org["id"], "role": "editor"}
    used = await client.post(f"/api/v1/invitations/{created['token']}/accept", headers=editor)
    assert used.status_code == 404 and used.json()["detail"] == "invitation_not_found"

    # The editor edits registers but does not manage members.
    team = {"full_name": "Sami Ben Salah", "team_role": "representative"}
    assert (await client.post(f"{base}/team", json=team, headers=editor)).status_code == 201
    forbidden = await client.post(f"{base}/invitations", json={"email": "y@example.tn"}, headers=editor)
    assert forbidden.status_code == 403 and forbidden.json()["detail"] == "org_role_required"

    member = await add_member(client, admin, org["id"], user, "member")
    denied = await client.post(f"{base}/equipment", json={"kind": "extinguisher", "count": 1}, headers=member)
    assert denied.status_code == 403
    members = (await client.get(f"{base}/members", headers=member)).json()
    assert sorted(m["role"] for m in members) == ["admin", "editor", "member"]
    assert any(m["email"] == "editor@example.tn" and m["display_name"] == "User editor" for m in members)

    admin_id = next(m["user_id"] for m in members if m["role"] == "admin")
    last = await client.put(f"{base}/members/{admin_id}", json={"role": "member"}, headers=admin)
    assert last.status_code == 409 and last.json()["detail"] == "last_admin"
    member_id = next(m["user_id"] for m in members if m["role"] == "member")
    assert (await client.delete(f"{base}/members/{member_id}", headers=member)).status_code == 204
    assert (await client.get(base, headers=member)).status_code == 404


async def test_expired_and_revoked_invitations(
    client: httpx.AsyncClient, user: User, staff: Staff, session: AsyncSession
) -> None:
    admin = user()
    org_id = await active_org(client, staff, admin)
    base = f"/api/v1/orgs/{org_id}/invitations"
    first = (await client.post(base, json={"email": "late@example.tn"}, headers=admin)).json()
    await session.execute(
        text("UPDATE org.invitation SET expires_at = now() - interval '1 minute' WHERE id = :id"), {"id": first["id"]}
    )
    await session.commit()
    expired = await client.post(f"/api/v1/invitations/{first['token']}/accept", headers=user("late@example.tn"))
    assert expired.status_code == 410 and expired.json()["detail"] == "invitation_expired"
    second = (await client.post(base, json={"email": "gone@example.tn"}, headers=admin)).json()
    assert (await client.delete(f"{base}/{second['id']}", headers=admin)).status_code == 204
    revoked = await client.get(f"/api/v1/invitations/{second['token']}", headers=user())
    assert revoked.status_code == 404


# ---------------------------------------------------------------- registers


async def test_team_training_and_alerts(client: httpx.AsyncClient, user: User) -> None:
    admin = user()
    org = await register(client, admin)
    base = f"/api/v1/orgs/{org['id']}"
    old = (date.today() - timedelta(days=800)).isoformat()
    soon = (date.today() - timedelta(days=700)).isoformat()
    rep = (
        await client.post(
            f"{base}/team",
            json={"full_name": "Sami", "team_role": "representative", "phone": "22 333 444", "last_training_on": old},
            headers=admin,
        )
    ).json()
    assert rep["training_status"] == "expired" and rep["phone"] == "+21622333444"
    second = await client.post(
        f"{base}/team", json={"full_name": "Autre", "team_role": "representative"}, headers=admin
    )
    assert second.status_code == 409 and second.json()["detail"] == "representative_exists"
    expiring = (
        await client.post(f"{base}/team", json={"full_name": "Amel", "last_training_on": soon}, headers=admin)
    ).json()
    assert expiring["training_status"] == "expiring"
    overdue = {"kind": "extinguisher", "count": 3, "last_maintenance_on": old, "maintenance_interval_months": 12}
    assert (await client.post(f"{base}/equipment", json=overdue, headers=admin)).json()[
        "maintenance_status"
    ] == "overdue"

    current = (await client.get(base, headers=admin)).json()
    kinds = sorted(a["kind"] for a in current["alerts"])
    assert kinds == ["maintenance_overdue", "training_expired", "training_expiring"]
    assert "equipment" in current["completeness"]["missing"]
    mine = (await client.get("/api/v1/orgs/mine", headers=admin)).json()
    assert mine[0]["alerts_count"] == 3

    fixed = {**overdue, "last_maintenance_on": date.today().isoformat()}
    items = (await client.get(f"{base}/equipment", headers=admin)).json()
    equipment_id = items[0]["id"]
    assert (await client.put(f"{base}/equipment/{equipment_id}", json=fixed, headers=admin)).json()[
        "maintenance_status"
    ] == "ok"
    assert (await client.delete(f"{base}/team/{rep['id']}", headers=admin)).status_code == 204
    assert len((await client.get(f"{base}/team", headers=admin)).json()) == 1


async def test_hazmat_register(client: httpx.AsyncClient, user: User) -> None:
    admin = user()
    org = await register(client, admin)
    base = f"/api/v1/orgs/{org['id']}"
    bad = await client.post(
        f"{base}/hazmat", json={"name": "Acétone", "un_number": "10A0", "quantity": 1, "unit": "t"}, headers=admin
    )
    assert bad.status_code == 422
    other = (await client.post(f"{base}/documents", json={"kind": "other", "title": "x"}, headers=admin)).json()
    wrong_doc = await client.post(
        f"{base}/hazmat",
        json={"name": "Acétone", "quantity": 2.5, "unit": "t", "sds_document_id": other["id"]},
        headers=admin,
    )
    assert wrong_doc.status_code == 422 and wrong_doc.json()["detail"] == "invalid_document"
    sds = (await client.post(f"{base}/documents", json={"kind": "sds", "title": "FDS acétone"}, headers=admin)).json()
    item = (
        await client.post(
            f"{base}/hazmat",
            json={
                "name": "Acétone",
                "un_number": "1090",
                "hazard_class": "3",
                "quantity": 2.5,
                "unit": "t",
                "sds_document_id": sds["id"],
            },
            headers=admin,
        )
    ).json()
    assert item["quantity"] == 2.5 and item["un_number"] == "1090"
    current = (await client.get(base, headers=admin)).json()
    assert current["classification"]["family"] == "industrial"
    # The SDS document exists but has no stored version yet.
    assert "hazmat_sds" in current["completeness"]["missing"]
    in_use = await client.delete(f"{base}/documents/{sds['id']}", headers=admin)
    assert in_use.status_code == 409 and in_use.json()["detail"] == "document_in_use"


async def test_map_features_must_be_near(client: httpx.AsyncClient, user: User) -> None:
    admin = user()
    org = await register(client, admin)
    base = f"/api/v1/orgs/{org['id']}/features"
    near = {"kind": "evacuation_point", "label": "Parking", "location": {"lat": 34.7410, "lon": 10.7610}}
    created = (await client.post(base, json=near, headers=admin)).json()
    assert created["location"] == near["location"]
    far = await client.post(base, json={**near, "location": TUNIS}, headers=admin)
    assert far.status_code == 422 and far.json()["detail"] == "feature_too_far"
    moved = {**near, "label": "Cour", "location": {"lat": 34.7420, "lon": 10.7600}}
    assert (await client.put(f"{base}/{created['id']}", json=moved, headers=admin)).json()["label"] == "Cour"
    assert len((await client.get(base, headers=admin)).json()) == 1


# ---------------------------------------------------------------- documents


async def test_document_versions(client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore) -> None:
    admin = user()
    org = await register(client, admin)
    base = f"/api/v1/orgs/{org['id']}/documents"
    doc = (await client.post(base, json={"kind": "safety_file", "title": "Dossier 2026"}, headers=admin)).json()
    assert doc["current_version"] is None and doc["versions_count"] == 0

    answer = await upload_document(client, admin, fake_store, doc["id"])
    assert answer["ChangeFileInfo"]["MetaData"]["version"] == "1"
    await upload_document(client, admin, fake_store, doc["id"])
    listed = (await client.get(base, headers=admin)).json()[0]
    current = listed["current_version"]
    assert listed["versions_count"] == 2 and current["version"] == 2 and current["status"] == "stored"
    assert current["filename"] == "dossier sécurité.pdf" and current["uploaded_by"].startswith("User ")
    versions = (await client.get(f"{base}/{doc['id']}/versions", headers=admin)).json()
    assert [v["version"] for v in versions] == [2, 1]
    link = (await client.get(f"{base}/{doc['id']}/versions/1/download", headers=admin)).json()
    assert link["url"].startswith("http://s3.test/uploads/")
    assert (
        "safety_file"
        not in (await client.get(f"/api/v1/orgs/{org['id']}", headers=admin)).json()["completeness"]["missing"]
    )

    staff_versions = await client.get(f"/api/v1/staff/orgs/{org['id']}/documents/{doc['id']}/versions", headers=staff())
    assert [v["version"] for v in staff_versions.json()] == [2, 1]
    renamed = (await client.put(f"{base}/{doc['id']}", json={"title": "Dossier 2027"}, headers=admin)).json()
    assert renamed["title"] == "Dossier 2027" and renamed["versions_count"] == 2
    assert (await client.delete(f"{base}/{doc['id']}", headers=admin)).status_code == 204
    assert any(k.startswith("uploads/") for k in fake_store.deleted)


async def test_document_upload_rejections(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore, session: AsyncSession
) -> None:
    admin = user()
    org_id = await active_org(client, staff, admin)
    doc = (
        await client.post(f"/api/v1/orgs/{org_id}/documents", json={"kind": "safety_file", "title": "x"}, headers=admin)
    ).json()
    data = b"%PDF-1.7 " + os.urandom(64)

    async def pre(headers: dict[str, str], upload: dict[str, Any]) -> tuple[int, str]:
        answer = (await client.post(HOOK, headers=HOOK_AUTH, json=_hook("pre-create", headers, upload))).json()
        response = answer["HTTPResponse"]
        return response["StatusCode"], response["Body"]

    assert await pre(admin, _upload(doc["id"], data, filetype="image/vnd.dwg")) == (
        415,
        '{"detail":"unsupported_media_type"}',
    )
    huge = {**_upload(doc["id"], data), "Size": 60 * 1024 * 1024}
    assert (await pre(admin, huge))[0] == 413
    assert (await pre(user(), _upload(doc["id"], data)))[1] == '{"detail":"document_not_found"}'
    assert (await pre(admin, _upload(str(uuid.uuid4()), data)))[0] == 404
    assert (await pre({}, _upload(doc["id"], data)))[0] == 401
    member = await add_member(client, admin, org_id, user, "member")
    assert (await pre(member, _upload(doc["id"], data)))[1] == '{"detail":"org_role_required"}'

    answer = (
        await client.post(HOOK, headers=HOOK_AUTH, json=_hook("pre-create", admin, _upload(doc["id"], data)))
    ).json()
    upload_id = answer["ChangeFileInfo"]["ID"]
    fake_store.objects[f"uploads/{upload_id}"] = b"tampered"
    finished = {**_upload(doc["id"], data), "ID": upload_id, "Storage": {"Key": f"uploads/{upload_id}"}}
    await client.post(HOOK, headers=HOOK_AUTH, json=_hook("post-finish", admin, finished))
    assert await documents.verify_one(get_system_sessionmaker(), fake_store) is True
    state = await session.scalar(text("SELECT status FROM org.document_version WHERE upload_id = :u"), {"u": upload_id})
    assert state == "rejected"

    second = (
        await client.post(HOOK, headers=HOOK_AUTH, json=_hook("pre-create", admin, _upload(doc["id"], data)))
    ).json()
    terminated = {**_upload(doc["id"], data), "ID": second["ChangeFileInfo"]["ID"]}
    await client.post(HOOK, headers=HOOK_AUTH, json=_hook("post-terminate", admin, terminated))
    assert (await client.get(f"/api/v1/orgs/{org_id}/documents", headers=admin)).json()[0]["versions_count"] == 0


# ---------------------------------------------------------------- certificate


async def test_certificate_lifecycle(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore, signing_key: None
) -> None:
    admin = user()
    org_id = await active_org(client, staff, admin)
    base = f"/api/v1/orgs/{org_id}"

    early = (await client.post(f"{base}/certificate", headers=admin)).json()
    incomplete = await client.post(f"{base}/certificates/{early['id']}/submit", headers=admin)
    assert incomplete.status_code == 409 and incomplete.json()["detail"] == "incomplete"

    await complete(client, admin, fake_store, org_id)
    outdated = await client.post(f"{base}/certificates/{early['id']}/submit", headers=admin)
    assert outdated.status_code == 409 and outdated.json()["detail"] == "certificate_outdated"

    draft = (await client.post(f"{base}/certificate", headers=admin)).json()
    assert draft["status"] == "draft" and draft["code"].startswith("EHC-") and "-61-" in draft["code"]
    assert draft["verify_url"].endswith(f"/verify/{draft['code']}")
    pdf = fake_store.objects[f"certificates/{draft['id']}/draft.pdf"]
    assert pdf.startswith(b"%PDF") and hashlib.sha256(pdf).hexdigest() == draft["pdf_sha256"]
    assert f"certificates/{early['id']}/draft.pdf" in fake_store.deleted  # the previous draft was replaced
    assert [c["id"] for c in (await client.get(f"{base}/certificates", headers=admin)).json()] == [draft["id"]]
    assert (await client.get(f"/api/v1/public/certificates/{draft['code']}")).status_code == 404

    submitted = (await client.post(f"{base}/certificates/{draft['id']}/submit", headers=admin)).json()
    assert submitted["status"] == "submitted"

    auditor = staff(["org_auditor"])
    queue = (await client.get("/api/v1/staff/certificates", headers=auditor)).json()["items"]
    assert any(item["id"] == draft["id"] and item["completeness"]["ok"] for item in queue)
    review = f"/api/v1/staff/certificates/{draft['id']}/review"
    too_far = (date.today() + timedelta(days=6 * 366)).isoformat()
    invalid = await client.post(review, json={"decision": "approve", "valid_until": too_far}, headers=auditor)
    assert invalid.status_code == 422 and invalid.json()["detail"] == "invalid_valid_until"
    operator = await client.post(review, json={"decision": "approve"}, headers=staff())
    assert operator.status_code == 403
    valid_until = (date.today() + timedelta(days=365)).isoformat()
    approved = (
        await client.post(review, json={"decision": "approve", "valid_until": valid_until}, headers=auditor)
    ).json()
    assert approved["status"] == "approved" and approved["valid_until"] == valid_until
    assert approved["fingerprint"] == draft["fingerprint"] and approved["pdf_sha256"] != draft["pdf_sha256"]

    public = (await client.get(f"/api/v1/public/certificates/{draft['code']}")).json()
    assert public["valid"] is True and public["signature_valid"] is True and public["superseded"] is False
    assert public["pdf_sha256"] == approved["pdf_sha256"] and public["classification"]["family"] == "workplace"
    key = (await client.get("/api/v1/public/certificate-key")).json()
    assert key["algorithm"] == "Ed25519" and len(base64.b64decode(key["public_key"])) == 32

    # A newer approved certificate supersedes the first one.
    newer = (await client.post(f"{base}/certificate", headers=admin)).json()
    await client.post(f"{base}/certificates/{newer['id']}/submit", headers=admin)
    await client.post(
        f"/api/v1/staff/certificates/{newer['id']}/review",
        json={"decision": "approve", "valid_until": valid_until},
        headers=auditor,
    )
    old = (await client.get(f"/api/v1/public/certificates/{draft['code']}")).json()
    assert old["superseded"] is True and old["valid"] is False
    staff_org = (await client.get(f"/api/v1/staff/orgs/{org_id}", headers=auditor)).json()
    assert [c["status"] for c in staff_org["certificates"]] == ["approved", "approved"]


async def test_approval_needs_the_signing_key(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "certificate_signing_key", None)
    admin = user()
    org_id = await active_org(client, staff, admin)
    await complete(client, admin, fake_store, org_id)
    cert = (await client.post(f"/api/v1/orgs/{org_id}/certificate", headers=admin)).json()
    await client.post(f"/api/v1/orgs/{org_id}/certificates/{cert['id']}/submit", headers=admin)
    auditor = staff(["org_auditor"])
    body = {"decision": "approve", "valid_until": (date.today() + timedelta(days=30)).isoformat()}
    r = await client.post(f"/api/v1/staff/certificates/{cert['id']}/review", json=body, headers=auditor)
    assert r.status_code == 503 and r.json()["detail"] == "signing_key_missing"
    rejected = await client.post(
        f"/api/v1/staff/certificates/{cert['id']}/review",
        json={"decision": "reject", "reason": "Plan absent"},
        headers=auditor,
    )
    assert rejected.json()["status"] == "rejected" and rejected.json()["review_reason"] == "Plan absent"
    public = (await client.get(f"/api/v1/public/certificates/{cert['code']}")).json()
    assert public["status"] == "rejected" and public["valid"] is False


# ---------------------------------------------------------------- staff hub


async def test_staff_list_scope_map_and_kpis(client: httpx.AsyncClient, user: User, staff: Staff) -> None:
    operator = staff()
    before = (await client.get("/api/v1/staff/kpis", headers=operator)).json()
    marker = uuid.uuid4().hex[:8]
    sfax = await register(client, user(), name=f"Usine Chimique Sfax {marker}", kind="industrial")
    tunis = await register(client, user(), name="Hôtel Tunis Centre", location=TUNIS)
    after = (await client.get("/api/v1/staff/kpis", headers=operator)).json()
    assert after["orgs_pending_review"] == before["orgs_pending_review"] + 1

    query = {"q": f"chimique sfax {marker}"}
    found = (await client.get("/api/v1/staff/orgs", params=query, headers=operator)).json()["items"]
    assert [o["id"] for o in found] == [sfax["id"]] and found[0]["certificate_status"] == "none"
    assert (await client.get(f"/api/v1/staff/orgs/{tunis['id']}", headers=operator)).status_code == 404
    national = staff(gouvernorat=None)
    assert (await client.get(f"/api/v1/staff/orgs/{tunis['id']}", headers=national)).status_code == 200
    bad = await client.get("/api/v1/staff/orgs", params={"status": "open"}, headers=operator)
    assert bad.status_code == 422

    page = (
        await client.get("/api/v1/staff/orgs", params={"limit": 1, "status": "pending_review"}, headers=operator)
    ).json()
    if page["next_cursor"]:
        nxt = await client.get(
            "/api/v1/staff/orgs",
            params={"limit": 1, "status": "pending_review", "cursor": page["next_cursor"]},
            headers=operator,
        )
        assert nxt.json()["items"][0]["id"] != page["items"][0]["id"]

    await approve(client, staff, sfax["id"])
    geo = (await client.get("/api/v1/staff/orgs/map", headers=operator)).json()
    feature = next(f for f in geo["features"] if f["properties"]["id"] == sfax["id"])
    assert feature["geometry"]["coordinates"] == [SFAX["lon"], SFAX["lat"]]
    assert feature["properties"]["family"] == "industrial"
    detail = (await client.get(f"/api/v1/staff/orgs/{sfax['id']}", headers=staff(["org_auditor"]))).json()
    assert detail["status"] == "active" and detail["members"][0]["role"] == "admin"


async def test_staff_detail_is_audited_and_events_are_queued(
    client: httpx.AsyncClient, user: User, staff: Staff, session: AsyncSession
) -> None:
    org = await register(client, user())
    await client.get(f"/api/v1/staff/orgs/{org['id']}", headers=staff())
    action = await session.scalar(
        text("SELECT action FROM audit.log WHERE target = :t ORDER BY seq DESC LIMIT 1"), {"t": f"org:{org['id']}"}
    )
    assert action == "org.view"
    payload = [e for e in await outbox_events(session, "org.updated") if e["org"]["id"] == org["id"]][-1]
    assert payload["org"]["status"] == "pending_review" and payload["org"]["gouvernorat_code"] == 61


def test_live_org_events_reach_the_auditor_only_for_institutions(make_token: TokenFactory) -> None:
    from fastapi.testclient import TestClient

    from app.main import app
    from app.modules.reports.live import hub

    token = make_token(issuer=STAFF_ISS, roles=["org_auditor"], gouvernorat_code="61")
    with TestClient(app) as tc, tc.websocket_connect("/api/v1/staff/live") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "ready"
        ws.portal.call(hub.on_event, "report.created", {"report": {"id": "r1", "gouvernorat_code": 61}})
        ws.portal.call(hub.on_event, "org.updated", {"org": {"id": "o-tunis", "gouvernorat_code": 11}})
        ws.portal.call(hub.on_event, "certificate.updated", {"certificate": {"id": "c1", "gouvernorat_code": 61}})
        message = ws.receive_json()
        assert message["type"] == "certificate.updated" and message["certificate"]["id"] == "c1"


# ---------------------------------------------------------------- reporting on behalf (§8) and sensitive sites (§10)


async def test_report_on_behalf_of_an_institution(
    client: httpx.AsyncClient, user: User, staff: Staff, make_token: TokenFactory
) -> None:
    admin = user()
    # A spot of its own, so institutions left by earlier runs are not the nearest sensitive site.
    # Inland: points off the coast south of Sfax fall outside every boundary and wait for geo-verification (§4).
    spot = {"lat": round(random.uniform(34.55, 34.70), 5), "lon": round(random.uniform(10.40, 10.52), 5)}
    org_id = await active_org(client, staff, admin, kind="industrial", location=spot)
    await client.post(
        f"/api/v1/orgs/{org_id}/hazmat",
        json={"name": "Chlore", "un_number": "1017", "quantity": 500, "unit": "kg"},
        headers=admin,
    )
    await client.post(
        f"/api/v1/orgs/{org_id}/features",
        json={"kind": "evacuation_point", "location": {"lat": spot["lat"] + 0.001, "lon": spot["lon"]}},
        headers=admin,
    )
    member = await add_member(client, admin, org_id, user, "member")
    await accept_charter(client, member)
    body = report_body({**spot, "accuracy_m": 10.0}, category="chemical_leak", organization_id=org_id)
    r = await client.post("/api/v1/reports", json=body, headers=member)
    assert r.status_code == 201, r.text
    report = r.json()
    assert report["organization"]["id"] == org_id

    outsider = user()
    await accept_charter(client, outsider)
    refused = await client.post("/api/v1/reports", json=report_body(organization_id=org_id), headers=outsider)
    assert refused.status_code == 404 and refused.json()["detail"] == "org_not_found"

    operator = staff()
    detail = (await client.get(f"/api/v1/staff/reports/{report['id']}", headers=operator)).json()
    assert detail["organization"]["kind"] == "industrial"
    card_ = detail["organization_card"]
    assert card_["hazmat"][0]["un_number"] == "1017" and card_["features"][0]["kind"] == "evacuation_point"
    sensitive = next(c for c in detail["analysis"]["priority"]["components"] if c["key"] == "sensitive_sites")
    assert sensitive["value"] == 1.0 and sensitive["detail"]["reason"] == "hazmat"
    assert sensitive["detail"]["org_id"] == org_id
    credibility = [c["key"] for c in detail["analysis"]["credibility"]["components"]]
    assert "organization" in credibility

    mine = (await client.get(f"/api/v1/orgs/{org_id}/reports", headers=admin)).json()["items"]
    assert mine[0]["tracking_code"] == report["tracking_code"] and mine[0]["reporter_display_name"].startswith("User")
    staff_reports = (await client.get(f"/api/v1/staff/orgs/{org_id}/reports", headers=operator)).json()["items"]
    assert [i["id"] for i in staff_reports] == [report["id"]]
    summary = (await client.get(f"/api/v1/orgs/{org_id}/summary", headers=member)).json()
    assert summary["hazmat_count"] == 1 and summary["classification"]["family"] == "industrial"

    # Reports made from the portal are marked as such.
    portal = bearer(make_token(roles=["citizen"], azp="ehimaya-portal"))
    await accept_charter(client, portal)
    created = (await client.post("/api/v1/reports", json=report_body(), headers=portal)).json()
    async with get_system_sessionmaker()() as s:
        source = await s.scalar(text("SELECT source FROM reports.report WHERE id = :id"), {"id": created["id"]})
    assert source == "portal"


async def test_pending_institution_cannot_report(client: httpx.AsyncClient, user: User) -> None:
    admin = user()
    org = await register(client, admin)
    await accept_charter(client, admin)
    r = await client.post("/api/v1/reports", json=report_body(organization_id=org["id"]), headers=admin)
    assert r.status_code == 409 and r.json()["detail"] == "org_not_active"


def test_sensitive_sites_only_raise_the_priority() -> None:
    from app.modules.ai import scoring
    from app.modules.ai.settings import PrioritySettings
    from app.modules.reports.domain import Category

    settings = PrioritySettings()
    plain = scoring.Facts(category=Category.DROWNING, reporter_kind="citizen", keywords={"lives_at_risk": True})
    base = scoring.priority(plain, 65, settings)
    near_hazmat = replace(plain, sensitive_site=(1.0, {"reason": "hazmat"}))
    assert scoring.priority(near_hazmat, 65, settings)["score"] > base["score"]
    near_office = replace(plain, sensitive_site=(0.4, {"reason": "nearby"}))
    result = scoring.priority(near_office, 65, settings)
    assert result["score"] == base["score"]
    component = next(c for c in result["components"] if c["key"] == "sensitive_sites")
    assert component["detail"]["counted"] is False and component["points"] == 0
