# covers: F-STF-06
"""Prevention visits on the inspector's phone, phase P4c (docs/phase-p4/design-staff.md §8): the inspector's list,
taking a visit, photos under the grid items, the inspection with both signatures, the decision with reservations,
and writes resent by the phone applied once."""

import base64
import uuid
from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from tests.conftest import FakeStore, TokenFactory, bearer
from tests.test_crew import Leader, Staff
from tests.test_orgs import signing_key  # noqa: F401  (a fixture)
from tests.test_prevention import User, auditor, ready_org

pytestmark = pytest.mark.usefixtures("signing_key")
TODAY = date.today()
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
SIGNATURE = base64.b64encode(PNG).decode()


@pytest.fixture
def user(make_token: TokenFactory) -> User:
    def _user() -> dict[str, str]:
        email = f"u{uuid.uuid4().hex[:10]}@example.tn"
        return bearer(make_token(roles=["citizen"], email=email, email_verified=True, name="Admin"))

    return _user


class Inspector(Leader):
    """An inspector of Sfax (61) with a stable account and a registered phone."""

    def __init__(self, client: httpx.AsyncClient, staff: Staff, name: str = "ليلى المفقّدة") -> None:
        self.client = client
        self.sub = str(uuid.uuid4())
        self.headers = staff(["org_auditor"], 61, sub=self.sub, name=name)
        self.device = None

    async def visit(self, visit_id: str) -> httpx.Response:
        return await self.client.get(f"/api/v1/crew/prevention/visits/{visit_id}", headers=self.h)

    async def send(self, visit_id: str, what: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return await self.client.post(
            f"/api/v1/crew/prevention/visits/{visit_id}/{what}", json=body or {}, headers=self.h
        )

    async def photo(
        self, visit_id: str, data: bytes, content_type: str = "image/jpeg", **params: Any
    ) -> httpx.Response:
        query = {"client_id": str(uuid.uuid4()), **params}
        return await self.client.post(
            f"/api/v1/crew/prevention/visits/{visit_id}/photos",
            params=query,
            content=data,
            headers={**self.h, "Content-Type": content_type},
        )


async def scheduled(client: httpx.AsyncClient, user: User, staff: Staff, store: FakeStore) -> tuple[str, str]:
    """A visit the Office scheduled for today; returns the institution and the visit."""
    _admin, org_id = await ready_org(client, user, staff, store)
    body = {"scheduled_on": TODAY.isoformat(), "inspector_name": "Cdt Ben Salah"}
    r = await client.post(f"/api/v1/staff/orgs/{org_id}/prevention/visits", json=body, headers=auditor(staff))
    assert r.status_code == 201, r.text
    return org_id, r.json()["id"]


def _inspection(checklist: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    items = [{"key": i["key"], "result": "conform"} for i in checklist if i["key"] != "site.exits"]
    items.append({"key": "site.exits", "result": "nonconform", "note": "Issue B encombrée"})
    return {
        "client_id": str(uuid.uuid4()),
        "device_at": f"{TODAY.isoformat()}T09:30:00+01:00",
        "inspected_on": TODAY.isoformat(),
        "attendees": "Directeur, responsable sécurité",
        "items": items,
        "representative_name": "Sami Trabelsi",
        "representative_role": "Directeur",
        "inspector_signature": SIGNATURE,
        "representative_signature": SIGNATURE,
        **extra,
    }


async def test_inspector_phone_takes_inspects_and_decides(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore
) -> None:
    _org_id, vid = await scheduled(client, user, staff, fake_store)
    inspector = Inspector(client, staff)

    # The inspector registers the phone like a team leader; the app learns the account's field roles.
    lists = "/api/v1/crew/prevention/visits"
    assert (await client.get(lists, headers=inspector.headers)).json()["detail"] == "device_required"
    await inspector.register()
    me = (await client.get("/api/v1/crew/me", headers=inspector.h)).json()
    assert me["roles"] == ["org_auditor"]
    leader = Leader(client, staff)
    await leader.register()
    assert (await client.get(lists, headers=leader.h)).status_code == 403

    # The list: the scheduled visit, with the address and the grid to take offline.
    r = await client.get(lists, headers=inspector.h)
    assert r.status_code == 200, r.text
    visit = next(v for v in r.json() if v["id"] == vid)
    assert visit["status"] == "scheduled" and visit["mine"] is False and visit["taken_by_other"] is False
    assert any(i["key"] == "site.exits" for i in visit["checklist"])
    assert visit["inspector_on_phone"] is False and visit["photos"] == [] and visit["signatures"] is None

    # «آخذها»: the visit is the inspector's; another inspector cannot take it nor write on it.
    r = await inspector.send(vid, "claim")
    assert r.status_code == 200, r.text
    assert r.json()["mine"] is True and r.json()["inspector_name"] == "ليلى المفقّدة"
    assert (await inspector.send(vid, "claim")).status_code == 200
    other = Inspector(client, staff, "Autre")
    await other.register()
    assert (await other.send(vid, "claim")).json()["detail"] == "visit_taken"
    assert (await other.visit(vid)).json()["taken_by_other"] is True
    assert (await other.photo(vid, JPEG)).json()["detail"] == "visit_taken"
    staff_view = (await client.get(f"/api/v1/staff/prevention/visits/{vid}", headers=auditor(staff))).json()
    assert staff_view["inspector_on_phone"] is True

    # Photos under grid items: checked from their bytes, a resend is kept once.
    client_id = str(uuid.uuid4())
    r = await inspector.photo(vid, JPEG, item_key="site.exits", client_id=client_id)
    assert r.status_code == 201, r.text
    again = await inspector.photo(vid, JPEG, item_key="site.exits", client_id=client_id)
    assert again.status_code == 201 and len(again.json()["photos"]) == 1
    photo = again.json()["photos"][0]
    assert photo["item_key"] == "site.exits" and photo["url"] and photo["created_by_name"] == "ليلى المفقّدة"
    assert (await inspector.photo(vid, PNG, "image/jpeg")).json()["detail"] == "type_mismatch"
    assert (await inspector.photo(vid, JPEG, "image/gif")).status_code == 415
    assert (await inspector.photo(vid, b"", "image/jpeg")).json()["detail"] == "empty_file"
    assert (await inspector.photo(vid, PNG, "image/png")).status_code == 201

    # The inspection with both signatures; a bad signature is refused, a resend is applied once.
    body = _inspection(visit["checklist"], inspector_signature=base64.b64encode(JPEG).decode())
    assert (await inspector.send(vid, "inspection", body)).json()["detail"] == "invalid_signature"
    body = _inspection(visit["checklist"])
    r = await inspector.send(vid, "inspection", body)
    assert r.status_code == 200, r.text
    inspected = r.json()
    assert inspected["status"] == "inspected" and inspected["has_report"] is True
    assert inspected["comparison"]["nonconform"] == 1
    assert inspected["comparison"]["suggested"] == "approved_with_reservations"
    signatures = inspected["signatures"]
    assert signatures["representative_name"] == "Sami Trabelsi" and signatures["representative_role"] == "Directeur"
    assert signatures["inspector_url"] and signatures["representative_url"]
    signature_keys = [k for k in fake_store.objects if k.startswith(f"prevention/{vid}/signature-")]
    assert len(signature_keys) == 2
    r = await inspector.send(vid, "inspection", body)
    assert r.status_code == 200 and r.json()["inspected_on"] == inspected["inspected_on"]
    assert len([k for k in fake_store.objects if k.startswith(f"prevention/{vid}/signature-")]) == 2

    # The decision from the phone, with the reservations proposed from the non-conformity.
    due = (TODAY + timedelta(days=90)).isoformat()
    decision = {
        "decision": "approved_with_reservations",
        "valid_until": (TODAY + timedelta(days=365)).isoformat(),
        "reservations": [{"text": "Dégager l'issue B", "due_on": due, "item_key": "site.exits"}],
    }
    assert (await other.send(vid, "decision", decision)).json()["detail"] == "visit_taken"
    r = await inspector.send(vid, "decision", decision)
    assert r.status_code == 200, r.text
    decided = r.json()
    assert decided["status"] == "decided" and decided["decided_by_name"] == "ليلى المفقّدة"
    assert decided["certificate"]["kind"] == "prevention" and len(decided["reservations"]) == 1
    # Sent again when the answer was lost: nothing new; the dashboard cannot decide it twice either.
    r = await inspector.send(vid, "decision", decision)
    assert r.status_code == 200 and r.json()["certificate"]["code"] == decided["certificate"]["code"]
    assert len(r.json()["reservations"]) == 1
    url = f"/api/v1/staff/prevention/visits/{vid}/decision"
    assert (await client.post(url, json=decision, headers=auditor(staff))).json()["detail"] == "invalid_transition"

    # A decided visit leaves the list; its photos and signatures stay on the dashboard.
    assert vid not in [v["id"] for v in (await client.get(lists, headers=inspector.h)).json()]
    assert (await inspector.photo(vid, JPEG)).json()["detail"] == "invalid_transition"
    staff_view = (await client.get(f"/api/v1/staff/prevention/visits/{vid}", headers=auditor(staff))).json()
    assert len(staff_view["photos"]) == 2 and staff_view["signatures"]["representative_name"] == "Sami Trabelsi"


async def test_rescheduling_to_another_inspector_frees_the_visit(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore
) -> None:
    _org_id, vid = await scheduled(client, user, staff, fake_store)
    inspector = Inspector(client, staff)
    await inspector.register()
    assert (await inspector.send(vid, "claim")).status_code == 200
    other = Inspector(client, staff, "Autre")
    await other.register()
    assert (await other.send(vid, "claim")).json()["detail"] == "visit_taken"

    # Same inspector named again: still on the phone. Another name: the visit is free again.
    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    url = f"/api/v1/staff/prevention/visits/{vid}/schedule"
    body = {"scheduled_on": tomorrow, "inspector_name": "ليلى المفقّدة"}
    assert (await client.post(url, json=body, headers=auditor(staff))).json()["inspector_on_phone"] is True
    body["inspector_name"] = "Cdt Ben Salah"
    assert (await client.post(url, json=body, headers=auditor(staff))).json()["inspector_on_phone"] is False
    r = await other.send(vid, "claim")
    assert r.status_code == 200 and r.json()["mine"] is True


async def test_photos_are_capped_and_client_ids_stay_with_their_visit(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore
) -> None:
    _org_id, vid = await scheduled(client, user, staff, fake_store)
    _org_id2, vid2 = await scheduled(client, user, staff, fake_store)
    inspector = Inspector(client, staff)
    await inspector.register()
    for v in (vid, vid2):
        assert (await inspector.send(v, "claim")).status_code == 200
    client_id = str(uuid.uuid4())
    assert (await inspector.photo(vid, JPEG, client_id=client_id)).status_code == 201
    assert (await inspector.photo(vid2, JPEG, client_id=client_id)).json()["detail"] == "client_id_reused"
    for _ in range(19):
        assert (await inspector.photo(vid, JPEG, item_key="site.alarm")).status_code == 201
    assert (await inspector.photo(vid, JPEG)).json()["detail"] == "too_many_photos"
    assert (await inspector.photo(vid2, JPEG, item_key="Bad Key")).status_code == 422
