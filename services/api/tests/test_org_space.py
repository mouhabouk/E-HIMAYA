# covers: FR-B-005, FR-B-006, FR-C-17, FR-C-19
"""Institution space, phase P2b: Office messages with acknowledgement, awareness by kind, drills and events,
maintenance log with a photo (docs/phase-p2/design-institutions-app.md §5)."""

import hashlib
import os
import uuid
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from app.core.db import get_system_sessionmaker
from app.modules.orgs import documents
from tests.conftest import HOOK_AUTH, FakeStore, TokenFactory, bearer
from tests.test_notifications import info_body, tip_content
from tests.test_orgs import HOOK, _hook, _upload, active_org, add_member

Staff = Callable[..., dict[str, str]]
User = Callable[..., dict[str, str]]
JPEG = b"\xff\xd8\xff\xe0" + os.urandom(4096)


@pytest.fixture
def user(make_token: TokenFactory) -> User:
    def _user(email: str | None = None) -> dict[str, str]:
        email = email or f"u{uuid.uuid4().hex[:10]}@example.tn"
        token = make_token(roles=["citizen"], email=email, email_verified=True, name=f"User {email.split('@')[0]}")
        return bearer(token)

    return _user


async def publish(client: httpx.AsyncClient, staff: Staff, **overrides: Any) -> str:
    editor = staff(["content_editor"], gouvernorat=None)
    r = await client.post("/api/v1/staff/notifications", json=info_body(**overrides), headers=editor)
    assert r.status_code == 201, r.text
    message_id = r.json()["id"]
    assert (await client.post(f"/api/v1/staff/notifications/{message_id}/publish", headers=editor)).status_code == 200
    return str(message_id)


async def summary(client: httpx.AsyncClient, headers: dict[str, str], org_id: str) -> dict[str, Any]:
    r = await client.get(f"/api/v1/orgs/{org_id}/summary", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_office_message_to_some_kinds_with_acknowledgement(
    client: httpx.AsyncClient, user: User, staff: Staff
) -> None:
    hospital_admin, shop_admin = user(), user()
    hospital = await active_org(client, staff, hospital_admin, kind="health", name="Clinique des Oliviers")
    shop = await active_org(client, staff, shop_admin)
    member = await add_member(client, hospital_admin, hospital, user, "member")
    editor = staff(["content_editor"], gouvernorat=None)

    # Kinds and acknowledgement only make sense for institutions.
    for body in (info_body(org_kinds=["health"]), info_body(ack_required=True)):
        r = await client.post("/api/v1/staff/notifications", json=body, headers=editor)
        assert (r.status_code, r.json()["detail"]) == (422, "org_target_requires_organizations")

    asked = await publish(client, staff, audience="organizations", org_kinds=["health"], ack_required=True)
    plain = await publish(client, staff, audience="organizations", topic="training")
    detail = (await client.get(f"/api/v1/staff/notifications/{asked}", headers=editor)).json()
    assert detail["org_kinds"] == ["health"] and detail["ack_required"] is True

    listed = {m["id"]: m for m in (await client.get(f"/api/v1/orgs/{hospital}/messages", headers=member)).json()}
    assert listed[asked]["ack_required"] and listed[asked]["acked_at"] is None
    assert listed[plain]["ack_required"] is False
    shop_messages = (await client.get(f"/api/v1/orgs/{shop}/messages", headers=shop_admin)).json()
    assert asked not in {m["id"] for m in shop_messages} and plain in {m["id"] for m in shop_messages}
    assert (await summary(client, member, hospital))["messages_pending"] >= 1

    # A plain member reads; an editor or the admin confirms, once.
    ack = f"/api/v1/orgs/{hospital}/messages/{asked}/ack"
    r = await client.post(ack, headers=member)
    assert (r.status_code, r.json()["detail"]) == (403, "org_role_required")
    r = await client.post(ack, headers=hospital_admin)
    assert r.status_code == 200, r.text
    first = r.json()
    assert first["acked_at"] and first["acked_by"].startswith("User ")
    assert (await client.post(ack, headers=hospital_admin)).json()["acked_at"] == first["acked_at"]
    r = await client.post(f"/api/v1/orgs/{hospital}/messages/{plain}/ack", headers=hospital_admin)
    assert (r.status_code, r.json()["detail"]) == (409, "ack_not_required")
    r = await client.post(f"/api/v1/orgs/{shop}/messages/{asked}/ack", headers=shop_admin)
    assert (r.status_code, r.json()["detail"]) == (404, "message_not_found")
    pending = await client.get(f"/api/v1/orgs/{hospital}/messages", headers=member)
    assert not any(m["ack_required"] and not m["acked_at"] and m["id"] == asked for m in pending.json())

    # The dashboard sees who confirmed among the institutions reached.
    acks = (await client.get(f"/api/v1/staff/notifications/{asked}/acks", headers=editor)).json()
    rows = {row["org_id"]: row for row in acks["items"]}
    assert hospital in rows and shop not in rows
    assert rows[hospital]["acked_at"] == first["acked_at"] and rows[hospital]["kind"] == "health"
    assert acks["acked"] >= 1 and acks["targeted"] >= acks["acked"]


async def test_awareness_by_kind(client: httpx.AsyncClient, user: User, staff: Staff) -> None:
    hospital_admin, shop_admin = user(), user()
    hospital = await active_org(client, staff, hospital_admin, kind="health")
    shop = await active_org(client, staff, shop_admin)
    editor = staff(["content_editor"], gouvernorat=None)
    r = await client.post(
        "/api/v1/staff/safety-tips",
        json={"hazard": "fire", "position": 5, "content": tip_content(), "org_kinds": ["health", "health"]},
        headers=editor,
    )
    assert r.status_code == 201, r.text
    tip = r.json()
    assert tip["org_kinds"] == ["health"]
    assert (await client.post(f"/api/v1/staff/safety-tips/{tip['id']}/publish", headers=editor)).status_code == 200

    # Awareness for institutions stays out of the citizens' tips.
    assert tip["id"] not in {t["id"] for t in (await client.get("/api/v1/safety-tips")).json()["items"]}
    hospital_tips = (await client.get(f"/api/v1/orgs/{hospital}/awareness", headers=hospital_admin)).json()
    assert tip["id"] in {t["id"] for t in hospital_tips}
    assert hospital_tips[0]["content"]["fr"]["title"]
    shop_tips = (await client.get(f"/api/v1/orgs/{shop}/awareness", headers=shop_admin)).json()
    assert tip["id"] not in {t["id"] for t in shop_tips}
    assert (await client.get(f"/api/v1/orgs/{hospital}/awareness", headers=shop_admin)).status_code == 404


async def test_drills_and_events(client: httpx.AsyncClient, user: User, staff: Staff) -> None:
    admin = user()
    org = await active_org(client, staff, admin)
    member = await add_member(client, admin, org, user, "member")
    base = f"/api/v1/orgs/{org}/activities"
    today = date.today()

    for body, code in (
        (
            {"kind": "drill", "title": "Évacuation", "starts_on": (today + timedelta(days=3)).isoformat()},
            "drill_in_future",
        ),
        (
            {"kind": "drill", "title": "Évacuation", "starts_on": today.isoformat(), "ends_on": today.isoformat()},
            "invalid_dates",
        ),
        (
            {
                "kind": "event",
                "title": "Salon",
                "starts_on": today.isoformat(),
                "ends_on": (today - timedelta(days=1)).isoformat(),
            },
            "invalid_dates",
        ),
    ):
        r = await client.post(base, json=body, headers=admin)
        assert (r.status_code, r.json()["detail"]) == (422, code)

    drill = {"kind": "drill", "title": "Évacuation générale", "starts_on": today.isoformat(), "participants": 38}
    r = await client.post(base, json=drill, headers=member)
    assert (r.status_code, r.json()["detail"]) == (403, "org_role_required")
    r = await client.post(base, json=drill, headers=admin)
    assert r.status_code == 201, r.text
    assert r.json()["created_by"].startswith("User ")
    event = {
        "kind": "event",
        "title": "Journée portes ouvertes",
        "starts_on": (today + timedelta(days=10)).isoformat(),
        "ends_on": (today + timedelta(days=11)).isoformat(),
        "participants": 1200,
        "notes": "Parking réservé aux secours",
    }
    created = (await client.post(base, json=event, headers=admin)).json()
    listed = (await client.get(base, headers=member)).json()
    assert [a["kind"] for a in listed] == ["event", "drill"]

    # The dashboard sees the events to come in its scope, and the drills on the institution's page.
    reader = staff(["org_auditor"])
    events = (await client.get("/api/v1/staff/org-events?limit=200", headers=reader)).json()
    mine = next(e for e in events if e["id"] == created["id"])
    assert mine["org_id"] == org and mine["participants"] == 1200
    away = (await client.get("/api/v1/staff/org-events", headers=staff(["org_auditor"], gouvernorat=11))).json()
    assert created["id"] not in {e["id"] for e in away}
    detail = (await client.get(f"/api/v1/staff/orgs/{org}", headers=reader)).json()
    assert {a["kind"] for a in detail["activities"]} == {"drill", "event"}

    assert (await client.delete(f"{base}/{created['id']}", headers=admin)).status_code == 204
    assert (await client.delete(f"{base}/{created['id']}", headers=admin)).status_code == 404


async def upload_photo(
    client: httpx.AsyncClient, headers: dict[str, str], store: FakeStore, document_id: str, data: bytes = JPEG
) -> dict[str, Any]:
    upload = _upload(document_id, data, filetype="image/jpeg", filename="photo.jpg", note="")
    answer = (await client.post(HOOK, headers=HOOK_AUTH, json=_hook("pre-create", headers, upload))).json()
    if "RejectUpload" in answer:
        return answer  # type: ignore[no-any-return]
    upload_id = answer["ChangeFileInfo"]["ID"]
    key = f"uploads/{upload_id}"
    store.objects[key] = data
    finished = {**upload, "ID": f"{upload_id}+mp", "Storage": {"Key": key}}
    assert (await client.post(HOOK, headers=HOOK_AUTH, json=_hook("post-finish", headers, finished))).status_code == 200
    assert await documents.verify_one(get_system_sessionmaker(), store) is True
    return answer  # type: ignore[no-any-return]


async def test_maintenance_with_a_photo(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore
) -> None:
    admin = user()
    org = await active_org(client, staff, admin)
    base = f"/api/v1/orgs/{org}"
    old = (date.today() - timedelta(days=400)).isoformat()
    item = (
        await client.post(
            f"{base}/equipment", json={"kind": "extinguisher", "count": 6, "last_maintenance_on": old}, headers=admin
        )
    ).json()
    assert item["maintenance_status"] == "overdue"
    log = f"{base}/equipment/{item['id']}/maintenance"

    photo = (
        await client.post(
            f"{base}/documents", json={"kind": "maintenance_photo", "title": "Extincteurs"}, headers=admin
        )
    ).json()
    # Only JPEG or PNG, at most 10 MB.
    pdf = _upload(photo["id"], b"%PDF-1.7", filetype="application/pdf")
    answer = (await client.post(HOOK, headers=HOOK_AUTH, json=_hook("pre-create", admin, pdf))).json()
    assert answer["HTTPResponse"]["StatusCode"] == 415
    big = {**_upload(photo["id"], JPEG, filetype="image/jpeg"), "Size": 11 * 1024 * 1024}
    answer = (await client.post(HOOK, headers=HOOK_AUTH, json=_hook("pre-create", admin, big))).json()
    assert answer["HTTPResponse"]["StatusCode"] == 413
    await upload_photo(client, admin, fake_store, photo["id"])

    today = date.today().isoformat()
    future = (date.today() + timedelta(days=1)).isoformat()
    r = await client.post(log, json={"done_on": future}, headers=admin)
    assert (r.status_code, r.json()["detail"]) == (422, "maintenance_in_future")
    r = await client.post(log, json={"done_on": today, "note": " Recharge ", "document_id": photo["id"]}, headers=admin)
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["photo_version"] == 1 and entry["note"] == "Recharge" and entry["recorded_by"].startswith("User ")
    r = await client.post(log, json={"done_on": today, "document_id": photo["id"]}, headers=admin)
    assert (r.status_code, r.json()["detail"]) == (422, "invalid_document")
    safety = (await client.post(f"{base}/documents", json={"kind": "safety_file", "title": "D"}, headers=admin)).json()
    r = await client.post(log, json={"done_on": today, "document_id": safety["id"]}, headers=admin)
    assert (r.status_code, r.json()["detail"]) == (422, "invalid_document")

    # An older record does not move the last maintenance back.
    assert (await client.post(log, json={"done_on": old}, headers=admin)).status_code == 201
    equipment = (await client.get(f"{base}/equipment", headers=admin)).json()
    assert equipment[0]["last_maintenance_on"] == today and equipment[0]["maintenance_status"] == "ok"
    entries = (await client.get(log, headers=admin)).json()
    assert [e["done_on"] for e in entries] == [today, old]

    # The photo is shown with the equipment, not among the documents; the dashboard can open it.
    assert photo["id"] not in {d["id"] for d in (await client.get(f"{base}/documents", headers=admin)).json()}
    reader = staff(["org_auditor"])
    detail = (await client.get(f"/api/v1/staff/orgs/{org}", headers=reader)).json()
    assert detail["maintenance"][0]["document_id"] == photo["id"]
    r = await client.get(f"/api/v1/staff/orgs/{org}/documents/{photo['id']}/versions/1/download", headers=reader)
    assert r.status_code == 200 and r.json()["url"]
    digest = hashlib.sha256(JPEG).hexdigest()
    versions = (await client.get(f"{base}/documents/{photo['id']}/versions", headers=admin)).json()
    assert versions[0]["sha256"] == digest and versions[0]["content_type"] == "image/jpeg"
