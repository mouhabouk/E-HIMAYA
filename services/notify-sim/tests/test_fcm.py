# ┏━━ SIMULATION ━━ tests of the emulated FCM HTTP v1 messages:send endpoint
# ┃ PRODUCTION: not shipped; see docs/api/notify-sim.md "Switching to production".
# ┗━━━━━━━━━━━━━━━━
import copy
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import bearer

URL = "/v1/projects/ehimaya-sim/messages:send"

# The exact shape services/api builds for an alert (FcmPush.message).
ALERT: dict[str, Any] = {
    "message": {
        "token": "sim-6f1c2e8a-0d7b-4b0e-9d55-7d6c3b1d2a10",
        "notification": {"title": "إنذار فيضان", "body": "ابتعدوا عن الأودية"},
        "data": {"type": "alert", "id": "42", "severity": "severe"},
        "android": {"priority": "high", "notification": {"channel_id": "ehimaya_alerts"}},
        "apns": {
            "headers": {"apns-priority": "10"},
            "payload": {"aps": {"sound": "alert.caf", "interruption-level": "time-sensitive"}},
        },
    }
}


def send(client: TestClient, token: str, body: Any) -> Any:
    return client.post(URL, json=body, headers=bearer(token))


def test_message_accepted_and_stored(client: TestClient, access_token: str) -> None:
    response = send(client, access_token, ALERT)
    assert response.status_code == 200
    name = response.json()["name"]
    assert name.startswith("projects/ehimaya-sim/messages/")
    [item] = client.get("/api/messages").json()["items"]
    assert item["id"] == name.rsplit("/", 1)[1]
    assert item["channel"] == "push"
    assert item["token"] == ALERT["message"]["token"]
    assert item["title"] == "إنذار فيضان"
    assert item["body"] == "ابتعدوا عن الأودية"
    assert item["data"] == {"type": "alert", "id": "42", "severity": "severe"}
    assert item["android_channel"] == "ehimaya_alerts"
    assert item["priority"] == "high"
    assert item["to"] is None and item["text"] is None and item["segments"] is None


def test_topic_message_has_no_token(client: TestClient, access_token: str) -> None:
    body = {"message": {"topic": "news", "notification": {"title": "t", "body": "b"}}}
    assert send(client, access_token, body).status_code == 200
    assert client.get("/api/messages").json()["items"][0]["token"] is None


def test_validate_only_is_not_stored(client: TestClient, access_token: str) -> None:
    response = send(client, access_token, {**ALERT, "validate_only": True})
    assert response.status_code == 200
    assert response.json()["name"] == "projects/ehimaya-sim/messages/fake_message_id"
    assert client.get("/api/messages").json()["items"] == []


@pytest.mark.parametrize("authorization", [None, "Bearer", "Bearer sim-at-unknown", "Basic abc"])
def test_requires_access_token(client: TestClient, authorization: str | None) -> None:
    headers = {"Authorization": authorization} if authorization else {}
    response = client.post(URL, json=ALERT, headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["status"] == "UNAUTHENTICATED"
    assert response.headers["www-authenticate"].startswith("Bearer")


def test_unknown_project_is_not_found(client: TestClient, access_token: str) -> None:
    response = client.post("/v1/projects/other/messages:send", json=ALERT, headers=bearer(access_token))
    assert response.status_code == 404
    assert response.json()["error"]["status"] == "NOT_FOUND"


def test_unregistered_token(client: TestClient, access_token: str) -> None:
    body = copy.deepcopy(ALERT)
    body["message"]["token"] = "sim-unregistered-1234"
    response = send(client, access_token, body)
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": 404,
            "message": "Requested entity was not found.",
            "status": "NOT_FOUND",
            "details": [{"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": "UNREGISTERED"}],
        }
    }
    assert client.get("/api/messages").json()["items"] == []


def _with(path: list[str], value: Any) -> dict[str, Any]:
    body = copy.deepcopy(ALERT)
    node = body["message"]
    for key in path[:-1]:
        node = node[key]
    if value is _DELETE:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return body


_DELETE = object()


@pytest.mark.parametrize(
    ("path", "value", "field"),
    [
        (["data", "id"], 42, "message.data[1].value"),
        (["data", "flag"], True, "message.data[3].value"),
        (["data", "nested"], {"a": "b"}, "message.data[3].value"),
        (["data", "none"], None, "message.data[3].value"),
        (["data"], ["a"], "message.data"),
        (["data", "from"], "x", "message.data"),
        (["data", "google.foo"], "x", "message.data"),
        (["notification", "title"], 5, "message.notification.title"),
        (["notification", "subtitle"], "x", "message.notification.subtitle"),
        (["android", "priority"], "urgent", "message.android.priority"),
        (["android", "notification", "channel_id"], 1, "message.android.notification.channel_id"),
        (["apns", "headers", "apns-priority"], 10, "message.apns.headers[0].value"),
        (["apns", "payload", "aps"], "x", "message.apns.payload.aps"),
        (["token"], "", "message.token"),
        (["token"], 123, "message.token"),
        (["topic"], "news", "message"),
        (["token"], _DELETE, "message"),
        (["recipient"], "x", "message.recipient"),
    ],
)
def test_invalid_argument(client: TestClient, access_token: str, path: list[str], value: Any, field: str) -> None:
    response = send(client, access_token, _with(path, value))
    assert response.status_code == 400, response.text
    error = response.json()["error"]
    assert error["code"] == 400
    assert error["status"] == "INVALID_ARGUMENT"
    violation = error["details"][0]["fieldViolations"][0]
    assert violation["field"] == field
    assert client.get("/api/messages").json()["items"] == []


def test_android_priority_is_case_insensitive(client: TestClient, access_token: str) -> None:
    assert send(client, access_token, _with(["android", "priority"], "NORMAL")).status_code == 200
    assert client.get("/api/messages").json()["items"][0]["priority"] == "normal"


@pytest.mark.parametrize("body", [{"msg": {}}, {"message": "x"}, [], "x"])
def test_malformed_body(client: TestClient, access_token: str, body: Any) -> None:
    response = send(client, access_token, body)
    assert response.status_code == 400
    assert response.json()["error"]["status"] == "INVALID_ARGUMENT"


def test_invalid_json(client: TestClient, access_token: str) -> None:
    response = client.post(
        URL, content=b"{not json", headers={**bearer(access_token), "Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["status"] == "INVALID_ARGUMENT"
