"""Regional audit view (phase 9, docs/api/phase-9-contract.md §7): entries carry the gouvernorats they concern inside
the hash chain; a regional manager reads the entries of its own gouvernorat only, redacted; the chain stays intact."""

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import service
from tests.conftest import SFAX
from tests.scopehelpers import Staff, new_report

URL = "/api/v1/staff/audit"


async def test_scoped_view_own_gouvernorat_redacted(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    sfax_report = await new_report(client, SFAX)
    operator = staff(gouvernorat=61, name="Sami Opérateur")
    r = await client.post(f"/api/v1/staff/reports/{sfax_report['id']}/claim", headers=operator)
    assert r.status_code == 200, r.text
    r = await client.request(
        "DELETE",
        f"/api/v1/staff/reports/{sfax_report['id']}/claim",
        json={"reason": "erreur de prise en charge"},
        headers=staff(["ops_manager"], gouvernorat=61),
    )
    assert r.status_code == 200, r.text
    manager = staff(["ops_manager"], gouvernorat=61)
    r = await client.get(URL, params={"limit": 200}, headers=manager)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items and all(61 in i["gouvernorats"] for i in items)
    claim = next(i for i in items if i["action"] == "report.claim" and i["target"] == f"report:{sfax_report['id']}")
    # Who acted by name only: no account id, no hash.
    assert claim["actor_name"] == "Sami Opérateur"
    assert "hash" not in claim and "actor" not in claim
    assert not any(str(v).startswith("staff:") for v in claim["details"].values())
    # Another gouvernorat's manager does not see it.
    gabes = (await client.get(URL, params={"limit": 200}, headers=staff(["ops_manager"], gouvernorat=81))).json()
    assert all(81 in i["gouvernorats"] for i in gabes["items"])
    assert claim["seq"] not in {i["seq"] for i in gabes["items"]}
    # Reading is audited, for the reader's gouvernorat.
    read = await session.scalar(
        text("SELECT details FROM audit.log WHERE action = 'audit.read_scoped' ORDER BY seq DESC LIMIT 1")
    )
    assert read["gouvernorats"] == [81]


async def test_scoped_view_roles(client: httpx.AsyncClient, staff: Staff) -> None:
    assert (await client.get(URL, headers=staff(["local_committee"], gouvernorat=61))).status_code == 200
    assert (await client.get(URL, headers=staff(["security_admin"], gouvernorat=61))).status_code == 200
    for role in ("operator", "field_commander", "sysadmin", "content_editor"):
        assert (await client.get(URL, headers=staff([role], gouvernorat=61))).status_code == 403, role
    # The national room uses the raw log instead.
    r = await client.get(URL, headers=staff(["ops_manager"], gouvernorat=None))
    assert r.status_code == 403


async def test_raw_entries_keep_their_scope_and_chain(session: AsyncSession) -> None:
    entry = await service.record(
        session, actor="system", action="test.scope", details={"x": 1}, gouvernorats=[61, 43, 61]
    )
    await session.commit()
    stored = (
        await session.execute(text("SELECT details, gouvernorats FROM audit.log WHERE seq = :s"), {"s": entry.seq})
    ).one()
    assert stored.details["gouvernorats"] == [43, 61] and sorted(stored.gouvernorats) == [43, 61]
    national = await service.record(session, actor="system", action="test.national")
    await session.commit()
    assert (await session.scalar(text("SELECT gouvernorats FROM audit.log WHERE seq = :s"), {"s": national.seq})) in (
        None,
        [],
    )
    assert await service.verify_chain(session) is None


async def test_real_send_flag_not_writable(client: httpx.AsyncClient, staff: Staff) -> None:
    for role in ("central_committee", "security_admin"):
        r = await client.put(
            "/api/v1/staff/settings/notify.real_send_enabled",
            json={"value": True, "version": 1, "reason": "essai d'envoi réel"},
            headers=staff([role], gouvernorat=None),
        )
        assert (r.status_code, r.json()["detail"]) == (403, "requires_formal_approval"), role
