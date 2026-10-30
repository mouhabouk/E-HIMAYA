# covers: FR-B-008
"""Certificate upgrade, phase P3a: "needs update", alerts and renewal reminders, the counter of a regional
administration with the hand stamp and its photo, the electronic seal (docs/phase-p3/design-certificates.md §3)."""

import os
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orgs import certificate, domain
from app.modules.orgs.models import Certificate
from tests.conftest import FakeStore, TokenFactory, bearer
from tests.test_orgs import active_org, complete, signing_key  # noqa: F401  (signing_key is a fixture)

Staff = Callable[..., dict[str, str]]
User = Callable[..., dict[str, str]]
JPEG = b"\xff\xd8\xff\xe0" + os.urandom(2048)

pytestmark = pytest.mark.usefixtures("signing_key")


@pytest.fixture
def user(make_token: TokenFactory) -> User:
    def _user(email: str | None = None) -> dict[str, str]:
        email = email or f"u{uuid.uuid4().hex[:10]}@example.tn"
        token = make_token(roles=["citizen"], email=email, email_verified=True, name=f"User {email.split('@')[0]}")
        return bearer(token)

    return _user


async def approved(
    client: httpx.AsyncClient, user: User, staff: Staff, store: FakeStore, days: int = 365, email: str | None = None
) -> tuple[dict[str, str], str, dict[str, Any]]:
    admin = user(email) if email else user()
    org_id = await active_org(client, staff, admin)
    await complete(client, admin, store, org_id)
    cert = (await client.post(f"/api/v1/orgs/{org_id}/certificate", headers=admin)).json()
    await client.post(f"/api/v1/orgs/{org_id}/certificates/{cert['id']}/submit", headers=admin)
    body = {"decision": "approve", "valid_until": (date.today() + timedelta(days=days)).isoformat()}
    r = await client.post(f"/api/v1/staff/certificates/{cert['id']}/review", json=body, headers=staff(["org_auditor"]))
    assert r.status_code == 200, r.text
    return admin, org_id, dict(r.json())


def alert_kinds(alerts: list[dict[str, Any]]) -> set[str]:
    return {a["kind"] for a in alerts if a["kind"].startswith("certificate_")}


def test_substantive_changes_only() -> None:
    def snap(**org: Any) -> dict[str, Any]:
        base = {
            "name": "X",
            "kind": "industrial",
            "identifier": "1",
            "capacity": 40,
            "location": {"lat": 34.7, "lon": 10.7},
        }
        return {
            "org": base | org,
            "classification": {"family": "workplace", "category": None, "high_rise": False},
            "team": [{"full_name": "Sami", "team_role": "representative", "training_expires_on": "2027-01-01"}],
            "hazmat": [],
            "documents": [{"kind": "safety_file", "title": "Dossier", "version": 1, "sha256": "a" * 64}],
            "features": [{"kind": "evacuation_point"}],
        }

    certified = snap()
    assert domain.certificate_changes(certified, snap()) == []
    # Training dates and a few metres of GPS drift are not substantive.
    later = snap(location={"lat": 34.7002, "lon": 10.7})
    later["team"][0]["training_expires_on"] = "2026-01-01"
    assert domain.certificate_changes(certified, later) == []
    moved = domain.certificate_changes(certified, snap(location={"lat": 34.701, "lon": 10.7}, capacity=90))
    assert [(s, f) for s, f, _, _ in moved] == [("building", "capacity"), ("building", "location")]
    new_file = snap()
    new_file["documents"][0] |= {"version": 2, "sha256": "b" * 64}
    new_file["features"] = []
    assert [(s, f) for s, f, _, _ in domain.certificate_changes(certified, new_file)] == [
        ("documents", "files"),
        ("evacuation", "points"),
    ]


async def test_needs_update_shows_where_the_institution_is_read(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore
) -> None:
    admin, org_id, cert = await approved(client, user, staff, fake_store)
    base = f"/api/v1/orgs/{org_id}"
    current = (await client.get(f"{base}/certificates", headers=admin)).json()[0]
    assert current["needs_update"] is False and current["changes"] == [] and current["stamps"] == []
    assert alert_kinds((await client.get(f"{base}/summary", headers=admin)).json()["alerts"]) == set()

    hazmat = {"name": "Toluène", "un_number": "1294", "quantity": 200, "unit": "l"}
    assert (await client.post(f"{base}/hazmat", json=hazmat, headers=admin)).status_code == 201

    current = (await client.get(f"{base}/certificates", headers=admin)).json()[0]
    assert current["needs_update"] is True
    hazmat_change = next(c for c in current["changes"] if c["section"] == "hazmat")
    assert hazmat_change["certified"] == [] and hazmat_change["current"] == ["Toluène (UN 1294): 200 l"]
    assert "certificate_needs_update" in alert_kinds(
        (await client.get(f"{base}/summary", headers=admin)).json()["alerts"]
    )
    assert "certificate_needs_update" in alert_kinds((await client.get(base, headers=admin)).json()["alerts"])
    detail = (await client.get(f"/api/v1/staff/orgs/{org_id}", headers=staff(["org_auditor"]))).json()
    assert detail["certificates"][0]["needs_update"] is True

    # The public verification says nothing about it.
    public = (await client.get(f"/api/v1/public/certificates/{cert['code']}")).json()
    assert public["valid"] is True and "needs_update" not in public and "changes" not in public

    # A new certificate certifies the change: the current one matches again, the old one has no comparison.
    newer = (await client.post(f"{base}/certificate", headers=admin)).json()
    assert newer["needs_update"] is None


async def test_expiry_alerts_and_renewal_reminders(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore, session: AsyncSession
) -> None:
    email = f"r{uuid.uuid4().hex[:10]}@example.tn"
    admin, org_id, cert = await approved(client, user, staff, fake_store, days=60, email=email)
    base = f"/api/v1/orgs/{org_id}"
    assert alert_kinds((await client.get(f"{base}/summary", headers=admin)).json()["alerts"]) == {
        "certificate_expiring"
    }
    mine = (await client.get("/api/v1/orgs/mine", headers=admin)).json()
    assert next(o for o in mine if o["id"] == org_id)["alerts_count"] == 1

    async def reminders() -> int:
        count = await session.scalar(
            text(
                "SELECT count(*) FROM notify.outbox WHERE channel = 'email' AND address = :a "
                "AND payload->>'text' LIKE :c"
            ),
            {"a": email, "c": f"%{cert['code']}%"},
        )
        return int(count or 0)

    today = date.today()
    await certificate.renewal_reminders(session, today)
    await session.commit()
    assert await reminders() == 1
    await certificate.renewal_reminders(session, today)
    await session.commit()
    assert await reminders() == 1  # once per threshold

    cert_id = uuid.UUID(cert["id"])
    await session.execute(
        text("UPDATE org.certificate SET valid_until = :d WHERE id = :i"),
        {"d": today + timedelta(days=20), "i": cert_id},
    )
    await session.commit()
    await certificate.renewal_reminders(session, today)
    await session.commit()
    assert await reminders() == 2
    row = await session.get(Certificate, cert_id, populate_existing=True)
    assert row is not None and row.reminded_90_on == today and row.reminded_30_on == today
    await certificate.renewal_reminders(session, today)
    await session.commit()
    assert await reminders() == 2

    await session.execute(
        text("UPDATE org.certificate SET valid_until = :d WHERE id = :i"),
        {"d": today - timedelta(days=1), "i": cert_id},
    )
    await session.commit()
    assert alert_kinds((await client.get(f"{base}/summary", headers=admin)).json()["alerts"]) == {"certificate_expired"}
    public = (await client.get(f"/api/v1/public/certificates/{cert['code']}")).json()
    assert public["valid"] is False


async def test_counter_lookup_and_hand_stamp(
    client: httpx.AsyncClient, user: User, staff: Staff, fake_store: FakeStore, session: AsyncSession
) -> None:
    admin, org_id, cert = await approved(client, user, staff, fake_store)
    auditor = staff(["org_auditor"], name="Agent Hichem")
    lookup = "/api/v1/staff/certificates/lookup"

    # The QR code gives the whole verification URL; a typed code may be in lower case.
    by_url = await client.get(lookup, params={"code": cert["verify_url"]}, headers=auditor)
    assert by_url.status_code == 200, by_url.text
    view = by_url.json()
    assert view["valid"] is True and view["reasons"] == [] and view["can_stamp"] is True
    assert view["signature_valid"] is True and view["org_id"] == org_id
    assert view["certificate"]["needs_update"] is False
    assert (await client.get(lookup, params={"code": cert["code"].lower()}, headers=auditor)).json()["valid"] is True
    bad = await client.get(lookup, params={"code": "not a certificate"}, headers=auditor)
    assert (bad.status_code, bad.json()["detail"]) == (422, "invalid_code")
    assert (
        await client.get(lookup, params={"code": cert["code"]}, headers=staff(["org_auditor"], gouvernorat=11))
    ).status_code == 404

    # An operator may check it but not stamp it.
    operator = staff(["operator"])
    assert (await client.get(lookup, params={"code": cert["code"]}, headers=operator)).json()["can_stamp"] is False
    stamps = f"/api/v1/staff/certificates/{cert['id']}/stamps"
    tunis_today = datetime.now(certificate.TUNIS_TZ).date()
    body = {"place": "الإدارة الجهوية للحماية المدنية بصفاقس", "stamped_on": tunis_today.isoformat()}
    assert (await client.post(stamps, json=body, headers=operator)).status_code == 403

    future = await client.post(
        stamps, json=body | {"stamped_on": (tunis_today + timedelta(days=1)).isoformat()}, headers=auditor
    )
    assert (future.status_code, future.json()["detail"]) == (422, "invalid_stamp_date")
    before = await client.post(stamps, json=body | {"stamped_on": "2020-01-01"}, headers=auditor)
    assert (before.status_code, before.json()["detail"]) == (422, "invalid_stamp_date")
    blank = await client.post(stamps, json=body | {"place": "   "}, headers=auditor)
    assert (blank.status_code, blank.json()["detail"]) == (422, "place_required")

    r = await client.post(stamps, json=body | {"note": "Original présenté"}, headers=auditor)
    assert r.status_code == 201, r.text
    stamp = r.json()
    assert stamp["stamped_by_name"] == "Agent Hichem" and stamp["has_photo"] is False and stamp["changes"] == []

    photo = f"{stamps}/{stamp['id']}/photo"
    wrong = await client.put(photo, content=b"%PDF-1.7 not an image", headers=auditor)
    assert (wrong.status_code, wrong.json()["detail"]) == (415, "unsupported_media_type")
    huge = await client.put(photo, content=b"\xff\xd8\xff" + bytes(domain.STAMP_PHOTO_MAX_BYTES), headers=auditor)
    assert (huge.status_code, huge.json()["detail"]) == (413, "photo_too_large")
    r = await client.put(photo, content=JPEG, headers=auditor)
    assert r.status_code == 200 and r.json()["has_photo"] is True
    key = next(k for k in fake_store.objects if f"/stamps/{stamp['id']}-" in k)
    assert fake_store.objects[key] == JPEG
    download = await client.get(photo, headers=operator)
    assert download.status_code == 200 and download.json()["url"]

    # Shown to the institution, and publicly as place and date only.
    mine = (await client.get(f"/api/v1/orgs/{org_id}/certificates", headers=admin)).json()[0]
    assert [s["place"] for s in mine["stamps"]] == [body["place"]]
    public = (await client.get(f"/api/v1/public/certificates/{cert['code']}")).json()
    assert public["stamps"] == [{"place": body["place"], "stamped_on": body["stamped_on"]}]
    assert "Hichem" not in str(public)
    assert await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'certificate.stamp' AND details->>'code' = :c"),
        {"c": cert["code"]},
    )

    # The electronic seal is on the approved PDF's page.
    row = await session.get(Certificate, uuid.UUID(cert["id"]))
    assert row is not None
    page = certificate.render_html(row, cert["verify_url"])
    assert "ختم إلكتروني" in page and "[SIM]" in page and (row.key_id or "") in page

    # A revoked certificate cannot be stamped any more.
    await client.post(f"/api/v1/staff/certificates/{cert['id']}/revoke", json={"reason": "Erreur"}, headers=auditor)
    view = (await client.get(lookup, params={"code": cert["code"]}, headers=auditor)).json()
    assert view["valid"] is False and view["reasons"] == ["revoked"] and view["can_stamp"] is False
    refused = await client.post(stamps, json=body, headers=auditor)
    assert (refused.status_code, refused.json()["detail"]) == (409, "certificate_not_valid")
