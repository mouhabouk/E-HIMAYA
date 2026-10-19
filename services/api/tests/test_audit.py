import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import service
from tests.conftest import STAFF_ISS, TokenFactory, bearer


async def test_entries_are_chained(session: AsyncSession) -> None:
    first = await service.record(session, actor="system", action="test.one", details={"n": 1})
    second = await service.record(session, actor="system", action="test.two", target="x")
    await session.commit()
    assert second.seq == first.seq + 1
    assert second.prev_hash == first.hash
    assert len(second.hash) == 64
    assert await service.verify_chain(session) is None


@pytest.mark.parametrize("statement", ["UPDATE audit.log SET action = 'forged'", "DELETE FROM audit.log"])
async def test_log_is_append_only(session: AsyncSession, statement: str) -> None:
    await service.record(session, actor="system", action="test.immutable")
    await session.commit()
    with pytest.raises(DBAPIError, match="append-only"):
        await session.execute(text(statement))
    await session.rollback()


async def test_client_cannot_forge_chain_fields(session: AsyncSession) -> None:
    await session.execute(
        text("INSERT INTO audit.log (seq, actor, action, prev_hash, hash) VALUES (999999, 'x', 'forge', 'a', 'b')")
    )
    await session.commit()
    row = (await session.execute(text("SELECT seq, hash FROM audit.log ORDER BY seq DESC LIMIT 1"))).one()
    assert row.seq != 999999 and row.hash != "b"
    assert await service.verify_chain(session) is None


async def test_sysadmin_reads_and_reading_is_audited(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    token = make_token(issuer=STAFF_ISS, roles=["sysadmin"], scope_level="national")
    r = await client.get("/api/v1/admin/audit", headers=bearer(token), params={"limit": 5})
    assert r.status_code == 200
    r = await client.get("/api/v1/admin/audit", headers=bearer(token), params={"limit": 1})
    assert r.json()[0]["action"] == "audit.read"
    r = await client.get("/api/v1/admin/audit/verify", headers=bearer(token))
    assert r.json() == {"intact": True, "first_broken_seq": None}


async def test_operator_cannot_read_audit(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    token = make_token(issuer=STAFF_ISS, roles=["operator"], gouvernorat_code="11")
    r = await client.get("/api/v1/admin/audit", headers=bearer(token))
    assert r.status_code == 403
