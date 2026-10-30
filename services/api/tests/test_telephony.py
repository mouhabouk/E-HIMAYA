"""Telephony and SMS reports (phase 7, docs/api/phase-7-contract.md §4 and §5): ARI events → calls, staff endpoints
(credentials, list, dial, link, scenario 2 transfer, crisis rooms), recordings, the signed SMS webhook with its
deduplication rules, live feed masking, citizen rights and retention. Asterisk is replaced by ``FakeAri``."""

import hashlib
import hmac
import io
import json
import os
import secrets
import time
import uuid
import wave
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import jwt
import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.modules.identity.models import Account, Profile, phone_index
from app.modules.notify.providers import PhoneSms
from app.modules.ops.models import Incident
from app.modules.privacy import retention
from app.modules.reports import live
from app.modules.reports.models import Media
from app.modules.telephony import ari, sms, worker
from app.modules.telephony import retention as telephony_retention
from app.modules.telephony.ari import AriUnavailable
from app.modules.telephony.domain import caller_index, endpoint_for, mask_number, normalize_tn_number
from app.modules.telephony.models import Call
from tests.conftest import (
    FakeChannel,
    FakeStore,
    TokenFactory,
    accept_charter,
    bearer,
    device_headers,
    outbox_events,
    report_body,
)

Staff = Callable[..., dict[str, str]]
SMS_SECRET = "test-sms-inbound-secret-000001"
SIM = {"X-Sim-Token": "test-telephony-sim-token-0001"}
SFAX_SMS = "34.74060,10.76030"


class FakeAri:
    """Records what the API asked Asterisk to do; ``fail`` makes every request fail like an unreachable Asterisk."""

    def __init__(self) -> None:
        self.fail = False
        self.pushed: list[tuple[str, str, str]] = []
        self.removed: list[str] = []
        self.controls: list[str] = []
        self.originated: list[tuple[str, str, str]] = []
        self.invites: list[tuple[str, str]] = []
        self.variables: dict[str, dict[str, str]] = {}
        self.live: set[str] = set()

    def _check(self) -> None:
        if self.fail:
            raise AriUnavailable("ConnectError")

    async def push_operator(self, endpoint: str, password: str, display_name: str) -> None:
        self._check()
        self.pushed.append((endpoint, password, display_name))

    async def remove_operator(self, endpoint: str) -> None:
        self._check()
        self.removed.append(endpoint)

    async def control(self, action: str) -> None:
        self._check()
        self.controls.append(action)

    async def originate_operator_call(self, endpoint: str, extension: str, channel_id: str, display: str) -> None:
        self._check()
        self.originated.append((endpoint, extension, channel_id))

    async def invite(self, extension: str, room: str) -> None:
        self._check()
        self.invites.append((extension, room))

    async def hangup(self, channel_id: str) -> None:
        self._check()

    async def set_variable(self, channel_id: str, name: str, value: str) -> None:
        self._check()
        self.variables.setdefault(channel_id, {})[name] = value

    async def channel_ids(self) -> set[str]:
        self._check()
        return set(self.live)


@pytest.fixture(autouse=True)
def fake_ari() -> Iterator[FakeAri]:
    fake = FakeAri()
    ari.set_ari(fake)
    yield fake
    ari.set_ari(None)


# ---------------------------------------------------------------- helpers


def mobile() -> str:
    return f"+2162{secrets.randbelow(10**7):07d}"


def channel() -> str:
    return f"{int(time.time())}.{secrets.randbelow(10**9)}"


async def event(body: dict[str, Any]) -> None:
    await worker.process(get_system_sessionmaker(), json.dumps(body))


async def call_event(channel_id: str, state: str, **fields: str) -> None:
    await event(
        {
            "type": "ChannelUserevent",
            "eventname": "EhimayaCall",
            "timestamp": datetime.now(UTC).isoformat(),
            "channel": {"id": channel_id, "caller": {"number": fields.pop("number", "")}},
            "userevent": {"state": state, "call": channel_id, **fields},
        }
    )


async def ringing(number: str | None = None, source: str = "trunk") -> str:
    channel_id = channel()
    await call_event(channel_id, "ringing", number=number or mobile(), source=source)
    return channel_id


async def destroyed(channel_id: str) -> None:
    await event({"type": "ChannelDestroyed", "timestamp": datetime.now(UTC).isoformat(), "channel": {"id": channel_id}})


async def call_row(session: AsyncSession, channel_id: str) -> Call:
    await session.rollback()
    found = await session.scalar(select(Call).where(Call.channel_id == channel_id))
    assert found is not None
    return found


def subject_of(headers: dict[str, str]) -> str:
    token = headers["Authorization"].removeprefix("Bearer ")
    return str(jwt.decode(token, options={"verify_signature": False})["sub"])


async def credentials(client: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    r = await client.post("/api/v1/staff/telephony/credentials", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def answered_call(client: httpx.AsyncClient, operator: dict[str, str], session: AsyncSession) -> Call:
    """An inbound call taken by ``operator`` (their endpoint answered it from the queue)."""
    creds = await credentials(client, operator)
    channel_id = await ringing()
    await call_event(channel_id, "answered", endpoint=creds["username"])
    return await call_row(session, channel_id)


def signed(body: dict[str, Any], *, secret: str = SMS_SECRET, at: int | None = None) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode()
    ts = str(at if at is not None else int(time.time()))
    mac = hmac.new(secret.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return raw, {"X-Timestamp": ts, "X-Signature": f"sha256={mac}", "Content-Type": "application/json"}


async def send_sms(client: httpx.AsyncClient, sender: str, text_: str, message_id: str | None = None) -> httpx.Response:
    raw, headers = signed({"message_id": message_id or uuid.uuid4().hex, "from": sender, "text": text_})
    return await client.post("/internal/sms/inbound", content=raw, headers=headers)


def prefix() -> tuple[str, str]:
    client_uuid = str(uuid.uuid4())
    return client_uuid, client_uuid[:8]


async def verified_citizen(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, phone: str
) -> tuple[dict[str, str], uuid.UUID]:
    headers = bearer(make_token(roles=["citizen"]))
    await accept_charter(client, headers)
    await session.rollback()
    account = await session.scalar(select(Account).where(Account.keycloak_sub == subject_of(headers)))
    assert account is not None
    session.add(
        Profile(
            user_id=account.user_id, phone=phone, phone_hash=phone_index(phone), phone_verified_at=datetime.now(UTC)
        )
    )
    await session.commit()
    return headers, account.user_id


async def new_incident(session: AsyncSession, gouvernorat: int = 61) -> uuid.UUID:
    incident = Incident(category="fire", gouvernorat_code=gouvernorat)
    session.add(incident)
    await session.commit()
    return incident.id


def wav_bytes(seconds: float = 1.0) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * int(8000 * seconds))
    return buffer.getvalue()


# ---------------------------------------------------------------- numbers and SMS format


def test_tunisian_numbers() -> None:
    assert normalize_tn_number("+216 20 123 456") == "+21620123456"
    assert normalize_tn_number("0021671123456") == "+21671123456"
    assert normalize_tn_number("21650123456") == "+21650123456"
    assert normalize_tn_number("98.123.456") == "+21698123456"
    for bad in ("198", "+33612345678", "12345678", "+2162012345", "2162012345678", ""):
        assert normalize_tn_number(bad) is None, bad
    assert mask_number("+21620123456") == "••••••••••56"


def test_sms_body_parsing() -> None:
    parsed = sms.parse("EH1 fire 36.80650,10.18150 12m 3f2a9c1d")
    assert parsed is not None
    assert (parsed.category.value, parsed.lat, parsed.lon, parsed.accuracy_m, parsed.prefix) == (
        "fire",
        36.8065,
        10.1815,
        12.0,
        "3f2a9c1d",
    )
    assert sms.parse("eh1 FLOOD 34.74,10.76 0m ABCDEF01") is not None
    assert sms.parse("EH1 flood 34.74,10.76 0m abcdef01").accuracy_m is None  # type: ignore[union-attr]
    assert sms.parse("EH1 fire 34.74,10.76 99999m abcdef01").accuracy_m == 99999  # type: ignore[union-attr]
    for bad in (
        "EH1 fire 48.85,2.35 10m abcdef01",  # outside Tunisia
        "EH1 unicorn 34.74,10.76 10m abcdef01",  # unknown category
        "EH1 fire 34.74,10.76 10m abcdef0",  # prefix too short
        "EH1 fire 34.74,10.76 100000m abcdef01",  # accuracy capped at 99999
        "EH2 fire 34.74,10.76 10m abcdef01",
        "hello",
    ):
        assert sms.parse(bad) is None, bad


# ---------------------------------------------------------------- ARI events → calls


async def test_inbound_call_life_cycle(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession, fake_ari: FakeAri
) -> None:
    operator = staff(gouvernorat=61)
    number = mobile()
    channel_id = await ringing("00" + number[1:])
    call = await call_row(session, channel_id)
    assert call.status == "ringing" and call.direction == "inbound" and call.source == "trunk"
    # calls.id handed to Asterisk for the X-EHimaya-Call-Id header of the INVITEs to operators.
    assert fake_ari.variables[channel_id] == {"__EH_CALL_UUID": str(call.id)}
    assert call.caller_number == number and call.caller_hash == caller_index(number)
    assert call.gouvernorat_code is None and call.recording_state == "pending"
    # The number is encrypted at rest.
    raw = await session.scalar(text("SELECT caller_number_enc FROM telephony.call WHERE id = :id"), {"id": call.id})
    assert number.encode() not in bytes(raw)
    ringing_events = [e for e in await outbox_events(session, "call.ringing") if e["call_id"] == str(call.id)]
    assert len(ringing_events) == 1 and ringing_events[0]["call"]["caller_number"] == number

    # A replayed ringing event (reconnection) does not create a second call.
    await call_event(channel_id, "ringing", number=number, source="trunk")
    assert (
        await session.scalar(text("SELECT count(*) FROM telephony.call WHERE channel_id = :c"), {"c": channel_id})
    ) == 1

    # Not located yet: every operator sees it (shared queue).
    elsewhere = staff(gouvernorat=11)
    listed = (await client.get("/api/v1/staff/calls?status=active", headers=elsewhere)).json()["items"]
    assert str(call.id) in {c["id"] for c in listed}

    creds = await credentials(client, operator)
    await call_event(channel_id, "answered", endpoint=creds["username"])
    call = await call_row(session, channel_id)
    assert call.status == "answered" and call.answered_at is not None
    assert call.operator_user_id == subject_of(operator) and call.gouvernorat_code == 61
    assert (await client.get(f"/api/v1/staff/calls/{call.id}", headers=elsewhere)).status_code == 404

    await destroyed(channel_id)
    call = await call_row(session, channel_id)
    assert call.status == "ended" and call.end_reason == "completed" and call.ended_at is not None
    detail = (await client.get(f"/api/v1/staff/calls/{call.id}", headers=operator)).json()
    assert detail["caller_number"] == number and detail["caller_masked"] is False
    assert detail["duration_s"] is not None and detail["transfer_198_available"] is False
    assert detail["simulated"] is False
    audit = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'call.detail' AND target = :t"), {"t": f"call:{call.id}"}
    )
    assert audit == 1


async def test_unanswered_call_is_missed(session: AsyncSession) -> None:
    channel_id = await ringing()
    await destroyed(channel_id)
    call = await call_row(session, channel_id)
    assert call.status == "missed" and call.end_reason == "abandoned"
    # Events of unknown channels and junk are ignored.
    await destroyed("unknown.1")
    await worker.process(get_system_sessionmaker(), "not json")
    await call_event("../etc", "answered")


async def test_reconcile_ends_calls_whose_channel_vanished(fake_ari: FakeAri, session: AsyncSession) -> None:
    alive, gone = await ringing(), await ringing()
    fake_ari.live = {alive}
    await worker._reconcile(get_system_sessionmaker())
    assert (await call_row(session, gone)).status == "missed"
    assert (await call_row(session, alive)).status == "ringing"
    await destroyed(alive)


async def test_numbers_masked_for_readers_without_call_access(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    number = mobile()
    channel_id = await ringing(number)
    call = await call_row(session, channel_id)
    committee = staff(roles=["local_committee"], gouvernorat=61)
    item = next(
        c
        for c in (await client.get("/api/v1/staff/calls", headers=committee)).json()["items"]
        if c["id"] == str(call.id)
    )
    assert item["caller_number"] == mask_number(number) and item["caller_masked"] is True
    # Call actions need call access.
    assert (await client.post("/api/v1/staff/telephony/credentials", headers=committee)).status_code == 403
    assert (await client.get(f"/api/v1/staff/calls/{call.id}/recording", headers=committee)).status_code == 403
    await destroyed(channel_id)


def test_live_feed_masks_and_scopes_call_events() -> None:
    number = "+21620123456"
    payload = {"call_id": "c1", "gouvernorat_code": 61, "call": {"caller_number": number, "operator_user_id": "u1"}}
    route = live._route("call.answered", payload)
    assert route is not None and route[0] == "reports"
    visible = route[1]

    def reader(code: int | None, subject: str = "x") -> Any:
        return SimpleNamespace(principal=SimpleNamespace(subject=subject), can_see=lambda c: c == code)

    assert visible(reader(61)) and not visible(reader(11)) and visible(reader(11, subject="u1"))
    shared = live._route("call.ringing", {**payload, "gouvernorat_code": None})
    assert shared is not None and shared[1](reader(11))
    masked = live._masked_call({"type": "call.answered", **payload})
    assert masked["call"]["caller_number"] == mask_number(number) and masked["call"]["caller_masked"] is True
    assert payload["call"]["caller_number"] == number  # the original message is untouched
    assert live._route("call.recording", {"call_id": "c1", "gouvernorat_code": 61}) is not None


# ---------------------------------------------------------------- credentials and outbound calls


async def test_credentials(client: httpx.AsyncClient, staff: Staff, fake_ari: FakeAri, session: AsyncSession) -> None:
    operator = staff(gouvernorat=61)
    r = await client.post("/api/v1/staff/telephony/credentials", headers=operator)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    endpoint = endpoint_for(subject_of(operator))
    assert body["username"] == endpoint and body["sip_uri"] == f"sip:{endpoint}@ehimaya.local"
    assert body["ws_url"] == "ws://localhost:8088/ws" and len(body["password"]) >= 32
    assert body["transfer_198_enabled"] is False and body["simulated"] is True
    expires = datetime.fromisoformat(body["expires_at"])
    assert timedelta(hours=3, minutes=59) < expires - datetime.now(UTC) <= timedelta(hours=4)
    assert fake_ari.pushed[-1][:2] == (endpoint, body["password"])
    assert fake_ari.controls[-1] == f"member-add-{endpoint}"
    # A new request rotates the password.
    again = await credentials(client, operator)
    assert again["username"] == endpoint and again["password"] != body["password"]
    # Only a hash of nothing: the password is never stored.
    stored = await session.scalar(
        text("SELECT row_to_json(e)::text FROM telephony.operator_endpoint e WHERE endpoint = :e"), {"e": endpoint}
    )
    assert again["password"] not in stored

    # Expired credentials leave the queue and Asterisk.
    removed = await worker.retire_expired(get_system_sessionmaker(), datetime.now(UTC) + timedelta(days=1))
    assert removed >= 1 and endpoint in fake_ari.removed and f"member-del-{endpoint}" in fake_ari.controls

    fake_ari.fail = True
    r = await client.post("/api/v1/staff/telephony/credentials", headers=operator)
    assert r.status_code == 503 and r.json()["detail"] == "telephony_unavailable"
    ari.set_ari(None)
    assert (await client.post("/api/v1/staff/telephony/credentials", headers=operator)).status_code == 503


async def test_dial(client: httpx.AsyncClient, staff: Staff, fake_ari: FakeAri, session: AsyncSession) -> None:
    operator = staff(gouvernorat=61)
    r = await client.post("/api/v1/staff/calls/dial", json={"number": "20 123 456"}, headers=operator)
    assert r.status_code == 409 and r.json()["detail"] == "softphone_not_registered"
    creds = await credentials(client, operator)

    for bad in ("+33612345678", "198", "12345678"):
        r = await client.post("/api/v1/staff/calls/dial", json={"number": bad}, headers=operator)
        assert r.status_code == 422 and r.json()["detail"] == "invalid_number", bad
    r = await client.post(
        "/api/v1/staff/calls/dial", json={"number": "+21620123456", "report_id": str(uuid.uuid4())}, headers=operator
    )
    assert r.status_code == 422

    r = await client.post("/api/v1/staff/calls/dial", json={"number": "20 123 456"}, headers=operator)
    assert r.status_code == 201, r.text
    call = r.json()
    assert call["direction"] == "outbound" and call["status"] == "ringing" and call["caller_number"] == "+21620123456"
    assert call["operator_user_id"] == subject_of(operator) and call["gouvernorat_code"] == 61
    assert call["simulated"] is True  # no trunk: the call-sim service answers in development
    assert fake_ari.originated[-1] == (creds["username"], "21620123456", call["id"])
    channel_id = call["id"]
    await call_event(channel_id, "dialing")
    await call_event(channel_id, "remote_answered")
    assert (await call_row(session, channel_id)).status == "answered"
    await destroyed(channel_id)
    ended = await call_row(session, channel_id)
    assert ended.status == "ended" and ended.end_reason == "completed"

    # Calling back a reporter: the number comes from the report (here the SMS that created it).
    sender = mobile()
    _, pre = prefix()
    sms_reply = await send_sms(client, sender, f"EH1 fire {SFAX_SMS} 8m {pre}")
    code = sms_reply.json()["tracking_code"]
    report_id = await session.scalar(text("SELECT id FROM reports.report WHERE tracking_code = :c"), {"c": code})
    r = await client.post("/api/v1/staff/calls/dial", json={"report_id": str(report_id)}, headers=operator)
    assert r.status_code == 201, r.text
    assert r.json()["caller_number"] == sender and r.json()["report_id"] == str(report_id)
    await destroyed(r.json()["id"])

    # Asterisk down: the call is recorded as failed and the operator gets 503.
    fake_ari.fail = True
    r = await client.post("/api/v1/staff/calls/dial", json={"number": "71123456"}, headers=operator)
    assert r.status_code == 503
    failed = await session.scalar(
        select(Call).where(Call.operator_user_id == subject_of(operator), Call.status == "failed")
    )
    assert failed is not None and failed.end_reason == "failed"


async def test_dial_refused_in_production_without_trunk(
    client: httpx.AsyncClient, staff: Staff, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator = staff(gouvernorat=61)
    await credentials(client, operator)
    monkeypatch.setattr(get_settings(), "app_env", "production")
    r = await client.post("/api/v1/staff/calls/dial", json={"number": "20123456"}, headers=operator)
    assert r.status_code == 409 and r.json()["detail"] == "outbound_unavailable"


# ---------------------------------------------------------------- link and scenario 2


async def test_link_call_to_report(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, session: AsyncSession
) -> None:
    operator = staff(gouvernorat=61)
    call = await answered_call(client, operator, session)
    citizen = bearer(make_token(roles=["citizen"]))
    await accept_charter(client, citizen)
    report = (await client.post("/api/v1/reports", json=report_body(), headers=citizen)).json()

    r = await client.post(f"/api/v1/staff/calls/{call.id}/link", json={}, headers=operator)
    assert r.status_code == 422
    r = await client.post(
        f"/api/v1/staff/calls/{call.id}/link", json={"tracking_code": "EH-2026-99-999999"}, headers=operator
    )
    assert r.status_code in (404, 422)
    r = await client.post(
        f"/api/v1/staff/calls/{call.id}/link", json={"tracking_code": report["tracking_code"]}, headers=operator
    )
    assert r.status_code == 200, r.text
    assert r.json()["report_id"] == report["id"] and r.json()["tracking_code"] == report["tracking_code"]

    incident_id = await new_incident(session)
    r = await client.post(
        f"/api/v1/staff/calls/{call.id}/link", json={"incident_id": str(incident_id)}, headers=operator
    )
    assert r.status_code == 200 and r.json()["incident_id"] == str(incident_id)
    timeline = await session.scalar(
        text("SELECT count(*) FROM ops.timeline_event WHERE incident_id = :i AND kind = 'call_linked'"),
        {"i": incident_id},
    )
    assert timeline == 1
    await destroyed(call.channel_id)


async def test_transfer_198(
    client: httpx.AsyncClient, staff: Staff, fake_ari: FakeAri, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator = staff(gouvernorat=61)
    call = await answered_call(client, operator, session)
    r = await client.post(f"/api/v1/staff/calls/{call.id}/transfer-198", headers=operator)
    assert r.status_code == 409 and r.json()["detail"] == "transfer_disabled"

    monkeypatch.setattr(get_settings(), "telephony_transfer_198_enabled", True)
    monkeypatch.setattr(get_settings(), "telephony_trunk_enabled", True)
    detail = (await client.get(f"/api/v1/staff/calls/{call.id}", headers=operator)).json()
    assert detail["transfer_198_available"] is True
    r = await client.post(f"/api/v1/staff/calls/{call.id}/transfer-198", headers=operator)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "transferred" and r.json()["transferred_to"] == "198"
    assert fake_ari.controls[-1] == f"transfer-{call.channel_id}"
    # Only an answered inbound call can be transferred.
    r = await client.post(f"/api/v1/staff/calls/{call.id}/transfer-198", headers=operator)
    assert r.status_code == 409 and r.json()["detail"] == "call_not_answered"

    # The trunk refused: the caller is back in the queue.
    await call_event(call.channel_id, "transferring", to="198")
    await call_event(call.channel_id, "transfer_failed", status="CONGESTION")
    assert (await call_row(session, call.channel_id)).status == "ringing"
    await call_event(call.channel_id, "transferring", to="198")
    await destroyed(call.channel_id)
    ended = await call_row(session, call.channel_id)
    assert ended.end_reason == "transferred" and ended.transferred_to == "198"


# ---------------------------------------------------------------- crisis rooms


async def test_conference(client: httpx.AsyncClient, staff: Staff, fake_ari: FakeAri, session: AsyncSession) -> None:
    operator = staff(gouvernorat=61)
    incident_id = await new_incident(session)
    r = await client.post(f"/api/v1/staff/incidents/{incident_id}/conference", headers=operator)
    assert r.status_code == 201, r.text
    room = r.json()
    assert len(room["room"]) == 8 and room["room"].isdigit() and room["active"] is True
    assert room["join_uri"] == f"sip:conf-{room['room']}@ehimaya.local"
    again = await client.post(f"/api/v1/staff/incidents/{incident_id}/conference", headers=operator)
    assert again.status_code == 200 and again.json()["id"] == room["id"]
    assert (
        await client.post(f"/api/v1/staff/incidents/{incident_id}/conference", headers=staff(gouvernorat=11))
    ).status_code == 404

    r = await client.post(
        f"/api/v1/staff/conferences/{room['id']}/invite", json={"number": "+21698123456"}, headers=operator
    )
    assert r.status_code == 202, r.text
    assert r.json()["number_masked"] == mask_number("+21698123456")
    assert fake_ari.invites[-1] == ("21698123456", room["room"])
    r = await client.post(
        f"/api/v1/staff/conferences/{room['id']}/invite", json={"number": "+33612345678"}, headers=operator
    )
    assert r.status_code == 422

    r = await client.post(f"/api/v1/staff/conferences/{room['id']}/end", headers=operator)
    assert r.status_code == 200 and r.json()["active"] is False
    assert fake_ari.controls[-1] == f"confkick-{room['room']}"
    r = await client.post(
        f"/api/v1/staff/conferences/{room['id']}/invite", json={"number": "+21698123456"}, headers=operator
    )
    assert r.status_code == 409 and r.json()["detail"] == "conference_ended"
    listed = (
        await client.get(f"/api/v1/staff/incidents/{incident_id}/conferences", headers=staff(roles=["local_committee"]))
    ).json()
    assert [c["id"] for c in listed["items"]] == [room["id"]]
    kinds = list(
        await session.scalars(
            text("SELECT kind FROM ops.timeline_event WHERE incident_id = :i ORDER BY id"), {"i": incident_id}
        )
    )
    assert kinds == ["conference_opened", "conference_ended"]
    # A new room once the previous one ended; the dashboard's forms: GET …/conference (list), DELETE …/{room}.
    r = await client.post(f"/api/v1/staff/incidents/{incident_id}/conference", headers=operator)
    assert r.status_code == 201 and r.json()["id"] != room["id"]
    second = r.json()
    listed = (await client.get(f"/api/v1/staff/incidents/{incident_id}/conference", headers=operator)).json()
    assert [c["id"] for c in listed["items"]] == [second["id"], room["id"]]
    r = await client.delete(f"/api/v1/staff/incidents/{incident_id}/conference/{second['room']}", headers=operator)
    assert r.status_code == 200 and r.json()["active"] is False
    assert fake_ari.controls[-1] == f"confkick-{second['room']}"
    r = await client.delete(f"/api/v1/staff/incidents/{incident_id}/conference/00000000", headers=operator)
    assert r.status_code == 404


# ---------------------------------------------------------------- recordings


async def test_recording_ingestion(
    client: httpx.AsyncClient,
    staff: Staff,
    session: AsyncSession,
    fake_store: FakeStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "telephony_recordings_dir", tmp_path)
    operator = staff(gouvernorat=61)
    call = await answered_call(client, operator, session)
    data = wav_bytes(2.0)
    file = tmp_path / f"{call.channel_id}.wav"
    file.write_bytes(data)
    os.utime(file, (time.time() - 60, time.time() - 60))
    await destroyed(call.channel_id)
    await session.execute(
        text("UPDATE telephony.call SET recording_next_at = now() - interval '1 second' WHERE id = :id"),
        {"id": call.id},
    )
    await session.commit()
    for _ in range(100):
        if (await call_row(session, call.channel_id)).recording_state != "pending":
            break
        assert await worker.ingest_one(get_system_sessionmaker(), fake_store)
    ingested = await call_row(session, call.channel_id)
    assert ingested.recording_state == "done" and ingested.recording_media_id is not None
    key = f"calls/{call.id}.wav"
    assert fake_store.objects[key] == data and not file.exists()
    media = await session.get(Media, ingested.recording_media_id)
    assert media is not None and media.kind == "call_recording" and media.report_id is None
    assert media.sha256 == hashlib.sha256(data).hexdigest() and media.duration_s == 2.0
    events = [e for e in await outbox_events(session, "call.recording") if e["call_id"] == str(call.id)]
    assert events and events[0]["sha256"] == media.sha256

    r = await client.get(f"/api/v1/staff/calls/{call.id}/recording", headers=operator)
    assert r.status_code == 302 and r.headers["location"].startswith(f"http://s3.test/{key}")
    detail = (await client.get(f"/api/v1/staff/calls/{call.id}", headers=operator)).json()
    assert detail["recording"]["sha256"] == media.sha256 and detail["recording"]["bytes"] == len(data)


async def test_orphan_recording_becomes_untracked_call(
    session: AsyncSession, fake_store: FakeStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "telephony_recordings_dir", tmp_path)
    channel_id = channel()
    old = time.time() - 3600
    for name, data in ((f"{channel_id}.wav", wav_bytes(0.5)), ("..evil.wav", b"x")):
        (tmp_path / name).write_bytes(data)
        os.utime(tmp_path / name, (old, old))
    assert await worker.queue_orphans(get_system_sessionmaker()) == 1
    call = await call_row(session, channel_id)
    assert call.end_reason == "untracked" and call.source == "unknown" and call.recording_state == "pending"
    assert worker.recording_file("../x") is None


def test_wav_duration_tolerates_unfinished_headers() -> None:
    data = bytearray(wav_bytes(1.0))
    assert worker.wav_duration(bytes(data)) == 1.0
    data[40:44] = b"\x00\x00\x00\x00"  # data size never written (crash)
    assert worker.wav_duration(bytes(data)) == 1.0
    assert worker.wav_duration(b"not a wav") is None


# ---------------------------------------------------------------- SMS webhook


async def test_sms_signature(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"message_id": "m1", "from": mobile(), "text": "EH1 fire 34.74,10.76 8m abcdef01"}
    raw, headers = signed(body, secret="wrong-secret-wrong-secret-0001")
    assert (await client.post("/internal/sms/inbound", content=raw, headers=headers)).status_code == 401
    raw, headers = signed(body, at=int(time.time()) - 600)
    assert (await client.post("/internal/sms/inbound", content=raw, headers=headers)).status_code == 401
    raw, headers = signed(body)
    tampered = raw.replace(b"abcdef01", b"abcdef02")
    assert (await client.post("/internal/sms/inbound", content=tampered, headers=headers)).status_code == 401
    assert (await client.post("/internal/sms/inbound", content=raw)).status_code == 401
    raw, headers = signed({"text": "x"})
    assert (await client.post("/internal/sms/inbound", content=raw, headers=headers)).status_code == 422
    monkeypatch.setattr(get_settings(), "sms_inbound_secret", None)
    raw, headers = signed(body)
    assert (await client.post("/internal/sms/inbound", content=raw, headers=headers)).status_code == 404


async def test_sms_creates_a_report(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession, channels: Any
) -> None:
    sender = mobile()
    _, pre = prefix()
    message_id = uuid.uuid4().hex
    r = await send_sms(client, sender, f"EH1 fire {SFAX_SMS} 12m {pre}", message_id)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "created"
    code = r.json()["tracking_code"]
    report = (
        await session.execute(
            text(
                "SELECT id, source, category, location_accuracy_m, gouvernorat_code, client_uuid, user_id "
                "FROM reports.report WHERE tracking_code = :c"
            ),
            {"c": code},
        )
    ).one()
    assert (report.source, report.category, report.location_accuracy_m, report.gouvernorat_code) == (
        "sms",
        "fire",
        12,
        61,
    )
    assert report.client_uuid is None
    actor = await session.scalar(
        text("SELECT actor FROM reports.status_history WHERE report_id = :r"), {"r": report.id}
    )
    assert actor == "sms"
    # The sender gets the tracking code back by SMS.
    assert isinstance(channels.sms, FakeChannel)
    assert channels.sms.sent[-1][0] == sender and code in channels.sms.sent[-1][1]
    # No message text is kept; the sender number is encrypted.
    row = (
        await session.execute(text("SELECT * FROM telephony.sms_inbound WHERE report_id = :r"), {"r": report.id})
    ).one()
    assert row.outcome == "created" and row.client_prefix == pre and sender.encode() not in bytes(row.sender_number_enc)
    # Staff see it like any report.
    seen = await client.get(f"/api/v1/staff/reports/{report.id}", headers=staff(gouvernorat=61))
    assert seen.status_code == 200 and seen.json()["tracking_code"] == code

    # Gateway retry (same message id) and the same SMS sent again: the same report, no second acknowledgement.
    sent = len(channels.sms.sent)
    retry = await send_sms(client, sender, f"EH1 fire {SFAX_SMS} 12m {pre}", message_id)
    assert retry.json() == {"status": "duplicate", "tracking_code": code, "reason": None}
    again = await send_sms(client, sender, f"EH1 fire {SFAX_SMS} 12m {pre}")
    assert again.json()["status"] == "duplicate" and again.json()["tracking_code"] == code
    assert len(channels.sms.sent) == sent

    bad = await send_sms(client, sender, "hello")
    assert bad.json() == {"status": "ignored", "tracking_code": None, "reason": "unparseable"}


# ┏━━ DEMONSTRATION ━━ an Android phone as the SMS gateway (docs/sms-phone-gateway.md).
PHONE_KEY = "phone-signing-key"


def phone_signed(body: dict[str, Any], *, key: str = PHONE_KEY, at: int | None = None) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode()
    ts = str(at if at is not None else int(time.time()))
    mac = hmac.new(key.encode(), raw + ts.encode(), hashlib.sha256).hexdigest()
    return raw, {"X-Timestamp": ts, "X-Signature": mac, "Content-Type": "application/json"}


async def test_sms_through_a_phone(client: httpx.AsyncClient, channels: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    hook = {
        "deviceId": "d1",
        "event": "sms:received",
        "id": "e1",
        "webhookId": "w1",
        "payload": {"messageId": uuid.uuid4().hex, "message": "", "sender": mobile(), "recipient": None},
    }
    raw, headers = phone_signed(hook)
    assert (await client.post("/internal/sms/phone", content=raw, headers=headers)).status_code == 404
    monkeypatch.setattr(get_settings(), "sms_phone_signing_key", SecretStr(PHONE_KEY))
    _, pre = prefix()
    hook["payload"]["message"] = f"EH1 fire {SFAX_SMS} 12m {pre}"  # type: ignore[index]
    raw, headers = phone_signed(hook, key="another-key")
    assert (await client.post("/internal/sms/phone", content=raw, headers=headers)).status_code == 401
    raw, headers = phone_signed(hook, at=int(time.time()) - 600)
    assert (await client.post("/internal/sms/phone", content=raw, headers=headers)).status_code == 401
    raw, headers = phone_signed(hook)
    r = await client.post("/internal/sms/phone", content=raw, headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "created", r.text
    assert channels.sms.sent[-1][1].find(r.json()["tracking_code"]) >= 0
    # The phone's own events (sent, delivered) are answered, never retried.
    raw, headers = phone_signed({"event": "sms:delivered", "payload": {"messageId": "x", "phoneNumber": "+1"}})
    assert (await client.post("/internal/sms/phone", content=raw, headers=headers)).json()["reason"] == (
        "not_a_received_sms"
    )


async def test_phone_sends_the_replies() -> None:
    sent: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(202, json={"id": "m1"})

    phone = PhoneSms(
        "http://192.168.1.20:8080/", "sms", "secret", client=httpx.AsyncClient(transport=httpx.MockTransport(answer))
    )
    assert (await phone.send("+21698111222", "EH-26-10-0000001")).ok
    assert str(sent[0].url) == "http://192.168.1.20:8080/message"
    assert json.loads(sent[0].content) == {
        "textMessage": {"text": "EH-26-10-0000001"},
        "phoneNumbers": ["+21698111222"],
    }
    assert sent[0].headers["authorization"].startswith("Basic ")


async def test_sms_after_app_report_is_a_duplicate(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    device = device_headers()
    await accept_charter(client, device)
    client_uuid, pre = prefix()
    app_report = (
        await client.post("/api/v1/reports", json=report_body(client_uuid=client_uuid), headers=device)
    ).json()

    # Same prefix, other category: not the same report (an 8-hex prefix can collide).
    other = await send_sms(client, mobile(), f"EH1 flood {SFAX_SMS} 8m {pre}")
    assert other.json()["status"] == "created" and other.json()["tracking_code"] != app_report["tracking_code"]
    # Same prefix and category but 60 km away, unknown sender: not the same report either.
    far = await send_sms(client, mobile(), f"EH1 fire 35.25000,10.76030 8m {pre}")
    assert far.json()["status"] == "created"
    # Same prefix, category, nearby: the app report.
    same = await send_sms(client, mobile(), f"EH1 fire {SFAX_SMS} 8m {pre}")
    assert same.json() == {"status": "duplicate", "tracking_code": app_report["tracking_code"], "reason": "app_report"}


async def test_sms_from_a_verified_phone_matches_only_its_owner(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    phone = mobile()
    citizen, user_id = await verified_citizen(client, make_token, session, phone)
    # Someone else's app report with the same prefix and category nearby.
    stranger = device_headers()
    await accept_charter(client, stranger)
    client_uuid, pre = prefix()
    theirs = (await client.post("/api/v1/reports", json=report_body(client_uuid=client_uuid), headers=stranger)).json()
    r = await send_sms(client, phone, f"EH1 fire {SFAX_SMS} 8m {pre}")
    assert r.json()["status"] == "created" and r.json()["tracking_code"] != theirs["tracking_code"]
    owner = await session.scalar(
        text("SELECT user_id FROM reports.report WHERE tracking_code = :c"), {"c": r.json()["tracking_code"]}
    )
    assert owner == user_id

    # The citizen's app then syncs that report: the SMS report is adopted (one report, one tracking code).
    other_uuid = pre + str(uuid.uuid4())[8:]
    synced = await client.post("/api/v1/reports", json=report_body(client_uuid=other_uuid), headers=citizen)
    assert synced.status_code == 200, synced.text
    assert synced.json()["tracking_code"] == r.json()["tracking_code"]
    assert synced.json()["text"] == "دخان كثيف قرب المخزن"
    mine = (await client.get("/api/v1/reports/mine", headers=citizen)).json()["items"]
    assert [m["tracking_code"] for m in mine] == [r.json()["tracking_code"]]
    # Replays of that client_uuid answer the same report.
    replay = await client.post("/api/v1/reports", json=report_body(client_uuid=other_uuid), headers=citizen)
    assert replay.status_code == 200 and replay.json()["id"] == synced.json()["id"]


async def test_sms_first_then_anonymous_app_sync(client: httpx.AsyncClient, session: AsyncSession) -> None:
    client_uuid, pre = prefix()
    r = await send_sms(client, mobile(), f"EH1 fire {SFAX_SMS} 0m {pre}")
    assert r.json()["status"] == "created"
    device = device_headers()
    await accept_charter(client, device)
    # Other category: a new report.
    flood = await client.post(
        "/api/v1/reports", json=report_body(client_uuid=pre + str(uuid.uuid4())[8:], category="flood"), headers=device
    )
    assert flood.status_code == 201
    synced = await client.post("/api/v1/reports", json=report_body(client_uuid=client_uuid), headers=device)
    assert synced.status_code == 200 and synced.json()["tracking_code"] == r.json()["tracking_code"]
    accuracy = await session.scalar(
        text("SELECT location_accuracy_m FROM reports.report WHERE id = :i"), {"i": synced.json()["id"]}
    )
    assert accuracy == 8.0  # the app's precise fix replaces the SMS position of unknown accuracy


async def test_sms_rate_limited_per_sender(client: httpx.AsyncClient) -> None:
    sender = mobile()
    for _ in range(10):
        await send_sms(client, sender, "hello")
    r = await send_sms(client, sender, f"EH1 fire {SFAX_SMS} 8m {prefix()[1]}")
    assert r.json() == {"status": "ignored", "tracking_code": None, "reason": "rate_limited"}


# ---------------------------------------------------------------- simulation endpoint


async def test_sim_calls_endpoint(client: httpx.AsyncClient, session: AsyncSession) -> None:
    assert (await client.get("/internal/sim/calls")).status_code == 404
    channel_id = await ringing(source="sim")
    r = await client.get("/internal/sim/calls", headers=SIM)
    assert r.status_code == 200 and r.json()["simulated"] is True
    call = await call_row(session, channel_id)
    assert str(call.id) in {c["id"] for c in r.json()["items"]}
    await destroyed(channel_id)


# ---------------------------------------------------------------- citizen rights and retention


async def test_export_and_delete(client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession) -> None:
    phone = mobile()
    citizen, user_id = await verified_citizen(client, make_token, session, phone)
    channel_id = await ringing(phone)
    sms_reply = await send_sms(client, phone, f"EH1 fire {SFAX_SMS} 8m {prefix()[1]}")
    assert sms_reply.json()["status"] == "created"
    export = (await client.get("/api/v1/me/export", headers=citizen)).json()
    call = await call_row(session, channel_id)
    assert [c["id"] for c in export["calls"]] == [str(call.id)]
    assert len(export["sms"]) == 1 and export["sms"][0]["outcome"] == "created"
    assert phone not in json.dumps(export["calls"])

    r = await client.post("/api/v1/me/delete", json={"confirm": "DELETE"}, headers=citizen)
    assert r.status_code == 202
    detached = await call_row(session, channel_id)
    assert detached.caller_number is None and detached.caller_hash is None
    left = await session.scalar(
        text("SELECT count(*) FROM telephony.sms_inbound WHERE sender_hash = :h"), {"h": sms.sender_hash(phone)}
    )
    assert left == 0
    details = await session.scalar(
        text("SELECT details FROM audit.log WHERE action = 'user.delete' AND target = :t"),
        {"t": f"account:{user_id}"},
    )
    assert details["calls_detached"] == 1 and details["sms_detached"] == 1
    await destroyed(channel_id)


async def test_retention_purges_old_calls(session: AsyncSession, fake_store: FakeStore) -> None:
    old, recent = await ringing(), await ringing()
    await destroyed(old)
    await destroyed(recent)
    key = f"calls/{uuid.uuid4()}.wav"
    fake_store.objects[key] = b"x"
    media_id = await session.scalar(
        text(
            "INSERT INTO reports.media (kind, object_key, sha256, bytes, content_type, status) "
            "VALUES ('call_recording', :k, :s, 1, 'audio/wav', 'stored') RETURNING id"
        ),
        {"k": key, "s": "0" * 64},
    )
    await session.execute(
        text(
            "UPDATE telephony.call SET started_at = now() - interval '3 years', ended_at = now() - interval '3 years', "
            "recording_media_id = :m, recording_state = 'done' WHERE channel_id = :c"
        ),
        {"m": media_id, "c": old},
    )
    await session.commit()
    assert ("calls", telephony_retention.purge_calls) in retention.JOBS
    assert await retention.run_job(get_system_sessionmaker(), "calls", telephony_retention.purge_calls) >= 1
    remaining = set(
        await session.scalars(
            text("SELECT channel_id FROM telephony.call WHERE channel_id IN (:a, :b)"), {"a": old, "b": recent}
        )
    )
    assert remaining == {recent}
    assert key in fake_store.deleted
    assert await session.scalar(text("SELECT count(*) FROM reports.media WHERE id = :m"), {"m": media_id}) == 0


async def test_calls_not_recorded_when_recording_is_disabled(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The dialplan says whether it records (TELEPHONY_RECORDING_ENABLED of the telephony container) ...
    channel_id = channel()
    await call_event(channel_id, "ringing", number=mobile(), source="trunk", recording="0")
    assert (await call_row(session, channel_id)).recording_state == "none"
    await destroyed(channel_id)
    assert (await call_row(session, channel_id)).recording_state == "none"
    # ... and without that field the API's own setting decides.
    monkeypatch.setattr(get_settings(), "telephony_recording_enabled", False)
    other = await ringing()
    assert (await call_row(session, other)).recording_state == "none"
    await destroyed(other)


def test_call_retention_is_at_most_two_years() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings

    assert get_settings().retention_call_days == 730
    with pytest.raises(ValidationError):
        Settings(_env_file=None, retention_call_days=731)  # type: ignore[call-arg]


def test_recording_is_opt_in_in_production() -> None:
    from tests.test_production_settings import production

    assert production(telephony_recording_enabled="").telephony_recording_enabled is False
    assert production(telephony_recording_enabled="true").telephony_recording_enabled is True
    assert production().telephony_transfer_198_enabled is False
