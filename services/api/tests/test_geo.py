import re

import httpx


async def test_24_gouvernorats_in_arabic_by_default(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/geo/gouvernorats")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 24
    by_code = {g["code"]: g for g in data}
    assert by_code[11]["name"] == "تونس"
    assert by_code[61]["name"] == "صفاقس"
    assert by_code[61]["iso_code"] == "TN-61"
    assert all(re.fullmatch(r"TN-\d{2}", g["iso_code"]) for g in data)
    assert sum(g["delegation_count"] for g in data) == 279
    assert "max-age" in r.headers["Cache-Control"]


async def test_french_names(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/geo/gouvernorats", params={"lang": "fr"})
    names = {g["code"]: g["name"] for g in r.json()}
    assert names[82] == "Médenine"


async def test_delegations_of_sfax(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/geo/gouvernorats/61/delegations")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 16
    assert {d["gouvernorat_code"] for d in data} == {61}
    assert "قرقنة" in {d["name"] for d in data}
    assert all(re.fullmatch(r"TN-61-\d{2}", d["code"]) for d in data)


async def test_unknown_gouvernorat(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/geo/gouvernorats/99/delegations")
    assert r.status_code == 404


async def test_invalid_lang_rejected(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/geo/gouvernorats", params={"lang": "de"})
    assert r.status_code == 422
