# ┏━━ SIMULATION ━━ tests of the emulated Tunisian SMS HTTP gateway
# ┃ PRODUCTION: not shipped; see docs/api/notify-sim.md "Switching to production".
# ┗━━━━━━━━━━━━━━━━
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.sms import segments
from tests.conftest import FAIL_NUMBER, SMS_TOKEN, bearer

AUTH = bearer(SMS_TOKEN)


def send(client: TestClient, body: Any, headers: dict[str, str] | None = None) -> Any:
    return client.post("/sms/send", json=body, headers=AUTH if headers is None else headers)


def sms(**overrides: Any) -> dict[str, Any]:
    return {"to": "+21655123456", "text": "Alerte inondation : évitez les oueds.", "sender": "E-HIMAYA", **overrides}


def test_accepted_and_stored(client: TestClient) -> None:
    response = send(client, sms())
    assert response.status_code == 200
    body = response.json()
    assert body["id"].startswith("sms-")
    assert body["segments"] == 1
    assert body["encoding"] == "GSM-7"
    [item] = client.get("/api/messages").json()["items"]
    assert item["channel"] == "sms"
    assert item["id"] == body["id"]
    assert item["to"] == "+21655123456"
    assert item["text"] == "Alerte inondation : évitez les oueds."
    assert item["segments"] == 1 and item["encoding"] == "GSM-7"
    assert item["token"] is None and item["title"] is None and item["data"] is None


def test_arabic_is_ucs2(client: TestClient) -> None:
    body = send(client, sms(text="تحذير: فيضان في وادي مجردة، ابتعدوا عن مجاري المياه")).json()
    assert body == {"id": body["id"], "segments": 1, "encoding": "UCS-2"}


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": SMS_TOKEN}, {"Authorization": "Basic x"}]
)
def test_requires_token(client: TestClient, headers: dict[str, str]) -> None:
    response = send(client, sms(), headers)
    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}
    assert client.get("/api/messages").json()["items"] == []


@pytest.mark.parametrize(
    "to",
    [
        "+21612345678",  # mobile numbers start with 2-9
        "+2165512345",  # too short
        "+216551234567",  # too long
        "21655123456",  # no plus sign
        "+33612345678",  # not Tunisian
        "+216 55 123 456",
        "+216٥٥١٢٣٤٥٦",  # Arabic-Indic digits
        "+21655123456\n",
        None,
        55123456,
    ],
)
def test_invalid_number(client: TestClient, to: Any) -> None:
    response = send(client, sms(to=to))
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_number"}


@pytest.mark.parametrize("to", ["+21620000000", "+21699999999", "+21640123456"])
def test_valid_numbers(client: TestClient, to: str) -> None:
    assert send(client, sms(to=to)).status_code == 200


@pytest.mark.parametrize("text", ["", "   ", "x" * 1001, None, 12])
def test_invalid_text(client: TestClient, text: Any) -> None:
    response = send(client, sms(text=text))
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_text"}


def test_text_of_1000_characters_is_accepted(client: TestClient) -> None:
    response = send(client, sms(text="a" * 1000))
    assert response.status_code == 200
    assert response.json()["segments"] == 7  # ceil(1000 / 153)


@pytest.mark.parametrize("sender", ["", "TWELVE-CHARS", None])
def test_invalid_sender(client: TestClient, sender: Any) -> None:
    response = send(client, sms(sender=sender))
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_sender"}


@pytest.mark.parametrize("body", [[], "x", 1])
def test_invalid_request(client: TestClient, body: Any) -> None:
    response = send(client, body)
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_request"}


def test_invalid_json(client: TestClient) -> None:
    response = client.post("/sms/send", content=b"{", headers={**AUTH, "Content-Type": "application/json"})
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_request"}


@pytest.mark.parametrize("to", [FAIL_NUMBER, "+21622000000"])
def test_failure_numbers(client: TestClient, to: str) -> None:
    response = send(client, sms(to=to))
    assert response.status_code == 503
    assert response.json() == {"error": "operator_unavailable"}
    assert client.get("/api/messages").json()["items"] == []


@pytest.mark.parametrize(
    ("text", "count", "encoding"),
    [
        ("a", 1, "GSM-7"),
        ("a" * 160, 1, "GSM-7"),
        ("a" * 161, 2, "GSM-7"),
        ("a" * 306, 2, "GSM-7"),
        ("a" * 307, 3, "GSM-7"),
        ("€" * 80, 1, "GSM-7"),  # extension characters take two septets
        ("€" * 81, 2, "GSM-7"),
        ("[]{}~^|\\" * 10, 1, "GSM-7"),
        ("Çà été ÄÖÑÜ ß £¥ @", 1, "GSM-7"),
        ("ب" * 70, 1, "UCS-2"),
        ("ب" * 71, 2, "UCS-2"),
        ("ب" * 134, 2, "UCS-2"),
        ("ب" * 135, 3, "UCS-2"),
        ("a" * 69 + "ê", 1, "UCS-2"),  # ê is not in the GSM-7 alphabet
        ("😀" * 35, 1, "UCS-2"),  # surrogate pairs count twice
        ("😀" * 36, 2, "UCS-2"),
    ],
)
def test_segments(text: str, count: int, encoding: str) -> None:
    result = segments(text)
    assert (result.count, result.encoding) == (count, encoding)
