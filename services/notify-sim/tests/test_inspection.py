# ┏━━ SIMULATION ━━ tests of the simulator's inspection API, health check and HTML inbox
# ┃ PRODUCTION: not shipped; see docs/api/notify-sim.md "Switching to production".
# ┗━━━━━━━━━━━━━━━━
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.store import Store
from tests.conftest import SMS_TOKEN, Clock, bearer

FCM_URL = "/v1/projects/ehimaya-sim/messages:send"


def push(client: TestClient, access_token: str, token: str, title: str = "t") -> None:
    body = {"message": {"token": token, "notification": {"title": title, "body": "b"}}}
    assert client.post(FCM_URL, json=body, headers=bearer(access_token)).status_code == 200


def sms(client: TestClient, to: str, text: str = "salam") -> None:
    body = {"to": to, "text": text, "sender": "E-HIMAYA"}
    assert client.post("/sms/send", json=body, headers=bearer(SMS_TOKEN)).status_code == 200


def items(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    response = client.get("/api/messages", params=params)
    assert response.status_code == 200, response.text
    result: list[dict[str, Any]] = response.json()["items"]
    return result


@pytest.fixture
def mixed(client: TestClient, access_token: str) -> None:
    push(client, access_token, "sim-a", "first")
    sms(client, "+21655000001")
    push(client, access_token, "sim-b")
    sms(client, "+21655000002")
    push(client, access_token, "sim-a", "second")


@pytest.mark.usefixtures("mixed")
def test_items_are_ordered_and_complete(client: TestClient) -> None:
    all_items = items(client)
    assert [i["channel"] for i in all_items] == ["push", "sms", "push", "sms", "push"]
    seqs = [i["seq"] for i in all_items]
    assert seqs == sorted(seqs) and len(set(seqs)) == 5
    expected = {"seq", "id", "channel", "received_at", "token", "to", "title", "body", "text", "data"}
    expected |= {"android_channel", "priority", "segments", "encoding"}
    assert all(set(i) == expected for i in all_items)
    assert all(i["received_at"].endswith("+00:00") for i in all_items)


@pytest.mark.usefixtures("mixed")
def test_filters(client: TestClient) -> None:
    assert [i["channel"] for i in items(client, channel="push")] == ["push"] * 3
    assert [i["to"] for i in items(client, channel="sms")] == ["+21655000001", "+21655000002"]
    assert [i["title"] for i in items(client, channel="push", token="sim-a")] == ["first", "second"]
    assert [i["to"] for i in items(client, to="+21655000002")] == ["+21655000002"]
    assert items(client, token="sim-unknown") == []


@pytest.mark.usefixtures("mixed")
def test_after_and_last_seq_for_polling(client: TestClient, access_token: str) -> None:
    first = client.get("/api/messages", params={"token": "sim-a", "limit": 1}).json()
    assert [i["title"] for i in first["items"]] == ["first"]
    assert first["last_seq"] == first["items"][0]["seq"]  # page full: continue right after it
    second = client.get("/api/messages", params={"token": "sim-a", "after": first["last_seq"]}).json()
    assert [i["title"] for i in second["items"]] == ["second"]
    newest = items(client)[-1]["seq"]
    assert second["last_seq"] == newest
    third = client.get("/api/messages", params={"token": "sim-a", "after": second["last_seq"]}).json()
    assert third == {"items": [], "last_seq": newest}
    push(client, access_token, "sim-a", "third")
    fourth = client.get("/api/messages", params={"token": "sim-a", "after": third["last_seq"]}).json()
    assert [i["title"] for i in fourth["items"]] == ["third"]


@pytest.mark.usefixtures("mixed")
def test_limit(client: TestClient) -> None:
    assert len(items(client, limit=2)) == 2
    assert client.get("/api/messages", params={"limit": 201}).status_code == 422
    assert client.get("/api/messages", params={"limit": 0}).status_code == 422
    assert client.get("/api/messages", params={"after": -1}).status_code == 422
    assert client.get("/api/messages", params={"channel": "email"}).status_code == 422


def test_default_limit_is_50(client: TestClient, access_token: str) -> None:
    for n in range(55):
        push(client, access_token, "sim-many", str(n))
    page = client.get("/api/messages").json()
    assert len(page["items"]) == 50
    assert page["last_seq"] == page["items"][-1]["seq"]


@pytest.mark.usefixtures("mixed")
def test_clear_keeps_sequence_increasing(client: TestClient) -> None:
    before = client.get("/api/messages").json()["last_seq"]
    assert client.delete("/api/messages").status_code == 204
    assert client.get("/api/messages").json() == {"items": [], "last_seq": before}
    sms(client, "+21655000003")
    assert items(client, after=before)[0]["seq"] == before + 1


def test_sequence_survives_a_restart(settings: Settings, clock: Clock) -> None:
    store = Store(clock=clock)
    old = store.add("sms", "x", to="+21655000001").seq
    clock.now += 1
    assert Store(clock=clock).add("sms", "y", to="+21655000001").seq > old


def test_ring_buffer_keeps_the_newest(settings: Settings, clock: Clock) -> None:
    app = create_app(settings.model_copy(update={"max_messages": 3}), clock=clock)
    with TestClient(app) as client:
        for n in range(5):
            sms(client, "+21655000001", f"m{n}")
        assert [i["text"] for i in items(client)] == ["m2", "m3", "m4"]


def test_health(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_inbox_is_self_contained(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "default-src 'none'" in response.headers["content-security-policy"]
    page = response.text
    assert "وضع المحاكاة · Mode simulation — not real deliveries" in page
    assert '<html lang="ar" dir="rtl">' in page
    assert "Boîte de réception" in page and "صندوق الإشعارات" in page
    assert "setInterval(poll" in page
    assert "ehimaya-sim" in page and "+21698000000" in page
    for external in ("<link", "src=", "http://", "https://", "@import", "url("):
        assert external not in page.replace("http://notify-sim.test", ""), external
