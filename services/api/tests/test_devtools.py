# covers: NFR-13
"""The «تطوير النظام» menu (docs/dev/repo-map.md): the repository map, for the national system administrator."""

import httpx

from tests.conftest import STAFF_ISS, TokenFactory, bearer

URL = "/api/v1/admin/dev/repo-map"


async def test_the_repository_map_is_for_the_national_sysadmin(
    client: httpx.AsyncClient, make_token: TokenFactory
) -> None:
    national = bearer(make_token(issuer=STAFF_ISS, roles=["sysadmin"], scope_level="national"))
    regional = bearer(make_token(issuer=STAFF_ISS, roles=["sysadmin"], gouvernorat_code="11"))
    operator = bearer(make_token(issuer=STAFF_ISS, roles=["operator"], scope_level="national"))
    assert (await client.get(URL, headers=operator)).status_code == 403
    assert (await client.get(URL, headers=regional)).status_code == 403
    out = await client.get(URL, headers=national)
    assert out.status_code == 200
    body = out.json()
    ids = {n["id"] for n in body["nodes"]}
    assert {"api:sqlconsole", "api:devtools", "dashboard:SqlConsolePage", "infra:postgres"} <= ids
    assert all(e["s"] in ids and e["t"] in ids for e in body["edges"])
    assert {e["k"] for e in body["edges"]} == {"import", "http", "calls"}
    assert body["routes"] > 100 and body["generated_at"]
