"""National settings (phase 9, docs/api/phase-9-contract.md §2): defaults, who may change what, versions, audit."""

from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.modules.settings import service as settings_service
from tests.conftest import outbox_events

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/settings"


@pytest.fixture
async def restore_settings() -> AsyncIterator[None]:
    """Put every national setting back as it was after the test (other tests rely on the defaults)."""
    async with get_sessionmaker()() as s:
        saved = (await s.execute(text("SELECT key, value::text, version FROM platform.setting"))).all()
    yield
    async with get_sessionmaker()() as s, s.begin():
        for key, value, version in saved:
            await s.execute(
                text("UPDATE platform.setting SET value = CAST(:v AS jsonb), version = :n WHERE key = :k"),
                {"k": key, "v": value, "n": version},
            )
    settings_service.invalidate()


def _items(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["key"]: item for item in body["items"]}


async def _put(
    client: httpx.AsyncClient, headers: dict[str, str], key: str, value: Any, version: int, reason: str = "test change"
) -> httpx.Response:
    return await client.put(
        f"{URL}/{key}", json={"value": value, "version": version, "reason": reason}, headers=headers
    )


async def test_defaults_present(client: httpx.AsyncClient, staff: Staff) -> None:
    r = await client.get(URL, headers=staff())
    assert r.status_code == 200, r.text
    items = _items(r.json())
    assert items["sla.bands"]["value"] == {"critical": 85, "high": 70, "normal": 40}
    assert items["sla.claim_delay_s"]["value"] == {"critical": 60, "high": 90, "normal": 120, "low": 180}
    assert items["anonymous.report_quota"]["value"] == 5
    assert items["geo.max_trusted_accuracy_m"]["value"] == 1000
    assert items["notify.real_send_enabled"]["value"] is False
    assert isinstance(items["sla.enforced_since"]["value"], str)
    # A regional operator reads everything and may change nothing.
    assert not any(item["editable"] for item in items.values())

    central = _items((await client.get(URL, headers=staff(["central_committee"], gouvernorat=None))).json())
    assert {k for k, v in central.items() if v["editable"]} == {
        "sla.bands",
        "sla.claim_delay_s",
        "anonymous.report_quota",
        "geo.max_trusted_accuracy_m",
    }
    security = _items((await client.get(URL, headers=staff(["security_admin"], gouvernorat=None))).json())
    assert {k for k, v in security.items() if v["editable"]} == {"anonymous.report_quota"}


async def test_readers_and_anonymous_callers(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    assert (await client.get(URL)).status_code == 401
    assert (await client.get(URL, headers=citizen)).status_code == 403


async def test_regional_refused(client: httpx.AsyncClient, staff: Staff, restore_settings: None) -> None:
    value = {"critical": 50, "high": 90, "normal": 120, "low": 180}
    regional = staff(["central_committee"], gouvernorat=61)
    r = await _put(client, regional, "sla.claim_delay_s", value, 1)
    assert (r.status_code, r.json()["detail"]) == (403, "national_scope_required")
    r = await _put(client, staff(["operator"], gouvernorat=None), "sla.claim_delay_s", value, 1)
    assert (r.status_code, r.json()["detail"]) == (403, "action_not_allowed")


async def test_technical_roles_only_within_their_domain(
    client: httpx.AsyncClient, staff: Staff, restore_settings: None
) -> None:
    security = staff(["security_admin"], gouvernorat=None)
    ai_admin = staff(["ai_admin"], gouvernorat=None)
    sysadmin = staff(["sysadmin"], gouvernorat=None)
    delays = {"critical": 50, "high": 90, "normal": 120, "low": 180}
    for headers in (security, ai_admin, sysadmin):
        r = await _put(client, headers, "sla.claim_delay_s", delays, 1)
        assert (r.status_code, r.json()["detail"]) == (403, "action_not_allowed")
    for headers in (ai_admin, sysadmin):
        assert (await _put(client, headers, "anonymous.report_quota", 3, 1)).status_code == 403
    r = await _put(client, security, "anonymous.report_quota", 3, 1)
    assert r.status_code == 200, r.text
    assert r.json()["value"] == 3 and r.json()["version"] == 2


async def test_version_conflict(client: httpx.AsyncClient, staff: Staff, restore_settings: None) -> None:
    central = staff(["central_committee"], gouvernorat=None)
    current = _items((await client.get(URL, headers=central)).json())["geo.max_trusted_accuracy_m"]
    r = await _put(client, central, "geo.max_trusted_accuracy_m", 500, current["version"])
    assert r.status_code == 200, r.text
    assert r.json()["version"] == current["version"] + 1 and r.json()["editable"] is True
    stale = await _put(client, central, "geo.max_trusted_accuracy_m", 800, current["version"])
    assert (stale.status_code, stale.json()["detail"]) == (409, "version_conflict")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("sla.bands", {"critical": 60, "high": 70, "normal": 40}),
        ("sla.bands", {"critical": 85, "high": 70, "normal": 70}),
        ("sla.bands", {"critical": 85, "high": 70}),
        ("sla.bands", {"critical": 101, "high": 70, "normal": 40}),
        ("sla.claim_delay_s", {"critical": 120, "high": 90, "normal": 120, "low": 180}),
        ("sla.claim_delay_s", {"critical": 10, "high": 90, "normal": 120, "low": 180}),
        ("sla.claim_delay_s", {"critical": 60, "high": 90, "normal": 120, "low": 4000}),
        ("anonymous.report_quota", 0),
        ("anonymous.report_quota", 101),
        ("anonymous.report_quota", "5"),
        ("anonymous.report_quota", True),
        ("geo.max_trusted_accuracy_m", 10),
        ("geo.max_trusted_accuracy_m", 30_000),
    ],
)
async def test_validation(client: httpx.AsyncClient, staff: Staff, key: str, value: Any) -> None:
    central = staff(["central_committee"], gouvernorat=None)
    version = _items((await client.get(URL, headers=central)).json())[key]["version"]
    r = await _put(client, central, key, value, version)
    assert (r.status_code, r.json()["detail"]) == (422, "invalid_setting")


async def test_reason_required_and_unknown_key(client: httpx.AsyncClient, staff: Staff) -> None:
    central = staff(["central_committee"], gouvernorat=None)
    assert (await _put(client, central, "anonymous.report_quota", 4, 1, reason="no")).status_code == 422
    r = await _put(client, central, "unknown.key", 4, 1)
    assert (r.status_code, r.json()["detail"]) == (404, "not_found")


async def test_audit_before_after_and_event(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession, restore_settings: None
) -> None:
    central = staff(["central_committee"], gouvernorat=None, name="Leila Trabelsi")
    current = _items((await client.get(URL, headers=central)).json())["sla.bands"]
    after = {"critical": 90, "high": 75, "normal": 45}
    r = await _put(client, central, "sla.bands", after, current["version"], reason="nouvelle grille nationale")
    assert r.status_code == 200, r.text
    assert r.json()["updated_by_name"] == "Leila Trabelsi"
    row = (
        await session.execute(
            text(
                "SELECT reason, details FROM audit.log WHERE action = 'settings.update' AND target = 'setting:sla.bands' "
                "ORDER BY seq DESC LIMIT 1"
            )
        )
    ).one()
    assert row.reason == "nouvelle grille nationale"
    assert row.details["before"] == current["value"] and row.details["after"] == after
    assert {"key": "sla.bands"} in await outbox_events(session, "settings.changed")
    # The cache is dropped at once: the new value is what the API reads now.
    assert await settings_service.get(session, "sla.bands") == after


async def test_read_only_and_formally_approved_keys(client: httpx.AsyncClient, staff: Staff) -> None:
    central = staff(["central_committee"], gouvernorat=None)
    r = await _put(client, central, "notify.real_send_enabled", True, 1)
    assert (r.status_code, r.json()["detail"]) == (403, "requires_formal_approval")
    r = await _put(client, staff(["security_admin"], gouvernorat=None), "notify.real_send_enabled", True, 1)
    assert (r.status_code, r.json()["detail"]) == (403, "requires_formal_approval")
    r = await _put(client, central, "sla.enforced_since", "2020-01-01T00:00:00+00:00", 1)
    assert (r.status_code, r.json()["detail"]) == (403, "action_not_allowed")


async def test_cache_dropped_on_bus_event(session: AsyncSession, restore_settings: None) -> None:
    assert await settings_service.get(session, "anonymous.report_quota") == 5
    await session.execute(text("UPDATE platform.setting SET value = '7' WHERE key = 'anonymous.report_quota'"))
    await session.commit()
    # Cached for a few seconds on this instance…
    assert await settings_service.get(session, "anonymous.report_quota") == 5
    # …until another instance announces the change.
    await settings_service.on_event("settings.changed", {"key": "anonymous.report_quota"})
    assert await settings_service.get(session, "anonymous.report_quota") == 7
