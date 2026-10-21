"""Phase 10 §5: four eyes on alerts, the emergency override, and delivery failures that reach a person."""

from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.notify.providers import Providers, set_providers
from app.modules.settings import service as settings_service
from tests.conftest import FakeChannel, TokenFactory, outbox_events
from tests.test_notifications import SFAX, Staff, alert_body, citizen_headers, drain, info_body, register

URL = "/api/v1/staff/notifications"


async def _draft(client: httpx.AsyncClient, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    r = await client.post(URL, json=alert_body(area={"gouvernorat_codes": [61]}, **overrides), headers=headers)
    assert r.status_code == 201, r.text
    return dict(r.json())


async def test_the_author_does_not_publish_alone(client: httpx.AsyncClient, staff: Staff) -> None:
    author, second = staff(["local_committee"], gouvernorat=61), staff(["local_committee"], gouvernorat=61)
    alert = await _draft(client, author)
    r = await client.post(f"{URL}/{alert['id']}/publish", headers=author)
    assert (r.status_code, r.json()["detail"]) == (403, "second_reviewer_required")
    r = await client.post(f"{URL}/{alert['id']}/publish", json={"emergency_reason": "vite"}, headers=author)
    assert (r.status_code, r.json()["detail"]) == (422, "reason_required")
    r = await client.post(f"{URL}/{alert['id']}/publish", headers=second)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "published" and r.json()["single_reviewer"] is False


async def test_the_last_editor_does_not_publish_alone(client: httpx.AsyncClient, staff: Staff) -> None:
    author = staff(["ops_manager"], gouvernorat=61)
    editor, third = staff(["local_committee"], gouvernorat=61), staff(["local_committee"], gouvernorat=61)
    alert = await _draft(client, author)
    body = alert_body(area={"gouvernorat_codes": [61]}, severity="medium", version=alert["version"])
    r = await client.put(f"{URL}/{alert['id']}", json=body, headers=editor)
    assert r.status_code == 200, r.text
    r = await client.post(f"{URL}/{alert['id']}/publish", headers=editor)
    assert (r.status_code, r.json()["detail"]) == (403, "second_reviewer_required")
    assert (await client.post(f"{URL}/{alert['id']}/publish", headers=third)).status_code == 200


async def test_emergency_override_then_second_look(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    author = staff(["local_committee"], gouvernorat=61)
    alert = await _draft(client, author)
    reason = "Crue soudaine, aucun second responsable joignable"
    r = await client.post(f"{URL}/{alert['id']}/publish", json={"emergency_reason": reason}, headers=author)
    assert r.status_code == 200, r.text
    published = r.json()
    assert published["single_reviewer"] is True and published["emergency_reason"] == reason
    assert published["reviewed_at"] is None
    assert await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'alert.publish_single' AND target = :t AND reason = :r"),
        {"t": f"notification:{alert['id']}", "r": reason},
    )
    needed = await outbox_events(session, "alert.review_needed")
    assert any(e["message"]["id"] == alert["id"] for e in needed)

    # The author cannot acknowledge their own emergency publication; another publisher can, once.
    ack = f"{URL}/{alert['id']}/acknowledge"
    r = await client.post(ack, headers=author)
    assert (r.status_code, r.json()["detail"]) == (403, "second_reviewer_required")
    assert (await client.post(ack, headers=staff(["operator"], gouvernorat=61))).status_code == 403
    r = await client.post(ack, headers=staff(["local_committee"], gouvernorat=61, name="Second Regard"))
    assert r.status_code == 200, r.text
    assert r.json()["reviewed_by"] == "Second Regard" and r.json()["reviewed_at"]
    r = await client.post(ack, headers=staff(["local_committee"], gouvernorat=61))
    assert (r.status_code, r.json()["detail"]) == (409, "already_acknowledged")


async def test_only_emergency_publications_are_acknowledged(client: httpx.AsyncClient, staff: Staff) -> None:
    alert = await _draft(client, staff(["local_committee"], gouvernorat=61))
    publisher = staff(["local_committee"], gouvernorat=61)
    await client.post(f"{URL}/{alert['id']}/publish", headers=publisher)
    r = await client.post(f"{URL}/{alert['id']}/acknowledge", headers=staff(["local_committee"], gouvernorat=61))
    assert (r.status_code, r.json()["detail"]) == (409, "invalid_transition")


async def test_information_messages_and_the_setting(client: httpx.AsyncClient, staff: Staff) -> None:
    # Informational messages keep the phase 5 rule: their editor publishes them.
    editor = staff(["content_editor"], gouvernorat=None)
    info = (await client.post(URL, json=info_body(), headers=editor)).json()
    assert (await client.post(f"{URL}/{info['id']}/publish", headers=editor)).status_code == 200

    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(text("UPDATE platform.setting SET value = 'false' WHERE key = 'alerts.four_eyes'"))
    settings_service.invalidate()
    try:
        author = staff(["local_committee"], gouvernorat=61)
        alert = await _draft(client, author)
        r = await client.post(f"{URL}/{alert['id']}/publish", headers=author)
        assert r.status_code == 200 and r.json()["single_reviewer"] is False
    finally:
        async with get_system_sessionmaker()() as s, s.begin():
            await s.execute(text("UPDATE platform.setting SET value = 'true' WHERE key = 'alerts.four_eyes'"))
        settings_service.invalidate()


async def test_four_eyes_setting_is_a_security_admin_choice(client: httpx.AsyncClient, staff: Staff) -> None:
    url = "/api/v1/staff/settings/alerts.four_eyes"
    body = {"value": "no", "version": 1, "reason": "Essai de valeur invalide"}
    r = await client.put(url, json=body, headers=staff(["security_admin"], gouvernorat=None))
    assert r.status_code == 422, r.text
    r = await client.put(url, json=body | {"value": False}, headers=staff(["central_committee"], gouvernorat=None))
    assert r.status_code == 403


async def _published(client: httpx.AsyncClient, staff: Staff) -> dict[str, Any]:
    alert = await _draft(client, staff(["local_committee"], gouvernorat=61))
    r = await client.post(f"{URL}/{alert['id']}/publish", headers=staff(["local_committee"], gouvernorat=61))
    assert r.status_code == 200, r.text
    return dict(r.json())


async def test_unconfigured_channel_reaches_a_person(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    set_providers(Providers(push=FakeChannel(configured=False), sms=FakeChannel(), email=FakeChannel()))
    alert = await _published(client, staff)
    await drain()
    events = [e for e in await outbox_events(session, "alert.delivery_degraded") if e["message"]["id"] == alert["id"]]
    assert [(e["channel"], e["reason"]) for e in events] == [("push", "not_configured")]
    assert await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'alert.delivery_degraded' AND target = :t"),
        {"t": f"notification:{alert['id']}"},
    )


class _FailingPush(FakeChannel):
    async def send(self, *args: Any) -> Any:
        from app.modules.notify.providers import Result

        self.sent.append(args)
        return Result(ok=False, error="http_503")


async def test_failed_deliveries_reach_a_person(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    await register(client, citizen_headers(make_token), SFAX)
    set_providers(Providers(push=_FailingPush(), sms=FakeChannel(), email=FakeChannel()))
    alert = await _published(client, staff)
    await drain()
    events = [e for e in await outbox_events(session, "alert.delivery_degraded") if e["message"]["id"] == alert["id"]]
    assert len(events) == 1 and events[0]["reason"] == "failures" and events[0]["failed"] >= 1


def test_the_failure_threshold() -> None:
    from app.modules.notify import delivery
    from app.modules.notify.models import Dispatch, Message

    row = Dispatch(channel="push", purpose="publish", status="done", sent=95, failed=4)
    assert delivery.degraded(row, Message(kind="alert")) is None
    row.failed = 11
    assert delivery.degraded(row, Message(kind="alert")) == "failures"
    assert delivery.degraded(row, Message(kind="info")) is None
