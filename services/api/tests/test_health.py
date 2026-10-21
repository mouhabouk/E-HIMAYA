# covers: NFR-05
import httpx


async def test_live(client: httpx.AsyncClient) -> None:
    r = await client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert len(r.headers["X-Request-ID"]) >= 8


async def test_ready_reports_database(client: httpx.AsyncClient) -> None:
    r = await client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["valkey"] == "not configured"


async def test_request_id_is_sanitized(client: httpx.AsyncClient) -> None:
    r = await client.get("/health/live", headers={"X-Request-ID": "bad id\r\ninjected"})
    assert "injected" not in r.headers["X-Request-ID"]
    r = await client.get("/health/live", headers={"X-Request-ID": "abcd-1234-efgh"})
    assert r.headers["X-Request-ID"] == "abcd-1234-efgh"


async def test_answers_are_not_cached_by_default(client: httpx.AsyncClient) -> None:
    assert (await client.get("/health/live")).headers["Cache-Control"] == "no-store"
    # An endpoint that chooses its own caching keeps it (public alerts, phase 6).
    assert (await client.get("/api/v1/alerts/active")).headers["Cache-Control"] == "public, max-age=60"
