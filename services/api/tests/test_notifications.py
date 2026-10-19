"""Phase 5: push devices, informational notifications, geographic alerts, the app inbox and safety tips."""

import secrets
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text

from app.core.db import get_sessionmaker
from app.modules.notify import delivery, service
from app.modules.notify.providers import Providers, Push, set_providers
from tests.conftest import FakeChannel, TokenFactory, bearer

Staff = Callable[..., dict[str, str]]
SFAX = (34.7406, 10.7603)
TUNIS = (36.8065, 10.1815)
# A small square around Sfax city centre (lon, lat).
SFAX_SQUARE = {
    "type": "Polygon",
    "coordinates": [[[10.70, 34.70], [10.82, 34.70], [10.82, 34.80], [10.70, 34.80], [10.70, 34.70]]],
}


@pytest.fixture(autouse=True)
async def _normal_levels() -> AsyncIterator[None]:
    yield
    async with get_sessionmaker()() as s, s.begin():
        await s.execute(text("UPDATE ops.level_state SET level = 'normal', reason = NULL"))


def citizen_headers(make_token: TokenFactory, email: str | None = None) -> dict[str, str]:
    email = email or f"c{secrets.token_hex(4)}@example.tn"
    return bearer(make_token(roles=["citizen"], email=email, email_verified=True))


def new_token() -> str:
    return "fcm-" + secrets.token_urlsafe(40)


async def register(
    client: httpx.AsyncClient, headers: dict[str, str], place: tuple[float, float] | None, **extra: Any
) -> str:
    token = new_token()
    body: dict[str, Any] = {"token": token, "platform": "android", "locale": "fr", **extra}
    if place is not None:
        body |= {"lat": place[0], "lon": place[1]}
    r = await client.put("/api/v1/devices", json=body, headers=headers)
    assert r.status_code == 204, r.text
    return token


async def user_of(token: str) -> str:
    async with get_sessionmaker()() as s:
        return str(await s.scalar(text("SELECT user_id FROM notify.device WHERE token = :t"), {"t": token}))


def alert_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "alert",
        "title": {"ar": "تنبيه أمطار غزيرة", "fr": "Alerte pluies abondantes", "en": "Heavy rain alert"},
        "body": {"ar": "تجنبوا الأودية", "fr": "Évitez les oueds", "en": "Keep away from wadis"},
        "channels": ["push"],
        "severity": "high",
        "category": "weather",
        "hazard": "heavy_rain",
        "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    }
    body.update(overrides)
    return body


def info_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "info",
        "title": {"ar": "يوم تحسيسي", "fr": "Journée de sensibilisation"},
        "body": {"ar": "يوم مفتوح للإسعافات الأولية", "fr": "Journée portes ouvertes premiers secours"},
        "channels": ["push"],
        "topic": "awareness",
        "audience": "all",
    }
    body.update(overrides)
    return body


async def drain() -> None:
    """Run every waiting fan-out job to the end, as the delivery worker would."""
    sessionmaker = get_sessionmaker()
    for _ in range(200):
        if not await delivery.run_job(sessionmaker):
            return
    raise AssertionError("delivery did not settle")


def pushes_to(channel: FakeChannel, token: str, message_id: str | None = None) -> list[Push]:
    """Pushes sent to a device (for one message): other tests' queued jobs may also reach it."""
    return [
        args[0]
        for args in channel.sent
        if isinstance(args[0], Push)
        and args[0].token == token
        and (message_id is None or args[0].data.get("id") == message_id)
    ]


async def active_ids(client: httpx.AsyncClient, **params: Any) -> set[str]:
    r = await client.get("/api/v1/alerts/active", params=params)
    assert r.status_code == 200, r.text
    return {a["id"] for a in r.json()}


async def inbox_ids(client: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, dict[str, Any]]:
    r = await client.get("/api/v1/notifications", headers=headers)
    assert r.status_code == 200, r.text
    return {i["id"]: i for i in r.json()["items"]}


# ---------------------------------------------------------------- devices


async def test_device_registration(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    headers = citizen_headers(make_token)
    token = await register(client, headers, SFAX)
    async with get_sessionmaker()() as s:
        row = (
            await s.execute(
                text(
                    "SELECT locale, gouvernorat_code, ST_Y(CAST(location AS geometry)), "
                    "ST_X(CAST(location AS geometry)) "
                    "FROM notify.device WHERE token = :t"
                ),
                {"t": token},
            )
        ).one()
    # Only a coarse position is kept (about 1 km).
    assert row == ("fr", 61, 34.74, 10.76)

    r = await client.put(
        "/api/v1/devices",
        json={"token": token, "platform": "android", "locale": "ar", "location_alerts": False},
        headers=headers,
    )
    assert r.status_code == 204
    async with get_sessionmaker()() as s:
        row = (
            await s.execute(
                text("SELECT locale, gouvernorat_code, location FROM notify.device WHERE token = :t"), {"t": token}
            )
        ).one()
    assert row == ("ar", None, None)

    bad = {"token": new_token(), "platform": "android", "lat": 48.85, "lon": 2.35}
    assert (await client.put("/api/v1/devices", json=bad, headers=headers)).status_code == 422
    assert (
        await client.put("/api/v1/devices", json={"token": "short", "platform": "ios"}, headers=headers)
    ).status_code == 422

    # Another account cannot forget someone else's device.
    other = citizen_headers(make_token)
    assert (await client.delete(f"/api/v1/devices/{token}", headers=other)).status_code == 204
    async with get_sessionmaker()() as s:
        assert await s.scalar(text("SELECT count(*) FROM notify.device WHERE token = :t"), {"t": token}) == 1
    assert (await client.delete(f"/api/v1/devices/{token}", headers=headers)).status_code == 204
    async with get_sessionmaker()() as s:
        assert await s.scalar(text("SELECT count(*) FROM notify.device WHERE token = :t"), {"t": token}) == 0


# ---------------------------------------------------------------- alerts


async def test_alert_lifecycle(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, channels: Any
) -> None:
    sfax_citizen, tunis_citizen = citizen_headers(make_token), citizen_headers(make_token)
    sfax_token = await register(client, sfax_citizen, SFAX)
    stale_token = await register(client, citizen_headers(make_token), SFAX)
    tunis_token = await register(client, tunis_citizen, TUNIS)
    channels.push.unregistered.add(stale_token)

    local = staff(["local_committee"], gouvernorat=61)
    assert (
        await client.post("/api/v1/staff/notifications", json=alert_body(), headers=staff(["operator"]))
    ).status_code == 403
    r = await client.post(
        "/api/v1/staff/notifications", json=alert_body(area={"gouvernorat_codes": [11]}), headers=local
    )
    assert (r.status_code, r.json()["detail"]) == (403, "out_of_scope")

    # The operations manager drafts; a committee publishes.
    manager = staff(["ops_manager"], gouvernorat=61)
    r = await client.post("/api/v1/staff/notifications", json=alert_body(), headers=manager)
    assert r.status_code == 201, r.text
    alert = r.json()
    assert alert["status"] == "draft" and alert["area"]["gouvernorat_codes"] == [61]
    assert (await client.post(f"/api/v1/staff/notifications/{alert['id']}/publish", headers=manager)).status_code == 403

    audience = (await client.get(f"/api/v1/staff/notifications/{alert['id']}/audience", headers=local)).json()
    assert audience["push"] >= 2

    r = await client.post(f"/api/v1/staff/notifications/{alert['id']}/publish", headers=local)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "published" and r.json()["stats"]["push"]["status"] == "pending"
    assert (await client.post(f"/api/v1/staff/notifications/{alert['id']}/publish", headers=local)).json()[
        "detail"
    ] == "not_draft"

    await drain()
    [push] = pushes_to(channels.push, sfax_token, alert["id"])
    assert push.alert and push.title == "Alerte pluies abondantes" and push.data["severity"] == "high"
    assert pushes_to(channels.push, tunis_token, alert["id"]) == []
    async with get_sessionmaker()() as s:
        assert await s.scalar(text("SELECT count(*) FROM notify.device WHERE token = :t"), {"t": stale_token}) == 0
    stats = (await client.get(f"/api/v1/staff/notifications/{alert['id']}", headers=local)).json()["stats"]["push"]
    assert stats["status"] == "done" and stats["sent"] >= 1 and stats["failed"] >= 1

    assert alert["id"] in await active_ids(client, lat=SFAX[0], lon=SFAX[1])
    assert alert["id"] in await active_ids(client, gouvernorat_code=61)
    assert alert["id"] in await active_ids(client)
    assert alert["id"] not in await active_ids(client, lat=TUNIS[0], lon=TUNIS[1])
    staff_active = await client.get("/api/v1/staff/alerts/active", headers=staff(["operator"]))
    assert alert["id"] in {a["id"] for a in staff_active.json()}

    inbox = await inbox_ids(client, sfax_citizen)
    assert inbox[alert["id"]]["active"] is True
    assert alert["id"] not in await inbox_ids(client, tunis_citizen)

    r = await client.post(f"/api/v1/staff/notifications/{alert['id']}/cancel", headers=local)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    await drain()
    cancel = pushes_to(channels.push, sfax_token, alert["id"])[-1]
    assert cancel.data == {"type": "alert_cancelled", "id": alert["id"]} and not cancel.alert
    assert alert["id"] not in await active_ids(client, lat=SFAX[0], lon=SFAX[1])
    assert (await inbox_ids(client, sfax_citizen))[alert["id"]]["active"] is False


async def test_alert_area_validation_and_scope(client: httpx.AsyncClient, staff: Staff) -> None:
    central = staff(["central_committee"], gouvernorat=None)
    post = lambda body, headers=central: client.post("/api/v1/staff/notifications", json=body, headers=headers)  # noqa: E731

    cases = [
        (alert_body(area={"gouvernorat_codes": [61], "polygon": SFAX_SQUARE}), "invalid_area"),
        (alert_body(area={"polygon": {"type": "Point", "coordinates": [10.7, 34.7]}}), "invalid_area"),
        (
            alert_body(area={"polygon": {"type": "Polygon", "coordinates": [[[2.3, 48.8], [2.4, 48.8], [2.4, 48.9]]]}}),
            "invalid_area",
        ),
        (alert_body(area={"gouvernorat_codes": [99]}), "invalid_gouvernorat"),
        (alert_body(severity=None), "severity_category_expiry_required"),
        (alert_body(expires_at=(datetime.now(UTC) + timedelta(days=8)).isoformat()), "invalid_expiry"),
        (alert_body(expires_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat()), "invalid_expiry"),
        (info_body(topic=None), "topic_and_audience_required"),
        (info_body(area={"polygon": SFAX_SQUARE}), "invalid_area"),
        (info_body(audience="user", user_id=str(uuid.uuid4())), "invalid_user"),
    ]
    for body, code in cases:
        r = await post(body)
        assert (r.status_code, r.json()["detail"]) == (422, code), (body, r.text)

    r = await post(alert_body(area={"polygon": SFAX_SQUARE}, severity="medium"))
    assert r.status_code == 201, r.text
    alert = r.json()
    assert alert["area"]["polygon"]["type"] == "Polygon"

    # A regional committee sees and handles what touches its gouvernorat only.
    assert (
        await client.get(
            f"/api/v1/staff/notifications/{alert['id']}", headers=staff(["local_committee"], gouvernorat=11)
        )
    ).status_code == 404
    sfax_committee = staff(["local_committee"], gouvernorat=61)
    r = await client.post(f"/api/v1/staff/notifications/{alert['id']}/publish", headers=sfax_committee)
    assert r.status_code == 200, r.text

    assert alert["id"] in await active_ids(client, lat=34.75, lon=10.76)
    assert alert["id"] in await active_ids(client, gouvernorat_code=61)
    assert alert["id"] not in await active_ids(client, lat=34.60, lon=10.50)
    assert alert["id"] not in await active_ids(client, gouvernorat_code=11)

    # A polygon drawn by a regional committee stays within its gouvernorat (5 km tolerance).
    tunis_square = {
        "type": "Polygon",
        "coordinates": [[[10.15, 36.78], [10.20, 36.78], [10.20, 36.83], [10.15, 36.78]]],
    }
    r = await post(alert_body(area={"polygon": tunis_square}), sfax_committee)
    assert (r.status_code, r.json()["detail"]) == (403, "out_of_scope")

    # Expiry ends the alert.
    async with get_sessionmaker()() as s, s.begin():
        await s.execute(
            text("UPDATE notify.message SET expires_at = now() - interval '1 second' WHERE id = :id"),
            {"id": alert["id"]},
        )
        assert uuid.UUID(alert["id"]) in await service.expire_alerts(s)
    assert alert["id"] not in await active_ids(client, lat=34.75, lon=10.76)
    assert (await client.get(f"/api/v1/staff/notifications/{alert['id']}", headers=central)).json()[
        "status"
    ] == "expired"


# ---------------------------------------------------------------- informational notifications


async def test_info_notifications(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, channels: Any
) -> None:
    editor = staff(["content_editor"], gouvernorat=None)
    assert (
        await client.post("/api/v1/staff/notifications", json=info_body(), headers=staff(["ops_manager"]))
    ).status_code == 403

    target, other = citizen_headers(make_token), citizen_headers(make_token)
    target_token = await register(client, target, None)
    await register(client, other, None)
    user_id = await user_of(target_token)

    r = await client.post(
        "/api/v1/staff/notifications", json=info_body(audience="user", user_id=user_id, topic="other"), headers=editor
    )
    assert r.status_code == 201, r.text
    message = r.json()
    assert message["version"] == 1

    # Drafts are edited with optimistic locking, and the kind is fixed.
    put = lambda body: client.put(f"/api/v1/staff/notifications/{message['id']}", json=body, headers=editor)  # noqa: E731
    stale = info_body(audience="user", user_id=user_id, topic="other", version=7)
    assert (await put(stale)).json()["detail"] == "version_conflict"
    assert (await put(alert_body())).json()["detail"] == "kind_change"
    r = await put(info_body(audience="user", user_id=user_id, topic="training", version=1))
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["topic"] == "training"

    assert (
        await client.post(f"/api/v1/staff/notifications/{message['id']}/publish", headers=editor)
    ).status_code == 200
    await drain()
    [push] = pushes_to(channels.push, target_token, message["id"])
    assert not push.alert and push.data["type"] == "info"
    assert message["id"] in await inbox_ids(client, target)
    assert message["id"] not in await inbox_ids(client, other)
    assert (await put(info_body(version=3))).json()["detail"] == "not_draft"
    r = await client.delete(f"/api/v1/staff/notifications/{message['id']}", headers=editor)
    assert (r.status_code, r.json()["detail"]) == (409, "not_draft")

    draft = (await client.post("/api/v1/staff/notifications", json=info_body(), headers=editor)).json()
    assert (await client.delete(f"/api/v1/staff/notifications/{draft['id']}", headers=editor)).status_code == 204
    assert (await client.get(f"/api/v1/staff/notifications/{draft['id']}", headers=editor)).status_code == 404

    listed = (
        await client.get("/api/v1/staff/notifications?kind=info&status=published&limit=100", headers=editor)
    ).json()
    assert message["id"] in {m["id"] for m in listed["items"]}
    assert (await client.get("/api/v1/staff/notifications?status=sent", headers=editor)).status_code == 422


async def test_sms_and_email_channels(client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory) -> None:
    sms = FakeChannel()
    set_providers(Providers(push=FakeChannel(), sms=sms, email=FakeChannel(configured=False)))
    await drain()  # jobs other tests left queued would reach this new profile too

    phone = f"+2162{secrets.randbelow(10_000_000):07d}"
    headers = citizen_headers(make_token)
    profile = {
        "first_name": "Amel",
        "last_name": "Jaziri",
        "cin": f"{secrets.randbelow(100_000_000):08d}",
        "phone": phone,
        "gouvernorat_code": 61,
        "delegation_id": 6101,
        "address": "Route de Tunis",
        "locale": "fr",
    }
    assert (await client.put("/api/v1/me/profile", json=profile, headers=headers)).status_code == 200, "profile"

    editor = staff(["content_editor"], gouvernorat=None)
    body = info_body(channels=["email", "sms", "sms"], area={"gouvernorat_codes": [61]})
    message = (await client.post("/api/v1/staff/notifications", json=body, headers=editor)).json()
    assert message["channels"] == ["sms", "email"]
    audience = (await client.get(f"/api/v1/staff/notifications/{message['id']}/audience", headers=editor)).json()
    assert audience["sms"] >= 1 and audience["email"] >= 1

    await client.post(f"/api/v1/staff/notifications/{message['id']}/publish", headers=editor)
    await drain()
    texts = [t for to, t in sms.sent if to == phone]
    assert texts == ["Journée de sensibilisation: Journée portes ouvertes premiers secours"]
    stats = (await client.get(f"/api/v1/staff/notifications/{message['id']}", headers=editor)).json()["stats"]
    assert stats["sms"]["status"] == "done" and stats["email"]["status"] == "skipped"


async def test_disaster_level_suspends_information_not_alerts(client: httpx.AsyncClient, staff: Staff) -> None:
    async with get_sessionmaker()() as s, s.begin():
        await s.execute(text("UPDATE ops.level_state SET level = 'disaster' WHERE gouvernorat_code = 61"))
    editor = staff(["content_editor"], gouvernorat=None)
    committee = staff(["central_committee"], gouvernorat=None)

    for area in ({"gouvernorat_codes": [61]}, {}):
        info = (await client.post("/api/v1/staff/notifications", json=info_body(area=area), headers=editor)).json()
        r = await client.post(f"/api/v1/staff/notifications/{info['id']}/publish", headers=editor)
        assert (r.status_code, r.json()["detail"]) == (409, "suspended_by_level")

    elsewhere = (
        await client.post(
            "/api/v1/staff/notifications", json=info_body(area={"gouvernorat_codes": [11]}), headers=editor
        )
    ).json()
    assert (
        await client.post(f"/api/v1/staff/notifications/{elsewhere['id']}/publish", headers=editor)
    ).status_code == 200
    alert = (
        await client.post(
            "/api/v1/staff/notifications", json=alert_body(area={"gouvernorat_codes": [61]}), headers=committee
        )
    ).json()
    assert (
        await client.post(f"/api/v1/staff/notifications/{alert['id']}/publish", headers=committee)
    ).status_code == 200


# ---------------------------------------------------------------- safety tips


def tip_content(complete: bool = True) -> dict[str, Any]:
    text_ = {
        "title": "Coupure d'électricité",
        "do": ["Débranchez les appareils"],
        "dont": ["N'utilisez pas l'ascenseur"],
    }
    return {
        "ar": {"title": "انقطاع الكهرباء", "do": ["افصل الأجهزة"], "dont": ["لا تستعمل المصعد"]},
        "fr": text_,
        "en": {"title": "Power cut", "do": ["Unplug appliances"], "dont": []} if complete else {},
    }


async def test_safety_tips(client: httpx.AsyncClient, staff: Staff) -> None:
    r = await client.get("/api/v1/safety-tips")
    assert r.status_code == 200
    etag, seeded = r.headers["ETag"], r.json()
    assert {t["hazard"] for t in seeded["items"]} >= {"fire", "flood", "earthquake"}
    assert all(t["content"]["en"]["title"] for t in seeded["items"])
    assert (await client.get("/api/v1/safety-tips", headers={"If-None-Match": etag})).status_code == 304

    editor = staff(["content_editor"], gouvernorat=None)
    assert (await client.get("/api/v1/staff/safety-tips", headers=staff(["operator"]))).status_code == 403

    r = await client.post(
        "/api/v1/staff/safety-tips",
        json={"hazard": "other", "position": 50, "content": tip_content(False)},
        headers=editor,
    )
    assert r.status_code == 201, r.text
    tip = r.json()
    assert tip["status"] == "draft"
    # Drafts do not change what the app downloads.
    assert (await client.get("/api/v1/safety-tips", headers={"If-None-Match": etag})).status_code == 304

    r = await client.post(f"/api/v1/staff/safety-tips/{tip['id']}/publish", headers=editor)
    assert (r.status_code, r.json()["detail"]) == (409, "translation_missing")
    body = {"hazard": "other", "position": 50, "content": tip_content(), "version": tip["version"]}
    r = await client.put(f"/api/v1/staff/safety-tips/{tip['id']}", json=body, headers=editor)
    assert r.status_code == 200 and r.json()["version"] == 2
    assert (await client.put(f"/api/v1/staff/safety-tips/{tip['id']}", json=body, headers=editor)).json()[
        "detail"
    ] == "version_conflict"

    r = await client.post(f"/api/v1/staff/safety-tips/{tip['id']}/publish", headers=editor)
    assert r.status_code == 200 and r.json()["status"] == "published"
    assert (await client.get("/api/v1/safety-tips", headers={"If-None-Match": etag})).status_code == 200
    public = await client.get("/api/v1/safety-tips")
    assert public.json()["revision"] > seeded["revision"] and public.headers["ETag"] != etag
    assert tip["id"] in {t["id"] for t in public.json()["items"]}

    incomplete = {"hazard": "other", "position": 50, "content": tip_content(False)}
    r = await client.put(f"/api/v1/staff/safety-tips/{tip['id']}", json=incomplete, headers=editor)
    assert (r.status_code, r.json()["detail"]) == (409, "translation_missing")

    assert (await client.post(f"/api/v1/staff/safety-tips/{tip['id']}/unpublish", headers=editor)).status_code == 200
    assert tip["id"] not in {t["id"] for t in (await client.get("/api/v1/safety-tips")).json()["items"]}
    assert (await client.delete(f"/api/v1/staff/safety-tips/{tip['id']}", headers=editor)).status_code == 204
    assert (await client.post(f"/api/v1/staff/safety-tips/{tip['id']}/publish", headers=editor)).status_code == 404


async def test_delivery_continues_across_batches(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, channels: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(delivery, "BATCH", 1)
    headers = citizen_headers(make_token)
    tokens = [await register(client, headers, None) for _ in range(3)]
    editor = staff(["content_editor"], gouvernorat=None)
    body = info_body(audience="user", user_id=await user_of(tokens[0]))
    message = (await client.post("/api/v1/staff/notifications", json=body, headers=editor)).json()
    await client.post(f"/api/v1/staff/notifications/{message['id']}/publish", headers=editor)
    await drain()
    assert all(len(pushes_to(channels.push, t, message["id"])) == 1 for t in tokens)
    stats = (await client.get(f"/api/v1/staff/notifications/{message['id']}", headers=editor)).json()["stats"]
    assert stats["push"] == {"status": "done", "sent": 3, "failed": 0}
